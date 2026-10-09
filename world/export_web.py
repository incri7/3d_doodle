"""Export the whole Kathmandu Ring Road loop for the web driving page.

Writes web/ktm_map.json and web/ktm_sat.jpg (Sentinel-2):
  road     closed centreline every 4 m; per point, from the OSM lanes: service
           carriageways each side, divided or not, lanes each way; bridges,
           the flyover, side-road stubs
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


def match(name, text):
    """Does a road / node name refer to this place? (OSM spells Ekantakuna 'Yekantakuna' too)"""
    t = (text or "").lower().replace("yekanta", "ekanta").replace(" ", "")
    return name.lower().replace(" ", "")[:6] in t


def junctions(meta, loop, o, ring_ids):
    """Where the city's main roads cross the Ring Road: (index, class, name)."""
    tags = {e["id"]: e.get("tags", {}) for e in json.load(open(os.path.join(DATA, "roads.json")))["elements"]}
    out = []
    for rd in meta["roads"]:
        if rd["id"] in ring_ids or rd["ring"] or rd["cls"] not in ("trunk", "primary", "secondary", "tertiary"):
            continue
        p = np.asarray(rd["pts"]) - o
        if LineString(p).distance(loop.ring) > 25:           # roads end at the outer kerb, up to ~18 m out
            continue
        d = ring_loop.resample(p, 2.0, closed=False)
        if len(d) < 2:
            continue
        k, off = loop.offset(d)
        i = int(np.argmin(np.abs(off)))
        t = np.gradient(d, axis=0)
        t /= np.linalg.norm(t, axis=1)[:, None] + 1e-9
        if abs(np.sum(t[i] * loop.T[k[i]])) > 0.8:          # runs along the Ring Road, not across
            continue
        t = tags.get(rd["id"], {})
        out.append((int(k[i]), rd["cls"], " ".join(filter(None, (t.get("name"), t.get("name:en"), t.get("ref"))))))
    return out


def places(meta, loop, o, ring_ids):
    """One board per place, at its chowk on the Ring Road:
    1. a node named '<place> Chowk' (junction, bus stop, square) on the road,
    2. else where a road named after the place crosses (nearest the place's own node),
    3. else the nearest main-road crossing within 450 m of the place's node,
    4. else level with the place's node."""
    pr = json.load(open(os.path.join(DATA, "places_ring.json")))
    lonlat = lambda lon, lat: np.array([(lon - meta["lon0"]) * meta["kx"] - o[0], (lat - meta["lat0"]) * meta["ky"] - o[1]])
    dist = lambda a, b: min(loop.ds(loop.s[a], loop.s[b]), loop.ds(loop.s[b], loop.s[a]))
    node = {}
    for h in pr["search"]:
        if h["q"] not in MAJOR:
            continue
        k, off = loop.offset(lonlat(h["lon"], h["lat"]))
        d = abs(float(off[0]))
        # a neighbourhood's node sits in its middle; the chowk it names is on the Ring Road
        if d > (750 if h["cls"] == "place" else 300):
            continue
        if h["q"] not in node or d < node[h["q"]][1]:
            node[h["q"]] = (int(k[0]), d)
    J = junctions(meta, loop, o, ring_ids)
    found = {}
    for name in MAJOR:
        guess = node.get(name, (None,))[0]
        near = lambda ks: min(ks, key=lambda k: dist(k, guess)) if guess is not None else ks[0]
        tagged = []
        for h in pr.get("chowk", []):
            if h["q"] != name or not match(name, h["name"]) or "chowk" not in (h["name"] or "").lower():
                continue
            k, off = loop.offset(lonlat(h["lon"], h["lat"]))
            if abs(float(off[0])) < 150:
                tagged.append(int(k[0]))
        named = [k for k, cls, nm in J if match(name, nm) and (guess is None or dist(k, guess) < 1000)]
        major = [k for k, cls, nm in J if guess is not None and dist(k, guess) < 450]
        for how, ks in (("chowk node", tagged), ("road named after it", named), ("nearest crossing", major)):
            if ks:
                found[name] = (near(ks), how)
                break
        else:
            if guess is not None:
                found[name] = (guess, "place node")
    out = []
    for name in MAJOR:                      # priority order; keep boards >= 450 m apart
        if name not in found:
            continue
        k, how = found[name]
        if all(dist(k, q["k"]) > 450 for q in out):
            out.append({"k": k, "en": name, "ne": NE.get(name, name), "how": how})
    # fill long gaps with the neighbourhood names from reverse geocoding
    for r in pr["reverse"]:
        a, b = r["en"], r["ne"]
        key = next((x for x in ("neighbourhood", "quarter", "suburb") if a.get(x)), None)
        if not key:
            continue
        k, en, ne = r["k"] // 2, a[key], b.get(key, a[key])          # loop.npy is 2 m, export is 4 m
        if any(en.lower().startswith(q["en"].lower()[:5]) for q in out):
            continue
        if all(dist(k, q["k"]) > 1300 for q in out):
            out.append({"k": int(k), "en": en, "ne": ne, "how": "neighbourhood"})
    out.sort(key=lambda q: q["k"])
    return out


