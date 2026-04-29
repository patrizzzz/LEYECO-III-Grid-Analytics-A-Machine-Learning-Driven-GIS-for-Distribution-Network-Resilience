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
import heapq
import json
import math
import re
from sqlalchemy import or_



def resolve_all_bus_ids(identifier):
    """
    Given a starting string (pole number or bus ID), resolves all 
    associated topological identifiers from Post and BusNode tables.
    Handles padding like "120" -> "P0000000120" and vice versa.
    """
    from models import Post, BusNode
    if identifier is None:
        return []
    
    s_id = str(identifier).strip()
    candidate_bus_ids = set()
    
    # 1. Generate normalized versions of the ID for searching
    search_ids = {s_id, s_id.lower()}
    
    # Handle 'P' prefix and padding
    numeric_part = re.sub(r'\D', '', s_id)
    if numeric_part:
        # Strip leading zeros for a core numeric ID
        core_id = numeric_part.lstrip('0') or '0'
        search_ids.add(core_id)
        # Standard P + 10 digits padding
        search_ids.add(f"P{core_id.zfill(10)}")
        # Standard P + 8 digits (some systems)
        search_ids.add(f"P{core_id.zfill(8)}")
    
    # If it starts with P, add the version without P
    if s_id.upper().startswith('P'):
        search_ids.add(s_id[1:])
        search_ids.add(s_id[1:].lstrip('0') or '0')

    # 2. Search Post table using all variants
    posts = Post.query.filter(
        or_(
            Post.primary_bus_id.in_(search_ids),
            Post.pole_number.in_(search_ids),
            Post.transformer_bus_id.in_(search_ids),
            Post.sec_bus_id.in_(search_ids)
        )
    ).all()

    for post in posts:
        if post.primary_bus_id: candidate_bus_ids.add(post.primary_bus_id)
        if post.transformer_bus_id: candidate_bus_ids.add(post.transformer_bus_id)
        if getattr(post, 'sec_bus_id', None): candidate_bus_ids.add(post.sec_bus_id)
        if post.pole_number: candidate_bus_ids.add(post.pole_number)
        
        if post.pole_number:
            b_nodes = BusNode.query.filter((BusNode.pole_id == post.id) | (BusNode.pole_number == post.pole_number)).all()
        else:
            b_nodes = BusNode.query.filter(BusNode.pole_id == post.id).all()
        
        for bn in b_nodes:
            if bn.bus_id: candidate_bus_ids.add(bn.bus_id)

    # 3. Search BusNode directly using all variants
    bn_query = BusNode.query.filter(
        or_(
            BusNode.bus_id.in_(search_ids),
            BusNode.pole_number.in_(search_ids)
        )
    ).all()
    for bn in bn_query:
        if bn.bus_id: candidate_bus_ids.add(bn.bus_id)
        # If this BusNode is linked to a pole, get all other bus IDs for that pole too
        if bn.pole_id:
            other_nodes = BusNode.query.filter_by(pole_id=bn.pole_id).all()
            for obn in other_nodes:
                if obn.bus_id: candidate_bus_ids.add(obn.bus_id)

    if not candidate_bus_ids:
        candidate_bus_ids.add(s_id)
        
    return list(candidate_bus_ids)


def resolve_specific_bus_ids(identifier):
    """
    Restrictive version of resolve_all_bus_ids.
    Generates normalized variants of an ID (padding/unpadding)
    but DOES NOT search the database for other linked IDs (aliases).
    Use this for specific asset lookups where only the direct 
    connection to the provided ID is desired.
    """
    import re
    if identifier is None:
        return []
    
    s_id = str(identifier).strip()
    search_ids = {s_id, s_id.lower(), s_id.upper()}
    
    # Handle padding variants
    numeric_part = re.sub(r'\D', '', s_id)
    if numeric_part:
        core_id = numeric_part.lstrip('0') or '0'
        search_ids.add(core_id)
        search_ids.add(f"P{core_id.zfill(10)}")
        search_ids.add(f"P{core_id.zfill(8)}")
    
    # If it starts with P, add the version without P
    if s_id.upper().startswith('P'):
        search_ids.add(s_id[1:])
        search_ids.add(s_id[1:].lstrip('0') or '0')
        
    return list(search_ids)



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

        path_ll = line.get("path_latlngs")
        if path_ll and len(path_ll) >= 2:
            coords = [[pt[1], pt[0]] for pt in path_ll]
        else:
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
            "route_auto": line.get("route_auto"),
        }
        if length_m is not None:
            props["length_meters"] = round(length_m, 2)
        if line.get("length_meters_source") is not None:
            props["length_meters_source"] = round(float(line["length_meters_source"]), 2)
        features.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": {"type": "LineString", "coordinates": coords},
            }
        )

    return {"type": "FeatureCollection", "features": features}


