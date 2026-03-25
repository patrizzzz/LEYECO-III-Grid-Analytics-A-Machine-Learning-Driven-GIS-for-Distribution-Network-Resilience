
from app import app, db
from utils.csv_importers import import_posts_from_csv, import_transformers_from_csv, import_secondary_lines_from_csv
from models import Post, DistributionTransformer, SecondaryLineSegment, LineConnection
import os


def run_verification():
    print("="*50)
    print(" STARTING IMPORT VERIFICATION")
    print("="*50)

    # Base path for files (using the paths provided in Prompt)
    base_dir = r"c:\Users\Patrick\Downloads\zip file leyeco\leyeco3\leyeco3\leyeco3"
    files = {
        'posts': os.path.join(base_dir, 'EXAMPLEDATA.csv'),
        'transformers': os.path.join(base_dir, 'example2.csv'),
        'secondary': os.path.join(base_dir, 'exampleSL.csv')
    }

    with app.app_context():
        # 1. Import Posts
        print(f"\n[1/3] Importing Posts from {files['posts']}...")
        if os.path.exists(files['posts']):
            with open(files['posts'], 'rb') as f:
                # Mock FileStorage object
                class MockFile:
                    def __init__(self, f): self.stream = f
                
                stats = import_posts_from_csv(MockFile(f))
                print(f"   -> Result: Created={stats.get('created')}, Updated={stats.get('updated')}, Errors={len(stats.get('errors', []))}")
        else:
            print("   -> File not found")

        # 2. Import Transformers
        print(f"\n[2/3] Importing Transformers from {files['transformers']}...")
        if os.path.exists(files['transformers']):
            with open(files['transformers'], 'rb') as f:
                class MockFile:
                    def __init__(self, f): self.stream = f
                stats = import_transformers_from_csv(MockFile(f))
                print(f"   -> Result: Created={stats.get('created')}, Updated={stats.get('updated')}, Errors={len(stats.get('errors', []))}")
        else:
            print("   -> File not found")

        # 3. Import Secondary Lines
        print(f"\n[3/3] Importing Secondary Lines from {files['secondary']}...")
        if os.path.exists(files['secondary']):
            with open(files['secondary'], 'rb') as f:
                class MockFile:
                    def __init__(self, f): self.stream = f
                stats = import_secondary_lines_from_csv(MockFile(f))
                print(f"   -> Result: Created={stats.get('created')}, Updated={stats.get('updated')}, Errors={len(stats.get('errors', []))}")
        else:
            print("   -> File not found")

        # 4. Summary & Geometry Check
        print("\n" + "="*50)
        print(" FINAL DATABASE STATE")
        print("="*50)
        print(f"Posts: {Post.query.count()}")
        print(f"Transformers: {DistributionTransformer.query.count()}")
        print(f"Secondary Lines: {SecondaryLineSegment.query.count()}")
        print(f"Line Connections: {LineConnection.query.count()}")
        
        # Quick check on geometry augmentation
        from network_geometry_db import get_network_geometry
        geo_data = get_network_geometry(app)
        nodes = geo_data['stats']['nodes']
        edges = geo_data['stats']['edges']
        print(f"\n Network Geometry: {nodes} nodes, {edges} edges generated.")
        if edges > 0:
            print("   -> Visualization data successfully generated!")
        else:
            print("   -> Warning: No edges generated. Check coordinate mapping.")

if __name__ == "__main__":
    run_verification()
