from app import app
from models import ShuntCapacitor, BusNode, Post
from extensions import db
import json

def diagnose():
    with app.app_context():
        results = {}
        
        # 1. Check Post 120 details
        p120 = Post.query.filter_by(pole_number='120').first()
        if p120:
            results['post_120'] = {
                'id': p120.id,
                'pole_number': p120.pole_number,
                'primary_bus_id': p120.primary_bus_id,
                'sec_bus_id': p120.sec_bus_id,
                'transformer_bus_id': p120.transformer_bus_id,
            }
        else:
            results['post_120'] = 'NOT FOUND'

        # 2. Check ALL BusNode entries for pole 120
        bns = BusNode.query.filter_by(pole_number='120').all()
        results['bus_nodes_120'] = [{'bus_id': bn.bus_id, 'pole_number': bn.pole_number} for bn in bns]
        
        # 3. Check total capacitors
        total = ShuntCapacitor.query.count()
        results['total_capacitors'] = total
        
        # 4. All unique bus_connected_id values (first 20)
        caps = ShuntCapacitor.query.limit(20).all()
        results['sample_cap_buses'] = [c.bus_connected_id for c in caps]
        
        # 5. Check what the frontend would actually send for pole 120
        if p120:
            bus_id_sent = p120.primary_bus_id or p120.pole_number
            results['frontend_would_send'] = bus_id_sent

        with open('diagnose_full_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print("Done. Results saved to diagnose_full_results.json")

if __name__ == "__main__":
    diagnose()
