# Reference library

Background knowledge for building models. These docs were written for driving
Blender through the Blender MCP add-on (`mcp__blender__execute_blender_code`).
In this repo we run Blender headlessly instead: the same `bpy` code goes into a
model script under `models/` and runs via `build.py`. Ignore the MCP and
viewport steps; the modeling, material, lighting and export recipes apply as-is.

| Folder | Source | License |
|---|---|---|
| `cc-blender-skill/` | [RobLe3/cc-blender-skill](https://github.com/RobLe3/cc-blender-skill) v1.3.0 | MIT (see `cc-blender-skill/LICENSE`) |

Most useful files:

- `cc-blender-skill/common-object-dimensions.md`: real-world sizes. Check before modeling anything real.
- `cc-blender-skill/assembly-order.md`: blockout, camera, light, refine, materials, detail.
- `cc-blender-skill/blender-materials.md`: PBR recipes (steel, gold, glass, skin, wood).
- `cc-blender-skill/blender-modeling.md`: elongated-object orientation, tapering to a point.
- `cc-blender-skill/blender-export.md`: glTF/FBX/STL/USD settings and per-platform polycount targets.

Also worth reading (linked, not copied, because it has no license file):
[kevinbadi/blender-skills](https://github.com/kevinbadi/blender-skills): camera
moves (turntable, crane, dolly, slow zoom, perfect loop) and Poly Haven studio setups.
