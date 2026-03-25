
from app import app
from models import DistributionTransformer, SecondaryLineSegment, BusNode, Post
from extensions import db

def trace_further():
    with app.app_context():
        bus_id = "S000090-0000011"
        print(f"Tracing from bus: {bus_id}")
        
        # 1. Check for DT
        dt = DistributionTransformer.query.filter_by(to_secondary_bus_id=bus_id).first()
        if dt:
            print(f"  Direct DT found: {dt.transformer_id}, Primary Bus: {dt.from_primary_bus_id}")
        else:
            print(f"  No direct DT. Checking secondary lines...")
            lines = SecondaryLineSegment.query.filter(
                (SecondaryLineSegment.from_bus_id == bus_id) |
                (SecondaryLineSegment.to_bus_id == bus_id)
            ).all()
            for l in lines:
                nxt = l.from_bus_id if l.to_bus_id == bus_id else l.to_bus_id
                print(f"    Connects to: {nxt}")
                # Check for DT on next hop
                dt2 = DistributionTransformer.query.filter_by(to_secondary_bus_id=nxt).first()
                if dt2:
                    print(f"      DT found on next hop: {dt2.transformer_id}, Primary Bus: {dt2.from_primary_bus_id}")

trace_further()
