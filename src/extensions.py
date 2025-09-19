from flask import g
from .services.db_utils import get_db_connection, init_db, ensure_skill_update_log_table
from .services.config_manager import load_app_config

class DatabaseManager:
    def __init__(self):
        self.app = None
        self.database_path = None

    def init_app(self, app):
        self.app = app
        self.database_path = app.config['DATABASE_PATH']

        @app.before_request
        def before_request():
            if 'db' not in g:
                g.db = self.get_db()

        @app.teardown_request
        def teardown_request(exception=None):
            db = g.pop('db', None)
            if db is not None:
                db.close()
            if exception is not None:
                app.logger.error(f"Request exception: {str(exception)}", exc_info=True)

        # Initial database setup
        with app.app_context():
            try:
                init_db(self.database_path, app.logger, app.config['DEBUG_USE_TEST_DB'])
                conn = self.get_db()
                ensure_skill_update_log_table(conn)
                load_app_config(self.database_path, app.logger)
                conn.close()
                app.logger.info("Database initialized successfully via extensions.")
            except Exception as e:
                app.logger.error(f"Failed to initialize database via extensions: {e}", exc_info=True)
                raise

    def get_db(self):
        """Opens a new database connection if there is none yet for the current application context."""
        if 'db' not in g:
            g.db = get_db_connection(self.database_path)
        return g.db

db_manager = DatabaseManager()
