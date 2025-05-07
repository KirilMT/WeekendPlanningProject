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

# Load technician mappings (unchanged)
try:
    print(f"Current working directory: {os.getcwd()}")
    with open('technician_mappings.json', 'r', encoding='utf-8') as f:
        mappings = json.load(f)

    if 'technicians' not in mappings:
        raise ValueError("Error: 'technicians' key missing in technician_mappings.json")

    technicians_data = mappings['technicians']
    TECHNICIAN_TASKS = {}
    TECHNICIAN_LINES = {}
    TECHNICIANS = list(technicians_data.keys())

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
        TECHNICIAN_TASKS[tech] = data['technician_tasks']
        TECHNICIAN_LINES[tech] = data['technician_lines']

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

# Task name mapping (unchanged)
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
        return 434
    elif day == "Saturday":
        return 651
    else:
        return 434

def normalize_string(s):
    s = str(s).lower().strip()
    s = re.sub(r'\s+', ' ', s)
    s = s.replace('Ã¼', 'u').replace('Ã¶', 'o').replace('Ã¤', 'a').replace('ÃŸ', 'ss')
    s = s.replace('ü', 'u').replace('ö', 'o').replace('ä', 'a').replace('ß', 'ss')
    s = s.replace('jährlich', 'yearly').replace('viertaljährlich', 'quarterly').replace('monatlich', 'monthly')
    s = s.replace('wöchentlich', 'weekly').replace('prüfung', 'check').replace('inspektion', 'inspection')
    s = s.replace('der druckanlage', '').replace('alle', 'all').replace('jahre', 'years')
    return s

def assign_tasks(tasks, present_technicians, total_work_minutes, rep_assignments=None):
    print("Task types before processing:", [task['task_type'] for task in tasks])
    filtered_tasks = []
    unassigned_tasks = []
    incomplete_tasks = []
    for task in tasks:
        task_type = task.get('task_type', '').upper()
        if task_type in ['PM', 'REP']:
            filtered_tasks.append(task)
        else:
            print(f"Skipping task {task.get('name', 'Unknown')}: task_type '{task_type}' is not 'PM' or 'REP'.")
    tasks = filtered_tasks
    print("Task types after filtering:", [task['task_type'] for task in tasks])
    priority_order = {'A': 1, 'B': 2, 'C': 3}
    tasks = sorted(tasks, key=lambda x: priority_order.get(x['priority'].upper(), 4))

    technician_schedules = {tech: [] for tech in present_technicians}
    assignments = []

    rep_assignments_dict = {item['task_id']: item for item in rep_assignments} if rep_assignments else {}

    for task in tasks:
        task_name = task.get('name', 'Unknown')
        task_type = task.get('task_type', '').upper()
        task_id = task['id']
        print(f"Processing task: {task_name} (Type: {task_type}, ID: {task_id})")
        try:
            base_duration = int(task['planned_worktime_min'])
            num_technicians_needed = int(task['mitarbeiter_pro_aufgabe'])
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

        task_lines = []
        try:
            if task.get('lines'):
                task_lines = [int(line.strip()) for line in str(task['lines']).split(',') if line.strip().isdigit()]
        except (ValueError, TypeError):
            print(f"Warning: Invalid lines format for task {task_name}: '{task['lines']}'. Assuming no line restriction.")

        # Determine eligible technicians
        eligible_technicians = []
        if task_type == 'REP' and task_id in rep_assignments_dict and not rep_assignments_dict[task_id].get('skipped'):
            eligible_technicians = rep_assignments_dict[task_id]['technicians']
            print(f"Using pre-assigned technicians for REP task {task_name}: {eligible_technicians}")
        else:
            for tech in present_technicians:
                tech_tasks = TECHNICIAN_TASKS.get(tech, [])
                tech_lines = TECHNICIAN_LINES.get(tech, [])

                can_do_task = False
                for tech_task in tech_tasks:
                    normalized_tech_task = normalize_string(tech_task)
                    if normalized_task_name in normalized_tech_task or normalized_tech_task in normalized_task_name:
                        can_do_task = True
                        break

                lines_match = True
                if task_lines:
                    lines_match = any(line in tech_lines for line in task_lines)

                if not can_do_task:
                    print(f"Technician {tech} cannot do task '{task_name}' (JSON: '{json_task_name}', normalized: '{normalized_task_name}').")
                elif not lines_match:
                    print(f"Technician {tech} cannot do task '{task_name}' due to line mismatch. Task lines: {task_lines}, Technician lines: {tech_lines}")
                else:
                    eligible_technicians.append(tech)

        if len(eligible_technicians) == 0:
            print(f"Task {task_name} (all {quantity} instances) has no eligible technicians. Marking as unassigned.")
            for i in range(quantity):
                unassigned_tasks.append(f"{task['id']}_{i+1}")
            continue

        # Generate possible technician groups
        viable_groups = []
        for r in range(num_technicians_needed, len(eligible_technicians) + 1):
            for group in combinations(eligible_technicians, r):
                viable_groups.append(list(group))

        def group_busy_score(group):
            total_busy_time = sum(
                sum(end - start for start, end, _ in technician_schedules[tech])
                for tech in group
            )
            return (len(group), total_busy_time)

        viable_groups.sort(key=group_busy_score)

        instances_to_schedule = [(f"{task['id']}_{i+1}", i + 1) for i in range(quantity)]
        instances_scheduled = 0

        for instance_id, instance_num in instances_to_schedule:
            instance_task_name = f"{task_name} (Instance {instance_num}/{quantity})"
            print(f"  Scheduling instance {instance_num}/{quantity} of task {task_name} (ID: {instance_id})")

            assigned = False
            for group in viable_groups:
                missing_technicians = max(0, num_technicians_needed - len(group))
                current_multiplier = 1 + missing_technicians
                task_duration = base_duration * current_multiplier

                start_time = 0
                while start_time <= total_work_minutes - task_duration:
                    all_available = True
                    for tech in group:
                        schedule = technician_schedules[tech]
                        for start, end, _ in schedule:
                            if not (end <= start_time or start >= start_time + task_duration):
                                all_available = False
                                break
                        if not all_available:
                            break
                    if all_available:
                        is_incomplete = False
                        original_task_duration = task_duration
                        if start_time + task_duration > total_work_minutes:
                            print(f"  Instance {instance_num}/{quantity} of task {task_name} duration {task_duration} exceeds total work minutes {total_work_minutes}. Capping at {total_work_minutes - start_time}.")
                            task_duration = total_work_minutes - start_time
                            is_incomplete = True
                            incomplete_tasks.append(instance_id)

                        for tech in group:
                            schedule = technician_schedules[tech]
                            schedule.append((start_time, start_time + task_duration, instance_task_name))
                            assignment = {
                                'technician': tech,
                                'task_name': instance_task_name,
                                'start': start_time,
                                'duration': task_duration,
                                'is_incomplete': is_incomplete,
                                'original_duration': original_task_duration,
                                'instance_id': instance_id
                            }
                            if task_type == 'REP':
                                assignment['ticket_mo'] = task.get('ticket_mo', '')
                                assignment['ticket_url'] = task.get('ticket_url', '')
                            assignments.append(assignment)

                        print(f"  Assigned instance {instance_num}/{quantity} of task {task_name} (ID: {instance_id}) to {group} at start time {start_time} with duration {task_duration} (multiplier: {current_multiplier}x, incomplete: {is_incomplete})")
                        instances_scheduled += 1
                        assigned = True
                        break
                    start_time += 15

                if assigned:
                    break

            if not assigned:
                print(f"  Instance {instance_num}/{quantity} of task {task_name} (ID: {instance_id}) could not be scheduled with any group. No available time slots.")
                unassigned_tasks.append(instance_id)

        if instances_scheduled < quantity:
            print(f"Task {task_name} (ID: {task['id']}) scheduled {instances_scheduled}/{quantity} instances. {quantity - instances_scheduled} instances unassigned.")
        else:
            print(f"Task {task_name} (ID: {task['id']}) scheduled all {quantity} instances.")

    return assignments, unassigned_tasks, incomplete_tasks

