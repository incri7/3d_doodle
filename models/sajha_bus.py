"""Sajha Yatayat skin for the Agni coach: same body, glass, wheels and
interior (models/agni_bus.py), new paint and graphics.

References (docs/reference/images/sajha_ref_*.jpg): Sajha's own site banner
(official bus render + logo) and news photos of the electric fleet
(Nepali Times 2024, The Annapurna Express). The livery: bright green body,
white roof units, a white sweep along the lower flank with thin speed
stripes, white "साझा यातायात" lettering, and the round cooperative seal
(green cog ring, "साझा यातायात" over "सहकारी", Nepal map in the middle).
"""

import math

from doodle import materials as M
from doodle import textshape
from models import agni_bus as A

LIGHTING = A.LIGHTING
HERO_AZIMUTH = A.HERO_AZIMUTH
HERO_ELEVATION = A.HERO_ELEVATION

PI = math.pi
SAJHA_GREEN = (0.046, 0.42, 0.04)     # body, sRGB ~#3FAE3A (sampled from the photos)
SEAL_GREEN = (0.008, 0.34, 0.018)     # logo, sRGB ~#169D24 (sajhayatayat.com.np logo)


def build():
    A.BODY.clear()
    m = A.materials()
    m["paint"] = M.painted_metal("MAT-sajha_green", paint=SAJHA_GREEN, wear=0.06, grime=0.25,
                                 paint_roughness=0.18, metal_color=(0.7, 0.7, 0.72))
    m["band"] = M.plastic("MAT-sajha_white", (0.93, 0.93, 0.91), roughness=0.22, coat=0.5)
    m["seal"] = M.plastic("MAT-sajha_seal_green", SEAL_GREEN, roughness=0.25, coat=0.5)
    m["led"] = M.emissive("MAT-led_amber", (1.0, 0.5, 0.04), strength=2.5)
    m["accent"] = m["seal"]
    roof_white = M.painted_metal("MAT-roof_white", paint=(0.92, 0.92, 0.9), wear=0.05, grime=0.3,
                                 paint_roughness=0.2, metal_color=(0.7, 0.7, 0.72))

    A._body(m)
    A._glazing(m)
    _front(m)
    A._front_hardware(m)
    A._mirrors(m)
    for side in (1, -1):
        _flank(m, side)
        A._side_markers(m, side)
    _rear(m)
    A._rear_hardware(m)
    A._wheels(m)
    A._roof({**m, "paint": roof_white})
    A._interior(m)
    A._tag_moving_parts()
    A._hitbox()


# --- the Sajha seal ------------------------------------------------------------------

# Nepal outline, west to east along the north border then back along the
# south; unit width, origin at the centre.
NEPAL = [(0.0, 0.62), (0.07, 0.72), (0.17, 0.69), (0.29, 0.61), (0.41, 0.53), (0.53, 0.47),
         (0.65, 0.43), (0.77, 0.37), (0.89, 0.34), (0.96, 0.37), (1.0, 0.27), (0.98, 0.13),
         (0.9, 0.1), (0.78, 0.12), (0.65, 0.15), (0.52, 0.2), (0.4, 0.26), (0.28, 0.33),
         (0.16, 0.4), (0.07, 0.47), (0.01, 0.53)]


def _resample(c, step):
    out = []
    for (x0, y0), (x1, y1) in zip(c, c[1:] + c[:1]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / step))
        out += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n)]
    return out


def _arc_text(body, radius, height, top=True, span=None):
    """Text bent around a circle: along the top (reading clockwise) or the
    bottom (reading counter-clockwise, letter tops toward the centre)."""
    raw = textshape.outlines(body, 1.0, "devanagari")
    xs = [x for c in raw for x, _ in c]
    ys = [y for c in raw for _, y in c]
    k = height / (max(ys) - min(ys))
    if span:  # fit the text to an angular span
        k = min(k, span * radius / (max(xs) - min(xs)))
    out = []
    for c in raw:
        pts = []
        for x, y in _resample([(x * k, y * k) for x, y in c], 0.004):
            if top:
                a, r = PI / 2 - x / radius, radius + y
            else:
                a, r = -PI / 2 + x / radius, radius - y
            pts.append((r * math.cos(a), r * math.sin(a)))
        out.append(pts)
    return out


def _disc(r, n=64):
    return [(r * math.cos(2 * PI * i / n), r * math.sin(2 * PI * i / n)) for i in range(n)]


def _cog(r_out, r_in, teeth=36):
    pts = []
    for i in range(teeth):
        a = 2 * PI * i / teeth
        for da, r in ((0.0, r_in), (0.18, r_in), (0.25, r_out), (0.75, r_out), (0.82, r_in)):
            t = a + da * 2 * PI / teeth
            pts.append((r * math.cos(t), r * math.sin(t)))
    return pts


