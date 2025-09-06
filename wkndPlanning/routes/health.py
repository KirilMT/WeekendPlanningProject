"""
Health check routes for application monitoring.
"""
from flask import Blueprint, jsonify, current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from ..services.health_check import HealthChecker
from ..services.logging_config import LoggingConfig
import os

health_bp = Blueprint('health', __name__, url_prefix='/health')

# Create a separate limiter instance for health checks with more permissive limits
health_limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per minute", "1000 per hour"]
)

@health_bp.route('/', methods=['GET'])
@health_limiter.limit("30 per minute")
def health_check():
    """
    Basic health check endpoint for load balancers and monitoring systems.
    Returns 200 OK if application is healthy, 503 if unhealthy.
    """
    try:
        checker = HealthChecker()
        result = checker.perform_full_health_check()

        status_code = 200 if result['status'] == 'healthy' else 503

        # Log unhealthy status for monitoring
        if result['status'] == 'unhealthy':
            current_app.logger.warning(f"Health check failed: {result}")

        return jsonify(result), status_code

    except Exception as e:
        current_app.logger.error(f"Health check endpoint error: {e}", exc_info=True)
        return jsonify({
            'status': 'unhealthy',
            'error': 'Health check system failure',
            'timestamp': None
        }), 503

@health_bp.route('/ready', methods=['GET'])
@health_limiter.limit("60 per minute")
def readiness_check():
    """
    Kubernetes-style readiness probe.
    Checks if application is ready to receive traffic.
    """
    try:
        checker = HealthChecker()

        # Quick checks for readiness
        db_healthy, _ = checker.check_database_health()
        config_healthy, _ = checker.check_configuration_health()

        if db_healthy and config_healthy:
            return jsonify({
                'status': 'ready',
                'timestamp': checker.perform_full_health_check()['timestamp']
            }), 200
        else:
            return jsonify({
                'status': 'not_ready',
                'timestamp': checker.perform_full_health_check()['timestamp']
            }), 503

    except Exception as e:
        current_app.logger.error(f"Readiness check error: {e}")
        return jsonify({'status': 'not_ready'}), 503

@health_bp.route('/live', methods=['GET'])
@health_limiter.limit("60 per minute")
def liveness_check():
    """
    Kubernetes-style liveness probe.
    Checks if application process is alive and responsive.
    """
    return jsonify({
        'status': 'alive',
        'service': 'weekend-planning-app'
    }), 200

@health_bp.route('/metrics', methods=['GET'])
@health_limiter.limit("10 per minute")
def metrics_endpoint():
    """
    Application metrics endpoint for monitoring systems.
    Combines health metrics with performance metrics.
    """
    try:
        checker = HealthChecker()
        health_metrics = checker.get_application_metrics()
        performance_metrics = LoggingConfig.get_metrics()

        return jsonify({
            'health_metrics': health_metrics,
            'performance_metrics': performance_metrics,
            'timestamp': checker.perform_full_health_check()['timestamp']
        }), 200

    except Exception as e:
        current_app.logger.error(f"Metrics endpoint error: {e}")
        return jsonify({'error': 'Metrics collection failed'}), 500

@health_bp.route('/debug', methods=['GET'])
@health_limiter.limit("5 per minute")
def debug_info():
    """
    Debug information endpoint (only available in debug mode).
    """
    if not current_app.config.get('FLASK_DEBUG'):
        return jsonify({'error': 'Debug endpoint not available in production'}), 403

    try:
        import sys
        import platform

        debug_info = {
            'python_version': sys.version,
            'platform': platform.platform(),
            'flask_config': {
                key: str(value) for key, value in current_app.config.items()
                if not key.startswith('SECRET')
            },
            'environment_variables': {
                key: value for key, value in os.environ.items()
                if not any(secret in key.lower() for secret in ['secret', 'key', 'password', 'token'])
            }
        }

        return jsonify(debug_info), 200

    except Exception as e:
        current_app.logger.error(f"Debug endpoint error: {e}")
        return jsonify({'error': 'Debug info collection failed'}), 500
