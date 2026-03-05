#!/usr/bin/env python3
"""
Command-line importer for distribution transformers (example2.csv style).
Creates/updates `DistributionTransformer` records and updates the linked `Post`.
Also creates `LineConnection` entries for the transformer.

Compatible with CSVs having newlines in headers like `example2.csv`.
"""

import sys
import pandas as pd
from pathlib import Path
from app import app, db
from models import DistributionTransformer, Post, LineConnection


def normalize_column_name(name):
    """Normalize column name for flexible matching, handling newlines and extra spaces."""
    if not name or pd.isna(name):
        return ''
    normalized = str(name).strip().lower()
    # Replace any whitespace sequence (including newlines) with a single underscore
    import re
    normalized = re.sub(r"\s+", "_", normalized)
    # Remove special chars but keep underscores
    normalized = normalized.replace('(', '').replace(')', '').replace('-', '_').replace('%', 'pct')
    # Remove consecutive underscores
    while '__' in normalized:
        normalized = normalized.replace('__', '_')
    return normalized.strip('_')


def sanitize_float(value):
    """Convert value to float, return None if invalid or NaN."""
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
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    return s if s and s.lower() != 'nan' else None


def import_transformers(csv_file):
    p = Path(csv_file)
    if not p.exists():
        print(f"File not found: {csv_file}")
        return

    with app.app_context():
        print("=" * 80)
        print("IMPORTING DISTRIBUTION TRANSFORMERS")
        print("=" * 80)
        print()

        try:
            # Read CSV with flexible encoding
            df = pd.read_csv(csv_file, encoding='utf-8-sig')
            
            # Normalize all column names
            original_columns = df.columns.tolist()
            df.columns = [normalize_column_name(c) for c in df.columns]
            
            print(f"Loaded {len(df)} rows from {csv_file}")
            print()

            created = 0
            updated = 0
            post_updates = 0
            skipped = 0
            errors = 0

            for idx, row in df.iterrows():
                try:
                    # Map field variations
                    transformer_id = sanitize_string(
                        row.get('distribution_transformer_id') or 
                        row.get('transformer_id') or 
                        row.get('transformer_id_num')
                    )
                    
                    from_bus = sanitize_string(
                        row.get('from_primary_bus_id') or 
                        row.get('from_bus_id') or 
                        row.get('primary_bus_id')
                    )
                    
                    if not transformer_id or not from_bus:
                        skipped += 1
                        continue

                    to_bus = sanitize_string(
                        row.get('to_secondary_bus_id') or 
                        row.get('to_bus_id') or 
                        row.get('secondary_bus_id')
                    )

                    data = {
                        'transformer_id': transformer_id,
                        'from_primary_bus_id': from_bus,
                        'to_secondary_bus_id': to_bus,
                        'primary_phasing': sanitize_string(row.get('primary_phasing')),
                        'secondary_phasing': sanitize_string(row.get('secondary_phasing')),
                        'installation_type': sanitize_string(row.get('installation_type')),
                        'no_dts_in_bank': (lambda x: int(x) if x is not None and str(x).replace('.0','').isdigit() else None)(sanitize_float(row.get('no_dts_in_bank'))),
                        'connection': sanitize_string(row.get('connection')),
                        'kva_rating': sanitize_float(row.get('kva_rating')),
                        'primary_voltage_kv': sanitize_float(row.get('primary_voltage_ratingkv')),
                        'secondary_voltage_kv': sanitize_float(row.get('secondary_voltage_rating_kv')),
                        'primary_tap_kv': sanitize_float(row.get('primary_tap_voltage_kv')),
                        'secondary_tap_kv': sanitize_float(row.get('secondary_tap_voltage_kv')),
                        'pct_z': sanitize_float(row.get('pctz')),
                        'xr_ratio': sanitize_float(row.get('x/r_ratio')),
                        'no_load_loss_kw': sanitize_float(row.get('no_load_loss_kw')),
                        'exciting_current_pct': sanitize_float(row.get('exciting_current_pct')),
                    }

                    # 1. Upsert DistributionTransformer
                    existing = DistributionTransformer.query.filter_by(
                        transformer_id=transformer_id, 
                        from_primary_bus_id=from_bus
                    ).first()
                    
                    if existing:
                        for k, v in data.items():
                            if v is not None:
                                setattr(existing, k, v)
                        updated += 1
                    else:
                        new_dt = DistributionTransformer(**{k: v for k, v in data.items() if v is not None})
                        db.session.add(new_dt)
                        created += 1

                    # 2. Update linked Post record with summary data
                    # This ensures the pole info modal shows transformer data
                    post = Post.query.filter(
                        (Post.primary_bus_id == from_bus) | 
                        (Post.pole_number == from_bus)
                    ).first()
                    
                    if post:
                        if data['kva_rating'] is not None:
                            post.kva_rating = data['kva_rating']
                        if data['primary_phasing'] is not None:
                            post.transformer_phasing = data['primary_phasing']
                        post.transformer_bus_id = transformer_id
                        post_updates += 1

                    # 3. Create LineConnection linking Primary to Secondary Side
                    if to_bus:
                        # Normalize from_bus to use the post's primary_bus_id if possible
                        from_bus_val = post.primary_bus_id if (post and post.primary_bus_id) else from_bus
                        
                        existing_conn = LineConnection.query.filter_by(
                            from_bus=from_bus_val, 
                            to_bus=to_bus, 
                            connection_type='Transformer'
                        ).first()
                        
                        if not existing_conn:
                            conn = LineConnection(
                                from_bus=from_bus_val, 
                                to_bus=to_bus, 
                                connection_type='Transformer'
                            )
                            db.session.add(conn)

                    if (created + updated) % 50 == 0:
                        db.session.flush()

                except Exception as e:
                    errors += 1
                    print(f"  ⚠️  Row {idx + 2}: {str(e)}")

            db.session.commit()
            print()
            print("=" * 80)
            print("IMPORT COMPLETE")
            print("=" * 80)
            print(f"  Created:      {created}")
            print(f"  Updated:      {updated}")
            print(f"  Post Updates: {post_updates}")
            print(f"  Skipped:      {skipped}")
            print(f"  Errors:       {errors}")
            print()

        except Exception as e:
            print(f"Import failed: {str(e)}")
            db.session.rollback()


if __name__ == '__main__':
    csv_file = sys.argv[1] if len(sys.argv) > 1 else 'example2.csv'
    import_transformers(csv_file)
