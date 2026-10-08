"""Merge the downloaded sources into one local, metric dataset for Blender.

Inputs (data/ktm/, from the fetch_*.py scripts):
  ringroad.json, roads.json, areas.json, buildings_*.json   OpenStreetMap (ODbL)
  open_buildings.json                                       Google Open Buildings v3 (CC BY 4.0)
  dem.tif                                                   Copernicus GLO-30 DSM
  sentinel2.tif                                             Sentinel-2 L2A true colour

Output: data/ktm/prep.npz + prep.json. Coordinates are metres east (x) and
north (y) of the area centre; z is metres above the lowest ground.
"""
import glob, hashlib, json, math, os

import numpy as np
import rasterio
import shapely
from shapely.geometry import Polygon

from fetch_osm import BBOX, OUT

LAT0 = (BBOX[0] + BBOX[2]) / 2
LON0 = (BBOX[1] + BBOX[3]) / 2
KX = 111320.0 * math.cos(math.radians(LAT0))   # metres per degree of longitude
KY = 110574.0                                    # metres per degree of latitude

# carriageway width (m) by OSM road class when lanes aren't tagged
ROAD_W = {"motorway": 14, "trunk": 14, "primary": 11, "secondary": 9, "tertiary": 7.5,
          "unclassified": 6, "residential": 5.5, "living_street": 4.5, "service": 4,
          "trunk_link": 7, "primary_link": 7, "secondary_link": 6, "tertiary_link": 6,
          "track": 3.5, "pedestrian": 4}
RIVER_W = {"river": 28, "stream": 8, "canal": 6, "drain": 3, "ditch": 2}


def xy(lon, lat):
    return (np.asarray(lon) - LON0) * KX, (np.asarray(lat) - LAT0) * KY


def smooth(z, sigma):
    """Separable gaussian blur (edge-padded)."""
    r = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    p = np.pad(z, r, mode="edge")
    p = np.apply_along_axis(lambda v: np.convolve(v, k, mode="valid"), 1, p)
    return np.apply_along_axis(lambda v: np.convolve(v, k, mode="valid"), 0, p)


def ground():
    with rasterio.open(f"{OUT}/dem.tif") as src:
        z = src.read(1).astype(np.float64)
        t = src.transform
    # Copernicus is a surface model (roofs, trees): blur the city's roofs
    # away but keep the valley's shape.
    g = smooth(z, 3.0)
    h, w = g.shape
    lon = t.c + (np.arange(w) + 0.5) * t.a
    lat = t.f + (np.arange(h) + 0.5) * t.e
    return g, lon, lat


