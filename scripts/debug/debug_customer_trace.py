
from app import app
from models import Customer, SecondaryServiceDrop, SecondaryLineSegment, DistributionTransformer, Post, BusNode
from extensions import db

def debug_customer_trace(cust_id):
    with app.app_context():
        print(f"DEBUGGING TRACE FOR CUSTOMER: {cust_id}")
        
        # 1. Customer
        cust = Customer.query.filter_by(customer_id=cust_id).first()
        if not cust:
            print("ERROR: Customer NOT found in database.")
            return
        print(f"Customer Found: {cust.name} (ID: {cust.customer_id})")
        
        # 2. Service Drop
        ssd = SecondaryServiceDrop.query.filter_by(to_customer_id=cust_id).first()
        if not ssd:
            print("ERROR: SecondaryServiceDrop NOT found for this customer.")
            return
        print(f"SSD Found: {ssd.service_drop_id}, From Bus: {ssd.from_bus_id}")
        
        start_bus = ssd.from_bus_id
        
        # 3. Direct Post Check
        post = Post.query.filter((Post.primary_bus_id == start_bus) | (Post.pole_number == start_bus)).first()
        if post:
            print(f"DIRECT POST MATCH: {post.pole_number} at ({post.lat}, {post.lng})")
            return

        # 4. BFS for Transformer
        visited = {start_bus}
        queue = [(start_bus, 0)]
        found_dt = None
        
        while queue:
            curr, depth = queue.pop(0)
            print(f"  BFS Depth {depth}: checking bus {curr}")
            
            dt = DistributionTransformer.query.filter_by(to_secondary_bus_id=curr).first()
            if dt:
                print(f"  TRANSFORMER FOUND: {dt.transformer_id} at Bus {dt.from_primary_bus_id}")
                found_dt = dt
                break
                
            lines = SecondaryLineSegment.query.filter(
                (SecondaryLineSegment.from_bus_id == curr) |
                (SecondaryLineSegment.to_bus_id == curr)
            ).all()
            
            for line in lines:
                nxt = line.from_bus_id if line.to_bus_id == curr else line.to_bus_id
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, depth + 1))
        
        if found_dt:
            # 5. Trace from DT to Post
            p_bus = found_dt.from_primary_bus_id
            post = Post.query.filter((Post.primary_bus_id == p_bus) | (Post.pole_number == p_bus)).first()
            if post:
                print(f"FINAL POST MATCH: {post.pole_number} at ({post.lat}, {post.lng})")
            else:
                print(f"ERROR: Transformer found at {p_bus} but no Post matches this primary bus.")
                # Check BusNode
                bn = BusNode.query.filter_by(bus_id=p_bus).first()
                if bn:
                    print(f"BusNode found for {p_bus}: pole={bn.pole_number}, lat={bn.lat}, lng={bn.lng}")

if __name__ == "__main__":
    debug_customer_trace("2020140010")
