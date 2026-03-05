import os
import sys
# Add current directory to path
sys.path.append(os.getcwd())

from app import app
from models import Post, BusNode, DistributionTransformer, LineConnection, DistributionLineSegment, SecondaryLineSegment

def inspect():
    with app.app_context():
        output = []
        output.append("=== DATA INSPECTION REPORT ===")
        
        # 1. Total Counts
        output.append(f"Total Posts: {Post.query.count()}")
        output.append(f"Total BusNodes: {BusNode.query.count()}")
        output.append(f"Total DistributionLineSegments: {DistributionLineSegment.query.count()}")
        output.append(f"Total SecondaryLineSegments: {SecondaryLineSegment.query.count()}")
        output.append(f"Total LineConnections: {LineConnection.query.count()}")
        
        # 2. Sample Posts
        output.append("\n--- Sample Posts (Pole 1 - 5) ---")
        posts = Post.query.filter(Post.name.like('Pole%')).order_by(Post.id).limit(10).all()
        for p in posts:
            output.append(f"ID: {p.id} | PoleNum: {p.pole_number} | Name: {p.name} | Feeder: {p.feeder} | BusID: {p.primary_bus_id}")
            
        # 3. Sample BusNodes
        output.append("\n--- Sample BusNodes (First 10) ---")
        bnodes = BusNode.query.limit(10).all()
        for bn in bnodes:
            output.append(f"ID: {bn.id} | BusID: {bn.bus_id} | PoleNum: {bn.pole_number} | Feeder: {bn.feeder}")
            
        # 4. Sample Distribution Lines
        output.append("\n--- Sample Distribution Line Segments (First 10) ---")
        dls = DistributionLineSegment.query.limit(10).all()
        for l in dls:
            output.append(f"ID: {l.id} | SegmentID: {l.segment_id} | From: {l.from_bus_id} | To: {l.to_bus_id} | Phasing: {l.phasing}")
            
        # 5. Check if Pole 1 is in Distribution Lines
        if posts:
            p1 = posts[0]
            output.append(f"\n--- Searching for Segments related to Post {p1.id} (Bus: {p1.primary_bus_id}, PoleNum: {p1.pole_number}) ---")
            
            # Search by exact BusID
            matches = DistributionLineSegment.query.filter(
                (DistributionLineSegment.from_bus_id == p1.primary_bus_id) | 
                (DistributionLineSegment.to_bus_id == p1.primary_bus_id)
            ).all()
            output.append(f"Matches by exact BusID '{p1.primary_bus_id}': {len(matches)}")
            
            # Search by PoleNum
            matches_pn = DistributionLineSegment.query.filter(
                (DistributionLineSegment.from_bus_id == p1.pole_number) | 
                (DistributionLineSegment.to_bus_id == p1.pole_number) |
                (DistributionLineSegment.from_bus_id == f"P{p1.pole_number}") |
                (DistributionLineSegment.to_bus_id == f"P{p1.pole_number}")
            ).all()
            output.append(f"Matches by PoleNum '{p1.pole_number}' or 'P{p1.pole_number}': {len(matches_pn)}")
            
        with open('data_inspection_report.txt', 'w') as f:
            f.write('\n'.join(output))

if __name__ == '__main__':
    inspect()
