# wkndPlanning/dashboard.py
import logging # Add logging import
from .extract_data import get_current_day, get_current_shift, get_current_week_number, get_current_week # Corrected relative import
import os
from .task_assigner import assign_tasks # Corrected relative import
from .data_processing import calculate_work_time, sanitize_data, validate_assignments_flat_input #, calculate_available_time, normalize_string # Unused imports removed

def prepare_dashboard_data(tasks, assignments, unassigned_tasks, incomplete_tasks, logger=None): # Added logger
    pm_tasks_input = []
    rep_tasks_input = []

    # Extract and sort tasks by original numeric ID to preserve Excel order
    def extract_numeric_id(task_id):
        if task_id.startswith('pm'):
            # Extract numeric part from pmX format
            numeric_part = task_id[2:]
            try:
                return int(numeric_part)
            except ValueError:
                return 999999  # Fallback for non-numeric parts
        elif task_id.isdigit():
            return int(task_id)
        else:
            # For other formats (like additional_X), use a high number
            return 999999

    # The 'tasks' list is all_tasks_for_dashboard, which is already a combined list.
    # We sort them here to preserve original order from Excel file
    sorted_tasks_for_display_id_assignment = sorted(
        tasks,
        key=lambda t: (
            0 if t.get('task_type', '').upper() == 'PM' else 1,  # PMs first
            extract_numeric_id(str(t.get('id', '')))  # Then by numeric ID to match Excel order
        )
    )

    for task in sorted_tasks_for_display_id_assignment:
        if task.get('task_type', '').upper() == 'PM':
            pm_tasks_input.append(task)
        elif task.get('task_type', '').upper() == 'REP':
            rep_tasks_input.append(task)
        # else: # Other types if any, could be appended to a general list or ignored for these specific sections
            # _log(logger, "debug", f"Task {task.get('id')} with type {task.get('task_type')} not categorized as PM/REP for table sections.")
            # For now, only PM/REP are explicitly handled for separate table sections.
            # If a task is neither PM nor REP, it won't appear in pm_tasks_data or rep_tasks_data.
            # This behavior is consistent with the original separation.

    display_id_counter = 1
    original_task_id_to_display_id_map = {}

    def compute_task_display_data(task, current_display_id):
        original_id = str(task['id']) # Keep original ID for internal logic
        original_task_id_to_display_id_map[original_id] = current_display_id

        # Color calculation using the new display_id
        color_r = (current_display_id * 97 % 200 + 55)
        color_g = (current_display_id * 53 % 200 + 55)
        color_b = (current_display_id * 37 % 200 + 55)
        color_hex = f"#{color_r:02x}{color_g:02x}{color_b:02x}"

        # Logic for group_counter, unassigned_instance_details, incomplete_instances_list
        # This uses the original task ID (task_id_original_for_instances) for matching with assignments.
        task_id_original_for_instances = str(task['id'])
        quantity_val = int(task.get('quantity', 1))

        group_counter_calc = {}
        if assignments: # Ensure assignments is not None
            for i in range(quantity_val):
                instance_id_calc = f"{task_id_original_for_instances}_{i + 1}"
                group_assignments_calc = [a for a in assignments if a['instance_id'] == instance_id_calc]
                if group_assignments_calc:
                    group_names_calc = [str(a['technician']) for a in group_assignments_calc if a.get('technician') is not None]
                    if group_names_calc:
                        group_display_calc = " & ".join(sorted(list(set(group_names_calc))))
                        group_counter_calc[group_display_calc] = group_counter_calc.get(group_display_calc, 0) + 1

        unassigned_details_calc = []
        incomplete_list_calc = []
        for i in range(quantity_val):
            instance_id_calc = f"{task_id_original_for_instances}_{i + 1}"
            # unassigned_tasks is unassigned_reasons_dict, incomplete_tasks is incomplete_ids
            if unassigned_tasks and instance_id_calc in unassigned_tasks:
                unassigned_details_calc.append({'num': i + 1, 'reason': unassigned_tasks[instance_id_calc]})
            if incomplete_tasks and instance_id_calc in incomplete_tasks:
                incomplete_list_calc.append(i + 1)

        return {
            **task,
            'display_id': current_display_id,
            'color_hex': color_hex,
            'group_counter': group_counter_calc,
            'unassigned_instance_details': unassigned_details_calc,
            'incomplete_instances_list': incomplete_list_calc,
        }

    pm_tasks_data_final = []
    # Iterate based on the order in pm_tasks_input which came from sorted_tasks_for_display_id_assignment
    for task_item in pm_tasks_input:
        pm_tasks_data_final.append(compute_task_display_data(task_item, display_id_counter))
        display_id_counter += 1

    rep_tasks_data_final = []
    # Iterate based on the order in rep_tasks_input
    for task_item in rep_tasks_input:
        rep_tasks_data_final.append(compute_task_display_data(task_item, display_id_counter))
        display_id_counter += 1

    _log(logger, "debug", "Dashboard data prepared with display IDs and new color_hex values.")
    return pm_tasks_data_final, rep_tasks_data_final, original_task_id_to_display_id_map

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

