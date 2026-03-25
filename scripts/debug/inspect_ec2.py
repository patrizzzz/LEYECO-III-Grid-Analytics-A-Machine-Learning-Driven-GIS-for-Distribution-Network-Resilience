from flask import Flask
from extensions import db
from models import Customer, EnergyConsumption
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///leyeco3.db'
db.init_app(app)

with app.app_context():
    print("--- Customer Sample ---")
    customers = Customer.query.limit(5).all()
    for c in customers:
        print(f"Customer ID: '{c.customer_id}' (Type: {type(c.customer_id)})")
        
    print("\n--- EnergyConsumption Sample ---")
    ec_sample = EnergyConsumption.query.limit(5).all()
    for ec in ec_sample:
        print(f"EC Customer ID: '{ec.customer_id}' (Type: {type(ec.customer_id)}) - {ec.kwh_consumed} kWh")
        
    print("\n--- Match Test ---")
    if len(customers) > 0:
        c_id = customers[0].customer_id
        matches = EnergyConsumption.query.filter_by(customer_id=c_id).all()
        print(f"Direct match for '{c_id}': {len(matches)} found")
        
        matches_str = EnergyConsumption.query.filter_by(customer_id=str(c_id)).all()
        print(f"String match for '{c_id}': {len(matches_str)} found")
