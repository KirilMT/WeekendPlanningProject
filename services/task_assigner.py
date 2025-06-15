# wkndPlanning/task_assigner.py

from itertools import combinations, permutations # Ensure permutations is imported
from .data_processing import normalize_string
from .config_manager import TASK_NAME_MAPPING, TECHNICIAN_TASKS, TECHNICIAN_LINES # Corrected relative import

# Maximum number of high-priority tasks to consider for permutation-based optimization.
# 7! = 5040, 8! = 40320. Keep this value mindful of performance.
MAX_PERMUTATION_TASKS = 1

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
    all_pm_task_names_from_excel_normalized_set, # Passed through
    # New parameter for technician skills
    technician_technology_skills=None
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
    is_additional_task_flag = task_to_assign.get('isAdditionalTask', False)
    # Task now has a list of technology_ids
    task_technology_ids = task_to_assign.get('technology_ids', []) # Expect a list of IDs


    # _log(logger, "debug", f"  (Helper) Processing task ID {task_id} ({task_name_excel}), Type: {task_type}, Prio: {task_to_assign.get('priority', 'C')}, Qty: {quantity}, Additional: {is_additional_task_flag}, TechIDs: {task_technology_ids}")

    if quantity <= 0:
        reason = f"Skipped ({task_type}): Invalid 'Quantity' ({quantity})."
        for i in range(1, max(1, quantity if quantity > 0 else 1)): # Log for expected instances if qty was >0
             unassigned_tasks_reasons_dict[f"{task_id}_{i}"] = reason
        # _log(logger, "warning", f"Task {task_name_excel} (ID: {task_id}) skipped due to invalid quantity: {quantity}")
        return

    # Handle tasks requiring zero technicians
    if num_technicians_needed == 0:
        if base_duration == 0:
            reason = f"Skipped ({task_type}): Task requires 0 technicians and has 0 duration. Cannot be scheduled."
        else: # base_duration > 0 (Excel validation should ensure base_duration is not negative if not zero)
            reason = f"Skipped ({task_type}): Invalid 'Mitarbeiter pro Aufgabe' (0) for non-zero duration task."

        for i in range(1, quantity + 1):
            unassigned_tasks_reasons_dict[f"{task_id}_{i}"] = reason
        _log(logger, "warning", f"Task definition {task_name_excel} (ID: {task_id}) unassigned for all {quantity} instances: {reason}")
        return

    # Handle tasks requiring negative technicians (should be caught by extract_data.py, but here for robustness)
    if num_technicians_needed < 0:
        reason = f"Skipped ({task_type}): Invalid 'Mitarbeiter pro Aufgabe' ({num_technicians_needed}) - value must be positive."
        for i in range(1, quantity + 1):
            unassigned_tasks_reasons_dict[f"{task_id}_{i}"] = reason
        _log(logger, "warning", f"Task definition {task_name_excel} (ID: {task_id}) unassigned for all {quantity} instances: {reason}")
        return

    # At this point, num_technicians_needed should be > 0.
    # The previous check `if num_technicians_needed <= 0 and base_duration > 0:` is now covered by the specific checks above.

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

        if task_type == 'PM' and is_additional_task_flag:
            # --- Additional PM Task Logic ---
            _log(logger, "debug", f"    (Helper) Assigning Additional PM instance: {instance_task_display_name} (ID: {task_id})")
            rep_assignments_map = {item['task_id']: item for item in rep_assignments} if rep_assignments else {}
            assignment_info = rep_assignments_map.get(task_id) # task_id is 'additional_X'

            if not assignment_info:
                last_known_failure_reason_for_instance = "Skipped (Add. PM): Task data not found in UI assignments."
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                _log(logger, "warning", f"      {last_known_failure_reason_for_instance} for task ID {task_id}")
                continue
            if assignment_info.get('skipped'):
                last_known_failure_reason_for_instance = assignment_info.get('skip_reason', "Skipped by user (Add. PM).")
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                _log(logger, "warning", f"      Task ID {task_id} skipped by user (Add. PM): {last_known_failure_reason_for_instance}")
                continue

            selected_techs_from_ui = assignment_info.get('technicians', [])
            raw_user_selection_count = len(selected_techs_from_ui)

            # For Additional PM, eligibility is primarily based on UI selection and presence.
            # Line check is still relevant if the additional task has lines specified.
            eligible_user_selected_techs = [
                tech for tech in selected_techs_from_ui
                if tech in present_technicians and
                   (not task_lines_list or any(line in TECHNICIAN_LINES.get(tech, []) for line in task_lines_list))
            ]

            if num_technicians_needed == 0 and base_duration == 0: # 0-duration, 0-tech task
                all_task_assignments_details.append({
                    'technician': None, 'task_name': instance_task_display_name, 'start': 0, 'duration': 0,
                    'is_incomplete': False, 'original_duration': 0, 'instance_id': instance_id_str,
                    'technician_task_priority': 'N/A_AddPM',
                    'resource_mismatch_info': "0-duration/0-tech Add.PM task"
                })
                assigned_this_instance_flag = True
                if instance_id_str in unassigned_tasks_reasons_dict: del unassigned_tasks_reasons_dict[instance_id_str]
                _log(logger, "info", f"    Successfully scheduled 0-duration/0-tech Add.PM task {instance_task_display_name}")
                continue

            if not eligible_user_selected_techs and num_technicians_needed > 0:
                last_known_failure_reason_for_instance = "Skipped (Add. PM): None of the UI-selected technicians are eligible (present/lines)."
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                _log(logger, "warning", f"      {last_known_failure_reason_for_instance} for task {instance_task_display_name}")
                continue

            viable_groups_with_scores = []
            if eligible_user_selected_techs: # Only form groups from those selected in UI and present/line-eligible
                for r_size in range(1, len(eligible_user_selected_techs) + 1):
                    for group_tuple in combinations(eligible_user_selected_techs, r_size):
                        group = list(group_tuple)
                        workload = sum(sum(end - start for start, end, _ in technician_schedules[tn]) for tn in group)
                        viable_groups_with_scores.append({'group': group, 'len': len(group), 'workload': workload})

            if not viable_groups_with_scores and num_technicians_needed > 0 :
                last_known_failure_reason_for_instance = "Skipped (Add. PM): No viable groups from UI-selected eligible techs (unexpected)."
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                _log(logger, "warning", f"      {last_known_failure_reason_for_instance} for task {instance_task_display_name}")
                continue

            # Sort groups: by closeness to num_technicians_needed, then by workload, then by name for stability
            viable_groups_with_scores.sort(key=lambda x: (abs(x['len'] - num_technicians_needed), x['workload'], ''.join(sorted(x['group']))))

            assignment_successful_this_instance = False
            final_chosen_group_for_instance = None
            final_start_time_for_instance = 0
            final_assigned_duration_for_instance = 0
            final_resource_mismatch_note = None

            for group_candidate_data in viable_groups_with_scores:
                current_candidate_group = group_candidate_data['group']
                current_actual_num_assigned = len(current_candidate_group)
                current_effective_duration = base_duration
                if base_duration > 0 and num_technicians_needed > 0 and current_actual_num_assigned > 0:
                    current_effective_duration = (base_duration * num_technicians_needed) / current_actual_num_assigned

                current_resource_mismatch_note_candidate = None
                if num_technicians_needed > 0:
                    if current_actual_num_assigned != num_technicians_needed:
                        current_resource_mismatch_note_candidate = f"Task requires {num_technicians_needed}. Assigned to {current_actual_num_assigned} from UI pool of {raw_user_selection_count} ({len(eligible_user_selected_techs)} eligible)."
                    elif raw_user_selection_count != num_technicians_needed :
                         current_resource_mismatch_note_candidate = f"Task requires {num_technicians_needed}. User selected {raw_user_selection_count} ({len(eligible_user_selected_techs)} eligible). Assigned to optimal {current_actual_num_assigned}."
                elif num_technicians_needed == 0 and current_actual_num_assigned > 0:
                     current_resource_mismatch_note_candidate = f"Task planned for 0 techs. Assigned to {current_actual_num_assigned}."

                search_start_time = 0
                while search_start_time <= total_work_minutes:
                    if current_effective_duration == 0 and search_start_time > total_work_minutes: break
                    if current_effective_duration > 0 and search_start_time >= total_work_minutes: break

                    duration_to_check_for_slot = 1 if current_effective_duration == 0 else current_effective_duration
                    all_techs_in_group_available = True
                    if not current_candidate_group and num_technicians_needed > 0 :
                         all_techs_in_group_available = False

                    for tech_in_group_name in current_candidate_group:
                        if not all(sch_end <= search_start_time or sch_start >= search_start_time + duration_to_check_for_slot
                                   for sch_start, sch_end, _ in technician_schedules[tech_in_group_name]):
                            all_techs_in_group_available = False; break

                    if all_techs_in_group_available:
                        final_chosen_group_for_instance = current_candidate_group
                        final_start_time_for_instance = search_start_time
                        assigned_duration_gantt = current_effective_duration

                        if current_effective_duration > 0 and (final_start_time_for_instance + current_effective_duration > total_work_minutes):
                            remaining_time = max(0, total_work_minutes - final_start_time_for_instance)
                            min_acceptable_partial = current_effective_duration * 0.75
                            if remaining_time >= min_acceptable_partial and remaining_time > 0 :
                                assigned_duration_gantt = remaining_time
                                if instance_id_str not in incomplete_tasks_instance_ids: incomplete_tasks_instance_ids.append(instance_id_str)
                            else:
                                all_techs_in_group_available = False

                        if all_techs_in_group_available:
                            final_assigned_duration_for_instance = assigned_duration_gantt
                            final_resource_mismatch_note = current_resource_mismatch_note_candidate
                            assignment_successful_this_instance = True; break
                    search_start_time += 15
                if assignment_successful_this_instance: break

            if assignment_successful_this_instance:
                assigned_this_instance_flag = True
                if instance_id_str in unassigned_tasks_reasons_dict: del unassigned_tasks_reasons_dict[instance_id_str]

                if not final_chosen_group_for_instance and num_technicians_needed == 0:
                     all_task_assignments_details.append({
                        'technician': None, 'task_name': instance_task_display_name,
                        'start': final_start_time_for_instance, 'duration': final_assigned_duration_for_instance,
                        'is_incomplete': instance_id_str in incomplete_tasks_instance_ids,
                        'original_duration': base_duration,
                        'instance_id': instance_id_str, 'technician_task_priority': 'N/A_AddPM',
                        'resource_mismatch_info': final_resource_mismatch_note or "0-tech Add.PM task"
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
                            'is_incomplete': instance_id_str in incomplete_tasks_instance_ids,
                            'original_duration': base_duration,
                            'instance_id': instance_id_str, 'technician_task_priority': 'N/A_AddPM',
                            'resource_mismatch_info': final_resource_mismatch_note
                        })
                _log(logger, "info", f"    (Helper) Successfully scheduled (Add. PM) {instance_task_display_name} for group {final_chosen_group_for_instance} at {final_start_time_for_instance} for {final_assigned_duration_for_instance} min.")
            else:
                if not last_known_failure_reason_for_instance or "Could not find a suitable time slot" in last_known_failure_reason_for_instance:
                    last_known_failure_reason_for_instance = "No group/slot for Add. PM task from UI selection."
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                _log(logger, "warning", f"      Failed to assign Add.PM instance {instance_task_display_name}. Reason: {last_known_failure_reason_for_instance}")

        elif task_type == 'PM' and not is_additional_task_flag:
            # --- Standard PM Task Logic (modified for multi-skills) ---
            _log(logger, "debug", f"    (Helper) Assigning Standard PM instance: {instance_task_display_name}, Required Technology IDs: {task_technology_ids}")
            json_task_name_lookup_pm = TASK_NAME_MAPPING.get(task_name_excel, task_name_excel)
            normalized_current_excel_task_name_pm = normalize_string(json_task_name_lookup_pm)

            if not task_technology_ids:
                last_known_failure_reason_for_instance = f"Skipped (PM): Task {task_name_excel} (ID: {task_id}) has no required technology_ids defined."
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                _log(logger, "warning", f"      {last_known_failure_reason_for_instance}")
                continue # Next instance or task

            eligible_technicians_details_pm = []
            for tech_cand_pm in present_technicians:
                tech_skills_map = technician_technology_skills.get(tech_cand_pm, {})

                # 1. Check if technician possesses AT LEAST ONE of the task's required skills (with level > 0)
                possesses_at_least_one_required_skill = any(
                    skill_id in tech_skills_map and tech_skills_map[skill_id] > 0
                    for skill_id in task_technology_ids
                )
                if not possesses_at_least_one_required_skill:
                    # _log(logger, "debug", f"      Technician {tech_cand_pm} does not possess any of the required skills {task_technology_ids} with level > 0 for task {task_name_excel}.")
                    continue

                # 2. Check line compatibility
                tech_lines_pm = TECHNICIAN_LINES.get(tech_cand_pm, [])
                line_match = not task_lines_list or any(line in tech_lines_pm for line in task_lines_list)
                if not line_match:
                    # _log(logger, "debug", f"      Technician {tech_cand_pm} failed line match for task {task_name_excel}.")
                    continue

                # 3. Check if technician is mapped to this task name (REMOVING THIS CHECK FOR STANDARD PMs as per skill-based logic)
                # tech_task_defs_pm = TECHNICIAN_TASKS.get(tech_cand_pm, [])
                # can_do_pm_task_name = False
                # for tech_task_obj_pm in tech_task_defs_pm:
                #     norm_tech_task_str_pm = normalize_string(tech_task_obj_pm['task_name'])
                #     task_name_match = normalized_current_excel_task_name_pm in norm_tech_task_str_pm or norm_tech_task_str_pm in normalized_current_excel_task_name_pm
                #     if task_name_match:
                #         can_do_pm_task_name = True
                #         break
                # if not can_do_pm_task_name:
                #     # _log(logger, "debug", f"      Technician {tech_cand_pm} not mapped to task name {task_name_excel} for assignment.")
                #     continue

                # Store all skills the technician has that are relevant to this task (and level > 0)
                relevant_skills_for_tech = {
                    skill_id: tech_skills_map[skill_id]
                    for skill_id in task_technology_ids
                    if skill_id in tech_skills_map and tech_skills_map[skill_id] > 0
                }
                if not relevant_skills_for_tech: # Should be caught by possesses_at_least_one_required_skill, but double check
                    continue

                eligible_technicians_details_pm.append({
                    'name': tech_cand_pm,
                    'relevant_skills': relevant_skills_for_tech # Dict of {skill_id: level}
                })

            if not eligible_technicians_details_pm:
                last_known_failure_reason_for_instance = "No technicians eligible for this PM task (possess at least one skill > 0, meet line/task mapping)."
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                _log(logger, "warning", f"      {last_known_failure_reason_for_instance} for {instance_task_display_name}")
                continue

            # Preliminary sort of eligible technicians (not strictly necessary for combinations, but can help in debugging/logging)
            # eligible_technicians_details_pm.sort(key=lambda x: (-max(x['relevant_skills'].values() or [0]), x['name']))

            sorted_eligible_tech_names_pm = [d['name'] for d in eligible_technicians_details_pm]
            tech_details_map_pm = {d['name']: d for d in eligible_technicians_details_pm}

            viable_groups_with_scores_pm = []
            # Iterate through possible group sizes, prioritizing closeness to num_technicians_needed
            possible_sizes_to_try = []
            if num_technicians_needed > 0 and len(sorted_eligible_tech_names_pm) > 0:
                # Generate a list of sizes to try: num_technicians_needed first, then others by closeness.
                # Max possible size is len(sorted_eligible_tech_names_pm).
                # Min possible size is 1.
                unique_sizes = set()
                # Add planned size first if possible
                if num_technicians_needed <= len(sorted_eligible_tech_names_pm):
                    unique_sizes.add(num_technicians_needed)

                # Add other sizes, from 1 up to number of eligible techs
                for i in range(1, len(sorted_eligible_tech_names_pm) + 1):
                    unique_sizes.add(i)

                # Sort these unique sizes: first by absolute difference to num_technicians_needed, then by the size itself (smaller preferred if diff is same)
                possible_sizes_to_try = sorted(list(unique_sizes), key=lambda s: (abs(s - num_technicians_needed), s))

            # _log(logger, "debug", f"    PM Instance {instance_task_display_name} - Possible group sizes to try (sorted by preference): {possible_sizes_to_try} for num_needed={num_technicians_needed} from {len(sorted_eligible_tech_names_pm)} eligible techs.")

            for r_actual_group_size in possible_sizes_to_try:
                # This check is implicitly handled by combinations if r_actual_group_size > len(sorted_eligible_tech_names_pm)
                # as combinations will yield no results. But an explicit check might be clearer if needed.
                # if len(sorted_eligible_tech_names_pm) < r_actual_group_size: continue

                for group_tuple in combinations(sorted_eligible_tech_names_pm, r_actual_group_size):
                    group_tech_names = list(group_tuple)
                    if not group_tech_names: continue # Should not happen with r_actual_group_size >= 1

                    # Check if the group collectively covers all required skills for the task
                    group_skills_possessed_by_id = set()
                    for tech_name_in_group in group_tech_names:
                        group_skills_possessed_by_id.update(tech_details_map_pm[tech_name_in_group]['relevant_skills'].keys())

                    if not set(task_technology_ids).issubset(group_skills_possessed_by_id):
                        # _log(logger, "debug", f"      Group {group_tech_names} does not collectively cover all required skills {task_technology_ids}. Missing: {set(task_technology_ids) - group_skills_possessed_by_id}")
                        continue # This group cannot perform the task

                    # Calculate per-skill average levels for the group
                    per_skill_avg_levels = {}
                    for req_skill_id in task_technology_ids:
                        techs_with_this_skill_in_group = [
                            tech_name for tech_name in group_tech_names
                            if req_skill_id in tech_details_map_pm[tech_name]['relevant_skills']
                        ]
                        if techs_with_this_skill_in_group:
                            avg_level_for_skill = sum(
                                tech_details_map_pm[tech_name]['relevant_skills'][req_skill_id]
                                for tech_name in techs_with_this_skill_in_group
                            ) / len(techs_with_this_skill_in_group)
                            per_skill_avg_levels[req_skill_id] = avg_level_for_skill
                        else:
                            # This case should ideally not be hit if the group covers all skills,
                            # but if a skill is required and no one has it (even level 0 was filtered out earlier),
                            # this group is invalid or the skill avg is effectively 0.
                            # Given the check above (issubset), this means at least one tech has it.
                            per_skill_avg_levels[req_skill_id] = 0 # Should not happen if logic is correct

                    # Tie-breaker: Combined average skill level for the group
                    total_skill_points_in_group_for_required_skills = 0
                    count_of_possessed_required_skills_in_group = 0
                    for tech_name_in_group in group_tech_names:
                        for req_skill_id in task_technology_ids: # Iterate over task's required skills
                            if req_skill_id in tech_details_map_pm[tech_name_in_group]['relevant_skills']:
                                total_skill_points_in_group_for_required_skills += tech_details_map_pm[tech_name_in_group]['relevant_skills'][req_skill_id]
                                count_of_possessed_required_skills_in_group += 1

                    combined_avg_skill_level_group = 0
                    if count_of_possessed_required_skills_in_group > 0:
                        combined_avg_skill_level_group = total_skill_points_in_group_for_required_skills / count_of_possessed_required_skills_in_group

                    workload = sum(sum(end - start for start, end, _ in technician_schedules[tn]) for tn in group_tech_names)

                    viable_groups_with_scores_pm.append({
                        'group': group_tech_names,
                        'len': r_actual_group_size, # Actual size of this candidate group
                        'per_skill_avg': per_skill_avg_levels, # Dict {skill_id: avg_level}
                        'combined_avg_skill': combined_avg_skill_level_group,
                        'workload': workload,
                        'size_diff': abs(r_actual_group_size - num_technicians_needed) # Store difference for primary sort
                    })

            # Ensure 0-tech, 0-duration PM tasks still get a dummy group if no other groups were formed
            # This handles cases where num_technicians_needed might have been >0 but no eligible techs were found, or num_technicians_needed was 0 initially.
            if num_technicians_needed == 0 and base_duration == 0 and not viable_groups_with_scores_pm:
                 viable_groups_with_scores_pm.append({ # Add a dummy group for 0-tech tasks
                    'group': [], 'len': 0, 'per_skill_avg': {},
                    'combined_avg_skill': 0, 'workload': 0,
                    'size_diff': 0 # No difference for 0-tech tasks
                })


            # Sort viable groups:
            # 1. Closeness to num_technicians_needed (ascending, using 'size_diff').
            # 2. Per-skill averages (higher is better for each skill, compared in a consistent order of skill IDs).
            # 3. Combined average skill level (higher is better).
            # 4. Workload (lower is better).
            # 5. Technician names (alphabetical, for determinism).
            sorted_req_skill_ids_for_sorting = sorted(list(task_technology_ids))

            viable_groups_with_scores_pm.sort(key=lambda x: (
                x['size_diff'], # Primary sort: closeness to planned size
                tuple(-x['per_skill_avg'].get(skill_id, 0) for skill_id in sorted_req_skill_ids_for_sorting),
                -x['combined_avg_skill'],
                x['workload'],
                ''.join(sorted(x['group']))
            ))

            # _log(logger, "debug", f"    PM Instance {instance_task_display_name} - Sorted Viable Groups (Target size {num_technicians_needed}, Multi-Skill): {[(g['group'], g['len'], g['per_skill_avg'], g['combined_avg_skill'], g['workload']) for g in viable_groups_with_scores_pm[:5]]}")

            if not viable_groups_with_scores_pm:
                if num_technicians_needed > 0:
                    last_known_failure_reason_for_instance = f"No viable technician groups found that collectively cover all required skills: {task_technology_ids}. Eligible techs: {len(sorted_eligible_tech_names_pm)} (Target size: {num_technicians_needed})."
                elif num_technicians_needed == 0 and base_duration == 0: # Should have formed a dummy group
                    last_known_failure_reason_for_instance = "Failed to process 0-tech, 0-duration PM task (no dummy group)."
                else: # Other num_technicians_needed == 0 cases (e.g. positive duration)
                    last_known_failure_reason_for_instance = f"No eligible technicians for 0-tech PM task {task_name_excel} (or other issue)."

                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                _log(logger, "warning", f"      {last_known_failure_reason_for_instance} for {instance_task_display_name}")
                continue

            assignment_successful_this_instance = False # Renamed from assignment_successful_and_full
            final_chosen_group_for_instance = None
            final_start_time_for_instance = 0
            final_assigned_duration_for_instance = 0
            # final_actual_num_assigned_for_instance = 0 # Will be num_technicians_needed or 0
            final_technician_task_info = 'Skill_Based' # Generic info

            for group_candidate_data in viable_groups_with_scores_pm:
                current_candidate_group = group_candidate_data['group']
                current_actual_num_assigned = len(current_candidate_group) # This is now the actual size of the chosen group candidate

                current_effective_duration = base_duration
                # Duration adjustment based on actual assigned vs. needed (if task has duration and needs techs)
                if base_duration > 0 and num_technicians_needed > 0 and current_actual_num_assigned > 0:
                    current_effective_duration = (base_duration * num_technicians_needed) / current_actual_num_assigned
                elif base_duration == 0: # 0-duration tasks always have 0 effective duration
                    current_effective_duration = 0
                # If num_technicians_needed is 0 but base_duration > 0, it's an invalid task config, handled by initial checks.
                # If current_actual_num_assigned is 0 for a task needing techs and duration, it won't be chosen or this calc won't matter.

                search_start_time = 0
                slot_found_for_this_group = False
                assigned_duration_for_slot = 0
                is_incomplete_for_slot = False

                while search_start_time <= total_work_minutes:
                    if current_effective_duration == 0 and search_start_time > total_work_minutes: break # 0-duration task can be at total_work_minutes
                    if current_effective_duration > 0 and search_start_time >= total_work_minutes: break # Positive duration task cannot start at end of shift

                    # Try to fit full duration first
                    duration_to_check = 1 if current_effective_duration == 0 else current_effective_duration

                    # Check if full duration fits within shift
                    if current_effective_duration > 0 and (search_start_time + current_effective_duration > total_work_minutes):
                        # Full duration does not fit. Check for partial (75% rule)
                        remaining_time_in_shift = max(0, total_work_minutes - search_start_time)
                        min_acceptable_partial_duration = current_effective_duration * 0.75

                        if remaining_time_in_shift >= min_acceptable_partial_duration and remaining_time_in_shift > 0:
                            duration_to_check = remaining_time_in_shift
                            is_incomplete_for_slot = True
                        else: # Not enough time for a meaningful partial assignment in this slot
                            search_start_time += 15
                            continue # Try next slot
                    else: # Full duration fits or it's a 0-duration task
                        duration_to_check = duration_to_check # Keep as is (full or 1 for 0-duration)
                        is_incomplete_for_slot = False


                    all_techs_in_group_available_at_slot = True
                    if not current_candidate_group and num_technicians_needed > 0 : # Should not happen if viable_groups exist and num_technicians_needed > 0
                         all_techs_in_group_available_at_slot = False

                    for tech_in_group_name in current_candidate_group:
                        if not all(sch_end <= search_start_time or sch_start >= search_start_time + duration_to_check
                                   for sch_start, sch_end, _ in technician_schedules[tech_in_group_name]):
                            all_techs_in_group_available_at_slot = False
                            break

                    if all_techs_in_group_available_at_slot:
                        final_chosen_group_for_instance = current_candidate_group
                        final_start_time_for_instance = search_start_time
                        final_assigned_duration_for_instance = duration_to_check if current_effective_duration > 0 else 0 # Actual assigned duration

                        assignment_successful_this_instance = True
                        slot_found_for_this_group = True
                        if is_incomplete_for_slot:
                            if instance_id_str not in incomplete_tasks_instance_ids:
                                incomplete_tasks_instance_ids.append(instance_id_str)
                        break # Break from search_start_time loop (slot found for this group)
                    else:
                        # If the slot was not available for all techs in the group, increment search_start_time
                        # This ensures the loop progresses if the `break` above was not hit.
                        # The partial assignment logic's `continue` handles its own increment.
                        search_start_time += 15
                # --- End of slot search logic for current_candidate_group ---

                if assignment_successful_this_instance:
                    break # Break from the for group_candidate_data loop (we've found our group and slot)
            # --- End of loop over viable_groups_with_scores_pm ---

            if assignment_successful_this_instance:
                assigned_this_instance_flag = True
                if instance_id_str in unassigned_tasks_reasons_dict:
                    del unassigned_tasks_reasons_dict[instance_id_str]

                resource_mismatch_note_pm = None
                if num_technicians_needed > 0: # Only note mismatch if techs were planned
                    if len(final_chosen_group_for_instance) != num_technicians_needed:
                        resource_mismatch_note_pm = f"Task planned for {num_technicians_needed} techs; assigned to {len(final_chosen_group_for_instance)}."
                    else:
                        resource_mismatch_note_pm = f"Assigned {len(final_chosen_group_for_instance)} as planned."
                elif num_technicians_needed == 0 and len(final_chosen_group_for_instance) > 0:
                     resource_mismatch_note_pm = f"Task planned for 0 techs; assigned to {len(final_chosen_group_for_instance)}."
                # If num_technicians_needed == 0 and len(final_chosen_group_for_instance) == 0, no note needed or handled by "0-tech PM task"


                if not final_chosen_group_for_instance: # Handles 0-tech PM task (group is [])
                    all_task_assignments_details.append({
                        'technician': None, 'task_name': instance_task_display_name,
                        'start': final_start_time_for_instance, 'duration': final_assigned_duration_for_instance, # Should be 0
                        'is_incomplete': instance_id_str in incomplete_tasks_instance_ids, # Should be False
                        'original_duration': base_duration, 'instance_id': instance_id_str,
                        'technician_task_info': final_technician_task_info, # Corrected key
                        'resource_mismatch_info': resource_mismatch_note_pm or "0-tech PM task"
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
                            'is_incomplete': instance_id_str in incomplete_tasks_instance_ids,
                            'original_duration': base_duration,
                            'instance_id': instance_id_str,
                            'technician_task_info': final_technician_task_info, # Corrected key
                            'resource_mismatch_info': resource_mismatch_note_pm
                        })
                _log(logger, "info", f"    (Helper) Successfully scheduled PM {instance_task_display_name} for group {final_chosen_group_for_instance} at {final_start_time_for_instance} for {final_assigned_duration_for_instance} min. Incomplete: {instance_id_str in incomplete_tasks_instance_ids}. Required skills: {task_technology_ids}")
            else: # No suitable group or slot found
                if not last_known_failure_reason_for_instance or "Could not find a suitable time slot" in last_known_failure_reason_for_instance or "No viable technician groups" in last_known_failure_reason_for_instance:
                    last_known_failure_reason_for_instance = f"No suitable group/slot for PM task {instance_task_display_name}. Required skills: {task_technology_ids}"
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                _log(logger, "warning", f"      Failed to assign PM instance {instance_task_display_name}. Reason: {last_known_failure_reason_for_instance}")

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
                    'technician_task_priority': 'N/A_REP',
                    'resource_mismatch_info': "0-duration/0-tech task"
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
                        'instance_id': instance_id_str,
                        'technician_task_info': 'N/A_REP', # Corrected key
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

