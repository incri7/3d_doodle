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


def profile_prism(name, profile_xz, y0, y1, location=(0, 0, 0), coll=None):
    """Extrude a closed 2D outline in the XZ plane along Y from y0 to y1.
    Good for vehicle bodies: draw the cross-section, extrude the length."""
    bm = bmesh.new()
    front = [bm.verts.new((x, y0, z)) for x, z in profile_xz]
    back = [bm.verts.new((x, y1, z)) for x, z in profile_xz]
    n = len(profile_xz)
    bm.faces.new(front[::-1])
    bm.faces.new(back)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((front[i], front[j], back[j], back[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_object(name, bm, location, coll)


def rounded_rect_profile(width, z0, z1, radius, steps=6):
    """Cross-section with vertical sides and rounded top corners (bus/van roof)."""
    hw = width / 2
    pts = [(-hw, z0), (hw, z0), (hw, z1 - radius)]
    for i in range(1, steps):
        a = (math.pi / 2) * i / steps
        pts.append((hw - radius + radius * math.cos(a), z1 - radius + radius * math.sin(a)))
    pts.append((hw - radius, z1))
    pts.append((-hw + radius, z1))
    for i in range(1, steps):
        a = math.pi / 2 + (math.pi / 2) * i / steps
        pts.append((-hw + radius + radius * math.cos(a), z1 - radius + radius * math.sin(a)))
    pts.append((-hw, z1 - radius))
    return pts


FONT_DEVANAGARI = "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"


def text(name, body, size=0.2, depth=0.004, location=(0, 0, 0), rotation=(0, 0, 0),
         font=FONT_DEVANAGARI, coll=None):
    """Text as a real mesh (exports and bakes like any other part).
    Centered on `location`. Default font covers Latin and Devanagari; Blender
    has no complex-script shaping, so prefer words without conjuncts or
    pre-base vowel signs (ि)."""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.font = bpy.data.fonts.load(font, check_existing=True)
    cu.size = size
    cu.extrude = depth / 2
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    tmp = bpy.data.objects.new(name + "_curve", cu)
    bpy.context.scene.collection.objects.link(tmp)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(depsgraph))
    bpy.data.objects.remove(tmp)
    obj = bpy.data.objects.new(name, me)
    obj.location = location
    obj.rotation_euler = rotation
    return _link(obj, coll)


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
