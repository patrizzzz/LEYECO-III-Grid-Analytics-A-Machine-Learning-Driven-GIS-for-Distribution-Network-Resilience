#!/usr/bin/env python3
"""Quick test of the API endpoints"""

from app import app
import json

with app.test_client() as client:
    # Test line-connections endpoint
    r = client.get('/api/line-connections?feeder=F6')
    data = r.get_json()
    print(f'Status: {r.status_code}')
    print(f'Total connections: {data.get("total", 0)}')
    print('First 5 connections:')
    for conn in data.get('connections', [])[:5]:
        print(f'  {conn["from_bus"]} -> {conn["to_bus"]} ({conn["connection_type"]})')
