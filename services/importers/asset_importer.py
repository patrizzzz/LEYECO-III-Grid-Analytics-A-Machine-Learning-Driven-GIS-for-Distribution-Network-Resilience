from flask import current_app
from services.importers.base_importer import BaseImporter, sanitize_float
from models import Post, BusNode, DistributionTransformer, UploadHistory, VoltageRegulator, ShuntCapacitor, ShuntInductor, SeriesInductor
from extensions import db
from services.linkage_service import LinkageService

class PostImporter(BaseImporter):
    file_type = 'posts'
    model_class = Post
    header_mappings = {
        'pole_number': ['pole id number', 'Post ID', 'post_id', 'Pole ID', 'pole_id', 'pole_number', 'Pole Number', 'Post No', 'Pole No', 'ID', 'id', 'Name', 'name'],
        'pole_num': ['pole_num', 'Pole Num', 'POLE_NUM', 'sequence_number', 'No.', 'no'],
        'name': ['name', 'Name', 'Post Name'],
        'feeder': ['feeder', 'Feeder'],
        'phasing': ['phasing', 'Phasing'],
        'lat': ['latitude', 'Latitude', 'lat', 'Lat', 'latitue'],
        'lng': ['longitude', 'Longitude', 'lon', 'long', 'Long', 'longitute', 'longtitude', 'longtiude'],
        
        # Primary Line Technical Fields
        'configuration': ['Configuration', 'config'],
        'system_grounding_type': ['System Grounding Type', 'grounding_type'],
        'length_meters': ['Length (meters)', 'Length (m)', 'length', 'Length         (meters)'],
        'conductor_type': ['Conductor Type', 'wire_type'],
        'pri_conductor_size': ['Conductor Size', 'pri_conductor_size'],
        'conductor_unit': ['Unit (C) ', 'Unit (C)', 'unit_c'],
        'conductor_strands': ['Strands (C) ', 'Strands (C)', 'strands_c'],
        'neutral_wire': ['Neutral Wire'],
        'neutral_wire_type': ['Neutral Wire Type'],
        'neutral_wire_size': ['Neutral Wire Size'],
        'neutral_wire_unit': ['Unit (NW)'],
        'neutral_wire_strands': ['Strands (NW)'],
        'spacing_d12': ['Spacing D12 (meters)', 'spacing_d12'],
        'spacing_d23': ['Spacing D23 (meters)', 'spacing_d23'],
        'spacing_d13': ['Spacing D13 (meters)', 'spacing_d13'],
        'spacing_d1n': ['Spacing D1n (meters)', 'spacing_d1n'],
        'spacing_d2n': ['Spacing D2n (meters)', 'spacing_d2n'],
        'spacing_d3n': ['Spacing D3n (meters)', 'spacing_d3n'],
        'spacing_dc1_c2': ['Spacing DC1-C2 (meters)', 'spacing_dc1_c2'],
        'height_h1': ['Height H1 (meters)', 'height_h1'],
        'height_h2': ['Height H2 (meters)', 'height_h2'],
        'height_h3': ['Height H3 (meters)', 'height_h3'],
        'height_hn': ['Height Hn (meters)', 'height_hn'],
        'earth_resistivity': ['Earth Resistivity (Ohm-meter)', 'earth_resistivity']
    }

    def process_rows(self, reader):
        existing_posts = {str(p.pole_number).strip().lower(): p for p in Post.query.all() if p.pole_number}
        batch_size = 500
        count = 0
        
        for row in reader:
            pole_num = self.get_val(row, 'pole_number')
            
            lat_val = sanitize_float(self.get_val(row, 'lat'))
            lng_val = sanitize_float(self.get_val(row, 'lng'))
            
            # Skip invalid rows that have no pole number and no coordinates
            if not pole_num and lat_val is None and lng_val is None:
                continue
            
            post = None
            if pole_num:
                key = str(pole_num).strip().lower()
                post = existing_posts.get(key)
            
            if not post:
                # Create new post
                post = Post(pole_number=pole_num)
                # Ensure primary_bus_id is set to the pole_number by default for matching
                if not post.primary_bus_id:
                    post.primary_bus_id = pole_num
                
                db.session.add(post)
                if pole_num:
                    existing_posts[str(pole_num).strip().lower()] = post
                
                self.stats['created'] += 1
                
                # Full update for NEW posts
                post.name = self.get_val(row, 'name')
                post.feeder = self.get_val(row, 'feeder')
                post.phasing = self.get_val(row, 'phasing')
                
                # Set coordinates
                post.lat = lat_val if lat_val is not None else 0.0
                post.lng = lng_val if lng_val is not None else 0.0

                # Technical fields for primary line
                for f in [
                    'configuration', 'system_grounding_type', 'conductor_type',
                    'conductor_unit', 'conductor_strands', 'neutral_wire',
                    'neutral_wire_type', 'neutral_wire_size', 'neutral_wire_unit', 'neutral_wire_strands'
                ]:
                    setattr(post, f, self.get_val(row, f))
                
                post.pri_conductor_size = self.get_val(row, 'pri_conductor_size')
                
                # Set pole_num for sequential sequence logic
                p_num_val = self.get_val(row, 'pole_num')
                if p_num_val is not None:
                    try: post.pole_num = int(float(str(p_num_val).strip()))
                    except: pass

                for f in [
                    'length_meters', 'spacing_d12', 'spacing_d23', 'spacing_d13', 'spacing_d1n',
                    'spacing_d2n', 'spacing_d3n', 'spacing_dc1_c2', 'height_h1', 'height_h2',
                    'height_h3', 'height_hn', 'earth_resistivity'
                ]:
                    setattr(post, f, sanitize_float(self.get_val(row, f)))
            else:
                self.stats['updated'] += 1
                # Existing post: update coordinates if provided
                if lat_val is not None: post.lat = lat_val
                if lng_val is not None: post.lng = lng_val
            
            post.upload_id = self.current_upload_id
            
            count += 1
            if count % batch_size == 0:
                db.session.flush()

        db.session.flush()
        
        # Apply default naming in one bulk SQL statement for efficiency
        try:
            db.session.execute(db.text("UPDATE post SET name = 'Pole ' || id WHERE name IS NULL AND upload_id = :uid"), 
                               {"uid": self.current_upload_id})
        except Exception as e:
            current_app.logger.warning(f"Bulk naming failed: {e}")
            # ... and so on

