import os
import sys
from werkzeug.security import generate_password_hash

# Setup path to include the current directory
sys.path.append(os.getcwd())

from app import app
from extensions import db
from models import User

def create_admin():
    username = "admin"
    password = "admin"
    
    with app.app_context():
        # Check if user already exists
        user = User.query.filter_by(username=username).first()
        if user:
            print(f"User '{username}' already exists. Updating password.")
            user.password_hash = generate_password_hash(password)
            user.role = 'admin'
        else:
            print(f"Creating new admin user '{username}'.")
            pw_hash = generate_password_hash(password)
            user = User(username=username, password_hash=pw_hash, role='admin')
            db.session.add(user)
        
        try:
            db.session.commit()
            print(f"Successfully set up admin account: {username}")
        except Exception as e:
            db.session.rollback()
            print(f"Error creating admin account: {e}")

if __name__ == "__main__":
    create_admin()
