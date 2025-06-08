# wkndPlanning/data_processing.py
import re
import pandas as pd
import logging

# Get a logger for this module
logger = logging.getLogger(__name__)

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

def calculate_work_time(day):
    return {"Monday": 434, "Friday": 434, "Sunday": 434, "Saturday": 651}.get(day, 434)

def is_valid_number(value):
    if value is None or value == '' or pd.isna(value):
        return False
    try:
        num = float(str(value).replace(',', '.').strip())
        return num >= 0 and num.is_integer()
    except (ValueError, TypeError):
        return False

def sanitize_data(data):
    sanitized_data = []
    required_fields = ['scheduler_group_task', 'task_type', 'priority']
    numeric_fields_to_int = ['planned_worktime_min', 'mitarbeiter_pro_aufgabe', 'quantity']

    for idx, row in enumerate(data):
        sanitized_row = row.copy() if isinstance(row, dict) else {}
        task_name_original = row.get('scheduler_group_task', 'Unknown')

        for field in required_fields:
            if field not in sanitized_row or sanitized_row[field] is None or pd.isna(sanitized_row[field]):
                sanitized_row[field] = 'Unknown' if field == 'scheduler_group_task' else ('C' if field == 'priority' else '')
                logger.warning(f"Warning: Missing or invalid {field} for task '{task_name_original}' at row {idx + 1}, set to default '{sanitized_row[field]}'")

        for field in numeric_fields_to_int:
            value = sanitized_row.get(field)
            if not is_valid_number(value):
                default_val = 1 if field in ['mitarbeiter_pro_aufgabe', 'quantity'] else 0
                logger.warning(f"Warning: Invalid {field}='{value}' for task '{task_name_original}' at row {idx + 1}, setting to {default_val}")
                sanitized_row[field] = default_val
            else:
                sanitized_row[field] = int(float(str(value).replace(',', '.')))

        sanitized_row['lines'] = str(sanitized_row.get('lines', ''))
        sanitized_row['ticket_mo'] = str(sanitized_row.get('ticket_mo', ''))
        sanitized_row['ticket_url'] = str(sanitized_row.get('ticket_url', ''))
        sanitized_data.append(sanitized_row)
    logger.info(f"Sanitized {len(sanitized_data)} rows from {len(data)} input rows via data_processing.")
    return sanitized_data

def validate_assignments_flat_input(assignments_list):
    valid_assignments = []
    if not isinstance(assignments_list, list):
        logger.warning(f"Warning: validate_assignments_flat_input expects a list, got {type(assignments_list)}")
        return []

    for idx, assignment in enumerate(assignments_list):
        if not isinstance(assignment, dict):
            logger.warning(f"Warning: Invalid assignment at index {idx}: not a dictionary")
            continue
        required_fields = ['technician', 'task_name', 'start', 'duration', 'instance_id']
        missing_field = False
        for field in required_fields:
            if field not in assignment or assignment[field] is None:
                logger.warning(f"Warning: Missing or None {field} in assignment at index {idx}: {assignment}")
                missing_field = True
                break
        if missing_field:
            continue

        try:
            start = float(assignment['start'])
            duration = float(assignment['duration'])
            if start < 0 or duration < 0:
                logger.warning(f"Warning: Invalid start={start} or duration={duration} in assignment at index {idx}: {assignment}")
                continue
            if not isinstance(assignment['instance_id'], str) or '_' not in assignment['instance_id']:
                logger.warning(f"Warning: Invalid instance_id='{assignment['instance_id']}' in assignment at index {idx}: {assignment}")
                continue
            task_id_part = assignment['instance_id'].split('_')[0]
            int(task_id_part)
            valid_assignments.append(assignment)
        except (ValueError, TypeError) as e:
            logger.warning(f"Warning: Invalid assignment at index {idx}: {str(e)} - {assignment}")
    logger.info(f"Validated {len(valid_assignments)} assignments from {len(assignments_list)} via data_processing.")
    return valid_assignments

def calculate_available_time(assignments, present_technicians, total_work_minutes):
    available_time = {tech: total_work_minutes for tech in present_technicians}
    for assignment in assignments:
        tech = assignment['technician']
        duration = assignment['duration']
        if tech in available_time:
            available_time[tech] -= duration
        else:
            logger.warning(f"Warning: Technician {tech} from assignment not in available_time for calculation (might be N/A or not present).")
    return available_time
