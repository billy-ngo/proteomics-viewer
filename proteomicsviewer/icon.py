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
_CARD_FACE = (0xFF, 0xFF, 0xFF)


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


def _blend(bg, fg, alpha):
    """Alpha-blend fg over bg.  alpha in [0,1]."""
    r = int(bg[0] * (1 - alpha) + fg[0] * alpha)
    g = int(bg[1] * (1 - alpha) + fg[1] * alpha)
    b = int(bg[2] * (1 - alpha) + fg[2] * alpha)
    return (r, g, b)


def _aa_dist(px, py, cx, cy, hw, hh, r, angle):
    """Return 0..1 coverage for a pixel against a rotated rounded rect.

    1 = fully inside, 0 = fully outside, fractional = edge (anti-alias).
    """
    lx, ly = _rot(px, py, cx, cy, -angle)
    lx -= cx
    ly -= cy
    # Signed distance from rounded rect edge (negative = inside)
    dx = abs(lx) - hw
    dy = abs(ly) - hh
    if dx > 1 or dy > 1:
        return 0.0
    if dx <= -1 and dy <= -1:
        # Well inside — but check corners
        if abs(lx) > hw - r and abs(ly) > hh - r:
            corner_x = (hw - r) * (1 if lx > 0 else -1)
            corner_y = (hh - r) * (1 if ly > 0 else -1)
            d = math.sqrt((lx - corner_x) ** 2 + (ly - corner_y) ** 2) - r
            if d > 1:
                return 0.0
            if d < -1:
                return 1.0
            return max(0.0, min(1.0, 0.5 - d * 0.5))
        return 1.0
    # Near straight edge
    if abs(lx) > hw - r and abs(ly) > hh - r:
        corner_x = (hw - r) * (1 if lx > 0 else -1)
        corner_y = (hh - r) * (1 if ly > 0 else -1)
        d = math.sqrt((lx - corner_x) ** 2 + (ly - corner_y) ** 2) - r
    else:
        d = max(dx, dy)
    if d > 1:
        return 0.0
    if d < -1:
        return 1.0
    return max(0.0, min(1.0, 0.5 - d * 0.5))


def _draw_card(pixels, s, cx, cy, angle, hw, hh, r, border_w):
    """Draw a card with anti-aliased thick dark border and white face."""
    outer_hw = hw + border_w
    outer_hh = hh + border_w
    outer_r = r + border_w * 0.6
    face_hw = hw - max(1, s * 0.02)
    face_hh = hh - max(1, s * 0.02)
    face_r = max(1, r * 0.7)
    for y in range(s):
        for x in range(s):
            outer_a = _aa_dist(x, y, cx, cy, outer_hw, outer_hh, outer_r, angle)
            if outer_a <= 0:
                continue
            face_a = _aa_dist(x, y, cx, cy, face_hw, face_hh, face_r, angle)
            if face_a >= 1.0:
                pixels[y][x] = _blend(pixels[y][x], _CARD_FACE, outer_a)
            elif face_a > 0:
                # Partly on face edge
                pixels[y][x] = _blend(pixels[y][x], _DARK, outer_a)
                pixels[y][x] = _blend(pixels[y][x], _CARD_FACE, face_a)
            else:
                pixels[y][x] = _blend(pixels[y][x], _DARK, outer_a)


# High-resolution "2" glyph — 8x12 grid for smoother rendering
_GLYPH_2 = [
    [0, 0, 1, 1, 1, 1, 0, 0],
    [0, 1, 1, 0, 0, 1, 1, 0],
    [1, 1, 0, 0, 0, 0, 1, 1],
    [0, 0, 0, 0, 0, 0, 1, 1],
    [0, 0, 0, 0, 0, 1, 1, 0],
    [0, 0, 0, 0, 1, 1, 0, 0],
    [0, 0, 0, 1, 1, 0, 0, 0],
    [0, 0, 1, 1, 0, 0, 0, 0],
    [0, 1, 1, 0, 0, 0, 0, 0],
    [1, 1, 0, 0, 0, 0, 0, 0],
    [1, 1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1],
]

# Diamond suit — 7x9 grid
_GLYPH_DIAMOND = [
    [0, 0, 0, 1, 0, 0, 0],
    [0, 0, 1, 1, 1, 0, 0],
    [0, 1, 1, 1, 1, 1, 0],
    [1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1],
    [0, 1, 1, 1, 1, 1, 0],
    [0, 0, 1, 1, 1, 0, 0],
    [0, 0, 0, 1, 0, 0, 0],
]


