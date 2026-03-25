
from app import app
from models import BusNode, Post
from extensions import db

def check_bus_p00000():
    with app.app_context():
        # Check BusNode table
        bn = BusNode.query.filter_by(bus_id='P00000').all()
        print(f"BusNodes with bus_id='P00000': {len(bn)}")
        for b in bn:
            print(f"  Pole: {b.pole_number}, Lat: {b.lat}, Lng: {b.lng}")
            
        # Check Post table
        p = Post.query.filter((Post.primary_bus_id == 'P00000') | (Post.pole_number == 'P00000')).all()
        print(f"Posts with ID/Bus='P00000': {len(p)}")
        for post in p:
            print(f"  Pole: {post.pole_number}, Bus: {post.primary_bus_id}, Lat: {post.lat}, Lng: {post.lng}")

check_bus_p00000()
