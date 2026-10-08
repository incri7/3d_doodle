"""Google Open Buildings v3 (CC BY-4.0 / ODbL) footprints for the Ring Road
area: stream the S2 level-6 cell file and keep buildings inside the box."""
import csv, gzip, io, json, os, sys, urllib.request
import s2sphere

from fetch_osm import BBOX, OUT

BASE = "https://storage.googleapis.com/open-buildings-data/v3/polygons_s2_level_6_gzip_no_header/"


def main():
    s, w, n, e = BBOX
    token = s2sphere.CellId.from_lat_lng(s2sphere.LatLng.from_degrees((s + n) / 2, (w + e) / 2)).parent(6).to_token()
    local = os.path.join(OUT, "cache", f"{token}_buildings.csv.gz")
    if not os.path.exists(local):
        os.makedirs(os.path.dirname(local), exist_ok=True)
        urllib.request.urlretrieve(BASE + f"{token}_buildings.csv.gz", local + ".part")
        os.replace(local + ".part", local)
    csv.field_size_limit(sys.maxsize)
    keep = []
    with gzip.open(local, "rt") as f:
        for row in csv.reader(f):
            lat, lon = float(row[0]), float(row[1])
            if s <= lat <= n and w <= lon <= e:
                # latitude, longitude, area_in_meters, confidence, geometry (WKT), full_plus_code
                keep.append({"lat": lat, "lon": lon, "area": float(row[2]), "conf": float(row[3]), "wkt": row[4]})
    json.dump(keep, open(os.path.join(OUT, "open_buildings.json"), "w"))
    print("open buildings in box:", len(keep))


if __name__ == "__main__":
    main()
