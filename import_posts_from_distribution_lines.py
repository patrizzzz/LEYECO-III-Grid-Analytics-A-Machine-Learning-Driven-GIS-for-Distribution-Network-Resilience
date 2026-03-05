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
    if not name or pd.isna(name):
        return ''
    import re
    return re.sub(r"\s+", "_", str(name).strip().lower()).strip('_')


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

            stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
            seen_buses = set()

            for idx, row in df.iterrows():
                from_bus = str(row.get('from_bus_id') or '').strip()
                to_bus = str(row.get('to_bus_id') or '').strip()
                
                lat = sanitize_float(row.get('latitude') or row.get('lat'))
                lng = sanitize_float(row.get('longitude') or row.get('lng') or row.get('lon'))

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
                        # Fallback for missing coords
                        post_data['lat'] = 0.0
                        post_data['lng'] = 0.0

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
