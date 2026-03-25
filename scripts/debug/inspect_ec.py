from app import create_app
from extensions import db
from models import Customer, EnergyConsumption

app = create_app()
with app.app_context():
    # Get a few customers
    customers = Customer.query.limit(5).all()
    for c in customers:
        print(f"Customer ID: '{c.customer_id}' (Type: {type(c.customer_id)})")
        
        # Check consumption
        consumptions = EnergyConsumption.query.filter_by(customer_id=c.customer_id).all()
        print(f"  Found {len(consumptions)} consumption records.")
        for ec in consumptions:
            print(f"    - {ec.kwh_consumed} kWh on {ec.billing_month}")
            
    # Check what customer IDs actually exist in EnergyConsumption
    ec_sample = EnergyConsumption.query.limit(5).all()
    print("\nSample EnergyConsumption records:")
    for ec in ec_sample:
        print(f"EC Customer ID: '{ec.customer_id}' (Type: {type(ec.customer_id)}) - {ec.kwh_consumed} kWh")
