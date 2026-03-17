
import psycopg2

def explain_path():
    try:
        conn = psycopg2.connect(host="localhost", port=8080, user="postgres", password="0000", database="mapping")
        cur = conn.cursor()
        
        # 1. Get all bus IDs for 83 and 60
        poles = ['83', '60']
        p_ids = {}
        for p in poles:
            cur.execute("SELECT bus_id FROM bus_node WHERE pole_number = %s", (p,))
            b1 = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT primary_bus_id, transformer_bus_id, sec_bus_id FROM post WHERE pole_number = %s", (p,))
            r2 = cur.fetchone()
            b2 = [x for x in r2 if x] if r2 else []
            p_ids[p] = list(set(b1 + b2))
            print(f"Pole {p} IDs: {p_ids[p]}")

        # 2. Trace path from 83 to 60 using CTE and keep track of segments
        start_ids = p_ids['83']
        target_ids = set(p_ids['60'])
        
        query = """
        WITH RECURSIVE path_trace AS (
            -- Start with all IDs for Pole 83
            SELECT CAST(s_bus AS varchar) AS current_bus, 
                   CAST('' AS varchar) AS segment_info,
                   CAST('' AS varchar) AS full_path,
                   0 as depth
            FROM unnest(%s::varchar[]) s_bus
            
            UNION ALL
            
            SELECT CAST(c.to_bus_id AS varchar),
                   CAST(c.table_name || ': ' || c.id || ' (' || c.from_bus_id || ' -> ' || c.to_bus_id || ')' AS varchar),
                   pt.full_path || ' | ' || c.table_name || ': ' || c.id,
                   pt.depth + 1
            FROM (
                SELECT 'DL' as table_name, segment_id as id, from_bus_id, to_bus_id FROM distribution_line_segment
                UNION ALL SELECT 'TX' as table_name, transformer_id as id, from_primary_bus_id, to_secondary_bus_id FROM distribution_transformer
                UNION ALL SELECT 'SL' as table_name, id::varchar as id, from_bus_id, to_bus_id FROM secondary_line_segment
                UNION ALL SELECT 'LC' as table_name, connection_type as id, from_bus, to_bus FROM line_connection
            ) c
            JOIN path_trace pt ON CAST(c.from_bus_id AS varchar) = pt.current_bus
            WHERE pt.depth < 15 -- Limit search
        )
        SELECT depth, current_bus, segment_info, full_path FROM path_trace WHERE current_bus = ANY(%s::varchar[]);
        """
        cur.execute(query, (start_ids, list(target_ids)))
        rows = cur.fetchall()
        
        if not rows:
            print("\nNo direct downstream path found in first 15 steps.")
        else:
            print("\n--- Paths Found from 83 to 60 ---")
            for r in rows:
                print(f"Depth {r[0]}: Reached {r[1]} via {r[2]}")
                print(f"Full Path sequence: {r[3]}")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    explain_path()
