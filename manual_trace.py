
import psycopg2

def manual_trace():
    try:
        conn = psycopg2.connect(host="localhost", port=8080, user="postgres", password="0000", database="mapping")
        cur = conn.cursor()
        
        poles = ['83', '60']
        for p in poles:
            print(f"\n--- Data for Pole {p} ---")
            cur.execute("SELECT bus_id, pole_number FROM bus_node WHERE pole_number = %s", (p,))
            print(f"  BusNode: {cur.fetchall()}")
            cur.execute("SELECT primary_bus_id, transformer_bus_id, sec_bus_id FROM post WHERE pole_number = %s", (p,))
            print(f"  Post: {cur.fetchone()}")

        print("\n--- Segments involving Pole 83 buses ---")
        cur.execute("""
            SELECT segment_id, from_bus_id, to_bus_id FROM distribution_line_segment 
            WHERE from_bus_id ILIKE '%108-5%' OR to_bus_id ILIKE '%108-5%'
        """)
        for r in cur.fetchall():
            print(f"  DL: {r[0]} | {r[1]} -> {r[2]}")

        cur.execute("""
            SELECT from_bus, to_bus, connection_type FROM line_connection 
            WHERE from_bus ILIKE '%108-5%' OR to_bus ILIKE '%108-5%'
        """)
        for r in cur.fetchall():
            print(f"  Conn: {r[0]} -> {r[1]} ({r[2]})")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    manual_trace()
