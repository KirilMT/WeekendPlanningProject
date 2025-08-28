# Weekend Planning Project

A professional Flask-based web application for managing weekend technician task assignments using skill-based matching and workload optimization.

## 🚀 Features

- **Advanced Skill-Based Matching:** Intelligent task assignment system matching technician skills with task requirements
- **Multi-Skill Task Support:** Tasks can require multiple technical skills with different proficiency levels
- **Group Assignment Logic:** Smart grouping of technicians to optimize skill coverage and team effectiveness
- **Technician Management:** Comprehensive technician profiles with skill tracking and experience levels
- **Task Management:** Create, update, and manage tasks with multi-skill requirements and duration calculations
- **Interactive Dashboard:** User-friendly interface for managing assignments and viewing technician workloads
- **Security Features:** CSRF protection, input validation, rate limiting, and secure headers
- **Excel Integration:** Import and process technician data and skill matrices from Excel files
- **Real-time Updates:** Dynamic skill mapping and assignment optimization
- **Workload Balancing:** Automatic adjustment of task duration based on team size and skill levels

## 📁 Project Structure

```
WeekendPlanningProject/
├── wkndPlanning/              # Main application package
│   ├── routes/                # Flask blueprints and routing
│   │   ├── api.py            # API endpoints for skill-based assignments
│   │   ├── health.py         # Health check endpoints
│   │   └── main.py           # Main web routes
│   ├── services/              # Business logic and utilities
│   │   ├── config_manager.py # Configuration management
│   │   ├── dashboard.py      # Dashboard generation
│   │   ├── data_processing.py # Data processing utilities
│   │   ├── db_utils.py       # Database operations and schema
│   │   ├── extract_data.py   # Excel data extraction
│   │   ├── health_check.py   # System health monitoring
│   │   ├── logging_config.py # Logging configuration
│   │   ├── security.py       # Security utilities
│   │   └── task_assigner.py  # Skill-based assignment algorithms
│   ├── static/               # CSS, JavaScript, and static assets
│   ├── templates/            # Jinja2 HTML templates
│   ├── uploads/              # File upload directory
│   ├── output/               # Generated output files
│   └── app.py               # Flask application factory
├── config.py                 # Application configuration
├── requirements.txt          # Python dependencies
├── run.py                   # Application entry point
└── README.md                # This file
```

## ⚙️ Setup and Installation

### Prerequisites

- Python 3.12 or higher
- pip (Python package installer)
- Git

### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd WeekendPlanningProject
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venvOld venvOld
   source venvOld/bin/activate  # On Windows: venvOld\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables (optional):**
   Create a `.env` file in the project root:
   ```env
   SECRET_KEY=your_secret_key_here
   DEBUG_MODE=1
   DATABASE_FILENAME=testsDB.db
   ```

5. **Initialize the database:**
   The database will be automatically initialized on first run.

6. **Run the application:**
   ```bash
   python run.py
   ```

7. **Access the application:**
   Open your browser and navigate to `http://127.0.0.1:5000`

## 🚀 Quick Test Guide

To help you quickly explore the features of the Weekend Planning application, follow these steps. On the first run, the application will create a new, empty database. You can use the sample Excel files located in the `Excels_Testing/` directory to populate it with data.

1.  **Start the Application**: If it's not already running, start the application with `python run.py`.
2.  **Navigate to Management Page**: Open your browser and go to `http://127.0.0.1:5000/manage_mappings`. This is the main interface for managing technicians, tasks, and skills.
3.  **Import Sample Data**:
    *   Use the file upload functionality on the page to import `testsExcel.xlsb` and `testsExcel2.xlsb` from the `Excels_Testing/` directory.
    *   This will populate the database with sample technicians, tasks, and their required skills.
4.  **Run Task Assignment**:
    *   Once the data is imported, you can trigger the task assignment process from the UI.
    *   The application will use its skill-based algorithm to assign the tasks to the most suitable technicians.
5.  **View the Dashboards**:
    *   **Supervisor Dashboard**: Navigate to the supervisor dashboard to get an overview of all task assignments, schedules, and workloads.
    *   **Technician Dashboard**: Check the individual technician dashboards to see their specific schedules and assigned tasks.

