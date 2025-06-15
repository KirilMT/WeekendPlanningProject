# wkndPlanning/db_utils.py
import sqlite3

# --- Database Helper Functions ---
def get_db_connection(database_path):
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn

def init_db(db_path, logger=None):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create satellite_points table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS satellite_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    logger.info("Table 'satellite_points' ensured.") if logger else None

    # Add a default satellite point if the table is empty
    cursor.execute("SELECT COUNT(*) FROM satellite_points")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO satellite_points (name) VALUES (?)", ("Default Satellite Point",))
        # conn.commit() # Commit will be handled later in the function or should be done immediately if critical path
        if logger: logger.info("Added 'Default Satellite Point' as no satellite points were found.")

    # Create lines table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            satellite_point_id INTEGER,
            FOREIGN KEY(satellite_point_id) REFERENCES satellite_points(id)
        )
    ''')
    logger.info("Table 'lines' ensured.") if logger else None

    # Create technicians table (or alter if exists)
    cursor.execute("PRAGMA table_info(technicians)")
    columns = [column[1] for column in cursor.fetchall()]

    if 'sattelite_point' in columns or 'lines' in columns or 'satellite_point_id' not in columns:
        logger.info("Old 'technicians' table structure found. Recreating with new schema.") if logger else None
        # Need to handle data migration if this were a production system
        # For development, we might drop and recreate or carefully alter
        # Simplified approach: drop and recreate if old columns exist or new one is missing.
        # This will lose existing technician data if not migrated.
        # A more robust solution would use ALTER TABLE commands carefully.

        # Try to preserve data (basic example, assumes id and name are key)
        cursor.execute("SELECT id, name FROM technicians")
        existing_technicians_simple = cursor.fetchall()

        cursor.execute("DROP TABLE IF EXISTS technicians")
        cursor.execute('''
            CREATE TABLE technicians (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                satellite_point_id INTEGER,
                FOREIGN KEY(satellite_point_id) REFERENCES satellite_points(id)
            )
        ''')
        logger.info("Table 'technicians' recreated with new schema (satellite_point_id).") if logger else None

        # Restore basic data if any was backed up (without old satellite/lines info)
        if existing_technicians_simple:
            cursor.executemany("INSERT INTO technicians (id, name) VALUES (?, ?)", existing_technicians_simple)
            logger.info(f"Restored {len(existing_technicians_simple)} technicians (name/id only) to new table structure.") if logger else None
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS technicians (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                satellite_point_id INTEGER,
                FOREIGN KEY(satellite_point_id) REFERENCES satellite_points(id)
            )
        ''')
        logger.info("Table 'technicians' (new schema) ensured.") if logger else None

    # Technologies Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS technologies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, -- Removed UNIQUE constraint
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

    # Tasks Table (new schema)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
            -- technology_id INTEGER, -- Removed: Tasks can have multiple skills via task_required_skills
            -- FOREIGN KEY (technology_id) REFERENCES technologies (id) -- Removed
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
            FOREIGN KEY (technician_id) REFERENCES technicians (id),
            FOREIGN KEY (task_id) REFERENCES tasks (id)
        )
    ''')

    # New Table: Task Required Skills
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_required_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            technology_id INTEGER,
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY(technology_id) REFERENCES technologies(id) ON DELETE CASCADE,
            UNIQUE(task_id, technology_id)
        )
    ''')
    logger.info("Table 'task_required_skills' ensured.") if logger else None

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

    # Indexes for task_required_skills
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_task_required_skills_task_id
        ON task_required_skills (task_id)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_task_required_skills_technology_id
        ON task_required_skills (technology_id)
    ''')

    conn.commit()
    conn.close()

def get_or_create_satellite_point(conn, name):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM satellite_points WHERE name = ?", (name,))
    row = cursor.fetchone()
    if row:
        return row['id']
    else:
        cursor.execute("INSERT INTO satellite_points (name) VALUES (?)", (name,))
        conn.commit()
        return cursor.lastrowid

def get_all_satellite_points(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM satellite_points ORDER BY name")
    return [{'id': row['id'], 'name': row['name']} for row in cursor.fetchall()]

def update_satellite_point(conn, point_id, new_name):
    """Updates the name of an existing satellite point."""
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE satellite_points SET name = ? WHERE id = ?", (new_name, point_id))
        conn.commit()
        if cursor.rowcount == 0:
            return False, "Satellite point not found or name unchanged."
        return True, "Satellite point updated successfully."
    except sqlite3.IntegrityError: # Handles unique constraint violation for name
        return False, "Satellite point name already exists."

def delete_satellite_point(conn, point_id):
    """Deletes a satellite point if it's not associated with any lines or technicians."""
    cursor = conn.cursor()
    # Check if any lines are associated with this satellite point
    cursor.execute("SELECT COUNT(*) FROM lines WHERE satellite_point_id = ?", (point_id,))
    if cursor.fetchone()[0] > 0:
        return False, "Satellite point is associated with lines and cannot be deleted."

    # Check if any technicians are associated with this satellite point
    cursor.execute("SELECT COUNT(*) FROM technicians WHERE satellite_point_id = ?", (point_id,))
    if cursor.fetchone()[0] > 0:
        return False, "Satellite point is associated with technicians and cannot be deleted."

    cursor.execute("DELETE FROM satellite_points WHERE id = ?", (point_id,))
    conn.commit()
    if cursor.rowcount == 0:
        return False, "Satellite point not found."
    return True, "Satellite point deleted successfully."

def add_line(conn, name, satellite_point_id):
    cursor = conn.cursor()
    cursor.execute("INSERT INTO lines (name, satellite_point_id) VALUES (?, ?)", (name, satellite_point_id))
    conn.commit()
    return cursor.lastrowid

def get_lines_for_satellite_point(conn, satellite_point_id):
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM lines WHERE satellite_point_id = ? ORDER BY name", (satellite_point_id,))
    return [{'id': row['id'], 'name': row['name']} for row in cursor.fetchall()]

# New helper function to get lines for a technician via their satellite point
def get_technician_lines_via_satellite_point(conn, technician_id):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT l.name
        FROM lines l
        JOIN technicians t ON l.satellite_point_id = t.satellite_point_id
        WHERE t.id = ?
        ORDER BY l.name
    ''', (technician_id,))
    return [row['name'] for row in cursor.fetchall()]

