# wkndPlanning/dashboard.py
import os
import traceback
from data_processing import sanitize_data, calculate_work_time, validate_assignments_flat_input
from task_assigner import assign_tasks
from extract_data import get_current_day, get_current_week_number, get_current_week, get_current_shift

def prepare_dashboard_data(tasks, assignments, unassigned_tasks, incomplete_tasks):
    pm_tasks = []
    rep_tasks = []
    for task in tasks:
        if task.get('task_type', '').upper() == 'PM':
            pm_tasks.append(task)
        elif task.get('task_type', '').upper() == 'REP':
            rep_tasks.append(task)

    def compute_task_data(task):
        task_id = str(task['id'])
        quantity = int(task.get('quantity', 1))
        color_r = ((int(task_id) if task_id.isdigit() else 1) * 97 % 200 + 55)
        color_g = ((int(task_id) if task_id.isdigit() else 1) * 53 % 200 + 55)
        color_b = ((int(task_id) if task_id.isdigit() else 1) * 37 % 200 + 55)
        color_hex = f"#{color_r:02x}{color_g:02x}{color_b:02x}"

        group_counter = {}
        for i in range(quantity):
            instance_id = f"{task_id}_{i + 1}"
            group_assignments = [a for a in assignments if a['instance_id'] == instance_id]
            if group_assignments:
                group_names = [str(a['technician']) for a in group_assignments if a.get('technician') is not None]
                if group_names:
                    group_display = " & ".join(sorted(list(set(group_names))))
                    group_counter[group_display] = group_counter.get(group_display, 0) + 1

        unassigned_instance_details = []
        incomplete_instances_list = []
        for i in range(quantity):
            instance_id = f"{task_id}_{i + 1}"
            if unassigned_tasks and instance_id in unassigned_tasks:
                unassigned_instance_details.append({'num': i + 1, 'reason': unassigned_tasks[instance_id]})
            if incomplete_tasks and instance_id in incomplete_tasks:
                incomplete_instances_list.append(i + 1)

        return {
            **task,
            'color_hex': color_hex,
            'group_counter': group_counter,
            'unassigned_instance_details': unassigned_instance_details,
            'incomplete_instances_list': incomplete_instances_list,
        }

    pm_tasks_data = [compute_task_data(task) for task in pm_tasks]
    rep_tasks_data = [compute_task_data(task) for task in rep_tasks]
    print("Dashboard data prepared via dashboard.py")
    return pm_tasks_data, rep_tasks_data

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

def generate_html_files(data, present_technicians, rep_assignments, jinja_env, output_folder_path, config_technicians, config_technician_groups, logger=None):
    try:
        # if logger: # Use the passed logger directly
        #     logger.debug(f"dashboard.py: generate_html_files received present_technicians: {present_technicians}")
        #     logger.debug(f"dashboard.py: generate_html_files received config_technicians (all): {config_technicians}")
        #     logger.debug(f"dashboard.py: generate_html_files received config_technician_groups: {config_technician_groups}")
        # else: # Fallback if no logger
        #     print(f"DEBUG dashboard.py: generate_html_files received present_technicians: {present_technicians}")
        #     print(f"DEBUG dashboard.py: generate_html_files received config_technicians (all): {config_technicians}")
        #     print(f"DEBUG dashboard.py: generate_html_files received config_technician_groups: {config_technician_groups}")

        sanitized_data_list = sanitize_data(data)
        tasks_for_processing = []
        for idx, row in enumerate(sanitized_data_list, start=1):
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

        current_day = get_current_day()
        total_work_minutes = calculate_work_time(current_day)
        current_shift_type = get_current_shift()
        shift_start_time_str = "06:00" if current_shift_type == "early" else "18:00"

        assignments_flat, unassigned_reasons_dict, incomplete_ids, final_available_time = assign_tasks(
            tasks_for_processing,
            present_technicians,
            total_work_minutes,
            rep_assignments,
            logger=logger  # Pass the logger instance
        )

        week_date_day_shift = {
            "week": get_current_week_number(),
            "date": get_current_week()[1].strftime("%d/%m/%Y"),
            "day": get_current_day(),
            "shift": get_current_shift().capitalize()
        }

        validated_assignments_to_render = validate_assignments_flat_input(assignments_flat)

        pm_tasks_data, rep_tasks_data = prepare_dashboard_data(
            tasks_for_processing,
            validated_assignments_to_render,
            unassigned_reasons_dict,
            incomplete_ids
        )

        technician_template = jinja_env.get_template('technician_dashboard.html')
        technician_html = technician_template.render(
            pm_tasks=pm_tasks_data,
            rep_tasks=rep_tasks_data,
            technicians=present_technicians,
            total_work_minutes=total_work_minutes,
            assignments=validated_assignments_to_render,
            shift_start_time_str=shift_start_time_str,
            week_date_day_shift=week_date_day_shift,
            all_technicians_config=config_technicians,
            technician_groups_config=config_technician_groups
        )

        output_path = os.path.join(output_folder_path, "technician_dashboard.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(technician_html)
        _log(logger, "info", f"Written output to {output_path} via dashboard.py")

        return final_available_time

    except Exception as e:
        print(f"Error in generate_html_files (dashboard.py): {str(e)}")
        print(traceback.format_exc())
        raise
