import pymysql

try:
    conn = pymysql.connect(
        host='127.0.0.1',
        port=3306,
        user='root',
        password='',
        database='mapping'
    )
    cursor = conn.cursor()
    
    # 1. Total counts
    cursor.execute("SELECT COUNT(*) FROM customer")
    print(f"Total customers: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM energy_consumption")
    print(f"Total energy_consumption records: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM secondary_service_drop")
    print(f"Total secondary_service_drops: {cursor.fetchone()[0]}")
    
    # 2. Detailed ID sampling
    print("\n--- Sample IDs ---")
    
    cursor.execute("SELECT customer_id FROM customer LIMIT 10")
    print("Customer ID chars:", [r[0] for r in cursor.fetchall()])
    
    cursor.execute("SELECT customer_id FROM energy_consumption LIMIT 10")
    print("EC Customer ID chars:", [r[0] for r in cursor.fetchall()])
    
    cursor.execute("SELECT to_customer_id FROM secondary_service_drop LIMIT 10")
    print("SD To-Customer ID chars:", [r[0] for r in cursor.fetchall()])

    # 3. Check for any overlap at all
    cursor.execute("""
        SELECT COUNT(*) 
        FROM secondary_service_drop sd 
        JOIN customer c ON sd.to_customer_id = c.customer_id
    """)
    print(f"\nMatches between SD and Customer: {cursor.fetchone()[0]}")
    
    cursor.execute("""
        SELECT COUNT(*) 
        FROM customer c 
        JOIN energy_consumption ec ON c.customer_id = ec.customer_id
    """)
    print(f"Matches between Customer and EC: {cursor.fetchone()[0]}")

    conn.close()
except Exception as e:
    print(f"Error: {e}")
