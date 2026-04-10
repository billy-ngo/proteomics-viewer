"""
Pro-ker Proteomics Analysis icon loader.

Loads the bundled icon.ico (designed by the author) and provides it
in ICO and PNG formats for desktop shortcuts and the macOS .app bundle.

Public API
----------
generate_ico() -> bytes          -- the bundled ICO file (16/32/48 px)
generate_png(size=48) -> bytes   -- PNG extracted from the ICO at the
                                    closest available size
"""

import struct
import zlib
from pathlib import Path

_ICO_PATH = Path(__file__).with_name("icon.ico")
_ico_cache = None


def _load_ico():
    global _ico_cache
    if _ico_cache is None:
        _ico_cache = _ICO_PATH.read_bytes()
    return _ico_cache


def generate_ico(sizes=None):
    """Return the bundled ICO bytes."""
    return _load_ico()


def _extract_bmp_to_png(ico_bytes, index):
    """Extract image *index* from an ICO and convert BMP→PNG.

    Handles the common case of uncompressed 8-bpp BMP DIBs stored
    inside ICO files (which is what most icon editors produce).
    Falls back to returning raw data if it's already PNG.
    """
    # Parse ICO directory
    _reserved, _type, count = struct.unpack_from("<HHH", ico_bytes, 0)
    if index >= count:
        index = count - 1
    entry_off = 6 + index * 16
    w, h, colors, _r, _planes, bpp, data_size, data_off = struct.unpack_from(
        "<BBBBHHII", ico_bytes, entry_off
    )
    w = w or 256
    h = h or 256
    data = ico_bytes[data_off : data_off + data_size]

    # If the embedded image is already PNG, return it directly
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return data

    # Otherwise it's a BMP DIB — parse and convert to PNG
    # DIB header
    hdr_size = struct.unpack_from("<I", data, 0)[0]
    dib_w = struct.unpack_from("<i", data, 4)[0]
    dib_h = struct.unpack_from("<i", data, 8)[0]
    # ICO BMPs store height as 2× (image + mask)
    actual_h = abs(dib_h) // 2
    dib_bpp = struct.unpack_from("<H", data, 14)[0]
    dib_compression = struct.unpack_from("<I", data, 16)[0]

    if dib_compression != 0:
        raise ValueError(f"Compressed BMP (type {dib_compression}) not supported")

    # Read colour table for indexed images
    palette = []
    if dib_bpp <= 8:
        n_colors = 1 << dib_bpp
        for i in range(n_colors):
            off = hdr_size + i * 4
            b, g, r, _a = struct.unpack_from("BBBB", data, off)
            palette.append((r, g, b))
        pixel_off = hdr_size + n_colors * 4
    else:
        pixel_off = hdr_size

    # Read pixel data (BMP rows are bottom-up, padded to 4-byte boundary)
    row_bits = dib_w * dib_bpp
    row_bytes = (row_bits + 7) // 8
    row_stride = (row_bytes + 3) & ~3

    # Read AND mask (1-bpp transparency mask after pixel data)
    mask_row_stride = ((dib_w + 31) // 32) * 4
    mask_off = pixel_off + row_stride * actual_h

    rows = []
    for y in range(actual_h):
        # BMP is bottom-up
        src_y = actual_h - 1 - y
        row_off = pixel_off + src_y * row_stride
        mask_row_off = mask_off + src_y * mask_row_stride
        png_row = bytearray()
        for x in range(dib_w):
            # Read transparency from AND mask
            if mask_row_off + x // 8 < len(data):
                mask_byte = data[mask_row_off + x // 8]
                transparent = (mask_byte >> (7 - x % 8)) & 1
            else:
                transparent = 0

            if dib_bpp == 8:
                idx = data[row_off + x]
                r, g, b = palette[idx] if idx < len(palette) else (0, 0, 0)
            elif dib_bpp == 4:
                byte_idx = row_off + x // 2
                if x % 2 == 0:
                    idx = (data[byte_idx] >> 4) & 0xF
                else:
                    idx = data[byte_idx] & 0xF
                r, g, b = palette[idx] if idx < len(palette) else (0, 0, 0)
            elif dib_bpp == 32:
                off = row_off + x * 4
                b, g, r, a = data[off], data[off + 1], data[off + 2], data[off + 3]
                png_row += bytes([r, g, b, a])
                continue
            elif dib_bpp == 24:
                off = row_off + x * 3
                b, g, r = data[off], data[off + 1], data[off + 2]
            else:
                r, g, b = 0, 0, 0

            alpha = 0 if transparent else 255
            png_row += bytes([r, g, b, alpha])
        rows.append(bytes(png_row))

    # Encode as PNG
    return _make_png(dib_w, actual_h, rows)


def _make_png(width, height, rows):
    def _chunk(ct, payload):
        c = ct + payload
        return struct.pack(">I", len(payload)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    raw = b"".join(b"\x00" + r for r in rows)
    return sig + ihdr + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b"")


def generate_png(size=48):
    """Return PNG bytes extracted from the bundled ICO at the closest size."""
    ico = _load_ico()
    _reserved, _type, count = struct.unpack_from("<HHH", ico, 0)

    # Find the image closest to the requested size
    best_idx = 0
    best_diff = 99999
    for i in range(count):
        entry_off = 6 + i * 16
        w = ico[entry_off] or 256
        diff = abs(w - size)
        if diff < best_diff:
            best_diff = diff
            best_idx = i

    return _extract_bmp_to_png(ico, best_idx)
