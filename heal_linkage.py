
import re
from app import app
from extensions import db
from models import Post, DistributionTransformer

def heal():
    with app.app_context():
        print("Starting smart linkage repair...")
        transformers = DistributionTransformer.query.all()
        posts = Post.query.all()
        
        # Create lookups
        post_by_pole = {str(p.pole_number).strip().lower(): p for p in posts if p.pole_number}
        post_by_bus = {str(p.primary_bus_id).strip().lower(): p for p in posts if p.primary_bus_id}
        
        count = 0
        for t in transformers:
            bus_id = str(t.from_primary_bus_id or "").strip()
            if not bus_id: continue
            
            key = bus_id.lower()
            p = post_by_bus.get(key) or post_by_pole.get(key)
            
            if not p:
                # Try numeric fallback: P00000001-7 -> 1
                match = re.search(r'P0*(\d+)', bus_id)
                if match:
                    num = match.group(1).lower()
                    p = post_by_bus.get(num) or post_by_pole.get(num)
            
            if p:
                p.kva_rating = t.kva_rating
                p.transformer_bus_id = t.from_primary_bus_id
                count += 1
        
        db.session.commit()
        print(f"Smart repair complete! Linked {count} transformers to posts.")

if __name__ == "__main__":
    heal()
