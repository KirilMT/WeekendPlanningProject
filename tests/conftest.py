"""
Test configuration and fixtures for the Weekend Planning Project.
"""
import pytest
import os
import tempfile
import sqlite3
from unittest.mock import patch
from wkndPlanning.app import create_app
from wkndPlanning.services.db_utils import init_db
from config import Config


class TestConfig(Config):
    """Test-specific configuration."""
    TESTING = True
    DEBUG_MODE = True
    WTF_CSRF_ENABLED = False  # Disable CSRF for testing

    # Use in-memory database for tests
    @property
    def DATABASE_PATH(self):
        return ':memory:'


@pytest.fixture
def app():
    """Create and configure a test app instance."""
    # Create a temporary file for test database
    db_fd, db_path = tempfile.mkstemp(suffix='.db')

    # Patch the config to use test database
    with patch.object(Config, 'DATABASE_PATH', db_path):
        app = create_app()
        app.config.from_object(TestConfig)
        app.config['DATABASE_PATH'] = db_path

        with app.app_context():
            # Initialize test database
            init_db(db_path)

        yield app

    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()


@pytest.fixture
def test_db(app):
    """Provide a clean database for each test."""
    with app.app_context():
        # Database is already initialized in app fixture
        yield
        # Could add cleanup here if needed


@pytest.fixture
def sample_technician_data():
    """Sample technician data for testing."""
    return {
        'name': 'Test Technician',
        'satellite_point_id': 1,
        'skills': {
            1: 3,  # technology_id: skill_level
            2: 4,
            3: 2
        }
    }


@pytest.fixture
def sample_task_data():
    """Sample task data for testing."""
    return {
        'name': 'Test Task',
        'required_skills': [1, 2],  # technology_ids
        'quantity': 2,
        'duration': 120  # minutes
    }
