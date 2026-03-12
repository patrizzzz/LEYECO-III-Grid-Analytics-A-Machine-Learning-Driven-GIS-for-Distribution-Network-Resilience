"""
Generate map-renderable line geometry from the electrical distribution network
stored in the database.

Uses only stored coordinates (Post.lat, Post.lng or LatLongData / X,Y if present).
Never generates or assumes coordinates.

Connectivity rules:
- Primary line segments: same Feeder + Circuit, sort by Pole Number, draw between
  sequential poles.
- Primary → Transformer: when Primary Bus ID and Transformer Bus ID both exist
  on a record, draw a connection (same pole → same coordinates).
- Transformer → Secondary: when Transformer Bus ID and Sec. Bus ID both exist,
  draw a connection.

No cross-feeder or cross-circuit connections.
Output: GeoJSON FeatureCollection and a lines list for map overlay.
"""

from collections import defaultdict
import json
import math
import re


def _haversine_meters(lat1, lng1, lat2, lng2):
    """
    Return great-circle distance between two (lat, lng) points in meters.
    Uses WGS84 Earth radius ~6371000 m.
    """
    try:
        la1, ln1 = float(lat1), float(lng1)
        la2, ln2 = float(lat2), float(lng2)
    except (TypeError, ValueError):
        return None
    R = 6371000  # meters
    phi1, phi2 = math.radians(la1), math.radians(la2)
    dphi = math.radians(la2 - la1)
    dlam = math.radians(ln2 - ln1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _numeric_sort_key(pole_number):
    """Extract numeric part for sorting; fallback to string."""
    if pole_number is None:
        return (0, "")
    s = str(pole_number).strip()
    digits = re.sub(r"\D", "", s)
    try:
        return (int(digits) if digits else 0, s)
    except ValueError:
        return (0, s)


def _valid_coord(lat, lng):
    """Return True if both lat and lng are valid numbers in valid ranges."""
    try:
        la, ln = float(lat), float(lng)
        return -90 <= la <= 90 and -180 <= ln <= 180
    except (TypeError, ValueError):
        return False


def get_posts_with_coords(session, Post):
    """
    Load all posts that have valid coordinates.
    Uses Post.lat, Post.lng. Optionally override from LatLongData by post_id if needed.
    Returns list of dicts: id, pole_number, lat, lng, feeder, circuit,
    primary_bus_id, transformer_bus_id, sec_bus_id.
    """
    rows = (
        session.query(
            Post.id,
            Post.pole_number,
            Post.lat,
            Post.lng,
            Post.feeder,
            Post.circuit,
            Post.primary_bus_id,
            Post.transformer_bus_id,
            Post.sec_bus_id,
        )
        .filter(Post.lat.isnot(None), Post.lng.isnot(None))
        .all()
    )
    out = []
    for r in rows:
        if not _valid_coord(r.lat, r.lng):
            continue
        out.append(
            {
                "id": r.id,
                "pole_number": (r.pole_number or "").strip() or None,
                "lat": float(r.lat),
                "lng": float(r.lng),
                "feeder": (r.feeder or "").strip() or None,
                "circuit": (r.circuit or "").strip() or None,
                "primary_bus_id": (r.primary_bus_id or "").strip() or None,
                "transformer_bus_id": (r.transformer_bus_id or "").strip() or None,
                "sec_bus_id": (r.sec_bus_id or "").strip() or None,
            }
        )
    return out


def build_primary_segments(posts):
    """
    Build primary line segments: same Feeder + Circuit, sort by Pole Number,
    connect sequential poles. No cross-feeder or cross-circuit.
    Returns list of dicts: lat1, lng1, lat2, lng2, from_pole, to_pole,
    feeder, circuit, connection_type='Primary_to_Primary'.
    """
    key = lambda p: (p.get("feeder") or "", p.get("circuit") or "")
    groups = defaultdict(list)
    for p in posts:
        groups[key(p)].append(p)

    segments = []
    for (feeder, circuit), group in groups.items():
        if len(group) < 2:
            continue
        group_sorted = sorted(group, key=lambda x: _numeric_sort_key(x.get("pole_number")))
        for i in range(len(group_sorted) - 1):
            a, b = group_sorted[i], group_sorted[i + 1]
            segments.append(
                {
                    "lat1": a["lat"],
                    "lng1": a["lng"],
                    "lat2": b["lat"],
                    "lng2": b["lng"],
                    "from_pole": a.get("pole_number"),
                    "to_pole": b.get("pole_number"),
                    "from_bus": a.get("primary_bus_id") or a.get("pole_number"),
                    "to_bus": b.get("primary_bus_id") or b.get("pole_number"),
                    "feeder": feeder,
                    "circuit": circuit,
                    "connection_type": "Primary_to_Primary",
                }
            )
    return segments




def build_all_edges(session, Post):
    """
    Build all line geometry from the database. Uses only stored coordinates.
    Returns (list of line dicts, list of node dicts).
    """
    posts = get_posts_with_coords(session, Post)
    lines = build_primary_segments(posts)

    nodes = []
    seen = set()
    for p in posts:
        key = (p["lat"], p["lng"], p.get("pole_number"))
        if key in seen:
            continue
        seen.add(key)
        nodes.append(
            {
                "id": p["id"],
                "pole_number": p.get("pole_number"),
                "lat": p["lat"],
                "lng": p["lng"],
                "feeder": p.get("feeder"),
                "circuit": p.get("circuit"),
                "primary_bus_id": p.get("primary_bus_id"),
                "transformer_bus_id": p.get("transformer_bus_id"),
                "sec_bus_id": p.get("sec_bus_id"),
            }
        )
    return lines, nodes


def lines_to_geojson(lines, nodes):
    """
    Build a GeoJSON FeatureCollection with:
    - Point features for each node (pole/bus).
    - LineString features for each edge (using only stored coordinates).
    """
    features = []

    for n in nodes:
        props = {
            "feature_type": n.get("feature_type") or "node",
            "pole_number": n.get("pole_number"),
            "customer_identifier": n.get("customer_identifier"),
            "post_id": n.get("id"),
            "feeder": n.get("feeder"),
            "circuit": n.get("circuit"),
            "primary_bus_id": n.get("primary_bus_id"),
            "transformer_bus_id": n.get("transformer_bus_id"),
            "sec_bus_id": n.get("sec_bus_id"),
        }
        features.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": {
                    "type": "Point",
                    "coordinates": [n["lng"], n["lat"]],
                },
            }
        )

    for i, line in enumerate(lines):
        # Double check: completely block service drops from reaching the map
        if line.get("connection_type") == "Secondary_to_Customer":
            continue

        # GeoJSON LineString: [lng, lat], [lng, lat]
        coords = [[line["lng1"], line["lat1"]], [line["lng2"], line["lat2"]]]
        length_m = line.get("length_meters")
        props = {
            "feature_type": "edge",
            "connection_type": line.get("connection_type"),
            "from_bus": line.get("from_bus"),
            "to_bus": line.get("to_bus"),
            "from_pole": line.get("from_pole"),
            "to_pole": line.get("to_pole"),
            "feeder": line.get("feeder"),
            "circuit": line.get("circuit"),
            "phasing": line.get("phasing"),
        }
        if length_m is not None:
            props["length_meters"] = round(length_m, 2)
        features.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": {"type": "LineString", "coordinates": coords},
            }
        )

    return {"type": "FeatureCollection", "features": features}


