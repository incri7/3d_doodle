"""Correctly shaped text (any script) as polygon outlines.

HarfBuzz does the shaping (Devanagari conjuncts, vowel-sign reordering,
kerning); fontTools reads the glyph outlines. geo.text() turns the contours
into a filled, extruded mesh.
"""

import os

import uharfbuzz as hb
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
FONTS = {
    "devanagari": "Mukta-ExtraBold.ttf",        # bold Nepali signwriting
    "devanagari_noto": "NotoSansDevanagari-Bold.ttf",
    "condensed": "Oswald-Bold.ttf",             # tall bus lettering
    "italic": "Exo2-BlackItalic.ttf",           # sporty logo text
    "wide": "Michroma-Regular.ttf",             # wide windshield logos
    "black": "ArchivoBlack-Regular.ttf",
}

_cache = {}


def _font(name):
    path = FONTS.get(name, name)
    if not os.path.isabs(path):
        path = os.path.join(FONT_DIR, path)
    if path not in _cache:
        blob = hb.Blob.from_file_path(path)
        tt = TTFont(path)
        _cache[path] = (hb.Font(hb.Face(blob)), tt, tt.getGlyphSet(), tt.getGlyphOrder(),
                        tt["head"].unitsPerEm)
    return _cache[path]


class _FlattenPen(BasePen):
    def __init__(self, glyphset, dx, dy, scale, steps):
        super().__init__(glyphset)
        self.dx, self.dy, self.s, self.steps = dx, dy, scale, steps
        self.contours, self.cur = [], []

    def _pt(self, p):
        return ((p[0] + self.dx) * self.s, (p[1] + self.dy) * self.s)

    def _moveTo(self, p):
        self.cur = [self._pt(p)]

    def _lineTo(self, p):
        self.cur.append(self._pt(p))

    def _curveToOne(self, p1, p2, p3):
        p0 = self._getCurrentPoint()
        for i in range(1, self.steps + 1):
            t = i / self.steps
            u = 1 - t
            x = u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0]
            y = u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]
            self.cur.append(self._pt((x, y)))

    def _qCurveToOne(self, p1, p2):
        p0 = self._getCurrentPoint()
        for i in range(1, self.steps + 1):
            t = i / self.steps
            u = 1 - t
            x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
            y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
            self.cur.append(self._pt((x, y)))

    def _closePath(self):
        if len(self.cur) > 2:
            if self.cur[0] == self.cur[-1]:
                self.cur.pop()
            self.contours.append(self.cur)
        self.cur = []

    _endPath = _closePath


def _union(contours):
    """Merge overlapping glyph outlines (Devanagari vowel signs overlap the
    next letter's headline) into clean contours. Fonts use non-zero winding;
    the mesh fill is even-odd, so overlaps would otherwise punch holes or
    drop pieces."""
    import pathops
    from fontTools.pens.recordingPen import RecordingPen

    path = pathops.Path(fillType=pathops.FillType.WINDING)
    pen = path.getPen()
    for c in contours:
        pen.moveTo(c[0])
        for pt in c[1:]:
            pen.lineTo(pt)
        pen.closePath()
    path = pathops.simplify(path, fix_winding=True)
    rec = RecordingPen()
    path.draw(rec)
    out, cur = [], []
    for cmd, pts in rec.value:
        if cmd == "moveTo":
            cur = [pts[0]]
        elif cmd == "lineTo":
            cur.append(pts[0])
        elif cmd in ("qCurveTo", "curveTo"):
            cur.extend(pts)
        elif cmd in ("closePath", "endPath"):
            if len(cur) > 2:
                out.append(cur)
            cur = []
    return out


def outlines(text, size, font="devanagari", steps=5, tracking=0.0):
    """Contours [[(x, y), ...], ...] for `text` at an em size of `size` meters,
    centered on the origin. tracking: extra letter spacing in em."""
    hbfont, tt, glyphset, order, upem = _font(font)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hbfont, buf, {"kern": True, "liga": True})
    scale = size / upem
    pen_x = pen_y = 0
    contours = []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        name = order[info.codepoint]
        pen = _FlattenPen(glyphset, pen_x + pos.x_offset, pen_y + pos.y_offset, scale, steps)
        glyphset[name].draw(pen)
        contours.extend(pen.contours)
        pen_x += pos.x_advance + (tracking * upem if pos.x_advance else 0)
        pen_y += pos.y_advance
    if not contours:
        return []
    contours = _union(contours)
    xs = [x for c in contours for x, _ in c]
    ys = [y for c in contours for _, y in c]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    return [[(x - cx, y - cy) for x, y in c] for c in contours]
