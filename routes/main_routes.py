from flask import Blueprint, render_template, redirect, url_for, session, g, request, jsonify
from functools import wraps
from models import Post, User

main_bp = Blueprint('main', __name__)

# --- Helpers ---
def get_current_user():
    uid = session.get('user_id')
    if not uid: return None
    try: return User.query.get(uid)
    except: return None

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not g.get('current_user'):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'authentication required'}), 401
            # Adjust redirect to auth.login
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        u = g.get('current_user')
        if not u or not u.is_admin():
            if request.path.startswith('/api/'):
                return jsonify({'error': 'admin required'}), 403
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return wrapper

# --- Routes ---

@main_bp.route('/')
def index():
    u = get_current_user()
    if u:
        return redirect(url_for('main.map_view'))
    return redirect(url_for('auth.login'))

@main_bp.route('/map')
@login_required
def map_view():
    return render_template('index.html', active_page='map')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    try:
        total = Post.query.count()
        in_ph = Post.query.filter(Post.lat >= 4.0, Post.lat <= 22.0, Post.lng >= 116.0, Post.lng <= 127.5).count()
        recent = Post.query.order_by(Post.id.desc()).all()
    except Exception:
        total = 0
        in_ph = 0
        recent = []
    return render_template('dashboard.html', active_page='dashboard', stats={'total': total, 'in_ph': in_ph}, posts=recent)

@main_bp.route('/seed', methods=['POST'])
def seed():
    from seed_db import seed_posts
    seed_posts()
    return redirect(url_for('main.dashboard'))

# Admin UI Pages
@main_bp.route('/admin/viewers')
@admin_required
def admin_viewers():
    viewers = User.query.filter_by(role='viewer').order_by(User.id.desc()).all()
    return render_template('admin_viewers.html', active_page='admin_viewers', viewers=viewers)

@main_bp.route('/resources')
@admin_required
def resources():
    return render_template('resources.html', active_page='resources')

@main_bp.route('/distribution-lines')
@admin_required
def distribution_lines():
    return render_template('distribution_lines.html', active_page='distribution_lines')

@main_bp.route('/predictions')
@login_required
def predictions():
    return render_template('predictions.html', active_page='predictions')
