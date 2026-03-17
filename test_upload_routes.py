import requests
import os

PORT = 5000
BASE_URL = f"http://127.0.0.1:{PORT}"

def test_endpoint(endpoint):
    url = f"{BASE_URL}{endpoint}"
    # Send an empty request to see if it exists (should return 400 No file part, not 404)
    try:
        response = requests.post(url)
        print(f"[{response.status_code}] {endpoint}")
        if response.status_code == 404:
            print("  ERROR: Still returning 404 Not Found")
        elif response.status_code == 403:
            print("  ERROR: Forbidden (needs admin, but route exists!)")
        elif response.status_code == 400:
            print("  SUCCESS: Route found (returned 400 Bad Request due to no file, as expected)")
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    endpoints = [
        "/api/voltage-regulators/bulk-import",
        "/api/shunt-capacitors/bulk-import",
        "/api/shunt-inductors/bulk-import",
        "/api/series-inductors/bulk-import"
    ]
    for ep in endpoints:
        test_endpoint(ep)
