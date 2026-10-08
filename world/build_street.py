"""Street-level Kathmandu Ring Road: Kalanki -> Balkhu bridge (~1.6 km).

Built on the real data (data/ktm/prep.*): road alignment from the two
OpenStreetMap carriageways, terrain from Copernicus, buildings from OSM +
Google Open Buildings. The street detail follows the Mapillary photos of
this stretch: worn asphalt with white lane dashes and yellow edge lines, a
raised median with black/yellow kerbs, footpaths with black/yellow kerbs,
electric poles with sagging wires, median street lights, 3-6 storey houses
with windows, balconies, shop shutters and signboards, black water tanks on
the roofs. The Agni and Sajha buses drive on it for scale.

  .venv/bin/python world/build_street.py [--fast] [--shots a,b]
Renders to output/ktm_street/ (and photo comparisons against Mapillary).
"""
import argparse, datetime, json, math, os, sys

import bpy
import numpy as np
import shapely
from shapely.geometry import LineString, Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from doodle import geo, render  # noqa: E402
import build_ktm  # noqa: E402
from build_ktm import Ground, mesh_obj, WALLS  # noqa: E402

DATA = os.path.join(ROOT, "data", "ktm")
OUTDIR = os.path.join(ROOT, "output", "ktm_street")

# carriageway A and the opposite carriageway B (OpenStreetMap way ids)
CHAIN_A = [180152353, 195858822, 195858821, 171599261]   # Balkhu bridge -> Kalanki, end to end
OPPOSITE = [777629770]
BRIDGE_WAYS = {195858822}
# Cross-section (OSM: inner trunk carriageways at +-4 m, outer ones at
# +-14..17 m; Mapillary: riders on the outer lanes, separator kerb on the
# right). 8 lanes: | foot | outer 2 | sep | inner 2 | median | inner 2 | sep | outer 2 | foot |
MEDIAN = 1.2          # central median width (m)
LANE = 3.5            # lane width
SHOULDER = 0.6        # paved strip next to each kerb
SEP = 1.8             # raised separator between inner and outer carriageways
FOOT = 2.6            # footpath width
CW = 2 * LANE + SHOULDER          # one carriageway (2 lanes)
M0 = MEDIAN / 2                   # inner carriageway starts
I1 = M0 + CW                      # inner carriageway ends / separator starts
S1 = I1 + SEP                     # outer carriageway starts
EDGE = S1 + CW                    # outer kerb line (distance from centreline)
CORRIDOR = 260        # buildings kept within this distance of the road
EXTEND = 120          # extend the road beyond the data ends (m)

SHOP_NAMES = ["किराना पसल", "मेडिकल हल", "मोबाइल सेन्टर", "हार्डवेयर", "फेन्सी स्टोर", "होटल तथा लज",
              "खाजा घर", "टायर पसल", "बैंक लिमिटेड", "सैलुन", "कपडा पसल", "फर्निचर", "अटो पार्ट्स",
              "मिठाई पसल", "स्टेशनरी", "रेष्टुरेन्ट", "इलेक्ट्रिकल्स", "ज्वेलर्स"]


# --- node helpers --------------------------------------------------------------------

class NT:
    """Tiny helper for building shader node graphs."""

    def __init__(self, mat):
        self.nt = mat.node_tree
        self.n = self.nt.nodes
        self.l = self.nt.links

    def node(self, kind, **props):
        nd = self.n.new(kind)
        for k, v in props.items():
            setattr(nd, k, v)
        return nd

    def math(self, op, a, b=None, clamp=False):
        nd = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        self._in(nd.inputs[0], a)
        if b is not None:
            self._in(nd.inputs[1], b)
        return nd.outputs[0]

    def mix(self, fac, a, b):
        nd = self.node("ShaderNodeMix", data_type="RGBA")
        self._in(nd.inputs[0], fac)
        self._in(nd.inputs[6], a)
        self._in(nd.inputs[7], b)
        return nd.outputs[2]

    def _in(self, sock, v):
        if hasattr(v, "is_output") or hasattr(v, "links"):
            self.l.new(v, sock)
        elif isinstance(v, (tuple, list)):
            sock.default_value = (*v, 1.0) if len(v) == 3 else v
        else:
            sock.default_value = v

    def link(self, out, sock):
        self._in(sock, out)

    def uv(self):
        sep = self.node("ShaderNodeSeparateXYZ")
        self.l.new(self.node("ShaderNodeUVMap", uv_map="UVMap").outputs[0], sep.inputs[0])
        return sep.outputs[0], sep.outputs[1]

    def attr(self, name, out="Color"):
        a = self.node("ShaderNodeAttribute", attribute_name=name, attribute_type="GEOMETRY")
        return a.outputs[out]

    def between(self, x, lo, hi):
        return self.math("MULTIPLY", self.math("GREATER_THAN", x, lo), self.math("LESS_THAN", x, hi))


def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, NT(m), m.node_tree.nodes["Principled BSDF"]


