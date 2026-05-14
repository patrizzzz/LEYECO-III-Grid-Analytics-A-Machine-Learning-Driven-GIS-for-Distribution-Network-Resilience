import sys
import os

# Add the project root to the python path
sys.path.append(os.getcwd())

from app import create_app
from services.linkage_service import LinkageService
from extensions import db

app = create_app()
with app.app_context():
    print("Starting Bulk Reconciliation...")
    print("This will reset all transformer assignments and re-link them using the fixed numeric logic.")
    
    stats = LinkageService.run_bulk_reconciliation()
    n = stats['linked_total'] if isinstance(stats, dict) else stats
    print(f"Success! {n} transformers have been correctly linked to their physical poles.")
    print("Please refresh your map to see the changes.")
