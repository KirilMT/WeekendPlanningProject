"""
Enhanced logging configuration for the Weekend Planning Project.
"""
import logging
import os
import json
import time
from datetime import datetime
from functools import wraps
from flask import request, g, current_app
from src.config import Config


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging in production."""

    def format(self, record):
        log_entry = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }

        # Add request context if available
        try:
            if request:
                log_entry['request'] = {
                    'method': request.method,
                    'path': request.path,
                    'remote_addr': request.remote_addr,
                    'user_agent': str(request.user_agent)
                }
        except RuntimeError:
            # Outside request context
            pass

        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class MetricsCollector:
    """Collects application performance metrics."""

    def __init__(self):
        self.request_metrics = {}
        self.database_metrics = {}

    def record_request_metric(self, endpoint, method, duration, status_code):
        """Record request timing and status metrics."""
        key = f"{method}_{endpoint}"
        if key not in self.request_metrics:
            self.request_metrics[key] = {
                'count': 0,
                'total_duration': 0,
                'avg_duration': 0,
                'status_codes': {}
            }

        metrics = self.request_metrics[key]
        metrics['count'] += 1
        metrics['total_duration'] += duration
        metrics['avg_duration'] = metrics['total_duration'] / metrics['count']

        # Track status codes
        if status_code not in metrics['status_codes']:
            metrics['status_codes'][status_code] = 0
        metrics['status_codes'][status_code] += 1

    def record_database_metric(self, operation, duration, success=True):
        """Record database operation metrics."""
        if operation not in self.database_metrics:
            self.database_metrics[operation] = {
                'count': 0,
                'total_duration': 0,
                'avg_duration': 0,
                'success_count': 0,
                'error_count': 0
            }

        metrics = self.database_metrics[operation]
        metrics['count'] += 1
        metrics['total_duration'] += duration
        metrics['avg_duration'] = metrics['total_duration'] / metrics['count']

        if success:
            metrics['success_count'] += 1
        else:
            metrics['error_count'] += 1

    def get_all_metrics(self):
        """Get all collected metrics."""
        return {
            'requests': self.request_metrics,
            'database': self.database_metrics,
            'collection_time': datetime.utcnow().isoformat()
        }


# Global metrics collector instance
metrics_collector = MetricsCollector()


def performance_monitor(operation_name):
    """Decorator to monitor function performance."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start_time
                if 'db' in operation_name.lower() or 'database' in operation_name.lower():
                    metrics_collector.record_database_metric(operation_name, duration, success)

                # Log slow operations
                if duration > 1.0:  # Operations taking more than 1 second
                    current_app.logger.warning(
                        f"Slow operation detected: {operation_name} took {duration:.2f}s"
                    )
        return wrapper
    return decorator


class LoggingConfig:
    """Centralized logging configuration for the application."""

    @staticmethod
    def setup_logging(app=None):
        """Configure application logging with appropriate levels and formatting."""

        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(Config.DATABASE_PATH), 'logs')
        os.makedirs(log_dir, exist_ok=True)

        # Set log level based on debug mode
        log_level = logging.DEBUG if Config.FLASK_DEBUG else logging.INFO

        # Create formatters
        if Config.FLASK_DEBUG:
            # Human-readable format for development
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        else:
            # Structured JSON format for production
            formatter = StructuredFormatter()

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

        # File handlers
        log_file = os.path.join(log_dir, 'application.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # Error-specific log file
        error_log_file = os.path.join(log_dir, 'errors.log')
        error_handler = logging.FileHandler(error_log_file)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)

        # Performance log file for production
        if not Config.FLASK_DEBUG:
            perf_log_file = os.path.join(log_dir, 'performance.log')
            perf_handler = logging.FileHandler(perf_log_file)
            perf_handler.setLevel(logging.WARNING)  # For slow operations
            perf_handler.setFormatter(formatter)
            root_logger.addHandler(perf_handler)

        # Set up request timing middleware if app is provided
        if app:
            LoggingConfig._setup_request_monitoring(app)

        return root_logger

    @staticmethod
    def _setup_request_monitoring(app):
        """Set up request timing and monitoring middleware."""

        @app.before_request
        def before_request():
            g.start_time = time.time()

        @app.after_request
        def after_request(response):
            if hasattr(g, 'start_time'):
                duration = time.time() - g.start_time

                # Record metrics
                metrics_collector.record_request_metric(
                    request.endpoint or 'unknown',
                    request.method,
                    duration,
                    response.status_code
                )

                # Log slow requests
                if duration > 2.0:  # Requests taking more than 2 seconds
                    app.logger.warning(
                        f"Slow request: {request.method} {request.path} took {duration:.2f}s"
                    )

                # Add performance headers for debugging
                if Config.FLASK_DEBUG:
                    response.headers['X-Response-Time'] = f"{duration:.3f}s"

            return response

    @staticmethod
    def get_metrics():
        """Get current application metrics."""
        return metrics_collector.get_all_metrics()
