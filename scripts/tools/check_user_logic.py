
import csv
from math import radians, cos, sin, asin, sqrt

def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance in kilometers between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 # Radius of earth in kilometers. Use 3956 for miles. Determines return value units.
    return c * r * 1000 # in meters

def analyze_logic():
    # 1. Load Poles (Post) with Coordinates
    poles = {}
    with open('poles_with_coordinates_clean.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                poles[row['pole_number'].strip()] = {
                    'lat': float(row['latitude']),
                    'lon': float(row['longitude'])
                }
            except:
                pass
                
    # 2. Load Secondary Lines (Assuming EXAMPLEDATA.csv actually has them? I'm checking bus_data first since EXAMPLEDATA had primary lines)
    # The user mentioned EXAMPLEDATA.csv, but that file's first line said "Primary Distribution Line Segment ID"
    # Let me check if there's actually a secondary file or if they meant bus_data
    
    print("Checking Pole 138 specifically")
    p138 = poles.get('138')
    if p138:
        print(f"Pole 138 found: Lat {p138['lat']}, Lon {p138['lon']}")
    else:
        print("Pole 138 not strictly found in coordinate dict.")
        return

    # Check for ANY transformer in the DB or CSV that might be physically located here
    # Since I don't have the secondary file loaded perfectly yet, I'll find all posts and see which ones are near 138
    print("Searching for closest poles to 138 to see if there's an ID mismatch...")
    closest = sorted(list(poles.keys()), key=lambda k: haversine(p138['lon'], p138['lat'], poles[k]['lon'], poles[k]['lat']))
    for c in closest[:5]:
        dist = haversine(p138['lon'], p138['lat'], poles[c]['lon'], poles[c]['lat'])
        print(f"  Pole {c} is {dist:.2f} meters away")

if __name__ == "__main__":
    analyze_logic()
