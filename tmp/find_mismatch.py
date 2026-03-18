import os
from services.ml_predictor import load_snapshot
from app import app
from models import Post

def find_mismatch():
    with app.app_context():
        # Searching for the pole near these coordinates: 11.299208, 124.675303
        snapshot = load_snapshot()
        p = Post.query.filter(Post.lat.between(11.2991, 11.2993), Post.lng.between(124.6752, 124.6754)).first()
        if p:
            print(f"Pole {p.pole_number} (ID: {p.id})")
            print(f"Transformer Bus: {p.transformer_bus_id}")
            print(f"Primary Bus: {p.primary_bus_id}")
            
            # Use same matching logic as in post_service
            from services.post_service import _normalize_asset_id
            db_ids = {p.transformer_bus_id, p.primary_bus_id, p.pole_number}
            db_norms = {_normalize_asset_id(i) for i in db_ids if i}
            
            stress_match = None
            if snapshot and 'details' in snapshot:
                for detail in snapshot['details']:
                    t_id = detail.get('transformer_id')
                    pb_id = detail.get('from_primary_bus_id')
                    
                    if (t_id and t_id in db_ids) or (pb_id and pb_id in db_ids):
                        stress_match = detail
                        break
                    
                    t_norm = _normalize_asset_id(t_id)
                    pb_norm = _normalize_asset_id(pb_id)
                    if (t_norm and t_norm in db_norms) or (pb_norm and pb_norm in db_norms):
                        stress_match = detail
                        break
            
            if stress_match:
                print(f"Stress Data Match: {stress_match['transformer_id']}")
                print(f"Utilization: {stress_match.get('utilization_percent')}%")
                print(f"Status: {stress_match.get('load_status')}")
                print(f"Risk Level: {stress_match.get('risk_level')}")
                print(f"Risk Score: {stress_match.get('risk_score', 'N/A')}")
                # Print full detail for audit
                print(f"Full Data: {stress_match}")
            else:
                print("No stress data match found.")
        else:
            print("No pole found at those coordinates.")

if __name__ == '__main__':
    find_mismatch()
