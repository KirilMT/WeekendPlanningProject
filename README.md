# Weekend Planning Project

A professional Flask-based web application for managing weekend technician task assignments using skill-based matching and workload optimization.

## 🚀 Features

- **Skill-Based Task Assignment:** Intelligent assignment of tasks to technicians based on required skills and competency levels
- **Technician Management:** Comprehensive technician profiles with skill tracking and satellite point assignments
- **Task Management:** Create, update, and manage tasks with multi-skill requirements
- **Interactive Dashboard:** User-friendly interface for managing assignments and viewing technician workloads
- **Security Features:** CSRF protection, input validation, rate limiting, and secure headers
- **Excel Integration:** Import and process technician data from Excel files
- **Real-time Updates:** Dynamic skill mapping and assignment optimization

## 📁 Project Structure

```
WeekendPlanningProject/
├── wkndPlanning/              # Main application package
│   ├── routes/                # Flask blueprints and routing
│   │   ├── api.py            # API endpoints
│   │   └── main.py           # Main web routes
│   ├── services/              # Business logic and utilities
│   │   ├── config_manager.py # Configuration management
│   │   ├── dashboard.py      # Dashboard generation
│   │   ├── data_processing.py # Data processing utilities
│   │   ├── db_utils.py       # Database operations
│   │   ├── extract_data.py   # Excel data extraction
│   │   ├── logging_config.py # Logging configuration
│   │   ├── security.py       # Security utilities
│   │   └── task_assigner.py  # Task assignment algorithms
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

- Python 3.8 or higher
- pip (Python package installer)

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

### Database Configuration

The application automatically selects the appropriate database:
- **Development:** `testsDB.db` (when `DEBUG_MODE=1`)
- **Production:** `weekend_planning.db`

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
