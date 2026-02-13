from app import app
from extensions import db
from models import Post
from sqlalchemy import text

with app.app_context():
    # Delete sample posts (IDs 311-320) - keep only original posts (1-310)
    try:
        deleted = db.session.execute(text("DELETE FROM post WHERE id > 310"))
        db.session.commit()
        print(f'Deleted {deleted.rowcount} sample posts. Keeping original 310 posts.')
    except Exception as e:
        db.session.rollback()
        print(f'Error: {e}')
