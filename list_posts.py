from app import app
from extensions import db
from models import Post

with app.app_context():
    posts = Post.query.order_by(Post.id).limit(20).all()
    for p in posts:
        print(f"ID={p.id}, PoleNumber={p.pole_number}, Name={p.name}")
