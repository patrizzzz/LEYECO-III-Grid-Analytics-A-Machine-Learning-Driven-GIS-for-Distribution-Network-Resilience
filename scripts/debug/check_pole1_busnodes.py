
import os
import sys
sys.path.append(os.getcwd())
from app import app
from extensions import db
from models import BusNode, Post

with app.app_context():
    p = Post.query.get(1)
    if not p:
        print("Post 1 not found")
        sys.exit(1)
        
    print(f"Post 1 Pole Number: '{p.pole_number}'")
    
    bns = BusNode.query.filter_by(pole_number=p.pole_number).all()
    print(f"Number of BusNodes with pole_number '{p.pole_number}': {len(bns)}")
    
    for bn in bns[:10]:
        print(f"  - BusID: {bn.bus_id}, Type: {bn.bus_type}, Feeder: {bn.feeder}")
        
    # Check if there are other posts with similar pole numbers
    others = Post.query.filter(Post.pole_number.like('%1%')).count()
    print(f"Other posts with '1' in pole_number: {others}")