def _add_edge(lines, bus_to_coord, from_bus, to_bus, connection_type, feeder=None, circuit=None, phasing=None, processed_edges=None, used_buses=None):
    """
    Append one line to `lines` if both bus IDs resolve to coordinates. 
    Uses bus_to_coord for lookup.
    Includes a safety filter to prevent "stretched" lines > 1km (secondary) or 10km (primary).
    """
    from_bus = (from_bus or "").strip()
    to_bus = (to_bus or "").strip()
    if not from_bus or not to_bus:
        return

    # Deduplication check
    if processed_edges is not None:
        # Sort bus IDs to treat A->B and B->A as the same connection
        edge_key = tuple(sorted([from_bus, to_bus]))
        if edge_key in processed_edges:
            return # Skip duplicate
        processed_edges.add(edge_key)

    a = bus_to_coord.get(from_bus)
    b = bus_to_coord.get(to_bus)
    if not a or not b:
        return

    # Disable Secondary_to_Customer lines entirely for now because customers lack valid coordinates
    if connection_type == "Secondary_to_Customer":
        return

    # Length filter
    dist = _haversine_meters(a["lat"], a["lng"], b["lat"], b["lng"])
    if dist is not None:
        # Stricter for secondary lines, more lenient for primary
        max_dist = 1000 # 1km for secondary
        if connection_type in ("Primary_to_Primary", "Distribution_Line", "Primary_Line", "Primary_to_Transformer"):
            max_dist = 10000 # 10km for primary
        
        if dist > max_dist:
            # Skip "stretching" lines that occur due to bus ID reuse or bad GPS
            return

    # Success: Add to lines and mark buses as used
    if used_buses is not None:
        used_buses.add(from_bus)
        used_buses.add(to_bus)

    lines.append({
        "lat1": a["lat"],
        "lng1": a["lng"],
        "lat2": b["lat"],
        "lng2": b["lng"],
        "from_pole": a.get("pole_number"),
        "to_pole": b.get("pole_number"),
        "from_bus": from_bus,
        "to_bus": to_bus,
        "feeder": (feeder or "").strip() or a.get("feeder") or b.get("feeder"),
        "circuit": (circuit or "").strip() or a.get("circuit") or b.get("circuit"),
        "phasing": (phasing or "").strip() or None,
        "connection_type": connection_type,
        "length_meters": round(dist, 2) if dist is not None else None
    })


