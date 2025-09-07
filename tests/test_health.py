"""
Unit tests for health check endpoints and monitoring functionality.
"""
import pytest
import json
from unittest.mock import patch, MagicMock


class TestHealthEndpoints:
    """Test health check and monitoring endpoints."""

    def test_health_check_healthy(self, client, test_db):
        """Test health check endpoint when application is healthy."""
        response = client.get('/health/')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert 'timestamp' in data
        assert 'checks' in data
        assert 'metrics' in data

    def test_liveness_check(self, client):
        """Test liveness probe endpoint."""
        response = client.get('/health/live')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['status'] == 'alive'
        assert data['service'] == 'weekend-planning-app'

    def test_readiness_check_ready(self, client, test_db):
        """Test readiness probe when application is ready."""
        response = client.get('/health/ready')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['status'] == 'ready'

    def test_metrics_endpoint(self, client, test_db):
        """Test metrics collection endpoint."""
        response = client.get('/health/metrics')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'health_metrics' in data
        assert 'performance_metrics' in data
        assert 'timestamp' in data

    def test_debug_endpoint_in_flask_debug_mode(self, client):
        """Test debug endpoint accessibility in debug mode."""
        response = client.get('/health/debug')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'python_version' in data
        assert 'platform' in data

    @patch('wkndPlanning.routes.health.current_app')
    def test_debug_endpoint_in_production(self, mock_app, client):
        """Test debug endpoint is blocked in production mode."""
        mock_app.config.get.return_value = False  # FLASK_DEBUG = False

        response = client.get('/health/debug')
        assert response.status_code == 403

        data = json.loads(response.data)
        assert 'error' in data
        assert 'not available in production' in data['error']

    @patch('wkndPlanning.services.health_check.HealthChecker.check_database_health')
    def test_health_check_unhealthy_database(self, mock_db_check, client):
        """Test health check when database is unhealthy."""
        mock_db_check.return_value = (False, "Database connection failed")

        response = client.get('/health/')
        assert response.status_code == 503

        data = json.loads(response.data)
        assert data['status'] == 'unhealthy'


class TestHealthChecker:
    """Test the HealthChecker class functionality."""

    def test_database_health_check_success(self, app):
        """Test successful database health check."""
        from wkndPlanning.services.health_check import HealthChecker

        with app.app_context():
            checker = HealthChecker()
            healthy, message = checker.check_database_health()

            assert healthy is True
            assert "healthy" in message.lower()

    def test_filesystem_health_check_success(self, app):
        """Test successful filesystem health check."""
        from wkndPlanning.services.health_check import HealthChecker

        with app.app_context():
            checker = HealthChecker()
            healthy, message = checker.check_filesystem_health()

            assert healthy is True
            assert "accessible" in message.lower()

    def test_configuration_health_check_success(self, app):
        """Test successful configuration health check."""
        from wkndPlanning.services.health_check import HealthChecker

        with app.app_context():
            checker = HealthChecker()
            healthy, message = checker.check_configuration_health()

            assert healthy is True
            assert "healthy" in message.lower()

    def test_get_application_metrics(self, app, test_db):
        """Test application metrics collection."""
        from wkndPlanning.services.health_.health_check import HealthChecker

        with app.app_context():
            checker = HealthChecker()
            metrics = checker.get_application_metrics()

            assert isinstance(metrics, dict)
            assert 'technicians_count' in metrics
            assert 'tasks_count' in metrics
            assert 'technologies_count' in metrics
