"""Where the real direction signs stand along the Ring Road, from Mapillary's
traffic-sign detections (map features, CC BY-SA 4.0) on its street photos.

For every 'direction' / 'information' sign within 35 m of the loop it records
the position and the travel direction it serves (from the compass heading of
the photos that saw its face). Writes data/ktm/signs.json.
Token: MAPILLARY_TOKEN or MAPILLARY_TOKEN_FILE (as fetch_mapillary.py)."""
import json, math, os, time, urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "ktm")
KINDS = ("object--traffic-sign--direction-front", "object--sign--information", "information--general-directions--g1")


def token():
    t = os.environ.get("MAPILLARY_TOKEN")
    if not t and os.environ.get("MAPILLARY_TOKEN_FILE"):
        t = open(os.environ["MAPILLARY_TOKEN_FILE"]).read().strip()
    if not t:
        raise SystemExit("set MAPILLARY_TOKEN or MAPILLARY_TOKEN_FILE")
    return t


def main():
    T = token()
    get = lambda u: json.loads(urllib.request.urlopen(u, timeout=60).read())
    meta = json.load(open(os.path.join(DATA, "prep.json")))
    c = np.load(os.path.join(DATA, "loop.npy"))                       # 2 m centreline
    t = np.roll(c, -1, 0) - np.roll(c, 1, 0)
    t /= np.linalg.norm(t, axis=1)[:, None]
    lon = c[:, 0] / meta["kx"] + meta["lon0"]
    lat = c[:, 1] / meta["ky"] + meta["lat0"]
    xy = lambda x, y: ((x - meta["lon0"]) * meta["kx"], (y - meta["lat0"]) * meta["ky"])
    feats = {}
    for k in range(0, len(c), 250):
        bb = f"{lon[k] - 0.003},{lat[k] - 0.003},{lon[k] + 0.003},{lat[k] + 0.003}"
        for f in get(f"https://graph.mapillary.com/map_features?access_token={T}&fields=id,object_value,geometry&bbox={bb}&limit=500").get("data", []):
            if f["object_value"] in KINDS:
                feats[f["id"]] = f
    out = []
    for fid, f in feats.items():
        x, y = xy(*f["geometry"]["coordinates"])
        d = np.hypot(c[:, 0] - x, c[:, 1] - y)
        k = int(d.argmin())
        if d[k] > 35:
            continue
        n = np.array([-t[k, 1], t[k, 0]])
        off = float((x - c[k, 0]) * n[0] + (y - c[k, 1]) * n[1])
        votes = 0.0
        for im in get(f"https://graph.mapillary.com/{fid}?access_token={T}&fields=images")["images"]["data"][:6]:
            a = get(f"https://graph.mapillary.com/{im['id']}?access_token={T}&fields=compass_angle").get("compass_angle")
            if a is None:
                continue
            h = np.array([math.sin(math.radians(a)), math.cos(math.radians(a))])   # camera heading (east, north)
            votes += float(h @ t[k])
            time.sleep(0.05)
        out.append({"id": fid, "kind": f["object_value"], "k2": k, "s": round(k * 2.0, 1), "off": round(off, 1),
                    "dir": 1 if votes >= 0 else -1, "votes": round(votes, 2)})
    out.sort(key=lambda r: r["s"])
    json.dump(out, open(os.path.join(DATA, "signs.json"), "w"), indent=1)
    print(len(out), "signs")


if __name__ == "__main__":
    main()