def _draw_glyph_rotated(pixels, glyph, ox, oy, scale, color, size, angle, rcx, rcy):
    """Draw a bitmap glyph rotated around (rcx, rcy), with AA."""
    rows = len(glyph)
    cols = len(glyph[0]) if rows else 0
    gw = cols * scale
    gh = rows * scale
    # Scan the bounding box of the rotated glyph
    corners = [(ox, oy), (ox + gw, oy), (ox, oy + gh), (ox + gw, oy + gh)]
    rot_corners = [_rot(cx, cy, rcx, rcy, angle) for cx, cy in corners]
    min_rx = max(0, int(min(c[0] for c in rot_corners)) - 1)
    max_rx = min(size - 1, int(max(c[0] for c in rot_corners)) + 2)
    min_ry = max(0, int(min(c[1] for c in rot_corners)) - 1)
    max_ry = min(size - 1, int(max(c[1] for c in rot_corners)) + 2)
    for sy in range(min_ry, max_ry + 1):
        for sx in range(min_rx, max_rx + 1):
            # Inverse-rotate to glyph space
            lx, ly = _rot(sx, sy, rcx, rcy, -angle)
            gx = lx - ox
            gy = ly - oy
            if gx < -0.5 or gx >= gw + 0.5 or gy < -0.5 or gy >= gh + 0.5:
                continue
            gi = int(gy / scale)
            gj = int(gx / scale)
            if 0 <= gi < rows and 0 <= gj < cols and glyph[gi][gj]:
                pixels[sy][sx] = color


def generate_png(size=48):
    """Return PNG bytes for two overlapping '2 of diamonds' cards."""
    pixels = [[_APP_BG for _ in range(size)] for _ in range(size)]
    s = size

    # Rounded dark background with AA
    bg_r = max(2, round(s * 0.1875))
    for y in range(s):
        for x in range(s):
            # Signed distance from rounded rect
            dx = abs(x - (s - 1) / 2) - (s - 1) / 2
            dy = abs(y - (s - 1) / 2) - (s - 1) / 2
            if dx > 0 and dy > 0:
                d = math.sqrt(max(0, dx + bg_r) ** 2 + max(0, dy + bg_r) ** 2) - bg_r
            else:
                d = max(dx, dy)
            if d > 0.5:
                pixels[y][x] = (0, 0, 0, 0)
            elif d > -0.5:
                a = max(0.0, min(1.0, 0.5 - d))
                pixels[y][x] = (
                    int(_APP_BG[0] * a), int(_APP_BG[1] * a), int(_APP_BG[2] * a),
                    int(255 * a),
                )

    # Card dimensions
    card_w = s * 0.42
    card_h = s * 0.62
    hw, hh = card_w / 2, card_h / 2
    corner_r = max(2, s * 0.06)
    border_w = max(1.5, s * 0.035)

    # Back card: offset left, tilted -12°
    back_cx = s * 0.38
    back_cy = s * 0.50
    back_angle = -12
    _draw_card(pixels, s, back_cx, back_cy, back_angle, hw, hh, corner_r, border_w)

    # Front card: offset right, tilted 4°
    front_cx = s * 0.58
    front_cy = s * 0.50
    front_angle = 4
    _draw_card(pixels, s, front_cx, front_cy, front_angle, hw, hh, corner_r, border_w)

    # Glyph scale
    sc = max(1, round(s / 32))

    # -- Front card glyphs (rotated 4°) --
    gw2 = 8 * sc
    gh2 = 12 * sc
    # Large centered "2"
    ox = round(front_cx - gw2 / 2)
    oy = round(front_cy - gh2 / 2)
    _draw_glyph_rotated(pixels, _GLYPH_2, ox, oy, sc, _RED, s, front_angle, front_cx, front_cy)

    # Small diamond below centered "2"
    dsc = max(1, round(s / 64))
    if dsc >= 1:
        dw = 7 * dsc
        dox = round(front_cx - dw / 2)
        doy = oy + gh2 + max(1, round(s * 0.015))
        _draw_glyph_rotated(pixels, _GLYPH_DIAMOND, dox, doy, dsc, _RED, s,
                            front_angle, front_cx, front_cy)

    # -- Back card glyphs (rotated -12°) -- only if large enough to see
    if s >= 32:
        ox_b = round(back_cx - gw2 / 2)
        oy_b = round(back_cy - gh2 / 2)
        _draw_glyph_rotated(pixels, _GLYPH_2, ox_b, oy_b, sc, _RED, s,
                            back_angle, back_cx, back_cy)

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
        sizes = [256, 48, 32, 16]
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
