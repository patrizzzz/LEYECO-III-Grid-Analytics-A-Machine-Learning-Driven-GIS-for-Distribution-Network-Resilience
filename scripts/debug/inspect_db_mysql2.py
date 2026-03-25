import pymysql
import pandas as pd

try:
    conn = pymysql.connect(
        host='127.0.0.1',
        port=3306,
        user='root',
        password='',
        database='mapping'
    )
    
    print("--- String Format Analysis ---")
    
    # Let's look at the literal lengths and values
    q_cust = """
    SELECT customer_id, LENGTH(customer_id) as len, HEX(customer_id) as hex 
    FROM customer LIMIT 5;
    """
    print("\nCustomer Table:")
    print(pd.read_sql(q_cust, conn))
    
    q_ec = """
    SELECT customer_id, user_id, LENGTH(customer_id) as len, HEX(customer_id) as hex 
    FROM energy_consumption LIMIT 5;
    """
    print("\nEnergy Consumption Table:")
    print(pd.read_sql(q_ec, conn))

    # Wait, does Energy Consumption use `user_id` instead of `customer_id`?
    print("\n--- Testing user_id match ---")
    q_match = """
    SELECT c.customer_id as target, e.user_id as matched, e.kwh_consumed
    FROM customer c
    JOIN energy_consumption e ON c.customer_id = e.user_id
    LIMIT 10;
    """
    matches = pd.read_sql(q_match, conn)
    print(f"User ID matches found: {len(matches)}")
    if len(matches) > 0:
        print(matches)

    conn.close()
except Exception as e:
    print(f"Error: {e}")
