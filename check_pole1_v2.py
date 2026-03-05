
import os
import sys

# Add the current directory to sys.path to ensure imports work
sys.path.append(os.getcwd())

from app import create_app
from extensions import db
from models import Post, DistributionLineSegment, SecondaryLineSegment, BusNode

def check_pole_connections():
    app = create_app()
    with app.app_context():
        # 1. Find the Post(s) that might be "pole 1"
        posts = Post.query.filter(
            (Post.pole_number == '1') | 
            (Post.name.like('%1%')) |
            (Post.pole_number == 'P00000001') |
            (Post.id == 1)
        ).all()
        
        if not posts:
            print("No posts found matching 'pole 1'")
            return

        for p in posts:
            print(f"\n--- Investigating Post: ID={p.id}, Pole={p.pole_number}, Name={p.name} ---")
            
            # Collect bus IDs like in the API logic
            buses = set()
            if p.pole_number:
                buses.add(p.pole_number)
                try:
                    # Logic from api_routes.py:195
                    if not str(p.pole_number).startswith('P'):
                        buses.add(f"P{str(p.pole_number).zfill(8)}")
                except: pass

            if p.primary_bus_id: buses.add(p.primary_bus_id)
            if p.sec_bus_id: buses.add(p.sec_bus_id)
            if p.transformer_bus_id: buses.add(p.transformer_bus_id)
            
            # Find BusNodes linked to this pole_number
            bns = BusNode.query.filter_by(pole_number=p.pole_number).all()
            for bn in bns:
                buses.add(bn.bus_id)
                
            print(f"Associated Bus IDs: {buses}")
            
            bus_list = list(buses)
            
            # Check Distribution Lines
            dist_lines = DistributionLineSegment.query.filter(
                (DistributionLineSegment.from_bus_id.in_(bus_list)) | 
                (DistributionLineSegment.to_bus_id.in_(bus_list))
            ).all()
            
            print(f"Primary Connections ({len(dist_lines)}):")
            for l in dist_lines:
                print(f"  - ID: {l.segment_id}, From: {l.from_bus_id}, To: {l.to_bus_id}, Phasing: {l.phasing}")
                
            # Check Secondary Lines
            sec_lines = SecondaryLineSegment.query.filter(
                (SecondaryLineSegment.from_bus_id.in_(bus_list)) | 
                (SecondaryLineSegment.to_bus_id.in_(bus_list))
            ).all()
            
            print(f"Secondary Connections ({len(sec_lines)}):")
            for l in sec_lines:
                print(f"  - ID: {l.id}, From: {l.from_bus_id}, To: {l.to_bus_id}")

            # Check if there are duplicate segments or if many lines truly converge here.
            all_conns = dist_lines + sec_lines
            print(f"Total Unique Connections found: {len(all_conns)}")

if __name__ == "__main__":
    check_pole_connections()
