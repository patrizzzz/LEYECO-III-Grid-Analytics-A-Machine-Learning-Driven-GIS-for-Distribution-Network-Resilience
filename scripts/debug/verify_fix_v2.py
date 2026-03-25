
from app import app
from routes.api_routes import find_customer_post_location
from models import SecondaryServiceDrop, DistributionTransformer, SecondaryLineSegment
from extensions import db

def verify_fix_verbose():
    with app.app_context():
        customer_id = "2020140010"
        print(f"Verifying trace for customer: {customer_id}")
        
        ssd = SecondaryServiceDrop.query.filter_by(to_customer_id=customer_id).first()
        if not ssd:
            print("No SSD found.")
            return
            
        start_bus = ssd.from_bus_id
        print(f"Starting at Bus: {start_bus}")
        
        # BFS for DT
        visited = {start_bus}
        queue = [(start_bus, 0)]
        found_dt = None
        
        while queue:
            curr, dist = queue.pop(0)
            dt = DistributionTransformer.query.filter_by(to_secondary_bus_id=curr).first()
            if dt:
                print(f"FOUND DT: {dt.transformer_id} at dist {dist} (Bus {curr})")
                print(f"  Primary Bus: {dt.from_primary_bus_id}")
                found_dt = dt
                break
            
            lines = SecondaryLineSegment.query.filter(
                (SecondaryLineSegment.from_bus_id == curr) |
                (SecondaryLineSegment.to_bus_id == curr)
            ).all()
            for l in lines:
                nxt = l.from_bus_id if l.to_bus_id == curr else l.to_bus_id
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, dist + 1))
        
        if found_dt:
            # Now call the actual function to see what Post it picks
            result = find_customer_post_location(customer_id)
            if result:
                print(f"Final Result: ID={result.get('id')}, Name={result.get('name')}")
            else:
                print("Final Result: None")

if __name__ == "__main__":
    verify_fix_verbose()
