from flask import Flask, request, jsonify, send_from_directory, render_template
import os
import json
import pandas as pd  # Add pandas import for Excel validation
from io import BytesIO  # Add BytesIO import for handling Excel bytes
from jinja2 import Environment, FileSystemLoader
from extract_data import extract_data, get_current_day, get_current_week_number #, get_current_week, get_current_week_number, get_current_shift
import traceback
import random
import sqlite3 # Used for specific error handling in routes
import logging # Import logging

# Import from new modules
from db_utils import (
    get_db_connection, init_db,
    get_or_create_technology, get_or_create_task,
    get_all_technician_skills_by_name, update_technician_skill, get_technician_skills_by_id,
    get_or_create_technology_group, get_all_technology_groups, delete_technology, # Added delete_technology
    get_all_specialities, get_or_create_speciality, # Added speciality imports
    get_technician_specialities, add_speciality_to_technician, remove_speciality_from_technician # Added technician speciality imports
)
from config_manager import load_app_config, TECHNICIAN_LINES, TECHNICIANS, TECHNICIAN_GROUPS #, TASK_NAME_MAPPING, TECHNICIAN_TASKS
from data_processing import sanitize_data, calculate_work_time #, calculate_available_time, validate_assignments_flat_input
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
                "id": tech_row['id'],
                "sattelite_point": tech_row['sattelite_point'],
                "technician_lines": [int(l.strip()) for l in tech_row['lines'].split(',') if l.strip().isdigit()] if tech_row['lines'] else [],
                "task_assignments": [],
                "specialities": [] # Add specialities list
            }
            # Updated query to join with tasks table for task_name
            cursor.execute('''
                SELECT t.name as task_name, tta.priority 
                FROM technician_task_assignments tta
                JOIN tasks t ON tta.task_id = t.id
                WHERE tta.technician_id = ? 
                ORDER BY tta.priority ASC
            ''', (tech_row['id'],))
            for assign_row in cursor.fetchall():
                tech_data["task_assignments"].append({'task': assign_row['task_name'], 'prio': assign_row['priority']})

            # Fetch and add specialities for the technician
            tech_data["specialities"] = get_technician_specialities(conn, tech_row['id'])

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
                    # Look up task_id by task_name
                    cursor.execute("SELECT id FROM tasks WHERE name = ?", (task_name_assign,))
                    task_db_row = cursor.fetchone()
                    if task_db_row:
                        task_id_assign = task_db_row['id']
                        cursor.execute("INSERT INTO technician_task_assignments (technician_id, task_id, priority) VALUES (?, ?, ?)",
                                       (technician_id, task_id_assign, priority_assign))
                    else:
                        # Log or handle missing task - for now, we skip assigning this task
                        app.logger.warning(f"Task '{task_name_assign}' not found in tasks table. Cannot save assignment for technician '{tech_name}'.")

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

