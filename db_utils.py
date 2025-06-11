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
            name TEXT UNIQUE NOT NULL,
            group_id INTEGER,
            parent_id INTEGER, -- Added for hierarchy
            FOREIGN KEY (group_id) REFERENCES technology_groups (id),
            FOREIGN KEY (parent_id) REFERENCES technologies (id) -- Self-referencing for hierarchy
        )
    ''')
    # Add group_id column to technologies if it doesn't exist (for existing dbs)
    try:
        cursor.execute("PRAGMA table_info(technologies)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'group_id' not in columns:
            cursor.execute("ALTER TABLE technologies ADD COLUMN group_id INTEGER REFERENCES technology_groups(id)")
            if logger: logger.info("Added group_id column to technologies table.")
        if 'parent_id' not in columns: # Check and add parent_id
            cursor.execute("ALTER TABLE technologies ADD COLUMN parent_id INTEGER REFERENCES technologies(id)")
            if logger: logger.info("Added parent_id column to technologies table.")
    except sqlite3.Error as e:
        if logger: logger.error(f"Error checking/adding group_id or parent_id to technologies: {e}")


    # Technology Groups Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS technology_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')

    # Specialities Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS specialities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')

    # Technician Specialities Table (Linking Table)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS technician_specialities (
            technician_id INTEGER NOT NULL,
            speciality_id INTEGER NOT NULL,
            FOREIGN KEY (technician_id) REFERENCES technicians (id),
            FOREIGN KEY (speciality_id) REFERENCES specialities (id),
            PRIMARY KEY (technician_id, speciality_id)
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
    # Index for technology group_id
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_technologies_group_id
        ON technologies (group_id)
    ''')
    # Index for parent_id
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_technologies_parent_id
        ON technologies (parent_id)
    ''')
    # Indexes for technician_specialities
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_technician_specialities_technician_id
        ON technician_specialities (technician_id)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_technician_specialities_speciality_id
        ON technician_specialities (speciality_id)
    ''')

    conn.commit()
    conn.close()

# --- Technology Management ---
def get_or_create_technology(conn, technology_name, group_id=None):
    """Gets the ID of an existing technology or creates it if it doesn't exist. Optionally assigns to a group."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM technologies WHERE name = ?", (technology_name,))
    row = cursor.fetchone()
    if row:
        # Optionally update group_id if it's provided and different (or was NULL)
        # For now, if tech exists, we don't auto-update its group here. This can be a separate management action.
        # if group_id is not None:
        #     cursor.execute("UPDATE technologies SET group_id = ? WHERE id = ?", (group_id, row['id']))
        #     conn.commit()
        # We also don't update parent_id here automatically if technology exists.
        # This should be a specific action in the UI if a technology needs to be moved.
        return row['id']
    else:
        # When creating, parent_id is not handled by this specific function yet.
        # It might be better to have a dedicated function or update this one carefully.
        # For now, keeping it simple and not setting parent_id on creation via this function.
        # The POST /api/technologies endpoint in app.py will handle parent_id.
        cursor.execute("INSERT INTO technologies (name, group_id, parent_id) VALUES (?, ?, NULL)", (technology_name, group_id)) # Ensure parent_id is explicitly NULL or handled
        conn.commit()
        return cursor.lastrowid

def delete_technology(conn, technology_id):
    """Deletes a technology by its ID."""
    cursor = conn.cursor()
    # Before deleting, consider implications:
    # 1. Child technologies: SQLite by default does not cascade deletes unless specified with ON DELETE CASCADE
    #    in the FOREIGN KEY constraint. The current schema does not specify this.
    #    So, child technologies will have their parent_id become NULL (or remain if the FK is not enforced strictly,
    #    but it should be). Or, you might want to prevent deletion if children exist, or delete them recursively.
    #    For now, we'll just delete the specified technology.
    # 2. Technician skills: Similar to above, skills linked to this technology might need to be handled.
    #    The technician_technology_skills table has a FOREIGN KEY. Deleting a technology
    #    could violate this if not handled (e.g., ON DELETE CASCADE or setting to NULL if allowed).
    #    Assuming for now that related skills should also be removed or handled by the database schema (e.g. CASCADE).
    #    Let's ensure related skills are deleted first to avoid FK constraint issues if not cascaded.
    cursor.execute("DELETE FROM technician_technology_skills WHERE technology_id = ?", (technology_id,))
    # Also, tasks might be linked to this technology.
    # cursor.execute("UPDATE tasks SET technology_id = NULL WHERE technology_id = ?", (technology_id,)) # Option 1: Set to NULL
    cursor.execute("DELETE FROM tasks WHERE technology_id = ?", (technology_id,)) # Option 2: Delete tasks (if appropriate)

    # Now, attempt to delete the technology itself
    cursor.execute("DELETE FROM technologies WHERE id = ?", (technology_id,))
    conn.commit()
    return cursor.rowcount # Returns the number of rows deleted (0 or 1)

# --- Technology Group Management ---
def get_or_create_technology_group(conn, group_name):
    """Gets the ID of an existing technology group or creates it if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM technology_groups WHERE name = ?", (group_name,))
    row = cursor.fetchone()
    if row:
        return row['id']
    else:
        cursor.execute("INSERT INTO technology_groups (name) VALUES (?)", (group_name,))
        conn.commit()
        return cursor.lastrowid