def seal_layers(R):
    """The cooperative seal as (contours, material key, lift) layers, centred
    at the origin in a flat (u, v) frame, u to the reader's right."""
    w = 0.92 * R  # map width; Nepal is about 3.3 times wider than tall
    nepal = [((x - 0.5) * w, (y - 0.42) * w * 0.55) for x, y in NEPAL]
    ring_out, ring_in = _disc(0.56 * R), _disc(0.52 * R)
    return [
        ([_disc(1.07 * R)], "band", 0.003),
        ([_cog(R, 0.93 * R)], "seal", 0.004),
        ([_disc(0.62 * R)], "band", 0.005),
        ([ring_out, ring_in], "seal", 0.006),
        ([nepal], "seal", 0.006),
        (_arc_text("साझा यातायात", 0.775 * R, 0.17 * R, top=True, span=2.9), "band", 0.006),
        (_arc_text("सहकारी", 0.775 * R, 0.17 * R, top=False, span=1.3), "band", 0.006),
    ]


def _place(layers, m, to_world, put, name):
    for contours, key, lift in layers:
        put(name, [[to_world(u, v) for u, v in c] for c in contours], m[key], lift)


# --- graphics ------------------------------------------------------------------------

def _sweep_top(y0):
    """Top edge of the white sweep, front to rear (y, z): low behind the front
    wheel, rising in a long S toward the back like the electric fleet."""
    pts = [(y0, 0.98)]
    pts += A.geo.bezier((y0, 0.98), (A.AXLE_F + 1.0, 0.92), (A.AXLE_F + 2.4, 0.9),
                        (0.4, 1.0))
    pts += A.geo.bezier((0.4, 1.0), (1.6, 1.08), (A.AXLE_R + 0.6, 1.42), (A.YB - 0.12, 1.5))
    return pts


def _flank(m, s):
    y0 = A.YF + (1.3 if s > 0 else 0.2)          # door side starts behind the door
    top = _sweep_top(y0)
    sweep = top + [(A.YB - 0.12, 0.5), (y0, 0.5)]
    A.on_side("GEO-sajha_sweep", [sweep], s, m["band"])
    # Thin green line inside the white, following the sweep's top edge.
    line = [(y, z - 0.07) for y, z in top]
    A.on_side("GEO-sajha_sweep_line", [line + [(y, z - 0.03) for y, z in reversed(line)]], s,
              m["paint"], lift=0.002)
    # Speed stripes along the bottom of the sweep at both ends.
    for i in range(3):
        z = 0.6 + i * 0.075
        for ya, yb in ((y0, A.AXLE_F - 0.75), (A.AXLE_R + 0.75, A.YB - 0.12)):
            if yb - ya > 0.15:
                A.on_side("GEO-sajha_stripe", [A.rect(ya, z, yb, z + 0.03)], s, m["seal"], lift=0.002)
    # Name in white above the sweep, small English name inside it.
    A.side_text("GEO-sajha_name", "साझा यातायात", s, 0.1, 1.55, 0.34, m["band"], font="devanagari")
    A.side_text("GEO-sajha_name_en", "SAJHA YATAYAT", s, -0.9, 0.74, 0.15, m["seal"],
                font="condensed", tracking=0.08, lift=0.002)
    # The seal just ahead of the rear wheel, over the sweep.
    cy, cz, R = A.AXLE_R - 1.15, 1.05, 0.36
    _place(seal_layers(R), m, lambda u, v: (cy + s * u, cz + v),
           lambda n, c, mat, lift: A.on_side(n, c, s, mat, lift=lift, clip=False), "GEO-sajha_seal")


def _front(m):
    zt = A.Z1 - 0.26
    # Destination board behind the top of the windshield: amber LED route.
    A.on_front("GEO-dest_board", [A.rect(-1.12, zt - 0.36, 1.12, zt)], m["black"], lift=0.008,
               z_hint=zt - 0.18)
    A.front_text("GEO-dest_route", "लगनखेल - नयाँ बसपार्क", 0, zt - 0.18, 0.19, m["led"], lift=0.012)
    # White name across the panel under the windshield.
    A.front_text("GEO-front_name", "साझा यातायात", 0, 1.45, 0.17, m["band"], lift=0.004)


def _rear(m):
    # Rear window with an amber LED route sign.
    A.on_rear("GEO-rear_glass", [A.rounded_rect(-1.15, 2.35, 1.15, A.Z1 - 0.2, 0.1)], m["glass"])
    A.rear_text("GEO-rear_route", "साझा यातायात", 0, 2.92, 0.26, m["led"], lift=0.004)
    for dx in (-0.08, 0, 0.08):
        A.on_rear("GEO-brake_dot", [A.circle(dx, 2.22, 0.025, 10)], m["led_red"])
    A.rear_text("GEO-rear_name", "साझा यातायात", 0, 1.95, 0.24, m["band"])
    # White band across the back at the tail lamps' height, seal on the hatch.
    A.on_rear("GEO-rear_band", [A.rect(-1.3, 1.66, 1.3, 1.76)], m["band"])
    cx, cz, R = 0.0, 1.22, 0.3
    _place(seal_layers(R), m, lambda u, v: (cx - u, cz + v),
           lambda n, c, mat, lift: A.on_rear(n, c, mat, lift=lift), "GEO-rear_seal")
