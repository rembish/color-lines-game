"""A ten-second comic-book trailer: the pretender knocks the king out and takes his crown.

    uv run --with numpy tools/trailer.py [SOURCE] [OUT.mp4]

SOURCE is your own LINES.LIB (default original/LINES.LIB) or a folder of its pictures as PNG
(`re/tools/lines.py extract DIR`). Every sprite is cut from the original's pictures at run time;
nothing of the original is in this file. The music and the sound effects are synthesised here.
Needs ffmpeg; writes clips/trailer.mp4 and clips/trailer.gif (git-ignored, like tools/clips.sh).
"""

import math
import os
import random
import subprocess
import sys
import wave
from functools import cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "re", "tools"))

W, H, FPS = 1280, 720, 30
PY = 480 / 350  # EGA 640x350 pixels are taller than wide on a 4:3 screen
SR = 44100
INK = (12, 10, 20, 255)
PAPER = (250, 243, 222, 255)

# Shots, in frames: (start, end)
SHOTS = {
    "open": (0, 36),
    "vs": (36, 82),
    "grind": (82, 114),
    "sweat": (114, 140),
    "strike": (140, 160),
    "hit": (160, 194),
    "ko": (194, 248),
    "end": (248, 298),
}
N = SHOTS["end"][1]
HIT = SHOTS["hit"][0] + 11  # the frame the pretender connects

# --- fonts (Google Fonts, OFL; fetched once into clips/fonts) --------------------------------

FONT_URLS = {
    "Bangers.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/bangers/Bangers-Regular.ttf",
    "ComicNeue-Bold.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/comicneue/ComicNeue-Bold.ttf",
}
FONT_DIR = os.path.join(ROOT, "clips", "fonts")


def fetch_fonts() -> None:
    os.makedirs(FONT_DIR, exist_ok=True)
    for name, url in FONT_URLS.items():
        p = os.path.join(FONT_DIR, name)
        if not os.path.exists(p):
            subprocess.run(["curl", "-sSfL", "-o", p, url], check=True)


@cache
def font(size: int, name: str = "Bangers.ttf") -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


# --- the original's pictures -------------------------------------------------------------------


def load_pictures(src: str) -> dict[str, Image.Image]:
    names = ["RS_LNS20", "RS_ZST20", "FL_LNS20", "ZS_LNS20"]
    if os.path.isdir(src):
        return {n: Image.open(os.path.join(src, n + ".png")).convert("RGB") for n in names}
    import lines

    out = {}
    for name, data in lines.entries(src):
        w, h, px, pal = lines.decode_pcx(data)
        im = Image.new("RGB", (w, h))
        im.putdata([pal[c] for c in px])
        out[name[:-4]] = im
    return {n: out[n] for n in names}


def key_black(im: Image.Image) -> Image.Image:
    """RGBA with the black connected to the border made transparent (the eyes stay black)."""
    a = np.asarray(im.convert("RGB"))
    blk = a.sum(-1) == 0
    reach = np.zeros_like(blk)
    reach[0], reach[-1], reach[:, 0], reach[:, -1] = blk[0], blk[-1], blk[:, 0], blk[:, -1]
    while True:
        r = reach.copy()
        r[1:] |= reach[:-1]
        r[:-1] |= reach[1:]
        r[:, 1:] |= reach[:, :-1]
        r[:, :-1] |= reach[:, 1:]
        r &= blk
        if (r == reach).all():
            break
        reach = r
    return Image.fromarray(np.dstack([a, np.where(reach, 0, 255).astype(np.uint8)]))


