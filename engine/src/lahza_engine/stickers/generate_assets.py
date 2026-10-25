"""Reproduce Lahza's original geometric stickers using only the standard library."""
import math
import struct
import zlib
from pathlib import Path


def write_png(path: Path, width: int, height: int, pixel) -> None:
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
    raw = b''.join(b'\0' + bytes(c for x in range(width) for c in pixel(x, y)) for y in range(height))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 6, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def generate() -> None:
    root = Path(__file__).parent / 'assets'
    root.mkdir(exist_ok=True)
    def spark(x, y):
        dx, dy = abs(x - 64), abs(y - 64)
        return (255, 202, 40, 255) if dx + dy < 56 and min(dx, dy) < 14 else (0, 0, 0, 0)
    def heart(x, y):
        a, b = (x - 64) / 49, -(y - 62) / 49
        inside = (a*a + b*b - 1)**3 - a*a*b**3 <= 0
        return (244, 75, 118, 255) if inside else (0, 0, 0, 0)
    def arrow(x, y):
        inside = (16 < x < 79 and 52 < y < 76) or (65 < x < 116 and abs(y - 64) < (116-x)*math.tan(.65))
        return (61, 214, 194, 255) if inside else (0, 0, 0, 0)
    for name, pixel in [('spark', spark), ('heart', heart), ('arrow', arrow)]:
        write_png(root / f'{name}.png', 128, 128, pixel)


if __name__ == '__main__':
    generate()
