import pandas as pd
import numpy as np
import os

def calculate_transformer_load_stress(data_dir=None):
    if data_dir is None:
        data_dir = os.path.dirname(os.path.abspath(__file__))
        
    common_encoding = 'latin-1'
    
    # Load core datasets
    try:
        df_trans = pd.read_csv(os.path.join(data_dir, "example2.csv"), encoding=common_encoding)
        df_curves = pd.read_csv(os.path.join(data_dir, "load_curve_data.csv"), encoding=common_encoding)
        df_customers = pd.read_csv(os.path.join(data_dir, "examplecustomerdata.csv"), encoding=common_encoding)
        df_consump = pd.read_csv(os.path.join(data_dir, "exampleconsump.csv"), encoding=common_encoding)
        df_sld = pd.read_csv(os.path.join(data_dir, "exampleSLD.csv"), encoding=common_encoding)
        df_sl = pd.read_csv(os.path.join(data_dir, "exampleSL.csv"), encoding=common_encoding)
    except Exception as e:
        print(f"Error loading load curve files: {e}")
        return []

    # Clean column names
    for df in [df_trans, df_curves, df_customers, df_consump, df_sld, df_sl]:
        df.columns = [c.replace('\n', ' ').replace('\r', ' ').strip() for c in df.columns]
        df.columns = [' '.join(c.split()) for c in df.columns]

    # 1. Map Load Curve hourly sums
    hour_cols = [f"Hour {i}" for i in range(1, 25)]
    df_curves['daily_sum'] = df_curves[hour_cols].sum(axis=1)
    curve_map = df_curves.set_index('Customer Type')['daily_sum'].to_dict()
    curve_multi_map = df_curves.set_index('Customer Type')[hour_cols].to_dict('index')

    # 2. Map Consumer Average Energy
    avg_consump = df_consump.groupby('Customer ID')['Energy Consumed (kWHr)'].mean().to_dict()
    customer_type = df_customers.set_index('Customer ID')['Customer Type'].to_dict()

    # 3. Build Network Hierarchy
    node_to_trans = {}
    for _, row in df_trans.iterrows():
        bus_id = str(row['To Secondary Bus ID']).strip()
        trans_id = str(row['Distribution Transformer ID']).strip()
        node_to_trans[bus_id] = trans_id

    for _, row in df_sl.iterrows():
        from_bus = str(row['From Bus ID']).strip()
        to_bus = str(row['To Bus ID']).strip()
        if from_bus in node_to_trans:
            node_to_trans[to_bus] = node_to_trans[from_bus]
    
    # 4. Map Customers to Transformers
    trans_loads = {} 
    for _, row in df_sld.iterrows():
        node_id = str(row['From Bus ID']).strip()
        cust_id = row['To Customer ID']
        if node_id in node_to_trans:
            trans_id = node_to_trans[node_id]
            kwh = avg_consump.get(cust_id, 0)
            ctype = customer_type.get(cust_id, 'RES1')
            if trans_id not in trans_loads:
                trans_loads[trans_id] = []
            trans_loads[trans_id].append((kwh, ctype))

    # 5. Calculate Hourly Load with PF and 95th Percentile
    results = []
    pf = 0.9
    
    for trans_id, ratings in trans_loads.items():
        t_info = df_trans[df_trans['Distribution Transformer ID'] == trans_id]
        if t_info.empty: continue
        kva = float(t_info.iloc[0]['KVA Rating'])
        capacity_kw = kva * pf
        
        hourly_totals = np.zeros(24)
        for kwh, ctype in ratings:
            s_c = curve_map.get(ctype, 24.0)
            if s_c == 0: s_c = 24.0
            peak_w = kwh / (max(kva, 1.0) * s_c) 
            
            # Use improved default multipliers mapping
            multipliers = curve_multi_map.get(ctype, {f"Hour {i}": 1.0 for i in range(1, 25)})
            for h in range(24):
                hourly_totals[h] += peak_w * multipliers[f"Hour {h+1}"]
        
        # Use 95th percentile to avoid spikes
        peak_load_kw = np.percentile(hourly_totals, 95)
        utilization = (peak_load_kw / capacity_kw) * 100 if capacity_kw > 0 else 0
        
        # Stress Classification
        if utilization < 40:
            status = "Underutilized"
        elif utilization < 80:
            status = "Normal"
        elif utilization < 100:
            status = "High Load"
        else:
            status = "Overloaded"
            
        results.append({
            'transformer_id': trans_id,
            'peak_load_kw': round(peak_load_kw, 2),
            'capacity_kva': kva,
            'capacity_kw': round(capacity_kw, 2),
            'utilization_percent': round(utilization, 2),
            'load_status': status
        })

    return results

if __name__ == "__main__":
    res = calculate_transformer_load_stress()
    print(f"Tested load flow stress calculation. Computed {len(res)} transformers.")
