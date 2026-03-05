
import os
import sys
sys.path.append(os.getcwd())
from app import app
from extensions import db
from models import Post, BusNode, DistributionLineSegment, SecondaryLineSegment

def simulate_api_connections(post_id):
    with app.app_context():
        p = Post.query.get(post_id)
        if not p: return []

        buses = set()
        if p.pole_number:
            buses.add(p.pole_number)
            try:
                if not str(p.pole_number).startswith('P'):
                    buses.add(f"P{str(p.pole_number).zfill(8)}")
            except: pass

        if p.primary_bus_id: buses.add(p.primary_bus_id)
        if p.sec_bus_id: buses.add(p.sec_bus_id)
        if p.transformer_bus_id: buses.add(p.transformer_bus_id)
        
        bns = BusNode.query.filter_by(pole_number=p.pole_number).all()
        for bn in bns:
            buses.add(bn.bus_id)

        if not buses: return []
        
        bus_list = list(buses)
        connections = []

        dist_lines = DistributionLineSegment.query.filter(
            (DistributionLineSegment.from_bus_id.in_(bus_list)) | 
            (DistributionLineSegment.to_bus_id.in_(bus_list))
        ).all()

        for l in dist_lines:
            connections.append({
                'id': l.segment_id or f"DL-{l.id}",
                'type': 'Primary',
                'name': f"Segment {l.segment_id}",
                'from_bus': l.from_bus_id,
                'to_bus': l.to_bus_id,
                'phase': l.phasing
            })

        sec_lines = SecondaryLineSegment.query.filter(
            (SecondaryLineSegment.from_bus_id.in_(bus_list)) | 
            (SecondaryLineSegment.to_bus_id.in_(bus_list))
        ).all()

        for l in sec_lines:
            connections.append({
                'id': f"SL-{l.id}",
                'type': 'Secondary',
                'name': f"Sec Line #{l.id}",
                'from_bus': l.from_bus_id,
                'to_bus': l.to_bus_id,
                'phase': getattr(l, 'phasing', 'N/A')
            })

        return connections

if __name__ == "__main__":
    conns = simulate_api_connections(1)
    print(f"Total Connections: {len(conns)}")
    for c in conns:
        print(f"  [{c['type']}] {c['from_bus']} -> {c['to_bus']} (Phase: {c['phase']})")
