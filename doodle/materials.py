"""Procedural PBR materials (Principled BSDF, metal/roughness workflow).

All materials are built from nodes so they look rich in Cycles renders.
export.bake_and_export() bakes them down to image textures (base color,
metallic, roughness, normal, emission) so Unity / Unreal / Three.js get
standard PBR maps.

Wear and grime use Ambient Occlusion and Bevel nodes; both bake correctly.
"""

import bpy


def _new(name):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (300, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat, nt, bsdf


def _rgba(c):
    return (*c, 1.0) if len(c) == 3 else tuple(c)


def assign(obj, mat):
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return obj


def _noise(nt, scale=8.0, detail=8.0, roughness=0.6, coord="Object"):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = roughness
    nt.links.new(tc.outputs[coord], n.inputs["Vector"])
    return n


def _ramp(nt, src, stops):
    """Color ramp from a float socket. stops = [(pos, rgba_or_float), ...]."""
    r = nt.nodes.new("ShaderNodeValToRGB")
    els = r.color_ramp.elements
    while len(els) > len(stops):
        els.remove(els[-1])
    while len(els) < len(stops):
        els.new(0.5)
    for el, (pos, col) in zip(els, stops):
        el.position = pos
        el.color = _rgba(col) if isinstance(col, (tuple, list)) else (col, col, col, 1)
    nt.links.new(src, r.inputs["Fac"])
    return r


def _bump(nt, height_socket, strength=0.2, distance=0.01):
    b = nt.nodes.new("ShaderNodeBump")
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = distance
    nt.links.new(height_socket, b.inputs["Height"])
    return b


# --- simple materials ------------------------------------------------------

def plastic(name, color, roughness=0.4, coat=0.0):
    mat, nt, b = _new(name)
    b.inputs["Base Color"].default_value = _rgba(color)
    b.inputs["Roughness"].default_value = roughness
    b.inputs["Coat Weight"].default_value = coat
    return mat


def metal(name, color=(0.8, 0.8, 0.82), roughness=0.3, brushed=False):
    mat, nt, b = _new(name)
    b.inputs["Base Color"].default_value = _rgba(color)
    b.inputs["Metallic"].default_value = 1.0
    n = _noise(nt, scale=60 if brushed else 12, detail=10)
    if brushed:  # stretch noise along X for brushed streaks
        mapping = nt.nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (0.02, 1, 1)
        nt.links.new(n.inputs["Vector"].links[0].from_socket, mapping.inputs["Vector"])
        nt.links.new(mapping.outputs["Vector"], n.inputs["Vector"])
    r = _ramp(nt, n.outputs["Fac"], [(0.3, roughness * 0.7), (0.7, roughness * 1.3)])
    nt.links.new(r.outputs["Color"], b.inputs["Roughness"])
    nt.links.new(_bump(nt, n.outputs["Fac"], 0.05).outputs["Normal"], b.inputs["Normal"])
    return mat


def rubber(name, color=(0.02, 0.02, 0.02)):
    mat, nt, b = _new(name)
    b.inputs["Base Color"].default_value = _rgba(color)
    b.inputs["Roughness"].default_value = 0.85
    n = _noise(nt, scale=200, detail=4)
    nt.links.new(_bump(nt, n.outputs["Fac"], 0.08).outputs["Normal"], b.inputs["Normal"])
    return mat


def glass(name, color=(0.9, 0.95, 1.0), roughness=0.02):
    mat, nt, b = _new(name)
    b.inputs["Base Color"].default_value = _rgba(color)
    b.inputs["Roughness"].default_value = roughness
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = 1.45
    return mat


def emissive(name, color, strength=8.0):
    mat, nt, b = _new(name)
    b.inputs["Base Color"].default_value = _rgba(color)
    b.inputs["Emission Color"].default_value = _rgba(color)
    b.inputs["Emission Strength"].default_value = strength
    b.inputs["Roughness"].default_value = 0.3
    return mat


def wood(name, light=(0.45, 0.28, 0.14), dark=(0.2, 0.11, 0.05), scale=3.0):
    mat, nt, b = _new(name)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1, 1, 12)  # long grain along Z
    nt.links.new(tc.outputs["Object"], mapping.inputs["Vector"])
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "RINGS"
    wave.inputs["Scale"].default_value = scale
    wave.inputs["Distortion"].default_value = 6
    wave.inputs["Detail"].default_value = 4
    nt.links.new(mapping.outputs["Vector"], wave.inputs["Vector"])
    r = _ramp(nt, wave.outputs["Fac"], [(0.2, dark), (0.8, light)])
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.55
    nt.links.new(_bump(nt, wave.outputs["Fac"], 0.1).outputs["Normal"], b.inputs["Normal"])
    return mat


# --- the hero material: painted metal with edge wear + grime ---------------

