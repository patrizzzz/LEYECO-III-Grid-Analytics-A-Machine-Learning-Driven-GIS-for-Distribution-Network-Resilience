import pymysql

conn = pymysql.connect(host='127.0.0.1', user='root', password='', database='mapping')
cursor = conn.cursor()

# Counts
cursor.execute("SELECT COUNT(*) FROM customer")
print(f"CUST: {cursor.fetchone()[0]}")
cursor.execute("SELECT COUNT(*) FROM energy_consumption")
print(f"EC:   {cursor.fetchone()[0]}")
cursor.execute("SELECT COUNT(*) FROM secondary_service_drop")
print(f"SD:   {cursor.fetchone()[0]}")

# Cross Matches
cursor.execute("SELECT COUNT(*) FROM secondary_service_drop sd JOIN customer c ON sd.to_customer_id = c.customer_id")
print(f"SD-CUST MATCH: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM customer c JOIN energy_consumption ec ON c.customer_id = ec.customer_id")
print(f"CUST-EC MATCH: {cursor.fetchone()[0]}")

# Samples if matches are 0
cursor.execute("SELECT customer_id FROM customer LIMIT 3")
print(f"C SAMPLE: {[r[0] for r in cursor.fetchall()]}")
cursor.execute("SELECT customer_id FROM energy_consumption LIMIT 3")
print(f"E SAMPLE: {[r[0] for r in cursor.fetchall()]}")
cursor.execute("SELECT to_customer_id FROM secondary_service_drop LIMIT 3")
print(f"S SAMPLE: {[r[0] for r in cursor.fetchall()]}")

conn.close()
