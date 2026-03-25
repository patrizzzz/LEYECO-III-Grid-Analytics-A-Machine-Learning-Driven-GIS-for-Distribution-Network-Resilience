import sqlite3
import pandas as pd
import os

db_path = "C:\\Users\\Patrick\\Downloads\\zip file leyeco\\leyeco3\\leyeco3\\leyeco3\\instance\\leyeco3.db"
if not os.path.exists(db_path):
    # Try alternate path
    db_path = "C:\\Users\\Patrick\\Downloads\\zip file leyeco\\leyeco3\\leyeco3\\leyeco3\\leyeco3.db"

print(f"Checking DB at: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    
    # Check what tables exist
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table';", conn)
    print("Tables:", tables['name'].tolist())
    
    if 'energy_consumption' in tables['name'].tolist():
        count = pd.read_sql("SELECT COUNT(*) as count FROM energy_consumption;", conn).iloc[0]['count']
        print(f"Total rows in EnergyConsumption: {count}")
        
        if count > 0:
            sample = pd.read_sql("SELECT * FROM energy_consumption LIMIT 5;", conn)
            print("\nSample Energy Consumption Records:")
            print(sample)
    else:
        print("Table 'energy_consumption' does not exist!")
        
    conn.close()
except Exception as e:
    print("Error:", e)
