
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

def verify():
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
            # Check counts
            cursor.execute("SELECT COUNT(*) as count FROM post")
            posts = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM distribution_transformer")
            transformers = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM bus_node")
            bus_nodes = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM upload_history")
            history = cursor.fetchone()['count']

            print(f"Counts: Posts={posts}, Transformers={transformers}, BusNodes={bus_nodes}, UploadHistory={history}")

            # Check for linked transformers
            cursor.execute("SELECT COUNT(*) as count FROM post WHERE kva_rating IS NOT NULL")
            linked_posts = cursor.fetchone()['count']
            print(f"Posts with kva_rating (transformers): {linked_posts}")

            if transformers > 0:
                print("\nSample Transformers (from_primary_bus_id):")
                cursor.execute("SELECT transformer_id, from_primary_bus_id FROM distribution_transformer LIMIT 5")
                for row in cursor.fetchall():
                    print(row)
            
            if posts > 0:
                print("\nSample Posts (pole_number, primary_bus_id):")
                cursor.execute("SELECT pole_number, primary_bus_id FROM post LIMIT 5")
                for row in cursor.fetchall():
                    print(row)

            # Look for mismatches
            cursor.execute("""
                SELECT t.from_primary_bus_id 
                FROM distribution_transformer t 
                LEFT JOIN post p ON (p.pole_number = t.from_primary_bus_id OR p.primary_bus_id = t.from_primary_bus_id)
                WHERE p.id IS NULL AND t.from_primary_bus_id IS NOT NULL 
                LIMIT 5
            """)
            mismatches = cursor.fetchall()
            if mismatches:
                print("\nTransformers with no matching Post (Top 5):")
                for m in mismatches:
                    print(m)
            else:
                print("\nNo orphaned transformers found (all match a post).")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify()
