import sys
import os
import pandas as pd
import numpy as np

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.ml_predictor import predict_transformer_risk

def run_stability_test():
    # 1. Create a "Stable Transformer" record
    stable_tx = {
        'transformer_id': 'TX-STABLE',
        'kva_rating': 25.0,
        '%Z': 2.3,
        'X/R Ratio': 1.0,
        'No-Load Loss (kW)': 0.1,
        'Exciting Current (%)': 0.3,
        'utilization_percent': 50.0
    }

    # 2. Run with dataset A (Mostly healthy)
    data_a = [stable_tx] + [
        {'transformer_id': f'TX-H-{i}', 'kva_rating': 25, '%Z': 2.3, 'X/R Ratio': 1.0, 'No-Load Loss (kW)': 0.1, 'Exciting Current (%)': 0.3, 'utilization_percent': 40}
        for i in range(20)
    ]
    
    res_a = predict_transformer_risk(source='db', db_records=data_a)
    score_a = next(r['risk_score'] for r in res_a['predictions'] if r['transformer_id'] == 'TX-STABLE')
    
    # 3. Run with dataset B (Mixed with anomalies)
    data_b = [stable_tx] + [
        {'transformer_id': f'TX-A-{i}', 'kva_rating': 10, '%Z': 6.0, 'X/R Ratio': 3.0, 'No-Load Loss (kW)': 0.4, 'Exciting Current (%)': 4.0, 'utilization_percent': 150}
        for i in range(10)
    ]
    
    res_b = predict_transformer_risk(source='db', db_records=data_b)
    score_b = next(r['risk_score'] for r in res_b['predictions'] if r['transformer_id'] == 'TX-STABLE')

    print(f"Dataset A (Healthy) - TX-STABLE Risk Score: {score_a}")
    print(f"Dataset B (Anomalous) - TX-STABLE Risk Score: {score_b}")
    
    diff = abs(score_a - score_b)
    print(f"Difference: {diff}")
    
    if diff < 10:
        print("SUCCESS: ML Model scores are stable!")
    else:
        print("FAILURE: ML Model scores fluctuated significantly.")

if __name__ == "__main__":
    run_stability_test()
