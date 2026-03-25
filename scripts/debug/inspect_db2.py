import sqlite3
import pandas as pd
import os

db_path = "C:\\Users\\Patrick\\Downloads\\zip file leyeco\\leyeco3\\leyeco3\\leyeco3\\instance\\app.db"
print(f"Checking DB at: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    
    # Check what tables exist
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table';", conn)
    print("Tables:", tables['name'].tolist())
    
    if 'energy_consumption' in tables['name'].tolist():
        count = pd.read_sql("SELECT COUNT(*) as count FROM energy_consumption;", conn).iloc[0]['count']
        print(f"\nTotal rows in EnergyConsumption: {count}")
        
        if count > 0:
            sample = pd.read_sql("SELECT customer_id, kwh_consumed FROM energy_consumption LIMIT 5;", conn)
            print("\nSample EC Records:")
            print(sample)
    
    if 'customer' in tables['name'].tolist():
        count = pd.read_sql("SELECT COUNT(*) as count FROM customer;", conn).iloc[0]['count']
        print(f"\nTotal rows in Customer: {count}")
        
        if count > 0:
            sample = pd.read_sql("SELECT customer_id, customer_type FROM customer LIMIT 5;", conn)
            print("\nSample Customer Records:")
            print(sample)

    # Let's do the match entirely in SQL!
    print("\n--- SQL Join Match Test ---")
    query = """
    SELECT c.customer_id as target, e.customer_id as matched, e.kwh_consumed
    FROM customer c
    JOIN energy_consumption e ON c.customer_id = e.customer_id
    LIMIT 10;
    """
    matches = pd.read_sql(query, conn)
    print(f"Direct SQL matches found: {len(matches)} (showing up to 10)")
    if len(matches) > 0:
        print(matches)

    conn.close()
except Exception as e:
    print("Error:", e)
