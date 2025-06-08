from flask import Flask, request, jsonify, send_from_directory, render_template
import os
import json
from jinja2 import Environment, FileSystemLoader
from extract_data import extract_data, get_current_day #, get_current_week, get_current_week_number, get_current_shift
import traceback
import random
import sqlite3 # Used for specific error handling in routes
import logging # Import logging

# Import from new modules
from db_utils import get_db_connection, init_db
from config_manager import load_app_config, TECHNICIAN_LINES, TECHNICIANS, TECHNICIAN_GROUPS #, TASK_NAME_MAPPING, TECHNICIAN_TASKS
from data_processing import sanitize_data, calculate_work_time #, calculate_available_time, validate_assignments_flat_input
from task_assigner import calculate_pm_assignments_and_availability # MODIFIED: Import new helper, removed assign_tasks
from dashboard import generate_html_files #, prepare_dashboard_data


app = Flask(__name__)
app.logger.setLevel(logging.DEBUG) # Explicitly set logger level to DEBUG

app.config['UPLOAD_FOLDER'] = 'Uploads'
app.config['OUTPUT_FOLDER'] = 'output'
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['DATABASE'] = os.path.join(BASE_DIR, 'weekend_planning.db')
UPLOAD_FOLDER_ABS = os.path.join(BASE_DIR, app.config['UPLOAD_FOLDER'])
OUTPUT_FOLDER_ABS = os.path.join(BASE_DIR, app.config['OUTPUT_FOLDER'])
os.makedirs(UPLOAD_FOLDER_ABS, exist_ok=True)
os.makedirs(OUTPUT_FOLDER_ABS, exist_ok=True)

env = Environment(loader=FileSystemLoader(os.path.join(BASE_DIR, 'templates')))
session_excel_data_cache = {}

with app.app_context():
    database_path = app.config['DATABASE']
    # Pass app.logger to init_db and load_app_config
    init_db(database_path, app.logger)
    load_app_config(database_path, app.logger)

@app.route('/manage_mappings_ui')
def manage_mappings_ui_route():
    return render_template('manage_mappings.html')

@app.route('/technicians', methods=['GET'])
def get_technicians_route():
    if TECHNICIAN_GROUPS:
        return jsonify(TECHNICIAN_GROUPS)
    else:
        return jsonify({"error": "Technician groups not available."}), 500

