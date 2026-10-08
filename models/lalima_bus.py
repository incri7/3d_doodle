"""Lalima Yatayat skin for the Agni coach: same body, glass, wheels and
interior (models/agni_bus.py), new paint and graphics.

References: docs/reference/images/lalima_ref_{1,2,3}_*.jpg (user photos of
the red Lalima tourist coaches; nothing more was findable online). The
livery: red body, big white swooshes with red brush strokes along the lower
flank, white diagonal stripes up the front corners, "AIR BUS" on the side
glass, a white TOURIST band under the windshield, "लालिमा" with yellow
TRAVEL & TOURS and a wifi mark across the top of the windshield, red
mirrors.
"""

import math

from doodle import geo, materials as M
from models import agni_bus as A

LIGHTING = A.LIGHTING
HERO_AZIMUTH = A.HERO_AZIMUTH
HERO_ELEVATION = A.HERO_ELEVATION

PI = math.pi
LALIMA_RED = (0.68, 0.007, 0.013)     # sRGB ~#D7141E, from the photos
BRUSH_RED = (0.36, 0.004, 0.01)       # darker strokes inside the white


def build():
    A.BODY.clear()
    m = A.materials()
    m["paint"] = M.painted_metal("MAT-lalima_red", paint=LALIMA_RED, wear=0.06, grime=0.25,
                                 paint_roughness=0.15, metal_color=(0.7, 0.7, 0.72))
    m["band"] = M.plastic("MAT-lalima_white", (0.93, 0.93, 0.91), roughness=0.22, coat=0.5)
    m["brush"] = M.plastic("MAT-lalima_brush", BRUSH_RED, roughness=0.25, coat=0.5)
    m["red_trim"] = M.plastic("MAT-lalima_red_trim", LALIMA_RED, roughness=0.25, coat=0.5)
    m["accent"] = m["band"]

    A._body(m)
    A._glazing(m)
    _front(m)
    A._front_hardware(m)
    A._mirrors({**m, "black": m["red_trim"]})
    for side in (1, -1):
        _flank(m, side)
        A._side_markers(m, side)
    _rear(m)
    A._rear_hardware(m)
    A._wheels(m)
    A._roof(m)
    A._interior(m)
    A._tag_moving_parts()
    A._hitbox()


def _ribbon(pts, w0, w1):
    """A brush-stroke ribbon along `pts`, tapering from width w0 to w1."""
    top, bot = [], []
    n = len(pts)
    for i, (y, z) in enumerate(pts):
        a = pts[min(i + 1, n - 1)]
        b = pts[max(i - 1, 0)]
        dy, dz = a[0] - b[0], a[1] - b[1]
        L = math.hypot(dy, dz) or 1.0
        ny, nz = -dz / L, dy / L
        w = (w0 + (w1 - w0) * i / (n - 1)) / 2
        top.append((y + ny * w, z + nz * w))
        bot.append((y - ny * w, z - nz * w))
    return top + bot[::-1]


# --- flanks -------------------------------------------------------------------------

def _flank(m, s):
    y0 = A.AXLE_F + 0.8
    # The white swoosh: low behind the front wheel, sweeping up to the
    # glazing line at the back.
    top = geo.bezier((y0, 0.95), (y0 + 2.2, 1.0), (A.AXLE_R - 1.2, 1.25), (A.YB - 0.12, 1.98), 20)
    white = top + [(A.YB - 0.12, 0.5), (y0 + 0.4, 0.5), (y0, 0.62)]
    A.on_side("GEO-lalima_swoosh", [white], s, m["band"])
    # Red brush strokes through the white, fanning toward the rear.
    for k, (z0, z1, w0, w1) in enumerate(((0.62, 1.6, 0.03, 0.11), (0.66, 1.25, 0.025, 0.07),
                                          (0.6, 0.92, 0.02, 0.05))):
        pts = geo.bezier((y0 + 0.9 + k * 0.5, z0), (y0 + 3.0, z0 + 0.05),
                         (A.AXLE_R - 0.4, z1 - 0.2), (A.YB - 0.25, z1), 18)
        A.on_side("GEO-lalima_brush", [_ribbon(pts, w0, w1)], s, m["brush"], lift=0.002)
    # Thin red line riding the swoosh's top edge.
    line = [(y, z - 0.08) for y, z in top]
    A.on_side("GEO-lalima_line", [line + [(y, z - 0.035) for y, z in reversed(line)]], s,
              m["paint"], lift=0.002)
    # White stripe climbing the front corner from the bumper to the glass.
    corner = _ribbon(geo.bezier((A.YF + 0.06, 0.62), (A.YF + 0.12, 1.1), (A.YF + 0.3, 1.6),
                                (A.YF + 0.45, 2.0), 12), 0.1, 0.14)
    A.on_side("GEO-lalima_corner", [corner], s, m["band"])
    # Name on the flank, AIR BUS on the side glass.
    A.side_text("GEO-lalima_name", "लालिमा यातायात", s, -0.2, 1.62, 0.36, m["band"],
                font="devanagari")
    A.side_text("GEO-lalima_glass", "LALIMA AIR BUS", s, 0.4, 2.82, 0.5, m["band"], depth=0.016)


