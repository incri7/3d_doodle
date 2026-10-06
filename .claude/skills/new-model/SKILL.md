---
name: new-model
description: Build a new 3D model in this repo from the user's description: plan with real dimensions, write models/<name>.py using the doodle toolkit, render, visually check, iterate, then bake and export GLB/FBX for Unity/Unreal/Three.js. Use whenever the user asks to make, model, create or design any 3D object, prop, vehicle, building, character or scene.
---

# New model workflow

1. **Plan**: restate the idea as parts with real-world sizes in meters. Check
   `docs/reference/cc-blender-skill/common-object-dimensions.md`. Ask at most
   one question if style or use is truly unclear; otherwise pick sensible
   defaults (stylized-realistic, game-ready, under 30k tris for props).
2. **Blockout**: write `models/<name>.py` with `build()` using `doodle.geo`
   primitives at the right size. Run `.venv/bin/python build.py <name> --fast --no-export`
   and read `hero.png` + `views.png`. Fix silhouette and proportions first.
3. **Refine**: boolean cuts (`geo.cut`), bevels (`geo.finish_hard_surface`),
   mirror/array for repetition, subsurf for organic parts. Add secondary
   detail (bolts, seams, panels): it's what makes a model read as "AAA".
4. **Materials**: `doodle.materials`. Vary roughness, add wear/grime; flat
   colors look like plastic toys. Pick a `LIGHTING` preset.
5. **Check**: read every render image. Is the subject recognizable, correctly
   proportioned, well framed, and are materials readable? If not, fix and re-run.
6. **Export**: `.venv/bin/python build.py <name>` (add `--turntable` for video).
   Read `export_check.png`: it must match `hero.png`. If it doesn't, something
   isn't routed through Principled BSDF inputs.
7. **Report**: tris count, file sizes, what to look at, and honest limits.
   Commit `models/<name>.py` and `output/<name>/` and push.

## Recipes and gotchas

- More detail: `docs/reference/cc-blender-skill/blender-modeling.md` and
  `blender-materials.md`.
- Elongated objects (swords, bottles): broad face toward the -Y camera.
- Points/tips: merge vertices to a single point (`bmesh.ops.pointmerge`); don't scale to 0.
- Organic shapes: bmesh cage + `geo.subsurf(obj, 2)`, not stacks of spheres.
- Glass: `materials.glass`; it stays a separate un-baked material on export.
- Emission strength above ~5 clips to white under AgX; 2-5 reads as glow.
- Fast loops: `--no-export` while iterating looks, `--no-render` for export-only.
