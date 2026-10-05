"""LINES.LIB, the pictures of Color Lines (1992): a Genus "pcxLib" archive of PCX images.

    python3 re/tools/lines.py list            the entries
    python3 re/tools/lines.py extract DIR     each picture as DIR/NAME.png (needs Pillow)

Archive: a header starting "pcxLib", then entries back to back, each 84 bytes of header
(0x01, the 8.3 name NUL-padded to 13 bytes, u32 size, u16 date, u16 time, the rest unused)
followed by the PCX file itself. The PCX files are 16-colour, planar (1 bit x 4 planes), with the
palette in the header.
"""

import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(HERE, "..", "..", "original")
ENTRY = 84


def entries(path: str | None = None) -> list[tuple[str, bytes]]:
    d = open(path or os.path.join(ORIG, "LINES.LIB"), "rb").read()
    if not d.startswith(b"pcxLib"):
        raise ValueError("not a pcxLib archive")
    out = []
    first = re.search(rb"\x01[A-Z0-9_]{1,8}\.[A-Z]{3}\x00", d)
    at = first.start() if first else -1
    while 0 <= at < len(d) - ENTRY:
        if d[at] != 1:
            break
        name = d[at + 1 : at + 14].split(b"\0")[0].decode("ascii")
        (size,) = struct.unpack("<I", d[at + 14 : at + 18])
        data = d[at + ENTRY : at + ENTRY + size]
        if not name or data[:1] != b"\x0a":
            break
        out.append((name, data))
        at += ENTRY + size
    return out


def decode_pcx(data: bytes) -> tuple[int, int, list[int], list[tuple[int, int, int]]]:
    """A 16-colour planar PCX (1 bit x 4 planes, RLE): width, height, pixels, palette.
    Pillow does not read this layout."""
    x0, y0, x1, y1 = struct.unpack("<4H", data[4:12])
    w, h = x1 - x0 + 1, y1 - y0 + 1
    planes, bpl = data[65], struct.unpack("<H", data[66:68])[0]
    pal = [(data[16 + 3 * i], data[17 + 3 * i], data[18 + 3 * i]) for i in range(16)]
    raw = bytearray()
    p, need = 128, h * planes * bpl
    while len(raw) < need and p < len(data):
        c = data[p]
        p += 1
        if c >= 0xC0:
            raw += bytes([data[p]]) * (c - 0xC0)
            p += 1
        else:
            raw.append(c)
    px = [0] * (w * h)
    for y in range(h):
        for pl in range(planes):
            row = raw[(y * planes + pl) * bpl : (y * planes + pl + 1) * bpl]
            for x in range(w):
                if row[x >> 3] & (0x80 >> (x & 7)):
                    px[y * w + x] |= 1 << pl
    return w, h, px, pal


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "list":
        for name, data in entries():
            w = struct.unpack("<H", data[8:10])[0] - struct.unpack("<H", data[4:6])[0] + 1
            h = struct.unpack("<H", data[10:12])[0] - struct.unpack("<H", data[6:8])[0] + 1
            print(f"{name:13} {len(data):7} bytes  {w}x{h}, {data[3]} bit x {data[65]} planes")
    elif cmd == "extract" and len(sys.argv) > 2:
        from PIL import Image

        os.makedirs(sys.argv[2], exist_ok=True)
        for name, data in entries():
            w, h, px, pal = decode_pcx(data)
            im = Image.new("RGB", (w, h))
            im.putdata([pal[c] for c in px])
            im.save(os.path.join(sys.argv[2], name[:-4] + ".png"))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
