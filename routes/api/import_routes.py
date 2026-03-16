from flask import Blueprint, jsonify, request, g, current_app
from functools import wraps
from extensions import db
from sqlalchemy import text
from models import (
    UploadHistory, Post, DistributionTransformer, SecondaryLineSegment, 
    DistributionLineSegment, SecondaryServiceDrop, 
    VoltageRegulator, ShuntCapacitor, ShuntInductor, SeriesInductor,
    Customer, EnergyConsumption, Meter, LatLongData, BusPostMapping, LineConnection, BusNode
)
from utils.network_utils import infer_connections_from_posts
from services.importers import (
    PostImporter, TransformerImporter, SecondaryLineImporter, ServiceDropImporter,
    CustomerImporter, ConsumptionImporter, BusNodeImporter, PrimaryLineImporter,
    LoadCurveImporter
)

import_api_bp = Blueprint('import_api', __name__)

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        u = g.get('current_user')
        if not u or not u.is_admin():
            return jsonify({'error': 'admin required'}), 403
        return f(*args, **kwargs)
    return wrapper

@import_api_bp.route('/posts/bulk-import', methods=['POST'])
@admin_required
def api_posts_bulk_import():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    if file:
        stats = PostImporter(file).run()
        if 'error' in stats: return jsonify(stats), 500
        try:
            conn_count = infer_connections_from_posts()
            stats['inferred_connections'] = conn_count
        except Exception as e:
            current_app.logger.error(f"Inference failed after import: {e}")
            stats['inferred_warnings'] = str(e)
        return jsonify(stats), 200
    return jsonify({'error': 'File processing failed'}), 500

@import_api_bp.route('/primary-lines/bulk-import', methods=['POST'])
@admin_required
def api_primary_lines_bulk_import():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    if file:
        stats = PrimaryLineImporter(file).run()
        return jsonify(stats), 200 if 'error' not in stats else 500
    return jsonify({'error': 'File processing failed'}), 500

@import_api_bp.route('/bus-nodes/bulk-import', methods=['POST'])
@admin_required
def api_bus_nodes_bulk_import():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    if file:
        stats = BusNodeImporter(file).run()
        if 'error' in stats: return jsonify(stats), 500
        return jsonify({
            'result': 'success',
            'message': f"Imported {stats['created']} new poles, updated {stats['updated']} existing. "
                       f"Skipped {stats['skipped']}.",
            'stats': stats
        }), 200
    return jsonify({'error': 'File processing failed'}), 500

@import_api_bp.route('/transformers/bulk-import', methods=['POST'])
@admin_required
def api_transformers_bulk_import():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    if file:
        stats = TransformerImporter(file).run()
        return jsonify(stats), 200 if 'error' not in stats else 500
    return jsonify({'error': 'File processing failed'}), 500

@import_api_bp.route('/secondary-lines/bulk-import', methods=['POST'])
@admin_required
def api_secondary_lines_bulk_import():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    if file:
        stats = SecondaryLineImporter(file).run()
        return jsonify(stats), 200 if 'error' not in stats else 500
    return jsonify({'error': 'File processing failed'}), 500

@import_api_bp.route('/secondary-service-drops/bulk-import', methods=['POST'])
@admin_required
def api_service_drops_import():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    if file:
        stats = ServiceDropImporter(file).run()
        return jsonify({'message': 'Import completed', 'stats': stats}), 200 if 'error' not in stats else 500
    return jsonify({'error': 'File processing failed'}), 500

@import_api_bp.route('/customers/bulk-import', methods=['POST'])
@admin_required
def api_customers_bulk_import():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    if file:
        stats = CustomerImporter(file).run()
        return jsonify(stats), 200 if 'error' not in stats else 500
    return jsonify({'error': 'File processing failed'}), 500

@import_api_bp.route('/energy-consumption/bulk-import', methods=['POST'])
@admin_required
def api_energy_consumption_bulk_import():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    if file:
        stats = ConsumptionImporter(file).run()
        return jsonify(stats), 200 if 'error' not in stats else 500
    return jsonify({'error': 'File processing failed'}), 500

@import_api_bp.route('/load-curves/bulk-import', methods=['POST'])
@admin_required
def api_load_curves_bulk_import():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    if file:
        stats = LoadCurveImporter(file).run()
        return jsonify(stats), 200 if 'error' not in stats else 500
    return jsonify({'error': 'File processing failed'}), 500

@import_api_bp.route('/data/upload-history', methods=['GET'])
def api_upload_history():
    try:
        history = UploadHistory.query.order_by(UploadHistory.upload_date.desc()).all()
        latest = {k: None for k in ['bus_nodes', 'posts', 'primary_lines', 'transformers', 'secondary_lines', 'service_drops', 'voltage_regulators', 'shunt_capacitors', 'shunt_inductors', 'series_inductors', 'customers', 'energy_consumption', 'load_curves']}
        for h in history:
            if h.file_type in latest and latest[h.file_type] is None:
                latest[h.file_type] = h.to_dict()
        return jsonify(latest)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@import_api_bp.route('/data/delete-all', methods=['POST'])
@admin_required
def api_delete_all_data():
    try:
        # Using TRUNCATE with RESTART IDENTITY CASCADE ensures that all primary key sequences 
        # are reset to 1 and all related data is removed efficiently.
        tables = [
            'energy_consumption', 'customer', 'secondary_service_drop', 'secondary_line_segment', 
            'distribution_line_segment', 'line_connection', 'distribution_transformer', 
            'voltage_regulator', 'shunt_capacitor', 'shunt_inductor', 'series_inductor', 
            'meter', 'latlongdata', 'bus_post_mapping', 'bus_node', 'post', 'load_curve', 'upload_history'
        ]
        truncate_query = f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"
        db.session.execute(text(truncate_query))
        db.session.commit()
        return jsonify({'result': 'success', 'message': 'All data deleted and IDs reset to 1'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
