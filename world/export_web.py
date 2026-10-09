"""Export the whole Kathmandu Ring Road loop for the web driving page.

Writes web/ktm_map.json and web/ktm_sat.jpg (Sentinel-2):
  road     closed centreline every 4 m, per-point "wide" (8 lanes Kalanki ->
           Koteshwor, 4 lanes elsewhere), bridge ranges, side-road stubs
  places   place boards (OpenStreetMap names via Nominatim, world/fetch_places.py)
  near     building footprints within NEAR m, with oriented-box colliders
  far      buildings NEAR..FAR m as boxes
  terrain  heights flattened around the road, satellite image bounds
Coordinates: metres, x east, y north, origin at the loop's centre. The
playable world is flat; the terrain rises to the real valley hills away from
the road.
"""
import base64, json, math, os, sys

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_street as S  # noqa: E402  (cross-section constants)
import ring_loop  # noqa: E402
from build_ktm import Ground  # noqa: E402

ROOT = os.path.join(HERE, "..")
DATA = os.path.join(ROOT, "data", "ktm")
WEB = os.path.join(ROOT, "web")
STEP = 4.0          # exported centreline spacing (m)
NEAR = 100          # detailed buildings out to this distance from the centreline
FAR = 400           # box buildings out to this distance
TER = 2600          # terrain extent around the loop
TSTEP = 40.0        # terrain grid step (m)
NARROW_EDGE = S.I1  # kerb line where the road has 4 lanes
STUB = 60           # side roads drawn this far out from the kerb
SIDE_CLS = {"trunk": 7.5, "primary": 7.5, "secondary": 6.5, "tertiary": 6, "unclassified": 5,
            "residential": 5, "trunk_link": 6, "primary_link": 6, "secondary_link": 5.5, "tertiary_link": 5}
# Ring Road junctions in order of priority (Nominatim queries in fetch_places.py)
MAJOR = ["Kalanki", "Balkhu", "Ekantakuna", "Satdobato", "Gwarko", "Koteshwor", "Chabahil", "Gongabu", "Balaju",
         "Sinamangal", "Gaushala", "Basundhara", "Samakhusi", "Narayan Gopal Chowk", "Dhumbarahi", "Gopikrishna",
         "Balkumari", "Machhapokhari", "Banasthali", "Swayambhu", "Sitapaila", "Nakhu", "Mahalaxmisthan",
         "Tinkune", "Maharajgunj", "Sukedhara", "Bafal", "Dallu", "Chobhar", "Hattiban", "Imadol", "Bijulibazar"]
NE = {"Kalanki": "कलंकी", "Balkhu": "बल्खु", "Ekantakuna": "एकान्तकुना", "Satdobato": "सातदोबाटो", "Gwarko": "ग्वार्को",
      "Koteshwor": "कोटेश्वर", "Chabahil": "चाबहिल", "Gongabu": "गोंगबु", "Balaju": "बालाजु", "Sinamangal": "सिनामंगल",
      "Gaushala": "गौशाला", "Basundhara": "बसुन्धरा", "Samakhusi": "सामाखुसी", "Narayan Gopal Chowk": "नारायण गोपाल चोक",
      "Dhumbarahi": "धुम्बाराही", "Gopikrishna": "गोपीकृष्ण", "Balkumari": "बालकुमारी", "Machhapokhari": "माछापोखरी",
      "Banasthali": "वनस्थली", "Swayambhu": "स्वयम्भू", "Sitapaila": "सितापाइला", "Nakhu": "नखु",
      "Mahalaxmisthan": "महालक्ष्मीस्थान", "Tinkune": "तीनकुने", "Maharajgunj": "महाराजगञ्ज", "Sukedhara": "सुकेधारा",
      "Bafal": "बफल", "Dallu": "डल्लु", "Chobhar": "चोभार", "Hattiban": "हात्तीवन", "Imadol": "इमाडोल",
      "Bijulibazar": "बिजुलीबजार"}


def obb(poly):
    r = poly.minimum_rotated_rectangle
    c = np.asarray(r.exterior.coords)[:4]
    e0, e1 = c[1] - c[0], c[2] - c[1]
    return (float(r.centroid.x), float(r.centroid.y), float(np.linalg.norm(e0)), float(np.linalg.norm(e1)),
            float(math.atan2(e0[1], e0[0])))


