import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

def check_postgis():
    db_user = os.getenv('DB_USERNAME')
    db_pass = os.getenv('DB_PASSWORD')
    db_host = os.getenv('DB_HOST', '127.0.0.1')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_DATABASE')
    
    print(f"Connecting to {db_user}@{db_host}:{db_port}/{db_name}...")

    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_pass,
            host=db_host,
            port=db_port,
            connect_timeout=5
        )
        cur = conn.cursor()
        
        # Check if PostGIS extension exists
        cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'postgis';")
        exists = cur.fetchone()
        
        if exists:
            cur.execute("SELECT postgis_version();")
            version = cur.fetchone()
            print(f"PostGIS is already enabled: {version[0]}")
        else:
            print("PostGIS not enabled. Trying to enable...")
            cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
            conn.commit()
            print("PostGIS extension enabled successfully.")
            
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        print(f"Error type: {type(e)}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    check_postgis()
