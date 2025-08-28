# AI Assistant Instructions for WeekendPlanningProject

This document provides instructions for an AI assistant to help it provide the best possible assistance for this project.

## Project Overview

This project, `wkndPlanning`, is a web application built with a Flask backend (Python) and vanilla JavaScript for the frontend. Its primary purpose is to manage and assign tasks to technicians based on their skills.

## Core Architectural Shift

The project is transitioning from a simple task priority-based system to a more sophisticated **technology skill-based system** for task assignments. This is the most critical context for any code modifications.

-   **Database Impact**: The `technician_task_assignments.priority` column is obsolete. The new schema requires a many-to-many relationship between tasks and the technologies/skills required to perform them.
-   **Logic Impact**: The core assignment logic in `task_assigner.py` must now prioritize matching task skill requirements with technician skill sets.

## Key Files

-   **Backend (Python)**:
    -   `wkndPlanning/app.py`: Main application file containing Flask routes and API endpoints.
    -   `wkndPlanning/services/db_utils.py`: Defines the database schema (SQLite) and handles all database operations.
    -   `wkndPlanning/services/task_assigner.py`: Contains the core business logic for assigning tasks to technicians.
    -   `wkndPlanning/services/config_manager.py`: Manages application configuration.
-   **Frontend (HTML/JavaScript)**:
    -   `wkndPlanning/templates/manage_mappings.html`: The main user interface for managing tasks, technicians, and skills.
    -   `wkndPlanning/static/js/manage_mappings_*.js`: A collection of JavaScript files that provide interactivity for the `manage_mappings.html` page.

## Development Guidelines

-   **When modifying `db_utils.py`**:
    -   Clearly state any Data Definition Language (DDL) changes (e.g., `CREATE TABLE`, `ALTER TABLE`).
    -   Ensure functions managing the new `task_required_skills` relationship are robust and efficient.

-   **When modifying `app.py`**:
    -   Update API endpoints (e.g., `/api/get_technician_mappings`, `/api/tasks`) to handle skill-based data.
    -   Ensure all data passed to templates or returned by APIs includes the necessary skill information.

-   **When modifying `task_assigner.py`**:
    -   The primary focus is the new skill-based assignment logic.
    -   Group selection must be based on skill coverage, average skill level, and tie-breakers (like workload).
    -   Implement time adjustments based on team size: `new_duration = (original_duration * required_technicians) / assigned_technicians`.

-   **When modifying the frontend**:
    -   The UI must allow for managing multiple skills per task.
    -   UI elements related to the old numerical priority system should be removed.
    -   Ensure the UI dynamically reflects backend data changes.

-   **General Rules**:
    -   For new features or refactoring in the `wkndPlanning/services/` directory, a class-based architecture is strongly preferred.
    -   Do not add `print()` statements or other temporary debugging logs to the final code.
    -   Follow existing file naming conventions, especially for new JavaScript files (e.g., `manage_mappings_[feature_name].js`).
    -   Be mindful that key data points (like `mitarbeiter_pro_aufgabe` and task duration) are integrated from Excel files.
