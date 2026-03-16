import pytest
import pandas as pd
from services.ml_predictor import predict_transformer_risk

def test_ml_predictor_basic_structure():
    """Verify the ML predictor returns the expected dictionary structure."""
    # Test data with 5 normal transformers
    data = [
        {'transformer_id': f'T{i}', 'kva_rating': 50.0, 'pct_z': 3.5, 'xr_ratio': 2.0, 'no_load_loss_kw': 0.1, 'exciting_current_pct': 0.5, 'utilization_percent': 60.0}
        for i in range(10)
    ]
    
    result = predict_transformer_risk(source='db', db_records=data)
    
    assert 'predictions' in result
    assert 'summary' in result
    assert len(result['predictions']) == 10
    assert result['summary']['total'] == 10

def test_ml_anomaly_detection_sensitivity():
    """Verify that a highly inefficient transformer is flagged as High/Critical risk."""
    # 9 Healthy transformers
    data = [
        {'transformer_id': f'HEALTHY_{i}', 'kva_rating': 50.0, 'pct_z': 3.5, 'xr_ratio': 2.0, 'no_load_loss_kw': 0.1, 'exciting_current_pct': 0.5, 'utilization_percent': 50.0}
        for i in range(15)
    ]
    
    # 1 Very unhealthy transformer (High losses, high impedance, high utilization)
    data.append({
        'transformer_id': 'UNHEALTHY_1',
        'kva_rating': 50.0,
        'pct_z': 15.0, # Way too high
        'xr_ratio': 10.0, # Unusual
        'no_load_loss_kw': 5.0, # Extreme losses
        'exciting_current_pct': 10.0, # Fault indicator
        'utilization_percent': 120.0 # Overloaded
    })
    
    result = predict_transformer_risk(source='db', db_records=data)
    
    # Find the unhealthy one in results
    unhealthy = next(r for r in result['predictions'] if r['transformer_id'] == 'UNHEALTHY_1')
    
    # Even with a small dataset, it should be at the top and marked as high/critical
    assert unhealthy['rank'] == 1
    assert unhealthy['risk_level'] in ['Critical', 'High']
    assert unhealthy['is_anomaly'] is True

def test_ml_empty_input():
    """Verify handling of empty or missing data (should ideally catch the ValueError)."""
    with pytest.raises(ValueError, match="Could not find transformer ID column"):
        predict_transformer_risk(source='db', db_records=[{'wrong_col': 1}])
