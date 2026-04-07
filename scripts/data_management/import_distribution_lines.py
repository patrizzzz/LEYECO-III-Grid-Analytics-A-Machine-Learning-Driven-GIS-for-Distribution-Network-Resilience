#!/usr/bin/env python3
"""
Import Distribution Line Segment data from CSV file.
Compatible with EXAMPLEDATA.csv format.
"""
import sys
import pandas as pd
from pathlib import Path
from app import app, db
from models import DistributionLineSegment

def normalize_column_name(name):
    """Normalize column name for flexible matching"""
    if not name:
        return ''
    normalized = str(name).strip().lower()
    # Remove extra spaces and standardize
    normalized = ' '.join(normalized.split())  # Collapse multiple spaces to single
    # Replace spaces and special chars
    normalized = normalized.replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
    # Remove consecutive underscores
    while '__' in normalized:
        normalized = normalized.replace('__', '_')
    return normalized

def sanitize_float(value):
    """Convert value to float, return None if invalid or NaN. Strips commas for number strings."""
    import math
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    s = str(value).strip()
    if s == '' or s.lower() == 'nan':
        return None
    s = s.replace(',', '')
    try:
        f = float(s)
        if math.isnan(f):
            return None
        return f
    except (ValueError, AttributeError, TypeError):
        return None

def sanitize_string(value):
    """Convert value to string, return None if invalid or nan"""
    if not value or str(value).strip() == '' or str(value).strip().lower() == 'nan':
        return None
    s = str(value).strip()
    return s if s else None

