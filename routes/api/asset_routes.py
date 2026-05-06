from flask import Blueprint, jsonify, request, g, current_app
from extensions import db
from sqlalchemy import text, func
import math
from models import (
    Post, Meter, LatLongData, BusNode, 
    DistributionLineSegment, SecondaryLineSegment, 
    DistributionTransformer, SecondaryServiceDrop, 
    VoltageRegulator, ShuntCapacitor, ShuntInductor, SeriesInductor,
    Customer, EnergyConsumption, LineConnection
)
from services.post_service import (
    create_post, get_paginated_posts, get_post_detail as svc_get_post_detail, 
    update_post, delete_post, search_posts
)

asset_api_bp = Blueprint('asset_api', __name__)

@asset_api_bp.route('/posts', methods=['GET', 'POST'])
def api_posts():
    if request.method == 'POST':
        if not g.get('current_user') or not g.current_user.is_admin():
            return jsonify({'error': 'admin required'}), 403
        try:
            data = request.get_json() or {}
            result = create_post(data)
            return jsonify(result), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), getattr(e, 'code', 400) if isinstance(e, ValueError) else 500
    
    in_ph = str(request.args.get('in_ph', '')).lower() in ('1', 'true', 'yes')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    if page < 1: page = 1
    if per_page < 1 or per_page > 1000: per_page = 10
    try:
        result = get_paginated_posts(in_ph, page, per_page)
        return jsonify(result)
    except Exception as e:
        return jsonify({"data": [], "error": str(e)}), 500

@asset_api_bp.route('/posts/search', methods=['GET'])
def api_posts_search():
    q = request.args.get('q', '')
    if not q:
        return jsonify([])
    try:
        results = search_posts(q)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@asset_api_bp.route('/posts/nearest', methods=['GET'])
def api_posts_nearest():
    """Find the single closest post to the given latitude and longitude."""
    try:
        lat = request.args.get('lat', type=float)
        lng = request.args.get('lng', type=float)
        in_ph = str(request.args.get('in_ph', '')).lower() in ('1', 'true', 'yes')
        pole_only = str(request.args.get('pole_only', '')).lower() in ('1', 'true', 'yes')
        if lat is None or lng is None:
            return jsonify({'error': 'lat and lng required'}), 400

        # Basic coordinate validation to avoid meaningless searches.
        if lat < -90 or lat > 90 or lng < -180 or lng > 180:
            return jsonify({'error': 'invalid latitude/longitude'}), 400

        query_point = func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)

        # Keep nearest lookup aligned with "real poles" shown on map.
        query = Post.query.filter(Post.lat.isnot(None), Post.lng.isnot(None))
        if in_ph:
            query = query.filter(Post.lat >= 4.0, Post.lat <= 22.0, Post.lng >= 116.0, Post.lng <= 127.5)
        if pole_only:
            query = query.filter(func.nullif(func.trim(Post.pole_number), '').isnot(None))

        # Prefer geospatial distance when PostGIS metadata is available.
        # If unavailable, fallback to Haversine distance using plain lat/lng math.
        db_point = func.ST_SetSRID(func.ST_MakePoint(Post.lng, Post.lat), 4326)
        geo_dist_expr = func.ST_DistanceSphere(db_point, query_point)
        try:
            nearest_post = query.order_by(geo_dist_expr.asc(), Post.id.asc()).first()
        except Exception:
            db.session.rollback()
            lat_rad = func.radians(Post.lat)
            lng_rad = func.radians(Post.lng)
            q_lat_rad = func.radians(lat)
            q_lng_rad = func.radians(lng)
            earth_radius_m = 6371000.0
            haversine_expr = earth_radius_m * 2.0 * func.asin(
                func.sqrt(
                    func.pow(func.sin((lat_rad - q_lat_rad) / 2.0), 2) +
                    func.cos(q_lat_rad) * func.cos(lat_rad) *
                    func.pow(func.sin((lng_rad - q_lng_rad) / 2.0), 2)
                )
            )
            nearest_post = query.order_by(haversine_expr.asc(), Post.id.asc()).first()

        if not nearest_post:
            return jsonify({'error': 'No posts found'}), 404

        # Add distance to help UI/debugging and validate nearest pick.
        nearest_data = nearest_post.to_dict()
        try:
            # Calculate precise distance in Python so response works in both modes.
            lat1 = math.radians(float(lat))
            lng1 = math.radians(float(lng))
            lat2 = math.radians(float(nearest_post.lat))
            lng2 = math.radians(float(nearest_post.lng))
            d_lat = lat2 - lat1
            d_lng = lng2 - lng1
            a = math.sin(d_lat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2.0) ** 2
            c = 2.0 * math.asin(math.sqrt(a))
            nearest_data['distance_meters'] = float(6371000.0 * c)
        except Exception:
            nearest_data['distance_meters'] = None

        return jsonify(nearest_data)
    except Exception as e:
        current_app.logger.error('Failed to find nearest post: %s', e)
        return jsonify({'error': str(e)}), 500