def assign_tasks(tasks, present_technicians, total_work_minutes, rep_assignments=None, logger=None, technician_technology_skills=None):
    _log(logger, "info",
        f"Unified Assigning (Global Opt Mode): {len(tasks)} tasks with {len(present_technicians)} technicians. Total work minutes: {total_work_minutes}"
    )
    if technician_technology_skills is None:
        technician_technology_skills = {} # Default to empty if not provided
        _log(logger, "warning", "Technician technology skills not provided to assign_tasks. Skill-based assignment will be limited.")

    priority_order = {'A': 1, 'B': 2, 'C': 3, 'DEFAULT': 4}
    all_tasks_combined = []
    for task in tasks:
        task_type = task.get('task_type', '').upper()
        if task_type in ['PM', 'REP']:
            # Ensure 'name' key exists for consistent access later,
            # using 'scheduler_group_task' as the source if 'name' is initially missing.
            current_name = task.get('name')
            if not current_name:
                current_name = task.get('scheduler_group_task', 'Unknown Task')

            processed_task = {
                **task, # Spread original task first
                'name': current_name, # Ensure 'name' is set to the determined name
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
                    all_pm_task_names_from_excel_normalized_set,
                    technician_technology_skills=technician_technology_skills # Pass skills
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
                all_pm_task_names_from_excel_normalized_set,
                technician_technology_skills=technician_technology_skills # Pass skills
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
            all_pm_task_names_from_excel_normalized_set,
            technician_technology_skills=technician_technology_skills # Pass skills
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
