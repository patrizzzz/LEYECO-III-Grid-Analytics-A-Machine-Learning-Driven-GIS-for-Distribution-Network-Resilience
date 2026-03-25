from app import app
from models import DistributionLineSegment

with app.app_context():
    query = DistributionLineSegment.query.filter(DistributionLineSegment.phasing != None)
    print("Count:", query.count())
    print("Sample:", [x.phasing for x in DistributionLineSegment.query.limit(5).all()])
