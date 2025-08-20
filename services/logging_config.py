"""
Enhanced logging configuration for the Weekend Planning Project.
"""
import logging
import logging.handlers
import os
from datetime import datetime


class ApplicationLogger:
    """Centralized logging configuration with rotation and structured formatting."""

    def __init__(self, app_name: str = "wkndPlanning", log_dir: str = None):
        self.app_name = app_name
        self.log_dir = log_dir or os.path.join(os.path.dirname(__file__), '..', 'logs')
        os.makedirs(self.log_dir, exist_ok=True)

    def setup_logging(self, log_level: str = "INFO", enable_file_logging: bool = True):
        """Configure application logging with both console and file handlers."""

        # Create logger
        logger = logging.getLogger(self.app_name)
        logger.setLevel(getattr(logging, log_level.upper()))

        # Clear existing handlers
        logger.handlers.clear()

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s'
        )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        if enable_file_logging:
            # File handler with rotation
            log_file = os.path.join(self.log_dir, f'{self.app_name}.log')
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=10*1024*1024, backupCount=5  # 10MB files, keep 5 backups
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            # Error file handler
            error_file = os.path.join(self.log_dir, f'{self.app_name}_errors.log')
            error_handler = logging.handlers.RotatingFileHandler(
                error_file, maxBytes=10*1024*1024, backupCount=5
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)
            logger.addHandler(error_handler)

        return logger


class DatabaseOperationLogger:
    """Specialized logger for database operations and performance monitoring."""

    def __init__(self, logger):
        self.logger = logger

    def log_query_performance(self, query: str, execution_time: float, row_count: int = None):
        """Log database query performance metrics."""
        message = f"DB Query executed in {execution_time:.3f}s"
        if row_count is not None:
            message += f" (returned {row_count} rows)"

        if execution_time > 1.0:  # Log slow queries as warnings
            self.logger.warning(f"SLOW QUERY: {message} - Query: {query[:100]}...")
        else:
            self.logger.debug(f"{message} - Query: {query[:100]}...")

    def log_transaction(self, operation: str, table: str, record_id: int = None):
        """Log database transaction operations."""
        message = f"DB {operation.upper()} on {table}"
        if record_id:
            message += f" (ID: {record_id})"
        self.logger.info(message)


def setup_app_logging(app, config):
    """Setup logging for Flask application."""
    app_logger = ApplicationLogger("wkndPlanning")

    # Determine log level from config
    log_level = "DEBUG" if config.DEBUG_MODE else "INFO"

    # Setup logging
    logger = app_logger.setup_logging(log_level)

    # Configure Flask's logger
    app.logger.handlers = logger.handlers
    app.logger.setLevel(logger.level)

    # Add request logging
    @app.before_request
    def log_request_info():
        from flask import request
        app.logger.debug(f"Request: {request.method} {request.url}")

    @app.after_request
    def log_response_info(response):
        app.logger.debug(f"Response: {response.status_code}")
        return response

    return logger
