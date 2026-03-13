from app import app
from models import DistributionLineSegment, DistributionTransformer, SecondaryLineSegment

with app.app_context():
    with app.test_client() as client:
        # Test primary lines
        resp = client.get('/api/primary-lines/by-bus/95')
        print("Primary Lines for 95:", resp.status_code, resp.json)
        
        # Test transformers
        resp = client.get('/api/transformers/by-bus/95')
        print("Transformers for 95:", resp.status_code, resp.json)
        
        # Test service drops via post_id. 
        # First we need a post. Post 60 corresponds to bus 60 in earlier trace, let's just pick one.
        from models import Post
        p = Post.query.filter_by(primary_bus_id='95').first()
        if p:
            resp = client.get(f'/api/posts/{p.id}/service-drops')
            print(f"Service Drops for Post {p.id}:", resp.status_code)
        else:
            print("No post found for bus_id 95")

