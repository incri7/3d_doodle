"""Copernicus GLO-30 elevation (30 m, ESA, free) for the Ring Road area,
read straight from the AWS open-data COG and saved as a small GeoTIFF."""
import os
import rasterio
from rasterio.windows import from_bounds

from fetch_osm import BBOX, OUT

URL = ("https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N27_00_E085_00_DEM/"
       "Copernicus_DSM_COG_10_N27_00_E085_00_DEM.tif")


def main():
    s, w, n, e = BBOX
    pad = 0.02
    with rasterio.open(URL) as src:
        win = from_bounds(w - pad, s - pad, e + pad, n + pad, src.transform)
        z = src.read(1, window=win)
        prof = src.profile.copy()
        prof.update(width=z.shape[1], height=z.shape[0], transform=src.window_transform(win),
                    driver="GTiff", compress="deflate", tiled=False)
        prof.pop("blockxsize", None); prof.pop("blockysize", None)
    os.makedirs(OUT, exist_ok=True)
    with rasterio.open(f"{OUT}/dem.tif", "w", **prof) as dst:
        dst.write(z, 1)
    print("dem", z.shape, "min", float(z.min()), "max", float(z.max()))


if __name__ == "__main__":
    main()
