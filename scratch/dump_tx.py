import os
import sys

# Add app directory to path
app_dir = r"c:\Users\Patrick\Downloads\zip file leyeco\leyeco3\leyeco3\leyeco3"
sys.path.append(app_dir)

from app import app
from models import DistributionTransformer, BusNode, Post

def dump_transformers(limit=20):
    with app.app_context():
        print(f"--- Dumping first {limit} Transformers ---")
        txs = DistributionTransformer.query.limit(limit).all()
        print(f"{'ID':<20} | {'Bus ID':<15} | {'Bus Lat':<12} | {'Bus Lng':<12} | {'Linked Post'}")
        print("-" * 80)
        for tx in txs:
            bn = BusNode.query.filter_by(bus_id=tx.from_primary_bus_id).first()
            lat = bn.lat if bn else "N/A"
            lng = bn.lng if bn else "N/A"
            
            post = Post.query.filter((Post.primary_bus_id == tx.from_primary_bus_id) | (Post.pole_number == tx.from_primary_bus_id)).first()
            post_str = f"ID:{post.id} ({post.pole_number})" if post else "None"
            
            print(f"{tx.transformer_id:<20} | {tx.from_primary_bus_id:<15} | {str(lat)[:10]:<12} | {str(lng)[:10]:<12} | {post_str}")

if __name__ == "__main__":
    dump_transformers()
