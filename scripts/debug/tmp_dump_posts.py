from app import app
from models import Post
with app.app_context():
    posts = Post.query.limit(20).all()
    for p in posts:
        print(f"Pole='{p.pole_number}', BusID='{p.primary_bus_id}'")
