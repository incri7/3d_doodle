"""Studio set: seamless backdrop, 3-point area lights, soft gradient world.

No HDRI downloads are needed (the cloud sandbox can't reach Poly Haven).
Everything goes in the "Studio" collection so export skips it.
"""

import math

import bmesh
import bpy
from mathutils import Vector

from . import scene as sc


def _area(name, loc, target, energy, size, color, coll):
    light = bpy.data.lights.new(name, "AREA")
    light.energy = energy
    light.size = size
    light.color = color
    obj = bpy.data.objects.new(name, light)
    obj.location = loc
    direction = Vector(target) - Vector(loc)
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(obj)
    return obj


def backdrop(size, color=(0.18, 0.18, 0.19), coll=None):
    """Curved cyclorama: flat floor bending up into a back wall."""
    bm = bmesh.new()
    w, depth, height, r, steps = size * 10, size * 4, size * 5, size * 0.8, 16
    profile = [(y, 0.0) for y in (depth, 0.0)]
    for i in range(1, steps + 1):
        a = (math.pi / 2) * i / steps
        profile.append((-r * math.sin(a), r - r * math.cos(a)))
    profile.append((-r, height))
    rows = []
    # Floor runs toward the camera (-Y); the curve and wall rise behind (+Y).
    for y, z in profile:
        rows.append([bm.verts.new((x, -y, z)) for x in (-w / 2, w / 2)])
    for a, b in zip(rows, rows[1:]):
        bm.faces.new((a[0], a[1], b[1], b[0]))
    me = bpy.data.meshes.new("Backdrop")
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    obj = bpy.data.objects.new("Backdrop", me)
    (coll or bpy.context.scene.collection).objects.link(obj)

    mat = bpy.data.materials.new("Backdrop")
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = 0.8
    obj.data.materials.append(mat)
    return obj


def studio(preset="studio", floor=True, world_strength=0.15):
    """Light the model. Presets: studio (balanced), dramatic, soft, sunset."""
    coll = sc.collection("Studio")
    lo, hi = sc.bounds()
    center = (lo + hi) / 2
    size = max((hi - lo).length, 0.1)
    d = size * 1.6

    p = {
        "studio":   dict(key=1.0, fill=0.45, rim=0.9, warm=(1.0, 0.96, 0.9), cool=(0.9, 0.95, 1.0)),
        "dramatic": dict(key=1.4, fill=0.12, rim=1.5, warm=(1.0, 0.9, 0.8), cool=(0.7, 0.8, 1.0)),
        "soft":     dict(key=0.7, fill=0.6, rim=0.5, warm=(1.0, 1.0, 1.0), cool=(1.0, 1.0, 1.0)),
        "sunset":   dict(key=1.2, fill=0.35, rim=1.2, warm=(1.0, 0.72, 0.42), cool=(0.6, 0.7, 1.0)),
    }[preset]
    e = 120 * size * size  # scale energy with model size (inverse-square)

    _area("Key", center + Vector((d, -d, d * 0.9)), center, e * p["key"], size * 1.2, p["warm"], coll)
    _area("Fill", center + Vector((-d * 1.2, -d * 0.8, d * 0.4)), center, e * p["fill"], size * 2.0, p["cool"], coll)
    _area("Rim", center + Vector((-d * 0.3, d * 1.2, d * 1.1)), center, e * p["rim"], size * 0.9, p["warm"], coll)
    _area("Top", center + Vector((0, 0, d * 1.5)), center, e * 0.3, size * 2.5, (1, 1, 1), coll)

    world = bpy.context.scene.world
    nt = world.node_tree
    bg = nt.nodes.get("Background") or nt.nodes.new("ShaderNodeBackground")
    out = nt.nodes.get("World Output") or nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    bg.inputs["Color"].default_value = (0.6, 0.65, 0.72, 1)
    bg.inputs["Strength"].default_value = world_strength

    if floor:
        bd = backdrop(size, coll=coll)
        bd.location.z = lo.z
        bd.location.x = center.x
        bd.location.y = center.y + size * 0.9
    return coll
