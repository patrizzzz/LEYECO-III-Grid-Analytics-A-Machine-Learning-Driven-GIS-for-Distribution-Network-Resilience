from flask import Blueprint, jsonify, request, g, current_app, Response
import io, csv, math, requests, traceback, json
from pathlib import Path
from extensions import db
from sqlalchemy import func
from models import Post, DistributionLineSegment, SecondaryLineSegment, DistributionTransformer, Customer, EnergyConsumption, SecondaryServiceDrop
from services.analysis_services import get_grid_health_analytics, calculate_transformer_load_stress, calculate_outage_impact, find_customer_post_location
from services.network_geometry_db import get_network_geometry

analysis_api_bp = Blueprint('analysis_api', __name__)


def _load_barangay_boundaries_geojson():
    """
    Load municipality/barangay boundaries used by map UI.
    Returns parsed GeoJSON dict or None if file is unavailable.
    """
    try:
        geojson_path = Path(current_app.root_path) / 'static' / 'data' / 'barangay-boundaries.json'
        if not geojson_path.exists():
            return None
        with geojson_path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _point_in_ring(lng, lat, ring):
    """Ray-casting point-in-polygon test for a single linear ring."""
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        intersects = ((yi > lat) != (yj > lat)) and (
            lng < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _point_in_polygon_coords(lng, lat, polygon_coords):
    """
    polygon_coords: GeoJSON Polygon coordinates [outerRing, hole1, ...]
    """
    if not polygon_coords:
        return False
    # Must be inside outer ring and outside holes.
    if not _point_in_ring(lng, lat, polygon_coords[0]):
        return False
    for hole in polygon_coords[1:]:
        if _point_in_ring(lng, lat, hole):
            return False
    return True


def _point_in_feature_geometry(lng, lat, geometry):
    if not geometry:
        return False
    gtype = geometry.get('type')
    coords = geometry.get('coordinates')
    if gtype == 'Polygon':
        return _point_in_polygon_coords(lng, lat, coords)
    if gtype == 'MultiPolygon':
        return any(_point_in_polygon_coords(lng, lat, poly) for poly in (coords or []))
    return False


def _get_municipality_geometries(geojson_data):
    """
    Groups features by municipality name (NAME_2 or name), returns:
    { municipality_name: [geometry1, geometry2, ...] }
    """
    muni_map = {}
    if not geojson_data:
        return muni_map
    for feat in (geojson_data.get('features') or []):
        props = feat.get('properties') or {}
        muni = (props.get('NAME_2') or props.get('name') or '').strip()
        geom = feat.get('geometry')
        if not muni or not geom:
            continue
        muni_map.setdefault(muni, []).append(geom)
    return muni_map

@analysis_api_bp.route('/network-geometry', methods=['GET'])
def api_network_geometry():
    try:
        data = get_network_geometry(current_app)
        try:
            health = get_grid_health_analytics()
            health_map = {h['transformer_id']: h for h in health.get('details', [])}
            for feat in data['geojson']['features']:
                props = feat['properties']
                tid = props.get('transformer_bus_id') or props.get('pole_number')
                if tid and tid in health_map:
                    h_info = health_map[tid]
                    props.update({'risk_level': h_info['risk_level'], 'risk_score': h_info['risk_score'], 'load_status': h_info['load_status'], 'health_index': h_info['health_index']})
            data['grid_health_summary'] = health.get('summary', {})
        except Exception as e:
            current_app.logger.warning(f"Health enrichment failed: {e}")
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e), 'lines': []}), 500