def get_all_lines(conn):
    """Fetches all lines with their satellite point information."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT l.id, l.name, l.satellite_point_id, sp.name as satellite_point_name
        FROM lines l
        JOIN satellite_points sp ON l.satellite_point_id = sp.id
        ORDER BY sp.name, l.name
    """)
    return [dict(row) for row in cursor.fetchall()]

def update_line(conn, line_id, new_name, new_satellite_point_id):
    """Updates a line's name and/or its satellite point."""
    cursor = conn.cursor()
    try:
        # Check if the new satellite_point_id is valid
        cursor.execute("SELECT id FROM satellite_points WHERE id = ?", (new_satellite_point_id,))
        if not cursor.fetchone():
            return False, "Invalid satellite point ID."

        # Check for duplicate line name within the same satellite point (optional, depends on requirements)
        # For now, allowing duplicate line names if they are under different satellite points, or even same.
        # If unique constraint (name, satellite_point_id) is desired, it should be added to DB schema.

        cursor.execute("UPDATE lines SET name = ?, satellite_point_id = ? WHERE id = ?",
                       (new_name, new_satellite_point_id, line_id))
        conn.commit()
        if cursor.rowcount == 0:
            return False, "Line not found or data unchanged."
        return True, "Line updated successfully."
    except sqlite3.Error as e: # Catch any potential SQLite errors, like FK issues if SP ID was invalid (though checked)
        return False, f"Database error: {e}"

def delete_line(conn, line_id):
    """Deletes a line by its ID."""
    cursor = conn.cursor()
    # No direct dependencies on the lines table from other tables that would prevent deletion by default FK constraints.
    # Technicians are linked via satellite_point_id, not directly to lines.
    # If there were other direct dependencies, checks would be needed here.
    cursor.execute("DELETE FROM lines WHERE id = ?", (line_id,))
    conn.commit()
    if cursor.rowcount == 0:
        return False, "Line not found."
    return True, "Line deleted successfully."


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

    # First, delete from task_required_skills where technology_id = technology_id
    cursor.execute("DELETE FROM task_required_skills WHERE technology_id = ?", (technology_id,))

    cursor.execute("DELETE FROM technician_technology_skills WHERE technology_id = ?", (technology_id,))
    # No direct action needed on tasks table here due to schema change.
    # task_required_skills entries will be cascaded by DB if technology is deleted.

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

# --- Task Management (with Technology) ---
def get_or_create_task(conn, task_name): # Removed technology_id parameter
    """Gets the ID of an existing task or creates it."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM tasks WHERE name = ?", (task_name,)) # Removed technology_id from query
    row = cursor.fetchone()
    if row:
        task_id = row['id']
        # No technology_id to update directly on the task anymore
        return task_id
    else:
        cursor.execute("INSERT INTO tasks (name) VALUES (?)", (task_name,)) # Removed technology_id
        conn.commit()
        return cursor.lastrowid

# --- Task Required Skills Management ---
def add_required_skill_to_task(conn, task_id, technology_id):
    """Adds a required technology/skill to a task. Ignores if already present."""
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO task_required_skills (task_id, technology_id) VALUES (?, ?)",
                       (task_id, technology_id))
        conn.commit()
    except sqlite3.IntegrityError as e:
        # This might happen if task_id or technology_id does not exist,
        # though INSERT OR IGNORE should handle UNIQUE constraint violations silently.
        print(f"Error adding required skill to task: {e}") # Or log this

def remove_required_skill_from_task(conn, task_id, technology_id):
    """Removes a required technology/skill from a task."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM task_required_skills WHERE task_id = ? AND technology_id = ?",
                   (task_id, technology_id))
    conn.commit()

def get_required_skills_for_task(conn, task_id):
    """Fetches all required technology/skill details for a given task."""
    cursor = conn.cursor()
    query = """
        SELECT trs.technology_id, t.name as technology_name
        FROM task_required_skills trs
        JOIN technologies t ON trs.technology_id = t.id
        WHERE trs.task_id = ?
        ORDER BY t.name
    """
    cursor.execute(query, (task_id,))
    return [{"technology_id": row["technology_id"], "technology_name": row["technology_name"]} for row in cursor.fetchall()]

def remove_all_required_skills_for_task(conn, task_id):
    """Removes all technology/skill requirements for a given task."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM task_required_skills WHERE task_id = ?", (task_id,))
    conn.commit()

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
