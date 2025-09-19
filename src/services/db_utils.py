# src/db_utils.py
import os
import json
import sqlite3

# --- Database Helper Functions ---
def get_db_connection(database_path):
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn

def populate_dummy_data(conn, logger):
    """Populates the database with dummy data from dummy_data.json."""
    logger.info("Populating database with dummy data.")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    dummy_data_path = os.path.join(current_dir, '..', '..', 'test_data', 'dummy_data.json')

    try:
        with open(dummy_data_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Dummy data file not found at {dummy_data_path}")
        return
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from {dummy_data_path}")
        return

    cursor = conn.cursor()
    tech_manager = TechnologyManager(conn)
    task_manager = TaskManager(conn)

    satellite_points = {}
    technicians = {}
    technologies = {}
    tasks = {}
    tech_groups = {}

    # Populate satellite_points
    for sp_name in data.get("satellite_points", []):
        sp_id = get_or_create_satellite_point(conn, sp_name)
        satellite_points[sp_name] = sp_id
    logger.info(f"Populated {len(satellite_points)} satellite points.")

    # Populate lines
    for line in data.get("lines", []):
        sp_id = satellite_points.get(line["satellite_point"])
        if sp_id:
            add_line(conn, line["name"], sp_id)
    logger.info(f"Populated lines.")

    # Populate technology_groups
    for group_name in data.get("technology_groups", []):
        group_id = tech_manager.get_or_create_group(group_name)
        tech_groups[group_name] = group_id
    logger.info(f"Populated {len(tech_groups)} technology groups.")

    # Populate technologies (first pass for parent-less techs)
    for tech_data in data.get("technologies", []):
        if "parent" not in tech_data:
            tech_name = tech_data["name"]
            group_id = tech_groups.get(tech_data.get("group"))
            tech_id = tech_manager.get_or_create(tech_name, group_id=group_id)
            technologies[tech_name] = tech_id
            
    # Second pass for technologies with parents
    for tech_data in data.get("technologies", []):
        if "parent" in tech_data:
            tech_name = tech_data["name"]
            group_id = tech_groups.get(tech_data.get("group"))
            parent_id = technologies.get(tech_data.get("parent"))
            tech_id = tech_manager.get_or_create(tech_name, group_id=group_id, parent_id=parent_id)
            technologies[tech_name] = tech_id
    logger.info(f"Populated {len(technologies)} technologies.")

    # Populate technicians and their skills
    for tech_data in data.get("technicians", []):
        tech_name = tech_data["name"]
        sp_id = satellite_points.get(tech_data["satellite_point"])
        cursor.execute("INSERT OR IGNORE INTO technicians (name, satellite_point_id) VALUES (?, ?)", (tech_name, sp_id))
        cursor.execute("SELECT id FROM technicians WHERE name = ?", (tech_name,))
        tech_id_result = cursor.fetchone()
        if tech_id_result:
            tech_id = tech_id_result[0] # Access by index to fix tuple error
            technicians[tech_name] = tech_id
            
            for skill_data in tech_data.get("skills", []):
                skill_name = skill_data["name"]
                level = skill_data["level"]
                tech_id_for_skill = technologies.get(skill_name)
                if tech_id_for_skill:
                    update_technician_skill(conn, tech_id, tech_id_for_skill, level)
    logger.info(f"Populated {len(technicians)} technicians and their skills.")

    # Populate tasks and their required skills
    for task_data in data.get("tasks", []):
        task_name = task_data["name"]
        task_id = task_manager.get_or_create(task_name)
        tasks[task_name] = task_id
        for skill_name in task_data.get("required_skills", []):
            skill_id = technologies.get(skill_name)
            if skill_id:
                task_manager.add_required_skill(task_id, skill_id)
    logger.info(f"Populated {len(tasks)} tasks and their required skills.")

    conn.commit()
    logger.info("Dummy data population complete.")

def init_db(db_path, logger=None, debug_use_test_db=False):
    db_exists = os.path.exists(db_path)
    
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Create satellite_points table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS satellite_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    logger.info("Table 'satellite_points' ensured.") if logger else None

    # Add a default satellite point if the table is empty and not in test mode
    if not debug_use_test_db:
        cursor.execute("SELECT COUNT(*) FROM satellite_points")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO satellite_points (name) VALUES (?)", ("Default Satellite Point",))
            conn.commit()  # Commit immediately for critical default data
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

    # --- Technicians Table Logic ---
    # Check if the technicians table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='technicians'")
    table_exists = cursor.fetchone()

    recreate_table = False
    existing_technicians_simple = []

    if table_exists:
        # If it exists, check if it has the old schema that needs updating
        cursor.execute("PRAGMA table_info(technicians)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'sattelite_point' in columns or 'lines' in columns or 'satellite_point_id' not in columns:
            recreate_table = True
            logger.info("Old 'technicians' table structure found. Preparing to recreate with new schema.") if logger else None
            # Back up existing data before dropping the table
            cursor.execute("SELECT id, name FROM technicians")
            existing_technicians_simple = cursor.fetchall()
            cursor.execute("DROP TABLE technicians")
            logger.info("Dropped old 'technicians' table.") if logger else None
    else:
        # If table doesn't exist, it needs to be created
        recreate_table = True

    if recreate_table:
        # Create the table with the new, correct schema
        cursor.execute('''
            CREATE TABLE technicians (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                satellite_point_id INTEGER,
                FOREIGN KEY(satellite_point_id) REFERENCES satellite_points(id)
            )
        ''')
        logger.info("Table 'technicians' created with new schema (satellite_point_id).") if logger else None

        # Restore basic data if any was backed up from an old table version
        if existing_technicians_simple:
            cursor.executemany("INSERT INTO technicians (id, name) VALUES (?, ?)", existing_technicians_simple)
            logger.info(f"Restored {len(existing_technicians_simple)} technicians (name/id only) to new table structure.") if logger else None
    else:
        logger.info("Table 'technicians' already up-to-date.") if logger else None


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

    # Technician Groups Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS technician_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    logger.info("Table 'technician_groups' ensured.") if logger else None

    # Technician Group Members Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS technician_group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            technician_id INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            FOREIGN KEY (technician_id) REFERENCES technicians (id) ON DELETE CASCADE,
            FOREIGN KEY (group_id) REFERENCES technician_groups (id) ON DELETE CASCADE,
            UNIQUE (technician_id, group_id)
        )
    ''')
    logger.info("Table 'technician_group_members' ensured.") if logger else None

    

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

    # Populate with dummy data if the DB was just created and we are in debug mode
    if not db_exists and debug_use_test_db:
        populate_dummy_data(conn, logger)

    conn.close()

def get_or_create_satellite_point(conn, name):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM satellite_points WHERE name = ?", (name,))
    row = cursor.fetchone()
    if row:
        return row[0] # Access by index to fix tuple error
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


class TechnologyManager:
    """Manages technologies and technology groups in the database."""
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()

    def get_or_create(self, technology_name, group_id=None, parent_id=None):
        """Gets the ID of an existing technology or creates it."""
        self.cursor.execute("SELECT id FROM technologies WHERE name = ?", (technology_name,))
        row = self.cursor.fetchone()
        if row:
            return row[0] # Access by index to fix tuple error
        else:
            self.cursor.execute("INSERT INTO technologies (name, group_id, parent_id) VALUES (?, ?, ?)",
                                (technology_name, group_id, parent_id))
            self.conn.commit()
            return self.cursor.lastrowid

    def delete(self, technology_id):
        """Deletes a technology by its ID after removing related skills."""
        self.cursor.execute("DELETE FROM task_required_skills WHERE technology_id = ?", (technology_id,))
        self.cursor.execute("DELETE FROM technician_technology_skills WHERE technology_id = ?", (technology_id,))
        self.cursor.execute("DELETE FROM technologies WHERE id = ?", (technology_id,))
        self.conn.commit()
        return self.cursor.rowcount

    def get_or_create_group(self, group_name):
        """Gets the ID of an existing technology group or creates it."""
        self.cursor.execute("SELECT id FROM technology_groups WHERE name = ?", (group_name,))
        row = self.cursor.fetchone()
        if row:
            return row[0] # Access by index to fix tuple error
        else:
            self.cursor.execute("INSERT INTO technology_groups (name) VALUES (?)", (group_name,))
            self.conn.commit()
            return self.cursor.lastrowid

    def get_all_groups(self):
        """Fetches all technology groups."""
        self.cursor.execute("SELECT id, name FROM technology_groups ORDER BY name")
        return [{"id": row['id'], "name": row['name']} for row in self.cursor.fetchall()]


class TaskManager:
    """Manages tasks and their required skills in the database."""
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()

    def get_or_create(self, task_name):
        """Gets the ID of an existing task or creates it."""
        self.cursor.execute("SELECT id FROM tasks WHERE name = ?", (task_name,))
        row = self.cursor.fetchone()
        if row:
            return row[0] # Access by index to fix tuple error
        else:
            self.cursor.execute("INSERT INTO tasks (name) VALUES (?)", (task_name,))
            self.conn.commit()
            return self.cursor.lastrowid

    def add_required_skill(self, task_id, technology_id):
        """Adds a required technology/skill to a task."""
        try:
            self.cursor.execute("INSERT OR IGNORE INTO task_required_skills (task_id, technology_id) VALUES (?, ?)",
                                (task_id, technology_id))
            self.conn.commit()
        except sqlite3.IntegrityError as e:
            # Log this error appropriately
            print(f"Error adding required skill to task: {e}")

    def remove_required_skill(self, task_id, technology_id):
        """Removes a required technology/skill from a task."""
        self.cursor.execute("DELETE FROM task_required_skills WHERE task_id = ? AND technology_id = ?",
                            (task_id, technology_id))
        self.conn.commit()

    def get_required_skills(self, task_id):
        """Fetches all required technology/skill details for a given task."""
        query = """
            SELECT trs.technology_id, t.name as technology_name
            FROM task_required_skills trs
            JOIN technologies t ON trs.technology_id = t.id
            WHERE trs.task_id = ?
            ORDER BY t.name
        """
        self.cursor.execute(query, (task_id,))
        return [{"technology_id": row["technology_id"], "technology_name": row["technology_name"]} for row in self.cursor.fetchall()]

    def remove_all_required_skills(self, task_id):
        """Removes all technology/skill requirements for a given task."""
        self.cursor.execute("DELETE FROM task_required_skills WHERE task_id = ?", (task_id,))
        self.conn.commit()



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

def ensure_skill_update_log_table(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS technician_skill_update_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            technician_id INTEGER,
            technology_id INTEGER,
            task_id TEXT,
            previous_skill_level INTEGER,
            new_skill_level INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            message TEXT
        )
    ''')
    conn.commit()


def log_technician_skill_update(conn, technician_id, technology_id, task_id, previous_skill_level, new_skill_level, message):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO technician_skill_update_log (
            technician_id, technology_id, task_id, previous_skill_level, new_skill_level, message
        ) VALUES (?, ?, ?, ?, ?, ?)
    ''', (technician_id, technology_id, task_id, previous_skill_level, new_skill_level, message))
    conn.commit()
