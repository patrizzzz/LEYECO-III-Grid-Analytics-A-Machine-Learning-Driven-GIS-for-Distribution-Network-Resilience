import pymysql
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

def check_mysql():
    print("--- MySQL (mapping) ---")
    try:
        conn = pymysql.connect(
            host=os.getenv('DB_HOST', '127.0.0.1'),
            port=int(os.getenv('DB_PORT', '3306')),
            user=os.getenv('DB_USERNAME', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_DATABASE', 'mapping')
        )
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [t[0] for t in cursor.fetchall()]
            for t in tables:
                cursor.execute(f"SELECT COUNT(*) FROM `{t}`")
                count = cursor.fetchone()[0]
                print(f" - {t}: {count}")
        conn.close()
    except Exception as e:
        print(f"Error checking MySQL: {e}")

def check_sqlite(path):
    if not os.path.exists(path):
        return
    print(f"--- SQLite ({path}) ---")
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall()]
        for t in tables:
            cursor.execute(f"SELECT COUNT(*) FROM \"{t}\"")
            count = cursor.fetchone()[0]
            print(f" - {t}: {count}")
        conn.close()
    except Exception as e:
        print(f"Error checking {path}: {e}")

if __name__ == '__main__':
    check_mysql()
    check_sqlite('instance/leyeco3.db')
    check_sqlite('instance/app.db')
    check_sqlite('instance/leyeco3_gis.db')
