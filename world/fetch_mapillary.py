"""Street-level photos along the Ring Road from Mapillary (CC BY-SA 4.0).

Samples a point every ~400 m around the loop, takes the newest photo near
each, and saves 1024 px thumbnails + metadata to data/ktm/mapillary/.
Token: MAPILLARY_TOKEN env var (or the first line of a file in MAPILLARY_TOKEN_FILE).
"""
import json, math, os, sys, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

from fetch_osm import OUT

API = "https://graph.mapillary.com/images"
STEP = 400.0      # metres between samples
R = 0.0006        # search half-size in degrees (~60 m)


def token():
    t = os.environ.get("MAPILLARY_TOKEN")
    if not t and os.environ.get("MAPILLARY_TOKEN_FILE"):
        t = open(os.environ["MAPILLARY_TOKEN_FILE"]).read().strip()
    if not t:
        sys.exit("set MAPILLARY_TOKEN")
    return t


def ring_points():
    """Ordered points along the Ring Road ways, then resampled every STEP m."""
    ways = [e for e in json.load(open(f"{OUT}/ringroad.json"))["elements"] if e["type"] == "way"]
    pts = [(p["lat"], p["lon"]) for w in ways for p in w["geometry"]]
    out, acc, last = [], STEP, None
    for la, lo in pts:
        if last:
            acc += math.hypot((la - last[0]) * 110574, (lo - last[1]) * 98600)
        if acc >= STEP:
            out.append((la, lo)); acc = 0.0
        last = (la, lo)
    return out


def nearest_new(tok, la, lo):
    q = urllib.parse.urlencode({"access_token": tok, "limit": 50,
                                "fields": "id,captured_at,compass_angle,geometry,thumb_1024_url,creator,is_pano",
                                "bbox": f"{lo - R},{la - R},{lo + R},{la + R}"})
    try:
        d = json.load(urllib.request.urlopen(f"{API}?{q}", timeout=60))["data"]
    except Exception as e:
        print("  error", e, file=sys.stderr)
        return None
    d = [x for x in d if not x.get("is_pano") and x.get("thumb_1024_url")]
    return max(d, key=lambda x: x["captured_at"]) if d else None


def main():
    tok = token()
    dst = os.path.join(OUT, "mapillary")
    os.makedirs(dst, exist_ok=True)
    pts = ring_points()
    print("samples", len(pts))
    with ThreadPoolExecutor(8) as ex:
        found = list(ex.map(lambda p: nearest_new(tok, *p), pts))
    meta, seen = [], set()
    for i, im in enumerate(found):
        if not im or im["id"] in seen:
            continue
        seen.add(im["id"])
        path = os.path.join(dst, f"{i:03d}_{im['id']}.jpg")
        if not os.path.exists(path):
            urllib.request.urlretrieve(im["thumb_1024_url"], path)
        meta.append({"i": i, "id": im["id"], "lon": im["geometry"]["coordinates"][0],
                     "lat": im["geometry"]["coordinates"][1], "heading": im.get("compass_angle"),
                     "date": im["captured_at"], "author": im.get("creator", {}).get("username"),
                     "file": os.path.basename(path)})
    json.dump(meta, open(os.path.join(dst, "index.json"), "w"), indent=1)
    print("photos", len(meta))


if __name__ == "__main__":
    main()