def levels_for(key, area):
    """Kathmandu houses: mostly 3-5 storeys; sheds 1-2; big blocks 3-4."""
    hv = int(hashlib.md5(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    if area < 25:
        return 1 + (hv > 0.6)
    if area > 900:
        return 3 + (hv > 0.5)
    for lv, cum in ((2, 0.1), (3, 0.38), (4, 0.7), (5, 0.9), (6, 1.0)):
        if hv <= cum:
            return lv
    return 4


def parse_levels(tags):
    for k in ("height", "building:height"):
        try:
            return float(str(tags[k]).split()[0]) / 2.9
        except (KeyError, ValueError):
            pass
    try:
        return float(tags["building:levels"])
    except (KeyError, ValueError):
        return None


def main():
    g, glon, glat = ground()
    zmin = float(g.min())

    # --- roads -------------------------------------------------------------------
    ring_ids = {e["id"] for e in json.load(open(f"{OUT}/ringroad.json"))["elements"] if e["type"] == "way"}
    roads = []
    for e in json.load(open(f"{OUT}/roads.json"))["elements"]:
        t = e.get("tags", {})
        cls = t.get("highway")
        if cls not in ROAD_W or "geometry" not in e:
            continue
        lanes = t.get("lanes")
        try:
            width = float(lanes) * 3.5 + 1.0
        except (TypeError, ValueError):
            width = ROAD_W[cls]
        if t.get("oneway") == "yes" and cls in ("trunk", "primary") and not lanes:
            width = 8.0
        x, y = xy([p["lon"] for p in e["geometry"]], [p["lat"] for p in e["geometry"]])
        roads.append({"id": e["id"], "cls": cls, "w": round(width, 2), "ring": e["id"] in ring_ids,
                      "bridge": t.get("bridge") == "yes", "name": t.get("name", ""),
                      "pts": np.round(np.stack([x, y], 1), 2).tolist()})

    # --- water and green ------------------------------------------------------------
    rivers, lakes, greens = [], [], []
    for e in json.load(open(f"{OUT}/areas.json"))["elements"]:
        t = e.get("tags", {})
        if "geometry" not in e:
            continue
        x, y = xy([p["lon"] for p in e["geometry"]], [p["lat"] for p in e["geometry"]])
        pts = np.round(np.stack([x, y], 1), 2).tolist()
        if t.get("waterway") in RIVER_W:
            rivers.append({"w": RIVER_W[t["waterway"]], "name": t.get("name", ""), "pts": pts})
        elif t.get("natural") == "water" and len(pts) > 3:
            lakes.append(pts)
        elif (t.get("leisure") in ("park", "garden", "golf_course") or t.get("natural") in ("wood", "scrub", "grassland")
              or t.get("landuse") in ("forest", "grass", "meadow", "recreation_ground")) and len(pts) > 3:
            greens.append(pts)

    # --- buildings: OpenStreetMap first, Google Open Buildings fills the gaps -----------
    polys, heights, src, seen = [], [], [], set()
    for f in sorted(glob.glob(f"{OUT}/buildings_*.json")):
        for e in json.load(open(f))["elements"]:
            # buildings on a tile border come back in both tiles
            if "geometry" not in e or len(e["geometry"]) < 4 or e["id"] in seen:
                continue
            seen.add(e["id"])
            x, y = xy([p["lon"] for p in e["geometry"]], [p["lat"] for p in e["geometry"]])
            p = Polygon(np.stack([x, y], 1))
            if not p.is_valid or p.area < 6:
                continue
            lv = parse_levels(e.get("tags", {}))
            polys.append(p)
            # tallest real buildings here are ~20 storeys; bad tags get capped
            heights.append(min(lv, 20) if lv else levels_for(f"osm{e['id']}", p.area))
            src.append(0)
    n_osm = len(polys)
    osm_tree = shapely.STRtree(polys)
    ob = [b for b in json.load(open(f"{OUT}/open_buildings.json")) if b["conf"] >= 0.70]
    geoms = shapely.from_wkt([b["wkt"] for b in ob])
    # project lon/lat -> local metres
    coords = shapely.get_coordinates(geoms)
    cx, cy = xy(coords[:, 0], coords[:, 1])
    geoms = shapely.set_coordinates(geoms, np.stack([cx, cy], 1))
    hit = osm_tree.query(geoms, predicate="intersects")
    covered = np.zeros(len(geoms), bool)
    covered[hit[0]] = True
    for i in np.nonzero(~covered)[0]:
        p = geoms[i]
        if p.geom_type != "Polygon" or p.area < 6:
            continue
        polys.append(p)
        heights.append(levels_for(f"gob{i}", p.area))
        src.append(1)
    print(f"buildings: {n_osm} OpenStreetMap + {len(polys) - n_osm} Google Open Buildings = {len(polys)}")

    # flatten outer rings (drop the closing point) for Blender
    rings = [np.asarray(p.exterior.coords)[:-1] for p in polys]
    # counter-clockwise outer rings so tops face up
    rings = [r if Polygon(r).exterior.is_ccw else r[::-1] for r in rings]
    off = np.cumsum([0] + [len(r) for r in rings])
    flat = np.concatenate(rings).astype(np.float32)
    lv = np.asarray(heights, np.float32)

    np.savez_compressed(f"{OUT}/prep.npz", ground=g.astype(np.float32), glon=glon, glat=glat,
                        bxy=flat, boff=off.astype(np.int64), blevels=lv, bsrc=np.asarray(src, np.uint8))
    json.dump({"lat0": LAT0, "lon0": LON0, "kx": KX, "ky": KY, "zmin": zmin, "roads": roads,
               "rivers": rivers, "lakes": lakes, "greens": greens}, open(f"{OUT}/prep.json", "w"))
    print(f"roads {len(roads)} (ring road ways {sum(r['ring'] for r in roads)}), rivers {len(rivers)}, "
          f"lakes {len(lakes)}, green areas {len(greens)}")
    print(f"ground {g.shape}, {zmin:.0f}-{g.max():.0f} m")


if __name__ == "__main__":
    main()
