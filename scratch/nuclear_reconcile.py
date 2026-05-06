import sys
import os
sys.path.append(os.getcwd())
from app import app
from models import Post, DistributionTransformer
from extensions import db
from services.linkage_service import LinkageService, LinkageContext

with app.app_context():
    print("--- Nuclear Reconciliation Starting ---")
    
    # 1. Wipe all transformer data from all poles first
    print("Step 1: Wiping all existing transformer assignments...")
    posts = Post.query.all()
    for p in posts:
        p.has_transformer = False
        p.kva_rating = None
        p.transformer_bus_id = None
    db.session.commit()
    
    # 2. Re-run matching with the fixed suffix-stripping logic
    print("Step 2: Re-matching all transformers...")
    transformers = DistributionTransformer.query.all()
    context = LinkageContext(posts=posts)
    
    match_count = 0
    for t in transformers:
        p = LinkageService.fuzzy_match_asset_to_post(t, context=context)
        if p:
            # We found a pole!
            p.has_transformer = True
            p.kva_rating = t.kva_rating
            p.transformer_bus_id = t.from_primary_bus_id or t.to_secondary_bus_id
            match_count += 1
            if p.id in [57, 58, 59, 64]:
                print(f"  [DEBUG] Linked {t.transformer_id} to Pole {p.id} (Number: {p.pole_number})")

    db.session.commit()
    print(f"\nSuccess! Re-linked {match_count} transformers.")
    print("Pole 57, 58, 59, and 64 should now be empty unless they have their OWN transformers.")
