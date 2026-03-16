import time
import sys
import os
import traceback

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import app
from services.network_geometry_db import get_network_geometry, get_network_geometry_optimized
from services.topology_service import TopologyService
from services.network_geometry_db import trace_downstream_bfs
from extensions import db
from models import Post, DistributionLineSegment

def benchmark():
    with app.app_context():
        try:
            # 1. Geometry Benchmark
            print("--- GeoJSON Generation Benchmark ---")
            start = time.time()
            get_network_geometry(app)
            legacy_time = time.time() - start
            print(f"Legacy Python GeoJSON: {legacy_time:.4f}s")

            start = time.time()
            get_network_geometry_optimized(app)
            optimized_time = time.time() - start
            print(f"Optimized PostGIS GeoJSON: {optimized_time:.4f}s")
            print(f"Speedup: {legacy_time/optimized_time:.2f}x")

            # 2. Tracing Benchmark
            # Find a real bus ID from the distribution lines
            line = DistributionLineSegment.query.first()
            start_id = line.from_bus_id if line else None
            
            if start_id:
                print(f"\n--- Tracing Benchmark (Start: {start_id}) ---")
                
                # Measure Legacy
                start = time.time()
                legacy_path = trace_downstream_bfs(app, [start_id])
                legacy_time = time.time() - start
                print(f"Legacy Python BFS: {legacy_time:.4f}s (Visited: {len(legacy_path)})")

                # Measure Optimized
                start = time.time()
                sql_path = TopologyService.trace_downstream_sql(start_id)
                sql_time = time.time() - start
                print(f"Optimized SQL CTE: {sql_time:.4f}s (Visited: {len(sql_path)})")
                
                if sql_time > 0:
                    print(f"Speedup: {legacy_time/sql_time:.2f}x")
            else:
                print("\nNo network data found for tracing benchmark.")

        except Exception:
            traceback.print_exc()

if __name__ == "__main__":
    benchmark()
