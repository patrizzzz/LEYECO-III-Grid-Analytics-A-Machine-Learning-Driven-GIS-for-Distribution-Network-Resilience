
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

def check():
    try:
        conn = pymysql.connect(
            host=os.getenv('DB_HOST', '127.0.0.1'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USERNAME', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_DATABASE', 'mapping'),
            cursorclass=pymysql.cursors.DictCursor
        )
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM post")
            print(f"Posts: {cursor.fetchone()['count']}")
            
            cursor.execute("SELECT COUNT(*) as count FROM distribution_transformer")
            print(f"Transformers: {cursor.fetchone()['count']}")
            
            cursor.execute("SELECT COUNT(*) as count FROM secondary_line_segment")
            print(f"Secondary Lines: {cursor.fetchone()['count']}")
            
            cursor.execute("SELECT COUNT(*) as count FROM secondary_service_drop")
            print(f"Service Drops: {cursor.fetchone()['count']}")

            cursor.execute("SELECT COUNT(*) as count FROM customer")
            print(f"Customers: {cursor.fetchone()['count']}")

            cursor.execute("SELECT COUNT(*) as count FROM post WHERE kva_rating IS NOT NULL")
            print(f"Posts with TX: {cursor.fetchone()['count']}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check()