class LateralPoleImporter(PostImporter):
    file_type = 'lateral_poles'


class BusNodeImporter(BaseImporter):
    file_type = 'bus_nodes'
    model_class = BusNode
    header_mappings = {
        'bus_id': ['Bus ID', 'bus_id', 'BusID'],
        'pole_number': ['Pole Number', 'pole_number'],
        'pole_id': ['Pole ID', 'pole_id', 'post_id', 'Post ID'],
        'nominal_voltage': ['Nominal Voltage (kV)', 'Nominal Voltage', 'volt', 'voltage'],
        'feeder': ['Feeder', 'feeder']
    }
    
    def process_rows(self, reader):
        existing_nodes = {n.bus_id.strip().lower(): n for n in BusNode.query.all()}
        # Use centralized lookup for posts: pole_number -> id AND id -> id
        all_posts = Post.query.all()
        post_by_pole = {str(p.pole_number).strip().lower(): p for p in all_posts if p.pole_number}
        post_by_id = {p.id: p for p in all_posts}
        
        batch_size = 500
        count = 0
        
        for row in reader:
            bus_id = self.get_val(row, 'bus_id')
            if not bus_id: continue
            
            key = str(bus_id).strip().lower()
            node = existing_nodes.get(key)
            if not node:
                node = BusNode(bus_id=bus_id)
                db.session.add(node)
                existing_nodes[key] = node
                self.stats['created'] += 1
            else:
                self.stats['updated'] += 1
                
            node.pole_number = self.get_val(row, 'pole_number')
            # node.pole_id is explicitly verified below to avoid FK violations
            node.nominal_voltage = sanitize_float(self.get_val(row, 'nominal_voltage'))
            node.feeder = self.get_val(row, 'feeder')
            node.upload_id = self.current_upload_id
            
            # Inherit coordinates from Post
            p = None
            # 1. Try numeric ID first if provided
            raw_pole_id = self.get_val(row, 'pole_id')
            if raw_pole_id:
                try:
                    p_id = int(float(raw_pole_id))
                    p = post_by_id.get(p_id)
                    if p:
                        node.pole_id = p.id
                        node.pole_number = p.pole_number
                except (ValueError, TypeError):
                    pass
            
            # 2. Try string pole_number if ID link failed
            if not p and node.pole_number:
                p = post_by_pole.get(str(node.pole_number).strip().lower())
                if p:
                    node.pole_id = p.id

            if p:
                node.lat, node.lng = p.lat, p.lng
                if node.feeder:
                    p.feeder = node.feeder

            count += 1
            if count % batch_size == 0:
                db.session.flush()

