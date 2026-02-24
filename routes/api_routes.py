from flask import Blueprint, jsonify, request, g, current_app
from functools import wraps
from werkzeug.utils import secure_filename
import io
import secrets
import traceback
import requests
from sqlalchemy import text

from extensions import db, migrate
from models import (
    Post, Meter, LatLongData, BusPostMapping, 
    DistributionLineSegment, SecondaryLineSegment, 
    DistributionTransformer, SecondaryServiceDrop, 
    UploadHistory, VoltageRegulator, 
    ShuntCapacitor, ShuntInductor, SeriesInductor,
    Customer, EnergyConsumption
)
import math
from utils.import_helpers import find_column_value, sanitize_float
from utils.network_utils import infer_connections_from_posts
from utils.csv_importers import (import_posts_from_csv, import_transformers_from_csv, 
                                import_secondary_lines_from_csv, import_service_drops_from_csv,
                                import_voltage_regulators_from_csv, import_shunt_capacitors_from_csv,
                                import_shunt_inductors_from_csv, import_series_inductors_from_csv,
                                import_customers_from_csv, import_energy_consumption_from_csv)

api_bp = Blueprint('api', __name__)

# --- Helpers (duplicate of main for now to avoid circular dependency issues, or common utils) ---
def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        u = g.get('current_user')
        if not u or not u.is_admin():
            return jsonify({'error': 'admin required'}), 403
        return f(*args, **kwargs)
    return wrapper

# Sample in-memory posts
POSTS = [
    {"id": 1, "name": "Pole A", "lat": 14.5995, "lng": 120.9842, "status": "Active"},
    {"id": 2, "name": "Pole B", "lat": 14.6091, "lng": 121.0223, "status": "Active"},
]

# --- API Routes ---

@api_bp.route('/posts', methods=['GET', 'POST'])
def api_posts():
    if request.method == 'POST':
        if not g.get('current_user') or not g.current_user.is_admin():
            return jsonify({'error': 'admin required'}), 403
        try:
            data = request.get_json() or {}
            name = (data.get('name') or '').strip()
            if not name:
                return jsonify({'error': 'name is required'}), 400
            try:
                lat = float(data.get('lat'))
                lng = float(data.get('lng'))
            except (TypeError, ValueError):
                return jsonify({'error': 'lat and lng must be numbers'}), 400
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                return jsonify({'error': 'lat/lng out of range'}), 400
            status = (data.get('status') or '').strip() or None
            area = (data.get('area') or '').strip() or None
            post = Post(name=name, lat=lat, lng=lng, status=status, area=area)
            db.session.add(post)
            db.session.commit()
            return jsonify({
                'id': post.id,
                'name': post.name,
                'lat': post.lat,
                'lng': post.lng,
                'status': post.status,
            }), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    # GET
    in_ph = str(request.args.get('in_ph', '')).lower() in ('1', 'true', 'yes')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    if page < 1: page = 1
    if per_page < 1 or per_page > 1000: per_page = 10
    
    try:
        query = Post.query
        if in_ph:
            query = query.filter(Post.lat >= 4.0, Post.lat <= 22.0, Post.lng >= 116.0, Post.lng <= 127.5)
        
        total = query.count()
        db_posts = query.offset((page - 1) * per_page).limit(per_page).all()
        posts = [{"id": p.id, "name": p.name, "lat": p.lat, "lng": p.lng, "status": p.status} for p in db_posts]
        
        total_pages = (total + per_page - 1) // per_page
        
        return jsonify({
            "data": posts,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        })
    except Exception as e:
        if current_app.debug:
            return jsonify({"error": "DB query failed", "details": str(e)}), 500
        pass
    
    # Fallback to in-memory
    fallback_posts = POSTS
    if in_ph:
        fallback_posts = [p for p in POSTS if p['lat'] >= 4.0 and p['lat'] <= 22.0 and p['lng'] >= 116.0 and p['lng'] <= 127.5]
    
    total = len(fallback_posts)
    total_pages = (total + per_page - 1) // per_page
    paginated_posts = fallback_posts[(page - 1) * per_page:page * per_page]
    
    return jsonify({
        "data": paginated_posts,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    })

