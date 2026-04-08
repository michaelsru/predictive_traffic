"""
fetch_route_v4.py
Fetches the Hwy 401 Westbound Express geometry directly from Overpass
(raw OSM way data — no routing, guaranteed to be on the actual highway),
then splits the full polyline into 20 equal-length sub-segments (S1–S20).

Run from project root:
    python scripts/fetch_route_v4.py
"""

import json
import requests

OVERPASS_URL = "http://overpass-api.de/api/interpreter"

# Broader bbox: south, west, north, east
# Covers 401 from Weston Rd to Allen Rd with room to spare
BBOX = "43.70,-79.55,43.74,-79.44"

OVERPASS_QUERY = f"""
[out:json];
way({BBOX})["highway"="motorway"]["ref"="401"]["oneway"="yes"];
out geom;
"""

N_SEGMENTS = 20


def fetch_overpass():
    print("Fetching from Overpass API...")
    r = requests.post(OVERPASS_URL, data={"data": OVERPASS_QUERY}, timeout=30)
    r.raise_for_status()
    return r.json()


def build_ordered_polyline(data):
    """
    Extract all WB Express way geometries, sort by longitude (W→E),
    deduplicate shared nodes, and return a single ordered [lat, lon] list.
    """
    ways = []
    for el in data.get("elements", []):
        if el["type"] != "way":
            continue
        geom = el.get("geometry", [])
        if len(geom) < 2:
            continue
        tags = el.get("tags", {})
        name = tags.get("name", "")
        # Keep only Express lanes (or fall back to any WB 401 way)
        lons = [p["lon"] for p in geom]
        lats = [p["lat"] for p in geom]
        # Direction: westbound = end lon < start lon
        if geom[-1]["lon"] < geom[0]["lon"]:
            direction = "WB"
        else:
            direction = "EB"
        ways.append({
            "name": name,
            "direction": direction,
            "geom": geom,
            "min_lon": min(lons),
            "max_lon": max(lons),
            "avg_lat": sum(lats) / len(lats),
        })

    print(f"Total ways found: {len(ways)}")
    for w in ways:
        print(f"  [{w['direction']}] {w['name']!r:40} lon {w['min_lon']:.4f}…{w['max_lon']:.4f}  lat_avg {w['avg_lat']:.4f}")

    # Prefer Express WB; fall back to any WB
    wb = [w for w in ways if w["direction"] == "WB" and "Express" in w["name"]]
    if not wb:
        wb = [w for w in ways if w["direction"] == "WB"]
    if not wb:
        raise RuntimeError("No westbound 401 ways found — check your bbox or query")

    print(f"\nUsing {len(wb)} WB ways")

    # Collect all points, sort W→E by longitude (ascending = east), then deduplicate
    all_pts = []
    for w in wb:
        for p in w["geom"]:
            all_pts.append((p["lon"], p["lat"]))

    # Deduplicate, sort ascending longitude (west is more negative, east is less negative)
    all_pts = sorted(set(all_pts), key=lambda x: x[0])

    # [lon, lat] → [lat, lon] for Leaflet
    return [[lat, lon] for lon, lat in all_pts]


def split_polyline(points, n):
    """Split into n segments sharing endpoints."""
    total = len(points)
    size = total / n
    segments = {}
    for i in range(n):
        start = round(i * size)
        end = min(round((i + 1) * size), total - 1)
        chunk = points[start : end + 1]
        segments[f"S{i + 1}"] = chunk
    return segments


def main():
    data = fetch_overpass()
    points = build_ordered_polyline(data)
    print(f"\nTotal ordered points: {len(points)}")
    print(f"West end: lat={points[0][0]:.4f} lng={points[0][1]:.4f}")
    print(f"East end: lat={points[-1][0]:.4f} lng={points[-1][1]:.4f}")

    if len(points) < N_SEGMENTS * 2:
        raise RuntimeError(f"Too few points ({len(points)}) to split into {N_SEGMENTS} segments")

    segments = split_polyline(points, N_SEGMENTS)

    out_path = "src/segment_data.json"
    with open(out_path, "w") as f:
        json.dump(segments, f, indent=2)
    print(f"\nSaved {N_SEGMENTS} segments to {out_path}")

    print("\nMidpoints (copy into gemini_client.py SEGMENT_LOCATIONS):")
    for seg_id, coords in segments.items():
        mid = coords[len(coords) // 2]
        print(f'    "{seg_id}": {{"lat": {mid[0]:.4f}, "lng": {mid[1]:.4f}}},')


if __name__ == "__main__":
    main()