class TransformerImporter(BaseImporter):
    file_type = 'transformers'
    model_class = DistributionTransformer
    header_mappings = {
        'transformer_id': ['Transformer ID', 'transformer_id', 'TransformerID', 'Distribution Transformer ID'],
        'from_primary_bus_id': ['From Primary Bus ID', 'primary_bus', 'from_bus'],
        'to_secondary_bus_id': ['To Secondary Bus ID', 'secondary_bus', 'to_bus'],
        'kva_rating': ['kVA Rating', 'kva', 'capacity', 'KVA Rating'],
        'primary_phasing': ['Primary Phasing'],
        'secondary_phasing': ['Secondary Phasing'],
        'installation_type': ['Installation Type'],
        'connection': ['Connection'],
        'primary_voltage_kv': ['Primary Voltage Rating(kV)', 'primary_voltage'],
        'secondary_voltage_kv': ['Secondary Voltage Rating (kV)', 'secondary_voltage'],
        'primary_tap_kv': ['Primary Tap Voltage (kV)'],
        'secondary_tap_kv': ['Secondary Tap Voltage (kV)'],
        'pct_z': ['%Z', 'z_pct'],
        'xr_ratio': ['X/R Ratio', 'xr_ratio'],
        'no_load_loss_kw': ['No-Load Loss (kW)'],
        'exciting_current_pct': ['Exciting Current (%)'],
    }
    
    def process_rows(self, reader):
        from services.linkage_service import LinkageContext
        existing_tx = {str(t.transformer_id).strip().lower(): t for t in DistributionTransformer.query.all()}
        
        # Pre-build lookup context for efficient reconciliation
        from models import BusNode
        posts = Post.query.all()
        bus_nodes = BusNode.query.all()
        context = LinkageContext(posts=posts, bus_nodes=bus_nodes)
        
        batch_size = 500
        count = 0
        
        for row in reader:
            tx_id = self.get_val(row, 'transformer_id')
            if not tx_id: continue
            
            key = str(tx_id).strip().lower()
            tx = existing_tx.get(key)
            if not tx:
                tx = DistributionTransformer(transformer_id=tx_id)
                db.session.add(tx)
                existing_tx[key] = tx
                self.stats['created'] += 1
            else:
                self.stats['updated'] += 1
            
            tx.from_primary_bus_id = self.get_val(row, 'from_primary_bus_id')
            tx.to_secondary_bus_id = self.get_val(row, 'to_secondary_bus_id')
            tx.kva_rating = sanitize_float(self.get_val(row, 'kva_rating'))
            tx.primary_phasing = self.get_val(row, 'primary_phasing')
            tx.secondary_phasing = self.get_val(row, 'secondary_phasing')
            tx.installation_type = self.get_val(row, 'installation_type')
            tx.connection = self.get_val(row, 'connection')
            tx.primary_voltage_kv = sanitize_float(self.get_val(row, 'primary_voltage_kv'))
            tx.secondary_voltage_kv = sanitize_float(self.get_val(row, 'secondary_voltage_kv'))
            tx.primary_tap_kv = sanitize_float(self.get_val(row, 'primary_tap_kv'))
            tx.secondary_tap_kv = sanitize_float(self.get_val(row, 'secondary_tap_kv'))
            tx.pct_z = sanitize_float(self.get_val(row, 'pct_z'))
            tx.xr_ratio = sanitize_float(self.get_val(row, 'xr_ratio'))
            tx.no_load_loss_kw = sanitize_float(self.get_val(row, 'no_load_loss_kw'))
            tx.exciting_current_pct = sanitize_float(self.get_val(row, 'exciting_current_pct'))
            tx.upload_id = self.current_upload_id
            
            # Integrated Healing Logic with context
            linked_post = LinkageService.fuzzy_match_transformer_to_post(tx, context=context)
            if linked_post and linked_post.lat and linked_post.lng and linked_post.lat != 0.0 and linked_post.lng != 0.0:
                linked_post.has_transformer = True
                linked_post.kva_rating = tx.kva_rating
                linked_post.transformer_bus_id = tx.from_primary_bus_id or tx.to_secondary_bus_id
                
                # AUTO-HEAL: Update the BusNode linkage to point to THIS visible post
                target_bus = tx.from_primary_bus_id or tx.to_secondary_bus_id
                if target_bus:
                    from services.linkage_service import normalize_id
                    norm_target = normalize_id(target_bus)
                    
                    # Extra safety: Ensure we aren't mapping a lateral ID to a highway pole
                    is_lateral_tx = '-' in str(target_bus)
                    pole_id_str = str(linked_post.pole_number or linked_post.primary_bus_id or "")
                    is_lateral_pole = '-' in pole_id_str
                    
                    if is_lateral_tx and not is_lateral_pole:
                        # Skip auto-heal for this mismatch to prevent pollution
                        pass
                    else:
                        # Find any existing bus nodes for this ID and point them to the linked_post
                        for bn in context.bus_nodes:
                            if normalize_id(bn.bus_id) == norm_target:
                                if bn.pole_id != linked_post.id:
                                    bn.pole_id = linked_post.id
                                    bn.pole_number = linked_post.pole_number
                                    db.session.add(bn)

            count += 1
            if count % batch_size == 0:
                db.session.flush()


