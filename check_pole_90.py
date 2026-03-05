
from app import app
from models import Post, BusNode, DistributionTransformer
from extensions import db

def check_pole_90():
    with app.app_context():
        # Check Post table
        p90 = Post.query.filter((Post.pole_number == '90') | (Post.pole_number.like('%90%'))).all()
        print(f"Posts found with '90':")
        for p in p90:
            print(f"  Pole: {p.pole_number}, ID: {p.id}, Bus: {p.primary_bus_id}, L: {p.lat}, {p.lng}")
            
        # Check BusNode table
        bn90 = BusNode.query.filter(BusNode.pole_number.like('%90%')).all()
        print(f"BusNodes found with '90':")
        for bn in bn90:
            print(f"  Bus: {bn.bus_id}, Pole: {bn.pole_number}, L: {bn.lat}, {bn.lng}")

        # Check DT table
        dt90 = DistributionTransformer.query.filter(DistributionTransformer.transformer_id.like('%90%')).all()
        print(f"DTs found with '90':")
        for dt in dt90:
            print(f"  DT: {dt.transformer_id}, Primary Bus: {dt.from_primary_bus_id}, Secondary Bus: {dt.to_secondary_bus_id}")

check_pole_90()
