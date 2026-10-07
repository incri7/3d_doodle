"""Agni Express "Super Agni A/C VIP Sofa": a modern Nepali long-route coach.

References: docs/reference/images/agni_ref_{1,2,3}.png (user-supplied photos:
left side, rear, front/right). Route board: Kathmandu - Kakarbhitta.

Size (typical Nepali 2+1 sofa coach on an 11 m chassis): 11.0 m long,
2.6 m wide, 3.45 m tall, 5.8 m wheelbase, 1.06 m tyres.
Front faces -Y. Nepal drives on the left: the door is on the vehicle's
left, which is +X here (the side in agni_ref_1).

Decals (graphics, lettering) are thin extruded shapes just proud of the
body, so they bake into the texture atlas and export cleanly.
"""

import math

from doodle import geo, materials as M

LIGHTING = "studio"
HERO_AZIMUTH = 38   # front + door side, like agni_ref_1
HERO_ELEVATION = 8

L, W = 11.0, 2.6
Z0, Z1 = 0.40, 3.45          # body underside / roof
YF, YB = -L / 2, L / 2
WS_Z0 = 1.55                 # windshield bottom; the front rakes back above it
RAKE = 0.16                  # meters back per meter up (~9 degrees)
AXLE_F = YF + 2.35
AXLE_R = AXLE_F + 5.8
TYRE_R, TYRE_W = 0.53, 0.30
BAND_Z0, BAND_Z1 = 2.05, 3.10  # side glazing band
EPS = 0.004                  # decal offset from the body
R_FRONT, R_REAR = 0.45, 0.32  # plan-view corner radii (rounded coach corners)

PI = math.pi


def front_y(z):
    """Y of the front face at height z (vertical below WS_Z0, raked above)."""
    return YF + max(0.0, z - WS_Z0) * RAKE


def build():
    BODY.clear()
    mats = {
        "paint": M.painted_metal("MAT-white_paint", paint=(0.92, 0.92, 0.9), wear=0.08, grime=0.3,
                                 paint_roughness=0.16, metal_color=(0.7, 0.7, 0.72)),
        "glass": M.glass("MAT-tinted_glass", (0.11, 0.12, 0.13), roughness=0.03),
        "interior": M.plastic("MAT-interior_lining", (0.62, 0.56, 0.48), roughness=0.7),
        "fabric": M.plastic("MAT-seat_velvet", (0.32, 0.03, 0.05), roughness=0.9),
        "cover": M.plastic("MAT-headrest_cover", (0.92, 0.9, 0.86), roughness=0.85),
        "curtain": M.plastic("MAT-curtain_orange", (0.88, 0.36, 0.05), roughness=0.9),
        "floor": M.plastic("MAT-floor", (0.08, 0.08, 0.09), roughness=0.6),
        "led_blue": M.emissive("MAT-ceiling_led", (0.15, 0.35, 1.0), strength=3.0),
        "black": M.plastic("MAT-black_trim", (0.015, 0.015, 0.015), roughness=0.35),
        "red": M.plastic("MAT-red_graphic", (0.72, 0.02, 0.03), roughness=0.25, coat=0.5),
        "maroon": M.plastic("MAT-maroon_graphic", (0.22, 0.01, 0.015), roughness=0.3, coat=0.5),
        "navy": M.plastic("MAT-navy_lettering", (0.03, 0.06, 0.38), roughness=0.3, coat=0.5),
        "white": M.plastic("MAT-white_lettering", (0.95, 0.95, 0.95), roughness=0.3),
        "yellow": M.plastic("MAT-yellow_lettering", (0.98, 0.7, 0.02), roughness=0.3),
        "orange": M.plastic("MAT-orange_lettering", (0.95, 0.35, 0.02), roughness=0.3),
        "gold": M.metal("MAT-gold", color=(0.9, 0.65, 0.2), roughness=0.25),
        "chrome": M.metal("MAT-chrome", color=(0.92, 0.92, 0.94), roughness=0.1),
        "silver": M.metal("MAT-silver_wheel", color=(0.75, 0.76, 0.78), roughness=0.3),
        "tyre": M.rubber("MAT-tyre"),
        "lens": M.emissive("MAT-headlamp", (1.0, 0.97, 0.9), strength=1.2),
        "amber": M.emissive("MAT-amber_lamp", (1.0, 0.5, 0.02), strength=1.2),
        "led_red": M.emissive("MAT-red_led", (1.0, 0.03, 0.02), strength=3.0),
        "tail": M.emissive("MAT-tail_lamp", (0.85, 0.02, 0.02), strength=1.0),
    }
    _body(mats)
    _glazing(mats)
    _front(mats)
    _mirrors(mats)
    _side_graphics_door_side(mats)
    _side_graphics_driver_side(mats)
    _rear(mats)
    _wheels(mats)
    _roof(mats)
    _interior(mats)
    _tag_moving_parts()


# --- placement helpers ---------------------------------------------------------
# Every decal is drawn flat in world units, densified where the body curves,
# then projected onto the body (Shrinkwrap) and given thickness. So glass,
# graphics and lettering follow the rounded corners like a real wrap.

BODY = []  # [body object], set by _body()


def _steps(lo, hi, step=0.03):
    n = max(1, int((hi - lo) / step))
    return [lo + (hi - lo) * i / n for i in range(n + 1)]


def _project(o, axis, positive, depth, lift, xs=(), ys=(), zs=()):
    geo.apply_transform(o)
    for ax, pos in (("X", xs), ("Y", ys), ("Z", zs)):
        if pos:
            geo.densify(o, ax, pos)
    return geo.project_onto(o, BODY[0], axis, positive, offset=EPS + lift, thickness=depth)


