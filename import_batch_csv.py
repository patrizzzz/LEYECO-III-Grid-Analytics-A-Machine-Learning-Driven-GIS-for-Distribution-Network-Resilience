#!/usr/bin/env python3
"""
Batch import multiple CSV files into the database.
Handles multiple electrical post data CSV files and imports them all at once.

Usage:
    python import_batch_csv.py "file1.csv" "file2.csv" "file3.csv"
    
Or import all CSV files from a directory:
    python import_batch_csv.py "data/*.csv"
"""

import csv
import sys
import glob
from pathlib import Path
from datetime import datetime
from app import app, db
from models import Post, Meter

def sanitize_float(value):
    """Convert value to float, return None if invalid"""
    if not value or str(value).strip() == '':
        return None
    try:
        return float(value)
    except (ValueError, AttributeError, TypeError):
        return None

def normalize_column_name(name):
    """Normalize column name for flexible matching"""
    if not name:
        return ""
    return str(name).strip().lower().replace(' ', '_')

def find_column(row, possible_names):
    """Find column value using flexible matching"""
    if not row or not possible_names:
        return None
    
    normalized_targets = [normalize_column_name(n) for n in possible_names]
    
    for key in row.keys():
        normalized_key = normalize_column_name(key)
        if normalized_key in normalized_targets:
            return row[key]
    
    return None

def import_single_csv(csv_file, posts_data):
    """
    Import a single CSV file and consolidate data into posts_data dict.
    Returns: (rows_processed, rows_skipped, poles_found)
    """
    if not Path(csv_file).exists():
        print(f"  ❌ File not found: {csv_file}")
        return 0, 0, 0
    
    rows_processed = 0
    rows_skipped = 0
    poles_in_file = 0
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            if not reader.fieldnames:
                print(f"  ❌ CSV appears empty: {csv_file}")
                return 0, 0, 0
            
            for row in reader:
                rows_processed += 1
                
                # Extract pole number with flexible column matching
                pole_number = (find_column(row, ['Pole Number', 'pole_number', 'pole number', 'Pole#', 'PoleNumber']) or '').strip()
                if not pole_number:
                    rows_skipped += 1
                    continue
                
                # Get coordinates
                lat = sanitize_float(find_column(row, ['Lat', 'Latitude', 'lat', 'LAT', 'latitude']))
                lng = sanitize_float(find_column(row, ['Long', 'Longitude', 'Lon', 'lng', 'LONG', 'LON', 'longitude']))
                
                if lat is None or lng is None:
                    rows_skipped += 1
                    continue
                
                # First time seeing this pole - create record
                if pole_number not in posts_data:
                    poles_in_file += 1
                    posts_data[pole_number] = {
                        'pole_number': pole_number,
                        'name': f"Post {pole_number}",
                        'lat': lat,
                        'lng': lng,
                        'area': (find_column(row, ['Lat, Long', 'Area', 'area', 'Area Name']) or '').strip() or None,
                        'feeder': (find_column(row, ['Feeder', 'feeder', 'Feeder Name', 'feeder name']) or '').strip() or None,
                        'pri_structure': (find_column(row, ['Pri. Structure', 'Primary Structure', 'pri structure']) or '').strip() or None,
                        'pri_conductor_size': (find_column(row, ['Conductor Size', 'Pri Conductor Size', 'conductor size']) or '').strip() or None,
                        'neutral_wire': (find_column(row, ['Neutral Wire', 'Neutral', 'neutral wire']) or '').strip() or None,
                        'configuration': (find_column(row, ['Configuration', 'Config', 'configuration']) or '').strip() or None,
                        'phasing': (find_column(row, ['Phasing', 'Phase', 'phasing']) or '').strip() or None,
                        'primary_bus_id': (find_column(row, ['Primary Bus ID', 'Pri Bus', 'Primary Bus']) or '').strip() or None,
                        'sec_structure': (find_column(row, ['Sec. Structure', 'Secondary Structure']) or '').strip() or None,
                        'sec_conductor_size': (find_column(row, ['Sec Conductor Size']) or '').strip() or None,
                        'sec_type': (find_column(row, ['Tpye', 'Type', 'Sec Type']) or '').strip() or None,
                        'conductor_type': (find_column(row, ['Conductor Type', 'Material']) or '').strip() or None,
                        'sec_bus_id': (find_column(row, ['Sec. Bus ID', 'Secondary Bus']) or '').strip() or None,
                        'kva_rating': sanitize_float(find_column(row, ['kVA Rating', 'kVA', 'Rating'])),
                        'common_sole': (find_column(row, ['Common/Sole', 'Common Sole']) or '').strip() or None,
                        'transformer_bus_id': (find_column(row, ['Transformer Bus ID', 'Transformer Bus']) or '').strip() or None,
                        'transformer_phasing': (find_column(row, ['Transformer Phasing']) or '').strip() or None,
                        'grounding_rod': (find_column(row, ['Grounding Rod', 'Grounding']) or '').strip() or None,
                        'circuit': (find_column(row, ['Circuit', 'Circuit ID']) or '').strip() or None,
                        'l2_conductor_size': (find_column(row, ['L2', 'L2 Size']) or '').strip() or None,
                        'l1_conductor_size': (find_column(row, ['L1', 'L1 Size']) or '').strip() or None,
                        'status': 'active',
                    }
                
                # Extract meter data
                meter_id = (find_column(row, ['kWhr Meter', 'Meter', 'Meter ID', 'Serial Number']) or '').strip() or None
                meter_brand = (find_column(row, ['Brand', 'Manufacturer', 'Meter Brand']) or '').strip() or None
                
                if meter_id or meter_brand:
                    posts_data[pole_number]['meter_id'] = meter_id
                    posts_data[pole_number]['meter_brand'] = meter_brand
        
        return rows_processed, rows_skipped, poles_in_file
        
    except Exception as e:
        print(f"  ❌ Error reading {csv_file}: {e}")
        return 0, 0, 0

