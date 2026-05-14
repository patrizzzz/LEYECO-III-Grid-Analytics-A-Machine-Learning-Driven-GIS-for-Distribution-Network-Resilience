from app import app
from models import SecondaryLineSegment
from extensions import db

with app.app_context():
    ids_to_delete = [143, 146]
    print(f"Deleting segments: {ids_to_delete}")
    
    count = SecondaryLineSegment.query.filter(SecondaryLineSegment.id.in_(ids_to_delete)).delete(synchronize_session=False)
    db.session.commit()
    
    print(f"Done. Deleted {count} segments.")