def _add_edge(
    lines,
    bus_to_coord,
    from_bus,
    to_bus,
    connection_type,
    feeder=None,
    circuit=None,
    phasing=None,
    processed_edges=None,
    used_buses=None,
    display_from_bus=None,
    display_to_bus=None,
    length_meters_source=None,
):
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
        if display_from_bus:
            used_buses.add(display_from_bus.strip())
        if display_to_bus:
            used_buses.add(display_to_bus.strip())

    show_from = (display_from_bus or from_bus).strip()
    show_to = (display_to_bus or to_bus).strip()
    line_row = {
        "lat1": a["lat"],
        "lng1": a["lng"],
        "lat2": b["lat"],
        "lng2": b["lng"],
        "from_pole": a.get("pole_number"),
        "to_pole": b.get("pole_number"),
        "from_bus": show_from,
        "to_bus": show_to,
        "feeder": (feeder or "").strip() or a.get("feeder") or b.get("feeder"),
        "circuit": (circuit or "").strip() or a.get("circuit") or b.get("circuit"),
        "phasing": (phasing or "").strip() or None,
        "connection_type": connection_type,
        "length_meters": round(dist, 2) if dist is not None else None,
    }
    if length_meters_source is not None:
        line_row["length_meters_source"] = float(length_meters_source)
    lines.append(line_row)


def _haversine_from_coords(a, b):
    """Distance in meters between two coord dicts."""
    if not a or not b:
        return None
    return _haversine_meters(a.get("lat"), a.get("lng"), b.get("lat"), b.get("lng"))


def _best_variant_endpoint(bus_to_coord, base_bus, other_bus, expected_length_m):
    """
    For known bad IDs (e.g. P0000000108 vs P0000000108-63), find a better
    variant endpoint that matches expected segment length.
    """
    base = (base_bus or "").strip()
    other = (other_bus or "").strip()
    if not base or not other or expected_length_m is None:
        return base
    if base not in bus_to_coord or other not in bus_to_coord:
        return base

    other_coord = bus_to_coord.get(other)
    base_coord = bus_to_coord.get(base)
    current_dist = _haversine_from_coords(base_coord, other_coord)
    if current_dist is None:
        return base

    # Only heal obviously impossible mappings.
    severe_mismatch = current_dist > max(1000, expected_length_m * 6)
    if not severe_mismatch:
        return base

    prefix = base + "-"
    candidates = [k for k in bus_to_coord.keys() if k.startswith(prefix)]
    if not candidates:
        return base

    best_bus = base
    best_score = abs(current_dist - expected_length_m)
    for cand in candidates:
        cand_dist = _haversine_from_coords(bus_to_coord.get(cand), other_coord)
        if cand_dist is None:
            continue
        score = abs(cand_dist - expected_length_m)
        if score < best_score:
            best_score = score
            best_bus = cand

    # Accept only if this is a strong improvement.
    if best_bus != base:
        best_dist = _haversine_from_coords(bus_to_coord.get(best_bus), other_coord)
        if best_dist is not None and best_dist < current_dist * 0.35:
            return best_bus
    return base


def _build_distribution_adjacency(segments):
    """Undirected graph: bus_id -> neighbor bus_ids from all distribution segments."""
    adj = defaultdict(set)
    for seg in segments:
        u = (seg.from_bus_id or "").strip()
        v = (seg.to_bus_id or "").strip()
        if u and v:
            adj[u].add(v)
            adj[v].add(u)
    return {k: list(v) for k, v in adj.items()}


