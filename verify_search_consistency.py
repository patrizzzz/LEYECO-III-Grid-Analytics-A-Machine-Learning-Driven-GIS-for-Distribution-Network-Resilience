import requests
import json

BASE_URL = "http://127.0.0.1:5000/api"

def verify_consistency():
    print("Starting consistency check...")
    
    # 1. Get a sample of customers
    try:
        resp = requests.get(f"{BASE_URL}/customers?per_page=20")
        if resp.status_code != 200:
            print(f"Failed to fetch customers: {resp.status_code}")
            return
        
        customers = resp.json().get('data', [])
        if not customers:
            print("No customers found to test.")
            return
            
        success_count = 0
        fail_count = 0
        no_link_count = 0
        
        for cust in customers:
            cust_id = cust['customer_id']
            print(f"\nChecking Customer: {cust_id} ({cust.get('name', 'N/A')})")
            
            # A. Trace Customer -> Pole
            loc_resp = requests.get(f"{BASE_URL}/customers/{cust_id}/location")
            if loc_resp.status_code != 200:
                print(f"  [ERROR] Location endpoint failed for {cust_id}")
                continue
                
            loc_data = loc_resp.json()
            post = loc_data.get('connected_post')
            
            if not post:
                print(f"  [INFO] Customer {cust_id} has no electrical link.")
                no_link_count += 1
                continue
                
            post_id = post['id']
            print(f"  -> Linked to Post ID: {post_id}")
            
            # B. Trace Pole -> Customer
            drops_resp = requests.get(f"{BASE_URL}/posts/{post_id}/service-drops")
            if drops_resp.status_code != 200:
                print(f"  [ERROR] Service drops endpoint failed for Post {post_id}")
                fail_count += 1
                continue
                
            drops_data = drops_resp.json()
            drops = drops_data.get('service_drops', [])
            
            # Check if our customer is in the list
            found_in_drops = any(d['to_customer_id'] == cust_id for d in drops)
            
            if found_in_drops:
                print(f"  [SUCCESS] Symmetric connection verified.")
                success_count += 1
            else:
                print(f"  [FAILURE] Customer {cust_id} NOT found in Post {post_id}'s service drops!")
                print(f"    Available IDs: {[d['to_customer_id'] for d in drops]}")
                fail_count += 1
                
        print("\n" + "="*40)
        print(f"RESULTS:")
        print(f"  Success: {success_count}")
        print(f"  Failures: {fail_count}")
        print(f"  No Links: {no_link_count}")
        print("="*40)
        
    except Exception as e:
        print(f"Error during verification: {e}")

if __name__ == "__main__":
    verify_consistency()