def get_network_geometry(app):
    """
    Build network line geometry only from explicit from/to data in the database.
    No inferred structure (no feeder/circuit ordering or post-based segments).

    Lines are drawn only from:
    - DistributionLineSegment (from_bus_id → to_bus_id)
    - DistributionTransformer (from_primary_bus_id → to_secondary_bus_id)
    - SecondaryLineSegment (from_bus_id → to_bus_id)
    - LineConnection (from_bus → to_bus)

    Bus IDs are resolved to coordinates using posts. Each post can provide coordinates for:
    - primary_bus_id, sec_bus_id, transformer_bus_id, and pole_number.
    So From/To like P0000000100-72M and P0000000100-72Q resolve when they match any of those
    on a post with valid lat/lng, and the line is drawn from one coordinates to the other.
    Returns dict with: geojson, lines, nodes, stats, optional error.
    """
    empty_result = {
        "geojson": {"type": "FeatureCollection", "features": []},
        "lines": [],
        "nodes": [],
        "stats": {"nodes": 0, "edges": 0, "total_length_meters": 0, "by_type": {}},
    }
    with app.app_context():
        try:
            from models import Post
            from extensions import db

            # Build bus → coordinate lookup from BusNode and Post.
            # BusNode is the authoritative source for coordinates in the bus-first architecture.
            bus_to_coord = {}
            nodes = []
            seen_node = set()

            # 1. Load from BusNode first (authoritative electrical location)
            try:
                from models import BusNode, Post
                # We join BusNode with Post to guarantee we get the latest physical coordinates
                # even if the cached lat/lng on BusNode isn't synced yet.
                query = db.session.query(BusNode, Post).outerjoin(Post, Post.pole_number == BusNode.pole_number)
                for bn, post in query.all():
                    # Prioritize live post coordinates over cached bus coordinates
                    lat = post.lat if post and _valid_coord(post.lat, post.lng) else bn.lat
                    lng = post.lng if post and _valid_coord(post.lat, post.lng) else bn.lng
                    
                    if getattr(bn, 'pole_number', None):
                        pole_no = bn.pole_number
                    else:
                         pole_no = bn.bus_id
                         
                    if not _valid_coord(lat, lng):
                        continue
                        
                    coord = {
                        "lat": float(lat),
                        "lng": float(lng),
                        "feeder": (bn.feeder or "").strip() or None,
                        "circuit": None, # BusNode doesn't have circuit yet
                        "pole_number": pole_no,
                    }
                    bus_to_coord[bn.bus_id.strip()] = coord
                    key = (coord["lat"], coord["lng"], coord["pole_number"])
                    if key not in seen_node:
                        seen_node.add(key)
                        nodes.append({
                            "bus_node_id": bn.id,
                            "pole_number": pole_no,
                            "lat": coord["lat"],
                            "lng": coord["lng"],
                            "feeder": coord["feeder"],
                            "primary_bus_id": bn.bus_id,
                            "feature_type": "node"
                        })
            except Exception as e:
                app.logger.warning("Loading BusNode coords failed: %s", e)

            # 2. Complement with Post data (for secondary buses and legacy records)
            posts = db.session.query(Post).all()
            for p in posts:
                if not _valid_coord(p.lat, p.lng):
                    continue
                coord = {
                    "lat": float(p.lat),
                    "lng": float(p.lng),
                    "feeder": (p.feeder or "").strip() or None,
                    "circuit": (p.circuit or "").strip() or None,
                    "pole_number": (p.pole_number or "").strip() if p.pole_number else None,
                }
                for bus_attr in ("primary_bus_id", "sec_bus_id", "transformer_bus_id", "pole_number"):
                    bus_val = getattr(p, bus_attr, None)
                    if bus_val and str(bus_val).strip():
                        # Don't overwrite BusNode entries if they exist
                        b_key = str(bus_val).strip()
                        if b_key not in bus_to_coord:
                            bus_to_coord[b_key] = coord
                
                key = (coord["lat"], coord["lng"], coord.get("pole_number"))
                if key not in seen_node:
                    seen_node.add(key)
                    nodes.append({
                        "id": p.id,
                        "pole_number": coord.get("pole_number"),
                        "lat": coord["lat"],
                        "lng": coord["lng"],
                        "feeder": coord.get("feeder"),
                        "circuit": coord.get("circuit"),
                        "primary_bus_id": (p.primary_bus_id or "").strip() or None,
                        "transformer_bus_id": (getattr(p, "transformer_bus_id", None) or "").strip() or None,
                        "sec_bus_id": (getattr(p, "sec_bus_id", None) or "").strip() or None,
                    })

            # 3. Complement with Customer coordinates (for Service Drops)
            try:
                from models import Customer
                customers = db.session.query(Customer).filter(Customer.lat.isnot(None), Customer.lng.isnot(None)).all()
                for cust in customers:
                    if not _valid_coord(cust.lat, cust.lng):
                        continue
                    coord = {
                        "lat": float(cust.lat),
                        "lng": float(cust.lng),
                        "customer_name": cust.name,
                    }
                    # Map both customer_id if possible, prioritizing customer_id as the 'bus ID'
                    if cust.customer_id:
                        bus_to_coord[str(cust.customer_id).strip()] = coord
                    
                    # Also collect as nodes for map markers if desired
                    key = (coord["lat"], coord["lng"], f"CUST:{cust.customer_id}")
                    if key not in seen_node:
                        seen_node.add(key)
                        nodes.append({
                            "customer_id": cust.id,
                            "customer_identifier": cust.customer_id,
                            "lat": coord["lat"],
                            "lng": coord["lng"],
                            "feature_type": "customer",
                        })
            except Exception as e:
                app.logger.warning("Loading Customer coords failed: %s", e)

            # All lines come only from explicit from/to data (no inferred structure)
            lines = []
            processed_edges = set() # Track added edges to prevent duplicates (e.g. LineConnection overwriting DistributionLineSegment)
            used_buses = set()      # Track which bus IDs are actually used by lines to ensure they have markers

            # 0. Augment bus_to_coord with transformer secondary buses that might not be on the post record directly
            # If a transformer is at PrimaryBus X (Which has coords), then SecondaryBus Y is typically at the same location.
            try:
                from models import DistributionTransformer
                transformers = db.session.query(DistributionTransformer).all()
                for t in transformers:
                    prim_id = (t.from_primary_bus_id or "").strip()
                    sec_id = (t.to_secondary_bus_id or "").strip()
                    
                    if prim_id and sec_id and prim_id in bus_to_coord and sec_id not in bus_to_coord:
                        # Inherit coordinates from primary side
                        bus_to_coord[sec_id] = bus_to_coord[prim_id].copy()
                        # Optimization: Add a virtual node? Or just let it be a coordinate for lines.
                        
            except Exception as e:
                app.logger.warning("Augmenting transformer coords failed: %s", e)

            # 1. Distribution line segments (from_bus_id → to_bus_id)
            try:
                from models import DistributionLineSegment
                for seg in db.session.query(DistributionLineSegment).all():
                    _add_edge(lines, bus_to_coord, seg.from_bus_id, seg.to_bus_id, "Distribution_Line", phasing=seg.phasing, processed_edges=processed_edges, used_buses=used_buses)
            except Exception as e:
                app.logger.warning("DistributionLineSegment in network geometry: %s", e)


            # 3. Secondary line segments (from_bus_id → to_bus_id)
            try:
                from models import SecondaryLineSegment
                for sl in db.session.query(SecondaryLineSegment).all():
                    _add_edge(
                        lines, bus_to_coord, sl.from_bus_id, sl.to_bus_id, "Secondary_Line",
                        feeder=sl.feeder, circuit=sl.circuit, phasing=sl.phasing, processed_edges=processed_edges, used_buses=used_buses
                    )
            except Exception as e:
                app.logger.warning("SecondaryLineSegment in network geometry: %s", e)

            # 4. Secondary Service Drops (from_bus_id → to_customer_id)
            try:
                from models import SecondaryServiceDrop
                for sd in db.session.query(SecondaryServiceDrop).all():
                    _add_edge(
                        lines, bus_to_coord, sd.from_bus_id, sd.to_customer_id, "Secondary_to_Customer",
                        phasing=sd.phasing, processed_edges=processed_edges, used_buses=used_buses
                    )
            except Exception as e:
                app.logger.warning("SecondaryServiceDrop in network geometry: %s", e)

            # 5. Line connections (from_bus → to_bus)
            try:
                from models import LineConnection
                for conn in db.session.query(LineConnection).filter(
                    LineConnection.connection_type.notin_(['Primary_to_Transformer', 'Transformer_to_Secondary'])
                ).all():
                    _add_edge(
                        lines, bus_to_coord, conn.from_bus, conn.to_bus,
                        conn.connection_type or "Line_Connection",
                        feeder=conn.feeder, circuit=conn.circuit, phasing=getattr(conn, 'phasing', None),
                        processed_edges=processed_edges, used_buses=used_buses
                    )
            except Exception as e:
                app.logger.warning("LineConnection in network geometry: %s", e)

            # Final Node Pass: Ensure all used bus IDs have markers, even virtual ones
            for bus_id in used_buses:
                coord = bus_to_coord.get(bus_id)
                if not coord:
                    continue
                
                # Use normalized key for seen_node check
                key = (coord["lat"], coord["lng"], bus_id)
                if key not in seen_node:
                    seen_node.add(key)
                    node_data = {
                        "pole_number": bus_id,
                        "lat": coord["lat"],
                        "lng": coord["lng"],
                        "feeder": coord.get("feeder"),
                        "feature_type": "virtual_node"
                    }
                    # If it's a customer, label it so
                    if bus_id.startswith("CUST:") or "customer_name" in coord:
                         node_data["feature_type"] = "customer"
                    
                    nodes.append(node_data)

            # Stats and total length calculation
            total_length_m = 0.0
            for line in lines:
                if line.get("length_meters") is not None:
                    total_length_m += line["length_meters"]

            geojson = lines_to_geojson(lines, nodes)

            by_type = defaultdict(int)
            for line in lines:
                by_type[line.get("connection_type", "unknown")] += 1

            return {
                "geojson": geojson,
                "lines": lines,
                "nodes": nodes,
                "stats": {
                    "nodes": len(nodes),
                    "edges": len(lines),
                    "total_length_meters": round(total_length_m, 2),
                    "by_type": dict(by_type),
                },
            }
        except Exception as e:
            app.logger.exception("get_network_geometry failed: %s", e)
            empty_result["error"] = str(e)
            return empty_result

