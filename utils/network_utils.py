from models import Post, LineConnection
from extensions import db

def infer_connections_from_posts():
    """
    Auto-infer line connections from post data based on feeder and circuit.
    Creates Primary_to_Primary connections for posts in same feeder/circuit.
    """
    try:
        # Get all posts grouped by feeder and circuit
        posts = Post.query.all()
        if not posts:
            return
        
        # Group posts by (feeder, circuit) 
        groups = {}
        for post in posts:
            if post.feeder and post.circuit and post.pole_number:
                key = (post.feeder, post.circuit)
                if key not in groups:
                    groups[key] = []
                groups[key].append(post)
        
        # For each group, create connections between consecutive posts
        connection_count = 0
        for (feeder, circuit), group_posts in groups.items():
            # Sort by pole_number to get order
            try:
                # Try to extract numbers from pole identifiers for sorting
                group_posts.sort(key=lambda p: int(''.join(c for c in str(p.pole_number) if c.isdigit())) if any(c.isdigit() for c in str(p.pole_number)) else 0)
            except:
                pass  # If sorting fails, keep original order
            
            # Create connections between sequential posts
            for i in range(len(group_posts) - 1):
                from_post = group_posts[i]
                to_post = group_posts[i + 1]
                
                from_bus = from_post.primary_bus_id or f"P{from_post.pole_number}"
                to_bus = to_post.primary_bus_id or f"P{to_post.pole_number}"
                
                # Check if connection already exists
                existing = LineConnection.query.filter_by(
                    from_bus=from_bus,
                    to_bus=to_bus,
                    connection_type='Primary_to_Primary'
                ).first()
                
                if not existing:
                    conn = LineConnection(
                        from_bus=from_bus,
                        to_bus=to_bus,
                        connection_type='Primary_to_Primary',
                        feeder=feeder,
                        circuit=circuit
                    )
                    db.session.add(conn)
                    connection_count += 1
        
        if connection_count > 0:
            db.session.commit()
            
    except Exception as e:
        print(f"Error inferring connections: {e}")
        db.session.rollback()
