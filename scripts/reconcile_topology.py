import sys
import os

# Add the project root to the python path
sys.path.append(os.getcwd())

from app import app
from extensions import db
from models import Post, BusNode, DistributionTransformer
from services.linkage_service import LinkageService, LinkageContext

def reconcile_topology():
    with app.app_context():
        print("=" * 80)
        print("TOPOLOGY RECONCILIATION & CLEANUP")
        print("=" * 80)
        
        # 1. Reset transformer flags and technical data on all posts
        print("Resetting transformer flags and KVA ratings on all posts...")
        Post.query.update({
            Post.has_transformer: False, 
            Post.transformer_bus_id: None,
            Post.kva_rating: None
        })
        
        # 2. Clear and fix BusNode mappings
        print("Clearing all BusNode-to-Pole mappings to force fresh reconciliation...")
        BusNode.query.update({BusNode.pole_id: None, BusNode.pole_number: None})
        db.session.commit()
        
        # Identify and un-link any remaining problematic state (though update clears it)
        fix_count = BusNode.query.count()
        
        print(f"Un-linked {fix_count} mismatched BusNode records.")
        db.session.commit()
        
        # 3. Re-run reconciliation
        print("Re-running bulk reconciliation with strict matching...")
        posts = Post.query.all()
        bus_nodes = BusNode.query.all()
        context = LinkageContext(posts=posts, bus_nodes=bus_nodes)
        
        stats = LinkageService.run_bulk_reconciliation()
        if isinstance(stats, dict):
            print(
                f"Transformer rows in DB: {stats['transformer_rows']}\n"
                f"  Linked (main-line From Bus, no '-'): {stats['linked_mainline']}\n"
                f"  Linked (lateral From Bus, has '-'): {stats['linked_lateral']}\n"
                f"  Not linked to any post: {stats['not_linked']}\n"
                f"  Total linked rows: {stats['linked_total']}\n"
                f"Posts with transformer icon flag: {stats['posts_with_transformer']}"
            )
        else:
            print(f"Linked {stats} transformers.")

        db.session.commit()
        print("=" * 80)
        print("RECONCILIATION COMPLETE")
        print("=" * 80)

if __name__ == "__main__":
    reconcile_topology()
