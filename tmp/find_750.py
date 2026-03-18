import sys
import os
sys.path.append(os.getcwd())

from app import app
from extensions import db
from models.assets import Post, DistributionTransformer

def find_pole_107():
    with app.app_context():
        print("Searching for Pole P000000106A...")
        
        p = Post.query.filter_by(pole_number='P000000106A').first()
        if p:
            print(f"Found Post - ID: {p.id}, Pole: {p.pole_number}, kVA: {p.kva_rating}")
        else:
            print("Pole P000000106A not found. Searching by name like 107...")
            p2 = Post.query.filter(Post.name.ilike('%107%')).first()
            if p2:
                print(f"Found Post by name - ID: {p2.id}, Pole: {p2.pole_number}, kVA: {p2.kva_rating}")
            else:
                print("No post found.")

if __name__ == "__main__":
    find_pole_107()
