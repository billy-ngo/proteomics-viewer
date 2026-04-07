"""
Pro-ker Proteomics Analysis icon generator.

Renders two overlapping poker cards with red "2" and "BN" — matching the
in-app SVG logo. Pure Python (struct + zlib), no Pillow required.

Public API
----------
generate_png(size=48) -> bytes   -- RGBA PNG
generate_ico(sizes=[48,32,16]) -> bytes  -- ICO wrapping PNG data
"""

import math
import struct
import zlib

_RED = (0xDC, 0x26, 0x26)
_WHITE = (0xFF, 0xFF, 0xFF)
_DARK = (0x0D, 0x11, 0x17)
_CARD_BG = (0xF0, 0xF0, 0xF0)
_CARD_BG2 = (0xFF, 0xFF, 0xFF)
_BORDER = (0xAA, 0xAA, 0xAA)


def _make_png(width, height, rows):
    def _chunk(ct, data):
        c = ct + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    raw = b"".join(b"\x00" + r for r in rows)
    return sig + ihdr + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b"")


def _rot(x, y, cx, cy, angle_deg):
    """Rotate point (x,y) around (cx,cy) by angle_deg."""
    a = math.radians(angle_deg)
    dx, dy = x - cx, y - cy
    return cx + dx * math.cos(a) - dy * math.sin(a), cy + dx * math.sin(a) + dy * math.cos(a)


def _in_rotated_rounded_rect(px, py, cx, cy, hw, hh, r, angle):
    """Check if pixel (px,py) is inside a rotated rounded rectangle."""
    # Transform pixel into card-local coords
    lx, ly = _rot(px, py, cx, cy, -angle)
    lx -= cx
    ly -= cy
    if abs(lx) > hw or abs(ly) > hh:
        return False
    # Corner rounding check
    if abs(lx) > hw - r and abs(ly) > hh - r:
        corner_x = (hw - r) * (1 if lx > 0 else -1)
        corner_y = (hh - r) * (1 if ly > 0 else -1)
        if math.sqrt((lx - corner_x) ** 2 + (ly - corner_y) ** 2) > r:
            return False
    return True


# Block-letter patterns (5x7 grid)
_GLYPHS = {
    '2': [
        [0, 1, 1, 1, 0],
        [1, 0, 0, 0, 1],
        [0, 0, 0, 0, 1],
        [0, 0, 0, 1, 0],
        [0, 0, 1, 0, 0],
        [0, 1, 0, 0, 0],
        [1, 1, 1, 1, 1],
    ],
    'B': [
        [1, 1, 1, 1, 0],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [1, 1, 1, 1, 0],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [1, 1, 1, 1, 0],
    ],
    'N': [
        [1, 0, 0, 0, 1],
        [1, 1, 0, 0, 1],
        [1, 0, 1, 0, 1],
        [1, 0, 0, 1, 1],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
    ],
}


def _draw_glyph(pixels, glyph, ox, oy, scale, color, size, angle=0, rcx=0, rcy=0):
    """Draw a block-letter glyph, optionally rotated around (rcx, rcy)."""
    for ri, row in enumerate(glyph):
        for ci, val in enumerate(row):
            if not val:
                continue
            for dy in range(scale):
                for dx in range(scale):
                    lx = ox + ci * scale + dx
                    ly = oy + ri * scale + dy
                    if angle != 0:
                        lx, ly = _rot(lx, ly, rcx, rcy, angle)
                        lx, ly = round(lx), round(ly)
                    if 0 <= lx < size and 0 <= ly < size:
                        pixels[ly][lx] = color


