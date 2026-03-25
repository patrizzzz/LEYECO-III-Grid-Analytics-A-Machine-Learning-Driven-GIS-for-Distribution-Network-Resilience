
from app import app
from models import SecondaryServiceDrop, Customer
from extensions import db

def check_ssd():
    with app.app_context():
        cust_id = "2020140010"
        ssd = SecondaryServiceDrop.query.filter_by(to_customer_id=cust_id).first()
        if ssd:
            print(f"SSD for {cust_id}:")
            print(f"  From Bus: {ssd.from_bus_id}")
            print(f"  Service Drop ID: {ssd.service_drop_id}")
        else:
            print(f"No SSD for {cust_id}")

check_ssd()
