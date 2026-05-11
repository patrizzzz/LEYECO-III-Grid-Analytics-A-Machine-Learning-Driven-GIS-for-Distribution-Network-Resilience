from sqlalchemy import text
from extensions import db

class TopologyService:
    """
    High-performance network topology tracing using SQL Recursive CTEs.
    Moves graph traversal into the database engine for maximum speed.
    """

    @staticmethod
    def parse_secondary_bus_id(bus_id):
        """
        Parses a secondary bus ID based on the 'First-Last = Pole' convention.
        Example: S16-13-11 -> Physical Pole 16-11 (Skips lateral 13)
        """
        import re
        if not bus_id: return None
        s = str(bus_id).strip().upper()
        parts = s.split('-')
        
        # 1. Extract the Transformer/Feeder part (First Segment)
        first_segment = parts[0].replace('S', '').replace('DT', '').lstrip('0') or '0'
        
        # 2. Extract the Pole part (Last Segment)
        last_segment = parts[-1].replace('S', '').replace('DT', '')
        match = re.match(r'^(\d+)([a-zA-Z0-9]*)$', last_segment)
        if not match: return None
        
        pole_num_str, suffix = match.groups()
        pole_num = pole_num_str.lstrip('0') or '0'
        
        # 3. Construct the 'Combined' physical ID (e.g. 16-11)
        combined_id = f"{first_segment}-{pole_num}"
        if suffix:
            combined_id += suffix
            
        return {
            'transformer_id': first_segment if len(parts) > 1 else None,
            'pole_num_only': int(pole_num),
            'suffix': suffix or '',
            'physical_pole_id': combined_id, # e.g. "16-11"
            'is_lateral': len(parts) > 2 or bool(suffix)
        }

    @staticmethod
    def normalize_secondary_id(bus_id):
        """Standardizes S-type IDs while preserving the correct segments."""
        if not bus_id: return ""
        s = str(bus_id).strip().upper()
        parts = s.split('-')
        
        # Normalize each segment
        norm_parts = []
        for i, p in enumerate(parts):
            clean = p.lstrip('S0') or ('0' if p.isdigit() else p)
            if i == 0 and s.startswith('S'):
                norm_parts.append(f"S{clean}")
            else:
                norm_parts.append(clean)
        
        return "-".join(norm_parts)

    @staticmethod
    def trace_downstream_sql(start_bus_id):
        """
        Performs a directed downstream trace starting from a bus ID.
        Ensures type consistency for PostgreSQL Recursive CTE.
        """
        query = text("""
            WITH RECURSIVE downstream_trace AS (
                -- 1. Initial set: Explicitly cast to character varying to match table columns
                SELECT CAST(:start_id AS varchar) AS current_bus
                
                UNION
                
                -- 2. Recursive step
                SELECT CAST(connected_bus AS varchar)
                FROM (
                    SELECT to_bus_id AS connected_bus, from_bus_id AS parent_bus FROM distribution_line_segment
                    UNION ALL
                    SELECT to_secondary_bus_id AS connected_bus, from_primary_bus_id AS parent_bus FROM distribution_transformer
                    UNION ALL
                    SELECT to_bus_id AS connected_bus, from_bus_id AS parent_bus FROM secondary_line_segment
                    UNION ALL
                    SELECT to_customer_id AS connected_bus, from_bus_id AS parent_bus FROM secondary_service_drop
                    UNION ALL
                    SELECT to_bus AS connected_bus, from_bus AS parent_bus FROM line_connection
                ) connections
                JOIN downstream_trace dt ON CAST(connections.parent_bus AS varchar) = dt.current_bus
            )
            SELECT DISTINCT current_bus FROM downstream_trace;
        """)
        
        try:
            # We strip to ensure no whitespace causes mismatch
            result = db.session.execute(query, {'start_id': str(start_bus_id).strip()})
            return [row[0] for row in result if row[0]]
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def trace_upstream_sql(start_bus_id):
        """
        Performs a reversed trace to find the path back to the substation/transformer.
        """
        query = text("""
            WITH RECURSIVE upstream_trace AS (
                SELECT CAST(:start_id AS varchar) AS current_bus
                
                UNION
                
                SELECT CAST(parent_bus AS varchar)
                FROM (
                    SELECT from_bus_id AS parent_bus, to_bus_id AS target_bus FROM distribution_line_segment
                    UNION ALL
                    SELECT from_primary_bus_id AS parent_bus, to_secondary_bus_id AS target_bus FROM distribution_transformer
                    UNION ALL
                    SELECT from_bus_id AS parent_bus, to_bus_id AS target_bus FROM secondary_line_segment
                    UNION ALL
                    SELECT from_bus_id AS parent_bus, to_customer_id AS target_bus FROM secondary_service_drop
                    UNION ALL
                    SELECT from_bus AS parent_bus, to_bus AS target_bus FROM line_connection
                ) connections
                JOIN upstream_trace ut ON CAST(connections.target_bus AS varchar) = ut.current_bus
            )
            SELECT DISTINCT current_bus FROM upstream_trace;
        """)
        
        try:
            result = db.session.execute(query, {'start_id': str(start_bus_id).strip()})
            return [row[0] for row in result if row[0]]
        except Exception as e:
            db.session.rollback()
            raise e
    @staticmethod
    def find_feeder_head(identifier):
        """
        Tries to find the 'Pole 1' or the root substation node for a given feeder/node.
        Returns (bus_id, lat, lng, feeder_name).
        """
        from models import Post, BusNode
        
        # 1. Resolve identifier to candidate bus IDs
        from services.network_geometry_db import resolve_all_bus_ids
        candidates = resolve_all_bus_ids(identifier)
        if not candidates:
            return None, None, None, None

        # 2. Find the feeder name from these candidates
        feeder_name = None
        # Try Post first
        post = Post.query.filter(Post.pole_number.in_(candidates) | Post.primary_bus_id.in_(candidates)).first()
        if post and post.feeder:
            feeder_name = post.feeder
        else:
            # Try BusNode
            bn = BusNode.query.filter(BusNode.bus_id.in_(candidates)).first()
            if bn and bn.feeder:
                feeder_name = bn.feeder
        
        if not feeder_name:
            # If we can't find a feeder name, we just return the first candidate as the 'head' 
            # (best effort fallback)
            target = post or bn
            if target:
                return candidates[0], target.lat, target.lng, "Unknown Feeder"
            return candidates[0], None, None, "Unknown Feeder"

        # 3. Look for 'Pole 1' of this feeder
        # We check both pole_num == 1 and pole_number matching '*0001' or similar
        head_post = Post.query.filter(
            Post.feeder == feeder_name,
            (Post.pole_num == 1) | (Post.pole_number.like('%0001')) | (Post.pole_number == '1')
        ).first()

        if head_post:
            bus_id = head_post.primary_bus_id or head_post.pole_number
            return bus_id, head_post.lat, head_post.lng, feeder_name

        # 4. Fallback: Perform Upstream Trace to find the true root (no parent)
        # We take the first candidate and trace up
        upstream_buses = TopologyService.trace_upstream_sql(candidates[0])
        if upstream_buses:
            # The 'root' node is usually the one that appears in the upstream trace 
            # but has no further parents in the database.
            # For simplicity, we'll take the 'last' one found in the trace depth.
            # But trace_upstream_sql returns a flat list. 
            # Let's find the one among these that has no parent.
            
            from models import DistributionLineSegment
            root_id = None
            for b_id in upstream_buses:
                parent_exists = db.session.query(DistributionLineSegment).filter_by(to_bus_id=b_id).first()
                if not parent_exists:
                    root_id = b_id
                    break
            
            if not root_id:
                root_id = upstream_buses[-1] # Fallback to last in list

            # Resolve coordinates for this root
            root_bn = BusNode.query.filter_by(bus_id=root_id).first()
            if root_bn:
                return root_id, root_bn.lat, root_bn.lng, feeder_name
            
            root_p = Post.query.filter((Post.primary_bus_id == root_id) | (Post.pole_number == root_id)).first()
            if root_p:
                return root_id, root_p.lat, root_p.lng, feeder_name

        return candidates[0], None, None, feeder_name
