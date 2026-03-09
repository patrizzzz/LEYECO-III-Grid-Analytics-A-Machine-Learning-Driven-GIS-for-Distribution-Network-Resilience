import sys
import os

# Add the current directory to sys.path to import app and models
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app import app
from extensions import db
from models import DistributionTransformer, Customer, SecondaryServiceDrop, EnergyConsumption

def check_counts():
    with app.app_context():
        print(f"Transformers: {DistributionTransformer.query.count()}")
        print(f"Customers: {Customer.query.count()}")
        print(f"Service Drops: {SecondaryServiceDrop.query.count()}")
        print(f"Energy Consumption: {EnergyConsumption.query.count()}")
        
        # Check a sample service drop
        sd = SecondaryServiceDrop.query.first()
        if sd:
            print(f"Sample Service Drop: From Bus: {sd.from_bus_id}, To Customer: {sd.to_customer_id}")
            
        # Check a sample transformer
        dt = DistributionTransformer.query.first()
        if dt:
            print(f"Sample Transformer: ID: {dt.transformer_id}, Sec Bus: {dt.to_secondary_bus_id}, kVA: {dt.kva_rating}")

if __name__ == "__main__":
    check_counts()
