# wkndPlanning/db_utils.py
import sqlite3
import os

# --- Database Helper Functions ---
def get_db_connection(database_path):
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn

def init_db(database_path, logger=None): # Added logger argument
    conn = get_db_connection(database_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS technicians (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            sattelite_point TEXT,
            lines TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS technician_task_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            technician_id INTEGER NOT NULL,
            task_name TEXT NOT NULL,
            priority INTEGER NOT NULL,
            FOREIGN KEY (technician_id) REFERENCES technicians (id)
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_technician_task_assignments_technician_id
        ON technician_task_assignments (technician_id)
    ''')
    conn.commit()
    conn.close()
    log_message = "Database initialized via db_utils."
    if logger:
        logger.info(log_message)
    else:
        print(log_message) # Fallback
