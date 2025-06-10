# wkndPlanning/task_assigner.py

from itertools import combinations, permutations # Ensure permutations is imported
from data_processing import normalize_string
from config_manager import TASK_NAME_MAPPING, TECHNICIAN_TASKS, TECHNICIAN_LINES # Assuming these are populated by load_app_config

# Maximum number of high-priority tasks to consider for permutation-based optimization.
# 7! = 5040, 8! = 40320. Keep this value mindful of performance.
MAX_PERMUTATION_TASKS = 7

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

def _calculate_hp_assignment_score(hp_assignments_details, hp_tasks_in_permutation, hp_unassigned_reasons_for_permutation, logger):
    """
    Calculates a score for a given assignment of high-priority tasks.
    Primary goal: Maximize the number of fully assigned high-priority task definitions.
    Secondary goal: Minimize the sum of priority values of unassigned/partially assigned HP task definitions.
                   (Effectively, maximize the negative sum).
    """
    num_fully_assigned_hp_task_definitions = 0
    penalty_score_from_unassigned_or_incomplete = 0 # Lower (more negative) is worse

    # Get all instance_ids that were successfully assigned from the details
    # Note: hp_assignments_details contains entries per technician, per instance.
    # We need to know if an *instance* was scheduled at all.
    # An instance is scheduled if it appears in hp_assignments_details and is not marked as incomplete for all its techs (which is complex).
    # Simpler: check against hp_unassigned_reasons_for_permutation. If an instance_id is there, it's unassigned.
    # If an instance_id is in incomplete_ids (needs to be passed or inferred), it's partially assigned.

    # Let's refine: A task definition is "fully assigned" if all its instances are scheduled and none are incomplete.
    # For simplicity in scoring permutations, we'll focus on whether all instances of a task definition were assigned without appearing in unassigned_reasons.
    # A more nuanced score might also consider 'is_incomplete', but that adds complexity to tracking across permutations.

    for task_def in hp_tasks_in_permutation:
        task_id = task_def['id']
        quantity = int(task_def.get('quantity', 1))
        if quantity == 0:
            continue # Skip 0-quantity tasks for scoring assignment success

        all_instances_of_this_task_def_assigned = True
        for i in range(1, quantity + 1):
            instance_id = f"{task_id}_{i}"
            if instance_id in hp_unassigned_reasons_for_permutation:
                all_instances_of_this_task_def_assigned = False
                break

        if all_instances_of_this_task_def_assigned:
            num_fully_assigned_hp_task_definitions += 1
        else:
            # Penalize based on the task's own priority value (lower is more important, so higher penalty)
            # Since priority_val is 1 for 'A', 2 for 'B', etc., a direct sum is fine.
            penalty_score_from_unassigned_or_incomplete += task_def['priority_val']

    # We want to maximize num_fully_assigned and minimize penalty_score.
    # So, the score tuple will be (num_fully_assigned, -penalty_score)
    # _log(logger, "debug", f"Score calc: Assigned defs: {num_fully_assigned_hp_task_definitions}, Penalty sum: {penalty_score_from_unassigned_or_incomplete}")
    return (num_fully_assigned_hp_task_definitions, -penalty_score_from_unassigned_or_incomplete)


