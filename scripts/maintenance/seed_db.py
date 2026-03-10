from app import app
from extensions import db
from models import Post
import json
import os


def seed_posts():
    with app.app_context():
        if Post.query.first():
            print("Posts already exist; skipping seed.")
            return
        pth = os.path.join(os.getcwd(), 'data', 'sample_posts.json')
        if not os.path.exists(pth):
            print("sample_posts.json not found.")
            return
        with open(pth) as f:
            posts = json.load(f)
        for p in posts:
            post = Post(name=p['name'], lat=p['lat'], lng=p['lng'], status=p.get('status'))
            db.session.add(post)
        db.session.commit()
        print(f"Seeded {len(posts)} posts.")


if __name__ == '__main__':
    seed_posts()
