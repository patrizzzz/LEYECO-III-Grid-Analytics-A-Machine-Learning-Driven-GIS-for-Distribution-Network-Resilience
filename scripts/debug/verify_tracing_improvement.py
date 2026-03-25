
import sys
import os
# Add the app directory to sys.path
sys.path.append(os.path.abspath(os.getcwd()))

from app import create_app
from network_geometry_db import trace_downstream_bfs, trace_upstream_bfs, build_topology_graph, trace_feeder_bfs

app = create_app()

def test_tracing():
    with app.app_context():
        # Test Case 1: Start at a known secondary node (customer or pole)
        # From previous debug, we know P00000000 is a root.
        # Let's find a transformer secondary bus
        from models import DistributionTransformer
        tx = DistributionTransformer.query.first()
        if not tx:
            print("No transformers found to test.")
            return

        sec_bus = tx.to_secondary_bus_id
        pri_bus = tx.from_primary_bus_id
        
        print(f"Testing Transformer: {tx.transformer_id}")
        print(f"Primary Bus: {pri_bus}")
        print(f"Secondary Bus: {sec_bus}")

        # Upstream Trace from Secondary
        print("\n--- Upstream Trace from Secondary Bus ---")
        upstream = trace_upstream_bfs(app, sec_bus)
        print(f"Total Upstream Nodes: {len(upstream)}")
        if pri_bus in upstream:
            print("SUCCESS: Primary bus found in upstream trace!")
        else:
            print("FAILURE: Primary bus NOT found in upstream trace.")

        # Downstream Trace from Primary
        print("\n--- Downstream Trace from Primary Bus ---")
        downstream = trace_downstream_bfs(app, pri_bus)
        print(f"Total Downstream Nodes: {len(downstream)}")
        if sec_bus in downstream:
            print("SUCCESS: Secondary bus found in downstream trace!")
        else:
            print("FAILURE: Secondary bus NOT found in downstream trace.")

        # Full Trace (Undirected)
        print("\n--- Full Trace (Undirected) from Primary Bus ---")
        full = trace_feeder_bfs(app, pri_bus)
        print(f"Total Nodes: {len(full)}")
        if pri_bus in full and sec_bus in full:
            print("SUCCESS: Both buses found in full trace!")

if __name__ == "__main__":
    test_tracing()