@asset_api_bp.route('/posts/<int:post_id>', methods=['GET', 'PUT', 'DELETE'])
def api_post_detail(post_id):
    try:
        if request.method == 'GET':
            post_dict = svc_get_post_detail(post_id)
            if not post_dict: return jsonify({'error': 'post not found'}), 404
            return jsonify(post_dict)
        if not g.get('current_user') or not g.current_user.is_admin():
            return jsonify({'error': 'admin required'}), 403
        if request.method == 'PUT':
            data = request.get_json() or {}
            result = update_post(post_id, data)
            result['success'] = True
            return jsonify(result)
        elif request.method == 'DELETE':
            success = delete_post(post_id)
            return jsonify({'success': success})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 404 if "not found" in str(e) else 500

@asset_api_bp.route('/posts/<int:post_id>/connections', methods=['GET'])
def api_post_connections(post_id):
    try:
        p = Post.query.get(post_id)
        if not p: return jsonify([]), 200
        buses = {p.pole_number} if p.pole_number else set()
        if p.pole_number and not str(p.pole_number).startswith('P'):
            try: buses.add(f"P{str(p.pole_number).zfill(8)}")
            except: pass
        if p.primary_bus_id: buses.add(p.primary_bus_id)
        if p.sec_bus_id: buses.add(p.sec_bus_id)
        if p.transformer_bus_id: buses.add(p.transformer_bus_id)
        
        # Use pole_id (FK) for more accurate matching, fallback to pole_number only if not Null
        if p.pole_number:
            bns = BusNode.query.filter((BusNode.pole_id == p.id) | (BusNode.pole_number == p.pole_number)).all()
        else:
            bns = BusNode.query.filter_by(pole_id=p.id).all()
        
        for bn in bns: buses.add(bn.bus_id)
        if not buses: return jsonify([]), 200
        bus_list = list(buses)
        connections = []
        dist_lines = DistributionLineSegment.query.filter(DistributionLineSegment.from_bus_id.in_(bus_list) | DistributionLineSegment.to_bus_id.in_(bus_list)).all()
        for l in dist_lines:
            connections.append({'id': l.segment_id or f"DL-{l.id}", 'type': 'Primary', 'name': f"Segment {l.segment_id}", 'from_bus': l.from_bus_id, 'to_bus': l.to_bus_id, 'phase': l.phasing, 'total_length': l.length_meters})
        sec_lines = SecondaryLineSegment.query.filter(SecondaryLineSegment.from_bus_id.in_(bus_list) | SecondaryLineSegment.to_bus_id.in_(bus_list)).all()
        for l in sec_lines:
            connections.append({'id': f"SL-{l.id}", 'type': 'Secondary', 'name': f"Sec Line #{l.id}", 'from_bus': l.from_bus_id, 'to_bus': l.to_bus_id, 'phase': l.phasing, 'total_length': l.length_meters})
        return jsonify(connections)
    except Exception as e:
        current_app.logger.warning('Failed to fetch connections for post %s: %s', post_id, e)
        return jsonify([])

