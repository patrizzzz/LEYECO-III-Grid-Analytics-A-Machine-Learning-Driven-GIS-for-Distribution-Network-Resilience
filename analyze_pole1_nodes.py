
import os
import sys
sys.path.append(os.getcwd())
from app import app
from extensions import db
from models import BusNode

with app.app_context():
    bus_id_counts = {}
    nodes = BusNode.query.filter_by(pole_number='1').all()
    
    types = {}
    feeders = {}
    
    for n in nodes:
        types[n.bus_type] = types.get(n.bus_type, 0) + 1
        feeders[n.feeder] = feeders.get(n.feeder, 0) + 1
        
    print("BusNode Types for Pole '1':")
    for t, count in types.items():
        print(f"  {t}: {count}")
        
    print("\nFeeders for Pole '1':")
    for f, count in feeders.items():
        print(f"  {f}: {count}")
        
    print("\nSample Bus IDs for Pole '1':")
    for n in nodes[:20]:
        print(f"  - {n.bus_id} ({n.bus_type})")
