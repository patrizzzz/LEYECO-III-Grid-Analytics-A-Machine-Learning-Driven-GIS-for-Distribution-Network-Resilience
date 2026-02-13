#!/usr/bin/env python3
"""
Verification script for the Line Connection Inference System.
Demonstrates that all components are in place and working correctly.
"""

import json
from pathlib import Path
from app import app, db
from models import LineConnection

def verify_system():
    """Run comprehensive verification checks"""
    
    print("=" * 70)
    print("🔌 LINE CONNECTION INFERENCE SYSTEM - VERIFICATION")
    print("=" * 70)
    print()
    
    checks = []
    
    # Check 1: CSV files exist
    print("[1/5] Checking generated CSV files...")
    csv_files = {
        'connections.csv': 'Connection edges',
        'bus_nodes.csv': 'Unique bus nodes'
    }
    csv_ok = True
    for fname, desc in csv_files.items():
        if Path(fname).exists():
            size = Path(fname).stat().st_size
            print(f"  ✅ {fname} ({desc}) - {size:,} bytes")
        else:
            print(f"  ❌ {fname} ({desc}) - NOT FOUND")
            csv_ok = False
    checks.append(('CSV Files', csv_ok))
    print()
    
    # Check 2: Database table exists
    print("[2/5] Checking database table...")
    with app.app_context():
        try:
            count = LineConnection.query.count()
            print(f"  ✅ line_connection table exists")
            print(f"  ✅ Contains {count} connections")
            checks.append(('Database Table', True))
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
            checks.append(('Database Table', False))
    print()
    
    # Check 3: Connection type distribution
    print("[3/5] Checking connection types...")
    with app.app_context():
        try:
            types_query = db.session.query(
                LineConnection.connection_type,
                db.func.count(LineConnection.id)
            ).group_by(LineConnection.connection_type).all()
            
            types_ok = False
            for conn_type, count in sorted(types_query):
                print(f"  • {conn_type}: {count}")
                types_ok = True
            
            checks.append(('Connection Types', types_ok))
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
            checks.append(('Connection Types', False))
    print()
    
    # Check 4: API endpoints
    print("[4/5] Testing API endpoints...")
    with app.test_client() as client:
        endpoints = [
            ('/api/line-connections', 'Connections list'),
            ('/api/line-connections/stats', 'Connection stats')
        ]
        
        api_ok = True
        for endpoint, desc in endpoints:
            try:
                response = client.get(endpoint)
                if response.status_code == 200:
                    data = response.get_json()
                    if data:
                        print(f"  ✅ {endpoint} - {desc}")
                    else:
                        print(f"  ⚠️  {endpoint} - Empty response")
                        api_ok = False
                else:
                    print(f"  ❌ {endpoint} - Status {response.status_code}")
                    api_ok = False
            except Exception as e:
                print(f"  ❌ {endpoint} - {str(e)}")
                api_ok = False
        
        checks.append(('API Endpoints', api_ok))
    print()
    
    # Check 5: Model & Migration
    print("[5/5] Checking model and migration...")
    model_ok = True
    
    # Check model exists
    if hasattr(LineConnection, '__tablename__'):
        print(f"  ✅ LineConnection model defined")
    else:
        print(f"  ❌ LineConnection model not found")
        model_ok = False
    
    # Check migration file
    if Path('migrations/versions/add_line_connections.py').exists():
        print(f"  ✅ Migration file exists (add_line_connections.py)")
    else:
        print(f"  ❌ Migration file not found")
        model_ok = False
    
    checks.append(('Model & Migration', model_ok))
    print()
    
    # Summary
    print("=" * 70)
    print("✅ VERIFICATION SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)
    
    for name, ok in checks:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"{status} - {name}")
    
    print()
    print(f"Overall: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 All systems operational! Connections ready for visualization.")
    else:
        print(f"\n⚠️  {total - passed} check(s) failed. Review above for details.")
    
    print("=" * 70)

if __name__ == '__main__':
    verify_system()
