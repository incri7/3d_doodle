"""Centreline of the whole Kathmandu Ring Road loop (28 km) from OpenStreetMap.

The Ring Road ways (relation 4659866 plus every way tagged ref=NH39) are
buffered and merged into one ring-shaped polygon; the centreline runs halfway
between its outer edge and its hole, smoothed and resampled every 2 m.
"""
import json, os

import numpy as np
import shapely
from shapely.geometry import LineString

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "ktm")


def resample(p, step, closed=True):
    if closed:
        p = np.vstack([p, p[:1]])
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    t = np.arange(0, s[-1] - (step * 0.5 if closed else 0), step)
    return np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], 1)


def smooth_closed(a, r):
    k = np.ones(2 * r + 1) / (2 * r + 1)
    pad = np.vstack([a[-r:], a, a[:r]])
    return np.stack([np.convolve(pad[:, j], k, mode="valid") for j in range(a.shape[1])], 1)


def ring_lines(meta):
    rr = json.load(open(os.path.join(DATA, "ringroad.json")))["elements"]
    ids = {e["id"] for e in rr if e["type"] == "way"}
    out = []
    for e in json.load(open(os.path.join(DATA, "roads.json")))["elements"]:
        t = e.get("tags", {})
        if (e["id"] in ids or t.get("ref") == "NH39") and "geometry" in e:
            g = e["geometry"]
            xy = [((q["lon"] - meta["lon0"]) * meta["kx"], (q["lat"] - meta["lat0"]) * meta["ky"]) for q in g]
            out.append((e, LineString(xy)))
    return out


def centreline(meta, step=2.0):
    """Closed loop, counter-clockwise, as an (n, 2) array (no repeated end point)."""
    lines = ring_lines(meta)
    u = shapely.union_all([l.buffer(18) for _, l in lines])
    hole = max(u.interiors, key=lambda r: r.length)
    ext = LineString(u.exterior.coords)
    H = resample(np.asarray(hole.coords)[:-1], step)
    q = np.array([ext.interpolate(ext.project(shapely.Point(p))).coords[0] for p in H])
    c = smooth_closed((H + q) / 2, 12)
    c = smooth_closed(resample(c, step), 8)
    c = resample(c, step)
    if not shapely.LinearRing(c).is_ccw:
        c = c[::-1]
    return c, lines
