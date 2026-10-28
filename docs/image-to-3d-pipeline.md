# Image-to-3D pipeline: plan

A plan for turning real captures (or, as a fallback, a single image) into clean,
editable, game-ready 3D models, finished in Blender by Claude through this repo.

Status: **design only, nothing built yet.** Written 28 Oct 2026.

---

## 1. Why this exists

Asking an AI to model straight into Blender (Blender MCP, or code like this
repo's `models/*.py`) works well for hard-surface objects such as the buses,
but breaks down on organic, complex shapes like people, animals and faces:

- The AI has to describe every curve as numbers. It is not short of code; it is
  short of **shape information**.
- It is weaker than a human at judging what looks right, so it has to render,
  look and fix in a loop.
- Single-model image-to-3D tools (Meshy, Rodin, TRELLIS, Hunyuan3D) are fast,
  but invent the hidden sides and give messy, hard-to-edit meshes. The open
  ones need 12 to 24 GB of VRAM.

**Idea:** don't make one AI do everything. Build a pipeline where each tool
does what it is best at:

| Part | Good at | Bad at |
|---|---|---|
| Real photos / video | Ground truth, all sides | Needs a careful capture |
| Plain maths (camera solve, silhouette carving) | Exact, repeatable | Can't see dents and hollows |
| Small AI models (masks, depth, extra views) | Filling gaps fast | Guessing, inconsistent between views |
| Templates (human base mesh) | Correct anatomy for complex shapes | Must be fitted to the subject |
| Claude + Blender | Judgment, clean rebuild, checking | Inventing complex shapes from nothing |
| Automatic check loop | Catching mistakes nobody noticed | Needs good reference images |

No method is 100%. Studios also fix their scans by hand. The aim is for each
part to cover the others' weak spots.

---

## 2. Goals and non-goals

**Goals**

- Realistic models of real people and objects that match the subject closely
  from every side.
- Clean, editable, animatable topology (not a triangle soup).
- Runs on owned hardware: a local NVIDIA GPU with **6 GB VRAM**, plus the
  cloud machine this repo runs on. No paid services, no daily limits.
- Output through the existing 3d_doodle bake and export: GLB, FBX, PBR textures.

**Non-goals (for now)**

- Beating Meshy at one-image speed.
- 100% identical results from a single photo. A single photo does not contain
  the back; any method can only guess it.
- Perfect hair, eyes, glasses or shiny surfaces. These are hard even for
  scanning studios and will need hand work.

---

## 3. Input: one video of a rotating person

The main input is a video of the subject turning in place in front of a phone on
a stand. This is the turntable method with the person as the turntable.

### Capture rules

1. **Phone on a stand**, not handheld. Highest resolution video.
2. **Turn in steps, not a smooth spin.** Mark the floor every 15° (24 steps per
   turn) and pause briefly at each mark. A cheap turntable is even better.
3. **Two or three full turns at different phone heights:** chest height, head
   height, and above the head looking down (for the top of the head and
   shoulders).
4. **A-pose the whole time:** arms slightly away from the body, still.
5. **Soft, even light from the front of the subject**, or daylight in shade.
   A lamp to one side lights different parts of the body as it turns, so colours
   won't match between frames.
6. **Matte clothes**, hair tied back if possible. Avoid shiny or very dark
   fabric.
7. **A scale reference** in shot (a ruler, an A4 sheet or a known height mark)
   so the model comes out at real size.
8. **Keep it short:** about 30 to 60 seconds per turn. People sway and blink,
   and every bit of movement blurs the scan.

### Why the room has to be removed

The model is only the person, but the room behind them still matters for one
technical reason: camera-solving software tracks features like doors and
furniture to work out angles. With a fixed camera, the room never moves, so the
solver would think the camera never moved either and fail. The pipeline cuts
the room out of every frame before solving. Then only the body is tracked and it
looks as if the camera orbited the person. Any room works; a plain wall just
makes the automatic cutout cleaner.

---

## 4. The pipeline, step by step

Steps 1 to 5 are **capture**, 6 to 9 are **building**, 10 and 11 are **quality
and output**. Claude's main jobs are steps 7, 8 and 10.

### Step 1: Video in

- **Input:** phone video following the capture rules above.
- **Output:** video file in the pipeline's input folder.

### Step 2: Frame picker

- **What:** extract frames, find the pauses between turns (low motion between
  consecutive frames), and keep the best frame from each pause.
- **Scoring:** sharpness (variance of the Laplacian), exposure (clipped
  highlights and shadows), near-duplicate removal.
- **Output:** about 24 frames per turn, 50 to 75 total, plus a score for each.
- **Tools:** ffmpeg, OpenCV. Plain Python, no AI.

### Step 3: Body cutout (masking)

- **What:** separate the person from the room in every frame.
- **Output:** a black and white mask and an RGBA cutout per frame.
- **Tools:** rembg (human segmentation model, CPU friendly) or SAM 2 small
  (better edges, GPU).

### Step 4: Angle solve

- **What:** work out the turn angle and height of each frame, as if the camera
  orbited the person. Use the masks so only the body is matched.
- **Scale:** from the reference object in step 3's frames.
- **Output:** camera position and direction for every frame, at real scale.
- **Tools:** COLMAP (pycolmap). Works on CPU, faster on GPU.

### Step 5: Coverage check

- **What:** check that every part of the body is seen from enough angles.
- **Report:** an angle chart per turn height, a contact sheet of the chosen
  frames, and plain-language problems, for example "not enough of the top of
  the head" or "left arm hidden in frames 40 to 55".
- **Action:** retake only the missing part instead of the whole capture.
- **Tools:** plain Python.

### Step 6: Rough shape

- **Silhouette carving (visual hull):** start from a block and cut away
  everything outside each mask, from each known camera angle. What's left is
  the body's overall shape. Plain maths, no AI.
- **Limit:** silhouettes can't see hollows and dents (between the legs, under
  the arms, the eye sockets).
