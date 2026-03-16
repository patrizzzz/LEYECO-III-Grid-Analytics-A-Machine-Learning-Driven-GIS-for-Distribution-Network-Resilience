from flask import Blueprint, jsonify, request, g, current_app
from functools import wraps
import secrets
from extensions import db
from models import User

user_api_bp = Blueprint('user_api', __name__)

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        u = g.get('current_user')
        if not u or not u.is_admin():
            return jsonify({'error': 'admin required'}), 403
        return f(*args, **kwargs)
    return wrapper

@user_api_bp.route('/users', methods=['GET', 'POST'])
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

@user_api_bp.route('/users/<int:user_id>', methods=['DELETE'])
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
