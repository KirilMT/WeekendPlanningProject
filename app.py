from flask import Flask, request, jsonify, send_from_directory
import os
import json
from jinja2 import Environment, FileSystemLoader
from extract_data import extract_data, get_current_day
from math import ceil
import re
from itertools import combinations

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'Uploads'
app.config['OUTPUT_FOLDER'] = 'output'

env = Environment(loader=FileSystemLoader('templates'))

# Load technician mappings from JSON file with UTF-8 encoding
try:
    print(f"Current working directory: {os.getcwd()}")
    with open('technician_mappings.json', 'r', encoding='utf-8') as f:
        mappings = json.load(f)

    # Validate JSON structure
    if 'technicians' not in mappings:
        raise ValueError("Error: 'technicians' key missing in technician_mappings.json")

    technicians_data = mappings['technicians']
    TECHNICIAN_TASKS = {}
    TECHNICIAN_LINES = {}
    TECHNICIANS = list(technicians_data.keys())

    # Validate each technician's data
    valid_groups = {"Fuchsbau", "Closures", "Aquarium"}
    for tech, data in technicians_data.items():
        if not isinstance(data, dict):
            raise ValueError(f"Error: Invalid data for technician '{tech}' in technician_mappings.json")
        if 'sattelite_point' not in data:
            raise ValueError(f"Error: Missing 'sattelite_point' for technician '{tech}' in technician_mappings.json")
        if data['sattelite_point'] not in valid_groups:
            raise ValueError(
                f"Error: Invalid 'sattelite_point' '{data['sattelite_point']}' for technician '{tech}'. Must be one of {valid_groups}")
        if 'technician_lines' not in data:
            raise ValueError(f"Error: Missing 'technician_lines' for technician '{tech}' in technician_mappings.json")
        if 'technician_tasks' not in data:
            raise ValueError(f"Error: Missing 'technician_tasks' for technician '{tech}' in technician_mappings.json")
        # Populate TECHNICIAN_TASKS and TECHNICIAN_LINES
        TECHNICIAN_TASKS[tech] = data['technician_tasks']
        TECHNICIAN_LINES[tech] = data['technician_lines']

    # Define technician groupings based on JSON sattelite_point
    TECHNICIAN_GROUPS = {
        "Fuchsbau": [],
        "Closures": [],
        "Aquarium": []
    }
    for tech, data in technicians_data.items():
        group = data['sattelite_point']
        TECHNICIAN_GROUPS[group].append(tech)

except FileNotFoundError:
    print("Error: 'technician_mappings.json' not found in the project directory.")
    raise ValueError("Error: 'technician_mappings.json' not found. Please ensure the file exists.")
except Exception as e:
    print(f"Error loading 'technician_mappings.json': {str(e)}")
    raise ValueError(f"Error loading 'technician_mappings.json': {str(e)}")

# Task name mapping: Excel task names (English/simplified) to JSON task names (German)
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
    if day in ["Monday", "Friday", "Sunday"]:
        return 434  # 8h shift
    elif day == "Saturday":
        return 651  # 12h shift (10.85h after breaks)
    else:
        return 434  # Default to 8h shift for other days

def normalize_string(s):
    """Normalize a string for comparison: lowercase, remove extra spaces, handle German terms and encoding artifacts."""
    s = str(s).lower().strip()
    s = re.sub(r'\s+', ' ', s)  # Replace multiple spaces with single space
    # Handle encoding artifacts
    s = s.replace('Ã¼', 'u').replace('Ã¶', 'o').replace('Ã¤', 'a').replace('ÃŸ', 'ss')
    # Replace German special characters
    s = s.replace('ü', 'u').replace('ö', 'o').replace('ä', 'a').replace('ß', 'ss')
    # Replace common German terms with English equivalents
    s = s.replace('jährlich', 'yearly').replace('viertaljährlich', 'quarterly').replace('monatlich', 'monthly')
    s = s.replace('wöchentlich', 'weekly').replace('prüfung', 'check').replace('inspektion', 'inspection')
    s = s.replace('der druckanlage', '').replace('alle', 'all').replace('jahre', 'years')
    return s


