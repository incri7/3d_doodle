"""Geometry building blocks.

Hard-surface recipe that holds up in game engines:
    primitive -> boolean cuts -> bevel (angle-limited, harden normals)
    -> weighted normals -> smooth shading with sharp edges by angle.
Keep modifiers live while modeling; export.py applies them.
"""

import math

import bmesh
import bpy
from mathutils import Vector


def _link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


def mesh_object(name, bm, location=(0, 0, 0), coll=None):
    """Turn a bmesh into a linked object and free the bmesh."""
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.location = location
    return _link(obj, coll)


def box(name, size=(1, 1, 1), location=(0, 0, 0), coll=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    return mesh_object(name, bm, location, coll)


def cylinder(name, radius=0.5, depth=1.0, segments=32, location=(0, 0, 0), coll=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments,
                          radius1=radius, radius2=radius, depth=depth)
    return mesh_object(name, bm, location, coll)


def sphere(name, radius=0.5, segments=32, rings=16, location=(0, 0, 0), coll=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=radius)
    return mesh_object(name, bm, location, coll)


def torus(name, major=0.5, minor=0.1, major_seg=48, minor_seg=12, location=(0, 0, 0), coll=None):
    bm = bmesh.new()
    verts = []
    for i in range(major_seg):
        a = 2 * math.pi * i / major_seg
        ring = []
        for j in range(minor_seg):
            b = 2 * math.pi * j / minor_seg
            r = major + minor * math.cos(b)
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), minor * math.sin(b))))
        verts.append(ring)
    for i in range(major_seg):
        for j in range(minor_seg):
            a, b = verts[i], verts[(i + 1) % major_seg]
            bm.faces.new((a[j], b[j], b[(j + 1) % minor_seg], a[(j + 1) % minor_seg]))
    return mesh_object(name, bm, location, coll)


# --- modifiers -------------------------------------------------------------

def bevel(obj, width=0.02, segments=3, angle=30, harden=True):
    m = obj.modifiers.new("Bevel", "BEVEL")
    m.width = width
    m.segments = segments
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    m.harden_normals = harden
    m.miter_outer = "MITER_ARC"
    return m


def subsurf(obj, levels=2):
    m = obj.modifiers.new("Subsurf", "SUBSURF")
    m.levels = m.render_levels = levels
    return m


def mirror(obj, axes=(True, False, False), bisect=True):
    m = obj.modifiers.new("Mirror", "MIRROR")
    m.use_axis = axes
    m.use_bisect_axis = axes if bisect else (False, False, False)
    m.use_clip = True
    return m


def array(obj, count=3, offset=(1.1, 0, 0), relative=True):
    m = obj.modifiers.new("Array", "ARRAY")
    m.count = count
    if relative:
        m.relative_offset_displace = offset
    else:
        m.use_relative_offset = False
        m.use_constant_offset = True
        m.constant_offset_displace = offset
    return m


def cut(obj, cutter, operation="DIFFERENCE", hide=True):
    """Boolean `cutter` into `obj`. The cutter is hidden from renders/exports."""
    m = obj.modifiers.new(f"Bool_{cutter.name}", "BOOLEAN")
    m.object = cutter
    m.operation = operation
    m.solver = "EXACT"
    if hide:
        cutter.hide_render = True
        cutter.display_type = "WIRE"
        cutter["doodle_cutter"] = True
    return m


def solidify(obj, thickness=0.02):
    m = obj.modifiers.new("Solidify", "SOLIDIFY")
    m.thickness = thickness
    return m


def weighted_normals(obj):
    m = obj.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
    m.keep_sharp = True
    return m


def smooth(obj, angle=30):
    """Smooth shading with edges sharper than `angle` kept crisp."""
    obj.data.shade_smooth()
    obj.data.set_sharp_from_angle(angle=math.radians(angle))


def finish_hard_surface(obj, bevel_width=0.015, segments=3, angle=30):
    """The standard hard-surface stack: bevel + weighted normals + smooth."""
    bevel(obj, bevel_width, segments, angle)
    weighted_normals(obj)
    smooth(obj, angle)
    return obj


def parent(child, par):
    child.parent = par
    child.matrix_parent_inverse = par.matrix_world.inverted()
    return child
