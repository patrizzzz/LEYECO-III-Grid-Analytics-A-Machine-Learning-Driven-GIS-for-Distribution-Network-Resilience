#!/usr/bin/env python3
"""Import poles from generated_connections.csv into the Post table."""

from app import app, db
from models import Post
import pandas as pd

def import_poles_from_csv(csv_file='poles_with_coordinates.csv', clear_first=False):
    """Import poles with coordinates into the database."""
    
    print(f"📂 Loading poles from {csv_file}...")
    
    try:
        poles_df = pd.read_csv(csv_file)
    except FileNotFoundError:
        print(f"❌ File not found: {csv_file}")
        return
    
    print(f"Found {len(poles_df)} poles to import")
    
    with app.app_context():
        # Clear existing posts if requested
        if clear_first:
            print("\n🗑 Clearing existing posts...")
            Post.query.delete()
            db.session.commit()
            print("  ✓ Cleared all existing posts")
        
        imported = 0
        skipped = 0
        duplicates = 0
        
        for idx, row in poles_df.iterrows():
            try:
                pole_num = str(row['pole_number']).strip()
                
                # Check if exists
                if Post.query.filter_by(pole_number=pole_num).first():
                    duplicates += 1
                    continue
                
                lat = float(row['latitude'])
                lng = float(row['longitude'])
                feeder = str(row['feeder']).strip()
                circuit = str(row['circuit']).strip()
                primary_bus = str(row['primary_bus']).strip() if pd.notna(row['primary_bus']) else None
                transformer_bus = str(row['transformer_bus']).strip() if pd.notna(row['transformer_bus']) else None
                secondary_bus = str(row['secondary_bus']).strip() if pd.notna(row['secondary_bus']) else None
                
                # Create new post
                post = Post(
                    name=f"Pole {pole_num}",
                    pole_number=pole_num,
                    lat=lat,
                    lng=lng,
                    feeder=feeder,
                    circuit=circuit,
                    primary_bus_id=primary_bus,
                    transformer_bus_id=transformer_bus,
                    sec_bus_id=secondary_bus
                )
                
                db.session.add(post)
                imported += 1
                
                if (idx + 1) % 50 == 0:
                    print(f"  Processing... {idx + 1}/{len(poles_df)}")
                
            except Exception as e:
                skipped += 1
                if skipped <= 5:  # Show first 5 errors
                    print(f"  ⚠ Row {idx}: {e}")
        
        # Commit all changes
        try:
            db.session.commit()
            print(f"\n✓ Successfully imported {imported} poles")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Database error: {e}")
            return
        
        if duplicates > 0:
            print(f"⚠ Duplicates: {duplicates} (skipped)")
        if skipped > 0:
            print(f"⚠ Errors: {skipped} (skipped)")
        
        # Show summary
        total_poles = Post.query.count()
        print(f"\n📊 Database now has {total_poles} total poles")
        print(f"📊 Feeders: {db.session.query(Post.feeder).distinct().count()}")
        print(f"📊 Circuits: {db.session.query(Post.circuit).distinct().count()}")

if __name__ == '__main__':
    import_poles_from_csv()

