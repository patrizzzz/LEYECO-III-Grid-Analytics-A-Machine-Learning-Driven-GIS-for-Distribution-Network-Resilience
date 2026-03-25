
from app import app
from models import Customer, SecondaryServiceDrop, SecondaryLineSegment, DistributionTransformer, Post, BusNode
from extensions import db

def debug_customer_trace(cust_id):
    with app.app_context():
        cust = Customer.query.filter_by(customer_id=cust_id).first()
        if not cust: return "Cust not found"
        
        ssd = SecondaryServiceDrop.query.filter_by(to_customer_id=cust_id).first()
        if not ssd: return "SSD not found"
        
        msg = f"Cust: {cust.name}, SSD From: {ssd.from_bus_id}\n"
        curr = ssd.from_bus_id
        
        # Check direct post
        post = Post.query.filter((Post.primary_bus_id == curr) | (Post.pole_number == curr)).first()
        if post:
            return msg + f"Direct Post: {post.pole_number} ({post.lat}, {post.lng})"
            
        # BFS for Transformer
        visited = {curr}
        queue = [(curr, 0)]
        while queue:
            c, d = queue.pop(0)
            dt = DistributionTransformer.query.filter_by(to_secondary_bus_id=c).first()
            if dt:
                msg += f"Found DT: {dt.transformer_id} at {dt.from_primary_bus_id} (dist {d})\n"
                p_bus = dt.from_primary_bus_id
                post = Post.query.filter((Post.primary_bus_id == p_bus) | (Post.pole_number == p_bus)).first()
                if post:
                    return msg + f"Final Post: {post.pole_number} ({post.lat}, {post.lng})"
                bn = BusNode.query.filter_by(bus_id=p_bus).first()
                if bn:
                    return msg + f"BusNode: {bn.bus_id} Pole: {bn.pole_number} ({bn.lat}, {bn.lng})"
                return msg + "Transformer found but no Post/BusNode"
                
            lines = SecondaryLineSegment.query.filter((SecondaryLineSegment.from_bus_id==c)|(SecondaryLineSegment.to_bus_id==c)).all()
            for l in lines:
                n = l.from_bus_id if l.to_bus_id == c else l.to_bus_id
                if n not in visited:
                    visited.add(n)
                    queue.append((n, d+1))
        return msg + "No path to transformer found"

print(debug_customer_trace("2020140010"))
