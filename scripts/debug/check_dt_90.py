
from app import app
from models import DistributionTransformer, BusNode, Post
from extensions import db

def check_dt_90():
    with app.app_context():
        # Get DT
        dt = DistributionTransformer.query.filter_by(transformer_id='DT0000000090U').first()
        if dt:
            print(f"DT: {dt.transformer_id}")
            print(f"  From Primary Bus: {dt.from_primary_bus_id}")
            print(f"  To Secondary Bus: {dt.to_secondary_bus_id}")
            
            # Check BusNode for the primary bus
            bn = BusNode.query.filter_by(bus_id=dt.from_primary_bus_id).first()
            if bn:
                print(f"BusNode for {dt.from_primary_bus_id}:")
                print(f"  Pole: {bn.pole_number}, Lat: {bn.lat}, Lng: {bn.lng}")
            else:
                print(f"NO BusNode found for {dt.from_primary_bus_id}")
                
            # Check Post for the primary bus
            p = Post.query.filter((Post.primary_bus_id == dt.from_primary_bus_id) | (Post.pole_number == dt.from_primary_bus_id)).first()
            if p:
                print(f"Post for {dt.from_primary_bus_id}:")
                print(f"  Pole: {p.pole_number}, Lat: {p.lat}, Lng: {p.lng}")
            else:
                print(f"NO Post found for {dt.from_primary_bus_id}")

        # Search for Pole 90 specifically
        p90 = Post.query.filter_by(pole_number='90').first()
        if p90:
            print(f"Post 90:")
            print(f"  Bus ID: {p90.primary_bus_id}")
            print(f"  Coords: {p90.lat}, {p90.lng}")

check_dt_90()
