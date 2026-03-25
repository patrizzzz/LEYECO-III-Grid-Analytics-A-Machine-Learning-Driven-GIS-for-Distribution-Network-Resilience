import pymysql
import pandas as pd

try:
    # Connect to MySQL Database based on .env
    conn = pymysql.connect(
        host='127.0.0.1',
        port=3306,
        user='root',
        password='',
        database='mapping'
    )
    
    print("Successfully connected to MySQL mapping database!")
    
    # Check if table exists
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES LIKE 'energy_consumption';")
    result = cursor.fetchone()
    
    if result:
        print("\nTable 'energy_consumption' exists.")
        
        # Count rows
        count = pd.read_sql("SELECT COUNT(*) as count FROM energy_consumption;", conn).iloc[0]['count']
        print(f"Total rows in energy_consumption: {count}")
        
        if count > 0:
            sample = pd.read_sql("SELECT customer_id, kwh_consumed FROM energy_consumption LIMIT 5;", conn)
            print("\nSample EC Records:")
            print(sample)
    else:
        print("\nTable 'energy_consumption' DOES NOT EXIST in this database!")

    # Check Customer Table
    cursor.execute("SHOW TABLES LIKE 'customer';")
    result2 = cursor.fetchone()
    
    if result2:
        count2 = pd.read_sql("SELECT COUNT(*) as count FROM customer;", conn).iloc[0]['count']
        print(f"\nTotal rows in customer: {count2}")
        
        if count2 > 0:
            sample2 = pd.read_sql("SELECT customer_id, customer_type FROM customer LIMIT 5;", conn)
            print("\nSample Customer Records:")
            print(sample2)
            
            # Perform JOIN Match
            print("\n--- SQL Join Match Test ---")
            query = """
            SELECT c.customer_id as target, e.customer_id as matched, e.kwh_consumed
            FROM customer c
            JOIN energy_consumption e ON c.customer_id = e.customer_id
            LIMIT 10;
            """
            matches = pd.read_sql(query, conn)
            print(f"Direct SQL matches found: {len(matches)}")
            if len(matches) > 0:
                print(matches)
                
            # Perform Like Match Check
            print("\n--- SQL LIKE Match Test (handling leading zeros) ---")
            query2 = """
            SELECT c.customer_id as target, e.customer_id as matched, e.kwh_consumed
            FROM customer c
            JOIN energy_consumption e ON c.customer_id = TRIM(LEADING '0' FROM e.customer_id)
            LIMIT 10;
            """
            matches2 = pd.read_sql(query2, conn)
            print(f"LIKE matches found: {len(matches2)}")

    conn.close()
    
except Exception as e:
    print(f"Error connecting to MySQL: {e}")