class Sprites:
    BALLS = ["green", "red", "magenta", "cyan", "dark-red", "yellow", "blue"]
    PHASES = ["ball", "grow-1", "grow-2", "squashed", "vanish-1", "vanish-2"]

    def __init__(self, pics: dict[str, Image.Image]) -> None:
        rs, zst = pics["RS_LNS20"], pics["RS_ZST20"]

        def cut(im: Image.Image, x: int, y: int, w: int, h: int) -> Image.Image:
            return im.crop((x, y, x + w, y + h))

        kx = [(478, 1), (551, 1), (478, 75), (551, 75), (478, 149), (551, 149), (551, 223)]
        self.king = [key_black(cut(rs, x, y, 72, 73)) for x, y in kx]
        px = [(249, 170), (300, 170), (351, 170), (402, 170), (249, 218), (300, 218)]
        self.pretender = [key_black(cut(rs, x, y, 50, 47)) for x, y in px]
        self.face = [key_black(cut(rs, 456, 171, 18, 16)), key_black(cut(rs, 571, 30, 18, 16))]
        self.crown = key_black(cut(self.king[0], 18, 6, 25, 22))
        self.cell = cut(rs, 247, 314, 34, 24)
        self.ball = {
            (c, p): cut(rs, 43 + 34 * j, 170 + 24 * i, 34, 24)
            for i, c in enumerate(self.BALLS)
            for j, p in enumerate(self.PHASES)
        }
        cell = np.asarray(self.cell)
        self.loose = {}  # balls without their cell, for the debris
        for c in self.BALLS:
            b = np.asarray(self.ball[(c, "ball")])
            alpha = np.where((b == cell).all(-1), 0, 255).astype(np.uint8)
            self.loose[c] = Image.fromarray(np.dstack([b, alpha]))
        self.digits = [cut(rs, 30, 120, 9, 8)] + [cut(rs, 31, 30 + 10 * i, 9, 8) for i in range(9)]
        self.trumpeter = [key_black(cut(zst, 1 + 87 * (i % 4), 1 + 48 * (i // 4), 86, 47)) for i in range(12)]
        title = pics["ZS_LNS20"]
        self.title = title
        self.logo = key_black(title.crop((0, 48, 640, 120)))
        self.screen = pics["FL_LNS20"]
        self.pillar = pics["FL_LNS20"].crop((60, 150, 114, 239))


# --- drawing helpers ----------------------------------------------------------------------------


def up(im: Image.Image, k: float) -> Image.Image:
    return im.resize((max(1, round(im.width * k)), max(1, round(im.height * k * PY))), Image.NEAREST)


def outlined(im: Image.Image, ink: int = 7, rim: int = 5) -> Image.Image:
    """The comic look: a thick black line and a white rim around a sprite."""
    pad = ink + rim + 4
    base = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    base.paste(im, (pad, pad))
    a = base.getchannel("A")

    def grow(r: int) -> Image.Image:
        return a.filter(ImageFilter.GaussianBlur(r * 0.55)).point(lambda v: 255 if v > 6 else 0)

    out = Image.new("RGBA", base.size, (0, 0, 0, 0))
    out.paste(Image.new("RGBA", base.size, (255, 255, 255, 255)), (0, 0), grow(ink + rim))
    out.paste(Image.new("RGBA", base.size, INK), (0, 0), grow(ink))
    out.alpha_composite(base)
    return out


def paste(
    dst: Image.Image,
    im: Image.Image,
    cx: float,
    cy: float,
    scale: float = 1.0,
    angle: float = 0.0,
    alpha: float = 1.0,
    smooth: bool = False,
) -> None:
    """Composite `im` centred at (cx, cy), scaled and rotated, clipped to `dst`."""
    if scale != 1.0:
        im = im.resize(
            (max(1, round(im.width * scale)), max(1, round(im.height * scale))),
            Image.BICUBIC if smooth else Image.NEAREST,
        )
    if angle:
        im = im.rotate(angle, Image.BICUBIC if smooth else Image.NEAREST, expand=True)
    if alpha < 1.0:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: round(v * alpha)))
    x, y = round(cx - im.width / 2), round(cy - im.height / 2)
    sx, sy = max(0, -x), max(0, -y)
    ex, ey = min(im.width, dst.width - x), min(im.height, dst.height - y)
    if ex <= sx or ey <= sy:
        return
    dst.alpha_composite(im.crop((sx, sy, ex, ey)), (x + sx, y + sy))


def text(
    txt: str,
    size: int,
    fill: tuple[int, ...],
    stroke: int = 8,
    depth: int = 8,
    name: str = "Bangers.ttf",
    stroke_fill: tuple[int, ...] = INK,
) -> Image.Image:
    """Lettering with a stroke and an extruded shadow."""
    f = font(size, name)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    lft, t, r, b = probe.multiline_textbbox((0, 0), txt, font=f, stroke_width=stroke, align="center")
    pad = stroke + depth + 4
    im = Image.new("RGBA", (math.ceil(r - lft) + 2 * pad, math.ceil(b - t) + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    org = (pad - lft, pad - t)
    for k in range(depth, 0, -1):
        d.multiline_text(
            (org[0] + k, org[1] + k),
            txt,
            font=f,
            fill=INK,
            stroke_width=stroke,
            stroke_fill=INK,
            align="center",
        )
    d.multiline_text(
        org, txt, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill, align="center"
    )
    return im


def caption(txt: str, size: int = 34, bg: tuple[int, ...] = (255, 226, 70, 255)) -> Image.Image:
    """A narration box: yellow, black frame, hard shadow."""
    f = font(size, "ComicNeue-Bold.ttf")
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    lft, t, r, b = probe.multiline_textbbox((0, 0), txt, font=f, align="center")
    w, h = math.ceil(r - lft) + 36, math.ceil(b - t) + 22
    im = Image.new("RGBA", (w + 8, h + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((8, 8, w + 7, h + 7), fill=INK)
    d.rectangle((0, 0, w - 1, h - 1), fill=bg, outline=INK, width=4)
    d.multiline_text((18 - lft, 11 - t), txt, font=f, fill=INK, align="center")
    return im


def bubble(
    dst: Image.Image, cx: float, cy: float, txt: str, size: int, tail: tuple[float, float], pop: float = 1.0
) -> None:
    """A speech balloon at (cx, cy) pointing at `tail`; `pop` 0..1 scales it in."""
    f = font(round(size * max(pop, 0.05)), "Bangers.ttf")
    d = ImageDraw.Draw(dst)
    lft, t, r, b = d.multiline_textbbox((0, 0), txt, font=f, align="center")
    rw, rh = (r - lft) * 0.62 + 34 * pop, (b - t) * 0.62 + 30 * pop
    ang = math.atan2(tail[1] - cy, tail[0] - cx)
    nx, ny = -math.sin(ang), math.cos(ang)
    bx, by = cx + math.cos(ang) * rw * 0.6, cy + math.sin(ang) * rh * 0.6
    tx, ty = cx + (tail[0] - cx) * pop, cy + (tail[1] - cy) * pop
    base = [(bx + nx * 22 * pop, by + ny * 22 * pop), (bx - nx * 22 * pop, by - ny * 22 * pop)]
    d.polygon([*base, (tx, ty)], fill=(255, 255, 255, 255), outline=INK, width=6)
    d.ellipse((cx - rw, cy - rh, cx + rw, cy + rh), fill=(255, 255, 255, 255), outline=INK, width=6)
    inner = [
        (bx + nx * 16 * pop - math.cos(ang) * 30, by + ny * 16 * pop - math.sin(ang) * 30),
        (bx - nx * 16 * pop - math.cos(ang) * 30, by - ny * 16 * pop - math.sin(ang) * 30),
        (tx - math.cos(ang) * 9, ty - math.sin(ang) * 9),
    ]
    d.polygon(inner, fill=(255, 255, 255, 255))
    d.multiline_text((cx - (r - lft) / 2 - lft, cy - (b - t) / 2 - t), txt, font=f, fill=INK, align="center")


def burst_points(cx: float, cy: float, r1: float, r2: float, n: int, seed: int) -> list[tuple[float, float]]:
    rnd = random.Random(seed)
    pts = []
    for i in range(2 * n):
        a = math.pi * i / n + rnd.uniform(-0.08, 0.08)
        r = (r2 * rnd.uniform(0.85, 1.15)) if i % 2 == 0 else r1
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r * 0.8))
    return pts


def burst(
    dst: Image.Image,
    cx: float,
    cy: float,
    r1: float,
    r2: float,
    fill: tuple[int, ...],
    n: int = 14,
    seed: int = 1,
    rim: tuple[int, ...] | None = (255, 255, 255, 255),
) -> None:
    d = ImageDraw.Draw(dst)
    if rim:
        d.polygon(burst_points(cx, cy, r1 + 22, r2 + 30, n, seed), fill=INK)
        d.polygon(burst_points(cx, cy, r1 + 12, r2 + 18, n, seed), fill=rim)
    d.polygon(burst_points(cx, cy, r1 + 6, r2 + 8, n, seed), fill=INK)
    d.polygon(burst_points(cx, cy, r1, r2, n, seed), fill=fill)


def star(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, rot: float, fill: tuple[int, ...]) -> None:
    pts = [
        (
            cx + math.cos(rot + math.pi * i / 5) * (r if i % 2 == 0 else r * 0.45),
            cy + math.sin(rot + math.pi * i / 5) * (r if i % 2 == 0 else r * 0.45),
        )
        for i in range(10)
    ]
    d.polygon(pts, fill=fill, outline=INK, width=4)


_YY, _XX = np.mgrid[0:H, 0:W].astype(np.float32)


def halftone(
    bg: tuple[int, ...],
    fg: tuple[int, ...],
    cx: float,
    cy: float,
    step: float = 22,
    rmin: float = 1.0,
    rmax: float = 11.0,
    reach: float = 900,
) -> Image.Image:
    """Ben-Day dots growing away from (cx, cy)."""
    c, s = math.cos(math.pi / 4), math.sin(math.pi / 4)
    u, v = (_XX * c - _YY * s) / step, (_XX * s + _YY * c) / step
    du, dv = u - np.round(u), v - np.round(v)
    dist = np.sqrt(du * du + dv * dv) * step
    rr = rmin + (rmax - rmin) * np.clip(np.hypot(_XX - cx, _YY - cy) / reach, 0, 1)
    m = (dist < rr)[..., None]
    out = np.where(m, np.array(fg[:3], np.uint8), np.array(bg[:3], np.uint8))
    return Image.fromarray(out.astype(np.uint8)).convert("RGBA")


def rays(c1: tuple[int, ...], c2: tuple[int, ...], cx: float, cy: float, n: int, rot: float) -> Image.Image:
    ang = (np.arctan2(_YY - cy, _XX - cx) + rot) % (2 * math.pi)
    m = (np.floor(ang / (2 * math.pi) * 2 * n).astype(int) % 2 == 0)[..., None]
    out = np.where(m, np.array(c1[:3], np.uint8), np.array(c2[:3], np.uint8))
    return Image.fromarray(out.astype(np.uint8)).convert("RGBA")


def speed_lines(
    dst: Image.Image, cx: float, cy: float, inner: float, seed: int, n: int = 70, color: tuple[int, ...] = INK
) -> None:
    """Radial action lines converging on (cx, cy), leaving a clear centre."""
    rnd = random.Random(seed)
    d = ImageDraw.Draw(dst)
    for _ in range(n):
        a = rnd.uniform(0, 2 * math.pi)
        r0 = inner * rnd.uniform(1.0, 1.6)
        wdt = rnd.uniform(0.006, 0.02)
        far = 1600
        d.polygon(
            [
                (cx + math.cos(a) * r0, cy + math.sin(a) * r0),
                (cx + math.cos(a - wdt) * far, cy + math.sin(a - wdt) * far),
                (cx + math.cos(a + wdt) * far, cy + math.sin(a + wdt) * far),
            ],
            fill=color,
        )


def hlines(dst: Image.Image, seed: int, n: int = 40, color: tuple[int, ...] = (255, 255, 255, 200)) -> None:
    rnd = random.Random(seed)
    d = ImageDraw.Draw(dst)
    for _ in range(n):
        y = rnd.uniform(0, H)
        x = rnd.uniform(-200, W)
        ln = rnd.uniform(150, 600)
        th = rnd.uniform(2, 7)
        d.polygon([(x, y), (x + ln, y - th / 2), (x + ln, y + th / 2)], fill=color)


def panel(dst: Image.Image, content: Image.Image, poly: list[tuple[float, float]], border: int = 9) -> None:
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon(poly, fill=255)
    dst.paste(content, (0, 0), mask)
    ImageDraw.Draw(dst).line([*poly, poly[0]], fill=INK, width=border, joint="curve")


def page() -> Image.Image:
    return halftone(PAPER, (236, 226, 200), W / 2, H / 2, step=14, rmin=1.2, rmax=1.2)


def ease_out(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def ease_back(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    c = 1.9
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def slam(t: float, frames: float = 6, start: float = 2.6) -> float:
    """A scale that crashes from `start` down to 1 with a little bounce."""
    if t < 0:
        return 0.0
    k = min(t / frames, 1.0)
    return 1 + (start - 1) * (1 - ease_back(k)) if k < 1 else 1.0


def ball_cell(sp: Sprites, color: str | None, phase: str = "ball") -> Image.Image:
    return sp.cell if color is None else sp.ball[(color, phase)]


def board(sp: Sprites, grid: list[list[tuple[str | None, str]]]) -> Image.Image:
    rows, cols = len(grid), len(grid[0])
    im = Image.new("RGB", (cols * 34, rows * 24))
    for r in range(rows):
        for c in range(cols):
            col, ph = grid[r][c]
            im.paste(ball_cell(sp, col, ph), (c * 34, r * 24))
    return im.convert("RGBA")


def score(sp: Sprites, value: int, k: float) -> Image.Image:
    s = f"{value:>3}"
    im = Image.new("RGBA", (9 * len(s) + 8, 14), (0, 0, 0, 255))
    for i, ch in enumerate(s):
        if ch != " ":
            im.paste(sp.digits[int(ch)], (4 + 9 * i, 3))
    return outlined(up(im, k), 5, 4)


class Debris:
    """Bits of a popped ball: they fly out and fall."""

    def __init__(self, x: float, y: float, color: tuple[int, ...], t0: int, seed: int, n: int = 9) -> None:
        rnd = random.Random(seed)
        self.t0, self.color = t0, color
        self.parts = [
            (x, y, rnd.uniform(-16, 16), rnd.uniform(-22, -6), rnd.uniform(8, 18)) for _ in range(n)
        ]

    def draw(self, dst: Image.Image, t: int) -> None:
        dt = t - self.t0
        if dt < 0 or dt > 30:
            return
        d = ImageDraw.Draw(dst)
        for x, y, vx, vy, s in self.parts:
            px, py = x + vx * dt, y + vy * dt + 1.6 * dt * dt
            d.rectangle(
                (px - s / 2, py - s / 2, px + s / 2, py + s / 2), fill=self.color, outline=INK, width=3
            )


BALL_RGB = {
    "red": (255, 40, 40, 255),
    "yellow": (255, 230, 40, 255),
    "blue": (60, 60, 255, 255),
    "magenta": (255, 60, 255, 255),
    "green": (40, 190, 40, 255),
    "cyan": (60, 240, 240, 255),
    "dark-red": (170, 0, 0, 255),
}


# --- the shots ------------------------------------------------------------------------------------


class Trailer:
    def __init__(self, sp: Sprites) -> None:
        self.sp = sp
        self.king = [outlined(up(k, 4.6)) for k in sp.king]
        self.king_small = outlined(up(sp.king[6], 2.2), 5, 3)
        self.pret = [outlined(up(p, 6.4)) for p in sp.pretender]
        self.face = [outlined(up(f, 17), 9, 6) for f in sp.face]
        self.crown = outlined(up(sp.crown, 6.4), 7, 5)
        self.king_hit = [outlined(up(k, 3.4)) for k in sp.king]
        self.pret_hit = outlined(up(sp.pretender[0], 4.8))
        self.crown_hit = outlined(up(sp.crown, 3.4), 6, 4)
        self.trump = [outlined(up(t, 2.4), 5, 3) for t in sp.trumpeter]
        self.logo = outlined(up(sp.logo, 1.85), 7, 5)
        title = sp.title.crop((0, 40, 640, 330)).convert("RGBA")
        self.title = up(title, 1.45)
        self.pillar_img = sp.pillar.convert("RGBA")
        self.bg_red = halftone((200, 20, 30), (255, 170, 40), 330, 360, rmax=12)
        self.bg_purple = halftone((90, 20, 140), (240, 80, 240), 950, 360, rmax=12)
        self.bg_navy = halftone((20, 24, 70), (50, 70, 170), W / 2, H / 2, rmax=10)
        self.bg_gold = halftone((255, 196, 0), (255, 240, 120), 950, 330, rmax=10)
        self.paper = page()
        grind = [[(None, "ball")] * 7 for _ in range(3)]
        grind[0] = [
            (None, "ball"),
            ("yellow", "ball"),
            (None, "ball"),
            ("cyan", "ball"),
            (None, "ball"),
            ("green", "ball"),
            ("magenta", "ball"),
        ]
        grind[1] = [("red", "ball")] * 4 + [(None, "ball"), ("blue", "ball"), (None, "ball")]
        grind[2] = [
            (None, "ball"),
            ("cyan", "ball"),
            (None, "ball"),
            (None, "ball"),
            ("red", "ball"),
            ("yellow", "ball"),
            (None, "ball"),
        ]
        self.grind_grid = grind
        cell_w, cell_h = 34 * 4, round(24 * 4 * PY)
        self.cell_wh = (cell_w, cell_h)
        self.board_xy = ((W - 7 * cell_w) / 2, 250)
        self.debris = [
            Debris(
                self.board_xy[0] + (c + 0.5) * cell_w,
                self.board_xy[1] + 1.5 * cell_h,
                BALL_RGB["red"],
                12 + 2 * c + 4,
                seed=c,
            )
            for c in range(5)
        ]

    # 0. cold open: the title slams in, the trumpeters blow
    def open(self, t: int) -> Image.Image:
        f = rays((25, 30, 110), (40, 50, 150), W / 2, H / 2, 16, t * 0.02)
        f.alpha_composite(halftone((0, 0, 0), (90, 110, 230), W / 2, H / 2, rmax=7), (0, 0))
        f = Image.blend(rays((25, 30, 110), (40, 50, 150), W / 2, H / 2, 16, t * 0.02), f, 0.35)
        s = slam(t, 7, 2.4)
        if s:
            card = Image.new("RGBA", (self.title.width + 24, self.title.height + 24), INK)
            card.paste(self.title, (12, 12))
            paste(f, card, W / 2, H / 2 + 10, s * 0.92, -2.5, smooth=True)
        if t >= 6:
            pose = 0 if t < 14 else (4 if t < 18 else 8)
            for i, (x, c) in enumerate([(150, 0), (W - 150, 3)]):
                bob = math.sin((t + i * 3) * 0.9) * 4
                im = self.trump[pose + c]
                if i == 1:
                    im = ImageOps.mirror(im)
                paste(f, im, x - (1 - ease_out((t - 6) / 6)) * (300 if i == 0 else -300), 600 + bob)
        if t >= 3:
            paste(f, caption("MOSCOW, 1992.", 36), 210 - 400 * (1 - ease_out((t - 3) / 6)), 70, angle=2)
        if t >= 18:
            paste(
                f, text("TA-DAAA!", 70, (255, 230, 60, 255), 7, 6), W / 2 + 380, 120, slam(t - 18, 5, 1.8), 8
            )
        if t >= 22:
            paste(
                f,
                caption("ONE BOARD.  ONE CROWN.", 40, (255, 255, 255, 255)),
                W / 2,
                655 + 120 * (1 - ease_out((t - 22) / 5)),
            )
        return f

    # 1. the line-up
    def vs(self, t: int) -> Image.Image:
        f = self.paper.copy()
        split = [(0, 0), (700, 0), (580, H), (0, H)]
        right = [(720, 0), (W, 0), (W, H), (600, H)]
        left = self.bg_red.copy()
        speed_lines(left, 300, 380, 230, seed=t // 2, n=50, color=(255, 230, 120, 255))
        kx = 300 - 700 * (1 - ease_out(t / 7))
        paste(left, self.king[0], kx, 395)
        panel(f, left, split)
        rt = self.bg_purple.copy()
        speed_lines(rt, 960, 400, 230, seed=99 + t // 2, n=50, color=(255, 160, 255, 255))
        px = 960 + 700 * (1 - ease_out((t - 6) / 7))
        paste(rt, self.pret[0], px, 420)
        panel(f, rt, right)
        if t >= 3:
            paste(f, text("THE KING", 86, (255, 226, 60, 255), 8, 7), 250, 90, slam(t - 3, 5, 1.6), 4)
            paste(f, caption("100 POINTS. NEVER LOST.\nVERY ROUND.", 26), 230, 640)
        if t >= 9:
            paste(f, text("THE PRETENDER", 80, (255, 255, 255, 255), 8, 7), 1000, 90, slam(t - 9, 5, 1.6), -4)
            paste(f, caption("0 POINTS. ONE SWORD.\nZERO CHILL.", 26), 1060, 640)
        if t >= 16:
            s = slam(t - 16, 5, 3.0)
            vs = Image.new("RGBA", (420, 360), (0, 0, 0, 0))
            burst(vs, 210, 180, 75, 150, (255, 40, 40, 255), 12, seed=7)
            paste(vs, text("VS", 130, (255, 240, 80, 255), 9, 8), 210, 180)
            paste(f, vs, 650, 380, s, -6 + math.sin(t) * 2)
        if t >= 24:
            bubble(f, 380, 200, "KNEEL,\nPEASANT.", 50, (330, 300), ease_back((t - 24) / 4))
        if t >= 35:
            bubble(f, 820, 230, "NAH.", 64, (900, 330), ease_back((t - 35) / 3))
        return f

    def grind_board(self, t: int) -> tuple[Image.Image, int]:
        g = [row[:] for row in self.grind_grid]
        # the red ball bounces (selected), then hops into the gap and the line goes
        if t < 9:
            g[2][4] = ("red", "squashed" if (t // 2) % 2 else "ball")
        elif t < 11:
            g[2][4] = (None, "ball")
            g[1][4] = ("red", "ball")
        else:
            g[2][4] = (None, "ball")
            g[1][4] = ("red", "ball")
            for c in range(5):
                k = t - (12 + 2 * c)
                if k >= 4:
                    g[1][c] = (None, "ball")
                elif k >= 2:
                    g[1][c] = ("red", "vanish-2")
                elif k >= 0:
                    g[1][c] = ("red", "vanish-1")
        popped = sum(1 for c in range(5) if t >= 12 + 2 * c + 2)
        return board(self.sp, g), popped

    # 2. meanwhile, on the board
    def grind(self, t: int) -> Image.Image:
        f = self.bg_navy.copy()
        b, popped = self.grind_board(t)
        zoom = 1 + 0.06 * t / 32
        bw, bh = 7 * self.cell_wh[0], 3 * self.cell_wh[1]
        big = b.resize((bw, bh), Image.NEAREST)
        frame = Image.new("RGBA", (bw + 24, bh + 24), INK)
        frame.paste(big, (12, 12))
        paste(f, frame, W / 2, self.board_xy[1] + bh / 2, zoom)
        for d in self.debris:
            d.draw(f, t)
        for c in range(5):
            k = t - (12 + 2 * c + 2)
            if 0 <= k < 12:
                x = self.board_xy[0] + (c + 0.5) * self.cell_wh[0]
                pop = text("POP!", 64 + 8 * c, (255, 240, 60, 255) if c % 2 else (255, 255, 255, 255), 7, 6)
                paste(f, pop, x, 200 - k * 2, slam(k, 3, 1.8), (-12, 9, -5, 14, -9)[c])
        paste(f, caption("MEANWHILE, ON THE BOARD...", 34), 290, 60, angle=-1)
        val = 50 + 10 * popped
        lab = text("PRETENDER", 40, (255, 255, 255, 255), 5, 4)
        paste(f, lab, 1080, 120)
        paste(f, score(self.sp, val, 5.0), 1080, 185, slam(t - 14, 3, 1.3) if popped else 1.0)
        return f

    # 3. the king sweats
    def sweat(self, t: int) -> Image.Image:
        f = self.paper.copy()
        left = self.bg_red.copy()
        shake = math.sin(t * 2.7) * 6
        paste(left, self.face[(t // 3) % 2], 310 + shake, 390)
        d = ImageDraw.Draw(left)
        for i, (x0, y0) in enumerate([(150, 200), (470, 240), (200, 520), (480, 470)]):
            y = y0 + ((t * 9 + i * 40) % 120)
            d.polygon(
                [(x0, y - 60), (x0 - 30, y + 6), (x0 + 30, y + 6)],
                fill=(120, 200, 255, 255),
                outline=INK,
                width=5,
            )
            d.ellipse((x0 - 30, y - 20, x0 + 30, y + 36), fill=(120, 200, 255, 255), outline=INK, width=5)
            d.ellipse((x0 - 25, y - 10, x0 + 25, y + 31), fill=(120, 200, 255, 255))
            d.ellipse((x0 - 14, y - 4, x0 - 4, y + 8), fill=(255, 255, 255, 255))
        panel(f, left, [(0, 0), (650, 0), (600, H), (0, H)])
        rt = self.bg_purple.copy()
        speed_lines(rt, 960, 400, 220, seed=t // 2, n=60, color=(255, 200, 255, 255))
        paste(rt, self.pret[0], 960, 430 - min(t, 6) * 3)
        panel(f, rt, [(670, 0), (W, 0), (W, H), (620, H)])
        paste(f, caption("THE KING: 100.\nTHE PRETENDER: 100.", 28), 230, 70, angle=-2)
        if t >= 4:
            paste(f, text("GULP!", 110, (120, 220, 255, 255), 8, 7), 330, 640, slam(t - 4, 4, 2.0), 8)
        if t >= 8:
            bubble(f, 930, 140, "ONE. MORE.\nLINE.", 52, (930, 280), ease_back((t - 8) / 4))
        return f

    # 4. the line that does it: a white flash, then 110
    def strike(self, t: int) -> Image.Image:
        if t < 5:
            f = self.bg_navy.copy()
            speed_lines(f, W / 2, H / 2, 260, seed=t, n=90, color=(255, 255, 255, 255))
            g = [[(None, "ball")] * 5 for _ in range(5)]
            filler = {(0, 1): "blue", (1, 3): "green", (3, 0): "magenta", (4, 2): "cyan", (2, 4): "red"}
            for (r, c), col in filler.items():
                g[r][c] = (col, "ball")
            for i in range(5):
                g[4 - i][i] = ("yellow", "vanish-1" if t >= 3 else "ball")
            b = up(board(self.sp, g), 3.0)
            fr = Image.new("RGBA", (b.width + 20, b.height + 20), INK)
            fr.paste(b, (10, 10))
            paste(f, fr, W / 2, H / 2, 1 + 0.08 * t)
            return f
        if t < 7:
            f = Image.new("RGBA", (W, H), (255, 255, 255, 255))
            paste(f, text("KA-BLAM!", 230, INK[:3] + (255,), 0, 0), W / 2, H / 2, 1 + 0.1 * (t - 5), -5)
            return f
        f = rays((255, 210, 0), (255, 120, 0), W / 2, H / 2, 18, t * 0.05)
        burst(f, W / 2, H / 2, 190, 330, (255, 40, 40, 255), 16, seed=3)
        paste(f, text("110!", 260, (255, 240, 80, 255), 12, 12), W / 2, H / 2 - 10, slam(t - 7, 5, 2.6), -4)
        paste(f, caption("PRETENDER 110  ·  KING 100", 36, (255, 255, 255, 255)), W / 2, 650)
        return f

    @cache  # noqa: B019 (one Trailer per run)
    def pillar(self, height: int, k: float) -> Image.Image:
        height = max(height, 1)
        p = self.pillar_img
        body = p.crop((0, 10, p.width, 11)).resize((p.width, height))
        col = Image.new("RGBA", (p.width, height + p.height - 10))
        col.paste(body, (0, 0))
        col.paste(p.crop((0, 10, p.width, p.height)), (0, height))
        return outlined(col.resize((round(col.width * k), round(col.height * k * PY)), Image.NEAREST), 6, 3)

    # 5. the hit
    def hit(self, t: int) -> Image.Image:
        h = HIT - SHOTS["hit"][0]
        f = self.bg_navy.copy()
        if t < h:
            hlines(f, seed=t // 1, n=46)
        else:
            speed_lines(f, 330, 230, 200, seed=t, n=70, color=(255, 255, 255, 255))
        kx, ky = 330, 340
        col = self.pillar(1, 3.4)
        paste(f, col, kx - 6, 490 + col.height / 2)
        if t < h:
            king = self.king_hit[0]
        elif t < h + 6:
            king = self.king_hit[4]
        elif t < h + 12:
            king = self.king_hit[5]
        else:
            king = self.king_hit[6]
        ang = 0.0 if t < h else max(0.0, 18 - (t - h) * 1.2)
        paste(f, king, kx + (8 if h <= t < h + 6 else 0), ky, angle=ang)
        if t < h:
            k = ease_out(t / h) ** 1.6
            x = 1450 + (500 - 1450) * k
            y = 520 - math.sin(k * math.pi) * 260 + (ky - 60 - 520) * k
            for g in range(3, 0, -1):
                kg = ease_out(max(t - g * 1.2, 0) / h) ** 1.6
                gx = 1450 + (500 - 1450) * kg
                gy = 520 - math.sin(kg * math.pi) * 260 + (ky - 60 - 520) * kg
                paste(f, self.pret_hit, gx, gy, angle=-25, alpha=0.18 * (4 - g))
            paste(f, self.pret_hit, x, y, angle=-25)
            if t > 3:
                paste(f, text("WHOOSH", 60, (255, 255, 255, 255), 6, 5), x + 230, y - 140, angle=-10)
        else:
            k = ease_out((t - h) / 10)
            paste(f, self.pret_hit, 500 + 450 * k, ky - 60 + 200 * k, angle=-25 + 25 * k)
            dt = t - h
            # the crown leaves, the teeth too
            cx, cy = kx + 30 + 26 * dt, ky - 130 - 34 * dt + 1.2 * dt * dt
            paste(f, self.crown_hit, cx, cy, angle=-dt * 38)
            d = ImageDraw.Draw(f)
            for i, (vx, vy) in enumerate([(-14, -20), (-9, -26)]):
                tx, ty = kx - 20 + vx * dt, ky - 20 + vy * dt + 1.8 * dt * dt
                d.rounded_rectangle(
                    (tx - 11, ty - 15, tx + 11, ty + 15), 5, fill=(255, 255, 255, 255), outline=INK, width=4
                )
                if i == 0:
                    d.line((tx - 6, ty - 4, tx + 6, ty - 4), fill=INK, width=3)
            burst(f, kx + 260, ky - 200, 95, 175, (255, 230, 50, 255), 13, seed=5)
            paste(f, text("BONK!", 140, (255, 40, 40, 255), 10, 9), kx + 260, ky - 200, slam(dt, 4, 2.2), 10)
            if dt > 10:
                paste(f, caption("THAT'S GOING TO\nLEAVE A MARK.", 30), 1000, 100)
        if h <= t < h + 2:  # the impact frame: black ink on white
            g = f.convert("L").point(lambda v: 0 if v > 90 else 255)
            f = Image.merge("RGBA", (g, g, g, Image.new("L", (W, H), 255)))
            speed_lines(f, kx + 100, ky - 140, 120, seed=77, n=90)
        return f

    # 6. K.O.; the crown finds a new head
    def ko(self, t: int) -> Image.Image:
        f = self.paper.copy()
        left = halftone((255, 120, 0), (255, 220, 60), 260, 420, rmax=12)
        paste(left, self.king[6], 280, 430, angle=-8)
        d = ImageDraw.Draw(left)
        for i in range(3):
            a = t * 0.35 + i * 2 * math.pi / 3
            star(d, 280 + math.cos(a) * 130, 300 + math.sin(a) * 36, 30, t * 0.3 + i, (255, 240, 60, 255))
        panel(f, left, [(0, 0), (610, 0), (540, H), (0, H)])
        rt = rays((255, 200, 0), (255, 160, 0), 960, 360, 14, -t * 0.04)
        rt.alpha_composite(halftone((0, 0, 0), (255, 240, 140), 960, 360, rmax=6), (0, 0))
        rt = Image.blend(rays((255, 200, 0), (255, 160, 0), 960, 360, 14, -t * 0.04), rt, 0.25)
        land = 22
        if t < land:
            p = self.pret[0]
        elif t < land + 3:
            p = self.pret[2]
        elif t < land + 6:
            p = self.pret[3]
        elif t < land + 14:
            p = self.pret[4]
        else:
            p = self.pret[5]
        px, py = 960, 450
        paste(rt, p, px, py)
        if t < land:
            k = t / land
            paste(
                rt,
                self.crown,
                px + 25 + (1 - k) * 120,
                -120 + (py - 165 + 120) * k * k,
                angle=(land - t) * 31,
            )
        else:
            dl = ImageDraw.Draw(rt)
            for i in range(8):
                a = i * math.pi / 4 + t * 0.1
                r = 120 + (t - land) * 6
                star(
                    dl,
                    px + 25 + math.cos(a) * r,
                    py - 170 + math.sin(a) * r * 0.6,
                    14,
                    a,
                    (255, 255, 255, 255),
                )
            if t - land < 10:
                paste(
                    rt,
                    text("CLINK!", 70, (255, 255, 255, 255), 6, 5),
                    px + 200,
                    py - 250,
                    slam(t - land, 3, 1.8),
                    12,
                )
        if t >= land + 8:
            for i, (x, c) in enumerate([(730, 0), (1190, 3)]):
                im = self.trump[8 + c]
                paste(rt, ImageOps.mirror(im) if i else im, x, 640 + math.sin(t + i) * 4)
        panel(f, rt, [(630, 0), (W, 0), (W, H), (560, H)])
        paste(f, text("K.O.!", 190, (255, 40, 40, 255), 11, 11), 280, 120, slam(t, 5, 2.8), -8)
        if t >= 8:
            paste(f, caption("HIS MAJESTY IS NAPPING.", 30), 270, 660, angle=1)
        if t >= land + 16:
            bubble(f, 1080, 120, "LONG LIVE\nME!", 56, (1000, 240), ease_back((t - land - 16) / 4))
        return f

    # 7. the end card
    def end(self, t: int) -> Image.Image:
        f = rays((210, 20, 30), (240, 60, 40), W / 2, 230, 20, t * 0.02)
        f = Image.blend(f, halftone((210, 20, 30), (255, 150, 40), W / 2, 230, rmax=10), 0.35)
        paste(f, self.logo, W / 2, 200, slam(t, 6, 2.5), -3)
        if t >= 8:
            paste(f, caption("THE CROWN IS UP FOR GRABS.", 40), W / 2, 380 + 90 * (1 - ease_out((t - 8) / 5)))
        if t >= 13:
            card = text("PLAY FREE AT  LINES.REMBI.SH", 76, (255, 255, 255, 255), 8, 8)
            paste(f, card, W / 2, 500, slam(t - 13, 5, 1.8), -2)
        paste(f, self.king_small, 150, 640)
        if t >= 24:
            bubble(f, 340, 650, "...REMATCH?", 34, (215, 640), ease_back((t - 24) / 4))
        lbl = text("COLOR LINES © 1992 GAMOS", 26, (255, 255, 255, 255), 3, 2)
        paste(f, lbl, W - lbl.width / 2 - 20, H - 26)
        return f

    def frame(self, n: int) -> Image.Image:
        for name, (a, b) in SHOTS.items():
            if a <= n < b:
                f = getattr(self, name)(n - a)
                break
        return shake(f, n)


SHAKES = [
    (SHOTS["open"][0] + 7, 14),
    (SHOTS["vs"][0] + 21, 18),
    (SHOTS["strike"][0] + 5, 26),
    (SHOTS["strike"][0] + 12, 16),
    (HIT, 40),
    (SHOTS["ko"][0] + 5, 22),
    (SHOTS["end"][0] + 6, 16),
]


def shake(f: Image.Image, n: int) -> Image.Image:
    amp = 0.0
    for at, a in SHAKES:
        if 0 <= n - at < 10:
            amp = max(amp, a * (1 - (n - at) / 10))
    if not amp:
        return f
    rnd = random.Random(n)
    dx, dy = rnd.uniform(-amp, amp), rnd.uniform(-amp, amp)
    s = 1 + amp / 400
    return f.transform(
        (W, H),
        Image.AFFINE,
        (1 / s, 0, (W - W / s) / 2 - dx / s, 0, 1 / s, (H - H / s) / 2 - dy / s),
        Image.BILINEAR,
    )


# --- sound ----------------------------------------------------------------------------------------


def sec(frame: float) -> float:
    return frame / FPS


def env(n: int, attack: float, decay: float) -> np.ndarray:
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def tone(freq: np.ndarray | float, dur: float, kind: str = "square", duty: float = 0.5) -> np.ndarray:
    n = int(dur * SR)
    f = np.broadcast_to(np.asarray(freq, float), (n,))
    ph = np.cumsum(f) / SR % 1.0
    if kind == "square":
        return np.where(ph < duty, 1.0, -1.0)
    if kind == "saw":
        return 2 * ph - 1
    return np.sin(2 * math.pi * ph)


def lowpass(x: np.ndarray, a: float) -> np.ndarray:
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += a * (v - acc)
        y[i] = acc
    return y


def note(name: str) -> float:
    names = {
        "C": 0,
        "C#": 1,
        "D": 2,
        "D#": 3,
        "E": 4,
        "F": 5,
        "F#": 6,
        "G": 7,
        "G#": 8,
        "A": 9,
        "A#": 10,
        "B": 11,
    }
    return 440.0 * 2 ** ((names[name[:-1]] + 12 * (int(name[-1]) + 1) - 69) / 12)


class Mix:
    def __init__(self, seconds: float) -> None:
        self.buf = np.zeros(int(seconds * SR) + SR)
        self.rnd = np.random.default_rng(7)

    def add(self, at: float, x: np.ndarray, gain: float = 1.0) -> None:
        i = int(at * SR)
        if i < 0:
            x, i = x[-i:], 0
        x = x[: len(self.buf) - i]
        self.buf[i : i + len(x)] += gain * x

    def noise(self, dur: float) -> np.ndarray:
        return self.rnd.uniform(-1, 1, int(dur * SR))

    def kick(self, at: float, g: float = 0.6) -> None:
        n = int(0.3 * SR)
        f = 45 + 110 * np.exp(-np.arange(n) / SR / 0.03)
        self.add(at, tone(f, 0.3, "sine") * env(n, 0.001, 0.09), g)

    def snare(self, at: float, g: float = 0.25) -> None:
        n = int(0.18 * SR)
        self.add(at, (self.noise(0.18) * 0.8 + tone(190, 0.18, "sine") * 0.4) * env(n, 0.001, 0.05), g)

    def hat(self, at: float, g: float = 0.06) -> None:
        x = np.diff(self.noise(0.05), prepend=0)
        self.add(at, x * env(len(x), 0.0005, 0.012), g)

    def impact(self, at: float, g: float = 1.0) -> None:
        n = int(0.9 * SR)
        f = 28 + 120 * np.exp(-np.arange(n) / SR / 0.06)
        body = tone(f, 0.9, "sine") * env(n, 0.001, 0.22)
        crunch = lowpass(self.noise(0.9), 0.25) * env(n, 0.001, 0.09) * 1.6
        self.add(at, np.tanh(2.5 * (body + crunch)), 0.7 * g)

    def whoosh(self, at: float, dur: float, g: float = 0.4) -> None:
        n = int(dur * SR)
        x = self.noise(dur)
        cut = np.linspace(0.02, 0.35, n)
        y = np.zeros(n)
        acc = 0.0
        for i in range(0, n, 64):  # a coarse sweeping one-pole filter
            seg = x[i : i + 64]
            for j, v in enumerate(seg):
                acc += cut[i + j] * (v - acc)
                y[i + j] = acc
        self.add(at, y * np.sin(np.linspace(0, math.pi, n)) ** 2 * 2.2, g)

    def pop(self, at: float, pitch: float, g: float = 0.18) -> None:
        n = int(0.08 * SR)
        f = pitch * np.exp(-np.arange(n) / SR / 0.05)
        self.add(at, tone(f, 0.08) * env(n, 0.001, 0.03), g)

    def bonk(self, at: float, g: float = 0.5) -> None:
        n = int(0.35 * SR)
        f = 160 + 620 * np.exp(-np.arange(n) / SR / 0.05)
        self.add(at, tone(f, 0.35, "sine") * env(n, 0.001, 0.12), g)
        self.add(at, tone(f * 2, 0.35) * env(n, 0.001, 0.05), g * 0.15)

    def ding(self, at: float, g: float = 0.25) -> None:
        n = int(1.2 * SR)
        x = sum(
            tone(fr, 1.2, "sine") * env(n, 0.001, dc) * a
            for fr, dc, a in [(1760, 0.5, 1), (2637, 0.3, 0.6), (3520, 0.2, 0.4), (4186, 0.12, 0.3)]
        )
        self.add(at, x, g)

    def gulp(self, at: float, g: float = 0.35) -> None:
        n = int(0.22 * SR)
        f = np.concatenate([np.linspace(420, 140, n // 2), np.linspace(180, 520, n - n // 2)])
        self.add(at, tone(f, 0.22, "sine") * env(n, 0.005, 0.12), g)

    def tweet(self, at: float, g: float = 0.07) -> None:
        n = int(0.07 * SR)
        self.add(at, tone(np.linspace(2600, 3600, n), 0.07, "sine") * env(n, 0.003, 0.03), g)

    def lead(self, at: float, notes: list[tuple[str, float]], step: float, g: float = 0.12) -> None:
        t = at
        for nm, beats in notes:
            dur = beats * step
            n = int(dur * SR)
            vib = 1 + 0.006 * np.sin(np.arange(n) / SR * 2 * math.pi * 6) * (np.arange(n) > SR * 0.12)
            x = tone(note(nm) * vib, dur, "square", 0.3) * np.minimum(1, env(n, 0.004, max(dur, 0.2) * 1.5))
            x[-int(0.01 * SR) :] *= np.linspace(1, 0, int(0.01 * SR))
            self.add(t, x, g)
            self.add(t, tone(note(nm) * 2.0, dur, "square", 0.5) * env(n, 0.002, 0.06), g * 0.15)
            t += dur


def soundtrack(path: str) -> None:
    m = Mix(sec(N))
    beat = 60 / 150
    eighth = beat / 2
    riff = [
        "D2",
        "D2",
        "D3",
        "D2",
        "C2",
        "C2",
        "C3",
        "C2",
        "A#1",
        "A#1",
        "A#2",
        "A#1",
        "A1",
        "A1",
        "A2",
        "C#3",
    ]
    quiet = (sec(HIT) - 0.45, sec(HIT))
    t, i = 0.0, 0
    while t < sec(SHOTS["end"][0]):
        if not quiet[0] <= t < quiet[1]:
            n = int(eighth * SR)
            m.add(t, tone(note(riff[i % 16]), eighth, "square", 0.5) * env(n, 0.002, 0.11), 0.11)
            m.hat(t)
            if i % 2 == 0:
                m.kick(t, 0.45)
            if i % 4 == 2:
                m.snare(t)
        t += eighth
        i += 1
    # the opening fanfare and the coronation fanfare
    m.lead(sec(SHOTS["open"][0] + 17), [("A4", 0.5), ("A4", 0.5), ("D5", 2.0)], eighth, 0.11)
    m.lead(sec(SHOTS["ko"][0] + 30), [("D5", 0.5), ("F#5", 0.5), ("A5", 0.5), ("D6", 3.0)], eighth, 0.1)
    # the hits
    m.impact(sec(SHOTS["open"][0] + 6), 0.7)
    m.whoosh(sec(SHOTS["vs"][0]) - 0.1, 0.35, 0.3)
    m.whoosh(sec(SHOTS["vs"][0] + 6) - 0.1, 0.35, 0.3)
    m.impact(sec(SHOTS["vs"][0] + 16), 0.9)
    for c in range(5):
        m.pop(sec(SHOTS["grind"][0] + 12 + 2 * c), 900 * 1.12**c)
    m.gulp(sec(SHOTS["sweat"][0] + 4))
    m.whoosh(sec(SHOTS["strike"][0]) - 0.05, 0.25, 0.25)
    m.impact(sec(SHOTS["strike"][0] + 5), 1.0)
    m.impact(sec(SHOTS["strike"][0] + 7), 0.6)
    m.whoosh(sec(SHOTS["hit"][0]), sec(HIT - SHOTS["hit"][0]) + 0.05, 0.55)
    m.impact(sec(HIT), 1.3)
    m.bonk(sec(HIT), 0.55)
    m.impact(sec(SHOTS["ko"][0] + 1), 0.9)
    for k in range(6):
        m.tweet(sec(SHOTS["ko"][0] + 8) + k * 0.17)
    m.whoosh(sec(SHOTS["ko"][0] + 8), sec(14), 0.15)
    m.ding(sec(SHOTS["ko"][0] + 22))
    m.impact(sec(SHOTS["end"][0] + 5), 0.9)
    m.lead(sec(SHOTS["end"][0] + 5), [("D4", 4.0)], eighth, 0.08)
    m.lead(sec(SHOTS["end"][0] + 5), [("A4", 4.0)], eighth, 0.06)
    m.lead(sec(SHOTS["end"][0] + 5), [("F#4", 4.0)], eighth, 0.06)
    m.pop(sec(SHOTS["end"][0] + 24), 500, 0.12)
    x = m.buf[: int(sec(N) * SR)]
    x[-int(0.25 * SR) :] *= np.linspace(1, 0, int(0.25 * SR))
    x = np.tanh(1.3 * x) * 0.75
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# --- main -----------------------------------------------------------------------------------------


def main() -> None:
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "original", "LINES.LIB")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "clips", "trailer.mp4")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    fetch_fonts()
    tr = Trailer(Sprites(load_pictures(src)))
    if os.environ.get("FRAMES"):  # FRAMES=10,50,... writes those frames as PNG and stops
        for n in map(int, os.environ["FRAMES"].split(",")):
            tr.frame(n).convert("RGB").save(f"{out}.{n:03}.png")
        return
    wav = out + ".wav"
    soundtrack(wav)
    enc = subprocess.Popen(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{W}x{H}",
            "-r",
            str(FPS),
            "-i",
            "-",
            "-i",
            wav,
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-shortest",
            "-movflags",
            "+faststart",
            out,
        ],
        stdin=subprocess.PIPE,
    )
    assert enc.stdin
    for n in range(N):
        enc.stdin.write(tr.frame(n).convert("RGB").tobytes())
    enc.stdin.close()
    if enc.wait():
        sys.exit("ffmpeg failed")
    os.remove(wav)
    gif = os.path.splitext(out)[0] + ".gif"
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-i",
            out,
            "-vf",
            "fps=12,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64[p];[b][p]paletteuse=dither=bayer:bayer_scale=3",
            "-loop",
            "0",
            gif,
        ],
        check=True,
    )
    print(out, gif)


if __name__ == "__main__":
    main()
