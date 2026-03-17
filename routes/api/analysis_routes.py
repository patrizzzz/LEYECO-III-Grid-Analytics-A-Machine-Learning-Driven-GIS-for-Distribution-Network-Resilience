from flask import Blueprint, jsonify, request, g, current_app, Response
import io, csv, math, requests, traceback
from extensions import db
from models import Post, DistributionLineSegment, SecondaryLineSegment, DistributionTransformer, Customer, EnergyConsumption, SecondaryServiceDrop
from services.analysis_services import get_grid_health_analytics, calculate_transformer_load_stress, calculate_outage_impact, find_customer_post_location
from services.network_geometry_db import get_network_geometry

analysis_api_bp = Blueprint('analysis_api', __name__)

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

@analysis_api_bp.route('/transformer-location/<transformer_id>', methods=['GET'])
def api_transformer_location(transformer_id):
    try:
        from models import DistributionTransformer, Post, BusNode
        trans = DistributionTransformer.query.filter_by(transformer_id=transformer_id).first()
        if not trans or not trans.from_primary_bus_id: return jsonify({'error': 'Not found'}), 404
        primary_bus = trans.from_primary_bus_id
        post = Post.query.filter((Post.primary_bus_id == primary_bus) | (Post.pole_number == primary_bus)).first()
        if not post:
            bn = BusNode.query.filter_by(bus_id=primary_bus).first()
            if bn and bn.pole_number: post = Post.query.filter_by(pole_number=bn.pole_number).first()
        if post and post.lat and post.lng: return jsonify({'post_id': post.id, 'lat': post.lat, 'lng': post.lng, 'pole_number': post.pole_number, 'name': post.name}), 200
        return jsonify({'error': 'No coordinates found'}), 404
    except Exception as e: return jsonify({'error': str(e)}), 500

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
