#!/usr/bin/env python3
"""
Manually add latitude and longitude columns to distribution_line_segment table
"""
from app import app, db
import sqlalchemy as sa

def add_columns():
    with app.app_context():
        try:
            # Add latitude column
            db.session.execute(sa.text("""
                ALTER TABLE distribution_line_segment 
                ADD COLUMN latitude FLOAT NULL
            """))
            print("✅ Added latitude column")
        except Exception as e:
            if 'Duplicate column name' in str(e):
                print("⚠️  latitude column already exists")
            else:
                print(f"❌ Error adding latitude: {e}")
        
        try:
            # Add longitude column
            db.session.execute(sa.text("""
                ALTER TABLE distribution_line_segment 
                ADD COLUMN longitude FLOAT NULL
            """))
            print("✅ Added longitude column")
        except Exception as e:
            if 'Duplicate column name' in str(e):
                print("⚠️  longitude column already exists")
            else:
                print(f"❌ Error adding longitude: {e}")
        
        db.session.commit()
        print("\n✅ Database update complete!")

if __name__ == '__main__':
    add_columns()
