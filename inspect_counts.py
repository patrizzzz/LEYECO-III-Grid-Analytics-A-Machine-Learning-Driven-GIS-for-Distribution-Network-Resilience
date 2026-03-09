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
    
    # 1. Row counts
    cursor.execute("SELECT COUNT(*) FROM customer")
    cust_count = cursor.fetchone()[0]
    print(f"Total customers: {cust_count}")
    
    cursor.execute("SELECT COUNT(*) FROM energy_consumption")
    ec_count = cursor.fetchone()[0]
    print(f"Total energy_consumption records: {ec_count}")
    
    cursor.execute("SELECT COUNT(*) FROM secondary_service_drop")
    sd_count = cursor.fetchone()[0]
    print(f"Total secondary_service_drops: {sd_count}")
    
    # 2. Sample IDs
    if cust_count > 0:
        cursor.execute("SELECT customer_id FROM customer LIMIT 5")
        print("\nSample Customer IDs:", [r[0] for r in cursor.fetchall()])
        
    if ec_count > 0:
        cursor.execute("SELECT customer_id FROM energy_consumption LIMIT 5")
        print("Sample EC Customer IDs:", [r[0] for r in cursor.fetchall()])
        
    if sd_count > 0:
        cursor.execute("SELECT to_customer_id FROM secondary_service_drop LIMIT 5")
        print("Sample SD To-Customer IDs:", [r[0] for r in cursor.fetchall()])

    conn.close()
except Exception as e:
    print(f"Error: {e}")
