"""Scene setup and object bookkeeping."""

import bpy
from mathutils import Vector


def reset():
    """Start from an empty scene in metric units (1 unit = 1 meter)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    return scene


def collection(name):
    """Get or create a collection linked to the scene."""
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll


def colliders():
    """Collision boxes created with geo.collider()."""
    return [o for o in bpy.context.scene.objects if o.get("doodle_collider")]


def model_objects():
    """All mesh objects that make up the model (excludes the studio set)."""
    studio = bpy.data.collections.get("Studio")
    skip = set(studio.objects) if studio else set()
    return [o for o in bpy.context.scene.objects
            if o.type == "MESH" and o not in skip and not o.get("doodle_cutter")
            and not o.get("doodle_collider")]


def bounds(objects=None):
    """World-space (min, max) corners over the evaluated model objects."""
    objects = objects or model_objects()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    lo = Vector((float("inf"),) * 3)
    hi = Vector((float("-inf"),) * 3)
    for obj in objects:
        ev = obj.evaluated_get(depsgraph)
        for corner in ev.bound_box:
            p = ev.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
    return lo, hi
