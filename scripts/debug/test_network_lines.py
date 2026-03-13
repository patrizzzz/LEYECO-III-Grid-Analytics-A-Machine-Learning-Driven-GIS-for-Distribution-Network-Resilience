#!/usr/bin/env python3
"""Test the network-geometry endpoint"""
from app import app
import json

with app.test_client() as client:
    resp = client.get('/api/network-geometry')
    print(f"Status: {resp.status_code}")
    data = resp.get_json()
    print(f"Lines returned: {len(data.get('lines', []))}")
    print(f"Stats: {data.get('stats', {})}")
    if data.get('lines'):
        print(f"\nFirst 3 lines:")
        for i, line in enumerate(data.get('lines', [])[:3]):
            print(f"  {i+1}. {line['from_bus']} -> {line['to_bus']} ({line['connection_type']}) at ({line['lat1']}, {line['lng1']}) to ({line['lat2']}, {line['lng2']})")
    else:
        print("\nNo lines returned!")
        print(f"\nFull response: {json.dumps(data, indent=2)}")
