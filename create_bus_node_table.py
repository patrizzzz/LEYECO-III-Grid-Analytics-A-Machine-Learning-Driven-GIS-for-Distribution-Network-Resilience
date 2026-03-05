from flask import Flask
from extensions import db
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
# Configure database
database_url = os.getenv('DATABASE_URL')
if not database_url:
    db_user = os.getenv('DB_USERNAME')
    db_pass = os.getenv('DB_PASSWORD')
    db_host = os.getenv('DB_HOST', '127.0.0.1')
    db_port = os.getenv('DB_PORT', '3306')
    db_name = os.getenv('DB_DATABASE')
    if db_user and db_name:
        database_url = f"mysql+pymysql://{db_user}:{db_pass or ''}@{db_host}:{db_port}/{db_name}"
    else:
        database_url = 'sqlite:///app.db'

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    # We only want to create the bus_node table
    # But db.create_all() will try to create everything
    # We can use the table object directly to create it
    from models import BusNode
    try:
        BusNode.__table__.create(db.engine)
        print("Successfully created 'bus_node' table.")
    except Exception as e:
        if "already exists" in str(e):
            print("'bus_node' table already exists.")
        else:
            print(f"Error creating 'bus_node' table: {e}")
