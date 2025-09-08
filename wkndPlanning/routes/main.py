from flask import Blueprint, render_template, send_from_directory, current_app, request, jsonify, url_for, g
from flask_wtf.csrf import CSRFProtect
from io import BytesIO
import json
import pandas as pd
import random
import time

from ..services.extract_data import extract_data, get_current_day, get_current_week_number
from ..services.data_processing import sanitize_data, calculate_work_time
from ..services.dashboard import generate_html_files
from ..services.config_manager import TECHNICIANS, TECHNICIAN_GROUPS, TECHNICIAN_LINES
from ..services.db_utils import get_db_connection, TaskManager, get_all_technician_skills_by_name
from ..services.security import InputValidator

main_bp = Blueprint('main', __name__)

# Enhanced session management with timestamps
session_excel_data_cache = {}
SESSION_TIMEOUT_SECONDS = 5 * 60  # 5 minutes to match frontend

def cleanup_expired_sessions():
    """Remove expired sessions from cache."""
    current_time = time.time()
    expired_sessions = []

    for session_id, session_data in session_excel_data_cache.items():
        if isinstance(session_data, dict) and 'timestamp' in session_data:
            if current_time - session_data['timestamp'] > SESSION_TIMEOUT_SECONDS:
                expired_sessions.append(session_id)

    for session_id in expired_sessions:
        del session_excel_data_cache[session_id]
        current_app.logger.info(f"Expired session removed: {session_id}")

def is_session_valid(session_id):
    """Check if session exists and is not expired."""
    cleanup_expired_sessions()  # Clean up first

    if session_id not in session_excel_data_cache:
        return False

    session_data = session_excel_data_cache[session_id]
    if not isinstance(session_data, dict) or 'timestamp' not in session_data:
        return False

    current_time = time.time()
    return current_time - session_data['timestamp'] <= SESSION_TIMEOUT_SECONDS

def get_session_data(session_id):
    """Get session data if session is valid."""
    if not is_session_valid(session_id):
        return None
    return session_excel_data_cache[session_id]['data']

def store_session_data(session_id, data):
    """Store data with timestamp for session management."""
    session_excel_data_cache[session_id] = {
        'data': data,
        'timestamp': time.time()
    }
    current_app.logger.info(f"Session data stored: {session_id}")

def update_session_timestamp(session_id):
    """Update session timestamp to extend session life."""
    if session_id in session_excel_data_cache:
        session_excel_data_cache[session_id]['timestamp'] = time.time()
        current_app.logger.info(f"Session timestamp updated: {session_id}")

@main_bp.route('/')
def index_route():
    return render_template('index.html')

@main_bp.route('/manage_mappings_ui')
def manage_mappings_route():
    return render_template('manage_mappings.html')

@main_bp.route('/output/<path:filename>')
def output_file_route(filename):
    return send_from_directory(current_app.config['OUTPUT_FOLDER'], filename)

