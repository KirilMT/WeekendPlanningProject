from flask import Flask, request, jsonify, send_from_directory
import os
import json
from jinja2 import Environment, FileSystemLoader
from extract_data import extract_data, get_current_day
from math import ceil
import re
from itertools import combinations
import numpy as np
import pandas as pd
import traceback  # Added for detailed traceback logging
import random

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'Uploads'
app.config['OUTPUT_FOLDER'] = 'output'

env = Environment(loader=FileSystemLoader('templates'))

# Store uploaded file paths temporarily
uploaded_files = {}

# Load technician mappings
try:
    print(f"Current working directory: {os.getcwd()}")
    with open('technician_mappings.json', 'r', encoding='utf-8') as f:
        mappings = json.load(f)
    if 'technicians' not in mappings:
        raise ValueError("Error: 'technicians' key missing in technician_mappings.json")
    technicians_data = mappings['technicians']
    TECHNICIAN_TASKS = {}  # Stores {'tech_name': [{'task': 'task_str', 'prio': 1}, ...]}
    TECHNICIAN_LINES = {}
    TECHNICIANS = list(technicians_data.keys())
    valid_groups = {"Fuchsbau", "Closures", "Aquarium"}
    for tech, data in technicians_data.items():
        if not isinstance(data, dict):
            raise ValueError(f"Error: Invalid data for technician '{tech}'")
        if 'sattelite_point' not in data or data['sattelite_point'] not in valid_groups:
            raise ValueError(f"Error: Invalid 'sattelite_point' for technician '{tech}'")
        # Changed 'technician_tasks' to 'task_assignments'
        if 'technician_lines' not in data or 'task_assignments' not in data:
            raise ValueError(f"Error: Missing 'technician_lines' or 'task_assignments' for technician '{tech}'")

        # Validate task_assignments structure
        if not isinstance(data['task_assignments'], list):
            raise ValueError(f"Error: 'task_assignments' for technician '{tech}' must be a list.")
        for task_assignment in data['task_assignments']:
            if not isinstance(task_assignment, dict) or 'task' not in task_assignment or 'prio' not in task_assignment:
                raise ValueError(
                    f"Error: Invalid item in 'task_assignments' for technician '{tech}'. Expected {{'task': ..., 'prio': ...}}.")
            if not isinstance(task_assignment['prio'], int) or task_assignment['prio'] < 1:
                if not (isinstance(task_assignment['prio'], float) and task_assignment['prio'].is_integer() and
                        task_assignment['prio'] >= 1):  # allow float if it's an int
                    raise ValueError(
                        f"Error: Invalid 'prio' value '{task_assignment['prio']}' in 'task_assignments' for technician '{tech}'. Must be a positive integer.")
            task_assignment['prio'] = int(task_assignment['prio'])

        TECHNICIAN_TASKS[tech] = data['task_assignments']
        TECHNICIAN_LINES[tech] = data['technician_lines']
    TECHNICIAN_GROUPS = {"Fuchsbau": [], "Closures": [], "Aquarium": []}
    for tech, data in technicians_data.items():
        TECHNICIAN_GROUPS[data['sattelite_point']].append(tech)
except FileNotFoundError:
    print("Error: 'technician_mappings.json' not found")
    raise ValueError("Error: 'technician_mappings.json' not found")
except Exception as e:
    print(f"Error loading 'technician_mappings.json': {str(e)}")
    raise ValueError(f"Error loading 'technician_mappings.json': {str(e)}")

# Task name mapping
TASK_NAME_MAPPING = {
    "BiW_PM_Tunkers Piercing Unit_Weekly_RSP": "BiW_PM_Tünkers Piercing Unit_Wöchentlich_RSP",
    "BiW_PM_Laser Absauger_6 Monthly Inspection": "BiW_PM_Laser Absauger_6 Monatlich Inspektion",
    "BiW_PM_KUKA_Roboter Quantec_10 Years GWA": "BiW_PM_KUKA_Roboter Quantec_10 Jahre GWA",
    "BiW_PM_Vigel_10 Yearly TÜV Check": "BiW_PM_Vigel_10 Jährlich TÜV Prüfung der Druckanlage",
    "BiW_PM_Dalmec Manipulator_Quarterly": "BiW_PM_Dalmec Manipulator_Viertaljährlich",
    "RSW_Visual Checks + Mastering": "RSW_Visual checks + Mastering & Force & Current calibration_New Lines",
    "BiW_PM_Kappenfräser_3 Monthly_All": "BiW_PM_Kappenfräser_3 monatlich_Alle",
    "BiW_PM_Leitungspaket": "BiW_PM_Leitungspaket",
    "BIW_PdM_RSW_C-Factor": "BIW_PdM_RSW_C-Factor"
}


