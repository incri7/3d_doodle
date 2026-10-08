"""Generate drive.html (the bus on the real Kathmandu Ring Road) from
index.html + map-ktm.js. Run after editing either:  python3 web/make_drive.py"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "index.html"), encoding="utf-8").read()
mapjs = open(os.path.join(HERE, "map-ktm.js"), encoding="utf-8").read()
assert "/* @@map */" in src and '<script type="importmap">' in src
out = src.replace("/* @@map */", "/* @@map: generated from map-ktm.js by make_drive.py */\n" + mapjs)
out = out.replace('<script type="importmap">', "<script>window.DRIVE_MAP = 'ktm';</script>\n<script type=\"importmap\">", 1)
out = out.replace("<title>Agni Express 3D</title>", "<title>Ring Road Drive</title>", 1)
if not out.lstrip().lower().startswith("<!doctype"):
    out = "<!doctype html>\n" + out      # served as its own page (standards mode)
open(os.path.join(HERE, "drive.html"), "w", encoding="utf-8").write(out)
print("drive.html", len(out), "chars")