class Loop:
    """Closed centreline with nearest-point queries."""

    def __init__(self, P):
        self.P = P
        self.n = len(P)
        d = np.linalg.norm(np.roll(P, -1, 0) - P, axis=1)
        self.s = np.concatenate([[0], np.cumsum(d)[:-1]])
        self.L = float(d.sum())
        t = np.roll(P, -1, 0) - np.roll(P, 1, 0)
        self.T = t / np.linalg.norm(t, axis=1)[:, None]
        self.N = np.stack([-self.T[:, 1], self.T[:, 0]], 1)
        self.ring = shapely.LinearRing(P)

    def nearest(self, xy):
        xy = np.atleast_2d(xy).astype(np.float32)
        P = self.P.astype(np.float32)
        out = np.empty(len(xy), np.int64)
        for i in range(0, len(xy), 1500):
            q = xy[i:i + 1500]
            d = (q[:, None, 0] - P[None, :, 0]) ** 2 + (q[:, None, 1] - P[None, :, 1]) ** 2
            out[i:i + 1500] = d.argmin(1)
        return out

    def offset(self, xy):
        """(index, signed lateral offset; + = left of travel)."""
        xy = np.atleast_2d(xy)
        k = self.nearest(xy)
        return k, np.sum((xy - self.P[k]) * self.N[k], 1)

    def ds(self, a, b):
        """Forward distance along the loop from s=a to s=b."""
        return (b - a) % self.L


def places(meta, loop, o):
    path = os.path.join(DATA, "places_ring.json")
    pr = json.load(open(path))
    lonlat = lambda lon, lat: np.array([(lon - meta["lon0"]) * meta["kx"] - o[0], (lat - meta["lat0"]) * meta["ky"] - o[1]])
    best = {}
    for h in pr["search"]:
        if h["q"] not in MAJOR:
            continue
        p = lonlat(h["lon"], h["lat"])
        k, off = loop.offset(p)
        d = abs(float(off[0]))
        # a neighbourhood's node sits in its middle; the chowk it names is on the Ring Road
        if d > (750 if h["cls"] == "place" else 300):
            continue
        if h["q"] not in best or d < best[h["q"]][1]:
            best[h["q"]] = (int(k[0]), d)
    out = []
    for name in MAJOR:                      # priority order; keep boards >= 450 m apart
        if name not in best:
            continue
        k = best[name][0]
        s = loop.s[k]
        if all(min(loop.ds(s, loop.s[q["k"]]), loop.ds(loop.s[q["k"]], s)) > 450 for q in out):
            out.append({"k": k, "en": name, "ne": NE.get(name, name)})
    # fill long gaps with the neighbourhood names from reverse geocoding
    names = []
    for r in pr["reverse"]:
        a, b = r["en"], r["ne"]
        for key in ("neighbourhood", "quarter", "suburb"):
            if a.get(key):
                names.append((r["k"], a[key], b.get(key, a[key])))
                break
    for k2, en, ne in names:
        k = k2 // 2                           # loop.npy is 2 m, export is 4 m
        s = loop.s[k]
        if any(en.lower().startswith(q["en"].lower()[:5]) for q in out):
            continue
        if all(min(loop.ds(s, loop.s[q["k"]]), loop.ds(loop.s[q["k"]], s)) > 1300 for q in out):
            out.append({"k": int(k), "en": en, "ne": ne})
    out.sort(key=lambda q: q["k"])
    return out


