import os
import sys
sys.path.append(os.getcwd())
from app import app
from services.network_geometry_db import get_network_geometry

with app.app_context():
    data = get_network_geometry(app)
    lines = data.get('lines', [])
    nodes = data.get('nodes', [])
    
    print(f"=== Network Export Summary ===")
    print(f"Total lines: {len(lines)}")
    print(f"Total nodes: {len(nodes)}")
    
    # Count by type
    by_type = {}
    for l in lines:
        t = l.get('connection_type', 'Unknown')
        by_type[t] = by_type.get(t, 0) + 1
    print("\nLines by type:")
    for t, count in sorted(by_type.items()):
        print(f"  {t}: {count}")
    
    # Count by feeder
    by_feeder = {}
    for l in lines:
        f = l.get('feeder') or 'None'
        by_feeder[f] = by_feeder.get(f, 0) + 1
    print("\nLines by feeder:")
    for f, count in sorted(by_feeder.items()):
        print(f"  {f}: {count}")
    
    # Count by phasing
    by_phase = {}
    for l in lines:
        p = l.get('phasing') or 'None'
        by_phase[p] = by_phase.get(p, 0) + 1
    print("\nLines by phasing:")
    for p, count in sorted(by_phase.items()):
        print(f"  {p}: {count}")
