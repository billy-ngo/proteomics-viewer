"""
Pro-ker Proteomics Analysis icon generator.

Renders two overlapping poker cards with red "2" and "BN" — matching the
browser favicon SVG. Pure Python (struct + zlib), no Pillow required.

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
# Back card: white at 85% opacity on _DARK background
_CARD_BACK = (0xDB, 0xDC, 0xDC)
_CARD_FRONT = (0xFF, 0xFF, 0xFF)
_BORDER = (0xBB, 0xBB, 0xBB)


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


def _in_rounded_rect(px, py, x0, y0, x1, y1, r):
    """Check if pixel is inside an axis-aligned rounded rectangle."""
    if px < x0 or px > x1 or py < y0 or py > y1:
        return False
    # Corner rounding
    hw = (x1 - x0) / 2
    hh = (y1 - y0) / 2
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2
    lx = abs(px - cx)
    ly = abs(py - cy)
    if lx > hw - r and ly > hh - r:
        return math.sqrt((lx - (hw - r)) ** 2 + (ly - (hh - r)) ** 2) <= r
    return True


def _in_rotated_rounded_rect(px, py, cx, cy, hw, hh, r, angle):
    """Check if pixel (px,py) is inside a rotated rounded rectangle."""
    lx, ly = _rot(px, py, cx, cy, -angle)
    lx -= cx
    ly -= cy
    if abs(lx) > hw or abs(ly) > hh:
        return False
    if abs(lx) > hw - r and abs(ly) > hh - r:
        corner_x = (hw - r) * (1 if lx > 0 else -1)
        corner_y = (hh - r) * (1 if ly > 0 else -1)
        if math.sqrt((lx - corner_x) ** 2 + (ly - corner_y) ** 2) > r:
            return False
    return True


def _on_rotated_rect_border(px, py, cx, cy, hw, hh, r, angle, thickness=1.0):
    """Check if pixel is on the border of a rotated rounded rectangle."""
    return (_in_rotated_rounded_rect(px, py, cx, cy, hw, hh, r, angle) and
            not _in_rotated_rounded_rect(px, py, cx, cy, hw - thickness, hh - thickness, max(0, r - thickness * 0.5), angle))


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
    """Return PNG bytes for two overlapping poker cards matching the browser favicon."""
    pixels = [[_DARK for _ in range(size)] for _ in range(size)]
    s = size

    # Rounded background (matching favicon's rx=12 on 64px → 18.75% of size)
    bg_r = max(2, round(s * 0.1875))
    for y in range(s):
        for x in range(s):
            if _in_rounded_rect(x, y, 0, 0, s - 1, s - 1, bg_r):
                pixels[y][x] = _DARK
            else:
                pixels[y][x] = (0, 0, 0, 0)  # transparent outside rounded rect

    # Card proportions matching favicon SVG (32x45 on 64px canvas → 50%x70%)
    card_w = s * 0.50
    card_h = s * 0.703
    hw, hh = card_w / 2, card_h / 2
    corner_r = max(2, s * 0.047)  # rx=3 on 64px
    border_t = max(0.8, s * 0.012)

    # Card positions matching favicon SVG layout
    # Favicon SVG: 64x64 canvas, translate(2,6) offset
    # Back card: rect(3,3,32,45) rotated -10° around (22,26) in group space
    # Front card: rect(26,1,32,45) rotated 8° around (40,26) in group space
    # After translate: back rot center (24,32), front rot center (42,32)
    back_cx = s * 0.30
    back_cy = s * 0.50
    back_angle = -10

    front_cx = s * 0.62
    front_cy = s * 0.46
    front_angle = 8

    # Letter scales
    ls = max(1, round(s / 48))    # scale for "2"
    bn_s = max(1, round(s / 38))  # scale for "BN"

    # Draw back card (slightly transparent look via blended color)
    for y in range(s):
        for x in range(s):
            if _on_rotated_rect_border(x, y, back_cx, back_cy, hw, hh, corner_r, back_angle, border_t):
                pixels[y][x] = _BORDER
            elif _in_rotated_rounded_rect(x, y, back_cx, back_cy, hw, hh, corner_r, back_angle):
                pixels[y][x] = _CARD_BACK

    # Draw "2" top-left and "BN" center on back card
    _draw_glyph(pixels, _GLYPHS['2'],
                round(back_cx - hw * 0.62), round(back_cy - hh * 0.72),
                ls, _RED, s, back_angle, back_cx, back_cy)
    # Upper BN
    _draw_glyph(pixels, _GLYPHS['B'],
                round(back_cx - bn_s * 5), round(back_cy - bn_s * 4.5),
                bn_s, _RED, s, back_angle, back_cx, back_cy)
    _draw_glyph(pixels, _GLYPHS['N'],
                round(back_cx + bn_s * 0.5), round(back_cy - bn_s * 4.5),
                bn_s, _RED, s, back_angle, back_cx, back_cy)
    # Lower BN (inverted)
    _draw_glyph(pixels, _GLYPHS['B'],
                round(back_cx - bn_s * 5), round(back_cy + bn_s * 0.5),
                bn_s, _RED, s, back_angle + 180, back_cx, back_cy)
    _draw_glyph(pixels, _GLYPHS['N'],
                round(back_cx + bn_s * 0.5), round(back_cy + bn_s * 0.5),
                bn_s, _RED, s, back_angle + 180, back_cx, back_cy)

    # Draw front card (on top, solid white)
    for y in range(s):
        for x in range(s):
            if _on_rotated_rect_border(x, y, front_cx, front_cy, hw, hh, corner_r, front_angle, border_t):
                pixels[y][x] = _BORDER
            elif _in_rotated_rounded_rect(x, y, front_cx, front_cy, hw, hh, corner_r, front_angle):
                pixels[y][x] = _CARD_FRONT

    # Draw "2" top-left and "BN" center on front card
    _draw_glyph(pixels, _GLYPHS['2'],
                round(front_cx - hw * 0.62), round(front_cy - hh * 0.72),
                ls, _RED, s, front_angle, front_cx, front_cy)
    # Upper BN
    _draw_glyph(pixels, _GLYPHS['B'],
                round(front_cx - bn_s * 5), round(front_cy - bn_s * 4.5),
                bn_s, _RED, s, front_angle, front_cx, front_cy)
    _draw_glyph(pixels, _GLYPHS['N'],
                round(front_cx + bn_s * 0.5), round(front_cy - bn_s * 4.5),
                bn_s, _RED, s, front_angle, front_cx, front_cy)
    # Lower BN (inverted)
    _draw_glyph(pixels, _GLYPHS['B'],
                round(front_cx - bn_s * 5), round(front_cy + bn_s * 0.5),
                bn_s, _RED, s, front_angle + 180, front_cx, front_cy)
    _draw_glyph(pixels, _GLYPHS['N'],
                round(front_cx + bn_s * 0.5), round(front_cy + bn_s * 0.5),
                bn_s, _RED, s, front_angle + 180, front_cx, front_cy)

    # Build rows (handle transparent pixels outside rounded background)
    rows = []
    for y in range(s):
        row = bytearray()
        for x in range(s):
            p = pixels[y][x]
            if isinstance(p, tuple) and len(p) == 4:
                row += bytes(p)
            else:
                r, g, b = p
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
