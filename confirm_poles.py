
import psycopg2

def confirm_poles():
    try:
        conn = psycopg2.connect(host="localhost", port=8080, user="postgres", password="0000", database="mapping")
        cur = conn.cursor()
        
        # 1. Search for Pole 83 and 60 in post table
        cur.execute("""
            SELECT id, pole_number, primary_bus_id, transformer_bus_id, sec_bus_id 
            FROM post 
            WHERE pole_number IN ('83', '60')
        """)
        print("--- POST table records ---")
        for r in cur.fetchall():
            print(f"ID: {r[0]} | Pole: {r[1]} | Prim: {r[2]} | Trans: {r[3]} | Sec: {r[4]}")

        # 2. Search for the specific bus IDs we found in the trace
        bus_ids = ('P0000000108-5', 'DT0000000100-30i')
        cur.execute("""
            SELECT id, pole_number, primary_bus_id, transformer_bus_id, sec_bus_id 
            FROM post 
            WHERE primary_bus_id IN %s OR transformer_bus_id IN %s OR sec_bus_id IN %s
        """, (bus_ids, bus_ids, bus_ids))
        print("\n--- POST table records matching trace bus IDs ---")
        for r in cur.fetchall():
            print(f"ID: {r[0]} | Pole: {r[1]} | Prim: {r[2]} | Trans: {r[3]} | Sec: {r[4]}")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    confirm_poles()
