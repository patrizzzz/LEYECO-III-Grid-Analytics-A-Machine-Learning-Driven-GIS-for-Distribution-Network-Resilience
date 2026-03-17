from app import app
from models import DistributionLineSegment

def check_data():
    with app.app_context():
        # Let's find Pole 136's segment. 
        # Earlier I found that Pole 136 is connected to segment starting/ending with '136' or 'P0000000136'
        # EXAMPLEDATA.csv line 239: 238,DXTUNGAF1C00136,P0000000134,P0000000136,...
        seg = DistributionLineSegment.query.filter_by(segment_id='DXTUNGAF1C00136').first()
        if seg:
            print(f"Segment: {seg.segment_id}")
            print(f"  Configuration: {seg.configuration}")
            print(f"  System Grounding: {seg.system_grounding_type}")
            print(f"  Conductor Type: {seg.conductor_type}")
            print(f"  Conductor Size: {seg.conductor_size}")
            print(f"  Spacing D12: {seg.spacing_d12}")
            print(f"  Spacing DC1-C2: {seg.spacing_dc1_c2}")
            print(f"  Height H1: {seg.height_h1}")
            print(f"  Height H2: {seg.height_h2}")
            print(f"  Height H3: {seg.height_h3}")
            print(f"  Height Hn: {seg.height_hn}")
        else:
            print("Segment DXTUNGAF1C00136 not found.")

if __name__ == "__main__":
    check_data()