@app.route('/api/get_technician_mappings', methods=['GET'])
def get_technician_mappings_api():
    conn = get_db_connection(app.config['DATABASE'])
    cursor = conn.cursor()
    technicians_output = {}
    try:
        cursor.execute("SELECT id, name, sattelite_point, lines FROM technicians ORDER BY name")
        db_technicians = cursor.fetchall()
        for tech_row in db_technicians:
            tech_name = tech_row['name']
            tech_data = {
                "sattelite_point": tech_row['sattelite_point'],
                "technician_lines": [int(l.strip()) for l in tech_row['lines'].split(',') if l.strip().isdigit()] if tech_row['lines'] else [],
                "task_assignments": []
            }
            cursor.execute("SELECT task_name, priority FROM technician_task_assignments WHERE technician_id = ? ORDER BY priority ASC", (tech_row['id'],))
            for assign_row in cursor.fetchall():
                tech_data["task_assignments"].append({'task': assign_row['task_name'], 'prio': assign_row['priority']})
            technicians_output[tech_name] = tech_data
        return jsonify({"technicians": technicians_output})
    except sqlite3.Error as e:
        print(f"SQLite error in get_technician_mappings_api: {e}")
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/save_technician_mappings', methods=['POST'])
def save_technician_mappings_api():
    conn = None
    try:
        conn = get_db_connection(app.config['DATABASE'])
        cursor = conn.cursor()
        updated_data = request.get_json()
        if not updated_data or 'technicians' not in updated_data:
            return jsonify({"message": "Invalid data format"}), 400
        technicians_from_payload = updated_data.get('technicians', {})
        for tech_name, tech_payload_data in technicians_from_payload.items():
            sattelite_point = tech_payload_data.get('sattelite_point')
            lines_list = tech_payload_data.get('technician_lines', [])
            # Ensure all elements in lines_list are integers before joining
            lines_str = ",".join(map(str, [l for l in lines_list if isinstance(l, int)])) if lines_list else ""
            task_assignments_payload = sorted(filter(lambda ta: isinstance(ta, dict) and 'task' in ta and 'prio' in ta and isinstance(ta['prio'], int) and ta['prio'] >= 1, tech_payload_data.get('task_assignments', [])), key=lambda x: x.get('prio'))
            cursor.execute("SELECT id FROM technicians WHERE name = ?", (tech_name,))
            tech_row = cursor.fetchone()
            technician_id = None
            if tech_row:
                technician_id = tech_row['id']
                cursor.execute("UPDATE technicians SET sattelite_point = ?, lines = ? WHERE id = ?", (sattelite_point, lines_str, technician_id))
                cursor.execute("DELETE FROM technician_task_assignments WHERE technician_id = ?", (technician_id,))
            else:
                cursor.execute("INSERT INTO technicians (name, sattelite_point, lines) VALUES (?, ?, ?)", (tech_name, sattelite_point, lines_str))
                technician_id = cursor.lastrowid
            for assignment in task_assignments_payload:
                task_name_assign = assignment.get('task')
                priority_assign = assignment.get('prio')
                if task_name_assign and isinstance(priority_assign, int) and priority_assign >= 1:
                    cursor.execute("INSERT INTO technician_task_assignments (technician_id, task_name, priority) VALUES (?, ?, ?)", (technician_id, task_name_assign, priority_assign))
        conn.commit()
        load_app_config(app.config['DATABASE'])
        return jsonify({"message": "Technician mappings saved to database and reloaded successfully!"})
    except sqlite3.Error as e:
        if conn: conn.rollback()
        print(f"SQLite error saving technician mappings: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error saving technician mappings: {str(e)}")
        return jsonify({"message": f"Error saving mappings: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/')
def index_route():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file_route():
    session_id = request.form.get('session_id')
    # excel_data_rows = None # Old variable

    if not session_id:
        return jsonify({"message": "Session ID is missing."}), 400

    # Stage 1: Initial file upload
    if 'excelFile' in request.files and request.files['excelFile'].filename != '':
        excel_file_stream = request.files['excelFile']
        try:
            # Unpack data and errors from extract_data
            excel_data_list, extraction_errors = extract_data(excel_file_stream)

            # Store only the list of data rows in the session cache
            session_excel_data_cache[session_id] = excel_data_list

            # Pass only the list of data rows to sanitize_data
            sanitized_data = sanitize_data(excel_data_list)
            pm_tasks_for_ui = []
            for idx, task_data in enumerate(sanitized_data):
                if task_data.get('task_type', '').upper() == 'PM':
                    pm_tasks_for_ui.append({
                        "id": str(idx + 1),
                        "name": task_data.get("scheduler_group_task", "Unknown PM Task"),
                        "lines": task_data.get("lines", ""),
                        "mitarbeiter_pro_aufgabe": int(task_data.get("mitarbeiter_pro_aufgabe", 1)),
                        "planned_worktime_min": int(task_data.get("planned_worktime_min", 0)),
                        "priority": task_data.get("priority", "C"),
                        "quantity": int(task_data.get("quantity", 1)),
                        "task_type": "PM",
                        "ticket_mo": task_data.get("ticket_mo", ""),
                        "ticket_url": task_data.get("ticket_url", "")
                    })

            response_message = "File processed."
            if extraction_errors:
                response_message += f" {len(extraction_errors)} issues found during data extraction (see details below)."
            elif not excel_data_list:
                response_message += " No data could be extracted. Please check the file format and content."
            else:
                response_message += " PM tasks extracted successfully."

            return jsonify({
                "message": response_message,
                "pm_tasks": pm_tasks_for_ui, # Only PM tasks initially
                "technicians": TECHNICIANS,
                "technician_groups": TECHNICIAN_GROUPS,
                "session_id": session_id,
                "extraction_errors": extraction_errors # Include extraction errors in the response
            })
        except Exception as e:
            app.logger.error(f"Error during initial file upload: {e}", exc_info=True) # Log full traceback
            return jsonify({"message": f"Error processing file: {str(e)}"}), 500

    # Stage 2: Absent technicians submitted, calculate REP task eligibility
    elif 'absentTechnicians' in request.form:
        if session_id not in session_excel_data_cache:
            return jsonify({"message": "Session expired or data not found. Please re-upload."}), 400

        excel_data_list_cached = session_excel_data_cache[session_id] # This will be the list of dicts
        app.logger.info(f"Stage 2 processing for session_id: {session_id} with {len(excel_data_list_cached) if excel_data_list_cached else 'no' } cached rows.")

        try:
            absent_technicians = json.loads(request.form.get('absentTechnicians', '[]'))
            all_technicians_flat = [tech for group in TECHNICIAN_GROUPS.values() for tech in group]
            present_technicians = [tech for tech in all_technicians_flat if tech not in absent_technicians]

            current_day = get_current_day()
            total_work_minutes = calculate_work_time(current_day)

            # Pass the correctly retrieved list to sanitize_data
            sanitized_data = sanitize_data(excel_data_list_cached)
            all_tasks_for_processing = []
            for idx, row in enumerate(sanitized_data, start=1):
                all_tasks_for_processing.append({
                    "id": str(idx), "name": row.get("scheduler_group_task", "Unknown"),
                    "lines": row.get("lines", ""), "mitarbeiter_pro_aufgabe": int(row.get("mitarbeiter_pro_aufgabe", 1)),
                    "planned_worktime_min": int(row.get("planned_worktime_min", 0)), "priority": row.get("priority", "C"),
                    "quantity": int(row.get("quantity", 1)), "task_type": row.get("task_type", ""),
                    "ticket_mo": row.get("ticket_mo", ""), "ticket_url": row.get("ticket_url", "")
                })

            pm_tasks_from_excel = [t for t in all_tasks_for_processing if t['task_type'].upper() == 'PM']
            _ , available_time_after_pm = calculate_pm_assignments_and_availability(
                pm_tasks_from_excel, present_technicians, total_work_minutes, logger=app.logger
            )

            rep_tasks_for_ui = []
            eligible_technicians_for_rep_modal = {}

            raw_rep_tasks = [t for t in all_tasks_for_processing if t['task_type'].upper() == 'REP']

            for task_rep in raw_rep_tasks:
                task_id_rep = task_rep['id']
                rep_tasks_for_ui.append(task_rep) # Add full task details for UI
                eligible_technicians_for_rep_modal[task_id_rep] = []
                task_duration_rep = int(task_rep.get('planned_worktime_min', 0))
                min_acceptable_time = task_duration_rep * 0.75
                task_lines_rep_str = str(task_rep.get('lines', ''))
                task_lines_rep_list = []
                if task_lines_rep_str and task_lines_rep_str.lower() != 'nan' and task_lines_rep_str.strip() != '':
                    try:
                        task_lines_rep_list = [int(line.strip()) for line in task_lines_rep_str.split(',') if line.strip().isdigit()]
                    except ValueError:
                        pass # Ignore malformed lines for this task

                for tech_name in present_technicians:
                    tech_available_time = available_time_after_pm.get(tech_name, 0)
                    tech_config_lines = TECHNICIAN_LINES.get(tech_name, [])

                    # Check line eligibility
                    line_eligible = True # Assume eligible if task has no lines specified
                    if task_lines_rep_list: # Only check if task specifies lines
                        line_eligible = any(line in tech_config_lines for line in task_lines_rep_list)

                    if line_eligible:
                        if task_duration_rep == 0 or tech_available_time >= min_acceptable_time:
                            eligible_technicians_for_rep_modal[task_id_rep].append({
                                'name': tech_name,
                                'available_time': tech_available_time,
                                'task_full_duration': task_duration_rep # For UI display of partial assignment potential
                            })

            return jsonify({
                "message": "PM tasks processed, REP task data prepared.",
                "repTasks": rep_tasks_for_ui, # Send REP tasks for the modal
                "eligibleTechnicians": eligible_technicians_for_rep_modal, # Send eligibility info
                "session_id": session_id # Keep session active
            })

        except Exception as e:
            print(f"Error during PM processing/REP prep: {e}")
            print(traceback.format_exc())
            return jsonify({"message": f"Error processing absent technicians: {str(e)}"}), 500

    # Fallback if neither excelFile nor absentTechnicians is in the request form
    # This case should ideally not be reached if frontend logic is correct.
    app.logger.warning(f"Invalid request for session_id: {session_id}. No excelFile or absentTechnicians provided.")
    return jsonify({"message": "Invalid request. No file or absent technician data provided."}), 400

@app.route('/generate_dashboard', methods=['POST'])
def generate_dashboard_route():
    try:
        form_data = request.form
        session_id = form_data.get('session_id')
        present_technicians_json = form_data.get('present_technicians', '[]')
        rep_assignments_json = form_data.get('rep_assignments', '[]')

        if not session_id or session_id not in session_excel_data_cache:
            return jsonify({"message": "Invalid session or data. Re-upload Excel."}), 400
        excel_data_to_process = session_excel_data_cache[session_id]
        try:
            present_technicians = json.loads(present_technicians_json)
            rep_assignments_from_ui = json.loads(rep_assignments_json)
        except json.JSONDecodeError as je:
            print(f"JSON Decode Error for present_technicians or rep_assignments: {je}")
            return jsonify({"message": "Invalid format for technician list or REP assignments."}), 400

        if not isinstance(present_technicians, list) or not all(isinstance(tech, str) for tech in present_technicians) or \
           not isinstance(rep_assignments_from_ui, list):
            return jsonify({"message": "Invalid format for present_technicians or rep_assignments."}),400

        available_time_result = generate_html_files(
            excel_data_to_process,
            present_technicians,
            rep_assignments_from_ui,
            env, # Pass the Jinja environment
            OUTPUT_FOLDER_ABS, # Pass the absolute output folder path
            TECHNICIANS, # Pass all configured technicians
            TECHNICIAN_GROUPS, # Pass configured technician groups
            app.logger # Pass the Flask app logger
        )

        dashboard_url = request.host_url + f'output/technician_dashboard.html?cache_bust={random.randint(1,100000)}'
        return jsonify({
            "message": "Dashboard data processed and HTML files generated.",
            "html_files": available_time_result.get('html_files', []),
            "session_id": session_id,
            "dashboard_url": dashboard_url # Return the dashboard URL
        })
    except Exception as e:
        print(f"Error in generate_dashboard_route: {e}")
        print(traceback.format_exc()) # It's good practice to log the full traceback for debugging
        return jsonify({"message": f"Error processing dashboard data: {str(e)}"}), 500

@app.route('/output/<path:filename>') # Added path converter for filename
def output_file_route(filename):
    return send_from_directory(OUTPUT_FOLDER_ABS, filename)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)
