"""Generate a compact Windows ICO asset without external dependencies."""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path


SIZE = 256


def _blend_pixel(rgba: bytearray, x: int, y: int, color: tuple[int, int, int, int]) -> None:
    if x < 0 or y < 0 or x >= SIZE or y >= SIZE:
        return

    idx = (y * SIZE + x) * 4
    sr, sg, sb, sa = color
    dr, dg, db, da = rgba[idx : idx + 4]
    src_alpha = sa / 255.0
    dst_alpha = da / 255.0
    out_alpha = src_alpha + dst_alpha * (1.0 - src_alpha)
    if out_alpha <= 0:
        rgba[idx : idx + 4] = b"\x00\x00\x00\x00"
        return

    def _channel(src: int, dst: int) -> int:
        value = (src * src_alpha + dst * dst_alpha * (1.0 - src_alpha)) / out_alpha
        return max(0, min(255, round(value)))

    rgba[idx] = _channel(sr, dr)
    rgba[idx + 1] = _channel(sg, dg)
    rgba[idx + 2] = _channel(sb, db)
    rgba[idx + 3] = max(0, min(255, round(out_alpha * 255)))


def _draw_circle(rgba: bytearray, cx: int, cy: int, radius: int, color: tuple[int, int, int, int]) -> None:
    r2 = radius * radius
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            dx = x - cx
            dy = y - cy
            if dx * dx + dy * dy <= r2:
                _blend_pixel(rgba, x, y, color)


def _draw_ring(rgba: bytearray, cx: int, cy: int, radius: int, thickness: int, color: tuple[int, int, int, int]) -> None:
    outer = radius * radius
    inner = max(0, (radius - thickness) * (radius - thickness))
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            dx = x - cx
            dy = y - cy
            dist = dx * dx + dy * dy
            if inner <= dist <= outer:
                _blend_pixel(rgba, x, y, color)


def _draw_line(
    rgba: bytearray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    thickness: int,
    color: tuple[int, int, int, int],
) -> None:
    steps = max(abs(x1 - x0), abs(y1 - y0))
    if steps == 0:
        _draw_circle(rgba, x0, y0, thickness // 2, color)
        return
    for i in range(steps + 1):
        t = i / steps
        x = round(x0 + (x1 - x0) * t)
        y = round(y0 + (y1 - y0) * t)
        _draw_circle(rgba, x, y, thickness // 2, color)


def build_icon() -> bytes:
    rgba = bytearray(SIZE * SIZE * 4)
    bg_top = (13, 17, 23, 255)
    bg_bottom = (26, 32, 44, 255)
    for y in range(SIZE):
        t = y / (SIZE - 1)
        color = tuple(round(bg_top[i] * (1.0 - t) + bg_bottom[i] * t) for i in range(4))
        for x in range(SIZE):
            idx = (y * SIZE + x) * 4
            rgba[idx : idx + 4] = bytes(color)

    # Central cache-card mark.
    _draw_ring(rgba, 128, 128, 82, 14, (67, 176, 255, 255))
    _draw_circle(rgba, 128, 128, 48, (24, 28, 35, 255))
    _draw_circle(rgba, 128, 128, 22, (13, 17, 23, 255))
    _draw_line(rgba, 96, 132, 118, 154, 16, (245, 158, 11, 255))
    _draw_line(rgba, 118, 154, 166, 102, 16, (16, 185, 129, 255))

    # Small "cache blocks" around the ring.
    block_color = (145, 158, 171, 230)
    for angle in range(0, 360, 60):
        rad = math.radians(angle)
        x = round(128 + math.cos(rad) * 108)
        y = round(128 + math.sin(rad) * 108)
        _draw_circle(rgba, x, y, 10, block_color)

    # Accent square in the corner.
    for y in range(46, 78):
        for x in range(178, 210):
            if 178 <= x <= 210 and 46 <= y <= 78:
                _blend_pixel(rgba, x, y, (59, 130, 246, 200))

    png = _encode_png(rgba)
    return _encode_ico_with_png(png)


def _encode_png(rgba: bytes) -> bytes:
    raw = bytearray()
    for y in range(SIZE):
        raw.append(0)
        start = y * SIZE * 4
        raw.extend(rgba[start : start + SIZE * 4])

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)
    compressed = zlib.compress(bytes(raw), level=9)
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", ihdr),
            chunk(b"IDAT", compressed),
            chunk(b"IEND", b""),
        ]
    )


def _encode_ico_with_png(png: bytes) -> bytes:
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22)
    return header + entry + png


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    assets = root / "assets"
    assets.mkdir(exist_ok=True)
    icon_path = assets / "app.ico"
    icon_path.write_bytes(build_icon())
    print(icon_path)


if __name__ == "__main__":
    main()

