# Gemini Code Assist Instructions

This document provides instructions for Gemini Code Assist to help it provide the best possible assistance for the Weekend Planning Project.

## Core Principles for Assistance

-   **Efficiency is Key:** Please perform all necessary edits for a given task in a single step. Avoid making multiple, sequential edits to the same file for the same topic.
-   **Be Concise:** Do not repeat the same information or plans multiple times. Provide important information when necessary—not less, not more.
-   **Single Edit Rule:** When editing a file, apply *all planned changes in one unified edit*. Do not split the edit into multiple smaller patches. Do not re-edit the same file again for the same request.
-   **No Repetition:** Never repeat the same text, instructions, or edits in multiple replies. Each reply must be unique and progress the task forward.
-   **Atomic Updates:** For each request, complete all necessary modifications in one atomic update per file. Do not provide partial or incremental changes.
-   **One-time Summary:** After making changes, provide a short summary of what was modified. Do not restate the same summary in following replies.
-   **No Restating Code:** If you’ve already shown the final code once, do not output the same code again unless explicitly asked.

## Project Overview

This is a professional Flask-based web application for managing weekend technician task assignments using skill-based matching and workload optimization. The application is designed to be modular, secure, and user-friendly, with a focus on intelligent task assignment and comprehensive management features.

## Key Features

- **Advanced Skill-Based Matching:** Intelligent task assignment system matching technician skills with task requirements.
- **Excel Integration:** Import and process technician data, skill matrices, and task lists from Excel files.
- **Interactive Dashboards:** User-friendly interfaces for supervisors and technicians to manage assignments and view workloads.
- **Comprehensive Management:** Tools for managing technicians, tasks, skills, and their relationships.
- **Dynamic & Real-time:** Real-time updates, dynamic skill mapping, and workload balancing.
- **Security:** CSRF protection, input validation, rate limiting, and secure headers.

## Technologies

- **Programming Language:** Python
- **Framework:** Flask
- **Database:** SQLite
- **Dependencies:**
    - Flask==3.1.1
    - pandas==2.3.0
    - Flask-WTF==1.2.1
    - numpy==2.2.6
    - pyxlsb==1.0.10
    - and others listed in `requirements.txt`.
- **Containerization:** Docker, Docker Compose
- **Testing:** Pytest

## Project Structure

```
WeekendPlanningProject/
├── src/                     # Main application package
│   ├── routes/              # Flask blueprints and routing
│   ├── services/            # Business logic and utilities (core logic here)
│   ├── static/              # CSS, JavaScript, and static assets
│   ├── templates/           # Jinja2 HTML templates
│   └── app.py               # Flask application factory
├── instance/                # Instance folder for database
├── logs/                    # Application and error logs
├── output/                  # Generated output files
├── docs/                    # Documentation
├── docker/                  # Docker configuration
├── tests/                   # Tests
├── test_data/               # Test data
├── .gitignore
├── requirements.txt
├── run.py
└── README.md
```

## Quick Test Guide

To test the application's end-to-end workflow:
1.  Run the application with `python run.py`.
2.  Navigate to `http://127.0.0.1:5000/manage_mappings`.
3.  Import `testsExcel.xlsb` and `testsExcel2.xlsb` from the `test_data/` directory to populate the database.
4.  Trigger the task assignment process from the UI.
5.  View the generated schedules on the supervisor and technician dashboards.
6.  (Optional) Run automated tests with `pytest` in the `tests/` directory: `pytest tests/`

## How to Interact with Me

-   **Be proactive:** When you ask me to work on something, I will scan the project to understand its structure and main technologies.
-   **Use the available tools:** I will use my tools to get information about the project before asking you.
-   **Ask for clarification:** If I am unsure about something, I will ask for clarification.
-   **Follow modern development practices:** I will adopt modern development practices where applicable, but consistency with your code and style is more important.
-   **Documentation Update Requirement:** When working on issues, before committing and pushing, I will update documentation files (README.md, AGENT.md, copilot-instructions.md, and any other relevant files) to reflect all changes.

## GitHub Issues

When you ask me to work on a GitHub issue, I will use the `gh` command-line tool to get the details of the issue.

You can ask me to list issues, for example:
- "What are the open issues assigned to me?"
- "List all open issues."

I will then use the following command to retrieve the necessary information:
- To see open issues assigned to you: `gh issue list --assignee "@me" --state open`
- To see all open issues: `gh issue list --state open`

## Working on Issues

When you ask me to work on an issue, I will adhere to the following process:

1.  **Follow the Workflow:** I will first consult the `GIT_WORKFLOW.md` file to understand the prescribed development workflow, including branching strategy, commit message conventions, and pull request procedures.

2.  **Command Execution Protocol:**
    *   If terminal commands are required for subsequent file modifications, provide all commands bundled together in the correct sequence.
    *   **HALT execution and wait for my confirmation** that the commands have been run before proceeding with any dependent tasks.

3.  **Issue and Sub-Tasks Prioritization:**
    *   I will announce which issue and sub-task I am about to work on based on the prioritization.
    *   IMPORTANT: If an issue is broken down into sub-tasks, I will address each sub-task **sequentially and independently**.
    *   I will provide my plan for the current sub-task and ask for your approval before I start making changes.
    *   I will only proceed to the next sub-task after the current one is fully resolved (each sub-task needs to be commited).
    *   If any of the issues or sub-tasks is already implemented, I will skip it and move to the next one.
    *   I will give information about the status of each issue and sub-task.
    *   After completing a sub-task, I will provide a summary of the changes and wait for your confirmation to proceed to the next one.
