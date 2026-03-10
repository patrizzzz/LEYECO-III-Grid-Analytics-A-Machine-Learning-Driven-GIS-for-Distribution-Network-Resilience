from app import app
from models import Post
with app.app_context():
    p = Post.query.filter_by(pole_number='130').first()
    if p:
        print(f"Post 130: BusID='{p.primary_bus_id}', KVA={p.kva_rating}, DT='{p.transformer_bus_id}'")
    else:
        print("Post 130 not found.")
