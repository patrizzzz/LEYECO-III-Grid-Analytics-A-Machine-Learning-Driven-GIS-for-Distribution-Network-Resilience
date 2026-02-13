#!/usr/bin/env python3
"""
Clear all posts and related data from the database.
WARNING: This will DELETE all post records!
"""

from app import app
from extensions import db
from models import Post, Meter

def clear_all_posts():
    """Delete all posts and meter readings from database"""
    with app.app_context():
        try:
            # Delete meter readings first (they reference posts)
            meter_count = Meter.query.delete()
            
            # Then delete posts
            post_count = Post.query.delete()
            
            db.session.commit()
            
            print("=" * 60)
            print("✓ DATABASE CLEARED SUCCESSFULLY")
            print("=" * 60)
            print(f"✓ Deleted {post_count} posts")
            print(f"✓ Deleted {meter_count} meter readings")
            print("\nReady for fresh data import!")
            print("=" * 60)
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error clearing database: {e}")
            return False
    
    return True

if __name__ == '__main__':
    print("=" * 60)
    print("⚠️  CLEARING ALL POSTS AND METER DATA")
    print("=" * 60)
    confirm = input("\nType 'DELETE' to confirm deletion: ").strip().upper()
    
    if confirm == 'DELETE':
        clear_all_posts()
    else:
        print("❌ Deletion cancelled.")

