"""Sentinel-2 true-colour image (10 m, ESA Copernicus, free) for the Ring
Road area: pick the clearest recent dry-season scene from the Element84
STAC catalogue and cut the area out of its 'visual' COG, reprojected to
lat/lon to line up with the DEM."""
import json, os, urllib.request
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.transform import from_bounds

from fetch_osm import BBOX, OUT



def search():
    """Clearest dry-season scenes (Oct-Mar) covering the area, least cloud first."""
    s, w, n, e = BBOX
    items, url = [], (f"https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items"
                      f"?bbox={w},{s},{e},{n}&datetime=2024-10-01T00:00:00Z/2026-09-30T00:00:00Z&limit=100")
    while url and len(items) < 600:
        page = json.load(urllib.request.urlopen(url, timeout=60))
        items += page["features"]
        url = next((l["href"] for l in page.get("links", []) if l.get("rel") == "next"), None)
    def dry(it):
        return int(it["properties"]["datetime"][5:7]) in (10, 11, 12, 1, 2, 3)
    items = [it for it in items if dry(it) and "visual" in it["assets"]
             and it["properties"].get("eo:cloud_cover", 100) < 2]
    # essentially cloud-free first, then the newest
    items.sort(key=lambda it: it["properties"]["datetime"], reverse=True)
    items.sort(key=lambda it: it["properties"].get("eo:cloud_cover", 100) > 0.01)
    return items


def main():
    s, w, n, e = BBOX
    pad = 0.02
    W, S, E, N = w - pad, s - pad, e + pad, n + pad
    width = int((E - W) * 111320 * np.cos(np.radians(27.7)) / 5)    # ~5 m pixels (upsampled from 10 m)
    height = int((N - S) * 111320 / 5)
    dst_t = from_bounds(W, S, E, N, width, height)
    for it in search():
        href = it["assets"]["visual"]["href"]
        out = np.zeros((3, height, width), np.uint8)
        # Range reads to this bucket fail through some proxies: fetch the whole
        # tile once (~270 MB) and read it locally.
        local = os.path.join(OUT, "cache", os.path.basename(os.path.dirname(href)) + "_TCI.tif")
        if not os.path.exists(local):
            os.makedirs(os.path.dirname(local), exist_ok=True)
            try:
                urllib.request.urlretrieve(href, local + ".part")
                os.replace(local + ".part", local)
            except Exception as err:
                print("skip", it["id"], err)
                continue
        try:
            with rasterio.open(local) as src:
                for b in range(3):
                    reproject(rasterio.band(src, b + 1), out[b], dst_transform=dst_t, dst_crs="EPSG:4326",
                              resampling=Resampling.cubic)
        except rasterio.errors.RasterioIOError as err:
            print("skip", it["id"], err)
            continue
        cover = (out.sum(0) > 0).mean()
        print(it["id"], it["properties"]["datetime"][:10], "cloud", it["properties"].get("eo:cloud_cover"), "coverage", round(cover, 3))
        if cover > 0.99:
            prof = dict(driver="GTiff", width=width, height=height, count=3, dtype="uint8", crs="EPSG:4326",
                        transform=dst_t, compress="deflate")
            with rasterio.open(f"{OUT}/sentinel2.tif", "w", **prof) as dst:
                dst.write(out)
            json.dump({"id": it["id"], "date": it["properties"]["datetime"]}, open(f"{OUT}/sentinel2.json", "w"))
            return
    raise SystemExit("no full-coverage scene")


if __name__ == "__main__":
    main()