@main_bp.route('/upload', methods=['POST'])
def upload_file_route():
    """Handle file upload with proper validation and error handling."""
    current_app.logger.info(f"Upload request received - Content-Type: {request.content_type}")
    current_app.logger.info(f"Upload request form keys: {list(request.form.keys())}")
    current_app.logger.info(f"Upload request files keys: {list(request.files.keys())}")

    try:
        session_id = request.form.get('session_id')
        current_app.logger.info(f"Session ID received: {session_id}")

        if not session_id:
            current_app.logger.warning("Upload attempt without session ID")
            return jsonify({"error": "Session ID is missing."}), 400

        # Validate session_id format
        try:
            session_id = InputValidator.validate_string(session_id, max_length=100, pattern=r'^[a-zA-Z0-9\-_]+$')
            current_app.logger.info(f"Session ID validated: {session_id}")
        except ValueError as e:
            current_app.logger.warning(f"Invalid session ID format: {e}")
            return jsonify({"error": "Invalid session ID format."}), 400

        if 'excelFile' in request.files and request.files['excelFile'].filename != '':
            excel_file_stream = request.files['excelFile']
            try:
                current_week_number = get_current_week_number()
                excel_file_copy = excel_file_stream.read()
                excel_file_stream.seek(0)
                original_filename = getattr(excel_file_stream, 'filename', '').lower()
                engine_to_use = 'pyxlsb' if original_filename.endswith('.xlsb') else 'openpyxl'

                with pd.ExcelFile(BytesIO(excel_file_copy), engine=engine_to_use) as xls:
                    expected_sheet_name = f"Summary KW{current_week_number}"
                    if expected_sheet_name not in xls.sheet_names:
                        available_weeks = [s.replace('Summary KW', '') for s in xls.sheet_names if s.startswith('Summary KW')]
                        available_weeks.sort()
                        error_msg = f"Week mismatch: File is not for current week ({current_week_number}). Available: {', '.join(available_weeks) if available_weeks else 'None'}."
                        return jsonify({"message": error_msg}), 400

                excel_file_stream.seek(0)
                excel_data_list, extraction_errors = extract_data(excel_file_stream)

                excel_data_list_with_ids = []
                for idx, item in enumerate(excel_data_list):
                    item_with_id = item.copy()
                    item_with_id['id'] = str(idx + 1)
                    if 'name' not in item_with_id or not item_with_id['name']:
                        item_with_id['name'] = item_with_id.get('scheduler_group_task', f'Unnamed Task {idx+1}')
                    excel_data_list_with_ids.append(item_with_id)

                store_session_data(session_id, excel_data_list_with_ids)

                sanitized_data_for_pm_ui = sanitize_data(excel_data_list, current_app.logger)
                pm_tasks_for_ui = [
                    {
                        "id": str(i + 1), "name": task.get("scheduler_group_task", "Unknown PM"),
                        "lines": task.get("lines", ""), "mitarbeiter_pro_aufgabe": int(task.get("mitarbeiter_pro_aufgabe", 1)),
                        "planned_worktime_min": int(task.get("planned_worktime_min", 0)), "priority": task.get("priority", "C"),
                        "quantity": int(task.get("quantity", 1)), "task_type": "PM",
                        "ticket_mo": task.get("ticket_mo", ""), "ticket_url": task.get("ticket_url", "")
                    } for i, task in enumerate(s_data for s_data in sanitized_data_for_pm_ui if s_data.get('task_type', '').upper() == 'PM')
                ]

                response_message = "File processed."
                if extraction_errors: response_message += f" {len(extraction_errors)} issues found."
                elif not excel_data_list: response_message += " No data extracted."
                else: response_message += " PM tasks extracted."

                return jsonify({
                    "message": response_message, "pm_tasks": pm_tasks_for_ui,
                    "technicians": TECHNICIANS, "technician_groups": TECHNICIAN_GROUPS,
                    "session_id": session_id, "extraction_errors": extraction_errors
                })
            except Exception as e:
                current_app.logger.error(f"Error during initial file upload: {e}", exc_info=True)
                return jsonify({"message": f"Error processing file: {str(e)}"}), 500

        elif 'absentTechnicians' in request.form:
            # Use new session validation
            if not is_session_valid(session_id):
                current_app.logger.warning(f"Session validation failed for session: {session_id}")
                return jsonify({"message": "Session expired. Re-upload."}), 400

            # Get cached data using new session management
            excel_data_list_cached = get_session_data(session_id)
            if excel_data_list_cached is None:
                current_app.logger.warning(f"No session data found for session: {session_id}")
                return jsonify({"message": "Session expired. Re-upload."}), 400

            # Update session timestamp to extend session life
            update_session_timestamp(session_id)

            try:
                absent_technicians = json.loads(request.form.get('absentTechnicians', '[]'))
                all_technicians_flat = [tech for group in TECHNICIAN_GROUPS.values() for tech in group]
                present_technicians = [tech for tech in all_technicians_flat if tech not in absent_technicians]

                total_work_minutes = calculate_work_time(get_current_day())
                sanitized_data = sanitize_data(excel_data_list_cached, current_app.logger)

                all_tasks_for_processing = [
                    {
                        "id": str(idx + 1), "name": row.get("scheduler_group_task", "Unknown"),
                        "lines": row.get("lines", ""), "mitarbeiter_pro_aufgabe": int(row.get("mitarbeiter_pro_aufgabe", 1)),
                        "planned_worktime_min": int(row.get("planned_worktime_min", 0)), "priority": row.get("priority", "C"),
                        "quantity": int(row.get("quantity", 1)), "task_type": row.get("task_type", ""),
                        "ticket_mo": row.get("ticket_mo", ""), "ticket_url": row.get("ticket_url", "")
                    } for idx, row in enumerate(sanitized_data)
                ]

                rep_tasks_for_ui = []
                eligible_technicians_for_rep_modal = {}
                raw_rep_tasks = [t for t in all_tasks_for_processing if t['task_type'].upper() == 'REP']

                for task_rep in raw_rep_tasks:
                    task_id_rep = task_rep['id']
                    rep_tasks_for_ui.append(task_rep)
                    eligible_technicians_for_rep_modal[task_id_rep] = []
                    task_duration_rep = int(task_rep.get('planned_worktime_min', 0))
                    min_acceptable_time = task_duration_rep * 0.75
                    task_lines_rep_str = str(task_rep.get('lines', ''))
                    task_lines_rep_list = [int(l.strip()) for l in task_lines_rep_str.split(',') if l.strip().isdigit()] if task_lines_rep_str and task_lines_rep_str.lower() not in ['nan', ''] else []

                    for tech_name in present_technicians:
                        tech_available_time = total_work_minutes
                        tech_config_lines = TECHNICIAN_LINES.get(tech_name, [])
                        line_eligible = not task_lines_rep_list or any(line in tech_config_lines for line in task_lines_rep_list)
                        if line_eligible and (task_duration_rep == 0 or tech_available_time >= min_acceptable_time):
                            eligible_technicians_for_rep_modal[task_id_rep].append({
                                'name': tech_name, 'available_time': tech_available_time,
                                'task_full_duration': task_duration_rep
                            })
                return jsonify({
                    "message": "REP task data prepared.", "rep_tasks": rep_tasks_for_ui,
                    "eligible_technicians": eligible_technicians_for_rep_modal, "session_id": session_id
                })
            except Exception as e:
                current_app.logger.error(f"Error processing absent technicians: {e}", exc_info=True)
                return jsonify({"message": f"Error processing absent technicians: {str(e)}"}), 500
        return jsonify({"message": "Invalid request."}), 400

    except Exception as e:
        current_app.logger.error(f"Unexpected error in upload_file_route: {e}", exc_info=True)
        return jsonify({"message": "An unexpected error occurred."}), 500

