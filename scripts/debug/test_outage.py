import requests
import json

url = 'http://localhost:5000/api/network/simulate-outage?start_bus=1'
try:
    response = requests.get(url)
    res = response.json()
    print("Outage Simulation Result for Pole 1:")
    print(f"Transformers: {len(res.get('affected_transformer_ids', []))}")
    print(f"Customers: {res.get('total_customers', 0)}")
    print(f"Load Loss: {res.get('total_load_kwh', 0)} kWh")
    print(f"Downstream buses: {res.get('downstream_bus_count', 0)}")
except Exception as e:
    print("Error:", e)
