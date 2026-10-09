"""Traffic signals and bus stops on the Ring Road from OpenStreetMap
(highway=traffic_signals / crossing=traffic_signals, highway=bus_stop /
public_transport=platform nodes), read with the main OSM API in small boxes
along the loop (the Overpass mirrors were down).
Writes data/ktm/signals.json and data/ktm/bus_stops.json. OSM data ODbL."""
import json, os, time, urllib.request
import xml.etree.ElementTree as ET

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "ktm")
UA = {"User-Agent": "3d_doodle ring road map (github.com/incri7/3d_doodle)"}


def main():
    meta = json.load(open(os.path.join(DATA, "prep.json")))
    c = np.load(os.path.join(DATA, "loop.npy"))
    lon = c[:, 0] / meta["kx"] + meta["lon0"]
    lat = c[:, 1] / meta["ky"] + meta["lat0"]
    cache = os.path.join(DATA, "osmapi")
    os.makedirs(cache, exist_ok=True)
    found, stops = {}, {}
    for k in range(0, len(c), 150):                       # every 300 m, 600 m boxes
        p = os.path.join(cache, f"{k:05d}.xml")
        if not os.path.exists(p):
            bb = f"{lon[k] - 0.003:.5f},{lat[k] - 0.003:.5f},{lon[k] + 0.003:.5f},{lat[k] + 0.003:.5f}"
            for i in range(4):
                try:
                    raw = urllib.request.urlopen(urllib.request.Request(f"https://api.openstreetmap.org/api/0.6/map?bbox={bb}", headers=UA), timeout=120).read()
                    open(p, "wb").write(raw)
                    break
                except Exception as e:  # noqa: BLE001
                    print("  retry", k, e, flush=True)
                    time.sleep(5 * (i + 1))
            time.sleep(1)
        if not os.path.exists(p):
            continue
        for n in ET.parse(p).getroot().iter("node"):
            tags = {t.get("k"): t.get("v") for t in n.iter("tag")}
            if tags.get("highway") == "traffic_signals" or tags.get("crossing") == "traffic_signals":
                found[n.get("id")] = {"id": n.get("id"), "lat": float(n.get("lat")), "lon": float(n.get("lon")),
                                      "src": "osm", "crossing": tags.get("highway") != "traffic_signals"}
            if tags.get("highway") == "bus_stop" or tags.get("public_transport") == "platform":
                stops[n.get("id")] = {"id": n.get("id"), "lat": float(n.get("lat")), "lon": float(n.get("lon")),
                                      "name": tags.get("name:en") or tags.get("name", "")}
        print(k, len(found), len(stops), flush=True)
    json.dump(list(found.values()), open(os.path.join(DATA, "signals.json"), "w"), indent=1)
    json.dump(list(stops.values()), open(os.path.join(DATA, "bus_stops.json"), "w"), indent=1, ensure_ascii=False)
    print(len(found), "signal nodes,", len(stops), "bus stops")


if __name__ == "__main__":
    main()
