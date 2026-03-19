
import os
import sys
# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app import app
from extensions import db

print(f"DATABASE_URL (os.getenv): {os.getenv('DATABASE_URL')}")
print(f"DB_DATABASE (os.getenv): {os.getenv('DB_DATABASE')}")
print(f"SQLALCHEMY_DATABASE_URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
