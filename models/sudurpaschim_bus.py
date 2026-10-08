"""Sudurpaschim Yatayat skin (the "राजगद्दी एक्सप्रेस" Dhangadhi - Kathmandu
coach) for the Agni coach: same body, glass, wheels and interior
(models/agni_bus.py), new paint and graphics.

Reference: docs/reference/images/sudurpaschim_ref_1_rajgaddi_express.jpg
(launch photo, Dinesh Khabar, late 2025). The livery: sky-blue body and
mirrors, a yellow pinstripe along the lower flank and across the front,
the dark windshield header "सुदूर पश्चिम यातायात प्रा.लि." over a big
"राजगद्दी एक्सप्रेस", and the route band "धनगढी 2X2 काठमाण्डौ".
"""

from doodle import geo, materials as M
from models import agni_bus as A

LIGHTING = A.LIGHTING
HERO_AZIMUTH = A.HERO_AZIMUTH
HERO_ELEVATION = A.HERO_ELEVATION

SKY_BLUE = (0.023, 0.24, 0.51)        # sRGB ~#2A86BD, from the photo in sun
GOLD = (0.75, 0.39, 0.04)             # sRGB ~#E0A83A pinstripe


def build():
    A.BODY.clear()
    m = A.materials()
    m["paint"] = M.painted_metal("MAT-sudur_blue", paint=SKY_BLUE, wear=0.06, grime=0.25,
                                 paint_roughness=0.15, metal_color=(0.7, 0.7, 0.72))
    m["gold"] = M.plastic("MAT-sudur_gold", GOLD, roughness=0.25, coat=0.5)
    m["blue_trim"] = M.plastic("MAT-sudur_blue_trim", SKY_BLUE, roughness=0.25, coat=0.5)
    m["accent"] = m["gold"]

    A._body(m)
    A._glazing(m)
    _front(m)
    A._front_hardware(m)
    A._mirrors({**m, "black": m["blue_trim"]})
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


def _flank(m, s):
    # Yellow pinstripe low along the flank, kicking up behind the rear wheel.
    y0 = A.YF + (1.3 if s > 0 else 0.15)
    line = [(y0, 0.62), (A.AXLE_R + 0.75, 0.62)]
    line += geo.bezier((A.AXLE_R + 0.75, 0.62), (A.AXLE_R + 1.3, 0.62), (A.YB - 0.9, 0.95),
                       (A.YB - 0.12, 0.98), 10)
    A.on_side("GEO-sudur_stripe", [line + [(y, z + 0.045) for y, z in reversed(line)]], s, m["gold"])
    # Coach name on the side glass, in gold like the photo's lettering.
    A.side_text("GEO-sudur_glass", "राजगद्दी एक्सप्रेस", s, 0.6, 2.6, 0.4, m["gold"],
                font="devanagari", depth=0.016)


def _front(m):
    zt = A.Z1 - 0.26
    # Dark header: operator in gold, coach name in white.
    A.on_front("GEO-ws_header", [A.rect(-1.12, zt - 0.42, 1.12, zt)], m["black"], lift=0.008,
               z_hint=zt - 0.21)
    A.front_text("GEO-ws_operator", "सुदूर पश्चिम यातायात प्रा.लि.", 0, zt - 0.07, 0.11, m["yellow"],
                 lift=0.012)
    A.front_text("GEO-ws_coach", "राजगद्दी एक्सप्रेस", 0, zt - 0.26, 0.24, m["white"], lift=0.012)
    # Route band at the bottom of the windshield.
    zb = A.WS_Z0 + 0.19
    A.on_front("GEO-ws_route_band", [A.rect(-1.12, A.WS_Z0 + 0.1, 1.12, A.WS_Z0 + 0.3)], m["black"],
               lift=0.008, z_hint=zb)
    A.front_text("GEO-route_from", "धनगढी", -0.68, zb, 0.15, m["white"], lift=0.012)
    A.front_text("GEO-route_seats", "2X2", 0, zb, 0.14, m["yellow"], font="black", lift=0.012)
    A.front_text("GEO-route_to", "काठमाण्डौ", 0.68, zb, 0.15, m["white"], lift=0.012)
    # Yellow pinstripe across the front under the windshield.
    A.on_front("GEO-front_stripe", [A.rect(-1.12, 1.42, 1.12, 1.455)], m["gold"], lift=0.004,
               z_hint=1.44)


def _rear(m):
    A.on_rear("GEO-rear_glass", [A.rounded_rect(-1.15, 2.35, 1.15, A.Z1 - 0.2, 0.1)], m["glass"])
    A.rear_text("GEO-rear_coach", "राजगद्दी एक्सप्रेस", 0, 2.85, 0.3, m["yellow"], lift=0.004)
    for dx in (-0.08, 0, 0.08):
        A.on_rear("GEO-brake_dot", [A.circle(dx, 2.22, 0.025, 10)], m["led_red"])
    A.rear_text("GEO-rear_operator", "सुदूर पश्चिम यातायात", 0, 2.0, 0.2, m["white"])
    A.on_rear("GEO-rear_stripe", [A.rect(-1.3, 1.7, 1.3, 1.735)], m["gold"])
    A.rear_text("GEO-rear_route", "धनगढी - काठमाण्डौ", 0, 1.25, 0.16, m["white"])
