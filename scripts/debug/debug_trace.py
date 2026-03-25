from app import app
from models import DistributionLineSegment, Post, BusNode, DistributionTransformer
from network_geometry_db import build_topology_graph, trace_feeder_bfs

with app.app_context():
    with open('debug_log.txt', 'w') as f:
        f.write("--- Distribution Line Segments ---\n")
        segs = DistributionLineSegment.query.limit(20).all()
        for s in segs:
            f.write(f"Segment {s.id}: {s.from_bus_id} -> {s.to_bus_id}\n")
        
        p = Post.query.filter(Post.primary_bus_id != None).first()
        if p:
            f.write(f"\n--- Tracing from Post {p.id} ({p.primary_bus_id}) ---\n")
            graph = build_topology_graph(app)
            start_node = p.primary_bus_id.strip()
            neighbors = graph.get(start_node, [])
            f.write(f"Direct neighbors of {start_node}: {neighbors}\n")
            
            visited = trace_feeder_bfs(app, start_node)
            f.write(f"Total nodes found in undirected trace: {len(visited)}\n")
            
            # Check for any 'upstream' indicator
            # Let's see if we find the 'Substation' or some common prefix
            for v in list(visited)[:50]:
                f.write(f"Visited: {v}\n")
        
        f.write("\n--- All Transformers ---\n")
        txs = DistributionTransformer.query.limit(20).all()
        for tx in txs:
            f.write(f"Transformer {tx.transformer_id}: Pri={tx.from_primary_bus_id}, Sec={tx.to_secondary_bus_id}\n")
