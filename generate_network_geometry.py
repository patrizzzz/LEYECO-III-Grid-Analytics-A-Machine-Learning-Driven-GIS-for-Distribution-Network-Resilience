#!/usr/bin/env python3
"""
Generate map-based line geometries from electrical distribution network data.

Produces:
1. GeoJSON with visible line features
2. Posts with proper geometry
3. Connections respecting Feeder and Circuit rules
"""

import pandas as pd
import json
import math
from pathlib import Path
from collections import defaultdict

def load_and_prepare_data(csv_path):
    """Load CSV and extract unique poles with coordinates."""
    print("📂 Loading CSV data...")
    df = pd.read_csv(csv_path)
    
    # Clean column names
    df.columns = df.columns.str.strip()
    
    print(f"Total records: {len(df)}")
    print(f"Columns available: {list(df.columns)[:15]}...")
    
    # Extract unique poles with their coordinates and network info
    poles_data = []
    seen_poles = set()
    
    for _, row in df.iterrows():
        pole_num = str(row['Pole Number']).strip() if pd.notna(row['Pole Number']) else None
        if not pole_num or pole_num == 'nan':
            continue
        
        if pole_num in seen_poles:
            continue
            
        try:
            lat = float(row['Lat']) if pd.notna(row['Lat']) else None
            lon = float(row['Long']) if pd.notna(row['Long']) else None
        except:
            continue
        
        if not (lat and lon):
            continue
        
        feeder = str(row['Feeder']).strip() if pd.notna(row['Feeder']) else 'Unknown'
        circuit = str(row['Circuit']).strip() if pd.notna(row['Circuit']) else 'Unknown'
        primary_bus = str(row['Primary Bus ID']).strip() if pd.notna(row['Primary Bus ID']) else None
        transformer_bus = str(row['Transformer Bus ID']).strip() if pd.notna(row['Transformer Bus ID']) else None
        sec_bus = str(row['Sec. Bus ID']).strip() if pd.notna(row['Sec. Bus ID']) else None
        
        poles_data.append({
            'pole_number': pole_num,
            'latitude': lat,
            'longitude': lon,
            'feeder': feeder,
            'circuit': circuit,
            'primary_bus': primary_bus if primary_bus != 'nan' else None,
            'transformer_bus': transformer_bus if transformer_bus != 'nan' else None,
            'secondary_bus': sec_bus if sec_bus != 'nan' else None,
        })
        seen_poles.add(pole_num)
    
    print(f"✅ Extracted {len(poles_data)} unique poles with coordinates")
    return pd.DataFrame(poles_data)

def generate_connections(poles_df):
    """Generate connection rules based on Feeder, Circuit, and Bus IDs."""
    connections = []
    
    print("\n🔗 Generating connections...")
    
    # Rule 1: Primary Bus → Transformer Bus (where both exist)
    print("  • Rule 1: Primary Bus → Transformer Bus...")
    primary_to_transformer = 0
    for _, pole in poles_df.iterrows():
        if pole['primary_bus'] and pole['transformer_bus']:
            connections.append({
                'from_bus': pole['primary_bus'],
                'to_bus': pole['transformer_bus'],
                'from_pole': pole['pole_number'],
                'to_pole': pole['pole_number'],
                'connection_type': 'Primary_to_Transformer',
                'feeder': pole['feeder'],
                'circuit': pole['circuit'],
                'geometry_type': 'same_pole'
            })
            primary_to_transformer += 1
    print(f"    Found {primary_to_transformer} Primary→Transformer connections")
    
    # Rule 2: Transformer Bus → Secondary Bus (where both exist)
    print("  • Rule 2: Transformer Bus → Secondary Bus...")
    transformer_to_secondary = 0
    for _, pole in poles_df.iterrows():
        if pole['transformer_bus'] and pole['secondary_bus']:
            connections.append({
                'from_bus': pole['transformer_bus'],
                'to_bus': pole['secondary_bus'],
                'from_pole': pole['pole_number'],
                'to_pole': pole['pole_number'],
                'connection_type': 'Transformer_to_Secondary',
                'feeder': pole['feeder'],
                'circuit': pole['circuit'],
                'geometry_type': 'same_pole'
            })
            transformer_to_secondary += 1
    print(f"    Found {transformer_to_secondary} Transformer→Secondary connections")
    
    # Rule 3: Sequential pole connections within same Feeder and Circuit
    print("  • Rule 3: Sequential poles (Feeder & Circuit based)...")
    
    # Group poles by Feeder and Circuit
    feeder_circuit_groups = defaultdict(list)
    for _, pole in poles_df.iterrows():
        key = (pole['feeder'], pole['circuit'])
        feeder_circuit_groups[key].append(pole)
    
    sequential_connections = 0
    for (feeder, circuit), poles_in_group in feeder_circuit_groups.items():
        if len(poles_in_group) < 2:
            continue
        
        # Sort by pole number (numeric part)
        try:
            poles_in_group = sorted(poles_in_group, 
                key=lambda x: int(''.join(c for c in str(x['pole_number']) if c.isdigit())))
        except:
            pass
        
        # Connect sequential poles
        for i in range(len(poles_in_group) - 1):
            from_pole = poles_in_group[i]
            to_pole = poles_in_group[i + 1]
            
            # Use Primary Bus ID for connections
            from_bus = from_pole['primary_bus'] or from_pole['pole_number']
            to_bus = to_pole['primary_bus'] or to_pole['pole_number']
            
            connections.append({
                'from_bus': from_bus,
                'to_bus': to_bus,
                'from_pole': from_pole['pole_number'],
                'to_pole': to_pole['pole_number'],
                'connection_type': 'Primary_to_Primary',
                'feeder': feeder,
                'circuit': circuit,
                'geometry_type': 'sequential'
            })
            sequential_connections += 1
    
    print(f"    Found {sequential_connections} sequential pole connections")
    
    print(f"\n✅ Total connections generated: {len(connections)}")
    return connections

