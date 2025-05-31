from flask import Flask, request, jsonify, send_from_directory, render_template  # Added render_template
import os
import json
from jinja2 import Environment, FileSystemLoader
from extract_data import extract_data, get_current_day
from math import ceil
import re
from itertools import combinations
import numpy as np  # Retained as it was in your original file
import pandas as pd
import traceback
import random
import sqlite3  # Import sqlite3

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'Uploads'
app.config['OUTPUT_FOLDER'] = 'output'
app.config['DATABASE'] = 'weekend_planning.db'  # Define database file path

env = Environment(loader=FileSystemLoader('templates'))

# Store uploaded file paths temporarily
uploaded_files = {}


# --- Database Helper Functions ---
def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS technicians (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            sattelite_point TEXT,
            lines TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS technician_task_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            technician_id INTEGER NOT NULL,
            task_name TEXT NOT NULL,
            priority INTEGER NOT NULL,
            FOREIGN KEY (technician_id) REFERENCES technicians (id)
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_technician_task_assignments_technician_id
        ON technician_task_assignments (technician_id)
    ''')
    conn.commit()
    conn.close()
    print("Database initialized.")


# --- Configuration Loading ---
# These will be global and reloaded by load_app_config()
TECHNICIAN_TASKS = {}
TECHNICIAN_LINES = {}
TECHNICIANS = []
TECHNICIAN_GROUPS = {}
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


def load_app_config():
    global TECHNICIAN_TASKS, TECHNICIAN_LINES, TECHNICIANS, TECHNICIAN_GROUPS

    print(f"Attempting to load configuration from database: {os.path.abspath(app.config['DATABASE'])}") # Print absolute path
    TECHNICIAN_TASKS.clear()
    TECHNICIAN_LINES.clear()
    TECHNICIANS.clear()
    TECHNICIAN_GROUPS.clear()
    TECHNICIAN_GROUPS.update({"Fuchsbau": [], "Closures": [], "Aquarium": []})
    valid_groups = {"Fuchsbau", "Closures", "Aquarium"}

    conn = None  # Initialize conn to None for the finally block
    try:
        conn = get_db_connection()
        if conn:
            print("  Successfully connected to the database.")
        else:
            print("  Failed to get database connection.")
            return # Exit if connection failed

        cursor = conn.cursor()
        print("  Cursor created.")

        sql_query = "SELECT id, name, sattelite_point, lines FROM technicians ORDER BY name"
        print(f"  Executing query: {sql_query}")
        cursor.execute(sql_query)
        db_technicians = cursor.fetchall() # This is the critical point

        print(f"  Query executed. Number of rows fetched from 'technicians' table: {len(db_technicians)}") # VERY IMPORTANT DEBUG LINE

        if not db_technicians:
            print("  'technicians' table appears empty or query returned no results.")

        for row_idx, row in enumerate(db_technicians): # Added enumerate for row index
            tech_id = row['id']
            tech_name = row['name']
            sattelite_point = row['sattelite_point']
            lines_str = row['lines']
            print(f"    Processing DB row {row_idx + 1}: ID={tech_id}, Name='{tech_name}', Sattelite='{sattelite_point}', Lines='{lines_str}'")


            if not tech_name:
                print(f"      SKIPPING row {row_idx + 1} (ID {tech_id}): tech_name is empty or None.")
                continue
            if not sattelite_point:
                print(f"      SKIPPING row {row_idx + 1} (Name '{tech_name}', ID {tech_id}): sattelite_point is empty or None.")
                continue
            if sattelite_point not in valid_groups:
                print(f"      SKIPPING row {row_idx + 1} (Name '{tech_name}', ID {tech_id}): sattelite_point '{sattelite_point}' is not in valid_groups {valid_groups}.")
                continue

            TECHNICIANS.append(tech_name)
            TECHNICIAN_LINES[tech_name] = [int(l.strip()) for l in lines_str.split(',') if
                                           l.strip().isdigit()] if lines_str else []
            if sattelite_point in TECHNICIAN_GROUPS:
                TECHNICIAN_GROUPS[sattelite_point].append(tech_name)
            else:
                print(
                    f"    Warning: sattelite_point '{sattelite_point}' for technician '{tech_name}' (ID {tech_id}) is not a predefined group.")

            task_assignments_query = "SELECT task_name, priority FROM technician_task_assignments WHERE technician_id = ? ORDER BY priority ASC"
            # print(f"      Executing task assignments query for tech_id {tech_id}: {task_assignments_query}") # Optional: very verbose
            cursor.execute(task_assignments_query, (tech_id,))
            assignments_for_tech = []
            db_assignments = cursor.fetchall()
            # print(f"      Found {len(db_assignments)} task assignments for tech_id {tech_id}") # Optional: very verbose
            for assign_row in db_assignments:
                assignments_for_tech.append({'task': assign_row['task_name'], 'prio': assign_row['priority']})
            TECHNICIAN_TASKS[tech_name] = assignments_for_tech
            print(f"    SUCCESS: Loaded technician '{tech_name}' (ID {tech_id}) with {len(assignments_for_tech)} tasks.")

        print(f"Successfully loaded configuration for {len(TECHNICIANS)} technicians from database.")

    except sqlite3.Error as e:
        print(f"SQLite error during config load: {e}")
        print(traceback.format_exc())
    except Exception as e:
        print(f"General error loading configuration from database: {e}")
        print(traceback.format_exc())
    finally:
        if conn:
            print("  Closing database connection.")
            conn.close()
        else:
            print("  No active database connection to close.")


# Initialize DB and Load configuration on startup
init_db()
load_app_config()


def calculate_work_time(day):
    return {"Monday": 434, "Friday": 434, "Sunday": 651, "Saturday": 651}.get(day, 434)


def normalize_string(s):
    if not s or not isinstance(s, str):
        return ""
    s = s.lower().strip()
    s = re.sub(r'\s+', ' ', s)
    s = s.replace('Ã¼', 'u').replace('Ã¶', 'o').replace('Ã¤', 'a').replace('ÃŸ',
                                                                           'ss')  # Handle potential mis-encoding first
    s = s.replace('ü', 'u').replace('ö', 'o').replace('ä', 'a').replace('ß', 'ss')
    s = s.replace('jährlich', 'yearly').replace('viertaljährlich', 'quarterly').replace('monatlich', 'monthly')
    s = s.replace('wöchentlich', 'weekly').replace('prüfung', 'check').replace('inspektion', 'inspection')
    s = s.replace('der druckanlage', '').replace('alle', 'all').replace('jahre', 'years')
    return s


def calculate_available_time(assignments, present_technicians, total_work_minutes):
    available_time = {tech: total_work_minutes for tech in present_technicians}
    for assignment in assignments:  # Expects a flat list of assignment dicts
        tech = assignment['technician']
        duration = assignment['duration']
        if tech in available_time:
            available_time[tech] -= duration
        else:
            print(f"Warning: Technician {tech} from assignment not in available_time for calculation.")
    return available_time


def is_valid_number(value):
    """Check if a value can be converted to a positive integer."""
    if value is None or value == '' or pd.isna(value):
        return False
    try:
        num = float(str(value).replace(',', '.').strip())
        return num >= 0 and num.is_integer()  # Allow 0 for planned_worktime_min
    except (ValueError, TypeError):
        return False


def sanitize_data(data):
    """Preprocess Excel data to ensure all required fields are valid."""
    sanitized_data = []
    required_fields = ['scheduler_group_task', 'task_type', 'priority']
    # Ensure numeric fields are consistently converted to int
    numeric_fields_to_int = ['planned_worktime_min', 'mitarbeiter_pro_aufgabe', 'quantity']

    for idx, row in enumerate(data):
        sanitized_row = row.copy() if isinstance(row, dict) else {}
        task_name_original = row.get('scheduler_group_task', 'Unknown')

        for field in required_fields:
            if field not in sanitized_row or sanitized_row[field] is None or pd.isna(sanitized_row[field]):
                sanitized_row[field] = 'Unknown' if field == 'scheduler_group_task' else (
                    'C' if field == 'priority' else '')
                print(
                    f"Warning: Missing or invalid {field} for task '{task_name_original}' at row {idx + 1}, set to default '{sanitized_row[field]}'")

        for field in numeric_fields_to_int:
            value = sanitized_row.get(field)
            if not is_valid_number(value):  # is_valid_number now checks for positive integers, allow 0 for time
                default_val = 1 if field in ['mitarbeiter_pro_aufgabe', 'quantity'] else 0
                print(
                    f"Warning: Invalid {field}='{value}' for task '{task_name_original}' at row {idx + 1}, setting to {default_val}")
                sanitized_row[field] = default_val
            else:
                sanitized_row[field] = int(float(str(value).replace(',', '.')))

        sanitized_row['lines'] = str(sanitized_row.get('lines', ''))
        sanitized_row['ticket_mo'] = str(sanitized_row.get('ticket_mo', ''))
        sanitized_row['ticket_url'] = str(sanitized_row.get('ticket_url', ''))

        sanitized_data.append(sanitized_row)

    print(f"Sanitized {len(sanitized_data)} rows from {len(data)} input rows")
    return sanitized_data


def validate_assignments_flat_input(assignments_list):
    """Validate assignments to ensure all required fields are present and valid."""
    valid_assignments = []
    if not isinstance(assignments_list, list):
        print(f"Warning: validate_assignments_flat_input expects a list, got {type(assignments_list)}")
        return []

    for idx, assignment in enumerate(assignments_list):
        if not isinstance(assignment, dict):
            print(f"Warning: Invalid assignment at index {idx}: not a dictionary")
            continue
        required_fields = ['technician', 'task_name', 'start', 'duration', 'instance_id']
        missing_field = False
        for field in required_fields:
            if field not in assignment or assignment[field] is None:
                print(f"Warning: Missing or None {field} in assignment at index {idx}: {assignment}")
                missing_field = True
                break
        if missing_field:
            continue

        try:
            start = float(assignment['start'])
            duration = float(assignment['duration'])
            # Allow duration 0 if task is immediately capped or has 0 planned time
            if start < 0 or duration < 0:
                print(
                    f"Warning: Invalid start={start} or duration={duration} in assignment at index {idx}: {assignment}")
                continue
            if not isinstance(assignment['instance_id'], str) or '_' not in assignment['instance_id']:
                print(
                    f"Warning: Invalid instance_id='{assignment['instance_id']}' in assignment at index {idx}: {assignment}")
                continue
            task_id_part = assignment['instance_id'].split('_')[0]
            int(task_id_part)
            valid_assignments.append(assignment)
        except (ValueError, TypeError) as e:
            print(f"Warning: Invalid assignment at index {idx}: {str(e)} - {assignment}")
    print(f"Validated {len(valid_assignments)} assignments from {len(assignments_list)}")
    return valid_assignments


def assign_tasks(tasks, present_technicians, total_work_minutes, rep_assignments=None):
    print(
        f"Assigning {len(tasks)} tasks with {len(present_technicians)} technicians. Total work minutes: {total_work_minutes}")
    filtered_tasks = [task for task in tasks if task.get('task_type', '').upper() in ['PM', 'REP']]

    priority_order = {'A': 1, 'B': 2, 'C': 3}
    pm_tasks = sorted(
        [task for task in filtered_tasks if task['task_type'].upper() == 'PM'],
        key=lambda x: priority_order.get(str(x.get('priority', 'C')).upper(), 4)
    )
    rep_tasks = [task for task in filtered_tasks if task['task_type'].upper() == 'REP']
    rep_assignments_dict = {item['task_id']: item for item in rep_assignments} if rep_assignments else {}

    technician_schedules = {tech: [] for tech in present_technicians}
    all_task_assignments = []
    unassigned_tasks_ids = []
    incomplete_tasks_ids = []

    all_pm_tasks_from_excel_normalized_names_set = {
        normalize_string(TASK_NAME_MAPPING.get(t['name'], t['name'])) for t in pm_tasks
    }

    for task in pm_tasks:
        task_name_from_excel = task.get('name', 'Unknown')
        task_id = task['id']
        print(f"\nProcessing PM Task: {task_name_from_excel} (ID: {task_id})")

        base_duration = int(task.get('planned_worktime_min', 0))
        num_technicians_needed = int(task.get('mitarbeiter_pro_aufgabe', 1))
        quantity = int(task.get('quantity', 1))

        if num_technicians_needed <= 0:  # Base duration can be 0 for some tasks
            print(f"  Skipping task {task_name_from_excel}: Invalid num_technicians_needed: {num_technicians_needed}")
            for i in range(quantity):
                unassigned_tasks_ids.append(f"{task_id}_{i + 1}")
            continue
        if quantity <= 0:
            print(f"  Skipping task {task_name_from_excel}: Invalid quantity: {quantity}")
            # No instances to mark as unassigned if quantity is zero or negative
            continue

        json_task_name_lookup = TASK_NAME_MAPPING.get(task_name_from_excel, task_name_from_excel)
        normalized_current_excel_task_name = normalize_string(json_task_name_lookup)

        task_lines_str = str(task.get('lines', ''))
        task_lines = []
        if task_lines_str and task_lines_str.lower() != 'nan' and task_lines_str.strip() != '':
            try:
                task_lines = [int(line.strip()) for line in task_lines_str.split(',') if line.strip().isdigit()]
            except ValueError:
                print(f"  Warning: Invalid line format '{task_lines_str}' for task {task_name_from_excel}")

        eligible_technicians_details = []
        for tech_candidate in present_technicians:
            tech_task_definitions_for_candidate = TECHNICIAN_TASKS.get(tech_candidate, [])
            tech_lines_for_candidate = TECHNICIAN_LINES.get(tech_candidate, [])

            candidate_stated_prio_for_current_task = None
            can_do_current_task_flag = False

            for tech_task_obj in tech_task_definitions_for_candidate:
                normalized_tech_task_string = normalize_string(tech_task_obj['task'])
                if (normalized_current_excel_task_name in normalized_tech_task_string or
                        normalized_tech_task_string in normalized_current_excel_task_name):
                    if not task_lines or any(line in tech_lines_for_candidate for line in task_lines):
                        can_do_current_task_flag = True
                        candidate_stated_prio_for_current_task = tech_task_obj['prio']
                        break

            if can_do_current_task_flag and candidate_stated_prio_for_current_task is not None:
                active_task_prios_for_tech = []
                for tech_json_task_def in tech_task_definitions_for_candidate:
                    norm_tech_json_task_name = normalize_string(tech_json_task_def['task'])
                    is_this_json_task_active = False
                    for excel_task_norm_name_iter in all_pm_tasks_from_excel_normalized_names_set:
                        if norm_tech_json_task_name in excel_task_norm_name_iter or \
                                excel_task_norm_name_iter in norm_tech_json_task_name:
                            is_this_json_task_active = True
                            break
                    if is_this_json_task_active:
                        active_task_prios_for_tech.append(tech_json_task_def['prio'])

                effective_prio = candidate_stated_prio_for_current_task
                if active_task_prios_for_tech:
                    sorted_unique_active_prios = sorted(list(set(active_task_prios_for_tech)))
                    if candidate_stated_prio_for_current_task in sorted_unique_active_prios:
                        effective_prio = sorted_unique_active_prios.index(candidate_stated_prio_for_current_task) + 1
                    else:
                        print(
                            f"  Warning: Stated prio {candidate_stated_prio_for_current_task} for {tech_candidate} on {task_name_from_excel} "
                            f"not found in their calculated active prios {sorted_unique_active_prios}. Using stated prio {candidate_stated_prio_for_current_task} as effective.")
                        # effective_prio remains candidate_stated_prio_for_current_task

                eligible_technicians_details.append({
                    'name': tech_candidate,
                    'prio_for_task': effective_prio,
                    'original_stated_prio': candidate_stated_prio_for_current_task
                })

        if not eligible_technicians_details:
            print(f"  Task {task_name_from_excel}: No eligible technicians found.")
            for i in range(quantity):
                unassigned_tasks_ids.append(f"{task_id}_{i + 1}")
            continue

        eligible_technicians_details.sort(key=lambda x: x['prio_for_task'])

        tech_prio_map = {
            detail['name']: {
                'effective': detail['prio_for_task'],
                'stated': detail['original_stated_prio']
            } for detail in eligible_technicians_details
        }
        sorted_eligible_tech_names = [detail['name'] for detail in eligible_technicians_details]

        if len(sorted_eligible_tech_names) < num_technicians_needed:
            print(
                f"  Task {task_name_from_excel}: Insufficient eligible technicians ({len(sorted_eligible_tech_names)}/{num_technicians_needed}).")
            for i in range(quantity):
                unassigned_tasks_ids.append(f"{task_id}_{i + 1}")
            continue

        viable_groups_with_scores = []
        for r in range(num_technicians_needed, len(sorted_eligible_tech_names) + 1):
            for group_tuple in combinations(sorted_eligible_tech_names, r):
                group = list(group_tuple)
                avg_effective_prio = sum(
                    tech_prio_map.get(tech, {}).get('effective', float('inf')) for tech in group) / len(
                    group) if group else float('inf')
                current_workload = sum(
                    sum(end - start for start, end, _ in technician_schedules[tech_name]) for tech_name in group)

                viable_groups_with_scores.append({
                    'group': group,
                    'len': len(group),
                    'avg_prio': avg_effective_prio,
                    'workload': current_workload
                })

        viable_groups_with_scores.sort(key=lambda x: (
            abs(x['len'] - num_technicians_needed),
            x['avg_prio'],
            random.random(),
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
                # If base_duration is 0, task_duration_for_group will also be 0.
                # This is acceptable if it represents a check-off task or similar.
                task_duration_for_group = base_duration * (1 + missing_technicians) if base_duration > 0 else 0

                start_time = 0
                # Allow scheduling even if task_duration_for_group is 0
                while start_time <= total_work_minutes - (
                task_duration_for_group if task_duration_for_group > 0 else 0):
                    all_available_in_group = all(
                        all(sch_end <= start_time or sch_start >= start_time + task_duration_for_group
                            for sch_start, sch_end, _ in technician_schedules[tech_in_group])
                        for tech_in_group in group
                    )

                    if all_available_in_group:
                        is_incomplete = False
                        current_instance_duration = task_duration_for_group

                        # Handle capping only if duration is positive
                        if task_duration_for_group > 0 and start_time + task_duration_for_group > total_work_minutes:
                            current_instance_duration = total_work_minutes - start_time
                            is_incomplete = True
                            incomplete_tasks_ids.append(instance_id)

                        technicians_for_assignment = group[:num_technicians_needed]

                        for tech_assigned in technicians_for_assignment:
                            technician_schedules[tech_assigned].append(
                                (start_time, start_time + current_instance_duration, instance_task_name))

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

                    if start_time >= total_work_minutes and task_duration_for_group == 0:  # Special case for 0 duration task at end of shift
                        if all_available_in_group:  # Check availability at the very end
                            # (Logic for 0-duration task assignment as above)
                            is_incomplete = False  # 0 duration task cannot be incomplete due to time
                            current_instance_duration = 0
                            technicians_for_assignment = group[:num_technicians_needed]
                            for tech_assigned in technicians_for_assignment:
                                technician_schedules[tech_assigned].append(
                                    (start_time, start_time + current_instance_duration, instance_task_name))
                                original_stated_prio_for_display = tech_prio_map.get(tech_assigned, {}).get('stated',
                                                                                                            'N/A')
                                assignment_detail = {
                                    'technician': tech_assigned, 'task_name': instance_task_name,
                                    'start': start_time, 'duration': current_instance_duration,
                                    'is_incomplete': is_incomplete, 'original_duration': 0,
                                    'instance_id': instance_id,
                                    'technician_task_priority': original_stated_prio_for_display
                                }
                                instance_assignments.append(assignment_detail)
                            assigned_tech_names_with_display_prio = [
                                f"{tech_assigned} (Prio: {tech_prio_map.get(tech_assigned, {}).get('stated', 'N/A')})"
                                for tech_assigned in technicians_for_assignment]
                            print(
                                f"  Assigned 0-duration {instance_task_name} to {', '.join(assigned_tech_names_with_display_prio)} at {start_time} for {current_instance_duration}min.")
                            assigned_this_instance = True
                        break  # Break from while loop after checking the end of shift for 0-duration task

                    start_time += 15
                    if start_time > total_work_minutes:  # Ensure loop terminates if no slot found
                        break

                if assigned_this_instance:
                    all_task_assignments.append(instance_assignments)
                    break

            if not assigned_this_instance:
                print(f"  Could not schedule {instance_task_name}")
                unassigned_tasks_ids.append(instance_id)
                all_task_assignments.append([])

    flat_pm_assignments_for_rep_time_calc = [item for sublist in all_task_assignments for item in sublist]
    available_time_for_rep = {tech: total_work_minutes for tech in present_technicians}
    for assignment_detail in flat_pm_assignments_for_rep_time_calc:
        tech = assignment_detail['technician']
        duration = assignment_detail['duration']
        if tech in available_time_for_rep:
            available_time_for_rep[tech] -= duration

    for task in rep_tasks:
        task_name = task.get('name', 'Unknown')
        task_id = task['id']
        print(f"Processing REP task: {task_name} (ID: {task_id})")

        base_duration = int(task.get('planned_worktime_min', 0))
        num_technicians_needed = int(task.get('mitarbeiter_pro_aufgabe', 1))
        quantity = int(task.get('quantity', 1))

        if num_technicians_needed <= 0:
            print(f"Skipping REP task {task_name}: invalid num_technicians_needed={num_technicians_needed}")
            for i in range(quantity): unassigned_tasks_ids.append(f"{task_id}_{i + 1}")
            continue
        if quantity <= 0:
            print(f"Skipping REP task {task_name}: invalid quantity={quantity}")
            continue

        task_lines_str_rep = str(task.get('lines', ''))
        task_lines = []
        if task_lines_str_rep and task_lines_str_rep.lower() != 'nan' and task_lines_str_rep.strip() != '':
            try:
                task_lines = [int(line.strip()) for line in task_lines_str_rep.split(',') if line.strip().isdigit()]
            except (ValueError, TypeError):
                print(f"Warning: Invalid lines format for REP task {task_name}")

        eligible_rep_technicians_for_task = []
        if task_id in rep_assignments_dict and not rep_assignments_dict[task_id].get('skipped'):
            selected_techs = rep_assignments_dict[task_id]['technicians']
            for tech in selected_techs:
                if tech in present_technicians and available_time_for_rep.get(tech, 0) >= (
                base_duration if base_duration > 0 else 0):  # Allow 0 duration tasks
                    if not task_lines or any(line in TECHNICIAN_LINES.get(tech, []) for line in task_lines):
                        eligible_rep_technicians_for_task.append(tech)
        else:
            print(f"REP Task {task_name} skipped or unassigned in pre-assignment phase")
            for i in range(quantity): unassigned_tasks_ids.append(f"{task_id}_{i + 1}")
            continue

        if len(eligible_rep_technicians_for_task) < num_technicians_needed:
            print(
                f"REP Task {task_name}: insufficient eligible/selected technicians ({len(eligible_rep_technicians_for_task)}/{num_technicians_needed})")
            for i in range(quantity): unassigned_tasks_ids.append(f"{task_id}_{i + 1}")
            continue

        viable_groups = [list(group_comb) for r_comb in
                         range(num_technicians_needed, len(eligible_rep_technicians_for_task) + 1)
                         for group_comb in combinations(eligible_rep_technicians_for_task, r_comb)]
        viable_groups.sort(key=lambda group_rep: (
            abs(len(group_rep) - num_technicians_needed),
            sum(sum(end - start for start, end, _ in technician_schedules[tech_in_group]) for tech_in_group in
                group_rep)
        ))

        for instance_num in range(1, quantity + 1):
            instance_id = f"{task_id}_{instance_num}"
            instance_task_name = f"{task_name} (Instance {instance_num}/{quantity})"
            assigned = False
            instance_assignments_rep = []

            for group in viable_groups:
                missing_technicians = max(0, num_technicians_needed - len(group))
                task_duration = base_duration * (1 + missing_technicians) if base_duration > 0 else 0
                start_time = 0

                while start_time <= total_work_minutes - (task_duration if task_duration > 0 else 0):
                    all_available = all(
                        all(end <= start_time or start >= start_time + task_duration
                            for start, end, _ in technician_schedules[tech_in_group_rep])  # Use distinct var
                        for tech_in_group_rep in group  # Use distinct var
                    )
                    if all_available:
                        is_incomplete = False
                        original_task_duration = task_duration
                        current_instance_duration_rep = task_duration

                        if task_duration > 0 and start_time + task_duration > total_work_minutes:
                            current_instance_duration_rep = total_work_minutes - start_time
                            is_incomplete = True
                            incomplete_tasks_ids.append(instance_id)

                        technicians_for_assignment_rep = group[:num_technicians_needed]

                        for tech_assigned_rep_final in technicians_for_assignment_rep:  # Use distinct var
                            technician_schedules[tech_assigned_rep_final].append(
                                (start_time, start_time + current_instance_duration_rep, instance_task_name))
                            assignment_detail_rep = {
                                'technician': tech_assigned_rep_final,
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
                            available_time_for_rep[tech_assigned_rep_final] -= current_instance_duration_rep

                        print(
                            f"Assigned REP {instance_task_name} to {', '.join(technicians_for_assignment_rep)} at {start_time}")
                        assigned = True
                        break

                    if start_time >= total_work_minutes and task_duration == 0:  # Special case for 0 duration task at end of shift
                        if all_available:
                            current_instance_duration_rep = 0
                            technicians_for_assignment_rep = group[:num_technicians_needed]
                            for tech_assigned_rep_final in technicians_for_assignment_rep:
                                technician_schedules[tech_assigned_rep_final].append(
                                    (start_time, start_time, instance_task_name))
                                assignment_detail_rep = {
                                    'technician': tech_assigned_rep_final, 'task_name': instance_task_name,
                                    'start': start_time, 'duration': 0, 'is_incomplete': False,
                                    'original_duration': 0, 'instance_id': instance_id,
                                    'ticket_mo': task.get('ticket_mo', ''), 'ticket_url': task.get('ticket_url', '')
                                }
                                instance_assignments_rep.append(assignment_detail_rep)
                                # No time deduction for 0-duration task
                            print(
                                f"Assigned 0-duration REP {instance_task_name} to {', '.join(technicians_for_assignment_rep)} at {start_time}")
                            assigned = True
                        break  # Break from while loop

                    start_time += 15
                    if start_time > total_work_minutes:
                        break

                if assigned:
                    all_task_assignments.append(instance_assignments_rep)
                    break

            if not assigned:
                print(f"Could not schedule REP {instance_task_name}")
                unassigned_tasks_ids.append(instance_id)
                all_task_assignments.append([])

    final_assignments_flat = [item for sublist in all_task_assignments for item in sublist]
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
        sanitized_data = sanitize_data(data)  # Data from Excel
        print(f"Sanitized data: {len(sanitized_data)} tasks")

        tasks_for_processing = []
        for idx, row in enumerate(sanitized_data, start=1):
            tasks_for_processing.append({
                "id": str(idx),
                "name": row.get("scheduler_group_task", "Unknown"),
                "lines": row.get("lines", ""),
                "mitarbeiter_pro_aufgabe": int(row.get("mitarbeiter_pro_aufgabe", 1)),
                "planned_worktime_min": int(row.get("planned_worktime_min", 0)),
                "priority": row.get("priority", "C"),
                "quantity": int(row.get("quantity", 1)),
                "task_type": row.get("task_type", ""),
                "ticket_mo": row.get("ticket_mo", ""),
                "ticket_url": row.get("ticket_url", "")
            })
        print(f"Created {len(tasks_for_processing)} task objects for assignment processing.")

        current_day = get_current_day()
        total_work_minutes = calculate_work_time(current_day)
        num_intervals = ceil(total_work_minutes / 15) if total_work_minutes > 0 else 1
        print(f"Total work minutes: {total_work_minutes}, Num intervals: {num_intervals}")

        assignments_flat, unassigned_tasks, incomplete_tasks, available_time = assign_tasks(
            tasks_for_processing,
            present_technicians,
            total_work_minutes,
            rep_assignments
        )
        print(
            f"Generated {len(assignments_flat)} assignment entries, {len(unassigned_tasks)} unassigned instances, {len(incomplete_tasks)} incomplete instances.")

        validated_assignments_to_render = validate_assignments_flat_input(assignments_flat)

        print("Loading technician_dashboard.html template")
        technician_template = env.get_template('technician_dashboard.html')
        print("Rendering template")

        technician_html = technician_template.render(
            tasks=tasks_for_processing,
            technicians=present_technicians,
            total_work_minutes=total_work_minutes,
            num_intervals=num_intervals,
            assignments=validated_assignments_to_render,
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


# --- Routes for Mappings Management UI ---
@app.route('/manage_mappings_ui')
def manage_mappings_ui_route():  # Renamed to avoid conflict
    return render_template('manage_mappings.html')


@app.route('/api/get_technician_mappings', methods=['GET'])
def get_technician_mappings_api():
    conn = get_db_connection()
    cursor = conn.cursor()
    technicians_output = {}
    try:
        cursor.execute("SELECT id, name, sattelite_point, lines FROM technicians ORDER BY name")
        db_technicians = cursor.fetchall()

        for tech_row in db_technicians:
            tech_name = tech_row['name']
            tech_data = {
                "sattelite_point": tech_row['sattelite_point'],
                "technician_lines": [int(l.strip()) for l in tech_row['lines'].split(',') if l.strip().isdigit()] if
                tech_row['lines'] else [],
                "task_assignments": []
            }
            cursor.execute("""
                SELECT task_name, priority FROM technician_task_assignments
                WHERE technician_id = ? ORDER BY priority ASC
            """, (tech_row['id'],))
            for assign_row in cursor.fetchall():
                tech_data["task_assignments"].append({'task': assign_row['task_name'], 'prio': assign_row['priority']})
            technicians_output[tech_name] = tech_data

        return jsonify({"technicians": technicians_output})
    except sqlite3.Error as e:
        print(f"SQLite error in get_technician_mappings_api: {e}")
        print(traceback.format_exc())
        return jsonify({"error": f"Database error: {e}"}), 500
    except Exception as e:
        print(f"General error in get_technician_mappings_api: {e}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/save_technician_mappings', methods=['POST'])
def save_technician_mappings_api():
    conn = None  # Ensure conn is defined for finally block
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        updated_data = request.get_json()
        if not updated_data or 'technicians' not in updated_data:
            return jsonify({"message": "Invalid data format"}), 400

        technicians_from_payload = updated_data.get('technicians', {})

        for tech_name, tech_payload_data in technicians_from_payload.items():
            sattelite_point = tech_payload_data.get('sattelite_point')
            lines_list = tech_payload_data.get('technician_lines', [])
            lines_str = ",".join(map(str, filter(lambda x: isinstance(x, int), lines_list))) if lines_list else ""

            task_assignments_payload = sorted(
                filter(lambda ta: isinstance(ta, dict) and 'task' in ta and 'prio' in ta and isinstance(ta['prio'],
                                                                                                        int) and ta[
                                      'prio'] >= 1,
                       tech_payload_data.get('task_assignments', [])),
                key=lambda x: x.get('prio')
            )

            cursor.execute("SELECT id FROM technicians WHERE name = ?", (tech_name,))
            tech_row = cursor.fetchone()
            technician_id = None

            if tech_row:
                technician_id = tech_row['id']
                cursor.execute("""
                    UPDATE technicians SET sattelite_point = ?, lines = ?
                    WHERE id = ?
                """, (sattelite_point, lines_str, technician_id))
                cursor.execute("DELETE FROM technician_task_assignments WHERE technician_id = ?", (technician_id,))
            else:
                cursor.execute("""
                    INSERT INTO technicians (name, sattelite_point, lines)
                    VALUES (?, ?, ?)
                """, (tech_name, sattelite_point, lines_str))
                technician_id = cursor.lastrowid

            for assignment in task_assignments_payload:
                task_name_assign = assignment.get('task')
                priority_assign = assignment.get('prio')
                # Redundant check as filtered above, but good for safety
                if task_name_assign and isinstance(priority_assign, int) and priority_assign >= 1:
                    cursor.execute("""
                        INSERT INTO technician_task_assignments (technician_id, task_name, priority)
                        VALUES (?, ?, ?)
                    """, (technician_id, task_name_assign, priority_assign))
                else:
                    print(f"Warning: Skipping invalid task assignment for {tech_name} during DB save: {assignment}")

        conn.commit()
        load_app_config()
        return jsonify({"message": "Technician mappings saved to database and reloaded successfully!"})

    except sqlite3.Error as e:
        if conn: conn.rollback()
        print(f"SQLite error saving technician mappings: {e}")
        print(traceback.format_exc())
        return jsonify({"message": f"Database error: {e}"}), 500
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error saving technician mappings: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"message": f"Error saving mappings: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()


# --- Existing Routes ---
@app.route('/')
def index_route():  # Renamed
    # If index.html is just static, send_from_directory is fine.
    # If it needs Jinja processing (e.g. for dynamic content not related to this feature), use render_template.
    # For simplicity, assuming it might just be static or you'll adapt.
    # The previous version read it directly, which is okay for simple cases.
    # Using render_template is more standard Flask practice if it's in templates dir.
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file_route():  # Renamed
    session_id = request.form.get('session_id', str(random.randint(10000, 99999)))

    if 'excelFile' in request.files and request.files['excelFile'].filename != '':
        file = request.files['excelFile']
        if file.filename == '':
            return jsonify({"message": "No file selected"}), 400

        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])

        # Use session_id in filename to avoid conflicts if multiple users upload same filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_{file.filename}")
        file.save(file_path)
        uploaded_files[session_id] = file_path  # Store full path
        try:
            data = extract_data(file_path)
            sanitized_data = sanitize_data(data)  # sanitized_data items are dicts with int fields
            if not sanitized_data:
                return jsonify({
                    "message": "No valid data found after sanitization. Check if the Summary KW sheet contains valid tasks."
                }), 400

            rep_tasks_for_ui = [
                {**task_item, 'id': str(idx + 1)}
                for idx, task_item in enumerate(sanitized_data)
                if task_item.get('task_type', '').upper() == 'REP'
                   and task_item.get('ticket_mo')
                   and str(task_item.get('ticket_mo')).strip().lower() != 'nan'
                   and str(task_item.get('ticket_mo')).strip() != ''
            ]

            return jsonify({
                "message": "File uploaded successfully. Please select absent technicians.",
                "repTasks": rep_tasks_for_ui,
                "filename": file.filename,  # Original filename for display
                "session_id": session_id
            })
        except Exception as e:
            print(f"Error processing file upload: {str(e)}")
            print(traceback.format_exc())
            # Clean up uploaded file on error if it exists
            if session_id in uploaded_files and os.path.exists(uploaded_files[session_id]):
                try:
                    os.remove(uploaded_files[session_id])
                except Exception as e_del:
                    print(f"Error deleting uploaded file during error handling: {e_del}")
            if session_id in uploaded_files:
                del uploaded_files[session_id]
            return jsonify({"message": f"Error processing file: {str(e)}"}), 500

    if 'filename' in request.form and session_id in uploaded_files:
        file_path = uploaded_files[session_id]  # Get full path
        if not os.path.exists(file_path):
            return jsonify({"message": "Uploaded file not found on server. Please re-upload."}), 400
        try:
            excel_data = extract_data(file_path)
            # sanitized_excel_data items are dicts with int fields
            sanitized_excel_data = sanitize_data(excel_data)
            if not sanitized_excel_data:
                return jsonify({
                    "message": "No valid data found after sanitization. Check if the Summary KW sheet contains valid tasks."
                }), 400

            absent_technicians = json.loads(request.form.get('absentTechnicians', '[]'))
            present_technicians = [tech for tech in TECHNICIANS if tech not in absent_technicians]

            if 'repAssignments' in request.form:
                rep_assignments_list = json.loads(request.form['repAssignments'])
                if not os.path.exists(app.config['OUTPUT_FOLDER']):
                    os.makedirs(app.config['OUTPUT_FOLDER'])
                # generate_html_files expects tasks with int fields
                available_time = generate_html_files(sanitized_excel_data, present_technicians, rep_assignments_list)

                if session_id in uploaded_files:  # Clean up
                    try:
                        os.remove(uploaded_files[session_id])
                        del uploaded_files[session_id]
                    except Exception as e_del:
                        print(f"Error deleting uploaded file {uploaded_files.get(session_id)}: {e_del}")

                return jsonify({
                    "message": "Technician dashboard generated successfully! Check the output folder.",
                    "availableTime": available_time
                })

            current_day = get_current_day()
            total_work_minutes = calculate_work_time(current_day)

            # tasks_for_pm_processing items should have int fields where appropriate
            tasks_for_pm_processing = []
            for idx, row_dict in enumerate(sanitized_excel_data):  # row_dict from sanitize_data
                tasks_for_pm_processing.append({
                    "id": str(idx + 1),
                    "name": row_dict.get("scheduler_group_task", "Unknown"),
                    "lines": row_dict.get("lines", ""),
                    "mitarbeiter_pro_aufgabe": row_dict.get("mitarbeiter_pro_aufgabe", 1),  # Already int
                    "planned_worktime_min": row_dict.get("planned_worktime_min", 0),  # Already int
                    "priority": row_dict.get("priority", "C"),
                    "quantity": row_dict.get("quantity", 1),  # Already int
                    "task_type": row_dict.get("task_type", ""),
                    "ticket_mo": row_dict.get("ticket_mo", ""),
                    "ticket_url": row_dict.get("ticket_url", "")
                })

            pm_only_tasks_for_processing = [t for t in tasks_for_pm_processing if t['task_type'].upper() == 'PM']

            _, _, _, available_time_after_pm = assign_tasks(
                pm_only_tasks_for_processing,
                present_technicians,
                total_work_minutes,
                []
            )

            rep_tasks_for_ui_selection = [
                task_item for task_item in tasks_for_pm_processing  # Use the list with correct int types
                if task_item.get('task_type', '').upper() == 'REP'
                   and task_item.get('ticket_mo')
                   and str(task_item.get('ticket_mo')).strip().lower() != 'nan'
                   and str(task_item.get('ticket_mo')).strip() != ''
            ]

            eligible_rep_technicians_ui = {}
            for task_rep in rep_tasks_for_ui_selection:
                base_duration_rep = int(task_rep.get('planned_worktime_min', 0))  # Ensure int

                eligible_techs_for_this_rep = [
                    {"name": tech, "available_time": time_val}
                    for tech, time_val in available_time_after_pm.items()
                    if time_val >= base_duration_rep and tech in present_technicians
                ]
                eligible_rep_technicians_ui[task_rep['id']] = eligible_techs_for_this_rep

            return jsonify({
                "message": "PM tasks processed. Please assign technicians for REP tasks.",
                "repTasks": rep_tasks_for_ui_selection,
                "eligibleTechnicians": eligible_rep_technicians_ui,
                "filename": os.path.basename(file_path),
                "session_id": session_id
            })
        except Exception as e:
            print(f"Error processing file after absent selection or during REP prep: {str(e)}")
            print(traceback.format_exc())
            # Clean up uploaded file on error
            if session_id in uploaded_files and os.path.exists(uploaded_files[session_id]):
                try:
                    os.remove(uploaded_files[session_id])
                except Exception as e_del:
                    print(f"Error deleting uploaded file during error handling: {e_del}")
            if session_id in uploaded_files:
                del uploaded_files[session_id]
            return jsonify({"message": f"Error processing file: {str(e)}"}), 500

    return jsonify({"message": "No file uploaded or invalid session"}), 400


@app.route('/technicians', methods=['GET'])
def get_technicians_route_actual():  # Renamed to avoid conflict
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
