from app import app
from models import ShuntCapacitor, BusNode, Post
from extensions import db

def diagnose():
    with app.app_context():
        # 1. Check pole 120
        p120 = Post.query.filter_by(pole_number='120').first()
        if p120:
            print(f"Post 120: ID={p120.id}, Primary Bus={p120.primary_bus_id}, Sec Bus={p120.sec_bus_id}")
        else:
            print("Post 120 not found by pole_number='120'")
            
        # 2. Check BusNode for 120
        bn120 = BusNode.query.filter_by(pole_number='120').first()
        if bn120:
            print(f"BusNode 120: Bus ID={bn120.bus_id}")
        else:
            print("BusNode 120 not found by pole_number='120'")
            
        # 3. Check some capacitors in DB
        caps = ShuntCapacitor.query.limit(10).all()
        print("\nFirst 10 Capacitors in DB:")
        for c in caps:
            print(f" - ID: {c.capacitor_id}, Bus Connected: {c.bus_connected_id}")
            
        # 4. Search for ANY capacitor connected to something like '120'
        like_matches = ShuntCapacitor.query.filter(ShuntCapacitor.bus_connected_id.like('%120%')).all()
        print(f"\nCapacitors matching '%120%': {len(like_matches)}")
        for m in like_matches:
            print(f" - ID: {m.capacitor_id}, Bus Connected: {m.bus_connected_id}")

if __name__ == "__main__":
    diagnose()
