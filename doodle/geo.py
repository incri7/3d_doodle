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


def flat_shape(name, contours, depth=0.004, location=(0, 0, 0), rotation=(0, 0, 0), coll=None):
    """Filled 2D shape(s) extruded by `depth`, as a mesh. `contours` are
    closed polylines [(x, y), ...] in the local XY plane; nested contours
    become holes (even-odd), so letters with counters just work.
    Place on a surface with `rotation`, e.g. (pi/2, 0, 0) to face -Y."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "2D"
    cu.fill_mode = "BOTH"
    cu.extrude = depth / 2
    for c in contours:
        sp = cu.splines.new("POLY")
        sp.points.add(len(c) - 1)
        for pt, (x, y) in zip(sp.points, c):
            pt.co = (x, y, 0, 1)
        sp.use_cyclic_u = True
    tmp = bpy.data.objects.new(name + "_curve", cu)
    bpy.context.scene.collection.objects.link(tmp)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(depsgraph))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    obj = bpy.data.objects.new(name, me)
    obj.location = location
    obj.rotation_euler = rotation
    return _link(obj, coll)


def text(name, body, size=0.2, depth=0.004, location=(0, 0, 0), rotation=(0, 0, 0),
         font="devanagari", tracking=0.0, skew=0.0, coll=None):
    """Shaped text (HarfBuzz, so Devanagari conjuncts are correct) as a mesh,
    centered on `location`. `size` is the em size in meters. Fonts: see
    textshape.FONTS (devanagari, condensed, italic, wide, black) or a path.
    skew > 0 slants it like italic."""
    from . import textshape
    contours = textshape.outlines(body, size, font, tracking=tracking)
    if skew:
        contours = [[(x + y * skew, y) for x, y in c] for c in contours]
    return flat_shape(name, contours, depth, location, rotation, coll)


def tube(name, points, radius=0.02, location=(0, 0, 0), resolution=8, coll=None):
    """Smooth round tube through 3D `points` (mirror arms, rails, handles)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 3
    cu.use_fill_caps = True
    sp = cu.splines.new("NURBS")
    sp.points.add(len(points) - 1)
    for pt, co in zip(sp.points, points):
        pt.co = (*co, 1)
    sp.use_endpoint_u = True
    sp.order_u = min(4, len(points))
    sp.resolution_u = resolution
    tmp = bpy.data.objects.new(name + "_curve", cu)
    bpy.context.scene.collection.objects.link(tmp)
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    obj = bpy.data.objects.new(name, me)
    obj.location = location
    obj.data.shade_smooth()
    return _link(obj, coll)


def bezier(p0, p1, p2, p3, steps=16):
    """Points along a 2D cubic Bezier (excluding p0), for building outlines."""
    out = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return out


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


def cut(obj, cutter, operation="DIFFERENCE", hide=True, material=None):
    """Boolean `cutter` into `obj`. The cutter is hidden from renders/exports.
    With `material`, the newly cut faces get that material (e.g. black arch
    liners) instead of the object's own."""
    m = obj.modifiers.new(f"Bool_{cutter.name}", "BOOLEAN")
    m.object = cutter
    m.operation = operation
    m.solver = "EXACT"
    if material is not None:
        cutter.data.materials.append(material)
        m.material_mode = "TRANSFER"
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
