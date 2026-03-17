
from app import create_app
from extensions import db
from models import Post, BusNode, DistributionLineSegment, LineConnection

app = create_app()

def diagnose_pole_connections(poles_to_check):
    with app.app_context():
        print(f"--- Diagnosing Connections for Poles: {poles_to_check} ---")
        
        bus_ids = {}
        for p_num in poles_to_check:
            # Gather all bus IDs for this pole
            p = Post.query.filter_by(pole_number=p_num).first()
            ids = set()
            if p:
                if p.primary_bus_id: ids.add(p.primary_bus_id)
                if p.transformer_bus_id: ids.add(p.transformer_bus_id)
            
            bns = BusNode.query.filter_by(pole_number=p_num).all()
            for bn in bns:
                ids.add(bn.bus_id)
            
            bus_ids[p_num] = list(ids)
            print(f"Pole {p_num} Bus IDs: {ids}")

        # Check for direct connections between these buses
        all_ids = []
        for ids in bus_ids.values():
            all_ids.extend(ids)

        print("\n--- Distribution Line Segments ---")
        segments = DistributionLineSegment.query.filter(
            (DistributionLineSegment.from_bus_id.in_(all_ids)) | 
            (DistributionLineSegment.to_bus_id.in_(all_ids))
        ).all()
        for s in segments:
            print(f"[{s.segment_id}] {s.from_bus_id} -> {s.to_bus_id}")

        print("\n--- Line Connections ---")
        conns = LineConnection.query.filter(
            (LineConnection.from_bus.in_(all_ids)) | 
            (LineConnection.to_bus.in_(all_ids))
        ).all()
        for c in conns:
            print(f"[{c.connection_type}] {c.from_bus} -> {c.to_bus}")

if __name__ == "__main__":
    diagnose_pole_connections(['1', '60', '83', '128'])
