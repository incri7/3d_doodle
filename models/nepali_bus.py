"""Nepali long-route bus: starting model.

Reference: docs/reference/images/nepali_bus_ref_ai.webp (AI-generated from a
description of the classic Tata LP 1512/1613 Nepali bus; the network blocks
photo sites). Red body with a yellow belt band, chrome trim line, two-piece
windshield, sliding windows, roof luggage rack with rear ladder, quad
headlights, chrome bumper, rainbow stripes on the lower panels.

Real-world size (Tata LP 1512 class): 10.6 m long, 2.5 m wide, ~3.1 m to the
roof (3.4 m with rack), 5.6 m wheelbase, 10.00-20 tyres (~1.05 m diameter).
Front faces -Y. Nepal drives on the left, so the passenger door is on the
vehicle's left side, which is +X here.
"""

import math

from doodle import geo, materials as M

LIGHTING = "studio"
HERO_AZIMUTH = 35  # show the front and the door (+X) side
HERO_ELEVATION = 10

L, W = 10.6, 2.5          # body length / width
Z0, Z1 = 0.70, 3.08       # body underside / roof top
YF = -L / 2               # front face
YB = L / 2                # back face
AXLE_F = YF + 2.0         # front axle (short front overhang, flat-front bus)
AXLE_R = AXLE_F + 5.6     # rear axle
TYRE_R, TYRE_W = 0.52, 0.28

WIN_Z0, WIN_Z1 = 1.88, 2.62   # side window band
BELT_Z = 1.80                 # chrome trim line
RED = (0.62, 0.03, 0.02)
YELLOW = (0.92, 0.55, 0.0)


def build():
    paint = M.painted_metal(
        "MAT-bus_paint", wear=0.35, grime=0.6, paint_roughness=0.35,
        bands=[(0.0, RED), (1.30, YELLOW), (BELT_Z, RED)], band_top=Z1)
    chrome = M.metal("MAT-chrome", color=(0.9, 0.9, 0.92), roughness=0.12)
    window = M.plastic("MAT-window_glass", (0.015, 0.02, 0.025), roughness=0.05, coat=1.0)
    rubber = M.rubber("MAT-tyre")
    rim = M.painted_metal("MAT-rim", paint=(0.55, 0.04, 0.03), wear=0.5, grime=0.8)
    chassis = M.painted_metal("MAT-chassis", paint=(0.03, 0.03, 0.03), wear=0.3, grime=0.9)
    lamp = M.emissive("MAT-headlamp", (1.0, 0.95, 0.85), strength=1.5)
    amber = M.emissive("MAT-indicator", (1.0, 0.45, 0.02), strength=1.0)
    tail = M.emissive("MAT-taillamp", (0.9, 0.02, 0.01), strength=1.0)
    plate = M.plastic("MAT-plate", (0.02, 0.02, 0.02), roughness=0.4)  # public vehicle: black
    board = M.plastic("MAT-dest_board", (0.95, 0.92, 0.85), roughness=0.5)
    rack = M.painted_metal("MAT-rack", paint=(0.35, 0.22, 0.12), metal_color=(0.4, 0.38, 0.36),
                           wear=0.7, grime=0.7)
    tarp = M.plastic("MAT-tarp_blue", (0.05, 0.18, 0.45), roughness=0.85)
    sack = M.plastic("MAT-sack", (0.55, 0.45, 0.3), roughness=0.95)

    body = _body(paint)
    _glass(window)
    _front(chrome, lamp, amber, plate, board, paint)
    _rear(tail, chrome, rack, window)
    _wheels(rubber, rim, chrome)
    _underside(chassis)
    _roof_rack(rack, tarp, sack)
    _mirrors_wipers(chassis, chrome)
    _stripes()
    _lettering(plate)
    _flowers()
    return body


# --- body ------------------------------------------------------------------

