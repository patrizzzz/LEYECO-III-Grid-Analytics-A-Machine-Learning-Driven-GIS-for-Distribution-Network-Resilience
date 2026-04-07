#!/usr/bin/env python3
"""
Importer for Secondary Customer Service Drops (exampleSLD.csv style).
Updates/Creates SecondaryServiceDrop records with technical data.
"""

import sys
import pandas as pd
from pathlib import Path
from app import app, db
from models import SecondaryServiceDrop
import re

def normalize_column_name(name):
    if not name or pd.isna(name): return ''
    normalized = str(name).strip().lower()
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = normalized.replace('(', '').replace(')', '').replace('-', '_').replace(' ', '_')
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

def import_service_drops(csv_file):
    if not Path(csv_file).exists():
        print(f"File not found: {csv_file}")
        return

    with app.app_context():
        print("=" * 80)
        print("IMPORTING SECONDARY SERVICE DROPS")
        print("=" * 80)

        try:
            df = pd.read_csv(csv_file, encoding='utf-8-sig')
            df.columns = [normalize_column_name(c) for c in df.columns]
            print(f"Loaded {len(df)} rows.")

            created, updated, skipped, errors = 0, 0, 0, 0

            for idx, row in df.iterrows():
                drop_id = sanitize_string(row.get('secondary_customer_service_drop_id') or row.get('service_drop_id'))
                from_bus = sanitize_string(row.get('from_bus_id'))
                to_cust = sanitize_string(row.get('to_customer_id'))

                if not drop_id or not from_bus:
                    skipped += 1
                    continue

                data = {
                    'service_drop_id': drop_id,
                    'from_bus_id': from_bus,
                    'to_customer_id': to_cust,
                    'phasing': sanitize_string(row.get('phasing')),
                    'installation_type': sanitize_string(row.get('installation_type')),
                    'length_meters_1': sanitize_float(row.get('length_1_meters') or row.get('length_1')),
                    'length_meters_2': sanitize_float(row.get('length_2_meters') or row.get('length_2')),
                    'conductor_type': sanitize_string(row.get('conductor_type')),
                    'conductor_size': sanitize_string(row.get('conductor_size')),
                    'conductor_unit': sanitize_string(row.get('unit_c') or row.get('conductor_unit'))
                }

                existing = SecondaryServiceDrop.query.filter_by(service_drop_id=drop_id).first()
                if existing:
                    for k, v in data.items():
                        if v is not None: setattr(existing, k, v)
                    updated += 1
                else:
                    new_drop = SecondaryServiceDrop(**{k:v for k,v in data.items() if v is not None})
                    db.session.add(new_drop)
                    created += 1

            db.session.commit()
            print(f"DONE: Created {created}, Updated {updated}, Skipped {skipped}, Errors {errors}")

        except Exception as e:
            print(f"Import failed: {e}")
            db.session.rollback()

if __name__ == '__main__':
    csv_path = sys.argv[1] if len(sys.argv) > 1 else 'data/samples/csv_data/exampleSLD.csv'
    import_service_drops(csv_path)
