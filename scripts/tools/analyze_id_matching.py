
import re
from app import app
from models import Post, DistributionTransformer

def analyze():
    with app.app_context():
        txs = DistributionTransformer.query.all()
        posts_dict = {str(p.pole_number).strip().lower(): p for p in Post.query.all() if p.pole_number}
        posts_dict.update({str(p.primary_bus_id).strip().lower(): p for p in Post.query.all() if p.primary_bus_id})
        
        # Specific check for 138
        if '138' in posts_dict:
            print("Pole 138 exists in DB!")
            
        print("Checking TXs for '138' in ID...")
        for t in txs:
            if t.from_primary_bus_id and '138' in t.from_primary_bus_id:
                print(f"  Found TX with 138: {t.from_primary_bus_id}")

        matches = 0
        unmatched = []

        for t in txs:
            bus_id = str(t.from_primary_bus_id or "").strip()
            if not bus_id: continue
            
            matched = False
            parts = re.split(r'[^a-zA-Z0-9]', bus_id)
            parts = [p for p in parts if p]
            
            candidates = set()
            
            if len(parts) > 1:
                # Add exact last part
                candidates.add(parts[-1].lower())
                # Add stripped leading zeros
                candidates.add(parts[-1].lstrip('0').lower())
                # Add last part stripping trailing letters (e.g., 7A -> 7)
                m = re.match(r'^(\d+)[a-zA-Z]*$', parts[-1])
                if m:
                    candidates.add(m.group(1).lower())
                    candidates.add(m.group(1).lstrip('0').lower())
                
                # Check mid parts if they might be the pole (like P0000000034-7A -> maybe 34 is the pole?)
                candidates.add(parts[0].replace('P', '').lstrip('0').lower())
            else:
                m = re.search(r'\d+', bus_id)
                if m:
                    num_str = m.group(0)
                    candidates.add(num_str.lstrip('0').lower())
                    candidates.add(num_str.lower())
            
            for c in candidates:
                if c and c in posts_dict:
                    matches += 1
                    matched = True
                    break
            
            if not matched:
                unmatched.append(bus_id)
                
        print(f"Total TXs: {len(txs)}")
        print(f"Matches newly found: {matches}")
        print("Sample Unmatched:", unmatched[:20])

if __name__ == "__main__":
    analyze()
