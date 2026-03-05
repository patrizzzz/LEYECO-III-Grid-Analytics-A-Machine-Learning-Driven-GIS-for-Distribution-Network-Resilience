import os
import sys
# Add current directory to path
sys.path.append(os.getcwd())

from app import app, db
from models import Post, BusNode

def sync():
    with app.app_context():
        print("=== SYNCHRONIZING POLES TO BUSNODES ===")
        posts = Post.query.all()
        updated_count = 0
        total_count = len(posts)
        
        for p in posts:
            # Try to find a BusNode that matches the physical pole number
            bn = BusNode.query.filter_by(pole_number=p.pole_number).first()
            if bn:
                changed = False
                if p.feeder != bn.feeder:
                    p.feeder = bn.feeder
                    changed = True
                if p.primary_bus_id != bn.bus_id:
                    p.primary_bus_id = bn.bus_id
                    changed = True
                
                if changed:
                    updated_count += 1
                    if updated_count <= 10:
                        print(f"Updated Post #{p.id} ({p.name}): Feeder={p.feeder}, BusID={p.primary_bus_id}")
                    elif updated_count == 11:
                        print("...")
        
        db.session.commit()
        print(f"\nSynchronization Complete.")
        print(f"Total Posts: {total_count}")
        print(f"Updated: {updated_count}")

if __name__ == '__main__':
    sync()
