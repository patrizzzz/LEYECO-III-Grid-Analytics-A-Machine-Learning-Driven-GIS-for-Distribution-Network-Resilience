
from app import app
from models import SecondaryLineSegment
from extensions import db

def check_link():
    with app.app_context():
        # Check if S000090-0000011 eventually links to DT0000000090
        start = "S000090-0000011"
        target = "DT0000000090"
        
        visited = {start}
        queue = [(start, 0)]
        while queue:
            curr, dist = queue.pop(0)
            if curr == target:
                print(f"FOUND LINK! {start} -> {target} in {dist} hops")
                return
            
            lines = SecondaryLineSegment.query.filter(
                (SecondaryLineSegment.from_bus_id == curr) |
                (SecondaryLineSegment.to_bus_id == curr)
            ).all()
            for l in lines:
                nxt = l.from_bus_id if l.to_bus_id == curr else l.to_bus_id
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, dist + 1))
        print("NO LINK found between these buses.")

check_link()
