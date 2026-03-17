
import psycopg2

def find_segments():
    try:
        conn = psycopg2.connect(host="localhost", port=8080, user="postgres", password="0000", database="mapping")
        cur = conn.cursor()
        
        # 1. Trace path and record segments
        # 83: ['DT0000000108-5', 'P0000000108-5']
        # 60: ['DT0000000100-30i']
        
        start_bus = 'P0000000108-5'
        target_bus = 'P0000000100-30i'
        
        query = """
        WITH RECURSIVE path_trace AS (
            SELECT CAST(%s AS varchar) AS current_bus, 
                   CAST(NULL AS varchar) AS segment_id,
                   CAST(NULL AS varchar) AS parent_bus,
                   0 AS depth
            UNION
            SELECT CAST(c.to_bus_id AS varchar), 
                   CAST(c.id AS varchar),
                   CAST(c.from_bus_id AS varchar),
                   pt.depth + 1
            FROM (
                SELECT segment_id as id, from_bus_id, to_bus_id FROM distribution_line_segment
                UNION ALL SELECT transformer_id as id, from_primary_bus_id, to_secondary_bus_id FROM distribution_transformer
                UNION ALL SELECT id::varchar, from_bus_id, to_bus_id FROM secondary_line_segment
                UNION ALL SELECT connection_type as id, from_bus, to_bus FROM line_connection
            ) c
            JOIN path_trace pt ON CAST(c.from_bus_id AS varchar) = pt.current_bus
            WHERE pt.depth < 20
        )
        SELECT depth, parent_bus, current_bus, segment_id FROM path_trace WHERE current_bus = %s;
        """
        cur.execute(query, (start_bus, target_bus))
        rows = cur.fetchall()
        for r in rows:
            print(f"Path to 60 (Depth {r[0]}): {r[1]} --[{r[3]}]--> {r[2]}")
            
            # Now show segments leading TO the parent
            curr = r[1]
            while curr and curr != start_bus:
                cur.execute("SELECT from_bus_id, segment_id FROM distribution_line_segment WHERE to_bus_id = %s", (curr,))
                prev = cur.fetchone()
                if prev:
                    print(f"  ... {prev[0]} --[{prev[1]}]--> {curr}")
                    curr = prev[0]
                else: break

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_segments()
