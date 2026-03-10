#!/usr/bin/env python3
"""Clear all post data from the database."""

from app import app, db
from models import Post

def clear_posts():
    """Delete all posts from the database."""
    with app.app_context():
        try:
            # Get count before
            count_before = Post.query.count()
            print(f"Posts before deletion: {count_before}")
            
            # Delete all posts
            Post.query.delete()
            db.session.commit()
            
            # Get count after
            count_after = Post.query.count()
            print(f"Posts after deletion: {count_after}")
            print("✅ All post data cleared successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error clearing posts: {e}")

if __name__ == '__main__':
    clear_posts()