This quick guide allows you to see the end-to-end workflow of the application, from data import to final schedule visualization.

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key for sessions | Auto-generated |
| `DEBUG_MODE` | Enable debug mode (1/true/yes) | 0 |
| `DEBUG_USE_TEST_DB` | Force use of test database | 0 |
| `DATABASE_FILENAME` | Custom database filename | Based on debug mode |
| `CSRF_TIME_LIMIT` | CSRF token expiration (seconds) | 3600 |
| `SESSION_LIFETIME` | Session timeout (seconds) | 1800 |
| `MAX_UPLOAD_SIZE` | Maximum file upload size (bytes) | 16777216 |
| `MIN_SKILL_LEVEL` | Minimum required skill level | 1 |
| `MAX_SKILL_LEVEL` | Maximum possible skill level | 5 |

## 📊 Skill-Based Assignment System

The application uses a sophisticated skill-based assignment system that:
- Matches technicians to tasks based on required technical skills
- Supports multiple skill requirements per task
- Calculates optimal team sizes based on task complexity
- Adjusts task duration based on team composition
- Ensures fair workload distribution while maintaining skill coverage

## 🔒 Security

- CSRF Protection for all forms
- Input validation and sanitization
- Rate limiting on API endpoints
- Secure session handling
- XSS prevention
- Secure file upload handling

## 📝 Documentation

Detailed documentation is available in the following files:
- `technician_dashboard_manual.md`: User manual for the technician dashboard
- `ROADMAP.md`: Development roadmap and future features

## 🎯 Usage

### Web Interface

1. **Dashboard Access:** Navigate to the main dashboard to view technician assignments
2. **Manage Mappings:** Use the mappings interface to configure:
   - Technician skills and competency levels (0-4)
   - Task requirements and multi-skill dependencies
   - Satellite points and line assignments
3. **File Upload:** Import Excel files with technician and task data
4. **Assignment Generation:** Generate optimized task assignments based on skills

### API Endpoints

The application provides REST API endpoints for programmatic access:

- `GET /api/technicians` - Retrieve all technicians
- `GET /api/get_technician_mappings` - Get technician skill mappings
- `POST /api/tasks` - Create or update tasks
- Additional endpoints available in `/routes/api.py`

## 🛡️ Security Features

- **CSRF Protection:** All forms protected against cross-site request forgery
- **Input Validation:** Comprehensive server-side validation and sanitization
- **Rate Limiting:** API endpoints protected against abuse
- **Secure Headers:** Security headers automatically added to responses
- **Session Management:** Secure session handling with configurable timeouts

## 🔍 Development

### Key Components

1. **Task Assignment Algorithm:** Skill-based matching with workload optimization
2. **Database Schema:** Normalized design supporting many-to-many relationships
3. **Security Layer:** Multi-layered security with validation and sanitization
4. **Configuration Management:** Environment-aware configuration system

### Code Quality

- **PEP 8 Compliance:** Python code follows PEP 8 styling guidelines
- **Class-based Architecture:** Modern object-oriented design patterns
- **Error Handling:** Comprehensive error handling and logging
- **Documentation:** Well-documented code with clear docstrings

## 📊 Database Schema

The application uses SQLite with the following key tables:

- `technicians` - Technician profiles and satellite point assignments
- `technologies` - Available technologies and skills
- `tasks` - Task definitions
- `technician_technology_skills` - Technician skill levels (0-4)
- `task_required_skills` - Task skill requirements
- `technician_task_assignments` - Final task assignments

## 🚨 Troubleshooting

### Common Issues

1. **Database Errors:** Ensure the database directory is writable
2. **Import Errors:** Verify all dependencies are installed
3. **Configuration Issues:** Check environment variables and file paths
4. **Security Warnings:** Ensure SECRET_KEY is set in production

### Logging

Application logs are available in the `wkndPlanning/logs/` directory with different log levels for debugging.

## 🤝 Contributing

1. Follow PEP 8 coding standards
2. Write comprehensive tests for new features
3. Update documentation for any changes
4. Ensure all security validations are in place

## 📝 License

[Add your license information here]

---

**Version:** 1.0.0  
**Last Updated:** August 2025
