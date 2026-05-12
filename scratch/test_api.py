
import requests
import sys
import os

# Try to find the app to get DB access
sys.path.insert(0, '.')
try:
    from app import app
    from models.assets import Post
    with app.app_context():
        p = Post.query.filter_by(pole_number='25').first()
        if p:
            pid = p.id
            p_num = p.pole_number
        else:
            # Try numeric
            p = Post.query.filter_by(pole_num=25).first()
            if p:
                pid = p.id
                p_num = p.pole_number
            else:
                pid = None
except Exception as e:
    print(f"Error accessing DB: {e}")
    pid = None

if pid:
    print(f"Testing Post ID {pid} (Pole {p_num})")
    base_url = 'http://127.0.0.1:5000/api'
    try:
        r_conns = requests.get(f'{base_url}/posts/{pid}/connections')
        print(f'Connections: {r_conns.json()}')
        
        r_drops = requests.get(f'{base_url}/posts/{pid}/service-drops')
        print(f'Drops count: {r_drops.json()["count"]}')
    except Exception as e:
        print(f"API Request Error: {e}")
else:
    print('Post 25 not found')
