#!/usr/bin/env python3
"""
Infer electrical line connections (From Bus → To Bus) from pole infrastructure data.

Rules:
1. Primary Bus → Primary Bus: Connect primary buses with same Feeder & Circuit, ordered by Pole Number
2. Primary Bus → Transformer Bus: If both present in a row
3. Transformer Bus → Secondary Bus: If both present in a row
4. Secondary Bus → Secondary Bus: If same Sec. Bus ID across rows, or sequential Sec. Structure

Output: connections.csv with normalized format for GIS/network visualization
"""

import csv
import pandas as pd
from pathlib import Path
from collections import defaultdict

def normalize_bus_id(bus_id):
    """Normalize bus ID for consistent matching"""
    if pd.isna(bus_id) or bus_id == '' or bus_id is None:
        return None
    return str(bus_id).strip()

def infer_connections(csv_file):
    """
    Read CSV and infer all connections based on rules.
    Returns list of connection dicts: {From_Bus, To_Bus, Connection_Type, Feeder, Circuit}
    """
    
    # Read CSV
    df = pd.read_csv(csv_file)
    
    print(f"📊 Analyzing {len(df)} rows from {Path(csv_file).name}")
    print(f"   Columns: {list(df.columns)}\n")
    
    connections = []
    connection_set = set()  # Track (from, to, type) to avoid duplicates
    
    # Group data by meaningful identifiers
    feeder_circuit_groups = defaultdict(list)  # (Feeder, Circuit) -> list of rows
    sec_bus_groups = defaultdict(list)  # Sec. Bus ID -> list of rows
    transformer_rows = []  # Rows with Transformer Bus ID
    
    # Normalize column names (handle spaces and different cases)
    col_mapping = {}
    for col in df.columns:
        col_lower = col.lower().strip()
        col_mapping[col] = col_lower
    
    # First pass: collect data into groups
    for idx, row in df.iterrows():
        pole = normalize_bus_id(row.get('Pole Number'))
        feeder = normalize_bus_id(row.get('Feeder'))
        circuit = normalize_bus_id(row.get('Circuit'))
        pri_bus = normalize_bus_id(row.get('Primary Bus ID'))
        trans_bus = normalize_bus_id(row.get('Transformer Bus ID'))
        sec_bus = normalize_bus_id(row.get('Sec. Bus ID'))
        sec_structure = normalize_bus_id(row.get('Sec. Structure'))
        
        # Store normalized row
        row_data = {
            'pole': pole,
            'feeder': feeder,
            'circuit': circuit,
            'pri_bus': pri_bus,
            'trans_bus': trans_bus,
            'sec_bus': sec_bus,
            'sec_structure': sec_structure,
            'original_idx': idx
        }
        
        if feeder and circuit:
            feeder_circuit_groups[(feeder, circuit)].append(row_data)
        
        if sec_bus:
            sec_bus_groups[sec_bus].append(row_data)
        
        if trans_bus:
            transformer_rows.append(row_data)
    
    print("📈 Groups identified:")
    print(f"   • Feeder-Circuit groups: {len(feeder_circuit_groups)}")
    print(f"   • Secondary bus groups: {len(sec_bus_groups)}")
    print(f"   • Rows with transformer buses: {len(transformer_rows)}\n")
    
    # ===== RULE 1: Primary Bus → Primary Bus =====
    print("🔗 Rule 1: Primary Bus → Primary Bus (same Feeder & Circuit, ordered by Pole Number)")
    rule1_count = 0
    for (feeder, circuit), rows in feeder_circuit_groups.items():
        # Extract unique primary buses with pole numbers
        pri_buses = {}
        for r in rows:
            if r['pri_bus'] and r['pole']:
                if r['pri_bus'] not in pri_buses:
                    pri_buses[r['pri_bus']] = r['pole']
        
        # Sort by pole number (numeric if possible, else alphabetic)
        try:
            sorted_buses = sorted(pri_buses.items(), key=lambda x: float(x[1]) if x[1].replace('-', '').replace('.', '').isdigit() else float('inf'))
        except:
            sorted_buses = sorted(pri_buses.items(), key=lambda x: x[1])
        
        # Connect consecutive primary buses
        for i in range(len(sorted_buses) - 1):
            from_bus = sorted_buses[i][0]
            to_bus = sorted_buses[i + 1][0]
            
            conn_key = (from_bus, to_bus, 'Primary_to_Primary')
            if conn_key not in connection_set:
                connections.append({
                    'From_Bus': from_bus,
                    'To_Bus': to_bus,
                    'Connection_Type': 'Primary_to_Primary',
                    'Feeder': feeder,
                    'Circuit': circuit
                })
                connection_set.add(conn_key)
                rule1_count += 1
    
    print(f"   ✓ Created {rule1_count} primary-to-primary connections\n")
    
    # ===== RULE 2: Primary Bus to Transformer Bus =====
    print("🔗 Rule 2: Primary Bus to Transformer Bus")
    rule2_count = 0
    for row in transformer_rows:
        if row['pri_bus'] and row['trans_bus']:
            conn_key = (row['pri_bus'], row['trans_bus'], 'Primary_to_Transformer')
            if conn_key not in connection_set:
                connections.append({
                    'From_Bus': row['pri_bus'],
                    'To_Bus': row['trans_bus'],
                    'Connection_Type': 'Primary_to_Transformer',
                    'Feeder': row['feeder'],
                    'Circuit': row['circuit']
                })
                connection_set.add(conn_key)
                rule2_count += 1
    
    print(f"   ✓ Created {rule2_count} primary-to-transformer connections\n")
    
    # ===== RULE 3: Transformer Bus to Secondary Bus =====
    print("🔗 Rule 3: Transformer Bus to Secondary Bus")
    rule3_count = 0
    for row in transformer_rows:
        if row['trans_bus'] and row['sec_bus']:
            conn_key = (row['trans_bus'], row['sec_bus'], 'Transformer_to_Secondary')
            if conn_key not in connection_set:
                connections.append({
                    'From_Bus': row['trans_bus'],
                    'To_Bus': row['sec_bus'],
                    'Connection_Type': 'Transformer_to_Secondary',
                    'Feeder': row['feeder'],
                    'Circuit': row['circuit']
                })
                connection_set.add(conn_key)
                rule3_count += 1
    
    print(f"   ✓ Created {rule3_count} transformer-to-secondary connections\n")
    
    # ===== RULE 4: Secondary Bus to Secondary Bus =====
    print("🔗 Rule 4: Secondary Bus to Secondary Bus")
    rule4_count = 0
    
    # Sub-rule 4a: Same Sec. Bus ID across multiple rows
    for sec_bus, rows in sec_bus_groups.items():
        if len(rows) > 1:
            # Connect secondary bus through transformer/structure hierarchy
            # If multiple meters on same secondary bus, they're already connected through the bus
            # So just note this as a consolidated bus (not a connection edge)
            pass
    
    # Sub-rule 4b: Sequential Sec. Structure values
    for sec_bus, rows in sec_bus_groups.items():
        # Extract unique sec structures for this sec bus
        structures = set()
        sec_structures = {}
        for r in rows:
            if r['sec_structure']:
                structures.add(r['sec_structure'])
                if r['sec_structure'] not in sec_structures:
                    sec_structures[r['sec_structure']] = []
                sec_structures[r['sec_structure']].append(r)
        
        # If multiple structures on same secondary bus, connect them
        sorted_structures = sorted(structures)
        for i in range(len(sorted_structures) - 1):
            from_struct = sorted_structures[i]
            to_struct = sorted_structures[i + 1]
            
            # Use structure as identifier for sub-connections
            from_bus_id = f"{sec_bus}-{from_struct}"
            to_bus_id = f"{sec_bus}-{to_struct}"
            
            conn_key = (from_bus_id, to_bus_id, 'Secondary_to_Secondary')
            if conn_key not in connection_set:
                connections.append({
                    'From_Bus': from_bus_id,
                    'To_Bus': to_bus_id,
                    'Connection_Type': 'Secondary_to_Secondary',
                    'Feeder': rows[0]['feeder'],
                    'Circuit': rows[0]['circuit']
                })
                connection_set.add(conn_key)
                rule4_count += 1
    
    print(f"   ✓ Created {rule4_count} secondary-to-secondary connections\n")
    
    return connections

