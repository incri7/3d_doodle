"""Fetch OpenStreetMap data for the Kathmandu Ring Road area via Overpass
(cached in data/ktm/). Buildings come in tiles so each query stays small."""
import json, os, sys, time, urllib.parse, urllib.request

BBOX = (27.650, 85.272, 27.750, 85.365)          # south, west, north, east
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "ktm")
MIRROR = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"


def overpass(q, path, tries=6):
    if os.path.exists(path) and os.path.getsize(path) > 100:
        return json.load(open(path))
    for i in range(tries):
        try:
            data = urllib.parse.urlencode({"data": q}).encode()
            raw = urllib.request.urlopen(MIRROR, data, timeout=300).read()
            if raw[:1] == b"{":
                open(path, "wb").write(raw)
                return json.loads(raw)
            print("  busy, retrying", file=sys.stderr)
        except Exception as e:
            print("  error", e, file=sys.stderr)
        time.sleep(10 * (i + 1))
    raise SystemExit("overpass failed: " + path)


def main():
    os.makedirs(OUT, exist_ok=True)
    s, w, n, e = BBOX
    bb = f"({s},{w},{n},{e})"
    d = overpass(f'[out:json][timeout:240];(way["highway"]{bb};);out geom tags;', f"{OUT}/roads.json")
    print("roads", len(d["elements"]))
    d = overpass(f'[out:json][timeout:240];(way["waterway"]{bb};way["natural"="water"]{bb};relation["natural"="water"]{bb};'
                 f'way["landuse"]{bb};way["leisure"~"park|garden|golf_course|pitch|stadium"]{bb};way["natural"~"wood|scrub|grassland"]{bb};'
                 f'way["aeroway"]{bb};way["amenity"~"place_of_worship|bus_station"]{bb};);out geom tags;', f"{OUT}/areas.json")
    print("areas/water", len(d["elements"]))
    N = 4
    total = 0
    for i in range(N):
        for j in range(N):
            ts, tn = s + (n - s) * i / N, s + (n - s) * (i + 1) / N
            tw, te = w + (e - w) * j / N, w + (e - w) * (j + 1) / N
            d = overpass(f'[out:json][timeout:240];way["building"]({ts},{tw},{tn},{te});out geom tags;',
                         f"{OUT}/buildings_{i}{j}.json")
            total += len(d["elements"])
            print(f"buildings tile {i}{j}: {len(d['elements'])}", flush=True)
    print("buildings total", total)


if __name__ == "__main__":
    main()
