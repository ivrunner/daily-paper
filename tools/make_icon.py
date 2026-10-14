"""Generate the Home Screen icons (orange sun on newsprint) with the standard library only.

Run: python tools/make_icon.py
"""
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

PAPER = (241, 237, 228)
ACCENT = (217, 102, 27)
STATIC = Path(__file__).resolve().parent.parent / "static"


def _inside_sun(x: float, y: float) -> bool:
    """Coordinates are in a 0..1 unit square."""
    dx, dy = x - 0.5, y - 0.5
    r = math.hypot(dx, dy)
    if r <= 0.19:
        return True
    if 0.27 <= r <= 0.40:
        angle = math.atan2(dy, dx) % (math.pi / 4)
        return min(angle, math.pi / 4 - angle) * r <= 0.024
    return False


def render(size: int, samples: int = 3) -> bytes:
    rows = []
    for py in range(size):
        row = bytearray([0])  # PNG filter type 0
        for px in range(size):
            hits = sum(_inside_sun((px + (sx + .5) / samples) / size, (py + (sy + .5) / samples) / size)
                       for sx in range(samples) for sy in range(samples))
            t = hits / samples ** 2
            row += bytes(round(p + (a - p) * t) for p, a in zip(PAPER, ACCENT))
        rows.append(bytes(row))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
            + chunk(b"IEND", b""))


if __name__ == "__main__":
    STATIC.mkdir(exist_ok=True)
    (STATIC / "apple-touch-icon.png").write_bytes(render(180))
    (STATIC / "icon-512.png").write_bytes(render(512))
    print("wrote static/apple-touch-icon.png and static/icon-512.png")