def _dijkstra_path_buses(adj, bus_to_coord, start, end, skip_edge):
    """
    Shortest path by summed haversine edge weights.
    skip_edge: (a, b) undirected edge to forbid (the segment being rendered).
    Returns ordered list of bus IDs, or None if unreachable.
    """
    if start not in bus_to_coord or end not in bus_to_coord:
        return None
    if start == end:
        return [start]
    skip = tuple(sorted((skip_edge[0].strip(), skip_edge[1].strip()))) if skip_edge else None

    dist = {start: 0.0}
    prev = {}
    pq = [(0.0, start)]

    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, float("inf")) + 1e-9:
            continue
        if u == end:
            break
        for v in adj.get(u, []):
            if skip and tuple(sorted((u, v))) == skip:
                continue
            w = _haversine_from_coords(bus_to_coord.get(u), bus_to_coord.get(v))
            if w is None:
                continue
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))

    if end not in dist:
        return None
    if end != start and end not in prev:
        return None

    path = []
    cur = end
    while True:
        path.append(cur)
        if cur == start:
            break
        p = prev.get(cur)
        if p is None:
            return None
        cur = p
    path.reverse()
    return path


def _path_length_along_buses(path_buses, bus_to_coord):
    if not path_buses or len(path_buses) < 2:
        return None
    total = 0.0
    for i in range(len(path_buses) - 1):
        d = _haversine_from_coords(
            bus_to_coord.get(path_buses[i]),
            bus_to_coord.get(path_buses[i + 1]),
        )
        if d is None:
            return None
        total += d
    return round(total, 2)


def _greedy_walk_toward_end(adj, bus_to_coord, start, end, skip_edge, max_hops=400):
    """
    Walk from start choosing each step's neighbor whose coordinates are closest to `end`
    (never traverses the undirected skip_edge). If `end` is not reached, append `end`
    anyway so the polyline can close with a short final span (visual only when no graph edge).
    """
    if start not in bus_to_coord or end not in bus_to_coord:
        return None
    if start == end:
        return [start]
    skip = tuple(sorted((skip_edge[0].strip(), skip_edge[1].strip()))) if skip_edge else None
    end_c = bus_to_coord.get(end)
    path = [start]
    current = start
    for _ in range(max_hops):
        if current == end:
            return path
        best_nb = None
        best_d = float("inf")
        for nb in adj.get(current, []):
            if skip and tuple(sorted((current, nb))) == skip:
                continue
            c1 = bus_to_coord.get(nb)
            if not c1:
                continue
            d = _haversine_from_coords(c1, end_c)
            if d < best_d:
                best_d = d
                best_nb = nb
        if best_nb is None:
            break
        if len(path) >= 2 and best_nb == path[-2]:
            break
        path.append(best_nb)
        current = best_nb
    if path[-1] != end:
        path.append(end)
    return path if len(path) >= 2 else None


