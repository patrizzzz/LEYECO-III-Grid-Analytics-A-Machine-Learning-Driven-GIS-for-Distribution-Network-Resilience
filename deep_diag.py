
import psycopg2

def deep_diagnose():
    try:
        conn = psycopg2.connect(host="localhost", port=8080, user="postgres", password="0000", database="mapping")
        cur = conn.cursor()
        
        # 1. Identify all IDs for the involved poles
        poles = ['83', '60', '1']
        pole_data = {}
        for p in poles:
            cur.execute("SELECT bus_id FROM bus_node WHERE pole_number = %s", (p,))
            buses = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT primary_bus_id, transformer_bus_id, sec_bus_id FROM post WHERE pole_number = %s", (p,))
            res = cur.fetchone()
            if res:
                for b in res:
                    if b: buses.append(b)
            pole_data[p] = list(set(buses))
            print(f"Pole {p} IDs: {pole_data[p]}")

        # 2. Trace downstream from Pole 83
        start_ids = pole_data['83']
        target_ids_60 = set(pole_data['60'])
        
        print("\n--- Tracing DOWNSTREAM from Pole 83 ---")
        query = """
        WITH RECURSIVE downstream_trace AS (
            SELECT CAST(%s AS varchar) AS current_bus, ARRAY[CAST(%s AS varchar)] AS path, 0 as depth
            UNION
            SELECT CAST(c.to_bus_id AS varchar), pt.path || CAST(c.to_bus_id AS varchar), pt.depth + 1
            FROM (
                SELECT from_bus_id, to_bus_id FROM distribution_line_segment
                UNION ALL SELECT from_primary_bus_id, to_secondary_bus_id FROM distribution_transformer
                UNION ALL SELECT from_bus_id, to_bus_id FROM secondary_line_segment
                UNION ALL SELECT from_bus, to_bus FROM line_connection
            ) c
            JOIN downstream_trace pt ON CAST(c.from_bus_id AS varchar) = pt.current_bus
            WHERE NOT c.to_bus_id = ANY(pt.path) AND pt.depth < 100
        )
        SELECT current_bus, path FROM downstream_trace WHERE current_bus IN %s;
        """
        for sid in start_ids:
            cur.execute(query, (sid, sid, tuple(target_ids_60)))
            results = cur.fetchall()
            for r in results:
                print(f"Path FOUND from 83 to 60:")
                print(f"  Target Bus: {r[0]}")
                print(f"  Path: {' -> '.join(r[1])}")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    deep_diagnose()
