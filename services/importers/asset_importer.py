from services.importers.base_importer import BaseImporter, sanitize_float
from models import Post, BusNode, DistributionTransformer, UploadHistory, VoltageRegulator, ShuntCapacitor, ShuntInductor, SeriesInductor
from extensions import db
from services.linkage_service import LinkageService

class PostImporter(BaseImporter):
    file_type = 'posts'
    model_class = Post
    header_mappings = {
        'pole_number': ['Post ID', 'post_id', 'Pole ID', 'pole_id', 'pole_number', 'Pole Number', 'post_id', 'Post ID'],
        'name': ['name', 'Name', 'Post Name'],
        'feeder': ['feeder', 'Feeder'],
        'phasing': ['phasing', 'Phasing'],
        'lat': ['latitude', 'Latitude', 'lat'],
        'lng': ['longitude', 'Longitude', 'lon', 'long'],
    }

    def process_rows(self, reader):
        existing_posts = {str(p.pole_number).strip().lower(): p for p in Post.query.all() if p.pole_number}
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
                # Create new post if no pole_number provided or not found
                post = Post(pole_number=pole_num)
                db.session.add(post)
                if pole_num:
                    existing_posts[str(pole_num).strip().lower()] = post
                
                self.stats['created'] += 1
                
                # Full update for NEW posts
                post.name = self.get_val(row, 'name')
                post.feeder = self.get_val(row, 'feeder')
                post.phasing = self.get_val(row, 'phasing')
                
                # Set coordinates BEFORE flush to satisfy NOT NULL constraints
                post.lat = lat_val if lat_val is not None else 0.0
                post.lng = lng_val if lng_val is not None else 0.0
                
                # Flush to get the ID if we need to generate a default name
                db.session.flush()
                if not post.name:
                    post.name = f"Pole {post.id}"
            else:
                self.stats['updated'] += 1
                # Existing post: update coordinates if provided
                if lat_val is not None: post.lat = lat_val
                if lng_val is not None: post.lng = lng_val
            
            post.upload_id = self.current_upload_id
            # ... and so on

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
        existing_posts = {str(p.pole_number).strip().lower(): p for p in Post.query.all() if p.pole_number}
        
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
            node.pole_id = self.get_val(row, 'pole_id')
            node.nominal_voltage = sanitize_float(self.get_val(row, 'nominal_voltage'))
            node.feeder = self.get_val(row, 'feeder')
            node.upload_id = self.current_upload_id
            
            # Inherit coordinates from Post
            p = None
            # 1. Try numeric ID first if provided
            if node.pole_id:
                try:
                    p_id = int(float(node.pole_id))
                    p = Post.query.get(p_id)
                    if p:
                        # Ensure node has the integer FK
                        node.pole_id = p.id
                        # Optionallly sync pole_number for reference
                        node.pole_number = p.pole_number
                except (ValueError, TypeError):
                    pass
            
            # 2. Try string pole_number if ID link failed
            if not p and node.pole_number:
                p = existing_posts.get(str(node.pole_number).strip().lower())
                if p:
                    node.pole_id = p.id

            if p:
                node.lat, node.lng = p.lat, p.lng
                if node.feeder:
                    p.feeder = node.feeder

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
        from models import BusNode
        existing_tx = {str(t.transformer_id).strip().lower(): t for t in DistributionTransformer.query.all()}
        all_posts = Post.query.all()
        # Build map: bus_id (lower) -> pole_number (which represents the post_id from bus_data.csv)
        # Build map: bus_id (lower) -> pole_id (integer)
        bus_nodes = BusNode.query.all()
        bus_node_map = {str(bn.bus_id).strip().lower(): bn.pole_id for bn in bus_nodes if bn.bus_id and bn.pole_id}
        
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
            
            # Integrated Healing Logic
            linked_post = LinkageService.fuzzy_match_transformer_to_post(tx, all_posts, bus_node_map=bus_node_map)
            if linked_post:
                linked_post.has_transformer = True
                linked_post.kva_rating = tx.kva_rating
                linked_post.transformer_bus_id = tx.from_primary_bus_id or tx.to_secondary_bus_id


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
