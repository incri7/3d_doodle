"""Inline web/bus-physics.js into web/index.html between the @@bus-physics markers.

The page inlines the physics (strict hosts may block loading a second script
file); bus-physics.js stays the single source that headless tests import.
    python3 web/sync_physics.py
"""
import pathlib
import re

here = pathlib.Path(__file__).parent
src = (here / "bus-physics.js").read_text()
src = re.sub(r"^import .*?;\n", "", src, flags=re.M)        # CANNON is imported by the page
src = re.sub(r"^export (const|function|class) ", r"\1 ", src, flags=re.M)
page = (here / "index.html").read_text()
start = page.index("/* @@bus-physics:start")
start = page.index("*/", start) + 2
end = page.index("/* @@bus-physics:end */")
(here / "index.html").write_text(page[:start] + "\n" + src + page[end:])
print("inlined", len(src), "chars")
