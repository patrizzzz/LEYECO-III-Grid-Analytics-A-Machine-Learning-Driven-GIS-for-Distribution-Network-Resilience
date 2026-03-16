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
        'length_meters': ['Length (meters)', 'Length (m)', 'length'],
        'phasing': ['Phasing', 'phasing']
    }
    
    def process_rows(self, reader):
        existing_segments = {str(s.segment_id).strip().upper(): s for s in DistributionLineSegment.query.all() if s.segment_id}
        
        for row in reader:
            seg_id = self.get_val(row, 'segment_id')
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
                
            seg.from_bus_id = self.get_val(row, 'from_bus_id')
            seg.to_bus_id = self.get_val(row, 'to_bus_id')
            seg.phasing = self.get_val(row, 'phasing')
            seg.length_meters = sanitize_float(self.get_val(row, 'length_meters'))
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