def build_topology_graph(app):
    """
    Builds an UNDIRECTED adjacency list graph of the electrical network.
    Used by general feeder tracing (sidebar, etc.).
    Returns: dict mapping bus_id -> list of connected bus_ids
    """
    from collections import defaultdict
    graph = defaultdict(set)
    with app.app_context():
        try:
            from models import DistributionLineSegment, SecondaryLineSegment, SecondaryServiceDrop, LineConnection
            from extensions import db

            for seg in db.session.query(DistributionLineSegment).all():
                from_b, to_b = (seg.from_bus_id or "").strip(), (seg.to_bus_id or "").strip()
                if from_b and to_b:
                    graph[from_b].add(to_b)
                    graph[to_b].add(from_b)

            for sl in db.session.query(SecondaryLineSegment).all():
                from_b, to_b = (sl.from_bus_id or "").strip(), (sl.to_bus_id or "").strip()
                if from_b and to_b:
                    graph[from_b].add(to_b)
                    graph[to_b].add(from_b)

            for sd in db.session.query(SecondaryServiceDrop).all():
                from_b, to_b = (sd.from_bus_id or "").strip(), str(sd.to_customer_id or "").strip()
                if from_b and to_b:
                    graph[from_b].add(to_b)
                    graph[to_b].add(from_b)

            from models import DistributionTransformer
            for tx in db.session.query(DistributionTransformer).all():
                from_b, to_b = (tx.from_primary_bus_id or "").strip(), (tx.to_secondary_bus_id or "").strip()
                if from_b and to_b:
                    graph[from_b].add(to_b)
                    graph[to_b].add(from_b)

            for conn in db.session.query(LineConnection).filter(
                LineConnection.connection_type.notin_(['Primary_to_Transformer', 'Transformer_to_Secondary'])
            ).all():
                from_b, to_b = (conn.from_bus or "").strip(), (conn.to_bus or "").strip()
                if from_b and to_b:
                    graph[from_b].add(to_b)
                    graph[to_b].add(from_b)

            # Suffix-mismatch bridge for undirected graph
            all_sec_lines = db.session.query(SecondaryLineSegment).all()
            sec_line_from_buses = {(sl.from_bus_id or "").strip() for sl in all_sec_lines}
            for tx in db.session.query(DistributionTransformer).all():
                sec_b = (tx.to_secondary_bus_id or "").strip()
                if sec_b:
                    base_b = sec_b.rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
                    if base_b != sec_b and base_b in sec_line_from_buses:
                        graph[sec_b].add(base_b)
                        graph[base_b].add(sec_b)

            return {k: list(v) for k, v in graph.items()}
        except Exception as e:
            app.logger.exception("build_topology_graph failed: %s", e)
            return {}


