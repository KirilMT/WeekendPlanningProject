"""
Health check service for monitoring application status.
"""
import sqlite3
import os
from datetime import datetime
from flask import current_app


class HealthChecker:
    """Centralized health checking for application components."""

    def __init__(self, app=None):
        self.app = app

    def check_database_health(self):
        """Check database connectivity and basic functionality."""
        try:
            db_path = current_app.config['DATABASE_PATH']
            if not os.path.exists(db_path):
                return False, "Database file does not exist"

            # Test connection and basic query
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            conn.close()

            if table_count < 5:  # Minimum expected tables
                return False, f"Insufficient tables found: {table_count}"

            return True, f"Database healthy with {table_count} tables"

        except Exception as e:
            return False, f"Database error: {str(e)}"

    def check_filesystem_health(self):
        """Check critical filesystem paths and permissions."""
        critical_paths = [
            current_app.config['UPLOAD_FOLDER'],
            current_app.config['OUTPUT_FOLDER'],
            current_app.config['TEMPLATES_FOLDER'],
            current_app.config['STATIC_FOLDER']
        ]

        issues = []
        for path in critical_paths:
            if not os.path.exists(path):
                issues.append(f"Missing directory: {path}")
            elif not os.access(path, os.R_OK | os.W_OK):
                issues.append(f"Permission denied: {path}")

        if issues:
            return False, "; ".join(issues)

        return True, "All filesystem paths accessible"

    def check_configuration_health(self):
        """Validate critical configuration settings."""
        try:
            # Check required config values
            required_configs = ['SECRET_KEY', 'DATABASE_PATH']
            missing = [key for key in required_configs if not current_app.config.get(key)]

            if missing:
                return False, f"Missing configuration: {', '.join(missing)}"

            # Check if in debug mode for production warning
            if current_app.config.get('FLASK_DEBUG'):
                return True, "Configuration valid (FLASK_DEBUG ACTIVE)"

            return True, "Configuration healthy"

        except Exception as e:
            return False, f"Configuration error: {str(e)}"

    def get_application_metrics(self):
        """Get basic application metrics for monitoring."""
        try:
            db_path = current_app.config['DATABASE_PATH']
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get record counts for key tables
            metrics = {}
            tables = ['technicians', 'tasks', 'technologies', 'technician_technology_skills']

            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    metrics[f"{table}_count"] = cursor.fetchone()[0]
                except sqlite3.Error:
                    metrics[f"{table}_count"] = "error"

            # Get database file size
            if os.path.exists(db_path):
                metrics['database_size_mb'] = round(os.path.getsize(db_path) / 1024 / 1024, 2)

            conn.close()
            return metrics

        except Exception as e:
            current_app.logger.error(f"Error collecting metrics: {e}")
            return {"error": str(e)}

    def perform_full_health_check(self):
        """Perform comprehensive health check of all components."""
        checks = {
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'healthy',
            'checks': {}
        }

        # Database health
        db_healthy, db_message = self.check_database_health()
        checks['checks']['database'] = {
            'status': 'healthy' if db_healthy else 'unhealthy',
            'message': db_message
        }

        # Filesystem health
        fs_healthy, fs_message = self.check_filesystem_health()
        checks['checks']['filesystem'] = {
            'status': 'healthy' if fs_healthy else 'unhealthy',
            'message': fs_message
        }

        # Configuration health
        config_healthy, config_message = self.check_configuration_health()
        checks['checks']['configuration'] = {
            'status': 'healthy' if config_healthy else 'unhealthy',
            'message': config_message
        }

        # Application metrics
        checks['metrics'] = self.get_application_metrics()

        # Overall status
        if not all([db_healthy, fs_healthy, config_healthy]):
            checks['status'] = 'unhealthy'

        return checks
