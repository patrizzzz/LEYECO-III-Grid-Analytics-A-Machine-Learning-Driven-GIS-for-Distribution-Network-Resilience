from services.importers.base_importer import BaseImporter, sanitize_float
from models import Post, BusNode, DistributionTransformer, UploadHistory
from extensions import db
from services.linkage_service import LinkageService

class PostImporter(BaseImporter):
    file_type = 'posts'
    model_class = Post
    header_mappings = {
        'pole_number': ['pole_number', 'Pole Number', 'Pole ID', 'pole_id', 'post_id', 'Post ID'],
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
            if not pole_num: continue
            
            key = str(pole_num).strip().lower()
            post = existing_posts.get(key)
            if not post:
                post = Post(pole_number=pole_num)
                db.session.add(post)
                existing_posts[key] = post
                self.stats['created'] += 1
            else:
                self.stats['updated'] += 1
            
            # Map common fields using header_mappings
            # Ensure required fields are not None to satisfy DB constraints
            post.name = self.get_val(row, 'name') or f"Pole {pole_num}"
            post.feeder = self.get_val(row, 'feeder')
            post.phasing = self.get_val(row, 'phasing')
            
            lat_val = sanitize_float(self.get_val(row, 'lat'))
            lng_val = sanitize_float(self.get_val(row, 'lng'))
            
            # PostGIS/SQLAlchemy requires lat/lng if the model says nullable=False
            post.lat = lat_val if lat_val is not None else 0.0
            post.lng = lng_val if lng_val is not None else 0.0
            # ... and so on

class BusNodeImporter(BaseImporter):
    file_type = 'bus_nodes'
    model_class = BusNode
    header_mappings = {
        'bus_id': ['Bus ID', 'bus_id', 'BusID'],
        'pole_number': ['Pole ID', 'pole_id', 'Pole Number', 'pole_number', 'post_id', 'Post ID'],
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
            node.nominal_voltage = sanitize_float(self.get_val(row, 'nominal_voltage'))
            node.feeder = self.get_val(row, 'feeder')
            
            # Inherit coordinates from Post
            if node.pole_number:
                p = existing_posts.get(str(node.pole_number).strip().lower())
                if p:
                    node.lat, node.lng = p.lat, p.lng

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
        bus_nodes = BusNode.query.all()
        bus_node_map = {str(bn.bus_id).strip().lower(): bn.pole_number for bn in bus_nodes if bn.bus_id and bn.pole_number}
        
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
            
            # Integrated Healing Logic
            linked_post = LinkageService.fuzzy_match_transformer_to_post(tx, all_posts, bus_node_map=bus_node_map)
            if linked_post:
                linked_post.has_transformer = True
                linked_post.kva_rating = tx.kva_rating
                linked_post.transformer_bus_id = tx.from_primary_bus_id or tx.to_secondary_bus_id
