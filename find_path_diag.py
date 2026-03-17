
import psycopg2

def find_path():
    try:
        conn = psycopg2.connect(host="localhost", port=8080, user="postgres", password="0000", database="mapping")
        cur = conn.cursor()
        
        # Pole 83 buses
        cur.execute("SELECT bus_id FROM bus_node WHERE pole_number = '83' UNION SELECT primary_bus_id FROM post WHERE pole_number = '83'")
        buses_83 = [r[0] for r in cur.fetchall() if r[0]]
        
        # Pole 60 buses
        cur.execute("SELECT bus_id FROM bus_node WHERE pole_number = '60' UNION SELECT primary_bus_id FROM post WHERE pole_number = '60'")
        buses_60 = [r[0] for r in cur.fetchall() if r[0]]
        
        print(f"83: {buses_83}")
        print(f"60: {buses_60}")

        # Recursive CTE to find path from 83
        query = """
        WITH RECURSIVE path_trace AS (
            SELECT CAST(%s AS varchar) AS current_bus, ARRAY[CAST(%s AS varchar)] AS path
            UNION
            SELECT CAST(c.to_bus_id AS varchar), pt.path || CAST(c.to_bus_id AS varchar)
            FROM (
                SELECT from_bus_id, to_bus_id FROM distribution_line_segment
                UNION ALL SELECT from_primary_bus_id, to_secondary_bus_id FROM distribution_transformer
                UNION ALL SELECT from_bus_id, to_bus_id FROM secondary_line_segment
                UNION ALL SELECT from_bus, to_bus FROM line_connection
            ) c
            JOIN path_trace pt ON CAST(c.from_bus_id AS varchar) = pt.current_bus
            WHERE NOT c.to_bus_id = ANY(pt.path)
        )
        SELECT path FROM path_trace WHERE current_bus IN %s;
        """
        for b in buses_83:
            cur.execute(query, (b, b, tuple(buses_60)))
            paths = cur.fetchall()
            for p in paths:
                print(f"PATH FOUND: {' -> '.join(p[0])}")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_path()
