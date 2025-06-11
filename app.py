import os
import sys
from flask import Flask, render_template, send_from_directory, request, jsonify, url_for
from jinja2 import Environment, FileSystemLoader
import json
import pandas as pd
from io import BytesIO

import random
import sqlite3 # For error types
import logging

# Add project root to sys.path to allow importing config
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config import Config

# Import from local services package (relative to wkndPlanning)
from .services.extract_data import extract_data, get_current_day, get_current_week_number
from .services.db_utils import (
    get_db_connection, init_db,
    get_or_create_technology, get_or_create_task,
    get_all_technician_skills_by_name, update_technician_skill, get_technician_skills_by_id,
    get_or_create_technology_group, get_all_technology_groups, delete_technology,
    get_all_specialities, get_or_create_speciality,
    get_technician_specialities, add_speciality_to_technician, remove_speciality_from_technician
)
from .services.config_manager import load_app_config, TECHNICIAN_LINES, TECHNICIANS, TECHNICIAN_GROUPS
from .services.data_processing import sanitize_data, calculate_work_time
from .services.dashboard import generate_html_files

app = Flask(__name__,
            template_folder='templates',  # Relative to app.py (wkndPlanning/templates)
            static_folder='static')     # Relative to app.py (wkndPlanning/static)
app.config.from_object(Config)

DATABASE_PATH = app.config['DATABASE_PATH']
OUTPUT_FOLDER_ABS = app.config['OUTPUT_FOLDER']

app.logger.setLevel(logging.DEBUG)

# Jinja environment for generate_html_files
# Use Flask's configured template_folder which is 'wkndPlanning/templates'
# The FileSystemLoader path should be absolute or relative to the execution directory of app.py
# Config.TEMPLATES_FOLDER is an absolute path.
env = Environment(loader=FileSystemLoader(app.config['TEMPLATES_FOLDER']))
session_excel_data_cache = {}

with app.app_context():
    init_db(DATABASE_PATH, app.logger)
    load_app_config(DATABASE_PATH, app.logger) # Populates globals in .services.config_manager

@app.route('/')
def index_route():
    return render_template('index.html')

@app.route('/manage_mappings_ui')
def manage_mappings_route():
    return render_template('manage_mappings.html')

@app.route('/output/<path:filename>')
def output_file_route(filename):
    return send_from_directory(OUTPUT_FOLDER_ABS, filename)

# API and other routes from the original app.py
# Ensure all imports are relative to the services package if they were local before.
# Global variables like TECHNICIAN_GROUPS are imported from .services.config_manager

@app.route('/technicians', methods=['GET'])
def get_technicians_route():
    if TECHNICIAN_GROUPS:
        return jsonify(TECHNICIAN_GROUPS)
    else:
        return jsonify({"error": "Technician groups not available."}), 500