def mat_asphalt():
    m, t, b = new_mat("MAT-asphalt_worn")
    u, v = t.uv()
    co = t.node("ShaderNodeCombineXYZ")
    t.link(u, co.inputs[0]); t.link(v, co.inputs[1])
    big = t.node("ShaderNodeTexNoise"); big.inputs["Scale"].default_value = 0.08
    t.link(co.outputs[0], big.inputs["Vector"])
    fine = t.node("ShaderNodeTexNoise"); fine.inputs["Scale"].default_value = 6.0
    fine.inputs["Detail"].default_value = 8
    t.link(co.outputs[0], fine.inputs["Vector"])
    # patches of repair and wear, fine aggregate speckle
    base = t.mix(t.math("MULTIPLY", big.outputs["Fac"], 1.0), (0.045, 0.045, 0.048), (0.085, 0.082, 0.08))
    col = t.mix(t.math("MULTIPLY", fine.outputs["Fac"], 0.5), base, (0.03, 0.03, 0.032))
    t.link(col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.9
    # cracks: voronoi edges as a bump
    vor = t.node("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE"); vor.inputs["Scale"].default_value = 0.9
    t.link(co.outputs[0], vor.inputs["Vector"])
    bump = t.node("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.35; bump.inputs["Distance"].default_value = 0.02
    t.link(t.math("LESS_THAN", vor.outputs["Distance"], 0.02), bump.inputs["Height"])
    t.link(bump.outputs[0], b.inputs["Normal"])
    return m


def mat_kerb(a=(0.015, 0.015, 0.015), c=(0.75, 0.5, 0.03), period=2.0):
    """Painted kerb: alternating black and yellow blocks along the road."""
    m, t, b = new_mat("MAT-kerb")
    u, _ = t.uv()
    f = t.math("LESS_THAN", t.math("FRACT", t.math("DIVIDE", u, period)), 0.5)
    t.link(t.mix(f, c, a), b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.6
    return m


def mat_pavers():
    m, t, b = new_mat("MAT-footpath_pavers")
    u, v = t.uv()
    co = t.node("ShaderNodeCombineXYZ")
    t.link(u, co.inputs[0]); t.link(v, co.inputs[1])
    br = t.node("ShaderNodeTexBrick")
    br.inputs["Color1"].default_value = (0.32, 0.25, 0.22, 1)
    br.inputs["Color2"].default_value = (0.42, 0.38, 0.34, 1)
    br.inputs["Mortar"].default_value = (0.2, 0.19, 0.18, 1)
    br.inputs["Scale"].default_value = 2.5
    br.inputs["Mortar Size"].default_value = 0.012
    t.link(co.outputs[0], br.inputs["Vector"])
    dirt = t.node("ShaderNodeTexNoise"); dirt.inputs["Scale"].default_value = 0.3
    t.link(co.outputs[0], dirt.inputs["Vector"])
    t.link(t.mix(t.math("MULTIPLY", dirt.outputs["Fac"], 0.6), br.outputs["Color"], (0.3, 0.26, 0.2)), b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.85
    return m


def mat_flat(name, color, rough=0.8, metal=0.0):
    m, t, b = new_mat(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def mat_attr(name, rough=0.7):
    m, t, b = new_mat(name)
    t.link(t.attr("col"), b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    return m


def mat_ground(sat_img):
    m, t, b = new_mat("MAT-ground")
    tc = t.node("ShaderNodeTexCoord")
    noise = t.node("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 0.035
    t.link(tc.outputs["Object"], noise.inputs["Vector"])
    fine = t.node("ShaderNodeTexNoise"); fine.inputs["Scale"].default_value = 1.5
    t.link(tc.outputs["Object"], fine.inputs["Vector"])
    dirt = t.mix(t.math("MULTIPLY", fine.outputs["Fac"], 0.6), (0.24, 0.17, 0.11), (0.17, 0.13, 0.09))
    grass = t.mix(t.math("MULTIPLY", fine.outputs["Fac"], 0.6), (0.09, 0.14, 0.04), (0.16, 0.18, 0.06))
    g = t.math("SMOOTHSTEP" if False else "GREATER_THAN", noise.outputs["Fac"], 0.55)
    proc = t.mix(g, dirt, grass)
    img = t.node("ShaderNodeTexImage"); img.image = bpy.data.images.load(sat_img); img.interpolation = "Cubic"
    t.link(t.mix(0.45, proc, img.outputs["Color"]), b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.95
    return m


def mat_walls():
    """Concrete house walls: colour per building, windows on every floor,
    slab bands, shop shutters on road-facing ground floors."""
    m, t, b = new_mat("MAT-house_walls")
    u, v = t.uv()
    wall = t.attr("col")
    shop = t.attr("shop", "Fac")
    fu = t.math("FRACT", t.math("DIVIDE", u, 3.1))
    fv = t.math("FRACT", t.math("DIVIDE", v, 2.9))
    above = t.math("GREATER_THAN", v, 0.4)
    win = t.math("MULTIPLY", t.math("MULTIPLY", t.between(fu, 0.24, 0.76), t.between(fv, 0.3, 0.8)), above)
    frame = t.math("MULTIPLY", t.math("MULTIPLY", t.between(fu, 0.2, 0.8), t.between(fv, 0.26, 0.84)), above)
    band = t.math("MULTIPLY", t.math("LESS_THAN", fv, 0.07), above)
    shopm = t.math("MULTIPLY", t.math("MULTIPLY", t.math("GREATER_THAN", shop, 0.5), t.math("LESS_THAN", v, 2.75)),
                   t.math("GREATER_THAN", v, 0.15))
    corr = t.math("ADD", 0.82, t.math("MULTIPLY", 0.18, t.math("SINE", t.math("MULTIPLY", u, 40.0))))
    shutter = t.mix(0.0, (0.22, 0.26, 0.3), (0.22, 0.26, 0.3))
    shutter = t.mix(t.math("SUBTRACT", 1.0, corr), shutter, (0.08, 0.09, 0.1))
    grime_n = t.node("ShaderNodeTexNoise"); grime_n.inputs["Scale"].default_value = 0.9
    tc = t.node("ShaderNodeTexCoord"); t.link(tc.outputs["Object"], grime_n.inputs["Vector"])
    c = t.mix(t.math("MULTIPLY", grime_n.outputs["Fac"], 0.35), wall, (0.12, 0.11, 0.1))
    c = t.mix(band, c, (0.55, 0.54, 0.52))
    c = t.mix(frame, c, (0.75, 0.75, 0.72))
    c = t.mix(win, c, (0.035, 0.05, 0.065))
    c = t.mix(shopm, c, shutter)
    t.link(c, b.inputs["Base Color"])
    t.link(t.math("ADD", 0.85, t.math("MULTIPLY", win, -0.75)), b.inputs["Roughness"])
    t.link(t.math("MULTIPLY", shopm, 0.6), b.inputs["Metallic"])
    return m


# --- geometry helpers ---------------------------------------------------------------

class Batch:
    """Accumulate boxes/cylinders into one mesh with a per-corner colour."""

    def __init__(self):
        self.v, self.f, self.c = [], [], []

    def box(self, center, axes, half, color):
        cx = np.asarray(center, float)
        ex, ey, ez = (np.asarray(a, float) * h for a, h in zip(axes, half))
        base = len(self.v)
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    self.v.append(tuple(cx + sx * ex + sy * ey + sz * ez))
        for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            self.f.append(tuple(base + i for i in q))
            self.c.extend([color] * 4)

    def cylinder(self, x, y, z0, r, h, color, n=12):
        base = len(self.v)
        for k in range(n):
            a = 2 * math.pi * k / n
            self.v += [(x + r * math.cos(a), y + r * math.sin(a), z0), (x + r * math.cos(a), y + r * math.sin(a), z0 + h)]
        for k in range(n):
            a0, a1 = base + 2 * k, base + 2 * ((k + 1) % n)
            self.f.append((a0, a1, a1 + 1, a0 + 1)); self.c.extend([color] * 4)
        self.f.append(tuple(base + 2 * k + 1 for k in range(n))); self.c.extend([color] * n)

    def build(self, name, material):
        col = np.concatenate([np.asarray(self.c, np.float32), np.ones((len(self.c), 1), np.float32)], 1).ravel()
        return mesh_obj(name, self.v, self.f, material, col)


# --- the road -----------------------------------------------------------------------

def load_line(roads_json, ids, meta):
    d = {e["id"]: e for e in roads_json if e.get("type") == "way"}
    pts = []
    for i in ids:
        g = d[i]["geometry"]
        p = [((q["lon"] - meta["lon0"]) * meta["kx"], (q["lat"] - meta["lat0"]) * meta["ky"]) for q in g]
        if pts and np.hypot(*(np.array(p[-1]) - pts[-1])) < np.hypot(*(np.array(p[0]) - pts[-1])):
            p = p[::-1]
        pts += p if not pts else p[1:]
    return np.asarray(pts)


def resample(p, step):
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    t = np.arange(0, s[-1], step)
    return np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], 1)


def smooth1d(a, r):
    k = np.ones(2 * r + 1) / (2 * r + 1)
    pad = np.pad(a, ((r, r),) + ((0, 0),) * (a.ndim - 1), mode="edge")
    if a.ndim == 1:
        return np.convolve(pad, k, mode="valid")
    return np.stack([np.convolve(pad[:, j], k, mode="valid") for j in range(a.shape[1])], 1)


class Road:
    def __init__(self, G, meta):
        rj = json.load(open(os.path.join(DATA, "roads.json")))["elements"]
        A = resample(load_line(rj, CHAIN_A, meta), 2.0)
        B = LineString(load_line(rj, OPPOSITE, meta))
        # centreline halfway between the two carriageways
        near = np.array([np.asarray(B.interpolate(B.project(shapely.Point(p))).coords[0]) for p in A])
        mid = (A + near) / 2
        far = np.linalg.norm(A - near, axis=1) > 25          # beyond B's ends: offset A by the typical gap
        c = np.where(far[:, None], np.nan, mid)
        # beyond B's ends: A shifted by half the carriageway separation toward B
        t = np.gradient(A, axis=0); t /= np.linalg.norm(t, axis=1)[:, None]
        nA = np.stack([-t[:, 1], t[:, 0]], 1)
        side = np.sign(np.median(np.sum(nA * (near - A), 1)[~far]))
        gap = np.median(np.linalg.norm(A - near, axis=1)[~far]) / 2
        c = np.where(np.isnan(c), A + side * nA * gap, c)
        c = smooth1d(c, 6)
        # extend both ends straight
        t0 = c[1] - c[0]; t0 /= np.linalg.norm(t0)
        t1 = c[-1] - c[-2]; t1 /= np.linalg.norm(t1)
        pre = [c[0] - t0 * k for k in np.arange(EXTEND, 0, -2.0)]
        post = [c[-1] + t1 * k for k in np.arange(2.0, EXTEND + 2, 2.0)]
        c = resample(np.vstack([pre, c, post]), 2.0)
        self.P = c
        tt = np.gradient(c, axis=0); tt /= np.linalg.norm(tt, axis=1)[:, None]
        self.T = tt
        self.N = np.stack([-tt[:, 1], tt[:, 0]], 1)          # left of travel (Kalanki -> Balkhu)
        self.s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(c, axis=0), axis=1))])
        z = G.z(c[:, 0], c[:, 1])
        # bridge: keep the deck level across the river
        bl = load_line(rj, list(BRIDGE_WAYS), meta)
        line = LineString(c)
        bs = sorted(line.project(shapely.Point(p)) for p in bl)
        self.bridge = (bs[0] - 15, bs[-1] + 15)
        zs = smooth1d(z, 15)
        inb = (self.s > self.bridge[0]) & (self.s < self.bridge[1])
        if inb.any():
            zb = np.interp(self.bridge, self.s, zs)
            zs[inb] = np.interp(self.s[inb], self.bridge, zb)
        self.z = smooth1d(zs, 5)
        self.line = line

    def at(self, s):
        """Position, tangent, left normal and height at distance s."""
        i = np.clip(np.searchsorted(self.s, s), 1, len(self.s) - 1)
        f = (s - self.s[i - 1]) / (self.s[i] - self.s[i - 1])
        p = self.P[i - 1] * (1 - f) + self.P[i] * f
        return p, self.T[i], self.N[i], self.z[i - 1] * (1 - f) + self.z[i] * f

    def strip(self, name, o0, o1, h0, h1, material, s0=None, s1=None):
        """Quad strip from lateral offset o0 to o1 (left positive) at heights
        h0/h1 above the road surface, UV = (along, lateral)."""
        sel = np.ones(len(self.s), bool)
        if s0 is not None:
            sel &= (self.s >= s0) & (self.s <= s1)
        idx = np.nonzero(sel)[0]
        verts, faces, uvs = [], [], []
        for k, i in enumerate(idx):
            a = self.P[i] + self.N[i] * o0
            b = self.P[i] + self.N[i] * o1
            verts += [(a[0], a[1], self.z[i] + h0), (b[0], b[1], self.z[i] + h1)]
            if k:
                q = 2 * (k - 1)
                faces.append((q, q + 2, q + 3, q + 1))
        ob = mesh_obj(name, verts, faces, material)
        me = ob.data
        uv = me.uv_layers.new(name="UVMap")
        lv = np.empty(len(me.loops), np.int64)
        me.loops.foreach_get("vertex_index", lv)
        su = np.repeat(self.s[idx], 2)
        sv = np.tile([o0, o1], len(idx)) + np.tile([h0, h1], len(idx)) * 0
        uv.data.foreach_set("uv", np.stack([su[lv], sv[lv]], 1).ravel())
        return ob

    def dashes(self, name, offset, width, on, off, material, h=0.012):
        verts, faces = [], []
        for s in np.arange(0, self.s[-1] - on, on + off):
            k0 = len(verts)
            for ss in (s, s + on):
                p, t, n, z = self.at(ss)
                a, b = p + n * (offset - width / 2), p + n * (offset + width / 2)
                verts += [(a[0], a[1], z + h), (b[0], b[1], z + h)]
            faces.append((k0, k0 + 2, k0 + 3, k0 + 1))
        return mesh_obj(name, verts, faces, material)


def build_road(R):
    asphalt = mat_asphalt()
    kerb = mat_kerb()
    pavers = mat_pavers()
    concrete = mat_flat("MAT-median_top", (0.12, 0.11, 0.09), 0.95)
    white = mat_flat("MAT-paint_white", (0.75, 0.75, 0.72), 0.55)
    yellow = mat_flat("MAT-paint_yellow", (0.8, 0.52, 0.03), 0.55)
    dirt = mat_flat("MAT-verge_grass", (0.06, 0.08, 0.025), 0.95)
    m2 = M0
    for sgn in (1, -1):
        tag = "L" if sgn > 0 else "R"
        for nm, lo_, hi_ in (("inner", M0, I1), ("outer", S1, EDGE)):
            lo, hi = sorted((sgn * lo_, sgn * hi_))
            R.strip(f"GEO-carriageway_{nm}_{tag}", lo, hi, 0, 0, asphalt)
            # yellow edge lines along both kerbs, white dashes between the two lanes
            for off in (lo_ + 0.3, hi_ - 0.3):
                a, b = sorted((sgn * (off - 0.06), sgn * (off + 0.06)))
                R.strip("GEO-line_yellow", a, b, 0.01, 0.01, yellow)
            R.dashes("GEO-lane_dash", sgn * (lo_ + SHOULDER / 2 + LANE), 0.13, 3.0, 6.0, white)
        # raised separator between inner and outer carriageways
        a, b = sorted((sgn * I1, sgn * S1))
        R.strip("GEO-separator", a, b, 0.25, 0.25, concrete)
        R.strip("GEO-kerb_sep_in", sgn * I1, sgn * I1, 0, 0.25, kerb)
        R.strip("GEO-kerb_sep_out", sgn * S1, sgn * S1, 0, 0.25, kerb)
        # kerb faces and footpath
        R.strip("GEO-kerb_median", sgn * m2, sgn * m2, 0, 0.25, kerb)
        R.strip("GEO-kerb_foot", sgn * EDGE, sgn * EDGE, 0, 0.2, kerb)
        a, b = sorted((sgn * EDGE, sgn * (EDGE + FOOT)))
        R.strip("GEO-footpath", a, b, 0.2, 0.2, pavers)
        a, b = sorted((sgn * (EDGE + FOOT), sgn * (EDGE + FOOT + 3.5)))
        R.strip("GEO-verge", a, b, 0.2 if sgn > 0 else -0.25, -0.25 if sgn > 0 else 0.2, dirt)
    R.strip("GEO-median", -m2, m2, 0.25, 0.25, concrete)
    # bridge parapets over the Balkhu Khola
    rail = mat_flat("MAT-bridge_rail", (0.45, 0.44, 0.42), 0.6)
    for sgn in (1, -1):
        o = sgn * (EDGE + FOOT)
        R.strip("GEO-bridge_parapet", o, o, 0.2, 1.3, rail, *R.bridge)


# --- ground ---------------------------------------------------------------------------

class GroundNear:
    """DEM ground that meets the road: flattened under the corridor."""

    def __init__(self, G, R, rivers):
        self.G, self.R = G, R
        self.rivers = rivers

    def z(self, x, y):
        x, y = np.atleast_1d(x).astype(float), np.atleast_1d(y).astype(float)
        pts = shapely.points(x, y)
        d = shapely.distance(self.R.line, pts)
        sa = shapely.line_locate_point(self.R.line, pts)
        zr = np.interp(sa, self.R.s, self.R.z)
        base = self.G.z(x, y)
        w = np.clip((d - (EDGE + FOOT + 3.5)) / 30.0, 0, 1)
        w = w * w * (3 - 2 * w)
        h = zr - 0.25 + (base - zr + 0.25) * w
        # river valley under the bridge
        for rv in self.rivers:
            dr = shapely.distance(rv, pts)
            cut = np.clip(1 - dr / 18.0, 0, 1)
            h = h - 5.5 * cut * cut * (3 - 2 * cut)
        return h


def build_ground(GN, meta, R, sat_img, half=CORRIDOR + 60, step=3.0):
    x0, y0 = R.P.min(0) - half
    x1, y1 = R.P.max(0) + half
    xs = np.arange(x0, x1, step); ys = np.arange(y0, y1, step)
    X, Y = np.meshgrid(xs, ys)
    pts = shapely.points(X.ravel(), Y.ravel())
    keep = shapely.distance(R.line, pts) < half
    Z = np.full(X.shape, np.nan)
    Z.ravel()[keep] = GN.z(X.ravel()[keep], Y.ravel()[keep])
    h, w = X.shape
    vid = -np.ones(X.shape, int)
    vid.ravel()[keep] = np.arange(keep.sum())
    verts = np.stack([X.ravel()[keep], Y.ravel()[keep], Z.ravel()[keep]], 1)
    a, b, c, d = vid[:-1, :-1], vid[:-1, 1:], vid[1:, 1:], vid[1:, :-1]
    ok = (a >= 0) & (b >= 0) & (c >= 0) & (d >= 0)
    faces = np.stack([a[ok], b[ok], c[ok], d[ok]], 1)
    ob = mesh_obj("GEO-ground", verts.tolist(), faces.tolist())
    import rasterio
    with rasterio.open(os.path.join(DATA, "sentinel2.tif")) as src:
        bd = src.bounds
    lon = verts[:, 0] / meta["kx"] + meta["lon0"]
    lat = verts[:, 1] / meta["ky"] + meta["lat0"]
    u = (lon - bd.left) / (bd.right - bd.left); v = (lat - bd.bottom) / (bd.top - bd.bottom)
    me = ob.data
    uv = me.uv_layers.new(name="UVMap")
    lv = np.empty(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", lv)
    uv.data.foreach_set("uv", np.stack([u[lv], v[lv]], 1).ravel())
    for p in me.polygons:
        p.use_smooth = True
    ob.data.materials.append(mat_ground(sat_img))
    return ob


# --- buildings --------------------------------------------------------------------------

def build_buildings(npz, GN, R, rng):
    xy, off, lv = npz["bxy"].astype(np.float64), npz["boff"], npz["blevels"]
    polys = [Polygon(xy[off[k]:off[k + 1]]) for k in range(len(lv))]
    cen = shapely.centroid(polys)
    d = shapely.distance(R.line, cen)
    road_buf = R.line.buffer(EDGE + FOOT + 1.5)
    hits = shapely.intersects(np.array(polys, dtype=object), road_buf)
    sel = np.nonzero((d < CORRIDOR) & ~hits)[0]
    print("street buildings:", len(sel), flush=True)
    pal = np.array([c for c, _ in WALLS]); wts = np.array([w for _, w in WALLS], float); wts /= wts.sum()
    walls_v, walls_f, cols, shopc, uvs = [], [], [], [], []
    extras = Batch()       # balconies, signboards, parapets
    tanks = Batch()
    signs = []
    for k in sel:
        ring = xy[off[k]:off[k + 1]]
        n = len(ring)
        floors = max(1, int(round(float(lv[k]))))
        gz = GN.z(ring[:, 0], ring[:, 1])
        base = float(gz.min()) - 0.2
        top = base + floors * 2.9 + 0.5
        wall = pal[rng.choice(len(pal), p=wts)] * rng.uniform(0.85, 1.1)
        wall = np.clip(wall.mean() + (wall - wall.mean()) * 1.3, 0, 1)     # Kathmandu paint is bold
        roofc = (0.33, 0.32, 0.3)
        dist = float(d[k])
        v0 = len(walls_v)
        for x, y in ring:
            walls_v += [(x, y, base), (x, y, top)]
        perim = 0.0
        cpt = np.asarray(cen[k].coords[0])
        for j in range(n):
            a, b = ring[j], ring[(j + 1) % n]
            e = b - a; L = float(np.hypot(*e))
            if L < 1e-3:
                continue
            out = np.array([e[1], -e[0]]) / L          # outward for a CCW ring
            ra = np.asarray(R.line.interpolate(R.line.project(shapely.Point(*(a + b) / 2))).coords[0])
            to_road = ra - (a + b) / 2; to_road /= max(np.linalg.norm(to_road), 1e-6)
            facing = float(out @ to_road) > 0.6
            shop = facing and dist < 45 and L > 2.5
            i0, i1 = v0 + 2 * j, v0 + 2 * ((j + 1) % n)
            walls_f.append((i0, i1, i1 + 1, i0 + 1))
            cols.extend([tuple(wall)] * 4)
            shopc.extend([1.0 if shop else 0.0] * 4)
            uvs += [(perim, 0), (perim + L, 0), (perim + L, top - base), (perim, top - base)]
            perim += L
            ez = np.array([0, 0, 1.0]); ed = np.array([e[0] / L, e[1] / L, 0]); eo = np.array([out[0], out[1], 0])
            mid = (a + b) / 2
            if facing and dist < 60 and L > 3.0 and floors >= 2:
                # balconies with solid parapets on the upper floors
                for f in range(1, floors):
                    if rng.random() < 0.25:
                        continue
                    zf = base + f * 2.9
                    c3 = np.array([mid[0], mid[1], zf]) + eo * 0.5
                    bal = tuple(np.clip(np.asarray(wall) * 1.15, 0, 1))
                    extras.box(c3, (ed, eo, ez), (L / 2 - 0.3, 0.5, 0.07), bal)
                    extras.box(c3 + eo * 0.45 + ez * 0.5, (ed, eo, ez), (L / 2 - 0.3, 0.05, 0.45), bal)
            if shop and rng.random() < 0.8:
                sc = [(0.6, 0.04, 0.03), (0.04, 0.16, 0.5), (0.75, 0.55, 0.02), (0.05, 0.35, 0.1),
                      (0.85, 0.85, 0.82), (0.5, 0.02, 0.25)][rng.integers(6)]
                w = min(L - 0.4, 6.0)
                c3 = np.array([mid[0], mid[1], base + 3.25]) + eo * 0.12
                extras.box(c3, (ed, eo, ez), (w / 2, 0.06, 0.38), sc)
                signs.append((c3 + eo * 0.07, eo, w, sc))
        k1 = len(walls_v) // 2
        # roof cap and parapet
        walls_f.append(tuple(v0 + 2 * j + 1 for j in range(n)))
        cols.extend([roofc] * n); shopc.extend([0.0] * n)
        uvs += [(0, -10)] * n
        # water tank(s) on most roofs (black plastic, sometimes blue)
        poly = polys[k]
        if poly.area > 20 and rng.random() < 0.7:
            p = poly.representative_point()
            tc = (0.02, 0.02, 0.02) if rng.random() < 0.85 else (0.05, 0.2, 0.55)
            tanks.cylinder(p.x, p.y, top, 0.6, 1.25, tc)
            if poly.area > 120 and rng.random() < 0.5:
                tanks.cylinder(p.x + 1.4, p.y, top, 0.55, 1.15, tc)
    ob = mesh_obj("GEO-houses", walls_v, walls_f, mat_walls())
    me = ob.data
    ca = me.color_attributes.new("col", "FLOAT_COLOR", "CORNER")
    ca.data.foreach_set("color", np.concatenate([np.asarray(cols, np.float32), np.ones((len(cols), 1), np.float32)], 1).ravel())
    sa = me.attributes.new("shop", "FLOAT", "CORNER")
    sa.data.foreach_set("value", np.asarray(shopc, np.float32))
    uv = me.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", np.asarray(uvs, np.float32).ravel())
    extras.build("GEO-balconies_signs", mat_attr("MAT-balcony_sign", 0.6))
    tanks.build("GEO-water_tanks", mat_attr("MAT-water_tank", 0.4))
    return signs


def sign_text(signs, rng, cam_points, limit=45):
    """Devanagari shop names on the signboards nearest the camera spots."""
    if not signs:
        return
    cp = np.asarray(cam_points)
    dist = [min(np.linalg.norm(cp - s[0][:2], axis=1)) for s in signs]
    order = np.argsort(dist)[:limit]
    ink_w = mat_flat("MAT-sign_ink_white", (0.95, 0.95, 0.92), 0.4)
    ink_d = mat_flat("MAT-sign_ink_dark", (0.03, 0.03, 0.04), 0.4)
    for k in order:
        c3, eo, w, sc = signs[k]
        name = SHOP_NAMES[rng.integers(len(SHOP_NAMES))]
        yaw = math.atan2(eo[0], -eo[1])
        ob = geo.text("GEO-sign_text", name, size=min(0.5, w / max(len(name) * 0.42, 1)), depth=0.01,
                      location=tuple(c3 + eo * 0.01), rotation=(math.pi / 2, 0, yaw))
        bright = sum(sc) > 1.5
        ob.data.materials.append(ink_d if bright else ink_w)


def far_field(npz, meta, G, R, radius=3500):
    """The rest of the valley beyond the corridor: DEM + satellite terrain
    (sunk a little under the detailed ground) and the city's other buildings."""
    t = build_ktm.terrain(G, meta, npz)
    t.location.z = -1.5
    xy, off, lv = npz["bxy"], npz["boff"], npz["blevels"]
    cen = np.add.reduceat(xy.astype(np.float64), off[:-1]) / np.diff(off)[:, None]
    pts = shapely.points(cen[:, 0], cen[:, 1])
    d = shapely.distance(R.line, pts)
    keep = np.nonzero((d >= CORRIDOR) & (d < radius))[0]
    counts = np.diff(off)[keep]
    idx = np.concatenate([np.arange(off[k], off[k + 1]) for k in keep])
    sub = {"bxy": xy[idx], "boff": np.concatenate([[0], np.cumsum(counts)]), "blevels": lv[keep]}
    build_ktm.buildings(sub, G, build_ktm.mat("MAT-far_buildings", (0.6, 0.6, 0.6), rough=0.85, attr="col"))
    print("far buildings:", len(keep), flush=True)


# --- street furniture -----------------------------------------------------------------------

def build_props(R, rng, GN):
    poles, lights = Batch(), Batch()
    lamp_glow = mat_flat("MAT-lamp_head", (0.9, 0.9, 0.85), 0.3)
    wires = bpy.data.curves.new("CRV-wires", "CURVE")
    wires.dimensions = "3D"
    wires.bevel_depth = 0.012
    wires.bevel_resolution = 1
    pole_pts = []
    for sgn in (1, -1):
        last = None
        for s in np.arange(10 + (17 if sgn < 0 else 0), R.s[-1] - 10, 36.0):
            p, t, n, z = R.at(s)
            q = p + n * sgn * (EDGE + FOOT - 0.4)
            gz = z + 0.2
            poles.box((q[0], q[1], gz + 4.6), ((1, 0, 0), (0, 1, 0), (0, 0, 1)), (0.12, 0.12, 4.6), (0.42, 0.41, 0.39))
            arm_dir = np.array([n[0], n[1], 0]) * sgn
            tt = np.array([t[0], t[1], 0])
            poles.box((q[0], q[1], gz + 8.6), (tt, arm_dir, (0, 0, 1)), (0.9, 0.06, 0.05), (0.2, 0.2, 0.2))
            # transformer on every fifth pole
            if rng.random() < 0.2:
                poles.box((q[0] - arm_dir[0] * 0.5, q[1] - arm_dir[1] * 0.5, gz + 6.2), (tt, arm_dir, (0, 0, 1)),
                          (0.35, 0.3, 0.45), (0.25, 0.28, 0.27))
            tops = [np.array([q[0], q[1], gz + 8.65]) + tt * o for o in (-0.8, -0.3, 0.3, 0.8)]
            if last is not None:
                for a, b in zip(last, tops):
                    for drop in (0.0, 0.25):           # bundled cables: two runs per position
                        sp = wires.splines.new("POLY")
                        pts = []
                        for f in np.linspace(0, 1, 9):
                            c = a * (1 - f) + b * f
                            c[2] -= (0.9 + drop) * 4 * f * (1 - f) + drop
                            pts.append(c)
                        sp.points.add(len(pts) - 1)
                        for pt, c in zip(sp.points, pts):
                            pt.co = (*c, 1)
            last = tops
            pole_pts.append(q)
    wob = bpy.data.objects.new("GEO-wires", wires)
    bpy.context.scene.collection.objects.link(wob)
    wob.data.materials.append(mat_flat("MAT-wire", (0.01, 0.01, 0.01), 0.5))
    poles.build("GEO-poles", mat_attr("MAT-pole", 0.8))
    # double-arm street lights on the median
    for s in np.arange(20, R.s[-1] - 10, 32.0):
        p, t, n, z = R.at(s)
        z0 = z + 0.25
        lights.cylinder(p[0], p[1], z0, 0.09, 10.0, (0.5, 0.5, 0.5), 8)
        for sgn in (1, -1):
            nn = np.array([n[0], n[1], 0]) * sgn
            lights.box(np.array([p[0], p[1], z0 + 9.9]) + nn * 1.0, (nn, (t[0], t[1], 0), (0, 0, 1)), (1.0, 0.04, 0.04), (0.5, 0.5, 0.5))
            lights.box(np.array([p[0], p[1], z0 + 9.82]) + nn * 1.9, (nn, (t[0], t[1], 0), (0, 0, 1)), (0.35, 0.14, 0.06), (0.85, 0.85, 0.8))
    lights.build("GEO-street_lights", mat_attr("MAT-light_pole", 0.5))
    # roadside trees (bottle-brush and broadleaf) on the outer verges, in clusters
    tree_batch = Batch()
    for sgn in (1, -1):
        for s in np.arange(5, R.s[-1], 7.0):
            if rng.random() > 0.35:
                continue
            p, t, n, z = R.at(s + rng.uniform(-2, 2))
            q = p + n * sgn * (EDGE + FOOT + rng.uniform(1.0, 3.0))
            if any(np.hypot(*(q - pp)) < 3 for pp in pole_pts[-200:]):
                continue
            gz = float(GN.z(q[0], q[1])[0])
            h = rng.uniform(4.5, 8.5)
            tree_batch.cylinder(q[0], q[1], gz, 0.14, h * 0.55, (0.2, 0.14, 0.09), 6)
            green = tuple(np.array([0.05, 0.13, 0.03]) * rng.uniform(0.8, 1.4))
            for k in range(3):
                r = rng.uniform(1.0, 1.9) * h / 7
                c = np.array([q[0] + rng.uniform(-0.8, 0.8), q[1] + rng.uniform(-0.8, 0.8), gz + h * (0.55 + 0.15 * k)])
                tree_batch.box(c, ((1, 0, 0), (0, 1, 0), (0, 0, 1)), (r, r, r * 0.8), green)
    tob = tree_batch.build("GEO-trees", mat_attr("MAT-tree", 0.9))
    sub = tob.modifiers.new("round", "SUBSURF"); sub.levels = 2; sub.render_levels = 2


# --- buses -------------------------------------------------------------------------------

def place_bus(glb, R, s, lateral, reverse=False):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=glb)
    new = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new("BUS-" + os.path.basename(glb), None)
    bpy.context.scene.collection.objects.link(root)
    for o in new:
        if o.name.startswith("COL-"):
            o.hide_render = True
        if o.parent is None:
            o.parent = root
    p, t, n, z = R.at(s)
    d = -t if reverse else t
    q = p + n * lateral
    root.location = (q[0], q[1], z)
    root.rotation_euler = (0, 0, math.atan2(d[0], -d[1]))
    return root


# --- scene, cameras ------------------------------------------------------------------------

def sky(sun_elev=52, sun_az=150):
    world = bpy.data.worlds.new("WORLD-sky")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    tex = nt.nodes.new("ShaderNodeTexSky")
    for ty in ("MULTIPLE_SCATTERING", "NISHITA", "SINGLE_SCATTERING", "PREETHAM"):
        try:
            tex.sky_type = ty
            break
        except TypeError:
            continue
    try:
        tex.sun_elevation = math.radians(sun_elev)
        tex.sun_rotation = math.radians(sun_az)
        tex.altitude = 1300
        tex.air_density = 1.4
        tex.aerosol_density = 1.6
    except AttributeError:
        pass
    nt.links.new(tex.outputs["Color"], nt.nodes["Background"].inputs["Color"])
    nt.nodes["Background"].inputs["Strength"].default_value = float(os.environ.get("SKY", 0.03))
    sun = bpy.data.lights.new("LGT-sun", "SUN")
    sun.energy = float(os.environ.get("SUN", 5.0)); sun.angle = math.radians(0.8); sun.color = (1.0, 0.96, 0.9)
    so = bpy.data.objects.new("LGT-sun", sun)
    bpy.context.scene.collection.objects.link(so)
    so.rotation_euler = (math.radians(90 - sun_elev), 0, math.radians(sun_az + 90))


def shot(path, eye, look, lens, res, samples):
    from mathutils import Vector
    cam = bpy.data.objects.get("CAM-street")
    if cam is None:
        cam = bpy.data.objects.new("CAM-street", bpy.data.cameras.new("CAM-street"))
        bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    cam.data.lens = lens
    cam.data.clip_start, cam.data.clip_end = 0.1, 8000
    cam.location = Vector(eye)
    cam.rotation_euler = (Vector(look) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    s = render.setup_cycles(samples=samples, res=res)
    s.view_settings.exposure = float(os.environ.get("EXPO", 0.0))
    s.view_settings.look = "AgX - High Contrast"
    s.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("render:", path, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--shots", default="all")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    os.makedirs(OUTDIR, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rng = np.random.default_rng(7)
    npz = np.load(os.path.join(DATA, "prep.npz"))
    meta = json.load(open(os.path.join(DATA, "prep.json")))
    G = Ground(npz, meta)
    R = Road(G, meta)
    print(f"road: {R.s[-1]:.0f} m, bridge {R.bridge[0]:.0f}-{R.bridge[1]:.0f} m, z {R.z.min():.1f}-{R.z.max():.1f}", flush=True)
    rivers = [LineString(rv["pts"]) for rv in meta["rivers"] if len(rv["pts"]) > 1
              and LineString(rv["pts"]).distance(R.line) < 40]
    GN = GroundNear(G, R, rivers)
    build_road(R)
    sat = os.path.join(DATA, "sentinel2.jpg")
    build_ground(GN, meta, R, sat)
    water = mat_flat("MAT-river_water", (0.06, 0.08, 0.06), 0.08)
    for rv in rivers:
        p = resample(np.asarray(rv.coords), 2.0)
        if len(p) < 2:
            continue
        zz = GN.z(p[:, 0], p[:, 1]) + 0.6
        t = np.gradient(p, axis=0); t /= np.linalg.norm(t, axis=1)[:, None]
        nn = np.stack([-t[:, 1], t[:, 0]], 1)
        a, b = p + nn * 5, p - nn * 5
        verts = [v for i in range(len(p)) for v in ((*a[i], zz[i]), (*b[i], zz[i]))]
        faces = [(2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1) for i in range(len(p) - 1)]
        mesh_obj("GEO-river", verts, faces, water)
    signs = build_buildings(npz, GN, R, rng)
    far_field(npz, meta, G, R)
    build_props(R, rng, GN)

    # cameras: street-level spots matching the Mapillary photos, plus hero shots
    photos = json.load(open(os.path.join(DATA, "mapillary", "index.json")))
    spots = []
    for ph in photos:
        x = (ph["lon"] - meta["lon0"]) * meta["kx"]; y = (ph["lat"] - meta["lat0"]) * meta["ky"]
        sa = R.line.project(shapely.Point(x, y)); dd = R.line.distance(shapely.Point(x, y))
        if dd < 40 and 30 < sa < R.s[-1] - 30 and ph["heading"] is not None:
            spots.append((ph, x, y, sa))
    hero_s = R.s[-1] * 0.42
    sign_text(signs, rng, [(x, y) for _, x, y, _ in spots] + [tuple(R.at(hero_s)[0])])
    base = os.path.join(ROOT, "output")
    place_bus(os.path.join(base, "agni_bus", "agni_bus.glb"), R, hero_s + 26, S1 + SHOULDER + LANE * 1.5)
    place_bus(os.path.join(base, "sajha_bus", "sajha_bus.glb"), R, hero_s + 75, -(S1 + SHOULDER + LANE * 0.5), reverse=True)
    sky()

    fast = args.fast
    S = 20 if fast else 64
    RES = (1000, 625) if fast else (1600, 1000)
    shots = {}
    p, t, n, z = R.at(hero_s)
    eye = p + n * (EDGE + 1.2) + t * 5
    shots["hero_buses"] = (np.array([eye[0], eye[1], z + 1.7]), np.r_[p + t * 40 + n * 2, z + 2.5], 24)
    p2, t2, n2, z2 = R.at(R.s[-1] * 0.5)
    shots["aerial"] = (np.r_[p2 - n2 * 260 - t2 * 260, z2 + 190], np.r_[p2 + t2 * 120, z2], 28)
    pb, tb, nb, zb = R.at(sum(R.bridge) / 2)
    shots["balkhu_bridge"] = (np.r_[pb - nb * 40 - tb * 35, zb + 2.0], np.r_[pb + tb * 10, zb - 1.0], 24)
    matches = []
    for ph, x, y, sa in spots[:10]:
        h = math.radians(ph["heading"])
        zg = float(np.interp(sa, R.s, R.z))
        q, _, nq, _ = R.at(sa)
        side = 1 if np.dot([x - q[0], y - q[1]], nq) > 0 else -1
        lat = side * (S1 + SHOULDER + LANE)          # middle of the outer carriageway (GPS is +-10 m)
        e = np.array([q[0] + nq[0] * lat, q[1] + nq[1] * lat, zg + 1.6])
        tgt = e + np.array([math.sin(h), math.cos(h), -0.04]) * 30
        nm = f"photo_{ph['i']:03d}"
        shots[nm] = (e, tgt, 16)
        matches.append((nm, ph))
    want = shots if args.shots == "all" else {k: v for k, v in shots.items() if k in args.shots.split(",")}
    for nm, (e, tg, lens) in want.items():
        shot(os.path.join(OUTDIR, nm + ".png"), tuple(e), tuple(tg), lens, RES, S)
    # side-by-side: Mapillary photo | our render
    from PIL import Image, ImageDraw
    rows = [(nm, ph) for nm, ph in matches if os.path.exists(os.path.join(OUTDIR, nm + ".png"))]
    if rows:
        W = 800
        sheet = Image.new("RGB", (2 * W, 0 + len(rows) * 500), (15, 15, 16))
        dr = ImageDraw.Draw(sheet)
        for r, (nm, ph) in enumerate(rows):
            a = Image.open(os.path.join(DATA, "mapillary", ph["file"])).convert("RGB")
            b = Image.open(os.path.join(OUTDIR, nm + ".png")).convert("RGB")
            for c, im in enumerate((a, b)):
                im = im.resize((W, int(im.height * W / im.width)))
                im = im.crop((0, max(0, (im.height - 500) // 2), W, max(0, (im.height - 500) // 2) + 500))
                sheet.paste(im, (c * W, r * 500))
            date = datetime.datetime.fromtimestamp(ph["date"] / 1000).strftime("%Y-%m")
            dr.text((10, r * 500 + 8), f"Mapillary #{ph['i']} {date} @{ph['author']}", fill=(255, 230, 150))
            dr.text((W + 10, r * 500 + 8), "3D rebuild (open data)", fill=(255, 230, 150))
        sheet.save(os.path.join(OUTDIR, "compare_photos.jpg"), quality=88)
    if not fast:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUTDIR, "ktm_street.blend"), compress=True)


if __name__ == "__main__":
    main()
