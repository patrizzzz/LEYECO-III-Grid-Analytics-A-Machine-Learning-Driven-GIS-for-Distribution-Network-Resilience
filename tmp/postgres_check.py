import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

db_host = os.getenv('DB_HOST', 'localhost')
db_port = os.getenv('DB_PORT', '8080')
db_user = os.getenv('DB_USERNAME', 'postgres')
db_pass = os.getenv('DB_PASSWORD', '0000')
db_name = os.getenv('DB_DATABASE', 'mapping')

print(f"Connecting to Postgres: {db_host}:{db_port} @ {db_name}")

try:
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_pass,
        database=db_name
    )
    cursor = conn.cursor()
    
    print(f"{'ID':<5} | {'Name':<15} | {'Feeder':<10} | {'Lat':<10} | {'Lng':<10}")
    print("-" * 60)
    
    cursor.execute("SELECT id, name, feeder, lat, lng FROM post ORDER BY id ASC LIMIT 20")
    rows = cursor.fetchall()
    for r in rows:
        print(f"{r[0]:<5} | {str(r[1]):<15} | {str(r[2]):<10} | {r[3]:<10} | {r[4]:<10}")
    
    cursor.execute("SELECT count(*) FROM post")
    count = cursor.fetchone()[0]
    print(f"\nTotal poles: {count}")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
