from extensions import db
from models import Post
from flask import current_app
from .ml_predictor import load_snapshot

# Sample in-memory posts fallback
POSTS = [
    {"id": 1, "name": "Pole A", "lat": 14.5995, "lng": 120.9842, "status": "Active"},
    {"id": 2, "name": "Pole B", "lat": 14.6091, "lng": 121.0223, "status": "Active"},
]

def create_post(data):
    """Creates a new post in the database."""
    name = (data.get('name') or '').strip()
    if not name:
        raise ValueError("name is required")
    
    try:
        lat = float(data.get('lat'))
        lng = float(data.get('lng'))
    except (TypeError, ValueError):
        raise ValueError("lat and lng must be numbers")
        
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError("lat/lng out of range")
        
    status = (data.get('status') or '').strip() or None
    area = (data.get('area') or '').strip() or None
    
    post = Post(name=name, lat=lat, lng=lng, status=status, area=area)
    db.session.add(post)
    db.session.commit()
    
    return {
        'id': post.id,
        'name': post.name,
        'lat': post.lat,
        'lng': post.lng,
        'status': post.status,
    }

def get_paginated_posts(in_ph, page, per_page):
    """Fetches paginated posts, optionally filtering by Philippines bounds."""
    try:
        query = Post.query
        if in_ph:
            query = query.filter(Post.lat >= 4.0, Post.lat <= 22.0, Post.lng >= 116.0, Post.lng <= 127.5)
        
        total = query.count()
        db_posts = query.order_by(Post.id.asc()).offset((page - 1) * per_page).limit(per_page).all()
        posts = [{"id": p.id, "name": p.name, "lat": p.lat, "lng": p.lng, "status": p.status, "kva_rating": p.kva_rating, "pole_number": p.pole_number, "pole_num": p.pole_num, "feeder": p.feeder, "primary_bus_id": p.primary_bus_id, "has_transformer": p.has_transformer, "transformer_bus_id": p.transformer_bus_id} for p in db_posts]
        
        total_pages = (total + per_page - 1) // per_page
        
        return {
            "data": posts,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
    except Exception as e:
        if current_app.debug:
            raise e
        pass
    
    # Fallback to in-memory
    fallback_posts = POSTS
    if in_ph:
        fallback_posts = [p for p in POSTS if p['lat'] >= 4.0 and p['lat'] <= 22.0 and p['lng'] >= 116.0 and p['lng'] <= 127.5]
    
    total = len(fallback_posts)
    total_pages = (total + per_page - 1) // per_page
    paginated_posts = fallback_posts[(page - 1) * per_page:page * per_page]
    
    return {
        "data": paginated_posts,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    }

def _normalize_asset_id(s):
    """Normalize asset IDs for comparison (e.g., P0000000088 -> 88)."""
    if not s: return ""
    s = str(s).upper().strip()
    # Remove common prefixes
    if s.startswith('DT'): s = s[2:]
    elif s.startswith('P'): s = s[1:]
    # Remove common suffixes and leading zeros
    if s.endswith('U'): s = s[:-1]
    s = s.lstrip('0')
    # Use split to handle complex IDs like 100-85U
    if '-' in s: s = s.split('-')[0]
    return s

def get_post_detail(post_id):
    """Fetches detailed information about a single post."""
    p = Post.query.get(post_id)
    if not p:
        return None
        
    post_dict = p.to_dict()
    meters = []
    for m in getattr(p, 'meters', []):
        meters.append({
            'id': m.id, 'meter_id': m.meter_id, 'meter_brand': m.meter_brand,
            'meter_rating': m.meter_rating, 'kwhr_reading': m.kwhr_reading,
            'reading_date': m.reading_date.isoformat() if m.reading_date else None,
        })
    post_dict['meters'] = meters
    
    extra_fields = [
        'pri_structure', 'pri_conductor_size', 'neutral_wire', 'configuration',
        'primary_bus_id', 'sec_structure', 'sec_conductor_size', 'sec_type',
        'conductor_type', 'sec_bus_id', 'common_sole', 'transformer_bus_id',
        'transformer_phasing', 'grounding_rod', 'l2_wire_type', 'l1_wire_type',
        'system_grounding_type', 'length_meters', 'conductor_unit', 'conductor_strands',
        'neutral_wire_type', 'neutral_wire_size', 'neutral_wire_unit', 'neutral_wire_strands',
        'spacing_d12', 'spacing_d23', 'spacing_d13', 'spacing_d1n', 'spacing_d2n', 'spacing_d3n',
        'spacing_dc1_c2', 'height_h1', 'height_h2', 'height_h3', 'height_hn', 'earth_resistivity',
        'created_at', 'updated_at'
    ]
    for f in extra_fields:
        post_dict[f] = getattr(p, f, None)

    # Enrich with BusNode data (Bus ID, Nominal Voltage, Feeder)
    from models import BusNode
    # Try exact pole_number match first
    bus_node = None
    if p.pole_number:
        bus_node = BusNode.query.filter_by(bus_id=p.pole_number).first()
    
    # Fallback: look for ANY bus node linked to this post ID
    if not bus_node:
        bus_node = BusNode.query.filter_by(pole_id=p.id).first()
        
    if bus_node:
        post_dict['bus_id'] = bus_node.bus_id
        post_dict['nominal_voltage'] = bus_node.nominal_voltage
        post_dict['bus_description'] = bus_node.bus_description
        if not post_dict.get('feeder'):
            post_dict['feeder'] = bus_node.feeder
    
    # Enrich with Stress Analysis Data
    try:
        snapshot = load_snapshot()
        if snapshot and 'details' in snapshot:
            # 1. Collect potential matches from DB record
            db_ids = {p.transformer_bus_id, p.primary_bus_id, p.pole_number}
            db_norms = {_normalize_asset_id(i) for i in db_ids if i}
            
            stress_match = None
            # 2. Search snapshot for first normalized match
            for detail in snapshot['details']:
                t_id = detail.get('transformer_id')
                pb_id = detail.get('from_primary_bus_id')
                
                # Check exact matches first
                if (t_id and t_id in db_ids) or (pb_id and pb_id in db_ids):
                    stress_match = detail
                    break
                
                # Check normalized (fuzzy) matches
                t_norm = _normalize_asset_id(t_id)
                pb_norm = _normalize_asset_id(pb_id)
                if (t_norm and t_norm in db_norms) or (pb_norm and pb_norm in db_norms):
                    stress_match = detail
                    break
            
            if stress_match:
                post_dict['utilization_percent'] = stress_match.get('utilization_percent', 0)
                post_dict['load_status'] = stress_match.get('load_status', 'Unknown')
                post_dict['risk_level'] = stress_match.get('risk_level', 'Low')
                post_dict['ml_risk_level'] = stress_match.get('ml_risk_level', 'Low')
                post_dict['impact_level'] = stress_match.get('impact_level', 'Low')
                post_dict['criticality_score'] = stress_match.get('criticality_score', 0)
    except Exception as e:
        current_app.logger.warning(f"Failed to enrich post {post_id} with stress data: {e}")
        
    return post_dict

def update_post(post_id, data):
    """Updates a post's properties."""
    p = Post.query.get(post_id)
    if not p:
        raise ValueError("Post not found")
        
    if 'lat' in data: p.lat = float(data['lat'])
    if 'lng' in data: p.lng = float(data['lng'])
    if 'status' in data: p.status = (data['status'] or '').strip() or None
    
    db.session.commit()
    return {'id': p.id, 'name': p.name, 'lat': p.lat, 'lng': p.lng, 'status': p.status}

def delete_post(post_id):
    """Deletes a post."""
    p = Post.query.get(post_id)
    if not p:
        raise ValueError("Post not found")
        
    db.session.delete(p)
    db.session.commit()
    return True

def search_posts(query_str, limit=10):
    """Search for posts by pole_number, name, or primary_bus_id."""
    if not query_str:
        return []
        
    search = f"%{query_str}%"
    results = Post.query.filter(
        (Post.pole_number.ilike(search)) |
        (Post.name.ilike(search)) |
        (Post.primary_bus_id.ilike(search))
    ).limit(limit).all()
    
    return [
        {
            "id": p.id,
            "pole_number": p.pole_number,
            "name": p.name,
            "lat": p.lat,
            "lng": p.lng,
            "feeder": p.feeder,
            "primary_bus_id": p.primary_bus_id
        }
        for p in results
    ]
