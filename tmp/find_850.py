import os
from services.ml_predictor import load_snapshot

def find_850():
    snapshot = load_snapshot()
    if not snapshot or 'details' not in snapshot:
        print("No snapshot data found.")
        return

    print("Searching for 850 kVA transformers...")
    found = False
    for d in snapshot['details']:
        kva = d.get('kva_rating')
        if kva == 850 or kva == 850.0:
            print(f"Found Match: {d}")
            found = True
    
    if not found:
        print("No exact 850 kVA match. Checking nearby values...")
        for d in snapshot['details']:
            kva = d.get('kva_rating')
            if kva and 840 <= kva <= 860:
                print(f"Found Near Match: {d}")

if __name__ == '__main__':
    find_850()
