from flask import Blueprint, g, request, jsonify, current_app
from ..services.db_utils import (
    TechnologyManager,
    TaskManager,
    update_technician_skill,
    get_technician_skills_by_id,
    get_or_create_satellite_point,
    update_satellite_point,
    delete_satellite_point,
    add_line,
    get_all_lines,
    update_line,
    delete_line
)
from ..services.config_manager import load_app_config, TECHNICIAN_GROUPS
import sqlite3

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/technicians', methods=['GET'])
def get_technicians_route():
    try:
        if TECHNICIAN_GROUPS is not None and isinstance(TECHNICIAN_GROUPS, dict) and TECHNICIAN_GROUPS:
            return jsonify(TECHNICIAN_GROUPS), 200
        elif TECHNICIAN_GROUPS is None:
            current_app.logger.warning("/technicians route: TECHNICIAN_GROUPS is None. Returning empty JSON with 200.")
            return jsonify({}), 200 # Explicitly handle None
        else: # Covers empty dict or other unexpected states
            current_app.logger.info(f"/technicians route: TECHNICIAN_GROUPS is empty or not a populated dict (type: {type(TECHNICIAN_GROUPS)}). Value: {TECHNICIAN_GROUPS}. Returning empty JSON with 200.")
            return jsonify({}), 200
    except Exception as e:
        current_app.logger.error(f"Error in /technicians route: {e}", exc_info=True)
        return jsonify({"error": "Failed to retrieve technician groups due to an internal error."}), 500

@api_bp.route('/get_technician_mappings', methods=['GET'])
def get_technician_mappings_api():
    cursor = g.db.cursor()
    technicians_output = {}
    try:
        # Get all technology details to identify parents
        cursor.execute("SELECT id, name, parent_id FROM technologies")
        all_technologies_list = cursor.fetchall()
        # Create a set of IDs for technologies that are parents
        parent_technology_ids = {tech['parent_id'] for tech in all_technologies_list if tech['parent_id'] is not None}

        # Get all tasks and their required skills first
        cursor.execute("""
            SELECT t.id as task_id, t.name as task_name, 
                   GROUP_CONCAT(trs.technology_id) as required_skill_ids, 
                   GROUP_CONCAT(tech.name) as required_skill_names 
            FROM tasks t 
            LEFT JOIN task_required_skills trs ON t.id = trs.task_id 
            LEFT JOIN technologies tech ON trs.technology_id = tech.id 
            GROUP BY t.id, t.name 
            ORDER BY t.name
        """)
        all_tasks_raw = cursor.fetchall()

        all_tasks_with_parsed_skills = []
        for task_row in all_tasks_raw:
            required_skills_list = []
            if task_row['required_skill_ids']:
                ids = str(task_row['required_skill_ids']).split(',')
                names = str(task_row['required_skill_names']).split(',')
                for i, skill_id_str in enumerate(ids):
                    try:
                        skill_id = int(skill_id_str)
                        skill_name = names[i] if i < len(names) else "Unknown Skill"
                        required_skills_list.append({'id': skill_id, 'name': skill_name})
                    except ValueError:
                        current_app.logger.warning(f"Invalid skill_id '{skill_id_str}' for task {task_row['task_name']}")
            all_tasks_with_parsed_skills.append({
                'task_id': task_row['task_id'],
                'task_name': task_row['task_name'],
                'required_skills_list': required_skills_list
            })

        cursor.execute("""
            SELECT t.id, t.name, t.satellite_point_id, sp.name as satellite_point_name
            FROM technicians t
            LEFT JOIN satellite_points sp ON t.satellite_point_id = sp.id
            ORDER BY t.name
        """)
        db_technicians = cursor.fetchall()

        for tech_row in db_technicians:
            tech_id = tech_row['id']
            tech_name = tech_row['name']

            tech_data = {
                "id": tech_id,
                "satellite_point_id": tech_row['satellite_point_id'],
                "satellite_point_name": tech_row['satellite_point_name'],
                "skill_matched_tasks": {
                    "full_match": [],
                    "partial_match": []
                },
                "explicitly_assigned_tasks": []
            }

            cursor.execute("SELECT technology_id, skill_level FROM technician_technology_skills WHERE technician_id = ?", (tech_id,))
            tech_skills = {row['technology_id']: row['skill_level'] for row in cursor.fetchall()}

            for task_info in all_tasks_with_parsed_skills:
                task_id = task_info['task_id']
                task_name = task_info['task_name']

                display_required_skills_info = []
                matchable_required_skills = []

                for req_skill in task_info['required_skills_list']:
                    skill_id = req_skill['id']
                    skill_name = req_skill['name']
                    is_parent = skill_id in parent_technology_ids
                    possessed = skill_id in tech_skills and tech_skills[skill_id] > 0
                    level = tech_skills.get(skill_id) if possessed else None

                    skill_detail_for_display = {
                        'skill_id': skill_id,
                        'skill_name': skill_name,
                        'possessed': possessed if not is_parent else False, # Parent skills are not "possessed" for matching
                        'level': level if not is_parent else None,
                        'is_parent': is_parent,
                        'status_note': 'Parent Skill (not directly assignable)' if is_parent else None
                    }
                    display_required_skills_info.append(skill_detail_for_display)

                    if not is_parent:
                        matchable_required_skills.append(req_skill)

                if not matchable_required_skills: # If task only has parent skills or no skills for matching
                    continue

                num_required_matchable = len(matchable_required_skills)
                num_possessed_matchable = 0
                highest_possessed_level_for_task = 0

                for m_skill in matchable_required_skills:
                    m_skill_id = m_skill['id']
                    if m_skill_id in tech_skills and tech_skills[m_skill_id] > 0:
                        num_possessed_matchable += 1
                        current_level = tech_skills[m_skill_id]
                        if current_level > highest_possessed_level_for_task:
                            highest_possessed_level_for_task = current_level

                if num_possessed_matchable == 0: # Technician possesses none of the *matchable* skills
                    continue

                is_full_match = (num_possessed_matchable == num_required_matchable)
                missing_skill_count = num_required_matchable - num_possessed_matchable

                task_display_data = {
                    'task_id': task_id,
                    'task_name': task_name,
                    'all_required_skills_info': display_required_skills_info, # Use the comprehensive list for display
                    'highest_possessed_skill_level': highest_possessed_level_for_task,
                    'missing_skill_count': missing_skill_count # Based on matchable skills
                }

                if is_full_match:
                    tech_data["skill_matched_tasks"]["full_match"].append(task_display_data)
                else: # Partial match (num_possessed_matchable > 0 but < num_required_matchable)
                    tech_data["skill_matched_tasks"]["partial_match"].append(task_display_data)

            tech_data["skill_matched_tasks"]["full_match"].sort(key=lambda x: -x['highest_possessed_skill_level'])
            tech_data["skill_matched_tasks"]["partial_match"].sort(key=lambda x: (-x['highest_possessed_skill_level'], x['missing_skill_count']))

            cursor.execute("SELECT t.id as task_id, t.name as task_name FROM technician_task_assignments tta JOIN tasks t ON tta.task_id = t.id WHERE tta.technician_id = ? ORDER BY t.name", (tech_id,))
            for assign_row in cursor.fetchall():
                tech_data["explicitly_assigned_tasks"].append({
                    'task_id': assign_row['task_id'],
                    'task_name': assign_row['task_name']
                })
            technicians_output[tech_name] = tech_data
        return jsonify({"technicians": technicians_output})
    except sqlite3.Error as e:
        current_app.logger.error(f"SQLite error in get_technician_mappings_api: {e}")
        return jsonify({"error": f"Database error: {e}"}), 500