@main_bp.route('/generate_dashboard', methods=['POST'])
def generate_dashboard_route():
    try:
        form_data = request.form
        session_id = form_data.get('session_id')

        # Use new session validation
        if not session_id or not is_session_valid(session_id):
            current_app.logger.warning(f"Session validation failed for dashboard generation: {session_id}")
            return jsonify({"message": "Invalid session. Re-upload Excel."}), 400

        # Get cached data using new session management
        excel_data_from_cache = get_session_data(session_id)
        if excel_data_from_cache is None:
            current_app.logger.warning(f"No session data found for dashboard generation: {session_id}")
            return jsonify({"message": "Invalid session. Re-upload Excel."}), 400

        # Update session timestamp to extend session life
        update_session_timestamp(session_id)

        present_technicians = json.loads(form_data.get('present_technicians', '[]'))
        rep_assignments_from_ui = json.loads(form_data.get('rep_assignments', '[]'))
        all_processed_tasks_from_ui = json.loads(form_data.get('all_processed_tasks', '[]'))

        conn = get_db_connection(current_app.config['DATABASE_PATH'])
        task_manager = TaskManager(conn)
        try:
            technician_skills_map = get_all_technician_skills_by_name(conn)
            final_tasks_map = {}
            # default_technology_id = get_or_create_technology(conn, "Default Technology") # Default tech not used this way anymore

            for task_from_ui in all_processed_tasks_from_ui:
                task_id_ui = str(task_from_ui.get('id'))
                if not task_id_ui: continue
                task_to_add = task_from_ui.copy()
                task_name = task_to_add.get('name', task_to_add.get('scheduler_group_task', f'Unknown Task UI {task_id_ui}'))
                if not task_to_add.get('name'): task_to_add['name'] = task_name
                db_task_id = task_manager.get_or_create(task_name)
                task_to_add.update({'db_task_id': db_task_id}) # Store db_task_id

                # Fetch and add technology_ids for the task
                required_skills_objects = task_manager.get_required_skills(db_task_id)
                technology_ids_for_task = [skill['technology_id'] for skill in required_skills_objects]
                task_to_add['technology_ids'] = technology_ids_for_task

                final_tasks_map[task_id_ui] = task_to_add

            for task_from_cache in excel_data_from_cache:
                cache_task_id_ui = str(task_from_cache.get('id'))
                if not cache_task_id_ui or cache_task_id_ui in final_tasks_map: continue
                if task_from_cache.get('task_type', '').upper() == 'PM':
                    task_to_add = task_from_cache.copy()
                    task_name = task_to_add.get('name', task_to_add.get('scheduler_group_task', f'Unknown Cache PM {cache_task_id_ui}'))
                    if not task_to_add.get('name'): task_to_add['name'] = task_name
                    task_to_add['isAdditionalTask'] = False
                    db_task_id = task_manager.get_or_create(task_name)
                    task_to_add.update({'db_task_id': db_task_id})

                    # Fetch and add technology_ids for the task
                    required_skills_objects = task_manager.get_required_skills(db_task_id)
                    technology_ids_for_task = [skill['technology_id'] for skill in required_skills_objects]
                    task_to_add['technology_ids'] = technology_ids_for_task

                    final_tasks_map[cache_task_id_ui] = task_to_add
            conn.commit()
        finally:
            if conn: conn.close()

        all_tasks_for_dashboard = list(final_tasks_map.values())
        available_time_summary, under_resourced_pm_tasks = generate_html_files(
            all_tasks_for_dashboard, present_technicians, rep_assignments_from_ui,
            current_app.jinja_env, current_app.config['OUTPUT_FOLDER'], TECHNICIANS, TECHNICIAN_GROUPS, current_app.logger, technician_skills_map
        )
        dashboard_url = url_for('main.output_file_route', filename='technician_dashboard.html', _external=True) + f'?cache_bust={random.randint(1,100000)}'
        return jsonify({
            "message": "Dashboard generated.",
            "available_time": available_time_summary,
            "under_resourced_tasks": under_resourced_pm_tasks,
            "session_id": session_id,
            "dashboard_url": dashboard_url
        })
    except Exception as e:
        current_app.logger.error(f"Error in generate_dashboard_route: {e}", exc_info=True)
        return jsonify({"message": f"Error generating dashboard: {str(e)}"}), 500
