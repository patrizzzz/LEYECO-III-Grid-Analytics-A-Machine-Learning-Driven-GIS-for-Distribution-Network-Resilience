import requests
import json

def get_route(server, user_lng, user_lat, dest_lng, dest_lat):
    url = f"{server}/route/v1/driving/{user_lng},{user_lat};{dest_lng},{dest_lat}?overview=full&geometries=geojson"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get('routes'):
            route = data['routes'][0]
            dist = route['distance']
            coords = route['geometry']['coordinates']
            print(f"[{server}] Distance: {dist}m, Coordinates count: {len(coords)}")
            # print a few coordinates from the middle to see where it goes
            mid = len(coords) // 2
            print(f"  Midpoint: lat {coords[mid][1]}, lng {coords[mid][0]}")
            return coords
        else:
            print(f"[{server}] No route found")
    except Exception as e:
        print(f"[{server}] Error: {e}")

# The user is probably near Route 70. 
# Let's get the user location from the previous log or approximate it.
# Wait, let's use the coordinates from the image. 
# Destination is 11.2978, 124.6300 (from our previous BFS script)
dest_lat, dest_lng = 11.2978, 124.6300
user_lat, user_lng = 11.293, 124.620 # Guessing from the map image (bottom left origin of the dashed line)

get_route("https://router.project-osrm.org", user_lng, user_lat, dest_lng, dest_lat)
get_route("https://routing.openstreetmap.de/routed-car", user_lng, user_lat, dest_lng, dest_lat)
