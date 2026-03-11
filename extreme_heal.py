
import pandas as pd
from app import app
from extensions import db
from models import Post, DistributionTransformer
import re

def extreme_heal():
    print("Loading bus_data.csv mappings...")
    try:
        bus_df = pd.read_csv('bus_data.csv')
        # Create a mapping from Bus ID matching variants to post_id
        # We need to map string matches because Bus ID is like "P0000000108-45H" and post_id is "138"
        bus_map = {}
        for _, row in bus_df.iterrows():
            bus_id = str(row['Bus ID']).strip().lower()
            post_id = str(row['post_id']).strip().lower()
            if bus_id and post_id and post_id != 'nan':
                bus_map[bus_id] = post_id
        print(f"Loaded {len(bus_map)} explicit bus mappings.")
    except Exception as e:
        print(f"Warning: Could not load bus_data.csv: {e}")
        bus_map = {}

    with app.app_context():
        # Clear old linkages to ensure pure matching
        conn = db.engine.connect()
        conn.execute(db.text("UPDATE post SET kva_rating = NULL, transformer_bus_id = NULL"))
        conn.commit()
        
        transformers = DistributionTransformer.query.all()
        posts = Post.query.all()
        
        post_by_pole = {str(p.pole_number).strip().lower(): p for p in posts if p.pole_number}
        post_by_bus = {str(p.primary_bus_id).strip().lower(): p for p in posts if p.primary_bus_id}
        
        count = 0
        for t in transformers:
            # 1. Check primary bus
            buses_to_check = [str(t.from_primary_bus_id or "").strip(), str(t.to_secondary_bus_id or "").strip()]
            
            p = None
            for bus_id in buses_to_check:
                if not bus_id: continue
                
                key = bus_id.lower()
                
                # Check direct mapping
                p = post_by_bus.get(key) or post_by_pole.get(key)
                
                # Check bus_map mapping
                if not p and key in bus_map:
                    mapped_post_id = bus_map[key]
                    p = post_by_pole.get(mapped_post_id) or post_by_bus.get(mapped_post_id)
                
                # Check regex variants
                if not p:
                    parts = re.split(r'[^a-zA-Z0-9]', bus_id)
                    parts = [part for part in parts if part]
                    
                    candidates = set()
                    if len(parts) > 1:
                        candidates.add(parts[-1].lower())
                        candidates.add(parts[-1].lstrip('0').lower())
                        m = re.match(r'^(\d+)[a-zA-Z]*$', parts[-1])
                        if m:
                            candidates.add(m.group(1).lower())
                            candidates.add(m.group(1).lstrip('0').lower())
                        candidates.add(parts[0].replace('P', '').replace('p', '').lstrip('0').lower())
                    else:
                        m = re.search(r'\d+', bus_id)
                        if m:
                            num_str = m.group(0)
                            candidates.add(num_str.lstrip('0').lower())
                            candidates.add(num_str.lower())
                    
                    for c in candidates:
                        p = post_by_bus.get(c) or post_by_pole.get(c)
                        if not p and c in bus_map: # chain through map
                            mapped = bus_map[c]
                            p = post_by_pole.get(mapped) or post_by_bus.get(mapped)
                        if p:
                            break
                            
                if p:
                    # Found a post!
                    break
                    
            if p:
                p.kva_rating = t.kva_rating
                # Let's assign the transformer_bus_id explicitly as primary to maintain consistency locally
                p.transformer_bus_id = t.from_primary_bus_id or t.to_secondary_bus_id
                count += 1
                if str(p.pole_number) == '138':
                    print(f"SUCCESS: Link found for POLE 138 using Transformer {t.transformer_id}")
        
        db.session.commit()
        print(f"Extreme heal complete! Linked {count} transformers.")

if __name__ == "__main__":
    extreme_heal()