def assign_tasks(tasks, present_technicians, total_work_minutes):
    print("Task types before filtering:", [task['task_type'] for task in tasks])
    filtered_tasks = []
    unassigned_tasks = []  # Track tasks with zero eligible technicians or unschedulable
    incomplete_tasks = []  # Track tasks with duration exceeding total_work_minutes
    for task in tasks:
        task_type = task.get('task_type', '').upper()
        if task_type.startswith('PM'):
            filtered_tasks.append(task)
        else:
            print(f"Skipping task {task.get('name', 'Unknown')}: task_type '{task_type}' is not 'PM'.")
    tasks = filtered_tasks
    print("Task types after filtering:", [task['task_type'] for task in tasks])
    priority_order = {'A': 1, 'B': 2, 'C': 3}
    tasks = sorted(tasks, key=lambda x: priority_order.get(x['priority'].upper(), 4))

    technician_schedules = {tech: [] for tech in present_technicians}
    assignments = []

    for task in tasks:
        task_name = task.get('name', 'Unknown')
        print(f"Processing task: {task_name}")
        try:
            base_duration = int(task['planned_worktime_min'])
            num_technicians_needed = int(task['mitarbeiter_pro_aufgabe'])
            # Convert quantity to integer, default to 1 if invalid
            quantity = int(float(str(task['quantity']).replace(',', '.'))) if str(task['quantity']).replace(',', '.').replace('.', '', 1).isdigit() else 1
        except (ValueError, TypeError) as e:
            print(f"Skipping task {task_name}: invalid duration, number of technicians, or quantity ({str(e)})")
            continue
        if base_duration <= 0 or num_technicians_needed <= 0 or quantity <= 0:
            print(f"Skipping task {task_name}: invalid duration, number of technicians needed, or quantity.")
            continue

        json_task_name = TASK_NAME_MAPPING.get(task_name, task_name)
        normalized_task_name = normalize_string(json_task_name)
        print(f"Task: '{task_name}' -> JSON: '{json_task_name}' -> Normalized: '{normalized_task_name}'")

        # Parse task lines (e.g., "1,2" -> [1, 2])
        task_lines = []
        try:
            if task.get('lines'):
                task_lines = [int(line.strip()) for line in str(task['lines']).split(',') if line.strip().isdigit()]
        except (ValueError, TypeError):
            print(f"Warning: Invalid lines format for task {task_name}: '{task['lines']}'. Assuming no line restriction.")

        # Determine eligible technicians
        eligible_technicians = []
        for tech in present_technicians:
            tech_tasks = TECHNICIAN_TASKS.get(tech, [])
            tech_lines = TECHNICIAN_LINES.get(tech, [])
            tech_sattelite_point = technicians_data.get(tech, {}).get('sattelite_point', 'Aquarium')

            can_do_task = False
            for tech_task in tech_tasks:
                normalized_tech_task = normalize_string(tech_task)
                print(f"  Comparing with tech task: '{tech_task}' -> Normalized: '{normalized_tech_task}'")
                if normalized_task_name in normalized_tech_task or normalized_tech_task in normalized_task_name:
                    can_do_task = True
                    break

            lines_match = True
            if task_lines:
                lines_match = any(line in tech_lines for line in task_lines)

            if not can_do_task:
                print(f"Technician {tech} cannot do task '{task_name}' (JSON: '{json_task_name}', normalized: '{normalized_task_name}'). Available tasks: {tech_tasks}")
            elif not lines_match:
                print(f"Technician {tech} cannot do task '{task_name}' due to line mismatch. Task lines: {task_lines}, Technician lines: {tech_lines}")
            else:
                eligible_technicians.append(tech)

        if len(eligible_technicians) == 0:
            print(f"Task {task_name} (all {quantity} instances) has no eligible technicians. Marking as unassigned.")
            for i in range(quantity):
                unassigned_tasks.append(f"{task['id']}_{i+1}")
            continue

        # Calculate total required duration for all instances
        # Assume optimal case: num_technicians_needed met (multiplier = 1)
        total_required_duration = base_duration * quantity
        duration_multiplier = 1  # Start with optimal multiplier

        # Generate possible technician groups
        viable_groups = []
        for r in range(num_technicians_needed, len(eligible_technicians) + 1):
            for group in combinations(eligible_technicians, r):
                viable_groups.append(list(group))

        # Sort groups by size (prefer smaller groups with num_technicians_needed)
        viable_groups.sort(key=len)

        selected_group = None
        group_start_time = None
        instances_scheduled = 0
        current_multiplier = 1

        # Try each group to schedule all instances
        for group in viable_groups:
            # Check if group can handle all instances
            missing_technicians = max(0, num_technicians_needed - len(group))
            current_multiplier = 1 + missing_technicians
            total_duration_with_multiplier = base_duration * quantity * current_multiplier

            if total_duration_with_multiplier > total_work_minutes:
                print(f"Group {group} cannot handle {quantity} instances of task {task_name}: total duration {total_duration_with_multiplier} exceeds {total_work_minutes}.")
                continue

            # Find earliest start time where all technicians in group are available
            for start_time in range(0, total_work_minutes + 1, 15):
                all_available = True
                for tech in group:
                    schedule = technician_schedules[tech]
                    for start, end, _ in schedule:
                        if not (end <= start_time or start >= start_time + base_duration * current_multiplier):
                            all_available = False
                            break
                    if not all_available:
                        break
                if all_available and start_time + total_duration_with_multiplier <= total_work_minutes:
                    selected_group = group
                    group_start_time = start_time
                    break

            if selected_group:
                break

        if not selected_group:
            print(f"No group can schedule all {quantity} instances of task {task_name}. Trying to schedule as many as possible.")
            # Try to schedule as many instances as possible with the best group
            for group in viable_groups:
                missing_technicians = max(0, num_technicians_needed - len(group))
                current_multiplier = 1 + missing_technicians
                instances_scheduled = 0
                temp_start_time = None

                for start_time in range(0, total_work_minutes + 1, 15):
                    all_available = True
                    for tech in group:
                        schedule = technician_schedules[tech]
                        for start, end, _ in schedule:
                            if not (end <= start_time or start >= start_time + base_duration * current_multiplier):
                                all_available = False
                                break
                        if not all_available:
                            break
                    if all_available and start_time + base_duration * current_multiplier <= total_work_minutes:
                        temp_start_time = start_time
                        instances_scheduled += 1
                        # Temporarily update schedules to check next instance
                        for tech in group:
                            schedule = technician_schedules[tech]
                            schedule.append((start_time, start_time + base_duration * current_multiplier, f"temp_{task_name}"))
                        if instances_scheduled >= quantity:
                            break
                    else:
                        break

                # Reset schedules
                for tech in group:
                    technician_schedules[tech] = [(s, e, t) for s, e, t in technician_schedules[tech] if not t.startswith("temp_")]

                if instances_scheduled > 0:
                    selected_group = group
                    group_start_time = temp_start_time
                    break

        if selected_group:
            # Schedule all possible instances with the selected group
            missing_technicians = max(0, num_technicians_needed - len(selected_group))
            current_multiplier = 1 + missing_technicians
            current_start_time = group_start_time
            instances_scheduled = 0

            for instance in range(quantity):
                instance_id = f"{task['id']}_{instance+1}"
                instance_task_name = f"{task_name} (Instance {instance+1}/{quantity})"
                print(f"  Scheduling instance {instance+1}/{quantity} of task {task_name} (ID: {instance_id})")

                # Check if we can schedule this instance
                all_available = True
                for tech in selected_group:
                    schedule = technician_schedules[tech]
                    for start, end, _ in schedule:
                        if not (end <= current_start_time or start >= current_start_time + base_duration * current_multiplier):
                            all_available = False
                            break
                    if not all_available:
                        break

                if not all_available or current_start_time + base_duration * current_multiplier > total_work_minutes:
                    print(f"  Instance {instance+1}/{quantity} of task {task_name} (ID: {instance_id}) could not be scheduled with group {selected_group}.")
                    unassigned_tasks.append(instance_id)
                    continue

                task_duration = base_duration * current_multiplier
                original_task_duration = task_duration
                is_incomplete = False
                if current_start_time + task_duration > total_work_minutes:
                    print(f"  Instance {instance+1}/{quantity} of task {task_name} duration {task_duration} exceeds total work minutes {total_work_minutes}. Capping at {total_work_minutes - current_start_time}.")
                    task_duration = total_work_minutes - current_start_time
                    is_incomplete = True
                    incomplete_tasks.append(instance_id)

                # Assign the instance to all technicians in the group
                for tech in selected_group:
                    schedule = technician_schedules[tech]
                    schedule.append((current_start_time, current_start_time + task_duration, instance_task_name))
                    assignments.append({
                        'technician': tech,
                        'task_name': instance_task_name,
                        'start': current_start_time,
                        'duration': task_duration,
                        'is_incomplete': is_incomplete,
                        'original_duration': original_task_duration,
                        'instance_id': instance_id
                    })

                print(f"  Assigned instance {instance+1}/{quantity} of task {task_name} (ID: {instance_id}) to {selected_group} at start time {current_start_time} with duration {task_duration} (multiplier: {current_multiplier}x, incomplete: {is_incomplete})")
                instances_scheduled += 1
                current_start_time += task_duration  # Schedule next instance consecutively

            if instances_scheduled < quantity:
                print(f"Task {task_name} (ID: {task['id']}) scheduled {instances_scheduled}/{quantity} instances with group {selected_group}. {quantity - instances_scheduled} instances unassigned.")
        else:
            print(f"No group can schedule any instances of task {task_name}. All {quantity} instances unassigned.")
            for i in range(quantity):
                unassigned_tasks.append(f"{task['id']}_{i+1}")

    return assignments, unassigned_tasks, incomplete_tasks

