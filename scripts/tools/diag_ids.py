
import re
from app import app
from models import Post, DistributionTransformer

def diag():
    with app.app_context():
        print("Numeric ID Diagnostic")
        txs = DistributionTransformer.query.all()
        posts = Post.query.all()
        
        post_nums = {}
        for p in posts:
            if p.pole_number:
                post_nums[str(p.pole_number).strip()] = p
            if p.primary_bus_id:
                post_nums[str(p.primary_bus_id).strip()] = p

        matches = 0
        samples = []
        for t in txs:
            bus_id = str(t.from_primary_bus_id or "")
            # Extract number: P00000001-7 -> 1
            match = re.search(r'P0*(\d+)', bus_id)
            if match:
                num = match.group(1)
                if num in post_nums:
                    matches += 1
                    if len(samples) < 5:
                        samples.append(f"TX {bus_id} -> Post {num}")
            else:
                # Try simple numeric extraction if no 'P'
                match = re.search(r'(\d+)', bus_id)
                if match:
                    num = match.group(1)
                    if num in post_nums:
                        matches += 1

        print(f"Total TX: {len(txs)}")
        print(f"Numeric matches found: {matches} / {len(txs)}")
        print(f"Samples: {samples}")

if __name__ == "__main__":
    diag()
