import os
import csv
import re
from services.importers.base_importer import BaseImporter, sanitize_float
from models import Post, DistributionLineSegment, SecondaryLineSegment, SecondaryServiceDrop, LineConnection, BusNode
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
        'earth_resistivity': ['Earth Resistivity (Ohm-meter)', 'earth_resistivity'],
        'latitude': ['latitude', 'Lat', 'lat', 'latitue', 'Latitude'],
        'longitude': ['longitude', 'Long', 'lon', 'lng', 'longitute', 'longtitude', 'longtiude', 'Longitude'],
        'feeder': ['Feeder', 'feeder']
    }
    
    
    def _normalize_bus_id(self, bus_id):
        """Strip redundant leading zeros from IDs (e.g., P00000001 -> P1, P1-007 -> P1-7)"""
        if not bus_id: return ""
        # Handle lateral segments
        parts = str(bus_id).strip().upper().split('-')
        norm_parts = []
        for part in parts:
            if part.startswith('P'):
                # Strip P, then strip leading zeros, then put P back
                core = part[1:].lstrip('0')
                if not core: core = '0' # Handle P000
                norm_parts.append(f"P{core}")
            else:
                core = part.lstrip('0')
                if not core: core = '0'
                norm_parts.append(core)
        return '-'.join(norm_parts)

    def _parse_pole_suffix(self, bus_id):
        """Extract sequence number from IDs like P1 (1) or P1-7 (7)"""
        norm_id = self._normalize_bus_id(bus_id)
        if not norm_id: return 0
        match = re.search(r'-(\d+)$', norm_id)
        if match:
            return int(match.group(1))
        # Highway pole check
        match = re.search(r'P(\d+)$', norm_id, re.I)
        if match:
            return int(match.group(1))
        return 0

    def _apply_segment_stats_to_post(self, seg, post):
        """Propagate technical metadata from line segment to the physical pole."""
        if not seg or not post: return
        
        # Mapping for string/config fields
        fields = [
            'configuration', 'system_grounding_type', 'conductor_type',
            'conductor_unit', 'conductor_strands', 'neutral_wire_type',
            'neutral_wire_size', 'neutral_wire_unit', 'neutral_wire_strands',
            'phasing'
        ]
        for f in fields:
            setattr(post, f, getattr(seg, f))
            
        post.pri_conductor_size = seg.conductor_size
        
        # Mapping for numeric/spacing fields
        num_fields = [
            'spacing_d12', 'spacing_d23', 'spacing_d13', 'spacing_d1n',
            'spacing_d2n', 'spacing_d3n', 'spacing_dc1_c2', 'height_h1',
            'height_h2', 'height_h3', 'height_hn', 'earth_resistivity'
        ]
        for f in num_fields:
            setattr(post, f, getattr(seg, f))

    def process_rows(self, reader):
        from models import UploadHistory
        # We need to read all rows into memory to find feeders for cleanup 
        # and because BaseImporter.get_reader() doesn't support resetting the stream easily.
        rows = list(reader)
        if not rows: return

        # Cleanup old data for found feeders in this file
        feeders = {self.get_val(row, 'feeder') for row in rows if self.get_val(row, 'feeder')}
        for f in feeders:
            if f:
                # Delete existing segments and connections for this feeder to ensure a clean re-import
                self.model_class.query.filter_by(feeder=f).delete()
                LineConnection.query.filter_by(feeder=f).delete()
        db.session.commit()
        
        # Load Pool Data for coordinate lookups from Database
        all_posts = Post.query.all()
        # Mapping for highway poles (imported via 'posts' file type)
        self.highway_post_map = {p.pole_num: p for p in all_posts if p.pole_num is not None}
        # Mapping for already named lateral poles
        self.named_post_map = {p.pole_number: p for p in all_posts if p.pole_number}
        
        self.highway_pool = {p.pole_num: {'latitude': p.lat, 'longitude': p.lng} for p in all_posts if p.pole_num is not None}
        lateral_posts = Post.query.join(UploadHistory).filter(UploadHistory.file_type == 'lateral_poles').all()
        self.lateral_pool = [{'post_id': p.id, 'latitude': p.lat, 'longitude': p.lng, 'record': p} for p in lateral_posts]
        
        # Cache for created/existing nodes to avoid repeated queries
        node_cache = {str(bn.bus_id).strip(): (bn.lat, bn.lng) for bn in BusNode.query.all()}
        
        # Session-level cache for connections and nodes to avoid UniqueConstraint errors
        conn_session_cache = set()
        node_session_cache = set()
        
        # Track existing segments for statistics
        existing_segments = {str(s.segment_id).strip().upper(): s for s in DistributionLineSegment.query.all() if s.segment_id}
        
        for row in rows:
            seg_id = self.get_val(row, 'segment_id')
            if not seg_id: continue
            
            seg = self.model_class()
            seg.segment_id = str(seg_id).strip().upper()
            
            existing = existing_segments.get(seg.segment_id)
            if not existing:
                self.stats['created'] += 1
            else:
                self.stats['updated'] += 1
                
            from_bus_raw = self.get_val(row, 'from_bus_id')
            to_bus_raw = self.get_val(row, 'to_bus_id')
            from_bus = self._normalize_bus_id(from_bus_raw)
            to_bus = self._normalize_bus_id(to_bus_raw)

            seg.from_bus_id = from_bus
            seg.to_bus_id = to_bus
            seg.phasing = self.get_val(row, 'phasing')
            seg.length_meters = sanitize_float(self.get_val(row, 'length_meters'))
            seg.feeder = self.get_val(row, 'feeder')
            
            # Technical fields
            for f in [
                'configuration', 'system_grounding_type', 'conductor_type', 'conductor_size', 
                'conductor_unit', 'conductor_strands', 'neutral_wire_type', 'neutral_wire_size', 
                'neutral_wire_unit', 'neutral_wire_strands'
            ]:
                setattr(seg, f, self.get_val(row, f))
                
            for f in [
                'spacing_d12', 'spacing_d23', 'spacing_d13', 'spacing_d1n', 'spacing_d2n', 
                'spacing_d3n', 'spacing_dc1_c2', 'height_h1', 'height_h2', 'height_h3', 
                'height_hn', 'earth_resistivity'
            ]:
                setattr(seg, f, sanitize_float(self.get_val(row, f)))
            
            seg.upload_id = self.current_upload_id
            
            # COORDINATE & CONNECTION LOGIC
            if not from_bus or not to_bus: 
                db.session.add(seg)
                continue
            
            s_from = self._parse_pole_suffix(from_bus)
            s_to = self._parse_pole_suffix(to_bus)
            
            # CASE SELECTION
            from_dash = '-' in from_bus
            to_dash = '-' in to_bus
            expanded = False
            
            if not from_dash and not to_dash:
                # 1. PURE HIGHWAY (P1 -> P9)
                expanded = True
                if s_from < s_to: rng = range(s_from, s_to + 1)
                else: rng = range(s_from, s_to - 1, -1)
                
                prev_bus = None
                for i in rng:
                    curr_bus = self._normalize_bus_id(f"P{i}")
                    # Update Post technical data
                    hp = self.highway_post_map.get(i)
                    if hp: self._apply_segment_stats_to_post(seg, hp)

                    if curr_bus not in node_cache and curr_bus not in node_session_cache:
                        p_data = self.highway_pool.get(i)
                        if p_data:
                            try:
                                bn_lat, bn_lng = float(p_data['latitude']), float(p_data['longitude'])
                                node_cache[curr_bus] = (bn_lat, bn_lng)
                                # Create BusNode if not exists in DB
                                if not BusNode.query.filter_by(bus_id=curr_bus).first():
                                    db.session.add(BusNode(bus_id=curr_bus, lat=bn_lat, lng=bn_lng, feeder=seg.feeder))
                                node_session_cache.add(curr_bus)
                            except (ValueError, TypeError, KeyError):
                                pass
                    
                    if curr_bus in node_cache:
                        if prev_bus:
                            # Link
                            conn_key = tuple(sorted([prev_bus, curr_bus]))
                            if conn_key not in conn_session_cache:
                                if not LineConnection.query.filter_by(from_bus=prev_bus, to_bus=curr_bus, connection_type='Primary_to_Primary').first():
                                    db.session.add(LineConnection(from_bus=prev_bus, to_bus=curr_bus, connection_type='Primary_to_Primary', phasing=seg.phasing, feeder=seg.feeder))
                                conn_session_cache.add(conn_key)
                        prev_bus = curr_bus
            
            elif (not from_dash and to_dash) or (from_dash and to_dash and to_bus.split('-')[0] == from_bus.split('-')[0]):
                # 2. LATERAL BRANCH (P16 -> P16-13 or P16-1 -> P16-2)
                expanded = True
                root_from = from_bus.split('-')[0] if '-' in from_bus else from_bus
                root_to = to_bus.split('-')[0] if '-' in to_bus else to_bus
                
                # Apply to root post if it exists
                root_num = self._parse_pole_suffix(root_from)
                hp = self.highway_post_map.get(root_num)
                if hp: self._apply_segment_stats_to_post(seg, hp)

                if not from_dash:
                    num_to_add = s_to
                    naming_base = 0
                elif root_to == root_from:
                    num_to_add = s_to - s_from
                    naming_base = s_from
                else:
                    num_to_add = s_to - s_from if s_to > s_from else 1
                    naming_base = s_from
                
                if num_to_add < 1: num_to_add = 1
                
                prev_bus = from_bus
                for i in range(1, num_to_add + 1):
                    if i == num_to_add: curr_bus = to_bus
                    else:
                        prefix = from_bus.split('-')[0]
                        curr_bus = f"{prefix}-{naming_base + i}"
                    
                    # Update Post technical data if already exists
                    lp = self.named_post_map.get(curr_bus)
                    if lp: self._apply_segment_stats_to_post(seg, lp)

                    if curr_bus not in node_cache and curr_bus not in node_session_cache:
                        prev_coords = node_cache.get(prev_bus)
                        if prev_coords and self.lateral_pool:
                            p_lat, p_lng = prev_coords
                            best_idx = -1
                            min_dist = float('inf')
                            for idx, lp_data in enumerate(self.lateral_pool):
                                try:
                                    lp_lat, lp_lng = float(lp_data['latitude']), float(lp_data['longitude'])
                                    dist_sq = (lp_lat - p_lat)**2 + (lp_lng - p_lng)**2
                                    if dist_sq < min_dist:
                                        min_dist = dist_sq
                                        best_idx = idx
                                except (ValueError, TypeError, KeyError):
                                    continue
                            
                            # Threshold check (500m)
                            if best_idx != -1 and min_dist < 0.000025:
                                p_data = self.lateral_pool.pop(best_idx)
                                bn_lat, bn_lng = float(p_data['latitude']), float(p_data['longitude'])
                                node_cache[curr_bus] = (bn_lat, bn_lng)
                                
                                # Update the underlying Post record so UI shows the correct Pole Number
                                post_record = p_data.get('record') or Post.query.get(p_data['post_id'])
                                if post_record:
                                    post_record.pole_number = curr_bus
                                    post_record.name = f"Pole {curr_bus.replace('P00000000', '')}"
                                    self._apply_segment_stats_to_post(seg, post_record)
                                    
                                if not BusNode.query.filter_by(bus_id=curr_bus).first():
                                    db.session.add(BusNode(bus_id=curr_bus, lat=bn_lat, lng=bn_lng, feeder=seg.feeder))
                                node_session_cache.add(curr_bus)
                    
                    if curr_bus in node_cache:
                        conn_key = tuple(sorted([prev_bus, curr_bus]))
                        if conn_key not in conn_session_cache:
                            if not LineConnection.query.filter_by(from_bus=prev_bus, to_bus=curr_bus, connection_type='Primary_to_Primary').first():
                                db.session.add(LineConnection(from_bus=prev_bus, to_bus=curr_bus, connection_type='Primary_to_Primary', phasing=seg.phasing, feeder=seg.feeder))
                            conn_session_cache.add(conn_key)
                        prev_bus = curr_bus
                    else: break
            
            else:
                # 3. DIRECT TAP / CROSS-CONNECTION
                # SAFETY: Prevent loops back to the origin pole in the same branch
                root_from = from_bus.split('-')[0] if '-' in from_bus else from_bus
                root_to = to_bus.split('-')[0] if '-' in to_bus else to_bus
                is_loop = (from_bus and to_bus and root_from == root_to)
                
                if from_bus in node_cache and to_bus in node_cache and not is_loop:
                    conn_key = tuple(sorted([from_bus, to_bus]))
                    if conn_key not in conn_session_cache:
                        if not LineConnection.query.filter_by(from_bus=from_bus, to_bus=to_bus, connection_type='Primary_to_Primary').first():
                            db.session.add(LineConnection(from_bus=from_bus, to_bus=to_bus, connection_type='Primary_to_Primary', phasing=seg.phasing, feeder=seg.feeder))
                        conn_session_cache.add(conn_key)
            
            # Only save the logical segment IF it wasn't expanded into a physical chain
            # This avoids 'double lines' on the map.
            if not expanded:
                db.session.add(seg)

