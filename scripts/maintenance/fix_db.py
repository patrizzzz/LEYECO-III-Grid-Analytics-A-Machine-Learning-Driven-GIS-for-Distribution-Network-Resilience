
from app import app, db
import models  # Ensure models are imported so SQLAlchemy knows about them

def fix_database():
    print("="*50)
    print("🛠️  FIXING DATABASE SCHEMA")
    print("="*50)
    
    with app.app_context():
        # This will create any tables that don't exist, but won't touch existing ones
        print("Running db.create_all()...")
        try:
            db.create_all()
            print("✅ Database tables created successfully.")
        except Exception as e:
            print(f"❌ Error creating tables: {e}")
            
        # Verify
        print("\nVerifying tables...")
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"Found tables: {', '.join(tables)}")
        
        required = ['secondary_line_segment', 'distribution_transformer', 'post', 'line_connection']
        missing = [t for t in required if t not in tables]
        
        if missing:
            print(f"❌ Still missing tables: {missing}")
        else:
            print("✅ All required tables are present.")

if __name__ == "__main__":
    fix_database()