def create_bus_node_file(csv_file, output_file='bus_nodes.csv'):
    """Create a file of unique bus nodes for visualization"""
    
    df = pd.read_csv(csv_file)
    
    buses = set()
    bus_info = {}  # bus -> {feeder, circuit, pole}
    
    for idx, row in df.iterrows():
        pri_bus = normalize_bus_id(row.get('Primary Bus ID'))
        trans_bus = normalize_bus_id(row.get('Transformer Bus ID'))
        sec_bus = normalize_bus_id(row.get('Sec. Bus ID'))
        feeder = normalize_bus_id(row.get('Feeder'))
        circuit = normalize_bus_id(row.get('Circuit'))
        pole = normalize_bus_id(row.get('Pole Number'))
        
        for bus in [pri_bus, trans_bus, sec_bus]:
            if bus:
                buses.add(bus)
                if bus not in bus_info:
                    bus_info[bus] = {
                        'bus_id': bus,
                        'feeder': feeder or '',
                        'circuit': circuit or '',
                        'pole': pole or '',
                        'bus_type': 'Primary' if bus == pri_bus else ('Transformer' if bus == trans_bus else 'Secondary')
                    }
    
    # Write bus nodes
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['Bus_ID', 'Bus_Type', 'Feeder', 'Circuit', 'Pole'])
        writer.writeheader()
        for bus in sorted(buses):
            info = bus_info[bus]
            writer.writerow({
                'Bus_ID': info['bus_id'],
                'Bus_Type': info['bus_type'],
                'Feeder': info['feeder'],
                'Circuit': info['circuit'],
                'Pole': info['pole']
            })
    
    print(f"📍 Bus node file created: {output_file} ({len(buses)} unique buses)")

