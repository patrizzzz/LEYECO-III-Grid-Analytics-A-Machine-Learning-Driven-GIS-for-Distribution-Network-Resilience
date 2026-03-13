import os
import sys
from dotenv import load_dotenv
import psycopg2

# Add project root to path to access models (not strictly needed for raw SQL but good practice)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

load_dotenv()

def sync_postgis():
    db_user = os.getenv('DB_USERNAME')
    db_pass = os.getenv('DB_PASSWORD')
    db_host = os.getenv('DB_HOST', '127.0.0.1')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_DATABASE')

    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_pass,
            host=db_host,
            port=db_port
        )
        cur = conn.cursor()

        print("Syncing Post coordinates...")
        cur.execute("""
            UPDATE post 
            SET geom = ST_SetSRID(ST_Point(lng, lat), 4326)
            WHERE lat IS NOT NULL AND lng IS NOT NULL AND geom IS NULL;
        """)
        print(f"Posts synced: {cur.rowcount}")

        print("Syncing BusNode coordinates...")
        cur.execute("""
            UPDATE bus_node 
            SET geom = ST_SetSRID(ST_Point(lng, lat), 4326)
            WHERE lat IS NOT NULL AND lng IS NOT NULL AND geom IS NULL;
        """)
        print(f"BusNodes synced: {cur.rowcount}")

        print("Syncing DistributionLineSegment geometries (Point-to-Point LineStrings)...")
        # Find start and end bus coordinates and create a LineString
        cur.execute("""
            UPDATE distribution_line_segment dls
            SET geom = ST_SetSRID(
                ST_MakeLine(
                    ST_Point(start_bus.lng, start_bus.lat),
                    ST_Point(end_bus.lng, end_bus.lat)
                ), 4326
            )
            FROM bus_node start_bus, bus_node end_bus
            WHERE dls.from_bus_id = start_bus.bus_id 
              AND dls.to_bus_id = end_bus.bus_id
              AND dls.geom IS NULL;
        """)
        print(f"LineSegments synced: {cur.rowcount}")

        conn.commit()
        print("PostGIS synchronization complete.")

    except Exception as e:
        print(f"Error during synchronization: {e}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    sync_postgis()
