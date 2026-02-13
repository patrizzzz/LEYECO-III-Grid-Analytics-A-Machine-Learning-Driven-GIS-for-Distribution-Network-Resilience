from app import app
from models import DistributionLineSegment

with app.app_context():
    print('distribution_line_segment rows:', DistributionLineSegment.query.count())
