#!/usr/bin/env python3
"""
Importer for Secondary Distribution Lines (exampleSL.csv style).
Updates/Creates SecondaryLineSegment records with technical data.
"""

import sys
import pandas as pd
from pathlib import Path
from app import app, db
from models import SecondaryLineSegment
import re

def normalize_column_name(name):
    if not name or pd.isna(name): return ''
    normalized = str(name).strip().lower()
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = normalized.replace('(', '').replace(')', '').replace('-', '_')
    while '__' in normalized: normalized = normalized.replace('__', '_')
    return normalized.strip('_')

def sanitize_float(value):
    if value is None or (isinstance(value, float) and pd.isna(value)): return None
    try:
        s = str(value).strip().replace(',', '')
        return float(s)
    except: return None

def sanitize_string(value):
    if value is None or (isinstance(value, float) and pd.isna(value)): return None
    s = str(value).strip()
    return s if s and s.lower() != 'nan' else None

def import_secondary_lines(csv_file):
    if not Path(csv_file).exists():
        print(f"File not found: {csv_file}")
        return

    with app.app_context():
        print("=" * 80)
        print("IMPORTING SECONDARY DISTRIBUTION LINES")
        print("=" * 80)

        try:
            df = pd.read_csv(csv_file, encoding='utf-8-sig')
            df.columns = [normalize_column_name(c) for c in df.columns]
            print(f"Loaded {len(df)} rows.")

            created, updated, skipped, errors = 0, 0, 0, 0

            for idx, row in df.iterrows():
                segment_id = sanitize_string(row.get('secondary_distribution_line_id') or row.get('segment_id'))
                from_bus = sanitize_string(row.get('from_bus_id'))
                to_bus = sanitize_string(row.get('to_bus_id'))

                if not segment_id or not from_bus:
                    skipped += 1
                    continue

                data = {
                    'segment_id': segment_id,
                    'from_bus_id': from_bus,
                    'to_bus_id': to_bus,
                    'phasing': sanitize_string(row.get('phasing')),
                    'installation_type': sanitize_string(row.get('installation_type')),
                    'length_meters': sanitize_float(row.get('length_meters') or row.get('length')),
                    'conductor_type': sanitize_string(row.get('conductor_type')),
                    'conductor_size': sanitize_string(row.get('conductor_size')),
                    'conductor_unit': sanitize_string(row.get('unit_c') or row.get('conductor_unit'))
                }

                existing = SecondaryLineSegment.query.filter_by(segment_id=segment_id).first()
                if existing:
                    for k, v in data.items():
                        if v is not None: setattr(existing, k, v)
                    updated += 1
                else:
                    new_seg = SecondaryLineSegment(**{k:v for k,v in data.items() if v is not None})
                    db.session.add(new_seg)
                    created += 1

            db.session.commit()
            print(f"DONE: Created {created}, Updated {updated}, Skipped {skipped}, Errors {errors}")

        except Exception as e:
            print(f"Import failed: {e}")
            db.session.rollback()

if __name__ == '__main__':
    csv_path = sys.argv[1] if len(sys.argv) > 1 else 'data/samples/csv_data/exampleSL.csv'
    import_secondary_lines(csv_path)
