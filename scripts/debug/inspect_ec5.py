import os
import sys

# Add project root to path if needed

from app import app
from extensions import db
from models import Customer, EnergyConsumption

with app.app_context():
    # Show exactly what's inside EC vs Customer
    print("--- Customer Sample ---")
    c1 = Customer.query.first()
    print(f"Customer 1: ID={c1.id}, customer_id='{c1.customer_id}'")
    
    print("\n--- EnergyConsumption Sample ---")
    ec1 = EnergyConsumption.query.first()
    print(f"EC 1: ID={ec1.id}, customer_id='{ec1.customer_id}', kwh={ec1.kwh_consumed}")
    
    # How many have matching customer IDs?
    all_c_ids = [c.customer_id for c in Customer.query.all()]
    all_ec_cids = [ec.customer_id for ec in EnergyConsumption.query.all()]
    
    print(f"\nTotal Customers: {len(all_c_ids)}")
    print(f"Total EC Records: {len(all_ec_cids)}")
    
    intersect = set(all_c_ids).intersection(set(all_ec_cids))
    print(f"Number of matching customer IDs: {len(intersect)}")
    
    print("\nFirst 5 Customer IDs:", all_c_ids[:5])
    print("\nFirst 5 EC Customer IDs:", all_ec_cids[:5])

