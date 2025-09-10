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
    -   **Documentation Update Requirement:** When working on issues, before committing and pushing, update documentation files (README.md, AGENT.md, copilot-instructions.md, and any other relevant files) to reflect all changes.

## Project Structure

```
WeekendPlanningProject/
├── wkndPlanning/                  # Main application package
│   ├── routes/                    # Flask blueprints and routing
│   ├── services/                  # Business logic and utilities (core logic here)
│   ├── static/                    # CSS, JavaScript, and static assets
│   ├── templates/                 # Jinja2 HTML templates
│   ├── app.py                     # Flask application factory
│   ├── testsDB.db                 # SQLite test database
│   ├── weekend_planning.db        # Main SQLite database
│   ├── logs/                      # Application and error logs
│   ├── output/                    # Generated HTML outputs
├── config.py                      # Application configuration
├── requirements.txt               # Python dependencies
├── run.py                         # Application entry point
├── README.md                      # Project documentation
├── ROADMAP.md                     # Development roadmap and future plans
├── issues.md                      # Issue tracking and prioritization
├── technician_dashboard_manual.md # Manual for technician dashboard usage
├── dummy_data.json                # Dummy data for testing
├── Dockerfile                     # Docker container configuration
├── docker-compose.yml             # Docker Compose setup
├── Excels_Testing/                # Excel files for testing and import
├── tests/                         # Pytest-based unit and integration tests
├── uploads/                       # Uploaded files (Excel, etc.)
```

## Key Features

- Advanced Skill-Based Matching: Intelligent task assignment system matching technician skills with task requirements.
- Excel Integration: Import and process technician data, skill matrices, and task lists from Excel files.
- Interactive Dashboards: User-friendly interfaces for supervisors and technicians to manage assignments and view workloads.
- Comprehensive Management: Tools for managing technicians, tasks, skills, and their relationships.
- Dynamic & Real-time: Real-time updates, dynamic skill mapping, and workload balancing.
- Security: CSRF protection, input validation, rate limiting, and secure headers.

## Technologies

- Programming Language: Python
- Framework: Flask
- Database: SQLite
- Dependencies:
    - Flask==3.1.1
    - pandas==2.3.0
    - Flask-WTF==1.2.1
    - numpy==2.2.6
    - pyxlsb==1.0.10
    - and others listed in requirements.txt.
- Containerization: Docker, Docker Compose
- Testing: Pytest

## Quick Test Guide

To test the application's end-to-end workflow:
1.  Run the application with `python run.py`.
2.  Navigate to `http://127.0.0.1:5000/manage_mappings`.
3.  Import `testsExcel.xlsb` and `testsExcel2.xlsb` from the `Excels_Testing/` directory to populate the database.
4.  Trigger the task assignment process from the UI.
5.  View the generated schedules on the supervisor and technician dashboards.
6.  (Optional) Run automated tests with `pytest` in the `tests/` directory: `pytest tests/`

## Development Roadmap Highlights

Key areas from `ROADMAP.md` and tracked in `issues.md`:
- Database & Data Management: Improving Excel data extraction, removing task priorities from the database, and integrating with external APIs.
- UI/UX Enhancements: Improving the technician dashboard (sticky headers, scrolling), and enhancing the Gantt chart (live time indicator, better interactivity).
- Task Assignment Logic: Documenting the current algorithm, fixing bugs, and exploring performance optimizations.
- Generalization: Making the application more modular and configurable (e.g., custom terminology, pluggable data sources).
- Testing: Creating a more robust dummy data seeding mechanism and expanding automated test coverage.

## How to Interact with Me

- Be proactive: When you ask me to work on something, I will scan the project to understand its structure and main technologies.
- Use the available tools: I will use my tools to get information about the project before asking you.
- Ask for clarification: If I am unsure about something, I will ask for clarification.
- Follow modern development practices: I will adopt modern development practices where applicable, but consistency with your code and style is more important.
- Documentation Update Requirement: When working on issues, before committing and pushing, I will update documentation files (README.md, AGENT.md, copilot-instructions.md, and any other relevant files) to reflect all changes.

## GitHub Issues

When you ask me to work on a GitHub issue, please remember that I cannot access external websites or run the `gh` command. You will need to provide me with the description of the issue.

## Working on Issues

When you ask me to work on an issue, I will adhere to the following process:

1.  Follow the Workflow: I will first consult the `GIT_WORKFLOW.md` file to understand the prescribed development workflow, including branching strategy, commit message conventions, and pull request procedures.
2.  Command Execution Protocol:
    *   If terminal commands are required for subsequent file modifications, provide all commands bundled together in the correct sequence.
    *   HALT execution and wait for my confirmation that the commands have been run before proceeding with any dependent tasks.
3.  Issue and Sub-Tasks Prioritization:
    *   I will announce which issue and sub-task I am about to work on based on the prioritization.
    *   I will prioritize issues based on the `issues.md` file, from highest (P1-High) to lowest (P3-Low).
    *   IMPORTANT: If an issue is broken down into sub-tasks, I will address each sub-task sequentially and independently.
    *   I will provide my plan for the current sub-task and ask for your approval before I start making changes.
    *   I will only proceed to the next sub-task after the current one is fully resolved (each sub-task needs to be commited).
    *   If any of the issues or sub-tasks is already implemented, I will skip it and move to the next one.
    *   I will give information about the status of each issue and sub-task.
    *   After completing a sub-task, I will provide a summary of the changes and wait for your confirmation to proceed to the next one.
