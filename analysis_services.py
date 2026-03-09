import pandas as pd
import numpy as np
import os
from datetime import datetime
from extensions import db
from models import Post, DistributionTransformer, SecondaryServiceDrop, Customer, EnergyConsumption
from network_geometry_db import build_topology_graph, trace_feeder_bfs

def calculate_outage_impact(start_bus_id):
    """
    Calculates the impact of an outage starting from a specific bus node.
    Returns:
    """
    from flask import current_app
    from models import Post

    # Resolve pole number to primary_bus_id if needed
    post = Post.query.filter((Post.primary_bus_id == start_bus_id) | (Post.pole_number == start_bus_id)).first()
    actual_start_bus = post.primary_bus_id if post else start_bus_id

    # 1. Trace entire downstream network from start_bus
    graph = build_topology_graph(current_app)
    downstream_buses = trace_feeder_bfs(current_app, actual_start_bus)
    
    if not downstream_buses:
        return {
            'total_customers': 0,
            'total_load_kwh': 0,
            'affected_transformer_ids': [],
            'customer_details': [],
            'downstream_bus_count': 0
        }

    # 2. Find all Service Drops connected to these buses
    service_drops = SecondaryServiceDrop.query.filter(
        SecondaryServiceDrop.from_bus_id.in_(downstream_buses)
    ).all()
    
    affected_customer_ids = [sd.to_customer_id for sd in service_drops if sd.to_customer_id]
    
    # 3. Find affected Transformers (for metadata)
    transformers = DistributionTransformer.query.filter(
        DistributionTransformer.from_primary_bus_id.in_(downstream_buses)
    ).all()
    affected_transformer_ids = [t.transformer_id for t in transformers]

    # 4. Get Customer data and latest consumption for load loss estimation
    unique_customer_ids = list(set(affected_customer_ids))
    customers = Customer.query.filter(Customer.customer_id.in_(unique_customer_ids)).all()
    
    # Pre-fetch all consumption data into a string-keyed dictionary to avoid type mismatch
    # Aggressively normalize IDs to handle "0001" vs "1" or padding issues
    all_consump = EnergyConsumption.query.all()
    consump_map = {}
    for ec in all_consump:
        if ec.customer_id:
            norm_id = str(ec.customer_id).strip().lower().lstrip('0')
            consump_map[norm_id] = float(ec.kwh_consumed or 0)
    
    total_load = 0
    customer_details = []
    
    for c in customers:
        if not c.customer_id:
            continue
            
        c_id_norm = str(c.customer_id).strip().lower().lstrip('0')
        load = consump_map.get(c_id_norm, 0)

        
        total_load += load
        
        customer_details.append({
            'customer_id': c.customer_id,
            'name': c.name,
            'type': c.customer_type,
            'load_kwh': load
        })

    return {
        'total_customers': len(unique_customer_ids),
        'total_load_kwh': round(total_load, 2),
        'affected_transformer_ids': affected_transformer_ids,
        'customer_details': customer_details,
        'downstream_bus_count': len(downstream_buses)
    }