def generate_html_files(data, present_technicians):
    tasks = []
    for idx, row in enumerate(data, start=1):
        # Ensure quantity is a string representation of the number
        quantity = str(row["quantity"]).strip()
        try:
            # Validate quantity as a number, default to 1 if invalid
            quantity = str(int(float(quantity.replace(',', '.')))) if quantity.replace(',', '.').replace('.', '', 1).isdigit() else "1"
        except (ValueError, TypeError):
            quantity = "1"
        task = {
            "id": idx,
            "name": row["scheduler_group_task"],
            "lines": row["lines"],
            "mitarbeiter_pro_aufgabe": row["mitarbeiter_pro_aufgabe"],
            "planned_worktime_min": row["planned_worktime_min"],
            "start": "2025-04-21",
            "end": "2025-04-22",
            "progress": 100 if quantity.lower() == "done" else 0,
            "priority": row["priority"],
            "quantity": quantity,  # Ensure quantity is a string
            "task_type": row["task_type"]
        }
        tasks.append(task)
    current_day = get_current_day()
    total_work_minutes = calculate_work_time(current_day)
    num_intervals = ceil(total_work_minutes / 15)
    assignments, unassigned_tasks, incomplete_tasks = assign_tasks(tasks, present_technicians, total_work_minutes)
    technician_template = env.get_template('technician_dashboard.html')
    technician_html = technician_template.render(
        tasks=tasks,
        technicians=present_technicians,
        total_work_minutes=total_work_minutes,
        num_intervals=num_intervals,
        assignments=assignments,
        unassigned_tasks=unassigned_tasks,
        incomplete_tasks=incomplete_tasks
    )
    with open(os.path.join(app.config['OUTPUT_FOLDER'], "technician_dashboard.html"), "w", encoding="utf-8") as f:
        f.write(technician_html)

@app.route('/')
def index():
    with open('templates/index.html', 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'excelFile' not in request.files:
        return jsonify({"message": "No file uploaded"}), 400
    file = request.files['excelFile']
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)
    try:
        data = extract_data(file_path)
        if not data:
            return jsonify({
                "message": "No data found after filtering. Check if the Summary KW17 sheet contains tasks with values >= 1 in the 'Monday CW-17' column for shift 'early', starting from row 9."
            }), 200
        absent_technicians = []
        if 'absentTechnicians' in request.form:
            absent_technicians = json.loads(request.form['absentTechnicians'])
        present_technicians = [tech for tech in TECHNICIANS if tech not in absent_technicians]
        if 'absentTechnicians' in request.form:
            generate_html_files(data, present_technicians)
            return jsonify({
                "message": "Technician dashboard generated successfully! Check the output folder for technician_dashboard.html."
            })
        else:
            return jsonify({"message": "File uploaded successfully. Please select absent technicians."})
    except Exception as e:
        return jsonify({"message": f"Error processing file: {str(e)}"}), 500

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