@asset_api_bp.route('/posts/<int:post_id>/service-drops', methods=['GET'])
def api_post_service_drops(post_id):
    try:
        from services.analysis_services import get_service_drops_for_post
        drops_list = get_service_drops_for_post(post_id)
        return jsonify({'count': len(drops_list), 'service_drops': [d.to_dict() for d in drops_list]}), 200
    except Exception as e:
        return jsonify({'count': 0, 'service_drops': [], 'error': str(e)}), 500

@asset_api_bp.route('/primary-lines/by-bus/<bus_id>', methods=['GET'])
def api_primary_lines_by_bus(bus_id):
    try:
        from services.network_geometry_db import resolve_all_bus_ids
        lookup_ids = resolve_all_bus_ids(bus_id)
        candidates = DistributionLineSegment.query.filter(DistributionLineSegment.from_bus_id.in_(lookup_ids) | DistributionLineSegment.to_bus_id.in_(lookup_ids) | DistributionLineSegment.from_bus_id.endswith(bus_id) | DistributionLineSegment.to_bus_id.endswith(bus_id)).all()
        items = []
        for c in candidates:
            if (c.from_bus_id in lookup_ids) or (c.to_bus_id in lookup_ids):
                items.append(c)
                continue
            for db_bus_id in (c.from_bus_id, c.to_bus_id):
                if db_bus_id and db_bus_id.endswith(bus_id):
                    prefix = db_bus_id[:-len(bus_id)]
                    if prefix == "" or (prefix.startswith("P") and prefix[1:].replace("0", "") == ""):
                        items.append(c)
                        break
        seen_ids = set()
        unique_items = [it for it in items if it.id not in seen_ids and not seen_ids.add(it.id)]
        return jsonify({'count': len(unique_items), 'primary_lines': [x.to_dict() for x in unique_items]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@asset_api_bp.route('/bus-nodes', methods=['GET'])
def api_bus_nodes_list():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 100, type=int)
        feeder = request.args.get('feeder', None)
        if page < 1: page = 1
        if per_page < 1 or per_page > 2000: per_page = 100
        query = BusNode.query
        if feeder: query = query.filter_by(feeder=feeder)
        query = query.order_by(BusNode.id.asc())
        total = query.count()
        nodes = query.offset((page - 1) * per_page).limit(per_page).all()
        return jsonify({'data': [n.to_dict() for n in nodes], 'pagination': {'page': page, 'per_page': per_page, 'total': total, 'total_pages': (total + per_page - 1) // per_page}})
    except Exception as e:
        return jsonify({'error': str(e), 'data': []}), 500

@asset_api_bp.route('/transformers/by-bus/<bus_id>', methods=['GET'])
def api_transformers_by_bus(bus_id):
    try:
        from services.network_geometry_db import resolve_all_bus_ids
        lookup_ids = resolve_all_bus_ids(bus_id)
        candidates = DistributionTransformer.query.filter(DistributionTransformer.from_primary_bus_id.in_(lookup_ids) | DistributionTransformer.from_primary_bus_id.endswith(bus_id)).all()
        def match_bus_id(query_id, db_id, allowed_list):
            if not db_id: return False
            
            # Strict Lateral Check: If query is main-line (no dash), 
            # it cannot match a lateral asset (has dash).
            query_is_lateral = '-' in str(query_id)
            db_is_lateral = '-' in str(db_id)
            if not query_is_lateral and db_is_lateral:
                return False

            if db_id in allowed_list: return True
            if not db_id.endswith(query_id): return False
            prefix = db_id[:-len(query_id)]
            return prefix == "" or (prefix.startswith("P") and prefix[1:].replace("0", "") == "")
            
        transformers = [t for t in candidates if match_bus_id(bus_id, t.from_primary_bus_id, lookup_ids)]
        # Final safety filter on the transformer ID itself
        if '-' not in str(bus_id):
            transformers = [t for t in transformers if '-' not in (t.transformer_id or '')]
        return jsonify({'bus_id': bus_id, 'count': len(transformers), 'transformers': [t.to_dict() for t in transformers]}), 200
    except Exception as e:
        return jsonify({'error': str(e), 'bus_id': bus_id}), 500

@asset_api_bp.route('/transformers/find/<path:tx_id>', methods=['GET'])
def api_find_transformer(tx_id):
    """Pinpoint the location (Post) of a specific Transformer ID."""
    try:
        # 1. Find the transformer record
        tx = DistributionTransformer.query.filter_by(transformer_id=tx_id).first()
        if not tx:
            # Try fuzzy match if exact fails
            tx = DistributionTransformer.query.filter(DistributionTransformer.transformer_id.ilike(f"%{tx_id}%")).first()
        
        if not tx:
            return jsonify({'error': 'Transformer record not found'}), 404
            
        # 2. Find the post that handles this transformer's bus
        # We look for matches on transformer_bus_id first, then primary_bus_id
        bus = tx.from_primary_bus_id
        post = Post.query.filter(
            (Post.transformer_bus_id == bus) | 
            (Post.primary_bus_id == bus) |
            (Post.pole_number == bus)
        ).first()
        
        if not post or not post.lat:
            return jsonify({'error': 'Transformer found but not mapped to a physical pole', 'tx': tx.to_dict()}), 404
            
        return jsonify({
            'success': True,
            'post_id': post.id,
            'pole_number': post.pole_number,
            'lat': post.lat,
            'lng': post.lng,
            'transformer_id': tx.transformer_id,
            'kva': tx.kva_rating
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@asset_api_bp.route('/distribution-lines', methods=['GET'])
def api_distribution_lines():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        if page < 1: page = 1
        query = DistributionLineSegment.query.order_by(DistributionLineSegment.id.asc())
        total = query.count()
        lines = query.offset((page - 1) * per_page).limit(per_page).all()
        return jsonify({"data": [l.to_dict() for l in lines], "pagination": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page}})
    except Exception as e:
        return jsonify({"data": [], "error": str(e)}), 500

@asset_api_bp.route('/secondary-lines', methods=['GET'])
def api_secondary_lines():
    try:
        lines = SecondaryLineSegment.query.order_by(SecondaryLineSegment.id.desc()).all()
        return jsonify([line.to_dict() for line in lines])
    except Exception as e:
        return jsonify([]), 200

@asset_api_bp.route('/secondary-lines/by-bus/<bus_id>', methods=['GET'])
def api_secondary_lines_by_bus(bus_id):
    try:
        from services.network_geometry_db import resolve_all_bus_ids
        lookup_ids = resolve_all_bus_ids(bus_id)
        lines = SecondaryLineSegment.query.filter((SecondaryLineSegment.from_bus_id.in_(lookup_ids)) | (SecondaryLineSegment.to_bus_id.in_(lookup_ids))).all()
        return jsonify({'bus_id': bus_id, 'count': len(lines), 'secondary_lines': [l.to_dict() for l in lines]}), 200
    except Exception as e:
        return jsonify({'error': str(e), 'bus_id': bus_id}), 500

@asset_api_bp.route('/secondary-service-drops/by-bus/<bus_id>', methods=['GET'])
def api_service_drops_by_bus(bus_id):
    try:
        drops = SecondaryServiceDrop.query.filter_by(from_bus_id=bus_id).all()
        return jsonify({'bus_id': bus_id, 'count': len(drops), 'service_drops': [d.to_dict() for d in drops]}), 200
    except Exception as e:
        return jsonify({'error': str(e), 'bus_id': bus_id}), 500

from services.network_geometry_db import resolve_all_bus_ids, resolve_specific_bus_ids

@asset_api_bp.route('/voltage-regulators/by-bus/<bus_id>', methods=['GET'])
def api_get_voltage_regulators_by_bus(bus_id):
    try:
        lookup_ids = resolve_specific_bus_ids(bus_id)
        items = VoltageRegulator.query.filter(
            VoltageRegulator.from_bus_id.in_(lookup_ids) |
            VoltageRegulator.to_bus_id.in_(lookup_ids) |
            VoltageRegulator.regulated_bus_id.in_(lookup_ids)
        ).all()
        return jsonify({'count': len(items), 'items': [x.to_dict() for x in items]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@asset_api_bp.route('/shunt-capacitors/by-bus/<bus_id>', methods=['GET'])
def api_get_shunt_capacitors_by_bus(bus_id):
    try:
        lookup_ids = resolve_specific_bus_ids(bus_id)
        items = ShuntCapacitor.query.filter(ShuntCapacitor.bus_connected_id.in_(lookup_ids)).all()
        return jsonify({'count': len(items), 'items': [x.to_dict() for x in items]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@asset_api_bp.route('/shunt-inductors/by-bus/<bus_id>', methods=['GET'])
def api_get_shunt_inductors_by_bus(bus_id):
    try:
        lookup_ids = resolve_specific_bus_ids(bus_id)
        items = ShuntInductor.query.filter(ShuntInductor.bus_connected_id.in_(lookup_ids)).all()
        return jsonify({'count': len(items), 'items': [x.to_dict() for x in items]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@asset_api_bp.route('/series-inductors/by-bus/<bus_id>', methods=['GET'])
def api_get_series_inductors_by_bus(bus_id):
    try:
        lookup_ids = resolve_specific_bus_ids(bus_id)
        items = SeriesInductor.query.filter(
            SeriesInductor.from_bus_id.in_(lookup_ids) |
            SeriesInductor.to_bus_id.in_(lookup_ids)
        ).all()
        return jsonify({'count': len(items), 'items': [x.to_dict() for x in items]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@asset_api_bp.route('/customers', methods=['GET'])
def get_customers():
    try:
        from services.analysis_services import find_customer_post_location
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        q = (request.args.get('q') or '').strip()
        skip_trace = request.args.get('skip_trace', 'false').lower() == 'true'
        query = Customer.query
        if q:
            term = f"%{q}%"
            query = query.filter((Customer.customer_id.ilike(term)) | (Customer.name.ilike(term)))
        query = query.order_by(Customer.customer_id.asc())
        total = query.count()
        items = query.offset((page - 1) * per_page).limit(per_page).all()
        data = []
        for c in items:
            c_dict = c.to_dict()
            c_dict['connected_post'] = find_customer_post_location(c.customer_id) if not skip_trace else None
            data.append(c_dict)
        return jsonify({"data": data, "pagination": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page}})
    except Exception as e:
        return jsonify({"data": [], "error": str(e)}), 500

@asset_api_bp.route('/customers/<path:customer_id>', methods=['GET'])
def get_customer(customer_id):
    c = Customer.query.filter_by(customer_id=customer_id).first()
    if not c: return jsonify({'error': 'Customer not found'}), 404
    return jsonify(c.to_dict())

@asset_api_bp.route('/customers/<path:customer_id>/location', methods=['GET'])
def get_customer_location(customer_id):
    try:
        from services.analysis_services import find_customer_post_location
        c = Customer.query.filter_by(customer_id=customer_id).first()
        if not c: return jsonify({'error': 'Customer not found', 'found': False}), 404
        return jsonify({'found': True, 'customer': c.to_dict(), 'connected_post': find_customer_post_location(customer_id)})
    except Exception as e:
        return jsonify({'error': str(e), 'found': False}), 500

@asset_api_bp.route('/customers/<path:customer_id>/consumption', methods=['GET'])
def get_customer_consumption(customer_id):
    records = EnergyConsumption.query.filter_by(customer_id=customer_id).order_by(EnergyConsumption.billing_period.desc()).all()
    return jsonify({'items': [r.to_dict() for r in records]})

@asset_api_bp.route('/latlongdata', methods=['GET'])
def api_latlongdata():
    try:
        res = db.session.execute(text('SELECT * FROM latlongdata LIMIT 0'))
        col_names = list(res.keys()); lower_cols = [c.lower() for c in col_names]
        mapping = {}
        for name in ['post_id', 'latitude', 'longitude']:
            if name in lower_cols: mapping[name] = col_names[lower_cols.index(name)]
        if len(mapping) < 3:
            if len(col_names) < 3: return jsonify({'error': 'latlongdata must have at least 3 columns'}), 400
            mapping = {'post_id': col_names[0], 'latitude': col_names[1], 'longitude': col_names[2]}
        sql = text(f'SELECT "{mapping["post_id"]}" AS post_id, "{mapping["latitude"]}" AS latitude, "{mapping["longitude"]}" AS longitude FROM latlongdata')
        rows = db.session.execute(sql).fetchall()
        out = []
        for r in rows:
            try:
                pid = r.post_id if hasattr(r, 'post_id') else r[0]
                lat = r.latitude if hasattr(r, 'latitude') else r[1]
                lng = r.longitude if hasattr(r, 'longitude') else r[2]
                if pid is not None or lat is not None or lng is not None:
                    out.append({'post_id': int(pid) if pid is not None else None, 'lat': float(lat) if lat is not None else None, 'lng': float(lng) if lng is not None else None})
            except: continue
        return jsonify(out)
    except: return jsonify([])

@asset_api_bp.route('/line-connections', methods=['GET'])
def api_line_connections():
    try:
        conns = LineConnection.query.all()
        return jsonify([c.to_dict() for c in conns])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@asset_api_bp.route('/connections', methods=['POST'])
def api_connections_create():
    if not g.get('current_user') or not g.current_user.is_admin():
        return jsonify({'error': 'admin required'}), 403
    try:
        data = request.get_json() or {}
        from_bus = data.get('from_bus')
        to_bus = data.get('to_bus')
        conn_type = data.get('connection_type', 'Manual')
        if not from_bus or not to_bus:
            return jsonify({'error': 'from_bus and to_bus required'}), 400
        
        existing = LineConnection.query.filter_by(from_bus=from_bus, to_bus=to_bus, connection_type=conn_type).first()
        if existing:
            return jsonify({'result': 'exists', 'id': existing.id})
            
        conn = LineConnection(
            from_bus=from_bus,
            to_bus=to_bus,
            connection_type=conn_type,
            feeder=data.get('feeder'),
            circuit=data.get('circuit'),
            phasing=data.get('phasing')
        )
        db.session.add(conn)
        db.session.commit()
        return jsonify({'result': 'ok', 'id': conn.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@asset_api_bp.route('/connections/<int:conn_id>', methods=['DELETE'])
def api_connection_delete(conn_id):
    if not g.get('current_user') or not g.current_user.is_admin():
        return jsonify({'error': 'admin required'}), 403
    try:
        conn = LineConnection.query.get(conn_id)
        if not conn:
            return jsonify({'error': 'connection not found'}), 404
        db.session.delete(conn)
        db.session.commit()
        return jsonify({'result': 'deleted', 'id': conn_id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@asset_api_bp.route('/export/post/<int:post_id>')
def api_export_post(post_id):
    post = Post.query.get(post_id)
    if not post: return jsonify({'error': 'Post not found'}), 404
    
    import io, csv
    from flask import Response
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    data = post.to_dict()
    writer.writerow(data.keys())
    writer.writerow(data.values())
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=post_{post.pole_number or post.id}.csv"}
    )
