from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, g
from werkzeug.security import check_password_hash, generate_password_hash
import secrets
from extensions import db
from models import User

auth_bp = Blueprint('auth', __name__)

# --- Helper to get current user ---
def get_current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    try:
        return User.query.get(uid)
    except Exception:
        return None

# --- Routes ---

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login for admins (username + password) and viewers (username + access_code)."""
    admin_exists = User.query.filter_by(role='admin').first() is not None
    if request.method == 'GET':
        if get_current_user():
            # Adjust redirect to main.dashboard
            return redirect(url_for('main.dashboard'))
        return render_template('login.html', admin_exists=admin_exists)

    data = request.get_json(silent=True) or request.form or {}
    username = (data.get('username') or '').strip()
    if not username:
        if request.form:
            return render_template('login.html', error='username required'), 400
        return jsonify({'error': 'username required'}), 400

    user = User.query.filter_by(username=username).first()
    if not user:
        if request.form:
            return render_template('login.html', error='Invalid credentials'), 401
        return jsonify({'error': 'invalid credentials'}), 401

    # Admins: password required
    if user.is_admin():
        pw = data.get('password')
        if not pw or not check_password_hash(user.password_hash or '', pw):
            if request.form:
                return render_template('login.html', error='Invalid credentials'), 401
            return jsonify({'error': 'invalid credentials'}), 401
    else:
        # Viewer: access code required and account enabled
        code = (data.get('access_code') or '').strip()
        if not code or not user.access_enabled or user.access_code != code:
            if request.form:
                return render_template('login.html', error='Invalid credentials or disabled account'), 401
            return jsonify({'error': 'invalid credentials or disabled account'}), 401

    # success: create login session
    session.clear()
    session['user_id'] = user.id
    session['role'] = user.role

    if request.form:
        return redirect(url_for('main.dashboard'))
    return jsonify({'result': 'ok', 'id': user.id, 'username': user.username, 'role': user.role})

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))

@auth_bp.route('/auth/whoami')
def whoami():
    u = get_current_user()
    if not u: return jsonify({'authenticated': False}), 200
    return jsonify({'authenticated': True, 'user': u.public_dict()})

@auth_bp.route('/setup/create-admin', methods=['POST'])
def setup_create_admin():
    data = request.get_json(silent=True) or request.form or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    if not username or not password:
        if request.form:
             return render_template('login.html', error='Username and password required', admin_exists=False), 400
        return jsonify({'error': 'username and password required'}), 400
    existing_admin = User.query.filter_by(role='admin').first()
    if existing_admin:
        if request.form:
             return render_template('login.html', error='Admin already exists', admin_exists=True), 400
        return jsonify({'error': 'admin already exists'}), 400
    pw_hash = generate_password_hash(password)
    u = User(username=username, role='admin', password_hash=pw_hash)
    db.session.add(u)
    db.session.commit()
    
    session.clear()
    session['user_id'] = u.id
    session['role'] = u.role

    if request.form:
        return redirect(url_for('main.dashboard'))
    return jsonify({'id': u.id, 'username': u.username, 'role': u.role}), 201


