# wkndPlanning/task_assigner.py

from itertools import combinations, permutations # Ensure permutations is imported
from .data_processing import normalize_string
from .config_manager import TASK_NAME_MAPPING, TECHNICIAN_TASKS, TECHNICIAN_LINES # Corrected relative import
from ..services.db_utils import update_technician_skill, log_technician_skill_update

# Maximum number of high-priority tasks to consider for permutation-based optimization.
# 7! = 5040, 8! = 40320. Keep this value mindful of performance.
MAX_PERMUTATION_TASKS = 3

# Performance tuning: Maximum number of top-skilled technicians to consider for PM task combinations.
# This helps prevent combinatorial explosion with large numbers of eligible technicians.
MAX_TECHS_FOR_COMBINATIONS = 12
# Performance tuning: Range of group sizes to check around the required number of technicians.
# e.g., a range of 1 means for a 3-tech task, we check groups of size 2, 3, and 4.
# A smaller range reduces the number of combinations to check.
GROUP_SIZE_SEARCH_RANGE = 1


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
            penalty_score_from_unassigned_or_incomplete += task_def['priority_val']

    return (num_fully_assigned_hp_task_definitions, -penalty_score_from_unassigned_or_incomplete)

def _assign_task_definition_to_schedule(
    task_to_assign, present_technicians, total_work_minutes, rep_assignments, logger,
    technician_schedules, all_task_assignments_details,
    unassigned_tasks_reasons_dict, incomplete_tasks_instance_ids,
    all_pm_task_names_from_excel_normalized_set, # Passed through
    db_conn, # Pass the database connection
    technician_technology_skills=None,
    under_resourced_tasks=None,
    technician_groups=None
):
    """
    Processes a single task definition (which may have multiple instances due to quantity)
    and attempts to assign its instances to the provided schedules.
    This function encapsulates the main loop body from the original assign_tasks.
    Modifies technician_schedules, all_task_assignments_details, etc., in-place.
    """
    task_id = task_to_assign['id']
    task_name_excel = task_to_assign.get('name', 'Unknown')
    task_type = task_to_assign['task_type_upper']
    base_duration = int(task_to_assign.get('planned_worktime_min', 0))
    num_technicians_needed = int(task_to_assign.get('mitarbeiter_pro_aufgabe', 1))
    quantity = int(task_to_assign.get('quantity', 1))
    is_additional_task_flag = task_to_assign.get('isAdditionalTask', False)
    task_technology_ids = task_to_assign.get('technology_ids', [])

    if quantity <= 0:
        reason = f"Skipped ({task_type}): Invalid 'Quantity' ({quantity})."
        for i in range(1, max(1, quantity if quantity > 0 else 1)):
             unassigned_tasks_reasons_dict[f"{task_id}_{i}"] = reason
        return

    if num_technicians_needed == 0:
        if base_duration == 0:
            reason = f"Skipped ({task_type}): Task requires 0 technicians and has 0 duration. Cannot be scheduled."
        else:
            reason = f"Skipped ({task_type}): Invalid 'Mitarbeiter pro Aufgabe' (0) for non-zero duration task."

        for i in range(1, quantity + 1):
            unassigned_tasks_reasons_dict[f"{task_id}_{i}"] = reason
        _log(logger, "warning", f"Task definition {task_name_excel} (ID: {task_id}) unassigned for all {quantity} instances: {reason}")
        return

    if num_technicians_needed < 0:
        reason = f"Skipped ({task_type}): Invalid 'Mitarbeiter pro Aufgabe' ({num_technicians_needed}) - value must be positive."
        for i in range(1, quantity + 1):
            unassigned_tasks_reasons_dict[f"{task_id}_{i}"] = reason
        _log(logger, "warning", f"Task definition {task_name_excel} (ID: {task_id}) unassigned for all {quantity} instances: {reason}")
        return

    task_lines_str = str(task_to_assign.get('lines', ''))
    task_lines_list = []
    if task_lines_str and task_lines_str.lower() != 'nan' and task_lines_str.strip() != '':
        try:
            task_lines_list = [int(line.strip()) for line in task_lines_str.split(',') if line.strip().isdigit()]
        except ValueError:
            _log(logger, "warning", f"  Warning ({task_type}): Invalid line format '{task_lines_str}' for task {task_name_excel}")

    for instance_num in range(1, quantity + 1):
        instance_id_str = f"{task_id}_{instance_num}"
        instance_task_display_name = f"{task_name_excel} (Instance {instance_num}/{quantity})"
        assigned_this_instance_flag = False
        last_known_failure_reason_for_instance = f"Could not find a suitable time slot or group for {instance_task_display_name}."

        if task_type == 'PM' and not is_additional_task_flag:
            _log(logger, "debug", f"    (Helper) Assigning Standard PM instance: {instance_task_display_name}, Required Technology IDs: {task_technology_ids}")

            if not task_technology_ids:
                last_known_failure_reason_for_instance = f"Skipped (PM): Task {task_name_excel} (ID: {task_id}) has no required technology_ids defined."
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                _log(logger, "warning", f"      {last_known_failure_reason_for_instance}")
                continue

            eligible_technicians_details_pm = []
            for tech_cand_pm in present_technicians:
                tech_skills_map = technician_technology_skills.get(tech_cand_pm, {})

                possesses_at_least_one_required_skill = any(
                    skill_id in tech_skills_map and tech_skills_map[skill_id] > 0
                    for skill_id in task_technology_ids
                )
                if not possesses_at_least_one_required_skill:
                    continue

                tech_lines_pm = TECHNICIAN_LINES.get(tech_cand_pm, [])
                line_match = not task_lines_list or any(line in tech_lines_pm for line in task_lines_list)
                if not line_match:
                    continue

                relevant_skills_for_tech = {
                    skill_id: tech_skills_map[skill_id]
                    for skill_id in task_technology_ids
                    if skill_id in tech_skills_map and tech_skills_map[skill_id] > 0
                }
                if not relevant_skills_for_tech:
                    continue

                eligible_technicians_details_pm.append({
                    'name': tech_cand_pm,
                    'relevant_skills': relevant_skills_for_tech
                })

            if not eligible_technicians_details_pm:
                last_known_failure_reason_for_instance = "No technicians eligible for this PM task (possess at least one skill > 0, meet line/task mapping)."
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                _log(logger, "warning", f"      {last_known_failure_reason_for_instance} for {instance_task_display_name}")
                continue

            if num_technicians_needed > 0 and len(eligible_technicians_details_pm) < num_technicians_needed:
                if under_resourced_tasks is not None:
                    is_already_added = any(t['task_id'] == task_id for t in under_resourced_tasks)
                    if not is_already_added:
                        under_resourced_tasks.append({
                            'task_id': task_id,
                            'task_name': task_name_excel,
                            'needed': num_technicians_needed,
                            'available': len(eligible_technicians_details_pm),
                            'eligible_technicians': [d['name'] for d in eligible_technicians_details_pm]
                        })

            def get_tech_score(tech_details):
                return sum(tech_details['relevant_skills'].values())

            eligible_technicians_details_pm.sort(key=get_tech_score, reverse=True)

            if len(eligible_technicians_details_pm) > MAX_TECHS_FOR_COMBINATIONS:
                eligible_technicians_details_pm = eligible_technicians_details_pm[:MAX_TECHS_FOR_COMBINATIONS]

            sorted_eligible_tech_names_pm = [d['name'] for d in eligible_technicians_details_pm]
            tech_details_map_pm = {d['name']: d for d in eligible_technicians_details_pm}

            viable_groups_with_scores_pm = []
            
            possible_sizes_to_try = []
            if num_technicians_needed > 0 and len(sorted_eligible_tech_names_pm) > 0:
                min_size = max(1, num_technicians_needed - GROUP_SIZE_SEARCH_RANGE)
                max_size = min(len(sorted_eligible_tech_names_pm), num_technicians_needed + GROUP_SIZE_SEARCH_RANGE)
                
                unique_sizes = set()
                for i in range(min_size, max_size + 1):
                    unique_sizes.add(i)
                
                if num_technicians_needed <= len(sorted_eligible_tech_names_pm):
                    unique_sizes.add(num_technicians_needed)

                possible_sizes_to_try = sorted(list(unique_sizes), key=lambda s: (abs(s - num_technicians_needed), s))
            
            for r_actual_group_size in possible_sizes_to_try:
                for group_tuple in combinations(sorted_eligible_tech_names_pm, r_actual_group_size):
                    group_tech_names = list(group_tuple)
                    if not group_tech_names: continue

                    group_skills_possessed_by_id = set()
                    for tech_name_in_group in group_tech_names:
                        group_skills_possessed_by_id.update(tech_details_map_pm[tech_name_in_group]['relevant_skills'].keys())

                    if not set(task_technology_ids).issubset(group_skills_possessed_by_id):
                        continue

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
                            per_skill_avg_levels[req_skill_id] = 0

                    total_skill_points_in_group_for_required_skills = 0
                    count_of_possessed_required_skills_in_group = 0
                    for tech_name_in_group in group_tech_names:
                        for req_skill_id in task_technology_ids:
                            if req_skill_id in tech_details_map_pm[tech_name_in_group]['relevant_skills']:
                                total_skill_points_in_group_for_required_skills += tech_details_map_pm[tech_name_in_group]['relevant_skills'][req_skill_id]
                                count_of_possessed_required_skills_in_group += 1

                    combined_avg_skill_level_group = 0
                    if count_of_possessed_required_skills_in_group > 0:
                        combined_avg_skill_level_group = total_skill_points_in_group_for_required_skills / count_of_possessed_required_skills_in_group

                    workload = sum(sum(end - start for start, end, _ in technician_schedules[tn]) for tn in group_tech_names)

                    viable_groups_with_scores_pm.append({
                        'group': group_tech_names,
                        'len': r_actual_group_size,
                        'per_skill_avg': per_skill_avg_levels,
                        'combined_avg_skill': combined_avg_skill_level_group,
                        'workload': workload,
                        'size_diff': abs(r_actual_group_size - num_technicians_needed)
                    })

            if str(task_to_assign.get('priority', 'C')).upper() == 'A' and 0 < len(sorted_eligible_tech_names_pm) < num_technicians_needed:
                _log(logger, "info", f"Task {task_name_excel} is Prio 'A' with {len(sorted_eligible_tech_names_pm)}/{num_technicians_needed} skilled techs. Seeking helpers.")

                helper_technicians_details_pm = []
                skilled_names_set = set(sorted_eligible_tech_names_pm)
                for tech_cand_pm in present_technicians:
                    if tech_cand_pm in skilled_names_set:
                        continue
                    
                    tech_lines_pm = TECHNICIAN_LINES.get(tech_cand_pm, [])
                    line_match = not task_lines_list or any(line in tech_lines_pm for line in task_lines_list)
                    if line_match:
                        helper_technicians_details_pm.append({'name': tech_cand_pm})
                
                all_helper_names = [d['name'] for d in helper_technicians_details_pm]
                
                for num_skilled in range(len(sorted_eligible_tech_names_pm), 0, -1):
                    num_helpers_needed = num_technicians_needed - num_skilled
                    if num_helpers_needed <= 0 or len(all_helper_names) < num_helpers_needed:
                        continue

                    for skilled_group_tuple in combinations(sorted_eligible_tech_names_pm, num_skilled):
                        skilled_names = list(skilled_group_tuple)
                        
                        group_skills_possessed_by_id = set()
                        for tech_name_in_group in skilled_names:
                            group_skills_possessed_by_id.update(tech_details_map_pm[tech_name_in_group]['relevant_skills'].keys())
                        
                        if not set(task_technology_ids).issubset(group_skills_possessed_by_id):
                            continue

                        for helper_group_tuple in combinations(all_helper_names, num_helpers_needed):
                            group_tech_names = skilled_names + list(helper_group_tuple)
                            
                            per_skill_avg_levels = {}
                            for req_skill_id in task_technology_ids:
                                techs_with_this_skill_in_group = [
                                    tech_name for tech_name in skilled_names
                                    if req_skill_id in tech_details_map_pm[tech_name]['relevant_skills']
                                ]
                                if techs_with_this_skill_in_group:
                                    avg_level_for_skill = sum(
                                        tech_details_map_pm[tech_name]['relevant_skills'][req_skill_id]
                                        for tech_name in techs_with_this_skill_in_group
                                    ) / len(techs_with_this_skill_in_group)
                                    per_skill_avg_levels[req_skill_id] = avg_level_for_skill
                                else:
                                    per_skill_avg_levels[req_skill_id] = 0

                            total_skill_points_in_group_for_required_skills = 0
                            count_of_possessed_required_skills_in_group = 0
                            for tech_name_in_group in skilled_names:
                                for req_skill_id in task_technology_ids:
                                    if req_skill_id in tech_details_map_pm[tech_name_in_group]['relevant_skills']:
                                        total_skill_points_in_group_for_required_skills += tech_details_map_pm[tech_name_in_group]['relevant_skills'][req_skill_id]
                                        count_of_possessed_required_skills_in_group += 1

                            combined_avg_skill_level_group = 0
                            if count_of_possessed_required_skills_in_group > 0:
                                combined_avg_skill_level_group = total_skill_points_in_group_for_required_skills / count_of_possessed_required_skills_in_group

                            workload = sum(sum(end - start for start, end, _ in technician_schedules[tn]) for tn in group_tech_names)
                            
                            viable_groups_with_scores_pm.append({
                                'group': group_tech_names,
                                'len': num_technicians_needed,
                                'per_skill_avg': per_skill_avg_levels,
                                'combined_avg_skill': combined_avg_skill_level_group,
                                'workload': workload,
                                'size_diff': 0,
                                'is_helper_group': True
                            })
                    
                    if any(g.get('is_helper_group') for g in viable_groups_with_scores_pm):
                        break

            sorted_req_skill_ids_for_sorting = sorted(list(task_technology_ids))

            def get_group_priority_score(group_tech_names):
                if not technician_groups: return float('inf')
                min_priority = float('inf')
                for tech_name in group_tech_names:
                    tech_group_data = technician_groups.get(tech_name)
                    if tech_group_data:
                        priority = tech_group_data['priorities'].get(task_id)
                        if priority is not None and priority < min_priority:
                            min_priority = priority
                return min_priority

            viable_groups_with_scores_pm.sort(key=lambda x: (
                get_group_priority_score(x['group']),
                x['size_diff'],
                tuple(-x['per_skill_avg'].get(skill_id, 0) for skill_id in sorted_req_skill_ids_for_sorting),
                -x['combined_avg_skill'],
                x['workload'],
                ''.join(sorted(x['group']))
            ))

            if not viable_groups_with_scores_pm:
                if num_technicians_needed > 0:
                    last_known_failure_reason_for_instance = f"No viable technician groups found that collectively cover all required skills: {task_technology_ids}. Eligible techs: {len(sorted_eligible_tech_names_pm)} (Target size: {num_technicians_needed})."
                elif num_technicians_needed == 0 and base_duration == 0:
                    last_known_failure_reason_for_instance = "Failed to process 0-tech, 0-duration PM task (no dummy group)."
                else:
                    last_known_failure_reason_for_instance = f"No eligible technicians for 0-tech PM task {task_name_excel} (or other issue)."

                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                _log(logger, "warning", f"      {last_known_failure_reason_for_instance} for {instance_task_display_name}")
                continue

            assignment_successful_this_instance = False
            final_chosen_group_for_instance = None
            final_start_time_for_instance = 0
            final_assigned_duration_for_instance = 0
            final_technician_task_info = 'Skill_Based'
            final_is_helper_group = False

            for group_candidate_data in viable_groups_with_scores_pm:
                current_candidate_group = group_candidate_data['group']
                current_actual_num_assigned = len(current_candidate_group)

                current_effective_duration = base_duration
                if base_duration > 0 and num_technicians_needed > 0 and current_actual_num_assigned > 0:
                    current_effective_duration = (base_duration * num_technicians_needed) / current_actual_num_assigned
                elif base_duration == 0:
                    current_effective_duration = 0

                search_start_time = 0
                slot_found_for_this_group = False
                is_incomplete_for_slot = False

                while search_start_time <= total_work_minutes:
                    if current_effective_duration == 0 and search_start_time > total_work_minutes: break
                    if current_effective_duration > 0 and search_start_time >= total_work_minutes: break

                    duration_to_check = 1 if current_effective_duration == 0 else current_effective_duration

                    if current_effective_duration > 0 and (search_start_time + current_effective_duration > total_work_minutes):
                        remaining_time_in_shift = max(0, total_work_minutes - search_start_time)
                        min_acceptable_partial_duration = current_effective_duration * 0.75

                        if remaining_time_in_shift >= min_acceptable_partial_duration and remaining_time_in_shift > 0:
                            duration_to_check = remaining_time_in_shift
                            is_incomplete_for_slot = True
                        else:
                            search_start_time += 15
                            continue
                    else:
                        is_incomplete_for_slot = False


                    all_techs_in_group_available_at_slot = True
                    if not current_candidate_group and num_technicians_needed > 0 :
                         all_techs_in_group_available_at_slot = False

                    for tech_in_group_name in current_candidate_group:
                        if not all(sch_end <= search_start_time or sch_start >= search_start_time + duration_to_check
                                   for sch_start, sch_end, _ in technician_schedules[tech_in_group_name]):
                            all_techs_in_group_available_at_slot = False
                            break

                    if all_techs_in_group_available_at_slot:
                        final_chosen_group_for_instance = current_candidate_group
                        final_start_time_for_instance = search_start_time
                        final_assigned_duration_for_instance = duration_to_check if current_effective_duration > 0 else 0

                        final_is_helper_group = group_candidate_data.get('is_helper_group', False)
                        assignment_successful_this_instance = True
                        slot_found_for_this_group = True
                        if is_incomplete_for_slot:
                            if instance_id_str not in incomplete_tasks_instance_ids:
                                incomplete_tasks_instance_ids.append(instance_id_str)
                        break
                    else:
                        search_start_time += 15

                if assignment_successful_this_instance:
                    break

            if assignment_successful_this_instance:
                assigned_this_instance_flag = True
                if instance_id_str in unassigned_tasks_reasons_dict:
                    del unassigned_tasks_reasons_dict[instance_id_str]

                if final_is_helper_group:
                    helpers_in_group = [tech for tech in final_chosen_group_for_instance if tech not in tech_details_map_pm]
                    if helpers_in_group:
                        helper_names_str = ', '.join(helpers_in_group)
                        _log(logger, "info", f"Helper(s) assigned to task {task_name_excel} (ID: {task_id}): {helper_names_str}")
                        try:
                            cursor = db_conn.cursor()
                            for helper_name in helpers_in_group:
                                cursor.execute("SELECT id FROM technicians WHERE name = ?", (helper_name,))
                                helper_row = cursor.fetchone()
                                if not helper_row:
                                    continue
                                helper_id = helper_row[0]
                                for tech_id in task_technology_ids:
                                    cursor.execute("SELECT skill_level FROM technician_technology_skills WHERE technician_id = ? AND technology_id = ?", (helper_id, tech_id))
                                    skill_row = cursor.fetchone()
                                    prev_level = skill_row[0] if skill_row else 0
                                    if prev_level == 0:
                                        update_technician_skill(db_conn, helper_id, tech_id, 1)
                                        log_technician_skill_update(
                                            db_conn,
                                            helper_id,
                                            tech_id,
                                            task_id,
                                            prev_level,
                                            1,
                                            f"Worked on task {task_name_excel} and level updated: 0 -> 1"
                                        )
                                        _log(logger, "info", f"Helper {helper_name} skill for technology {tech_id} updated from 0 to 1 due to assignment to {task_name_excel}")
                            db_conn.commit()
                        except Exception as e:
                            _log(logger, "warning", f"Helper skill update/logging failed for task {task_name_excel} (ID: {task_id}): {e}")

                resource_mismatch_note_pm = None
                if num_technicians_needed > 0:
                    if len(final_chosen_group_for_instance) != num_technicians_needed:
                        resource_mismatch_note_pm = f"Task planned for {num_technicians_needed} techs; assigned to {len(final_chosen_group_for_instance)}."
                    else:
                        resource_mismatch_note_pm = f"Assigned {len(final_chosen_group_for_instance)} as planned."
                elif num_technicians_needed == 0 and len(final_chosen_group_for_instance) > 0:
                     resource_mismatch_note_pm = f"Task planned for 0 techs; assigned to {len(final_chosen_group_for_instance)}."

                if not final_chosen_group_for_instance:
                    all_task_assignments_details.append({
                        'technician': None, 'task_name': instance_task_display_name,
                        'start': final_start_time_for_instance, 'duration': final_assigned_duration_for_instance,
                        'is_incomplete': instance_id_str in incomplete_tasks_instance_ids,
                        'original_duration': base_duration, 'instance_id': instance_id_str,
                        'technician_task_info': final_technician_task_info,
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
                            'technician_task_info': final_technician_task_info,
                            'resource_mismatch_info': resource_mismatch_note_pm
                        })
                _log(logger, "info", f"    (Helper) Successfully scheduled PM {instance_task_display_name} for group {final_chosen_group_for_instance} at {final_start_time_for_instance} for {final_assigned_duration_for_instance} min. Incomplete: {instance_id_str in incomplete_tasks_instance_ids}. Required skills: {task_technology_ids}")
            else:
                if not last_known_failure_reason_for_instance or "Could not find a suitable time slot" in last_known_failure_reason_for_instance or "No viable technician groups" in last_known_failure_reason_for_instance:
                    last_known_failure_reason_for_instance = f"No suitable group/slot for PM task {instance_task_display_name}. Required skills: {task_technology_ids}"
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                _log(logger, "warning", f"      Failed to assign PM instance {instance_task_display_name}. Reason: {last_known_failure_reason_for_instance}")

        elif task_type == 'REP':
            _log(logger, "debug", f"    (Helper) Assigning REP instance: {instance_task_display_name}")
            rep_assignments_map = {item['task_id']: item for item in rep_assignments} if rep_assignments else {}
            assignment_info_rep = rep_assignments_map.get(task_id)

            if not assignment_info_rep:
                last_known_failure_reason_for_instance = "Skipped (REP): Task data not received from UI."
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                continue
            if assignment_info_rep.get('skipped'):
                last_known_failure_reason_for_instance = assignment_info_rep.get('skip_reason', "Skipped by user.")
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                continue

            selected_tech_assignments_from_ui = assignment_info_rep.get('technicians', [])
            raw_user_selection_count_rep = len(selected_tech_assignments_from_ui)
            
            selected_tech_names_from_ui = [tech['name'] for tech in selected_tech_assignments_from_ui]
            
            eligible_user_selected_techs_rep = [
                tech_name for tech_name in selected_tech_names_from_ui
                if tech_name in present_technicians and
                   (not task_lines_list or any(line in TECHNICIAN_LINES.get(tech_name, []) for line in task_lines_list))
            ]

            forced_tech_names = {
                tech['name'] for tech in selected_tech_assignments_from_ui
                if tech.get('force_assign') and tech['name'] in eligible_user_selected_techs_rep
            }

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
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                continue

            viable_groups_with_scores_rep = []
            
            other_eligible_techs = [tech for tech in eligible_user_selected_techs_rep if tech not in forced_tech_names]
            forced_tech_list = list(forced_tech_names)

            for r_size in range(len(other_eligible_techs) + 1):
                for other_group_tuple in combinations(other_eligible_techs, r_size):
                    group = forced_tech_list + list(other_group_tuple)
                    if not group: continue

                    workload = sum(sum(end - start for start, end, _ in technician_schedules[tn]) for tn in group)
                    viable_groups_with_scores_rep.append({'group': group, 'len': len(group), 'workload': workload})

            if not viable_groups_with_scores_rep and num_technicians_needed > 0:
                last_known_failure_reason_for_instance = "Skipped (REP): No viable groups could be formed from eligible UI-selected techs."
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance
                continue

            viable_groups_with_scores_rep.sort(key=lambda x: (abs(x['len'] - num_technicians_needed), x['workload'], ''.join(sorted(x['group']))))

            assignment_successful_this_instance_rep = False
            final_chosen_group_for_rep_instance = None
            final_start_time_for_rep_instance = 0
            final_assigned_duration_for_rep_instance = 0
            final_resource_mismatch_note_rep = None

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
                    elif raw_user_selection_count_rep != num_technicians_needed:
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
                        
                        if current_effective_duration_rep > 0 and (final_start_time_for_rep_instance + current_effective_duration_rep > total_work_minutes):
                            remaining_time = max(0, total_work_minutes - final_start_time_for_rep_instance)
                            min_acceptable_partial = current_effective_duration_rep * 0.75
                            if remaining_time >= min_acceptable_partial and remaining_time > 0:
                                assigned_duration_gantt_rep = remaining_time
                                if instance_id_str not in incomplete_tasks_instance_ids: incomplete_tasks_instance_ids.append(instance_id_str)
                            else:
                                all_techs_in_rep_group_available = False

                        if all_techs_in_rep_group_available:
                            final_assigned_duration_for_rep_instance = assigned_duration_gantt_rep
                            final_resource_mismatch_note_rep = current_resource_mismatch_note_rep_candidate
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
                        'original_duration': base_duration,
                        'instance_id': instance_id_str,
                        'technician_task_info': 'N/A_REP',
                        'resource_mismatch_info': final_resource_mismatch_note_rep
                    })
            else:
                if not last_known_failure_reason_for_instance or "Could not find a suitable time slot" in last_known_failure_reason_for_instance:
                    last_known_failure_reason_for_instance = "No group/slot for REP task from UI selection."
                unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance

        if not assigned_this_instance_flag and instance_id_str not in unassigned_tasks_reasons_dict:
            unassigned_tasks_reasons_dict[instance_id_str] = last_known_failure_reason_for_instance