class VoltageRegulatorImporter(BaseImporter):
    file_type = 'voltage_regulators'
    model_class = VoltageRegulator
    header_mappings = {
        'regulator_id': ['Voltage Regulator ID', 'Regulator ID', 'regulator_id'],
        'from_bus_id': ['From \nBus ID', 'From Bus ID', 'from_bus'],
        'to_bus_id': ['To  \nBus ID', 'To Bus ID', 'to_bus'],
        'regulated_bus_id': ['Regulated Bus ID'],
        'phase_type': ['Phase Type'],
        'phasing': ['Phasing'],
        'phase_sense': ['Phase Sense'],
        'kva_rating': ['KVA Rating ', 'kVA Rating', 'kva'],
        'kv_rating': ['KV Rating ', 'kV Rating', 'kv'],
        'target_voltage': ['Target Voltage (120V base)', 'Target Voltage'],
        'bandwidth': ['Bandwidth     (120V base)', 'Bandwidth'],
        'r_setting_a': ['R-Setting Phase A'],
        'r_setting_b': ['R-Setting Phase B'],
        'r_setting_c': ['R-Setting Phase C'],
        'x_setting_a': ['X-Setting Phase A'],
        'x_setting_b': ['X-Setting Phase B'],
        'x_setting_c': ['X-Setting Phase C'],
        'primary_current_rating': ['Primary Current Rating (A)', 'Primary Current Rating'],
        'pt_ratio': ['PT Ratio'],
        'no_load_loss_kw': ['No-Load Loss (kW)'],
        'exciting_current_pct': ['Exciting Current (%)'],
    }

    def process_rows(self, reader):
        from models import BusNode
        posts = Post.query.all()
        bus_nodes = BusNode.query.all()
        context = LinkageService.LinkageContext(posts=posts, bus_nodes=bus_nodes) if hasattr(LinkageService, 'LinkageContext') else None
        
        existing = {str(r.regulator_id).strip().lower(): r for r in VoltageRegulator.query.all() if r.regulator_id}
        for row in reader:
            reg_id = self.get_val(row, 'regulator_id')
            if not reg_id: continue
            key = str(reg_id).strip().lower()
            record = existing.get(key)
            if not record:
                record = VoltageRegulator(regulator_id=reg_id)
                db.session.add(record)
                existing[key] = record
                self.stats['created'] += 1
            else:
                self.stats['updated'] += 1

            record.from_bus_id = self.get_val(row, 'from_bus_id')
            record.to_bus_id = self.get_val(row, 'to_bus_id')
            record.regulated_bus_id = self.get_val(row, 'regulated_bus_id')
            record.phase_type = self.get_val(row, 'phase_type')
            record.phasing = self.get_val(row, 'phasing')
            record.phase_sense = self.get_val(row, 'phase_sense')
            record.kva_rating = sanitize_float(self.get_val(row, 'kva_rating'))
            record.kv_rating = sanitize_float(self.get_val(row, 'kv_rating'))
            record.target_voltage = sanitize_float(self.get_val(row, 'target_voltage'))
            record.bandwidth = sanitize_float(self.get_val(row, 'bandwidth'))
            record.r_setting_a = sanitize_float(self.get_val(row, 'r_setting_a'))
            record.r_setting_b = sanitize_float(self.get_val(row, 'r_setting_b'))
            record.r_setting_c = sanitize_float(self.get_val(row, 'r_setting_c'))
            record.x_setting_a = sanitize_float(self.get_val(row, 'x_setting_a'))
            record.x_setting_b = sanitize_float(self.get_val(row, 'x_setting_b'))
            record.x_setting_c = sanitize_float(self.get_val(row, 'x_setting_c'))
            record.primary_current_rating = sanitize_float(self.get_val(row, 'primary_current_rating'))
            record.pt_ratio = sanitize_float(self.get_val(row, 'pt_ratio'))
            record.no_load_loss_kw = sanitize_float(self.get_val(row, 'no_load_loss_kw'))
            record.exciting_current_pct = sanitize_float(self.get_val(row, 'exciting_current_pct'))
            record.upload_id = self.current_upload_id

            # Topology Linkage: If we find a matching post, ensure at least one bus is associated with it
            linked_post = LinkageService.fuzzy_match_asset_to_post(record, context=context)
            if linked_post:
                # Ensure a BusNode entry exists for this bus linked to this post
                target_bus = record.from_bus_id or record.to_bus_id
                if target_bus:
                    bn = next((b for b in bus_nodes if b.bus_id == target_bus), None)
                    if not bn:
                        bn = BusNode(bus_id=target_bus, pole_id=linked_post.id, pole_number=linked_post.pole_number, upload_id=self.current_upload_id)
                        db.session.add(bn)
                        bus_nodes.append(bn)
                    else:
                        bn.pole_id = linked_post.id
                        bn.pole_number = linked_post.pole_number