def build_reversed_topology_graph(app):
    """
    Builds a REVERSED DIRECTED adjacency list graph of the electrical network.
    Models power flow in reverse: Customers → Service Drops → Secondary Lines →
    Transformers → Primary Lines → Substation.
    
    Returns: dict mapping bus_id -> list of upstream bus_ids
    """
    from collections import defaultdict
    graph = defaultdict(set)
    with app.app_context():
        try:
            from models import DistributionLineSegment, SecondaryLineSegment, \
                               SecondaryServiceDrop, LineConnection, DistributionTransformer
            from extensions import db

            # Reversed primary distribution lines (to→from)
            for seg in db.session.query(DistributionLineSegment).all():
                from_b = (seg.from_bus_id or "").strip()
                to_b   = (seg.to_bus_id or "").strip()
                if from_b and to_b:
                    graph[to_b].add(from_b)

            # Reversed transformer bridge: secondary side → primary side
            for tx in db.session.query(DistributionTransformer).all():
                from_b = (tx.from_primary_bus_id or "").strip()
                to_b   = (tx.to_secondary_bus_id or "").strip()
                if from_b and to_b:
                    graph[to_b].add(from_b)

            # Reversed suffix-mismatch bridge
            all_sec_lines = db.session.query(SecondaryLineSegment).all()
            sec_line_from_buses = {(sl.from_bus_id or "").strip() for sl in all_sec_lines}
            for tx in db.session.query(DistributionTransformer).all():
                sec_b = (tx.to_secondary_bus_id or "").strip()
                if sec_b:
                    base_b = sec_b.rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
                    if base_b != sec_b and base_b in sec_line_from_buses:
                        graph[base_b].add(sec_b)

            # Reversed secondary lines (to→from)
            for sl in db.session.query(SecondaryLineSegment).all():
                from_b = (sl.from_bus_id or "").strip()
                to_b   = (sl.to_bus_id or "").strip()
                if from_b and to_b:
                    graph[to_b].add(from_b)

            # Reversed service drops: customer → bus
            for sd in db.session.query(SecondaryServiceDrop).all():
                from_b = (sd.from_bus_id or "").strip()
                to_b   = str(sd.to_customer_id or "").strip()
                if from_b and to_b:
                    graph[to_b].add(from_b)

            # Reversed line connections (to→from)
            for conn in db.session.query(LineConnection).filter(
                LineConnection.connection_type.notin_(['Primary_to_Transformer', 'Transformer_to_Secondary'])
            ).all():
                from_b = (conn.from_bus or "").strip()
                to_b   = (conn.to_bus or "").strip()
                if from_b and to_b:
                    graph[to_b].add(from_b)

            return {k: list(v) for k, v in graph.items()}
        except Exception as e:
            app.logger.exception("build_reversed_topology_graph failed: %s", e)
            return {}