def generate_html_files(all_tasks, present_technicians, rep_assignments, env, output_folder, all_technicians_global, technician_groups_global, db_conn, logger, technician_technology_skills=None):
    if logger is None:
        # Basic fallback logger if none is provided
        logger = logging.getLogger(__name__)
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)

    logger.info(f"Starting HTML file generation. Received {len(all_tasks)} tasks, {len(present_technicians)} present technicians.")
    if technician_technology_skills is None:
        technician_technology_skills = {} # Ensure it's a dict if not provided
        logger.warning("Technician technology skills not provided to generate_html_files. Skill-based assignment may be limited.")


    current_day = get_current_day()
    total_work_minutes = calculate_work_time(current_day)
    current_shift_type = get_current_shift()
    shift_start_time_str = "06:00" if current_shift_type == "early" else "18:00"

    # Sanitize data (e.g., ensure numeric types, default missing fields if any still exist)
    # sanitize_data itself also ensures 'name' from 'scheduler_group_task' if needed,
    # but app.py should have already done this robustly.
    tasks_for_processing = sanitize_data(all_tasks, logger) # Pass logger to sanitize_data

    _log(logger, "debug", f"Tasks for assigner in dashboard.py (after sanitize): {len(tasks_for_processing)}")
    # For detailed debugging of tasks entering assign_tasks:
    # for t_debug_dash in tasks_for_processing:
    #    _log(logger, "debug", f"  Dash SanTask: ID={t_debug_dash.get('id')}, Name='{t_debug_dash.get('name')}', Type={t_debug_dash.get('task_type')}, Add={t_debug_dash.get('isAdditionalTask')}")


    # Call the unified assign_tasks function
    assigned_tasks_details, unassigned_tasks_reasons, incomplete_tasks_ids, available_time_summary, under_resourced_pm_tasks = assign_tasks(
        tasks_for_processing,
        present_technicians,
        total_work_minutes,
        db_conn,
        rep_assignments, # Pass the filtered and structured REP assignments
        logger,
        technician_technology_skills=technician_technology_skills # Pass skills
    )
    logger.info(f"Task assignment phase completed. {len(assigned_tasks_details)} task segments assigned.")
    if unassigned_tasks_reasons:
        logger.warning(f"Task assignment completed with {len(unassigned_tasks_reasons)} unassigned task segments.")
    if incomplete_tasks_ids:
        logger.warning(f"Task assignment completed with {len(incomplete_tasks_ids)} incomplete task segments.")

    week_date_day_shift = {
        "week": get_current_week_number(),
        "date": get_current_week()[1].strftime("%d/%m/%Y"),
        "day": get_current_day(),
        "shift": get_current_shift().capitalize()
    }

    validated_assignments_to_render = validate_assignments_flat_input(assigned_tasks_details)

    # Pass logger to prepare_dashboard_data
    pm_tasks_data, rep_tasks_data, original_task_id_to_display_id_map = prepare_dashboard_data(
        tasks_for_processing, # Use the same list of tasks that assign_tasks used
        validated_assignments_to_render,
        unassigned_tasks_reasons,
        incomplete_tasks_ids,
        logger # Pass logger
    )

    technician_template = env.get_template('technician_dashboard.html')
    technician_html = technician_template.render(
        pm_tasks=pm_tasks_data,
        rep_tasks=rep_tasks_data,
        technicians=present_technicians,
        total_work_minutes=total_work_minutes,
        assignments=validated_assignments_to_render,
        shift_start_time_str=shift_start_time_str,
        week_date_day_shift=week_date_day_shift,
        all_technicians_config=all_technicians_global,
        technician_groups_config=technician_groups_global,
        original_task_id_to_display_id_map=original_task_id_to_display_id_map, # Pass the map
        under_resourced_pm_tasks=under_resourced_pm_tasks
    )

    output_path = os.path.join(output_folder, "technician_dashboard.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(technician_html)
    _log(logger, "info", f"Written output to {output_path} via dashboard.py")

    return available_time_summary, under_resourced_pm_tasks
