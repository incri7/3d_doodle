"""Build the Kathmandu Ring Road area in Blender from data/ktm/prep.* and
render overview and close-up shots to output/ktm_ringroad/.

  .venv/bin/python world/build_ktm.py            # full quality
  .venv/bin/python world/build_ktm.py --fast     # quick look
"""
import argparse, json, math, os, sys

import bpy
import numpy as np
from mathutils import Vector

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from doodle import render  # noqa: E402

DATA = os.path.join(ROOT, "data", "ktm")
OUTDIR = os.path.join(ROOT, "output", "ktm_ringroad")

# Kathmandu house colours (linear): concrete, cream, white, brick, pastel paints.
WALLS = [((0.42, 0.41, 0.39), 18), ((0.62, 0.52, 0.36), 14), ((0.7, 0.7, 0.66), 9),
         ((0.33, 0.1, 0.06), 24), ((0.68, 0.36, 0.34), 7), ((0.33, 0.48, 0.62), 6),
         ((0.74, 0.58, 0.18), 6), ((0.66, 0.3, 0.12), 6), ((0.4, 0.55, 0.36), 4),
         ((0.55, 0.42, 0.55), 3), ((0.2, 0.3, 0.45), 2)]


class Ground:
    """Bilinear lookup in the smoothed elevation grid (local metres)."""

    def __init__(self, npz, meta):
        self.g = npz["ground"].astype(np.float64) - meta["zmin"]
        lon, lat = npz["glon"], npz["glat"]
        self.x = (lon - meta["lon0"]) * meta["kx"]
        self.y = (lat - meta["lat0"]) * meta["ky"]          # descending (north first)

    def z(self, x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        fx = np.clip((x - self.x[0]) / (self.x[1] - self.x[0]), 0, len(self.x) - 1.001)
        fy = np.clip((y - self.y[0]) / (self.y[1] - self.y[0]), 0, len(self.y) - 1.001)
        i, j = fy.astype(int), fx.astype(int)
        ty, tx = fy - i, fx - j
        g = self.g
        return ((g[i, j] * (1 - tx) + g[i, j + 1] * tx) * (1 - ty)
                + (g[i + 1, j] * (1 - tx) + g[i + 1, j + 1] * tx) * ty)


def mat(name, color, rough=0.8, attr=None, image=None, emission=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = rough
    if attr:
        a = nt.nodes.new("ShaderNodeAttribute")
        a.attribute_name = attr
        a.attribute_type = "GEOMETRY"
        nt.links.new(a.outputs["Color"], bsdf.inputs["Base Color"])
    if image:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(image)
        tex.interpolation = "Cubic"
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = 1.0
    return m


def mesh_obj(name, verts, faces, material=None, colors=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate(clean_customdata=False)
    if colors is not None:
        attr = me.color_attributes.new("col", "FLOAT_COLOR", "CORNER")
        attr.data.foreach_set("color", colors)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if material:
        ob.data.materials.append(material)
    return ob


# --- terrain -------------------------------------------------------------------------

def terrain(G, meta, npz, step=1):
    g = G.g[::step, ::step]
    xs, ys = G.x[::step], G.y[::step]
    h, w = g.shape
    X, Y = np.meshgrid(xs, ys)
    verts = np.stack([X, Y, g], -1).reshape(-1, 3)
    i = np.arange(h - 1)[:, None] * w + np.arange(w - 1)[None, :]
    faces = np.stack([i, i + w, i + w + 1, i + 1], -1).reshape(-1, 4)
    ob = mesh_obj("GEO-terrain", verts.tolist(), faces.tolist())
    # UVs from the Sentinel-2 image bounds (lon/lat)
    import rasterio
    with rasterio.open(os.path.join(DATA, "sentinel2.tif")) as src:
        b = src.bounds
    lon = verts[:, 0] / meta["kx"] + meta["lon0"]
    lat = verts[:, 1] / meta["ky"] + meta["lat0"]
    u = (lon - b.left) / (b.right - b.left)
    v = (lat - b.bottom) / (b.top - b.bottom)
    me = ob.data
    uv = me.uv_layers.new(name="UVMap")
    loop_v = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", loop_v)
    uv.data.foreach_set("uv", np.stack([u[loop_v], v[loop_v]], 1).ravel())
    for p in me.polygons:
        p.use_smooth = True
    img = os.path.join(DATA, "sentinel2.jpg")
    if not os.path.exists(img):
        from PIL import Image
        with rasterio.open(os.path.join(DATA, "sentinel2.tif")) as src:
            a = np.moveaxis(src.read(), 0, -1).astype(np.float32)
        # Sentinel-2 TCI is dull and hazy: stretch it like a print
        lo, hi = np.percentile(a, 0.5), np.percentile(a, 99.7)
        a = np.clip((a - lo) / (hi - lo), 0, 1) ** 0.9
        Image.fromarray((a * 255).astype(np.uint8)).save(img, quality=92)
    ob.data.materials.append(mat("MAT-satellite", (0.5, 0.5, 0.5), rough=0.95, image=img))
    return ob


# --- ribbons (roads, rivers) ---------------------------------------------------------------

def ribbons(name, lines, G, material, lift=0.3, colors=None):
    """Flat strips along polylines: lines = [(pts[n,2], width)]. Draped on the
    ground with a small lift."""
    verts, faces, cols = [], [], []
    for k, (pts, width) in enumerate(lines):
        p = np.asarray(pts, float)
        if len(p) < 2:
            continue
        d = np.diff(p, axis=0)
        L = np.linalg.norm(d, axis=1)
        keep = np.concatenate([[True], L > 0.05])
        p = p[keep]
        if len(p) < 2:
            continue
        d = np.diff(p, axis=0)
        d /= np.linalg.norm(d, axis=1)[:, None]
        n = np.stack([-d[:, 1], d[:, 0]], 1)
        # vertex normals = average of the adjacent segments (mitred, clamped)
        vn = np.vstack([n[:1], n[:-1] + n[1:], n[-1:]])
        vn /= np.maximum(np.linalg.norm(vn, axis=1), 1e-6)[:, None]
        cosv = np.vstack([[1.0], np.sum(n[:-1] * vn[1:-1], 1)[:, None] if len(n) > 1 else np.zeros((0, 1)), [1.0]])
        scale = np.clip(1.0 / np.maximum(cosv, 0.35), 1, 2.5)
        off = vn * (width / 2) * scale
        a, b = p + off, p - off
        z = G.z(p[:, 0], p[:, 1]) + lift
        base = len(verts)
        for q in range(len(p)):
            verts.append((a[q, 0], a[q, 1], z[q]))
            verts.append((b[q, 0], b[q, 1], z[q]))
        for q in range(len(p) - 1):
            i0 = base + 2 * q
            faces.append((i0, i0 + 1, i0 + 3, i0 + 2))
            if colors is not None:
                cols.extend([colors[k]] * 4)
    flat = np.asarray(cols, np.float32).ravel() if colors is not None else None
    return mesh_obj(name, verts, faces, material, flat)


def polygons_flat(name, polys, G, material, lift=0.2):
    from shapely.geometry import Polygon
    verts, faces = [], []
    for pts in polys:
        r = np.asarray(pts, float)
        if len(r) > 3 and np.allclose(r[0], r[-1]):
            r = r[:-1]
        if len(r) < 3 or Polygon(r).area < 20:
            continue
        if not Polygon(r).exterior.is_ccw:
            r = r[::-1]
        z = G.z(r[:, 0], r[:, 1]).mean() + lift
        base = len(verts)
        verts += [(x, y, z) for x, y in r]
        faces.append(tuple(range(base, base + len(r))))
    return mesh_obj(name, verts, faces, material)


# --- buildings ------------------------------------------------------------------------

def buildings(npz, G, material):
    xy, off, lv = npz["bxy"].astype(np.float64), npz["boff"], npz["blevels"]
    n = len(lv)
    counts = np.diff(off)
    # colours: hashed per building, weighted palette; roofs are grey concrete
    rng = np.random.default_rng(42)
    pal = np.array([c for c, _ in WALLS])
    wts = np.array([w for _, w in WALLS], float)
    wall_idx = rng.choice(len(pal), size=n, p=wts / wts.sum())
    shade = rng.uniform(0.82, 1.12, n)
    wall_col = np.clip(pal[wall_idx] * shade[:, None], 0, 1)
    roof_col = np.clip(np.array([0.36, 0.35, 0.33])[None, :] * rng.uniform(0.75, 1.2, n)[:, None], 0, 1)
    # base height: lowest ground under the footprint (so nothing floats)
    gz = G.z(xy[:, 0], xy[:, 1])
    base = np.minimum.reduceat(gz, off[:-1]) - 0.3
    top = base + lv * 2.9 + 0.6
    nv = 2 * len(xy)
    verts = np.empty((nv, 3))
    bi = np.repeat(np.arange(n), counts)
    verts[0::2, :2] = xy
    verts[0::2, 2] = base[bi]
    verts[1::2, :2] = xy
    verts[1::2, 2] = top[bi]
    faces, cols = [], []
    for k in range(n):
        s, c = off[k], counts[k]
        idx = np.arange(s, s + c)
        nxt = np.roll(idx, -1)
        # walls
        for a, b in zip(idx, nxt):
            faces.append((2 * a, 2 * b, 2 * b + 1, 2 * a + 1))
        cols.append(np.repeat(wall_col[k][None, :], 4 * c, 0))
        # roof (n-gon)
        faces.append(tuple(2 * idx + 1))
        cols.append(np.repeat(roof_col[k][None, :], c, 0))
    col = np.concatenate(cols)
    col = np.concatenate([col, np.ones((len(col), 1))], 1).astype(np.float32).ravel()
    return mesh_obj("GEO-buildings", verts.tolist(), faces, material, col)


# --- scene ---------------------------------------------------------------------------------

def sky(sun_elev=38, sun_az=135):
    world = bpy.data.worlds.new("WORLD-sky")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    sky_tex = nt.nodes.new("ShaderNodeTexSky")
    for t in ("NISHITA", "MULTIPLE_SCATTERING", "SINGLE_SCATTERING", "PREETHAM"):
        try:
            sky_tex.sky_type = t
            break
        except TypeError:
            continue
    try:
        sky_tex.sun_elevation = math.radians(sun_elev)
        sky_tex.sun_rotation = math.radians(sun_az)
        sky_tex.altitude = 1400
        sky_tex.air_density = 2.5          # Kathmandu haze
        sky_tex.aerosol_density = 3.0
    except AttributeError:
        pass
    nt.links.new(sky_tex.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.12
    sun = bpy.data.lights.new("LGT-sun", "SUN")
    sun.energy = 2.6
    sun.angle = math.radians(1.0)
    sun.color = (1.0, 0.95, 0.88)
    so = bpy.data.objects.new("LGT-sun", sun)
    bpy.context.scene.collection.objects.link(so)
    so.rotation_euler = (math.radians(90 - sun_elev), 0, math.radians(sun_az + 90))


def shot(name, eye, target, lens=35, ortho=None, res=(1600, 1000), samples=64):
    cam = bpy.data.objects.get("CAM-main")
    if cam is None:
        cam = bpy.data.objects.new("CAM-main", bpy.data.cameras.new("CAM-main"))
        bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    cam.data.clip_start, cam.data.clip_end = 5, 60000
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = ortho
    else:
        cam.data.type = "PERSP"
        cam.data.lens = lens
    cam.location = Vector(eye)
    cam.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    s = render.setup_cycles(samples=samples, res=res)
    s.view_settings.exposure = -0.6
    s.view_settings.look = "AgX - Base Contrast"
    hl = bpy.data.objects.get("GEO-ring_highlight")
    if hl:
        hl.hide_render = not ortho          # the loop highlight is for the map view only
    s.render.filepath = os.path.join(OUTDIR, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("render:", s.render.filepath, flush=True)


def place(meta, lat, lon):
    return ((lon - meta["lon0"]) * meta["kx"], (lat - meta["lat0"]) * meta["ky"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--shots", default="all")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    os.makedirs(OUTDIR, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)

    npz = np.load(os.path.join(DATA, "prep.npz"))
    meta = json.load(open(os.path.join(DATA, "prep.json")))
    G = Ground(npz, meta)

    terrain(G, meta, npz)
    asphalt = mat("MAT-asphalt", (0.075, 0.075, 0.08), rough=0.85)
    ring_mat = mat("MAT-ring_road", (0.045, 0.045, 0.05), rough=0.7)
    lane_mat = mat("MAT-ring_edge", (0.85, 0.62, 0.08), rough=0.5, emission=(0.4, 0.28, 0.02))
    water = mat("MAT-river", (0.08, 0.12, 0.1), rough=0.15)
    roads = meta["roads"]
    minor = [(r["pts"], r["w"]) for r in roads if not r["ring"]]
    ring = [(r["pts"], r["w"]) for r in roads if r["ring"]]
    ribbons("GEO-roads", minor, G, asphalt, lift=0.6)
    ribbons("GEO-ring_road", ring, G, ring_mat, lift=0.9)
    # yellow edge lines along each Ring Road carriageway (shows the loop from the air)
    edges = []
    for r in roads:
        if not r["ring"]:
            continue
        p = np.asarray(r["pts"], float)
        if len(p) < 2:
            continue
        d = np.gradient(p, axis=0)
        d /= np.maximum(np.linalg.norm(d, axis=1), 1e-6)[:, None]
        nrm = np.stack([-d[:, 1], d[:, 0]], 1)
        for sgn in (-1, 1):
            edges.append((p + sgn * nrm * (r["w"] / 2 - 0.4), 0.35))
    ribbons("GEO-ring_edges", edges, G, lane_mat, lift=1.0)
    glow = mat("MAT-ring_highlight", (1.0, 0.55, 0.05), rough=0.6, emission=(1.0, 0.45, 0.02))
    ribbons("GEO-ring_highlight", [(r["pts"], 34.0) for r in roads if r["ring"]], G, glow, lift=30.0)
    ribbons("GEO-rivers", [(r["pts"], r["w"]) for r in meta["rivers"]], G, water, lift=0.15)
    polygons_flat("GEO-lakes", meta["lakes"], G, water, lift=0.2)
    bmat = mat("MAT-buildings", (0.6, 0.6, 0.6), rough=0.85, attr="col")
    buildings(npz, G, bmat)
    sky()

    fast = args.fast
    S = 24 if fast else 96
    R = (1200, 750) if fast else (1920, 1200)
    z0 = lambda x, y: float(G.z(x, y))
    shots = {
        # whole loop from straight above
        "overview": dict(eye=(0, 0, 9000), target=(0, 0.01, 0), ortho=11800, res=(R[0], int(R[0] * 1.15))),
        # bird's-eye from the south-west over the valley toward Shivapuri
        "valley": dict(eye=(-6500, -9500, 2600), target=(800, 1500, 0), lens=30),
    }
    spots = {"kalanki": (27.6935, 85.2817), "koteshwor": (27.6787, 85.3494),
             "gongabu_buspark": (27.7353, 85.3134), "balkhu": (27.6838, 85.2961),
             "chabahil": (27.7176, 85.3466)}
    for nm, (la, lo) in spots.items():
        x, y = place(meta, la, lo)
        g = z0(x, y)
        shots[nm] = dict(eye=(x - 420, y - 520, g + 260), target=(x, y, g), lens=32)
    want = shots if args.shots == "all" else {k: shots[k] for k in args.shots.split(",")}
    for nm, sh in want.items():
        shot(nm, sh["eye"], sh["target"], lens=sh.get("lens", 35), ortho=sh.get("ortho"),
             res=sh.get("res", R), samples=S)
    if not fast:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUTDIR, "ktm_ringroad.blend"), compress=True)


if __name__ == "__main__":
    main()
