
import os
import sys
sys.path.append(os.getcwd())
from app import app
from extensions import db
from models import Post, DistributionLineSegment, SecondaryLineSegment, BusNode

with app.app_context():
    p = Post.query.get(1)
    if not p:
        print("Post 1 not found")
        sys.exit(1)
        
    print(f"Post: {p.pole_number}, ID: {p.id}")
    
    buses = set()
    if p.pole_number:
        buses.add(p.pole_number)
        if not str(p.pole_number).startswith('P'):
            buses.add(f"P{str(p.pole_number).zfill(8)}")

    if p.primary_bus_id: buses.add(p.primary_bus_id)
    if p.sec_bus_id: buses.add(p.sec_bus_id)
    if p.transformer_bus_id: buses.add(p.transformer_bus_id)
    
    bns = BusNode.query.filter_by(pole_number=p.pole_number).all()
    for bn in bns:
        buses.add(bn.bus_id)
        
    print(f"Buses: {buses}")
    
    for b in buses:
        # Distribution
        d_count = DistributionLineSegment.query.filter(
            (DistributionLineSegment.from_bus_id == b) | 
            (DistributionLineSegment.to_bus_id == b)
        ).count()
        
        # Secondary
        s_count = SecondaryLineSegment.query.filter(
            (SecondaryLineSegment.from_bus_id == b) | 
            (SecondaryLineSegment.to_bus_id == b)
        ).count()
        
        if d_count > 0 or s_count > 0:
            print(f"Bus {b}: Primary={d_count}, Secondary={s_count}")