class SecondaryLineImporter(BaseImporter):
    file_type = 'secondary_lines'
    model_class = SecondaryLineSegment
    header_mappings = {
        'segment_id': ['Secondary Distribution Line ID', 'Segment ID', 'segment_id'],
        'from_bus_id': ['from_bus_id', 'From Bus ID', 'from_bus', 'From\nBus ID'],
        'to_bus_id': ['to_bus_id', 'To Bus ID', 'to_bus', 'To\nBus ID', 'To \nBus ID'],
        'phasing': ['phasing', 'Phasing'],
        'installation_type': ['Installation Type', 'installation_type'],
        'length_meters': ['length_meters', 'Length (m)', 'length', 'Length (meters)', 'Length         (meters)'],
        'conductor_type': ['conductor_type', 'Conductor Type'],
        'conductor_size': ['Conductor Size', 'conductor_size'],
        'conductor_unit': ['Unit (C) ', 'Unit (C)', 'unit_c', 'conductor_unit'],
    }
    
    def process_rows(self, reader):
        existing_segments = {}
        for s in SecondaryLineSegment.query.all():
            if s.segment_id:
                existing_segments[s.segment_id.strip().upper()] = s
            existing_segments[(s.from_bus_id, s.to_bus_id, s.phasing)] = s

        for row in reader:
            from_bus = self.get_val(row, 'from_bus_id')
            to_bus = self.get_val(row, 'to_bus_id')
            phasing = self.get_val(row, 'phasing')
            if not from_bus or not to_bus: continue
            
            seg_id = self.get_val(row, 'segment_id')
            clean_seg_id = seg_id.strip().upper() if seg_id else None

            # Try to find existing by segment_id first, then composite key
            seg = None
            if clean_seg_id:
                seg = existing_segments.get(clean_seg_id)
            if not seg:
                seg = existing_segments.get((from_bus, to_bus, phasing))
            
            if not seg:
                seg = SecondaryLineSegment(from_bus_id=from_bus, to_bus_id=to_bus, phasing=phasing)
                if clean_seg_id:
                    seg.segment_id = clean_seg_id
                db.session.add(seg)
                if clean_seg_id:
                    existing_segments[clean_seg_id] = seg
                existing_segments[(from_bus, to_bus, phasing)] = seg
                self.stats['created'] += 1
            else:
                self.stats['updated'] += 1
            
            seg.length_meters = sanitize_float(self.get_val(row, 'length_meters'))
            seg.conductor_type = self.get_val(row, 'conductor_type')
            seg.conductor_size = self.get_val(row, 'conductor_size')
            seg.installation_type = self.get_val(row, 'installation_type')
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