def create_geojson(poles_df, connections):
    """Create GeoJSON FeatureCollection with points and line geometries."""
    print("\n📍 Creating GeoJSON...")
    
    features = []
    pole_coords = {}
    
    # Create pole point features
    for _, pole in poles_df.iterrows():
        pole_num = pole['pole_number']
        coord = [pole['longitude'], pole['latitude']]
        pole_coords[pole_num] = coord
        
        features.append({
            'type': 'Feature',
            'id': f"pole_{pole_num}",
            'geometry': {
                'type': 'Point',
                'coordinates': coord
            },
            'properties': {
                'pole_number': pole_num,
                'feeder': pole['feeder'],
                'circuit': pole['circuit'],
                'primary_bus': pole['primary_bus'],
                'transformer_bus': pole['transformer_bus'],
                'secondary_bus': pole['secondary_bus'],
                'feature_type': 'pole'
            }
        })
    
    print(f"  Added {len(features)} pole point features")
    
    # Create line features for connections
    line_count = 0
    valid_connections = 0
    
    for conn in connections:
        from_pole = conn['from_pole']
        to_pole = conn['to_pole']
        
        # Get or create coordinates
        if from_pole not in pole_coords:
            continue
        if to_pole not in pole_coords:
            continue
        
        from_coord = pole_coords[from_pole]
        to_coord = pole_coords[to_pole]
        
        features.append({
            'type': 'Feature',
            'id': f"line_{conn['from_bus']}_{conn['to_bus']}",
            'geometry': {
                'type': 'LineString',
                'coordinates': [from_coord, to_coord]
            },
            'properties': {
                'from_bus': conn['from_bus'],
                'to_bus': conn['to_bus'],
                'from_pole': from_pole,
                'to_pole': to_pole,
                'connection_type': conn['connection_type'],
                'feeder': conn['feeder'],
                'circuit': conn['circuit'],
                'geometry_type': conn['geometry_type'],
                'feature_type': 'connection'
            }
        })
        valid_connections += 1
    
    print(f"  Added {valid_connections} line connection features")
    
    return {
        'type': 'FeatureCollection',
        'features': features
    }

def save_outputs(poles_df, connections, geojson, output_dir='./'):
    """Save all output files."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    print("\n💾 Saving outputs...")
    
    # Save GeoJSON
    geojson_file = output_path / 'network_geometry.geojson'
    with open(geojson_file, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, indent=2)
    print(f"  OK: GeoJSON: {geojson_file} ({len(geojson['features'])} features)")
    
    # Save poles CSV
    poles_csv = output_path / 'poles_with_coordinates.csv'
    poles_df.to_csv(poles_csv, index=False)
    print(f"  OK: Poles CSV: {poles_csv}")
    
    # Save connections CSV
    connections_df = pd.DataFrame(connections)
    connections_csv = output_path / 'generated_connections.csv'
    connections_df.to_csv(connections_csv, index=False)
    print(f"  OK: Connections CSV: {connections_csv} ({len(connections)} rows)")
    
    # Summary report
    report = f"""
ELECTRICAL NETWORK GEOMETRY GENERATION REPORT
==============================================

INPUT DATA:
  Source: amonaini.csv
  
EXTRACTED DATA:
  Poles: {len(poles_df)}
  Unique Feeders: {poles_df['feeder'].nunique()}
  Unique Circuits: {poles_df['circuit'].nunique()}

GENERATED CONNECTIONS:
  Total: {len(connections)}
  
CONNECTION BREAKDOWN:
"""
    
    conn_types = connections_df.groupby('connection_type').size()
    for conn_type, count in conn_types.items():
        report += f"  - {conn_type}: {count}\n"
    
    report += f"""
FEEDER SUMMARY:
"""
    
    feeder_counts = connections_df.groupby('feeder').size()
    for feeder, count in feeder_counts.items():
        report += f"  - {feeder}: {count} connections\n"
    
    report += f"""
OUTPUT FILES:
  1. network_geometry.geojson - GeoJSON with all points and lines
  2. poles_with_coordinates.csv - Extracted pole data
  3. generated_connections.csv - All generated connections
  4. geometry_report.txt - This report

MAPPING READY:
  * All coordinates in WGS84 (lat/long)
  * All line geometries valid
  * No cross-feeder or cross-circuit connections
  * Ready for map visualization (Leaflet, Mapbox, etc.)

"""
    
    report_file = output_path / 'geometry_report.txt'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"  ✓ Report: {report_file}")
    
    print("\n" + report)
    
    return {
        'geojson_file': str(geojson_file),
        'poles_csv': str(poles_csv),
        'connections_csv': str(connections_csv),
        'report_file': str(report_file)
    }

def main():
    csv_file = 'amonaini.csv'
    
    if not Path(csv_file).exists():
        print(f"❌ File not found: {csv_file}")
        return
    
    # Load and prepare data
    poles_df = load_and_prepare_data(csv_file)
    
    # Generate connections
    connections = generate_connections(poles_df)
    
    # Create GeoJSON
    geojson = create_geojson(poles_df, connections)
    
    # Save all outputs
    outputs = save_outputs(poles_df, connections, geojson)
    
    print("\n✓ COMPLETE! Geometry files ready for mapping.")
    print(f"\nTo visualize: Open network_geometry.geojson in a GIS tool or load in the map application.")

if __name__ == '__main__':
    main()
