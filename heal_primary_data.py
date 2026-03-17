import csv
import os
import re
from app import app
from models import DistributionLineSegment
from extensions import db
from services.importers.base_importer import sanitize_float

def heal_primary_lines():
    csv_path = 'data/samples/EXAMPLEDATA.csv'
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return

    with app.app_context():
        with open(csv_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            # Map headers to normalize them (collapse all internal whitespace to single spaces)
            header_map = {re.sub(r'\s+', ' ', fn.strip()): fn for fn in reader.fieldnames}
            
            updated_count = 0
            for row in reader:
                # Find segment ID using various possible header names
                seg_id = None
                for possible in ['Primary Distribution Line Segment ID', 'Segment ID', 'segment_id']:
                    raw_fn = header_map.get(possible)
                    if raw_fn:
                        seg_id = row.get(raw_fn)
                        if seg_id: break
                
                if not seg_id: continue
                
                clean_id = str(seg_id).strip().upper()
                seg = DistributionLineSegment.query.filter_by(segment_id=clean_id).first()
                
                if seg:
                    def get_v(key_base):
                        raw_key = header_map.get(key_base)
                        return row.get(raw_key) if raw_key else None

                    seg.configuration = get_v('Configuration')
                    seg.system_grounding_type = get_v('System Grounding Type')
                    seg.conductor_type = get_v('Conductor Type')
                    seg.conductor_size = get_v('Conductor Size')
                    seg.conductor_unit = get_v('Unit (C)')
                    seg.conductor_strands = get_v('Strands (C)')
                    seg.neutral_wire_type = get_v('Neutral Wire Type')
                    seg.neutral_wire_size = get_v('Neutral Wire Size')
                    seg.neutral_wire_unit = get_v('Unit (NW)')
                    seg.neutral_wire_strands = get_v('Strands (NW)')
                    
                    seg.spacing_d12 = sanitize_float(get_v('Spacing D12 (meters)'))
                    seg.spacing_d23 = sanitize_float(get_v('Spacing D23 (meters)'))
                    seg.spacing_d13 = sanitize_float(get_v('Spacing D13 (meters)'))
                    seg.spacing_d1n = sanitize_float(get_v('Spacing D1n (meters)'))
                    seg.spacing_d2n = sanitize_float(get_v('Spacing D2n (meters)'))
                    seg.spacing_d3n = sanitize_float(get_v('Spacing D3n (meters)'))
                    seg.spacing_dc1_c2 = sanitize_float(get_v('Spacing DC1-C2 (meters)'))
                    
                    seg.height_h1 = sanitize_float(get_v('Height H1 (meters)'))
                    seg.height_h2 = sanitize_float(get_v('Height H2 (meters)'))
                    seg.height_h3 = sanitize_float(get_v('Height H3 (meters)'))
                    seg.height_hn = sanitize_float(get_v('Height Hn (meters)'))
                    
                    seg.earth_resistivity = sanitize_float(get_v('Earth Resistivity (Ohm-meter)'))
                    
                    updated_count += 1
            
            db.session.commit()
            print(f"Successfully updated {updated_count} Primary Line Segments.")

if __name__ == "__main__":
    heal_primary_lines()
