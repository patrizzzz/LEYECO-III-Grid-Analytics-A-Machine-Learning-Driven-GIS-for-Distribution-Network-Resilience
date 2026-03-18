import pandas as pd
import numpy as np
import os
from datetime import datetime
from extensions import db
from models import Post, DistributionTransformer, SecondaryServiceDrop, Customer, EnergyConsumption, LoadCurve
from .network_geometry_db import build_topology_graph, trace_feeder_bfs, trace_downstream_bfs
from .topology_service import TopologyService

def calculate_outage_impact(start_bus_id):
    """
    Calculates the impact of an outage starting from a specific bus node.
    Uses SQL RECURSIVE CTE for high-performance downstream tracing.
    """
    from flask import current_app
    from models import Post, BusNode
    from .network_geometry_db import resolve_all_bus_ids

    # 1. Resolve starting point to all associated bus IDs
    root_buses = resolve_all_bus_ids(start_bus_id)

    # 2. Trace DOWNSTREAM-ONLY network using high-performance SQL CTE
    all_downstream = set()
    for rb in root_buses:
        path = TopologyService.trace_downstream_sql(rb)
        all_downstream.update(path)
    
    downstream_buses = list(all_downstream)
    
    if not downstream_buses:
        return {
            'total_customers': 0,
            'total_load_kwh': 0,
            'affected_transformer_ids': [],
            'customer_details': [],
            'downstream_bus_count': 0,
            'visited_buses': []
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
    
    # Pre-fetch consumption data
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
        'downstream_bus_count': len(downstream_buses),
        'visited_buses': downstream_buses
    }

def calculate_transformer_load_stress():
    """
    Calculates load stress for all transformers in the database.
    Integrates logic from calculate_load_stress.py using DB models.
    """
    # Load curve data from Database
    try:
        curves = LoadCurve.query.all()
        curve_map = {}
        curve_multi_map = {}
        hour_cols = [f"hour_{i}" for i in range(1, 25)]
        
        for c in curves:
            ctype = c.customer_type
            if not ctype: continue
            
            multipliers = {f"Hour {i}": getattr(c, f"hour_{i}") for i in range(1, 25)}
            daily_sum = sum(multipliers.values())
            
            curve_map[ctype] = daily_sum
            curve_multi_map[ctype] = multipliers
            
        # If DB is empty, try fallback to original CSV if it exists
        if not curves:
            base_dir = os.path.abspath(os.path.dirname(__file__))
            curve_path = os.path.join(base_dir, "load_curve_data.csv")
            if os.path.exists(curve_path):
                df_curves = pd.read_csv(curve_path, encoding='latin-1')
                df_curves.columns = [c.replace('\n', ' ').replace('\r', ' ').strip() for c in df_curves.columns]
                df_curves.columns = [' '.join(c.split()) for c in df_curves.columns]
                
                h_cols = [f"Hour {i}" for i in range(1, 25)]
                df_curves['daily_sum'] = df_curves[h_cols].sum(axis=1)
                curve_map.update(df_curves.set_index('Customer Type')['daily_sum'].to_dict())
                curve_multi_map.update(df_curves.set_index('Customer Type')[h_cols].to_dict('index'))
    except Exception as e:
        current_app.logger.warning(f"Failed to fetch load curves from DB: {e}")
        curve_map = {}
        curve_multi_map = {}

    # Get all transformers
    transformers = DistributionTransformer.query.all()
    if not transformers:
        return []

    # Optimization: Bulk load all required data to avoid thousands of individual queries
    from collections import defaultdict
    
    # 1. Adjacency list for Secondary Lines (undirected for BFS)
    adj = defaultdict(list)
    from models import SecondaryLineSegment
    for line in SecondaryLineSegment.query.all():
        f_id = (line.from_bus_id or "").strip()
        t_id = (line.to_bus_id or "").strip()
        if f_id and t_id:
            adj[f_id].append(t_id)
            adj[t_id].append(f_id)

    # 2. Map Bus ID -> Service Drops
    drops_by_bus = defaultdict(list)
    for sd in SecondaryServiceDrop.query.all():
        if sd.from_bus_id:
            drops_by_bus[sd.from_bus_id.strip()].append(sd)
            
    # 3. Map Customer ID -> Type
    cust_type_map = {c.customer_id: (c.customer_type or 'RES1') for c in Customer.query.all()}
    
    # 4. Map Customer ID -> Latest Consumption
    all_consump = EnergyConsumption.query.all()
    consump_map = defaultdict(float)
    for ec in all_consump:
        consump_map[ec.customer_id] = float(ec.kwh_consumed or 0)

    results = []
    pf = 0.9

    for trans in transformers:
        kva = trans.kva_rating or 0
        if kva == 0: continue
        capacity_kw = kva * pf

        sec_bus_id = (trans.to_secondary_bus_id or "").strip()
        if not sec_bus_id: continue

        # --- Optimized SQL Tracing to find all downstream service drops ---
        downstream_ids = TopologyService.trace_downstream_sql(sec_bus_id)
        
        # Filter for service drops and customers in the downstream set
        service_drops = [sd for sd in SecondaryServiceDrop.query.filter(
            SecondaryServiceDrop.from_bus_id.in_(downstream_ids)
        ).all()]
        # --- End Optimized Tracing ---
        
        hourly_totals = np.zeros(24)
        for sd in service_drops:
            cid = sd.to_customer_id
            if not cid: continue
            
            kwh = consump_map.get(cid, 0)
            ctype = cust_type_map.get(cid, 'RES1')
            
            s_c = curve_map.get(ctype, 24.0)
            if s_c == 0: s_c = 24.0
            peak_w = kwh / (max(kva, 1.0) * s_c)
            
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
            'customer_count': len(service_drops),
            'load_status': status
        })

    return results

