#!/usr/bin/env python3
"""Restore original data from CSV"""
from app import app, db
from models import Post
import pandas as pd

with app.app_context():
    print("Restoring data from amonaini.csv...")
    
    # Read CSV
    df = pd.read_csv('amonaini.csv')
    
    # Normalize column names
    df.columns = df.columns.str.strip()
    
    imported = 0
    for _, row in df.iterrows():
        pole_num = str(row.get('Pole Number', '')).strip() or str(row.get('pole number', '')).strip()
        if not pole_num:
            continue
            
        try:
            lat = float(row.get('Lat', row.get('latitude', 0)))
            lng = float(row.get('Long', row.get('longitude', 0)))
        except:
            continue
        
        # Check if exists
        existing = Post.query.filter_by(pole_number=pole_num).first()
        if existing:
            continue  # Skip existing
        
        post = Post(
            pole_number=pole_num,
            name=f"Post {pole_num}",
            lat=lat,
            lng=lng,
            feeder=str(row.get('Feeder', '')).strip() or None,
            circuit=str(row.get('Circuit', '')).strip() or None,
            primary_bus_id=str(row.get('Primary Bus ID', '')).strip() or pole_num,
            kva_rating=float(row['kVA Rating']) if pd.notna(row.get('kVA Rating')) else None,
        )
        db.session.add(post)
        imported += 1
        
        if imported % 100 == 0:
            print(f"  Imported {imported} posts...")
    
    db.session.commit()
    
    # Auto-infer connections
    print(f"\nImported {imported} posts, now inferring connections...")
    from app import infer_connections_from_posts
    infer_connections_from_posts()
    
    total_posts = Post.query.count()
    from models import LineConnection
    total_conns = LineConnection.query.count()
    
    print(f"\n✓ Restore complete: {total_posts} posts, {total_conns} connections")
