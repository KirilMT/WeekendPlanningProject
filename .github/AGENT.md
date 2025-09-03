# Gemini Code Assist Instructions

This document provides instructions for Gemini Code Assist to help it provide the best possible assistance for the Weekend Planning Project.

## Core Principles for Assistance

-   **Efficiency is Key:** Please perform all necessary edits for a given task in a single step. Avoid making multiple, sequential edits to the same file for the same topic.
-   **Be Concise:** Do not repeat the same information or plans multiple times. Provide important information when necessary—not less, not more.

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
- **Dependencies:**
    - Flask==3.1.1
    - pandas==2.3.0
    - Flask-WTF==1.2.1
    - numpy==2.2.6
    - pyxlsb==1.0.10
    - and others listed in `requirements.txt`.

## Project Structure

```
WeekendPlanningProject/
├── wkndPlanning/              # Main application package
│   ├── routes/                # Flask blueprints and routing
│   ├── services/              # Business logic and utilities (core logic here)
│   ├── static/                # CSS, JavaScript, and static assets
│   ├── templates/             # Jinja2 HTML templates
│   └── app.py                 # Flask application factory
├── config.py                  # Application configuration
├── requirements.txt           # Python dependencies
├── run.py                     # Application entry point
└── README.md                  # Project documentation
```

## Quick Test Guide

To test the application's end-to-end workflow:
1.  Run the application with `python run.py`.
2.  Navigate to `http://127.0.0.1:5000/manage_mappings`.
3.  Import `testsExcel.xlsb` and `testsExcel2.xlsb` from the `Excels_Testing/` directory to populate the database.
4.  Trigger the task assignment process from the UI.
5.  View the generated schedules on the supervisor and technician dashboards.

## Development Roadmap Highlights

I am aware of the future development plans outlined in `ROADMAP.md`. I will keep these in mind when providing assistance. Key areas include:

-   **Database & Data Management:** Improving Excel data extraction, removing task priorities from the database, and integrating with external APIs.
-   **UI/UX Enhancements:** Improving the technician dashboard (sticky headers, scrolling), and enhancing the Gantt chart (live time indicator, better interactivity).
-   **Task Assignment Logic:** Documenting the current algorithm, fixing bugs, and exploring performance optimizations.
-   **Generalization:** Making the application more modular and configurable (e.g., custom terminology, pluggable data sources).
-   **Testing:** Creating a more robust dummy data seeding mechanism.

## How to Interact with Me

-   **Be proactive:** When you ask me to work on something, I will scan the project to understand its structure and main technologies.
-   **Use the available tools:** I will use my tools to get information about the project before asking you.
-   **Ask for clarification:** If I am unsure about something, I will ask for clarification.
-   **Follow modern development practices:** I will adopt modern development practices where applicable, but consistency with your code and style is more important.

## GitHub Issues

When you ask me to work on a GitHub issue, please remember that I cannot access external websites or run the `gh` command. You will need to provide me with the description of the issue.

## Working on Issues

When you ask me to work on an issue, I will adhere to the following process:

1.  **Follow the Workflow:** I will first consult the `GIT_WORKFLOW.md` file to understand the prescribed development workflow, including branching strategy, commit message conventions, and pull request procedures.

2.  **Command Execution Protocol:**
    *   If terminal commands are required for subsequent file modifications, provide all commands bundled together in the correct sequence.
    *   **HALT execution and wait for my confirmation** that the commands have been run before proceeding with any dependent tasks.

3.  **Issue and Sub-Issue Prioritization:**
    *   I will prioritize issues based on the `issues.md` file, from highest (P1-High) to lowest (P3-Low).
    *   If an issue is broken down into sub-issues, I will address each sub-issue **sequentially and independently**.
    *   I will only proceed to the next sub-issue after the current one is fully resolved.
