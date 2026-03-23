import sqlite3
import os

db_path = r'c:\Users\Patrick\Downloads\zip file leyeco\leyeco3\leyeco3\leyeco3\instance\app.db'

if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
    # try other possible paths
    db_path = r'c:\Users\Patrick\Downloads\zip file leyeco\leyeco3\leyeco3\leyeco3\app.db'

print(f"Checking DB: {db_path}")
try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"{'ID':<5} | {'Name':<15} | {'Lat':<10} | {'Lng':<10}")
    print("-" * 50)
    
    cursor.execute("SELECT id, name, lat, lng FROM post ORDER BY id ASC LIMIT 20")
    rows = cursor.fetchall()
    for r in rows:
        print(f"{r[0]:<5} | {str(r[1]):<15} | {r[2]:<10} | {r[3]:<10}")
    
    cursor.execute("SELECT count(*) FROM post")
    count = cursor.fetchone()[0]
    print(f"\nTotal poles: {count}")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
