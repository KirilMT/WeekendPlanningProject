# wkndPlanning/db_utils.py
import sqlite3

# --- Database Helper Functions ---
def get_db_connection(database_path):
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn

def init_db(database_path, logger=None): # Added logger argument
    conn = get_db_connection(database_path)
    cursor = conn.cursor()

    # 1. Define and ensure all tables exist with the LATEST schema
    # Technicians Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS technicians (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            sattelite_point TEXT,
            lines TEXT
        )
    ''')

    # Technologies Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS technologies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')

    # Tasks Table (new schema)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            technology_id INTEGER,
            FOREIGN KEY (technology_id) REFERENCES technologies (id)
        )
    ''')

    # Technician Technology Skills Table (using skill_level 0-4 as per your file)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS technician_technology_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            technician_id INTEGER NOT NULL,
            technology_id INTEGER NOT NULL,
            skill_level INTEGER CHECK(skill_level IN (0, 1, 2, 3, 4)),
            FOREIGN KEY (technician_id) REFERENCES technicians (id),
            FOREIGN KEY (technology_id) REFERENCES technologies (id),
            UNIQUE (technician_id, technology_id)
        )
    ''')

    # Ensure 'technician_task_assignments' table exists with the new schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS technician_task_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            technician_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            priority INTEGER NOT NULL,
            FOREIGN KEY (technician_id) REFERENCES technicians (id),
            FOREIGN KEY (task_id) REFERENCES tasks (id)
        )
    ''')

    # 3. Create Indexes (idempotently)
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_technician_task_assignments_technician_id
        ON technician_task_assignments (technician_id)
    ''')
    # Index for new task_id column
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_technician_task_assignments_task_id
        ON technician_task_assignments (task_id)
    ''')
    # Indexes for technician_technology_skills
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_technician_technology_skills_technician_id
        ON technician_technology_skills (technician_id)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_technician_technology_skills_technology_id
        ON technician_technology_skills (technology_id)
    ''')

    conn.commit()
    conn.close()

# --- Technology Management ---
def get_or_create_technology(conn, technology_name):
    """Gets the ID of an existing technology or creates it if it doesn\'t exist."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM technologies WHERE name = ?", (technology_name,))
    row = cursor.fetchone()
    if row:
        return row['id']
    else:
        cursor.execute("INSERT INTO technologies (name) VALUES (?)", (technology_name,))
        conn.commit()
        return cursor.lastrowid

# --- Task Management (with Technology) ---
def get_or_create_task(conn, task_name, technology_id):
    """Gets the ID of an existing task or creates it with a technology link."""
    cursor = conn.cursor()
    # Check if task exists and if its technology_id needs update (or is NULL)
    cursor.execute("SELECT id, technology_id FROM tasks WHERE name = ?", (task_name,))
    row = cursor.fetchone()
    if row:
        task_id = row['id']
        # Optionally update technology_id if it\'s different or was null
        # For now, we assume if it exists, its technology link is managed elsewhere or stable
        # if row['technology_id'] != technology_id:
        #     cursor.execute("UPDATE tasks SET technology_id = ? WHERE id = ?", (technology_id, task_id))
        #     conn.commit()
        return task_id
    else:
        cursor.execute("INSERT INTO tasks (name, technology_id) VALUES (?, ?)", (task_name, technology_id))
        conn.commit()
        return cursor.lastrowid

# --- Technician Skill Management ---
def get_all_technician_skills_by_name(conn):
    """
    Fetches all technician skills and returns them in a nested dictionary:
    {tech_name: {technology_id: skill_level}}
    """
    skills_map = {}
    cursor = conn.cursor()
    query = """
        SELECT t.name as tech_name, tts.technology_id, tts.skill_level
        FROM technician_technology_skills tts
        JOIN technicians t ON tts.technician_id = t.id
    """
    cursor.execute(query)
    for row in cursor.fetchall():
        tech_name = row['tech_name']
        technology_id = row['technology_id']
        skill_level = row['skill_level']
        if tech_name not in skills_map:
            skills_map[tech_name] = {}
        skills_map[tech_name][technology_id] = skill_level
    return skills_map

# You might also need functions to add/update technician skills, for example:
def update_technician_skill(conn, technician_id, technology_id, skill_level):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO technician_technology_skills (technician_id, technology_id, skill_level)
        VALUES (?, ?, ?)
    ''', (technician_id, technology_id, skill_level))
    conn.commit()
