from extensions import db
from models import Post
import json
import os
from flask import current_app

def seed_posts():
    """
    Seeds initial post data from sample_posts.json if the database is empty.
    Designed to be called within a Flask application context.
    """
    if Post.query.first():
        current_app.logger.info("Posts already exist; skipping seed.")
        return
    
    # Locate sample data relative to the application root
    pth = os.path.join(current_app.root_path, 'data', 'sample_posts.json')
    if not os.path.exists(pth):
        current_app.logger.warning(f"sample_posts.json not found at {pth}")
        return
        
    try:
        with open(pth, 'r') as f:
            posts = json.load(f)
            
        for p in posts:
            post = Post(name=p['name'], lat=p['lat'], lng=p['lng'], status=p.get('status'))
            db.session.add(post)
            
        db.session.commit()
        current_app.logger.info(f"Successfully seeded {len(posts)} posts.")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to seed posts: {str(e)}")