def _assign_task_definition_to_schedule(
    task_to_assign, present_technicians, total_work_minutes, rep_assignments, logger,
    technician_schedules, all_task_assignments_details,
    unassigned_tasks_reasons_dict, incomplete_tasks_instance_ids,
    all_pm_task_names_from_excel_normalized_set # Passed through
    # TASK_NAME_MAPPING, TECHNICIAN_TASKS, TECHNICIAN_LINES are accessed from global/module scope
):
    """
    Processes a single task definition (which may have multiple instances due to quantity)
    and attempts to assign its instances to the provided schedules.
    This function encapsulates the main loop body from the original assign_tasks.
    Modifies technician_schedules, all_task_assignments_details, etc., in-place.
    """
    task_id = task_to_assign['id']
    task_name_excel = task_to_assign.get('name', 'Unknown')
    task_type = task_to_assign['task_type_upper'] # Assumes 'task_type_upper' is pre-processed
    base_duration = int(task_to_assign.get('planned_worktime_min', 0))
    num_technicians_needed = int(task_to_assign.get('mitarbeiter_pro_aufgabe', 1))
    quantity = int(task_to_assign.get('quantity', 1))

    # _log(logger, "debug", f"  (Helper) Processing task ID {task_id} ({task_name_excel}), Type: {task_type}, Prio: {task_to_assign.get('priority', 'C')}, Qty: {quantity}")

    if quantity <= 0:
        reason = f"Skipped ({task_type}): Invalid 'Quantity' ({quantity})."
        for i in range(1, max(1, quantity if quantity > 0 else 1)): # Log for expected instances if qty was >0
             unassigned_tasks_reasons_dict[f"{task_id}_{i}"] = reason
        # _log(logger, "warning", f"Task {task_name_excel} (ID: {task_id}) skipped due to invalid quantity: {quantity}")
        return

    if num_technicians_needed <= 0 and base_duration > 0 :
        reason = f"Skipped ({task_type}): Invalid 'Mitarbeiter pro Aufgabe' ({num_technicians_needed}) for non-zero duration task."
        for i in range(1, quantity + 1): unassigned_tasks_reasons_dict[f"{task_id}_{i}"] = reason
        # _log(logger, "warning", f"Task {task_name_excel} (ID: {task_id}) skipped, techs needed {num_technicians_needed} for duration {base_duration}")
        return

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
        # resource_mismatch_note = None # Defined per task type logic

        if task_type == 'PM':
            # --- PM Task Logic (Copied and adapted from original, ensuring it uses passed-in state) ---
            # _log(logger, "debug", f"    (Helper) Assigning PM instance: {instance_task_display_name}")
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
                    # _log(logger, "debug", f"    PM Eligibility Check for {tech_cand_pm} on task '{normalized_current_excel_task_name_pm}':")
                    # _log(logger, "debug", f"      Tech Lines: {tech_lines_pm}, Task Lines: {task_lines_list}")
                    # _log(logger, "debug", f"      Tech Tasks Defs: {tech_task_defs_pm}")
                    pass # Keep the if block for structure if other non-debug logs were here

                for tech_task_obj_pm in tech_task_defs_pm:
                    norm_tech_task_str_pm = normalize_string(tech_task_obj_pm['task'])
                    task_name_match = normalized_current_excel_task_name_pm in norm_tech_task_str_pm or norm_tech_task_str_pm in normalized_current_excel_task_name_pm
                    line_match = not task_lines_list or any(line in tech_lines_pm for line in task_lines_list)
                    if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                        # _log(logger, "debug", f"        Comparing with tech task '{norm_tech_task_str_pm}': Name match: {task_name_match}, Line match: {line_match}")
                        pass
                    if task_name_match and line_match:
                        can_do_pm_task = True
                        cand_stated_prio_pm = tech_task_obj_pm['prio']
                        if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                            # _log(logger, "debug", f"          Match found! Tech can do task. Stated Prio: {cand_stated_prio_pm}")
                            pass
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

            if not eligible_technicians_details_pm:
                last_known_failure_reason_for_instance = "No technicians eligible for this PM task (check skills/lines)."
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                continue # Next instance or task

            eligible_technicians_details_pm.sort(key=lambda x: x['prio_for_task'])
            if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                # _log(logger, "debug", f"    PM Instance {instance_task_display_name} - Eligible Technicians (pre-sort): {eligible_technicians_details_pm}")
                pass

            tech_prio_map_pm = {d['name']: {'effective': d['prio_for_task'], 'stated': d['original_stated_prio']} for d in eligible_technicians_details_pm}
            sorted_eligible_tech_names_pm = [d['name'] for d in eligible_technicians_details_pm]

            viable_groups_with_scores_pm = []
            # Consider groups of size 1 up to num_technicians_needed, and then num_technicians_needed up to len(sorted_eligible_tech_names_pm)
            # This prioritizes groups closer to the target size.
            # For simplicity and consistency with original, iterate all possible sizes for now.
            for r_size in range(1, len(sorted_eligible_tech_names_pm) + 1):
                for group_tuple in combinations(sorted_eligible_tech_names_pm, r_size):
                    group = list(group_tuple)
                    avg_eff_prio = sum(tech_prio_map_pm.get(t, {}).get('effective', float('inf')) for t in group) / len(group) if group else float('inf')
                    workload = sum(sum(end - start for start, end, _ in technician_schedules[tn]) for tn in group)
                    viable_groups_with_scores_pm.append({'group': group, 'len': len(group), 'avg_prio': avg_eff_prio, 'workload': workload})

            viable_groups_with_scores_pm.sort(key=lambda x: (abs(x['len'] - num_technicians_needed), x['avg_prio'], x['workload'], ''.join(sorted(x['group'])))) # Deterministic tie-breaker

            if not viable_groups_with_scores_pm:
                last_known_failure_reason_for_instance = "No viable technician groups found for PM task."
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                continue # Next instance or task

            assignment_successful_and_full = False
            final_chosen_group_for_instance = None
            final_start_time_for_instance = 0
            final_assigned_duration_for_instance = 0
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
                elif base_duration == 0: # 0-duration task
                    current_effective_duration_for_this_group = 0
                    valid_duration_calc_for_this_group = True

                if not valid_duration_calc_for_this_group:
                    # _log(logger, "debug", f"    PM Instance {instance_task_display_name} - Invalid duration calculation for group {current_candidate_group}. Skipping group.")
                    continue # Try next group

                if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                    # _log(logger, "debug", f"    PM Instance {instance_task_display_name} - Attempting to schedule FULLY with group: {current_candidate_group}, effective_duration: {current_effective_duration_for_this_group}")
                    pass

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
                            # _log(logger, "debug", f"    PM Instance {instance_task_display_name} - Found valid FULL slot for group {current_candidate_group} at {search_start_time} for {current_effective_duration_for_this_group} min.")
                            pass
                        break # Break from search_start_time loop

                    search_start_time += 15 # Try next 15-min slot
                # --- End of slot search logic for current_candidate_group ---

                if assignment_successful_and_full: # If a full assignment was made with this group
                    if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                        # _log(logger, "debug", f"    PM Instance {instance_task_display_name} - Full assignment confirmed with group {final_chosen_group_for_instance}. Breaking from group search.")
                        pass
                    break # Break from the for group_candidate_data loop (we've found our group)
                else:
                    if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                         # _log(logger, "debug", f"    PM Instance {instance_task_display_name} - Group {current_candidate_group} could not be scheduled fully. Trying next group.")
                         pass
            # --- End of loop over viable_groups_with_scores_pm ---

            if assignment_successful_and_full:
                assigned_this_instance_flag = True
                if instance_id_str in unassigned_tasks_reasons_dict:
                    del unassigned_tasks_reasons_dict[instance_id_str]

                if task_name_excel == "BIW_PM_FANUC_Roboter R-2000iC_Fettwechsel":
                     # _log(logger, "debug", f"    PM Instance {instance_task_display_name} - Proceeding with fully assigned group: {final_chosen_group_for_instance} at {final_start_time_for_instance}")
                     pass

                if not final_chosen_group_for_instance: # Handles 0-tech PM task assigned to an empty group
                    all_task_assignments_details.append({
                        'technician': None, 'task_name': instance_task_display_name,
                        'start': final_start_time_for_instance, 'duration': 0, 'is_incomplete': False,
                        'original_duration': 0, 'instance_id': instance_id_str,
                        'technician_task_priority': final_original_stated_priority_for_instance,
                        'resource_mismatch_info': "0-duration/0-tech PM task"
                    })
                else:
                    for tech_assigned_name in final_chosen_group_for_instance:
                        technician_schedules[tech_assigned_name].append(
                            (final_start_time_for_instance, final_start_time_for_instance + final_assigned_duration_for_instance, instance_task_display_name)
                        )
                        technician_schedules[tech_assigned_name].sort()
                        all_task_assignments_details.append({
                            'technician': tech_assigned_name, 'task_name': instance_task_display_name,
                            'start': final_start_time_for_instance, 'duration': final_assigned_duration_for_instance,
                            'is_incomplete': False, 'original_duration': final_current_effective_duration_for_chosen_group,
                            'instance_id': instance_id_str, 'technician_task_priority': final_original_stated_priority_for_instance,
                            'resource_mismatch_info': None
                        })
                # _log(logger, "info", f"    (Helper) Successfully scheduled (fully) {instance_task_display_name} for group {final_chosen_group_for_instance}...")
            else:
                last_known_failure_reason_for_instance = "No technician group could be fully assigned to the PM task."
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance

        elif task_type == 'REP':
            # --- REP Task Logic (Copied and adapted from original) ---
            # _log(logger, "debug", f"    (Helper) Assigning REP instance: {instance_task_display_name}")
            rep_assignments_map = {item['task_id']: item for item in rep_assignments} if rep_assignments else {}
            assignment_info_rep = rep_assignments_map.get(task_id)

            if not assignment_info_rep:
                last_known_failure_reason_for_instance = "Skipped (REP): Task data not received from UI."
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance; continue
            if assignment_info_rep.get('skipped'):
                last_known_failure_reason_for_instance = assignment_info_rep.get('skip_reason', "Skipped by user.")
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance; continue

            selected_techs_from_ui_rep = assignment_info_rep.get('technicians', [])
            raw_user_selection_count_rep = len(selected_techs_from_ui_rep)
            eligible_user_selected_techs_rep = [
                tech for tech in selected_techs_from_ui_rep
                if tech in present_technicians and (not task_lines_list or any(line in TECHNICIAN_LINES.get(tech, []) for line in task_lines_list))
            ]

            if num_technicians_needed == 0 and base_duration == 0:
                all_task_assignments_details.append({
                    'technician': None, 'task_name': instance_task_display_name, 'start': 0, 'duration': 0,
                    'is_incomplete': False, 'original_duration': 0, 'instance_id': instance_id_str,
                    'technician_task_priority': 'N/A_REP', 'resource_mismatch_info': "0-duration/0-tech task"
                })
                assigned_this_instance_flag = True
                if instance_id_str in unassigned_tasks_reasons_dict: del unassigned_tasks_reasons_dict[instance_id_str]
                continue

            if not eligible_user_selected_techs_rep and num_technicians_needed > 0:
                last_known_failure_reason_for_instance = "Skipped (REP): None of the user-selected technicians are eligible."
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance; continue

            viable_groups_with_scores_rep = []
            if eligible_user_selected_techs_rep:
                for r_size in range(1, len(eligible_user_selected_techs_rep) + 1):
                    for group_tuple in combinations(eligible_user_selected_techs_rep, r_size):
                        group = list(group_tuple)
                        workload = sum(sum(end - start for start, end, _ in technician_schedules[tn]) for tn in group)
                        viable_groups_with_scores_rep.append({'group': group, 'len': len(group), 'workload': workload})

            if not viable_groups_with_scores_rep and num_technicians_needed > 0:
                last_known_failure_reason_for_instance = "Skipped (REP): No viable groups from eligible UI-selected techs."
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance; continue

            viable_groups_with_scores_rep.sort(key=lambda x: (abs(x['len'] - num_technicians_needed), x['workload'], ''.join(sorted(x['group']))))

            assignment_successful_this_instance_rep = False
            final_chosen_group_for_rep_instance = None
            final_start_time_for_rep_instance = 0
            final_assigned_duration_for_rep_instance = 0
            final_resource_mismatch_note_rep = None # Store the note for the chosen group

            for group_candidate_data_rep in viable_groups_with_scores_rep:
                current_candidate_group_rep = group_candidate_data_rep['group']
                current_actual_num_assigned_rep = len(current_candidate_group_rep)
                current_effective_duration_rep = base_duration
                if base_duration > 0 and num_technicians_needed > 0 and current_actual_num_assigned_rep > 0:
                    current_effective_duration_rep = (base_duration * num_technicians_needed) / current_actual_num_assigned_rep

                current_resource_mismatch_note_rep_candidate = None
                if num_technicians_needed > 0:
                    if current_actual_num_assigned_rep != num_technicians_needed:
                        current_resource_mismatch_note_rep_candidate = f"Task requires {num_technicians_needed}. Assigned to {current_actual_num_assigned_rep} from UI pool of {raw_user_selection_count_rep} ({len(eligible_user_selected_techs_rep)} eligible)."
                    elif raw_user_selection_count_rep != num_technicians_needed: # Assigned optimally but UI selection was different
                         current_resource_mismatch_note_rep_candidate = f"Task requires {num_technicians_needed}. User selected {raw_user_selection_count_rep} ({len(eligible_user_selected_techs_rep)} eligible). Assigned to optimal {current_actual_num_assigned_rep}."
                elif num_technicians_needed == 0 and current_actual_num_assigned_rep > 0:
                     current_resource_mismatch_note_rep_candidate = f"Task planned for 0 techs. Assigned to {current_actual_num_assigned_rep}."


                search_start_time_rep = 0
                while search_start_time_rep <= total_work_minutes:
                    if current_effective_duration_rep == 0 and search_start_time_rep > total_work_minutes: break
                    if current_effective_duration_rep > 0 and search_start_time_rep >= total_work_minutes: break

                    duration_to_check_for_slot_rep = 1 if current_effective_duration_rep == 0 else current_effective_duration_rep
                    all_techs_in_rep_group_available = True
                    if not current_candidate_group_rep and num_technicians_needed > 0: all_techs_in_rep_group_available = False

                    for tech_in_group_name_rep in current_candidate_group_rep:
                        if not all(sch_end <= search_start_time_rep or sch_start >= search_start_time_rep + duration_to_check_for_slot_rep
                                   for sch_start, sch_end, _ in technician_schedules[tech_in_group_name_rep]):
                            all_techs_in_rep_group_available = False; break

                    if all_techs_in_rep_group_available:
                        final_chosen_group_for_rep_instance = current_candidate_group_rep
                        final_start_time_for_rep_instance = search_start_time_rep
                        assigned_duration_gantt_rep = current_effective_duration_rep
                        is_incomplete_task_flag_rep = False

                        if current_effective_duration_rep > 0 and (final_start_time_for_rep_instance + current_effective_duration_rep > total_work_minutes):
                            remaining_time = max(0, total_work_minutes - final_start_time_for_rep_instance)
                            min_acceptable_partial = current_effective_duration_rep * 0.75 # 75% rule
                            if remaining_time >= min_acceptable_partial and remaining_time > 0:
                                assigned_duration_gantt_rep = remaining_time
                                is_incomplete_task_flag_rep = True
                                if instance_id_str not in incomplete_tasks_instance_ids: incomplete_tasks_instance_ids.append(instance_id_str)
                            else: # Not enough time for a meaningful partial assignment
                                all_techs_in_rep_group_available = False # Force trying next slot/group

                        if all_techs_in_rep_group_available: # Re-check after partial assignment logic
                            final_assigned_duration_for_rep_instance = assigned_duration_gantt_rep
                            final_resource_mismatch_note_rep = current_resource_mismatch_note_rep_candidate # Capture note for chosen group
                            assignment_successful_this_instance_rep = True; break
                    search_start_time_rep += 15
                if assignment_successful_this_instance_rep: break

            if assignment_successful_this_instance_rep:
                assigned_this_instance_flag = True
                if instance_id_str in unassigned_tasks_reasons_dict: del unassigned_tasks_reasons_dict[instance_id_str]
                for tech_assigned_name_rep in final_chosen_group_for_rep_instance:
                    technician_schedules[tech_assigned_name_rep].append(
                        (final_start_time_for_rep_instance, final_start_time_for_rep_instance + final_assigned_duration_for_rep_instance, instance_task_display_name)
                    )
                    technician_schedules[tech_assigned_name_rep].sort()
                    all_task_assignments_details.append({
                        'technician': tech_assigned_name_rep, 'task_name': instance_task_display_name,
                        'start': final_start_time_for_rep_instance, 'duration': final_assigned_duration_for_rep_instance,
                        'is_incomplete': instance_id_str in incomplete_tasks_instance_ids,
                        'original_duration': base_duration, # Original planned duration of one instance
                        'instance_id': instance_id_str, 'technician_task_priority': 'N/A_REP',
                        'resource_mismatch_info': final_resource_mismatch_note_rep
                    })
                # _log(logger, "info", f"    (Helper) Successfully scheduled (REP) {instance_task_display_name} for group {final_chosen_group_for_rep_instance}...")
            else:
                if not last_known_failure_reason_for_instance or "Could not find a suitable time slot" in last_known_failure_reason_for_instance : # if default or not specific enough
                    last_known_failure_reason_for_instance = "No group/slot for REP task from UI selection."
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance

        # Common logic for unassigned instances
        if not assigned_this_instance_flag and instance_id_str not in unassigned_tasks_reasons_dict:
            unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
            # _log(logger, "warning", f"    (Helper) Failed to assign {instance_task_display_name} (Type: {task_type}). Reason: {last_known_failure_reason_for_instance}")
    # End of instance loop

