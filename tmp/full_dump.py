import joblib
import os
from services.ml_predictor import load_snapshot

def full_dump():
    snapshot = load_snapshot()
    with open('tmp/snapshot_dump.txt', 'w', encoding='utf-8') as f:
        if not snapshot:
            f.write("No snapshot loaded.\n")
            return
            
        f.write(f"Snapshot Keys: {list(snapshot.keys())}\n")
        if 'details' in snapshot:
            f.write(f"Total Details: {len(snapshot['details'])}\n\n")
            for d in snapshot['details']:
                f.write(str(d) + "\n")
        else:
            f.write("No 'details' key in snapshot.\n")
            f.write(f"Full Snapshot: {snapshot}\n")

if __name__ == '__main__':
    full_dump()
