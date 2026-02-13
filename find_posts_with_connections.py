#!/usr/bin/env python3
"""Identify all posts that have connection lines."""

from app import app, db
from models import Post, LineConnection

def find_posts_with_connections():
    """Find all posts that have line connections."""
    with app.app_context():
        try:
            # Get all unique buses from connections
            connections = LineConnection.query.all()
            
            if not connections:
                print("❌ No connections found in database")
                return
            
            # Collect all unique bus IDs
            all_buses = set()
            for conn in connections:
                all_buses.add(conn.from_bus)
                all_buses.add(conn.to_bus)
            
            print(f"\n📡 Total unique buses in connections: {len(all_buses)}")
            print(f"Total connections: {len(connections)}\n")
            
            # Try to find posts matching these buses
            posts_with_connections = []
            
            for post in Post.query.all():
                # Check if this post's pole_number matches any bus
                pole_num = post.pole_number
                
                # Check exact match
                if pole_num in all_buses:
                    posts_with_connections.append((post, 'exact'))
                    continue
                
                # Check numeric match (extract digits)
                if pole_num:
                    numeric_part = ''.join(c for c in pole_num if c.isdigit())
                    if numeric_part:
                        for bus in all_buses:
                            bus_numeric = ''.join(c for c in bus if c.isdigit())
                            if numeric_part == bus_numeric:
                                posts_with_connections.append((post, 'numeric'))
                                break
            
            print(f"✅ Found {len(posts_with_connections)} posts with connections:\n")
            
            # Sort by post name
            posts_with_connections.sort(key=lambda x: x[0].name or '')
            
            for post, match_type in posts_with_connections:
                print(f"  • {post.name:30} (ID: {post.post_id:6} | Pole: {post.pole_number:10} | Feeder: {post.feeder or 'N/A'})")
            
            # Show connection summary by feeder
            print("\n📊 Connections by Feeder:")
            feeders = {}
            for conn in connections:
                feeder = conn.feeder or 'Unknown'
                if feeder not in feeders:
                    feeders[feeder] = 0
                feeders[feeder] += 1
            
            for feeder in sorted(feeders.keys()):
                print(f"  • {feeder:20} {feeders[feeder]:4} connections")
            
            # Show connection types summary
            print("\n🔌 Connections by Type:")
            types = {}
            for conn in connections:
                conn_type = conn.connection_type or 'Unknown'
                if conn_type not in types:
                    types[conn_type] = 0
                types[conn_type] += 1
            
            for conn_type in sorted(types.keys()):
                print(f"  • {conn_type:35} {types[conn_type]:4} connections")
            
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == '__main__':
    find_posts_with_connections()