def assign_tasks(tasks, present_technicians, total_work_minutes, rep_assignments=None, logger=None):
    _log(logger, "info",
        f"Unified Assigning (Global Opt Mode): {len(tasks)} tasks with {len(present_technicians)} technicians. Total work minutes: {total_work_minutes}"
    )

    priority_order = {'A': 1, 'B': 2, 'C': 3, 'DEFAULT': 4}
    all_tasks_combined = []
    for task in tasks:
        task_type = task.get('task_type', '').upper()
        if task_type in ['PM', 'REP']:
            processed_task = {
                **task,
                'task_type_upper': task_type,
                'priority_val': priority_order.get(str(task.get('priority', 'C')).upper(), priority_order['DEFAULT'])
            }
            all_tasks_combined.append(processed_task)

    all_tasks_combined.sort(key=lambda x: (x['priority_val'], x['id'])) # Sort by prio, then ID for stable order

    # _log(logger, "debug", "Initial task order for processing: %s",
    #      [(t['id'], t.get('priority', 'C'), t['priority_val']) for t in all_tasks_combined])

    all_pm_task_names_from_excel_normalized_set = {
        normalize_string(TASK_NAME_MAPPING.get(t['name'], t['name']))
        for t in all_tasks_combined if t['task_type_upper'] == 'PM'
    }

    hp_tasks = [t for t in all_tasks_combined if t['priority_val'] == 1]
    other_tasks = [t for t in all_tasks_combined if t['priority_val'] != 1]

    # These will store the final results
    final_all_task_assignments_details = []
    final_technician_schedules = {tech: [] for tech in present_technicians}
    final_unassigned_tasks_reasons_dict = {}
    final_incomplete_tasks_instance_ids = []

    if 0 < len(hp_tasks) <= MAX_PERMUTATION_TASKS:
        _log(logger, "info", f"Optimizing {len(hp_tasks)} high-priority tasks using permutations (limit: {MAX_PERMUTATION_TASKS}).")

        best_hp_overall_assignments = []
        best_hp_overall_schedules = {}
        best_hp_overall_unassigned_reasons = {}
        best_hp_overall_incomplete_ids = []
        # Score: (num_fully_assigned_hp_task_defs, -sum_penalty_unassigned_hp_tasks)
        best_hp_overall_score = (-1, float('inf'))

        # hp_tasks are already sorted by id as a secondary key from all_tasks_combined sort
        # This ensures permutations are generated from a consistent base order.
        count = 0
        num_permutations = 0
        if len(hp_tasks) > 0:
            num_permutations = 1
            for i in range(1, len(hp_tasks) + 1): num_permutations *= i

        # _log(logger, "debug", f"Generating {num_permutations} permutations for {len(hp_tasks)} HP tasks.")

        for p_hp_task_list in permutations(hp_tasks):
            count += 1
            # if count % 1000 == 0 : _log(logger, "debug", f"  Processed {count}/{num_permutations} HP permutations...")

            current_perm_schedules = {tech: [] for tech in present_technicians}
            current_perm_assignments = []
            current_perm_unassigned_reasons = {}
            current_perm_incomplete_ids = []

            for task_def in p_hp_task_list:
                _assign_task_definition_to_schedule(
                    task_def, present_technicians, total_work_minutes, rep_assignments, logger,
                    current_perm_schedules, current_perm_assignments,
                    current_perm_unassigned_reasons, current_perm_incomplete_ids,
                    all_pm_task_names_from_excel_normalized_set
                )

            current_score = _calculate_hp_assignment_score(current_perm_assignments, hp_tasks, current_perm_unassigned_reasons, logger)

            if current_score > best_hp_overall_score:
                best_hp_overall_score = current_score
                best_hp_overall_assignments = list(current_perm_assignments)
                best_hp_overall_schedules = {k: list(v) for k, v in current_perm_schedules.items()}
                best_hp_overall_unassigned_reasons = dict(current_perm_unassigned_reasons)
                best_hp_overall_incomplete_ids = list(current_perm_incomplete_ids)

        _log(logger, "info", f"Best HP permutation score: {best_hp_overall_score}. Using this schedule for HP tasks.")
        final_all_task_assignments_details = best_hp_overall_assignments
        final_technician_schedules = best_hp_overall_schedules
        # Merge unassigned reasons and incomplete IDs from the best HP permutation run
        # For unassigned, HP task reasons from the best run take precedence or are the only ones for HP tasks.
        # For incomplete, also take from the best run.
        final_unassigned_tasks_reasons_dict.update(best_hp_overall_unassigned_reasons)
        final_incomplete_tasks_instance_ids.extend(iid for iid in best_hp_overall_incomplete_ids if iid not in final_incomplete_tasks_instance_ids)

    else: # No HP tasks, or too many for permutation: process HP tasks greedily first
        if len(hp_tasks) > MAX_PERMUTATION_TASKS:
            _log(logger, "info", f"Number of high-priority tasks ({len(hp_tasks)}) > {MAX_PERMUTATION_TASKS}. Assigning HP tasks greedily.")
            # Sort HP tasks by difficulty: num_techs (desc), duration (desc), then id (asc) for stability
            hp_tasks.sort(key=lambda t: (
                -int(t.get('mitarbeiter_pro_aufgabe', 1)),
                -int(t.get('planned_worktime_min', 0)),
                t['id']
            ))
            _log(logger, "info", "Greedy HP tasks re-sorted by num_techs (desc), duration (desc), id (asc).")
        elif not hp_tasks:
             _log(logger, "info", "No high-priority tasks to optimize with permutations.")

        for task_def in hp_tasks: # hp_tasks are now sorted by difficulty or original if not re-sorted
            _assign_task_definition_to_schedule(
                task_def, present_technicians, total_work_minutes, rep_assignments, logger,
                final_technician_schedules, final_all_task_assignments_details,
                final_unassigned_tasks_reasons_dict, final_incomplete_tasks_instance_ids,
                all_pm_task_names_from_excel_normalized_set
            )

    # Assign other_tasks based on the schedule resulting from HP task assignments
    _log(logger, "info", "Assigning other-priority tasks.")
    # Sort other_tasks by main priority (asc), then by difficulty: num_techs (desc), duration (desc), then id (asc)
    other_tasks.sort(key=lambda t: (
        t['priority_val'],
        -int(t.get('mitarbeiter_pro_aufgabe', 1)),
        -int(t.get('planned_worktime_min', 0)),
        t['id']
    ))
    _log(logger, "info", "Other-priority tasks re-sorted by prio (asc), num_techs (desc), duration (desc), id (asc).")

    for task_def in other_tasks: # other_tasks are now sorted by prio and then difficulty
        _assign_task_definition_to_schedule(
            task_def, present_technicians, total_work_minutes, rep_assignments, logger,
            final_technician_schedules, final_all_task_assignments_details,
            final_unassigned_tasks_reasons_dict, final_incomplete_tasks_instance_ids,
            all_pm_task_names_from_excel_normalized_set
        )

    # --- Final available time calculation ---
    final_available_time_summary_map = {tech: total_work_minutes for tech in present_technicians}
    for tech_name_final, schedule_entries_final in final_technician_schedules.items():
        total_scheduled_time_for_tech = sum(end - start for start, end, _ in schedule_entries_final)
        final_available_time_summary_map[tech_name_final] -= total_scheduled_time_for_tech
        if final_available_time_summary_map[tech_name_final] < 0:
            # _log(logger, "warning", f"Technician {tech_name_final} has negative available time ({final_available_time_summary_map[tech_name_final]:.2f}) corrected to 0. Workload: {total_scheduled_time_for_tech}, Shift: {total_work_minutes}")
            final_available_time_summary_map[tech_name_final] = 0


    _log(logger, "info", f"Unified task assignment process completed. Assigned {len(final_all_task_assignments_details)} task segments.")
    if final_unassigned_tasks_reasons_dict:
        _log(logger, "warning", f"Unassigned task instances: {len(final_unassigned_tasks_reasons_dict)}. Reasons (sample):")
        count = 0
        for inst_id, reason in final_unassigned_tasks_reasons_dict.items():
            _log(logger, "warning", f"  - Instance {inst_id}: {reason}")
            count +=1
            if count >= 10 and len(final_unassigned_tasks_reasons_dict) > 15 : # Log a sample if many
                _log(logger, "warning", f"  ... and {len(final_unassigned_tasks_reasons_dict) - count} more unassigned instances.")
                break


    if final_incomplete_tasks_instance_ids:
        _log(logger, "info", f"Incomplete task instances (due to shift end): {len(final_incomplete_tasks_instance_ids)} -> {final_incomplete_tasks_instance_ids}")

    # _log(logger, "debug", f"Final Technician Schedules at end of assign_tasks: {final_technician_schedules}")
    return final_all_task_assignments_details, final_unassigned_tasks_reasons_dict, final_incomplete_tasks_instance_ids, final_available_time_summary_map