def _body(paint):
    prof = geo.rounded_rect_profile(W, Z0, Z1, radius=0.32, steps=6)
    body = geo.profile_prism("GEO-bus_body", prof, YF, YB)
    # Round the big box corners first, then cut openings, then a fine bevel.
    big = geo.bevel(body, width=0.12, segments=5, angle=60, harden=False)
    big.name = "BevelBig"

    # Wheel arches: cylinders along X through the whole body.
    for y in (AXLE_F, AXLE_R):
        arch = geo.cylinder("CUT-arch", TYRE_R + 0.12, W + 1, 32, (0, y, TYRE_R))
        arch.rotation_euler = (0, math.pi / 2, 0)
        geo.cut(body, arch)

    # Side window recesses (both sides). The front +X side starts after the door.
    win_w, gap = 0.92, 0.14
    for side in (-1, 1):
        start = YF + (1.25 if side > 0 else 0.55)
        n = int((YB - 0.35 - start) // (win_w + gap))
        cutter = geo.box("CUT-windows", (0.08, win_w, WIN_Z1 - WIN_Z0),
                         (side * W / 2, start + win_w / 2, (WIN_Z0 + WIN_Z1) / 2))
        geo.array(cutter, n, (0, (win_w + gap) / win_w, 0))
        geo.cut(body, cutter)
    # Driver's side window (vehicle right, -X) is part of the run above.

    # Passenger door on +X, in the front overhang.
    door = geo.box("CUT-door", (0.05, 0.78, 2.0), (W / 2, YF + 0.55, Z0 + 1.0))
    geo.cut(body, door)

    # Two-piece windshield and destination board recess on the front face.
    for x in (-0.6, 0.6):
        ws = geo.box("CUT-windshield", (1.08, 0.08, 0.86), (x, YF, 2.28))
        geo.cut(body, ws)
    # Rear window.
    rw = geo.box("CUT-rear_window", (1.9, 0.08, 0.6), (0, YB, 2.3))
    geo.cut(body, rw)

    geo.finish_hard_surface(body, bevel_width=0.01, segments=2, angle=40)
    M.assign(body, paint)
    return body


def _glass(window):
    inset = 0.025  # recesses are 0.04 deep; glass sits just proud of the bottom
    for side in (-1, 1):
        g = geo.box("GEO-side_glass", (0.01, L - 0.6, WIN_Z1 - WIN_Z0 - 0.02),
                    (side * (W / 2 - inset), 0.05, (WIN_Z0 + WIN_Z1) / 2))
        M.assign(g, window)
    g = geo.box("GEO-windshield", (2.3, 0.01, 0.84), (0, YF + inset, 2.28))
    M.assign(g, window)
    g = geo.box("GEO-rear_glass", (1.88, 0.01, 0.58), (0, YB - inset, 2.3))
    M.assign(g, window)
    # Door: glass in the upper half only; the lower half is the painted recess.
    g = geo.box("GEO-door_glass", (0.01, 0.66, 0.95), (W / 2 - inset + 0.012, YF + 0.55, 2.1))
    M.assign(g, window)
    # Sliding-window rails: aluminium bars across the window band.
    alu = M.metal("MAT-aluminium", color=(0.75, 0.76, 0.78), roughness=0.3)
    for side in (-1, 1):
        for z in (WIN_Z0 + 0.3, WIN_Z1 - 0.02):
            r = geo.box("GEO-window_rail", (0.02, L - 0.9, 0.025), (side * (W / 2 - 0.012), 0.2, z))
            M.assign(r, alu)


# --- front -----------------------------------------------------------------

def _front(chrome, lamp, amber, plate, board, paint):
    yf = YF - 0.01
    grille = geo.box("GEO-grille_frame", (1.2, 0.05, 0.5), (0, yf, 1.12))
    geo.finish_hard_surface(grille, 0.012)
    M.assign(grille, chrome)
    slat = geo.box("GEO-grille_slats", (1.08, 0.03, 0.035), (0, yf - 0.025, 0.93))
    geo.array(slat, 7, (0, 0, 1.75))
    geo.finish_hard_surface(slat, 0.006, 2)
    M.assign(slat, chrome)

    for sx in (-1, 1):
        for dx in (0.0, 0.22):  # quad round headlights
            x = sx * (0.78 + dx)
            bezel = geo.cylinder("GEO-headlamp_bezel", 0.1, 0.06, 32, (x, yf - 0.02, 1.08))
            bezel.rotation_euler = (math.pi / 2, 0, 0)
            geo.finish_hard_surface(bezel, 0.01)
            M.assign(bezel, chrome)
            lens = geo.sphere("GEO-headlamp", 0.085, 24, 12, (x, yf - 0.03, 1.08))
            lens.scale = (1, 0.35, 1)
            geo.smooth(lens)
            M.assign(lens, lamp)
        ind = geo.box("GEO-indicator", (0.14, 0.04, 0.07), (sx * 0.98, yf - 0.02, 0.88))
        geo.finish_hard_surface(ind, 0.01)
        M.assign(ind, amber)

    bumper = geo.box("GEO-bumper", (W + 0.06, 0.16, 0.16), (0, YF - 0.1, 0.72))
    geo.finish_hard_surface(bumper, 0.03, 4)
    M.assign(bumper, chrome)
    for sx in (-1, 1):
        guard = geo.box("GEO-bumper_guard", (0.1, 0.12, 0.3), (sx * 0.62, YF - 0.2, 0.74))
        geo.finish_hard_surface(guard, 0.03, 3)
        M.assign(guard, chrome)
    pl = geo.box("GEO-number_plate", (0.5, 0.02, 0.14), (0, YF - 0.19, 0.72))
    geo.finish_hard_surface(pl, 0.005)
    M.assign(pl, plate)

    # Destination board over the windshield, under a small visor.
    db = geo.box("GEO-destination_board", (1.6, 0.03, 0.22), (0, yf, 2.85))
    geo.finish_hard_surface(db, 0.008)
    M.assign(db, board)
    visor = geo.box("GEO-visor", (W - 0.1, 0.14, 0.05), (0, YF - 0.06, 3.0))
    geo.finish_hard_surface(visor, 0.02, 3)
    M.assign(visor, paint)

    # Chrome trim line wrapping front and both sides.
    for side in (-1, 1):
        t = geo.box("GEO-trim_side", (0.02, L - 0.2, 0.05), (side * (W / 2 + 0.005), 0, BELT_Z))
        geo.finish_hard_surface(t, 0.008)
        M.assign(t, chrome)
    t = geo.box("GEO-trim_front", (W - 0.2, 0.02, 0.05), (0, YF - 0.005, BELT_Z))
    geo.finish_hard_surface(t, 0.008)
    M.assign(t, chrome)


# --- rear --------------------------------------------------------------------

def _rear(tail, chrome, rack, window):
    yb = YB + 0.01
    for sx in (-1, 1):
        tl = geo.box("GEO-tail_lamp", (0.16, 0.04, 0.24), (sx * 1.0, yb, 1.05))
        geo.finish_hard_surface(tl, 0.012)
        M.assign(tl, tail)
    bumper = geo.box("GEO-rear_bumper", (W, 0.14, 0.14), (0, YB + 0.07, 0.74))
    geo.finish_hard_surface(bumper, 0.025, 3)
    M.assign(bumper, chrome)

    # Ladder up the back to the roof rack (+X side of the rear face).
    x, y = 0.75, YB + 0.09
    for dx in (-0.2, 0.2):
        rail = geo.cylinder("GEO-ladder_rail", 0.022, 2.65, 12, (x + dx, y, 2.05))
        geo.smooth(rail)
        M.assign(rail, rack)
    for i in range(9):
        rung = geo.cylinder("GEO-ladder_rung", 0.016, 0.4, 10, (x, y, 0.95 + i * 0.28))
        rung.rotation_euler = (0, math.pi / 2, 0)
        geo.smooth(rung)
        M.assign(rung, rack)


# --- wheels and underside -------------------------------------------------------

def _wheel(name, x, y, rubber, rim, chrome, outward):
    tyre = geo.cylinder(f"GEO-{name}_tyre", TYRE_R, TYRE_W, 48, (x, y, TYRE_R))
    tyre.rotation_euler = (0, math.pi / 2, 0)
    geo.bevel(tyre, 0.09, 5, 30, harden=False)
    geo.smooth(tyre, 60)
    M.assign(tyre, rubber)
    disc = geo.cylinder(f"GEO-{name}_rim", 0.3, TYRE_W + 0.02, 32, (x, y, TYRE_R))
    disc.rotation_euler = (0, math.pi / 2, 0)
    geo.finish_hard_surface(disc, 0.012)
    M.assign(disc, rim)
    if outward:
        hub = geo.cylinder(f"GEO-{name}_hub", 0.11, 0.08, 24,
                           (x + outward * (TYRE_W / 2 + 0.03), y, TYRE_R))
        hub.rotation_euler = (0, math.pi / 2, 0)
        geo.finish_hard_surface(hub, 0.012)
        M.assign(hub, chrome)
        for i in range(8):  # lug nuts
            a = 2 * math.pi * i / 8
            nut = geo.cylinder(f"GEO-{name}_nut", 0.018, 0.04, 6,
                               (x + outward * (TYRE_W / 2 + 0.02), y + 0.17 * math.cos(a),
                                TYRE_R + 0.17 * math.sin(a)))
            nut.rotation_euler = (0, math.pi / 2, 0)
            M.assign(nut, chrome)


def _wheels(rubber, rim, chrome):
    for sx in (-1, 1):
        _wheel(f"wheel_f{'l' if sx > 0 else 'r'}", sx * 0.97, AXLE_F, rubber, rim, chrome, sx)
        _wheel(f"wheel_ri{'l' if sx > 0 else 'r'}", sx * 0.80, AXLE_R, rubber, rim, chrome, 0)
        _wheel(f"wheel_ro{'l' if sx > 0 else 'r'}", sx * 1.10, AXLE_R, rubber, rim, chrome, sx)


def _underside(chassis):
    for sx in (-1, 1):  # frame rails
        rail = geo.box("GEO-frame_rail", (0.12, L - 1.2, 0.25), (sx * 0.45, 0.3, 0.62))
        M.assign(rail, chassis)
    for y in (AXLE_F, AXLE_R):
        axle = geo.cylinder("GEO-axle", 0.07, 2.1, 16, (0, y, TYRE_R))
        axle.rotation_euler = (0, math.pi / 2, 0)
        M.assign(axle, chassis)
    diff = geo.sphere("GEO-differential", 0.22, 24, 12, (0, AXLE_R, TYRE_R))
    M.assign(diff, chassis)
    tank = geo.cylinder("GEO-fuel_tank", 0.22, 0.9, 24, (-0.85, 0.4, 0.55))
    tank.rotation_euler = (math.pi / 2, 0, 0)
    geo.finish_hard_surface(tank, 0.03)
    M.assign(tank, chassis)
    for sx in (-1, 1):  # mud flaps behind the rear wheels
        flap = geo.box("GEO-mudflap", (0.5, 0.015, 0.45), (sx * 0.95, AXLE_R + 0.75, 0.45))
        M.assign(flap, chassis)
    skirt = geo.box("GEO-under_skirt", (W - 0.3, L - 0.6, 0.12), (0, 0, Z0 - 0.04))
    M.assign(skirt, chassis)


# --- roof rack ----------------------------------------------------------------

def _roof_rack(rack, tarp, sack):
    y0, y1 = YF + 2.2, YB - 0.25
    zb, zt = Z1 + 0.06, Z1 + 0.32
    length = y1 - y0
    yc = (y0 + y1) / 2
    for sx in (-1, 1):
        for z in (zb, zt):
            r = geo.cylinder("GEO-rack_rail", 0.022, length, 12, (sx * 1.08, yc, z))
            r.rotation_euler = (math.pi / 2, 0, 0)
            geo.smooth(r)
            M.assign(r, rack)
        n = int(length // 0.75) + 1
        post = geo.cylinder("GEO-rack_post", 0.018, zt - Z1 + 0.02, 10,
                            (sx * 1.08, y0, (zt + Z1) / 2 - 0.01))
        geo.array(post, n, (0, length / (n - 1), 0), relative=False)
        geo.smooth(post)
        M.assign(post, rack)
    for y in (y0, y1):
        r = geo.cylinder("GEO-rack_end", 0.022, 2.16, 12, (0, y, zt))
        r.rotation_euler = (0, math.pi / 2, 0)
        geo.smooth(r)
        M.assign(r, rack)
    slat = geo.box("GEO-rack_slat", (2.16, 0.05, 0.025), (0, y0, zb))
    geo.array(slat, int(length // 0.4) + 1, (0, 0.4, 0), relative=False)
    M.assign(slat, rack)

    # Luggage: a tarp-covered heap and a few sacks.
    heap = geo.box("GEO-luggage_tarp", (1.8, 2.4, 0.5), (0.0, YB - 2.0, zb + 0.26))
    geo.bevel(heap, 0.12, 3, 30, harden=False)
    geo.subsurf(heap, 1)
    geo.smooth(heap, 80)
    M.assign(heap, tarp)
    for i, (x, y, rz) in enumerate([(-0.5, -0.6, 0.2), (0.45, -0.4, -0.15), (-0.1, 0.4, 0.05),
                                    (0.55, 0.9, 0.3)]):
        s = geo.box(f"GEO-sack_{i}", (0.6, 0.95, 0.34), (x, y, zb + 0.18))
        s.rotation_euler = (0, 0, rz)
        geo.bevel(s, 0.1, 3, 30, harden=False)
        geo.subsurf(s, 1)
        geo.smooth(s, 80)
        M.assign(s, sack)


# --- small parts and decoration -----------------------------------------------------

def _mirrors_wipers(black, chrome):
    for sx in (-1, 1):
        arm = geo.cylinder("GEO-mirror_arm", 0.015, 0.35, 10, (sx * 1.38, YF + 0.1, 2.55))
        arm.rotation_euler = (0, math.pi / 2, 0)
        M.assign(arm, chrome)
        m = geo.box("GEO-mirror", (0.04, 0.2, 0.32), (sx * 1.55, YF + 0.1, 2.35))
        geo.finish_hard_surface(m, 0.015)
        M.assign(m, black)
        stalk = geo.cylinder("GEO-mirror_stalk", 0.012, 0.25, 8, (sx * 1.55, YF + 0.1, 2.6))
        M.assign(stalk, chrome)
        wiper = geo.box("GEO-wiper", (0.03, 0.01, 0.7), (sx * 0.6, YF - 0.005, 2.12))
        wiper.rotation_euler = (0, sx * 0.5, 0)
        M.assign(wiper, black)


def _stripes():
    """Rainbow stripe decal on the lower panels, both sides (thin raised panels)."""
    colors = [(0.05, 0.35, 0.85), (0.1, 0.65, 0.2), (0.95, 0.85, 0.05),
              (0.95, 0.45, 0.02), (0.75, 0.05, 0.4), (0.45, 0.1, 0.7)]
    mats = [M.plastic(f"MAT-stripe_{i}", c, roughness=0.35) for i, c in enumerate(colors)]
    for side in (-1, 1):
        for y0 in (AXLE_F + 1.2, AXLE_R + 1.0):
            for i, mat in enumerate(mats):
                s = geo.box("GEO-stripe", (0.004, 0.1, 0.62),
                            (side * (W / 2 + 0.002), y0 + i * 0.105, 1.0))
                s.rotation_euler = (-0.4, 0, 0)  # lean toward the rear
                M.assign(s, mat)


def _lettering(plate):
    """Painted Devanagari lettering. Words avoid conjuncts and the pre-base
    vowel sign, which Blender can't shape."""
    ink_red = M.plastic("MAT-ink_red", (0.55, 0.02, 0.02), roughness=0.35)
    ink_white = M.plastic("MAT-ink_white", (0.95, 0.95, 0.92), roughness=0.4)
    ink_blue = M.plastic("MAT-ink_blue", (0.04, 0.1, 0.45), roughness=0.35)
    band_z = (1.30 + BELT_Z) / 2
    for side in (-1, 1):  # "Nepal Yatayat" (Nepal Transport) along the yellow band
        t = geo.text("GEO-text_side", "नेपाल यातायात", size=0.46, depth=0.006,
                     location=(side * (W / 2 + 0.003), 0.9, band_z - 0.02),
                     rotation=(math.pi / 2, 0, side * math.pi / 2))
        M.assign(t, ink_red)
    t = geo.text("GEO-text_destination", "पोखरा", size=0.2, depth=0.004,
                 location=(0, YF - 0.03, 2.84), rotation=(math.pi / 2, 0, 0))
    M.assign(t, ink_red)
    t = geo.text("GEO-text_plate", "बा ३ ख ४५६७", size=0.085, depth=0.003,
                 location=(0, YF - 0.205, 0.715), rotation=(math.pi / 2, 0, 0))
    M.assign(t, ink_white)
    t = geo.text("GEO-text_horn", "HORN PLEASE", size=0.16, depth=0.004,
                 location=(-0.3, YB + 0.012, 1.55), rotation=(math.pi / 2, 0, math.pi))
    M.assign(t, ink_blue)
    # Sticker band across the top of the windshield (red / green / blue).
    for i, c in enumerate([(0.8, 0.05, 0.03), (0.05, 0.55, 0.15), (0.05, 0.2, 0.75)]):
        b = geo.box("GEO-windshield_band", (2.25, 0.004, 0.035), (0, YF + 0.012, 2.68 - i * 0.04))
        M.assign(b, M.plastic(f"MAT-band_{i}", c, roughness=0.3))


def _flowers():
    """Simple painted flowers on the lower red panels, both sides."""
    cols = [(0.95, 0.45, 0.65), (0.98, 0.85, 0.1), (0.95, 0.95, 0.95), (0.85, 0.2, 0.55)]
    petals = [M.plastic(f"MAT-petal_{i}", c, roughness=0.4) for i, c in enumerate(cols)]
    leaf = M.plastic("MAT-leaf", (0.05, 0.45, 0.1), roughness=0.45)
    heart = M.plastic("MAT-flower_center", (0.95, 0.6, 0.02), roughness=0.4)
    spots = [(AXLE_F + 2.2, 1.0, 1.0), (AXLE_F + 2.75, 0.92, 0.8), (AXLE_F + 3.3, 1.02, 1.1),
             (AXLE_F + 3.85, 0.95, 0.85), (AXLE_R + 1.85, 1.0, 0.9), (AXLE_R + 2.4, 0.95, 0.8)]
    for side in (-1, 1):
        x = side * (W / 2 + 0.004)
        for k, (y, z, sc) in enumerate(spots):
            r = 0.12 * sc
            for i in range(5):
                a = 2 * math.pi * i / 5 + k
                p = geo.cylinder("GEO-petal", r * 0.55, 0.004, 12,
                                 (x, y + r * math.cos(a), z + r * math.sin(a)))
                p.rotation_euler = (0, math.pi / 2, 0)
                M.assign(p, petals[k % len(petals)])
            c = geo.cylinder("GEO-flower_center", r * 0.4, 0.006, 12, (x, y, z))
            c.rotation_euler = (0, math.pi / 2, 0)
            M.assign(c, heart)
            for d in (-1, 1):  # two leaves
                lf = geo.cylinder("GEO-leaf", r * 0.5, 0.003, 10,
                                  (x, y + d * r * 1.5, z - r * 1.4))
                lf.rotation_euler = (0, math.pi / 2, 0)
                lf.scale = (0.45, 1.0, 1.0)  # local X is world Z after the Y rotation
                M.assign(lf, leaf)
