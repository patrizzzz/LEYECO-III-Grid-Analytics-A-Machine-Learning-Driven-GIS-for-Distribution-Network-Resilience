# Interactive Electrical Post Mapping & Connection System

Quick start (Windows):

1. Create a virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1   # PowerShell
# or for Command Prompt (cmd):
venv\Scripts\activate.bat
```

If PowerShell blocks script activation, run this once in your PowerShell session to allow the activation script to run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

2. Install deps:

```powershell
pip install -r requirements.txt
```

3. Initialize database (first time only):

```powershell
set FLASK_APP=app.py
flask db upgrade
```

4. Import electrical post data from CSV:

```powershell
# Single file
python import_posts_from_csv.py "sample (1).csv"

# Multiple files at once
python import_batch_csv.py "file1.csv" "file2.csv" "file3.csv"

# All CSV files from data folder
python import_batch_csv.py "data/*.csv"
```

5. Run the app:

```powershell
set FLASK_APP=app.py
set FLASK_ENV=development
python app.py
```

Open http://127.0.0.1:5000

---

## Data Management

### Clear All Data and Start Fresh

```powershell
python clear_posts.py
```
Follow the prompt to confirm deletion (type `DELETE`).

### Import CSV Data

**Column Name Flexibility** - Supports multiple column naming conventions:
- `Pole Number`, `pole_number`, `PoleNumber`, `pole#` ✓
- `Lat`, `Latitude`, `longitude`, `lng` ✓
- `Feeder`, `feeder name`, `Meter Brand` etc. ✓

**Single CSV file:**
```powershell
python import_posts_from_csv.py "sample (1).csv"
```

**Multiple CSV files at once:**
```powershell
python import_batch_csv.py "file1.csv" "file2.csv" "file3.csv"
```

**All CSV files from a folder:**
```powershell
python import_batch_csv.py "data/*.csv"
```

---

## User Workflow: Fresh Data Setup

1. **Clear old data:**
   ```powershell
   python clear_posts.py
   ```

2. **Import new CSV files:**
   ```powershell
   python import_batch_csv.py "data/file1.csv" "data/file2.csv"
   ```

3. **Run the application:**
   ```powershell
   python app.py
   ```

4. **View the map** at http://127.0.0.1:5000 with all new data loaded!

---

Map behavior:
- Each post that has `latitude` and `longitude` will appear as a pin on the map.
- When the app loads, the map will automatically center on the first available post and open its popup so you are "auto-located" to the first post.
- Posts without valid coordinates are ignored by the map until coordinates are provided.

---

## Advanced Setup (MySQL Database)

To use MySQL instead of SQLite:

1. Install MySQL server and create a database (e.g., `leyeco_db`).
2. Set your `DATABASE_URL` in `.env`:
   - `DATABASE_URL=mysql+pymysql://<user>:<password>@<host>/<dbname>`
3. Run migrations:

```powershell
flask db upgrade
```

4. Then import your CSV data (see Data Management section above).

---

## Feeder Visualization (Bus-Based)

Engineering feeder data uses **Bus IDs** (no coordinates). The app can draw feeder lines by:

1. **Bus–Post mapping** — Table `bus_post_mapping` links each Bus ID to a Post ID. Run the new migration then add rows (e.g. via API `POST /api/bus_post_mapping` with `{"bus_id": "BUS001", "post_id": 1}`).
2. **Feeder Excel** — Put bus-to-bus connections in `data/feeder_connections.xlsx` with columns **From_Bus** and **To_Bus** (or first two columns). Optional: set `FEEDER_EXCEL_PATH` to another path.
3. **Map layer** — Turn on the "Feeder (bus)" layer. A line is drawn only when *both* buses are mapped to a post that has coordinates; other connections are skipped and logged (and returned in `GET /api/feeder/lines` as `skipped`).

This is **visualization only**; the system does not infer electrical logic. Create a sample Excel: `python scripts/create_sample_feeder_excel.py`.

Notes: For advanced GIS queries consider PostGIS (PostgreSQL) for spatial functions. Use `Flask-Migrate` for schema migrations and keep your `DATABASE_URL` secure (do not commit credentials).


Authentication / Roles
----------------------
- The app supports two roles: **admin** and **viewer**.
- Admins authenticate with username + password (securely hashed).
- Viewers authenticate with username + an administrator-generated **access code** (no passwords for viewers).
- Public self-registration is disabled. Admins can create viewer users via `POST /api/users` (admin-only) which returns the access code.

Setup (after model changes / migrations)
- Run migrations to add the new user fields:

```powershell
flask db migrate -m "Add user access code and role fields"
flask db upgrade
```

- Create an initial admin (development only): POST to `/setup/create-admin` with JSON `{ "username": "admin", "password": "strongpw" }` (only works when `FLASK_ENV=development`).

API highlights
- `POST /login` with JSON `{ username, password }` for admins or `{ username, access_code }` for viewers.
- `GET /auth/whoami` returns current user info.
- `GET /api/users` (admin only) lists users.
- `POST /api/users` (admin only) creates a viewer and returns its `access_code`.
- Server enforces role checks; viewers have read-only access and cannot modify data.

Security notes
- Passwords are hashed using Werkzeug's secure hashing.
- Access codes are generated with `secrets.token_urlsafe()` and shown only to admins at creation/regeneration time.
- All protected actions are checked server-side; client-side UI adjustments are only convenience.