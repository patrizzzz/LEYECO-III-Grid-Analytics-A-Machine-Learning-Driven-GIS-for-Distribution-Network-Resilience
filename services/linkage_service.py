import re
from extensions import db
from models import Post, DistributionTransformer

def normalize_id(id_str):
    """
    Standardize IDs (like P00000001 -> P1, DT000001 -> DT1).
    Ensures consistent matching between assets and posts across different CSV sources.
    """
    if not id_str:
        return ""
    s = str(id_str).strip().upper()
    
    # regex to find prefix (letters) and number part
    match = re.match(r'^([a-zA-Z]+)(\d+)(.*)$', s)
    if match:
        prefix, num_part, suffix = match.groups()
        # Strip leading zeros from number part
        num_part = num_part.lstrip('0') or '0'
        return f"{prefix}{num_part}{suffix}"
    
    return s

class LinkageContext:
    """Helper to cache lookup maps for fuzzy matching to avoid repeated O(P) work."""
    def __init__(self, posts=None, bus_nodes=None):
        posts = posts or []
        bus_nodes = bus_nodes or []
        self.post_by_id = {str(p.id): p for p in posts}
        # Use normalized IDs for lookup maps
        self.post_by_pole = {normalize_id(p.pole_number): p for p in posts if p.pole_number}
        self.post_by_bus = {normalize_id(p.primary_bus_id): p for p in posts if p.primary_bus_id}
        self.bus_node_map = {normalize_id(bn.bus_id): bn.pole_id for bn in bus_nodes if bn.bus_id and bn.pole_id}

class LinkageService:
    """Consolidated topology reconciliation logic from legacy heal scripts."""
    
    @staticmethod
    def fuzzy_match_asset_to_post(asset, posts=None, bus_node_map=None, context=None):
        """
        Attempts to find a physical Post for any given Asset (VoltageRegulator, etc.) based on bus IDs.
        Checks for from_bus_id, to_bus_id, and bus_connected_id.
        """
        if context:
            post_by_id = context.post_by_id
            post_by_pole = context.post_by_pole
            post_by_bus = context.post_by_bus
            bus_node_map = context.bus_node_map
        else:
            post_by_id = {str(p.id): p for p in posts or []}
            post_by_pole = {normalize_id(p.pole_number): p for p in posts or [] if p.pole_number}
            post_by_bus = {normalize_id(p.primary_bus_id): p for p in posts or [] if p.primary_bus_id}
            bus_node_map = {normalize_id(k): v for k, v in (bus_node_map or {}).items()}
        
        # Collect all likely bus attributes across different asset models
        buses_to_check = []
        for attr in ['from_bus_id', 'to_bus_id', 'from_primary_bus_id', 'to_secondary_bus_id', 'bus_connected_id', 'regulated_bus_id']:
            val = getattr(asset, attr, None)
            if val:
                buses_to_check.append(str(val).strip())
        
        for bus_id in buses_to_check:
            if not bus_id: continue
            norm_id = normalize_id(bus_id)
            
            # 1. Explicit BusNode Mapping (Priority)
            if bus_node_map and norm_id in bus_node_map:
                target_post_id = str(bus_node_map[norm_id])
                p = post_by_id.get(target_post_id)
                if p: return p

            # 2. Direct match on pole_number or primary_bus_id
            p = post_by_bus.get(norm_id) or post_by_pole.get(norm_id)
            if p: return p
                
            # 3. Regex variants (Fuzzy fallback)
            # Only if direct match fails, try stripping punctuation or common prefixes
            parts = [part for part in re.split(r'[^a-zA-Z0-9]', bus_id) if part]
            candidates = set()
            if len(parts) > 1:
                last = parts[-1].upper()
                candidates.add(normalize_id(last))
                m = re.match(r'^(\d+)[A-Z]*$', last)
                if m: candidates.add(normalize_id(m.group(1)))
                candidates.add(normalize_id(parts[0]))
            else:
                m = re.search(r'\d+', bus_id)
                if m:
                    num = m.group(0)
                    candidates.add(normalize_id(num))
            
            for c in candidates:
                p = post_by_bus.get(c) or post_by_pole.get(c)
                if p: return p
                    
        return None

    @staticmethod
    def fuzzy_match_transformer_to_post(transformer, posts=None, bus_node_map=None, context=None):
        """LEGACY: Wrapper for generalized method."""
        return LinkageService.fuzzy_match_asset_to_post(transformer, posts, bus_node_map, context)

    @classmethod
    def run_bulk_reconciliation(cls):
        """Re-links all transformers and various assets to posts using explicit mappings where available."""
        from models import BusNode, VoltageRegulator, ShuntCapacitor, ShuntInductor, SeriesInductor
        transformers = DistributionTransformer.query.all()
        posts = Post.query.all()
        bus_nodes = BusNode.query.all()
        
        context = LinkageContext(posts=posts, bus_nodes=bus_nodes)
        
        count = 0
        # Reconcile Transformers
        for t in transformers:
            p = cls.fuzzy_match_asset_to_post(t, context=context)
            if p:
                p.has_transformer = True
                p.kva_rating = t.kva_rating
                p.transformer_bus_id = t.from_primary_bus_id or t.to_secondary_bus_id
                count += 1
        
        db.session.commit()
        return count
