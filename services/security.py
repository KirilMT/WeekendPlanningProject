"""
Security utilities for input validation and sanitization.
"""
from functools import wraps
from flask import request, jsonify, current_app
import re
from typing import Any, Dict, List, Optional, Union


class InputValidator:
    """Centralized input validation and sanitization utilities."""

    @staticmethod
    def validate_integer(value: Any, min_val: int = None, max_val: int = None) -> int:
        """Validate and convert input to integer with optional range checking."""
        try:
            int_val = int(value)
            if min_val is not None and int_val < min_val:
                raise ValueError(f"Value {int_val} is less than minimum {min_val}")
            if max_val is not None and int_val > max_val:
                raise ValueError(f"Value {int_val} is greater than maximum {max_val}")
            return int_val
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid integer value: {value}") from e

    @staticmethod
    def validate_string(value: Any, max_length: int = 255, pattern: str = None) -> str:
        """Validate and sanitize string input."""
        if not isinstance(value, str):
            raise ValueError(f"Expected string, got {type(value)}")

        # Basic sanitization - remove null bytes and excessive whitespace
        sanitized = value.replace('\x00', '').strip()

        if len(sanitized) > max_length:
            raise ValueError(f"String too long: {len(sanitized)} > {max_length}")

        if pattern and not re.match(pattern, sanitized):
            raise ValueError(f"String does not match required pattern")

        return sanitized

    @staticmethod
    def validate_technician_id(tech_id: Any) -> int:
        """Validate technician ID."""
        return InputValidator.validate_integer(tech_id, min_val=1)

    @staticmethod
    def validate_task_id(task_id: Any) -> int:
        """Validate task ID."""
        return InputValidator.validate_integer(task_id, min_val=1)

    @staticmethod
    def validate_skill_level(level: Any) -> int:
        """Validate skill level (1-5)."""
        return InputValidator.validate_integer(level, min_val=1, max_val=5)

    @staticmethod
    def validate_json_request(required_fields: List[str] = None) -> Dict:
        """Validate JSON request and check for required fields."""
        if not request.is_json:
            raise ValueError("Request must be JSON")

        data = request.get_json()
        if not isinstance(data, dict):
            raise ValueError("JSON must be an object")

        if required_fields:
            missing = [field for field in required_fields if field not in data]
            if missing:
                raise ValueError(f"Missing required fields: {missing}")

        return data


def validate_request(*validation_rules):
    """Decorator for API endpoint input validation."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Apply validation rules
                for rule in validation_rules:
                    rule()
                return f(*args, **kwargs)
            except ValueError as e:
                current_app.logger.warning(f"Validation error in {f.__name__}: {e}")
                return jsonify({"error": str(e)}), 400
            except Exception as e:
                current_app.logger.error(f"Unexpected error in {f.__name__}: {e}", exc_info=True)
                return jsonify({"error": "Internal server error"}), 500
        return decorated_function
    return decorator


def require_json_fields(*fields):
    """Validation rule for required JSON fields."""
    def validation():
        InputValidator.validate_json_request(list(fields))
    return validation


def validate_tech_id_param():
    """Validation rule for technician_id parameter."""
    def validation():
        tech_id = request.args.get('technician_id') or request.json.get('technician_id')
        if tech_id is not None:
            InputValidator.validate_technician_id(tech_id)
    return validation


def rate_limit_key():
    """Generate rate limiting key based on IP and user agent."""
    return f"{request.remote_addr}:{hash(request.user_agent.string) % 10000}"


class SecurityMiddleware:
    """Security middleware for additional protection."""

    @staticmethod
    def add_security_headers(response):
        """Add security headers to response."""
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response
