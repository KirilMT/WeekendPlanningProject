from flask import Flask, request, jsonify, send_from_directory
import os
import json
from jinja2 import Environment, FileSystemLoader
from extract_data import extract_data, get_current_day
from math import ceil
import re

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'Uploads'
app.config['OUTPUT_FOLDER'] = 'output'

env = Environment(loader=FileSystemLoader('templates'))

# Load technician mappings from JSON file with UTF-8 encoding
try:
    print(f"Current working directory: {os.getcwd()}")
    with open('technician_mappings.json', 'r', encoding='utf-8') as f:
        mappings = json.load(f)
    TECHNICIAN_TASKS = mappings['technician_tasks']
    TECHNICIAN_LINES = mappings['technician_lines']  # Loaded but unused
    TECHNICIANS = list(TECHNICIAN_TASKS.keys())
except FileNotFoundError:
    print("Error: 'technician_mappings.json' not found in the project directory.")
    print("Creating a default empty mapping to continue...")
    TECHNICIAN_TASKS = {}
    TECHNICIAN_LINES = {}
    TECHNICIANS = []
except Exception as e:
    print(f"Error loading 'technician_mappings.json': {str(e)}")
    TECHNICIAN_TASKS = {}
    TECHNICIAN_LINES = {}
    TECHNICIANS = []

# Define technician groupings
TECHNICIAN_GROUPS = {
    "Fuchsbau": [
        "Yeison Berbeci",
        "Dianka Blick",
        "Keegan Goeda",
        "Gaurav Rawal",
        "Mohamed Ali Loummir",
        "Khanh Nguyen",
        "Sophia Annabell Wagner",
        "Robert Rakowski",
        "Moritz Kipper",
        "József Szőke (PLC)"
    ],
    "Closures": [
        "Lukasz Brach",
        "Rafal Crispim",
        "Phannic Phiri (PLC)"
    ],
    "Aquarium": [
        "Bilgehan Berk Unsal",
        "Ben Kacem Hicham",
        "Marvin Bienek",
        "Codrean Dumitru",
        "Tom Grage",
        "Thiago Nery (PLC)",
        "Kiril Martinez Tamayo (PLC)"
    ]
}

# Add remaining technicians to the "Aquarium" group
aquarium_technicians = TECHNICIAN_GROUPS["Aquarium"]
for tech in TECHNICIANS:
    if not any(tech in group for group in [TECHNICIAN_GROUPS["Fuchsbau"], TECHNICIAN_GROUPS["Closures"]]):
        if tech not in aquarium_technicians:
            aquarium_technicians.append(tech)

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
            task_duration = int(task['planned_worktime_min'])
            num_technicians_needed = int(task['mitarbeiter_pro_aufgabe'])
        except (ValueError, TypeError) as e:
            print(f"Skipping task {task_name}: invalid duration or number of technicians ({str(e)})")
            continue
        if task_duration <= 0 or num_technicians_needed <= 0:
            print(f"Skipping task {task_name}: invalid duration or number of technicians needed.")
            continue
        json_task_name = TASK_NAME_MAPPING.get(task_name, task_name)
        normalized_task_name = normalize_string(json_task_name)
        print(f"Task: '{task_name}' -> JSON: '{json_task_name}' -> Normalized: '{normalized_task_name}'")
        eligible_technicians = []
        for tech in present_technicians:
            tech_tasks = TECHNICIAN_TASKS.get(tech, [])
            can_do_task = False
            for tech_task in tech_tasks:
                normalized_tech_task = normalize_string(tech_task)
                print(f"  Comparing with tech task: '{tech_task}' -> Normalized: '{normalized_tech_task}'")
                if normalized_task_name in normalized_tech_task or normalized_tech_task in normalized_task_name:
                    can_do_task = True
                    break
            if not can_do_task:
                print(f"Technician {tech} cannot do task '{task_name}' (JSON: '{json_task_name}', normalized: '{normalized_task_name}'). Available tasks: {tech_tasks}")
            if can_do_task:
                eligible_technicians.append(tech)
        if len(eligible_technicians) < num_technicians_needed:
            print(f"Task {task_name} requires {num_technicians_needed} technicians, but only {len(eligible_technicians)} are eligible.")
            continue
        assigned_technicians = []
        for tech in eligible_technicians:
            if len(assigned_technicians) >= num_technicians_needed:
                break
            schedule = technician_schedules[tech]
            start_time = 0
            for start, end, _ in schedule:
                if start_time < end:
                    start_time = end
            if start_time + task_duration > total_work_minutes:
                continue
            assigned_technicians.append(tech)
            schedule.append((start_time, start_time + task_duration, task_name))
            assignments.append({
                'technician': tech,
                'task_name': task_name,
                'start': start_time,
                'duration': task_duration
            })
        if len(assigned_technicians) < num_technicians_needed:
            print(f"Could not assign enough technicians to task {task_name}. Needed {num_technicians_needed}, assigned {len(assigned_technicians)}.")
            for tech in assigned_technicians:
                schedule = technician_schedules[tech]
                schedule.pop()
                assignments[:] = [a for a in assignments if a['technician'] != tech or a['task_name'] != task_name]
    return assignments

def generate_html_files(data, present_technicians):
    tasks = []
    for row in data:
        task = {
            "id": row["scheduler_group_task"],
            "name": row["scheduler_group_task"],
            "lines": row["lines"],
            "mitarbeiter_pro_aufgabe": row["mitarbeiter_pro_aufgabe"],
            "planned_worktime_min": row["planned_worktime_min"],
            "start": "2025-04-21",
            "end": "2025-04-22",
            "progress": 100 if row["status"] == "done" else 0,
            "priority": row["priority"],
            "status": row["status"],
            "task_type": row["task_type"]
        }
        tasks.append(task)
    current_day = get_current_day()
    total_work_minutes = calculate_work_time(current_day)
    num_intervals = ceil(total_work_minutes / 15)
    assignments = assign_tasks(tasks, present_technicians, total_work_minutes)
    technician_template = env.get_template('technician_dashboard.html')
    technician_html = technician_template.render(
        tasks=tasks,
        technicians=present_technicians,
        total_work_minutes=total_work_minutes,
        num_intervals=num_intervals,
        assignments=assignments
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