#!/usr/bin/env python3
"""Direct import without Unicode printing"""
from app import app, db
from models import Post, LineConnection
import pandas as pd

with app.app_context():
    # Clear existing
    Post.query.delete()
    LineConnection.query.delete()
    db.session.commit()
    
    # Read and import
    df = pd.read_csv('amonaini.csv')
    df.columns = df.columns.str.strip()
    
    posts_map = {}
    for _, row in df.iterrows():
        pole_num = str(row.get('Pole Number', '')).strip()
        if not pole_num or pole_num in posts_map:
            continue
        
        try:
            lat = float(row.get('Lat', 0))
            lng = float(row.get('Long', 0))
            if not lat or not lng:
                continue
        except:
            continue
        
        posts_map[pole_num] = {
            'pole_number': pole_num,
            'name': f"Post {pole_num}",
            'lat': lat,
            'lng': lng,
            'feeder': str(row.get('Feeder', '')).strip() or None,
            'circuit': str(row.get('Circuit', '')).strip() or None,
            'primary_bus_id': str(row.get('Primary Bus ID', '')).strip() or pole_num,
            'kva_rating': float(row['kVA Rating']) if pd.notna(row.get('kVA Rating')) else None,
        }
    
    # Insert all posts
    for post_data in posts_map.values():
        post = Post(**post_data)
        db.session.add(post)
    
    db.session.commit()
    
    # Infer connections
    from app import infer_connections_from_posts
    infer_connections_from_posts()
    
    total_posts = Post.query.count()
    total_conns = LineConnection.query.count()
    print(f"Restored: {total_posts} posts, {total_conns} connections")
