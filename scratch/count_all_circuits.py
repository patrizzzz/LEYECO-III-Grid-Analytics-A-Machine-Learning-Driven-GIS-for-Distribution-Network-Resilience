import os
import sys
sys.path.append(os.getcwd())
from app import app
from models import DistributionLineSegment, SecondaryLineSegment, LineConnection

with app.app_context():
    d = DistributionLineSegment.query.filter(DistributionLineSegment.circuit.isnot(None)).count()
    s = SecondaryLineSegment.query.filter(SecondaryLineSegment.circuit.isnot(None)).count()
    c = LineConnection.query.filter(LineConnection.circuit.isnot(None)).count()
    print(f"Dist: {d}, Sec: {s}, Conn: {c}")
