from services.ml_predictor import load_snapshot

def search_discrepancy():
    snapshot = load_snapshot()
    if not snapshot or 'details' not in snapshot:
        print("No snapshot found.")
        return
        
    print("Searching for poles with Risk: Critical and low utilization...")
    for d in snapshot['details']:
        util = d.get('utilization_percent', 0)
        risk = d.get('risk_level', '')
        # Looking for ~35.6% util and Critical risk
        if risk == 'Critical' and 30 < util < 40:
            print(f"FOUND DISCREPANCY: {d}")
        elif risk == 'Critical':
            print(f"Critical Risk Pole: {d.get('transformer_id')} | Util: {util}%")

if __name__ == '__main__':
    search_discrepancy()
