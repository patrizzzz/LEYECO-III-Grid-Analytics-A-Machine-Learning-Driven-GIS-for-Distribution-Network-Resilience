
from app import app
from models import Post, BusNode
from extensions import db

def check_pole_184():
    with app.app_context():
        p184 = Post.query.filter_by(id=184).first()
        if p184:
            print(f"Post ID 184:")
            print(f"  Pole Number: {p184.pole_number}")
            print(f"  Primary Bus: {p184.primary_bus_id}")
            print(f"  Coords: {p184.lat}, {p184.lng}")
        else:
            print("Post ID 184 NOT FOUND")
            
        # Also check for any post with pole_number '184'
        p184n = Post.query.filter_by(pole_number='184').first()
        if p184n:
            print(f"Post with Pole Number '184':")
            print(f"  ID: {p184n.id}")
            print(f"  Primary Bus: {p184n.primary_bus_id}")
            
        # Check why P0000000090 matched ID 184
        p_bus = Post.query.filter((Post.primary_bus_id == 'P0000000090') | (Post.pole_number == 'P0000000090')).all()
        print(f"Posts matching P0000000090: {len(p_bus)}")
        for p in p_bus:
            print(f"  ID: {p.id}, Pole: {p.pole_number}, Bus: {p.primary_bus_id}")

check_pole_184()