def generate_png(size=48):
    """Return PNG bytes for two overlapping poker cards matching the in-app logo."""
    pixels = [[_DARK for _ in range(size)] for _ in range(size)]
    s = size  # shorthand

    # Card proportions (playing card ~2.5:3.5 ratio)
    card_w = s * 0.42
    card_h = s * 0.60
    hw, hh = card_w / 2, card_h / 2
    corner_r = max(2, s * 0.06)

    # Card centers and angles (matching the SVG logo)
    back_cx, back_cy, back_angle = s * 0.38, s * 0.52, -10
    front_cx, front_cy, front_angle = s * 0.60, s * 0.48, 8

    # Letter scale
    ls = max(1, round(s / 40))  # scale for "2"
    bn_s = max(1, round(s / 32))  # scale for "BN"

    # Draw back card (slightly transparent feel)
    for y in range(s):
        for x in range(s):
            if _in_rotated_rounded_rect(x, y, back_cx, back_cy, hw, hh, corner_r, back_angle):
                pixels[y][x] = _CARD_BG

    # Draw "2" top-left and "BN" center on back card
    _draw_glyph(pixels, _GLYPHS['2'],
                round(back_cx - hw * 0.65), round(back_cy - hh * 0.70),
                ls, _RED, s, back_angle, back_cx, back_cy)
    # Upper BN
    _draw_glyph(pixels, _GLYPHS['B'],
                round(back_cx - bn_s * 5.5), round(back_cy - bn_s * 5),
                bn_s, _RED, s, back_angle, back_cx, back_cy)
    _draw_glyph(pixels, _GLYPHS['N'],
                round(back_cx + bn_s * 0.5), round(back_cy - bn_s * 5),
                bn_s, _RED, s, back_angle, back_cx, back_cy)
    # Lower BN (inverted)
    _draw_glyph(pixels, _GLYPHS['B'],
                round(back_cx - bn_s * 5.5), round(back_cy + bn_s * 1),
                bn_s, _RED, s, back_angle + 180, back_cx, back_cy)
    _draw_glyph(pixels, _GLYPHS['N'],
                round(back_cx + bn_s * 0.5), round(back_cy + bn_s * 1),
                bn_s, _RED, s, back_angle + 180, back_cx, back_cy)

    # Draw front card (on top)
    for y in range(s):
        for x in range(s):
            if _in_rotated_rounded_rect(x, y, front_cx, front_cy, hw, hh, corner_r, front_angle):
                pixels[y][x] = _CARD_BG2

    # Draw "2" top-left and "BN" center on front card
    _draw_glyph(pixels, _GLYPHS['2'],
                round(front_cx - hw * 0.65), round(front_cy - hh * 0.70),
                ls, _RED, s, front_angle, front_cx, front_cy)
    # Upper BN
    _draw_glyph(pixels, _GLYPHS['B'],
                round(front_cx - bn_s * 5.5), round(front_cy - bn_s * 5),
                bn_s, _RED, s, front_angle, front_cx, front_cy)
    _draw_glyph(pixels, _GLYPHS['N'],
                round(front_cx + bn_s * 0.5), round(front_cy - bn_s * 5),
                bn_s, _RED, s, front_angle, front_cx, front_cy)
    # Lower BN (inverted)
    _draw_glyph(pixels, _GLYPHS['B'],
                round(front_cx - bn_s * 5.5), round(front_cy + bn_s * 1),
                bn_s, _RED, s, front_angle + 180, front_cx, front_cy)
    _draw_glyph(pixels, _GLYPHS['N'],
                round(front_cx + bn_s * 0.5), round(front_cy + bn_s * 1),
                bn_s, _RED, s, front_angle + 180, front_cx, front_cy)

    # Build rows
    rows = []
    for y in range(s):
        row = bytearray()
        for x in range(s):
            r, g, b = pixels[y][x]
            row += bytes([r, g, b, 255])
        rows.append(bytes(row))
    return _make_png(s, s, rows)


def generate_ico(sizes=None):
    """Return ICO bytes containing PNG data for each requested size."""
    if sizes is None:
        sizes = [48, 32, 16]
    png_blobs = [generate_png(s) for s in sizes]
    num = len(sizes)
    header = struct.pack("<HHH", 0, 1, num)
    data_offset = 6 + 16 * num
    entries = b""
    for i, s in enumerate(sizes):
        w = 0 if s >= 256 else s
        blob = png_blobs[i]
        entries += struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32, len(blob), data_offset)
        data_offset += len(blob)
    return header + entries + b"".join(png_blobs)
