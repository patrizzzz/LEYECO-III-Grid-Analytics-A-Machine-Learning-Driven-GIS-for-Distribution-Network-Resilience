from app import app
from models import SecondaryLineSegment, DistributionTransformer

with app.app_context():
    print("Finding all connections for S16-13-11...")
    
    # List all remaining S16-13 segments
    lines = SecondaryLineSegment.query.filter(
        (SecondaryLineSegment.from_bus_id.like('S16-13-%')) |
        (SecondaryLineSegment.to_bus_id.like('S16-13-%'))
    ).all()
    print(f"\nRemaining S16-13 segments ({len(lines)}):")
    for l in lines:
        print(f"  ID: {l.id}, From: {l.from_bus_id}, To: {l.to_bus_id}")