def assign_tasks(tasks, present_technicians, total_work_minutes, db_conn, rep_assignments=None, logger=None, technician_technology_skills=None):
    _log(logger, "info",
        f"Unified Assigning (Global Opt Mode): {len(tasks)} tasks with {len(present_technicians)} technicians. Total work minutes: {total_work_minutes}"
    )
    if technician_technology_skills is None:
        technician_technology_skills = {}
        _log(logger, "warning", "Technician technology skills not provided to assign_tasks. Skill-based assignment will be limited.")

    technician_groups = _get_technician_groups(db_conn)

    priority_order = {'A': 1, 'B': 2, 'C': 3, 'DEFAULT': 4}
    all_tasks_combined = []
    under_resourced_tasks = []
    for task in tasks:
        task_type = task.get('task_type', '').upper()
        if task_type in ['PM', 'REP']:
            current_name = task.get('name')
            if not current_name:
                current_name = task.get('scheduler_group_task', 'Unknown Task')

            processed_task = {
                **task,
                'name': current_name,
                'task_type_upper': task_type,
                'priority_val': priority_order.get(str(task.get('priority', 'C')).upper(), priority_order['DEFAULT'])
            }
            all_tasks_combined.append(processed_task)

    all_tasks_combined.sort(key=lambda x: (x['priority_val'], x['id']))

    all_pm_task_names_from_excel_normalized_set = {
        normalize_string(TASK_NAME_MAPPING.get(t['name'], t['name']))
        for t in all_tasks_combined if t['task_type_upper'] == 'PM'
    }

    hp_tasks = [t for t in all_tasks_combined if t['priority_val'] == 1]
    other_tasks = [t for t in all_tasks_combined if t['priority_val'] != 1]

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
        best_hp_overall_score = (-1, float('inf'))

        count = 0
        num_permutations = 0
        if len(hp_tasks) > 0:
            num_permutations = 1
            for i in range(1, len(hp_tasks) + 1): num_permutations *= i

        for p_hp_task_list in permutations(hp_tasks):
            count += 1

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
                    db_conn,
                    technician_technology_skills=technician_technology_skills,
                    under_resourced_tasks=under_resourced_tasks,
                    technician_groups=technician_groups
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
        final_unassigned_tasks_reasons_dict.update(best_hp_overall_unassigned_reasons)
        final_incomplete_tasks_instance_ids.extend(iid for iid in best_hp_overall_incomplete_ids if iid not in final_incomplete_tasks_instance_ids)

    else: 
        if len(hp_tasks) > MAX_PERMUTATION_TASKS:
            _log(logger, "info", f"Number of high-priority tasks ({len(hp_tasks)}) > {MAX_PERMUTATION_TASKS}. Assigning HP tasks greedily.")
            hp_tasks.sort(key=lambda t: (
                -int(t.get('mitarbeiter_pro_aufgabe', 1)),
                -int(t.get('planned_worktime_min', 0)),
                t['id']
            ))
            _log(logger, "info", "Greedy HP tasks re-sorted by num_techs (desc), duration (desc), id (asc).")
        elif not hp_tasks:
             _log(logger, "info", "No high-priority tasks to optimize with permutations.")

        for task_def in hp_tasks:
            _assign_task_definition_to_schedule(
                task_def, present_technicians, total_work_minutes, rep_assignments, logger,
                final_technician_schedules, final_all_task_assignments_details,
                final_unassigned_tasks_reasons_dict, final_incomplete_tasks_instance_ids,
                all_pm_task_names_from_excel_normalized_set,
                db_conn,
                technician_technology_skills=technician_technology_skills,
                under_resourced_tasks=under_resourced_tasks,
                technician_groups=technician_groups
            )

    _log(logger, "info", "Assigning other-priority tasks.")
    other_tasks.sort(key=lambda t: (
        t['priority_val'],
        -int(t.get('mitarbeiter_pro_aufgabe', 1)),
        -int(t.get('planned_worktime_min', 0)),
        t['id']
    ))
    _log(logger, "info", "Other-priority tasks re-sorted by prio (asc), num_techs (desc), duration (desc), id (asc).")

    for task_def in other_tasks:
        _assign_task_definition_to_schedule(
            task_def, present_technicians, total_work_minutes, rep_assignments, logger,
            final_technician_schedules, final_all_task_assignments_details,
            final_unassigned_tasks_reasons_dict, final_incomplete_tasks_instance_ids,
            all_pm_task_names_from_excel_normalized_set,
            db_conn,
            technician_technology_skills=technician_technology_skills,
            under_resourced_tasks=under_resourced_tasks,
            technician_groups=technician_groups
        )

    final_available_time_summary_map = {tech: total_work_minutes for tech in present_technicians}
    for tech_name_final, schedule_entries_final in final_technician_schedules.items():
        total_scheduled_time_for_tech = sum(end - start for start, end, _ in schedule_entries_final)
        final_available_time_summary_map[tech_name_final] -= total_scheduled_time_for_tech
        if final_available_time_summary_map[tech_name_final] < 0:
            final_available_time_summary_map[tech_name_final] = 0


    _log(logger, "info", f"Unified task assignment process completed. Assigned {len(final_all_task_assignments_details)} task segments.")
    if final_unassigned_tasks_reasons_dict:
        _log(logger, "warning", f"Unassigned task instances: {len(final_unassigned_tasks_reasons_dict)}. Reasons (sample):")
        count = 0
        for inst_id, reason in final_unassigned_tasks_reasons_dict.items():
            _log(logger, "warning", f"  - Instance {inst_id}: {reason}")
            count +=1
            if count >= 10 and len(final_unassigned_tasks_reasons_dict) > 15 :
                _log(logger, "warning", f"  ... and {len(final_unassigned_tasks_reasons_dict) - count} more unassigned instances.")
                break


    if final_incomplete_tasks_instance_ids:
        _log(logger, "info", f"Incomplete task instances (due to shift end): {len(final_incomplete_tasks_instance_ids)} -> {final_incomplete_tasks_instance_ids}")

    if under_resourced_tasks:
        _log(logger, "warning", f"Under-resourced PM tasks detected: {under_resourced_tasks}")

    return final_all_task_assignments_details, final_unassigned_tasks_reasons_dict, final_incomplete_tasks_instance_ids, final_available_time_summary_map, under_resourced_tasks