def import_batch_csv(csv_files):
    """
    Import multiple CSV files and populate database.
    """
    if not csv_files:
        print("❌ No CSV files provided!")
        return
    
    # Expand glob patterns and get all files
    all_files = []
    for pattern in csv_files:
        matches = glob.glob(pattern)
        if not matches:
            # Try as direct file path
            if Path(pattern).exists():
                all_files.append(pattern)
            else:
                print(f"⚠️  No files matching: {pattern}")
        else:
            all_files.extend(matches)
    
    if not all_files:
        print("❌ No valid CSV files found!")
        return
    
    print("=" * 70)
    print("⚡ BATCH ELECTRICAL POST DATA IMPORTER")
    print("=" * 70)
    print(f"\n📂 Found {len(all_files)} CSV file(s) to import:\n")
    
    for f in all_files:
        print(f"   • {f}")
    
    print("\n" + "-" * 70)
    
    # Consolidate data from all files
    posts_data = {}
    total_rows = 0
    total_skipped = 0
    total_files = 0
    
    for csv_file in all_files:
        rows, skipped, poles = import_single_csv(csv_file, posts_data)
        if rows > 0:
            print(f"✓ {Path(csv_file).name}: {rows} rows, {poles} new poles")
            total_rows += rows
            total_skipped += skipped
            total_files += 1
    
    print("\n" + "-" * 70)
    print(f"\n📊 CONSOLIDATION SUMMARY:")
    print(f"   Total rows processed: {total_rows}")
    print(f"   Total rows skipped: {total_skipped}")
    print(f"   Total unique poles: {len(posts_data)}")
    
    if len(posts_data) == 0:
        print("\n❌ No poles found in any CSV files. Check column names!")
        return
    
    print(f"\n📝 Importing {len(posts_data)} poles into database...")
    print("-" * 70 + "\n")
    
    # Import into database
    with app.app_context():
        imported = 0
        updated = 0
        errors = []
        
        for pole_number, post_data in posts_data.items():
            try:
                existing_post = Post.query.filter_by(pole_number=pole_number).first()
                
                if existing_post:
                    for key, value in post_data.items():
                        setattr(existing_post, key, value)
                    updated += 1
                    print(f"  ✓ Updated: {pole_number}")
                else:
                    new_post = Post(**post_data)
                    db.session.add(new_post)
                    imported += 1
                    print(f"  ✓ Added: {pole_number}")
                
                db.session.flush()
                
            except Exception as e:
                errors.append(f"Pole {pole_number}: {str(e)}")
                db.session.rollback()
                continue
        
        try:
            db.session.commit()
            print(f"\n{'=' * 70}")
            print("✓ IMPORT SUCCESSFUL")
            print("=" * 70)
            print(f"✓ Imported {imported} new poles")
            print(f"✓ Updated {updated} existing poles")
            print(f"✓ Total poles in database: {imported + updated}")
            
            if errors:
                print(f"\n⚠️  {len(errors)} errors encountered:")
                for err in errors[:5]:
                    print(f"   - {err}")
                    
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Database commit failed: {e}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("=" * 70)
        print("⚡ BATCH CSV IMPORTER")
        print("=" * 70)
        print("\nUsage:")
        print("  python import_batch_csv.py file1.csv file2.csv file3.csv")
        print("  python import_batch_csv.py \"data/*.csv\"")
        print("  python import_batch_csv.py \"sample (1).csv\" \"sample (2).csv\"")
        print("\n" + "=" * 70)
        sys.exit(1)
    
    csv_files = sys.argv[1:]
    import_batch_csv(csv_files)
