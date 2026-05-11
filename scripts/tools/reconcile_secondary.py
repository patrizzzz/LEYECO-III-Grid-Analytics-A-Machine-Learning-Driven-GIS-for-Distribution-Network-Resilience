import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import app
from extensions import db
from models import SecondaryLineSegment, BusNode, Post
from services.topology_service import TopologyService

def reconcile_secondary():
    print("Starting secondary network reconciliation...")
    
    with app.app_context():
        # Optimization: Pre-load poles
        all_posts = Post.query.all()
        pole_map = {p.pole_num: (p.lat, p.lng, p.id) for p in all_posts if p.pole_num is not None}
        pole_str_map = {str(p.pole_number).strip().upper(): (p.lat, p.lng, p.id) for p in all_posts if p.pole_number}
        
        segments = SecondaryLineSegment.query.all()
        print(f"Analyzing {len(segments)} secondary line segments...")
        
        nodes_created = 0
        nodes_updated = 0
        
        # Get all secondary bus nodes
        nodes = BusNode.query.all()
        print(f"Analyzing {len(nodes)} bus nodes...")
        
        nodes_updated = 0
        
        for bn in nodes:
            b_id = bn.bus_id
            parsed = TopologyService.parse_secondary_bus_id(b_id)
            if parsed:
                # Search for physical pole candidates
                phys_id = parsed['physical_pole_id']
                pole_only = str(parsed['pole_num_only'])
                
                if parsed['transformer_id']:
                    # Strict matching for multi-part IDs
                    search_keys = [phys_id, f"P{phys_id}", f"S{phys_id}"]
                else:
                    # 1-part IDs can match simple numbers
                    search_keys = [pole_only, f"P{pole_only}"]
                
                coords = None
                p_id = None
                lat, lng = None, None
                
                for k in search_keys:
                    if k.upper() in pole_str_map:
                        coords_data = pole_str_map[k.upper()]
                        lat, lng, p_id = coords_data
                        coords = (lat, lng)
                        break
            
                # Update the node: If no exact pole was found, lat/lng will be None
                # This prevents "flying" lines by hiding nodes with missing poles
                bn.lat = lat
                bn.lng = lng
                bn.pole_id = p_id
                
                if p_id:
                    pole = Post.query.get(p_id)
                    bn.pole_number = pole.pole_number if pole else f"P{phys_id}"
                else:
                    bn.pole_number = f"P{phys_id}"
                
                nodes_updated += 1
                    
        db.session.commit()
        print(f"Reconciliation complete: {nodes_updated} nodes updated.")

if __name__ == "__main__":
    reconcile_secondary()
