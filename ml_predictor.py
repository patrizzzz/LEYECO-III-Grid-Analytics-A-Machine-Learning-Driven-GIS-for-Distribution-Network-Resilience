"""
ML Transformer Failure Risk Predictor
Uses Isolation Forest (unsupervised anomaly detection) to score
distribution transformers by failure risk based on electrical characteristics.
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler, LabelEncoder
import os


def predict_transformer_risk(source='csv', csv_path=None, db_records=None):
    """
    Predict transformer failure risk using Isolation Forest anomaly detection.

    Args:
        source: 'csv' to load from CSV file, 'db' to use database records
        csv_path: path to CSV file (used when source='csv')
        db_records: list of dicts from DistributionTransformer.to_dict() (used when source='db')

    Returns:
        dict with keys:
          - predictions: list of dicts sorted by risk_score descending
          - summary: {critical: N, high: N, medium: N, low: N, total: N}
          - model_info: {features_used: [...], contamination: float, n_samples: int}
    """

    # --- 1. Load data ---
    if source == 'db' and db_records:
        df = pd.DataFrame(db_records)
        # Map DB column names to CSV-style names for uniform processing
        col_map = {
            'transformer_id': 'Distribution Transformer ID',
            'kva_rating': 'KVA Rating',
            'installation_type': 'Installation Type',
            'primary_phasing': 'Primary Phasing',
            'secondary_phasing': 'Secondary Phasing',
            'connection': 'Connection',
            'no_dts_in_bank': 'No. DTs in Bank',
            'pct_z': '%Z',
            'xr_ratio': 'X/R Ratio',
            'no_load_loss_kw': 'No-Load Loss (kW)',
            'exciting_current_pct': 'Exciting Current (%)',
            'primary_voltage_kv': 'Primary Voltage Rating(kV)',
            'secondary_voltage_kv': 'Secondary Voltage Rating (kV)',
            'from_primary_bus_id': 'From \nPrimary Bus ID',
            'to_secondary_bus_id': 'To  \nSecondary Bus ID',
        }
        df.rename(columns=col_map, inplace=True)
    else:
        if csv_path is None:
            csv_path = os.path.join(os.path.dirname(__file__), 'example2.csv')
        df = pd.read_csv(csv_path)

    # Clean column names (remove newlines/extra whitespace)
    df.columns = [c.replace('\n', ' ').replace('\r', ' ').strip() for c in df.columns]
    df.columns = [' '.join(c.split()) for c in df.columns]

    # --- 1b. Load stress data if available ---
    stress_path = os.path.join(os.path.dirname(__file__), 'transformer_load_stress.csv')
    df_stress = pd.DataFrame()
    if os.path.exists(stress_path):
        df_stress = pd.read_csv(stress_path)
        # Ensure ID columns match for merge
        df = df.merge(df_stress[['transformer_id', 'utilization_percent']], 
                     left_on='Distribution Transformer ID', right_on='transformer_id', 
                     how='left').drop(columns=['transformer_id'])

    # Ensure we have a transformer ID column
    id_col = None
    for candidate in ['Distribution Transformer ID', 'transformer_id']:
        if candidate in df.columns:
            id_col = candidate
            break
    if id_col is None:
        raise ValueError("Could not find transformer ID column in data")

    # --- 2. Feature engineering ---
    # Numerical features - strictly limited to electrical characteristics
    allowed_stats = ['KVA Rating', '%Z', 'X/R Ratio', 'No-Load Loss (kW)', 'Exciting Current (%)', 'utilization_percent']
    numerical_features = [f for f in allowed_stats if f in df.columns]

    categorical_features = [] # Removed non-electrical categorical features

    # Build feature matrix
    feature_df = pd.DataFrame()

    # Numerical features - fill NaN with median
    for feat in numerical_features:
        col = pd.to_numeric(df[feat], errors='coerce')
        col = col.fillna(col.median())
        feature_df[feat] = col

    # Categorical features - label encode
    label_encoders = {}
    for feat in categorical_features:
        le = LabelEncoder()
        col = df[feat].fillna('Unknown').astype(str)
        feature_df[feat] = le.fit_transform(col)
        label_encoders[feat] = le

    # Derived features for better anomaly detection
    if 'KVA Rating' in feature_df.columns and 'No-Load Loss (kW)' in feature_df.columns:
        # Loss ratio: higher ratio = less efficient = potentially degraded
        feature_df['loss_to_kva_ratio'] = feature_df['No-Load Loss (kW)'] / (feature_df['KVA Rating'] + 0.001)

    if '%Z' in feature_df.columns and 'X/R Ratio' in feature_df.columns:
        # Impedance-reactance product: unusual combos may indicate issues
        feature_df['z_xr_product'] = feature_df['%Z'] * feature_df['X/R Ratio']

    if 'Exciting Current (%)' in feature_df.columns:
        # Exciting Ratio = Exciting Current / Rated Current (already represented by % / 100)
        feature_df['exciting_ratio'] = feature_df['Exciting Current (%)'] / 100.0

    # --- 3. Scale and train model ---
    # We drop 'KVA Rating', 'No-Load Loss (kW)', and 'Exciting Current (%)' from X 
    # because they are raw values or raw percentages that we have now converted 
    # to standardized ratios (loss_to_kva_ratio, exciting_ratio).
    # We KEEP 'utilization_percent' as a primary stress indicator.
    to_drop = ['KVA Rating', 'No-Load Loss (kW)', 'Exciting Current (%)', 'No. DTs in Bank', 'Primary Voltage Rating(kV)', 'Secondary Voltage Rating (kV)']
    training_df = feature_df.drop(columns=[c for c in to_drop if c in feature_df.columns])

    scaler = StandardScaler()
    X = scaler.fit_transform(training_df.values)

    # Contamination: assume ~15% of transformers might be at risk
    contamination = 0.15
    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
        max_samples='auto'
    )
    model.fit(X)

    # Get anomaly scores (-1 = anomaly, 1 = normal)
    raw_scores = model.decision_function(X)  # lower = more anomalous
    predictions = model.predict(X)  # -1 or 1

    # --- 4. Convert to risk scores (0-100) ---
    # Invert so that higher score = higher risk
    min_score = raw_scores.min()
    max_score = raw_scores.max()
    if max_score - min_score > 0:
        risk_scores = 100 * (1 - (raw_scores - min_score) / (max_score - min_score))
    else:
        risk_scores = np.full_like(raw_scores, 50.0)

    # --- 5. Classify risk levels ---
    def classify_risk(score):
        if score >= 80:
            return 'Critical'
        elif score >= 60:
            return 'High'
        elif score >= 40:
            return 'Medium'
        else:
            return 'Low'

    # --- 6. Build results ---
    results = []
    for i in range(len(df)):
        row = df.iloc[i]
        risk_score = round(float(risk_scores[i]), 1)
        risk_level = classify_risk(risk_score)

        result = {
            'rank': 0,  # filled after sorting
            'transformer_id': str(row.get(id_col, f'Unknown-{i}')),
            'kva_rating': float(row.get('KVA Rating', 0)) if pd.notna(row.get('KVA Rating')) else 0,
            'installation_type': str(row.get('Installation Type', 'N/A')),
            'primary_phasing': str(row.get('Primary Phasing', 'N/A')),
            'connection': str(row.get('Connection', 'N/A')) if pd.notna(row.get('Connection')) else 'N/A',
            'pct_z': float(row.get('%Z', 0)) if pd.notna(row.get('%Z')) else 0,
            'xr_ratio': float(row.get('X/R Ratio', 0)) if pd.notna(row.get('X/R Ratio')) else 0,
            'no_load_loss_kw': float(row.get('No-Load Loss (kW)', 0)) if pd.notna(row.get('No-Load Loss (kW)')) else 0,
            'exciting_current_pct': float(row.get('Exciting Current (%)', 0)) if pd.notna(row.get('Exciting Current (%)')) else 0,
            'risk_score': risk_score,
            'risk_level': risk_level,
            'is_anomaly': bool(predictions[i] == -1),
            'utilization_percent': float(row.get('utilization_percent', 0)) if pd.notna(row.get('utilization_percent')) else 0,
        }
        results.append(result)

    # Sort by risk score descending
    results.sort(key=lambda x: x['risk_score'], reverse=True)
    for i, r in enumerate(results):
        r['rank'] = i + 1

    # Summary
    summary = {
        'total': len(results),
        'critical': sum(1 for r in results if r['risk_level'] == 'Critical'),
        'high': sum(1 for r in results if r['risk_level'] == 'High'),
        'medium': sum(1 for r in results if r['risk_level'] == 'Medium'),
        'low': sum(1 for r in results if r['risk_level'] == 'Low'),
        'anomalies_detected': sum(1 for r in results if r['is_anomaly']),
    }

    model_info = {
        'algorithm': 'Isolation Forest',
        'features_used': list(feature_df.columns),
        'contamination': contamination,
        'n_estimators': 200,
        'n_samples': len(df),
    }

    return {
        'predictions': results,
        'summary': summary,
        'model_info': model_info,
    }


if __name__ == '__main__':
    # Quick test
    result = predict_transformer_risk(source='csv')
    print(f"Total predictions: {result['summary']['total']}")
    print(f"Summary: {result['summary']}")
    print(f"\nTop 5 at-risk transformers:")
    for p in result['predictions'][:5]:
        print(f"  #{p['rank']} {p['transformer_id']} - Score: {p['risk_score']} ({p['risk_level']}) - KVA: {p['kva_rating']}")
