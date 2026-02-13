#!/usr/bin/env python3
"""Import amonaini.csv using the app's import logic"""
from app import app, db, infer_connections_from_posts, find_column_value, sanitize_float
from models import Post
import pandas as pd
import io

with app.app_context():
    print("Loading CSV file...")
    df = pd.read_csv('amonaini.csv')
    
    # Normalize column names for finding
    df.columns = [str(c).strip() for c in df.columns]
    
    # Build header map
    header_map = {}
    for idx, col_name in enumerate(df.columns):
        if col_name:
            header_map[col_name] = idx
    
    print(f"Found {len(df)} rows, {len(header_map)} columns")
    print("Importing posts...")
    
    stats = {'created': 0, 'updated': 0, 'skipped': 0}
    
    for idx, row in df.iterrows():
        try:
            pole_number = (find_column_value(row, ['Pole Number', 'pole_number', 'pole number', 'Pole#'], header_map) or '').strip()
            
            if not pole_number:
                stats['skipped'] += 1
                continue
            
            lat = sanitize_float(find_column_value(row, ['Lat', 'Latitude', 'lat', 'LAT'], header_map))
            lng = sanitize_float(find_column_value(row, ['Long', 'Longitude', 'Lon', 'lng', 'LONG'], header_map))
            
            if lat is None or lng is None:
                stats['skipped'] += 1
                continue
            
            post_data = {
                'pole_number': pole_number,
                'name': f"Post {pole_number}",
                'lat': lat,
                'lng': lng,
                'feeder': find_column_value(row, ['Feeder', 'feeder', 'Feeder Name'], header_map),
                'primary_bus_id': find_column_value(row, ['Primary Bus ID', 'Pri Bus'], header_map) or pole_number,
                'sec_bus_id': find_column_value(row, ['Sec. Bus ID', 'Secondary Bus'], header_map),
                'transformer_bus_id': find_column_value(row, ['Transformer Bus ID', 'Transformer Bus'], header_map),
                'circuit': find_column_value(row, ['Circuit', 'Circuit ID'], header_map),
                'kva_rating': sanitize_float(find_column_value(row, ['kVA Rating', 'kVA', 'Rating'], header_map)),
            }
            
            # Remove None values
            post_data = {k: v for k, v in post_data.items() if v is not None}
            
            # Check if exists
            existing = Post.query.filter_by(pole_number=pole_number).first()
            if existing:
                stats['updated'] += 1
            else:
                new_post = Post(**post_data)
                db.session.add(new_post)
                stats['created'] += 1
            
            if (idx + 1) % 100 == 0:
                print(f"  Processed {idx + 1} rows...")
        
        except Exception as e:
            stats['skipped'] += 1
    
    db.session.commit()
    print(f"\nImport complete: {stats['created']} created, {stats['updated']} updated, {stats['skipped']} skipped")
    
    # Infer connections
    print("Inferring connections...")
    infer_connections_from_posts()
    
    from models import LineConnection
    total_posts = Post.query.count()
    total_conns = LineConnection.query.count()
    print(f"\nFinal: {total_posts} posts, {total_conns} connections")
