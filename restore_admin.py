from app import app
from extensions import db
from models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    # Only create if doesn't exist (though we know it's empty)
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        pw_hash = generate_password_hash('admin')
        u = User(username='admin', role='admin', password_hash=pw_hash)
        db.session.add(u)
        db.session.commit()
        print("ADMIN_CREATED")
    else:
        print("ADMIN_ALREADY_EXISTS")