def import_distribution_lines(csv_file):
    """Import distribution line segments from CSV file"""
    
    if not Path(csv_file).exists():
        print(f"❌ File not found: {csv_file}")
        return False
    
    with app.app_context():
        print("=" * 80)
        print("⚡ IMPORTING DISTRIBUTION LINE SEGMENTS")
        print("=" * 80)
        print()
        
        try:
            # Read CSV (utf-8-sig strips BOM so column names are correct)
            df = pd.read_csv(csv_file, encoding='utf-8-sig')
            # Strip whitespace from column names so "Unit (C) " etc. match
            df.columns = [str(c).strip().strip('\r\n') if c else '' for c in df.columns]
            
            # Normalize column names for flexible matching
            column_map = {}
            for col in df.columns:
                normalized = normalize_column_name(col)
                column_map[col] = normalized
            df.rename(columns=column_map, inplace=True)
            
            print(f"📂 Loaded {len(df)} rows from {csv_file}")
            print(f"📋 Columns: {list(df.columns)[:5]}... ({len(df.columns)} total)")
            print()
            
            # Ensure all column names are normalized (idempotent)
            df.columns = [normalize_column_name(c) for c in df.columns]
            
            def get_val(r, base):
                """Helper to get value with multiple name variations"""
                base = base.lower()
                # Direct match
                if base in r: return r[base]
                # Try common suffixes from normalization
                for suffix in ['_meters', '_c', '_id', '_unit', '_strands', '_meters_1', '_meters_2', '_normalized']:
                    if base + suffix in r: return r[base + suffix]
                # Try prefix-based matching for cases like "Primary Distribution Line Segment ID"
                for col in r.index:
                    if col.startswith(base): return r[col]
                return None

            imported = 0
            skipped = 0
            duplicates = 0
            errors = 0
            
            for idx, row in df.iterrows():
                try:
                    # Required fields - with multiple name variations
                    segment_id = str(
                        get_val(row, 'primary_distribution_line_segment') or 
                        get_val(row, 'segment') or
                        row.get('segment_id') or
                        ''
                    ).strip()
                    
                    from_bus = str(get_val(row, 'from_bus') or '').strip()
                    to_bus = str(get_val(row, 'to_bus') or '').strip()
                    
                    if not segment_id or not from_bus or not to_bus:
                        skipped += 1
                        continue
                    
                    # Field preparation
                    line_data = {
                        'phasing': sanitize_string(get_val(row, 'phasing')),
                        'configuration': sanitize_string(get_val(row, 'configuration')),
                        'system_grounding_type': sanitize_string(get_val(row, 'system_grounding_type')),
                        'length_meters': sanitize_float(get_val(row, 'length_meters') or get_val(row, 'length')),
                        'conductor_type': sanitize_string(get_val(row, 'conductor_type')),
                        'conductor_size': sanitize_string(get_val(row, 'conductor_size')),
                        'conductor_unit': sanitize_string(get_val(row, 'conductor_unit') or get_val(row, 'unit_c')),
                        'conductor_strands': sanitize_string(get_val(row, 'conductor_strands') or get_val(row, 'strands_c')),
                        'neutral_wire_type': sanitize_string(get_val(row, 'neutral_wire_type')),
                        'neutral_wire_size': sanitize_string(get_val(row, 'neutral_wire_size')),
                        'neutral_wire_unit': sanitize_string(get_val(row, 'neutral_wire_unit') or get_val(row, 'unit_nw')),
                        'neutral_wire_strands': sanitize_string(get_val(row, 'neutral_wire_strands') or get_val(row, 'strands_nw')),
                        'spacing_d12': sanitize_float(get_val(row, 'spacing_d12')),
                        'spacing_d23': sanitize_float(get_val(row, 'spacing_d23')),
                        'spacing_d13': sanitize_float(get_val(row, 'spacing_d13')),
                        'spacing_d1n': sanitize_float(get_val(row, 'spacing_d1n')),
                        'spacing_d2n': sanitize_float(get_val(row, 'spacing_d2n')),
                        'spacing_d3n': sanitize_float(get_val(row, 'spacing_d3n')),
                        'spacing_dc1_c2': sanitize_float(get_val(row, 'spacing_dc1_c2')),
                        'height_h1': sanitize_float(get_val(row, 'height_h1')),
                        'height_h2': sanitize_float(get_val(row, 'height_h2')),
                        'height_h3': sanitize_float(get_val(row, 'height_h3')),
                        'height_hn': sanitize_float(get_val(row, 'height_hn')),
                        'earth_resistivity': sanitize_float(get_val(row, 'earth_resistivity')),
                        'latitude': sanitize_float(get_val(row, 'latitude')),
                        'longitude': sanitize_float(get_val(row, 'longitude')),
                    }

                    # Check if already exists
                    existing = DistributionLineSegment.query.filter_by(segment_id=segment_id).first()
                    if existing:
                        for k, v in line_data.items():
                            setattr(existing, k, v)
                        # Also update the basic IDs if needed
                        existing.from_bus_id = from_bus
                        existing.to_bus_id = to_bus
                        duplicates += 1
                        continue
                    
                    # Create new
                    line = DistributionLineSegment(
                        segment_id=segment_id,
                        from_bus_id=from_bus,
                        to_bus_id=to_bus,
                        **line_data
                    )
                    
                    db.session.add(line)
                    imported += 1
                    
                    if (imported + duplicates) % 50 == 0:
                        print(f"  ✓ Processed {imported + duplicates} lines...")
                    
                except Exception as e:
                    errors += 1
                    print(f"  ⚠️  Row {idx + 2}: {str(e)}")
            
            # Commit all changes
            db.session.commit()
            print()
            print("=" * 80)
            print("✅ IMPORT COMPLETE")
            print("=" * 80)
            print(f"  Imported:   {imported} lines")
            print(f"  Duplicates: {duplicates} (skipped)")
            print(f"  Skipped:    {skipped} (missing required fields)")
            print(f"  Errors:     {errors}")
            print()
            
            total = DistributionLineSegment.query.count()
            print(f"📊 Total in database: {total} distribution lines")
            print()
            return True
            
        except Exception as e:
            print(f"❌ Import failed: {str(e)}")
            db.session.rollback()
            return False

if __name__ == '__main__':
    csv_file = sys.argv[1] if len(sys.argv) > 1 else 'EXAMPLEDATA.csv'
    success = import_distribution_lines(csv_file)
    sys.exit(0 if success else 1)
