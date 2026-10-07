"""Bake procedural materials to PBR textures and export game-ready files.

Unity, Unreal and Three.js can't run Blender shader node trees, so:
  1. copy every model object with modifiers applied, join into one mesh
  2. smart-UV-unwrap it into a single texture atlas
  3. bake each Principled input (base color, metallic, roughness, emission)
     by piping it through an Emission shader, plus a tangent-space normal map
  4. swap in one image-texture material and export GLB + FBX (+ PNG maps)

Glass (transmission) materials keep their constant values instead of being
baked; glTF carries them through KHR_materials_transmission.
"""

import json
import math
import os

import bpy

from . import scene as sc

CHANNELS = [  # (name, Principled input, colorspace)
    ("basecolor", "Base Color", "sRGB"),
    ("metallic", "Metallic", "Non-Color"),
    ("roughness", "Roughness", "Non-Color"),
    ("emission", "Emission Color", "sRGB"),
]


def _select_only(objs, active):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active


def _is_glass(mat):
    b = _bsdf(mat)
    return b is not None and b.inputs["Transmission Weight"].default_value > 0.5


def _bsdf(mat):
    if mat is None or mat.node_tree is None:
        return None
    return next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)


def _materials(obj):
    """Unique materials on obj (a material can fill several slots)."""
    return list(dict.fromkeys(s.material for s in obj.material_slots if s.material))


def _output(mat):
    nodes = mat.node_tree.nodes
    return next((n for n in nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output), None) \
        or next(n for n in nodes if n.type == "OUTPUT_MATERIAL")


def _fill_empty_slots(me):
    """Boolean cuts leave faces in an empty material slot (the cutter's).
    Point them at the mesh's first real material so they bake."""
    mats = list(me.materials)
    real = next((i for i, m in enumerate(mats) if m is not None), None)
    if real is None or all(m is not None for m in mats):
        return
    for p in me.polygons:
        if mats[p.material_index] is None:
            p.material_index = real


