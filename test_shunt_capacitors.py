import requests
import json
import os

BASE_URL = "http://127.0.0.1:5000"

def test_shunt_capacitor_upload():
    print("--- Testing Shunt Capacitor Upload ---")
    url = f"{BASE_URL}/api/shunt-capacitors/bulk-import"
    file_path = os.path.join("data", "samples", "exampleSC.csv")
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': ('exampleSC.csv', f, 'text/csv')}
            response = requests.post(url, files=files)
            
        print(f"Upload Status Code: {response.status_code}")
        # print(f"Upload Response: {response.json()}")
    except Exception as e:
        print(f"Error during upload test: {e}")

def test_fetch_shunt_capacitors(pole_id):
    print(f"\n--- Testing Fetch for Bus ID: {pole_id} ---")
    url = f"{BASE_URL}/api/shunt-capacitors/by-bus/{pole_id}"
    
    try:
        response = requests.get(url)
        print(f"Fetch Status Code: {response.status_code}")
        data = response.json()
        count = data.get('count', 0)
        print(f"Found count: {count}")
        if count > 0:
            print("Successfully fetched capacitors!")
            print(f"First capacitor: {json.dumps(data.get('items', [])[0], indent=2)}")
        else:
            print("WARN: No capacitors found for this ID.")
    except Exception as e:
        print(f"Error during fetch test: {e}")

if __name__ == "__main__":
    test_shunt_capacitor_upload()
    test_fetch_shunt_capacitors("120") 
    test_fetch_shunt_capacitors("P0000000120") 
    test_fetch_shunt_capacitors("1")
