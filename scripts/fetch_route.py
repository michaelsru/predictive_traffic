import requests
import json

# Define the start and end points for each segment (approximate based on the current coords)
# S1: Weston Rd to 400
# S2: 400 to Black Creek
# S3: Black Creek to Dufferin
# S4: Dufferin to Keele
# S5: Keele to Allen

waypoints = [
    [43.7145, -79.5298], # Weston Rd (approx start of W/B express)
    [43.7225, -79.5160], # 400
    [43.7265, -79.5015], # Black Creek
    [43.7290, -79.4890], # Keele
    [43.7320, -79.4750], # Dufferin
    [43.7345, -79.4550], # Allen Rd
]

# Note: The original coordinates in the code seem to be somewhat inaccurate or reversed in longitude direction for Toronto
# Let's use more accurate coordinates for Hwy 401 WB Express in Toronto
# Weston Rd: 43.7145, -79.5298
# Hwy 400: 43.7225, -79.5160
# Black Creek Dr: 43.7265, -79.5015
# Keele St: 43.7290, -79.4890
# Dufferin St: 43.7320, -79.4750
# Allen Rd: 43.7345, -79.4550

segments = {
    "S1": ([-79.5298, 43.7145], [-79.5160, 43.7225]), # Weston to 400
    "S2": ([-79.5160, 43.7225], [-79.5015, 43.7265]), # 400 to Black Creek
    "S3": ([-79.5015, 43.7265], [-79.4890, 43.7290]), # Black Creek to Keele
    "S4": ([-79.4890, 43.7290], [-79.4750, 43.7320]), # Keele to Dufferin
    "S5": ([-79.4750, 43.7320], [-79.4550, 43.7345]), # Dufferin to Allen
}

segment_coords = {}

for seg_id, (start, end) in segments.items():
    # OSRM expects lon,lat
    url = f"http://router.project-osrm.org/route/v1/driving/{start[0]},{start[1]};{end[0]},{end[1]}?overview=full&geometries=geojson"
    
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

with open("segment_data.json", "w") as f:
    json.dump(segment_coords, f, indent=2)
print("Saved to segment_data.json")
