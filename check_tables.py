from app import app
from extensions import db
from sqlalchemy import inspect

with app.app_context():
    engine = db.engine
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print("Tables in database:")
    for table in tables:
        print(f"  - {table}")
    
    # Check latlongdata table
    if 'latlongdata' in tables:
        print("\nlatlongdata table found:")
        from sqlalchemy import text
        result = db.session.execute(text("SELECT COUNT(*) as count FROM latlongdata")).fetchone()
        print(f"  Rows: {result[0]}")
