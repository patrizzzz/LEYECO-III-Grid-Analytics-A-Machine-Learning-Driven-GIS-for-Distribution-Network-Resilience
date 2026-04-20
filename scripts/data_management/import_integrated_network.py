#!/usr/bin/env python3
"""
Integrated Network Importer specializing in joining:
1. EXAMPLEDATA.csv (Topology: From/To Bus IDs)
2. bus_data.csv (Mapping: Bus ID -> pole_id)
3. pole.csv (Coordinates: pole_id -> Lat/Lng)

This script ensures that Posts and BusNodes are correctly localized on the map.
"""

import os
import sys
import pandas as pd
import re
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from app import app, db
from models import Post, BusNode, DistributionLineSegment, LineConnection

def normalize_id(id_str):
    """
    Standardize IDs (like P00000001 -> P1, DT000001 -> DT1).
    This ensures consistent matching across multiple CSV files.
    """
    if not id_str or pd.isna(id_str):
        return ""
    s = str(id_str).strip().upper()
    
    # regex to find prefix (letters) and number part
    match = re.match(r'^([a-zA-Z]+)(\d+)(.*)$', s)
    if match:
        prefix, num_part, suffix = match.groups()
        # Strip leading zeros from number part
        num_part = num_part.lstrip('0') or '0'
        return f"{prefix}{num_part}{suffix}"
    
    return s

def normalize_column(name):
    """Universal column normalization for electrical CSVs"""
    if not name or pd.isna(name):
        return ""
    # Handle newlines, multiple spaces, etc.
    n = str(name).strip().lower()
    n = re.sub(r'\s+', '_', n)
    return n.strip('_')

def import_integrated():
    base_path = Path("data/samples/csv_data")
    pole_csv = base_path / "pole.csv"
    bus_csv = base_path / "bus_data.csv"
    lines_csv = base_path / "EXAMPLEDATA.csv"

    if not all(p.exists() for p in [pole_csv, bus_csv, lines_csv]):
        print("Error: Missing one or more required CSV files in data/samples/csv_data/")
        print(f"Pole: {pole_csv.exists()}, Bus: {bus_csv.exists()}, Lines: {lines_csv.exists()}")
        return

    with app.app_context():
        print("=" * 80)
        print("STARTING INTEGRATED NETWORK IMPORT")
        print("=" * 80)

        # 1. Load Pole Coordinates
        print("\n[STEP 1] Loading Coordinates from pole.csv...")
        poles_df = pd.read_csv(pole_csv)
        # pole_id is 1-based index (row 0 in DF + 1)
        pole_coords = {}
        for idx, row in poles_df.iterrows():
            pole_id = idx + 1
            pole_coords[pole_id] = (row['latitude'], row['longitude'])
        print(f"   Loaded {len(pole_coords)} coordinates.")

        # 2. Load Bus Mapping
        print("\n[STEP 2] Loading Bus Mappings from bus_data.csv...")
        bus_df = pd.read_csv(bus_csv)
        bus_df.columns = [normalize_column(c) for c in bus_df.columns]
        
        bus_to_pole = {}
        bus_details = {} # Store voltage, feeder etc
        
        for _, row in bus_df.iterrows():
            raw_bus_id = row.get('bus_id')
            p_id = row.get('pole_id')
            if pd.isna(raw_bus_id) or pd.isna(p_id):
                continue
            
            norm_id = normalize_id(raw_bus_id)
            p_id = int(p_id)
            
            bus_to_pole[norm_id] = p_id
            bus_details[norm_id] = {
                'feeder': row.get('feeder'),
                'description': row.get('bus_description'),
                'voltage': row.get('nominal_voltage_kv')
            }
        print(f"   Mapped {len(bus_to_pole)} Bus IDs.")

        # 3. Create Posts based on Bus IDs and Coordinates
        print("\n[STEP 3] Synchronizing Posts and BusNodes...")
        for norm_id, p_id in bus_to_pole.items():
            if p_id not in pole_coords:
                continue
            
            lat, lng = pole_coords[p_id]
            details = bus_details.get(norm_id, {})
            
            # Sync Post
            post = Post.query.filter_by(pole_number=norm_id).first()
            if not post:
                # Also try matching by p_id as pole_number if it looks like a pole ID
                post = Post.query.filter_by(pole_number=str(p_id)).first()
            
            if not post:
                post = Post(pole_number=norm_id, name=f"Post {norm_id}", lat=lat, lng=lng)
                db.session.add(post)
            else:
                post.lat = lat
                post.lng = lng
            
            post.feeder = details.get('feeder')
            post.primary_bus_id = norm_id
            
            # Sync BusNode
            bn = BusNode.query.filter_by(bus_id=norm_id).first()
            if not bn:
                bn = BusNode(bus_id=norm_id)
                db.session.add(bn)
            
            bn.lat = lat
            bn.lng = lng
            bn.pole_id = post.id
            bn.pole_number = post.pole_number
            bn.feeder = details.get('feeder')
            bn.nominal_voltage = details.get('voltage')
            bn.bus_description = details.get('description')

        db.session.commit()
        print("   Posts and BusNodes synchronized.")

        # 4. Import Line Segments
        print("\n[STEP 4] Importing Topology from EXAMPLEDATA.csv...")
        lines_df = pd.read_csv(lines_csv)
        lines_df.columns = [normalize_column(c) for c in lines_df.columns]
        
        created_lines = 0
        connections = 0
        
        for _, row in lines_df.iterrows():
            seg_id = (row.get('primary_distribution_line_segment_id') or 
                     row.get('segment_id') or 
                     row.get('distribution_line_segment_id'))
            
            from_bus_raw = (row.get('from_bus_id') or row.get('from_bus'))
            to_bus_raw = (row.get('to_bus_id') or row.get('to_bus'))
            
            if not seg_id or not from_bus_raw or not to_bus_raw:
                continue
                
            from_norm = normalize_id(from_bus_raw)
            to_norm = normalize_id(to_bus_raw)
            
            # Upsert Line Segment
            seg = DistributionLineSegment.query.filter_by(segment_id=str(seg_id)).first()
            if not seg:
                seg = DistributionLineSegment(segment_id=str(seg_id))
                db.session.add(seg)
                created_lines += 1
            
            seg.from_bus_id = from_norm
            seg.to_bus_id = to_norm
            seg.length_meters = row.get('length_meters') or row.get('length')
            seg.phasing = row.get('phasing')
            seg.configuration = row.get('configuration')
            
            # Create/Sync Connection
            conn = LineConnection.query.filter_by(
                from_bus=from_norm, 
                to_bus=to_norm, 
                connection_type='Primary_to_Primary'
            ).first()
            if not conn:
                conn = LineConnection(
                    from_bus=from_norm,
                    to_bus=to_norm,
                    connection_type='Primary_to_Primary',
                    phasing=seg.phasing
                )
                db.session.add(conn)
                connections += 1

        db.session.commit()
        print(f"   Created/Updated {created_lines} line segments.")
        print(f"   Established {connections} topological connections.")

        print("\n" + "=" * 80)
        print("INTEGRATED IMPORT COMPLETE")
        print("=" * 80)

if __name__ == '__main__':
    import_integrated()