@app.route('/api/get_technician_mappings', methods=['GET'])
def get_technician_mappings_api():
    conn = get_db_connection(DATABASE_PATH)
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
                "specialities": []
            }
            cursor.execute(
                "SELECT t.name as task_name, tta.priority FROM technician_task_assignments tta JOIN tasks t ON tta.task_id = t.id WHERE tta.technician_id = ? ORDER BY tta.priority ASC",
                (tech_row['id'],)
            )
            for assign_row in cursor.fetchall():
                tech_data["task_assignments"].append({'task': assign_row['task_name'], 'prio': assign_row['priority']})
            tech_data["specialities"] = get_technician_specialities(conn, tech_row['id'])
            technicians_output[tech_name] = tech_data
        return jsonify({"technicians": technicians_output})
    except sqlite3.Error as e:
        app.logger.error(f"SQLite error in get_technician_mappings_api: {e}")
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/save_technician_mappings', methods=['POST'])
def save_technician_mappings_api():
    conn = None
    try:
        conn = get_db_connection(DATABASE_PATH)
        cursor = conn.cursor()
        updated_data = request.get_json()
        if not updated_data or 'technicians' not in updated_data:
            return jsonify({"message": "Invalid data format"}), 400

        technicians_from_payload = updated_data.get('technicians', {})
        for tech_name, tech_payload_data in technicians_from_payload.items():
            sattelite_point = tech_payload_data.get('sattelite_point')
            lines_list = tech_payload_data.get('technician_lines', [])
            lines_str = ",".join(map(str, [l for l in lines_list if isinstance(l, int)])) if lines_list else ""

            task_assignments_payload = sorted(
                filter(lambda ta: isinstance(ta, dict) and 'task' in ta and 'prio' in ta and isinstance(ta['prio'], int) and ta['prio'] >= 1,
                       tech_payload_data.get('task_assignments', [])),
                key=lambda x: x.get('prio')
            )

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
                    cursor.execute("SELECT id FROM tasks WHERE name = ?", (task_name_assign,))
                    task_db_row = cursor.fetchone()
                    if task_db_row:
                        task_id_assign = task_db_row['id']
                        cursor.execute("INSERT INTO technician_task_assignments (technician_id, task_id, priority) VALUES (?, ?, ?)",
                                       (technician_id, task_id_assign, priority_assign))
                    else:
                        app.logger.warning(f"Task '{task_name_assign}' not found. Cannot save assignment for '{tech_name}'.")
        conn.commit()
        load_app_config(DATABASE_PATH, app.logger) # Reload config globals
        return jsonify({"message": "Technician mappings saved and reloaded."})
    except sqlite3.Error as e:
        if conn: conn.rollback()
        app.logger.error(f"SQLite error saving technician mappings: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    except Exception as e:
        if conn: conn.rollback()
        app.logger.error(f"Error saving technician mappings: {e}", exc_info=True)
        return jsonify({"message": f"Error saving mappings: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/technologies', methods=['GET'])
def get_technologies_api():
    conn = None
    try:
        conn = get_db_connection(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT t.id, t.name, t.group_id, t.parent_id, tg.name as group_name FROM technologies t LEFT JOIN technology_groups tg ON t.group_id = tg.id ORDER BY tg.name, t.name")
        technologies = [{"id": row['id'], "name": row['name'], "group_id": row['group_id'], "group_name": row['group_name'], "parent_id": row['parent_id']} for row in cursor.fetchall()]
        return jsonify(technologies)
    except sqlite3.Error as e:
        app.logger.error(f"Database error fetching technologies: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    finally:
        if conn: conn.close()

@app.route('/api/technologies', methods=['POST'])
def add_technology_api():
    conn = None
    tech_name = None  # Initialize tech_name
    try:
        data = request.get_json()
        tech_name = data.get('name', '').strip()
        if not tech_name:
            return jsonify({"message": "Technology name is required."}), 400

        group_id = data.get('group_id')
        parent_id = data.get('parent_id')
        if group_id is not None: group_id = int(group_id)
        if parent_id is not None: parent_id = int(parent_id)

        conn = get_db_connection(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM technologies WHERE name = ?", (tech_name,))
        if cursor.fetchone():
            return jsonify({"message": f"Technology '{tech_name}' already exists."}), 409

        cursor.execute("INSERT INTO technologies (name, group_id, parent_id) VALUES (?, ?, ?)", (tech_name, group_id, parent_id))
        conn.commit()
        technology_id = cursor.lastrowid

        cursor.execute("SELECT t.id, t.name, t.group_id, t.parent_id, tg.name as group_name FROM technologies t LEFT JOIN technology_groups tg ON t.group_id = tg.id WHERE t.id = ?", (technology_id,))
        technology = cursor.fetchone()
        return jsonify(dict(technology)), 201
    except ValueError:
        return jsonify({"message": "Invalid group_id or parent_id format."}), 400
    except sqlite3.IntegrityError:
        if conn: conn.rollback()
        return jsonify({"message": f"Technology '{tech_name}' already exists or invalid foreign key."}), 409
    except sqlite3.Error as e:
        if conn: conn.rollback()
        app.logger.error(f"Database error adding technology: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    except Exception as e:
        if conn: conn.rollback()
        app.logger.error(f"Server error adding technology: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn: conn.close()

@app.route('/api/technologies/<int:technology_id>', methods=['DELETE'])
def delete_technology_api(technology_id):
    conn = None
    try:
        conn = get_db_connection(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE technologies SET parent_id = NULL WHERE parent_id = ?", (technology_id,))
        conn.commit()

        rows_deleted = delete_technology(conn, technology_id) # db_utils function
        if rows_deleted > 0:
            return jsonify({"message": f"Technology ID {technology_id} and dependencies deleted."}), 200
        else:
            return jsonify({"message": f"Technology ID {technology_id} not found."}), 404
    except Exception as e:
        if conn: conn.rollback()
        app.logger.error(f"Error deleting technology {technology_id}: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn: conn.close()

@app.route('/api/technology_groups', methods=['GET'])
def get_technology_groups_api():
    conn = None
    try:
        conn = get_db_connection(DATABASE_PATH)
        groups = get_all_technology_groups(conn)
        return jsonify(groups)
    except Exception as e:
        app.logger.error(f"Error fetching technology groups: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn: conn.close()

@app.route('/api/technology_groups', methods=['POST'])
def add_technology_group_api():
    conn = None
    group_name = None  # Initialize group_name
    try:
        data = request.get_json()
        group_name = data.get('name', '').strip()
        if not group_name:
            return jsonify({"message": "Technology group name is required."}), 400

        conn = get_db_connection(DATABASE_PATH)
        group_id = get_or_create_technology_group(conn, group_name)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM technology_groups WHERE id = ?", (group_id,))
        group = cursor.fetchone()
        return jsonify(dict(group)), 201
    except sqlite3.IntegrityError:
        if conn: conn.rollback()
        return jsonify({"message": f"Technology group '{group_name}' already exists."}), 409
    except Exception as e:
        if conn: conn.rollback()
        app.logger.error(f"Error adding technology group: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn: conn.close()

@app.route('/api/technology_groups/<int:group_id>', methods=['PUT'])
def update_technology_group_api(group_id):
    conn = None
    try:
        data = request.get_json()
        new_name = data.get('name', '').strip()
        if not new_name:
            return jsonify({"message": "New name for technology group is required."}), 400

        conn = get_db_connection(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM technology_groups WHERE id = ?", (group_id,))
        if not cursor.fetchone():
            return jsonify({"message": f"Technology group ID {group_id} not found."}), 404

        cursor.execute("SELECT id FROM technology_groups WHERE name = ? AND id != ?", (new_name, group_id))
        if cursor.fetchone():
            return jsonify({"message": f"Technology group name \'{new_name}\' already exists."}), 409

        cursor.execute("UPDATE technology_groups SET name = ? WHERE id = ?", (new_name, group_id))
        conn.commit()

        cursor.execute("SELECT id, name FROM technology_groups WHERE id = ?", (group_id,))
        updated_group = cursor.fetchone()
        return jsonify(dict(updated_group)), 200
    except sqlite3.IntegrityError:
        if conn: conn.rollback()
        return jsonify({"message": f"Technology group name \'{new_name}\' already exists."}), 409
    except Exception as e:
        if conn: conn.rollback()
        app.logger.error(f"Error updating technology group {group_id}: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn: conn.close()

@app.route('/api/technology_groups/<int:group_id>', methods=['DELETE'])
def delete_technology_group_api(group_id):
    conn = None
    try:
        conn = get_db_connection(DATABASE_PATH)
        cursor = conn.cursor()

        # Check if group exists
        cursor.execute("SELECT id FROM technology_groups WHERE id = ?", (group_id,))
        if not cursor.fetchone():
            return jsonify({"message": f"Technology group ID {group_id} not found."}), 404

        # Optional: Check if any technologies are using this group
        cursor.execute("SELECT COUNT(*) FROM technologies WHERE group_id = ?", (group_id,))
        if cursor.fetchone()[0] > 0:
            # Decide on behavior: disallow deletion, or nullify group_id in technologies
            # For now, let's disallow if in use, or you can change to set group_id = NULL
            return jsonify({"message": f"Technology group ID {group_id} is in use and cannot be deleted."}), 400
            # To nullify instead:
            # cursor.execute("UPDATE technologies SET group_id = NULL WHERE group_id = ?", (group_id,))
            # conn.commit()

        cursor.execute("DELETE FROM technology_groups WHERE id = ?", (group_id,))
        conn.commit()

        if cursor.rowcount > 0:
            return jsonify({"message": f"Technology group ID {group_id} deleted."}), 200
        else:
            # This case should ideally be caught by the initial check
            return jsonify({"message": f"Technology group ID {group_id} not found or already deleted."}), 404
    except Exception as e:
        if conn: conn.rollback()
        app.logger.error(f"Error deleting technology group {group_id}: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn: conn.close()

@app.route('/api/specialities', methods=['GET'])
def get_specialities_api():
    conn = None
    try:
        conn = get_db_connection(DATABASE_PATH)
        specialities = get_all_specialities(conn)
        return jsonify(specialities)
    except Exception as e:
        app.logger.error(f"Error fetching specialities: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn: conn.close()

@app.route('/api/specialities', methods=['POST'])
def add_speciality_api():
    conn = None
    speciality_name = None  # Initialize speciality_name
    try:
        data = request.get_json()
        speciality_name = data.get('name', '').strip()
        if not speciality_name:
            return jsonify({"message": "Speciality name is required."}), 400

        conn = get_db_connection(DATABASE_PATH)
        speciality_id = get_or_create_speciality(conn, speciality_name)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM specialities WHERE id = ?", (speciality_id,))
        speciality = cursor.fetchone()
        return jsonify(dict(speciality)), 201
    except sqlite3.IntegrityError:
        if conn: conn.rollback()
        return jsonify({"message": f"Speciality '{speciality_name}' already exists."}), 409
    except Exception as e:
        if conn: conn.rollback()
        app.logger.error(f"Error adding speciality: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn: conn.close()

@app.route('/api/specialities/<int:speciality_id>', methods=['PUT'])
def update_speciality_api(speciality_id):
    conn = None
    try:
        data = request.get_json()
        new_name = data.get('name', '').strip()
        if not new_name:
            return jsonify({"message": "New name for speciality is required."}), 400

        conn = get_db_connection(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM specialities WHERE id = ?", (speciality_id,))
        if not cursor.fetchone():
            return jsonify({"message": f"Speciality ID {speciality_id} not found."}), 404

        cursor.execute("SELECT id FROM specialities WHERE name = ? AND id != ?", (new_name, speciality_id))
        if cursor.fetchone():
            return jsonify({"message": f"Speciality name \'{new_name}\' already exists."}), 409

        cursor.execute("UPDATE specialities SET name = ? WHERE id = ?", (new_name, speciality_id))
        conn.commit()

        cursor.execute("SELECT id, name FROM specialities WHERE id = ?", (speciality_id,))
        updated_speciality = cursor.fetchone()
        return jsonify(dict(updated_speciality)), 200
    except sqlite3.IntegrityError:
        if conn: conn.rollback()
        # This case might be redundant due to the explicit name check above, but good for safety
        return jsonify({"message": f"Speciality name \'{new_name}\' already exists."}), 409
    except Exception as e:
        if conn: conn.rollback()
        app.logger.error(f"Error updating speciality {speciality_id}: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn: conn.close()

@app.route('/api/specialities/<int:speciality_id>', methods=['DELETE'])
def delete_speciality_api(speciality_id):
    conn = None
    try:
        conn = get_db_connection(DATABASE_PATH)
        cursor = conn.cursor()

        # Check if speciality exists
        cursor.execute("SELECT id FROM specialities WHERE id = ?", (speciality_id,))
        if not cursor.fetchone():
            return jsonify({"message": f"Speciality ID {speciality_id} not found."}), 404

        # Remove associations from technician_specialities
        cursor.execute("DELETE FROM technician_specialities WHERE speciality_id = ?", (speciality_id,))
        conn.commit() # Commit this change first

        # Delete the speciality itself
        cursor.execute("DELETE FROM specialities WHERE id = ?", (speciality_id,))
        conn.commit()

        if cursor.rowcount > 0:
            return jsonify({"message": f"Speciality ID {speciality_id} and its assignments deleted."}), 200
        else:
            # This case should ideally be caught by the initial check if the speciality didn't exist
            return jsonify({"message": f"Speciality ID {speciality_id} not found or already deleted."}), 404
    except Exception as e:
        if conn: conn.rollback()
        app.logger.error(f"Error deleting speciality {speciality_id}: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn: conn.close()

@app.route('/api/technicians/<int:technician_id>/specialities', methods=['GET'])
def get_technician_specialities_api(technician_id):
    conn = None
    try:
        conn = get_db_connection(DATABASE_PATH)
        specialities = get_technician_specialities(conn, technician_id)
        return jsonify(specialities)
    except Exception as e:
        app.logger.error(f"Error fetching specialities for technician {technician_id}: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn: conn.close()

@app.route('/api/technicians/<int:technician_id>/specialities', methods=['POST'])
def add_technician_speciality_api(technician_id):
    conn = None
    try:
        data = request.get_json()
        speciality_id = data.get('speciality_id')
        if speciality_id is None:
            return jsonify({"message": "speciality_id is required."}), 400
        speciality_id = int(speciality_id)

        conn = get_db_connection(DATABASE_PATH)
        add_speciality_to_technician(conn, technician_id, speciality_id)
        return jsonify({"message": f"Speciality {speciality_id} added to technician {technician_id}."}), 201
    except ValueError:
        return jsonify({"message": "Invalid speciality_id format."}), 400
    except sqlite3.IntegrityError:
        if conn: conn.rollback()
        return jsonify({"message": "Failed to add speciality. Ensure IDs exist and it's not a duplicate."}), 400
    except Exception as e:
        if conn: conn.rollback()
        app.logger.error(f"Error adding speciality to technician: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn: conn.close()

@app.route('/api/technicians/<int:technician_id>/specialities/<int:speciality_id>', methods=['DELETE'])
def remove_technician_speciality_api(technician_id, speciality_id):
    conn = None
    try:
        conn = get_db_connection(DATABASE_PATH)
        remove_speciality_from_technician(conn, technician_id, speciality_id)
        return jsonify({"message": f"Speciality {speciality_id} removed from technician {technician_id}."}), 200
    except Exception as e:
        if conn: conn.rollback()
        app.logger.error(f"Error removing speciality from technician: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn: conn.close()

@app.route('/api/technician_skills/<int:technician_id>', methods=['GET'])
def get_technician_skills_api(technician_id):
    conn = None
    try:
        conn = get_db_connection(DATABASE_PATH)
        skills = get_technician_skills_by_id(conn, technician_id)
        return jsonify({"technician_id": technician_id, "skills": skills})
    except Exception as e:
        app.logger.error(f"Error fetching skills for technician {technician_id}: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn: conn.close()

@app.route('/api/technician_skill', methods=['POST'])
def update_technician_skill_api():
    conn = None
    try:
        data = request.get_json()
        technician_id = data.get('technician_id')
        technology_id = data.get('technology_id')
        skill_level = data.get('skill_level')

        if technician_id is None or technology_id is None or skill_level is None:
            return jsonify({"message": "Missing required fields."}), 400

        skill_level = int(skill_level)
        if not (0 <= skill_level <= 4):
            raise ValueError("Skill level must be between 0 and 4.")

        conn = get_db_connection(DATABASE_PATH)
        update_technician_skill(conn, technician_id, technology_id, skill_level)
        return jsonify({"message": "Technician skill updated.", "technician_id": technician_id, "technology_id": technology_id, "skill_level": skill_level}), 200
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 400
    except sqlite3.IntegrityError:
        if conn: conn.rollback()
        return jsonify({"message": "Database integrity error. Check IDs."}), 400
    except Exception as e:
        if conn: conn.rollback()
        app.logger.error(f"Error updating skill: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn: conn.close()

@app.route('/api/tasks_for_mapping', methods=['GET'])
def get_tasks_for_mapping_api():
    conn = None
    try:
        conn = get_db_connection(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT t.id, t.name, t.technology_id, tech.name as technology_name FROM tasks t LEFT JOIN technologies tech ON t.technology_id = tech.id ORDER BY t.name")
        tasks = [{"id": row['id'], "name": row['name'], "technology_id": row['technology_id'], "technology_name": row['technology_name']} for row in cursor.fetchall()]
        return jsonify(tasks)
    except Exception as e:
        app.logger.error(f"Error fetching tasks for mapping: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn: conn.close()

@app.route('/api/tasks/<int:task_id>/technology', methods=['PUT'])
def update_task_technology_api(task_id):
    conn = None
    try:
        data = request.get_json()
        technology_id = data.get('technology_id')
        if technology_id is not None:
            technology_id = int(technology_id)

        conn = get_db_connection(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
        if not cursor.fetchone():
            return jsonify({"message": f"Task ID {task_id} not found."}), 404
        if technology_id is not None:
            cursor.execute("SELECT id FROM technologies WHERE id = ?", (technology_id,))
            if not cursor.fetchone():
                return jsonify({"message": f"Technology ID {technology_id} not found."}), 404

        cursor.execute("UPDATE tasks SET technology_id = ? WHERE id = ?", (technology_id, task_id))
        conn.commit()
        return jsonify({"message": f"Task {task_id} technology mapping updated."}), 200
    except ValueError:
        return jsonify({"message": "Invalid technology_id format."}), 400
    except Exception as e:
        if conn: conn.rollback()
        app.logger.error(f"Error updating task technology for task {task_id}: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    finally:
        if conn: conn.close()

@app.route('/upload', methods=['POST'])
def upload_file_route():
    session_id = request.form.get('session_id')
    if not session_id:
        return jsonify({"message": "Session ID is missing."}), 400

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

            session_excel_data_cache[session_id] = excel_data_list_with_ids

            sanitized_data_for_pm_ui = sanitize_data(excel_data_list, app.logger)
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
            app.logger.error(f"Error during initial file upload: {e}", exc_info=True)
            return jsonify({"message": f"Error processing file: {str(e)}"}), 500

    elif 'absentTechnicians' in request.form:
        if session_id not in session_excel_data_cache:
            return jsonify({"message": "Session expired. Re-upload."}), 400

        excel_data_list_cached = session_excel_data_cache[session_id]
        try:
            absent_technicians = json.loads(request.form.get('absentTechnicians', '[]'))
            all_technicians_flat = [tech for group in TECHNICIAN_GROUPS.values() for tech in group]
            present_technicians = [tech for tech in all_technicians_flat if tech not in absent_technicians]

            total_work_minutes = calculate_work_time(get_current_day())
            sanitized_data = sanitize_data(excel_data_list_cached, app.logger)

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
                "message": "REP task data prepared.", "repTasks": rep_tasks_for_ui,
                "eligibleTechnicians": eligible_technicians_for_rep_modal, "session_id": session_id
            })
        except Exception as e:
            app.logger.error(f"Error processing absent technicians: {e}", exc_info=True)
            return jsonify({"message": f"Error processing absent technicians: {str(e)}"}), 500
    return jsonify({"message": "Invalid request."}), 400

@app.route('/generate_dashboard', methods=['POST'])
def generate_dashboard_route():
    try:
        form_data = request.form
        session_id = form_data.get('session_id')
        if not session_id or session_id not in session_excel_data_cache:
            return jsonify({"message": "Invalid session. Re-upload Excel."}), 400

        excel_data_from_cache = session_excel_data_cache[session_id]
        present_technicians = json.loads(form_data.get('present_technicians', '[]'))
        rep_assignments_from_ui = json.loads(form_data.get('rep_assignments', '[]'))
        all_processed_tasks_from_ui = json.loads(form_data.get('all_processed_tasks', '[]'))

        conn = get_db_connection(DATABASE_PATH)
        try:
            technician_skills_map = get_all_technician_skills_by_name(conn)
            final_tasks_map = {}
            default_technology_id = get_or_create_technology(conn, "Default Technology")

            for task_from_ui in all_processed_tasks_from_ui:
                task_id_ui = str(task_from_ui.get('id'))
                if not task_id_ui: continue
                task_to_add = task_from_ui.copy()
                task_name = task_to_add.get('name', task_to_add.get('scheduler_group_task', f'Unknown Task UI {task_id_ui}'))
                if not task_to_add.get('name'): task_to_add['name'] = task_name
                db_task_id = get_or_create_task(conn, task_name, default_technology_id)
                task_to_add.update({'technology_id': default_technology_id, 'db_task_id': db_task_id})
                final_tasks_map[task_id_ui] = task_to_add

            for task_from_cache in excel_data_from_cache:
                cache_task_id_ui = str(task_from_cache.get('id'))
                if not cache_task_id_ui or cache_task_id_ui in final_tasks_map: continue
                if task_from_cache.get('task_type', '').upper() == 'PM':
                    task_to_add = task_from_cache.copy()
                    task_name = task_to_add.get('name', task_to_add.get('scheduler_group_task', f'Unknown Cache PM {cache_task_id_ui}'))
                    if not task_to_add.get('name'): task_to_add['name'] = task_name
                    task_to_add['isAdditionalTask'] = False
                    db_task_id = get_or_create_task(conn, task_name, default_technology_id)
                    task_to_add.update({'technology_id': default_technology_id, 'db_task_id': db_task_id})
                    final_tasks_map[cache_task_id_ui] = task_to_add
            conn.commit()
        finally:
            if conn: conn.close()

        all_tasks_for_dashboard = list(final_tasks_map.values())
        available_time_result = generate_html_files(
            all_tasks_for_dashboard, present_technicians, rep_assignments_from_ui,
            env, OUTPUT_FOLDER_ABS, TECHNICIANS, TECHNICIAN_GROUPS, app.logger, technician_skills_map
        )
        dashboard_url = url_for('output_file_route', filename='technician_dashboard.html', _external=True) + f'?cache_bust={random.randint(1,100000)}'
        return jsonify({
            "message": "Dashboard generated.", "html_files": available_time_result.get('html_files', []),
            "session_id": session_id, "dashboard_url": dashboard_url
        })
    except Exception as e:
        app.logger.error(f"Error in generate_dashboard_route: {e}", exc_info=True)
        return jsonify({"message": f"Error generating dashboard: {str(e)}"}), 500

# Note: The explicit /css/ and /js/ routes are removed because Flask's static_folder setting handles /static/*
# HTML files should be updated to link to /static/css/file.css and /static/js/file.js