class ShuntCapacitorImporter(BaseImporter):
    file_type = 'shunt_capacitors'
    model_class = ShuntCapacitor
    header_mappings = {
        'capacitor_id': ['Shunt Capacitor ID', 'Capacitor ID', 'capacitor_id'],
        'bus_connected_id': ['Bus Connected \n(Bus ID)', 'Bus Connected ID'],
        'phase_type': ['Phase Type'],
        'phasing': ['Phasing'],
        'voltage_rating_kv': ['Voltage Rating (kV)'],
        'kvar_rating_a': ['KVAR Rating Phase A', 'kVAR Rating Phase A'],
        'kvar_rating_b': ['KVAR Rating Phase B', 'kVAR Rating Phase B'],
        'kvar_rating_c': ['KVAR Rating Phase C', 'kVAR Rating Phase C'],
        'power_loss_watts': ['Power Loss (Watts)'],
    }

    def process_rows(self, reader):
        from models import BusNode
        posts = Post.query.all()
        bus_nodes = BusNode.query.all()
        context = LinkageService.LinkageContext(posts=posts, bus_nodes=bus_nodes) if hasattr(LinkageService, 'LinkageContext') else None
        
        existing = {str(r.capacitor_id).strip().lower(): r for r in ShuntCapacitor.query.all() if r.capacitor_id}
        for row in reader:
            cap_id = self.get_val(row, 'capacitor_id')
            if not cap_id: continue
            key = str(cap_id).strip().lower()
            record = existing.get(key)
            if not record:
                record = ShuntCapacitor(capacitor_id=cap_id)
                db.session.add(record)
                existing[key] = record
                self.stats['created'] += 1
            else:
                self.stats['updated'] += 1

            record.bus_connected_id = self.get_val(row, 'bus_connected_id')
            record.phase_type = self.get_val(row, 'phase_type')
            record.phasing = self.get_val(row, 'phasing')
            record.voltage_rating_kv = sanitize_float(self.get_val(row, 'voltage_rating_kv'))
            record.kvar_rating_a = sanitize_float(self.get_val(row, 'kvar_rating_a'))
            record.kvar_rating_b = sanitize_float(self.get_val(row, 'kvar_rating_b'))
            record.kvar_rating_c = sanitize_float(self.get_val(row, 'kvar_rating_c'))
            record.power_loss_watts = sanitize_float(self.get_val(row, 'power_loss_watts'))
            record.upload_id = self.current_upload_id

            # Topology Linkage
            linked_post = LinkageService.fuzzy_match_asset_to_post(record, context=context)
            if linked_post and record.bus_connected_id:
                bn = next((b for b in bus_nodes if b.bus_id == record.bus_connected_id), None)
                if not bn:
                    bn = BusNode(bus_id=record.bus_connected_id, pole_id=linked_post.id, pole_number=linked_post.pole_number, upload_id=self.current_upload_id)
                    db.session.add(bn)
                    bus_nodes.append(bn)
                else:
                    bn.pole_id = linked_post.id
                    bn.pole_number = linked_post.pole_number


