#!/usr/bin/env python3
"""
Import unique bus IDs from a distribution-lines CSV (EXAMPLEDATA.csv) as Post records.
This is a CLI helper mirroring the new web-upload behavior for distribution-line files.

Usage: python import_posts_from_distribution_lines.py EXAMPLEDATA.csv
"""
import csv
import sys
from pathlib import Path
from app import app, db, infer_connections_from_posts
from models import Post

def find_value(row, choices):
    if not row:
        return None
    keys = {k.strip().lower(): k for k in row.keys()}
    for c in choices:
        k = c.strip().lower()
        if k in keys:
            v = row[keys[k]]
            return str(v).strip() if v is not None else None
    return None

def sanitize_float(v):
    if v is None or str(v).strip() == '':
        return None
    try:
        return float(v)
    except Exception:
        return None

def import_buses(csv_file):
    p = Path(csv_file)
    if not p.exists():
        print('File not found:', csv_file)
        return

    with open(p, 'r', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    if not rows:
        print('No rows in file')
        return

    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}

    with app.app_context():
        seen = set()
        for i, row in enumerate(rows, start=2):
            try:
                from_bus = (find_value(row, ['From_Bus_ID', 'From_Bus', 'from_bus_id', 'from bus id']) or '').strip()
                to_bus = (find_value(row, ['To_Bus_ID', 'To_Bus', 'to_bus_id', 'to bus id']) or '').strip()
                lat = sanitize_float(find_value(row, ['latitude', 'lat']))
                lng = sanitize_float(find_value(row, ['longitude', 'lon', 'lng']))

                for bus in (from_bus, to_bus):
                    if not bus or bus in seen:
                        continue
                    seen.add(bus)
                    post_data = {'pole_number': bus, 'name': f'Post {bus}', 'primary_bus_id': bus, 'status': 'active'}
                    if lat is not None and lng is not None:
                        post_data['lat'] = lat
                        post_data['lng'] = lng

                    existing = Post.query.filter_by(pole_number=post_data['pole_number']).first()
                    if existing:
                        for k, v in post_data.items():
                            setattr(existing, k, v)
                        stats['updated'] += 1
                    else:
                        db.session.add(Post(**post_data))
                        stats['created'] += 1

            except Exception as e:
                stats['errors'].append({'row': i, 'error': str(e)})
                stats['skipped'] += 1

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print('DB commit error:', e)

        # Try to infer connections after import
        try:
            infer_connections_from_posts()
        except Exception:
            pass

    print('Import complete:', stats)


if __name__ == '__main__':
    csv_file = sys.argv[1] if len(sys.argv) > 1 else 'EXAMPLEDATA.csv'
    import_buses(csv_file)
