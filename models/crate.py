"""Sci-fi supply crate: pipeline test model.

Real-world size: 1.0 m wide x 0.7 m deep x 0.6 m tall (standard cargo crate).
Shows the hard-surface stack: boolean cuts, bevels, arrays, edge wear.
"""

import math

from doodle import geo, materials as M

LIGHTING = "studio"

W, D, H = 1.0, 0.7, 0.6


def build():
    paint = M.painted_metal("MAT-paint_orange", paint=(0.62, 0.22, 0.03), wear=0.55, grime=0.6)
    steel = M.painted_metal("MAT-gunmetal", paint=(0.05, 0.055, 0.06), metal_color=(0.55, 0.55, 0.56),
                            wear=0.4, grime=0.4, paint_roughness=0.35)
    rubber = M.rubber("MAT-rubber")
    glow = M.emissive("MAT-glow_cyan", (0.1, 0.8, 1.0), strength=4)
    metal = M.metal("MAT-steel_bolts", roughness=0.35)

    # --- body: box with recessed front/back panels and a lid seam ---------
    body = geo.box("GEO-body", (W, D, H), (0, 0, H / 2 + 0.04))
    for y in (-D / 2, D / 2):
        panel = geo.box("CUT-panel", (W * 0.72, 0.03, H * 0.55), (0, y, H / 2 + 0.02))
        geo.cut(body, panel)
    seam = geo.box("CUT-seam", (W + 0.1, D + 0.1, 0.008), (0, 0, H * 0.82 + 0.04))
    inner = geo.box("CUT-seam_keep", (W - 0.012, D - 0.012, 0.02), seam.location)
    geo.cut(seam, inner)  # turns the seam cutter into a thin ring
    geo.cut(body, seam)
    geo.finish_hard_surface(body, bevel_width=0.012)
    M.assign(body, paint)

    # --- corner guards: L-profile posts at the 4 vertical edges ------------
    for sx in (-1, 1):
        for sy in (-1, 1):
            post = geo.box("GEO-corner", (0.09, 0.09, H + 0.03),
                           (sx * (W / 2 - 0.035), sy * (D / 2 - 0.035), H / 2 + 0.04))
            hollow = geo.box("CUT-corner", (0.09, 0.09, H + 0.1),
                             (sx * (W / 2 - 0.045), sy * (D / 2 - 0.045), H / 2 + 0.04))
            geo.cut(post, hollow)
            geo.finish_hard_surface(post, bevel_width=0.006)
            M.assign(post, steel)
            # rubber foot under each corner
            foot = geo.cylinder("GEO-foot", 0.045, 0.04, 24,
                                (sx * (W / 2 - 0.07), sy * (D / 2 - 0.07), 0.02))
            geo.finish_hard_surface(foot, bevel_width=0.008)
            M.assign(foot, rubber)
            # bolts down the post faces
            for face_axis in ("x", "y"):
                for z in (0.14, H * 0.5 + 0.04, H - 0.04):
                    loc = [sx * (W / 2 - 0.035), sy * (D / 2 - 0.035), z]
                    if face_axis == "x":
                        loc[0] = sx * (W / 2 + 0.012)
                        loc[1] = sy * (D / 2 - 0.04)
                    else:
                        loc[1] = sy * (D / 2 + 0.012)
                        loc[0] = sx * (W / 2 - 0.04)
                    bolt = geo.cylinder("GEO-bolt", 0.011, 0.012, 6, loc)
                    bolt.rotation_euler = (0, math.pi / 2, 0) if face_axis == "x" else (math.pi / 2, 0, 0)
                    geo.finish_hard_surface(bolt, bevel_width=0.002, segments=2)
                    M.assign(bolt, metal)

    # --- side handles -------------------------------------------------------
    for sx in (-1, 1):
        bar = geo.cylinder("GEO-handle_bar", 0.014, 0.3, 24, (sx * (W / 2 + 0.06), 0, H * 0.62))
        bar.rotation_euler = (math.pi / 2, 0, 0)
        geo.smooth(bar)
        M.assign(bar, rubber)
        for sy in (-1, 1):
            arm = geo.box("GEO-handle_arm", (0.07, 0.03, 0.04),
                          (sx * (W / 2 + 0.03), sy * 0.15, H * 0.62))
            geo.finish_hard_surface(arm, bevel_width=0.006)
            M.assign(arm, steel)

    # --- front status strip + lid latches ------------------------------------
    strip = geo.box("GEO-status_strip", (W * 0.5, 0.012, 0.025), (0, -D / 2 - 0.004, H * 0.92))
    geo.finish_hard_surface(strip, bevel_width=0.004)
    M.assign(strip, glow)
    for sx in (-1, 1):
        for sy in (-1, 1):
            latch = geo.box("GEO-latch", (0.08, 0.03, 0.09),
                            (sx * W * 0.3, sy * (D / 2 + 0.012), H * 0.82 + 0.04))
            geo.finish_hard_surface(latch, bevel_width=0.008)
            M.assign(latch, steel)
