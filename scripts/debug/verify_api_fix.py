import os
import sys
# Add current directory to path
sys.path.append(os.getcwd())

from app import app
import json

def test_api():
    with app.test_client() as client:
        print("=== API VERIFICATION ===")
        
        # Test Post 1 Connections
        print("\n--- Posting 1 Connections ---")
        r = client.get('/api/posts/1/connections')
        if r.status_code == 200:
            conns = r.get_json()
            print(f"Found {len(conns)} connections for Post 1")
            for c in conns:
                print(f"  ID: {c['id']}, Type: {c['type']}, From: {c['from_bus']}, To: {c['to_bus']}, Phase: {c['phase']}")
        else:
            print(f"Error: {r.status_code}")
            
        # Test Post 3 Connections
        print("\n--- Posting 3 Connections ---")
        r = client.get('/api/posts/3/connections')
        if r.status_code == 200:
            conns = r.get_json()
            print(f"Found {len(conns)} connections for Post 3")
            for c in conns:
                print(f"  ID: {c['id']}, Type: {c['type']}, From: {c['from_bus']}, To: {c['to_bus']}, Phase: {c['phase']}")
        else:
            print(f"Error: {r.status_code}")

if __name__ == '__main__':
    test_api()
