
from app import app
from extensions import db
from models import User
from werkzeug.security import generate_password_hash
import sqlalchemy as sa

def restore():
    with app.app_context():
        print("Re-creating database tables...")
        # Ensure PostGIS is there
        try:
            db.session.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis"))
            db.session.commit()
        except Exception as e:
            print(f"PostGIS extension check failed (might already exist or permission denied): {e}")
            db.session.rollback()

        db.create_all()
        print("Schema re-created.")

        # Re-create admin user if missing
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("Creating default admin user...")
            pw_hash = generate_password_hash('admin123')
            admin = User(username='admin', role='admin', password_hash=pw_hash)
            db.session.add(admin)
            db.session.commit()
            print("Admin user created (username: admin, password: admin123). PLEASE CHANGE PASSWORD IMMEDIATELY.")
        else:
            print("Admin user already exists.")

if __name__ == "__main__":
    restore()
