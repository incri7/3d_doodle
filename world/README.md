# Real-world maps

Builds real places from open data. First area: the Kathmandu Ring Road
(28.8 km loop) and the city inside it.

```bash
.venv/bin/python world/fetch_osm.py             # roads, rivers, parks, buildings (OpenStreetMap)
.venv/bin/python world/fetch_dem.py             # terrain heights (Copernicus GLO-30)
.venv/bin/python world/fetch_sentinel.py        # satellite colour (Sentinel-2)
.venv/bin/python world/fetch_open_buildings.py  # extra footprints (Google Open Buildings)
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
| Ground colour | Contains modified Copernicus Sentinel data (2026), Sentinel-2 L2A | Copernicus open licence |

Building heights: OSM `building:levels` / `height` where tagged; otherwise
a Kathmandu-typical 2-6 storeys (mostly 3-5) picked per building.