def calculate_work_time(day):
    return {"Monday": 434, "Friday": 434, "Sunday": 651, "Saturday": 651}.get(day, 434)


def normalize_string(s):
    if not s or not isinstance(s, str):
        return ""
    s = s.lower().strip()
    s = re.sub(r'\s+', ' ', s)
    s = s.replace('Ã¼', 'u').replace('Ã¶', 'o').replace('Ã¤', 'a').replace('ÃŸ', 'ss')
    s = s.replace('ü', 'u').replace('ö', 'o').replace('ä', 'a').replace('ß', 'ss')
    s = s.replace('jährlich', 'yearly').replace('viertaljährlich', 'quarterly').replace('monatlich', 'monthly')
    s = s.replace('wöchentlich', 'weekly').replace('prüfung', 'check').replace('inspektion', 'inspection')
    s = s.replace('der druckanlage', '').replace('alle', 'all').replace('jahre', 'years')
    return s


def calculate_available_time(assignments, present_technicians, total_work_minutes):
    available_time = {tech: total_work_minutes for tech in present_technicians}
    for assignment in assignments:
        tech = assignment['technician']
        duration = assignment['duration']
        available_time[tech] -= duration
    return available_time


def is_valid_number(value):
    """Check if a value can be converted to a positive integer."""
    if value is None or value == '' or pd.isna(value):
        return False
    try:
        num = float(str(value).replace(',', '.').strip())
        return num > 0 and num.is_integer()
    except (ValueError, TypeError):
        return False


def sanitize_data(data):
    """Preprocess Excel data to ensure all required fields are valid."""
    sanitized_data = []
    required_fields = ['scheduler_group_task', 'task_type', 'priority']
    numeric_fields = ['planned_worktime_min', 'mitarbeiter_pro_aufgabe', 'quantity']

    for idx, row in enumerate(data):
        sanitized_row = row.copy() if isinstance(row, dict) else {}
        task_name = row.get('scheduler_group_task', 'Unknown')

        # Ensure required fields have defaults
        for field in required_fields:
            if field not in sanitized_row or sanitized_row[field] is None or pd.isna(sanitized_row[field]):
                sanitized_row[field] = 'Unknown' if field == 'scheduler_group_task' else (
                    'C' if field == 'priority' else '')
                print(f"Warning: Missing or invalid {field} for task {task_name} at row {idx + 1}, set to default")

        # Sanitize numeric fields
        for field in numeric_fields:
            value = sanitized_row.get(field)
            if not is_valid_number(value):
                default = '1' if field in ['mitarbeiter_pro_aufgabe', 'quantity'] else '0'
                print(f"Warning: Invalid {field}='{value}' for task {task_name} at row {idx + 1}, setting to {default}")
                sanitized_row[field] = default
            else:
                sanitized_row[field] = str(int(float(str(value).replace(',', '.'))))

        # Handle optional fields
        sanitized_row['lines'] = sanitized_row.get('lines', '')
        sanitized_row['ticket_mo'] = sanitized_row.get('ticket_mo', '')
        sanitized_row['ticket_url'] = sanitized_row.get('ticket_url', '')

        sanitized_data.append(sanitized_row)

    print(f"Sanitized {len(sanitized_data)} rows from {len(data)} input rows")
    return sanitized_data


def validate_assignments(assignments):
    """Validate assignments to ensure all required fields are present and valid."""
    valid_assignments = []
    for idx, assignment in enumerate(assignments):
        if not isinstance(assignment, dict):
            print(f"Warning: Invalid assignment at index {idx}: not a dictionary")
            continue
        required_fields = ['technician', 'task_name', 'start', 'duration', 'instance_id']
        for field in required_fields:
            if field not in assignment or assignment[field] is None:
                print(f"Warning: Missing or None {field} in assignment at index {idx}: {assignment}")
                break
        else:
            try:
                start = float(assignment['start'])
                duration = float(assignment['duration'])
                if start < 0 or duration <= 0:
                    print(
                        f"Warning: Invalid start={start} or duration={duration} in assignment at index {idx}: {assignment}")
                    continue
                if not isinstance(assignment['instance_id'], str) or '_' not in assignment['instance_id']:
                    print(
                        f"Warning: Invalid instance_id='{assignment['instance_id']}' in assignment at index {idx}: {assignment}")
                    continue
                task_id_part = assignment['instance_id'].split('_')[0]
                int(task_id_part)  # Ensure task_id is a valid integer
                valid_assignments.append(assignment)
            except (ValueError, TypeError) as e:
                print(f"Warning: Invalid assignment at index {idx}: {str(e)} - {assignment}")
    print(f"Validated {len(valid_assignments)} assignments from {len(assignments)}")
    return valid_assignments


