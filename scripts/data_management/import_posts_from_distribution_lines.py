#!/usr/bin/env python3
"""
Import unique bus IDs from a distribution-lines CSV (EXAMPLEDATA.csv) as Post records.
Fixed to use pandas for robust column parsing.
"""

import sys
import pandas as pd
from pathlib import Path
from app import app, db
from utils.network_utils import infer_connections_from_posts
from models import Post


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


def sanitize_float(v):
    if v is None or pd.isna(v):
        return None
    try:
        return float(v)
    except Exception:
        return None


def import_buses(csv_file):
    p = Path(csv_file)
    if not p.exists():
        print(f"File not found: {csv_file}")
        return

    with app.app_context():
        print("=" * 80)
        print("IMPORTING POSTS FROM DISTRIBUTION LINES")
        print("=" * 80)

        try:
            df = pd.read_csv(csv_file, encoding='utf-8-sig')
            df.columns = [normalize_column_name(c) for c in df.columns]

            print(f"Loaded {len(df)} rows from {csv_file}")

            def get_val(r, base):
                """Helper to get value with multiple name variations"""
                base = base.replace(' ', '_').lower()
                # Direct match
                if base in r: return r[base]
                # Try common suffixes from normalization
                for suffix in ['_meters', '_c', '_id', '_unit', '_strands', '_meters_1', '_meters_2', '_normalized']:
                    if base + suffix in r: return r[base + suffix]
                # Try prefix-based matching
                for col in r.index:
                    if col.startswith(base): return r[col]
                return None

            stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
            seen_buses = set()

            for idx, row in df.iterrows():
                from_bus = str(get_val(row, 'from_bus') or '').strip()
                to_bus = str(get_val(row, 'to_bus') or '').strip()
                
                lat = sanitize_float(get_val(row, 'latitude') or get_val(row, 'lat'))
                lng = sanitize_float(get_val(row, 'longitude') or get_val(row, 'lng'))

                # Technical data for the pole
                tech_data = {
                    'configuration': str(get_val(row, 'configuration') or '').strip() or None,
                    'system_grounding_type': str(get_val(row, 'system_grounding_type') or '').strip() or None,
                    'conductor_type': str(get_val(row, 'conductor_type') or '').strip() or None,
                    'pri_conductor_size': str(get_val(row, 'conductor_size') or '').strip() or None,
                    'conductor_unit': str(get_val(row, 'conductor_unit') or get_val(row, 'unit_c') or '').strip() or None,
                    'conductor_strands': str(get_val(row, 'conductor_strands') or get_val(row, 'strands_c') or '').strip() or None,
                    'neutral_wire': str(get_val(row, 'neutral_wire_type') or '').strip() or None,
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
                }

                for bus in (from_bus, to_bus):
                    if not bus or bus == 'nan' or bus in seen_buses:
                        continue
                    
                    seen_buses.add(bus)
                    
                    post_data = {
                        'pole_number': bus,
                        'name': f'Post {bus}',
                        'primary_bus_id': bus,
                        'status': 'active'
                    }
                    if lat is not None and lng is not None:
                        post_data['lat'] = lat
                        post_data['lng'] = lng
                    else:
                        post_data['lat'] = 0.0
                        post_data['lng'] = 0.0

                    # Only from_bus gets the technical data from this row
                    if bus == from_bus:
                        post_data.update(tech_data)

                    existing = Post.query.filter_by(pole_number=bus).first()
                    if existing:
                        for k, v in post_data.items():
                            setattr(existing, k, v)
                        stats['updated'] += 1
                    else:
                        db.session.add(Post(**post_data))
                        stats['created'] += 1

                if (stats['created'] + stats['updated']) % 100 == 0:
                    db.session.flush()

            db.session.commit()
            print(f"Post import complete. Created: {stats['created']}, Updated: {stats['updated']}")

            # Try to infer connections after import
            try:
                print("Inferring connections from posts...")
                infer_connections_from_posts()
                print("Connections inferred.")
            except Exception as e:
                print(f"Connection inference failed: {e}")

        except Exception as e:
            print(f"Import failed: {e}")
            db.session.rollback()


if __name__ == '__main__':
    csv_file = sys.argv[1] if len(sys.argv) > 1 else 'EXAMPLEDATA.csv'
    import_buses(csv_file)
