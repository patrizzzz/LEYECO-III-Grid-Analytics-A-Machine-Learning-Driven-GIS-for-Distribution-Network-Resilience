
from app import app
from models import BusNode, Post
from extensions import db

def check_bus_node():
    with app.app_context():
        bus = "S000090-0000011"
        bn = BusNode.query.filter_by(bus_id=bus).first()
        if bn:
            print(f"BusNode for {bus}:")
            print(f"  Pole Number: {bn.pole_number}")
            print(f"  Lat/Lng: {bn.lat}, {bn.lng}")
            
            if bn.pole_number:
                p = Post.query.filter_by(pole_number=bn.pole_number).first()
                if p:
                    print(f"  Mapped Post ID: {p.id}")
                    print(f"  Mapped Post Number: {p.pole_number}")
        else:
            print(f"No BusNode for {bus}")

check_bus_node()
