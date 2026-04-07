"""
Pro-ker Proteomics Analysis icon generator.

Produces a poker-card icon as PNG bytes using only the Python standard
library (struct + zlib). No Pillow / PIL dependency required.

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
_CARD_BG = (0xF5, 0xF5, 0xF5)
_BORDER = (0xBB, 0xBB, 0xBB)


def _clamp(v, lo=0, hi=255):
    return max(lo, min(hi, int(v)))


def _make_png(width, height, rows):
    def _chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    raw = b""
    for row in rows:
        raw += b"\x00" + row
    idat = _chunk(b"IDAT", zlib.compress(raw, 9))
    iend = _chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _in_rounded_rect(x, y, rx, ry, rw, rh, radius):
    """Check if (x, y) is inside a rounded rectangle."""
    if x < rx or x > rx + rw or y < ry or y > ry + rh:
        return False
    # Check corners
    for cx, cy in [(rx + radius, ry + radius), (rx + rw - radius, ry + radius),
                   (rx + radius, ry + rh - radius), (rx + rw - radius, ry + rh - radius)]:
        if ((x < rx + radius or x > rx + rw - radius) and
                (y < ry + radius or y > ry + rh - radius)):
            if math.sqrt((x - cx) ** 2 + (y - cy) ** 2) > radius:
                return False
    return True


# Simple block-letter patterns for "B" and "N" (5x7 grid each)
_B = [
    [1, 1, 1, 1, 0],
    [1, 0, 0, 0, 1],
    [1, 0, 0, 0, 1],
    [1, 1, 1, 1, 0],
    [1, 0, 0, 0, 1],
    [1, 0, 0, 0, 1],
    [1, 1, 1, 1, 0],
]
_N = [
    [1, 0, 0, 0, 1],
    [1, 1, 0, 0, 1],
    [1, 0, 1, 0, 1],
    [1, 0, 0, 1, 1],
    [1, 0, 0, 0, 1],
    [1, 0, 0, 0, 1],
    [1, 0, 0, 0, 1],
]


def _draw_letter(pixels, letter, ox, oy, scale, color, size):
    for row_i, row in enumerate(letter):
        for col_i, val in enumerate(row):
            if not val:
                continue
            for dy in range(scale):
                for dx in range(scale):
                    px = ox + col_i * scale + dx
                    py = oy + row_i * scale + dy
                    if 0 <= px < size and 0 <= py < size:
                        pixels[py][px] = color


def generate_png(size=48):
    """Return PNG bytes for a poker-card icon at the given size."""
    pixels = [[_DARK for _ in range(size)] for _ in range(size)]

    # Card dimensions (centered, fills most of the icon)
    margin = max(2, size // 10)
    card_w = size - margin * 2
    card_h = size - margin * 2
    card_x = margin
    card_y = margin
    corner_r = max(2, size // 10)

    # Draw card background
    for y in range(size):
        for x in range(size):
            if _in_rounded_rect(x, y, card_x, card_y, card_w, card_h, corner_r):
                pixels[y][x] = _CARD_BG

    # Draw "BN" in red, centered on card
    letter_scale = max(1, size // 24)
    letter_w = 5 * letter_scale
    letter_h = 7 * letter_scale
    gap = max(1, letter_scale)
    total_w = letter_w * 2 + gap
    start_x = card_x + (card_w - total_w) // 2
    start_y = card_y + (card_h - letter_h) // 2

    _draw_letter(pixels, _B, start_x, start_y, letter_scale, _RED, size)
    _draw_letter(pixels, _N, start_x + letter_w + gap, start_y, letter_scale, _RED, size)

    # Build PNG rows
    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            r, g, b = pixels[y][x]
            row += bytes([r, g, b, 255])
        rows.append(bytes(row))

    return _make_png(size, size, rows)


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
        h = w
        blob = png_blobs[i]
        entries += struct.pack(
            "<BBBBHHII", w, h, 0, 0, 1, 32, len(blob), data_offset,
        )
        data_offset += len(blob)

    return header + entries + b"".join(png_blobs)