def assign_tasks(tasks, present_technicians, total_work_minutes, rep_assignments=None):
    print(
        f"Assigning {len(tasks)} tasks with {len(present_technicians)} technicians. Total work minutes: {total_work_minutes}")
    filtered_tasks = [task for task in tasks if task.get('task_type', '').upper() in ['PM', 'REP']]

    priority_order = {'A': 1, 'B': 2, 'C': 3}  # Excel priority
    pm_tasks = sorted(
        [task for task in filtered_tasks if task['task_type'].upper() == 'PM'],
        key=lambda x: priority_order.get(str(x.get('priority', 'C')).upper(), 4)  # Use .get for safety
    )
    rep_tasks = [task for task in filtered_tasks if task['task_type'].upper() == 'REP']
    rep_assignments_dict = {item['task_id']: item for item in rep_assignments} if rep_assignments else {}

    technician_schedules = {tech: [] for tech in present_technicians}
    all_task_assignments = []  # This will store lists of assignments, one list per task instance
    unassigned_tasks_ids = []
    incomplete_tasks_ids = []

    # Create a set of normalized names of all PM tasks from the current Excel input
    # This is used to efficiently check if a technician's defined task is "active"
    all_pm_tasks_from_excel_normalized_names_set = {
        normalize_string(TASK_NAME_MAPPING.get(t['name'], t['name'])) for t in pm_tasks
    }

    # --- Process PM tasks with new priority logic ---
    for task in pm_tasks:  # task is current_excel_task
        task_name_from_excel = task.get('name', 'Unknown')
        task_id = task['id']
        print(f"\nProcessing PM Task: {task_name_from_excel} (ID: {task_id})")

        base_duration = int(task.get('planned_worktime_min', 0))
        num_technicians_needed = int(task.get('mitarbeiter_pro_aufgabe', 1))
        quantity = int(task.get('quantity', 1))

        if base_duration <= 0 or num_technicians_needed <= 0 or quantity <= 0:
            print(
                f"  Skipping task {task_name_from_excel}: Invalid parameters (duration: {base_duration}, needed: {num_technicians_needed}, qty: {quantity})")
            for i in range(quantity):
                unassigned_tasks_ids.append(f"{task_id}_{i + 1}")
            continue

        json_task_name_lookup = TASK_NAME_MAPPING.get(task_name_from_excel, task_name_from_excel)
        normalized_current_excel_task_name = normalize_string(json_task_name_lookup)

        task_lines_str = str(task.get('lines', ''))
        task_lines = []
        if task_lines_str and task_lines_str != 'nan':
            try:
                task_lines = [int(line.strip()) for line in task_lines_str.split(',') if line.strip().isdigit()]
            except ValueError:
                print(f"  Warning: Invalid line format '{task_lines_str}' for task {task_name_from_excel}")

        eligible_technicians_details = []
        for tech_candidate in present_technicians:
            # CORRECTED LINE: Use TECHNICIAN_TASKS instead of TECHNICIAN_TASK_ASSIGNMENTS
            tech_task_definitions_for_candidate = TECHNICIAN_TASKS.get(tech_candidate, [])
            tech_lines_for_candidate = TECHNICIAN_LINES.get(tech_candidate, [])

            candidate_stated_prio_for_current_task = None
            can_do_current_task_flag = False

            # Check if tech_candidate can do the current_excel_task and get their stated priority for it
            for tech_task_obj in tech_task_definitions_for_candidate:
                normalized_tech_task_string = normalize_string(tech_task_obj['task'])
                if (normalized_current_excel_task_name in normalized_tech_task_string or
                        normalized_tech_task_string in normalized_current_excel_task_name):
                    if not task_lines or any(line in tech_lines_for_candidate for line in task_lines):
                        can_do_current_task_flag = True
                        candidate_stated_prio_for_current_task = tech_task_obj['prio']
                        break

            if can_do_current_task_flag and candidate_stated_prio_for_current_task is not None:
                # Calculate effective priority
                active_task_prios_for_tech = []
                for tech_json_task_def in tech_task_definitions_for_candidate:
                    norm_tech_json_task_name = normalize_string(tech_json_task_def['task'])
                    # Check if this task from tech's JSON list is active in the current Excel run
                    is_this_json_task_active = False
                    for excel_task_norm_name_iter in all_pm_tasks_from_excel_normalized_names_set:
                        if norm_tech_json_task_name in excel_task_norm_name_iter or \
                                excel_task_norm_name_iter in norm_tech_json_task_name:
                            is_this_json_task_active = True
                            break
                    if is_this_json_task_active:
                        active_task_prios_for_tech.append(tech_json_task_def['prio'])

                effective_prio = candidate_stated_prio_for_current_task  # Default to stated
                if active_task_prios_for_tech:
                    sorted_unique_active_prios = sorted(list(set(active_task_prios_for_tech)))
                    try:
                        # Rank is 1-based index
                        effective_prio = sorted_unique_active_prios.index(candidate_stated_prio_for_current_task) + 1
                    except ValueError:
                        # This means candidate_stated_prio_for_current_task was not among its own active priorities.
                        # This could happen if current_excel_task was matched, but its prio wasn't added to active_task_prios_for_tech
                        # which implies a logic error in how active_task_prios_for_tech is populated or how candidate_stated_prio is found.
                        # For robustness, let's ensure candidate_stated_prio_for_current_task is in the list if the task is active.
                        # The current logic for active_task_prios_for_tech should include it.
                        # If it's truly not there, it's an anomaly. Fallback to stated.
                        print(
                            f"  Warning: Stated prio {candidate_stated_prio_for_current_task} for {tech_candidate} on {task_name_from_excel} "
                            f"not found in their calculated active prios {sorted_unique_active_prios}. Using stated prio as effective.")
                        effective_prio = candidate_stated_prio_for_current_task

                eligible_technicians_details.append({
                    'name': tech_candidate,
                    'prio_for_task': effective_prio,  # This is the new "effective" priority for sorting
                    'original_stated_prio': candidate_stated_prio_for_current_task  # For display
                })

        if not eligible_technicians_details:
            print(
                f"  Task {task_name_from_excel}: No eligible technicians found based on task name/lines (after effective prio calc).")
            for i in range(quantity):
                unassigned_tasks_ids.append(f"{task_id}_{i + 1}")
            continue

        # Sort eligible technicians by their new "effective" priority for this task
        eligible_technicians_details.sort(key=lambda x: x['prio_for_task'])

        # This map will now store both effective (for logic) and stated (for display)
        tech_prio_map = {
            detail['name']: {
                'effective': detail['prio_for_task'],
                'stated': detail['original_stated_prio']
            } for detail in eligible_technicians_details
        }
        # Get just the names, now sorted by effective task-specific priority
        sorted_eligible_tech_names = [detail['name'] for detail in eligible_technicians_details]

        if len(sorted_eligible_tech_names) < num_technicians_needed:
            print(
                f"  Task {task_name_from_excel}: Insufficient eligible technicians ({len(sorted_eligible_tech_names)}/{num_technicians_needed}) after effective priority sort.")
            for i in range(quantity):
                unassigned_tasks_ids.append(f"{task_id}_{i + 1}")
            continue

        viable_groups_with_scores = []
        for r in range(num_technicians_needed, len(sorted_eligible_tech_names) + 1):
            for group_tuple in combinations(sorted_eligible_tech_names, r):
                group = list(group_tuple)
                # Calculate average "effective" task-specific priority for the groupapp
                avg_effective_prio = sum(
                    tech_prio_map.get(tech, {}).get('effective', float('inf')) for tech in group) / len(
                    group) if group else float('inf')
                current_workload = sum(
                    sum(end - start for start, end, _ in technician_schedules[tech_name]) for tech_name in group)

                viable_groups_with_scores.append({
                    'group': group,
                    'len': len(group),
                    'avg_prio': avg_effective_prio,  # Using effective priority for sorting groups
                    'workload': current_workload
                })

        # Sort groups: 1. by size, 2. by average *effective* task-specific priority, 3. random, 4. workload
        viable_groups_with_scores.sort(key=lambda x: (
            abs(x['len'] - num_technicians_needed),
            x['avg_prio'],  # This is now the average of "effective" priorities
            random.random(),  # Added for tie-breaking among equally good effective prio groups
            x['workload']
        ))

        viable_groups_sorted = [item['group'] for item in viable_groups_with_scores]

        for instance_num in range(1, quantity + 1):
            instance_id = f"{task_id}_{instance_num}"
            instance_task_name = f"{task_name_from_excel} (Instance {instance_num}/{quantity})"
            assigned_this_instance = False
            instance_assignments = []

            for group in viable_groups_sorted:
                missing_technicians = max(0, num_technicians_needed - len(group))
                task_duration_for_group = base_duration * (1 + missing_technicians)
                start_time = 0

                while start_time <= total_work_minutes - task_duration_for_group:
                    all_available_in_group = all(
                        all(sch_end <= start_time or sch_start >= start_time + task_duration_for_group
                            for sch_start, sch_end, _ in technician_schedules[tech_in_group])
                        for tech_in_group in group
                    )

                    if all_available_in_group:
                        is_incomplete = False
                        current_instance_duration = task_duration_for_group
                        if start_time + task_duration_for_group > total_work_minutes:
                            current_instance_duration = total_work_minutes - start_time
                            is_incomplete = True
                            incomplete_tasks_ids.append(instance_id)

                        technicians_for_assignment = group[:num_technicians_needed]

                        for tech_assigned in technicians_for_assignment:
                            technician_schedules[tech_assigned].append(
                                (start_time, start_time + current_instance_duration, instance_task_name))

                            # For display, use the original stated priority
                            original_stated_prio_for_display = tech_prio_map.get(tech_assigned, {}).get('stated', 'N/A')

                            assignment_detail = {
                                'technician': tech_assigned,
                                'task_name': instance_task_name,
                                'start': start_time,
                                'duration': current_instance_duration,
                                'is_incomplete': is_incomplete,
                                'original_duration': task_duration_for_group,
                                'instance_id': instance_id,
                                'technician_task_priority': original_stated_prio_for_display
                            }
                            instance_assignments.append(assignment_detail)

                        assigned_tech_names_with_display_prio = [
                            f"{tech_assigned} (Prio: {tech_prio_map.get(tech_assigned, {}).get('stated', 'N/A')})"
                            for tech_assigned in technicians_for_assignment
                        ]
                        print(
                            f"  Assigned {instance_task_name} to {', '.join(assigned_tech_names_with_display_prio)} at {start_time} for {current_instance_duration}min.")
                        assigned_this_instance = True
                        break
                    start_time += 15

                if assigned_this_instance:
                    all_task_assignments.append(instance_assignments)
                    break

            if not assigned_this_instance:
                print(f"  Could not schedule {instance_task_name}")
                unassigned_tasks_ids.append(instance_id)
                all_task_assignments.append([])

    # Process REP tasks (logic remains largely the same, no technician_task_priority needed in assignment dict)
    # Flatten PM assignments to correctly calculate available time for REP tasks
    flat_pm_assignments_for_rep_time_calc = [item for sublist in all_task_assignments for item in sublist]

    available_time_for_rep = {tech: total_work_minutes for tech in present_technicians}
    for assignment_detail in flat_pm_assignments_for_rep_time_calc:
        tech = assignment_detail['technician']
        duration = assignment_detail['duration']
        if tech in available_time_for_rep: # Ensure tech is in the dict
            available_time_for_rep[tech] -= duration


    for task in rep_tasks:
        task_name = task.get('name', 'Unknown')
        task_id = task['id']
        print(f"Processing REP task: {task_name} (ID: {task_id})")

        base_duration = int(task['planned_worktime_min']) if is_valid_number(task['planned_worktime_min']) else 0
        num_technicians_needed = int(task['mitarbeiter_pro_aufgabe']) if is_valid_number(
            task['mitarbeiter_pro_aufgabe']) else 1
        quantity = int(task['quantity']) if is_valid_number(task['quantity']) else 1

        if base_duration <= 0 or num_technicians_needed <= 0 or quantity <= 0:
            print(
                f"Skipping task {task_name}: invalid or zero duration={base_duration}, technicians={num_technicians_needed}, or quantity={quantity}")
            for i in range(quantity):
                unassigned_tasks_ids.append(f"{task_id}_{i + 1}") # Corrected variable name
            continue

        task_lines = []
        try:
            if task.get('lines'):
                task_lines = [int(line.strip()) for line in str(task['lines']).split(',') if line.strip().isdigit()]
        except (ValueError, TypeError):
            print(f"Warning: Invalid lines format for task {task_name}")

        eligible_rep_technicians_for_task = []
        if task_id in rep_assignments_dict and not rep_assignments_dict[task_id].get('skipped'):
            selected_techs = rep_assignments_dict[task_id]['technicians']
            for tech in selected_techs:
                if tech in present_technicians and available_time_for_rep.get(tech, 0) >= base_duration:
                    if not task_lines or any(line in TECHNICIAN_LINES.get(tech, []) for line in task_lines):
                        eligible_rep_technicians_for_task.append(tech)
        else:
            print(f"Task {task_name} skipped or unassigned in REP pre-assignment phase")
            for i in range(quantity):
                unassigned_tasks_ids.append(f"{task_id}_{i + 1}") # Corrected variable name
            continue

        if len(eligible_rep_technicians_for_task) < num_technicians_needed:
            print(
                f"Task {task_name}: insufficient eligible/selected technicians for REP ({len(eligible_rep_technicians_for_task)}/{num_technicians_needed})")
            for i in range(quantity):
                unassigned_tasks_ids.append(f"{task_id}_{i + 1}") # Corrected variable name
            continue

        viable_groups = [list(group) for r in range(num_technicians_needed, len(eligible_rep_technicians_for_task) + 1)
                         for group in combinations(eligible_rep_technicians_for_task, r)]
        viable_groups.sort(key=lambda group: (len(group), sum(
            sum(end - start for start, end, _ in technician_schedules[tech]) for tech in group)))

        for instance_num in range(1, quantity + 1):
            instance_id = f"{task_id}_{instance_num}"
            instance_task_name = f"{task_name} (Instance {instance_num}/{quantity})"
            assigned = False
            instance_assignments_rep = [] # To store assignments for this REP instance

            for group in viable_groups:
                missing_technicians = max(0, num_technicians_needed - len(group))
                task_duration = base_duration * (1 + missing_technicians)
                start_time = 0

                while start_time <= total_work_minutes - task_duration:
                    all_available = all(
                        all(end <= start_time or start >= start_time + task_duration
                            for start, end, _ in technician_schedules[tech])
                        for tech in group
                    )
                    if all_available:
                        is_incomplete = False
                        original_task_duration = task_duration
                        current_instance_duration_rep = task_duration # Use a distinct name
                        if start_time + task_duration > total_work_minutes:
                            current_instance_duration_rep = total_work_minutes - start_time
                            is_incomplete = True
                            incomplete_tasks_ids.append(instance_id) # Corrected variable name

                        technicians_for_assignment_rep = group[:num_technicians_needed] # Distinct name

                        for tech in technicians_for_assignment_rep: # Use distinct name
                            technician_schedules[tech].append(
                                (start_time, start_time + current_instance_duration_rep, instance_task_name))
                            assignment_detail_rep = { # Distinct name
                                'technician': tech,
                                'task_name': instance_task_name,
                                'start': start_time,
                                'duration': current_instance_duration_rep,
                                'is_incomplete': is_incomplete,
                                'original_duration': original_task_duration,
                                'instance_id': instance_id,
                                'ticket_mo': task.get('ticket_mo', ''),
                                'ticket_url': task.get('ticket_url', '')
                            }
                            instance_assignments_rep.append(assignment_detail_rep)
                            available_time_for_rep[tech] -= current_instance_duration_rep

                        print(f"Assigned {instance_task_name} to {technicians_for_assignment_rep} at {start_time}")
                        assigned = True
                        break
                    start_time += 15

                if assigned:
                    all_task_assignments.append(instance_assignments_rep) # Add this instance's assignments
                    break

            if not assigned:
                print(f"Could not schedule {instance_task_name}")
                unassigned_tasks_ids.append(instance_id) # Corrected variable name
                all_task_assignments.append([]) # Add empty list for unassigned REP instance


    # Flatten all_task_assignments for returning and further processing
    final_assignments_flat = [item for sublist in all_task_assignments for item in sublist]

    # Recalculate final available_time based on all assignments
    final_available_time = {tech: total_work_minutes for tech in present_technicians}
    for assignment_detail in final_assignments_flat:
        tech = assignment_detail['technician']
        duration = assignment_detail['duration']
        if tech in final_available_time:
            final_available_time[tech] -= duration

    return final_assignments_flat, unassigned_tasks_ids, incomplete_tasks_ids, final_available_time


