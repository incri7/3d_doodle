# Real-world maps

Builds real places from open data. First area: the Kathmandu Ring Road
(28.8 km loop) and the city inside it.

```bash
.venv/bin/python world/fetch_osm.py             # roads, rivers, parks, buildings (OpenStreetMap)
.venv/bin/python world/fetch_dem.py             # terrain heights (Copernicus GLO-30)
.venv/bin/python world/fetch_sentinel.py        # satellite colour (Sentinel-2)
.venv/bin/python world/fetch_open_buildings.py  # extra footprints (Google Open Buildings)
MAPILLARY_TOKEN=... .venv/bin/python world/fetch_mapillary.py  # street photos every 400 m
.venv/bin/python world/mapillary_sheet.py       # contact sheet + photo map
.venv/bin/python world/prep_ktm.py              # merge into local metres -> data/ktm/prep.*
.venv/bin/python world/build_ktm.py [--fast]    # Blender scene + renders -> output/ktm_ringroad/
```

Downloads are cached in `data/ktm/` (not committed, ~0.7 GB).

## Sources and licences

| Data | Source | Licence |
|---|---|---|
| Roads, Ring Road route (relation 4659866), rivers, parks, 227k buildings | © OpenStreetMap contributors | ODbL 1.0 |
| 64k extra building footprints (where OSM has none) | Google Open Buildings v3 | CC BY 4.0 / ODbL |
| Terrain | Copernicus GLO-30 DEM, © DLR e.V. 2010-2014 and © Airbus 2014-2018, provided under COPERNICUS by the European Union and ESA | Copernicus DEM licence (free) |
| Street photos (120 along the loop, contact sheet and map in output/ktm_ringroad/) | Mapillary, photos by @roadroid, @thapa7, @geohacker, @mahesh_thapa, @olily, @gauravparajuli09, @nitishmishra, @ArunBhomi, @mapconcierge, @Ghyasang_Ghising, @fundacja_geolife | CC BY-SA 4.0 |
| Ground colour | Contains modified Copernicus Sentinel data (2026), Sentinel-2 L2A | Copernicus open licence |

Building heights: OSM `building:levels` / `height` where tagged; otherwise
a Kathmandu-typical 2-6 storeys (mostly 3-5) picked per building.

## Street level: Kalanki -> Balkhu bridge

```bash
.venv/bin/python world/build_street.py [--fast]   # -> output/ktm_street/
```

1.8 km of the Ring Road rebuilt at street level on the same data. The
cross-section comes from OpenStreetMap (inner carriageways at +-4 m, outer
ones at +-14..17 m: 8 lanes) and the Mapillary photos (black/yellow kerbs,
raised separators, yellow edge lines, white lane dashes, paver footpaths,
poles with sagging wires, median street lights, the Balkhu Khola bridge).
3,168 nearby buildings get windows, slab bands, balconies, shop shutters,
signboards with Devanagari shop names and rooftop water tanks; the rest of
the valley (113k buildings, DEM + Sentinel-2) is the backdrop. The Agni and
Sajha buses drive on it. `compare_photos.jpg` puts each Mapillary photo next
to a render from the same spot and heading.
