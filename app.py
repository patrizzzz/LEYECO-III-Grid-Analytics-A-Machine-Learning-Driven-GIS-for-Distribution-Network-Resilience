from flask import Flask, render_template, jsonify, redirect, url_for
from flask_cors import CORS
from dotenv import load_dotenv
import os

from extensions import db, migrate

load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')
# Secret key: use configured SECRET_KEY or generate a temporary one (not recommended for production)
app.secret_key = os.getenv('SECRET_KEY') or os.urandom(24)
CORS(app)

# Dev UX: auto-reload templates and disable static caching when configured
if str(os.getenv('TEMPLATES_AUTO_RELOAD', '')).lower() in ('1', 'true', 'yes'):
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.jinja_env.auto_reload = True
if str(os.getenv('SEND_FILE_MAX_AGE_DEFAULT', '')).strip() != '':
    try:
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = int(os.getenv('SEND_FILE_MAX_AGE_DEFAULT', '0'))
    except Exception:
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# Configure database
database_url = os.getenv('DATABASE_URL')
if not database_url:
    db_user = os.getenv('DB_USERNAME')
    db_pass = os.getenv('DB_PASSWORD')
    db_host = os.getenv('DB_HOST', '127.0.0.1')
    db_port = os.getenv('DB_PORT', '3306')
    db_name = os.getenv('DB_DATABASE')
    if db_user and db_name is not None:
        if db_pass:
            database_url = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        else:
            database_url = f"mysql+pymysql://{db_user}@{db_host}:{db_port}/{db_name}"
    else:
        database_url = 'sqlite:///app.db'

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Bind extensions to app
db.init_app(app)
migrate.init_app(app, db)

# Import models to ensure they are registered with SQLAlchemy
with app.app_context():
    import models

# Register Blueprints
from routes.auth_routes import auth_bp
from routes.main_routes import main_bp
from routes.api_routes import api_bp

app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(api_bp, url_prefix='/api')

# Helper: make current user available in templates
from routes.auth_routes import get_current_user
from flask import g, session

@app.context_processor
def inject_current_user():
    return {'current_user': get_current_user()}

@app.before_request
def load_current_user_into_g():
    g.current_user = get_current_user()

if __name__ == '__main__':
    app.run(debug=True)