@api_bp.route('/posts/<int:post_id>', methods=['GET', 'PUT', 'DELETE'])
def api_post_detail(post_id):
    try:
        p = Post.query.get(post_id)
        if not p: return jsonify({'error': 'post not found'}), 404
        
        if request.method == 'GET':
            post_dict = p.to_dict()
            meters = []
            for m in getattr(p, 'meters', []):
                meters.append({
                    'id': m.id, 'meter_id': m.meter_id, 'meter_brand': m.meter_brand,
                    'meter_rating': m.meter_rating, 'kwhr_reading': m.kwhr_reading,
                    'reading_date': m.reading_date.isoformat() if m.reading_date else None,
                })
            post_dict['meters'] = meters
            extra_fields = ['pri_structure','pri_conductor_size','neutral_wire','configuration',
                            'primary_bus_id','sec_structure','sec_conductor_size','sec_type',
                            'conductor_type','sec_bus_id','common_sole','transformer_bus_id',
                            'transformer_phasing','grounding_rod','l2_wire_type','l1_wire_type',
                            'created_at','updated_at']
            for f in extra_fields:
                post_dict[f] = getattr(p, f, None)
            return jsonify(post_dict)
        
        if not g.get('current_user') or not g.current_user.is_admin():
            return jsonify({'error': 'admin required'}), 403
        
        if request.method == 'PUT':
            data = request.get_json() or {}
            if 'lat' in data: p.lat = float(data['lat'])
            if 'lng' in data: p.lng = float(data['lng'])
            if 'status' in data: p.status = (data['status'] or '').strip() or None
            db.session.commit()
            return jsonify({'success': True, 'id': p.id, 'name': p.name, 'lat': p.lat, 'lng': p.lng, 'status': p.status})
        
        elif request.method == 'DELETE':
            db.session.delete(p)
            db.session.commit()
            return jsonify({'success': True})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/posts/<int:post_id>/connections', methods=['GET'])
def api_post_connections(post_id):
    try:
        p = Post.query.get(post_id)
        if not p: return jsonify([]), 200

        # Collect all bus IDs associated with this post
        buses = set()
        if p.primary_bus_id: buses.add(p.primary_bus_id)
        if p.sec_bus_id: buses.add(p.sec_bus_id)
        if p.transformer_bus_id: buses.add(p.transformer_bus_id)
        
        # Also interpret pole number as a potential bus ID (common in some datasets)
        if p.pole_number:
            buses.add(p.pole_number)
            buses.add(f"P{p.pole_number}")

        if not buses: return jsonify([]), 200
        
        bus_list = list(buses)
        connections = []

        # 1. Check Distribution Lines (Primary)
        # Import inside function to ensure no circular deps, though mostly ok at top level
        from models import DistributionLineSegment, SecondaryLineSegment
        
        dist_lines = DistributionLineSegment.query.filter(
            (DistributionLineSegment.from_bus_id.in_(bus_list)) | 
            (DistributionLineSegment.to_bus_id.in_(bus_list))
        ).all()

        for l in dist_lines:
            connections.append({
                'id': l.segment_id or f"DL-{l.id}",
                'type': 'Primary',
                'name': f"Segment {l.segment_id}",
                'from_bus': l.from_bus_id,
                'to_bus': l.to_bus_id,
                'phase': l.phasing
            })

        # 2. Check Secondary Lines
        sec_lines = SecondaryLineSegment.query.filter(
            (SecondaryLineSegment.from_bus_id.in_(bus_list)) | 
            (SecondaryLineSegment.to_bus_id.in_(bus_list))
        ).all()

        for l in sec_lines:
            connections.append({
                'id': f"SL-{l.id}",
                'type': 'Secondary',
                'name': f"Sec Line #{l.id}",
                'from_bus': l.from_bus_id,
                'to_bus': l.to_bus_id,
                'phase': l.phasing
            })

        return jsonify(connections)
    except Exception as e:
        current_app.logger.warning('Failed to fetch connections for post %s: %s', post_id, e)
        # Return empty list on error to avoid breaking UI
@api_bp.route('/posts/<int:post_id>/service-drops', methods=['GET'])
def api_post_service_drops(post_id):
    try:
        from models import Post, DistributionTransformer, SecondaryLineSegment, SecondaryServiceDrop
        p = Post.query.get(post_id)
        if not p: return jsonify({'count': 0, 'service_drops': []}), 404

        primary_bus_id = p.primary_bus_id or p.pole_number
        if not primary_bus_id:
            return jsonify({'count': 0, 'service_drops': []}), 200

        # Reproduce exact logic from main.js map popup (Secondary Service Drop button)
        transformers = DistributionTransformer.query.filter_by(from_primary_bus_id=primary_bus_id).all()
        if not transformers:
            return jsonify({'count': 0, 'service_drops': []}), 200

        transformer = transformers[0]
        secondary_bus_id = transformer.to_secondary_bus_id

        if not secondary_bus_id:
            return jsonify({'count': 0, 'service_drops': []}), 200

        lines = SecondaryLineSegment.query.filter(
            (SecondaryLineSegment.from_bus_id == secondary_bus_id) |
            (SecondaryLineSegment.to_bus_id == secondary_bus_id)
        ).all()

        to_bus_ids = set()
        for line in lines:
            if line.to_bus_id:
                to_bus_ids.add(line.to_bus_id)

        if not to_bus_ids:
            return jsonify({'count': 0, 'service_drops': []}), 200

        drops = SecondaryServiceDrop.query.filter(SecondaryServiceDrop.from_bus_id.in_(list(to_bus_ids))).all()

        return jsonify({
            'count': len(drops),
            'service_drops': [d.to_dict() for d in drops]
        }), 200

    except Exception as e:
        current_app.logger.warning('Failed to fetch service drops for post %s: %s', post_id, e)
        return jsonify({'count': 0, 'service_drops': [], 'error': str(e)}), 500

