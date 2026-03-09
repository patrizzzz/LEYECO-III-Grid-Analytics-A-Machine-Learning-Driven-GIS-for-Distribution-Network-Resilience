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
    SELECT customer_id, LENGTH(customer_id) as len, HEX(customer_id) as hex 
    FROM energy_consumption LIMIT 5;
    """
    print("\nEnergy Consumption Table:")
    print(pd.read_sql(q_ec, conn))

    conn.close()
except Exception as e:
    print(f"Error: {e}")
