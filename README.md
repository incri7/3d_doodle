# 3d_doodle

Game-ready 3D models built from code with Blender, from idea to `.glb`/`.fbx`
you can drop into **Unity, Unreal, Godot or Three.js**.

![crate](output/crate/hero.png)

## How it works

```
idea ─► models/<name>.py ─► Blender (headless) ─► renders ─► bake ─► GLB + FBX + PBR textures
```

1. A model is a Python script that builds geometry with real-world sizes,
   hard-surface modifiers (bevels, boolean cuts, arrays) and procedural PBR
   materials (painted metal with edge wear, grime, wood, rubber, glass, glow).
2. Cycles renders a hero shot, a 4-view sheet and, optionally, a 360° turntable.
3. Export joins the parts, unwraps UVs, **bakes every material to image
   textures** (base color, metallic, roughness, normal, emission) and writes
   one-material, triangulated GLB and FBX files.
4. The GLB is re-imported and rendered again (`export_check.png`) to prove it
   looks the same with textures only, as a game engine will see it.

## Usage

```bash
bash setup.sh                                  # installs Blender 5.2 as a Python module
.venv/bin/python build.py crate --fast         # quick preview
.venv/bin/python build.py crate --turntable    # full quality + 360 video
```

## Output per model (`output/<name>/`)

| File | What |
|---|---|
| `hero.png` | Beauty render |
| `views.png` | Front / right / back / top |
| `turntable.mp4` | 360° loop (with `--turntable`) |
| `export_check.png` | The exported GLB re-rendered (engine view) |
| `<name>.glb` | glTF binary: Three.js, Godot, Unity (glTFast), Unreal (glTF importer) |
| `<name>.fbx` | FBX with embedded textures: Unity / Unreal |
| `textures/` | `basecolor`, `metallic`, `roughness`, `normal`, `emission` PNGs |
| `<name>.blend` | Source scene: open in Blender desktop to tweak by hand |

### Importing

- **Unity**: drag the `.fbx` into Assets. If textures don't show, assign the
  maps from `textures/` to a Standard/URP Lit material (metallic and roughness
  are separate maps: Unity's smoothness = 1 − roughness).
- **Unreal**: Import the `.fbx` (or `.glb` with the glTF importer); normal map
  is OpenGL-style (+Y), so tick *Flip Green Channel* if you use the PNG directly.
- **Three.js**: `GLTFLoader().load('crate.glb')`.

## Models

| Model | Tris | Notes |
|---|---|---|
| `crate` | ~9.6k | Sci-fi supply crate, pipeline test |
| `nepali_bus` | | Classic Tata-style Nepali long-route bus (starting model) |
| `agni_bus` | ~139k | Agni Express "Super Agni A/C VIP Sofa" coach, from user photos |

## Web viewer

`web/` is a small Three.js driving sandbox for the Agni coach on a Nepali
hill road. Drive with W/A/S/D or the arrow keys (Space handbrake, hold H
for the air horn, J for the musical pressure horn, L headlights) and switch between ten game cameras with C or 1–0:
chase, far chase, driver (first person, with live side mirrors), bumper,
second person, wheel, passenger, bird's eye, TV roadside cameras and free
orbit. A rear-view mirror inset can be toggled with M, hold B to look back,
and drag to look around. Touch screens get on-screen pedals. The road wheels
roll and the front pair steer, and the steering wheel turns with your input.

Physics: real vehicle simulation with [cannon-es](https://github.com/pmndrs/cannon-es)
(`web/bus-physics.js`, inlined into the page by `python3 web/sync_physics.py`),
with no driving assists: no ABS, no stability control, no anti-roll cheat.
12 t chassis built from the model's hitbox with a 1.5 m centre of mass, six
raycast wheels on soft air suspension with the full physical roll moment,
Ackermann steering, load-sensitive tyre grip (less on grass), friction-limited
brakes that lock the wheels when you ask for more than the tyres can give, a
diesel torque curve through a 6-speed automatic with reverse, drag, rolling
resistance and a 110 km/h governor. Keyboard steering winds on over about
0.8 s, so taps are small corrections and holding turns hard. Trees, poles,
speed bumps and knock-over props collide. R resets the bus, K shows the
hitbox and suspension rays.

Measured in headless tests (`web/bus-physics.js` under Node): inside wheels
lift at 0.52 g and the bus rolls at 0.73 g (real coaches: about 0.5-0.6 g lift);
90-0 km/h in 39 m with locked wheels; holding full steer at 40 km/h or more,
or a handbrake turn at 50, rolls the bus; a full swerve at 80 km/h leaves it on
three wheels at 14 deg of lean; quick taps and half steer stay upright.

Hitbox: models add collision boxes with `geo.collider()`. They export as
`COL-*` nodes in the GLB (the web viewer builds its physics shape from them)
and as `UCX_GEO-<model>_NN` in the FBX, which Unreal imports as the mesh's
simple collision automatically.

Moving parts: tag objects with `geo.part(obj, "wheel_fl", pivot)` in a model;
`export.bake_and_export()` bakes everything into one atlas, then splits each
part into its own `PART-<name>` object with its origin at the pivot.

```bash
python3 -m http.server 8000 -d web
# then open http://localhost:8000
```

It needs internet for three.js (cdn.jsdelivr.net) and fonts. Opening
`index.html` directly from disk won't work; browsers block file loads there.
The model ships as `agni_bus.glb.b64.txt` (the web-optimized GLB: WebP
textures, quantized geometry, base64 so any static host serves it).
Regenerate it after rebuilding the bus:

```bash
npx @gltf-transform/cli optimize output/agni_bus/agni_bus.glb /tmp/agni_web.glb \
  --compress quantize --texture-compress webp --texture-size 2048 --simplify false \
  --join false --flatten false   # keep the PART- nodes separate
base64 -w0 /tmp/agni_web.glb > web/agni_bus.glb.b64.txt
```

## Text and lettering

`geo.text()` shapes text with HarfBuzz and builds the real glyph outlines as
mesh, so Devanagari conjuncts (काठमाण्डौ, काँकडभिट्टा) come out correct and
lettering bakes and exports like any other part. Fonts are in `assets/fonts/`
(all SIL OFL): Mukta, Noto Sans Devanagari, Oswald, Exo 2, Michroma, Archivo Black.

## Credits

Reference recipes in `docs/reference/cc-blender-skill/` are from
[RobLe3/cc-blender-skill](https://github.com/RobLe3/cc-blender-skill) (MIT).
