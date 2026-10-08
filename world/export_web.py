"""Export the Kalanki -> Balkhu street map for the web driving page.

Writes web/ktm_map.json (road centreline, near building footprints with
oriented-box colliders, far buildings as boxes, bridge range, terrain
heights flattened around the road) and web/ktm_sat.jpg (Sentinel-2).
Coordinates: metres, x east, y north, origin at the road's midpoint; the
playable world is flat (the real 1.3 % grade is dropped) and the terrain
rises to the real valley hills away from the road.
"""
import base64, json, math, os, sys

import numpy as np
import shapely
from shapely.geometry import Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_street as S  # noqa: E402  (Road, constants)
from build_ktm import Ground  # noqa: E402

ROOT = os.path.join(HERE, "..")
DATA = os.path.join(ROOT, "data", "ktm")
WEB = os.path.join(ROOT, "web")
FAR = 1400          # far buildings out to this distance from the road
TER = 2600          # terrain extent around the road
TSTEP = 20.0        # terrain grid step (m)


def obb(poly):
    r = poly.minimum_rotated_rectangle
    c = np.asarray(r.exterior.coords)[:4]
    e0, e1 = c[1] - c[0], c[2] - c[1]
    return (float(r.centroid.x), float(r.centroid.y), float(np.linalg.norm(e0)), float(np.linalg.norm(e1)),
            float(math.atan2(e0[1], e0[0])))


def main():
    npz = np.load(os.path.join(DATA, "prep.npz"))
    meta = json.load(open(os.path.join(DATA, "prep.json")))
    G = Ground(npz, meta)
    R = S.Road(G, meta)
    o = R.P[len(R.P) // 2].copy()                       # origin: road midpoint
    P = R.P - o
    line = shapely.LineString(P)

    xy, off, lv = npz["bxy"].astype(np.float64) - o, npz["boff"], npz["blevels"]
    polys = [Polygon(xy[off[k]:off[k + 1]]) for k in range(len(lv))]
    cen = shapely.centroid(polys)
    d = shapely.distance(line, cen)
    hits = shapely.intersects(np.array(polys, dtype=object), line.buffer(S.EDGE + S.FOOT + 1.5))
    near, far = [], []
    rng = np.random.default_rng(7)
    for k in np.nonzero(d < FAR)[0]:
        p = polys[k]
        if hits[k] or p.area < 8:
            continue
        floors = max(1, int(round(float(lv[k]))))
        col = int(rng.integers(0, 1 << 30))
        if d[k] < S.CORRIDOR:
            q = p.simplify(0.25)
            if q.is_empty or q.geom_type != "Polygon":
                continue
            ring = np.asarray(q.exterior.coords)[:-1]
            if not Polygon(ring).exterior.is_ccw:
                ring = ring[::-1]
            near.append({"p": np.round(ring, 2).ravel().tolist(), "f": floors, "c": col,
                         "b": [round(v, 2) for v in obb(q)]})
        else:
            far.append([round(v, 1) for v in obb(p)] + [floors, col % 997])
    print(f"near buildings {len(near)}, far {len(far)}")

    # terrain: real DEM relative to the road, flattened to 0 near the corridor
    x0, y0 = P.min(0) - TER
    x1, y1 = P.max(0) + TER
    xs = np.arange(x0, x1 + TSTEP, TSTEP); ys = np.arange(y0, y1 + TSTEP, TSTEP)
    X, Y = np.meshgrid(xs, ys)
    z = G.z(X.ravel() + o[0], Y.ravel() + o[1])
    dd = shapely.distance(line, shapely.points(X.ravel(), Y.ravel()))
    zr = float(np.median(R.z))
    w = np.clip((dd - (S.CORRIDOR + 40)) / 500.0, 0, 1)
    w = w * w * (3 - 2 * w)
    h = (z - zr) * w - 0.45          # sits well under the road surfaces (no z-fighting)
    hq = np.clip(np.round(h * 10), -32000, 32000).astype(np.int16)
    # far buildings sit on the terrain
    for fb in far:
        i = int(round((fb[1] - y0) / TSTEP)); j = int(round((fb[0] - x0) / TSTEP))
        i = min(max(i, 0), len(ys) - 1); j = min(max(j, 0), len(xs) - 1)
        fb.append(round(float(h.reshape(X.shape)[i, j]), 1))

    # satellite image bounds in the same local frame
    import rasterio
    from PIL import Image
    with rasterio.open(os.path.join(DATA, "sentinel2.tif")) as src:
        bd = src.bounds
    sat = Image.open(os.path.join(DATA, "sentinel2.jpg"))
    sat.thumbnail((2048, 2048))
    sat.save(os.path.join(WEB, "ktm_sat.jpg"), quality=86)
    sb = [(bd.left - meta["lon0"]) * meta["kx"] - o[0], (bd.bottom - meta["lat0"]) * meta["ky"] - o[1],
          (bd.right - meta["lon0"]) * meta["kx"] - o[0], (bd.top - meta["lat0"]) * meta["ky"] - o[1]]

    out = {
        "about": "Kathmandu Ring Road, Kalanki - Balkhu. OpenStreetMap (ODbL), Google Open Buildings (CC BY 4.0), "
                 "Copernicus GLO-30 DEM, Sentinel-2 (contains modified Copernicus Sentinel data 2026).",
        "road": {"pts": np.round(P[::2], 2).ravel().tolist(), "step": 4.0, "bridge": [round(v, 1) for v in R.bridge],
                 "median": S.MEDIAN, "lane": S.LANE, "shoulder": S.SHOULDER, "sep": S.SEP, "foot": S.FOOT},
        "near": near, "far": far,
        "terrain": {"x0": round(x0, 1), "y0": round(y0, 1), "step": TSTEP, "nx": len(xs), "ny": len(ys),
                    "h": base64.b64encode(hq.tobytes()).decode()},
        "sat": {"file": "ktm_sat.jpg", "bounds": [round(v, 1) for v in sb]},
    }
    path = os.path.join(WEB, "ktm_map.json")
    json.dump(out, open(path, "w"), separators=(",", ":"))
    print("wrote", path, round(os.path.getsize(path) / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
