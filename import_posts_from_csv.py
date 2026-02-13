#!/usr/bin/env python3
"""
Import electrical post data from CSV into the database.
Each row represents a meter/connection at a pole. We consolidate them by pole.

FLEXIBLE COLUMN NAME HANDLING:
- Handles column names with spaces (e.g., "Pole Number", "pole number", "PoleNumber")
- Case-insensitive matching
- Supports common naming variations
"""

import csv
import sys
from pathlib import Path
from datetime import datetime
from app import app, db
from models import Post, Meter

def sanitize_float(value):
    """Convert value to float, return None if invalid"""
    if not value or str(value).strip() == '':
        return None
    try:
        # Handle scientific notation like 2.024E+11
        return float(value)
    except (ValueError, AttributeError, TypeError):
        return None

def normalize_column_name(name):
    """
    Normalize column name for flexible matching.
    Strips whitespace, converts to lowercase, replaces spaces with underscores.
    """
    if not name:
        return ""
    return str(name).strip().lower().replace(' ', '_')

def find_column(row, possible_names):
    """
    Find column value using flexible matching of column names.
    
    Args:
        row: Dictionary from CSV DictReader
        possible_names: List of possible column name variations to try
    
    Returns:
        Value from matching column, or None if not found
    
    Example:
        find_column(row, ['Pole Number', 'pole_number', 'PoleNumber'])
    """
    if not row or not possible_names:
        return None
    
    # Normalize all target names for comparison
    normalized_targets = [normalize_column_name(n) for n in possible_names]
    
    # Try to find matching key in row
    for key in row.keys():
        normalized_key = normalize_column_name(key)
        if normalized_key in normalized_targets:
            return row[key]
    
    return None

