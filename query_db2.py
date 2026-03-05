from app import app
from models import Post, DistributionLineSegment

with app.app_context():
    print("--- POSTS ---")
    for p in Post.query.limit(5).all():
        print(f"ID: {p.id}, Pole: {p.pole_number}, Primary Bus: {p.primary_bus_id}")
        
    print("--- LINES ---")
    for d in DistributionLineSegment.query.limit(5).all():
        print(f"Segment: {d.segment_id}, From: {d.from_bus_id}, To: {d.to_bus_id}")