def get_grid_health_analytics(force_refresh=False):
    """
    Consolidates ML failure risk and load stress data into a single health report.
    Used by Layer 2 (API) to provide a combined GeoJSON-friendly summary.
    """
    from .ml_predictor import predict_transformer_risk, export_snapshot, load_snapshot
    
    # 0. Try loading from snapshot first (unless force_refresh is True)
    if not force_refresh:
        snapshot = load_snapshot()
        if snapshot:
            snapshot['is_snapshot'] = True
            return snapshot
    
    # 1. Get Load Stress Analysis
    stress_results = calculate_transformer_load_stress()
    stress_map = {r['transformer_id']: r for r in stress_results}
    
    # 1b. Fallback: If service drops are empty, estimate customer counts per transformer
    #     by distributing total customers proportionally based on kVA rating.
    total_sd_customers = sum(r.get('customer_count', 0) for r in stress_results)
    total_db_customers = Customer.query.count()
    
    if total_sd_customers == 0 and total_db_customers > 0 and stress_results:
        # No service drops uploaded — distribute customers proportionally by kVA
        total_kva_all = sum((stress_map[tid].get('capacity_kva', 0) or 1) for tid in stress_map) or 1
        for tid, sdata in stress_map.items():
            kva = sdata.get('capacity_kva', 0) or 1
            estimated_count = max(1, round(total_db_customers * (kva / total_kva_all)))
            sdata['customer_count'] = estimated_count
            sdata['customer_count_estimated'] = True
    
    # 2. Get ML Failure Risk Analysis
    transformers = DistributionTransformer.query.all()
    if not transformers:
        return {'summary': {'total': 0, 'critical': 0, 'high': 0, 'medium': 0, 'low': 0}, 'details': [], 'model_info': {}}
        
    db_records = []
    for t in transformers:
        record = t.to_dict()
        tid = t.transformer_id
        stress = stress_map.get(tid, {})
        # Inject stress metrics so ML model sees them as features
        record['utilization_percent'] = stress.get('utilization_percent', 0)
        db_records.append(record)
        
    ml_results = predict_transformer_risk(source='db', db_records=db_records)

    # Compute average kVA for the criticality formula
    total_kva = sum(t.kva_rating or 0 for t in transformers)
    avg_kva = max(total_kva / len(transformers), 1.0) if transformers else 1.0
    
    # Build a map from transformer_id -> from_primary_bus_id for frontend lookup
    trans_bus_map = {t.transformer_id: t.from_primary_bus_id for t in transformers if t.from_primary_bus_id}
    
    # Build a map from from_primary_bus_id -> Post to get post_id for frontend _mlRiskMap lookup
    # The popup looks up by p.id (Post.id), so we need post_id in the ML predictions
    all_primary_bus_ids = [t.from_primary_bus_id for t in transformers if t.from_primary_bus_id]
    posts_by_bus = {}
    if all_primary_bus_ids:
        from models import BusNode
        matched_posts = Post.query.filter(
            (Post.primary_bus_id.in_(all_primary_bus_ids)) | (Post.pole_number.in_(all_primary_bus_ids))
        ).all()
        for p in matched_posts:
            if p.primary_bus_id:
                posts_by_bus[p.primary_bus_id] = p.id
            if p.pole_number:
                posts_by_bus[str(p.pole_number)] = p.id
        # Also try BusNode -> Post lookup for any still-unmatched bus IDs
        unmatched = [bid for bid in all_primary_bus_ids if bid not in posts_by_bus]
        if unmatched:
            bn_posts = BusNode.query.filter(BusNode.bus_id.in_(unmatched)).all()
            for bn in bn_posts:
                if bn.pole_number:
                    p2 = Post.query.filter_by(pole_number=bn.pole_number).first()
                    if p2:
                        posts_by_bus[bn.bus_id] = p2.id
    
    # 3. Merge results — keep ALL original ML fields and add load stress data
    combined_details = []
    for ml_pred in ml_results.get('predictions', []):
        tid = ml_pred['transformer_id']
        stress = stress_map.get(tid, {})
        
        # Start with all ML prediction fields (rank, transformer_id, kva_rating, etc.)
        merged = dict(ml_pred)
        
        # Add from_primary_bus_id and post_id so the frontend can match to map markers
        primary_bus = trans_bus_map.get(tid, '')
        merged['from_primary_bus_id'] = primary_bus
        merged['post_id'] = posts_by_bus.get(primary_bus, None) if primary_bus else None
        
        # Add load stress fields
        util_pct = stress.get('utilization_percent', 0)
        cust_count = stress.get('customer_count', 0)
        kva = ml_pred.get('kva_rating', 0) or 0
        
        # Fallback: if this transformer has no stress data but customers exist in DB,
        # estimate a minimum customer count based on kVA proportion
        if cust_count == 0 and total_db_customers > 0 and kva > 0:
            fallback_count = max(1, round(total_db_customers * (kva / max(total_kva, 1))))
            cust_count = fallback_count
        
        merged['utilization_percent'] = util_pct
        merged['customer_count'] = cust_count
        merged['load_status'] = stress.get('load_status', 'Unknown')
        
        # Impact Scoring Refinements:
        # 1. Normalized & Clamped Utilization (e.g. 1.2 for 120%, max 1.5)
        u_clamped = min(util_pct, 150) / 100.0
        
        # 2. Criticality Score: customers * utilization * (kva / avg_kva)
        criticality = cust_count * u_clamped * (kva / avg_kva)
        
        # 3. Final Impact Score: ML Risk * Criticality
        risk_factor = (ml_pred.get('risk_score', 0) / 100.0)
        impact_score = risk_factor * criticality
        
        merged['criticality_score'] = round(float(criticality), 2)
        merged['impact_score'] = round(float(impact_score), 2)
        
        # 4. Categorize Risk Levels
        # ML Risk level (Probability of failure)
        merged['ml_risk_level'] = ml_pred.get('risk_level', 'Low')
        
        # Impact level (Consequence of failure)
        if impact_score >= 25:
            merged['impact_level'] = 'Critical'
        elif impact_score >= 10:
            merged['impact_level'] = 'High'
        elif impact_score >= 5:
            merged['impact_level'] = 'Medium'
        else:
            merged['impact_level'] = 'Low'
            
        # Keep risk_level as impact-based for the dashboard statistics but 
        # consider renaming it later if we want the dashboard to show ML probability.
        merged['risk_level'] = merged['impact_level']
        
        merged['health_index'] = round(( (100 - ml_pred['risk_score']) + (100 - max(0, util_pct-100)) ) / 2, 1)
        combined_details.append(merged)
    
    # 4. Sort by Impact Score Descending
    combined_details.sort(key=lambda x: x['impact_score'], reverse=True)
    
    # 5. Assign Impact Rank
    for i, item in enumerate(combined_details):
        item['impact_rank'] = i + 1
        
    # 6. Re-calculate Summary based on Impact-based Categorization
    summary = {
        'total': len(combined_details),
        'critical': sum(1 for r in combined_details if r['risk_level'] == 'Critical'),
        'high': sum(1 for r in combined_details if r['risk_level'] == 'High'),
        'medium': sum(1 for r in combined_details if r['risk_level'] == 'Medium'),
        'low': sum(1 for r in combined_details if r['risk_level'] == 'Low'),
    }

    analysis_final = {
        'summary': summary,
        'details': combined_details,
        'model_info': ml_results.get('model_info', {}),
        'timestamp': datetime.utcnow().isoformat(),
        'is_snapshot': False
    }

    # 7. Export an initial snapshot if one doesn't exist, or if forced to refresh, to "freeze" results
    try:
        if force_refresh or not load_snapshot():
            export_snapshot(analysis_final)
    except Exception as e:
        current_app.logger.warning(f"Failed to auto-export snapshot: {e}")

    return analysis_final


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

    # 3. Use high-performance SQL trace to find the upstream path
    upstream_ids = TopologyService.trace_upstream_sql(ssd.from_bus_id.strip())
    
    # Check the path for the first Post or Transformer primary node
    for curr in upstream_ids:
        post = get_post_by_bus_or_pole(curr)
        if post:
            return {'lat': post.lat, 'lng': post.lng, 'id': post.id, 'name': post.name}
            
        dt = DistributionTransformer.query.filter_by(to_secondary_bus_id=curr).first()
        if dt:
            p_post = get_post_by_bus_or_pole(dt.from_primary_bus_id)
            if p_post:
                return {'lat': p_post.lat, 'lng': p_post.lng, 'id': p_post.id, 'name': p_post.name}

    return None