def import_posts_from_csv(csv_file):
    """
    Import posts from CSV file with flexible column name handling.
    Groups multiple meter records by pole_number and consolidates data.
    """
    if not Path(csv_file).exists():
        print(f"❌ Error: File '{csv_file}' not found")
        return
    
    posts_data = {}  # Key: pole_number, Value: consolidated post data
    
    print(f"📂 Reading CSV file: {csv_file}")
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            if not reader.fieldnames:
                print("❌ Error: CSV file appears empty or invalid")
                return
            
            print(f"📋 Found {len(reader.fieldnames)} columns")
            row_count = 0
            skipped = 0
            
            for row in reader:
                row_count += 1
                
                # Extract pole number - try multiple column name variations
                pole_number = (find_column(row, ['Pole Number', 'pole_number', 'pole number', 'Pole#', 'PoleNumber', 'pole#']) or '').strip()
                if not pole_number:
                    skipped += 1
                    continue
                
                # Get coordinates - handle different naming conventions
                lat = sanitize_float(find_column(row, ['Lat', 'Latitude', 'lat', 'LAT', 'latitude']))
                lng = sanitize_float(find_column(row, ['Long', 'Longitude', 'Lon', 'lng', 'LONG', 'LON', 'longitude']))
                
                if lat is None or lng is None:
                    skipped += 1
                    continue
                
                # First time seeing this pole - create record
                if pole_number not in posts_data:
                    posts_data[pole_number] = {
                        'pole_number': pole_number,
                        'name': f"Post {pole_number}",
                        'lat': lat,
                        'lng': lng,
                        'area': (find_column(row, ['Lat, Long', 'Area', 'area', 'Area Name']) or '').strip() or None,
                        'feeder': (find_column(row, ['Feeder', 'feeder', 'Feeder Name', 'feeder name']) or '').strip() or None,
                        'pri_structure': (find_column(row, ['Pri. Structure', 'Primary Structure', 'pri structure', 'pri_structure']) or '').strip() or None,
                        'pri_conductor_size': (find_column(row, ['Conductor Size', 'Pri Conductor Size', 'conductor size', 'conductor_size']) or '').strip() or None,
                        'neutral_wire': (find_column(row, ['Neutral Wire', 'Neutral', 'neutral wire', 'neutral_wire']) or '').strip() or None,
                        'configuration': (find_column(row, ['Configuration', 'Config', 'configuration']) or '').strip() or None,
                        'phasing': (find_column(row, ['Phasing', 'Phase', 'phasing']) or '').strip() or None,
                        'primary_bus_id': (find_column(row, ['Primary Bus ID', 'Pri Bus', 'Primary Bus', 'primary bus id']) or '').strip() or None,
                        'sec_structure': (find_column(row, ['Sec. Structure', 'Secondary Structure', 'sec structure', 'sec_structure']) or '').strip() or None,
                        'sec_conductor_size': (find_column(row, ['Sec Conductor Size', 'Secondary Conductor Size', 'secondary conductor size']) or '').strip() or None,
                        'sec_type': (find_column(row, ['Tpye', 'Type', 'Sec Type', 'Secondary Type', 'sec type', 'sec_type']) or '').strip() or None,
                        'conductor_type': (find_column(row, ['Conductor Type', 'Material', 'conductor type', 'conductor_type']) or '').strip() or None,
                        'sec_bus_id': (find_column(row, ['Sec. Bus ID', 'Secondary Bus', 'Sec Bus', 'secondary bus id']) or '').strip() or None,
                        'kva_rating': sanitize_float(find_column(row, ['kVA Rating', 'kVA', 'kva rating', 'kva_rating', 'Rating'])),
                        'common_sole': (find_column(row, ['Common/Sole', 'Common Sole', 'Type (Sole/Common)', 'common sole']) or '').strip() or None,
                        'transformer_bus_id': (find_column(row, ['Transformer Bus ID', 'Transformer Bus', 'Xfmr Bus', 'transformer bus id']) or '').strip() or None,
                        'transformer_phasing': (find_column(row, ['Transformer Phasing', 'Xfmr Phasing', 'transformer phasing']) or '').strip() or None,
                        'grounding_rod': (find_column(row, ['Grounding Rod', 'Grounding', 'Ground Rod', 'grounding rod']) or '').strip() or None,
                        'circuit': (find_column(row, ['Circuit', 'Circuit ID', 'circuit id']) or '').strip() or None,
                        'l2_conductor_size': (find_column(row, ['L2', 'L2 Size', 'l2']) or '').strip() or None,
                        'l1_conductor_size': (find_column(row, ['L1', 'L1 Size', 'l1']) or '').strip() or None,
                        'status': 'active',
                    }
                
                # Extract meter data with flexible column name matching
                meter_id = (find_column(row, ['kWhr Meter', 'Meter', 'Meter ID', 'Serial Number', 'meter id', 'meter']) or '').strip() or None
                meter_brand = (find_column(row, ['Brand', 'Manufacturer', 'Meter Brand', 'meter brand']) or '').strip() or None
                
                if meter_id or meter_brand:
                    # Update post with latest meter info
                    posts_data[pole_number]['meter_id'] = meter_id
                    posts_data[pole_number]['meter_brand'] = meter_brand
        
        print(f"\n✓ Processed {row_count} rows ({skipped} skipped - missing pole number or coordinates)")
        print(f"✓ Found {len(posts_data)} unique poles\n")
        
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Import into database
    with app.app_context():
        print("📝 Importing into database...")
        imported = 0
        updated = 0
        errors = []
        
        for pole_number, post_data in posts_data.items():
            try:
                existing_post = Post.query.filter_by(pole_number=pole_number).first()
                
                if existing_post:
                    # Update existing post
                    for key, value in post_data.items():
                        setattr(existing_post, key, value)
                    updated += 1
                    print(f"  ✓ Updated: {pole_number}")
                else:
                    # Create new post
                    new_post = Post(**post_data)
                    db.session.add(new_post)
                    imported += 1
                    print(f"  ✓ Added: {pole_number}")
                
                # Flush to prevent integrity issues
                db.session.flush()
                
            except Exception as e:
                errors.append(f"Pole {pole_number}: {str(e)}")
                db.session.rollback()
                continue
        
        try:
            db.session.commit()
            print(f"\n✓ Imported {imported} new poles")
            print(f"✓ Updated {updated} existing poles")
            if errors:
                print(f"\n⚠️  {len(errors)} errors encountered:")
                for err in errors[:5]:  # Show first 5 errors
                    print(f"   - {err}")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Database commit failed: {e}")


if __name__ == '__main__':
    print("=" * 70)
    print("⚡ ELECTRICAL DISTRIBUTION POST DATA IMPORTER")
    print("=" * 70)
    print("\n✓ Flexible column name handling (handles spaces, case variations)")
    print("✓ Supports: 'Pole Number', 'pole number', 'PoleNumber', etc.")
    print("\n")
    
    csv_file = 'sample (1).csv'
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    
    import_posts_from_csv(csv_file)
    
    print("\n" + "=" * 70)
    print("✓ Import process complete!")
    print("=" * 70)