def generate_html_files(data, present_technicians, rep_assignments=None):
    try:
        print("Starting generate_html_files")
        sanitized_data = sanitize_data(data)
        print(f"Sanitized data: {len(sanitized_data)} tasks")

        tasks = []
        for idx, row in enumerate(sanitized_data, start=1):
            task = {
                "id": str(idx),
                "name": row.get("scheduler_group_task", "Unknown"),
                "lines": row.get("lines", ""),
                "mitarbeiter_pro_aufgabe": row.get("mitarbeiter_pro_aufgabe", "1"),
                "planned_worktime_min": row.get("planned_worktime_min", "0"),
                "start": "2025-04-21",
                "end": "2025-04-22",
                "progress": 100 if row.get("quantity", "1").lower() == "done" else 0,
                "priority": row.get("priority", "C"),
                "quantity": row.get("quantity", "1"),
                "task_type": row.get("task_type", ""),
                "ticket_mo": row.get("ticket_mo", ""),
                "ticket_url": row.get("ticket_url", "")
            }
            tasks.append(task)
        print(f"Created {len(tasks)} tasks")

        current_day = get_current_day()
        total_work_minutes = calculate_work_time(current_day)
        num_intervals = ceil(total_work_minutes / 15)
        print(f"Total work minutes: {total_work_minutes}, Num intervals: {num_intervals}")

        assignments, unassigned_tasks, incomplete_tasks, available_time = assign_tasks(tasks, present_technicians,
                                                                                       total_work_minutes,
                                                                                       rep_assignments)
        print(
            f"Generated {len(assignments)} assignments, {len(unassigned_tasks)} unassigned, {len(incomplete_tasks)} incomplete")

        # Validate assignments before rendering
        assignments = validate_assignments(assignments)

        print("Loading technician_dashboard.html template")
        technician_template = env.get_template('technician_dashboard.html')
        print("Rendering template")
        technician_html = technician_template.render(
            tasks=tasks,
            technicians=present_technicians,
            total_work_minutes=total_work_minutes,
            num_intervals=num_intervals,
            assignments=assignments,
            unassigned_tasks=unassigned_tasks,
            incomplete_tasks=incomplete_tasks
        )
        print("Template rendered successfully")

        output_path = os.path.join(app.config['OUTPUT_FOLDER'], "technician_dashboard.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(technician_html)
        print(f"Written output to {output_path}")

        return available_time
    except Exception as e:
        print(f"Error in generate_html_files: {str(e)}")
        print(traceback.format_exc())
        raise


@app.route('/')
def index():
    with open('templates/index.html', 'r', encoding='utf-8') as f:
        return f.read()


@app.route('/upload', methods=['POST'])
def upload_file():
    session_id = request.form.get('session_id', '')
    if 'excelFile' in request.files and request.files['excelFile'].filename != '':
        file = request.files['excelFile']
        if file.filename == '':
            return jsonify({"message": "No file selected"}), 400
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)
        uploaded_files[session_id] = file_path
        try:
            data = extract_data(file_path)
            sanitized_data = sanitize_data(data)
            if not sanitized_data:
                return jsonify({
                    "message": "No valid data found after sanitization. Check if the Summary KW17 sheet contains valid tasks."
                }), 400

            rep_tasks = [
                task | {'id': str(idx + 1)}
                for idx, task in enumerate(sanitized_data)
                if task.get('task_type', '').upper() == 'REP' and task.get('ticket_mo') and str(
                    task.get('ticket_mo')) != 'nan'
            ]
            return jsonify({
                "message": "File uploaded successfully. Please select absent technicians.",
                "repTasks": rep_tasks,
                "filename": file.filename,
                "session_id": session_id
            })
        except Exception as e:
            print(f"Error processing file upload: {str(e)}")
            print(traceback.format_exc())
            return jsonify({"message": f"Error processing file: {str(e)}"}), 500

    if 'filename' in request.form and session_id in uploaded_files:
        file_path = uploaded_files[session_id]
        if not os.path.exists(file_path):
            return jsonify({"message": "Uploaded file not found on server"}), 400
        try:
            data = extract_data(file_path)
            sanitized_data = sanitize_data(data)
            if not sanitized_data:
                return jsonify({
                    "message": "No valid data found after sanitization. Check if the Summary KW17 sheet contains valid tasks."
                }), 400

            absent_technicians = json.loads(request.form.get('absentTechnicians', '[]'))
            present_technicians = [tech for tech in TECHNICIANS if tech not in absent_technicians]

            if 'repAssignments' in request.form:
                rep_assignments_list = json.loads(request.form['repAssignments'])
                available_time = generate_html_files(sanitized_data, present_technicians, rep_assignments_list)
                if session_id in uploaded_files:
                    try:  # Attempt to delete, but don't fail hard if it's already gone
                        del uploaded_files[session_id]
                    except KeyError:
                        print(f"Session ID {session_id} already removed from uploaded_files.")
                return jsonify({
                    "message": "Technician dashboard generated successfully! Check the output folder for technician_dashboard.html.",
                    "availableTime": available_time
                })

            current_day = get_current_day()
            total_work_minutes = calculate_work_time(current_day)
            # Create task objects for assign_tasks, including an ID
            tasks_for_pm_processing = []
            for idx, row in enumerate(sanitized_data):
                tasks_for_pm_processing.append({
                    "id": str(idx + 1),  # Unique ID for processing
                    "name": row.get("scheduler_group_task", "Unknown"),
                    "lines": row.get("lines", ""),
                    "mitarbeiter_pro_aufgabe": row.get("mitarbeiter_pro_aufgabe", "1"),
                    "planned_worktime_min": row.get("planned_worktime_min", "0"),
                    "priority": row.get("priority", "C"),  # Excel priority A, B, C
                    "quantity": row.get("quantity", "1"),
                    "task_type": row.get("task_type", ""),
                    "ticket_mo": row.get("ticket_mo", ""),
                    "ticket_url": row.get("ticket_url", "")
                })

            pm_tasks_only = [task for task in tasks_for_pm_processing if task.get('task_type', '').upper() == 'PM']

            # Assign PM tasks first to calculate available time for REP tasks
            pm_assignments, _, _, available_time_after_pm = assign_tasks(pm_tasks_only,
                                                                         present_technicians,
                                                                         total_work_minutes,
                                                                         [])  # No rep_assignments yet

            rep_tasks_for_selection = [
                # Use original sanitized_data to build rep_tasks with their original index as ID
                # but ensure the ID is consistent with how REP tasks are identified later
                task_data | {'id': str(s_idx + 1)}  # s_idx is from enumerate(sanitized_data)
                for s_idx, task_data in enumerate(sanitized_data)
                if task_data.get('task_type', '').upper() == 'REP'
                and task_data.get('ticket_mo') and str(task_data.get('ticket_mo')) != 'nan'
            ]

            eligible_rep_technicians = {}
            for task_rep in rep_tasks_for_selection:
                base_duration = int(task_rep.get('planned_worktime_min', 0)) if is_valid_number(
                    task_rep.get('planned_worktime_min')) else 0

                current_tech_availability = {}
                # Recalculate available time based on PM assignments for each technician
                # This available_time_after_pm is crucial
                for tech_name in present_technicians:
                    current_tech_availability[tech_name] = available_time_after_pm.get(tech_name, total_work_minutes)

                eligible_technicians_for_this_rep_task = [
                    {"name": tech, "available_time": time_val}
                    for tech, time_val in current_tech_availability.items()  # Use the time after PMs
                    if time_val >= base_duration and tech in present_technicians
                ]
                eligible_rep_technicians[task_rep['id']] = eligible_technicians_for_this_rep_task

            return jsonify({
                "message": "PM tasks processed. Please assign technicians for REP tasks.",
                "repTasks": rep_tasks_for_selection,  # Send REP tasks that need selection
                "eligibleTechnicians": eligible_rep_technicians,
                "filename": os.path.basename(file_path),
                "session_id": session_id
            })
        except Exception as e:
            print(f"Error processing file: {str(e)}")
            print(traceback.format_exc())
            return jsonify({"message": f"Error processing file: {str(e)}"}), 500

    return jsonify({"message": "No file uploaded or invalid session"}), 400


@app.route('/technicians', methods=['GET'])
def get_technicians():
    return jsonify(TECHNICIAN_GROUPS)


@app.route('/output/<path:filename>')
def serve_output(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)


if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    if not os.path.exists(app.config['OUTPUT_FOLDER']):
        os.makedirs(app.config['OUTPUT_FOLDER'])
    app.run(debug=True, use_reloader=False)