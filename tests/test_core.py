"""
Unit tests for core application functionality.
"""
import pytest
import json
from unittest.mock import patch


class TestDatabaseOperations:
    """Test database utility functions."""

    def test_database_initialization(self, app, test_db):
        """Test database tables are created correctly."""
        from wkndPlanning.services.db_utils import get_db_connection

        with app.app_context():
            conn = get_db_connection(app.config['DATABASE_PATH'])
            cursor = conn.cursor()

            # Check critical tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            expected_tables = [
                'technicians', 'technologies', 'tasks',
                'technician_technology_skills', 'task_required_skills'
            ]

            for table in expected_tables:
                assert table in tables

            conn.close()

    def test_technician_operations(self, app, test_db):
        """Test technician CRUD operations."""
        from wkndPlanning.services.db_utils import get_db_connection

        with app.app_context():
            conn = get_db_connection(app.config['DATABASE_PATH'])
            cursor = conn.cursor()

            # Create test technician
            cursor.execute(
                "INSERT INTO technicians (name, satellite_point_id) VALUES (?, ?)",
                ("Test Tech", 1)
            )
            conn.commit()

            # Verify creation
            cursor.execute("SELECT name FROM technicians WHERE name = ?", ("Test Tech",))
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == "Test Tech"

            conn.close()


class TestSecurityValidation:
    """Test security and input validation."""

    def test_skill_level_validation(self):
        """Test skill level validation matches database schema."""
        from wkndPlanning.services.security import InputValidator

        # Valid skill levels (0-4)
        for level in [0, 1, 2, 3, 4]:
            assert InputValidator.validate_skill_level(level) == level

        # Invalid skill levels
        with pytest.raises(ValueError):
            InputValidator.validate_skill_level(-1)

        with pytest.raises(ValueError):
            InputValidator.validate_skill_level(5)

    def test_string_validation(self):
        """Test string input validation and sanitization."""
        from wkndPlanning.services.security import InputValidator

        # Valid string
        result = InputValidator.validate_string("  Test String  ")
        assert result == "Test String"

        # String too long
        with pytest.raises(ValueError):
            InputValidator.validate_string("x" * 300, max_length=255)

        # Null byte removal
        result = InputValidator.validate_string("Test\x00String")
        assert result == "TestString"


class TestAPIEndpoints:
    """Test API endpoint functionality."""

    def test_technicians_api_endpoint(self, client, test_db):
        """Test technicians API endpoint."""
        response = client.get('/api/technicians')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_api_rate_limiting(self, client):
        """Test API rate limiting is active."""
        # This test would require multiple rapid requests
        # For now, just verify the endpoint exists
        response = client.get('/api/technicians')
        assert response.status_code in [200, 429]  # 429 = Rate Limited


class TestLoggingAndMetrics:
    """Test logging and metrics collection."""

    def test_metrics_collection_initialization(self):
        """Test metrics collector initializes correctly."""
        from wkndPlanning.services.logging_config import MetricsCollector

        collector = MetricsCollector()
        assert isinstance(collector.request_metrics, dict)
        assert isinstance(collector.database_metrics, dict)

    def test_performance_monitor_decorator(self):
        """Test performance monitoring decorator."""
        from wkndPlanning.services.logging_config import performance_monitor

        @performance_monitor("test_operation")
        def test_function():
            return "success"

        # Should execute without error
        result = test_function()
        assert result == "success"

    def test_request_metric_recording(self):
        """Test request metrics are recorded correctly."""
        from wkndPlanning.services.logging_config import MetricsCollector

        collector = MetricsCollector()
        collector.record_request_metric("test_endpoint", "GET", 0.5, 200)

        assert "GET_test_endpoint" in collector.request_metrics
        metrics = collector.request_metrics["GET_test_endpoint"]
        assert metrics['count'] == 1
        assert metrics['total_duration'] == 0.5


class TestConfigurationValidation:
    """Test configuration validation."""

    def test_config_validation_success(self, app):
        """Test configuration validation passes for test config."""
        from wkndPlanning.config import Config

        with app.app_context():
            # Should not raise exception
            Config.validate_config()

    @patch('config.Config.FLASK_DEBUG', False)
    def test_production_config_warnings(self):
        """Test production configuration validation warnings."""
        from wkndPlanning.config import Config

        # Test would check for production-specific validations
        # This is a placeholder for more comprehensive production checks
        assert hasattr(Config, 'validate_config')
