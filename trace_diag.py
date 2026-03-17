
import psycopg2
import sys

def check_direct_sql_trace():
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=8080,
            user="postgres",
            password="0000",
            database="mapping"
        )
        cur = conn.cursor()
        
        # 1. Get bus IDs for Pole 83 and 60
        poles = ['60', '83', '128']
        bus_map = {}
        for p in poles:
            cur.execute("SELECT bus_id FROM bus_node WHERE pole_number = %s", (p,))
            buses = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT primary_bus_id, transformer_bus_id, sec_bus_id FROM post WHERE pole_number = %s", (p,))
            res = cur.fetchone()
            if res:
                for b in res:
                    if b: buses.append(b)
            bus_map[p] = list(set(buses))
            print(f"Pole {p} Buses: {bus_map[p]}")

        # 2. Trace downstream from Pole 83 buses and see if any Pole 60 buses are reached
        start_buses = bus_map['83']
        target_buses = set(bus_map['60'])
        
        print("\n--- Downstream Trace from Pole 83 ---")
        for start_id in start_buses:
            query = """
            WITH RECURSIVE downstream_trace AS (
                SELECT CAST(%s AS varchar) AS current_bus
                UNION
                SELECT CAST(connected_bus AS varchar)
                FROM (
                    SELECT to_bus_id AS connected_bus, from_bus_id AS parent_bus FROM distribution_line_segment
                    UNION ALL
                    SELECT to_secondary_bus_id AS connected_bus, from_primary_bus_id AS parent_bus FROM distribution_transformer
                    UNION ALL
                    SELECT to_bus_id AS connected_bus, from_bus_id AS parent_bus FROM secondary_line_segment
                    UNION ALL
                    SELECT to_customer_id AS connected_bus, from_bus_id AS parent_bus FROM secondary_service_drop
                    UNION ALL
                    SELECT to_bus AS connected_bus, from_bus AS parent_bus FROM line_connection
                ) connections
                JOIN downstream_trace dt ON CAST(connections.parent_bus AS varchar) = dt.current_bus
            )
            SELECT current_bus FROM downstream_trace;
            """
            cur.execute(query, (start_id,))
            reachable = [r[0] for r in cur.fetchall()]
            found = [b for b in reachable if b in target_buses]
            if found:
                print(f"Buses from Pole 60 reached: {found}")
                # Now find the exact path
                print(f"Path Trace (Reverse search to find connection):")
                # This is more complex, but let's just look at segments between these two sets
                cur.execute("SELECT segment_id, from_bus_id, to_bus_id FROM distribution_line_segment WHERE (from_bus_id IN %s AND to_bus_id IN %s) OR (from_bus_id IN %s AND to_bus_id IN %s)", 
                            (tuple(reachable), tuple(target_buses), tuple(target_buses), tuple(reachable)))
                rows = cur.fetchall()
                for r in rows:
                    print(f"  DL Segment: {r[0]} | {r[1]} -> {r[2]}")
                
                cur.execute("SELECT from_bus, to_bus, connection_type FROM line_connection WHERE (from_bus IN %s AND to_bus IN %s) OR (from_bus IN %s AND to_bus IN %s)",
                             (tuple(reachable), tuple(target_buses), tuple(target_buses), tuple(reachable)))
                rows = cur.fetchall()
                for r in rows:
                    print(f"  Line Conn: {r[0]} -> {r[1]} ({r[2]})")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_direct_sql_trace()
