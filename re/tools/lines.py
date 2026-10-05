"""LINES.LIB, the pictures of Color Lines (1992): a Genus "pcxLib" archive of PCX images.

    python3 re/tools/lines.py list            the entries
    python3 re/tools/lines.py extract [DIR]   each picture as a PNG, and the pieces the game cuts
                                              from them (default assets-local/lines; Pillow)

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


COLOURS = ["green", "red", "magenta", "cyan", "dark-red", "yellow", "blue"]
BALL_FRAMES = [
    (43, "ball"),
    (77, "grow-1"),
    (111, "grow-2"),
    (145, "squashed"),
    (179, "vanish-1"),
    (213, "vanish-2"),
]
LABELS = ["help", "sound", "next", "restart"]


def pieces() -> list[tuple[str, str, int, int, int, int]]:
    """(file, picture, x, y, w, h) of the pieces, where LINES.EXE's tables (init, 346f) put them."""
    out = []
    for c, colour in enumerate(COLOURS):
        for x, frame in BALL_FRAMES:
            out.append((f"balls/{c + 1}-{colour}-{frame}.png", "RS_LNS20", x, 170 + 24 * c, 34, 24))
    out.append(("cells/empty.png", "RS_LNS20", 247, 314, 34, 24))
    for d in range(10):
        out.append((f"digits/{d}.png", "RS_LNS20", 462 + 9 * d, 304, 9, 8))
    out.append(("font/font-9x10.png", "RS_LNS20", 318, 305, 9 * 33, 36))
    for j, label in enumerate(LABELS):
        for i, state in enumerate(("off", "on")):
            out.append((f"buttons/{label}-{state}.png", "RS_LNS20", 148 * j + 74 * i, 340, 72, 10))
    out.append(("panels/top-ten.png", "RS_LNS20", 0, 0, 239, 169))
    out.append(("panels/help.png", "RS_LNS20", 238, 0, 239, 169))
    for k, (x, y) in enumerate(
        [(478, 1), (551, 1), (478, 75), (551, 75), (478, 149), (551, 149), (551, 223)]
    ):
        out.append((f"kings/king-{k + 1}.png", "RS_LNS20", x, y, 72, 73))
    for k, (x, y) in enumerate([(249, 170), (300, 170), (351, 170), (402, 170), (249, 218), (300, 218)]):
        out.append((f"kings/pretender-{k + 1}.png", "RS_LNS20", x, y, 50, 47))
    for k in range(2):
        out.append((f"kings/king-face-{k + 1}.png", "RS_LNS20", 456, 171 + 17 * k, 18, 16))
    for i in range(3):
        for j in range(4):
            out.append((f"trumpeters/{i * 4 + j + 1:02d}.png", "RS_ZST20", j * 87 + 1, i * 48 + 1, 86, 47))
    return out


def extract(out: str) -> None:
    from PIL import Image

    pictures = {}
    os.makedirs(os.path.join(out, "pictures"), exist_ok=True)
    for name, data in entries():
        w, h, px, pal = decode_pcx(data)
        im = Image.new("RGB", (w, h))
        im.putdata([pal[c] for c in px])
        im.save(os.path.join(out, "pictures", name[:-4] + ".png"))
        pictures[name[:-4]] = im
    for file, pic, x, y, w, h in pieces():
        os.makedirs(os.path.dirname(os.path.join(out, file)), exist_ok=True)
        pictures[pic].crop((x, y, x + w, y + h)).save(os.path.join(out, file))
    print(f"{out}: {len(pictures)} pictures, {len(pieces())} pieces")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "list":
        for name, data in entries():
            w = struct.unpack("<H", data[8:10])[0] - struct.unpack("<H", data[4:6])[0] + 1
            h = struct.unpack("<H", data[10:12])[0] - struct.unpack("<H", data[6:8])[0] + 1
            print(f"{name:13} {len(data):7} bytes  {w}x{h}, {data[3]} bit x {data[65]} planes")
    elif cmd == "extract":
        extract(sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "..", "assets-local", "lines"))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