@analysis_api_bp.route('/path', methods=['GET'])
def api_shortest_path():
    try:
        customer_id = (request.args.get('customer_id') or '').strip()
        try:
            user_lat, user_lng = float(request.args.get('user_lat')), float(request.args.get('user_lng'))
        except: return jsonify({'error': 'Missing or invalid user_lat / user_lng'}), 400
        if not customer_id: return jsonify({'error': 'customer_id is required'}), 400
        cust = Customer.query.filter_by(customer_id=customer_id).first()
        if not cust: return jsonify({'found': False, 'error': f'Customer "{customer_id}" not found.'}), 404
        dest_info = find_customer_post_location(customer_id)
        if not dest_info: return jsonify({'found': False, 'customer_id': customer_id, 'error': 'Not linked to any electrical post.'}), 200
        osm_url = f"https://routing.openstreetmap.de/routed-car/route/v1/driving/{user_lng},{user_lat};{dest_info['lng']},{dest_info['lat']}?overview=full&geometries=geojson"
        try: response = requests.get(osm_url, timeout=5)
        except: return jsonify({'found': False, 'error': 'Road routing service failed.'}), 200
        if response.status_code != 200: return jsonify({'found': False, 'error': 'Routing service unavailable.'}), 200
        res_data = response.json()
        if not res_data.get('routes'): return jsonify({'found': False, 'error': 'No road path found.'}), 200
        route = res_data['routes'][0]
        return jsonify({'found': True, 'customer_id': customer_id, 'customer_name': getattr(cust, 'name', 'Unknown'), 'user_location': {'lat': user_lat, 'lng': user_lng}, 'destination_post': dest_info, 'path': [{'lat': c[1], 'lng': c[0]} for c in route['geometry']['coordinates']], 'total_distance_m': round(route['distance'], 1), 'duration_sec': round(route['duration'], 0)})
    except Exception as e:
        return jsonify({'found': False, 'error': str(e)}), 500

