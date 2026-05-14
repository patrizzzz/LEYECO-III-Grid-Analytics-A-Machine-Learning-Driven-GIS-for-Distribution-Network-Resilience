
import os
import sys
sys.path.append(os.getcwd())
import csv
from app import app, db
from models.assets import Post, BusNode, DistributionLineSegment
from services.importers.network_importer import PrimaryLineImporter

def test_primary_import_with_coords():
    print("Testing Primary Line Import with coordinates...")
    
    with app.app_context():
        # Clean up existing test data
        BusNode.query.filter(BusNode.bus_id.like('TEST-P%')).delete()
        Post.query.filter(Post.pole_number.like('TEST-P%')).delete()
        DistributionLineSegment.query.filter(DistributionLineSegment.segment_id == 'TEST-PRI-SEG').delete()
        db.session.commit()
        
        # Create a dummy CSV file
        csv_path = 'test_pri_coords.csv'
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Segment ID', 'From Bus ID', 'To Bus ID', 'latitude', 'longitude', 'feeder'])
            # We provide coords for the 'To Bus ID'
            writer.writerow(['TEST-PRI-SEG', 'TESTP1', 'TESTP2', '11.222', '122.333', 'TEST-FEEDER'])
            
        try:
            with open(csv_path, 'rb') as f:
                importer = PrimaryLineImporter(csv_file=f)
                result = importer.run()
                print(f"Import result: {result}")
                
            # Verify segment exists
            all_segs = DistributionLineSegment.query.all()
            print(f"Total segments in DB: {len(all_segs)}")
            for s in all_segs:
                print(f" - ID: {s.segment_id}, From: {s.from_bus_id}, To: {s.to_bus_id}")
            
            seg = DistributionLineSegment.query.filter_by(segment_id='TEST-PRI-SEG').first()
            if seg:
                print(f"PASS: Segment found. Coords: {seg.latitude}, {seg.longitude}, Feeder: {seg.feeder}")
            else:
                print("FAIL: Segment 'TEST-PRI-SEG' not found in table.")

            # Verify BusNode TEST-P2 exists and has coordinates
            bn2 = BusNode.query.filter_by(bus_id='TESTP2').first()
            if bn2 and bn2.lat == 11.222 and bn2.lng == 122.333:
                print("PASS: BusNode created with coordinates.")
            else:
                print(f"FAIL: BusNode check failed: {bn2}")
                
            # Verify Post TEST-P2 exists
            p2 = Post.query.filter_by(pole_number='TESTP2').first()
            if p2 and p2.lat == 11.222 and p2.lng == 122.333:
                print("PASS: Post created with coordinates.")
            else:
                print(f"FAIL: Post check failed: {p2}")
                
            # Verify Linkage
            if bn2 and p2 and bn2.pole_id == p2.id:
                print("PASS: BusNode correctly linked to Post.")
            else:
                print(f"FAIL: Linkage check failed.")
                
        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)

if __name__ == "__main__":
    test_primary_import_with_coords()
