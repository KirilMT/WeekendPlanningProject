"""
Weekend Planning Project - src Package

A Flask-based web application for managing weekend technician task assignments
based on skill-based matching and workload optimization.
"""

__version__ = "1.0.0"
__author__ = "Weekend Planning Team"

# Package-level imports for easier access
from .app import create_app

__all__ = ['create_app']
