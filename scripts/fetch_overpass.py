import requests
import json

bbox = "43.71,-79.54,43.74,-79.44"
overpass_url = "http://overpass-api.de/api/interpreter"
# Fetch 401 Westbound ways (they have name or destination tags, or we can filter by direction later)
overpass_query = f"""
[out:json];
way({bbox})["highway"="motorway"]["ref"="401"];
out geom;
"""

print("Fetching from Overpass API...")
response = requests.post(overpass_url, data={'data': overpass_query})
data = response.json()

lines = []
for element in data.get('elements', []):
    if element['type'] == 'way':
        geom = element.get('geometry', [])
        # Check direction: start lon vs end lon
        if geom and geom[-1]['lon'] < geom[0]['lon']:
            # It goes Westbound
            tags = element.get('tags', {})
            name = tags.get('name', '')
            lines.append({
                'id': element['id'],
                'geom': geom,
                'name': name,
                'min_lon': min(p['lon'] for p in geom),
                'max_lon': max(p['lon'] for p in geom),
                'avg_lat': sum(p['lat'] for p in geom)/len(geom)
            })

# Filter for Express: WB Express is usually "Highway 401 Express"
# Let's see if we have ones with "Express" in name
express_lines = [l for l in lines if 'Express' in l['name']]
if not express_lines:
    # Fallback to the southernmost WB line if "Express" isn't explicitly named
    express_lines = lines # Will sort by lat later

# Build all coordinates
wb_express_coords = []
for l in express_lines:
    for p in l['geom']:
        wb_express_coords.append((p['lon'], p['lat']))

# Sort by longitude (East to West means descending longitude)
wb_express_coords = sorted(list(set(wb_express_coords)), key=lambda x: x[0], reverse=True)

# Now we have a dense sequence of all WB Express nodes from East to West.
# We must split this sequence into S1-S5 based on Longitude bounds.

bounds = {
    "S5": (-79.4550, -79.4750), # Allen to Dufferin (East to West)
    "S4": (-79.4750, -79.4883), # Dufferin to Keele
    "S3": (-79.4883, -79.5015), # Keele to Black Creek
    "S2": (-79.5015, -79.5160), # Black Creek to 400
    "S1": (-79.5160, -79.5298), # 400 to Weston
}

segment_coords = {}
for seg, (east_lon, west_lon) in bounds.items():
    seg_nodes = []
    for lon, lat in wb_express_coords:
        if west_lon <= lon <= east_lon:
            seg_nodes.append([lat, lon]) # leaflet expects [lat, lon]
    
    # Sort them East to West (descending longitude)
    seg_nodes.sort(key=lambda x: x[1], reverse=True)
    segment_coords[seg] = seg_nodes

with open("src/segment_data.json", "w") as f:
    json.dump(segment_coords, f, indent=2)

print("Saved cleanly split coordinates to src/segment_data.json")

for k in ["S1", "S2", "S3", "S4", "S5"]:
    v = segment_coords.get(k, [])
    if v:
        mid = v[len(v)//2]
        print(f"{k} nodes: {len(v)} | midpoint: {mid[0]:.4f}, {mid[1]:.4f}")
    else:
        print(f"{k} has 0 nodes! :(")
