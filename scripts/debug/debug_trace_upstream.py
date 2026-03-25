from app import app
from models import DistributionLineSegment, Post, BusNode, DistributionTransformer
from network_geometry_db import build_topology_graph, trace_feeder_bfs

with app.app_context():
    with open('debug_log_upstream.txt', 'w') as f:
        graph = build_topology_graph(app)
        
        # Test 1: Start from a mid-point pole
        start_node = "P00000001-7A"
        f.write(f"--- Tracing from {start_node} (Upstream Check) ---\n")
        neighbors = graph.get(start_node, [])
        f.write(f"Direct neighbors of {start_node}: {neighbors}\n")
        
        visited = trace_feeder_bfs(app, start_node)
        f.write(f"Total nodes found: {len(visited)}\n")
        f.write(f"Is root (P00000000) in visited? {'P00000000' in visited}\n")
        
        # Test 2: Start from a secondary customer node
        # Based on previous log, S0001-0007-0001 was visited
        sec_node = "S0001-0007-0001"
        f.write(f"\n--- Tracing from Secondary {sec_node} ---\n")
        neighbors = graph.get(sec_node, [])
        f.write(f"Direct neighbors of {sec_node}: {neighbors}\n")
        
        visited = trace_feeder_bfs(app, sec_node)
        f.write(f"Total nodes found: {len(visited)}\n")
        f.write(f"Is root (P00000000) in visited? {'P00000000' in visited}\n")

        # Test 3: Check transformer bridge logic in undirected graph
        # Transformer DT00000001-7U: Pri=P00000001-7, Sec=DT00000001-7
        f.write(f"\n--- Transformer bridge check for DT00000001-7U ---\n")
        f.write(f"Neighbors of P00000001-7: {graph.get('P00000001-7', [])}\n")
        f.write(f"Neighbors of DT00000001-7: {graph.get('DT00000001-7', [])}\n")