- **Dense scan on top:** multi-view reconstruction (COLMAP dense, or Gaussian
  splatting with a lighter implementation such as gsplat) adds the real surface
  detail: clothing folds, face shape. This is the step that needs the GPU.
- **Depth (optional):** a depth model (Depth Anything V2, or a human-specific
  model like Sapiens) helps where the scan is thin. Its depth is relative, not
  real distance, and differs between views, so each depth map is scaled to fit
  the silhouette shape.
- **Output:** a dense, coloured but messy mesh or point cloud.

### Step 7: Template fit (Claude + Blender)

- **What:** don't build a human from scratch. Start from a clean human base
  mesh and fit it to the scan:
  1. Estimate the skeleton pose from the frames and pose the template to match.
  2. Adjust body proportions (height, limb lengths, girth) to match measurements
     taken from the scan.
  3. Shrinkwrap the template onto the scan surface so it follows the real shape
     while keeping its tidy topology.
- **Template:** MPFB (MakeHuman for Blender). Open source, its characters are
  free to use commercially. *To check:* whether its body assets download from
  GitHub or from MakeHuman's own site (blocked on the cloud machine).
- **Why Claude:** fitting and fixing is judgment work: which parts to trust,
  where the scan is wrong, how to keep the topology clean. Claude works from
  **measurements and renders**, not the raw mesh: cross-section slices, part
  sizes, joint positions, side-by-side comparisons.
- **Output:** a clean, riggable human mesh in the subject's shape and pose.

### Step 8: Face pass

- **What:** faces are where people notice errors first, so they get their own
  fitting: face landmarks from the front frames, then extra shaping of the
  template's face region against the dense scan.
- **Tools:** a face landmark model (CPU friendly), Blender for the shaping.

### Step 9: Texture

- **What:** project colours from the chosen frames onto the clean model's UVs,
  blend the overlaps, and even out lighting differences between frames.
- **Gaps:** areas no frame saw (top of the head, under the chin) are filled from
  neighbouring colours and flagged.
- **Output:** base colour texture plus roughness, and normal detail baked from
  the dense scan onto the clean mesh.

### Step 10: Check loop

