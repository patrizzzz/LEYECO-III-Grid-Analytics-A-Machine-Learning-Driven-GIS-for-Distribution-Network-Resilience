#!/usr/bin/env python3
"""Simple direct import from amonaini.csv"""
from app import app, db, infer_connections_from_posts
from models import Post
import pandas as pd

with app.app_context():
    print("Loading CSV...")
    df = pd.read_csv('amonaini.csv')
    df.columns = [c.strip() for c in df.columns]
    
    # Standard column names
    pole_col = [c for c in df.columns if 'pole' in c.lower() and 'number' in c.lower()][0]
    lat_col = [c for c in df.columns if c.lower() in ['lat', 'latitude']][0]
    lng_col = [c for c in df.columns if c.lower() in ['long', 'longitude', 'lon', 'lng']][0]
    feeder_col = [c for c in df.columns if 'feeder' in c.lower()][0] if any('feeder' in c.lower() for c in df.columns) else None
    circuit_col = [c for c in df.columns if 'circuit' in c.lower()][0] if any('circuit' in c.lower() for c in df.columns) else None
    bus_col = [c for c in df.columns if 'primary bus' in c.lower()][0] if any('primary bus' in c.lower() for c in df.columns) else None
    kva_col = [c for c in df.columns if 'kva' in c.lower()][0] if any('kva' in c.lower() for c in df.columns) else None
    
    print(f"Columns: pole={pole_col}, lat={lat_col}, lng={lng_col}")
    
    posts_by_pole = {}
    for _, row in df.iterrows():
        pole = str(row[pole_col]).strip()
        if not pole or pole in posts_by_pole:
            continue
        
        try:
            lat = float(row[lat_col])
            lng = float(row[lng_col])
        except:
            continue
        
        if lat == 0 or lng == 0:
            continue
        
        posts_by_pole[pole] = {
            'pole_number': pole,
            'name': f"Post {pole}",
            'lat': lat,
            'lng': lng,
            'feeder': row[feeder_col] if feeder_col else None,
            'circuit': row[circuit_col] if circuit_col else None,
            'primary_bus_id': row[bus_col] if bus_col else pole,
            'kva_rating': float(row[kva_col]) if kva_col else None,
        }
    
    print(f"Importing {len(posts_by_pole)} unique poles...")
    for post_data in posts_by_pole.values():
        # Remove None values
        clean_data = {k: v for k, v in post_data.items() if v not in [None, '', 'nan', 0]}
        post = Post(**clean_data)
        db.session.add(post)
    
    db.session.commit()
    print(f"Created {len(posts_by_pole)} posts")
    
    # Infer connections
    print("Inferring connections...")
    infer_connections_from_posts()
    
    from models import LineConnection
    posts_count = Post.query.count()
    conns_count = LineConnection.query.count()
    print(f"Final: {posts_count} posts, {conns_count} connections")
