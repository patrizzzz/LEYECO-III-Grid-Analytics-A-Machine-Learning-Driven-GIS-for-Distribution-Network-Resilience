#!/usr/bin/env python3
"""
Test the complete workflow: Delete all data → Import posts → Auto-infer connections → Render geometry
"""
from app import app, db
from models import Post, LineConnection
import csv
from io import StringIO

def test_complete_workflow():
    print("=" * 70)
    print("🧪 TESTING COMPLETE WORKFLOW: DELETE → IMPORT → INFER → RENDER")
    print("=" * 70)
    
    with app.app_context():
        # Step 1: Check initial data
        print("\n[1/5] Checking initial database state...")
        initial_posts = Post.query.count()
        initial_conns = LineConnection.query.count()
        print(f"   Posts: {initial_posts}, Connections: {initial_conns}")
        
        # Step 2: Delete all data
        print("\n[2/5] Deleting all data...")
        try:
            Post.query.delete()
            LineConnection.query.delete()
            db.session.commit()
            print("   ✓ All data deleted")
        except Exception as e:
            print(f"   ❌ Delete failed: {e}")
            return
        
        # Verify deletion
        after_delete_posts = Post.query.count()
        after_delete_conns = LineConnection.query.count()
        print(f"   Verification - Posts: {after_delete_posts}, Connections: {after_delete_conns}")
        
        # Step 3: Create sample CSV data
        print("\n[3/5] Creating sample posts for import...")
        sample_posts = [
            {'pole_number': '100', 'lat': 11.2956, 'lng': 124.664, 'feeder': 'F6', 'circuit': '3 Phase', 'primary_bus_id': '100', 'name': 'Pole 100'},
            {'pole_number': '101', 'lat': 11.2957, 'lng': 124.663, 'feeder': 'F6', 'circuit': '3 Phase', 'primary_bus_id': '101', 'name': 'Pole 101'},
            {'pole_number': '102', 'lat': 11.2958, 'lng': 124.662, 'feeder': 'F6', 'circuit': '3 Phase', 'primary_bus_id': '102', 'name': 'Pole 102'},
            {'pole_number': '103', 'lat': 11.2959, 'lng': 124.661, 'feeder': 'F6', 'circuit': '3 Phase', 'primary_bus_id': '103', 'name': 'Pole 103'},
        ]
        
        # Insert sample posts
        for data in sample_posts:
            post = Post(**data)
            db.session.add(post)
        db.session.commit()
        
        posts_created = Post.query.count()
        print(f"   ✓ Created {posts_created} test poles")
        
        # Step 4: Auto-infer connections
        print("\n[4/5] Auto-inferring connections...")
        from app import infer_connections_from_posts
        try:
            infer_connections_from_posts()
            connections_created = LineConnection.query.count()
            print(f"   ✓ Inferred {connections_created} connections")
            
            # Show connection details
            conns = LineConnection.query.all()
            for conn in conns[:3]:
                print(f"      - {conn.from_bus} → {conn.to_bus} (Type: {conn.connection_type})")
            if len(conns) > 3:
                print(f"      ... and {len(conns) - 3} more")
        except Exception as e:
            print(f"   ❌ Connection inference failed: {e}")
            return
        
        # Step 5: Test network geometry rendering
        print("\n[5/5] Testing network geometry API...")
        with app.test_client() as client:
            resp = client.get('/api/network-geometry')
            data = resp.get_json()
            
            if resp.status_code == 200:
                lines = data.get('lines', [])
                print(f"   ✓ API returned {len(lines)} drawable lines")
                
                # Show sample lines
                for i, line in enumerate(lines[:3]):
                    print(f"      {i+1}. {line['from_bus']} → {line['to_bus']}")
                    print(f"         From: ({line['lat1']}, {line['lng1']}) → To: ({line['lat2']}, {line['lng2']})")
                    print(f"         Circuit: {line.get('circuit', 'N/A')}")
                
                if len(lines) > 3:
                    print(f"      ... and {len(lines) - 3} more lines")
                    
                if len(lines) > 0:
                    print("\n✅ WORKFLOW COMPLETE AND SUCCESSFUL!")
                    print("   Network lines are ready to render on the map")
                    return True
                else:
                    print("\n⚠️ WARNING: API returned 0 lines")
                    return False
            else:
                print(f"   ❌ API error: {resp.status_code}")
                print(f"      {data}")
                return False

if __name__ == '__main__':
    success = test_complete_workflow()
    exit(0 if success else 1)