@api_bp.route('/save_technician_mappings', methods=['POST'])
def save_technician_mappings_api():
    try:
        cursor = g.db.cursor()
        updated_data = request.get_json()
        if not updated_data or 'technicians' not in updated_data:
            return jsonify({"message": "Invalid data format"}), 400

        technicians_from_payload = updated_data.get('technicians', {})
        for tech_name, tech_payload_data in technicians_from_payload.items():
            satellite_point_id = tech_payload_data.get('satellite_point_id') # Changed from sattelite_point

            # Ensure task_assignments remains an empty array as per instructions
            task_assignments_payload = [] # Kept as empty array

            cursor.execute("SELECT id FROM technicians WHERE name = ?", (tech_name,))
            tech_row = cursor.fetchone()
            technician_id = None
            if tech_row:
                technician_id = tech_row['id']
                # Updated to use satellite_point_id and remove lines
                cursor.execute("UPDATE technicians SET satellite_point_id = ? WHERE id = ?", (satellite_point_id, technician_id))
                cursor.execute("DELETE FROM technician_task_assignments WHERE technician_id = ?", (technician_id,))
            else:
                # Updated to use satellite_point_id and remove lines
                cursor.execute("INSERT INTO technicians (name, satellite_point_id) VALUES (?, ?)", (tech_name, satellite_point_id))
                technician_id = cursor.lastrowid

            # Task assignment logic remains, but based on an empty task_assignments_payload, no assignments will be made here.
            for assignment in task_assignments_payload:
                task_name_assign = assignment.get('task')
                if task_name_assign:
                    cursor.execute("SELECT id FROM tasks WHERE name = ?", (task_name_assign,))
                    task_db_row = cursor.fetchone()
                    if task_db_row:
                        task_id_assign = task_db_row['id']
                        cursor.execute("INSERT INTO technician_task_assignments (technician_id, task_id) VALUES (?, ?)",
                                       (technician_id, task_id_assign))
                    else:
                        current_app.logger.warning(f"Task '{task_name_assign}' not found. Cannot save assignment for '{tech_name}'.")
        g.db.commit()
        load_app_config(current_app.config['DATABASE_PATH'], current_app.logger) # Reload config globals
        return jsonify({"message": "Technician mappings saved and reloaded."})
    except sqlite3.Error as e:
        g.db.rollback()
        current_app.logger.error(f"SQLite error saving technician mappings: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    except Exception as e:
        g.db.rollback()
        current_app.logger.error(f"Error saving technician mappings: {e}", exc_info=True)
        return jsonify({"message": f"Error saving mappings: {str(e)}"}), 500

@api_bp.route('/technicians', methods=['POST'])
def add_technician_api():
    name_from_payload = None  # Initialize for use in error logging
    try:
        data = request.get_json()
        name_from_payload = data.get('name', '').strip()

        # Explicitly get satellite_point_id, default to None if not provided or empty string.
        # Client should send null or an integer for satellite_point_id.
        satellite_point_id_from_payload = data.get('satellite_point_id', None)
        if isinstance(satellite_point_id_from_payload, str) and not satellite_point_id_from_payload:
            satellite_point_id_from_payload = None
        elif satellite_point_id_from_payload is not None:
            try:
                satellite_point_id_from_payload = int(satellite_point_id_from_payload)
            except ValueError:
                current_app.logger.warning(f"Invalid satellite_point_id format received: {data.get('satellite_point_id')}. Setting to None.")
                satellite_point_id_from_payload = None

        if not name_from_payload:
            return jsonify({"message": "Technician name is required."}), 400

        cursor = g.db.cursor()

        # Check if technician already exists
        cursor.execute("SELECT id FROM technicians WHERE name = ?", (name_from_payload,))
        if cursor.fetchone():
            return jsonify({"message": f"Technician '{name_from_payload}' already exists."}), 409

        current_app.logger.info(f"Attempting to insert technician: Name='{name_from_payload}', SatellitePointID='{satellite_point_id_from_payload}'")

        # Use satellite_point_id in INSERT.
        # This SQL query is critical and must not contain 'group_id'.
        sql_insert = "INSERT INTO technicians (name, satellite_point_id) VALUES (?, ?)"
        cursor.execute(sql_insert, (name_from_payload, satellite_point_id_from_payload))
        g.db.commit()
        technician_id = cursor.lastrowid
        current_app.logger.info(f"Technician inserted with ID: {technician_id}")

        # Fetch the newly created technician, ensuring satellite_point_id is selected.
        # This SQL query is also critical.
        sql_select = "SELECT id, name, satellite_point_id FROM technicians WHERE id = ?"
        cursor.execute(sql_select, (technician_id,))
        new_technician_row = cursor.fetchone()

        # Call load_app_config AFTER successful DB operations and BEFORE sending response
        # to ensure the global config is up-to-date.
        try:
            load_app_config(current_app.config['DATABASE_PATH'], current_app.logger)
        except Exception as e_config_load:
            current_app.logger.error(f"Error reloading app config after adding technician: {e_config_load}", exc_info=True)
            # Decide if this should be a critical error response or just a warning.
            # For now, proceed with technician addition success message.

        if new_technician_row:
            return jsonify({"message": f"Technician '{name_from_payload}' added successfully.", "technician": dict(new_technician_row)}), 201
        else:
            # This case should ideally not be reached if insert and lastrowid worked
            current_app.logger.error(f"Technician '{name_from_payload}' was added (ID: {technician_id}) but could not be retrieved immediately after insert.")
            return jsonify({"message": "Technician added but failed to retrieve details post-insertion."}), 500

    except sqlite3.IntegrityError as ie:
        if g.db: g.db.rollback()
        error_message = f"Technician '{name_from_payload or 'Unknown'}' already exists or another integrity constraint failed. Details: {str(ie)}"
        current_app.logger.error(f"IntegrityError adding technician: {error_message}")
        return jsonify({"message": error_message}), 409
    except sqlite3.Error as e_sqlite: # More specific variable for SQLite errors
        if g.db: g.db.rollback()
        # This is where "no column named group_id" would be caught if it's an SQLite error from THIS function's direct operations
        db_error_message = f"Database error: {str(e_sqlite)}"
        current_app.logger.error(f"SQLite error in add_technician_api for '{name_from_payload or 'Unknown'}': {db_error_message}. SQL operations in this function use 'satellite_point_id'.", exc_info=True)
        return jsonify({"message": db_error_message}), 500
    except Exception as e_general:
        if g.db: g.db.rollback()
        server_error_message = f"Server error: {str(e_general)}"
        current_app.logger.error(f"Generic server error in add_technician_api for '{name_from_payload or 'Unknown'}': {server_error_message}", exc_info=True)
        return jsonify({"message": server_error_message}), 500

@api_bp.route('/technicians/<int:technician_id>', methods=['PUT'])
def update_technician_api(technician_id):
    name = None  # Initialize name to avoid UnboundLocalError
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        satellite_point_id = data.get('satellite_point_id') # Ensure this is satellite_point_id

        # It's better to only update fields that are provided.
        # The following logic will be improved in a subsequent step.
        # For now, the main fix is to use satellite_point_id instead of group_id.

        if not name and satellite_point_id is None: # Check if there is anything to update
            return jsonify({"message": "No data provided for update."}), 400

        cursor = g.db.cursor()

        cursor.execute("SELECT id FROM technicians WHERE id = ?", (technician_id,))
        if not cursor.fetchone():
            return jsonify({"message": "Technician not found."}), 404

        if name: # Check for name conflict only if name is being updated
            cursor.execute("SELECT id FROM technicians WHERE name = ? AND id != ?", (name, technician_id))
            if cursor.fetchone():
                return jsonify({"message": f"Another technician with the name '{name}' already exists."}), 409

        # Use satellite_point_id in UPDATE
        # This will be improved to dynamically build the SET clause.
        # For now, if name is empty, it might cause issues if name is NOT NULL.
        # Assuming name is always provided if satellite_point_id is, or handled by client.
        # The primary fix here is replacing group_id with satellite_point_id.
        if name and satellite_point_id is not None:
            cursor.execute("UPDATE technicians SET name = ?, satellite_point_id = ? WHERE id = ?", (name, satellite_point_id, technician_id))
        elif name:
            cursor.execute("UPDATE technicians SET name = ? WHERE id = ?", (name, technician_id))
        elif satellite_point_id is not None:
            cursor.execute("UPDATE technicians SET satellite_point_id = ? WHERE id = ?", (satellite_point_id, technician_id))
        else:
            # This case should be caught by "No data provided for update" if both are None,
            # but as a fallback, do nothing if only one is None and it's the only one provided.
            # Or, more simply, the initial check for `name` in the payload for `handleEditTechnicianName` means `name` will be present.
            # The JS for `handleEditTechnicianName` only sends `name`.
            # The JS for `handleTechSatellitePointChange` sends `satellite_point_id`.
            # So, this simple if/elif should cover current frontend behavior.
            pass # No actual update query if only one field was expected but not provided (e.g. name was empty string)

        g.db.commit()

        # Fetch satellite_point_id in SELECT
        cursor.execute("SELECT id, name, satellite_point_id FROM technicians WHERE id = ?", (technician_id,))
        updated_technician = cursor.fetchone()

        load_app_config(current_app.config['DATABASE_PATH'], current_app.logger) # Reload config globals
        # Ensure the message reflects what was actually updated if possible, or a generic success.
        return jsonify({"message": f"Technician ID {technician_id} updated successfully.", "technician": dict(updated_technician)}), 200

    except sqlite3.IntegrityError:
        if g.db: g.db.rollback()
        # This specific error for name uniqueness is caught above, but this is a general fallback.
        return jsonify({"message": f"Technician name '{name}' may already exist for another technician or other integrity issue."}), 409
    except sqlite3.Error as e:
        if g.db: g.db.rollback()
        current_app.logger.error(f"Database error updating technician {technician_id}: {e}")
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    except Exception as e:
        if g.db: g.db.rollback()
        current_app.logger.error(f"Server error updating technician {technician_id}: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@api_bp.route('/technicians/<int:technician_id>', methods=['DELETE'])
def delete_technician_api(technician_id):
    try:
        cursor = g.db.cursor()

        # Check if technician exists
        cursor.execute("SELECT name FROM technicians WHERE id = ?", (technician_id,))
        technician = cursor.fetchone()
        if not technician:
            return jsonify({"message": "Technician not found."}), 404

        technician_name = technician['name']

        # Delete related data first (adjust table and column names as per your schema)
        # Example: technician_technology_skills, technician_task_assignments
        cursor.execute("DELETE FROM technician_technology_skills WHERE technician_id = ?", (technician_id,))
        cursor.execute("DELETE FROM technician_task_assignments WHERE technician_id = ?", (technician_id,))
        # Add other related data deletions here if necessary

        # Delete the technician
        cursor.execute("DELETE FROM technicians WHERE id = ?", (technician_id,))
        g.db.commit()

        if cursor.rowcount > 0:
            load_app_config(current_app.config['DATABASE_PATH'], current_app.logger) # Reload config globals
            return jsonify({"message": f"Technician '{technician_name}' (ID: {technician_id}) and related data deleted successfully."}), 200
        else:
            # Should be caught by the initial check, but as a safeguard
            return jsonify({"message": "Technician found but could not be deleted."}), 500

    except sqlite3.Error as e:
        if g.db: g.db.rollback()
        current_app.logger.error(f"Database error deleting technician {technician_id}: {e}", exc_info=True)
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    except Exception as e:
        if g.db: g.db.rollback()
        current_app.logger.error(f"Server error deleting technician {technician_id}: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@api_bp.route('/technologies', methods=['GET'])
def get_technologies_api():
    try:
        cursor = g.db.cursor()
        cursor.execute("SELECT t.id, t.name, t.group_id, t.parent_id, tg.name as group_name FROM technologies t LEFT JOIN technology_groups tg ON t.group_id = tg.id ORDER BY tg.name, t.name")
        technologies = [{"id": row['id'], "name": row['name'], "group_id": row['group_id'], "group_name": row['group_name'], "parent_id": row['parent_id']} for row in cursor.fetchall()]
        return jsonify(technologies)
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error in get_technologies_api: {e}")
        return jsonify({"error": f"Database error: {e}"}), 500

@api_bp.route('/lines', methods=['GET', 'POST']) # Added 'POST'
def get_lines_api():
    try:
        cursor = g.db.cursor()
        if request.method == 'POST':
            data = request.get_json()
            name = data.get('name')
            satellite_point_id = data.get('satellite_point_id')
            if not name or satellite_point_id is None:
                return jsonify({"message": "Line name and satellite_point_id are required"}), 400
            try:
                # Ensure satellite_point_id is an integer
                satellite_point_id = int(satellite_point_id)
                # Check if satellite point exists
                cursor.execute("SELECT id FROM satellite_points WHERE id = ?", (satellite_point_id,))
                if not cursor.fetchone():
                    return jsonify({"message": f"Satellite point ID {satellite_point_id} not found."}), 400

                line_id = add_line(g.db, name, satellite_point_id)
                # Fetch the created line to return its details
                cursor.execute("SELECT id, name, satellite_point_id FROM lines WHERE id = ?", (line_id,))
                line = cursor.fetchone()
                return jsonify(dict(line)), 201
            except ValueError: # Catches if int(satellite_point_id) fails
                return jsonify({"message": "Invalid satellite_point_id format. Must be an integer."}), 400
            except sqlite3.IntegrityError:
                 return jsonify({"message": f"Line with name '{name}' may already exist for the given satellite point or other integrity issue."}), 409
            except Exception as e:
                current_app.logger.error(f"Error creating line: {e}", exc_info=True)
                return jsonify({"message": f"Server error: {str(e)}"}), 500

        # GET request part
        lines = get_all_lines(g.db)
        return jsonify(lines)
    except Exception as e:
        current_app.logger.error(f"Error in /api/lines: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@api_bp.route('/lines/<int:line_id>', methods=['PUT', 'DELETE'])
def manage_line_item_api(line_id):
    try:
        cursor = g.db.cursor()
        if request.method == 'PUT':
            data = request.get_json()
            name = data.get('name')
            satellite_point_id = data.get('satellite_point_id')
            if not name or satellite_point_id is None:
                return jsonify({"message": "Name and satellite_point_id are required for update"}), 400
            try:
                satellite_point_id = int(satellite_point_id)
                # Check if satellite point exists
                cursor.execute("SELECT id FROM satellite_points WHERE id = ?", (satellite_point_id,))
                if not cursor.fetchone():
                    return jsonify({"message": f"Satellite point ID {satellite_point_id} not found."}), 400

                updated_line_data = update_line(g.db, line_id, name, satellite_point_id)
                if updated_line_data:
                    return jsonify(updated_line_data), 200
                else:
                    return jsonify({"message": "Line not found"}), 404
            except ValueError: # Catches if int(satellite_point_id) fails
                return jsonify({"message": "Invalid satellite_point_id format. Must be an integer."}), 400
            except sqlite3.IntegrityError:
                 return jsonify({"message": f"Line with name '{name}' may already exist for the given satellite point or other integrity issue."}), 409
            except Exception as e:
                current_app.logger.error(f"Error updating line {line_id}: {e}", exc_info=True)
                return jsonify({"message": f"Server error: {str(e)}"}), 500

        elif request.method == 'DELETE':
            try:
                success = delete_line(g.db, line_id)
                if success:
                    return jsonify({"message": "Line deleted successfully"}), 200
                else:
                    return jsonify({"message": "Line not found or could not be deleted"}), 404
            except sqlite3.IntegrityError as e: # e.g. if line is referenced by technicians or other entities
                current_app.logger.error(f"Integrity error deleting line {line_id}: {e}", exc_info=True)
                return jsonify({"message": f"Cannot delete line: it is currently in use. Details: {str(e)}"}), 409
            except Exception as e:
                current_app.logger.error(f"Error deleting line {line_id}: {e}", exc_info=True)
                return jsonify({"message": f"Server error: {str(e)}"}), 500
    except Exception as e:
        current_app.logger.error(f"Error in /api/lines/<id>: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@api_bp.route('/satellite_points', methods=['GET', 'POST']) # Added 'POST'
def get_satellite_points_api():
    try:
        cursor = g.db.cursor()
        if request.method == 'POST':
            data = request.get_json()
            name = data.get('name')
            if not name:
                return jsonify({"message": "Satellite point name is required"}), 400
            try:
                point_id = get_or_create_satellite_point(g.db, name)
                # Fetch the created/existing point to return its details
                cursor.execute("SELECT id, name FROM satellite_points WHERE id = ?", (point_id,))
                point = cursor.fetchone()
                return jsonify(dict(point)), 201 # Return the created or existing point
            except sqlite3.IntegrityError: # Should be caught by get_or_create if it tries to insert duplicate
                return jsonify({"message": f"Satellite point '{name}' may already exist or another integrity issue."}), 409
            except Exception as e:
                current_app.logger.error(f"Error creating satellite point: {e}", exc_info=True)
                return jsonify({"message": f"Server error: {str(e)}"}), 500

        # GET request part remains the same
        cursor = g.db.cursor()
        cursor.execute("SELECT id, name FROM satellite_points ORDER BY name")
        satellite_points = [{"id": row['id'], "name": row['name']} for row in cursor.fetchall()]
        return jsonify(satellite_points)
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error fetching satellite points: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    except Exception as e: # Catch other potential errors, e.g., if request.get_json() fails
        current_app.logger.error(f"Error in /api/satellite_points: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@api_bp.route('/satellite_points/<int:point_id>', methods=['PUT', 'DELETE'])
def manage_satellite_point_item_api(point_id):
    try:
        cursor = g.db.cursor()
        if request.method == 'PUT':
            data = request.get_json()
            name = data.get('name')
            if not name:
                return jsonify({"message": "Name is required for update"}), 400
            try:
                updated_point = update_satellite_point(g.db, point_id, name)
                if updated_point:
                    return jsonify(updated_point), 200
                else:
                    return jsonify({"message": "Satellite point not found"}), 404
            except sqlite3.IntegrityError:
                 return jsonify({"message": f"Satellite point with name '{name}' may already exist."}), 409
            except Exception as e:
                current_app.logger.error(f"Error updating satellite point {point_id}: {e}", exc_info=True)
                return jsonify({"message": f"Server error: {str(e)}"}), 500

        elif request.method == 'DELETE':
            try:
                success = delete_satellite_point(g.db, point_id)
                if success:
                    return jsonify({"message": "Satellite point deleted successfully"}), 200
                else:
                    return jsonify({"message": "Satellite point not found or could not be deleted"}), 404
            except sqlite3.IntegrityError as e: # e.g. if point is referenced by technicians
                current_app.logger.error(f"Integrity error deleting satellite point {point_id}: {e}", exc_info=True)
                return jsonify({"message": f"Cannot delete satellite point: it is currently in use. Details: {str(e)}"}), 409
            except Exception as e:
                current_app.logger.error(f"Error deleting satellite point {point_id}: {e}", exc_info=True)
                return jsonify({"message": f"Server error: {str(e)}"}), 500
    except Exception as e:
        current_app.logger.error(f"Error in /api/satellite_points/<id>: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@api_bp.route('/technologies', methods=['POST'])
def add_technology_api():
    tech_name = None  # Initialize tech_name
    parent_id_from_payload = None # Initialize for cleanup logic
    try:
        data = request.get_json()
        tech_name = data.get('name', '').strip()
        if not tech_name:
            return jsonify({"message": "Technology name is required."}), 400

        group_id = data.get('group_id') # Frontend ensures this is sent for new tech
        parent_id_from_payload = data.get('parent_id')

        if group_id is None: # Should ideally not happen if frontend enforces it
             return jsonify({"message": "Technology group ID is required."}), 400

        try:
            group_id = int(group_id)
            if parent_id_from_payload is not None:
                parent_id_from_payload = int(parent_id_from_payload)
        except ValueError:
            return jsonify({"message": "Invalid group_id or parent_id format. Must be integers."}), 400

        cursor = g.db.cursor()
        technology_manager = TechnologyManager(g.db)

        # Check for duplicate: name, group_id, parent_id must be unique together
        query_check_duplicate = "SELECT id FROM technologies WHERE name = ? AND group_id = ?"
        params_check_duplicate = [tech_name, group_id]

        if parent_id_from_payload is None:
            query_check_duplicate += " AND parent_id IS NULL"
        else:
            query_check_duplicate += " AND parent_id = ?"
            params_check_duplicate.append(parent_id_from_payload)

        cursor.execute(query_check_duplicate, tuple(params_check_duplicate))
        if cursor.fetchone():
            return jsonify({"message": f"Technology '{tech_name}' with the same parent under group ID {group_id} already exists."}), 409

        # Use the new manager to create the technology
        created_technology_id = technology_manager.get_or_create(tech_name, group_id, parent_id_from_payload)

        # Cleanup: If the new technology was assigned a parent, that parent technology's skills should be cleared.
        if parent_id_from_payload is not None:
            cursor.execute("DELETE FROM technician_technology_skills WHERE technology_id = ?", (parent_id_from_payload,))
            if cursor.rowcount > 0:
                current_app.logger.info(f"Cleaned skills for technology {parent_id_from_payload} as it's now parent to new tech {created_technology_id}.")
                g.db.commit() # Commit the deletion

        cursor.execute("SELECT t.id, t.name, t.group_id, t.parent_id, tg.name as group_name FROM technologies t LEFT JOIN technology_groups tg ON t.group_id = tg.id WHERE t.id = ?", (created_technology_id,))
        technology = cursor.fetchone()
        return jsonify(dict(technology)), 201
    except ValueError:
        return jsonify({"message": "Invalid group_id or parent_id format."}), 400
    except sqlite3.IntegrityError:
        if g.db: g.db.rollback()
        return jsonify({"message": f"Technology '{tech_name}' already exists or invalid foreign key."}), 409
    except sqlite3.Error as e:
        if g.db: g.db.rollback()
        current_app.logger.error(f"Database error adding technology: {e}")
        return jsonify({"message": f"Database error: {e}"}), 500
    except Exception as e:
        if g.db: g.db.rollback()
        current_app.logger.error(f"Server error adding technology: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@api_bp.route('/technologies/<int:technology_id>', methods=['PUT', 'DELETE'])
def manage_technology_item_api(technology_id):
    new_name = None # Initialize new_name here
    try:
        technology_manager = TechnologyManager(g.db)
        if request.method == 'PUT':
            data = request.get_json()
            new_name = data.get('name', '').strip() # Assigned here
            group_id = data.get('group_id') # Can be None if client allows clearing it
            parent_id_from_payload = data.get('parent_id') # Can be None

            if not new_name:
                return jsonify({"message": "Technology name is required."}), 400

            # Validate and convert IDs if present
            try:
                if group_id is not None: group_id = int(group_id)
                if parent_id_from_payload is not None: parent_id_from_payload = int(parent_id_from_payload)
            except ValueError:
                return jsonify({"message": "Invalid group_id or parent_id format. Must be integers or null."}), 400

            cursor = g.db.cursor()

            cursor.execute("SELECT id FROM technologies WHERE id = ?", (technology_id,))
            if not cursor.fetchone():
                return jsonify({"message": f"Technology ID {technology_id} not found."}), 404

            # Check for duplicate: name, group_id, parent_id must be unique together, excluding current tech_id
            query_parts_check_duplicate = ["SELECT id FROM technologies WHERE name = ? AND id != ?"]
            params_check_duplicate = [new_name, technology_id]

            if group_id is None:
                query_parts_check_duplicate.append("AND group_id IS NULL")
            else:
                query_parts_check_duplicate.append("AND group_id = ?")
                params_check_duplicate.append(group_id)

            if parent_id_from_payload is None:
                query_parts_check_duplicate.append("AND parent_id IS NULL")
            else:
                query_parts_check_duplicate.append("AND parent_id = ?")
                params_check_duplicate.append(parent_id_from_payload)

            final_query_check_duplicate = " ".join(query_parts_check_duplicate)
            cursor.execute(final_query_check_duplicate, tuple(params_check_duplicate))
            if cursor.fetchone():
                return jsonify({"message": f"Another technology with the name '{new_name}', same parent, and same group already exists."}), 409

            # Validate group_id if provided
            if group_id is not None:
                cursor.execute("SELECT id FROM technology_groups WHERE id = ?", (group_id,))
                if not cursor.fetchone():
                    return jsonify({"message": f"Technology group ID {group_id} not found."}), 400

            # Validate parent_id if provided
            if parent_id_from_payload is not None:
                if parent_id_from_payload == technology_id:
                    return jsonify({"message": "Technology cannot be its own parent."}), 400
                cursor.execute("SELECT id FROM technologies WHERE id = ?", (parent_id_from_payload,))
                if not cursor.fetchone():
                    return jsonify({"message": f"Parent technology ID {parent_id_from_payload} not found."}), 400

            cursor.execute("UPDATE technologies SET name = ?, group_id = ?, parent_id = ? WHERE id = ?",
                           (new_name, group_id, parent_id_from_payload, technology_id))
            g.db.commit()

            # --- Start of skill cleanup logic ---
            skills_cleaned_for_new_parent = False
            if parent_id_from_payload is not None:
                cursor.execute("DELETE FROM technician_technology_skills WHERE technology_id = ?", (parent_id_from_payload,))
                if cursor.rowcount > 0:
                    current_app.logger.info(f"Cleaned skills for technology {parent_id_from_payload} as it is parent to {technology_id}.")
                    skills_cleaned_for_new_parent = True

            skills_cleaned_for_edited_tech = False
            cursor.execute("SELECT 1 FROM technologies WHERE parent_id = ? LIMIT 1", (technology_id,))
            if cursor.fetchone() is not None: # True if technology_id has children
                cursor.execute("DELETE FROM technician_technology_skills WHERE technology_id = ?", (technology_id,))
                if cursor.rowcount > 0:
                    current_app.logger.info(f"Cleaned skills for technology {technology_id} as it has children.")
                    skills_cleaned_for_edited_tech = True

            if skills_cleaned_for_new_parent or skills_cleaned_for_edited_tech:
                g.db.commit()
            # --- End of skill cleanup logic ---

            cursor.execute("SELECT t.id, t.name, t.group_id, t.parent_id, tg.name as group_name FROM technologies t LEFT JOIN technology_groups tg ON t.group_id = tg.id WHERE t.id = ?", (technology_id,))
            updated_technology = cursor.fetchone()
            return jsonify(dict(updated_technology)), 200

        elif request.method == 'DELETE':
            cursor = g.db.cursor()

            cursor.execute("SELECT id FROM technologies WHERE id = ?", (technology_id,))
            if not cursor.fetchone():
                return jsonify({"message": f"Technology ID {technology_id} not found."}), 404

            cursor.execute("UPDATE technologies SET parent_id = NULL WHERE parent_id = ?", (technology_id,))
            g.db.commit()

            rows_deleted = technology_manager.delete(technology_id)

            if rows_deleted > 0:
                return jsonify({"message": f"Technology ID {technology_id} deleted. Child references updated."}), 200
            else:
                current_app.logger.warning(f"delete_technology function returned 0 for existing tech_id {technology_id}")
                return jsonify({"message": f"Technology ID {technology_id} found but could not be deleted by the utility function."}), 500

    except ValueError as ve:
        return jsonify({"message": f"Invalid data format: {str(ve)}"}), 400
    except sqlite3.IntegrityError:
        if g.db: g.db.rollback()
        return jsonify({"message": f"Technology group name \'{new_name}\' already exists."}), 409
    except Exception as e:
        if g.db: g.db.rollback()
        current_app.logger.error(f"Error processing technology {technology_id} ({request.method}): {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@api_bp.route('/technology_groups', methods=['GET'])
def get_technology_groups_api():
    try:
        technology_manager = TechnologyManager(g.db)
        groups = technology_manager.get_all_groups()
        return jsonify(groups)
    except Exception as e:
        current_app.logger.error(f"Error fetching technology groups: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@api_bp.route('/technology_groups', methods=['POST'])
def add_technology_group_api():
    group_name = None  # Initialize group_name
    try:
        data = request.get_json()
        group_name = data.get('name', '').strip()
        if not group_name:
            return jsonify({"message": "Technology group name is required."}), 400

        technology_manager = TechnologyManager(g.db)
        group_id = technology_manager.get_or_create_group(group_name)
        cursor = g.db.cursor()
        cursor.execute("SELECT id, name FROM technology_groups WHERE id = ?", (group_id,))
        group = cursor.fetchone()
        return jsonify(dict(group)), 201
    except sqlite3.IntegrityError:
        if g.db: g.db.rollback()
        return jsonify({"message": f"Technology group '{group_name}' already exists."}), 409
    except Exception as e:
        if g.db: g.db.rollback()
        current_app.logger.error(f"Error adding technology group: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@api_bp.route('/technology_groups/<int:group_id>', methods=['PUT'])
def update_technology_group_api(group_id):
    new_name = None # Initialize to avoid UnboundLocalError
    try:
        data = request.get_json()
        new_name = data.get('name', '').strip()
        if not new_name:
            return jsonify({"message": "New name for technology group is required."}), 400

        cursor = g.db.cursor()
        cursor.execute("SELECT id FROM technology_groups WHERE id = ?", (group_id,))
        if not cursor.fetchone():
            return jsonify({"message": f"Technology group ID {group_id} not found."}), 404

        cursor.execute("SELECT id FROM technology_groups WHERE name = ? AND id != ?", (new_name, group_id))
        if cursor.fetchone():
            return jsonify({"message": f"Technology group name \'{new_name}\' already exists."}), 409

        cursor.execute("UPDATE technology_groups SET name = ? WHERE id = ?", (new_name, group_id))
        g.db.commit()

        cursor.execute("SELECT id, name FROM technology_groups WHERE id = ?", (group_id,))
        updated_group = cursor.fetchone()
        return jsonify(dict(updated_group)), 200
    except sqlite3.IntegrityError:
        if g.db: g.db.rollback()
        return jsonify({"message": f"Technology group name \'{new_name}\' already exists."}), 409
    except Exception as e:
        if g.db: g.db.rollback()
        current_app.logger.error(f"Error updating technology group {group_id}: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@api_bp.route('/technology_groups/<int:group_id>', methods=['DELETE'])
def delete_technology_group_api(group_id):
    try:
        cursor = g.db.cursor()

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
            # g.db.commit()

        cursor.execute("DELETE FROM technology_groups WHERE id = ?", (group_id,))
        g.db.commit()

        if cursor.rowcount > 0:
            return jsonify({"message": f"Technology group ID {group_id} deleted."}), 200
        else:
            # This case should ideally be caught by the initial check
            return jsonify({"message": f"Technology group ID {group_id} not found or already deleted."}), 404
    except Exception as e:
        if g.db: g.db.rollback()
        current_app.logger.error(f"Error deleting technology group {group_id}: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@api_bp.route('/technician_skills/<int:technician_id>', methods=['GET'])
def get_technician_skills_api(technician_id):
    try:
        skills = get_technician_skills_by_id(g.db, technician_id)
        return jsonify({"technician_id": technician_id, "skills": skills})
    except Exception as e:
        current_app.logger.error(f"Error fetching skills for technician {technician_id}: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@api_bp.route('/technician_skill', methods=['POST'])
def update_technician_skill_api():
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

        update_technician_skill(g.db, technician_id, technology_id, skill_level)
        return jsonify({"message": "Technician skill updated.", "technician_id": technician_id, "technology_id": technology_id, "skill_level": skill_level}), 200
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 400
    except sqlite3.IntegrityError:
        if g.db: g.db.rollback()
        return jsonify({"message": "Database integrity error. Check IDs."}), 400
    except Exception as e:
        if g.db: g.db.rollback()
        current_app.logger.error(f"Error updating skill: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@api_bp.route('/tasks', methods=['POST'])
def add_task_api():
    try:
        data = request.get_json()
        task_name = data.get('name', '').strip()
        technology_ids = data.get('technology_ids', []) # Expect a list of technology IDs

        if not task_name:
            return jsonify({"message": "Task name is required."}), 400
        if not isinstance(technology_ids, list) or not technology_ids: # Ensure it's a non-empty list
            return jsonify({"message": "At least one Technology ID is required for the task."}), 400

        task_manager = TaskManager(g.db)
        cursor = g.db.cursor()

        # Validate all technology IDs
        for tech_id in technology_ids:
            try:
                tech_id_int = int(tech_id)
                cursor.execute("SELECT id FROM technologies WHERE id = ?", (tech_id_int,))
                if not cursor.fetchone():
                    return jsonify({"message": f"Technology ID {tech_id_int} not found."}), 400
            except ValueError:
                return jsonify({"message": f"Invalid Technology ID format: {tech_id}."}), 400

        task_id = task_manager.get_or_create(task_name)

        # Add required skills
        for tech_id in technology_ids:
            task_manager.add_required_skill(task_id, int(tech_id))

        # Fetch the newly created task and its skills to return it
        cursor.execute("SELECT id, name FROM tasks WHERE id = ?", (task_id,))
        new_task_data = cursor.fetchone()
        if not new_task_data: # Should not happen if creation was successful
             current_app.logger.error(f"Failed to fetch newly created task with ID {task_id}")
             return jsonify({"message": "Error retrieving created task."}), 500

        required_skills_objects = task_manager.get_required_skills(task_id)

        response_data = dict(new_task_data)
        response_data['required_skills'] = required_skills_objects # Keep for detailed info
        response_data['technology_ids'] = [skill['technology_id'] for skill in required_skills_objects] # Add for frontend compatibility

        return jsonify(response_data), 201

    except sqlite3.IntegrityError as e:
        if g.db: g.db.rollback()
        current_app.logger.error(f"Database integrity error adding task: {e}")
        return jsonify({"message": f"Database integrity error: {e}"}), 409
    except Exception as e:
        if g.db: g.db.rollback()
        current_app.logger.error(f"Server error adding task: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@api_bp.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task_api(task_id):
    try:
        data = request.get_json()
        new_name = data.get('name', '').strip()
        new_technology_ids = data.get('technology_ids', []) # Expect a list of technology IDs

        if not new_name:
            return jsonify({"message": "Task name cannot be empty."}), 400
        if not isinstance(new_technology_ids, list) or not new_technology_ids: # Ensure it's a non-empty list
            return jsonify({"message": "At least one Technology ID is required for the task."}), 400

        task_manager = TaskManager(g.db)
        cursor = g.db.cursor()

        # Check if task exists
        cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
        if not cursor.fetchone():
            return jsonify({"message": f"Task ID {task_id} not found."}), 404

        # Validate all new technology IDs
        for tech_id in new_technology_ids:
            try:
                tech_id_int = int(tech_id)
                cursor.execute("SELECT id FROM technologies WHERE id = ?", (tech_id_int,))
                if not cursor.fetchone():
                    return jsonify({"message": f"Technology ID {tech_id_int} not found."}), 400
            except ValueError:
                return jsonify({"message": f"Invalid Technology ID format: {tech_id}."}), 400

        # Update task name
        cursor.execute("UPDATE tasks SET name = ? WHERE id = ?", (new_name, task_id))

        # Update required skills
        task_manager.remove_all_required_skills(task_id) # Remove old skills
        for tech_id in new_technology_ids:
            task_manager.add_required_skill(task_id, int(tech_id)) # Add new skills

        g.db.commit()

        cursor.execute("SELECT id, name FROM tasks WHERE id = ?", (task_id,))
        updated_task_data = cursor.fetchone()
        required_skills_objects = task_manager.get_required_skills(task_id)

        response_data = dict(updated_task_data)
        response_data['required_skills'] = required_skills_objects # Keep for detailed info
        response_data['technology_ids'] = [skill['technology_id'] for skill in required_skills_objects] # Add for frontend compatibility

        return jsonify(response_data), 200
    except Exception as e:
        if g.db: g.db.rollback()
        current_app.logger.error(f"Error updating task {task_id}: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@api_bp.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task_api(task_id):
    try:
        cursor = g.db.cursor()

        # Check if task exists
        cursor.execute("SELECT name FROM tasks WHERE id = ?", (task_id,))
        task = cursor.fetchone()
        if not task:
            return jsonify({"message": f"Task ID {task_id} not found."}), 404

        task_name = task['name']

        # Delete assignments of this task from technicians
        cursor.execute("DELETE FROM technician_task_assignments WHERE task_id = ?", (task_id,))

        # Delete the task itself
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

        g.db.commit()

        if cursor.rowcount > 0: # Checks if the task itself was deleted
            return jsonify({"message": f"Task '{task_name}' (ID: {task_id}) and its assignments deleted successfully."}), 200
        else:
            # This case should ideally be caught by the initial check if the task didn't exist
            # Or if it existed but deletion failed for some reason (though IntegrityError should catch foreign key issues if not handled)
            return jsonify({"message": f"Task ID {task_id} found but could not be deleted."}), 500

    except sqlite3.Error as e: # Catch SQLite specific errors
        if g.db: g.db.rollback()
        current_app.logger.error(f"Database error deleting task {task_id}: {e}", exc_info=True)
        return jsonify({"message": f"Database error: {str(e)}"}), 500
    except Exception as e:
        if g.db: g.db.rollback()
        current_app.logger.error(f"Server error deleting task {task_id}: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@api_bp.route('/tasks_for_mapping', methods=['GET'])
def get_tasks_for_mapping_api():
    try:
        task_manager = TaskManager(g.db)
        cursor = g.db.cursor()
        cursor.execute("SELECT id, name FROM tasks ORDER BY name") # Removed technology_id and technology_name from direct task query
        tasks_raw = cursor.fetchall()

        tasks_with_skills = []
        for task_row in tasks_raw:
            task_data = dict(task_row)
            required_skills_objects = task_manager.get_required_skills(task_row['id'])
            task_data['required_skills'] = required_skills_objects # Keep for detailed info
            task_data['technology_ids'] = [skill['technology_id'] for skill in required_skills_objects] # Add for frontend compatibility
            tasks_with_skills.append(task_data)

        return jsonify({"tasks": tasks_with_skills})
    except Exception as e:
        current_app.logger.error(f"Error fetching tasks for mapping: {e}", exc_info=True)
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@api_bp.route('/tasks/<int:task_id>/technology', methods=['PUT'])
def update_task_technology_api(task_id):
    # This endpoint might be deprecated or re-purposed if tasks now have multiple skills
    # For now, let's assume it's for adding a single skill or replacing all skills with a single one.
    # Or, it could be used to add/remove one specific skill if the payload is adjusted.
    # Given the new structure, it's better to use the main PUT /api/tasks/<task_id> endpoint
    # with a list of technology_ids.
    # For now, returning a 404 or a message indicating deprecation might be best.
    current_app.logger.warning(f"Attempt to use deprecated /api/tasks/{task_id}/technology PUT endpoint.")
    return jsonify({"message": "This endpoint is deprecated. Use PUT /api/tasks/<task_id> with a 'technology_ids' list to update task skills."}), 410 # 410 Gone