@app.route('/api/technologies', methods=['GET'])
def get_technologies_api():
    conn = None
    try:
        conn = get_db_connection(app.config['DATABASE'])
        cursor = conn.cursor()
        # Join with technology_groups to get group_name, and include parent_id
        cursor.execute("""
            SELECT t.id, t.name, t.group_id, t.parent_id, tg.name as group_name
            FROM technologies t
            LEFT JOIN technology_groups tg ON t.group_id = tg.id
            ORDER BY tg.name, t.name -- Consider a more sophisticated sort for hierarchy later if needed
        """)
        technologies = [
            {"id": row['id'], "name": row['name'], "group_id": row['group_id'], "group_name": row['group_name'], "parent_id": row['parent_id']}
            for row in cursor.fetchall()
        ]
        return jsonify(technologies)
    except sqlite3.Error as e:
        app.logger.error(f"Database error fetching technologies: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/technologies', methods=['POST'])
def add_technology_api():
    conn = None
    try:
        data = request.get_json()
        if not data or 'name' not in data or not data['name'].strip():
            return jsonify({"message": "Technology name is required."}), 400

        tech_name = data['name'].strip()
        group_id = data.get('group_id')
        parent_id = data.get('parent_id') # Get parent_id from request

        if group_id is not None:
            try:
                group_id = int(group_id)
            except ValueError:
                return jsonify({"message": "Invalid group_id format."}), 400

        if parent_id is not None:
            try:
                parent_id = int(parent_id)
            except ValueError:
                return jsonify({"message": "Invalid parent_id format."}), 400

        conn = get_db_connection(app.config['DATABASE'])
        cursor = conn.cursor() # Use cursor for direct insert with parent_id

        # Check if technology with this name already exists to prevent duplicates by name
        cursor.execute("SELECT id FROM technologies WHERE name = ?", (tech_name,))
        existing_tech = cursor.fetchone()
        if existing_tech:
            # Optionally, could update existing tech's group_id/parent_id here if desired
            # For now, returning conflict if name exists, as get_or_create_technology also implies uniqueness by name.
            return jsonify({"message": f"Technology '{tech_name}' already exists."}), 409

        cursor.execute("INSERT INTO technologies (name, group_id, parent_id) VALUES (?, ?, ?)",
                       (tech_name, group_id, parent_id))
        conn.commit()
        technology_id = cursor.lastrowid

        # Fetch the created technology to return its details, including group and parent info
        cursor.execute(""" 
            SELECT t.id, t.name, t.group_id, t.parent_id, tg.name as group_name
            FROM technologies t
            LEFT JOIN technology_groups tg ON t.group_id = tg.id
            WHERE t.id = ?
        """, (technology_id,))
        technology = cursor.fetchone()

        if technology:
            return jsonify({
                "id": technology['id'],
                "name": technology['name'],
                "group_id": technology['group_id'],
                "group_name": technology['group_name'],
                "parent_id": technology['parent_id']
            }), 201
        else: # Should not happen if get_or_create_technology works
            return jsonify({"message": "Failed to create or retrieve technology."}), 500

    except sqlite3.IntegrityError: # Handles unique constraint violation if name already exists (though get_or_create should handle this)
        if conn: conn.rollback()
        return jsonify({"message": f"Technology '{tech_name}' already exists."}), 409 # Conflict
    except sqlite3.Error as e:
        if conn: conn.rollback()
        app.logger.error(f"Database error adding technology: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    except Exception as e:
        if conn: conn.rollback()
        app.logger.error(f"Server error adding technology: {e}")
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/technologies/<int:technology_id>', methods=['DELETE'])
def delete_technology_api(technology_id):
    conn = None
    try:
        conn = get_db_connection(app.config['DATABASE'])
        # Before deleting the technology, ensure child technologies have their parent_id updated to NULL
        cursor = conn.cursor()
        cursor.execute("UPDATE technologies SET parent_id = NULL WHERE parent_id = ?", (technology_id,))
        conn.commit() # Commit this change first

        # Now call the new db_utils function to delete the technology and its direct dependencies
        rows_deleted = delete_technology(conn, technology_id) # This function now handles commit

        if rows_deleted > 0:
            return jsonify({"message": f"Technology ID {technology_id} and its dependencies deleted successfully."}), 200
        else:
            return jsonify({"message": f"Technology ID {technology_id} not found."}), 404
    except sqlite3.Error as e:
        if conn: conn.rollback()
        app.logger.error(f"Database error deleting technology {technology_id}: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    except Exception as e:
        if conn: conn.rollback()
        app.logger.error(f"Server error deleting technology {technology_id}: {e}")
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/technology_groups', methods=['GET'])
def get_technology_groups_api():
    conn = None
    try:
        conn = get_db_connection(app.config['DATABASE'])
        groups = get_all_technology_groups(conn)
        return jsonify(groups)
    except sqlite3.Error as e:
        app.logger.error(f"Database error fetching technology groups: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/technology_groups', methods=['POST'])
def add_technology_group_api():
    conn = None
    try:
        data = request.get_json()
        if not data or 'name' not in data or not data['name'].strip():
            return jsonify({"message": "Technology group name is required."}), 400

        group_name = data['name'].strip()

        conn = get_db_connection(app.config['DATABASE'])
        group_id = get_or_create_technology_group(conn, group_name)

        # Fetch the created/existing group to return its details
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM technology_groups WHERE id = ?", (group_id,))
        group = cursor.fetchone()

        if group:
            return jsonify({"id": group['id'], "name": group['name']}), 201
        else:
            return jsonify({"message": "Failed to create or retrieve technology group."}), 500

    except sqlite3.IntegrityError: # Handles unique constraint violation
        if conn: conn.rollback()
        return jsonify({"message": f"Technology group '{group_name}' already exists."}), 409
    except sqlite3.Error as e:
        if conn: conn.rollback()
        app.logger.error(f"Database error adding technology group: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    except Exception as e:
        if conn: conn.rollback()
        app.logger.error(f"Server error adding technology group: {e}")
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

# --- Speciality API Endpoints ---
@app.route('/api/specialities', methods=['GET'])
def get_specialities_api():
    conn = None
    try:
        conn = get_db_connection(app.config['DATABASE'])
        specialities = get_all_specialities(conn)
        return jsonify(specialities)
    except sqlite3.Error as e:
        app.logger.error(f"Database error fetching specialities: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/specialities', methods=['POST'])
def add_speciality_api():
    conn = None
    try:
        data = request.get_json()
        if not data or 'name' not in data or not data['name'].strip():
            return jsonify({"message": "Speciality name is required."}), 400

        speciality_name = data['name'].strip()
        conn = get_db_connection(app.config['DATABASE'])
        speciality_id = get_or_create_speciality(conn, speciality_name)

        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM specialities WHERE id = ?", (speciality_id,))
        speciality = cursor.fetchone()

        if speciality:
            return jsonify({"id": speciality['id'], "name": speciality['name']}), 201
        else:
            return jsonify({"message": "Failed to create or retrieve speciality."}), 500

    except sqlite3.IntegrityError:
        if conn: conn.rollback()
        return jsonify({"message": f"Speciality '{speciality_name}' already exists."}), 409
    except sqlite3.Error as e:
        if conn: conn.rollback()
        app.logger.error(f"Database error adding speciality: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    except Exception as e:
        if conn: conn.rollback()
        app.logger.error(f"Server error adding speciality: {e}")
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

# --- Technician Speciality API Endpoints ---
@app.route('/api/technicians/<int:technician_id>/specialities', methods=['GET'])
def get_technician_specialities_api(technician_id):
    conn = None
    try:
        conn = get_db_connection(app.config['DATABASE'])
        specialities = get_technician_specialities(conn, technician_id)
        return jsonify(specialities)
    except sqlite3.Error as e:
        app.logger.error(f"Database error fetching specialities for technician {technician_id}: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/technicians/<int:technician_id>/specialities', methods=['POST'])
def add_technician_speciality_api(technician_id):
    conn = None
    try:
        data = request.get_json()
        speciality_id = data.get('speciality_id')
        if speciality_id is None:
            return jsonify({"message": "speciality_id is required."}), 400
        try:
            speciality_id = int(speciality_id)
        except ValueError:
            return jsonify({"message": "Invalid speciality_id format."}), 400

        conn = get_db_connection(app.config['DATABASE'])
        add_speciality_to_technician(conn, technician_id, speciality_id)
        return jsonify({"message": f"Speciality {speciality_id} added to technician {technician_id}."}), 201
    except sqlite3.IntegrityError as e: # Handles FK constraints or if combo already exists
        if conn: conn.rollback()
        app.logger.warning(f"Integrity error adding speciality {speciality_id} to technician {technician_id}: {e}")
        return jsonify({"message": f"Failed to add speciality. Ensure technician and speciality exist, and it's not a duplicate."}), 400
    except sqlite3.Error as e:
        if conn: conn.rollback()
        app.logger.error(f"Database error adding speciality to technician: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/technicians/<int:technician_id>/specialities/<int:speciality_id>', methods=['DELETE'])
def remove_technician_speciality_api(technician_id, speciality_id):
    conn = None
    try:
        conn = get_db_connection(app.config['DATABASE'])
        remove_speciality_from_technician(conn, technician_id, speciality_id)
        # Check if the row was actually deleted if needed by checking cursor.rowcount, but for now assume success if no error
        return jsonify({"message": f"Speciality {speciality_id} removed from technician {technician_id}."}), 200
    except sqlite3.Error as e:
        if conn: conn.rollback()
        app.logger.error(f"Database error removing speciality from technician: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/technician_skills/<int:technician_id>', methods=['GET'])
def get_technician_skills_api(technician_id):
    conn = None
    try:
        conn = get_db_connection(app.config['DATABASE'])
        # Use the new db_utils function
        skills = get_technician_skills_by_id(conn, technician_id)
        return jsonify({"technician_id": technician_id, "skills": skills})
    except sqlite3.Error as e:
        app.logger.error(f"Database error fetching skills for technician {technician_id}: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    except Exception as e:
        app.logger.error(f"Server error fetching skills for technician {technician_id}: {e}")
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/technician_skill', methods=['POST'])
def update_technician_skill_api():
    conn = None
    try:
        data = request.get_json()
        technician_id = data.get('technician_id')
        technology_id = data.get('technology_id')
        skill_level = data.get('skill_level')

        if technician_id is None or technology_id is None or skill_level is None:
            return jsonify({"message": "Missing technician_id, technology_id, or skill_level."}), 400

        try:
            skill_level = int(skill_level)
            if not (0 <= skill_level <= 4):
                 raise ValueError("Skill level must be between 0 and 4.")
        except ValueError as ve:
            return jsonify({"message": str(ve)}), 400

        conn = get_db_connection(app.config['DATABASE'])
        # update_technician_skill handles commit internally
        update_technician_skill(conn, technician_id, technology_id, skill_level)

        return jsonify({
            "message": "Technician skill updated successfully.",
            "technician_id": technician_id,
            "technology_id": technology_id,
            "skill_level": skill_level
        }), 200
    except sqlite3.IntegrityError as e: # e.g. foreign key constraint failed
        if conn: conn.rollback()
        app.logger.error(f"Database integrity error updating skill: {e}")
        return jsonify({"message": f"Database integrity error: {e}. Check if technician and technology IDs exist."}), 400
    except sqlite3.Error as e:
        if conn: conn.rollback()
        app.logger.error(f"Database error updating skill: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    except Exception as e:
        if conn: conn.rollback()
        app.logger.error(f"Server error updating skill: {e}")
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/tasks_for_mapping', methods=['GET'])
def get_tasks_for_mapping_api():
    conn = None
    try:
        conn = get_db_connection(app.config['DATABASE'])
        cursor = conn.cursor()
        # Fetch tasks along with their currently assigned technology_id and technology_name
        cursor.execute('''
            SELECT t.id, t.name, t.technology_id, tech.name as technology_name
            FROM tasks t
            LEFT JOIN technologies tech ON t.technology_id = tech.id
            ORDER BY t.name
        ''')
        tasks = [
            {
                "id": row['id'],
                "name": row['name'],
                "technology_id": row['technology_id'],
                "technology_name": row['technology_name']
            }
            for row in cursor.fetchall()
        ]
        return jsonify(tasks)
    except sqlite3.Error as e:
        app.logger.error(f"Database error fetching tasks for mapping: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/tasks/<int:task_id>/technology', methods=['PUT'])
def update_task_technology_api(task_id):
    conn = None
    try:
        data = request.get_json()
        technology_id = data.get('technology_id') # This can be None/null

        # Validate technology_id if not None
        if technology_id is not None:
            try:
                technology_id = int(technology_id)
            except ValueError:
                return jsonify({"message": "Invalid technology_id format."}), 400

        conn = get_db_connection(app.config['DATABASE'])
        cursor = conn.cursor()

        # Check if task exists
        cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
        task_row = cursor.fetchone()
        if not task_row:
            return jsonify({"message": f"Task with ID {task_id} not found."}), 404

        # If technology_id is provided, check if it exists
        if technology_id is not None:
            cursor.execute("SELECT id FROM technologies WHERE id = ?", (technology_id,))
            tech_row = cursor.fetchone()
            if not tech_row:
                return jsonify({"message": f"Technology with ID {technology_id} not found."}), 404

        # Update the task's technology_id (can be set to NULL)
        cursor.execute("UPDATE tasks SET technology_id = ? WHERE id = ?", (technology_id, task_id))
        conn.commit()

        return jsonify({"message": f"Task {task_id} technology mapping updated successfully."}), 200

    except sqlite3.Error as e:
        if conn: conn.rollback()
        app.logger.error(f"Database error updating task technology for task {task_id}: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    except Exception as e:
        if conn: conn.rollback()
        app.logger.error(f"Server error updating task technology for task {task_id}: {e}")
        return jsonify({"message": f"Server error: {str(e)}"}), 500
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
            # Get the current week number for validation
            current_week_number = get_current_week_number()

            # Check if the Excel file contains a worksheet for the current week
            # First, create a copy of the file stream for preliminary analysis
            excel_file_copy = excel_file_stream.read()
            excel_file_stream.seek(0)  # Reset the file pointer

            # Determine engine based on filename
            original_filename = getattr(excel_file_stream, 'filename', '').lower()
            engine_to_use = 'pyxlsb' if original_filename.endswith('.xlsb') else 'openpyxl'

            # Read the Excel file sheets to check if the current week sheet exists
            try:
                with pd.ExcelFile(BytesIO(excel_file_copy), engine=engine_to_use) as xls:
                    expected_sheet_name = f"Summary KW{current_week_number}"
                    if expected_sheet_name not in xls.sheet_names:
                        # Week mismatch detected
                        available_weeks = [sheet for sheet in xls.sheet_names if sheet.startswith('Summary KW')]
                        available_week_numbers = [w.replace('Summary KW', '') for w in available_weeks]

                        error_msg = f"Week mismatch error: The uploaded Excel file doesn't contain data for the current week ({current_week_number}). "
                        if available_week_numbers:
                            # Sort the week numbers for better display
                            available_week_numbers.sort()
                            weeks_str = ', '.join(available_week_numbers)
                            error_msg += f"The Excel file contains data for week(s): {weeks_str}"
                        else:
                            error_msg += "No valid week sheets found in the Excel file."
                        return jsonify({"message": error_msg}), 400
            except Exception as sheet_check_error:
                app.logger.error(f"Error checking Excel sheets: {sheet_check_error}")
                # Continue with normal processing if sheet checking fails

            # Reset the file stream again before extracting data
            excel_file_stream.seek(0)

            # Unpack data and errors from extract_data
            excel_data_list, extraction_errors = extract_data(excel_file_stream)

            # MODIFICATION START: Add IDs to tasks from Excel before caching
            excel_data_list_with_ids = []
            for idx, task_data_item in enumerate(excel_data_list):
                item_with_id = task_data_item.copy()
                item_with_id['id'] = str(idx + 1) # Assign 1-based string ID
                # Ensure 'name' field is populated from 'scheduler_group_task' if 'name' is missing
                if 'name' not in item_with_id or not item_with_id['name']:
                    item_with_id['name'] = item_with_id.get('scheduler_group_task', f'Unnamed Task {idx+1}')
                excel_data_list_with_ids.append(item_with_id)
            # MODIFICATION END

            session_excel_data_cache[session_id] = excel_data_list_with_ids # Cache data with IDs

            # Pass the original excel_data_list to sanitize_data for pm_tasks_for_ui construction,
            # as pm_tasks_for_ui re-assigns its own 'id' based on its filtered list index.
            # The critical part is that session_excel_data_cache[session_id] has the IDs and initial names.
            sanitized_data_for_pm_ui = sanitize_data(excel_data_list, app.logger) # Pass logger
            pm_tasks_for_ui = []
            for idx, task_data in enumerate(sanitized_data_for_pm_ui): # task_data here is from original list
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
            sanitized_data = sanitize_data(excel_data_list_cached, app.logger) # Pass app.logger
            all_tasks_for_processing = []
            for idx, row in enumerate(sanitized_data, start=1):
                all_tasks_for_processing.append({
                    "id": str(idx), "name": row.get("scheduler_group_task", "Unknown"),
                    "lines": row.get("lines", ""), "mitarbeiter_pro_aufgabe": int(row.get("mitarbeiter_pro_aufgabe", 1)),
                    "planned_worktime_min": int(row.get("planned_worktime_min", 0)), "priority": row.get("priority", "C"),
                    "quantity": int(row.get("quantity", 1)), "task_type": row.get("task_type", ""),
                    "ticket_mo": row.get("ticket_mo", ""), "ticket_url": row.get("ticket_url", "")
                })

            # PM tasks are no longer pre-assigned here.
            # available_time_after_pm is no longer calculated here.

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
                    # Use total_work_minutes as the initial available time for REP modal eligibility
                    tech_available_time = total_work_minutes
                    tech_config_lines = TECHNICIAN_LINES.get(tech_name, [])

                    # Check line eligibility
                    line_eligible = True # Assume eligible if task has no lines specified
                    if task_lines_rep_list: # Only check if task specifies lines
                        line_eligible = any(line in tech_config_lines for line in task_lines_rep_list)

                    if line_eligible:
                        if task_duration_rep == 0 or tech_available_time >= min_acceptable_time:
                            eligible_technicians_for_rep_modal[task_id_rep].append({
                                'name': tech_name,
                                'available_time': tech_available_time, # This is now gross available time
                                'task_full_duration': task_duration_rep # For UI display of partial assignment potential
                            })

            return jsonify({
                "message": "Absent technicians processed, REP task data prepared.", # Message updated
                "repTasks": rep_tasks_for_ui, # Send REP tasks for the modal
                "eligibleTechnicians": eligible_technicians_for_rep_modal, # Send eligibility info
                "session_id": session_id # Keep session active
            })

        except Exception as e:
            print(f"Error during absent tech processing/REP prep: {e}") # Message updated
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
        all_processed_tasks_json = form_data.get('all_processed_tasks', '[]')

        if not session_id or session_id not in session_excel_data_cache:
            return jsonify({"message": "Invalid session or data. Re-upload Excel."}), 400

        excel_data_from_cache = session_excel_data_cache[session_id] # Has string IDs "1", "2", ... and 'name'

        try:
            present_technicians = json.loads(present_technicians_json)
            rep_assignments_from_ui = json.loads(rep_assignments_json)
            all_processed_tasks_from_ui = json.loads(all_processed_tasks_json)
        except json.JSONDecodeError as je:
            app.logger.error(f"JSON Decode Error in generate_dashboard_route: {je}")
            return jsonify({"message": "Invalid format for technician list, REP assignments, or processed tasks."}), 400

        if not isinstance(present_technicians, list) or not all(isinstance(tech, str) for tech in present_technicians) or \
           not isinstance(rep_assignments_from_ui, list) or \
           not isinstance(all_processed_tasks_from_ui, list):
            return jsonify({"message": "Invalid data structure for present_technicians, rep_assignments, or all_processed_tasks."}),400

        # Get DB connection
        conn = get_db_connection(app.config['DATABASE'])
        try:
            # Fetch technician skills
            technician_skills_map = get_all_technician_skills_by_name(conn)
            app.logger.debug(f"Fetched technician skills map: {technician_skills_map}")

            final_tasks_map = {}
            app.logger.debug(f"Starting to build final_tasks_map. all_processed_tasks_from_ui count: {len(all_processed_tasks_from_ui)}")

            default_technology_name = "Default Technology" # Define a default technology
            default_technology_id = get_or_create_technology(conn, default_technology_name)
            app.logger.info(f"Using default technology ID: {default_technology_id} for '{default_technology_name}'")

            # 1. Add all tasks that went through the UI modal flow.
            for task_from_ui in all_processed_tasks_from_ui:
                task_id_ui = str(task_from_ui.get('id'))
                if not task_id_ui:
                    app.logger.warning(f"Task from UI missing ID: {task_from_ui.get('scheduler_group_task')}")
                    continue

                task_to_add = task_from_ui.copy()
                task_name = task_to_add.get('name', task_to_add.get('scheduler_group_task', f'Unknown Task UI {task_id_ui}'))
                if not task_to_add.get('name'): task_to_add['name'] = task_name

                # Get or create task in DB and assign technology_id
                # For now, all tasks from UI flow get the default technology
                db_task_id = get_or_create_task(conn, task_name, default_technology_id)
                task_to_add['technology_id'] = default_technology_id
                task_to_add['db_task_id'] = db_task_id # Store the actual DB task ID

                final_tasks_map[task_id_ui] = task_to_add
                app.logger.debug(f"Processed task from UI: UI ID {task_id_ui}, DB Task ID {db_task_id}, Name: {task_name}, TechID: {default_technology_id}")

            # 2. Add original PM tasks from the cache if they weren't processed via the UI.
            app.logger.debug(f"Processing excel_data_from_cache (count: {len(excel_data_from_cache)}) for PM tasks not in UI flow.")
            for task_from_cache in excel_data_from_cache:
                cache_task_id_ui = str(task_from_cache.get('id'))
                if not cache_task_id_ui:
                    app.logger.warning(f"Task from cache missing ID: {task_from_cache.get('scheduler_group_task') or task_from_cache.get('name')}")
                    continue

                if cache_task_id_ui not in final_tasks_map:
                    task_type = task_from_cache.get('task_type', '').upper()
                    if task_type == 'PM':
                        task_to_add = task_from_cache.copy()
                        task_name = task_to_add.get('name', task_to_add.get('scheduler_group_task', f'Unknown Cache PM {cache_task_id_ui}'))
                        if not task_to_add.get('name'): task_to_add['name'] = task_name
                        task_to_add['isAdditionalTask'] = False

                        # Get or create task in DB and assign technology_id
                        db_task_id = get_or_create_task(conn, task_name, default_technology_id)
                        task_to_add['technology_id'] = default_technology_id
                        task_to_add['db_task_id'] = db_task_id

                        # Use a consistent ID format if these tasks are added to final_tasks_map
                        # The original cache_task_id_ui (e.g., "1", "2") is fine as a key if it's unique
                        final_tasks_map[cache_task_id_ui] = task_to_add
                        app.logger.debug(f"Processed PM task from cache: UI ID {cache_task_id_ui}, DB Task ID {db_task_id}, Name: {task_name}, TechID: {default_technology_id}")

            conn.commit() # Commit any new tasks/technologies created

        finally:
            if conn:
                conn.close()

        all_tasks_for_dashboard = list(final_tasks_map.values())
        app.logger.info(f"Constructed all_tasks_for_dashboard with {len(all_tasks_for_dashboard)} tasks for dashboard generation.")

        available_time_result = generate_html_files(
            all_tasks_for_dashboard,
            present_technicians,
            rep_assignments_from_ui,
            env,
            OUTPUT_FOLDER_ABS,
            TECHNICIANS,
            TECHNICIAN_GROUPS,
            app.logger,
            technician_skills_map # Pass technician skills
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
