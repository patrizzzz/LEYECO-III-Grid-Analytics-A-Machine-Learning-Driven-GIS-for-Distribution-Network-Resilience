import sys
import os
import re

# Add the project root to the python path
sys.path.append(os.getcwd())

from app import app
from models import Post
from extensions import db
from services.linkage_service import LinkageService

with app.app_context():
    print("Healing Pole Identifiers...")
    posts = Post.query.all()
    updated_count = 0
    
    for p in posts:
        # If pole_number is missing, try to extract it from the Name (e.g. "Pole 94" -> "94")
        if not p.pole_number and p.name:
            match = re.search(r'(\d+)', p.name)
            if match:
                p.pole_number = match.group(1)
                updated_count += 1
        
        # Ensure primary_bus_id is set (needed for transformer matching)
        if not p.primary_bus_id and p.pole_number:
            # Format as P + Number to match DT bus IDs like P0000000094
            p.primary_bus_id = f"P{p.pole_number}"
            
    db.session.commit()
    print(f"Updated {updated_count} poles with proper identification numbers.")
    
    print("\nNow running Bulk Reconciliation to fix transformer links...")
    match_count = LinkageService.run_bulk_reconciliation()
    print(f"Finished! {match_count} transformers are now correctly linked.")