def build_directed_topology_graph(app):
    """
    Builds a DIRECTED adjacency list graph of the electrical network.
    Models power flow direction: Substation → Primary Lines → Transformers →
    Secondary Lines → Service Drops → Customers.

    Only adds edges in the from_bus → to_bus direction (not the reverse).
    Used by outage simulation to accurately identify downstream-only impact.
    Returns: dict mapping bus_id -> list of downstream bus_ids
    """
    from collections import defaultdict
    graph = defaultdict(set)
    with app.app_context():
        try:
            from models import DistributionLineSegment, SecondaryLineSegment, \
                               SecondaryServiceDrop, LineConnection, DistributionTransformer
            from extensions import db

            # Primary distribution lines: directed from→to (power flows downstream)
            for seg in db.session.query(DistributionLineSegment).all():
                from_b = (seg.from_bus_id or "").strip()
                to_b   = (seg.to_bus_id or "").strip()
                if from_b and to_b:
                    graph[from_b].add(to_b)   # one-way: power flows →

            # Transformer bridge: primary side → secondary side
            for tx in db.session.query(DistributionTransformer).all():
                from_b = (tx.from_primary_bus_id or "").strip()
                to_b   = (tx.to_secondary_bus_id or "").strip()
                if from_b and to_b:
                    graph[from_b].add(to_b)   # one-way: primary → secondary

            # Secondary lines: directed from→to
            all_sec_lines = db.session.query(SecondaryLineSegment).all()
            sec_line_from_buses = {(sl.from_bus_id or "").strip() for sl in all_sec_lines}

            for sl in all_sec_lines:
                from_b = (sl.from_bus_id or "").strip()
                to_b   = (sl.to_bus_id or "").strip()
                if from_b and to_b:
                    graph[from_b].add(to_b)   # one-way

            # Suffix-mismatch bridge: some transformers store secondary bus as
            # "DT0000000108-24A" but secondary lines use "DT0000000108-24" (no suffix).
            # Add a bridge edge so BFS can continue downstream.
            for tx in db.session.query(DistributionTransformer).all():
                sec_b = (tx.to_secondary_bus_id or "").strip()
                if not sec_b:
                    continue
                # Strip trailing uppercase letters to get base ID
                base_b = sec_b.rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
                if base_b != sec_b and base_b in sec_line_from_buses:
                    graph[sec_b].add(base_b)  # bridge: DT...-24A → DT...-24

            # Service drops: bus → customer (terminal nodes)
            for sd in db.session.query(SecondaryServiceDrop).all():
                from_b = (sd.from_bus_id or "").strip()
                to_b   = str(sd.to_customer_id or "").strip()
                if from_b and to_b:
                    graph[from_b].add(to_b)   # one-way: bus → customer

            # Line connections (exclude transformer connections already handled)
            for conn in db.session.query(LineConnection).filter(
                LineConnection.connection_type.notin_(['Primary_to_Transformer', 'Transformer_to_Secondary'])
            ).all():
                from_b = (conn.from_bus or "").strip()
                to_b   = (conn.to_bus or "").strip()
                if from_b and to_b:
                    graph[from_b].add(to_b)   # one-way

            return {k: list(v) for k, v in graph.items()}
        except Exception as e:
            app.logger.exception("build_directed_topology_graph failed: %s", e)
            return {}


