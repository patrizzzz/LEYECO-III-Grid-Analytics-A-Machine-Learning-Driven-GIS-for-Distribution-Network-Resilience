import re
from extensions import db
from models import Post, DistributionTransformer

def normalize_id(id_str):
    """
    Standardize IDs (strip whitespace and uppercase).
    Normalization that strips leading zeros is disabled per user request to preserve original data format.
    """
    if not id_str:
        return ""
    return str(id_str).strip().upper()

class LinkageContext:
    """Helper to cache lookup maps for fuzzy matching to avoid repeated O(P) work."""
    def __init__(self, posts=None, bus_nodes=None):
        self.posts = posts or []
        self.bus_nodes = bus_nodes or []
        self.post_by_id = {str(p.id): p for p in self.posts}
        # Use normalized IDs for lookup maps
        self.post_by_pole = {normalize_id(p.pole_number): p for p in self.posts if p.pole_number}
        self.post_by_bus = {normalize_id(p.primary_bus_id): p for p in self.posts if p.primary_bus_id}
        self.post_by_seq = {str(p.pole_num): p for p in self.posts if p.pole_num is not None}
        self.bus_node_map = {normalize_id(bn.bus_id): bn.pole_id for bn in self.bus_nodes if bn.bus_id and bn.pole_id}
        # Absolute numeric lookup: extracts the pure integer from pole_number (e.g. "P116" -> "116").
        # This ensures P0000000116 always resolves to the pole physically labelled 116, not a
        # DB-sequence offset. Used as the authoritative fallback in Step 3.
        self.post_by_pole_num = {}
        for p in self.posts:
            if p.pole_number:
                m = re.match(r'^[A-Za-z]*0*(\d+)', str(p.pole_number))
                if m:
                    self.post_by_pole_num[m.group(1)] = p

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
            post_by_seq = getattr(context, 'post_by_seq', {})
            pole_num_map = getattr(context, 'post_by_pole_num', {})
            bus_node_map = context.bus_node_map
        else:
            posts = posts or []
            post_by_id = {str(p.id): p for p in posts}
            post_by_pole = {normalize_id(p.pole_number): p for p in posts if p.pole_number}
            post_by_bus = {normalize_id(p.primary_bus_id): p for p in posts if p.primary_bus_id}
            post_by_seq = {str(p.pole_num): p for p in posts if getattr(p, 'pole_num', None) is not None}
            bus_node_map = {normalize_id(k): v for k, v in (bus_node_map or {}).items()}
            
            # Replicate pole_num_map logic from LinkageContext
            pole_num_map = {}
            for p in posts:
                if p.pole_number:
                    m = re.match(r'^[A-Za-z]*0*(\d+)', str(p.pole_number))
                    if m:
                        pole_num_map[m.group(1)] = p
        
        # Collect all likely bus attributes across different asset models
        buses_to_check = []
        for attr in ['from_bus_id', 'to_bus_id', 'from_primary_bus_id', 'to_secondary_bus_id', 'bus_connected_id', 'regulated_bus_id']:
            val = getattr(asset, attr, None)
            if val:
                buses_to_check.append(str(val).strip())
        
        for bus_id in buses_to_check:
            if not bus_id: continue
            norm_id = normalize_id(bus_id)
            # Check for dash in Bus ID OR the asset's own ID (e.g. transformer_id)
            asset_id = str(getattr(asset, 'transformer_id', '') or getattr(asset, 'regulator_id', '') or '')
            has_dash = '-' in str(bus_id) or '-' in asset_id
            
            # 1. Direct match on pole_number or primary_bus_id (Priority)
            p = post_by_bus.get(norm_id) or post_by_pole.get(norm_id)
            
            # VALIDATION: If the asset has a dash, the pole MUST also have a dash in its identifier
            # or primary bus ID to be considered a valid match.
            if p and has_dash:
                pole_id_str = str(p.pole_number or p.primary_bus_id or "")
                if '-' not in pole_id_str:
                    p = None # Reject highway pole for lateral asset
            
            if p: return p

            # 2. Explicit BusNode Mapping (Fallback)
            if bus_node_map and norm_id in bus_node_map:
                target_post_id = str(bus_node_map[norm_id])
                p = post_by_id.get(target_post_id)
                
                # VALIDATION: Same dash consistency check for BusNode mappings
                if p and has_dash:
                    pole_id_str = str(p.pole_number or p.primary_bus_id or "")
                    if '-' not in pole_id_str:
                        p = None
                
                if p: return p
            
            # 2.5 Strip 'P' prefix and leading zeros (e.g. P0000000016-13 -> 16-13)
            # CRITICAL: We only allow the numeric fallback (post_by_seq) if there is NO dash.
            m = re.match(r'^P0*([0-9].*)$', bus_id.upper())
            if m:
                g1 = m.group(1)
                stripped_norm = normalize_id(g1)
                
                # Check direct maps with stripped ID
                p = post_by_bus.get(stripped_norm) or post_by_pole.get(stripped_norm)
                
                # Dash consistency check for stripped match
                if p and has_dash:
                    pole_id_str = str(p.pole_number or p.primary_bus_id or "")
                    if '-' not in pole_id_str:
                        p = None
                
                if p: return p
                
                # 3. Absolute Numeric Fallback - ONLY for non-lateral IDs.
                # Extracts the raw integer from the bus ID (e.g. "116" from "P0000000116")
                # and looks up the pole whose pole_number physically contains that same number.
                # This is more reliable than post_by_seq which uses an unrelated DB integer.
                if not has_dash:
                    try:
                        # Extract only the leading numeric part (e.g. "94" from "94A")
                        numeric_match = re.search(r'^(\d+)', g1)
                        if numeric_match:
                            num_str = str(int(numeric_match.group(1)))
                            p = pole_num_map.get(num_str)
                            if p: return p
                        
                        # Fallback to the full string match in sequence map
                        p = post_by_seq.get(g1)
                        if p: return p
                    except (ValueError, TypeError):
                        p = post_by_seq.get(g1)
                        if p: return p
                    
            # 4. Fuzzy fallback removed to enforce strict data matching
                    
        return None

    @staticmethod
    def _leading_digits_from_p_label(label):
        """First integer in a P-style label (P0000000009 -> '9', P0000000010 -> '10')."""
        if not label:
            return None
        m = re.match(r'^[A-Za-z]*0*(\d+)', str(label).strip())
        if not m:
            return None
        try:
            return str(int(m.group(1)))
        except (ValueError, TypeError):
            return m.group(1)

    @staticmethod
    def _disambiguate_transformer_posts(fp, matches):
        """
        When several posts normalize to the same primary bus, pick the pole whose
        physical pole number matches the From Primary bus index (e.g. P0000000009 -> pole 9).
        """
        if not matches:
            return None
        if len(matches) == 1:
            return matches[0]

        fp_upper = str(fp).strip().upper()
        has_dash = '-' in fp_upper
        core_fp = None if has_dash else LinkageService._leading_digits_from_p_label(fp)

        best = None
        best_score = -1
        for p in matches:
            sc = 0
            if p.primary_bus_id and str(p.primary_bus_id).strip().upper() == fp_upper:
                sc += 5
            if p.pole_number and str(p.pole_number).strip().upper() == fp_upper:
                sc += 4
            if core_fp:
                pc = LinkageService._leading_digits_from_p_label(p.pole_number or '')
                if pc == core_fp:
                    sc += 3
                if p.pole_num is not None:
                    try:
                        if str(int(p.pole_num)) == core_fp:
                            sc += 2
                    except (ValueError, TypeError):
                        pass
            if sc > best_score:
                best_score = sc
                best = p
        return best if best is not None else matches[0]

    @staticmethod
    def _transformer_match_fallback_primary(fp, norm_fp, context):
        """BusNode / pole-sequence fallback using only the primary bus string (no DT bus)."""
        bus_node_map = context.bus_node_map
        post_by_id = context.post_by_id
        if norm_fp in bus_node_map:
            pid = str(bus_node_map[norm_fp])
            p = post_by_id.get(pid)
            if p:
                return p

        has_dash = '-' in str(fp)
        m = re.match(r'^P0*([0-9].*)$', str(fp).upper())
        if not m or has_dash:
            return None
        g1 = m.group(1)
        pole_num_map = context.post_by_pole_num
        numeric_match = re.search(r'^(\d+)', g1)
        if numeric_match:
            num_str = str(int(numeric_match.group(1)))
            p = pole_num_map.get(num_str)
            if p:
                return p
        return context.post_by_seq.get(g1)

    @staticmethod
    def _post_looks_lateral(post):
        """Tap / spur poles use '-' in primary bus or pole_number (e.g. P00000001-19-10)."""
        pb = str(getattr(post, 'primary_bus_id', None) or '')
        pn = str(getattr(post, 'pole_number', None) or '')
        return '-' in pb or '-' in pn

    @staticmethod
    def _filter_lateral_consistency(from_primary, posts_list):
        """
        Highway poles (no dash in IDs) must not host lateral transformers (From Primary with '-').
        Lateral transformers only reconcile to lateral posts, and vice versa for strict splits.
        """
        if not posts_list:
            return posts_list
        tx_lat = '-' in str(from_primary)
        out = []
        for p in posts_list:
            p_lat = LinkageService._post_looks_lateral(p)
            if tx_lat == p_lat:
                out.append(p)
        return out

    @staticmethod
    def match_post_for_transformer(transformer, context):
        """
        Map a distribution transformer to the physical post using From Primary Bus ID only.
        Secondary (DT…) IDs are not used for placement — they normalize ambiguously and
        caused DT assets to appear on the wrong pole when another post shared a bad primary key.
        """
        fp = (getattr(transformer, 'from_primary_bus_id', None) or '').strip()
        if not fp:
            return LinkageService.fuzzy_match_asset_to_post(transformer, context=context)

        norm_fp = normalize_id(fp)
        matches = []
        for p in context.posts:
            pb = normalize_id(p.primary_bus_id) if p.primary_bus_id else ''
            pn = normalize_id(p.pole_number) if p.pole_number else ''
            if pb == norm_fp or pn == norm_fp:
                matches.append(p)

        matches = LinkageService._filter_lateral_consistency(fp, matches)

        if not matches:
            return LinkageService._transformer_match_fallback_primary(fp, norm_fp, context)

        return LinkageService._disambiguate_transformer_posts(fp, matches)

    @staticmethod
    def fuzzy_match_transformer_to_post(transformer, posts=None, bus_node_map=None, context=None):
        """Resolve transformer → post using From Primary Bus ID (CSV authority)."""
        if context is None:
            from models import BusNode, Post
            posts = posts or Post.query.all()
            bus_nodes = BusNode.query.all()
            context = LinkageContext(posts=posts, bus_nodes=bus_nodes)
        return LinkageService.match_post_for_transformer(transformer, context)

    @classmethod
    def run_bulk_reconciliation(cls):
        """Clear post transformer flags, re-link from DistributionTransformer rows, commit.

        Returns a dict: transformer_rows, linked_total, linked_mainline (From Bus without '-'),
        linked_lateral (From Bus with '-'), not_linked, posts_with_transformer.
        """
        from models import BusNode, VoltageRegulator, ShuntCapacitor, ShuntInductor, SeriesInductor
        transformers = DistributionTransformer.query.all()
        posts = Post.query.all()
        bus_nodes = BusNode.query.all()
        
        context = LinkageContext(posts=posts, bus_nodes=bus_nodes)
        
        # 0. Reset all existing assignments to prevent "ghost" assets on wrong poles
        for p in posts:
            p.has_transformer = False
            p.kva_rating = None
            p.transformer_bus_id = None

        stats = {
            'transformer_rows': len(transformers),
            'linked_total': 0,
            'linked_mainline': 0,
            'linked_lateral': 0,
            'not_linked': 0,
            'posts_with_transformer': 0,
        }
        # 1. Reconcile Transformers (From Primary Bus only; see match_post_for_transformer)
        for t in transformers:
            p = cls.match_post_for_transformer(t, context=context)
            if p and p.lat and p.lng and p.lat != 0.0 and p.lng != 0.0:
                p.has_transformer = True
                p.kva_rating = t.kva_rating
                p.transformer_bus_id = t.to_secondary_bus_id or t.from_primary_bus_id
                stats['linked_total'] += 1
                fp = str(getattr(t, 'from_primary_bus_id', None) or '')
                if '-' in fp:
                    stats['linked_lateral'] += 1
                else:
                    stats['linked_mainline'] += 1
            else:
                stats['not_linked'] += 1

        stats['posts_with_transformer'] = Post.query.filter_by(has_transformer=True).count()

        db.session.commit()
        return stats
