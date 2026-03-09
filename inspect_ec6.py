from app import create_app
from extensions import db
from models import Customer, EnergyConsumption
import logging

app = create_app()

with app.app_context():
    # 1. Look at a specific customer
    c1 = Customer.query.filter(Customer.customer_id.isnot(None)).first()
    if c1:
        print(f"Sample Customer: ID='{c1.customer_id}' Name='{c1.name}'")
        
    # 2. Look at a specific EC record
    ec1 = EnergyConsumption.query.filter(EnergyConsumption.customer_id.isnot(None)).first()
    if ec1:
        print(f"Sample EC Record: ID='{ec1.customer_id}' kWh={ec1.kwh_consumed}")
        
    print("\n--- Testing Exact Match ---")
    all_c_ids = [str(c.customer_id).strip() for c in Customer.query.all()]
    all_ec_ids = [str(ec.customer_id).strip() for ec in EnergyConsumption.query.all()]
    
    print(f"Total Customer IDs: {len(all_c_ids)}")
    print(f"Total EC IDs: {len(all_ec_ids)}")
    
    intersect = set(all_c_ids).intersection(set(all_ec_ids))
    print(f"Matching IDs: {len(intersect)}")
    
    if len(intersect) == 0:
        print("\n--- No matches found! Let's look at the formats. ---")
        print("First 10 Customer IDs: ", all_c_ids[:10])
        print("First 10 EC IDs:       ", all_ec_ids[:10])
