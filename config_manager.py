# wkndPlanning/config_manager.py
import sqlite3
import traceback
import os
from db_utils import get_db_connection

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
    TECHNICIAN_GROUPS.update({"Fuchsbau": [], "Closures": [], "Aquarium": []})
    valid_groups = {"Fuchsbau", "Closures", "Aquarium"}

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

        sql_query = "SELECT id, name, sattelite_point, lines FROM technicians ORDER BY name"
        cursor.execute(sql_query)
        db_technicians = cursor.fetchall()
        _log(f"  Query executed. Number of rows fetched from 'technicians' table: {len(db_technicians)}")

        if not db_technicians:
            _log("  'technicians' table appears empty or query returned no results.", 'warning')

        for row_idx, row in enumerate(db_technicians):
            tech_id = row['id']
            tech_name = row['name']
            sattelite_point = row['sattelite_point']
            lines_str = row['lines']

            if not tech_name or not sattelite_point or sattelite_point not in valid_groups:
                _log(f"      SKIPPING row {row_idx + 1} (ID {tech_id}, Name '{tech_name}', Sattelite '{sattelite_point}') due to missing/invalid critical data.", 'warning')
                continue

            TECHNICIANS.append(tech_name)
            TECHNICIAN_LINES[tech_name] = [int(l.strip()) for l in lines_str.split(',') if l.strip().isdigit()] if lines_str else []
            if sattelite_point in TECHNICIAN_GROUPS:
                TECHNICIAN_GROUPS[sattelite_point].append(tech_name)
            # else: # This case was already handled by the skip condition

            task_assignments_query = "SELECT task_name, priority FROM technician_task_assignments WHERE technician_id = ? ORDER BY priority ASC"
            cursor.execute(task_assignments_query, (tech_id,))
            assignments_for_tech = []
            db_assignments = cursor.fetchall()
            for assign_row in db_assignments:
                assignments_for_tech.append({'task': assign_row['task_name'], 'prio': assign_row['priority']})
            TECHNICIAN_TASKS[tech_name] = assignments_for_tech

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
