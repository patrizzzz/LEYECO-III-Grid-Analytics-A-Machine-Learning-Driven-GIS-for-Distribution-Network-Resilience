import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

db_host = os.getenv('DB_HOST', 'localhost')
db_port = os.getenv('DB_PORT', '8080')
db_user = os.getenv('DB_USERNAME', 'postgres')
db_pass = os.getenv('DB_PASSWORD', '0000')
db_name = os.getenv('DB_DATABASE', 'mapping')

try:
    conn = psycopg2.connect(
        host=db_host, port=db_port, user=db_user, password=db_pass, database=db_name
    )
    cursor = conn.cursor()
    
    print(f"{'ID':<5} | {'Name':<15} | {'Feeder':<8} | {'Cust count':<10} | {'Links':<5}")
    print("-" * 60)
    
    cursor.execute("SELECT id, name, feeder, pole_number, primary_bus_id FROM post WHERE id <= 15 ORDER BY id ASC")
    posts = cursor.fetchall()
    
    for pid, name, feeder, p_num, pb_id in posts:
        # Count customers (service drops)
        # Service drops link to bus_id. We need to find bus IDs linked to this pole.
        cursor.execute("SELECT bus_id FROM bus_node WHERE pole_id = %s", (pid,))
        bus_ids = [b[0] for b in cursor.fetchall()]
        if pb_id: bus_ids.append(pb_id)
        if p_num: bus_ids.append(p_num)
        
        cust_count = 0
        link_count = 0
        if bus_ids:
            # Customers
            cursor.execute("SELECT count(*) FROM secondary_service_drop WHERE from_bus_id IN %s", (tuple(bus_ids),))
            cust_count = cursor.fetchone()[0]
            
            # Links
            cursor.execute("SELECT count(*) FROM line_connection WHERE from_bus IN %s OR to_bus IN %s", (tuple(bus_ids), tuple(bus_ids)))
            link_count = cursor.fetchone()[0]
            
        print(f"{pid:<5} | {str(name):<15} | {str(feeder):<8} | {cust_count:<10} | {link_count:<5}")
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
