
import csv

def analyze_user_logic():
    # 1. Load Transformers
    transformers = {}
    with open('example2.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sec_bus = row.get('To  \nSecondary Bus ID', '').strip()
            if sec_bus:
                transformers[sec_bus] = {
                    'dt_id': row['Distribution Transformer ID'],
                    'primary_bus': row['From \nPrimary Bus ID'].strip(),
                    'kva': row['KVA Rating']
                }

    print(f"Loaded {len(transformers)} transformers by secondary bus ID.")
    
    # 2. Check for Pole 138 explicitly in any bus field
    print("Checking if '138' is in any transformer's secondary bus string...")
    for sec_bus in transformers:
        if '138' in sec_bus:
            print("  Found '138' in secondary bus:", sec_bus)

    # 3. Load EXAMPLEDATA lines to see where secondary busses originate
    line_origins = {}
    with open('EXAMPLEDATA.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            from_bus = row['From_Bus_ID'].strip()
            to_bus = row['To_Bus_ID'].strip()
            
            # Record that this from_bus was used
            line_origins[from_bus] = to_bus
            
    print(f"Loaded {len(line_origins)} line origins.")
    
    # Check if '138' is an origin or destination in EXAMPLEDATA
    found_138_lines = []
    for f_bus, t_bus in line_origins.items():
        if '138' in f_bus or '138' in t_bus:
            found_138_lines.append((f_bus, t_bus))
            
    print(f"Lines involving 138: {found_138_lines}")

if __name__ == "__main__":
    analyze_user_logic()
