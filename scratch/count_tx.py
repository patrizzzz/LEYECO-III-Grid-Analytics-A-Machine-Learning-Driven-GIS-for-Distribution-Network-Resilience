from app import app
from models import Post

def count_tx():
    with app.app_context():
        count = Post.query.filter_by(has_transformer=True).count()
        print(f"Total poles with transformers: {count}")

if __name__ == "__main__":
    count_tx()
