from app import app
from models import Post

def list_posts():
    with app.app_context():
        posts = Post.query.filter_by(has_transformer=True).all()
        print(f"Total TX Posts: {len(posts)}")
        for p in posts:
            print(f"ID: {p.id}, Name: {p.name}, Bus: {p.transformer_bus_id}")

if __name__ == "__main__":
    list_posts()
