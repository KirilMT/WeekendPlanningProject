# wkndPlanning/task_assigner.py
import random
from itertools import combinations
from data_processing import normalize_string
from config_manager import TASK_NAME_MAPPING, TECHNICIAN_TASKS, TECHNICIAN_LINES # Assuming these are populated by load_app_config

def calculate_pm_assignments_and_availability(pm_tasks_list, present_technicians, total_work_minutes):
    """
    Calculates PM task assignments and the available time for technicians after PM tasks.
    This is a focused version of the PM assignment logic from the main assign_tasks function.
    """
    print(f"Calculating PM assignments for {len(pm_tasks_list)} PM tasks with {len(present_technicians)} technicians. Total work minutes: {total_work_minutes}")

    technician_schedules_pm_only = {tech: [] for tech in present_technicians}
    pm_assignments_details = []
    # unassigned_pm_tasks_reasons = {} # If you need to track unassigned PMs specifically

    # Simplified PM Task Assignment Logic (adapted from assign_tasks)
    # This needs to mirror the PM assignment logic of the main assign_tasks function
    # to ensure consistent available time calculation.

    all_pm_tasks_from_input_normalized_names_set = {
        normalize_string(TASK_NAME_MAPPING.get(t['name'], t['name'])) for t in pm_tasks_list
    }

    for task in pm_tasks_list:
        task_name_from_excel = task.get('name', 'Unknown')
        task_id = task['id'] # Assuming PM tasks passed in also have an 'id'
        base_duration = int(task.get('planned_worktime_min', 0))
        num_technicians_needed = int(task.get('mitarbeiter_pro_aufgabe', 1))
        quantity = int(task.get('quantity', 1))

        if num_technicians_needed <= 0 or quantity <= 0:
            # print(f"Skipping PM task {task_name_from_excel} due to invalid techs needed or quantity.")
            continue

        json_task_name_lookup = TASK_NAME_MAPPING.get(task_name_from_excel, task_name_from_excel)
        normalized_current_excel_task_name = normalize_string(json_task_name_lookup)
        task_lines_str = str(task.get('lines', ''))
        task_lines = []
        if task_lines_str and task_lines_str.lower() != 'nan' and task_lines_str.strip() != '':
            try:
                task_lines = [int(line.strip()) for line in task_lines_str.split(',') if line.strip().isdigit()]
            except ValueError:
                pass # print(f"  Warning (PM Helper): Invalid line format '{task_lines_str}' for task {task_name_from_excel}")

        eligible_technicians_details = []
        for tech_candidate in present_technicians:
            tech_task_definitions = TECHNICIAN_TASKS.get(tech_candidate, [])
            tech_lines = TECHNICIAN_LINES.get(tech_candidate, [])
            candidate_prio = None
            can_do = False
            for tech_task_obj in tech_task_definitions:
                normalized_tech_task_str = normalize_string(tech_task_obj['task'])
                if (normalized_current_excel_task_name in normalized_tech_task_str or
                        normalized_tech_task_str in normalized_current_excel_task_name):
                    if not task_lines or any(line in tech_lines for line in task_lines):
                        can_do = True
                        candidate_prio = tech_task_obj['prio']
                        break
            if can_do and candidate_prio is not None:
                # Simplified effective prio calculation for this helper
                effective_prio = candidate_prio # In a full system, this might be more complex
                eligible_technicians_details.append({
                    'name': tech_candidate,
                    'prio_for_task': effective_prio,
                    'original_stated_prio': candidate_prio
                })

        if not eligible_technicians_details:
            continue

        eligible_technicians_details.sort(key=lambda x: x['prio_for_task'])
        tech_prio_map_helper = {
            detail['name']: {'effective': detail['prio_for_task'], 'stated': detail['original_stated_prio']}
            for detail in eligible_technicians_details
        }
        sorted_eligible_tech_names_helper = [detail['name'] for detail in eligible_technicians_details]

        viable_groups_with_scores_helper = []
        # Simplified group selection: try to find a group of the required size first
        # This is a simplification; the main assign_tasks has more complex group scoring.
        # For available time calculation, precise group formation might be less critical than just assigning *someone*.

        # Try combinations matching num_technicians_needed
        found_optimal_group = False
        for group_tuple in combinations(sorted_eligible_tech_names_helper, num_technicians_needed):
            group = list(group_tuple)
            # Simplified scoring for helper
            avg_effective_prio = sum(tech_prio_map_helper.get(t, {}).get('effective', float('inf')) for t in group) / len(group) if group else float('inf')
            current_workload = sum(sum(end - start for start, end, _ in technician_schedules_pm_only[tech_name]) for tech_name in group)
            viable_groups_with_scores_helper.append({
                'group': group, 'len': len(group), 'avg_prio': avg_effective_prio, 'workload': current_workload
            })
            found_optimal_group = True # Prioritize exact match size

        if not found_optimal_group: # Fallback to other group sizes if exact not found
             for r_group_size in range(1, len(sorted_eligible_tech_names_helper) + 1):
                if r_group_size == num_technicians_needed: continue # Already tried
                for group_tuple in combinations(sorted_eligible_tech_names_helper, r_group_size):
                    group = list(group_tuple)
                    avg_effective_prio = sum(tech_prio_map_helper.get(t, {}).get('effective', float('inf')) for t in group) / len(group) if group else float('inf')
                    current_workload = sum(sum(end - start for start, end, _ in technician_schedules_pm_only[tech_name]) for tech_name in group)
                    viable_groups_with_scores_helper.append({
                        'group': group, 'len': len(group), 'avg_prio': avg_effective_prio, 'workload': current_workload
                    })

        viable_groups_with_scores_helper.sort(key=lambda x: (
            abs(x['len'] - num_technicians_needed), x['avg_prio'], x['workload'], random.random()
        ))
        viable_groups_sorted_helper = [item['group'] for item in viable_groups_with_scores_helper]

        for instance_num in range(1, quantity + 1):
            instance_id = f"{task_id}_{instance_num}_pm_helper" # Ensure unique ID for helper context
            instance_task_name = f"{task_name_from_excel} (Instance {instance_num}/{quantity})"
            assigned_this_instance = False

            for group in viable_groups_sorted_helper:
                if not group: continue
                actual_num_assigned = len(group)
                current_task_duration_for_group = base_duration
                if base_duration > 0 and num_technicians_needed > 0 and actual_num_assigned > 0:
                    current_task_duration_for_group = (base_duration * num_technicians_needed) / actual_num_assigned
                elif base_duration == 0:
                    current_task_duration_for_group = 0
                else:
                    continue # Cannot assign if duration > 0 but no way to calculate

                start_time = 0
                while start_time <= total_work_minutes:
                    duration_to_check = 1 if current_task_duration_for_group == 0 else current_task_duration_for_group
                    if start_time + duration_to_check > total_work_minutes and current_task_duration_for_group > 0 : # Cannot fit
                        break
                    if start_time > total_work_minutes and current_task_duration_for_group == 0: # Cannot schedule 0-min task past end time
                        break

                    all_available = all(
                        all(sch_end <= start_time or sch_start >= start_time + duration_to_check
                            for sch_start, sch_end, _ in technician_schedules_pm_only[tech_in_group])
                        for tech_in_group in group
                    )

                    if all_available:
                        assigned_duration = current_task_duration_for_group
                        is_incomplete = False
                        if start_time + current_task_duration_for_group > total_work_minutes: # Task will be cut short
                            assigned_duration = total_work_minutes - start_time
                            is_incomplete = True

                        if assigned_duration <= 0 and current_task_duration_for_group > 0: # Cannot assign if it results in 0 or negative duration unless original was 0
                            start_time +=15
                            continue

                        for tech_assigned in group:
                            technician_schedules_pm_only[tech_assigned].append(
                                (start_time, start_time + assigned_duration, instance_task_name)
                            )
                            technician_schedules_pm_only[tech_assigned].sort()
                            pm_assignments_details.append({
                                'technician': tech_assigned, 'task_name': instance_task_name,
                                'start': start_time, 'duration': assigned_duration,
                                'instance_id': instance_id, 'is_incomplete': is_incomplete,
                                'original_duration': current_task_duration_for_group
                            })
                        assigned_this_instance = True
                        break
                    start_time += 15
                if assigned_this_instance:
                    break
            # if not assigned_this_instance:
                # unassigned_pm_tasks_reasons[instance_id] = "Could not find slot/group in PM helper"

    available_time_calc = {tech: total_work_minutes for tech in present_technicians}
    for tech_name, schedule_items in technician_schedules_pm_only.items():
        current_tech_workload = sum(end - start for start, end, _ in schedule_items)
        available_time_calc[tech_name] -= current_tech_workload
        if available_time_calc[tech_name] < 0:
            available_time_calc[tech_name] = 0

    print(f"PM Helper: Assignments created: {len(pm_assignments_details)}, Available time calculated for {len(available_time_calc)} techs.")
    return pm_assignments_details, available_time_calc


