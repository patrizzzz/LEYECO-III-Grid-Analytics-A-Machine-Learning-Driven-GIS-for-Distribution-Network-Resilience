#!/usr/bin/env python3
"""Debug script to see bus IDs and pole numbers"""
from app import app
from models import Post, LineConnection

with app.app_context():
    # Get sample posts and their pole_numbers
    print("Sample Posts:")
    posts = Post.query.limit(5).all()
    for post in posts:
        print(f"  ID: {post.id}, Pole Number: '{post.pole_number}', Lat: {post.lat}, Lng: {post.lng}")
    
    print("\nSample LineConnections:")
    conns = LineConnection.query.limit(5).all()
    for conn in conns:
        print(f"  {conn.from_bus} -> {conn.to_bus} (Type: {conn.connection_type})")
    
    # Check pole_map logic
    print("\nDebug pole_map creation:")
    pole_map = {}
    for post in Post.query.all():
        if post.pole_number:
            pole_num = ''.join(c for c in str(post.pole_number) if c.isdigit())
            if pole_num:
                pole_map[pole_num] = post
    
    print(f"Total poles in pole_map: {len(pole_map)}")
    print(f"Sample pole_map entries: {list(pole_map.keys())[:10]}")
    
    # Check connection matching
    print("\nDebug connection matching:")
    count_matched = 0
    for conn in LineConnection.query.limit(10).all():
        from_match = ''.join(c for c in str(conn.from_bus) if c.isdigit())
        to_match = ''.join(c for c in str(conn.to_bus) if c.isdigit())
        in_pole_map_from = from_match in pole_map
        in_pole_map_to = to_match in pole_map
        print(f"  {conn.from_bus} (extract: '{from_match}', in map: {in_pole_map_from}) -> {conn.to_bus} (extract: '{to_match}', in map: {in_pole_map_to})")
        if in_pole_map_from and in_pole_map_to:
            count_matched += 1
    print(f"\nMatched in sample: {count_matched}/10")
