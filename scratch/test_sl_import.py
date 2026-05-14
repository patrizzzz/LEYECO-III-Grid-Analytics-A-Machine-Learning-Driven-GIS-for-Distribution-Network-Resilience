
import os
import sys
sys.path.append(os.getcwd())
import csv
from app import app, db
from models.assets import Post, BusNode, SecondaryLineSegment
from services.importers.network_importer import SecondaryLineImporter

def test_secondary_import_with_coords():
    print("Testing Secondary Line Import with coordinates...")
    
    with app.app_context():
        # Clean up existing test data
        BusNode.query.filter(BusNode.bus_id.like('TEST-S%')).delete()
        Post.query.filter(Post.pole_number.like('TEST-S%')).delete()
        SecondaryLineSegment.query.filter(SecondaryLineSegment.segment_id == 'TEST-SEG-1').delete()
        db.session.commit()
        
        # Create a dummy CSV file
        csv_path = 'test_sl_coords.csv'
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Secondary Distribution Line ID', 'From Bus ID', 'To Bus ID', 'latitude', 'longitude'])
            # We provide coords for the 'To Bus ID'
            writer.writerow(['TEST-SEG-1', 'TEST-S1', 'TEST-S2', '11.111', '122.222'])
            
        try:
            with open(csv_path, 'rb') as f:
                importer = SecondaryLineImporter(csv_file=f)
                result = importer.run()
                print(f"Import result: {result}")
                
            # Verify BusNode TEST-S2 exists and has coordinates
            bn2 = BusNode.query.filter_by(bus_id='TEST-S2').first()
            if bn2 and bn2.lat == 11.111 and bn2.lng == 122.222:
                print("PASS: BusNode created with coordinates.")
            else:
                print(f"FAIL: BusNode check failed: {bn2}")
                
            # Verify Post TEST-S2 exists
            p2 = Post.query.filter_by(pole_number='TEST-S2').first()
            if p2 and p2.lat == 11.111 and p2.lng == 122.222:
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
    test_secondary_import_with_coords()
