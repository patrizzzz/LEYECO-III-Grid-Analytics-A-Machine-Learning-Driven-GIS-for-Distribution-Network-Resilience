from services.ml_predictor import load_snapshot

def dump_dt108():
    snapshot = load_snapshot()
    if not snapshot or 'details' not in snapshot: return
    for d in snapshot['details']:
        tid = str(d.get('transformer_id', ''))
        if '108' in tid and '25' in tid:
            print(f"FULL DATA FOR {tid}:")
            for k, v in d.items():
                print(f"  {k}: {v}")
            return

if __name__ == '__main__':
    dump_dt108()