def _get_technician_groups(db_conn):
    cursor = db_conn.cursor()
    
    # Get all groups
    cursor.execute("SELECT id, name FROM technician_groups")
    groups = {row['id']: {'name': row['name'], 'members': [], 'priorities': {}} for row in cursor.fetchall()}
    
    # Get group members
    cursor.execute("SELECT g.name as group_name, t.name as tech_name FROM technician_group_members gm JOIN technicians t ON gm.technician_id = t.id JOIN technician_groups g ON gm.group_id = g.id")
    technician_to_groups = {}
    for row in cursor.fetchall():
        if row['tech_name'] not in technician_to_groups:
            technician_to_groups[row['tech_name']] = []
        technician_to_groups[row['tech_name']].append(row['group_name'])
            
    # Get group priorities
    cursor.execute("SELECT g.name as group_name, p.task_type_id, p.priority FROM technician_group_priorities p JOIN technician_groups g ON p.group_id = g.id")
    group_priorities = {}
    for row in cursor.fetchall():
        if row['group_name'] not in group_priorities:
            group_priorities[row['group_name']] = {}
        group_priorities[row['group_name']][row['task_type_id']] = row['priority']

    # Combine into a technician-centric view
    technician_groups_data = {}
    for tech_name, tech_groups in technician_to_groups.items():
        technician_groups_data[tech_name] = {'groups': tech_groups, 'priorities': {}}
        for group_name in tech_groups:
            if group_name in group_priorities:
                for task_type_id, priority in group_priorities[group_name].items():
                    if task_type_id not in technician_groups_data[tech_name]['priorities'] or priority < technician_groups_data[tech_name]['priorities'][task_type_id]:
                        technician_groups_data[tech_name]['priorities'][task_type_id] = priority

    return technician_groups_data