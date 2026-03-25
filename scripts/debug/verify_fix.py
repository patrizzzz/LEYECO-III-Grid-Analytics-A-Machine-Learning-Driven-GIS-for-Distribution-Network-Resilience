
from app import app
from routes.api_routes import find_customer_post_location

def verify_fix():
    with app.app_context():
        customer_id = "2020140010"
        print(f"Verifying trace for customer: {customer_id}")
        result = find_customer_post_location(customer_id)
        if result:
            print(f"SUCCESS: Found location!")
            print(f"  ID: {result.get('id')}")
            print(f"  Name: {result.get('name')}")
            print(f"  Coords: {result.get('lat')}, {result.get('lng')}")
            
            # Check if name contains "90" or ID is "90"
            if "90" in str(result.get('name', '')) or str(result.get('id')) == "90":
                print("CONFIRMED: Customer correctly traces to Pole 90.")
            else:
                print("WARNING: Customer found but not at Pole 90.")
        else:
            print("FAILURE: Customer location not found.")

if __name__ == "__main__":
    verify_fix()