def get_all_technology_groups(conn):
    """Fetches all technology groups."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM technology_groups ORDER BY name")
    return [{"id": row['id'], "name": row['name']} for row in cursor.fetchall()]

# --- Speciality Management ---
def get_or_create_speciality(conn, speciality_name):
    """Gets the ID of an existing speciality or creates it if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM specialities WHERE name = ?", (speciality_name,))
    row = cursor.fetchone()
    if row:
        return row['id']
    else:
        cursor.execute("INSERT INTO specialities (name) VALUES (?)", (speciality_name,))
        conn.commit()
        return cursor.lastrowid

def get_all_specialities(conn):
    """Fetches all specialities."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM specialities ORDER BY name")
    return [{"id": row['id'], "name": row['name']} for row in cursor.fetchall()]

def get_technician_specialities(conn, technician_id):
    """Fetches all specialities for a given technician_id."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, s.name 
        FROM specialities s
        JOIN technician_specialities ts ON s.id = ts.speciality_id
        WHERE ts.technician_id = ?
        ORDER BY s.name
    """, (technician_id,))
    return [{"id": row['id'], "name": row['name']} for row in cursor.fetchall()]

def add_speciality_to_technician(conn, technician_id, speciality_id):
    """Adds a speciality to a technician."""
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO technician_specialities (technician_id, speciality_id) VALUES (?, ?)", (technician_id, speciality_id))
        conn.commit()
    except sqlite3.IntegrityError:
        # Combination already exists, or foreign key constraint failed. Silently ignore for now or log.
        pass # Or raise an error to be handled by the caller

def remove_speciality_from_technician(conn, technician_id, speciality_id):
    """Removes a speciality from a technician."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM technician_specialities WHERE technician_id = ? AND speciality_id = ?", (technician_id, speciality_id))
    conn.commit()

# --- Task Management (with Technology) ---
def get_or_create_task(conn, task_name, technology_id):
    """Gets the ID of an existing task or creates it with a technology link."""
    cursor = conn.cursor()
    # Check if task exists and if its technology_id needs update (or is NULL)
    cursor.execute("SELECT id, technology_id FROM tasks WHERE name = ?", (task_name,))
    row = cursor.fetchone()
    if row:
        task_id = row['id']
        # Update technology_id if it's different or was null and a new one is provided.
        # This function will now update the technology_id if a valid one is passed.
        if technology_id is not None and row['technology_id'] != technology_id:
            cursor.execute("UPDATE tasks SET technology_id = ? WHERE id = ?", (technology_id, task_id))
            conn.commit()
        elif technology_id is None and row['technology_id'] is not None: # If passed technology_id is null, set it to null in DB
            cursor.execute("UPDATE tasks SET technology_id = NULL WHERE id = ?", (task_id,))
            conn.commit()
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

def get_technician_skills_by_id(conn, technician_id):
    """
    Fetches skills for a specific technician by their ID.
    Returns a dictionary: {technology_id: skill_level}
    """
    skills = {}
    cursor = conn.cursor()
    query = """
        SELECT technology_id, skill_level
        FROM technician_technology_skills
        WHERE technician_id = ?
    """
    cursor.execute(query, (technician_id,))
    for row in cursor.fetchall():
        skills[row['technology_id']] = row['skill_level']
    return skills