# --- front and rear --------------------------------------------------------------------

def _wifi(cx, cz, r, mat):
    """Wifi mark: a dot and three arcs, on the windshield header."""
    A.on_front("GEO-wifi_dot", [A.circle(cx, cz, r * 0.18, 12)], mat, lift=0.012, z_hint=cz)
    for i in range(3):
        r0, r1 = r * (0.45 + i * 0.3), r * (0.6 + i * 0.3)
        arc = [(cx + r1 * math.cos(a), cz + r1 * math.sin(a))
               for a in [PI / 4 + j / 10 * PI / 2 for j in range(11)]]
        arc += [(cx + r0 * math.cos(a), cz + r0 * math.sin(a))
                for a in [3 * PI / 4 - j / 10 * PI / 2 for j in range(11)]]
        A.on_front("GEO-wifi_arc", [arc], mat, lift=0.012, z_hint=cz)


def _front(m):
    zt = A.Z1 - 0.26
    # Header across the top of the windshield: white name, yellow TRAVEL & TOURS.
    A.on_front("GEO-ws_header", [A.rect(-1.12, zt - 0.44, 1.12, zt)], m["black"], lift=0.008,
               z_hint=zt - 0.22)
    A.front_text("GEO-ws_name", "लालिमा", 0, zt - 0.14, 0.3, m["band"], lift=0.012)
    A.front_text("GEO-ws_tours", "TRAVEL & TOURS", -0.12, zt - 0.34, 0.12, m["yellow"],
                 font="black", lift=0.012)
    _wifi(0.62, zt - 0.37, 0.09, m["yellow"])
    # White TOURIST band under the windshield.
    A.on_front("GEO-tourist_band", [A.rect(-1.22, 1.39, 1.22, 1.54)], m["band"], lift=0.004,
               z_hint=1.46)
    A.front_text("GEO-tourist", "TOURIST", 0, 1.465, 0.15, m["red_trim"], font="black",
                 tracking=0.2, lift=0.008)
    # White stripes climbing the front corners.
    for sx in (-1, 1):
        a, b = (sx * 0.96, 0.84), (sx * 1.27, 1.36)
        A.on_front("GEO-front_stripe", [A.stroke(a, b, 0.07)], m["band"], lift=0.004, z_hint=1.1)


def _rear(m):
    A.on_rear("GEO-rear_glass", [A.rounded_rect(-1.15, 2.35, 1.15, A.Z1 - 0.2, 0.1)], m["glass"])
    A.rear_text("GEO-rear_name", "लालिमा", 0, 2.9, 0.42, m["yellow"], lift=0.004)
    for dx in (-0.08, 0, 0.08):
        A.on_rear("GEO-brake_dot", [A.circle(dx, 2.22, 0.025, 10)], m["led_red"])
    A.rear_text("GEO-rear_yatayat", "लालिमा यातायात", 0, 2.02, 0.2, m["band"])
    # White brow over the tail lamps (the Agni shape, in white).
    brow = geo.bezier((-1.25, 1.9), (-0.8, 1.86), (-0.6, 1.72), (-0.3, 1.72), 8)
    brow = brow + [(-x, z) for x, z in reversed(brow)]
    brow_low = [(x, z - 0.12) for x, z in reversed(brow)]
    A.on_rear("GEO-rear_brow", [brow + brow_low], m["band"])
    A.rear_text("GEO-rear_tourist", "TOURIST", 0, 1.25, 0.2, m["band"], font="black", tracking=0.2)
