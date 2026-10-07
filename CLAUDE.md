# 3d_doodle

Game-ready 3D models built from code with headless Blender (`bpy` 5.2 LTS).
The user describes an idea; we model it in Python, render previews, and bake +
export it for Unity / Unreal / Three.js.

## Setup

`bash setup.sh` installs Blender as a Python module into `.venv` (the
SessionStart hook runs it). Always use `.venv/bin/python`.

## Commands

```bash
.venv/bin/python build.py <model> --fast        # quick check (~1-2 min)
.venv/bin/python build.py <model>               # full quality
.venv/bin/python build.py <model> --turntable   # + 360 mp4 loop
.venv/bin/python build.py <model> --no-export   # renders only (iterating on looks)
```

Output in `output/<model>/`: `hero.png`, `views.png` (front/right/back/top),
`export_check.png` (the re-imported GLB, i.e. what an engine sees),
`<model>.glb`, `<model>.fbx`, `textures/*.png`, `<model>.blend`.

## Layout

- `doodle/geo.py`: primitives (box, cylinder, sphere, torus), modifiers (bevel,
  boolean `cut`, mirror, array, subsurf), `finish_hard_surface()`.
- `doodle/materials.py`: procedural PBR (`painted_metal` with edge wear and
  grime, `metal`, `plastic`, `rubber`, `glass`, `emissive`, `wood`).
- `doodle/lighting.py`: studio backdrop + area-light presets
  (studio/dramatic/soft/sunset).
- `doodle/render.py`: Cycles CPU setup, auto-framing camera, hero/views/turntable.
- `doodle/export.py`: join, triangulate, smart-UV, bake every Principled input to
  textures, single atlas material, GLB + FBX.
- `doodle/textshape.py` + `geo.text()`: HarfBuzz-shaped text (any script) as mesh;
  `geo.flat_shape()` for vector decals; `geo.tube()` for bent rods.
- `models/<name>.py`: one file per model; defines `build()` and optional `LIGHTING`.
- `docs/reference/`: recipes and real-world dimensions (MIT, from cc-blender-skill).

## Rules

- Model in meters at real-world size. Look up
  `docs/reference/cc-blender-skill/common-object-dimensions.md` first.
- Front of a model faces -Y, up is +Z (Blender convention; exporters convert to Y-up).
- Naming: `GEO-` meshes, `MAT-` materials, `CUT-` boolean cutters, `CAM-`, `LGT-`.
- Use Principled BSDF for everything; any node tree feeding its inputs bakes.
  Shader-only effects that don't route through Principled inputs won't export.
- **Always look at the renders** (`hero.png`, `views.png`, `export_check.png`)
  before reporting success. Numbers passing doesn't mean it looks right.
- EEVEE doesn't work here (no GPU). Use Cycles on CPU.
- The network blocks blender.org, polyhaven.com and most sites; PyPI,
  GitHub and Hugging Face work. Don't plan on HDRI or texture downloads.
- Commit renders + exports in `output/` so the user can see them on GitHub.
