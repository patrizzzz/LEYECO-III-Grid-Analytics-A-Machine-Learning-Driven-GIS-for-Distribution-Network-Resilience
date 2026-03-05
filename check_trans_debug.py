
from app import app
from models import DistributionTransformer
from extensions import db

def check_trans():
    with app.app_context():
        # Check for DT with secondary bus starting with S000090
        dts = DistributionTransformer.query.filter(DistributionTransformer.to_secondary_bus_id.like('S000090%')).all()
        print(f"Transformers matching S000090%: {len(dts)}")
        for dt in dts:
            print(f"  DT: {dt.transformer_id}, Primary: {dt.from_primary_bus_id}, Secondary: {dt.to_secondary_bus_id}")

check_trans()
