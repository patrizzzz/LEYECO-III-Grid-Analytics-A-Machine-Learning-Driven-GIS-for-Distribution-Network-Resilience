from app import app
from models import Post
import json

def dump_pole_23():
    with app.app_context():
        p = Post.query.get(23)
        if p:
            # Manually construct dict if to_dict fails or is missing
            d = {c.name: getattr(p, c.name) for c in p.__table__.columns}
            print(json.dumps(d, indent=2, default=str))

if __name__ == "__main__":
    dump_pole_23()
