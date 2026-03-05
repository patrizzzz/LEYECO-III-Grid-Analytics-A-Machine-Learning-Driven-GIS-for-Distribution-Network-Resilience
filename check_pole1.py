
from app import create_app
from extensions import db
from models import Post, DistributionLineSegment, SecondaryLineSegment, BusNode

app = create_app()
with app.app_context():
    # 1. Find the Post
    # The user says "pole 1", this could be id=1 or pole_number="1"
    post_by_id = Post.query.get(1)
    post_by_num = Post.query.filter_by(pole_number='1').first()
    
    print(f"Post by ID 1: {post_by_id}")
    if post_by_id:
        print(f"  Name: {post_by_id.name}, Pole Number: {post_by_id.pole_number}")
        
    print(f"Post by Pole Number '1': {post_by_num}")
    if post_by_num:
        print(f"  ID: {post_by_num.id}, Name: {post_by_num.name}")

    target_post = post_by_num or post_by_id
    if not target_post:
        print("No post found for 'pole 1'")
    else:
        # Collect bus IDs like in the API logic
        buses = set()
        if target_post.pole_number:
            buses.add(target_post.pole_number)
            try:
                if not str(target_post.pole_number).startswith('P'):
                    buses.add(f"P{str(target_post.pole_number).zfill(8)}")
            except: pass

        if target_post.primary_bus_id: buses.add(target_post.primary_bus_id)
        if target_post.sec_bus_id: buses.add(target_post.sec_bus_id)
        if target_post.transformer_bus_id: buses.add(target_post.transformer_bus_id)
        
        bns = BusNode.query.filter_by(pole_number=target_post.pole_number).all()
        for bn in bns:
            buses.add(bn.bus_id)
            
        print(f"Associated Bus IDs: {buses}")
        
        bus_list = list(buses)
        
        # Check Distribution Lines
        dist_lines = DistributionLineSegment.query.filter(
            (DistributionLineSegment.from_bus_id.in_(bus_list)) | 
            (DistributionLineSegment.to_bus_id.in_(bus_list))
        ).all()
        
        print(f"Primary Connections ({len(dist_lines)}):")
        for l in dist_lines:
            print(f"  - ID: {l.segment_id}, From: {l.from_bus_id}, To: {l.to_bus_id}")
            
        # Check Secondary Lines
        sec_lines = SecondaryLineSegment.query.filter(
            (SecondaryLineSegment.from_bus_id.in_(bus_list)) | 
            (SecondaryLineSegment.to_bus_id.in_(bus_list))
        ).all()
        
        print(f"Secondary Connections ({len(sec_lines)}):")
        for l in sec_lines:
            print(f"  - ID: {l.id}, From: {l.from_bus_id}, To: {l.to_bus_id}")
