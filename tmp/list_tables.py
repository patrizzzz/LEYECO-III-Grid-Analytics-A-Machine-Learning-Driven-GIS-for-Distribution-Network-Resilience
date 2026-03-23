import sqlite3
import os

instance_dir = r'c:\Users\Patrick\Downloads\zip file leyeco\leyeco3\leyeco3\leyeco3\instance'
databases = ['app.db', 'leyeco3.db', 'leyeco3_gis.db']

for db_name in databases:
    db_path = os.path.join(instance_dir, db_name)
    if os.path.exists(db_path):
        print(f"\n--- Tables in {db_name} ---")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            for t in tables:
                print(t[0])
            conn.close()
        except Exception as e:
            print(f"Error reading {db_name}: {e}")
    else:
        print(f"\n{db_name} not found")
