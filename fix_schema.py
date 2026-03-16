from app import app
from extensions import db
from sqlalchemy import text

def fix_schema():
    tables_to_update = [
        'post', 'bus_node', 'distribution_line_segment', 'secondary_line_segment',
        'distribution_transformer', 'secondary_service_drop', 'line_connection',
        'customer', 'energy_consumption', 'load_curve', 'voltage_regulator',
        'shunt_capacitor', 'shunt_inductor', 'series_inductor'
    ]
    
    with app.app_context():
        # 1. Create upload_history table if it doesn't exist
        print("Checking upload_history table...")
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS upload_history (
                id SERIAL PRIMARY KEY,
                file_type VARCHAR(50),
                filename VARCHAR(255),
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                record_count INTEGER,
                status VARCHAR(20)
            )
        """))
        db.session.commit()

        # 2. Add columns to each table
        for table in tables_to_update:
            print(f"Checking table: {table}")
            try:
                # Add upload_id
                db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS upload_id INTEGER REFERENCES upload_history(id)"))
                # Add created_at if not present
                if table in ['voltage_regulator', 'shunt_capacitor', 'shunt_inductor', 'series_inductor']:
                    db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
                
                # Add index on upload_id
                db.session.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table}_upload_id ON {table} (upload_id)"))
                
                db.session.commit()
                print(f"  Successfully checked/updated {table}")
            except Exception as e:
                db.session.rollback()
                print(f"  Error updating {table}: {e}")

        # 3. Stamp Alembic to the latest head so it's happy
        # We'll do this separately via CLI
        print("Schema sync complete.")

if __name__ == "__main__":
    fix_schema()
