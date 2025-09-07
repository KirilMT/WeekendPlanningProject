import os
import sys
from flask import Flask, g
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from jinja2 import Environment, FileSystemLoader

# Add project root to sys.path to allow importing config
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config import Config

# Import from local services package (relative to wkndPlanning)
from .services.db_utils import get_db_connection, init_db
from .services.config_manager import load_app_config
from .services.security import SecurityMiddleware
from .services.logging_config import LoggingConfig

# Import Blueprints
from .routes.main import main_bp
from .routes.api import api_bp
from .routes.health import health_bp

def create_app():
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')
    app.config.from_object(Config)

    # Validate configuration before proceeding
    try:
        Config.validate_config()
    except ValueError as e:
        print(f"Configuration Error: {e}")
        raise

    # Setup logging first
    logger = LoggingConfig.setup_logging(app)
    app.logger = logger

    # Initialize security extensions
    csrf = CSRFProtect(app)

    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://"
    )

    DATABASE_PATH = app.config['DATABASE_PATH']

    # Jinja environment for generate_html_files
    env = Environment(loader=FileSystemLoader(app.config['TEMPLATES_FOLDER']))

    # Register Blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(health_bp)

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

        # Log any exceptions that occurred during request processing
        if exception is not None:
            app.logger.error(f"Request exception: {str(exception)}", exc_info=True)

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        app.logger.warning(f"404 error: {error}")
        return "Page not found", 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"500 error: {error}", exc_info=True)
        return "Internal server error", 500

    # Only initialize database and config if we're in the main reloader process
    # This prevents double initialization when Flask's auto-reloader is enabled
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        with app.app_context():
            try:
                init_db(DATABASE_PATH, app.logger, app.config['DEBUG_USE_TEST_DB'])
                load_app_config(DATABASE_PATH, app.logger)
                app.logger.info("Application initialized successfully")
            except Exception as e:
                app.logger.error(f"Failed to initialize application: {e}", exc_info=True)
                raise

    return app

app = create_app()
