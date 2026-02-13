#!/usr/bin/env python3
"""
Command-line importer for distribution transformers (example2.csv style).
Creates/updates `DistributionTransformer` records and attempts to create
`LineConnection` entries linking the transformer's `from_primary_bus_id`
to its `to_secondary_bus_id` where possible (links to `Post` via primary_bus_id).

Usage: python import_transformers.py example2.csv
"""

import csv
import sys
from pathlib import Path
from app import app, db
from models import DistributionTransformer, Post, LineConnection


def normalize_column_name(name):
    if not name:
        return ''
    import re
    # collapse any whitespace (spaces, newlines, tabs) to single underscore
    return re.sub(r"\s+", "_", str(name).strip().lower())


def find_value(row, choices):
    """Flexible lookup in a CSV row (dict) using multiple possible header names."""
    if not row:
        return None
    targets = [normalize_column_name(c) for c in choices]
    for k, v in row.items():
        if normalize_column_name(k) in targets:
            return str(v).strip() if v is not None else None
    return None


def sanitize_float(v):
    if v is None or str(v).strip() == '':
        return None
    try:
        return float(v)
    except Exception:
        return None


def import_transformers(csv_file):
    p = Path(csv_file)
    if not p.exists():
        print(f"File not found: {csv_file}")
        return

    with open(p, 'r', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    if not rows:
        print('No data rows found in file')
        return

    created = 0
    updated = 0
    skipped = 0
    errors = []

    with app.app_context():
        for i, row in enumerate(rows, start=2):
            try:
                transformer_id = find_value(row, ['Transformer ID', 'Distribution Transformer ID', 'transformer_id', 'distribution transformer id']) or ''
                from_bus = find_value(row, ['From Primary Bus ID', 'From_Primary_Bus_ID', 'from_primary_bus_id', 'from bus id', 'from_bus_id']) or ''
                to_bus = find_value(row, ['To Secondary Bus ID', 'To_Secondary_Bus_ID', 'to_secondary_bus_id', 'to bus id', 'to_bus_id']) or ''

                if not transformer_id or not from_bus:
                    skipped += 1
                    errors.append({'row': i, 'error': 'transformer_id and from_primary_bus_id required'})
                    continue

                def get_str(names):
                    return find_value(row, names)

                def get_float(names):
                    return sanitize_float(find_value(row, names))

                data = {
                    'transformer_id': transformer_id,
                    'from_primary_bus_id': from_bus,
                    'to_secondary_bus_id': get_str(['To Secondary Bus ID', 'to_secondary_bus_id', 'to bus id']),
                    'primary_phasing': get_str(['Primary Phasing', 'primary_phasing']),
                    'secondary_phasing': get_str(['Secondary Phasing', 'secondary_phasing']),
                    'installation_type': get_str(['Installation Type', 'installation_type']),
                    'no_dts_in_bank': (lambda x: int(x) if x and str(x).strip().isdigit() else None)(find_value(row, ['No. DTs in Bank', 'No DTs in Bank', 'no_dts_in_bank'])),
                    'connection': get_str(['Connection', 'connection']),
                    'kva_rating': get_float(['kVA Rating', 'KVA Rating', 'kva_rating']),
                    'primary_voltage_kv': get_float(['Primary Voltage Rating(kV)', 'Primary Voltage Rating (kV)', 'primary_voltage_kv']),
                    'secondary_voltage_kv': get_float(['Secondary Voltage Rating (kV)', 'secondary_voltage_kv']),
                    'primary_tap_kv': get_float(['Primary Tap Voltage (kV)', 'primary_tap_kv']),
                    'secondary_tap_kv': get_float(['Secondary Tap Voltage (kV)', 'secondary_tap_kv']),
                    'pct_z': get_float(['%Z', 'pct_z']),
                    'xr_ratio': get_float(['X/R Ratio', 'xr_ratio']),
                    'no_load_loss_kw': get_float(['No-Load Loss (kW)', 'no_load_loss_kw']),
                    'exciting_current_pct': get_float(['Exciting Current (%)', 'exciting_current_pct']),
                }

                # Upsert transformer
                existing = DistributionTransformer.query.filter_by(transformer_id=transformer_id, from_primary_bus_id=from_bus).first()
                if existing:
                    for k, v in data.items():
                        if v is not None:
                            setattr(existing, k, v)
                    updated += 1
                else:
                    new = DistributionTransformer(**{k: v for k, v in data.items() if v is not None})
                    db.session.add(new)
                    created += 1

                # If there's a to_bus value, try to create a LineConnection linking them
                if data.get('to_secondary_bus_id'):
                    from_bus_val = from_bus
                    to_bus_val = data.get('to_secondary_bus_id')

                    # Prefer using the post's primary_bus_id if a Post exists matching from_bus
                    post = Post.query.filter((Post.primary_bus_id == from_bus) | (Post.pole_number == from_bus)).first()
                    if post and post.primary_bus_id:
                        from_bus_val = post.primary_bus_id

                    # Avoid duplicates - unique constraint handled in model but check first
                    existing_conn = LineConnection.query.filter_by(from_bus=from_bus_val, to_bus=to_bus_val, connection_type='Transformer').first()
                    if not existing_conn:
                        conn = LineConnection(from_bus=from_bus_val, to_bus=to_bus_val, connection_type='Transformer', feeder=None, circuit=None)
                        db.session.add(conn)

                # periodically flush
                if (created + updated) % 100 == 0:
                    db.session.flush()

            except Exception as e:
                errors.append({'row': i, 'error': str(e)})
                db.session.rollback()

        try:
            db.session.commit()
        except Exception as e:
            print('Database commit failed:', e)
            db.session.rollback()

    print(f"Done. Created: {created}, Updated: {updated}, Skipped: {skipped}, Errors: {len(errors)}")
    if errors:
        for e in errors[:10]:
            print('  -', e)


if __name__ == '__main__':
    csv_file = 'example2.csv'
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    import_transformers(csv_file)