def main():
    npz = np.load(os.path.join(DATA, "prep.npz"))
    meta = json.load(open(os.path.join(DATA, "prep.json")))
    G = Ground(npz, meta)
    c2, lines = ring_loop.centreline(meta)
    c = c2[::int(STEP / 2)]
    o = c.mean(0).round(0)
    loop = Loop(c - o)
    P = loop.P
    print(f"loop {loop.L:.0f} m, {loop.n} points")

    # --- places and the 8-lane stretch (Kalanki -> Balkhu -> Koteshwor, the southern arc) -----------
    pl = places(meta, loop, o)
    for q in pl:
        print(f"  {loop.s[q['k']]:7.0f} m  {q['en']}  {q['ne']}")
    kk = {q["en"]: q["k"] for q in pl}
    a, b = loop.s[kk["Kalanki"]], loop.s[kk["Koteshwor"]]
    sb = loop.s[kk["Balkhu"]]
    if loop.ds(a, sb) > loop.ds(a, b):       # go the way that passes Balkhu
        a, b = b, a
    a, b = a - 150, b + 150                   # the widening runs past both junctions
    inside = np.array([loop.ds(a, s) <= loop.ds(a, b) for s in loop.s], float)
    # 120 m transitions
    r = 15
    k = np.ones(2 * r + 1) / (2 * r + 1)
    wide = np.convolve(np.concatenate([inside[-r:], inside, inside[:r]]), k, mode="valid")
    wide = np.clip(np.round(wide * 20) / 20, 0, 1)
    edge = NARROW_EDGE + (S.EDGE - NARROW_EDGE) * wide

    # --- bridges --------------------------------------------------------------------------------
    br = []
    for e, l in lines:
        # river bridges; the long flyovers are drawn at grade, without parapets
        if e.get("tags", {}).get("bridge") == "yes" and l.length < 200:
            ks = loop.nearest(np.asarray(l.coords) - o)
            s0, s1 = loop.s[ks.min()], loop.s[ks.max()]
            if ks.max() - ks.min() > loop.n / 2:          # wraps around the start
                continue
            br.append([s0 - 10, s1 + 10])
    br.sort()
    bridges = []
    for s0, s1 in br:
        if bridges and s0 <= bridges[-1][1] + 5:
            bridges[-1][1] = max(bridges[-1][1], s1)
        else:
            bridges.append([s0, s1])
    print("bridges", [round(b[1] - b[0]) for b in bridges])

    # --- side road stubs (where the city's roads meet the Ring Road) ------------------------------
    ring_ids = {e["id"] for e, _ in lines}
    stubs = []
    for rd in meta["roads"]:
        if rd["id"] in ring_ids or rd["cls"] not in SIDE_CLS or rd["ring"]:
            continue
        pts = np.asarray(rd["pts"]) - o
        if len(pts) < 2:
            continue
        line = LineString(pts)
        if line.distance(loop.ring) > S.EDGE + 2:
            continue
        d = ring_loop.resample(pts, 2.0, closed=False)
        if len(d) < 3:
            continue
        kd, off = loop.offset(d)
        ein = np.abs(off) < edge[kd] + 0.5
        w = SIDE_CLS[rd["cls"]]
        # each run of outside points that starts at the kerb becomes a stub
        for direction in (1, -1):
            idx = np.arange(len(d))[::direction]
            for j in range(1, len(idx)):
                i0, i1 = idx[j - 1], idx[j]
                if ein[i0] and not ein[i1]:
                    run = [d[i0]]
                    for i in idx[j:]:
                        if ein[i] or len(run) > STUB / 2:
                            break
                        run.append(d[i])
                    run = np.asarray(run)
                    if len(run) < 4:
                        continue
                    side = 1 if off[i1] > 0 else -1
                    if abs(off[i1]) > edge[kd[i1]] + S.FOOT + 6:
                        continue
                    stubs.append({"k": int(kd[i1]), "side": side, "w": w,
                                  "p": np.round(run, 1).ravel().tolist()})
    print("side roads", len(stubs))
    stub_geo = shapely.union_all([LineString(np.asarray(s["p"]).reshape(-1, 2)).buffer(s["w"] / 2 + 1.2) for s in stubs])

    # --- buildings ------------------------------------------------------------------------------
    xy, off, lv = npz["bxy"].astype(np.float64) - o, npz["boff"], npz["blevels"]
    cx = np.add.reduceat(xy[:, 0], off[:-1]) / np.diff(off)
    cy = np.add.reduceat(xy[:, 1], off[:-1]) / np.diff(off)
    dc = shapely.distance(loop.ring, shapely.points(cx, cy))
    sel = np.nonzero(dc < FAR + 30)[0]
    polys = np.array([Polygon(xy[off[k]:off[k + 1]]) for k in sel], dtype=object)
    dpoly = shapely.distance(loop.ring, polys)
    kc = loop.nearest(np.stack([cx[sel], cy[sel]], 1))
    clear = edge[kc] + S.FOOT + 1.5
    hit_stub = shapely.intersects(polys, stub_geo)
    near, far = [], []
    rng = np.random.default_rng(7)
    for j, k in enumerate(sel):
        p = polys[j]
        if dpoly[j] < clear[j] or hit_stub[j] or p.area < 8:
            continue
        floors = max(1, int(round(float(lv[k]))))
        col = int(rng.integers(0, 1 << 30))
        if dc[k] < NEAR:
            q = p.simplify(0.25)
            if q.is_empty or q.geom_type != "Polygon":
                continue
            ring = np.asarray(q.exterior.coords)[:-1]
            if not Polygon(ring).exterior.is_ccw:
                ring = ring[::-1]
            near.append({"p": np.round(ring, 1).ravel().tolist(), "f": floors, "c": col % 100000, "k": int(kc[j]),
                         "b": [round(v, 2) for v in obb(q)]})
        elif dc[k] < FAR:
            far.append([round(v, 1) for v in obb(p)] + [floors, col % 997, int(kc[j])])
    print(f"near buildings {len(near)}, far {len(far)}")

    # --- terrain: real DEM relative to the road, flattened near it ---------------------------------
    x0, y0 = P.min(0) - TER
    x1, y1 = P.max(0) + TER
    xs = np.arange(x0, x1 + TSTEP, TSTEP)
    ys = np.arange(y0, y1 + TSTEP, TSTEP)
    X, Y = np.meshgrid(xs, ys)
    z = G.z(X.ravel() + o[0], Y.ravel() + o[1])
    dd = shapely.distance(loop.ring, shapely.points(X.ravel(), Y.ravel()))
    inner = shapely.contains_xy(Polygon(P), X.ravel(), Y.ravel())
    zr = float(np.median(G.z(P[:, 0] + o[0], P[:, 1] + o[1])))
    w = np.clip((dd - (FAR + 40)) / 600.0, 0, 1)
    w = np.where(inner, 0, w * w * (3 - 2 * w))          # the city inside the ring stays flat
    h = (z - zr) * w - 0.45          # sits well under the road surfaces (no z-fighting)
    h = np.maximum(h, -0.45)
    hq = np.clip(np.round(h * 10), -32000, 32000).astype(np.int16)
    hg = h.reshape(X.shape)
    for fb in far:
        i = min(max(int(round((fb[1] - y0) / TSTEP)), 0), len(ys) - 1)
        j = min(max(int(round((fb[0] - x0) / TSTEP)), 0), len(xs) - 1)
        fb.append(round(float(hg[i, j]), 1))

    # --- satellite image in the same frame ---------------------------------------------------------
    import rasterio
    from PIL import Image
    with rasterio.open(os.path.join(DATA, "sentinel2.tif")) as src:
        bd = src.bounds
    sat = Image.open(os.path.join(DATA, "sentinel2.jpg"))
    sat.thumbnail((4096, 4096))
    sat.save(os.path.join(WEB, "ktm_sat.jpg"), quality=84)
    sbnd = [(bd.left - meta["lon0"]) * meta["kx"] - o[0], (bd.bottom - meta["lat0"]) * meta["ky"] - o[1],
            (bd.right - meta["lon0"]) * meta["kx"] - o[0], (bd.top - meta["lat0"]) * meta["ky"] - o[1]]

    out = {
        "about": "Kathmandu Ring Road. OpenStreetMap (ODbL), Google Open Buildings (CC BY 4.0), "
                 "Copernicus GLO-30 DEM, Sentinel-2 (contains modified Copernicus Sentinel data 2026).",
        "road": {"pts": np.round(P, 2).ravel().tolist(), "step": STEP, "loop": round(loop.L, 1),
                 "wide": [int(v * 20) for v in wide], "bridges": [[round(a, 1), round(b, 1)] for a, b in bridges],
                 "median": S.MEDIAN, "lane": S.LANE, "shoulder": S.SHOULDER, "sep": S.SEP, "foot": S.FOOT,
                 "start": int(kk["Kalanki"])},
        "stubs": stubs, "places": pl,
        "near": near, "far": far,
        "terrain": {"x0": round(x0, 1), "y0": round(y0, 1), "step": TSTEP, "nx": len(xs), "ny": len(ys),
                    "h": base64.b64encode(hq.tobytes()).decode()},
        "sat": {"file": "ktm_sat.jpg", "bounds": [round(v, 1) for v in sbnd]},
    }
    path = os.path.join(WEB, "ktm_map.json")
    json.dump(out, open(path, "w"), separators=(",", ":"), ensure_ascii=False)
    print("wrote", path, round(os.path.getsize(path) / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
