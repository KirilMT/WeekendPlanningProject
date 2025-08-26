import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
WKND_PLANNING_DIR = os.path.join(BASE_DIR, 'wkndPlanning')

class Config:
    """
    Application configuration class with environment variable support.

    This class centralizes all configuration settings and provides secure defaults
    for development while requiring proper configuration for production.
    """

    # --- Core Secrets / Flags ---
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

    # Global debug mode toggle (string env values '1', 'true', 'True')
    DEBUG_MODE = os.environ.get('DEBUG_MODE', '0').lower() in ('1', 'true', 'yes')

    # Optional separate flag just to force using test DB without enabling all debug behaviors
    DEBUG_USE_TEST_DB = os.environ.get('DEBUG_USE_TEST_DB', '0').lower() in ('1', 'true', 'yes')

    # Optional fixed date (ISO formats e.g. '2025-04-19' or '2025-04-19T16:00:00') used by services when DEBUG_MODE active
    DEBUG_FIXED_DATE = os.environ.get('DEBUG_FIXED_DATE')  # parsed lazily where needed

    # --- Flask-WTF Configuration ---
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = int(os.environ.get('CSRF_TIME_LIMIT', '3600'))  # 1 hour default
    WTF_CSRF_SSL_STRICT = not DEBUG_MODE  # Disable SSL requirement in debug mode

    # --- Security Configuration ---
    PERMANENT_SESSION_LIFETIME = int(os.environ.get('SESSION_LIFETIME', '1800'))  # 30 minutes default
    SESSION_COOKIE_SECURE = not DEBUG_MODE  # Only send cookies over HTTPS in production
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # --- Database Configuration ---
    # Determine the database filename based on environment settings.
    # Priority:
    # 1. DATABASE_FILENAME environment variable (for explicit override).
    # 2. 'testsDB.db' if in debug mode or if test DB is forced.
    # 3. 'weekend_planning.db' as the default production database.
    if 'DATABASE_FILENAME' in os.environ:
        _db_filename = os.environ['DATABASE_FILENAME']
    elif DEBUG_MODE or DEBUG_USE_TEST_DB:
        _db_filename = 'testsDB.db'
    else:
        _db_filename = 'weekend_planning.db'

    # The database is located inside the 'wkndPlanning' package directory.
    DATABASE_PATH = os.path.join(WKND_PLANNING_DIR, _db_filename)

    # --- Paths ---
    UPLOAD_FOLDER = os.path.join(WKND_PLANNING_DIR, 'uploads')
    OUTPUT_FOLDER = os.path.join(WKND_PLANNING_DIR, 'output')
    TEMPLATES_FOLDER = os.path.join(WKND_PLANNING_DIR, 'templates')
    STATIC_FOLDER = os.path.join(WKND_PLANNING_DIR, 'static')

    # File upload restrictions
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_UPLOAD_SIZE', '16777216'))  # 16MB default
    ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'xlsb', 'csv'}

    # Ensure these directories exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    @classmethod
    def is_debug(cls):
        """Check if application is in debug mode."""
        return cls.DEBUG_MODE

    @classmethod
    def get_fixed_datetime(cls):
        """Return a datetime override if DEBUG_MODE and a fixed date is set; else None.
        If DEBUG_FIXED_DATE not set but DEBUG_MODE is true, returns canonical test date.
        """
        if not cls.DEBUG_MODE:
            return None
        from datetime import datetime
        if cls.DEBUG_FIXED_DATE:
            try:
                return datetime.fromisoformat(cls.DEBUG_FIXED_DATE)
            except ValueError:
                # Fall back to canonical date if parse fails
                pass
        # Canonical fallback debug date/time
        return datetime(2025, 4, 19, 16, 0, 0)

    @classmethod
    def validate_config(cls):
        """Validate critical configuration settings."""
        errors = []

        # Check if SECRET_KEY is properly set in production
        if not cls.DEBUG_MODE and cls.SECRET_KEY == secrets.token_hex(32):
            errors.append("SECRET_KEY should be explicitly set in production")

        # Validate file upload size
        if cls.MAX_CONTENT_LENGTH > 50 * 1024 * 1024:  # 50MB
            errors.append("MAX_CONTENT_LENGTH seems too large (>50MB)")

        # Check database path accessibility
        import os
        db_dir = os.path.dirname(cls.DATABASE_PATH)
        if not os.path.exists(db_dir):
            errors.append(f"Database directory does not exist: {db_dir}")

        if errors:
            raise ValueError("Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors))