def _append_distribution_segment_line(
    lines,
    bus_to_coord,
    seg,
    adj,
    processed_edges,
    used_buses,
):
    """
    Draw one distribution segment: logical From/To stay the CSV row IDs.
    Geometry may follow an auto-routed path through intermediate buses.
    """
    orig_from = (seg.from_bus_id or "").strip()
    orig_to = (seg.to_bus_id or "").strip()
    if not orig_from or not orig_to:
        return

    edge_key = tuple(sorted([orig_from, orig_to]))
    if edge_key in processed_edges:
        return

    expected_len = seg.length_meters
    a = bus_to_coord.get(orig_from)
    b = bus_to_coord.get(orig_to)
    direct_dist = _haversine_from_coords(a, b)

    path_buses = _dijkstra_path_buses(
        adj, bus_to_coord, orig_from, orig_to, (orig_from, orig_to)
    )
    route_geo = _path_length_along_buses(path_buses, bus_to_coord) if path_buses else None

    use_route = False
    if (
        path_buses
        and len(path_buses) >= 2
        and route_geo is not None
        and direct_dist is not None
    ):
        # Prefer routed path when it is clearly shorter than the bad direct chord,
        # or when it uses intermediate poles (not a single hop).
        if len(path_buses) >= 3:
            use_route = route_geo < direct_dist * 0.98
        elif route_geo < direct_dist * 0.85:
            use_route = True

    # If shortest-path routing cannot connect (e.g. bogus direct edge is the only link),
    # walk along branches toward the target, then close to the logical endpoint bus.
    if not use_route and direct_dist is not None and expected_len is not None:
        mismatch = direct_dist > max(1000.0, float(expected_len) * 6.0)
    else:
        mismatch = False
    if not use_route and mismatch:
        alt = _greedy_walk_toward_end(
            adj, bus_to_coord, orig_from, orig_to, (orig_from, orig_to)
        )
        if alt and len(alt) >= 3:
            rg = _path_length_along_buses(alt, bus_to_coord)
            last_hop = _haversine_from_coords(
                bus_to_coord.get(alt[-2]), bus_to_coord.get(alt[-1])
            ) if len(alt) >= 2 else None
            exp = float(expected_len) if expected_len is not None else 0.0
            # Total path may be longer than the bogus chord; trust branch walk + short final span to `to_bus`.
            if (
                rg is not None
                and last_hop is not None
                and len(alt) >= 4
                and last_hop <= max(350.0, exp * 3.0 if exp else 350.0)
            ):
                path_buses = alt
                route_geo = rg
                use_route = True

    if use_route and path_buses:
        pts = []
        for bid in path_buses:
            c = bus_to_coord.get(bid)
            if not c:
                use_route = False
                break
            pts.append([float(c["lat"]), float(c["lng"])])
        if use_route and len(pts) >= 2:
            processed_edges.add(edge_key)
            for bid in path_buses:
                used_buses.add(bid)
            lat1, lng1 = pts[0][0], pts[0][1]
            lat2, lng2 = pts[-1][0], pts[-1][1]
            lines.append(
                {
                    "lat1": lat1,
                    "lng1": lng1,
                    "lat2": lat2,
                    "lng2": lng2,
                    "path_latlngs": pts,
                    "from_pole": bus_to_coord.get(orig_from, {}).get("pole_number"),
                    "to_pole": bus_to_coord.get(orig_to, {}).get("pole_number"),
                    "from_bus": orig_from,
                    "to_bus": orig_to,
                    "feeder": (a.get("feeder") if a else None) or (b.get("feeder") if b else None),
                    "circuit": None,
                    "phasing": (seg.phasing or "").strip() or None,
                    "connection_type": "Distribution_Line",
                    "length_meters": route_geo,
                    "length_meters_source": float(expected_len) if expected_len is not None else None,
                    "route_auto": True,
                }
            )
            return

    # Fallback: healed endpoints, straight segment (popup still shows orig_from / orig_to)
    from_healed = _best_variant_endpoint(bus_to_coord, orig_from, orig_to, expected_len)
    to_healed = _best_variant_endpoint(bus_to_coord, orig_to, from_healed, expected_len)
    _add_edge(
        lines,
        bus_to_coord,
        from_healed,
        to_healed,
        "Distribution_Line",
        phasing=seg.phasing,
        processed_edges=processed_edges,
        used_buses=used_buses,
        display_from_bus=orig_from,
        display_to_bus=orig_to,
        length_meters_source=float(expected_len) if expected_len is not None else None,
    )


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
                        "feeder": (post.feeder if post and post.feeder else bn.feeder or "").strip() or None,
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

            # 1b. Bridge short-form bus IDs (P0, P16-1) with long-form BusNode feeder data
            #     Short-ID BusNodes have coordinates but no feeder.
            #     Long-ID BusNodes (P00000000, P00000016-1) have feeder data but no coordinates.
            #     This step queries all BusNodes with feeder regardless of coords, normalizes
            #     both IDs to the same format, and copies feeder to the short-ID entries.
            try:
                import re as _re
                def _normalize_bus_id(bus_id):
                    """Convert P16-1 → P00000016-1, P0 → P00000000 etc."""
                    m = _re.match(r'^P(\d+)(-.+)?$', bus_id, _re.IGNORECASE)
                    if m:
                        num = m.group(1).lstrip('0') or '0'
                        suffix = m.group(2) or ''
                        return f"P{int(num):08d}{suffix}"
                    return None

                # Query ALL BusNodes that have feeder (whether or not they have coords)
                feeder_bns = db.session.query(BusNode.bus_id, BusNode.feeder).filter(
                    BusNode.feeder.isnot(None)
                ).all()

                # Build lookup: normalized_id -> feeder
                norm_feeder_lookup = {}
                for bid, feeder in feeder_bns:
                    norm = _normalize_bus_id(bid)
                    if norm and feeder:
                        norm_feeder_lookup[norm] = feeder
                    # Also store the raw ID for direct matches
                    norm_feeder_lookup[bid] = feeder

                # Propagate feeder to all coord-having entries that lack feeder
                for bid in list(bus_to_coord.keys()):
                    if not bus_to_coord[bid].get('feeder'):
                        # Try direct match first
                        feeder = norm_feeder_lookup.get(bid)
                        if not feeder:
                            # Try normalized match
                            norm = _normalize_bus_id(bid)
                            if norm:
                                feeder = norm_feeder_lookup.get(norm)
                        if feeder:
                            bus_to_coord[bid]['feeder'] = feeder
            except Exception as e:
                app.logger.warning("Feeder bridging (short/long bus ID) failed: %s", e)

            # 1c. Topology-based feeder propagation (Healing)
            #     Some segments lack technical feeder data in both Post and BusNode tables.
            #     If they are physically connected to a known feeder path, they should inherit it.
            try:
                from collections import deque
                
                # Build undirected adjacency from LineConnection to find physical neighbors
                # We do this BEFORE the main line building loop to heal the coord lookup.
                from models import LineConnection
                phys_adj = defaultdict(set)
                for conn in db.session.query(LineConnection.from_bus, LineConnection.to_bus).all():
                    fb = (conn.from_bus or "").strip()
                    tb = (conn.to_bus or "").strip()
                    if fb and tb:
                        phys_adj[fb].add(tb)
                        phys_adj[tb].add(fb)
                
                # BFS to propagate feeder from known nodes to unknown neighbors
                # Start with all nodes that already have a feeder
                queue = deque()
                for bid, coord in bus_to_coord.items():
                    if coord.get('feeder'):
                        queue.append(bid)
                
                while queue:
                    current = queue.popleft()
                    current_feeder = bus_to_coord[current]['feeder']
                    
                    for neighbor in phys_adj.get(current, []):
                        if neighbor in bus_to_coord and not bus_to_coord[neighbor].get('feeder'):
                            bus_to_coord[neighbor]['feeder'] = current_feeder
                            queue.append(neighbor)
            except Exception as e:
                app.logger.warning("Topology-based feeder propagation failed: %s", e)

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
                        else:
                            # Propagate feeder/circuit from Post if BusNode was missing them
                            existing = bus_to_coord[b_key]
                            if not existing.get("feeder") and coord.get("feeder"):
                                existing["feeder"] = coord["feeder"]
                            if not existing.get("circuit") and coord.get("circuit"):
                                existing["circuit"] = coord["circuit"]
                
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

            # 0b. Propagate coordinates through the secondary line topology.
            # Transformer secondary buses have coords from step 0, but the
            # downstream secondary bus IDs (S0001-0007-0001, etc.) do not.
            # BFS from every secondary line bus that already has coords,
            # tracking the incoming bearing so linear chains stay straight
            # and only branch points fan out.
            try:
                from models import SecondaryLineSegment as _SLS
                from collections import deque

                # Build undirected adjacency with length metadata
                sec_adj = defaultdict(list)
                for sl in db.session.query(_SLS).all():
                    fb = (sl.from_bus_id or "").strip()
                    tb = (sl.to_bus_id or "").strip()
                    length = sl.length_meters or 50  # default 50m if missing
                    if fb and tb:
                        sec_adj[fb].append((tb, length))
                        sec_adj[tb].append((fb, length))

                # BFS queue: (bus_id, incoming_bearing_deg or None)
                sec_queue = deque()
                for bus_id in sec_adj:
                    if bus_id in bus_to_coord:
                        sec_queue.append((bus_id, None))

                visited = set(b for b, _ in sec_queue)

                while sec_queue:
                    current, incoming_bearing = sec_queue.popleft()
                    cur_coord = bus_to_coord.get(current)
                    if not cur_coord:
                        continue

                    # Collect unvisited neighbours
                    unvisited = [(nb, ln) for nb, ln in sec_adj[current]
                                 if nb not in visited and nb not in bus_to_coord]
                    if not unvisited:
                        continue

                    # Determine base bearing: continue from incoming direction,
                    # or use a default for root nodes (transformer buses).
                    if incoming_bearing is not None:
                        base_bearing = incoming_bearing
                    else:
                        # Root node: use a hash of the bus ID for a stable initial direction
                        base_bearing = (hash(current) % 360)

                    for idx, (neighbor, length_m) in enumerate(unvisited):
                        if neighbor in visited:
                            continue
                        visited.add(neighbor)

                        # Linear chain: 1 unvisited neighbor → continue straight
                        # Branch point: spread children evenly around base bearing
                        if len(unvisited) == 1:
                            bearing_deg = base_bearing
                        else:
                            # Fan out: ±30° spread for branches
                            spread = 60.0  # total arc degrees
                            step = spread / max(len(unvisited) - 1, 1)
                            offset = -spread / 2 + idx * step
                            bearing_deg = base_bearing + offset

                        bearing_rad = math.radians(bearing_deg % 360)

                        # Convert length to approximate lat/lng offset
                        dlat = (length_m * math.cos(bearing_rad)) / 111320.0
                        cos_lat = max(math.cos(math.radians(cur_coord["lat"])), 0.01)
                        dlng = (length_m * math.sin(bearing_rad)) / (111320.0 * cos_lat)

                        new_coord = {
                            "lat": cur_coord["lat"] + dlat,
                            "lng": cur_coord["lng"] + dlng,
                            "feeder": cur_coord.get("feeder"),
                            "circuit": cur_coord.get("circuit"),
                            "pole_number": neighbor,
                        }
                        bus_to_coord[neighbor] = new_coord
                        sec_queue.append((neighbor, bearing_deg))

                        # Also add as a node for map markers
                        key = (new_coord["lat"], new_coord["lng"], neighbor)
                        if key not in seen_node:
                            seen_node.add(key)
                            nodes.append({
                                "pole_number": neighbor,
                                "lat": new_coord["lat"],
                                "lng": new_coord["lng"],
                                "feeder": new_coord.get("feeder"),
                                "feature_type": "secondary_node",
                            })

            except Exception as e:
                app.logger.warning("Secondary line coord propagation failed: %s", e)

            # 1. Distribution line segments (from_bus_id → to_bus_id)
            try:
                from models import DistributionLineSegment
                dist_segments = db.session.query(DistributionLineSegment).all()
                dist_adj = _build_distribution_adjacency(dist_segments)
                for seg in dist_segments:
                    _append_distribution_segment_line(
                        lines,
                        bus_to_coord,
                        seg,
                        dist_adj,
                        processed_edges,
                        used_buses,
                    )
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
                for conn in db.session.query(LineConnection).all():
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

