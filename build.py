"""Build a model headlessly: geometry -> renders -> baked game-ready export.

    .venv/bin/python build.py crate                 # hero + views + export
    .venv/bin/python build.py crate --fast          # quick low-sample check
    .venv/bin/python build.py crate --turntable     # also a 360 mp4 loop
    .venv/bin/python build.py crate --no-export     # renders only

Each model lives in models/<name>.py and defines build() (plus optional
LIGHTING preset). Output goes to output/<name>/.
"""

import argparse
import importlib
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from doodle import export, lighting, render, scene  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--fast", action="store_true", help="low samples/resolution")
    ap.add_argument("--turntable", action="store_true")
    ap.add_argument("--no-export", action="store_true")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--no-stills", action="store_true", help="skip hero/views (e.g. resuming a turntable)")
    ap.add_argument("--tex", type=int, default=2048, help="baked texture size")
    args = ap.parse_args()

    mod = importlib.import_module(f"models.{args.model}")
    out = os.path.join(ROOT, "output", args.model)
    os.makedirs(out, exist_ok=True)
    t0 = time.time()

    scene.reset()
    mod.build()
    lighting.studio(getattr(mod, "LIGHTING", "studio"))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, f"{args.model}.blend"))
    print(f"built in {time.time() - t0:.1f}s")

    if not args.no_render:
        q = dict(samples=24, res=(800, 600)) if args.fast else {}
        if not args.no_stills:
            print("render:", render.hero(out, azimuth=getattr(mod, "HERO_AZIMUTH", -35),
                                           elevation=getattr(mod, "HERO_ELEVATION", 18), **q))
            print("render:", render.views(out, **({"samples": 16, "res": (480, 360)} if args.fast else {})))
        if args.turntable:
            print("render:", render.turntable(out))
        print(f"rendered at {time.time() - t0:.1f}s")

    if not args.no_export:
        _, paths, _ = export.bake_and_export(args.model, out, size=512 if args.fast else args.tex)
        print(f"exported at {time.time() - t0:.1f}s")
        if not args.no_render:
            print("render:", check_export(paths["glb"], out, mod, args.fast))


def check_export(glb, out, mod, fast):
    """Re-import the GLB into an empty scene and render it: this is what a
    game engine will see (baked textures only, no Blender shader nodes)."""
    scene.reset()
    bpy.ops.import_scene.gltf(filepath=glb)
    lighting.studio(getattr(mod, "LIGHTING", "studio"))
    q = dict(samples=24, res=(800, 600)) if fast else dict(samples=96, res=(1200, 900))
    render.setup_cycles(**q)
    cam = render.frame(render.camera(), getattr(mod, "HERO_AZIMUTH", -35),
                       getattr(mod, "HERO_ELEVATION", 18))
    return render.still(os.path.join(out, "export_check.png"), cam)


if __name__ == "__main__":
    main()