- **What:** render the model from exactly the same camera angles as the chosen
  frames and compare:
  - **Silhouette overlap:** how well the render's outline matches each mask
    (intersection over union).
  - **Colour difference** per region.
  - **A side-by-side sheet** for Claude to look at.
- **Action:** fix the worst areas first, re-render, re-score. Stop when scores
  stop improving.
- **Why:** the automatic score catches mistakes even when Claude misses them.

### Step 11: Export

- **What:** this repo's existing bake and export: join, UV, bake every material
  input to textures, single atlas material, GLB + FBX, then re-import and render
  again (`export_check.png`) to prove it looks the same in a game engine.
- **Extras for game use:** lower-detail versions for distance (LODs), collision
  boxes with `geo.collider()`, moving parts with `geo.part()`.

---

## 5. Fallback: when there is only one image

Real photos from many angles always win. When only one image exists, the
missing views have to be guessed. Options, best first:

1. **Mirroring:** most creatures and people are left-right symmetric. Flipping
   the image gives the other side's three-quarter view (the pose comes out
   reversed).
2. **Anatomy knowledge:** for the back, top and belly, fill in from how the
   subject is built (Claude knows what the back of a theropod or a human usually
   looks like). An educated guess, not the real thing.
3. **Blockout first:** build a rough model from the one image, render it from
   every angle, and use those renders as the other-side references.
4. **AI novel views:**
   - **Zero123++** (v1.2): one image in, **six views at fixed, known angles**
     (azimuth 30°, 90°, 150°, 210°, 270°, 330°; elevations alternating 20° and
     -10°), 320x320 each. Needs about **5 GB VRAM**. Wants a square input with
     the background removed. Known angles mean the views go straight into
     silhouette carving with no camera guessing. Weak on people; faces drift.
   - **Qwen Image Edit Angles** (hosted on Hugging Face): rotates the camera
     around a subject in a photo. Tested on 28 Oct 2026 with a dinosaur
     illustration: about 10 to 15 seconds per view; near views were good, the
     back view got the head wrong. Too big to run locally on 6 GB, and free
     hosted Spaces have daily limits and can go offline, so not something to
     depend on.
5. **For humans specifically:** a human template plus pose estimation plus
   human-specific depth beats general novel-view models.

Single-image results should be clearly marked as guessed on the unseen sides.

---

## 6. Hardware split