def get_network_geometry_optimized(app):
    """
    High-performance PostGIS-based GeoJSON generation.
    Bypasses Python dict-to-JSON loops by constructing the JSON directly in PostgreSQL.
    """
    with app.app_context():
        try:
            from sqlalchemy import text
            from extensions import db

            # Note: We use jsonb_build_object and ST_AsGeoJSON for speed
            query = text("""
                WITH node_features AS (
                    SELECT 
                        jsonb_build_object(
                            'type', 'Feature',
                            'geometry', ST_AsGeoJSON(geom)::jsonb,
                            'properties', jsonb_build_object(
                                'feature_type', 'node',
                                'pole_number', pole_number,
                                'feeder', feeder,
                                'id', id
                            )
                        ) as feature
                    FROM post
                    WHERE geom IS NOT NULL
                ),
                edge_features AS (
                    -- Combine all line tables for GeoJSON export
                    SELECT 
                        jsonb_build_object(
                            'type', 'Feature',
                            'geometry', ST_AsGeoJSON(geom)::jsonb,
                            'properties', jsonb_build_object(
                                'feature_type', 'edge',
                                'segment_id', segment_id,
                                'connection_type', 'Primary_Line',
                                'from_bus', from_bus_id,
                                'to_bus', to_bus_id
                            )
                        ) as feature
                    FROM distribution_line_segment
                    WHERE geom IS NOT NULL
                ),
                all_features AS (
                    SELECT feature FROM node_features
                    UNION ALL
                    SELECT feature FROM edge_features
                )
                SELECT jsonb_build_object(
                    'type', 'FeatureCollection',
                    'features', jsonb_agg(feature)
                )
                FROM all_features;
            """)
            
            result = db.session.execute(query).scalar()
            return {
                "geojson": result or {"type": "FeatureCollection", "features": []},
                "stats": {"optimized": True}
            }
        except Exception as e:
            app.logger.exception("get_network_geometry_optimized failed: %s", e)
            return {"error": str(e)}

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
    
    # Identify substation bus IDs (Pole 1 explicitly requested by user)
    substation_buses = set()
    try:
        from models import BusNode
        for bn in BusNode.query.filter_by(pole_number='1').all():
            if bn.bus_id: substation_buses.add(bn.bus_id)
    except: pass

    for sid in start_bus_ids:
        if sid and sid in graph:
            visited_set.add(sid)
            queue.append(sid)

    while queue:
        node = queue.pop(0)
        
        # Stop upstream tracing if we hit the designated substation
        if node == '1' or node in substation_buses:
            continue

        for neighbor in graph.get(node, []):
            if neighbor not in visited_set:
                visited_set.add(neighbor)
                queue.append(neighbor)

    return visited_set
