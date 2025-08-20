import os
import sys
from flask import Flask, g
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from jinja2 import Environment, FileSystemLoader
import logging

# Add project root to sys.path to allow importing config
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config import Config

# Import from local services package (relative to wkndPlanning)
from .services.db_utils import get_db_connection, init_db
from .services.config_manager import load_app_config
from .services.security import SecurityMiddleware

# Import Blueprints
from .routes.main import main_bp
from .routes.api import api_bp

def create_app():
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')
    app.config.from_object(Config)

    # Validate configuration
    Config.validate_config()

    # Initialize security extensions
    csrf = CSRFProtect(app)

    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://"
    )

    DATABASE_PATH = app.config['DATABASE_PATH']

    app.logger.setLevel(logging.DEBUG)

    # Jinja environment for generate_html_files
    env = Environment(loader=FileSystemLoader(app.config['TEMPLATES_FOLDER']))

    # Register Blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    # Configure CSRF exemptions after blueprint registration
    csrf.exempt(main_bp)

    # Security middleware
    @app.after_request
    def after_request(response):
        return SecurityMiddleware.add_security_headers(response)

    # Database connection management using Flask's application context
    @app.before_request
    def before_request():
        """Open a database connection before each request."""
        if 'db' not in g:
            g.db = get_db_connection(DATABASE_PATH)

    @app.teardown_request
    def teardown_request(exception=None):
        """Close the database connection at the end of each request."""
        db = g.pop('db', None)
        if db is not None:
            db.close()

    # Only initialize database and config if we're in the main reloader process
    # This prevents double initialization when Flask's auto-reloader is enabled
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        with app.app_context():
            init_db(DATABASE_PATH, app.logger)
            load_app_config(DATABASE_PATH, app.logger)

    return app

app = create_app()