| Machine | Has | Runs |
|---|---|---|
| Local PC | NVIDIA GPU, 6 GB VRAM | Dense scan / Gaussian splatting, SAM 2, depth, Zero123++, ComfyUI |
| Cloud machine (this repo's Claude Code sessions) | 2 CPU cores, about 7 GB RAM, no GPU, internet limited to GitHub and package registries | Frame picker, rembg masks, COLMAP on CPU, coverage check, silhouette carving, all Blender work (Cycles on CPU), check loop, export |

**What fits in 6 GB:** COLMAP dense at medium resolution, lighter Gaussian
splatting (gsplat) with fewer/smaller frames, SAM 2 small, Depth Anything V2
small/base, smaller Sapiens models, Zero123++ (just).

**What doesn't:** TRELLIS, Hunyuan3D, Era3D (at least 16 GB) and similar large
image-to-3D models; highest-resolution scans (process in chunks).

**Cloud machine notes:** sessions are temporary (Blender is reinstalled by
`setup.sh` each session); Hugging Face, Pixabay, Wikimedia and most sites are
blocked unless allowed in claude.ai settings; EEVEE doesn't work (no GPU).

---

## 7. Orchestration: ComfyUI + Blender MCP + Claude

Loose scripts are hard to manage. ComfyUI turns each step into a node, so the
pipeline becomes one visible, repeatable workflow.

- **ComfyUI** runs on the local PC with the GPU.
- **Comfy MCP local server** (`comfy-mcp`, open source, by Comfy Org) lets Claude
  run workflows, build and edit them, search installed nodes and models,
  start/stop ComfyUI, and check VRAM. Comfy's own guidance suggests 8 GB VRAM or
  more for local generation, so 6 GB is tight; stick to the lighter nodes.
- **Blender MCP** lets Claude control Blender on the same PC. Alternatively the
  Blender steps run headless in this repo on the cloud machine.
- **Hand-off between them:** ComfyUI writes frames, masks, cameras, depth and the
  rough mesh to a shared folder; Claude loads them into Blender.

### Step to node mapping

| Step | ComfyUI node | Source |
|---|---|---|
| 2 Frame picker | Custom node (to write) | Own Python |
| 3 Masking | rembg / SAM 2 nodes | Existing custom nodes |
| 4 Angle solve | COLMAP node (to write) | Own Python, wraps pycolmap |
| 5 Coverage check | Custom node (to write) | Own Python |
| 6 Rough shape | 3DGS reconstruction from multi-view, Instant NGP, FlexiCubes | ComfyUI-3D-Pack |
| 6 Depth | Depth Anything V2 node | Existing custom nodes |
| Fallback views | Zero123++ node | ComfyUI-3D-Pack |
| 7 to 10 | Claude in Blender via Blender MCP | This repo |
| 11 Export | `doodle/export.py` | This repo |

**ComfyUI-3D-Pack caveats:** prebuilt packages target Windows with CUDA 12.4;
installation can be painful; many of its models need more than 6 GB.
Photogrammetry (COLMAP), the frame picker and the coverage check are not in it,
which is where custom nodes come in.

---

## 8. Tools and licences

| Tool | Use | Licence / notes |
|---|---|---|
| ffmpeg, OpenCV | Frames, scoring | Open source |
| rembg | Masks | MIT |
| SAM 2 | Masks | Apache 2.0 |
| COLMAP / pycolmap | Camera solve, dense scan | BSD |
| gsplat | Gaussian splatting | Apache 2.0 |
| Depth Anything V2 | Depth | Small model Apache 2.0; check larger ones |
| Sapiens | Human depth / normals | Check licence before use |
| Zero123++ | Fallback views | Code Apache 2.0; **weights CC-BY-NC 4.0** (non-commercial; generated images are free to use) |
| MPFB | Human template | Open source; characters free for commercial use |
| ComfyUI, comfy-mcp | Orchestration | Open source |
| ComfyUI-3D-Pack | 3D nodes | MIT (each bundled model has its own licence) |
| Blender (bpy) | Build, render, export | GPL |

**Dropped:** SMPL (registration needed, non-commercial only, can't be shared
publicly). Zero123++ kept only for the fallback path.

Installed agent skills in this repo (`.claude/skills/`): `new-model` (lead
workflow), `blender` (headless bpy reference), `blender-image-to-3d`
(reference-matched building and review checks).

---

## 9. Where this stands against existing tools

- **Meshy, Rodin:** one image or text to a textured model in about a minute.
  Hidden sides invented, messy meshes. Not the target to beat on speed.
- **Polycam, KIRI Engine, RealityScan:** scanning apps. These are the closer
  competitors. They give a raw scan.
- **This pipeline's edge:** accuracy from real captures **plus** a clean,
  editable, game-ready rebuild by Claude, free on owned hardware.

---

## 10. Milestones

1. **Capture test:** record one rotating-person video following section 3.
2. **Capture stage (steps 2 to 5):** frame picker, masks, angle solve, coverage
   report. Test first on a rendered video of a rotating figure with known
   angles, so results can be checked against the right answer.
3. **Rough shape (step 6):** silhouette carving on the cloud machine; dense scan
   on the local GPU.
4. **Template fit (steps 7 and 8):** confirm MPFB assets are reachable; fit to
   the scan.
5. **Texture, check loop, export (steps 9 to 11).**
6. **ComfyUI workflow:** wrap the steps as nodes; Claude drives it with
   comfy-mcp and Blender MCP.
7. **Benchmark:** same person through this pipeline vs Meshy and Polycam.

## 11. Open questions

- Are MPFB's body assets downloadable from GitHub?
- Which dense method gives the best result in 6 GB: COLMAP dense or gsplat?
- Which human depth model has a licence that fits?
- Commercial use later? If so, keep non-commercial weights (Zero123++) out of
  the main path.
