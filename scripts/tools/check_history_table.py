import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

try:
    conn = pymysql.connect(
        host=os.getenv('DB_HOST', '127.0.0.1'),
        port=int(os.getenv('DB_PORT', '3306')),
        user=os.getenv('DB_USERNAME', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_DATABASE', 'mapping')
    )
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = [t[0] for t in cursor.fetchall()]
    print("Existing tables:", tables)
    
    if 'upload_history' in tables:
        cursor.execute("DESCRIBE upload_history")
        print("\nupload_history columns:")
        for col in cursor.fetchall():
            print(col)
    else:
        print("\nERROR: upload_history table is missing!")
        
    cursor.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
