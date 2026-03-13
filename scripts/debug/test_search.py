from app import app

def test_search():
    with app.test_client() as client:
        response = client.get('/api/customers?q=1&per_page=5&skip_trace=true')
        print(f"Status: {response.status_code}")
        print(f"Data: {response.json}")

test_search()
