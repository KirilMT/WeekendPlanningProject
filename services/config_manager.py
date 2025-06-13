# wkndPlanning/config_manager.py
import sqlite3
import traceback
import os
from .db_utils import get_db_connection, get_technician_lines_via_satellite_point

# --- Configuration Store ---
TECHNICIAN_TASKS = {}
TECHNICIAN_LINES = {}
TECHNICIANS = []
TECHNICIAN_GROUPS = {}
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

def load_app_config(database_path, logger=None): # Added logger argument
    global TECHNICIAN_TASKS, TECHNICIAN_LINES, TECHNICIANS, TECHNICIAN_GROUPS
    TECHNICIAN_TASKS.clear()
    TECHNICIAN_LINES.clear()
    TECHNICIANS.clear()
    TECHNICIAN_GROUPS.clear()
    # Initialize default groups. Satellite points will be dynamic from DB.
    # The concept of TECHNICIAN_GROUPS might need to align with satellite points now.
    # For now, keeping its structure but it will be populated based on technician's satellite point name.
    # We will fetch all satellite points and use their names as keys if needed.

    def _log(message, level='info'):
        if logger:
            if level == 'info':
                logger.info(message)
            elif level == 'warning':
                logger.warning(message)
            elif level == 'error':
                logger.error(message)
            # Removed explicit debug level handling here to reduce verbosity
            # If a message was intended for debug, it won't be printed unless logger's global level is DEBUG
            # and the call to _log specifies 'debug'.
            # For very detailed, less frequent debugging, direct logger.debug() calls can be used.
        else:
            print(f"{level.upper()}: {message}") # Fallback

    _log(f"Attempting to load configuration from database: {os.path.abspath(database_path)}")
    conn = None
    try:
        conn = get_db_connection(database_path)
        if not conn:
            _log("  Failed to get database connection for config load.", 'error')
            return
        _log("  Successfully connected to the database for config load.")
        cursor = conn.cursor()

        # Fetch all satellite points to map their IDs to names for TECHNICIAN_GROUPS population
        cursor.execute("SELECT id, name FROM satellite_points")
        satellite_points_map = {sp['id']: sp['name'] for sp in cursor.fetchall()}
        # Initialize TECHNICIAN_GROUPS with names from satellite_points table
        for sp_name in satellite_points_map.values():
            if sp_name not in TECHNICIAN_GROUPS:
                TECHNICIAN_GROUPS[sp_name] = []

        # Updated query to fetch satellite_point_id
        sql_query = "SELECT id, name, satellite_point_id FROM technicians ORDER BY name"
        cursor.execute(sql_query)
        db_technicians = cursor.fetchall()
        _log(f"  Query executed. Number of rows fetched from 'technicians' table: {len(db_technicians)}")

        if not db_technicians:
            _log("  'technicians' table appears empty or query returned no results.", 'warning')

        for row_idx, row in enumerate(db_technicians):
            tech_id = row['id']
            tech_name = row['name']
            tech_satellite_point_id = row['satellite_point_id']

            # Determine satellite point name for grouping
            tech_satellite_point_name = None
            if tech_satellite_point_id in satellite_points_map:
                tech_satellite_point_name = satellite_points_map[tech_satellite_point_id]

            if not tech_name or not tech_satellite_point_name:
                _log(f"      SKIPPING row {row_idx + 1} (ID {tech_id}, Name '{tech_name}', SP_ID '{tech_satellite_point_id}') due to missing name or unresolvable/unassigned satellite point.", 'warning')
                continue

            TECHNICIANS.append(tech_name)

            # Fetch lines for the technician using their satellite_point_id via the new db_utils function
            # get_technician_lines_via_satellite_point returns a list of line names
            # The original code expected line numbers, this needs to be clarified if line names or IDs are expected here.
            # Assuming line *names* are now expected in TECHNICIAN_LINES based on the db structure.
            # If line IDs (integers) were expected, the get_technician_lines_via_satellite_point would need to return IDs or this logic adjusted.
            # For now, proceeding with line names as strings.
            technician_actual_lines = get_technician_lines_via_satellite_point(conn, tech_id)
            TECHNICIAN_LINES[tech_name] = technician_actual_lines

            if tech_satellite_point_name in TECHNICIAN_GROUPS:
                TECHNICIAN_GROUPS[tech_satellite_point_name].append(tech_name)
            else:
                # This case should ideally not happen if TECHNICIAN_GROUPS is pre-populated from all satellite_points
                _log(f"  Warning: Satellite point '{tech_satellite_point_name}' for technician '{tech_name}' not found in pre-populated TECHNICIAN_GROUPS. Adding it.", 'warning')
                TECHNICIAN_GROUPS[tech_satellite_point_name] = [tech_name]

        _log(f"Successfully loaded configuration for {len(TECHNICIANS)} technicians from database via config_manager.")

    except sqlite3.Error as e:
        _log(f"SQLite error during config load in config_manager: {e}", 'error')
        _log(traceback.format_exc(), 'error')
    except Exception as e:
        _log(f"General error loading configuration from database in config_manager: {e}", 'error')
        _log(traceback.format_exc(), 'error')
    finally:
        if conn:
            conn.close()
        else:
            _log("  No active database connection to close in config_manager.", 'warning')
