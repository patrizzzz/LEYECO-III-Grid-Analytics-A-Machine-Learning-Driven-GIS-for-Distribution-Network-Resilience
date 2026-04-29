import os
import sys
sys.path.append(os.getcwd())
from app import app
from models import DistributionTransformer, DistributionLineSegment, Post, LineConnection

with app.app_context():
    print(f"Posts: {Post.query.count()}")
    print(f"Transformers: {DistributionTransformer.query.count()}")
    print(f"LineSegments: {DistributionLineSegment.query.count()}")
    print(f"LineConnections: {LineConnection.query.count()}")