def main():
    csv_file = 'amonaini.csv'
    output_file = 'connections.csv'
    
    if not Path(csv_file).exists():
        print(f"❌ File not found: {csv_file}")
        return
    
    print("=" * 70)
    print("🔌 ELECTRICAL LINE CONNECTION INFERENCE")
    print("=" * 70)
    print()
    
    # Infer connections
    connections = infer_connections(csv_file)
    
    # Write connections to CSV
    if connections:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['From_Bus', 'To_Bus', 'Connection_Type', 'Feeder', 'Circuit'])
            writer.writeheader()
            for conn in connections:
                writer.writerow(conn)
        
        print(f"✅ Connections saved to: {output_file}")
        print(f"   Total connections: {len(connections)}")
        print()
        
        # Summary by type
        type_counts = defaultdict(int)
        for conn in connections:
            type_counts[conn['Connection_Type']] += 1
        
        print("📊 Connection Summary by Type:")
        for conn_type, count in sorted(type_counts.items()):
            print(f"   • {conn_type}: {count}")
    else:
        print("⚠️  No connections inferred from data")
    
    print()
    
    # Create bus nodes file
    create_bus_node_file(csv_file, 'bus_nodes.csv')
    
    print()
    print("=" * 70)
    print("✨ Analysis Complete!")
    print("   Files generated:")
    print(f"     1. {output_file} - Connection edges for network graph")
    print(f"     2. bus_nodes.csv - Unique bus nodes with metadata")
    print("=" * 70)

if __name__ == '__main__':
    main()
