# wkndPlanning/task_assigner.py
import random
from itertools import combinations, groupby # Ensure groupby is imported here
from data_processing import normalize_string
from config_manager import TASK_NAME_MAPPING, TECHNICIAN_TASKS, TECHNICIAN_LINES # Assuming these are populated by load_app_config

def _log(logger, level, message, *args):
    """Helper function to log or print."""
    if logger:
        if level == "info":
            logger.info(message, *args)
        elif level == "debug":
            logger.debug(message, *args)
        elif level == "warning":
            logger.warning(message, *args)
        elif level == "error":
            logger.error(message, *args)
    else:
        print(f"[{level.upper()}] {message % args if args else message}")

def assign_tasks(tasks, present_technicians, total_work_minutes, rep_assignments=None, logger=None):
    _log(logger, "info",
        f"Unified Assigning: {len(tasks)} tasks with {len(present_technicians)} technicians. Total work minutes: {total_work_minutes}"
    )

    # Combine all tasks and sort by priority
    priority_order = {'A': 1, 'B': 2, 'C': 3, 'DEFAULT': 4} # Added DEFAULT for tasks without clear prio

    all_tasks_combined = []
    for task in tasks:
        task_type = task.get('task_type', '').upper()
        if task_type in ['PM', 'REP']:
            # Ensure all tasks have a consistent structure for sorting and processing
            processed_task = {
                **task, # Spread existing task data
                'task_type_upper': task_type,
                'priority_val': priority_order.get(str(task.get('priority', 'C')).upper(), priority_order['DEFAULT'])
            }
            all_tasks_combined.append(processed_task)

    # Sort: 1. Priority (A,B,C), 2. For PMs of same prio, maybe by duration or original order (optional refinement)
    # For now, simple priority sort. If IDs are numeric and sequential, could add 'id' as secondary sort key.
    all_tasks_combined.sort(key=lambda x: x['priority_val'])

    _log(logger, "debug", "Original task order after sorting by priority_val: %s", [(t['id'], t.get('priority', 'C'), t['priority_val']) for t in all_tasks_combined])

    # Shuffle tasks within each priority group to vary processing order
    _log(logger, "info", "Shuffling tasks within each priority level.")
    shuffled_task_list = []
    # itertools.groupby requires the data to be sorted by the key you're grouping by.
    # all_tasks_combined is already sorted by 'priority_val'.
    for priority_val_group, tasks_in_priority_group_iter in groupby(all_tasks_combined, key=lambda x: x['priority_val']):
        current_priority_group_tasks = list(tasks_in_priority_group_iter)
        random.shuffle(current_priority_group_tasks) # In-place shuffle
        shuffled_task_list.extend(current_priority_group_tasks)
        _log(logger, "debug", f"Tasks for priority value {priority_val_group} (count: {len(current_priority_group_tasks)}) shuffled. Example task ID after shuffle: {current_priority_group_tasks[0]['id'] if current_priority_group_tasks else 'N/A'}")

    all_tasks_combined = shuffled_task_list
    _log(logger, "debug", "Final task order for assignment after shuffling within priorities: %s", [(t['id'], t.get('priority', 'C'), t['priority_val']) for t in all_tasks_combined])

    technician_schedules = {tech: [] for tech in present_technicians}
    all_task_assignments_details = []
    unassigned_tasks_reasons_dict = {}
    incomplete_tasks_instance_ids = []

    # This set is used for PM task eligibility calculation (dynamic priority adjustment)
    all_pm_task_names_from_excel_normalized_set = {
        normalize_string(TASK_NAME_MAPPING.get(t['name'], t['name']))
        for t in all_tasks_combined if t['task_type_upper'] == 'PM'
    }

    _log(logger, "debug", f"Combined and sorted tasks for assignment: {len(all_tasks_combined)}")

    for task_to_assign in all_tasks_combined:
        task_id = task_to_assign['id']
        task_name_excel = task_to_assign.get('name', 'Unknown')
        task_type = task_to_assign['task_type_upper']
        base_duration = int(task_to_assign.get('planned_worktime_min', 0))
        num_technicians_needed = int(task_to_assign.get('mitarbeiter_pro_aufgabe', 1))
        quantity = int(task_to_assign.get('quantity', 1))

        _log(logger, "debug", f"Processing task ID {task_id} ({task_name_excel}), Type: {task_type}, Prio: {task_to_assign.get('priority', 'C')}")

        if quantity <= 0:
            reason = f"Skipped ({task_type}): Invalid 'Quantity' ({quantity})."
            # For multi-quantity tasks, if quantity is 0, all instances are effectively unassigned.
            # If an ID scheme like task_id_1, task_id_2 exists, this loop should reflect that.
            # Assuming task_id is unique per task definition, and quantity implies multiple instances of that definition.
            for i in range(1, max(1, quantity)): # Ensure at least one entry if quantity was 0 but expected >0
                 unassigned_tasks_reasons_dict[f"{task_id}_{i}"] = reason
            _log(logger, "warning", f"Task {task_name_excel} (ID: {task_id}) skipped due to invalid quantity: {quantity}")
            continue

        if num_technicians_needed <= 0 and base_duration > 0 : # 0-duration tasks can have 0 techs
            reason = f"Skipped ({task_type}): Invalid 'Mitarbeiter pro Aufgabe' ({num_technicians_needed}) for non-zero duration task."
            for i in range(1, quantity + 1): unassigned_tasks_reasons_dict[f"{task_id}_{i}"] = reason
            _log(logger, "warning", f"Task {task_name_excel} (ID: {task_id}) skipped, techs needed {num_technicians_needed} for duration {base_duration}")
            continue

        task_lines_str = str(task_to_assign.get('lines', ''))
        task_lines_list = []
        if task_lines_str and task_lines_str.lower() != 'nan' and task_lines_str.strip() != '':
            try:
                task_lines_list = [int(line.strip()) for line in task_lines_str.split(',') if line.strip().isdigit()]
            except ValueError:
                _log(logger, "warning", f"  Warning ({task_type}): Invalid line format '{task_lines_str}' for task {task_name_excel}")

        # --- Instance Loop (Quantity) ---
        for instance_num in range(1, quantity + 1):
            instance_id_str = f"{task_id}_{instance_num}"
            instance_task_display_name = f"{task_name_excel} (Instance {instance_num}/{quantity})"
            assigned_this_instance_flag = False
            last_known_failure_reason_for_instance = f"Could not find a suitable time slot or group for {instance_task_display_name}."

            target_assignment_group_for_instance = []
            resource_mismatch_note = None
            effective_task_duration_for_group = base_duration
            original_stated_priority_for_display = 'N/A' # Default for REP or if PM logic fails to set

            if task_type == 'PM':
                # --- PM Task Logic ---
                _log(logger, "debug", f"  Assigning PM instance: {instance_task_display_name}")
                json_task_name_lookup_pm = TASK_NAME_MAPPING.get(task_name_excel, task_name_excel)
                normalized_current_excel_task_name_pm = normalize_string(json_task_name_lookup_pm)

                eligible_technicians_details_pm = []
                for tech_cand_pm in present_technicians:
                    tech_task_defs_pm = TECHNICIAN_TASKS.get(tech_cand_pm, [])
                    tech_lines_pm = TECHNICIAN_LINES.get(tech_cand_pm, [])
                    cand_stated_prio_pm = None
                    can_do_pm_task = False
                    # More detailed logging for individual technician eligibility for PM task
                    if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                        _log(logger, "debug", f"    PM Eligibility Check for {tech_cand_pm} on task '{normalized_current_excel_task_name_pm}':")
                        _log(logger, "debug", f"      Tech Lines: {tech_lines_pm}, Task Lines: {task_lines_list}")
                        _log(logger, "debug", f"      Tech Tasks Defs: {tech_task_defs_pm}")

                    for tech_task_obj_pm in tech_task_defs_pm:
                        norm_tech_task_str_pm = normalize_string(tech_task_obj_pm['task'])
                        task_name_match = normalized_current_excel_task_name_pm in norm_tech_task_str_pm or norm_tech_task_str_pm in normalized_current_excel_task_name_pm
                        line_match = not task_lines_list or any(line in tech_lines_pm for line in task_lines_list)
                        if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                            _log(logger, "debug", f"        Comparing with tech task '{norm_tech_task_str_pm}': Name match: {task_name_match}, Line match: {line_match}")
                        if task_name_match and line_match:
                            can_do_pm_task = True
                            cand_stated_prio_pm = tech_task_obj_pm['prio']
                            if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                                _log(logger, "debug", f"          Match found! Tech can do task. Stated Prio: {cand_stated_prio_pm}")
                            break
                    if can_do_pm_task and cand_stated_prio_pm is not None:
                        active_task_prios_for_tech_pm = [
                            tech_json_task_def['prio']
                            for tech_json_task_def in tech_task_defs_pm
                            if any(normalize_string(tech_json_task_def['task']) in en_iter or en_iter in normalize_string(tech_json_task_def['task'])
                                   for en_iter in all_pm_task_names_from_excel_normalized_set)
                        ]
                        eff_prio_pm = cand_stated_prio_pm
                        if active_task_prios_for_tech_pm:
                            sorted_unique_active_prios_pm = sorted(list(set(active_task_prios_for_tech_pm)))
                            if cand_stated_prio_pm in sorted_unique_active_prios_pm:
                                eff_prio_pm = sorted_unique_active_prios_pm.index(cand_stated_prio_pm) + 1
                        eligible_technicians_details_pm.append({
                            'name': tech_cand_pm, 'prio_for_task': eff_prio_pm, 'original_stated_prio': cand_stated_prio_pm
                        })
                if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                    _log(logger, "debug", f"    PM Instance {instance_task_display_name} - Eligible Technicians (pre-sort): {eligible_technicians_details_pm}")

                if not eligible_technicians_details_pm:
                    last_known_failure_reason_for_instance = "No technicians eligible for this PM task (check skills/lines)."
                    unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                    _log(logger, "warning", f"    {instance_task_display_name} unassigned: {last_known_failure_reason_for_instance}")
                    continue # Next instance or task

                eligible_technicians_details_pm.sort(key=lambda x: x['prio_for_task'])
                if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                    _log(logger, "debug", f"    PM Instance {instance_task_display_name} - Sorted Eligible Technicians & Prio Map: {eligible_technicians_details_pm}")
                tech_prio_map_pm = {d['name']: {'effective': d['prio_for_task'], 'stated': d['original_stated_prio']} for d in eligible_technicians_details_pm}
                sorted_eligible_tech_names_pm = [d['name'] for d in eligible_technicians_details_pm]

                viable_groups_with_scores_pm = []
                for r_size in range(1, len(sorted_eligible_tech_names_pm) + 1):
                    for group_tuple in combinations(sorted_eligible_tech_names_pm, r_size):
                        group = list(group_tuple)
                        avg_eff_prio = sum(tech_prio_map_pm.get(t, {}).get('effective', float('inf')) for t in group) / len(group) if group else float('inf')
                        workload = sum(sum(end - start for start, end, _ in technician_schedules[tn]) for tn in group)
                        viable_groups_with_scores_pm.append({'group': group, 'len': len(group), 'avg_prio': avg_eff_prio, 'workload': workload})
                if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                    _log(logger, "debug", f"    PM Instance {instance_task_display_name} - Viable Groups (pre-sort): {viable_groups_with_scores_pm}")

                viable_groups_with_scores_pm.sort(key=lambda x: (abs(x['len'] - num_technicians_needed), x['avg_prio'], x['workload'], random.random()))
                if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                    _log(logger, "debug", f"    PM Instance {instance_task_display_name} - Sorted Viable Groups: {viable_groups_with_scores_pm}")

                if not viable_groups_with_scores_pm:
                    last_known_failure_reason_for_instance = "No viable technician groups found for PM task after considering eligibility and combinations."
                    unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                    _log(logger, "warning", f"    {instance_task_display_name} unassigned: {last_known_failure_reason_for_instance}")
                    continue # Next instance or task

                assignment_successful_and_full = False
                # Variables to store details of the chosen assignment if one is found
                final_chosen_group_for_instance = None
                final_start_time_for_instance = 0
                final_assigned_duration_for_instance = 0
                # final_effective_duration_for_instance = 0 # This will be current_effective_duration_for_this_group
                final_actual_num_assigned_for_instance = 0
                final_original_stated_priority_for_instance = 'N/A'
                final_current_effective_duration_for_chosen_group = 0


                for group_candidate_data in viable_groups_with_scores_pm:
                    current_candidate_group = group_candidate_data['group']
                    current_actual_num_assigned = len(current_candidate_group)
                    current_original_stated_priority = tech_prio_map_pm.get(current_candidate_group[0], {}).get('stated', 'N/A') if current_candidate_group else 'N/A'

                    current_effective_duration_for_this_group = 0
                    valid_duration_calc_for_this_group = False
                    if base_duration > 0 and num_technicians_needed > 0 and current_actual_num_assigned > 0:
                        current_effective_duration_for_this_group = (base_duration * num_technicians_needed) / current_actual_num_assigned
                        valid_duration_calc_for_this_group = True
                    elif base_duration == 0:
                        current_effective_duration_for_this_group = 0
                        valid_duration_calc_for_this_group = True

                    if not valid_duration_calc_for_this_group:
                        _log(logger, "debug", f"    PM Instance {instance_task_display_name} - Invalid duration calculation for group {current_candidate_group}. Skipping group.")
                        continue # Try next group

                    if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                        _log(logger, "debug", f"    PM Instance {instance_task_display_name} - Attempting to schedule FULLY with group: {current_candidate_group}, effective_duration: {current_effective_duration_for_this_group}")

                    # --- Start of slot search logic for current_candidate_group ---
                    search_start_time = 0
                    slot_found_for_this_group = False
                    while search_start_time <= total_work_minutes:
                        # For 0-duration tasks, if start time is beyond shift (and it needs a slot), break.
                        # A 0-duration task at total_work_minutes is fine if it doesn't extend.
                        if current_effective_duration_for_this_group == 0 and search_start_time > total_work_minutes:
                            break

                        # For positive duration tasks, if start time itself is at or beyond shift end, break
                        if current_effective_duration_for_this_group > 0 and search_start_time >= total_work_minutes:
                            break

                        # Check if the task *fully* fits within the shift
                        if current_effective_duration_for_this_group > 0 and (search_start_time + current_effective_duration_for_this_group > total_work_minutes):
                            search_start_time += 15 # Try next slot
                            continue

                        duration_to_check_for_slot = 1 if current_effective_duration_for_this_group == 0 else current_effective_duration_for_this_group

                        all_techs_in_group_available_at_slot = True
                        if not current_candidate_group and num_technicians_needed > 0 : # Should not happen if viable_groups exist
                             all_techs_in_group_available_at_slot = False

                        for tech_in_group_name in current_candidate_group:
                            # Check against the main technician_schedules (reflecting prior committed tasks)
                            if not all(sch_end <= search_start_time or sch_start >= search_start_time + duration_to_check_for_slot
                                       for sch_start, sch_end, _ in technician_schedules[tech_in_group_name]):
                                all_techs_in_group_available_at_slot = False
                                break

                        if all_techs_in_group_available_at_slot:
                            # Full slot found for this group at this time
                            final_chosen_group_for_instance = current_candidate_group
                            final_start_time_for_instance = search_start_time
                            final_assigned_duration_for_instance = current_effective_duration_for_this_group # Assign full duration
                            final_actual_num_assigned_for_instance = current_actual_num_assigned
                            final_original_stated_priority_for_instance = current_original_stated_priority
                            final_current_effective_duration_for_chosen_group = current_effective_duration_for_this_group

                            assignment_successful_and_full = True
                            slot_found_for_this_group = True
                            if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                                _log(logger, "debug", f"    PM Instance {instance_task_display_name} - Found valid FULL slot for group {current_candidate_group} at {search_start_time} for {current_effective_duration_for_this_group} min.")
                            break # Break from search_start_time loop

                        search_start_time += 15 # Try next 15-min slot
                    # --- End of slot search logic for current_candidate_group ---

                    if assignment_successful_and_full: # If a full assignment was made with this group
                        if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                            _log(logger, "debug", f"    PM Instance {instance_task_display_name} - Full assignment confirmed with group {final_chosen_group_for_instance}. Breaking from group search.")
                        break # Break from the for group_candidate_data loop (we've found our group)
                    else:
                        if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                             _log(logger, "debug", f"    PM Instance {instance_task_display_name} - Group {current_candidate_group} could not be scheduled fully. Trying next group.")
                # --- End of loop over viable_groups_with_scores_pm ---

                if assignment_successful_and_full:
                    if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                         _log(logger, "debug", f"    PM Instance {instance_task_display_name} - Proceeding with fully assigned group: {final_chosen_group_for_instance} at {final_start_time_for_instance}")

                    if not final_chosen_group_for_instance: # Handles 0-tech PM task assigned to an empty group
                        assignment_detail_entry = {
                            'technician': None,
                            'task_name': instance_task_display_name,
                            'start': final_start_time_for_instance,
                            'duration': final_assigned_duration_for_instance, # Should be 0 for 0-tech, 0-base_duration tasks
                            'is_incomplete': False,
                            'original_duration': final_current_effective_duration_for_chosen_group, # Should be 0
                            'instance_id': instance_id_str,
                            'technician_task_priority': final_original_stated_priority_for_instance,
                            'resource_mismatch_info': "0-duration/0-tech PM task"
                        }
                        all_task_assignments_details.append(assignment_detail_entry)
                    else:
                        for tech_assigned_name in final_chosen_group_for_instance:
                            technician_schedules[tech_assigned_name].append(
                                (final_start_time_for_instance, final_start_time_for_instance + final_assigned_duration_for_instance, instance_task_display_name)
                            )
                            technician_schedules[tech_assigned_name].sort()
                            if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                                _log(logger, "debug", f"      Assigned {instance_task_display_name} to {tech_assigned_name} from {final_start_time_for_instance} to {final_start_time_for_instance + final_assigned_duration_for_instance}. Updated schedule for {tech_assigned_name}: {technician_schedules[tech_assigned_name]}")

                            assignment_detail_entry = {
                                'technician': tech_assigned_name,
                                'task_name': instance_task_display_name,
                                'start': final_start_time_for_instance,
                                'duration': final_assigned_duration_for_instance,
                                'is_incomplete': False, # As we prioritized and found a full assignment
                                'original_duration': final_current_effective_duration_for_chosen_group,
                                'instance_id': instance_id_str,
                                'technician_task_priority': final_original_stated_priority_for_instance,
                                'resource_mismatch_info': None
                            }
                            all_task_assignments_details.append(assignment_detail_entry)

                    _log(logger, "info", f"    Successfully scheduled (fully) {instance_task_display_name} for group {final_chosen_group_for_instance} at {final_start_time_for_instance} for {final_assigned_duration_for_instance} min.")
                    assigned_this_instance_flag = True # Mark instance as assigned
                    if instance_id_str in unassigned_tasks_reasons_dict:
                        del unassigned_tasks_reasons_dict[instance_id_str]
                else:
                    # No group could be fully assigned.
                    last_known_failure_reason_for_instance = "No technician group could be fully assigned to the PM task after trying all viable options."
                    unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                    _log(logger, "warning", f"    {instance_task_display_name} unassigned: {last_known_failure_reason_for_instance}")
                    # assigned_this_instance_flag remains False, will be handled by outer logic
            elif task_type == 'REP':
                # --- REP Task Logic ---
                _log(logger, "debug", f"  Assigning REP instance: {instance_task_display_name}")
                rep_assignments_map = {item['task_id']: item for item in rep_assignments} if rep_assignments else {}
                assignment_info_rep = rep_assignments_map.get(task_id)

                if not assignment_info_rep:
                    last_known_failure_reason_for_instance = "Skipped (REP): Task data not received from UI for assignment/skip."
                    unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                    _log(logger, "warning", f"    {instance_task_display_name} unassigned: {last_known_failure_reason_for_instance}")
                    continue

                if assignment_info_rep.get('skipped'):
                    last_known_failure_reason_for_instance = assignment_info_rep.get('skip_reason', "Skipped by user (reason not specified).")
                    unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                    _log(logger, "info", f"    REP Task {task_name_excel} (ID: {task_id}, Inst: {instance_num}) was skipped by user. Reason: {last_known_failure_reason_for_instance}")
                    continue

                selected_techs_from_ui_rep = assignment_info_rep.get('technicians', [])
                raw_user_selection_count_rep = len(selected_techs_from_ui_rep)
                _log(logger, "debug", f"    REP Instance {instance_task_display_name} - Selected Techs from UI: {selected_techs_from_ui_rep}")

                # Filter selected_techs_from_ui_rep: must be present and meet line criteria
                eligible_user_selected_techs_rep = []
                for tech_ui_sel in selected_techs_from_ui_rep:
                    if tech_ui_sel in present_technicians:
                        if not task_lines_list or any(line in TECHNICIAN_LINES.get(tech_ui_sel, []) for line in task_lines_list):
                            eligible_user_selected_techs_rep.append(tech_ui_sel)
                _log(logger, "debug", f"    REP Instance {instance_task_display_name} - Eligible User-Selected Techs (after filtering for presence & lines): {eligible_user_selected_techs_rep}")

                if not eligible_user_selected_techs_rep and num_technicians_needed > 0: # If task needs techs but none of UI selected are eligible
                    last_known_failure_reason_for_instance = "Skipped (REP): None of the user-selected technicians are eligible (present & lines)."
                    unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                    _log(logger, "warning", f"    {instance_task_display_name} unassigned: {last_known_failure_reason_for_instance}")
                    continue

                target_assignment_group_for_instance = eligible_user_selected_techs_rep # Use the filtered list from UI
                _log(logger, "debug", f"    REP Instance {instance_task_display_name} - Target Assignment Group: {target_assignment_group_for_instance}")
                actual_num_assigned = len(target_assignment_group_for_instance)
                effective_task_duration_for_group = base_duration # For REP, duration doesn't change based on #techs in this simplified model

                if num_technicians_needed > 0:
                    if actual_num_assigned != num_technicians_needed:
                         resource_mismatch_note = f"Task requires {num_technicians_needed}. Assigned to {actual_num_assigned} (User selected {raw_user_selection_count_rep}, {len(eligible_user_selected_techs_rep)} eligible)."
                    elif raw_user_selection_count_rep != num_technicians_needed and len(eligible_user_selected_techs_rep) >= num_technicians_needed:
                         resource_mismatch_note = f"Task requires {num_technicians_needed}. User selected {raw_user_selection_count_rep} ({len(eligible_user_selected_techs_rep)} eligible). Assigned to {actual_num_assigned}."
                elif num_technicians_needed == 0 and actual_num_assigned > 0: # Planned for 0, but user assigned some
                    resource_mismatch_note = f"Task planned for 0 technicians. User assigned {actual_num_assigned}."

                if not target_assignment_group_for_instance and num_technicians_needed > 0: # If after filtering UI selection, no one is left for a task that needs techs
                    last_known_failure_reason_for_instance = f"Skipped (REP): No eligible technicians remained from UI selection for '{task_name_excel}'."
                    unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                    _log(logger, "warning", f"    {instance_task_display_name} unassigned: {last_known_failure_reason_for_instance}")
                    continue

            # --- Scheduling Logic (Common for PM and REP after group is determined) ---
            if not target_assignment_group_for_instance and num_technicians_needed > 0 and base_duration > 0:
                # This case implies PM logic failed to find a group (handled by assignment_successful_and_full check now for PM),
                # or REP pre-checks failed.
                # For PM, if assignment_successful_and_full is False, assigned_this_instance_flag is False,
                # and it will be caught by the check at the end of the instance loop.
                if task_type == 'REP': # Only log for REP here as PM has its own unassigned logging
                    if instance_id_str not in unassigned_tasks_reasons_dict:
                        unassigned_tasks_reasons_dict[instance_id_str] = f"No assignment group formed for {instance_task_display_name}."
                    _log(logger, "debug", f"    No target group for REP task {instance_task_display_name}, reason: {unassigned_tasks_reasons_dict.get(instance_id_str)}")
                    continue # To next instance

            # Handle tasks that require 0 technicians (e.g., informational, 0 duration)
            # This block should only be hit if task_type is not PM (since PM has its own path) or if PM somehow bypasses its logic.
            # Or if a PM task was successfully assigned (assignment_successful_and_full = True) but was a 0-duration/0-tech task.
            if num_technicians_needed == 0 and base_duration == 0 and not target_assignment_group_for_instance and task_type != 'PM':
                 _log(logger, "info", f"  Task {instance_task_display_name} (Type: {task_type}) is 0 duration, 0 techs, no specific assignment. Marking as 'conceptually done'.")
                 all_task_assignments_details.append({
                    'technician': None, 'task_name': instance_task_display_name,
                    'start': 0, 'duration': 0, 'is_incomplete': False,
                    'original_duration': 0, 'instance_id': instance_id_str,
                    'technician_task_priority': 'N/A', 'resource_mismatch_info': "0-duration/0-tech task"
                 })
                 assigned_this_instance_flag = True
                 if instance_id_str in unassigned_tasks_reasons_dict:
                    del unassigned_tasks_reasons_dict[instance_id_str]
                 continue

            # The following block is for REP tasks or if PM tasks somehow fall through (which they shouldn't with new logic)
            # If it's a PM task, assigned_this_instance_flag would be True if successfully scheduled by the new logic.
            # If it's False, PM task was unassigned and already logged.
            if task_type == 'REP' and not assigned_this_instance_flag : # Only proceed if REP and not yet assigned (or skipped)
                current_start_time = 0
                if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel" or task_type == 'REP':
                    _log(logger, "debug", f"    Attempting to schedule {instance_task_display_name} (Duration: {effective_task_duration_for_group} min) for group {target_assignment_group_for_instance}. Technician schedules before attempt: {technician_schedules}")

                # Ensure target_assignment_group_for_instance is not None for REP tasks needing assignment
                if not target_assignment_group_for_instance and num_technicians_needed > 0:
                    if instance_id_str not in unassigned_tasks_reasons_dict: # Should have been caught earlier for REP
                        last_known_failure_reason_for_instance = f"Skipped (REP): Target group empty for '{task_name_excel}' needing technicians."
                        unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                    _log(logger, "warning", f"    {instance_task_display_name} unassigned: {unassigned_tasks_reasons_dict.get(instance_id_str)}")
                    # assigned_this_instance_flag remains False
                else: # Proceed with REP scheduling attempt
                    while current_start_time <= total_work_minutes:
                        if effective_task_duration_for_group == 0 and current_start_time > total_work_minutes:
                            last_known_failure_reason_for_instance = f"Cannot schedule 0-duration task instance '{instance_task_display_name}' after shift end."
                            break

                        if effective_task_duration_for_group > 0 and current_start_time >= total_work_minutes:
                            last_known_failure_reason_for_instance = f"No time remaining in shift to start task instance '{instance_task_display_name}'."
                            break

                        duration_to_check_for_slot = 1 if effective_task_duration_for_group == 0 else effective_task_duration_for_group
                        all_techs_in_group_available = True
                        if not target_assignment_group_for_instance and num_technicians_needed > 0 :
                            all_techs_in_group_available = False
                            last_known_failure_reason_for_instance = "Internal error: Target group empty for REP task needing technicians."

                        for tech_in_group_name in target_assignment_group_for_instance: # target_assignment_group_for_instance is set for REP tasks
                            if not all(sch_end <= current_start_time or sch_start >= current_start_time + duration_to_check_for_slot
                                    for sch_start, sch_end, _ in technician_schedules[tech_in_group_name]):
                                all_techs_in_group_available = False
                                last_known_failure_reason_for_instance = f"Technician(s) in group '{', '.join(target_assignment_group_for_instance)}' not available at {current_start_time}min for {duration_to_check_for_slot:.0f}min for REP task. Tech {tech_in_group_name} schedule: {technician_schedules[tech_in_group_name]}"
                                if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel" or task_type == 'REP':
                                    _log(logger, "debug", f"      Slot Check Failed (REP): {last_known_failure_reason_for_instance}")
                                break

                        if all_techs_in_group_available:
                            assigned_duration_for_gantt_chart = effective_task_duration_for_group
                            is_incomplete_task_flag = False

                            if effective_task_duration_for_group > 0 and (current_start_time + effective_task_duration_for_group > total_work_minutes):
                                remaining_time_in_shift_for_task = total_work_minutes - current_start_time
                                min_acceptable_duration_for_partial = effective_task_duration_for_group * 0.75

                                if remaining_time_in_shift_for_task >= min_acceptable_duration_for_partial and remaining_time_in_shift_for_task > 0:
                                    assigned_duration_for_gantt_chart = remaining_time_in_shift_for_task
                                    is_incomplete_task_flag = True
                                    if instance_id_str not in incomplete_tasks_instance_ids:
                                        incomplete_tasks_instance_ids.append(instance_id_str)
                                    _log(logger, "info", f"    Task {instance_task_display_name} (REP) will be partially assigned ({assigned_duration_for_gantt_chart} of {effective_task_duration_for_group} min).")
                                else:
                                    last_known_failure_reason_for_instance = f"Insufficient time for 75% completion (REP). Ideal: {effective_task_duration_for_group:.0f}min, Remaining: {remaining_time_in_shift_for_task:.0f}min, Min 75% needed: {min_acceptable_duration_for_partial:.0f}min."
                                    current_start_time += 15
                                    continue

                            for tech_assigned_name in target_assignment_group_for_instance:
                                technician_schedules[tech_assigned_name].append(
                                    (current_start_time, current_start_time + assigned_duration_for_gantt_chart, instance_task_display_name)
                                )
                                technician_schedules[tech_assigned_name].sort()
                                if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel" or task_type == 'REP':
                                    _log(logger, "debug", f"      Assigned {instance_task_display_name} (REP) to {tech_assigned_name} from {current_start_time} to {current_start_time + assigned_duration_for_gantt_chart}. Updated schedule for {tech_assigned_name}: {technician_schedules[tech_assigned_name]}")

                                assignment_detail_entry = {
                                    'technician': tech_assigned_name,
                                    'task_name': instance_task_display_name,
                                    'start': current_start_time,
                                    'duration': assigned_duration_for_gantt_chart,
                                    'is_incomplete': is_incomplete_task_flag,
                                    'original_duration': effective_task_duration_for_group,
                                    'instance_id': instance_id_str,
                                    'technician_task_priority': original_stated_priority_for_display if task_type == 'PM' else 'N/A_REP', # original_stated_priority_for_display is set for REP
                                    'resource_mismatch_info': resource_mismatch_note # resource_mismatch_note is set for REP
                                }
                                all_task_assignments_details.append(assignment_detail_entry)

                            _log(logger, "info", f"    Successfully scheduled {instance_task_display_name} (REP) for group {target_assignment_group_for_instance} at {current_start_time} for {assigned_duration_for_gantt_chart} min.")
                            assigned_this_instance_flag = True
                            if instance_id_str in unassigned_tasks_reasons_dict:
                                del unassigned_tasks_reasons_dict[instance_id_str]
                            break

                        current_start_time += 15
            # This final check catches any instance that wasn't assigned and didn't have a reason set yet.
            # For PM, if assignment_successful_and_full was False, assigned_this_instance_flag is False, and reason is set.
            # For REP, if its own scheduling loop failed, assigned_this_instance_flag is False, and reason is set.
            if not assigned_this_instance_flag and instance_id_str not in unassigned_tasks_reasons_dict:
                # last_known_failure_reason_for_instance should have been set by the specific logic (PM or REP)
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                _log(logger, "warning", f"    Failed to assign {instance_task_display_name} (Type: {task_type}). Reason: {last_known_failure_reason_for_instance}")

    # --- Final available time calculation ---
    final_available_time_summary_map = {tech: total_work_minutes for tech in present_technicians}
    for tech_name_final, schedule_entries_final in technician_schedules.items():
        total_scheduled_time_for_tech = sum(end - start for start, end, _ in schedule_entries_final)
        final_available_time_summary_map[tech_name_final] -= total_scheduled_time_for_tech
        if final_available_time_summary_map[tech_name_final] < 0:
            final_available_time_summary_map[tech_name_final] = 0
            _log(logger, "warning", f"Technician {tech_name_final} has negative available time corrected to 0. Workload: {total_scheduled_time_for_tech}, Shift: {total_work_minutes}")

    _log(logger, "info", f"Unified task assignment process completed. Assigned {len(all_task_assignments_details)} task segments.")
    if unassigned_tasks_reasons_dict:
        _log(logger, "warning", f"Unassigned task instances: {len(unassigned_tasks_reasons_dict)}. Reasons:")
        for inst_id, reason in unassigned_tasks_reasons_dict.items():
            # Check if the unassigned task is the one we are interested in
            task_name_for_unassigned_log = ""
            # Attempt to find the task name from all_tasks_combined using the task_id part of inst_id
            original_task_id_for_unassigned = inst_id.split('_')[0]
            matching_task_for_log = next((t for t in all_tasks_combined if t['id'] == original_task_id_for_unassigned), None)
            if matching_task_for_log:
                task_name_for_unassigned_log = matching_task_for_log.get('name', 'Unknown')

            if task_name_for_unassigned_log == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                 _log(logger, "warning", f"  - Instance {inst_id} (Task: {task_name_for_unassigned_log}): {reason}")
            elif not matching_task_for_log : # If task name couldn't be found, log it anyway if it's a general issue
                 _log(logger, "warning", f"  - Instance {inst_id} (Task ID: {original_task_id_for_unassigned} - Name not found): {reason}")
            # For other tasks, this detailed line won't be printed, reducing verbosity.
            # The summary count of unassigned tasks is still logged above.

    if incomplete_tasks_instance_ids:
        _log(logger, "info", f"Incomplete task instances (due to shift end): {incomplete_tasks_instance_ids}")

    _log(logger, "debug", f"Final Technician Schedules at end of assign_tasks: {technician_schedules}")
    return all_task_assignments_details, unassigned_tasks_reasons_dict, incomplete_tasks_instance_ids, final_available_time_summary_map
