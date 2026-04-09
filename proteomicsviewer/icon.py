"""
Pro-ker Proteomics Analysis icon generator.

Renders two overlapping "2 of diamonds" playing cards with thick dark
borders, matching the in-app SVG logo.  Pure Python (struct + zlib),
no Pillow required.

Public API
----------
generate_png(size=48) -> bytes   -- RGBA PNG
generate_ico(sizes=[48,32,16]) -> bytes  -- ICO wrapping PNG data
"""

import math
import struct
import zlib

_RED = (0xDC, 0x26, 0x26)
_DARK = (0x22, 0x22, 0x22)
_APP_BG = (0x0D, 0x11, 0x17)
_CARD_EDGE = (0xF5, 0xF5, 0xF5)
_CARD_FACE = (0xFF, 0xFF, 0xFF)
_INNER_BORDER = (0xDD, 0xDD, 0xDD)


def _make_png(width, height, rows):
    def _chunk(ct, data):
        c = ct + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    raw = b"".join(b"\x00" + r for r in rows)
    return sig + ihdr + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b"")


def _rot(x, y, cx, cy, angle_deg):
    a = math.radians(angle_deg)
    dx, dy = x - cx, y - cy
    return cx + dx * math.cos(a) - dy * math.sin(a), cy + dx * math.sin(a) + dy * math.cos(a)


def _in_rounded_rect(px, py, x0, y0, x1, y1, r):
    if px < x0 or px > x1 or py < y0 or py > y1:
        return False
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


def _draw_card(pixels, s, cx, cy, angle, hw, hh, r, border_w):
    """Draw a card with thick dark border, gray edge, and white face."""
    outer_hw = hw + border_w
    outer_hh = hh + border_w
    outer_r = r + border_w * 0.6
    edge_hw = hw
    edge_hh = hh
    face_hw = hw - max(1, s * 0.025)
    face_hh = hh - max(1, s * 0.025)
    face_r = max(1, r - 1)
    for y in range(s):
        for x in range(s):
            if _in_rotated_rounded_rect(x, y, cx, cy, outer_hw, outer_hh, outer_r, angle):
                if _in_rotated_rounded_rect(x, y, cx, cy, face_hw, face_hh, face_r, angle):
                    pixels[y][x] = _CARD_FACE
                elif _in_rotated_rounded_rect(x, y, cx, cy, edge_hw, edge_hh, r, angle):
                    pixels[y][x] = _CARD_EDGE
                else:
                    pixels[y][x] = _DARK


# "2" glyph on a 5x7 grid
_GLYPH_2 = [
    [0, 1, 1, 1, 0],
    [1, 0, 0, 0, 1],
    [0, 0, 0, 0, 1],
    [0, 0, 0, 1, 0],
    [0, 0, 1, 0, 0],
    [0, 1, 0, 0, 0],
    [1, 1, 1, 1, 1],
]

# Diamond suit as a simple 5x7 grid
_GLYPH_DIAMOND = [
    [0, 0, 1, 0, 0],
    [0, 1, 1, 1, 0],
    [1, 1, 1, 1, 1],
    [0, 1, 1, 1, 0],
    [0, 0, 1, 0, 0],
]


def _draw_glyph(pixels, glyph, ox, oy, scale, color, size):
    for ri, row in enumerate(glyph):
        for ci, val in enumerate(row):
            if not val:
                continue
            for dy in range(scale):
                for dx in range(scale):
                    lx = ox + ci * scale + dx
                    ly = oy + ri * scale + dy
                    if 0 <= lx < size and 0 <= ly < size:
                        pixels[ly][lx] = color


def _draw_glyph_rotated(pixels, glyph, ox, oy, scale, color, size, angle, rcx, rcy):
    for ri, row in enumerate(glyph):
        for ci, val in enumerate(row):
            if not val:
                continue
            for dy in range(scale):
                for dx in range(scale):
                    lx = ox + ci * scale + dx
                    ly = oy + ri * scale + dy
                    rx, ry = _rot(lx, ly, rcx, rcy, angle)
                    rx, ry = round(rx), round(ry)
                    if 0 <= rx < size and 0 <= ry < size:
                        pixels[ry][rx] = color


def generate_png(size=48):
    """Return PNG bytes for two overlapping '2 of diamonds' cards."""
    pixels = [[_APP_BG for _ in range(size)] for _ in range(size)]
    s = size

    # Rounded dark background
    bg_r = max(2, round(s * 0.1875))
    for y in range(s):
        for x in range(s):
            if not _in_rounded_rect(x, y, 0, 0, s - 1, s - 1, bg_r):
                pixels[y][x] = (0, 0, 0, 0)

    # Card dimensions
    card_w = s * 0.44
    card_h = s * 0.64
    hw, hh = card_w / 2, card_h / 2
    corner_r = max(2, s * 0.06)
    border_w = max(1.5, s * 0.04)

    # Back card: offset left, tilted -12
    back_cx = s * 0.36
    back_cy = s * 0.50
    back_angle = -12
    _draw_card(pixels, s, back_cx, back_cy, back_angle, hw, hh, corner_r, border_w)

    # Front card: offset right, tilted 4
    front_cx = s * 0.58
    front_cy = s * 0.50
    front_angle = 4
    _draw_card(pixels, s, front_cx, front_cy, front_angle, hw, hh, corner_r, border_w)

    # Draw "2" centered on front card
    sc = max(1, round(s / 22))
    gw = 5 * sc
    gh = 7 * sc
    ox = round(front_cx - gw / 2)
    oy = round(front_cy - gh / 2)
    _draw_glyph(pixels, _GLYPH_2, ox, oy, sc, _RED, s)

    # Small diamond below the "2" on front card
    dsc = max(1, round(s / 48))
    if dsc >= 1:
        dox = round(front_cx - 2.5 * dsc)
        doy = oy + gh + max(1, round(s * 0.02))
        _draw_glyph(pixels, _GLYPH_DIAMOND, dox, doy, dsc, _RED, s)

    # Build rows
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
