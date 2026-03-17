from services.importers.base_importer import BaseImporter, sanitize_float
from models import DistributionLineSegment, SecondaryLineSegment, SecondaryServiceDrop, LineConnection
from extensions import db

class PrimaryLineImporter(BaseImporter):
    file_type = 'primary_lines'
    model_class = DistributionLineSegment
    header_mappings = {
        'segment_id': ['Primary Distribution Line Segment ID', 'Segment ID', 'segment_id'],
        'from_bus_id': ['From_Bus_ID', 'From Bus ID', 'from_bus'],
        'to_bus_id': ['To_Bus_ID', 'To Bus ID', 'to_bus'],
        'length_meters': ['Length (meters)', 'Length (m)', 'length', 'Length         (meters)'],
        'phasing': ['Phasing', 'phasing'],
        'configuration': ['Configuration', 'config'],
        'system_grounding_type': ['System Grounding Type', 'grounding_type'],
        'conductor_type': ['Conductor Type', 'wire_type'],
        'conductor_size': ['Conductor Size'],
        'conductor_unit': ['Unit (C) ', 'Unit (C)', 'unit_c'],
        'conductor_strands': ['Strands (C) ', 'Strands (C)', 'strands_c'],
        'neutral_wire_type': ['Neutral Wire Type'],
        'neutral_wire_size': ['Neutral Wire Size'],
        'neutral_wire_unit': ['Unit (NW)'],
        'neutral_wire_strands': ['Strands (NW)'],
        'spacing_d12': ['Spacing D12 (meters)'],
        'spacing_d23': ['Spacing D23 (meters)'],
        'spacing_d13': ['Spacing D13 (meters)'],
        'spacing_d1n': ['Spacing D1n (meters)'],
        'spacing_d2n': ['Spacing D2n (meters)'],
        'spacing_d3n': ['Spacing D3n (meters)'],
        'spacing_dc1_c2': ['Spacing DC1-C2 (meters)', 'Spacing DC1-C2       (meters)'],
        'height_h1': ['Height H1 (meters)', 'Height H1   (meters)'],
        'height_h2': ['Height H2 (meters)', 'Height H2   (meters)'],
        'height_h3': ['Height H3 (meters)', 'Height H3   (meters)'],
        'height_hn': ['Height Hn (meters)', 'Height Hn   (meters)'],
        'earth_resistivity': ['Earth Resistivity (Ohm-meter)', 'earth_resistivity']
    }
    
    
    def process_rows(self, reader):
        import re
        existing_segments = {str(s.segment_id).strip().upper(): s for s in DistributionLineSegment.query.all() if s.segment_id}
        
        # Normalize reader fieldnames to handle inconsistent spacing
        header_map = {re.sub(r'\s+', ' ', fn.strip()): fn for fn in reader.fieldnames}
        
        for row in reader:
            # Use raw header names for lookup via mapped normalized keys
            def get_v(norm_key):
                raw_key = header_map.get(norm_key)
                if not raw_key: return None
                return row.get(raw_key)

            seg_id = get_v('Primary Distribution Line Segment ID') or get_v('Segment ID') or get_v('segment_id')
            if not seg_id: continue
            
            clean_id = str(seg_id).strip().upper()
            seg = existing_segments.get(clean_id)
            if not seg:
                seg = DistributionLineSegment(segment_id=clean_id)
                db.session.add(seg)
                existing_segments[clean_id] = seg
                self.stats['created'] += 1
            else:
                self.stats['updated'] += 1
                
            seg.from_bus_id = get_v('From_Bus_ID') or get_v('From Bus ID') or get_v('from_bus')
            seg.to_bus_id = get_v('To_Bus_ID') or get_v('To Bus ID') or get_v('to_bus')
            seg.phasing = row.get('Phasing') or row.get('phasing')
            seg.length_meters = sanitize_float(get_v('Length (meters)') or get_v('Length (m)') or get_v('length') or get_v('Length (meters)'))
            
            # Additional Technical Fields (Using normalized lookups)
            seg.configuration = row.get('Configuration') or row.get('config')
            seg.system_grounding_type = get_v('System Grounding Type') or row.get('grounding_type')
            seg.conductor_type = get_v('Conductor Type') or row.get('wire_type')
            seg.conductor_size = row.get('Conductor Size')
            seg.conductor_unit = get_v('Unit (C)') or row.get('unit_c')
            seg.conductor_strands = get_v('Strands (C)') or row.get('strands_c')
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
            seg.earth_resistivity = sanitize_float(get_v('Earth Resistivity (Ohm-meter)') or row.get('earth_resistivity'))
            
            seg.upload_id = self.current_upload_id
            
            if seg.from_bus_id and seg.to_bus_id:
                conn = LineConnection.query.filter_by(from_bus=seg.from_bus_id, to_bus=seg.to_bus_id, connection_type='Primary_to_Primary').first()
                if not conn:
                    db.session.add(LineConnection(from_bus=seg.from_bus_id, to_bus=seg.to_bus_id, connection_type='Primary_to_Primary', phasing=seg.phasing))