class ShuntInductorImporter(BaseImporter):
    file_type = 'shunt_inductors'
    model_class = ShuntInductor
    header_mappings = {
        'inductor_id': ['Shunt Inductor ID', 'Inductor ID', 'inductor_id'],
        'bus_connected_id': ['Bus Connected\n(Bus ID)', 'Bus Connected \n(Bus ID)', 'Bus Connected ID'],
        'phase_type': ['Phase Type'],
        'phasing': ['Phasing'],
        'voltage_rating_kv': ['Voltage Rating (kV)'],
        'resistance_a': ['Resistance Phase A (Ohms)', 'Resistance Phase A'],
        'resistance_b': ['Resistance Phase B (Ohms)', 'Resistance Phase B'],
        'resistance_c': ['Resistance Phase C (Ohms)', 'Resistance Phase C'],
        'reactance_a': ['Reactance\nPhase A (Ohms)', 'Reactance \nPhase A (Ohms)', 'Reactance Phase A'],
        'reactance_b': ['Reactance \nPhase B (Ohms)', 'Reactance Phase B'],
        'reactance_c': ['Reactance \nPhase C (Ohms)', 'Reactance Phase C'],
    }

    def process_rows(self, reader):
        from models import BusNode
        posts = Post.query.all()
        bus_nodes = BusNode.query.all()
        context = LinkageService.LinkageContext(posts=posts, bus_nodes=bus_nodes) if hasattr(LinkageService, 'LinkageContext') else None
        
        existing = {str(r.inductor_id).strip().lower(): r for r in ShuntInductor.query.all() if r.inductor_id}
        for row in reader:
            ind_id = self.get_val(row, 'inductor_id')
            if not ind_id: continue
            key = str(ind_id).strip().lower()
            record = existing.get(key)
            if not record:
                record = ShuntInductor(inductor_id=ind_id)
                db.session.add(record)
                existing[key] = record
                self.stats['created'] += 1
            else:
                self.stats['updated'] += 1

            record.bus_connected_id = self.get_val(row, 'bus_connected_id')
            record.phase_type = self.get_val(row, 'phase_type')
            record.phasing = self.get_val(row, 'phasing')
            record.voltage_rating_kv = sanitize_float(self.get_val(row, 'voltage_rating_kv'))
            record.resistance_a = sanitize_float(self.get_val(row, 'resistance_a'))
            record.resistance_b = sanitize_float(self.get_val(row, 'resistance_b'))
            record.resistance_c = sanitize_float(self.get_val(row, 'resistance_c'))
            record.reactance_a = sanitize_float(self.get_val(row, 'reactance_a'))
            record.reactance_b = sanitize_float(self.get_val(row, 'reactance_b'))
            record.reactance_c = sanitize_float(self.get_val(row, 'reactance_c'))
            record.upload_id = self.current_upload_id

            # Topology Linkage
            linked_post = LinkageService.fuzzy_match_asset_to_post(record, context=context)
            if linked_post and record.bus_connected_id:
                bn = next((b for b in bus_nodes if b.bus_id == record.bus_connected_id), None)
                if not bn:
                    bn = BusNode(bus_id=record.bus_connected_id, pole_id=linked_post.id, pole_number=linked_post.pole_number, upload_id=self.current_upload_id)
                    db.session.add(bn)
                    bus_nodes.append(bn)
                else:
                    bn.pole_id = linked_post.id
                    bn.pole_number = linked_post.pole_number


