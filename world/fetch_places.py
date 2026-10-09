"""Place names along the Ring Road from OpenStreetMap, via Nominatim
(the Overpass mirrors were down). Writes data/ktm/places_ring.json:
reverse geocodes every 100 m of the loop (English and Nepali) plus a
search for each well-known Ring Road chowk.
Each place's board goes at its chowk (world/export_web.py places): a node
named "<place> Chowk", else where the road named after it crosses the Ring
Road, else the nearest major crossing.
Usage policy: one request per second, cached on disk."""
import json, os, time, urllib.parse, urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "ktm")
CACHE = os.path.join(DATA, "nominatim.json")
UA = {"User-Agent": "3d_doodle ring road map (github.com/incri7/3d_doodle)"}
CHOWKS = ["Kalanki", "Balkhu", "Ekantakuna", "Satdobato", "Gwarko", "Balkumari", "Koteshwor", "Tinkune",
          "Sinamangal", "Gaushala", "Chabahil", "Gopikrishna", "Dhumbarahi", "Narayan Gopal Chowk", "Basundhara",
          "Samakhusi", "Gongabu", "Machhapokhari", "Balaju", "Banasthali", "Swayambhu", "Sitapaila", "Nayabazar",
          "Bafal", "Dallu", "Chobhar", "Nakhu", "Mahalaxmisthan", "Jawalakhel", "Kuleshwor", "Teku", "Maharajgunj",
          "Tokha", "Naxal", "Bansbari", "Golfutar", "Mitrapark", "Pepsicola", "Old Baneshwor", "Baneshwor",
          "Thapagaun", "Bijulibazar", "Kumaripati", "Lagankhel", "Dhobighat", "Harisiddhi", "Imadol", "Hattiban",
          "Sanepa", "Kirtipur", "Taukhel", "Bhaisepati", "Talchhikhel", "Hattigauda", "Chundevi", "Sukedhara",
          "Mandikhatar", "Kapan", "Boudha", "Jorpati", "Battisputali", "Bhimsengola", "Shantinagar", "Tribhuvan Airport"]

cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}


def get(url):
    if url in cache:
        return cache[url]
    for i in range(4):
        try:
            time.sleep(1.1)
            r = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read())
            cache[url] = r
            if len(cache) % 20 == 0:
                json.dump(cache, open(CACHE, "w"))
            return r
        except Exception as e:  # noqa: BLE001
            print("  retry", e, flush=True)
            time.sleep(5 * (i + 1))
    return None


def main():
    meta = json.load(open(os.path.join(DATA, "prep.json")))
    c = np.load(os.path.join(DATA, "loop.npy"))
    lon = c[:, 0] / meta["kx"] + meta["lon0"]
    lat = c[:, 1] / meta["ky"] + meta["lat0"]
    rev = []
    for k in range(0, len(c), 50):                       # every 100 m
        row = {"k": k}
        for lang in ("en", "ne"):
            u = (f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat[k]:.6f}&lon={lon[k]:.6f}"
                 f"&zoom=17&addressdetails=1&accept-language={lang}")
            r = get(u) or {}
            row[lang] = r.get("address", {})
        rev.append(row)
        print(k, row["en"].get("neighbourhood") or row["en"].get("quarter") or row["en"].get("suburb"), flush=True)
    found = []
    vb = f"{meta['lon0'] - 0.06},{meta['lat0'] + 0.06},{meta['lon0'] + 0.06},{meta['lat0'] - 0.06}"
    for name in CHOWKS:
        for lang in ("en", "ne"):
            u = (f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(name)}&format=jsonv2&limit=6"
                 f"&viewbox={vb}&bounded=1&namedetails=1&accept-language={lang}")
            for h in get(u) or []:
                found.append({"q": name, "lang": lang, "name": h.get("name"), "names": h.get("namedetails", {}),
                              "lat": float(h["lat"]), "lon": float(h["lon"]), "cls": h.get("category"), "type": h.get("type")})
        print(name, len(found), flush=True)
    # the chowk itself: junction nodes, bus stops and squares named "<place> Chowk"
    chowk = []
    for name in CHOWKS:
        u = (f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(name + ' Chowk')}&format=jsonv2&limit=8"
             f"&viewbox={vb}&bounded=1&namedetails=1&accept-language=en")
        for h in get(u) or []:
            chowk.append({"q": name, "name": h.get("name"), "lat": float(h["lat"]), "lon": float(h["lon"]),
                          "cls": h.get("category"), "type": h.get("type")})
    json.dump(cache, open(CACHE, "w"))
    json.dump({"reverse": rev, "search": found, "chowk": chowk}, open(os.path.join(DATA, "places_ring.json"), "w"), ensure_ascii=False)


if __name__ == "__main__":
    main()