def assign_tasks(tasks, present_technicians, total_work_minutes, rep_assignments=None):
    print(
        f"Assigning {len(tasks)} tasks with {len(present_technicians)} technicians. Total work minutes: {total_work_minutes} (via task_assigner)"
    )
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
    unassigned_tasks_reasons = {}
    incomplete_tasks_ids = []

    all_pm_tasks_from_excel_normalized_names_set = {
        normalize_string(TASK_NAME_MAPPING.get(t['name'], t['name'])) for t in pm_tasks
    }

    # --- PM Task Assignment ---
    for task in pm_tasks:
        task_name_from_excel = task.get('name', 'Unknown')
        task_id = task['id']
        base_duration = int(task.get('planned_worktime_min', 0))
        num_technicians_needed = int(task.get('mitarbeiter_pro_aufgabe', 1))
        quantity = int(task.get('quantity', 1))

        if num_technicians_needed <= 0:
            reason = f"Skipped (PM): Invalid 'Mitarbeiter pro Aufgabe' ({num_technicians_needed})."
            for i in range(quantity): unassigned_tasks_reasons[f"{task_id}_{i + 1}"] = reason
            continue
        if quantity <= 0:
            reason = f"Skipped (PM): Invalid 'Quantity' ({quantity})."
            continue

        json_task_name_lookup = TASK_NAME_MAPPING.get(task_name_from_excel, task_name_from_excel)
        normalized_current_excel_task_name = normalize_string(json_task_name_lookup)
        task_lines_str = str(task.get('lines', ''))
        task_lines = []
        if task_lines_str and task_lines_str.lower() != 'nan' and task_lines_str.strip() != '':
            try:
                task_lines = [int(line.strip()) for line in task_lines_str.split(',') if line.strip().isdigit()]
            except ValueError:
                print(f"  Warning (PM): Invalid line format '{task_lines_str}' for task {task_name_from_excel}")

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
                    is_this_json_task_active = any(
                        norm_tech_json_task_name in excel_task_norm_name_iter or
                        excel_task_norm_name_iter in norm_tech_json_task_name
                        for excel_task_norm_name_iter in all_pm_tasks_from_excel_normalized_names_set
                    )
                    if is_this_json_task_active:
                        active_task_prios_for_tech.append(tech_json_task_def['prio'])
                effective_prio = candidate_stated_prio_for_current_task
                if active_task_prios_for_tech:
                    sorted_unique_active_prios = sorted(list(set(active_task_prios_for_tech)))
                    if candidate_stated_prio_for_current_task in sorted_unique_active_prios:
                        effective_prio = sorted_unique_active_prios.index(
                            candidate_stated_prio_for_current_task) + 1
                eligible_technicians_details.append({
                    'name': tech_candidate,
                    'prio_for_task': effective_prio,
                    'original_stated_prio': candidate_stated_prio_for_current_task
                })

        if not eligible_technicians_details:
            reason = "No technicians are eligible for this PM task (check skills/lines configuration)."
            for i in range(quantity): unassigned_tasks_reasons[f"{task_id}_{i + 1}"] = reason
            continue

        eligible_technicians_details.sort(key=lambda x: x['prio_for_task'])
        tech_prio_map = {
            detail['name']: {'effective': detail['prio_for_task'], 'stated': detail['original_stated_prio']}
            for detail in eligible_technicians_details
        }
        sorted_eligible_tech_names = [detail['name'] for detail in eligible_technicians_details]

        viable_groups_with_scores = []
        for r_group_size in range(1, len(sorted_eligible_tech_names) + 1):
            for group_tuple in combinations(sorted_eligible_tech_names, r_group_size):
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
            x['workload'],
            random.random()
        ))
        viable_groups_sorted = [item['group'] for item in viable_groups_with_scores]

        for instance_num in range(1, quantity + 1):
            instance_id = f"{task_id}_{instance_num}"
            instance_task_name = f"{task_name_from_excel} (Instance {instance_num}/{quantity})"
            assigned_this_instance = False
            last_known_failure_reason = "Could not find a suitable time slot for any eligible group (PM)."

            for group in viable_groups_sorted:
                actual_num_assigned_technicians = len(group)
                current_task_duration_for_group = base_duration
                if base_duration > 0 and num_technicians_needed > 0 and actual_num_assigned_technicians > 0:
                    current_task_duration_for_group = (base_duration * num_technicians_needed) / actual_num_assigned_technicians
                elif base_duration == 0:
                    current_task_duration_for_group = 0
                else:
                    current_task_duration_for_group = float('inf')

                resource_mismatch_info = None
                if actual_num_assigned_technicians != num_technicians_needed:
                    resource_mismatch_info = f"Requires {num_technicians_needed}, assigned to {actual_num_assigned_technicians} (PM)"

                start_time = 0
                while start_time <= total_work_minutes:
                    if current_task_duration_for_group > 0 and start_time >= total_work_minutes:
                        last_known_failure_reason = "No time remaining in shift to start PM task."
                        break
                    if current_task_duration_for_group == 0 and start_time > total_work_minutes:
                        last_known_failure_reason = "No time remaining in shift to start 0-duration PM task."
                        break

                    duration_to_check_availability = 1 if current_task_duration_for_group == 0 else current_task_duration_for_group
                    all_available_in_group = all(
                        all(sch_end <= start_time or sch_start >= start_time + duration_to_check_availability
                            for sch_start, sch_end, _ in technician_schedules[tech_in_group])
                        for tech_in_group in group
                    )

                    if all_available_in_group:
                        assigned_duration_for_gantt = current_task_duration_for_group
                        is_incomplete_flag = False
                        if current_task_duration_for_group > 0 and (start_time + current_task_duration_for_group > total_work_minutes):
                            remaining_time_in_shift = total_work_minutes - start_time
                            min_acceptable_duration = current_task_duration_for_group * 0.75
                            if remaining_time_in_shift >= min_acceptable_duration and remaining_time_in_shift > 0:
                                assigned_duration_for_gantt = remaining_time_in_shift
                                is_incomplete_flag = True
                                if instance_id not in incomplete_tasks_ids:
                                    incomplete_tasks_ids.append(instance_id)
                            else:
                                last_known_failure_reason = f"Insufficient time for 75% completion (PM). Ideal for group: {current_task_duration_for_group:.0f}min, Remaining: {remaining_time_in_shift:.0f}min, Min 75% needed: {min_acceptable_duration:.0f}min."
                                start_time += 15
                                continue
                        elif current_task_duration_for_group == 0 and start_time > total_work_minutes:
                            last_known_failure_reason = "Cannot schedule 0-duration PM task after shift end."
                            start_time += 15
                            continue

                        for tech_assigned in group:
                            technician_schedules[tech_assigned].append(
                                (start_time, start_time + assigned_duration_for_gantt, instance_task_name))
                            technician_schedules[tech_assigned].sort()
                            original_stated_prio_for_display = tech_prio_map.get(tech_assigned, {}).get('stated', 'N/A')
                            assignment_detail = {
                                'technician': tech_assigned,
                                'task_name': instance_task_name,
                                'start': start_time,
                                'duration': assigned_duration_for_gantt,
                                'is_incomplete': is_incomplete_flag,
                                'original_duration': current_task_duration_for_group,
                                'instance_id': instance_id,
                                'technician_task_priority': original_stated_prio_for_display,
                                'resource_mismatch_info': resource_mismatch_info
                            }
                            all_task_assignments.append(assignment_detail)
                        assigned_this_instance = True
                        break
                    else:
                        last_known_failure_reason = f"Technician(s) in group '{', '.join(group)}' not available at {start_time}min for {duration_to_check_availability:.0f}min (PM)."
                    start_time += 15
                if assigned_this_instance:
                    break
            if not assigned_this_instance:
                print(f"  Could not schedule PM {instance_task_name}. Reason: {last_known_failure_reason}")
                unassigned_tasks_reasons[instance_id] = last_known_failure_reason

    available_time_after_pm = {tech: total_work_minutes for tech in present_technicians}
    for tech_name_sched, schedule_items_list in technician_schedules.items():
        current_tech_workload = sum(end - start for start, end, _ in schedule_items_list)
        available_time_after_pm[tech_name_sched] -= current_tech_workload

    # --- REP Task Assignment ---
    for task in rep_tasks:
        task_name = task.get('name', 'Unknown')
        task_id = task['id']
        quantity_rep = int(task.get('quantity', 1))
        base_duration_rep = int(task.get('planned_worktime_min', 0))
        num_technicians_needed_rep = int(task.get('mitarbeiter_pro_aufgabe', 1))

        if task_id in rep_assignments_dict:
            assignment_info = rep_assignments_dict[task_id]
            if assignment_info.get('skipped'):
                reason_for_unassignment = assignment_info.get('skip_reason', "Skipped by user (reason not specified).")
                for i in range(quantity_rep):
                    unassigned_tasks_reasons[f"{task_id}_{i + 1}"] = reason_for_unassignment
                print(f"  REP Task {task_name} (ID: {task_id}) was skipped. Reason: {reason_for_unassignment}")
                continue
            else:
                selected_techs_from_ui = assignment_info.get('technicians', [])
        else:
            reason = "Skipped (REP): Task data not received from UI for assignment/skip."
            for i in range(quantity_rep):
                unassigned_tasks_reasons[f"{task_id}_{i + 1}"] = reason
            print(f"  REP Task {task_name} (ID: {task_id}) was not found in rep_assignments_dict. Marked as unassigned.")
            continue

        if num_technicians_needed_rep <= 0:
            if base_duration_rep == 0:
                num_technicians_needed_rep = 0
            else:
                reason = f"Skipped (REP): Invalid 'Mitarbeiter pro Aufgabe' ({num_technicians_needed_rep}) for non-zero duration task."
                for i in range(quantity_rep): unassigned_tasks_reasons[f"{task_id}_{i + 1}"] = reason
                continue
        if quantity_rep <= 0:
            reason = f"Skipped (REP): Invalid 'Quantity' ({quantity_rep})."
            continue

        task_lines_str_rep = str(task.get('lines', ''))
        task_lines_rep = []
        if task_lines_str_rep and task_lines_str_rep.lower() != 'nan' and task_lines_str_rep.strip() != '':
            try:
                task_lines_rep = [int(line.strip()) for line in task_lines_str_rep.split(',') if line.strip().isdigit()]
            except (ValueError, TypeError):
                print(f"  Warning (REP): Invalid lines format '{task_lines_str_rep}' for task {task_name}")

        eligible_technicians_for_this_rep_task = []
        raw_user_selection_count = len(selected_techs_from_ui)

        for tech_name_from_ui in selected_techs_from_ui:
            if tech_name_from_ui in present_technicians:
                if not task_lines_rep or any(line in TECHNICIAN_LINES.get(tech_name_from_ui, []) for line in task_lines_rep):
                    min_acceptable_time_for_eligibility = base_duration_rep * 0.75
                    if (base_duration_rep > 0 and available_time_after_pm.get(tech_name_from_ui, 0) >= min_acceptable_time_for_eligibility) or \
                       (base_duration_rep == 0):
                        eligible_technicians_for_this_rep_task.append(tech_name_from_ui)

        if not eligible_technicians_for_this_rep_task and num_technicians_needed_rep > 0 :
            reason = "Skipped (REP): None of the user-selected technicians are eligible (present, lines, >=75% gross time after PMs)."
            for i in range(quantity_rep): unassigned_tasks_reasons[f"{task_id}_{i + 1}"] = reason
            continue
        elif not eligible_technicians_for_this_rep_task and num_technicians_needed_rep == 0 and base_duration_rep == 0:
            pass

        target_assignment_group_rep = []
        if num_technicians_needed_rep == 0 and base_duration_rep == 0:
            target_assignment_group_rep = []
            print(f"  REP Info for '{task_name}': Task is 0 duration and needs 0 technicians. No assignment group formed.")
        elif eligible_technicians_for_this_rep_task:
            techs_100_percent_capable = [
                tech_name for tech_name in eligible_technicians_for_this_rep_task
                if available_time_after_pm.get(tech_name, 0) >= base_duration_rep or base_duration_rep == 0
            ]
            aim_for_group_size = num_technicians_needed_rep
            if len(eligible_technicians_for_this_rep_task) < num_technicians_needed_rep :
                aim_for_group_size = len(eligible_technicians_for_this_rep_task)

            if len(techs_100_percent_capable) >= aim_for_group_size:
                sorted_techs_100_percent = sorted(
                    techs_100_percent_capable,
                    key=lambda tech_name: available_time_after_pm.get(tech_name, 0),
                    reverse=True
                )
                target_assignment_group_rep = sorted_techs_100_percent[:aim_for_group_size]
                print(f"  REP Info for '{task_name}': Formed assignment group from 100% capable user-selected technicians: {target_assignment_group_rep} (aimed for {aim_for_group_size})")
            else:
                print(f"  REP Info for '{task_name}': Not enough 100% capable user-selected technicians ({len(techs_100_percent_capable)} found, aimed for {aim_for_group_size}). Falling back to 75%+ capable.")
                sorted_eligible_user_selected_75_plus = sorted(
                    eligible_technicians_for_this_rep_task,
                    key=lambda tech_name: available_time_after_pm.get(tech_name, 0),
                    reverse=True
                )
                target_assignment_group_rep = sorted_eligible_user_selected_75_plus[:aim_for_group_size]
                print(f"  REP Info for '{task_name}': Formed assignment group from 75%+ capable user-selected technicians: {target_assignment_group_rep} (aimed for {aim_for_group_size})")

        if not target_assignment_group_rep and num_technicians_needed_rep > 0 :
            reason = f"Skipped (REP): Could not form a target assignment group for '{task_name}' from user selection (even after fallback)."
            for i in range(quantity_rep): unassigned_tasks_reasons[f"{task_id}_{i + 1}"] = reason
            continue
        elif not target_assignment_group_rep and num_technicians_needed_rep == 0 and base_duration_rep > 0:
            reason = f"Skipped (REP): Task '{task_name}' has duration but needs 0 technicians. Marked unassigned."
            for i in range(quantity_rep): unassigned_tasks_reasons[f"{task_id}_{i + 1}"] = reason
            continue

        actual_num_assigned_rep = len(target_assignment_group_rep)
        current_task_duration_rep = base_duration_rep
        resource_mismatch_info_rep = None
        if num_technicians_needed_rep > 0:
            if actual_num_assigned_rep != num_technicians_needed_rep:
                resource_mismatch_info_rep = f"Task requires {num_technicians_needed_rep}. Assigned to {actual_num_assigned_rep} (User selected {raw_user_selection_count}, {len(eligible_technicians_for_this_rep_task)} eligible with >=75% time)."
            elif raw_user_selection_count != num_technicians_needed_rep and len(eligible_technicians_for_this_rep_task) >= num_technicians_needed_rep :
                 resource_mismatch_info_rep = f"Task requires {num_technicians_needed_rep}. User selected {raw_user_selection_count} ({len(eligible_technicians_for_this_rep_task)} eligible with >=75% time). Assigned to {actual_num_assigned_rep}."
        elif num_technicians_needed_rep == 0 and actual_num_assigned_rep > 0:
            resource_mismatch_info_rep = f"Task planned for 0 technicians. Assigned to {actual_num_assigned_rep}."

        if not target_assignment_group_rep and base_duration_rep == 0 and num_technicians_needed_rep == 0:
            print(f"  REP Info for '{task_name}': Task is 0 duration, 0 technicians. Considered complete by definition.")
            continue

        for instance_num_rep in range(1, quantity_rep + 1):
            instance_id_rep = f"{task_id}_{instance_num_rep}"
            instance_task_name_rep = f"{task_name} (Instance {instance_num_rep}/{quantity_rep})"
            assigned_this_instance_rep = False
            last_known_failure_reason_rep = f"Could not find a suitable time slot for the target group for '{task_name}' (REP)."
            group_to_schedule = target_assignment_group_rep

            if not group_to_schedule and num_technicians_needed_rep > 0:
                unassigned_tasks_reasons[instance_id_rep] = last_known_failure_reason_rep
                print(f"  Could not schedule REP {instance_task_name_rep} as no group was formed (and task required technicians). Reason: {last_known_failure_reason_rep}")
                continue

            start_time_rep = 0
            while start_time_rep <= total_work_minutes:
                if not group_to_schedule:
                    last_known_failure_reason_rep = f"No group to schedule for REP {instance_task_name_rep} (should have been marked unassigned)."
                    break

                duration_to_check_availability_rep = 1 if current_task_duration_rep == 0 else current_task_duration_rep
                if current_task_duration_rep > 0 and start_time_rep >= total_work_minutes:
                    last_known_failure_reason_rep = "No time remaining in shift to start REP task."
                    break
                if current_task_duration_rep == 0 and start_time_rep > total_work_minutes:
                    last_known_failure_reason_rep = "No time remaining in shift to start 0-duration REP task."
                    break

                all_available_in_group_to_schedule = all(
                    all(sch_end <= start_time_rep or sch_start >= start_time_rep + duration_to_check_availability_rep
                        for sch_start, sch_end, _ in technician_schedules[tech_in_group_to_schedule])
                    for tech_in_group_to_schedule in group_to_schedule
                )

                if all_available_in_group_to_schedule:
                    assigned_duration_for_gantt_rep = current_task_duration_rep
                    is_incomplete_flag_rep = False
                    if current_task_duration_rep > 0 and (start_time_rep + current_task_duration_rep > total_work_minutes):
                        remaining_time_in_shift_rep = total_work_minutes - start_time_rep
                        min_acceptable_duration_rep = current_task_duration_rep * 0.75
                        if remaining_time_in_shift_rep >= min_acceptable_duration_rep and remaining_time_in_shift_rep > 0:
                            assigned_duration_for_gantt_rep = remaining_time_in_shift_rep
                            is_incomplete_flag_rep = True
                            if instance_id_rep not in incomplete_tasks_ids:
                                incomplete_tasks_ids.append(instance_id_rep)
                        else:
                            last_known_failure_reason_rep = f"Insufficient time for 75% completion (REP) for '{task_name}'. Task duration: {current_task_duration_rep:.0f}min, Remaining in slot: {remaining_time_in_shift_rep:.0f}min, Min 75% needed: {min_acceptable_duration_rep:.0f}min."
                            start_time_rep += 15
                            continue
                    elif current_task_duration_rep == 0 and start_time_rep > total_work_minutes:
                        last_known_failure_reason_rep = "Cannot schedule 0-duration REP task after shift end."
                        start_time_rep += 15
                        continue

                    for tech_assigned_rep in group_to_schedule:
                        technician_schedules[tech_assigned_rep].append(
                            (start_time_rep, start_time_rep + assigned_duration_for_gantt_rep, instance_task_name_rep))
                        technician_schedules[tech_assigned_rep].sort()
                        assignment_detail_rep = {
                            'technician': tech_assigned_rep,
                            'task_name': instance_task_name_rep,
                            'start': start_time_rep,
                            'duration': assigned_duration_for_gantt_rep,
                            'is_incomplete': is_incomplete_flag_rep,
                            'original_duration': current_task_duration_rep,
                            'instance_id': instance_id_rep,
                            'ticket_mo': task.get('ticket_mo', ''),
                            'ticket_url': task.get('ticket_url', ''),
                            'resource_mismatch_info': resource_mismatch_info_rep,
                            'technician_task_priority': 'N/A'
                        }
                        all_task_assignments.append(assignment_detail_rep)
                    print(
                        f"  Assigned REP {instance_task_name_rep} to {', '.join(group_to_schedule)} at {start_time_rep} for {assigned_duration_for_gantt_rep}min "
                        f"(Task duration: {current_task_duration_rep}min). Incomplete: {is_incomplete_flag_rep}. Mismatch: {resource_mismatch_info_rep}")
                    assigned_this_instance_rep = True
                    break
                else:
                    last_known_failure_reason_rep = f"Technician(s) in group '{', '.join(group_to_schedule)}' not available at {start_time_rep}min for {duration_to_check_availability_rep:.0f}min (REP for '{task_name}')."
                start_time_rep += 15

            if not assigned_this_instance_rep:
                is_zero_tech_zero_duration_task_instance = (num_technicians_needed_rep == 0 and base_duration_rep == 0)
                if not is_zero_tech_zero_duration_task_instance:
                    print(f"  Could not schedule REP {instance_task_name_rep}. Reason: {last_known_failure_reason_rep}")
                    if instance_id_rep not in unassigned_tasks_reasons:
                         unassigned_tasks_reasons[instance_id_rep] = last_known_failure_rep

    final_available_time = {tech: total_work_minutes for tech in present_technicians}
    for assignment_detail in all_task_assignments:
        tech = assignment_detail['technician']
        duration = assignment_detail['duration']
        if tech in final_available_time:
            final_available_time[tech] -= duration
            if final_available_time[tech] < 0:
                print(f"Warning: Technician {tech} has negative available time: {final_available_time[tech]}")
                final_available_time[tech] = 0

    return all_task_assignments, unassigned_tasks_reasons, incomplete_tasks_ids, final_available_time
