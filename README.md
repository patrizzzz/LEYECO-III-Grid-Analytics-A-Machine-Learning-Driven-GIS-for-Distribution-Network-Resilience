# Leyeco Interactive Electrical Post Mapping System

[![Python Application](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask Framework](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An advanced web-based Geographic Information System (GIS) designed for electric cooperatives to manage, visualize, and analyze their distribution network infrastructure. The system provides real-time mapping of electrical posts, transformers, bus nodes, and consumer service drops, enriched with machine-learning-driven predictive maintenance and load stress analytics.

---

## 📸 Screenshots

| Map View | Dashboard |
| :---: | :---: |
| *(Add your `docs/screenshots/map_view.png` here to view)* | *(Add your `docs/screenshots/dashboard.png` here to view)* |

| ML Predictions |
| :---: |
| *(Add your `docs/screenshots/ml_predictions.png` here to view)* |

---

## 🚀 Quick Start (Development)

### Prerequisites
- Python 3.8+
- SQLite (built-in) or MySQL (for production)
- Node.js & npm (if modifying frontend assets extensively)

### 1. Environment Setup (Windows)
Clone the repository and spin up a virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1   # PowerShell
# or cmd: venv\Scripts\activate.bat
```
*(If PowerShell blocks activation, run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process`)*

Install the Python dependencies:
```powershell
pip install -r requirements.txt
```

### 2. Database Initialization
Ensure your `.env` file exists (copy from `.env.example` if applicable) and is configured. For local development, it will default to SQLite if `DATABASE_URL` is omitted.

```powershell
set FLASK_APP=app.py
flask db upgrade
```

### 3. Import Initial Data
You can import infrastructure data from your CSV files:
```powershell
# Single file
python import_posts_from_csv.py "sample (1).csv"

# Batch import all CSV files in the data directory
python import_batch_csv.py "data/*.csv"
```
*(For detailed importing guidelines and conventions, read [DATA_MANAGEMENT_GUIDE.md](DATA_MANAGEMENT_GUIDE.md))*

### 4. Run the Application
Start the Flask development server:
```powershell
set FLASK_APP=app.py
set FLASK_ENV=development
python app.py
```
View the app in your browser at: **`http://127.0.0.1:5000`**

---

## 🏗️ Architecture Stack

- **Backend:** Flask (Python) with SQLAlchemy ORM. Follows a modular architecture. See [API_REFERENCE.md](docs/API_REFERENCE.md) for details.
- **Frontend:** HTML5 templates, Bootstrap 5, Javascript, Leaflet.js (Map Rendering).
- **Database:** SQLite (Dev) / MySQL (Production). Alembic handles database migrations.
- **Analytics:** Integration with internal ML models predicting transformer failure risk and load stress.

---

## 📚 Documentation Reference

Extensive documentation is maintained in the repository for specialized modules:

- [API Reference](docs/API_REFERENCE.md) - Details RESTful endpoints and payload structures.
- [Deployment Guide](DEPLOYMENT.md) - Guide on setting up Waitress/Gunicorn and Nginx for production.
- [Data Management Guide](DATA_MANAGEMENT_GUIDE.md) - Rules and conventions for interacting with the database externally.
- [CSV Flexible Import Guide](CSV_FLEXIBLE_IMPORT_GUIDE.md) - How the robust CSV import heuristic mapping operates.
- [Distribution Lines Guide](DISTRIBUTION_LINES_GUIDE.md) - Rendering lines and configuring connectivity hierarchies.
- [System Integration Complete](SYSTEM_INTEGRATION_COMPLETE.md) - Overview of how data modules hook together.
- [Data Analysis Metadata](DATA_ANALYSIS.md) - Breakdown of the predictive models and their thresholds.
- [UI Improvements](UI_IMPROVEMENTS.md) - Pending visual feature requests.

---

## 🔒 Authentication & Roles

The system supports strict Role-Based Access Control (RBAC):
- **Admin**: Full read/write access. Authenticates with Username and Password.
- **Viewer**: Read-only access to maps and non-sensitive dashboards. Authenticates with Username and an Admin-generated highly secure **Access Code**. Self-registration is disabled for maximum enterprise security.

*Note: You can initialize your first admin by sending a POST to `/setup/create-admin` with a `{username, password}` payload (only available when `FLASK_ENV=development`).*

---

## 🧰 Maintainers

If you encounter issues deploying or migrating database schemas, refer to `Flask-Migrate` guidelines. Keep your `.env` credential file out of version control.