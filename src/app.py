import os
import sys
from flask import Flask, g, jsonify
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from jinja2 import Environment, FileSystemLoader

# Add project root to sys.path to allow importing config
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.config import Config

# Import from local services package (relative to src)
from .services.security import SecurityMiddleware
from .services.logging_config import LoggingConfig

# Import Blueprints
from .routes.main import main_bp
from .routes.api import api_bp
from .routes.health import health_bp
from .extensions import db_manager

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

    db_manager.init_app(app)

    DATABASE_PATH = app.config['DATABASE_PATH']

    # Jinja environment for generate_html_files
    env = Environment(loader=FileSystemLoader(app.config['TEMPLATES_FOLDER']))

    # Register Blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(health_bp)

    # Configure CSRF exemptions after blueprint registration
    csrf.exempt(main_bp)
    csrf.exempt(api_bp)

    # Security middleware
    @app.after_request
    def after_request(response):
        return SecurityMiddleware.add_security_headers(response)
    @app.errorhandler(404)
    def not_found(error):
        from flask import request
        app.logger.warning(f"404 Not Found: The requested URL '{request.path}' was not found on the server.")
        return f"Page not found: {request.path}", 404

    @app.errorhandler(400)
    def handle_400_error(error):
        response = jsonify({
            "message": "Bad request",
            "details": str(error)
        })
        response.status_code = 400
        return response

    @app.errorhandler(500)
    def handle_500_error(error):
        response = jsonify({
            "message": "Internal server error",
            "details": str(error)
        })
        response.status_code = 500
        return response

    return app

app = create_app()
