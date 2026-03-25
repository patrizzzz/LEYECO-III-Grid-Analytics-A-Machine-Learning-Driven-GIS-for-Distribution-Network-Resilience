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
    with conn.cursor() as cursor:
        cursor.execute("SELECT version_num FROM alembic_version")
        versions = cursor.fetchall()
        print("Current migration versions in DB:")
        for v in versions:
            print(f" - {v[0]}")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
