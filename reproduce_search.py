from app import app
from models import Customer
from flask import url_for

with app.app_context():
    # Test search by customer_id
    test_id = '2020010046' # Example from CSV
    q = test_id
    term = f"%{q}%"
    results = Customer.query.filter((Customer.customer_id.ilike(term)) | (Customer.name.ilike(term))).all()
    print(f"Search results for ID '{q}': {len(results)} found")
    for r in results:
        print(f" - {r.customer_id}: {r.name}")

    # Test search by name
    test_name = 'BACATANO'
    q = test_name
    term = f"%{q}%"
    results = Customer.query.filter((Customer.customer_id.ilike(term)) | (Customer.name.ilike(term))).all()
    print(f"Search results for Name '{q}': {len(results)} found")
    for r in results:
        print(f" - {r.customer_id}: {r.name}")