def painted_metal(name, paint=(0.55, 0.32, 0.08), metal_color=(0.6, 0.6, 0.62),
                  wear=0.5, grime=0.5, paint_roughness=0.45, bands=None, band_top=1.0):
    """Painted steel: paint chips off sharp edges revealing bare metal,
    dirt collects in crevices (AO). `wear`/`grime` in 0..1.

    bands: optional livery by object-space height, e.g.
        [(0.0, red), (1.3, yellow), (1.8, red)] with band_top=3.1
    means red from z=0, yellow from z=1.3, red again from z=1.8 (meters).
    Object origin must sit at ground level for heights to line up."""
    mat, nt, b = _new(name)
    L = nt.links

    # Edge mask: difference between bevel-rounded normal and true normal.
    bev = nt.nodes.new("ShaderNodeBevel")
    bev.samples = 8
    bev.inputs["Radius"].default_value = 0.012
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    L.new(bev.outputs["Normal"], dot.inputs[0])
    L.new(geo.outputs["Normal"], dot.inputs[1])
    edge = nt.nodes.new("ShaderNodeMath")
    edge.operation = "SUBTRACT"
    edge.inputs[0].default_value = 1.0
    L.new(dot.outputs["Value"], edge.inputs[1])
    edge_gain = nt.nodes.new("ShaderNodeMath")
    edge_gain.operation = "MULTIPLY"
    edge_gain.inputs[1].default_value = 40.0
    L.new(edge.outputs["Value"], edge_gain.inputs[0])

    # Break up the edge mask with noise so chips look organic.
    chips = _noise(nt, scale=18, detail=12, roughness=0.7)
    mix_mask = nt.nodes.new("ShaderNodeMath")
    mix_mask.operation = "MULTIPLY"
    L.new(edge_gain.outputs["Value"], mix_mask.inputs[0])
    L.new(chips.outputs["Fac"], mix_mask.inputs[1])
    lo = 0.55 - 0.35 * wear
    wear_mask = _ramp(nt, mix_mask.outputs["Value"], [(lo, 0.0), (lo + 0.05, 1.0)])

    # Grime from ambient occlusion + large noise.
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.samples = 16
    ao.inputs["Distance"].default_value = 0.15
    grime_noise = _noise(nt, scale=3, detail=6)
    grime_mul = nt.nodes.new("ShaderNodeMath")
    grime_mul.operation = "MULTIPLY"
    inv_ao = nt.nodes.new("ShaderNodeMath")
    inv_ao.operation = "SUBTRACT"
    inv_ao.inputs[0].default_value = 1.0
    L.new(ao.outputs["AO"], inv_ao.inputs[1])
    L.new(inv_ao.outputs["Value"], grime_mul.inputs[0])
    L.new(grime_noise.outputs["Fac"], grime_mul.inputs[1])
    grime_mask = _ramp(nt, grime_mul.outputs["Value"], [(0.05, 0.0), (0.35, grime)])

    # Paint color with subtle variation, then grime darken.
    paint_var = _noise(nt, scale=6, detail=4)
    paint_col = _ramp(nt, paint_var.outputs["Fac"],
                      [(0.3, tuple(c * 0.85 for c in paint)), (0.7, paint)])
    if bands:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        L.new(tc.outputs["Object"], sep.inputs["Vector"])
        norm = nt.nodes.new("ShaderNodeMath")
        norm.operation = "DIVIDE"
        norm.inputs[1].default_value = band_top
        L.new(sep.outputs["Z"], norm.inputs[0])
        band = _ramp(nt, norm.outputs["Value"], [(z / band_top, c) for z, c in bands])
        band.color_ramp.interpolation = "CONSTANT"
        shade = _ramp(nt, paint_var.outputs["Fac"], [(0.3, 0.85), (0.7, 1.0)])
        var = nt.nodes.new("ShaderNodeMix")
        var.data_type = "RGBA"
        var.blend_type = "MULTIPLY"
        var.inputs["Factor"].default_value = 1.0
        L.new(band.outputs["Color"], var.inputs["A"])
        L.new(shade.outputs["Color"], var.inputs["B"])
        paint_col = var  # downstream reads paint_col.outputs["Color"]
    dirty = nt.nodes.new("ShaderNodeMix")
    dirty.data_type = "RGBA"
    dirty.blend_type = "MULTIPLY"
    dirty.inputs["B"].default_value = (0.25, 0.2, 0.15, 1)
    L.new(grime_mask.outputs["Color"], dirty.inputs["Factor"])
    L.new(paint_col.outputs["Result" if bands else "Color"], dirty.inputs["A"])

    # Final mixes: paint vs bare metal by wear mask.
    color = nt.nodes.new("ShaderNodeMix")
    color.data_type = "RGBA"
    L.new(wear_mask.outputs["Color"], color.inputs["Factor"])
    L.new(dirty.outputs["Result"], color.inputs["A"])
    color.inputs["B"].default_value = _rgba(metal_color)
    L.new(color.outputs["Result"], b.inputs["Base Color"])

    L.new(wear_mask.outputs["Color"], b.inputs["Metallic"])

    rough = nt.nodes.new("ShaderNodeMix")
    rough.data_type = "FLOAT"
    L.new(wear_mask.outputs["Color"], rough.inputs["Factor"])
    rough.inputs["A"].default_value = paint_roughness
    rough.inputs["B"].default_value = 0.25
    rough_g = nt.nodes.new("ShaderNodeMath")
    rough_g.operation = "ADD"
    L.new(rough.outputs["Result"], rough_g.inputs[0])
    L.new(grime_mask.outputs["Color"], rough_g.inputs[1])
    L.new(rough_g.outputs["Value"], b.inputs["Roughness"])

    # Chipped paint has a height step: bump from the wear mask.
    L.new(_bump(nt, wear_mask.outputs["Color"], 0.3, 0.002).outputs["Normal"], b.inputs["Normal"])
    return mat
