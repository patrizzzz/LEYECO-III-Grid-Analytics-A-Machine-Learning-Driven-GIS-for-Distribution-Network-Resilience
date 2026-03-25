
import sys
import os
sys.path.append(os.path.abspath(os.getcwd()))

from app import app
from network_geometry_db import trace_downstream_bfs, build_directed_topology_graph
from models import Post, DistributionLineSegment, SecondaryLineSegment, SecondaryServiceDrop, DistributionTransformer, BusNode, BusPostMapping

def debug_pole_trace(pole_id):
    with app.app_context():
        # Resolve pole number to primary_bus_id
        post = Post.query.filter((Post.primary_bus_id == pole_id) | (Post.pole_number == pole_id)).first()
        start_bus = post.primary_bus_id if post else pole_id
        
        print(f"--- Debugging Trace for Pole: {pole_id} (Resolved Bus: {start_bus}) ---")
        
        visited = trace_downstream_bfs(app, start_bus)
        print(f"Total nodes in downstream trace: {len(visited)}")
        
        # Categorize visited nodes
        posts = Post.query.filter(Post.primary_bus_id.in_(visited) | Post.pole_number.in_(visited)).all()
        transformer_ids = [tx.transformer_id for tx in DistributionTransformer.query.all()]
        visited_transformers = [v for v in visited if v in transformer_ids]
        
        # Check for customers (Service Drops)
        visited_customers = []
        for v in visited:
            # Customers are usually the 'to_customer_id' in SecondaryServiceDrop
            # Let's count them
            sd = SecondaryServiceDrop.query.filter(SecondaryServiceDrop.to_customer_id == v).first()
            if sd:
                visited_customers.append(v)

        print(f"Posts found: {len(posts)}")
        print(f"Transformers found: {len(visited_transformers)}")
        print(f"Customers found: {len(visited_customers)}")
        
        print("\nAll nodes in trace:")
        print(list(visited))
        
        # Check connections from start_bus
        graph = build_directed_topology_graph(app)
        neighbors = graph.get(start_bus, [])
        print(f"\nImmediate downstream neighbors of {start_bus}:")
        print(neighbors)
        
        for n in neighbors:
            # Check what kind of connection this is
            line = DistributionLineSegment.query.filter((DistributionLineSegment.from_bus_id == start_bus) & (DistributionLineSegment.to_bus_id == n)).first()
            if line:
                print(f"  -> {n} via DistributionLine (ID: {line.segment_id})")
            
            sec_line = SecondaryLineSegment.query.filter((SecondaryLineSegment.from_bus_id == start_bus) & (SecondaryLineSegment.to_bus_id == n)).first()
            if sec_line:
                print(f"  -> {n} via SecondaryLine (ID: {sec_line.secondary_line_id})")
                
            tx = DistributionTransformer.query.filter((DistributionTransformer.from_primary_bus_id == start_bus) & (DistributionTransformer.to_secondary_bus_id == n)).first()
            if tx:
                print(f"  -> {n} via Transformer (ID: {tx.transformer_id})")

if __name__ == "__main__":
    debug_pole_trace("132")