def trace_feeder_bfs(app, start_bus_id):
    """
    Performs standard Breadth First Search (BFS) to compute feeder topology.
    Returns a list of visited bus_ids in BFS order.
    """
    graph = build_topology_graph(app)
    if not start_bus_id or start_bus_id not in graph:
        return []

    visited = []
    queue = [start_bus_id]
    visited_set = {start_bus_id}

    while queue:
        node = queue.pop(0) # dequeue
        visited.append(node)

        neighbors = graph.get(node, [])
        for n in neighbors:
            if n not in visited_set:
                visited_set.add(n)
                queue.append(n)

    return visited


def trace_downstream_bfs(app, start_bus_ids):
    """
    Performs DIRECTED BFS from a given set of buses, following only downstream edges.
    Used for outage simulation: returns all bus/customer IDs that would lose
    power if the starting points are disconnected.
    Returns a set of visited downstream bus_ids.
    """
    graph = build_directed_topology_graph(app)
    if not start_bus_ids:
        return set()

    # Normalize single starting ID to a list
    if isinstance(start_bus_ids, str):
        start_bus_ids = [start_bus_ids]

    visited_set = set()
    queue = []

    for sid in start_bus_ids:
        if sid and sid in graph:
            visited_set.add(sid)
            queue.append(sid)

    while queue:
        node = queue.pop(0)
        for neighbor in graph.get(node, []):
            if neighbor not in visited_set:
                visited_set.add(neighbor)
                queue.append(neighbor)

    return visited_set


def trace_upstream_bfs(app, start_bus_ids):
    """
    Performs REVERSED DIRECTED BFS from a given set of buses, following only upstream edges.
    Returns a set of visited upstream bus_ids.
    """
    graph = build_reversed_topology_graph(app)
    if not start_bus_ids:
        return set()

    if isinstance(start_bus_ids, str):
        start_bus_ids = [start_bus_ids]

    visited_set = set()
    queue = []

    for sid in start_bus_ids:
        if sid and sid in graph:
            visited_set.add(sid)
            queue.append(sid)

    while queue:
        node = queue.pop(0)
        for neighbor in graph.get(node, []):
            if neighbor not in visited_set:
                visited_set.add(neighbor)
                queue.append(neighbor)

    return visited_set
