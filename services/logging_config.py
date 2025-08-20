"""
Enhanced logging configuration for the Weekend Planning Project.
"""
import logging
import os
from datetime import datetime
from config import Config


class LoggingConfig:
    """Centralized logging configuration for the application."""

    @staticmethod
    def setup_logging(app=None):
        """Configure application logging with appropriate levels and formatting."""

        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(Config.DATABASE_PATH), 'logs')
        os.makedirs(log_dir, exist_ok=True)

        # Set log level based on debug mode
        log_level = logging.DEBUG if Config.DEBUG_MODE else logging.INFO

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # Remove existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # File handler for application logs
        if not Config.DEBUG_MODE:  # Only log to file in production
            log_file = os.path.join(log_dir, 'application.log')
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

            # Error file handler
            error_log_file = os.path.join(log_dir, 'errors.log')
            error_handler = logging.FileHandler(error_log_file)
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)
            root_logger.addHandler(error_handler)

        # Configure Flask app logger if provided
        if app:
            app.logger.setLevel(log_level)

        return logging.getLogger(__name__)

    @staticmethod
    def get_logger(name):
        """Get a logger instance with the given name."""
        return logging.getLogger(name)


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
    app_logger = LoggingConfig("wkndPlanning")

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
