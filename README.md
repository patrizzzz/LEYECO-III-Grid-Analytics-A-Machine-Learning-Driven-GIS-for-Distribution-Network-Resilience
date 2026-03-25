# ⚡ Leyeco Interactive Electrical Post Mapping System

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0+-000000.svg?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-336791.svg?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Leaflet](https://img.shields.io/badge/Leaflet-1.9+-199900.svg?style=for-the-badge&logo=leaflet&logoColor=white)](https://leafletjs.com/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952b3.svg?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com/)

An advanced, enterprise-grade **Geographic Information System (GIS)** tailored for electric cooperatives. This system streamlines infrastructure management through real-time visualization, automated data ingestion, and machine-learning-driven predictive analytics.

---

## ✨ Key Features

### 🗺️ Precision Mapping & GIS
- **Interactive Multi-layer Map:** High-performance rendering of electrical posts, transformers, and bus nodes using **Leaflet.js**.
- **Dynamic Asset Visualization:** Real-time visibility of consumer service drops and distribution line connectivity.
- **Geospatial Search:** Quickly locate assets by ID, pole number, or geographic coordinates.

### 📊 Intelligence & Analytics
- **Health Monitoring:** Dashboard providing live stats on grid infrastructure and asset health.
- **Load Stress Analysis:** Automated calculation of transformer load stress to prevent overloads.
- **Predictive Maintenance:** ML models identifying high-risk transformers before failures occur.

### 🔌 Network Operations
- **Topology Tracing:** Upstream and downstream feeder tracing to understand network hierarchy.
- **Outage Simulation:** Predictive impact analysis for simulated maintenance or fault scenarios.
- **Master Data Export:** Comprehensive CSV/JSON exports for external reporting and auditing.

### 🔒 Enterprise Governance
- **Role-Based Access Control (RBAC):** Granular permissions for Admins and Viewers.
- **Secure Authentication:** Admin-controlled access codes for viewers to maintain maximum site security.
- **Audit Logging:** System-wide tracking of data imports and asset modifications.

---

## 🛠️ Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend** | ![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) ![Flask](https://img.shields.io/badge/Flask-000000?style=flat-square&logo=flask&logoColor=white) ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat-square&logo=sqlalchemy&logoColor=white) |
| **Frontend** | ![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat-square&logo=javascript&logoColor=black) ![Leaflet](https://img.shields.io/badge/Leaflet-199900?style=flat-square&logo=leaflet&logoColor=white) ![Bootstrap](https://img.shields.io/badge/Bootstrap-7952B3?style=flat-square&logo=bootstrap&logoColor=white) |
| **Database** | ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=flat-square&logo=postgresql&logoColor=white) ![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white) |
| **DevOps** | ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white) ![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat-square&logo=github-actions&logoColor=white) |

---

## 🚀 Quick Start

### 1. Environment Setup
```powershell
# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration
Create a `.env` file from the provided template:
```env
FLASK_APP=app.py
FLASK_ENV=development
DATABASE_URL=postgresql://user:password@localhost:5432/leyeco_db
SECRET_KEY=your_secret_key
```

### 3. Database & Data
```powershell
# Run migrations
flask db upgrade

# Batch import infrastructure data
python scripts/data_management/import_batch_csv.py "data/*.csv"
```

### 4. Run App
```powershell
python app.py
```
Access the dashboard at `http://localhost:5000`

---

## 👨‍💻 Developer
**[patrizzzz](https://github.com/patrizzzz)**
*Software Developer*

Specializing in GIS integration, electrical grid analytics, and full-stack Python development.

---

## 📚 Documentation
- [📘 API Reference](docs/API_REFERENCE.md)
- [🚢 Deployment Guide](DEPLOYMENT.md)
- [📊 Data Management](DATA_MANAGEMENT_GUIDE.md)
- [⚡ Distribution Lines Guide](DISTRIBUTION_LINES_GUIDE.md)

---
*Developed for Leyeco III Electrical Cooperative.*
 of version control.