@analysis_api_bp.route('/export/master.csv', methods=['GET'])
def export_master_csv():
    from collections import defaultdict
    posts = Post.query.order_by(Post.id).all(); pole_numbers = sorted(set(p.pole_number for p in posts if p.pole_number), key=len, reverse=True)
    dist_by_from = defaultdict(list); tx_by_pole = defaultdict(list); sec_by_tx_sec_bus = defaultdict(list); drops_by_bus = defaultdict(list)
    for seg in DistributionLineSegment.query.all(): dist_by_from[seg.from_bus_id].append(seg)
    for t in DistributionTransformer.query.all():
        bus = t.from_primary_bus_id or ''
        for pn in pole_numbers:
            if bus.startswith(pn): tx_by_pole[pn].append(t); break
    for sl in SecondaryLineSegment.query.all(): sec_by_tx_sec_bus[sl.from_bus_id].append(sl)
    for d in SecondaryServiceDrop.query.all(): drops_by_bus[d.from_bus_id].append(d)
    cust_map = {c.customer_id: c for c in Customer.query.all()}; kwh_map = defaultdict(float)
    for ec in EnergyConsumption.query.all(): kwh_map[ec.customer_id] += (ec.kwh_consumed or 0)
    headers = ['Post ID', 'Pole Number', 'Post Name', 'Feeder', 'Post Phasing', 'Status', 'Latitude', 'Longitude', 'Area', 'Primary Bus ID', 'Dist Line Segment ID', 'Dist Line From Bus', 'Dist Line To Bus', 'Dist Line Phasing', 'Dist Line Length (m)', 'Dist Line Conductor Type', 'Dist Line Conductor Size', 'Transformer ID', 'TX From Primary Bus', 'TX To Secondary Bus', 'TX Primary Phasing', 'TX Secondary Phasing', 'TX kVA Rating', 'TX Primary V (kV)', 'TX Secondary V (kV)', 'TX Primary Tap V (kV)', 'TX Secondary Tap V (kV)', 'TX %Z', 'TX X/R Ratio', 'TX No-Load Loss (kW)', 'TX Exciting Current (%)', 'TX Installation Type', 'TX Connection', 'Sec Line Segment ID', 'Sec Line From Bus', 'Sec Line To Bus', 'Sec Line Phasing', 'Sec Line Length (m)', 'Sec Line Conductor Type', 'Sec Line Conductor Size', 'Service Drop ID', 'Drop From Bus', 'Drop To Customer ID', 'Drop Phasing', 'Drop Install Type', 'Drop Length-1 (m)', 'Drop Length-2 (m)', 'Customer ID', 'Customer Name', 'Customer Type', 'Service Voltage', 'Customer Phase', 'Total kWh Consumed']
    def _v(v): return v if v is not None else ''
    def generate():
        out = io.StringIO(); w = csv.writer(out); w.writerow(headers); yield out.getvalue(); out.seek(0); out.truncate(0)
        for p in posts:
            pole = p.pole_number or ''; pc = [p.id, pole, _v(p.name), _v(p.feeder), _v(p.phasing), _v(p.status), _v(p.lat), _v(p.lng), _v(p.area), _v(p.primary_bus_id)]
            dl = dist_by_from.get(pole, [None])[0]
            dc = [_v(dl.segment_id) if dl else '', _v(dl.from_bus_id) if dl else '', _v(dl.to_bus_id) if dl else '', _v(dl.phasing) if dl else '', _v(dl.length_meters) if dl else '', _v(dl.conductor_type) if dl else '', _v(dl.conductor_size) if dl else '']
            txs = tx_by_pole.get(pole, [])
            if not txs: w.writerow(pc + dc + [''] * (len(headers) - len(pc) - len(dc))); yield out.getvalue(); out.seek(0); out.truncate(0); continue
            for t in txs:
                tc = [_v(t.transformer_id), _v(t.from_primary_bus_id), _v(t.to_secondary_bus_id), _v(t.primary_phasing), _v(t.secondary_phasing), _v(t.kva_rating), _v(t.primary_voltage_kv), _v(t.secondary_voltage_kv), _v(t.primary_tap_kv), _v(t.secondary_tap_kv), _v(t.pct_z), _v(t.xr_ratio), _v(t.no_load_loss_kw), _v(t.exciting_current_pct), _v(t.installation_type), _v(t.connection)]
                slines = sec_by_tx_sec_bus.get(t.to_secondary_bus_id, [])
                if not slines: w.writerow(pc + dc + tc + [''] * (len(headers) - len(pc) - len(dc) - len(tc))); yield out.getvalue(); out.seek(0); out.truncate(0); continue
                for sl in slines:
                    sc = [_v(sl.segment_id), _v(sl.from_bus_id), _v(sl.to_bus_id), _v(sl.phasing), _v(sl.length_meters), _v(sl.conductor_type), _v(sl.conductor_size)]
                    drops = drops_by_bus.get(sl.to_bus_id, [])
                    if not drops: w.writerow(pc + dc + tc + sc + [''] * (len(headers) - len(pc) - len(dc) - len(tc) - len(sc))); yield out.getvalue(); out.seek(0); out.truncate(0); continue
                    for d in drops:
                        drc = [_v(d.service_drop_id), _v(d.from_bus_id), _v(d.to_customer_id), _v(d.phasing), _v(d.installation_type), _v(d.length_meters_1), _v(d.length_meters_2)]
                        cust = cust_map.get(d.to_customer_id); cc = [_v(cust.customer_id) if cust else _v(d.to_customer_id), _v(cust.name) if cust else '', _v(cust.customer_type) if cust else '', _v(cust.service_voltage) if cust else '', _v(cust.phase) if cust else '']
                        w.writerow(pc + dc + tc + sc + drc + cc + [round(kwh_map.get(d.to_customer_id, 0), 2)]); yield out.getvalue(); out.seek(0); out.truncate(0)
    return Response(generate(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=master_export.csv'})


@analysis_api_bp.route('/export/network/options', methods=['GET'])
def export_network_options():
    """Return feeder/municipality options for network image export filters."""
    try:
        feeders = [
            (r[0] or '').strip()
            for r in db.session.query(Post.feeder)
            .filter(Post.feeder.isnot(None), func.length(func.trim(Post.feeder)) > 0)
            .distinct()
            .order_by(Post.feeder.asc())
            .all()
        ]
        geojson_data = _load_barangay_boundaries_geojson()
        muni_map = _get_municipality_geometries(geojson_data)
        municipalities = sorted(muni_map.keys())
        # Fallback when boundary file is unavailable.
        if not municipalities:
            municipalities = [
                (r[0] or '').strip()
                for r in db.session.query(Post.area)
                .filter(Post.area.isnot(None), func.length(func.trim(Post.area)) > 0)
                .distinct()
                .order_by(Post.area.asc())
                .all()
            ]
        return jsonify({
            'feeders': feeders,
            'municipalities': municipalities,
        }), 200
    except Exception as e:
        current_app.logger.error('Failed to load export options: %s', e)
        return jsonify({'feeders': [], 'municipalities': [], 'error': str(e)}), 500


@analysis_api_bp.route('/export/network/data', methods=['GET'])
def export_network_data():
    """
    Return filtered posts + lines for image export.
    Filter modes:
      - filter_type=feeder & filter_value=<feeder>
      - filter_type=municipality & filter_value=<municipality name from barangay-boundaries.json>
    """
    try:
        filter_type = (request.args.get('filter_type') or '').strip().lower()
        filter_value = (request.args.get('filter_value') or '').strip()
        include_posts = (request.args.get('include_posts') or '1').strip().lower() in ('1', 'true', 'yes')

        if filter_type not in ('feeder', 'municipality'):
            return jsonify({'error': 'filter_type must be "feeder" or "municipality"'}), 400
        if not filter_value:
            return jsonify({'error': 'filter_value is required'}), 400

        post_query = Post.query.filter(Post.lat.isnot(None), Post.lng.isnot(None))
        if filter_type == 'feeder':
            post_query = post_query.filter(func.lower(func.trim(Post.feeder)) == filter_value.lower())
        else:
            geojson_data = _load_barangay_boundaries_geojson()
            muni_map = _get_municipality_geometries(geojson_data)
            muni_geometries = muni_map.get(filter_value, [])
            if muni_geometries:
                # Use geometry-based inclusion (authoritative map boundary source).
                matched_posts = []
                for p in post_query.all():
                    if p.lat is None or p.lng is None:
                        continue
                    lng = float(p.lng)
                    lat = float(p.lat)
                    if any(_point_in_feature_geometry(lng, lat, g) for g in muni_geometries):
                        matched_posts.append(p)
                posts = matched_posts
            else:
                # Fallback to area text match only if boundary file/data is unavailable.
                posts = post_query.filter(func.lower(func.trim(Post.area)) == filter_value.lower()).all()

        if filter_type == 'feeder':
            posts = post_query.all()
        posts_out = [p.to_dict() for p in posts] if include_posts else []

        # Build bus-id lookup from selected posts to keep only relevant lines.
        selected_bus_ids = set()
        for p in posts:
            for bus_val in (p.pole_number, p.primary_bus_id, p.sec_bus_id, p.transformer_bus_id):
                val = (bus_val or '').strip()
                if val:
                    selected_bus_ids.add(val)

        data = get_network_geometry(current_app)
        lines = data.get('lines', []) if isinstance(data, dict) else []
        filtered_lines = []

        if filter_type == 'feeder':
            target = filter_value.lower()
            for line in lines:
                line_feeder = (line.get('feeder') or '').strip().lower()
                if line_feeder == target:
                    filtered_lines.append(line)
        else:
            # Municipality filter: keep lines connected to selected posts by bus id.
            for line in lines:
                from_bus = (line.get('from_bus') or '').strip()
                to_bus = (line.get('to_bus') or '').strip()
                if (from_bus and from_bus in selected_bus_ids) or (to_bus and to_bus in selected_bus_ids):
                    filtered_lines.append(line)

        municipality_boundary = []
        if filter_type == 'municipality':
            geojson_data = _load_barangay_boundaries_geojson()
            muni_map = _get_municipality_geometries(geojson_data)
            municipality_boundary = muni_map.get(filter_value, [])

        return jsonify({
            'filter_type': filter_type,
            'filter_value': filter_value,
            'posts': posts_out,
            'lines': filtered_lines,
            'municipality_boundary': municipality_boundary,
            'meta': {
                'post_count': len(posts_out),
                'line_count': len(filtered_lines),
            }
        }), 200
    except Exception as e:
        current_app.logger.error('Failed to build export network data: %s', e)
        return jsonify({'error': str(e), 'posts': [], 'lines': []}), 500

@analysis_api_bp.route('/transformer-location/<transformer_id>', methods=['GET'])
def api_transformer_location(transformer_id):
    try:
        from models import DistributionTransformer, Post, BusNode
        # 1. Robust Transformer Lookup (case-insensitive & trimmed)
        tid = transformer_id.strip()
        trans = DistributionTransformer.query.filter(DistributionTransformer.transformer_id.ilike(tid)).first()
        if not trans or not trans.from_primary_bus_id:
            return jsonify({'error': 'Transformer not found in registry'}), 404
        
        primary_bus = trans.from_primary_bus_id
        post = None
        
        # 2. Try Direct Post Match
        post = Post.query.filter((Post.primary_bus_id == primary_bus) | (Post.pole_number == primary_bus)).first()
        
        # 3. Try BusNode Bridge
        if not post:
            bn = BusNode.query.filter_by(bus_id=primary_bus).first()
            if bn:
                if bn.pole_id:
                    post = Post.query.get(bn.pole_id)
                elif bn.pole_number:
                    post = Post.query.filter_by(pole_number=bn.pole_number).first()
                
                # If we found a BusNode but it has no Post link, use its coordinates directly
                if not post and bn.lat and bn.lng:
                    return jsonify({'post_id': None, 'lat': bn.lat, 'lng': bn.lng, 'name': f"Bus {bn.bus_id}"}), 200

        # 4. Final Fallback: Numeric ID match for the bus
        if not post and primary_bus.isdigit():
            post = Post.query.get(int(primary_bus))

        if post and post.lat and post.lng:
            return jsonify({
                'post_id': post.id,
                'lat': post.lat,
                'lng': post.lng,
                'pole_number': post.pole_number,
                'name': post.name or post.pole_number or f"Pole {post.id}"
            }), 200
            
        return jsonify({'error': f'Coordinates could not be resolved for primary bus: {primary_bus}'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analysis_api_bp.route('/ml/transformer-risk', methods=['GET'])
def api_ml_transformer_risk():
    try:
        force_refresh = request.args.get('refresh', 'false').lower() == 'true'
        result = get_grid_health_analytics(force_refresh=force_refresh)
        return jsonify({
            'predictions': result.get('details', []),
            'summary': result.get('summary', {}),
            'model_info': result.get('model_info', {}),
            'timestamp': result.get('timestamp', ''),
            'is_snapshot': result.get('is_snapshot', False)
        }), 200
    except Exception as e: return jsonify({'error': str(e), 'predictions': []}), 500

@analysis_api_bp.route('/ml/transformer-load-stress', methods=['GET'])
def api_transformer_load_stress_route():
    try:
        results = calculate_transformer_load_stress()
        return jsonify({'status': 'success', 'count': len(results), 'predictions': results}), 200
    except Exception as e: return jsonify({'error': str(e), 'predictions': []}), 500

@analysis_api_bp.route('/network/trace-feeder', methods=['GET'])
def api_trace_feeder():
    start_bus = request.args.get('start_bus')
    if not start_bus: return jsonify({'error': 'Missing start_bus'}), 400
    try:
        from services.network_geometry_db import trace_feeder_bfs, trace_downstream_bfs, trace_upstream_bfs, resolve_all_bus_ids
        from models import BusNode
        direction = request.args.get('direction', 'both').lower()

        # Gather ALL bus IDs using shared utility
        actual_start_bus = resolve_all_bus_ids(start_bus)

        if direction == 'downstream':
            visited = list(trace_downstream_bfs(current_app, actual_start_bus))
        elif direction == 'upstream':
            visited = list(trace_upstream_bfs(current_app, actual_start_bus))
        else:
            # For 'both' direction, use undirected BFS with first candidate
            visited = trace_feeder_bfs(current_app, actual_start_bus[0])
        return jsonify({'status': 'success', 'start_bus': actual_start_bus, 'count': len(visited), 'visited_buses': visited}), 200
    except Exception as e:
        import traceback
        current_app.logger.error(f"Trace feeder error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@analysis_api_bp.route('/network/simulate-outage', methods=['GET'])
def api_simulate_outage():
    start_bus = request.args.get('start_bus')
    if not start_bus: return jsonify({'error': 'Missing start_bus'}), 400
    try:
        impact = calculate_outage_impact(start_bus)
        return jsonify(impact), 200
    except Exception as e: return jsonify({'error': str(e)}), 500