def q20(a):
    return [int(v) for v in np.clip(np.round(np.asarray(a) * 20), 0, 20)]


def smooth_loop(v, r):
    k = np.ones(2 * r + 1) / (2 * r + 1)
    return np.convolve(np.concatenate([v[-r:], v, v[:r]]), k, mode="valid")


def close_gaps(v, n):
    """Fill runs of False shorter than n points between True runs (closed loop)."""
    v = v.copy()
    if not v.any():
        return v
    start = int(np.argmax(v))
    r = np.roll(v, -start)
    i = 0
    while i < len(r):
        if not r[i]:
            j = i
            while j < len(r) and not r[j]:
                j += 1
            if j - i < n and j < len(r):
                r[i:j] = True
            i = j
        else:
            i += 1
    return np.roll(r, start)


def drop_short(v, n):
    v = v.copy()
    i = 0
    while i < len(v):
        if v[i]:
            j = i
            while j < len(v) and v[j]:
                j += 1
            if j - i < n:
                v[i:j] = False
            i = j
        else:
            i += 1
    return v


def cross_section(meta, loop, o, lines):
    """What OpenStreetMap says at each centreline point:
    wl / wr  a one-way 2-lane service carriageway beside the main road on the
             left (+) / right (-) side: the parallel primary roads Kalanki -> Koteshwor
    div      the main road is a dual carriageway (two one-way ways) with a median,
             rather than one undivided two-way way
    ln       lanes each way on the main road (two-way lanes / 2, or the one-way lanes)"""
    n = loop.n
    ring = {e["id"] for e, _ in lines}
    side = {1: np.zeros(n, bool), -1: np.zeros(n, bool)}
    for rd in meta["roads"]:
        if rd["cls"] != "primary":           # (the relation itself carries a few of them near Kalanki)
            continue
        p = ring_loop.resample(np.asarray(rd["pts"]) - o, 2.0, closed=False)
        if len(p) < 3:
            continue
        k, off = loop.offset(p)
        d = np.gradient(p, axis=0)
        d /= np.linalg.norm(d, axis=1)[:, None] + 1e-9
        m = (np.abs(np.sum(d * loop.T[k], 1)) > 0.94) & (np.abs(off) > 7) & (np.abs(off) < 24)
        for kk, oo in zip(k[m], off[m]):
            side[1 if oo > 0 else -1][kk] = True
    out = {}
    for sg, name in ((1, "wl"), (-1, "wr")):
        v = drop_short(close_gaps(side[sg], 50), 25)          # bridge junction gaps < 200 m; ignore stubs < 100 m
        out[name] = np.clip(smooth_loop(v.astype(float), 15), 0, 1)
    dual = {1: np.zeros(n, bool), -1: np.zeros(n, bool)}
    single = np.zeros(n, bool)
    lanes = np.full(n, np.nan)
    for e, l in lines:
        t = e.get("tags", {})
        p = ring_loop.resample(np.asarray(l.coords) - o, 2.0, closed=False)
        if len(p) < 2:
            continue
        k, off = loop.offset(p)
        try:
            nl = float(t.get("lanes"))
        except (TypeError, ValueError):
            nl = None
        if t.get("oneway") == "yes":
            for kk, oo in zip(k, off):
                if 1.0 < abs(oo) < 10:
                    dual[1 if oo > 0 else -1][kk] = True
            per = min(nl, 2) if nl else 2
        else:
            single[k[np.abs(off) < 3]] = True
            per = nl / 2 if nl else 2
        lanes[k] = np.where(np.isnan(lanes[k]), per, np.minimum(lanes[k], per))
    div = close_gaps(dual[1] & dual[-1] & ~single, 15) | (dual[1] & dual[-1])
    div = drop_short(div, 10)
    out["div"] = np.clip(smooth_loop(div.astype(float), 5), 0, 1)
    # lanes: fill points no way covers from the neighbours, then taper over ~40 m
    idx = np.nonzero(~np.isnan(lanes))[0]
    lanes = np.interp(np.arange(n), idx, lanes[idx], period=n)
    lanes = np.clip(np.round(lanes), 1, 2)
    out["ln"] = np.clip(smooth_loop(lanes, 5), 1, 2)
    for kname in ("wl", "wr", "div"):
        v = out[kname] > 0.5
        runs = []
        i = 0
        while i < n:
            if v[i]:
                j = i
                while j < n and v[j]:
                    j += 1
                runs.append((round(loop.s[i]), round(loop.s[j - 1])))
                i = j
            else:
                i += 1
        print(kname, runs)
    one = np.nonzero(out["ln"] < 1.5)[0]
    print("1 lane each way at", sorted({round(loop.s[i] / 100) * 100 for i in one}))
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

    # --- places ----------------------------------------------------------------------------------
    pl = places(meta, loop, o, {e["id"] for e, _ in lines})
    for q in pl:
        print(f"  {loop.s[q['k']]:7.0f} m  {q['en']}  {q['ne']}  ({q.pop('how')})")
    kk = {q["en"]: q["k"] for q in pl}

    # --- cross-section from the OSM lanes, per point and per side -------------------------------
    sec = cross_section(meta, loop, o, lines)
    wl, wr, div, ln = sec["wl"], sec["wr"], sec["div"], sec["ln"]
    inner = div * S.MEDIAN / 2 + ln * S.LANE + S.SHOULDER
    edge = inner + np.maximum(wl, wr) * (S.SEP + S.CW)          # outer kerb line (the wider side)

    # --- bridges: short ones cross rivers; the long ones are the flyover's elevated deck -------------
    def merged(ranges, pad):
        out = []
        for s0, s1 in sorted(ranges):
            if out and s0 <= out[-1][1] + 5:
                out[-1][1] = max(out[-1][1], s1)
            else:
                out.append([s0, s1])
        return [[a - pad, b + pad] for a, b in out]
    br, fly = [], []
    for e, l in lines:
        if e.get("tags", {}).get("bridge") != "yes":
            continue
        ks = loop.nearest(np.asarray(l.coords) - o)
        if ks.max() - ks.min() > loop.n / 2:          # wraps around the start
            continue
        (br if l.length < 200 else fly).append([loop.s[ks.min()], loop.s[ks.max()]])
    bridges = merged(br, 10)
    flyovers = merged(fly, 0)
    print("flyovers", [[round(a), round(b)] for a, b in flyovers])
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
                 "wl": q20(wl), "wr": q20(wr), "div": q20(div), "ln": q20(ln - 1), "bridges": [[round(a, 1), round(b, 1)] for a, b in bridges],
                 "flyovers": [[round(a, 1), round(b, 1)] for a, b in flyovers],
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