class SeriesInductorImporter(BaseImporter):
    file_type = 'series_inductors'
    model_class = SeriesInductor
    header_mappings = {
        'inductor_id': ['Series Inductor ID', 'Inductor ID', 'inductor_id'],
        'from_bus_id': ['From \nBus ID', 'From Bus ID'],
        'to_bus_id': ['To  \nBus ID', 'To Bus ID'],
        'phase_type': ['Phase Type'],
        'phasing': ['Phasing'],
        'voltage_rating_kv': ['Voltage Rating (kV)'],
        'resistance_a': ['Resistance Phase A (Ohms)', 'Resistance Phase A'],
        'resistance_b': ['Resistance Phase B (Ohms)', 'Resistance Phase B'],
        'resistance_c': ['Resistance Phase C (Ohms)', 'Resistance Phase C'],
        'reactance_a': ['Reactance Phase A (Ohms)', 'Reactance Phase A'],
        'reactance_b': ['Reactance Phase B (Ohms)', 'Reactance Phase B'],
        'reactance_c': ['Reactance Phase C (Ohms)', 'Reactance Phase C'],
    }

    def process_rows(self, reader):
        from models import BusNode
        posts = Post.query.all()
        bus_nodes = BusNode.query.all()
        context = LinkageService.LinkageContext(posts=posts, bus_nodes=bus_nodes) if hasattr(LinkageService, 'LinkageContext') else None
        
        existing = {str(r.inductor_id).strip().lower(): r for r in SeriesInductor.query.all() if r.inductor_id}
        for row in reader:
            ind_id = self.get_val(row, 'inductor_id')
            if not ind_id: continue
            key = str(ind_id).strip().lower()
            record = existing.get(key)
            if not record:
                record = SeriesInductor(inductor_id=ind_id)
                db.session.add(record)
                existing[key] = record
                self.stats['created'] += 1
            else:
                self.stats['updated'] += 1

            record.from_bus_id = self.get_val(row, 'from_bus_id')
            record.to_bus_id = self.get_val(row, 'to_bus_id')
            record.phase_type = self.get_val(row, 'phase_type')
            record.phasing = self.get_val(row, 'phasing')
            record.voltage_rating_kv = sanitize_float(self.get_val(row, 'voltage_rating_kv'))
            record.resistance_a = sanitize_float(self.get_val(row, 'resistance_a'))
            record.resistance_b = sanitize_float(self.get_val(row, 'resistance_b'))
            record.resistance_c = sanitize_float(self.get_val(row, 'resistance_c'))
            record.reactance_a = sanitize_float(self.get_val(row, 'reactance_a'))
            record.reactance_b = sanitize_float(self.get_val(row, 'reactance_b'))
            record.reactance_c = sanitize_float(self.get_val(row, 'reactance_c'))
            record.upload_id = self.current_upload_id

            # Topology Linkage
            linked_post = LinkageService.fuzzy_match_asset_to_post(record, context=context)
            if linked_post:
                target_bus = record.from_bus_id or record.to_bus_id
                if target_bus:
                    bn = next((b for b in bus_nodes if b.bus_id == target_bus), None)
                    if not bn:
                        bn = BusNode(bus_id=target_bus, pole_id=linked_post.id, pole_number=linked_post.pole_number, upload_id=self.current_upload_id)
                        db.session.add(bn)
                        bus_nodes.append(bn)
                    else:
                        bn.pole_id = linked_post.id
                        bn.pole_number = linked_post.pole_number
