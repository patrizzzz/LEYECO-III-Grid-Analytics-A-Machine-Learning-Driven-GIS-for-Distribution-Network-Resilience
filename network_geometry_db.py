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


def build_primary_to_transformer_edges(posts):
    """
    When Primary Bus ID and Transformer Bus ID both exist on a record,
    draw a connection. Geometry: same pole → same coordinates (stored only).
    """
    edges = []
    for p in posts:
        if not p.get("primary_bus_id") or not p.get("transformer_bus_id"):
            continue
        lat, lng = p["lat"], p["lng"]
        edges.append(
            {
                "lat1": lat,
                "lng1": lng,
                "lat2": lat,
                "lng2": lng,
                "from_pole": p.get("pole_number"),
                "to_pole": p.get("pole_number"),
                "from_bus": p["primary_bus_id"],
                "to_bus": p["transformer_bus_id"],
                "feeder": p.get("feeder"),
                "circuit": p.get("circuit"),
                "connection_type": "Primary_to_Transformer",
            }
        )
    return edges


def build_transformer_to_secondary_edges(posts):
    """
    When Transformer Bus ID and Sec. Bus ID both exist on a record,
    draw a connection. Geometry: same pole → same coordinates (stored only).
    """
    edges = []
    for p in posts:
        if not p.get("transformer_bus_id") or not p.get("sec_bus_id"):
            continue
        lat, lng = p["lat"], p["lng"]
        edges.append(
            {
                "lat1": lat,
                "lng1": lng,
                "lat2": lat,
                "lng2": lng,
                "from_pole": p.get("pole_number"),
                "to_pole": p.get("pole_number"),
                "from_bus": p["transformer_bus_id"],
                "to_bus": p["sec_bus_id"],
                "feeder": p.get("feeder"),
                "circuit": p.get("circuit"),
                "connection_type": "Transformer_to_Secondary",
            }
        )
    return edges


def build_all_edges(session, Post):
    """
    Build all line geometry from the database. Uses only stored coordinates.
    Returns (list of line dicts, list of node dicts).
    """
    posts = get_posts_with_coords(session, Post)
    primary = build_primary_segments(posts)
    p2t = build_primary_to_transformer_edges(posts)
    t2s = build_transformer_to_secondary_edges(posts)
    lines = primary + p2t + t2s

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
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "feature_type": "node",
                    "pole_number": n.get("pole_number"),
                    "post_id": n.get("id"),
                    "feeder": n.get("feeder"),
                    "circuit": n.get("circuit"),
                    "primary_bus_id": n.get("primary_bus_id"),
                    "transformer_bus_id": n.get("transformer_bus_id"),
                    "sec_bus_id": n.get("sec_bus_id"),
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [n["lng"], n["lat"]],
                },
            }
        )

    for i, line in enumerate(lines):
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


def _add_edge(lines, bus_to_coord, from_bus, to_bus, connection_type, feeder=None, circuit=None, phasing=None, processed_edges=None):
    """Append one line to `lines` if both bus IDs resolve to coordinates. Uses bus_to_coord for lookup."""
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

            # Build bus → coordinate lookup from posts so every From/To resolves to (lat, lng).
            # Register primary_bus_id, sec_bus_id, transformer_bus_id, and pole_number so
            # lines like "P0000000100-72M → P0000000100-72Q" connect one coordinates to another.
            bus_to_coord = {}
            nodes = []
            seen_node = set()
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
                        bus_to_coord[str(bus_val).strip()] = coord
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

            # All lines come only from explicit from/to data (no inferred structure)
            lines = []
            processed_edges = set() # Track added edges to prevent duplicates (e.g. LineConnection overwriting DistributionLineSegment)

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
                    _add_edge(lines, bus_to_coord, seg.from_bus_id, seg.to_bus_id, "Distribution_Line", phasing=seg.phasing, processed_edges=processed_edges)
            except Exception as e:
                app.logger.warning("DistributionLineSegment in network geometry: %s", e)

            # 2. Distribution transformers (from_primary_bus_id → to_secondary_bus_id)
            try:
                from models import DistributionTransformer
                for t in db.session.query(DistributionTransformer).all():
                    _add_edge(lines, bus_to_coord, t.from_primary_bus_id, t.to_secondary_bus_id, "Primary_to_Secondary", phasing=t.primary_phasing, processed_edges=processed_edges)
            except Exception as e:
                app.logger.warning("DistributionTransformer in network geometry: %s", e)

            # 3. Secondary line segments (from_bus_id → to_bus_id)
            try:
                from models import SecondaryLineSegment
                for sl in db.session.query(SecondaryLineSegment).all():
                    _add_edge(
                        lines, bus_to_coord, sl.from_bus_id, sl.to_bus_id, "Secondary_Line",
                        feeder=sl.feeder, circuit=sl.circuit, phasing=sl.phasing, processed_edges=processed_edges
                    )
            except Exception as e:
                app.logger.warning("SecondaryLineSegment in network geometry: %s", e)

            # 4. Line connections (from_bus → to_bus)
            try:
                from models import LineConnection
                for conn in db.session.query(LineConnection).all():
                    _add_edge(
                        lines, bus_to_coord, conn.from_bus, conn.to_bus,
                        conn.connection_type or "Line_Connection",
                        feeder=conn.feeder, circuit=conn.circuit, processed_edges=processed_edges
                    )
            except Exception as e:
                app.logger.warning("LineConnection in network geometry: %s", e)

            # Compute length (meters) for each line and total
            total_length_m = 0.0
            for line in lines:
                m = _haversine_meters(
                    line.get("lat1"), line.get("lng1"),
                    line.get("lat2"), line.get("lng2"),
                )
                line["length_meters"] = round(m, 2) if m is not None else None
                if line["length_meters"] is not None:
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
