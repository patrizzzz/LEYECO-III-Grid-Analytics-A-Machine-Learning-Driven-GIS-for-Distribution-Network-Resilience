import requests
import sys
import os

# Add project root to path to import app if needed, but requests is safer for running server
sys.path.append(os.getcwd())

def check_api():
    print("Checking API /api/network-geometry...")
    try:
        r = requests.get('http://127.0.0.1:5000/api/network-geometry')
        if r.status_code != 200:
            print(f"API Error: {r.status_code}")
            return
        
        data = r.json()
        lines = data.get('lines', [])
        print(f"Total lines returned: {len(lines)}")
        
        phasing_counts = {'Present': 0, 'None': 0, 'Empty': 0}
        unique_phases = set()
        
        for line in lines:
            p = line.get('phasing')
            if p is None:
                phasing_counts['None'] += 1
            elif str(p).strip() == '':
                phasing_counts['Empty'] += 1
            else:
                phasing_counts['Present'] += 1
                unique_phases.add(p)
                
        print("Phasing stats in API response:")
        print(phasing_counts)
        print(f"Unique phases found: {unique_phases}")
        
        if phasing_counts['Present'] == 0:
            print("\nWARNING: No phasing data found in API response!")
        else:
            print("\nSUCCESS: Phasing data is present in API response.")

    except Exception as e:
        print(f"Failed to connect to API: {e}")

if __name__ == "__main__":
    check_api()
