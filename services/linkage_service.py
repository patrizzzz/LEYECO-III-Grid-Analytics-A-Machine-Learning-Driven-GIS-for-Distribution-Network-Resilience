import re
from extensions import db
from models import Post, DistributionTransformer

class LinkageService:
    """Consolidated topology reconciliation logic from legacy heal scripts."""
    
    @staticmethod
    def fuzzy_match_transformer_to_post(transformer, posts, bus_node_map=None):
        """
        Attempts to find a physical Post for a given Transformer based on bus IDs.
        Prioritizes explicit post_id mapping from BusNodes.
        """
        post_by_id = {str(p.id): p for p in posts}
        post_by_pole = {str(p.pole_number).strip().lower(): p for p in posts if p.pole_number}
        post_by_bus = {str(p.primary_bus_id).strip().lower(): p for p in posts if p.primary_bus_id}
        
        buses_to_check = [
            str(transformer.from_primary_bus_id or "").strip(), 
            str(transformer.to_secondary_bus_id or "").strip()
        ]
        
        for bus_id in buses_to_check:
            if not bus_id: continue
            key = bus_id.lower()
            
            # 1. Explicit BusNode Mapping (Priority)
            if bus_node_map and key in bus_node_map:
                target_post_id = str(bus_node_map[key])
                p = post_by_id.get(target_post_id)
                if p: return p

            # 2. Direct match on pole_number or primary_bus_id
            p = post_by_bus.get(key) or post_by_pole.get(key)
            if p: return p
                
            # 3. Regex variants (Fuzzy fallback)
            parts = [part for part in re.split(r'[^a-zA-Z0-9]', bus_id) if part]
            candidates = set()
            if len(parts) > 1:
                last = parts[-1].lower()
                candidates.update([last, last.lstrip('0')])
                m = re.match(r'^(\d+)[a-zA-Z]*$', last)
                if m: candidates.update([m.group(1).lower(), m.group(1).lstrip('0').lower()])
                candidates.add(parts[0].replace('P', '').replace('p', '').lstrip('0').lower())
            else:
                m = re.search(r'\d+', bus_id)
                if m:
                    num = m.group(0).lower()
                    candidates.update([num, num.lstrip('0')])
            
            for c in candidates:
                p = post_by_bus.get(c) or post_by_pole.get(c)
                if p: return p
                    
        return None

    @classmethod
    def run_bulk_reconciliation(cls):
        """Re-links all transformers to posts using explicit mappings where available."""
        from models import BusNode
        transformers = DistributionTransformer.query.all()
        posts = Post.query.all()
        bus_nodes = BusNode.query.all()
        
        # Build map: bus_id (lower) -> pole_number (post_id)
        bus_node_map = {str(bn.bus_id).strip().lower(): bn.pole_number for bn in bus_nodes if bn.bus_id and bn.pole_number}
        
        count = 0
        for t in transformers:
            p = cls.fuzzy_match_transformer_to_post(t, posts, bus_node_map=bus_node_map)
            if p:
                p.has_transformer = True
                p.kva_rating = t.kva_rating
                p.transformer_bus_id = t.from_primary_bus_id or t.to_secondary_bus_id
                count += 1
        db.session.commit()
        return count
