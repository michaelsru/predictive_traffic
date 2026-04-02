import requests
import json

# coordinates are carefully pinned to the Hwy 401 Westbound EXPRESS lanes
segments = {
    "S1": [
        [-79.5310, 43.7138], # Weston
        [-79.5249, 43.7169], # mid
        [-79.5163, 43.7222], # 400
    ],
    "S2": [
        [-79.5163, 43.7222], # 400
        [-79.5085, 43.7246], # mid
        [-79.5015, 43.7262], # Black Creek
    ],
    "S3": [
        [-79.5015, 43.7262], # Black Creek
        [-79.4949, 43.7276], # mid
        [-79.4883, 43.7289], # Keele
    ],
    "S4": [
        [-79.4883, 43.7289], # Keele
        [-79.4816, 43.7305], # mid
        [-79.4750, 43.7319], # Dufferin
    ],
    "S5": [
        [-79.4750, 43.7319], # Dufferin
        [-79.4649, 43.7334], # mid
        [-79.4550, 43.7346], # Allen
    ]
}

segment_coords = {}

for seg_id, points in segments.items():
    # Construct OSRM url with multiple waypoints
    coords_str = ";".join([f"{lon},{lat}" for lon, lat in points])
    url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}?overview=full&geometries=geojson"
    
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data['code'] == 'Ok':
            # GeoJSON returns [lon, lat], but react-leaflet Polyline expects [lat, lon]
            coords = data['routes'][0]['geometry']['coordinates']
            leaflet_coords = [[lat, lon] for lon, lat in coords]
            segment_coords[seg_id] = leaflet_coords
            print(f"Fetched {len(leaflet_coords)} points for {seg_id}")
        else:
            print(f"Error for {seg_id}: {data['code']}")
    else:
        print(f"Failed request for {seg_id}: {response.status_code}")

with open("src/segment_data.json", "w") as f:
    json.dump(segment_coords, f, indent=2)
print("Saved to src/segment_data.json")

# Also print out the midpoints to update LLM clients
for k, v in segment_coords.items():
    if v:
        mid = v[len(v)//2]
        print(f"{k}: {mid[0]:.4f}, {mid[1]:.4f}")
