import sys
from app import app, db
from models import SecondaryServiceDrop, SecondaryLineSegment, DistributionTransformer, Post

def find_dt_bfs(start_bus):
    visited = set([start_bus])
    queue = [start_bus]
    
    # Check if start_bus already has a DT
    dt = DistributionTransformer.query.filter_by(to_secondary_bus_id=start_bus).first()
    if dt: return dt
    
    while queue:
        current_bus = queue.pop(0)
        lines = SecondaryLineSegment.query.filter((SecondaryLineSegment.from_bus_id == current_bus) | (SecondaryLineSegment.to_bus_id == current_bus)).all()
        for line in lines:
            nxt = line.from_bus_id if line.to_bus_id == current_bus else line.to_bus_id
            if nxt not in visited:
                visited.add(nxt)
                dt = DistributionTransformer.query.filter_by(to_secondary_bus_id=nxt).first()
                if dt: return dt
                queue.append(nxt)
    return None

with app.app_context():
    customer_id = '20-2086-0101'
    ssd = SecondaryServiceDrop.query.filter_by(to_customer_id=customer_id).first()
    print('SSD:', ssd)
    if ssd and ssd.from_bus_id:
        dt = find_dt_bfs(ssd.from_bus_id)
        print('Found DT via BFS:', dt)
        if dt and dt.from_primary_bus_id:
            post = Post.query.filter_by(primary_bus_id=dt.from_primary_bus_id).first()
            print('Post match via primary:', post)
            post2 = Post.query.filter_by(pole_number=dt.from_primary_bus_id).first()
            print('Post match via pole sequence:', post2)