def generate_html_files(data, present_technicians, rep_assignments=None):
    tasks = []
    for idx, row in enumerate(data, start=1):
        quantity = str(row["quantity"]).strip()
        try:
            quantity = str(int(float(quantity.replace(',', '.')))) if quantity.replace(',', '.').replace('.', '', 1).isdigit() else "1"
        except (ValueError, TypeError):
            quantity = "1"
        task = {
            "id": str(idx),
            "name": row["scheduler_group_task"],
            "lines": row["lines"],
            "mitarbeiter_pro_aufgabe": row["mitarbeiter_pro_aufgabe"],
            "planned_worktime_min": row["planned_worktime_min"],
            "start": "2025-04-21",
            "end": "2025-04-22",
            "progress": 100 if quantity.lower() == "done" else 0,
            "priority": row["priority"],
            "quantity": quantity,
            "task_type": row["task_type"],
            "ticket_mo": row.get("ticket_mo", ""),
            "ticket_url": row.get("ticket_url", "")
        }
        tasks.append(task)
    current_day = get_current_day()
    total_work_minutes = calculate_work_time(current_day)
    num_intervals = ceil(total_work_minutes / 15)
    assignments, unassigned_tasks, incomplete_tasks = assign_tasks(tasks, present_technicians, total_work_minutes, rep_assignments)
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
            }), 400

        rep_tasks = [
            task | {'id': str(idx + 1)}
            for idx, task in enumerate(data)
            if task['task_type'].upper() == 'REP' and task.get('ticket_mo') and task.get('ticket_mo') != 'nan'
        ]

        if 'absentTechnicians' not in request.form:
            print("Initial file upload successful, prompting for absent technicians.")
            return jsonify({
                "message": "File uploaded successfully. Please select absent technicians.",
                "repTasks": rep_tasks
            })

        absent_technicians = json.loads(request.form['absentTechnicians'])
        present_technicians = [tech for tech in TECHNICIANS if tech not in absent_technicians]

        if 'repAssignments' in request.form:
            print("Received Rep assignments, generating dashboard.")
            rep_assignments_list = json.loads(request.form['repAssignments'])
            generate_html_files(data, present_technicians, rep_assignments_list)
            return jsonify({
                "message": "Technician dashboard generated successfully! Check the output folder for technician_dashboard.html."
            })

        return jsonify({"message": "Unexpected request state. Please try again."}), 400

    except Exception as e:
        print(f"Error processing file: {str(e)}")
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