@api_bp.route('/posts/bulk-import', methods=['POST'])
@admin_required
def api_posts_bulk_import():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file:
        stats = import_posts_from_csv(file)
        # Attempt to infer conections after import
        try:
            conn_count = infer_connections_from_posts()
            stats['inferred_connections'] = conn_count
        except Exception as e:
            current_app.logger.error(f"Inference failed after import: {e}")
            stats['inferred_warnings'] = str(e)
            
        return jsonify(stats), 200
        
    return jsonify({'error': 'File processing failed'}), 500

@api_bp.route('/transformers/bulk-import', methods=['POST'])
@admin_required
def api_transformers_bulk_import():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file:
        stats = import_transformers_from_csv(file)
        return jsonify(stats), 200
    return jsonify({'error': 'File processing failed'}), 500

@api_bp.route('/secondary-lines/bulk-import', methods=['POST'])
@admin_required
def api_secondary_lines_bulk_import():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file:
        stats = import_secondary_lines_from_csv(file)
        return jsonify(stats), 200
    return jsonify({'error': 'File processing failed'}), 500

# User Management APIs
@api_bp.route('/users', methods=['GET', 'POST'])
@admin_required
def api_users():
    if request.method == 'GET':
        users = User.query.order_by(User.id.asc()).all()
        return jsonify([u.public_dict() for u in users])
    
    data = request.get_json(silent=True) or {}
    display_name = (data.get('display_name') or '').strip()
    username = (data.get('username') or '').strip()
    if not username and not display_name:
        return jsonify({'error': 'display_name (or username) required'}), 400

    if not username:
        import re
        base = re.sub(r'[^a-z0-9]+', '.', display_name.lower()).strip('.')
        base = base or 'viewer'
        username = base
        n = 2
        while User.query.filter_by(username=username).first() is not None:
            username = f"{base}-{n}"
            n += 1
            
    existing = User.query.filter_by(username=username).first()
    if existing: return jsonify({'error': 'username already exists'}), 400
    
    code = secrets.token_urlsafe(8)
    user = User(username=username, role='viewer', access_code=code, access_enabled=True)
    db.session.add(user)
    db.session.commit()
    return jsonify({'id': user.id, 'username': user.username, 'access_code': code, 'access_enabled': user.access_enabled}), 201

