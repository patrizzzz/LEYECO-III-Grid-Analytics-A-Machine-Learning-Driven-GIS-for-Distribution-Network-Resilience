
import os
import sys
sys.path.append(os.getcwd())
from app import app
from extensions import db
from models import LineConnection, Post

with app.app_context():
    p = Post.query.get(1)
    if not p:
        print("Post 1 not found")
        sys.exit(1)
    
    # LineConnection uses from_bus and to_bus IDs
    # Let's find IDs starting with '1' or 'P00000001'
    conns = LineConnection.query.filter(
        (LineConnection.from_bus == '1') | 
        (LineConnection.to_bus == '1') |
        (LineConnection.from_bus == 'P00000001') |
        (LineConnection.to_bus == 'P00000001')
    ).all()
    
    print(f"LineConnections for '1' or 'P00000001': {len(conns)}")
    for c in conns:
        print(f"  {c.from_bus} -> {c.to_bus} ({c.connection_type})")
