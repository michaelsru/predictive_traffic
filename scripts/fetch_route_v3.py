"""
fetch_route_v3.py
Get one continuous OSRM route along Hwy 401 WB (Weston Rd → Allen Rd),
then split the full polyline into 20 equal-length sub-segments (S1–S20).
Each segment shares its last point with the next segment's first point,
so there are zero gaps on the map.

Run from project root:
    python scripts/fetch_route_v3.py
"""

import json
import requests

# Waypoints pinned to Hwy 401 WB express lanes (lon, lat for OSRM).
# Dense enough to keep the router on the 401 and out of surface streets.
# West → East (decreasing longitude, increasing lat slightly)
WAYPOINTS = [
    [-79.5297, 43.7149],   # Weston Rd (west terminus)
    [-79.5250, 43.7160],   # mid Weston–400
    [-79.5160, 43.7182],   # Hwy 400 overpass
    [-79.5085, 43.7177],   # just east of 400
    [-79.5015, 43.7207],   # Black Creek Dr
    [-79.4950, 43.7220],   # mid Black Creek–Keele
    [-79.4883, 43.7231],   # Keele St
    [-79.4816, 43.7248],   # mid Keele–Dufferin
    [-79.4750, 43.7265],   # Dufferin St
    [-79.4650, 43.7276],   # mid Dufferin–Allen
    [-79.4550, 43.7283],   # Allen Rd (east terminus)
]

N_SEGMENTS = 20  # S1 … S20

def fetch_route(waypoints):
    coords_str = ";".join(f"{lon},{lat}" for lon, lat in waypoints)
    url = (
        f"http://router.project-osrm.org/route/v1/driving/{coords_str}"
        f"?overview=full&geometries=geojson&steps=false"
    )
    print(f"Requesting: {url}")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data["code"] != "Ok":
        raise RuntimeError(f"OSRM error: {data['code']}")
    # GeoJSON coords are [lon, lat]; convert to [lat, lon] for Leaflet
    raw = data["routes"][0]["geometry"]["coordinates"]
    return [[lat, lon] for lon, lat in raw]


def split_polyline(points, n):
    """Split points into n equal chunks, sharing endpoints between segments."""
    total = len(points)
    size = total / n
    segments = {}
    for i in range(n):
        seg_id = f"S{i + 1}"
        start = round(i * size)
        # Include next segment's first point so polylines touch
        end = round((i + 1) * size)
        chunk = points[start : end + 1]
        segments[seg_id] = chunk
    return segments


def main():
    points = fetch_route(WAYPOINTS)
    print(f"Total points in route: {len(points)}")

    segments = split_polyline(points, N_SEGMENTS)

    out_path = "src/segment_data.json"
    with open(out_path, "w") as f:
        json.dump(segments, f, indent=2)
    print(f"Saved {N_SEGMENTS} segments to {out_path}")

    print("\nMidpoints (copy into gemini_client.py SEGMENT_LOCATIONS):")
    for seg_id, coords in segments.items():
        mid = coords[len(coords) // 2]
        print(f'    "{seg_id}": {{"lat": {mid[0]:.4f}, "lng": {mid[1]:.4f}}},')


if __name__ == "__main__":
    main()