@api_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def api_user_delete(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'user not found'}), 404
    if user.role == 'admin':
        return jsonify({'error': 'cannot delete admin user'}), 403
    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify({'id': user.id, 'deleted': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/transformers/by-bus/<bus_id>', methods=['GET'])
def api_transformers_by_bus(bus_id):
    try:
        transformers = DistributionTransformer.query.filter_by(from_primary_bus_id=bus_id).all()
        return jsonify({
            'bus_id': bus_id,
            'count': len(transformers),
            'transformers': [t.to_dict() for t in transformers],
        }), 200
    except Exception as e:
        return jsonify({'error': str(e), 'bus_id': bus_id}), 500

@api_bp.route('/distribution-lines', methods=['GET'])
def api_distribution_lines():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        if page < 1: page = 1
        if per_page < 1 or per_page > 1000: per_page = 10

        query = DistributionLineSegment.query.order_by(DistributionLineSegment.id.asc())
        total = query.count()
        
        lines = query.offset((page - 1) * per_page).limit(per_page).all()
        total_pages = (total + per_page - 1) // per_page

        return jsonify({
            "data": [line.to_dict() for line in lines],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        })
    except Exception as e:
        return jsonify({"data": [], "error": str(e)}), 500

@api_bp.route('/secondary-lines', methods=['GET'])
def api_secondary_lines():
    try:
        lines = SecondaryLineSegment.query.order_by(SecondaryLineSegment.id.desc()).all()
        return jsonify([line.to_dict() for line in lines])
    except Exception as e:
        return jsonify([]), 200

@api_bp.route('/secondary-lines/by-bus/<bus_id>', methods=['GET'])
def api_secondary_lines_by_bus(bus_id):
    try:
        # correct logic: find lines where from_bus_id OR to_bus_id matches
        lines = SecondaryLineSegment.query.filter(
            (SecondaryLineSegment.from_bus_id == bus_id) | 
            (SecondaryLineSegment.to_bus_id == bus_id)
        ).all()
        
        return jsonify({
            'bus_id': bus_id,
            'count': len(lines),
            'secondary_lines': [l.to_dict() for l in lines]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e), 'bus_id': bus_id}), 500

@api_bp.route('/secondary-service-drops/bulk-import', methods=['POST'])
@admin_required
def api_service_drops_import():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        try:
            from utils.csv_importers import import_service_drops_from_csv
            stats = import_service_drops_from_csv(file)
            return jsonify({'message': 'Import completed', 'stats': stats}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@api_bp.route('/secondary-service-drops/by-bus/<bus_id>', methods=['GET'])
def api_service_drops_by_bus(bus_id):
    try:
        # Service Drops are linked via 'from_bus_id'
        # Import model inside function to avoid circular imports if necessary
        from models import SecondaryServiceDrop
        drops = SecondaryServiceDrop.query.filter_by(from_bus_id=bus_id).all()
        return jsonify({
            'bus_id': bus_id,
            'count': len(drops),
            'service_drops': [d.to_dict() for d in drops]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e), 'bus_id': bus_id}), 500

# --- RESTORED ENDPOINTS ---

@api_bp.route('/line-connections', methods=['GET'])
def api_line_connections():
    """Return all inferred line connections for visualization."""
    try:
        from models import LineConnection
        connections = LineConnection.query.all()
        return jsonify({'connections': [c.to_dict() for c in connections], 'count': len(connections)})
    except ImportError:
        # LineConnection model doesn't exist yet
        return jsonify({'connections': [], 'count': 0})
    except Exception as e:
        current_app.logger.error(f"Error fetching line connections: {e}")
        return jsonify({'error': str(e), 'connections': []}), 500

@api_bp.route('/network-geometry', methods=['GET'])
def api_network_geometry():
    """Return network geometry (lines and nodes) for map rendering."""
    try:
        from network_geometry_db import get_network_geometry
        # Pass current_app as the app context
        data = get_network_geometry(current_app)
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Error fetching network geometry: {e}")
        return jsonify({'error': str(e), 'lines': []}), 500

@api_bp.route('/latlongdata', methods=['GET'])
def api_latlongdata():
    """Return normalized rows from `latlongdata` table as JSON."""
    try:
        # Check if table exists/desc
        desc = db.session.execute(text('DESCRIBE latlongdata')).fetchall()
        col_names = [row[0] for row in desc]
        lower_cols = [c.lower() for c in col_names]
        expected = ['post_id', 'latitude', 'longitude']
        mapping = {}
        for name in expected:
            if name in lower_cols:
                mapping[name] = col_names[lower_cols.index(name)]

        if not all(k in mapping for k in expected):
            if len(col_names) < 3:
                return jsonify({'error': 'latlongdata must have at least 3 columns'}), 400
            mapping = {'post_id': col_names[0], 'latitude': col_names[1], 'longitude': col_names[2]}

        sql = text(f"SELECT `{mapping['post_id']}` AS post_id, `{mapping['latitude']}` AS latitude, `{mapping['longitude']}` AS longitude FROM latlongdata")
        rows = db.session.execute(sql).fetchall()

        out = []
        for r in rows:
            # Handle row access
            try:
                # Try mappings/attributes first
                pid = r.post_id if hasattr(r, 'post_id') else r[0]
                lat = r.latitude if hasattr(r, 'latitude') else r[1]
                lng = r.longitude if hasattr(r, 'longitude') else r[2]
            except:
                continue
                
            if pid is None and lat is None and lng is None:
                continue
            
            try:
                out.append({
                    'post_id': int(pid) if pid is not None else None, 
                    'lat': float(lat) if lat is not None else None, 
                    'lng': float(lng) if lng is not None else None
                })
            except:
                continue

        return jsonify(out)
    except Exception as e:
        # If table doesn't exist etc.
        current_app.logger.warning(f"Error fetching latlongdata: {e}")
        return jsonify([])

@api_bp.route('/data/delete-all', methods=['POST'])
def api_delete_all_data():
    """
    Permanently delete all data from all relevant models.
    Also resets auto-increment counters.
    """
    try:
        from models import (Post, DistributionTransformer, SecondaryLineSegment, 
                          DistributionLineSegment, SecondaryServiceDrop, UploadHistory, 
                          VoltageRegulator, ShuntCapacitor, ShuntInductor, SeriesInductor,
                          Customer, EnergyConsumption, Meter, LatLongData, BusPostMapping, LineConnection)
        
        # 1. Delete all rows (order matters for foreign keys if any, though most are soft-linked by ID strings)
        num_ec = db.session.query(EnergyConsumption).delete()
        num_cust = db.session.query(Customer).delete()
        num_v = db.session.query(VoltageRegulator).delete()
        num_sc = db.session.query(ShuntCapacitor).delete()
        num_si = db.session.query(ShuntInductor).delete()
        num_eri = db.session.query(SeriesInductor).delete()
        num_drops = db.session.query(SecondaryServiceDrop).delete()
        num_lines = db.session.query(SecondaryLineSegment).delete()
        num_dist_lines = db.session.query(DistributionLineSegment).delete()
        num_transformers = db.session.query(DistributionTransformer).delete()
        num_meters = db.session.query(Meter).delete()
        num_latlong = db.session.query(LatLongData).delete()
        num_bus_post = db.session.query(BusPostMapping).delete()
        num_line_conn = db.session.query(LineConnection).delete()
        num_posts = db.session.query(Post).delete()
        num_history = db.session.query(UploadHistory).delete() # Clear history log

        # 2. Reset Auto-Increment (MySQL specific)
        reset_status = "Skipped"
        try:
            if 'mysql' in str(db.engine.url):
                tables = [
                    'post', 'distribution_transformer', 'secondary_line_segment', 
                    'distribution_line_segment', 'secondary_service_drop', 'upload_history', 
                    'voltage_regulator', 'shunt_capacitor', 'shunt_inductor', 'series_inductor',
                    'customer', 'energy_consumption', 'meter', 'latlongdata', 
                    'bus_post_mapping', 'line_connection'
                ]
                for tbl in tables:
                     db.session.execute(text(f"ALTER TABLE {tbl} AUTO_INCREMENT = 1"))
                reset_status = "Reset to 1"
        except Exception as e:
             reset_status = f"Failed ({str(e)})"

        db.session.commit()
        
        return jsonify({
            'result': 'success',
            'message': f"Comprehensive Cleanup: Deleted {num_posts} Posts, {num_transformers} Transformers, {num_cust} Customers, {num_ec} Consumption Records, {num_meters} Meter Readings, and related infrastructure data.",
            'reset_status': reset_status
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/data/upload-history', methods=['GET'])
def api_upload_history():
    """
    Get the latest upload history for each file type.
    """
    try:
        from models import UploadHistory
        # Get latest successful upload for each type
        # We can fetch all and group in python for simplicity since volume is low
        history = UploadHistory.query.order_by(UploadHistory.upload_date.desc()).all()
        
        # Group by file_type, keeping only the most recent one
        latest = {}
        # Pre-initialize keys
        for k in ['posts', 'transformers', 'secondary_lines', 'service_drops', 'voltage_regulators', 'shunt_capacitors', 'shunt_inductors', 'series_inductors']:
            latest[k] = None

        for h in history:
            if h.file_type not in latest or latest[h.file_type] is None:
                latest[h.file_type] = h.to_dict()
        
        return jsonify(latest)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- New Asset Endpoints ---

# Voltage Regulators
@api_bp.route('/voltage-regulators/bulk-import', methods=['POST'])
@admin_required
def api_voltage_regulators_bulk_import():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and file.filename.lower().endswith('.csv'):
        stats = import_voltage_regulators_from_csv(file)
        if 'error' in stats:
            return jsonify(stats), 500
        return jsonify({'result': 'success', 'stats': stats})
    return jsonify({'error': 'Invalid file format'}), 400

@api_bp.route('/voltage-regulators/by-bus/<bus_id>', methods=['GET'])
def api_get_voltage_regulators_by_bus(bus_id):
    try:
        if not bus_id:
            return jsonify({'error': 'Bus ID required'}), 400
        # Check from_bus, to_bus, or regulated_bus
        items = VoltageRegulator.query.filter(
            (VoltageRegulator.from_bus_id == bus_id) | 
            (VoltageRegulator.to_bus_id == bus_id) | 
            (VoltageRegulator.regulated_bus_id == bus_id)
        ).all()
        return jsonify({'count': len(items), 'items': [x.to_dict() for x in items]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Shunt Capacitors
@api_bp.route('/shunt-capacitors/bulk-import', methods=['POST'])
@admin_required
def api_shunt_capacitors_bulk_import():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and file.filename.lower().endswith('.csv'):
        stats = import_shunt_capacitors_from_csv(file)
        if 'error' in stats:
            return jsonify(stats), 500
        return jsonify({'result': 'success', 'stats': stats})
    return jsonify({'error': 'Invalid file format'}), 400

@api_bp.route('/shunt-capacitors/by-bus/<bus_id>', methods=['GET'])
def api_get_shunt_capacitors_by_bus(bus_id):
    try:
        if not bus_id:
            return jsonify({'error': 'Bus ID required'}), 400
        items = ShuntCapacitor.query.filter_by(bus_connected_id=bus_id).all()
        return jsonify({'count': len(items), 'items': [x.to_dict() for x in items]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Shunt Inductors
@api_bp.route('/shunt-inductors/bulk-import', methods=['POST'])
@admin_required
def api_shunt_inductors_bulk_import():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and file.filename.lower().endswith('.csv'):
        stats = import_shunt_inductors_from_csv(file)
        if 'error' in stats:
            return jsonify(stats), 500
        return jsonify({'result': 'success', 'stats': stats})
    return jsonify({'error': 'Invalid file format'}), 400

@api_bp.route('/shunt-inductors/by-bus/<bus_id>', methods=['GET'])
def api_get_shunt_inductors_by_bus(bus_id):
    try:
        if not bus_id:
            return jsonify({'error': 'Bus ID required'}), 400
        items = ShuntInductor.query.filter_by(bus_connected_id=bus_id).all()
        return jsonify({'count': len(items), 'items': [x.to_dict() for x in items]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Series Inductors
@api_bp.route('/series-inductors/bulk-import', methods=['POST'])
@admin_required
def api_series_inductors_bulk_import():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and file.filename.lower().endswith('.csv'):
        stats = import_series_inductors_from_csv(file)
        if 'error' in stats:
            return jsonify(stats), 500
        return jsonify({'result': 'success', 'stats': stats})
    return jsonify({'error': 'Invalid file format'}), 400

@api_bp.route('/series-inductors/by-bus/<bus_id>', methods=['GET'])
def api_get_series_inductors_by_bus(bus_id):
    try:
        if not bus_id:
            return jsonify({'error': 'Bus ID required'}), 400
        items = SeriesInductor.query.filter(
            (SeriesInductor.from_bus_id == bus_id) | 
            (SeriesInductor.to_bus_id == bus_id)
        ).all()
        return jsonify({'count': len(items), 'items': [x.to_dict() for x in items]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Customer Routes ---
@api_bp.route('/customers/bulk-import', methods=['POST'])
@admin_required
def api_customers_bulk_import():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    if file:
        stats = import_customers_from_csv(file)
        return jsonify(stats), 200
    return jsonify({'error': 'File processing failed'}), 500

@api_bp.route('/energy-consumption/bulk-import', methods=['POST'])
@admin_required
def api_energy_consumption_bulk_import():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    if file:
        stats = import_energy_consumption_from_csv(file)
        return jsonify(stats), 200
    return jsonify({'error': 'File processing failed'}), 500

def find_customer_post_location(customer_id):
    """
    Traces the electrical network to find a customer's connected post.
    Chain: Customer → SSD(to_customer_id) → [BFS through SecondaryLineSegment] → DistributionTransformer → Post(primary_bus_id)
    Returns dict with lat, lng, id, name if found, else None.
    """
    try:
        # 1. Find the SecondaryServiceDrop for this customer
        ssd = SecondaryServiceDrop.query.filter_by(to_customer_id=customer_id).first()
        if not ssd or not ssd.from_bus_id:
            return None

        # 2. BFS from the SSD bus to find a DistributionTransformer
        start_bus = ssd.from_bus_id
        visited = set([start_bus])
        queue = [start_bus]
        
        # Check if the start_bus itself is directly connected to a transformer
        dt = DistributionTransformer.query.filter_by(to_secondary_bus_id=start_bus).first()
        
        # If not, traverse the secondary line segments
        while not dt and queue:
            current_bus = queue.pop(0)
            lines = SecondaryLineSegment.query.filter(
                (SecondaryLineSegment.from_bus_id == current_bus) |
                (SecondaryLineSegment.to_bus_id == current_bus)
            ).all()
            
            for line in lines:
                nxt = line.from_bus_id if line.to_bus_id == current_bus else line.to_bus_id
                if nxt not in visited:
                    visited.add(nxt)
                    dt = DistributionTransformer.query.filter_by(to_secondary_bus_id=nxt).first()
                    if dt:
                        break
                    queue.append(nxt)

        if dt and dt.from_primary_bus_id:
            # 3. Find the Post with matching primary_bus_id
            post = Post.query.filter_by(primary_bus_id=dt.from_primary_bus_id).first()
            if not post:
                # Fallback: Check if the primary bus ID matches a pole number directly
                post = Post.query.filter_by(pole_number=dt.from_primary_bus_id).first()
                
            if post and post.lat and post.lng:
                return {'lat': post.lat, 'lng': post.lng, 'id': post.id, 'name': post.name}

    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error tracing post location for customer {customer_id}: {e}")
        return None

    return None

@api_bp.route('/customers', methods=['GET'])
def get_customers():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        q = (request.args.get('q') or '').strip()

        if page < 1: page = 1
        if per_page < 1 or per_page > 1000: per_page = 10

        query = Customer.query
        if q:
            # Search by ID or Name
            term = f"%{q}%"
            query = query.filter((Customer.customer_id.ilike(term)) | (Customer.name.ilike(term)))
        
        # Consistent ordering
        query = query.order_by(Customer.customer_id.asc())
        
        total = query.count()
        items = query.offset((page - 1) * per_page).limit(per_page).all()
        total_pages = (total + per_page - 1) // per_page
        
        # Enrich with location data
        data = []
        for c in items:
            c_dict = c.to_dict()
            loc = find_customer_post_location(c.customer_id)
            if loc:
                c_dict['connected_post'] = loc
            data.append(c_dict)

        return jsonify({
            "data": data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        })
    except Exception as e:
        return jsonify({"data": [], "error": str(e)}), 500

@api_bp.route('/customers/<path:customer_id>', methods=['GET'])
def get_customer(customer_id):
    c = Customer.query.filter_by(customer_id=customer_id).first()
    if not c: return jsonify({'error': 'Customer not found'}), 404
    return jsonify(c.to_dict())

@api_bp.route('/customers/<path:customer_id>/location', methods=['GET'])
def get_customer_location(customer_id):
    """Get customer info and their connected post location for map display."""
    try:
        c = Customer.query.filter_by(customer_id=customer_id).first()
        if not c:
            return jsonify({'error': 'Customer not found', 'found': False}), 404
        
        # Get the post location serving this customer
        post_loc = find_customer_post_location(customer_id)
        
        result = {
            'found': True,
            'customer': c.to_dict(),
            'connected_post': post_loc if post_loc else None
        }
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e), 'found': False}), 500

@api_bp.route('/customers/<path:customer_id>/consumption', methods=['GET'])
def get_customer_consumption(customer_id):
    records = EnergyConsumption.query.filter_by(customer_id=customer_id).order_by(EnergyConsumption.billing_period.desc()).all()
    return jsonify({'items': [r.to_dict() for r in records]})


# --- Network Shortest Path (Dijkstra) ---

def _haversine_m(lat1, lng1, lat2, lng2):
    """Return distance in metres between two lat/lng points."""
    import math
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


@api_bp.route('/path', methods=['GET'])
def api_shortest_path():
    """
    Find the shortest ROAD path from the user's GPS location to the
    post that serves a given customer via OSRM.
    """
    try:
        customer_id = (request.args.get('customer_id') or '').strip()
        try:
            user_lat = float(request.args.get('user_lat'))
            user_lng = float(request.args.get('user_lng'))
        except (TypeError, ValueError):
            return jsonify({'error': 'Missing or invalid user_lat / user_lng'}), 400

        if not customer_id:
            return jsonify({'error': 'customer_id is required'}), 400

        # 1. Verify customer exists
        cust = Customer.query.filter_by(customer_id=customer_id).first()
        if not cust:
            return jsonify({'found': False, 'error': f'Customer "{customer_id}" not found.'}), 404

        # 2. Trace customer → destination post
        dest_info = find_customer_post_location(customer_id)
        if not dest_info:
            return jsonify({
                'found': False,
                'customer_id': customer_id,
                'customer_name': getattr(cust, 'name', 'Unknown'),
                'error': 'This customer is not linked to any electrical post on the map.'
            }), 200

        # 3. Call OSRM API for road-based routing
        # Origin: User GPS, Destination: Post GPS
        osm_url = f"https://routing.openstreetmap.de/routed-car/route/v1/driving/{user_lng},{user_lat};{dest_info['lng']},{dest_info['lat']}?overview=full&geometries=geojson"
        
        response = requests.get(osm_url, timeout=10)
        
        if response.status_code != 200:
            return jsonify({
                'found': False,
                'error': f'Road routing service unavailable (Status {response.status_code}).'
            }), 200
            
        res_data = response.json()
        if not res_data.get('routes'):
            return jsonify({
                'found': False,
                'customer_name': getattr(cust, 'name', 'Unknown'),
                'destination_post': dest_info,
                'error': 'No road path found to this customer\'s location.'
            }), 200
            
        route = res_data['routes'][0]
        geojson_coords = route['geometry']['coordinates']
        
        # Convert to [{lat, lng}, ...] for Leaflet
        path_nodes = [{'lat': c[1], 'lng': c[0]} for c in geojson_coords]
        
        return jsonify({
            'found': True,
            'customer_id': customer_id,
            'customer_name': getattr(cust, 'name', 'Juan dela Cruz'),
            'user_location': {'lat': user_lat, 'lng': user_lng},
            'destination_post': dest_info,
            'path': path_nodes,
            'total_distance_m': round(route['distance'], 1),
            'duration_sec': round(route['duration'], 0)
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'found': False, 
            'error': f'Internal Server Error: {str(e)}'
        }), 500


# --- Master CSV Export ---
@api_bp.route('/export/master.csv', methods=['GET'])
def export_master_csv():
    """
    Export a single comprehensive CSV with the full multi-hop chain flattened:
    Post -> Dist. Line -> Transformer -> Secondary Line -> Service Drop -> Customer -> kWh
    Each row = one complete chain path with all detail fields.
    """
    import csv
    from flask import Response
    from models import SecondaryServiceDrop
    from collections import defaultdict

    posts = Post.query.order_by(Post.id).all()
    pole_numbers = sorted(set(p.pole_number for p in posts if p.pole_number), key=len, reverse=True)

    # Dist lines by from_bus_id
    dist_by_from = defaultdict(list)
    for seg in DistributionLineSegment.query.all():
        dist_by_from[seg.from_bus_id].append(seg)

    # Transformers matched to pole_number by prefix
    tx_by_pole = defaultdict(list)
    for t in DistributionTransformer.query.all():
        bus = t.from_primary_bus_id or ''
        for pn in pole_numbers:
            if bus.startswith(pn):
                tx_by_pole[pn].append(t)
                break

    # Secondary lines by from_bus_id (= transformer's to_secondary_bus_id)
    sec_by_tx_sec_bus = defaultdict(list)
    for sl in SecondaryLineSegment.query.all():
        sec_by_tx_sec_bus[sl.from_bus_id].append(sl)

    # Service drops by from_bus_id (= secondary line to_bus_id)
    drops_by_bus = defaultdict(list)
    for d in SecondaryServiceDrop.query.all():
        drops_by_bus[d.from_bus_id].append(d)

    # Customers by customer_id
    cust_map = {c.customer_id: c for c in Customer.query.all()}

    # kWh per customer_id
    kwh_map = defaultdict(float)
    for ec in EnergyConsumption.query.all():
        if ec.kwh_consumed:
            kwh_map[ec.customer_id] += ec.kwh_consumed

    headers = [
        'Post ID', 'Pole Number', 'Post Name', 'Feeder', 'Post Phasing', 'Status',
        'Latitude', 'Longitude', 'Area', 'Primary Bus ID',
        'Dist Line Segment ID', 'Dist Line From Bus', 'Dist Line To Bus',
        'Dist Line Phasing', 'Dist Line Length (m)', 'Dist Line Conductor Type', 'Dist Line Conductor Size',
        'Transformer ID', 'TX From Primary Bus', 'TX To Secondary Bus',
        'TX Primary Phasing', 'TX Secondary Phasing', 'TX kVA Rating',
        'TX Primary V (kV)', 'TX Secondary V (kV)', 'TX Installation Type', 'TX Connection',
        'Sec Line Segment ID', 'Sec Line From Bus', 'Sec Line To Bus',
        'Sec Line Phasing', 'Sec Line Length (m)', 'Sec Line Conductor Type', 'Sec Line Conductor Size',
        'Service Drop ID', 'Drop From Bus', 'Drop To Customer ID',
        'Drop Phasing', 'Drop Install Type', 'Drop Length-1 (m)', 'Drop Length-2 (m)',
        'Customer ID', 'Customer Name', 'Customer Type', 'Service Voltage', 'Customer Phase',
        'Total kWh Consumed',
    ]

    def _v(val):
        return val if val is not None else ''

    EMPTY = [''] 

    def generate():
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(headers)
        yield out.getvalue(); out.seek(0); out.truncate(0)

        for p in posts:
            pole = p.pole_number or ''
            pc = [p.id, pole, _v(p.name), _v(p.feeder), _v(p.phasing), _v(p.status),
                  _v(p.lat), _v(p.lng), _v(p.area), _v(p.primary_bus_id)]
            dl = dist_by_from.get(pole, [None])[0]
            dc = [_v(dl.segment_id) if dl else '', _v(dl.from_bus_id) if dl else '',
                  _v(dl.to_bus_id) if dl else '', _v(dl.phasing) if dl else '',
                  _v(dl.length_meters) if dl else '', _v(dl.conductor_type) if dl else '',
                  _v(dl.conductor_size) if dl else '']

            txs = tx_by_pole.get(pole, [])
            if not txs:
                w.writerow(pc + dc + [''] * (len(headers) - len(pc) - len(dc)))
                yield out.getvalue(); out.seek(0); out.truncate(0)
                continue

            for t in txs:
                tc = [_v(t.transformer_id), _v(t.from_primary_bus_id), _v(t.to_secondary_bus_id),
                      _v(t.primary_phasing), _v(t.secondary_phasing), _v(t.kva_rating),
                      _v(t.primary_voltage_kv), _v(t.secondary_voltage_kv),
                      _v(t.installation_type), _v(t.connection)]

                slines = sec_by_tx_sec_bus.get(t.to_secondary_bus_id, [])
                if not slines:
                    w.writerow(pc + dc + tc + [''] * (len(headers) - len(pc) - len(dc) - len(tc)))
                    yield out.getvalue(); out.seek(0); out.truncate(0)
                    continue

                for sl in slines:
                    sc = [_v(sl.segment_id), _v(sl.from_bus_id), _v(sl.to_bus_id),
                          _v(sl.phasing), _v(sl.length_meters),
                          _v(sl.conductor_type), _v(sl.conductor_size)]

                    drops = drops_by_bus.get(sl.to_bus_id, [])
                    if not drops:
                        w.writerow(pc + dc + tc + sc + [''] * (len(headers) - len(pc) - len(dc) - len(tc) - len(sc)))
                        yield out.getvalue(); out.seek(0); out.truncate(0)
                        continue

                    for d in drops:
                        drc = [_v(d.service_drop_id), _v(d.from_bus_id), _v(d.to_customer_id),
                               _v(d.phasing), _v(d.installation_type),
                               _v(d.length_meters_1), _v(d.length_meters_2)]
                        cust = cust_map.get(d.to_customer_id)
                        cc = [_v(cust.customer_id) if cust else _v(d.to_customer_id),
                              _v(cust.name) if cust else '', _v(cust.customer_type) if cust else '',
                              _v(cust.service_voltage) if cust else '', _v(cust.phase) if cust else '']
                        kwh = round(kwh_map.get(d.to_customer_id, 0), 2)
                        w.writerow(pc + dc + tc + sc + drc + cc + [kwh])
                        yield out.getvalue(); out.seek(0); out.truncate(0)

    return Response(
        generate(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=master_export.csv'}
    )