class SecondaryLineImporter(BaseImporter):
    file_type = 'secondary_lines'
    model_class = SecondaryLineSegment
    header_mappings = {
        'from_bus_id': ['from_bus_id', 'From Bus ID', 'from_bus'],
        'to_bus_id': ['to_bus_id', 'To Bus ID', 'to_bus'],
        'phasing': ['phasing', 'Phasing'],
        'length_meters': ['length_meters', 'Length (m)', 'length'],
        'conductor_type': ['conductor_type', 'Conductor Type']
    }
    
    def process_rows(self, reader):
        existing_segments = {(s.from_bus_id, s.to_bus_id, s.phasing): s for s in SecondaryLineSegment.query.all()}
        for row in reader:
            from_bus = self.get_val(row, 'from_bus_id')
            to_bus = self.get_val(row, 'to_bus_id')
            phasing = self.get_val(row, 'phasing')
            if not from_bus or not to_bus: continue
            
            key = (from_bus, to_bus, phasing)
            seg = existing_segments.get(key)
            if not seg:
                seg = SecondaryLineSegment(from_bus_id=from_bus, to_bus_id=to_bus, phasing=phasing)
                db.session.add(seg)
                existing_segments[key] = seg
                self.stats['created'] += 1
            else:
                self.stats['updated'] += 1
            
            seg.length_meters = sanitize_float(self.get_val(row, 'length_meters'))
            seg.conductor_type = self.get_val(row, 'conductor_type')
            seg.upload_id = self.current_upload_id

class ServiceDropImporter(BaseImporter):
    file_type = 'service_drops'
    model_class = SecondaryServiceDrop
    header_mappings = {
        'service_drop_id': ['Service Drop ID', 'service_drop_id', 'SD_ID', 'Drop ID', 'drop_id'],
        'from_bus_id': ['From Bus ID', 'from_bus_id', 'from_bus', 'Bus ID', 'bus_id',
                        'From_Bus_ID', 'Secondary Bus ID', 'secondary_bus_id'],
        'to_customer_id': ['To Customer ID', 'to_customer_id', 'Customer ID', 'customer_id',
                           'To_Customer_ID', 'Cust ID', 'cust_id', 'Account Number'],
        'phasing': ['Phasing', 'phasing', 'Phase'],
        'installation_type': ['Installation Type', 'installation_type', 'Install Type'],
        'length_meters_1': ['Length (m)', 'length_meters_1', 'Length-1 (m)', 'length', 'Length'],
        'length_meters_2': ['Length-2 (m)', 'length_meters_2'],
        'conductor_type': ['Conductor Type', 'conductor_type', 'Wire Type', 'wire_type'],
        'conductor_size': ['Conductor Size', 'conductor_size', 'Wire Size', 'wire_size'],
    }
    
    def process_rows(self, reader):
        # Build lookup by composite key (from_bus_id, to_customer_id) for dedup
        existing_drops = {}
        for d in SecondaryServiceDrop.query.all():
            if d.service_drop_id:
                existing_drops[d.service_drop_id] = d
            if d.from_bus_id and d.to_customer_id:
                existing_drops[(d.from_bus_id, d.to_customer_id)] = d
        
        auto_id_counter = 0
        for row in reader:
            from_bus = self.get_val(row, 'from_bus_id')
            to_cust = self.get_val(row, 'to_customer_id')
            
            # Must have at least a customer ID to be useful
            if not to_cust:
                self.stats['skipped'] += 1
                continue
            
            # Get or auto-generate service_drop_id
            drop_id = self.get_val(row, 'service_drop_id')
            if not drop_id:
                auto_id_counter += 1
                drop_id = f"SD-{from_bus or 'UNK'}-{to_cust}"
            
            # Dedup: check by service_drop_id first, then composite key
            drop = existing_drops.get(drop_id)
            if not drop and from_bus and to_cust:
                drop = existing_drops.get((from_bus, to_cust))
            
            if not drop:
                drop = SecondaryServiceDrop(service_drop_id=drop_id)
                db.session.add(drop)
                existing_drops[drop_id] = drop
                if from_bus and to_cust:
                    existing_drops[(from_bus, to_cust)] = drop
                self.stats['created'] += 1
            else:
                self.stats['updated'] += 1
                
            drop.from_bus_id = from_bus
            drop.to_customer_id = to_cust
            drop.phasing = self.get_val(row, 'phasing')
            drop.installation_type = self.get_val(row, 'installation_type')
            drop.length_meters_1 = sanitize_float(self.get_val(row, 'length_meters_1'))
            drop.length_meters_2 = sanitize_float(self.get_val(row, 'length_meters_2'))
            drop.conductor_type = self.get_val(row, 'conductor_type')
            drop.conductor_size = self.get_val(row, 'conductor_size')
            drop.upload_id = self.current_upload_id