def _front_cuts():
    hw = W / 2
    xs = _steps(hw - R_FRONT - 0.05, hw) + [-x for x in _steps(hw - R_FRONT - 0.05, hw)]
    zs = _steps(WS_Z0 - 0.06, WS_Z0 + 0.06, 0.02) + _steps(Z1 - 0.45, Z1) + _steps(Z0, Z0 + 0.2)
    return xs, zs


def _rear_cuts():
    hw = W / 2
    xs = _steps(hw - R_REAR - 0.05, hw) + [-x for x in _steps(hw - R_REAR - 0.05, hw)]
    zs = _steps(Z1 - 0.45, Z1) + _steps(Z0, Z0 + 0.2)
    return xs, zs


def _side_cuts():
    ys = _steps(YF, YF + R_FRONT + 0.4) + _steps(YB - R_REAR - 0.05, YB)
    zs = _steps(Z1 - 0.5, Z1) + _steps(Z0, Z0 + 0.2)
    return ys, zs


def on_side(name, contours, side, mat, depth=0.004, lift=0.0):
    """Shape on the +X (side=1) or -X (side=-1) flank. Contours are in world
    (y, z), so the same numbers mean the same spot on the bus."""
    if min(z for c in contours for _, z in c) < TYRE_R + 0.75:
        # Graphics never span the wheel openings: trim them out in 2D.
        holes = [[(ay + (TYRE_R + 0.14) * math.cos(a), TYRE_R + 0.02 + (TYRE_R + 0.14) * math.sin(a))
                  for a in [2 * PI * i / 48 for i in range(48)]] for ay in (AXLE_F, AXLE_R)]
        contours = geo.clip_contours(contours, holes)
        if not contours:
            return None
    local = [[(side * y, z) for y, z in c] for c in contours]
    o = geo.flat_shape(name, local, 0, (side * (W / 2 + 0.5), 0, 0), (PI / 2, 0, side * PI / 2))
    ys, zs = _side_cuts()
    _project(o, "X", side < 0, depth, lift, ys=ys, zs=zs)
    return M.assign(o, mat)


def side_text(name, body, side, y, z, size, mat, font="condensed", depth=0.004, lift=0.0, **kw):
    o = geo.text(name, body, size, 0, (side * (W / 2 + 0.5), y, z),
                 (PI / 2, 0, side * PI / 2), font=font, **kw)
    ys, zs = _side_cuts()
    _project(o, "X", side < 0, depth, lift, ys=ys, zs=zs)
    return M.assign(o, mat)


def on_front(name, contours, mat, depth=0.006, lift=0.0, z_hint=None):
    """Shape on the front (vertical below WS_Z0, raked above, rounded corners);
    contours in world (x, z)."""
    o = geo.flat_shape(name, contours, 0, (0, YF - 0.6, 0), (PI / 2, 0, 0))
    xs, zs = _front_cuts()
    _project(o, "Y", True, depth, lift, xs=xs, zs=zs)
    return M.assign(o, mat)


def front_text(name, body, x, z, size, mat, font="devanagari", depth=0.006, lift=0.0, **kw):
    o = geo.text(name, body, size, 0, (x, YF - 0.6, z), (PI / 2, 0, 0), font=font, **kw)
    xs, zs = _front_cuts()
    _project(o, "Y", True, depth, lift, xs=xs, zs=zs)
    return M.assign(o, mat)


def on_rear(name, contours, mat, depth=0.006, lift=0.0):
    """Shape on the back face; contours in world (x, z)."""
    local = [[(-x, z) for x, z in c] for c in contours]
    o = geo.flat_shape(name, local, 0, (0, YB + 0.6, 0), (PI / 2, 0, PI))
    xs, zs = _rear_cuts()
    _project(o, "Y", False, depth, lift, xs=xs, zs=zs)
    return M.assign(o, mat)


def rear_text(name, body, x, z, size, mat, font="devanagari", depth=0.006, lift=0.0, **kw):
    o = geo.text(name, body, size, 0, (x, YB + 0.6, z), (PI / 2, 0, PI), font=font, **kw)
    xs, zs = _rear_cuts()
    _project(o, "Y", False, depth, lift, xs=xs, zs=zs)
    return M.assign(o, mat)