def calculate_transformer_load_stress():
    """
    Calculates load stress for all transformers in the database.
    Integrates logic from calculate_load_stress.py using DB models.
    """
    # Load curve data from CSV (still useful as lookup)
    # Assuming the app's root directory is used
    base_dir = os.path.abspath(os.path.dirname(__file__))
    curve_path = os.path.join(base_dir, "load_curve_data.csv")
    
    try:
        df_curves = pd.read_csv(curve_path, encoding='latin-1')
        df_curves.columns = [c.replace('\n', ' ').replace('\r', ' ').strip() for c in df_curves.columns]
        df_curves.columns = [' '.join(c.split()) for c in df_curves.columns]
        
        hour_cols = [f"Hour {i}" for i in range(1, 25)]
        df_curves['daily_sum'] = df_curves[hour_cols].sum(axis=1)
        curve_map = df_curves.set_index('Customer Type')['daily_sum'].to_dict()
        curve_multi_map = df_curves.set_index('Customer Type')[hour_cols].to_dict('index')
    except Exception as e:
        # Fallback if CSV is missing
        curve_map = {}
        curve_multi_map = {}

    # Get all transformers
    transformers = DistributionTransformer.query.all()
    if not transformers:
        return []

    # Optimization: Bulk load all required data to avoid thousands of individual queries
    from collections import defaultdict
    
    # 1. Map Secondary Bus -> Service Drops
    drops_by_bus = defaultdict(list)
    for sd in SecondaryServiceDrop.query.all():
        if sd.from_bus_id:
            drops_by_bus[sd.from_bus_id.strip()].append(sd)
            
    # 2. Map Customer ID -> Type
    cust_type_map = {c.customer_id: (c.customer_type or 'RES1') for c in Customer.query.all()}
    
    # 3. Map Customer ID -> Latest Consumption (simulated "latest" by loading all if needed, but here we assume one record per customer for proto)
    # In a real system, we'd use a more specialized query, but for 13k records this is fine.
    all_consump = EnergyConsumption.query.all()
    consump_map = defaultdict(float)
    for ec in all_consump:
        # Simple policy: overwrite with latest (assumes query order is stable or we don't care for proto)
        consump_map[ec.customer_id] = float(ec.kwh_consumed or 0)

    results = []
    pf = 0.9

    for trans in transformers:
        kva = trans.kva_rating or 0
        if kva == 0: continue
        capacity_kw = kva * pf

        sec_bus_id = (trans.to_secondary_bus_id or "").strip()
        if not sec_bus_id: continue

        service_drops = drops_by_bus.get(sec_bus_id, [])
        
        hourly_totals = np.zeros(24)
        for sd in service_drops:
            cid = sd.to_customer_id
            if not cid: continue
            
            kwh = consump_map.get(cid, 0)
            ctype = cust_type_map.get(cid, 'RES1')
            
            s_c = curve_map.get(ctype, 24.0)
            if s_c == 0: s_c = 24.0
            peak_w = kwh / (30.0 * s_c)
            
            multipliers = curve_multi_map.get(ctype, {f"Hour {i}": 1.0 for i in range(1, 25)})
            for h in range(24):
                hourly_totals[h] += peak_w * multipliers[f"Hour {h+1}"]

        peak_load_kw = np.percentile(hourly_totals, 95) if len(service_drops) > 0 else 0
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
            'transformer_id': trans.transformer_id,
            'peak_load_kw': round(float(peak_load_kw), 2),
            'capacity_kva': kva,
            'capacity_kw': round(float(capacity_kw), 2),
            'utilization_percent': round(float(utilization), 2),
            'load_status': status
        })

    return results

def get_grid_health_analytics():
    """
    Consolidates ML failure risk and load stress data into a single health report.
    Used by Layer 2 (API) to provide a combined GeoJSON-friendly summary.
    """
    from ml_predictor import predict_transformer_risk
    
    # 1. Get Load Stress Analysis
    stress_results = calculate_transformer_load_stress()
    stress_map = {r['transformer_id']: r for r in stress_results}
    
    # 2. Get ML Failure Risk Analysis
    transformers = DistributionTransformer.query.all()
    if not transformers:
        return {'summary': {'total': 0, 'critical': 0, 'high': 0, 'medium': 0, 'low': 0}, 'details': [], 'model_info': {}}
        
    db_records = [t.to_dict() for t in transformers]
    ml_results = predict_transformer_risk(source='db', db_records=db_records)
    
    # 3. Merge results — keep ALL original ML fields and add load stress data
    combined_details = []
    for ml_pred in ml_results.get('predictions', []):
        tid = ml_pred['transformer_id']
        stress = stress_map.get(tid, {})
        
        # Start with all ML prediction fields (rank, transformer_id, kva_rating, etc.)
        merged = dict(ml_pred)
        # Add load stress fields
        merged['utilization_percent'] = stress.get('utilization_percent', 0)
        merged['load_status'] = stress.get('load_status', 'Unknown')
        merged['health_index'] = round(( (100 - ml_pred['risk_score']) + (100 - max(0, stress.get('utilization_percent', 0)-100)) ) / 2, 1)
        combined_details.append(merged)
        
    return {
        'summary': ml_results.get('summary', {}),
        'details': combined_details,
        'model_info': ml_results.get('model_info', {}),
        'timestamp': datetime.utcnow().isoformat()
    }


