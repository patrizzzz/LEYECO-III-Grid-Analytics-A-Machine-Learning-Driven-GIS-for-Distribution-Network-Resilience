# Production Deployment Guide

This guide describes how to deploy the Leyeco3 Interactive Electrical Post Mapping system into a production environment.

## Architecture Request

In production, Flask's built-in server (`app.run()`) is **not suitable**. A proper production stack typically includes:
1. **Application Server:** Waitress (Windows) or Gunicorn (Linux).
2. **Reverse Proxy:** Nginx or Apache.
3. **Database:** MySQL/PostgreSQL instead of SQLite.
4. **Environment Variables:** Handled via `.env` files or OS-level environment variables.

---

## 1. Environment Configuration

Create or update your `.env` file for production usage:

```env
# Disable debug mode
FLASK_ENV=production
FLASK_DEBUG=0

# Security Key - MUST BE A LONG RANDOM STRING IN PRODUCTION
SECRET_KEY=super-secret-production-key-change-me

# Database Configuration (MySQL recommended for production)
DATABASE_URL=mysql+pymysql://<db_user>:<db_password>@<db_host>:<db_port>/<db_name>
```

---

## 2. Using Waitress (Windows Production)

Waitress is a production-quality WSGI server that fully supports Windows.

1. Install Waitress:
   ```cmd
   pip install waitress
   ```

2. Run the application via Waitress (running on port 5000):
   ```cmd
   waitress-serve --host 127.0.0.1 --port 5000 app:app
   ```

3. To keep Waitress running continuously on Windows, you can wrap it in a **NSSM** (Non-Sucking Service Manager) service.
   - Download NSSM: http://nssm.cc
   - Install as a service:
     ```cmd
     nssm install Leyeco3Service "C:\path\to\venv\Scripts\waitress-serve.exe" "--host 127.0.0.1 --port 5000 app:app"
     ```

---

## 3. Using Gunicorn (Linux Production)

If hosting on Linux (Ubuntu/Debian, CentOS, etc.):

1. Install Gunicorn:
   ```bash
   pip install gunicorn
   ```

2. Run with Gunicorn using multiple workers:
   ```bash
   gunicorn -w 4 -b 127.0.0.1:5000 app:app
   ```

---

## 4. Setting up Nginx as a Reverse Proxy

You should place Nginx in front of Waitress/Gunicorn to handle client connections, SSL/HTTPS certificates, and serving static files directly.

Install Nginx and add the following configuration to `/etc/nginx/sites-available/leyeco3`:

```nginx
server {
    listen 80;
    server_name yourdomain.com; # Or your server's IP address

    # Serve static files directly through Nginx for performance
    location /static/ {
        alias /path/to/leyeco3/static/;
    }

    # Proxy API and Dynamic routes to Waitress/Gunicorn
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the Nginx config and restart:
```bash
sudo ln -s /etc/nginx/sites-available/leyeco3 /etc/nginx/sites-enabled
sudo systemctl restart nginx
```

---

## 5. Database Setup (MySQL)

By default, the app uses an SQLite database `app.db`. SQLite is fine for development, but in production with multiple concurrent users, it is highly recommended to migrate to MySQL.

1. Ensure MySQL Server is perfectly running.
2. In your `.env` file, point the `DATABASE_URL` to your MySQL instance:
   ```env
   DATABASE_URL=mysql+pymysql://admin:securepassword@localhost:3306/leyeco_db
   ```
3. Initialize the database schema and migrate:
   ```powershell
   # Ensure FLASK_APP is set
   set FLASK_APP=app.py
   flask db upgrade
   ```
4. Perform an initial data migration using your CSVs as described in the README `Data Management` section.

## 6. Docker Compose Deployment (Recommended)

Docker Compose provides a self-contained, production-ready environment including the application server, PostgreSQL database, and pgAdmin.

1.  **Configure Environment**:
    - Copy `.env.example` to `.env`.
    - Update `SECRET_KEY` and database credentials.
    - Set `DB_HOST=db` for the internal Docker network.

2.  **Build and Start**:
    ```bash
    docker-compose up --build -d
    ```

3.  **Database Migration**:
    Initialize the database schema inside the container:
    ```bash
    docker-compose exec web flask db upgrade
    ```

4.  **Access the System**:
    - **Web App**: http://localhost:5000
    - **pgAdmin**: http://localhost:5050 (Login: admin@leyeco.com / admin)

5.  **Stopping the System**:
    ```bash
    docker-compose down
    ```