def rect(x0, z0, x1, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


def rounded_rect(x0, z0, x1, z1, r, steps=5):
    pts = []
    for cx, cz, a0 in ((x1 - r, z0 + r, -PI / 2), (x1 - r, z1 - r, 0), (x0 + r, z1 - r, PI / 2),
                       (x0 + r, z0 + r, PI)):
        for i in range(steps + 1):
            a = a0 + (PI / 2) * i / steps
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return pts


def circle(cx, cz, r, n=24):
    return [(cx + r * math.cos(2 * PI * i / n), cz + r * math.sin(2 * PI * i / n)) for i in range(n)]


def stroke(p0, p1, width):
    """Straight band from p0 to p1 with the given width (graphic stripes)."""
    dx, dz = p1[0] - p0[0], p1[1] - p0[1]
    n = math.hypot(dx, dz)
    ox, oz = -dz / n * width / 2, dx / n * width / 2
    return [(p0[0] + ox, p0[1] + oz), (p1[0] + ox, p1[1] + oz),
            (p1[0] - ox, p1[1] - oz), (p0[0] - ox, p0[1] - oz)]


# --- body -------------------------------------------------------------------------

def _body(m):
    import bpy
    hw = W / 2
    prof = geo.rounded_rect_profile(W, Z0, Z1, radius=0.38, steps=8)
    # Add vertices at the windshield line so the front can rake above it.
    prof = prof[:2] + [(hw, WS_Z0)] + prof[2:] + [(-hw, WS_Z0)]
    body = geo.profile_prism("GEO-coach_body", prof, YF, YB)
    for v in body.data.vertices:
        if abs(v.co.y - YF) < 1e-6 and v.co.z > WS_Z0:
            v.co.y = front_y(v.co.z)
    # The front cap is now bent at WS_Z0: split it into two planar faces.
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(body.data)
    knee = [v for v in bm.verts if abs(v.co.y - YF) < 1e-6 and abs(v.co.z - WS_Z0) < 1e-6]
    bmesh.ops.connect_verts(bm, verts=knee)
    bm.to_mesh(body.data)
    bm.free()
    # Big plan-view radii on the vertical corners (bevel weights select them),
    # then the general edge rounding.
    me = body.data
    weight = me.attributes.new("bevel_weight_edge", "FLOAT", "EDGE")
    for e in me.edges:
        a, b = (me.vertices[i].co for i in e.vertices)
        if abs(abs(a.x) - hw) < 1e-6 and abs(abs(b.x) - hw) < 1e-6:
            if abs(a.y - front_y(a.z)) < 1e-6 and abs(b.y - front_y(b.z)) < 1e-6:
                weight.data[e.index].value = 1.0
            elif abs(a.y - YB) < 1e-6 and abs(b.y - YB) < 1e-6:
                weight.data[e.index].value = R_REAR / R_FRONT
    corners = body.modifiers.new("BevelCorners", "BEVEL")
    corners.limit_method = "WEIGHT"
    corners.width = R_FRONT
    corners.segments = 12
    corners.harden_normals = False
    geo.bevel(body, width=0.13, segments=5, angle=50, harden=False).name = "BevelBig"
    for y in (AXLE_F, AXLE_R):
        arch = geo.cylinder("CUT-arch", TYRE_R + 0.1, W + 1, 40, (0, y, TYRE_R + 0.02))
        arch.rotation_euler = (0, PI / 2, 0)
        geo.cut(body, arch, material=m["black"])
    M.assign(body, m["paint"])
    body.data.materials.append(m["interior"])

    # Glass and graphics are projected onto the closed outer skin: a hidden
    # copy taken before the window openings are cut.
    target = body.copy()
    target.name = "CUT-projection_skin"
    bpy.context.scene.collection.objects.link(target)
    target.hide_render = True
    target.display_type = "WIRE"
    target["doodle_cutter"] = True
    BODY.append(target)

    # Hollow shell (inner faces use the lining material), then real openings.
    shell = body.modifiers.new("Shell", "SOLIDIFY")
    shell.thickness = 0.04
    shell.offset = -1.0
    shell.material_offset = 1
    shell.material_offset_rim = 1
    for side in (-1, 1):
        y0 = YF + (1.3 if side > 0 else 0.62) + 0.05
        cut = geo.box("CUT-window_band", (0.5, YB - 0.25 - y0, BAND_Z1 - BAND_Z0 - 0.08),
                      (side * W / 2, (y0 + YB - 0.25) / 2, (BAND_Z0 + BAND_Z1) / 2))
        geo.cut(body, cut)
    door = geo.box("CUT-door", (0.5, 0.62, BAND_Z1 - 0.7), (W / 2, YF + 0.86, (0.66 + BAND_Z1 - 0.04) / 2))
    geo.cut(body, door)
    zt = Z1 - 0.3
    ws = geo.box("CUT-windshield", (2.4, 1.0, zt - WS_Z0 - 0.14), (0, YF - 0.05, (WS_Z0 + 0.14 + zt) / 2))
    geo.cut(body, ws)
    geo.finish_hard_surface(body, bevel_width=0.008, segments=2, angle=40)
    # Arch cut faces got MAT-black_trim (liner); body keeps white in slot 0.


def _glazing(m):
    g, blk = m["glass"], m["black"]
    for side in (-1, 1):
        # +X: door ahead of the band; -X: the driver's window wraps from the corner.
        y0 = YF + (1.3 if side > 0 else 0.62)
        on_side("GEO-side_glass", [rect(y0, BAND_Z0, YB - 0.2, BAND_Z1)], side, g, depth=0.008)
    # Door on +X: tall dark glazed door just behind the corner.
    on_side("GEO-door", [rounded_rect(YF + 0.5, 0.6, YF + 1.22, BAND_Z1, 0.05)], 1, g, depth=0.008)
    # Windshield: wraps around the rounded front corners, black frame border.
    zt = Z1 - 0.2
    on_front("GEO-windshield_frame", [rounded_rect(-1.29, WS_Z0 + 0.02, 1.29, zt, 0.12),
                                       rounded_rect(-1.24, WS_Z0 + 0.1, 1.24, zt - 0.06, 0.1)], blk,
             depth=0.008)
    on_front("GEO-windshield", [rounded_rect(-1.24, WS_Z0 + 0.1, 1.24, zt - 0.06, 0.1)], g,
             depth=0.008, lift=0.004)


# --- front ------------------------------------------------------------------------

def _front(m):
    zt = Z1 - 0.26
    # Header band behind the glass top: big white AGNI, orange rule beneath.
    on_front("GEO-ws_header", [rect(-1.12, zt - 0.42, 1.12, zt)], m["black"], lift=0.008,
             z_hint=zt - 0.21)
    front_text("GEO-ws_agni", "AGNI", 0, zt - 0.2, 0.44, m["white"], font="black", lift=0.012,
               tracking=0.12)
    on_front("GEO-ws_rule", [rect(-0.95, zt - 0.47, 0.95, zt - 0.44)], m["orange"], lift=0.008,
             z_hint=zt - 0.45)
    # Route band at the bottom of the windshield.
    zb = WS_Z0 + 0.18
    on_front("GEO-ws_route_band", [rect(-1.12, WS_Z0 + 0.1, 1.12, WS_Z0 + 0.27)], m["black"],
             lift=0.008, z_hint=zb)
    front_text("GEO-route_from", "काठमाण्डौ", -0.68, zb, 0.15, m["white"], lift=0.012)
    front_text("GEO-route_to", "काँकडभिट्टा", 0.68, zb, 0.15, m["white"], lift=0.012)
    star = [(0.09 * math.cos(PI / 2 + i * PI / 5) * (1 if i % 2 == 0 else 0.45),
             zb + 0.09 * math.sin(PI / 2 + i * PI / 5) * (1 if i % 2 == 0 else 0.45))
            for i in range(10)]
    on_front("GEO-route_star", [star], m["gold"], lift=0.012, z_hint=zb)

    # Red LED strip arching under the windshield.
    arc_top = [(x, 1.47 - 0.05 * (x / 1.05) ** 2) for x in [i / 10 * 2.1 - 1.05 for i in range(11)]]
    arc = arc_top + [(x, z - 0.035) for x, z in reversed(arc_top)]
    on_front("GEO-led_strip", [arc], m["led_red"], z_hint=1.3)

    # Grille slot with a diagonal chrome badge.
    slot = rounded_rect(-0.95, 1.16, 0.95, 1.36, 0.06)
    on_front("GEO-grille", [slot], m["black"], z_hint=1.0)
    badge = circle(0, 1.26, 0.065)
    on_front("GEO-badge", [badge], m["chrome"], lift=0.006, z_hint=1.0)
    on_front("GEO-badge_bar", [stroke((-0.55, 1.19), (0.55, 1.33), 0.022)], m["chrome"], lift=0.005,
             z_hint=1.0)
    # Faint panel crease: the lower bumper section.
    on_front("GEO-crease", [rect(-1.15, 1.06, 1.15, 1.075)], m["black"], depth=0.002, z_hint=1.0)

    for sx in (-1, 1):
        # Headlamp: black trapezoid housing with two round projectors.
        hx = sx * 1.08
        house = [(hx - sx * 0.12, 0.8), (hx + sx * 0.1, 0.83), (hx + sx * 0.11, 1.05),
                 (hx - sx * 0.1, 1.03)]
        if sx < 0:
            house = house[::-1]
        on_front("GEO-headlamp_housing", [house], m["black"], depth=0.02, z_hint=1.0)
        for z in (0.88, 0.98):
            on_front("GEO-projector_ring", [circle(hx, z, 0.042)], m["chrome"], depth=0.01,
                     lift=0.012, z_hint=1.0)
            on_front("GEO-projector", [circle(hx, z, 0.03)], m["lens"], depth=0.01, lift=0.016,
                     z_hint=1.0)
        on_front("GEO-drl", [rect(hx - 0.07, 1.035, hx + 0.07, 1.05)], m["lens"], lift=0.012,
                 z_hint=1.0)
        # Amber corner lamp in a black pod.
        on_front("GEO-corner_pod", [rounded_rect(sx * 1.17 - 0.09, 0.5, sx * 1.17 + 0.09, 0.62, 0.05)],
                 m["black"], depth=0.015, z_hint=1.0)
        on_front("GEO-corner_lamp", [circle(sx * 1.17, 0.56, 0.035)], m["amber"], lift=0.01,
                 z_hint=1.0)
        # Bumper: red wedge ends, fog lamps, small parking lights.
        wedge = [(sx * 0.88, 0.8), (sx * 1.0, 0.8), (sx * 0.93, 0.68), (sx * 0.84, 0.66)]
        if sx < 0:
            wedge = wedge[::-1]
        on_front("GEO-bumper_wedge", [wedge], m["red"], lift=0.004, z_hint=1.0)
        on_front("GEO-fog_pod", [rounded_rect(sx * 0.55 - 0.1, 0.5, sx * 0.55 + 0.1, 0.72, 0.04)],
                 m["black"], depth=0.02, z_hint=1.0)
        on_front("GEO-fog_lamp", [circle(sx * 0.55, 0.61, 0.07)], m["lens"], depth=0.01, lift=0.014,
                 z_hint=1.0)
        on_front("GEO-park_lamp", [rounded_rect(sx * 0.55 - 0.05, 0.76, sx * 0.55 + 0.05, 0.8, 0.015)],
                 m["lens"], lift=0.004, z_hint=1.0)
    on_front("GEO-bumper_band", [rect(-0.86, 0.66, 0.86, 0.8)], m["black"], z_hint=1.0)
    # Number plate (Nepal embossed plate: province line + number).
    on_front("GEO-plate", [rounded_rect(-0.3, 0.5, 0.3, 0.66, 0.015)], m["black"], depth=0.01,
             lift=0.006, z_hint=1.0)
    front_text("GEO-plate_province", "कोशी प्रदेश", 0, 0.625, 0.045, m["white"], lift=0.012)
    front_text("GEO-plate_number", "०१-००२ ख ५५४४", 0, 0.56, 0.07, m["white"], lift=0.012)

    # Wipers parked at the bottom of the windshield, both leaning left.
    for px in (-0.55, 0.45):
        z = WS_Z0 + 0.35
        blade = geo.box("GEO-wiper", (0.75, 0.012, 0.02), (px - 0.25, front_y(z) - 0.02, z))
        blade.rotation_euler = (-math.atan(RAKE), -0.35, 0)
        M.assign(blade, m["black"])
    # Roof marker lamps on the front cap.
    for sx in (-0.85, -0.3, 0.3, 0.85):
        lamp = geo.sphere("GEO-marker", 0.03, 12, 6, (sx, front_y(Z1 - 0.12) + 0.03, Z1 - 0.08))
        M.assign(lamp, m["led_red"])


def _mirrors(m):
    """Rabbit-ear mirrors hanging from the roof corners."""
    for sx in (-1, 1):
        root = (sx * 1.2, front_y(Z1 - 0.15) + 0.05, Z1 - 0.12)
        arm = geo.tube("GEO-mirror_arm", [root, (sx * 1.38, root[1] - 0.25, Z1 - 0.1),
                                           (sx * 1.44, YF - 0.42, Z1 - 0.35),
                                           (sx * 1.41, YF - 0.5, 2.85)], radius=0.032)
        M.assign(arm, m["black"])
        head = geo.box("GEO-mirror_head", (0.24, 0.1, 0.58), (sx * 1.40, YF - 0.52, 2.55))
        head.rotation_euler = (0.05, 0, sx * 0.25)
        geo.bevel(head, 0.035, 4, 30, harden=False)
        geo.smooth(head, 40)
        M.assign(head, m["black"])
        chev = geo.flat_shape("GEO-mirror_chevron",
                              [[(-0.03, 0.06), (0.03, 0.0), (-0.03, -0.06), (-0.01, 0.0)]], 0.004,
                              (sx * 1.52, YF - 0.55, 2.6), (PI / 2, 0, sx * PI / 2 + sx * 0.25))
        M.assign(chev, m["amber"])


# --- side graphics -------------------------------------------------------------------

def _wave_top():
    """Top edge of the red swoosh on the door side, rear to front (y, z)."""
    pts = [(YB - 0.14, 2.0)]
    pts += geo.bezier((YB - 0.14, 2.0), (YB - 0.9, 1.98), (AXLE_R + 0.5, 1.45), (AXLE_R - 0.9, 1.12))
    pts += geo.bezier((AXLE_R - 0.9, 1.12), (AXLE_R - 2.4, 0.82), (AXLE_F + 2.0, 0.8),
                      (AXLE_F + 0.95, 0.95))
    pts += geo.bezier((AXLE_F + 0.95, 0.9), (AXLE_F + 0.75, 0.95), (AXLE_F + 0.68, 0.75),
                      (AXLE_F + 0.7, 0.55), 8)
    return pts


def _side_graphics_door_side(m):
    s = 1
    top = _wave_top()
    red = top + [(YB - 0.14, 0.53)]
    on_side("GEO-swoosh_red", [red], s, m["red"])
    # White pinstripe gap and a thin red line following the wave at the rear.
    follow = [(y, z + 0.13) for y, z in top[:14]]
    on_side("GEO-swoosh_line", [follow + [(y, z - 0.035) for y, z in reversed(follow)]], s, m["red"])
    # Maroon brush strokes and white slashes across the rear red section.
    for (a, b, w) in [((AXLE_R + 0.5, 0.6), (YB - 0.45, 1.9), 0.16),
                      ((AXLE_R + 1.15, 0.6), (YB - 0.2, 1.35), 0.1)]:
        on_side("GEO-swoosh_stroke", [stroke(a, b, w)], s, m["maroon"], lift=0.002)
    for (a, b) in [((AXLE_R + 0.15, 0.55), (YB - 0.75, 1.98)), ((AXLE_R + 0.35, 0.55), (YB - 0.55, 1.98))]:
        on_side("GEO-swoosh_slash", [stroke(a, b, 0.04)], s, m["white"], lift=0.003)
    # AGNI <logo> EXPRESS
    side_text("GEO-agni", "AGNI", s, -0.55, 1.72, 0.42, m["navy"], font="italic")
    on_side("GEO-agni_logo", [circle(0.15, 1.73, 0.1, 16)], s, m["red"])
    side_text("GEO-express", "EXPRESS", s, 1.15, 1.72, 0.42, m["navy"], font="italic")
    # Lettering on the glazing band.
    side_text("GEO-band_text", "SUPER AGNI A/C VIP SOFA", s, 0.4, 2.82, 0.5, m["white"], depth=0.016)
    on_side("GEO-heater_box", [rect(YB - 1.05, 2.66, YB - 0.25, 2.98)], s, m["yellow"], depth=0.016)
    side_text("GEO-heater", "HEATER", s, YB - 0.65, 2.82, 0.26, m["red"], depth=0.01, lift=0.01)
    on_side("GEO-door_emblem", [circle(YF + 1.3, 1.75, 0.08)], s, m["red"])
    _side_markers(m, s)


def _side_graphics_driver_side(m):
    s = -1
    # Red block at the rear top, under the glazing.
    block = [(YB - 0.14, 2.0), (YB - 2.1, 2.0), (YB - 1.3, 1.3), (YB - 0.14, 1.1)]
    on_side("GEO-red_block", [block], s, m["red"])
    # Mountain zigzag lines running toward the front wheel.
    peaks = [(YB - 0.14, 1.05), (YB - 0.9, 1.62), (YB - 1.6, 0.9), (AXLE_R - 0.4, 1.45),
             (AXLE_R - 1.4, 0.75), (AXLE_R - 2.3, 1.2), (AXLE_R - 3.2, 0.6)]
    for a, b in zip(peaks, peaks[1:]):
        on_side("GEO-mountain", [stroke(a, b, 0.08)], s, m["red"], lift=0.001)
    low = [(y, z - 0.3) for y, z in peaks]
    for a, b in zip(low, low[1:]):
        if min(a[1], b[1]) > 0.56:
            on_side("GEO-mountain_low", [stroke(a, b, 0.04)], s, m["red"], lift=0.001)
    big = [(AXLE_R - 2.4, 0.55), (AXLE_R - 1.4, 1.3), (AXLE_R - 0.5, 0.55)]
    on_side("GEO-mountain_fill", [big], s, m["red"])
    # Red outline hugging the front wheel arch.
    r0, r1 = TYRE_R + 0.12, TYRE_R + 0.2
    ring = [(AXLE_F + r1 * math.cos(a), TYRE_R + 0.02 + r1 * math.sin(a))
            for a in [i / 16 * PI for i in range(17)]]
    ring += [(AXLE_F + r0 * math.cos(a), TYRE_R + 0.02 + r0 * math.sin(a))
             for a in [PI - i / 16 * PI for i in range(17)]]
    on_side("GEO-arch_outline", [[(y, max(z, 0.53)) for y, z in ring]], s, m["red"])
    # AGNI with red underline rules.
    side_text("GEO-agni_r", "AGNI", s, AXLE_F + 1.9, 1.72, 0.48, m["navy"], font="italic")
    for i in range(3):
        on_side("GEO-agni_rule", [rect(AXLE_F + 1.35, 1.46 - i * 0.05, AXLE_F + 2.45, 1.475 - i * 0.05)],
                s, m["red"])
    # Glazing band lettering.
    side_text("GEO-band_super", "SUPER AGNI", s, 2.7, 2.82, 0.5, m["orange"], depth=0.016)
    side_text("GEO-band_air", "AIR SUSPENSION", s, -0.9, 2.82, 0.5, m["white"], depth=0.016)
    _side_markers(m, s)


def _side_markers(m, s):
    for y in (AXLE_F + 1.2, AXLE_F + 2.6, AXLE_F + 4.0, AXLE_R + 1.2, AXLE_R + 2.2):
        on_side("GEO-side_marker", [rounded_rect(y - 0.03, 0.6, y + 0.03, 0.66, 0.01)], s, m["amber"],
                lift=0.003)


# --- rear -------------------------------------------------------------------------

def _rear(m):
    # Upper black glass with the lit AGNI sign and an LED row.
    on_rear("GEO-rear_glass", [rounded_rect(-1.15, 2.35, 1.15, Z1 - 0.2, 0.1)], m["glass"])
    rear_text("GEO-rear_agni", "AGNI", 0.12, 2.92, 0.42, m["yellow"], font="black", lift=0.004)
    logo = [(-0.78 + 0.16 * math.cos(a), 2.95 + 0.08 * math.sin(a)) for a in
            [2 * PI * i / 24 for i in range(24)]]
    on_rear("GEO-rear_logo", [logo], m["red"], lift=0.004)
    for i in range(9):
        x = -0.9 + i * 0.225
        on_rear("GEO-rear_led", [circle(x, 2.5, 0.04, 12)], m["lens"], lift=0.004)
    # White cap: third brake light and slogan.
    for dx in (-0.08, 0, 0.08):
        on_rear("GEO-brake_dot", [circle(dx, 2.22, 0.025, 10)], m["led_red"])
    rear_text("GEO-rear_slogan", "आमाको आशीर्वाद", 0, 2.05, 0.15, m["red"])
    # Red eyebrow stripe with a white lamp strip in the middle.
    brow = geo.bezier((-1.25, 1.9), (-0.8, 1.86), (-0.6, 1.72), (-0.3, 1.72), 8)
    brow = brow + [(-x, z) for x, z in reversed(brow)]
    brow_low = [(x, z - 0.16) for x, z in reversed(brow)]
    on_rear("GEO-rear_brow", [brow + brow_low], m["red"])
    on_rear("GEO-rear_lamp_strip", [rounded_rect(-0.34, 1.62, 0.34, 1.7, 0.03)], m["white"], lift=0.003)
    # Engine hatch outline and the deity art (Om glyph stands in for Ganesh).
    outer = rounded_rect(-0.95, 0.82, 0.95, 1.6, 0.08)
    inner = rounded_rect(-0.935, 0.835, 0.935, 1.585, 0.07)
    on_rear("GEO-hatch_seam", [outer, inner], m["black"], depth=0.003)
    rear_text("GEO-rear_om", "ॐ", 0, 1.25, 0.42, m["red"], depth=0.004)
    on_rear("GEO-hatch_badge", [rounded_rect(-0.06, 0.9, 0.06, 0.95, 0.02)], m["chrome"])
    # Tail lamps: tall red clusters on the rear corners.
    for sx in (-1, 1):
        x = sx * 1.08
        on_rear("GEO-tail_housing", [rounded_rect(x - 0.11, 0.85, x + 0.11, 1.62, 0.06)], m["black"],
                depth=0.03)
        on_rear("GEO-tail_lens", [rounded_rect(x - 0.08, 1.05, x + 0.08, 1.58, 0.05)], m["tail"],
                depth=0.01, lift=0.02)
        on_rear("GEO-tail_bulb", [circle(x, 1.3, 0.04)], m["led_red"], depth=0.01, lift=0.026)
        on_rear("GEO-reverse_lamp", [rounded_rect(x - 0.08, 0.9, x + 0.08, 1.02, 0.03)], m["lens"],
                depth=0.01, lift=0.02)
        on_rear("GEO-reflector", [circle(sx * 1.12, 0.52, 0.045)], m["led_red"], lift=0.01)
    # Plate and bumper.
    on_rear("GEO-rear_plate", [rounded_rect(-0.3, 0.6, 0.3, 0.76, 0.015)], m["black"], depth=0.01)
    rear_text("GEO-rear_plate_province", "कोशी प्रदेश", 0, 0.725, 0.045, m["white"], lift=0.006)
    rear_text("GEO-rear_plate_number", "०१-००२ ख ५५४४", 0, 0.66, 0.07, m["white"], lift=0.006)
    bumper = geo.box("GEO-rear_bumper", (W - 0.2, 0.08, 0.14), (0, YB + 0.03, 0.5))
    geo.finish_hard_surface(bumper, 0.03, 3)
    M.assign(bumper, m["black"])


# --- wheels and roof -------------------------------------------------------------------

def _wheel(name, x, y, m, outward):
    tyre = geo.cylinder(f"GEO-{name}_tyre", TYRE_R, TYRE_W, 48, (x, y, TYRE_R))
    tyre.rotation_euler = (0, PI / 2, 0)
    geo.bevel(tyre, 0.08, 5, 30, harden=False)
    geo.smooth(tyre, 60)
    M.assign(tyre, m["tyre"])
    disc = geo.cylinder(f"GEO-{name}_rim", 0.29, TYRE_W + 0.02, 40, (x, y, TYRE_R))
    disc.rotation_euler = (0, PI / 2, 0)
    geo.finish_hard_surface(disc, 0.015)
    M.assign(disc, m["silver"])
    if outward:
        face = x + outward * (TYRE_W / 2 + 0.012)
        # Ventilation holes ring + chrome hub cap + nuts.
        for i in range(8):
            a = 2 * PI * i / 8 + PI / 8
            hole = geo.cylinder(f"GEO-{name}_vent", 0.04, 0.01, 12,
                                (face, y + 0.21 * math.cos(a), TYRE_R + 0.21 * math.sin(a)))
            hole.rotation_euler = (0, PI / 2, 0)
            M.assign(hole, m["black"])
        hub = geo.cylinder(f"GEO-{name}_hub", 0.12, 0.08, 32, (face + outward * 0.03, y, TYRE_R))
        hub.rotation_euler = (0, PI / 2, 0)
        geo.finish_hard_surface(hub, 0.02, 3)
        M.assign(hub, m["chrome"])
        for i in range(10):
            a = 2 * PI * i / 10
            nut = geo.cylinder(f"GEO-{name}_nut", 0.016, 0.04, 6,
                               (face + outward * 0.01, y + 0.15 * math.cos(a), TYRE_R + 0.15 * math.sin(a)))
            nut.rotation_euler = (0, PI / 2, 0)
            M.assign(nut, m["chrome"])


def _wheels(m):
    for sx in (-1, 1):
        k = "l" if sx > 0 else "r"
        _wheel(f"wheel_f{k}", sx * 1.0, AXLE_F, m, sx)
        _wheel(f"wheel_ri{k}", sx * 0.78, AXLE_R, m, 0)
        _wheel(f"wheel_ro{k}", sx * 1.1, AXLE_R, m, sx)
    under = geo.box("GEO-underbody", (W - 0.4, L - 1.0, 0.25), (0, 0, Z0 - 0.08))
    M.assign(under, m["black"])
    for y in (AXLE_F, AXLE_R):
        axle = geo.cylinder("GEO-axle", 0.07, 2.0, 16, (0, y, TYRE_R))
        axle.rotation_euler = (0, PI / 2, 0)
        M.assign(axle, m["black"])


def _roof(m):
    ac = geo.box("GEO-roof_ac", (1.7, 3.0, 0.2), (0, -1.6, Z1 + 0.08))
    geo.bevel(ac, 0.08, 5, 30, harden=False)
    geo.finish_hard_surface(ac, 0.01)
    M.assign(ac, m["paint"])
    for i in range(3):
        grille = geo.box("GEO-ac_vent", (1.2, 0.5, 0.01), (0, -2.6 + i * 0.95, Z1 + 0.185))
        M.assign(grille, m["black"])
    hatch = geo.box("GEO-roof_hatch", (0.8, 0.8, 0.08), (0, 2.2, Z1 + 0.02))
    geo.finish_hard_surface(hatch, 0.02)
    M.assign(hatch, m["paint"])


# --- interior (seen through the glass) ------------------------------------------------

FLOOR = 1.2  # high-deck coach floor height


def _soft_box(name, size, loc, mat, rot=(0, 0, 0), bevel=0.04):
    o = geo.box(name, size, loc)
    o.rotation_euler = rot
    geo.bevel(o, bevel, 3, 30, harden=False)
    geo.smooth(o, 60)
    return M.assign(o, mat)


def _seat(name, x, y, width, m):
    """Sofa seat facing forward (-Y): velvet cushion and backrest, white
    headrest cover (a Nepali bus staple), armrests, pedestal."""
    _soft_box(f"GEO-{name}_base", (width - 0.12, 0.4, 0.32), (x, y, FLOOR + 0.18), m["floor"], bevel=0.02)
    _soft_box(f"GEO-{name}_cushion", (width, 0.56, 0.15), (x, y - 0.02, FLOOR + 0.42), m["fabric"])
    back_y, back_z = y + 0.27, FLOOR + 0.86
    _soft_box(f"GEO-{name}_back", (width, 0.15, 0.78), (x, back_y, back_z), m["fabric"], rot=(-0.2, 0, 0))
    _soft_box(f"GEO-{name}_cover", (width - 0.08, 0.17, 0.26), (x, back_y + 0.06, back_z + 0.3),
              m["cover"], rot=(-0.2, 0, 0), bevel=0.03)
    for dx in (-width / 2, width / 2):
        _soft_box(f"GEO-{name}_arm", (0.06, 0.48, 0.05), (x + dx, y, FLOOR + 0.66), m["black"], bevel=0.02)


def _interior(m):
    hw = W / 2 - 0.04  # inner wall
    floor = geo.box("GEO-floor", (W - 0.1, L - 0.6, 0.05), (0, 0, FLOOR - 0.025))
    M.assign(floor, m["floor"])
    # 2+1 sofa layout: doubles on the driver's side (-X), singles on the door side.
    y = YF + 1.95
    i = 0
    while y < YB - 0.6:
        _seat(f"seat_{i}_d", -(hw - 0.08 - 0.5), y, 1.0, m)
        _seat(f"seat_{i}_s", hw - 0.08 - 0.28, y, 0.56, m)
        y += 0.95
        i += 1
    # Pleated orange curtains tied back between windows, valance on top.
    for side in (-1, 1):
        y0 = YF + (1.35 if side > 0 else 0.7)
        yy = y0
        while yy < YB - 0.3:
            c = geo.cylinder("GEO-curtain_tie", 0.11, BAND_Z1 - BAND_Z0 - 0.1, 16,
                             (side * (hw - 0.1), yy, (BAND_Z0 + BAND_Z1) / 2 - 0.02))
            c.scale = (0.55, 1.0, 1.0)
            geo.smooth(c)
            M.assign(c, m["curtain"])
            yy += 1.15
        val = geo.box("GEO-valance", (0.03, YB - 0.3 - y0, 0.16),
                      (side * (hw - 0.05), (y0 + YB - 0.3) / 2, BAND_Z1 - 0.12))
        M.assign(val, m["curtain"])
        rack = geo.box("GEO-luggage_rack", (0.38, L - 2.6, 0.04), (side * (hw - 0.22), 0.4, BAND_Z1 + 0.06))
        geo.finish_hard_surface(rack, 0.01)
        M.assign(rack, m["black"])
        led = geo.box("GEO-ceiling_led", (0.05, L - 2.4, 0.012), (side * 0.42, 0.4, Z1 - 0.07))
        M.assign(led, m["led_blue"])
    # Cabin light (render only; lights don't export): daylight spill inside.
    import bpy
    lamp = bpy.data.lights.new("LGT-cabin", "AREA")
    lamp.shape = "RECTANGLE"
    lamp.size, lamp.size_y = 1.2, L - 2.0
    lamp.energy = 350
    lamp.color = (1.0, 0.93, 0.85)
    lo = bpy.data.objects.new("LGT-cabin", lamp)
    lo.location = (0, 0.3, Z1 - 0.12)
    bpy.context.scene.collection.objects.link(lo)
    # Driver area (right-hand drive: driver on -X). Dashboard with fringed cloth.
    dash_y = YF + 0.5
    dash = geo.box("GEO-dashboard", (W - 0.25, 0.5, 0.38), (0, dash_y, FLOOR + 0.35))
    geo.finish_hard_surface(dash, 0.04)
    M.assign(dash, m["floor"])
    cloth = geo.box("GEO-dash_cloth", (W - 0.3, 0.52, 0.03), (0, dash_y, FLOOR + 0.555))
    M.assign(cloth, m["curtain"])
    for k in range(40):  # fringe
        fx = -(W - 0.35) / 2 + k * (W - 0.35) / 39
        f = geo.box("GEO-fringe", (0.02, 0.01, 0.07), (fx, dash_y - 0.265, FLOOR + 0.51))
        M.assign(f, m["gold"])
    valance = geo.box("GEO-ws_valance", (W - 0.3, 0.03, 0.18), (0, front_y(Z1 - 0.45) + 0.12, Z1 - 0.45))
    M.assign(valance, m["curtain"])
    wheel = geo.torus("GEO-steering_wheel", 0.24, 0.025, 32, 8, (-0.62, YF + 0.95, FLOOR + 0.78))
    wheel.rotation_euler = (1.1, 0, 0)
    M.assign(wheel, m["black"])
    col = geo.cylinder("GEO-steering_column", 0.035, 0.45, 12, (-0.62, YF + 0.82, FLOOR + 0.6))
    col.rotation_euler = (0.5, 0, 0)
    M.assign(col, m["black"])
    _seat("driver_seat", -0.62, YF + 1.35, 0.55, m)
    # Entry steps up from the door (+X) to the deck.
    for k, z in enumerate((0.72, 0.95)):
        step = geo.box("GEO-door_step", (0.55 - k * 0.15, 0.62, 0.05), (hw - 0.3 - k * 0.07, YF + 0.86, z))
        geo.finish_hard_surface(step, 0.01)
        M.assign(step, m["floor"])
        nose = geo.box("GEO-step_nosing", (0.55 - k * 0.15, 0.03, 0.02), (hw - 0.3 - k * 0.07, YF + 0.56, z + 0.03))
        M.assign(nose, m["yellow"])


def _tag_moving_parts():
    """Wheels and the steering wheel export as separate pivoted objects
    (PART-wheel_fl, PART-steering_wheel, ...) so viewers can animate them."""
    import bpy
    for o in bpy.data.objects:
        n = o.name
        if n.startswith("GEO-wheel_"):
            key = n.split("_")[1]                    # fl, fr, ril, rol, rir, ror
            tyre = bpy.data.objects[f"GEO-wheel_{key}_tyre"]
            geo.part(o, f"wheel_{key}", tyre.location)
        elif n.startswith("GEO-steering_wheel"):
            geo.part(o, "steering_wheel", o.location)