def bake_ready_copy(name="GEO-export"):
    """One joined mesh with all modifiers applied, model objects untouched.

    Objects tagged with geo.part() (wheels, steering wheel, doors...) are
    remembered per face, so split_parts() can pull them back out as separate
    pivoted objects after baking (they still share the one texture atlas)."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    copies = []
    parts, pivots = ["body"], {}
    for obj in sc.model_objects():
        if obj.hide_render or obj.get("doodle_cutter"):
            continue
        me = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph),
                                             preserve_all_data_layers=True, depsgraph=depsgraph)
        _fill_empty_slots(me)
        part = obj.get("doodle_part", "body")
        if part not in parts:
            parts.append(part)
            pivots[part] = list(obj["doodle_pivot"])
        attr = me.attributes.new("doodle_part", "INT", "FACE")
        attr.data.foreach_set("value", [parts.index(part)] * len(me.polygons))
        cp = bpy.data.objects.new(obj.name + "_x", me)
        cp.matrix_world = obj.matrix_world.copy()
        bpy.context.scene.collection.objects.link(cp)
        copies.append(cp)
    if not copies:
        raise RuntimeError("nothing to export")
    _select_only(copies, copies[0])
    if len(copies) > 1:
        bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = name
    joined["doodle_parts"] = parts
    joined["doodle_pivots"] = json.dumps(pivots)
    bpy.ops.object.material_slot_remove_unused()
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    # Triangulate now so the baked normal map's tangent basis matches what
    # the engine computes (MikkTSpace on triangles).
    tri = joined.modifiers.new("Triangulate", "TRIANGULATE")
    tri.keep_custom_normals = True
    bpy.ops.object.modifier_apply(modifier=tri.name)
    return joined


def unwrap(obj, margin=0.004):
    _select_only([obj], obj)
    me = obj.data
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    me.uv_layers.new(name="UVMap")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=margin,
                             area_weight=0.0, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode="OBJECT")


def _bake_channel(obj, image, channel_input, samples):
    """Bake one Principled input to `image` via a temporary Emission rewire."""
    restore = []
    for mat in _materials(obj):
        b = _bsdf(mat)
        if b is None:
            continue
        nt = mat.node_tree
        out = _output(mat)
        old = out.inputs["Surface"].links[0].from_socket if out.inputs["Surface"].links else None
        emit = nt.nodes.new("ShaderNodeEmission")
        emit.inputs["Strength"].default_value = 1.0
        src = b.inputs[channel_input]
        if src.links:
            nt.links.new(src.links[0].from_socket, emit.inputs["Color"])
        else:
            v = src.default_value
            emit.inputs["Color"].default_value = tuple(v) if hasattr(v, "__len__") else (v, v, v, 1)
        if channel_input == "Emission Color" and b.inputs["Emission Strength"].default_value <= 0:
            emit.inputs["Color"].default_value = (0, 0, 0, 1)
            for link in list(emit.inputs["Color"].links):
                nt.links.remove(link)
        nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        nt.nodes.active = tex
        restore.append((mat, emit, tex, old, out))

    s = bpy.context.scene
    s.cycles.samples = samples
    s.render.bake.margin = 16
    s.render.bake.use_clear = True
    bpy.ops.object.bake(type="EMIT")

    for mat, emit, tex, old, out in restore:
        nt = mat.node_tree
        nt.nodes.remove(emit)
        nt.nodes.remove(tex)
        if old is not None:
            nt.links.new(old, out.inputs["Surface"])


def _bake_normal(obj, image, samples):
    added = []
    for mat in _materials(obj):
        if mat.node_tree is None:
            continue
        nt = mat.node_tree
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        nt.nodes.active = tex
        added.append((nt, tex))
    s = bpy.context.scene
    s.cycles.samples = samples
    s.render.bake.normal_space = "TANGENT"
    bpy.ops.object.bake(type="NORMAL")
    for nt, tex in added:
        nt.nodes.remove(tex)


def bake(obj, out_dir, size=2048, samples=32):
    """Bake all channels. Returns {channel: image}."""
    bpy.context.scene.render.engine = "CYCLES"
    bpy.context.scene.cycles.device = "CPU"
    _select_only([obj], obj)
    tex_dir = os.path.join(out_dir, "textures")
    os.makedirs(tex_dir, exist_ok=True)
    # Hide everything else: the originals overlap the copy and would make
    # AO / grime nodes read as fully occluded; the backdrop would too.
    hidden = [o for o in bpy.context.scene.objects if o is not obj and not o.hide_render]
    for o in hidden:
        o.hide_render = True
    images = {}
    has_emission = any((b := _bsdf(s.material)) is not None
                       and b.inputs["Emission Strength"].default_value > 0 for s in obj.material_slots)
    for name, inp, cs in CHANNELS + [("normal", None, "Non-Color")]:
        if name == "emission" and not has_emission:
            continue
        img = bpy.data.images.new(f"T_{obj.name}_{name}", size, size, alpha=False,
                                  float_buffer=(name == "normal"))
        img.colorspace_settings.name = cs
        if name == "normal":
            _bake_normal(obj, img, samples)
        else:
            _bake_channel(obj, img, inp, samples)
        img.filepath_raw = os.path.join(tex_dir, f"{name}.png")
        img.file_format = "PNG"
        img.save()
        images[name] = img
        print(f"baked:{name}")
    for o in hidden:
        o.hide_render = False
    return images


def baked_material(images, emission_strength=1.0, name="MAT-baked"):
    mat = bpy.data.materials.new(name)
    nt = mat.node_tree
    b = nt.nodes["Principled BSDF"]
    x = -500
    for i, (ch, inp) in enumerate([("basecolor", "Base Color"), ("metallic", "Metallic"),
                                   ("roughness", "Roughness"), ("emission", "Emission Color")]):
        if ch not in images:
            continue
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = images[ch]
        t.location = (x, 300 - i * 280)
        nt.links.new(t.outputs["Color"], b.inputs[inp])
    if "emission" in images:
        b.inputs["Emission Strength"].default_value = emission_strength
    if "normal" in images:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = images["normal"]
        t.location = (x, -900)
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.location = (-200, -900)
        nt.links.new(t.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    return mat


def _collapse_materials(obj, baked):
    """Replace every non-glass slot with `baked`: one material per glass
    type plus one baked atlas material -> as few draw calls as possible."""
    me = obj.data
    old = [s.material for s in obj.material_slots]
    keep = [baked] + list(dict.fromkeys(m for m in old if m is not None and _is_glass(m)))
    remap = [keep.index(m) if m in keep else 0 for m in old]
    idx = [0] * len(me.polygons)
    me.polygons.foreach_get("material_index", idx)
    me.materials.clear()
    for m in keep:
        me.materials.append(m)
    me.polygons.foreach_set("material_index", [remap[i] if i < len(remap) else 0 for i in idx])
    me.update()


def split_parts(obj):
    """Separate tagged parts (see bake_ready_copy) into their own objects named
    PART-<name>, each with its origin at the part's pivot so engines can spin
    or steer it. Returns the list of new objects."""
    from mathutils import Matrix, Vector
    parts = list(obj.get("doodle_parts", ["body"]))
    pivots = json.loads(obj.get("doodle_pivots", "{}"))
    attr = obj.data.attributes.get("doodle_part")
    if attr is None or len(parts) < 2:
        return []
    ids = [0] * len(obj.data.polygons)
    attr.data.foreach_get("value", ids)
    made = []
    for idx, part in enumerate(parts):
        if idx == 0 or idx not in ids:
            continue
        _select_only([obj], obj)
        me = obj.data
        me.polygons.foreach_set("select", [i == idx for i in ids])
        me.edges.foreach_set("select", [False] * len(me.edges))
        me.vertices.foreach_set("select", [False] * len(me.vertices))
        for poly in me.polygons:
            if poly.select:
                for v in poly.vertices:
                    me.vertices[v].select = True
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_mode(type="FACE")
        bpy.ops.mesh.separate(type="SELECTED")
        bpy.ops.object.mode_set(mode="OBJECT")
        new = next(o for o in bpy.context.selected_objects if o is not obj)
        new.name = f"PART-{part}"
        pivot = Vector(pivots[part])
        new.data.transform(Matrix.Translation(-pivot))
        new.location = pivot
        made.append(new)
        ids = [0] * len(obj.data.polygons)
        obj.data.attributes["doodle_part"].data.foreach_get("value", ids)
    print("parts:", ", ".join(o.name for o in made))
    return made


def bake_and_export(name, out_dir, size=2048, samples=32, formats=("glb", "fbx")):
    """Full pipeline. Writes <out_dir>/<name>.glb/.fbx and textures/*.png."""
    os.makedirs(out_dir, exist_ok=True)
    obj = bake_ready_copy(f"GEO-{name}")
    unwrap(obj)
    images = bake(obj, out_dir, size, samples)

    strengths = [b.inputs["Emission Strength"].default_value
                 for s in obj.material_slots if (b := _bsdf(s.material)) is not None]
    baked = baked_material(images, max(strengths + [1.0]), f"MAT-{name}")
    _collapse_materials(obj, baked)
    parts = split_parts(obj)
    cols = sc.colliders()
    _select_only([obj] + parts + cols, obj)

    tris = sum(len(p.vertices) - 2 for o in [obj] + parts for p in o.data.polygons)
    paths = {}
    if "glb" in formats:
        paths["glb"] = os.path.join(out_dir, f"{name}.glb")
        bpy.ops.export_scene.gltf(filepath=paths["glb"], export_format="GLB", use_selection=True,
                                  export_apply=True, export_yup=True, export_materials="EXPORT",
                                  export_image_format="AUTO", export_tangents=True)
    if "fbx" in formats:
        # Unreal picks up UCX_<mesh>_NN boxes as the mesh's simple collision.
        glb_names = [c.name for c in cols]
        for i, c in enumerate(cols):
            c.name = f"UCX_GEO-{name}_{i:02d}"
        paths["fbx"] = os.path.join(out_dir, f"{name}.fbx")
        bpy.ops.export_scene.fbx(filepath=paths["fbx"], use_selection=True, apply_unit_scale=True,
                                 apply_scale_options="FBX_SCALE_ALL", bake_space_transform=True,
                                 object_types={"MESH"}, use_mesh_modifiers=True,
                                 mesh_smooth_type="FACE", use_tspace=True,
                                 path_mode="COPY", embed_textures=True,
                                 axis_forward="-Z", axis_up="Y")
        for c, n in zip(cols, glb_names):
            c.name = n
    for k, p in paths.items():
        print(f"exported:{k} {p} {os.path.getsize(p) / 1e6:.2f}MB")
    print(f"export_stats: tris={tris} materials={len(obj.material_slots)} colliders={len(cols)}")
    return obj, paths, tris