def get_service_drops_for_post(post_id):
    """
    Traces from a Post -> [Buses] -> Transformers -> [Secondary BFS] -> Service Drops.
    Returns list of SecondaryServiceDrop objects.
    """
    from models import Post, DistributionTransformer, SecondaryLineSegment, SecondaryServiceDrop, BusNode
    p = Post.query.get(post_id)
    if not p: return []

    # 1. Collect all "root" buses associated with this pole
    root_buses = set()
    if p.pole_number: root_buses.add(p.pole_number)
    if p.primary_bus_id: root_buses.add(p.primary_bus_id)
    if getattr(p, 'sec_bus_id', None): root_buses.add(p.sec_bus_id)
    if getattr(p, 'transformer_bus_id', None): root_buses.add(p.transformer_bus_id)
    
    # Also find any BusNodes that point to this pole
    bns = BusNode.query.filter_by(pole_number=p.pole_number).all()
    for bn in bns:
        root_buses.add(bn.bus_id)

    # 2. Find any transformers connected to these root buses
    transformers = DistributionTransformer.query.filter(
        DistributionTransformer.from_primary_bus_id.in_(list(root_buses))
    ).all()

    # 3. BFS downstream from each transformer's secondary bus
    all_drops = {}
    visited_sec_buses = set()
    
    for tx in transformers:
        sec_start = tx.to_secondary_bus_id
        if not sec_start or sec_start in visited_sec_buses:
            continue
            
        queue = [sec_start]
        visited_sec_buses.add(sec_start)
        
        while queue:
            curr = queue.pop(0)
            
            # A. Check for service drops at this bus
            drops = SecondaryServiceDrop.query.filter_by(from_bus_id=curr).all()
            for d in drops:
                all_drops[d.id] = d
            
            # B. Continue BFS through secondary lines
            lines = SecondaryLineSegment.query.filter(
                (SecondaryLineSegment.from_bus_id == curr) |
                (SecondaryLineSegment.to_bus_id == curr)
            ).all()
            
            for line in lines:
                nxt = line.from_bus_id if line.to_bus_id == curr else line.to_bus_id
                if nxt and nxt not in visited_sec_buses:
                    visited_sec_buses.add(nxt)
                    queue.append(nxt)

    # 4. Direct check for service drops linked to root buses
    for b_id in root_buses:
        direct_drops = SecondaryServiceDrop.query.filter_by(from_bus_id=b_id).all()
        for d in direct_drops:
            all_drops[d.id] = d
            
    return list(all_drops.values())

def find_customer_post_location(customer_id):
    """
    Traces the electrical network to find a customer's connected post.
    Chain: Customer → SSD → [Secondary BFS] → Transformer → Post
    Returns dict with lat, lng, id, name if found, else None.
    """
    from models import Post, DistributionTransformer, SecondaryLineSegment, SecondaryServiceDrop, BusNode
    
    # 1. Find the SecondaryServiceDrop for this customer
    ssd = SecondaryServiceDrop.query.filter_by(to_customer_id=customer_id).first()
    if not ssd or not ssd.from_bus_id:
        return None

    # 2. Helper to try finding a post by bus ID or normalized pole number
    def get_post_by_bus_or_pole(bus_id):
        if not bus_id: return None
        bus_id = str(bus_id).strip()
        p = Post.query.filter((Post.primary_bus_id == bus_id) | (Post.pole_number == bus_id)).first()
        if p and p.lat and p.lng: return p
        
        bn = BusNode.query.filter_by(bus_id=bus_id).first()
        if bn and bn.pole_number:
            p = Post.query.filter_by(pole_number=bn.pole_number).first()
            if p and p.lat and p.lng: return p
        return None

    # 3. BFS from the SSD bus to find a DistributionTransformer or direct Post
    start_bus = ssd.from_bus_id.strip()
    visited = {start_bus}
    queue = [start_bus]
    
    while queue:
        curr = queue.pop(0)
        
        # Check if this bus is a pole
        post = get_post_by_bus_or_pole(curr)
        if post:
            return {'lat': post.lat, 'lng': post.lng, 'id': post.id, 'name': post.name}
        
        # Check if this bus is connected to a transformer secondary
        dt = DistributionTransformer.query.filter_by(to_secondary_bus_id=curr).first()
        if dt:
            # Trace back to transformer's primary post
            p_post = get_post_by_bus_or_pole(dt.from_primary_bus_id)
            if p_post:
                return {'lat': p_post.lat, 'lng': p_post.lng, 'id': p_post.id, 'name': p_post.name}
            
        # Otherwise, find connected secondary lines and continue BFS
        lines = SecondaryLineSegment.query.filter(
            (SecondaryLineSegment.from_bus_id == curr) |
            (SecondaryLineSegment.to_bus_id == curr)
        ).all()
        
        for line in lines:
            nxt = line.from_bus_id if line.to_bus_id == curr else line.to_bus_id
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)

    return None
