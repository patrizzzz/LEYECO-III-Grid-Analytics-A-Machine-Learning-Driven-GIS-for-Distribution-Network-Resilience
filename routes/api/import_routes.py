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
    LoadCurveImporter, VoltageRegulatorImporter, ShuntCapacitorImporter,
    ShuntInductorImporter, SeriesInductorImporter
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


@import_api_bp.route('/voltage-regulators/bulk-import', methods=['POST'])
@admin_required
def api_voltage_regulators_import():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    if file:
        stats = VoltageRegulatorImporter(file).run()
        return jsonify(stats), 200 if 'error' not in stats else 500
    return jsonify({'error': 'File processing failed'}), 500


@import_api_bp.route('/shunt-capacitors/bulk-import', methods=['POST'])
@admin_required
def api_shunt_capacitors_import():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    if file:
        stats = ShuntCapacitorImporter(file).run()
        return jsonify(stats), 200 if 'error' not in stats else 500
    return jsonify({'error': 'File processing failed'}), 500


@import_api_bp.route('/shunt-inductors/bulk-import', methods=['POST'])
@admin_required
def api_shunt_inductors_import():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    if file:
        stats = ShuntInductorImporter(file).run()
        return jsonify(stats), 200 if 'error' not in stats else 500
    return jsonify({'error': 'File processing failed'}), 500


@import_api_bp.route('/series-inductors/bulk-import', methods=['POST'])
@admin_required
def api_series_inductors_import():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'No selected file'}), 400
    if file:
        stats = SeriesInductorImporter(file).run()
        return jsonify(stats), 200 if 'error' not in stats else 500
    return jsonify({'error': 'File processing failed'}), 500


@import_api_bp.route('/data/upload-history', methods=['GET'])
def api_upload_history():
    try:
        history = UploadHistory.query.order_by(UploadHistory.upload_date.desc()).all()
        # Summary for the dashboard/resources main view
        summary = {k: None for k in ['bus_nodes', 'posts', 'primary_lines', 'transformers', 'secondary_lines', 'service_drops', 'voltage_regulators', 'shunt_capacitors', 'shunt_inductors', 'series_inductors', 'customers', 'energy_consumption', 'load_curves']}
        for h in history:
            if h.file_type in summary and summary[h.file_type] is None:
                summary[h.file_type] = h.to_dict()
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@import_api_bp.route('/data/upload-history-full', methods=['GET'])
@admin_required
def api_upload_history_full():
    try:
        history = UploadHistory.query.order_by(UploadHistory.upload_date.desc()).all()
        return jsonify([h.to_dict() for h in history])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@import_api_bp.route('/data/upload/<int:upload_id>', methods=['DELETE'])
@admin_required
def api_delete_upload(upload_id):
    try:
        h = UploadHistory.query.get(upload_id)
        if not h:
            return jsonify({'error': 'Upload not found'}), 404
            
        # Define tables to clean up
        models_to_clean = [
            EnergyConsumption, Customer, SecondaryServiceDrop, SecondaryLineSegment, 
            DistributionLineSegment, DistributionTransformer, 
            VoltageRegulator, ShuntCapacitor, ShuntInductor, SeriesInductor,
            BusNode, Post, LoadCurve
        ]
        
        counts = {}
        for model in models_to_clean:
            # Delete records associated with this upload
            deleted = model.query.filter_by(upload_id=upload_id).delete()
            counts[model.__tablename__] = deleted
            
        # For Post, we might need to reset has_transformer flags on other posts if tx were deleted
        # But for now, let's keep it simple: if the post is deleted, the tx is gone anyway.
        
        db.session.delete(h)
        db.session.commit()
        
        return jsonify({
            'result': 'success', 
            'message': f"Deleted upload {upload_id} and associated records",
            'deleted_counts': counts
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to delete upload {upload_id}: {e}")
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
