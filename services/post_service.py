from extensions import db
from models import Post
from flask import current_app

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
        db_posts = query.offset((page - 1) * per_page).limit(per_page).all()
        posts = [{"id": p.id, "name": p.name, "lat": p.lat, "lng": p.lng, "status": p.status, "kva_rating": p.kva_rating, "pole_number": p.pole_number} for p in db_posts]
        
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
        'created_at', 'updated_at'
    ]
    for f in extra_fields:
        post_dict[f] = getattr(p, f, None)
        
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
