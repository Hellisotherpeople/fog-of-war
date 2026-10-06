"""Procedurally painted top-down sprites.

Everything is drawn at a 64x64 master resolution with PIL and downsampled to the
current tile size.  Sprites live in the Unicode private use area of a tcod
tileset; terrain has fixed codepoints, units/items/effects are allocated lazily.
"""
from __future__ import annotations

import math
import random

import numpy as np
import tcod
from PIL import Image, ImageDraw, ImageFilter

from . import tiles as T

M = 64                      # master resolution
TERRAIN_BASE = 0xE000       # tid * 4 + variant
DYN_BASE = 0xE800           # dynamically allocated sprites
VARIANTS = 4


# ====================================================================== colour helpers

def clamp(c):
    return tuple(int(max(0, min(255, v))) for v in c)


def shade(c, f):
    return clamp(tuple(v * f for v in c[:3]))


def mix(a, b, t):
    return clamp(tuple(a[i] * (1 - t) + b[i] * t for i in range(3)))


def lighten(c, amt):
    return clamp(tuple(v + (255 - v) * amt for v in c[:3]))


def vnoise(rng, cells=4, size=M):
    g = (rng.random((cells + 1, cells + 1)) * 255).astype(np.uint8)
    img = Image.fromarray(g, "L").resize((size, size), Image.BICUBIC)
    return np.asarray(img, np.float32) / 255.0


class Canvas:
    def __init__(self, seed=0):
        self.img = Image.new("RGBA", (M, M), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self.rng = random.Random(seed)
        self.nrng = np.random.default_rng(seed)

    # ---- fills
    def texture(self, base, var=0.12, cells=5, fine=0.06):
        n = vnoise(self.nrng, cells) * 0.7 + vnoise(self.nrng, cells * 3) * 0.3
        f = 1 + (n - 0.5) * 2 * var + (self.nrng.random((M, M)) - 0.5) * fine
        arr = np.zeros((M, M, 4), np.float32)
        for i in range(3):
            arr[..., i] = base[i] * f
        arr[..., 3] = 255
        self.img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
        self.d = ImageDraw.Draw(self.img)

    def speckle(self, color, n, r=(1, 2), alpha=255):
        for _ in range(n):
            x, y = self.rng.uniform(0, M), self.rng.uniform(0, M)
            rr = self.rng.uniform(*r)
            c = clamp(color) + (alpha,)
            self.d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=c)

    def blades(self, color, n, length=(4, 9), width=1, lean=2.5, alpha=255):
        for _ in range(n):
            x, y = self.rng.uniform(0, M), self.rng.uniform(4, M)
            L = self.rng.uniform(*length)
            dx = self.rng.uniform(-lean, lean)
            c = mix(color, (255, 255, 255), self.rng.uniform(-0.1, 0.25)) if True else color
            self.d.line((x, y, x + dx, y - L), fill=c + (alpha,), width=width)

    def lines_h(self, color, spacing, width=1, jitter=1.0, alpha=255):
        y = self.rng.uniform(0, spacing)
        while y < M:
            pts = []
            for x in range(0, M + 8, 8):
                pts.append((x, y + self.rng.uniform(-jitter, jitter)))
            self.d.line(pts, fill=clamp(color) + (alpha,), width=width)
            y += spacing

    def ellipse(self, box, fill=None, outline=None, width=1):
        self.d.ellipse(box, fill=fill, outline=outline, width=width)

    def rect(self, box, fill=None, outline=None, width=1):
        self.d.rectangle(box, fill=fill, outline=outline, width=width)

    def poly(self, pts, fill=None, outline=None, width=1):
        self.d.polygon(pts, fill=fill, outline=outline)
        if outline and width > 1:
            self.d.line(pts + [pts[0]], fill=outline, width=width)

    def line(self, pts, fill, width=1):
        self.d.line(pts, fill=fill, width=width)

    def shadow(self, box, alpha=90, blur=3):
        sh = Image.new("RGBA", (M, M), (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse(box, fill=(0, 0, 0, alpha))
        sh = sh.filter(ImageFilter.GaussianBlur(blur))
        self.img = Image.alpha_composite(self.img, sh)
        self.d = ImageDraw.Draw(self.img)

    def paste(self, other):
        self.img = Image.alpha_composite(self.img, other.img)
        self.d = ImageDraw.Draw(self.img)

    def bevel(self, light=70, dark=150, w=6):
        """Raised: lit along the top and left edges, shadowed along the bottom and right, like a wall."""
        sh = Image.new("RGBA", (M, M), (0, 0, 0, 0))
        d = ImageDraw.Draw(sh)
        for k in range(w):
            f = 1 - k / w
            d.line([(0, M - 1 - k), (M, M - 1 - k)], fill=(5, 10, 5, int(dark * f)))
            d.line([(M - 1 - k, 0), (M - 1 - k, M)], fill=(5, 10, 5, int(dark * f)))
            d.line([(0, k), (M - k, k)], fill=(255, 255, 220, int(light * f)))
            d.line([(k, 0), (k, M - k)], fill=(255, 255, 220, int(light * f)))
        self.img = Image.alpha_composite(self.img, sh)
        self.d = ImageDraw.Draw(self.img)

    def stand(self, thing, rim=(10, 14, 8), width=4, drop=(4, 5)):
        """Put something you can't walk through on this ground: a dark rim round its solid shape and a
        shadow cast down and to the right, so it reads as standing up out of the ground (walkable things -
        undergrowth, crops, rubble - are painted flat, without either)."""
        a = np.asarray(thing.img)[..., 3]
        solid = Image.fromarray(np.where(a > 180, 255, 0).astype(np.uint8), "L")
        cast = solid.transform((M, M), Image.AFFINE, (1, 0, -drop[0], 0, 1, -drop[1]))
        cast = cast.filter(ImageFilter.GaussianBlur(2)).point(lambda v: int(v * 0.5))
        sh = Image.new("RGBA", (M, M), (0, 0, 0, 255))
        sh.putalpha(cast)
        ring = solid.filter(ImageFilter.MaxFilter(width * 2 + 1)).point(lambda v: int(v * 0.9))
        edge = Image.new("RGBA", (M, M), tuple(rim) + (255,))
        edge.putalpha(ring)
        self.img = Image.alpha_composite(Image.alpha_composite(Image.alpha_composite(self.img, sh), edge),
                                         thing.img)
        self.d = ImageDraw.Draw(self.img)

    def array(self):
        return np.asarray(self.img, np.uint8)


def rot(pts, ang, cx=M / 2, cy=M / 2):
    ca, sa = math.cos(ang), math.sin(ang)
    return [(cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca) for x, y in pts]


# ====================================================================== terrain painters

def ground_color(tid):
    return tuple(int(c) for c in T.BG[tid])


def fg_color(tid):
    return tuple(int(c) for c in T.FG[tid])


def paint_ground(c: Canvas, key: str, tid: int):
    base = ground_color(tid)
    fg = fg_color(tid)
    if key in ("grass", "grass_dry", "grass_autumn"):
        c.texture(lighten(base, 0.18), 0.12)
        c.blades(shade(fg, 0.8), 60, (3, 6))
        c.blades(lighten(fg, 0.1), 25, (3, 5))
    elif key in ("tall_grass", "tall_grass_dry", "kunai"):
        c.texture(lighten(base, 0.12), 0.14)
        c.blades(shade(fg, 0.75), 90, (7, 13), lean=4)
        c.blades(lighten(fg, 0.15), 40, (6, 11), lean=4)
    elif key == "wheat":
        c.texture(shade(fg, 0.72), 0.1)
        for row in range(3, M, 7):
            for x in range(0, M, 3):
                xx = x + c.rng.uniform(-1, 1)
                c.line([(xx, row + 5), (xx + c.rng.uniform(-1, 1), row)], fill=lighten(fg, 0.1) + (255,), width=1)
                c.ellipse((xx - 1, row - 2, xx + 1, row + 1), fill=lighten(fg, 0.25) + (255,))
    elif key == "corn":
        c.texture(shade(base, 1.3), 0.15)
        for _ in range(14):
            x, y = c.rng.uniform(4, M - 4), c.rng.uniform(4, M - 4)
            for _k in range(3):
                a = c.rng.uniform(0, math.tau)
                c.line([(x, y), (x + math.cos(a) * 9, y + math.sin(a) * 9)], fill=lighten(fg, c.rng.uniform(-0.2, 0.2)) + (255,), width=2)
            c.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(170, 150, 60, 255))
    elif key == "sunflower":
        c.texture(shade(base, 1.3), 0.15)
        c.blades((70, 110, 40), 50, (4, 8))
        for _ in range(7):
            x, y = c.rng.uniform(6, M - 6), c.rng.uniform(6, M - 6)
            c.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(235, 195, 40, 255))
            c.ellipse((x - 2.5, y - 2.5, x + 2.5, y + 2.5), fill=(90, 60, 25, 255))
    elif key == "plowed":
        c.texture(base, 0.1)
        c.lines_h(shade(base, 0.7), 6, width=2)
        c.lines_h(lighten(base, 0.15), 6, width=1)
    elif key in ("dirt", "burnt", "rubble_earth", "gun_pit"):
        c.texture(lighten(base, 0.15) if key != "burnt" else base, 0.14)
        c.speckle(shade(base, 0.6), 25, (0.7, 1.8))
        c.speckle(lighten(base, 0.3), 15, (0.5, 1.2))
        if key == "burnt":
            c.speckle((120, 110, 100), 30, (0.5, 1.5))
            c.speckle((200, 90, 30), 4, (0.5, 1.0))
    elif key == "mud":
        c.texture(base, 0.18)
        for _ in range(5):
            x, y = c.rng.uniform(0, M), c.rng.uniform(0, M)
            c.ellipse((x - 7, y - 3, x + 7, y + 3), fill=lighten(base, 0.18) + (160,))
        c.speckle(shade(base, 0.6), 20)
    elif key == "road":
        c.texture(lighten(base, 0.1), 0.08)
        c.speckle(shade(base, 0.75), 30, (0.5, 1.5))
        for y0 in (20, 42):
            c.line([(0, y0), (M, y0 + c.rng.uniform(-2, 2))], fill=shade(base, 0.8) + (140,), width=5)
    elif key == "paved":
        c.texture(base, 0.05, fine=0.12)
        c.speckle(lighten(base, 0.2), 20, (0.3, 0.8))
    elif key == "cobble":
        c.texture(shade(base, 0.7), 0.05)
        for y in range(0, M, 8):
            off = 4 if (y // 8) % 2 else 0
            for x in range(-8, M, 8):
                col = mix(lighten(base, 0.2), base, c.rng.random())
                c.ellipse((x + off + 1, y + 1, x + off + 7, y + 7), fill=col + (255,))
    elif key in ("sand", "wet_sand"):
        c.texture(lighten(base, 0.12), 0.08, fine=0.1)
        c.lines_h(shade(base, 0.9), 9, width=1, jitter=2, alpha=110)
    elif key == "shingle":
        c.texture(base, 0.1)
        for _ in range(70):
            x, y = c.rng.uniform(0, M), c.rng.uniform(0, M)
            r = c.rng.uniform(1.5, 3.5)
            col = mix((150, 150, 145), (200, 195, 185), c.rng.random())
            c.ellipse((x - r, y - r * 0.8, x + r, y + r * 0.8), fill=col + (255,))
    elif key in ("snow", "deep_snow"):
        c.texture(lighten(base, 0.35), 0.06, fine=0.04)
        for _ in range(6):
            x, y = c.rng.uniform(0, M), c.rng.uniform(0, M)
            c.ellipse((x - 9, y - 4, x + 9, y + 4), fill=(200, 210, 230, 70))
    elif key == "ash":
        c.texture(lighten(base, 0.1), 0.1, fine=0.15)
        c.speckle((70, 65, 60), 40, (0.5, 1.2))
    elif key == "rock_ground":
        c.texture(lighten(base, 0.1), 0.15)
        c.speckle(shade(base, 0.6), 20, (1, 3))
        for _ in range(3):
            x, y = c.rng.uniform(0, M), c.rng.uniform(0, M)
            c.line([(x, y), (x + c.rng.uniform(-12, 12), y + c.rng.uniform(-12, 12))], fill=shade(base, 0.55) + (200,), width=1)
    elif key in ("floor_wood", "doorway"):
        c.texture(base if key == "floor_wood" else (70, 58, 45), 0.06)
        wood = base if key == "floor_wood" else (80, 65, 50)
        for y in range(0, M, 8):
            c.line([(0, y), (M, y)], fill=shade(wood, 0.6) + (255,), width=1)
            x = c.rng.uniform(0, M)
            c.line([(x, y), (x, y + 8)], fill=shade(wood, 0.6) + (255,), width=1)
        c.lines_h(lighten(wood, 0.1), 3, alpha=60)
    elif key == "floor_stone":
        c.texture(base, 0.06)
        for y in range(0, M, 16):
            off = 8 if (y // 16) % 2 else 0
            c.line([(0, y), (M, y)], fill=shade(base, 0.7) + (255,))
            for x in range(off, M, 16):
                c.line([(x, y), (x, y + 16)], fill=shade(base, 0.7) + (255,))
    elif key in ("floor_concrete", "runway"):
        c.texture(base, 0.05, fine=0.1)
        c.line([(0, M - 1), (M, M - 1)], fill=shade(base, 0.75) + (255,), width=1)
        c.line([(M - 1, 0), (M - 1, M)], fill=shade(base, 0.75) + (255,), width=1)
        if key == "runway":
            c.rect((M / 2 - 10, M / 2 - 2, M / 2 + 10, M / 2 + 2), fill=(220, 220, 210, 255))
    elif key in ("shallow", "paddy", "crater_water", "marsh"):
        c.texture(lighten(base, 0.12), 0.1, cells=3)
        for _ in range(7):
            x, y = c.rng.uniform(0, M), c.rng.uniform(0, M)
            c.line([(x - 5, y), (x, y - 1), (x + 5, y)], fill=lighten(base, 0.45) + (140,), width=1)
        if key == "paddy":
            for x in range(3, M, 8):
                for y in range(3, M, 8):
                    c.line([(x, y + 3), (x, y - 2)], fill=(120, 180, 90, 255), width=1)
                    c.line([(x, y + 3), (x + 2, y - 1)], fill=(130, 190, 90, 255), width=1)
        if key == "marsh":
            for _ in range(8):
                x, y = c.rng.uniform(3, M - 3), c.rng.uniform(3, M - 3)
                for _k in range(4):
                    c.line([(x, y), (x + c.rng.uniform(-3, 3), y - c.rng.uniform(5, 10))], fill=(110, 140, 70, 255))
        if key == "crater_water":
            c.ellipse((6, 6, M - 6, M - 6), fill=None, outline=(90, 75, 55, 255), width=5)
    elif key in ("deep",):
        c.texture(lighten(base, 0.1), 0.12, cells=3)
        for _ in range(9):
            x, y = c.rng.uniform(0, M), c.rng.uniform(0, M)
            c.line([(x - 7, y), (x, y - 2), (x + 7, y)], fill=lighten(base, 0.35) + (130,), width=2)
    elif key == "surf":
        c.texture(lighten(base, 0.1), 0.12, cells=3)
        for _ in range(4):
            y = c.rng.uniform(0, M)
            c.line([(0, y), (M / 3, y - 2), (M * 2 / 3, y + 1), (M, y - 1)], fill=(235, 240, 245, 200), width=3)
    elif key in ("deck_steel", "deck_inside", "plane_floor", "deck_holed"):
        # grey steel plate: seams, rows of rivets, the non-skid texture
        col = {"deck_steel": (118, 122, 130), "deck_inside": (98, 101, 108), "plane_floor": (112, 112, 104),
               "deck_holed": (80, 74, 70)}[key]
        c.texture(col, 0.05, cells=8, fine=0.04)
        for k in (0, 32):
            c.line([(0, k), (M, k)], fill=shade(col, 0.72) + (255,), width=1)
            c.line([(k, 0), (k, M)], fill=shade(col, 0.78) + (255,), width=1)
        for k in range(4, M, 8):
            for yy in (3, 35):
                c.ellipse((k - 1, yy - 1, k + 1, yy + 1), fill=lighten(col, 0.25) + (255,))
        if key == "deck_holed":
            c.ellipse((14, 14, 50, 50), fill=(20, 18, 18, 255))
            for _ in range(10):
                x, y = c.rng.uniform(10, 54), c.rng.uniform(10, 54)
                c.line([(32, 32), (x, y)], fill=(120, 110, 100, 255), width=2)
    elif key in ("deck_wood", "pier"):
        c.texture((168, 146, 108), 0.05, cells=6)
        for yy in range(0, M, 8):
            c.line([(0, yy), (M, yy)], fill=(96, 80, 58, 255), width=1)
            off = (yy * 13) % M
            c.line([(off, yy), (off, yy + 8)], fill=(110, 92, 66, 255), width=1)
    elif key in ("catwalk",):
        c.texture((70, 72, 78), 0.04)
        for k in range(0, M, 6):
            c.line([(k, 0), (k, M)], fill=(130, 132, 138, 255), width=2)
        c.line([(0, 2), (M, 2)], fill=(160, 160, 165, 255), width=2)
    elif key in ("elevator",):
        c.texture((150, 132, 100), 0.05)
        c.rect((2, 2, M - 3, M - 3), outline=(60, 50, 40, 255), width=3)
        c.line([(0, M // 2), (M, M // 2)], fill=(110, 96, 70, 255), width=1)
    elif key in ("arrest_wire", "catapult"):
        c.texture((168, 146, 108), 0.05, cells=6)
        if key == "arrest_wire":
            c.line([(0, 30), (M, 30)], fill=(40, 40, 42, 255), width=3)
            c.line([(0, 29), (M, 29)], fill=(200, 200, 205, 255), width=1)
        else:
            c.rect((0, 26, M, 38), fill=(90, 90, 92, 255))
            c.line([(0, 32), (M, 32)], fill=(40, 40, 40, 255), width=2)
    elif key in ("ladder", "hatch", "ladder_up"):
        c.texture((88, 90, 96), 0.05)
        c.rect((10, 6, 54, 58), fill=(30, 32, 36, 255), outline=(170, 160, 110, 255), width=3)
        for yy in range(12, 56, 8):
            c.line([(14, yy), (50, yy)], fill=(190, 180, 130, 255), width=3)
    elif key in ("sea_below",):
        c.texture((22, 42, 88), 0.1)
        c.blades((60, 90, 150), 8, (3, 6), lean=6, alpha=140)
    elif key in ("deck_below",):
        c.texture((58, 60, 66), 0.05)
    elif key in ("sky",):
        c.texture((120, 150, 195), 0.04, cells=4)
    elif key == "cloud":
        # a bank of cloud streaming past: soft, lumpy, bright on top
        c.texture((200, 208, 220), 0.07, cells=3, fine=0.05)
        for _ in range(7):
            x, y, rr = c.rng.uniform(4, 60), c.rng.uniform(4, 60), c.rng.uniform(8, 16)
            c.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(232, 236, 242, 150))
    elif key == "ice":
        c.texture(lighten(base, 0.3), 0.06)
        for _ in range(4):
            x, y = c.rng.uniform(0, M), c.rng.uniform(0, M)
            c.line([(x, y), (x + c.rng.uniform(-20, 20), y + c.rng.uniform(-20, 20))], fill=(235, 245, 255, 220), width=1)
    elif key == "gravel":
        c.texture(lighten(base, 0.12), 0.06, fine=0.12)
        for _ in range(90):
            x, y = c.rng.uniform(0, M), c.rng.uniform(0, M)
            rr = c.rng.uniform(0.8, 1.8)
            col = mix((170, 162, 145), (215, 208, 190), c.rng.random())
            c.ellipse((x - rr, y - rr, x + rr, y + rr), fill=col + (255,))
    elif key == "platform":
        c.texture(base, 0.04, fine=0.08)
        for k in (0, 32):
            c.line([(0, k), (M, k)], fill=shade(base, 0.72) + (255,), width=1)
            c.line([(k, 0), (k, M)], fill=shade(base, 0.78) + (255,), width=1)
        c.speckle(lighten(base, 0.2), 12, (0.4, 1.0))
    elif key == "slag":
        c.texture(lighten(base, 0.1), 0.2, fine=0.15)
        for _ in range(26):
            x, y = c.rng.uniform(0, M), c.rng.uniform(0, M)
            rr = c.rng.uniform(1.5, 4)
            col = mix((30, 28, 28), (85, 80, 78), c.rng.random())
            c.ellipse((x - rr, y - rr, x + rr, y + rr * 0.8), fill=col + (255,))
    elif key == "bracken":
        c.texture(lighten(base, 0.15), 0.12)
        c.blades(shade(fg, 0.8), 30, (3, 6))
        for _ in range(7):
            x, y = c.rng.uniform(4, M - 4), c.rng.uniform(4, M - 4)
            _fern(c, x, y, c.rng.uniform(0, math.tau), c.rng.uniform(8, 12), mix(fg, (160, 120, 60), c.rng.random() * 0.5))
    else:
        c.texture(lighten(base, 0.1), 0.1)


def ground_under(key, tid, climate_hint=None):
    """What ground to paint beneath an object tile."""
    bg = ground_color(tid)
    return bg


def _sprays(c, x, y, col, n=5, length=(5, 9), width=2, alpha=255, narrow=False):
    """Leaves radiating from a point: undergrowth seen from above."""
    r = c.rng
    for _ in range(n):
        a = r.uniform(0, math.tau)
        L = r.uniform(*length)
        tip = (x + math.cos(a) * L, y + math.sin(a) * L)
        k = mix(col, (255, 255, 255), r.uniform(-0.15, 0.2))
        if narrow:
            c.line([(x, y), tip], fill=k + (alpha,), width=width)
        else:
            side = 2.2
            c.poly([(x, y), (x + math.cos(a) * L * 0.5 + math.cos(a + 1.57) * side,
                             y + math.sin(a) * L * 0.5 + math.sin(a + 1.57) * side), tip,
                    (x + math.cos(a) * L * 0.5 + math.cos(a - 1.57) * side,
                     y + math.sin(a) * L * 0.5 + math.sin(a - 1.57) * side)], fill=k + (alpha,))


def _fern(c, x, y, a, L, col):
    """A fern frond: a rib with leaflets down both sides."""
    tx, ty = x + math.cos(a) * L, y + math.sin(a) * L
    c.line([(x, y), (tx, ty)], fill=shade(col, 0.7) + (230,), width=1)
    for k in range(1, 6):
        t = k / 6
        px, py = x + (tx - x) * t, y + (ty - y) * t
        ll = (1 - t) * 6 + 2
        for sgn in (1, -1):
            b = a + sgn * 1.1
            c.line([(px, py), (px + math.cos(b) * ll, py + math.sin(b) * ll)], fill=col + (235,), width=2)


def paint_object(c: Canvas, key: str, tid: int):
    bg = ground_color(tid)
    fg = fg_color(tid)
    r = c.rng
    snowy = key.endswith("_snow") or key == "tree_snow"
    # ground
    under = lighten(bg, 0.15)
    c.texture(under, 0.12)
    if snowy:
        c.texture((215, 220, 232), 0.05)
    elif key in ("tree", "tree_autumn", "olive", "bush", "hedge", "garden_hedge", "palm", "poplar",
                 "dead_tree", "stump", "log", "grave", "wire", "fence", "fence_h", "sign", "calvary", "pole",
                 "radar", "water_tower", "torii", "sail", "sail2"):
        c.blades(shade(bg, 1.4), 35, (3, 6))
    solid = not T.DEFS[tid].walk
    if solid:
        # you can't walk through it: painted on its own, then stood on the ground with a rim and a shadow
        ground, c = c, Canvas(seed=tid * 131 + 5)
        c.rng, c.nrng = ground.rng, ground.nrng

    if key in ("tree", "tree_autumn", "tree_snow", "olive"):
        c.shadow((12, 18, 60, 62), 110, 4)
        cols = {"tree": [(40, 110, 35), (55, 135, 45), (80, 160, 60)],
                "tree_autumn": [(150, 80, 25), (190, 110, 35), (220, 160, 60)],
                "tree_snow": [(35, 80, 50), (50, 100, 60), (230, 235, 245)],
                "olive": [(110, 125, 85), (140, 150, 105), (175, 180, 140)]}[key]
        big = 0.72 if key == "olive" else 0.88
        for i, col in enumerate(cols):
            for _ in range(5 - i):
                x = 32 + r.uniform(-10, 10) * big - i * 2
                y = 30 + r.uniform(-10, 10) * big - i * 3
                rr = r.uniform(9, 13) * big - i * 2
                c.ellipse((x - rr, y - rr, x + rr, y + rr), fill=col + (255,))
    elif key == "pine":
        c.shadow((14, 18, 60, 62), 110, 4)
        for i, (rad, col) in enumerate(((26, (25, 80, 45)), (19, (35, 100, 55)), (12, (50, 125, 70)), (5, (70, 145, 85)))):
            pts = []
            for k in range(16):
                a = k / 16 * math.tau
                rr = rad * (1.0 if k % 2 == 0 else 0.72)
                pts.append((32 + math.cos(a) * rr, 30 + math.sin(a) * rr))
            c.poly(pts, fill=col + (255,))
    elif key == "palm":
        c.shadow((18, 22, 58, 58), 90, 4)
        for k in range(7):
            a = k / 7 * math.tau + r.uniform(-0.2, 0.2)
            x2, y2 = 32 + math.cos(a) * 27, 32 + math.sin(a) * 27
            c.line([(32, 32), (x2, y2)], fill=(60, 130, 45, 255), width=5)
            for t in (0.4, 0.6, 0.8):
                px, py = 32 + math.cos(a) * 27 * t, 32 + math.sin(a) * 27 * t
                c.line([(px, py), (px + math.cos(a + 1.3) * 5, py + math.sin(a + 1.3) * 5)], fill=(80, 150, 55, 255), width=2)
                c.line([(px, py), (px + math.cos(a - 1.3) * 5, py + math.sin(a - 1.3) * 5)], fill=(80, 150, 55, 255), width=2)
        c.ellipse((28, 28, 36, 36), fill=(110, 85, 50, 255))
    elif key == "dead_tree":
        c.shadow((20, 26, 56, 58), 70, 3)
        for k in range(6):
            a = r.uniform(0, math.tau)
            L = r.uniform(12, 24)
            x2, y2 = 32 + math.cos(a) * L, 32 + math.sin(a) * L
            c.line([(32, 32), (x2, y2)], fill=(95, 80, 65, 255), width=3)
            c.line([(x2, y2), (x2 + math.cos(a + 0.6) * 6, y2 + math.sin(a + 0.6) * 6)], fill=(95, 80, 65, 255), width=2)
        c.ellipse((27, 27, 37, 37), fill=(80, 65, 50, 255))
    elif key == "stump":
        c.ellipse((20, 20, 44, 44), fill=(110, 80, 45, 255), outline=(70, 50, 30, 255), width=2)
        for rr in (8, 5, 2):
            c.ellipse((32 - rr, 32 - rr, 32 + rr, 32 + rr), outline=(150, 115, 70, 255))
    elif key == "log":
        c.shadow((6, 30, 60, 50), 90, 3)
        c.rect((6, 22, 54, 40), fill=(115, 80, 45, 255), outline=(70, 50, 30, 255))
        c.lines_h((90, 60, 35), 5)
        c.ellipse((48, 22, 60, 40), fill=(150, 110, 65, 255), outline=(80, 55, 30, 255), width=2)
    elif key in ("bush", "bush_snow", "scrub"):
        # undergrowth you push through: loose sprays of leaves, ground between, flat - no shadow, no rim
        cols = [(60, 118, 44), (88, 148, 58)] if key == "bush" else [(70, 108, 70), (235, 238, 245)] \
            if key == "bush_snow" else [(130, 120, 65), (160, 145, 80)]
        for _ in range(5 if key != "scrub" else 3):
            x, y = r.uniform(8, 56), r.uniform(8, 56)
            for col in cols:
                _sprays(c, x, y, col, n=5, length=(5, 9), width=2, alpha=225)
    elif key in ("jungle",):
        # dense undergrowth: ferns and leaf sprays over a floor of dead leaves - thick, but a man goes through
        c.texture(mix(bg, (58, 46, 26), 0.45), 0.18)
        c.speckle(mix(bg, (95, 70, 40), 0.5), 30, (0.8, 2.0))
        for _ in range(8):
            x, y = r.uniform(4, M - 4), r.uniform(4, M - 4)
            _sprays(c, x, y, (45, 100, 42), n=6, length=(6, 11), width=2, alpha=200)
        for _ in range(12):
            x, y = r.uniform(4, M - 4), r.uniform(4, M - 4)
            col = mix((48, 112, 46), (98, 150, 62), r.random())
            _fern(c, x, y, r.uniform(0, math.tau), r.uniform(10, 15), col)
        for _ in range(3):
            x = r.uniform(0, M)
            c.line([(x, 0), (x + r.uniform(-14, 14), M / 2), (x + r.uniform(-10, 10), M)],
                   fill=(70, 95, 40, 150), width=1)
    elif key == "bamboo":
        # clumps of cane with sprays of narrow leaves, the floor showing between
        c.texture(mix(bg, (70, 60, 30), 0.4), 0.14)
        for _ in range(4):
            x, y = r.uniform(10, 54), r.uniform(10, 54)
            for _k in range(5):
                xx, yy = x + r.uniform(-4, 4), y + r.uniform(-4, 4)
                c.ellipse((xx - 2, yy - 2, xx + 2, yy + 2), fill=(150, 190, 90, 255), outline=(80, 110, 50, 255))
            _sprays(c, x, y, (140, 190, 80), n=8, length=(8, 14), width=2, alpha=215, narrow=True)
    elif key == "hedge":
        c.texture((75, 60, 40), 0.15)     # earth bank
        for _ in range(60):
            x, y = r.uniform(4, M - 4), r.uniform(4, M - 4)
            rr = r.uniform(4, 9)
            col = mix((26, 72, 24), (62, 120, 46), r.random())
            c.ellipse((x - rr, y - rr, x + rr, y + rr), fill=col + (255,))
        c.bevel()
    elif key == "garden_hedge":
        # a clipped garden hedge, knee to chest high, gaps in it: slow to push through, not a wall
        for gx in (14, 32, 50):
            for gy in (14, 32, 50):
                if r.random() < 0.2:
                    continue
                rr = r.uniform(6, 8)
                col = mix((70, 130, 55), (100, 155, 70), r.random())
                c.ellipse((gx - rr, gy - rr, gx + rr, gy + rr), fill=col + (235,))
                c.ellipse((gx - rr + 2, gy - rr + 1, gx, gy - 1), fill=lighten(col, 0.2) + (220,))
    elif key in ("wall_brick", "wall_factory"):
        base = (150, 70, 55) if key == "wall_brick" else (120, 85, 70)
        c.texture(base, 0.08)
        for y in range(0, M, 8):
            c.line([(0, y), (M, y)], fill=(190, 180, 165, 255), width=1)
            off = 8 if (y // 8) % 2 else 0
            for x in range(off, M, 16):
                c.line([(x, y), (x, y + 8)], fill=(190, 180, 165, 255), width=1)
        c.rect((0, 0, M - 1, 3), fill=lighten(base, 0.3) + (120,))
    elif key == "wall_stone":
        c.texture((140, 138, 128), 0.06)
        for _ in range(14):
            x, y = r.uniform(0, M), r.uniform(0, M)
            w, h = r.uniform(8, 16), r.uniform(6, 10)
            col = mix((150, 148, 138), (190, 188, 178), r.random())
            c.rect((x, y, x + w, y + h), fill=col + (255,), outline=(100, 98, 90, 255))
    elif key in ("wall_wood", "wall_log"):
        c.texture((120, 85, 50), 0.08)
        step = 8 if key == "wall_wood" else 12
        for y in range(0, M, step):
            c.rect((0, y + 1, M, y + step - 1), fill=mix((140, 100, 60), (110, 75, 45), r.random()) + (255,))
            c.line([(0, y), (M, y)], fill=(70, 50, 30, 255), width=1)
            if key == "wall_log":
                c.ellipse((M - 10, y + 1, M - 1, y + step - 1), fill=(165, 125, 80, 255), outline=(90, 65, 40, 255))
    elif key == "wall_thatch":
        c.texture((170, 150, 85), 0.1)
        c.blades((200, 180, 110), 120, (6, 12), lean=6)
        c.blades((130, 110, 60), 60, (6, 12), lean=6)
    elif key in ("wall_concrete", "embrasure"):
        c.texture((150, 150, 144), 0.05, fine=0.1)
        c.rect((0, 0, M - 1, M - 1), fill=None, outline=(110, 110, 105, 255), width=3)
        c.speckle((120, 120, 115), 12, (0.5, 1.2))
        if key == "embrasure":
            c.rect((6, 26, M - 6, 38), fill=(15, 15, 15, 255))
            c.rect((6, 38, M - 6, 41), fill=(190, 190, 185, 255))
    elif key in ("window", "window_broken"):
        c.texture((120, 115, 110), 0.05)
        c.rect((6, 18, M - 6, M - 18), fill=(60, 50, 40, 255))
        if key == "window":
            c.rect((9, 21, M - 9, M - 21), fill=(150, 195, 215, 255))
            c.line([(32, 21), (32, M - 21)], fill=(60, 50, 40, 255), width=2)
            c.line([(12, 24), (22, 24)], fill=(230, 245, 255, 255), width=2)
        else:
            c.rect((9, 21, M - 9, M - 21), fill=(25, 25, 30, 255))
            for _ in range(5):
                x = r.uniform(10, 54)
                c.poly([(x, 21), (x + 4, 21), (x + 2, 21 + r.uniform(4, 10))], fill=(170, 200, 215, 255))
    elif key in ("door", "door_open"):
        c.texture((75, 60, 48), 0.06)
        if key == "door":
            c.rect((8, 8, M - 8, M - 8), fill=(135, 90, 50, 255), outline=(70, 45, 25, 255), width=2)
            for x in range(16, M - 8, 8):
                c.line([(x, 10), (x, M - 10)], fill=(105, 70, 40, 255))
            c.ellipse((44, 30, 49, 35), fill=(210, 190, 90, 255))
        else:
            c.rect((4, 4, 12, M - 4), fill=(135, 90, 50, 255), outline=(70, 45, 25, 255))
    elif key in ("fence", "fence_h"):
        vertical = key == "fence"
        for k in range(3):
            if vertical:
                x = 24 + k * 8
                c.line([(x, 0), (x, M)], fill=(150, 110, 65, 255), width=3)
            else:
                y = 24 + k * 8
                c.line([(0, y), (M, y)], fill=(150, 110, 65, 255), width=3)
        for p in (8, 32, 56):
            box = (28, p - 4, 36, p + 4) if vertical else (p - 4, 28, p + 4, 36)
            c.rect(box, fill=(110, 80, 45, 255))
    elif key == "low_wall":
        c.shadow((2, 30, 62, 48), 90, 3)
        for x in range(0, M, 10):
            col = mix((150, 148, 135), (190, 185, 170), r.random())
            c.ellipse((x - 1, 20 + r.uniform(-2, 2), x + 12, 42 + r.uniform(-2, 2)), fill=col + (255,), outline=(110, 108, 98, 255))
    elif key in ("rubble", "rubble_light", "rubble_heavy", "rubble_wood"):
        if key == "rubble_light":
            c.texture((105, 100, 94), 0.07, fine=0.08)
            c.speckle((80, 76, 70), 18, (0.6, 1.4))
        n = {"rubble": 22, "rubble_light": 5, "rubble_heavy": 40, "rubble_wood": 14}[key]
        for _ in range(n):
            x, y = r.uniform(0, M), r.uniform(0, M)
            s = r.uniform(3, 9) if key != "rubble_heavy" else r.uniform(5, 13)
            if key == "rubble_wood":
                a = r.uniform(0, math.pi)
                c.line([(x, y), (x + math.cos(a) * s * 2, y + math.sin(a) * s * 2)], fill=(60, 40, 25, 255), width=4)
                continue
            col = mix((140, 95, 80), (165, 160, 150), r.random()) if key != "rubble_light" else mix((125, 120, 112), (150, 145, 138), r.random())
            pts = [(x + math.cos(a) * s * r.uniform(0.6, 1), y + math.sin(a) * s * r.uniform(0.6, 1))
                   for a in np.linspace(0, math.tau, 6, endpoint=False)]
            c.poly(pts, fill=col + (255,), outline=shade(col, 0.6) + (255,))
        if key == "rubble_heavy":
            c.line([(8, 12), (56, 40)], fill=(90, 80, 70, 255), width=4)
    elif key == "machinery":
        c.texture((80, 80, 88), 0.05)
        c.rect((6, 6, M - 6, M - 6), fill=(100, 100, 110, 255), outline=(50, 50, 55, 255), width=2)
        c.ellipse((14, 14, 34, 34), fill=(70, 70, 76, 255), outline=(140, 140, 150, 255), width=3)
        c.rect((38, 12, 54, 52), fill=(120, 110, 90, 255))
        c.line([(10, 48), (54, 48)], fill=(160, 140, 60, 255), width=3)
    elif key == "arms_rack":
        c.rect((6, 14, 58, 20), fill=(115, 78, 43, 255))
        c.rect((6, 45, 58, 51), fill=(115, 78, 43, 255))
        for x in range(12, 57, 9):
            c.line([(x, 7), (x - 3, 41)], fill=(70, 76, 72, 255), width=3)
            c.line([(x - 3, 35), (x - 4, 55)], fill=(160, 110, 63, 255), width=5)
    elif key in ("crates", "ammo_stack"):
        for i, (x, y) in enumerate(((6, 6), (32, 8), (8, 32), (33, 33))):
            col = (150, 110, 65) if key == "crates" else (95, 100, 60)
            c.shadow((x + 2, y + 4, x + 28, y + 30), 80, 2)
            c.rect((x, y, x + 24, y + 22), fill=col + (255,), outline=shade(col, 0.6) + (255,), width=2)
            c.line([(x, y), (x + 24, y + 22)], fill=shade(col, 0.7) + (255,), width=2)
            if key == "ammo_stack":
                c.rect((x + 3, y + 8, x + 12, y + 12), fill=(210, 200, 120, 255))
    elif key in ("table", "pew", "bed", "altar", "stove"):
        c.texture((70, 55, 40), 0.06)
        if key == "table":
            c.rect((10, 16, 54, 48), fill=(140, 100, 60, 255), outline=(80, 55, 30, 255), width=2)
        elif key == "pew":
            c.rect((4, 22, 60, 42), fill=(120, 85, 50, 255), outline=(70, 50, 30, 255), width=2)
        elif key == "bed":
            c.rect((12, 6, 52, 58), fill=(180, 170, 150, 255), outline=(90, 70, 50, 255), width=2)
            c.rect((16, 10, 48, 20), fill=(235, 235, 230, 255))
            c.rect((14, 26, 50, 56), fill=(110, 90, 80, 255))
        elif key == "altar":
            c.rect((8, 16, 56, 48), fill=(225, 220, 205, 255), outline=(150, 145, 130, 255), width=2)
            c.rect((28, 12, 36, 52), fill=(160, 30, 40, 255))
        elif key == "stove":
            c.rect((14, 14, 50, 50), fill=(40, 40, 42, 255), outline=(90, 90, 95, 255), width=2)
            c.ellipse((22, 22, 42, 42), fill=(70, 30, 20, 255))
    elif key == "hay":
        for x, y in ((6, 8), (32, 6), (10, 34), (34, 34)):
            c.shadow((x + 2, y + 4, x + 26, y + 26), 70, 2)
            c.rect((x, y, x + 22, y + 20), fill=(215, 185, 100, 255), outline=(170, 140, 70, 255))
            c.blades((240, 215, 130), 10, (4, 8), lean=5)
    elif key == "wreck":
        c.texture((50, 45, 40), 0.1)
        c.rect((12, 8, 52, 56), fill=(55, 45, 38, 255), outline=(25, 20, 18, 255), width=3)
        c.ellipse((22, 20, 42, 40), fill=(40, 33, 28, 255), outline=(100, 60, 35, 255), width=2)
        c.speckle((140, 70, 30), 15, (1, 2))
        c.speckle((20, 18, 16), 15, (1, 3))
    elif key == "well":
        c.ellipse((10, 10, 54, 54), fill=(150, 148, 138, 255), outline=(100, 98, 90, 255), width=3)
        c.ellipse((20, 20, 44, 44), fill=(20, 25, 35, 255))
    elif key == "grave":
        c.rect((29, 14, 35, 50), fill=(200, 200, 195, 255))
        c.rect((20, 22, 44, 28), fill=(200, 200, 195, 255))
    elif key == "boulder":
        c.shadow((10, 16, 60, 60), 110, 3)
        c.ellipse((8, 8, 54, 50), fill=(135, 130, 122, 255), outline=(90, 86, 80, 255), width=2)
        c.ellipse((16, 12, 38, 28), fill=(170, 166, 158, 255))
    elif key == "cliff":
        c.texture((120, 112, 100), 0.18)
        for y in range(4, M, 10):
            c.line([(0, y), (M / 2, y + r.uniform(-3, 3)), (M, y)], fill=(80, 74, 66, 255), width=3)
            c.line([(0, y + 3), (M, y + 3)], fill=(165, 158, 145, 180), width=1)
    elif key == "bridge":
        c.texture((60, 90, 140), 0.1, cells=3)
        c.rect((0, 6, M, M - 6), fill=(140, 110, 75, 255))
        for x in range(0, M, 6):
            c.line([(x, 6), (x, M - 6)], fill=(95, 70, 45, 255))
        c.line([(0, 6), (M, 6)], fill=(70, 50, 30, 255), width=3)
        c.line([(0, M - 7), (M, M - 7)], fill=(70, 50, 30, 255), width=3)
    elif key == "rail":
        c.texture((110, 105, 95), 0.15)
        c.speckle((80, 75, 70), 40)
        for y in range(4, M, 10):
            c.rect((4, y, M - 4, y + 5), fill=(90, 65, 40, 255))
        c.line([(18, 0), (18, M)], fill=(170, 170, 175, 255), width=3)
        c.line([(46, 0), (46, M)], fill=(170, 170, 175, 255), width=3)
    elif key == "sandbags":
        c.shadow((2, 12, 62, 58), 100, 3)
        for row, y in enumerate((12, 24, 36)):
            off = 8 if row % 2 else 0
            for x in range(-8 + off, M, 16):
                col = mix((180, 160, 105), (205, 185, 130), r.random())
                c.ellipse((x, y, x + 17, y + 14), fill=col + (255,), outline=(130, 115, 75, 255))
    elif key == "wire":
        for k in range(3):
            y = 18 + k * 12
            pts = [(x, y + (5 if (x // 6) % 2 else -5)) for x in range(-6, M + 7, 6)]
            c.line(pts, fill=(160, 160, 160, 255), width=1)
            c.line([(p[0], p[1] + 2) for p in pts], fill=(110, 110, 110, 255), width=1)
        for x in (10, 32, 54):
            c.line([(x, 12), (x, 52)], fill=(100, 80, 55, 255), width=3)
    elif key == "hedgehog":
        c.shadow((10, 18, 60, 60), 100, 3)
        c.line([(10, 10), (54, 54)], fill=(95, 85, 75, 255), width=7)
        c.line([(54, 10), (10, 54)], fill=(110, 100, 90, 255), width=7)
        c.line([(32, 6), (32, 58)], fill=(80, 72, 64, 255), width=6)
    elif key == "teeth":
        c.shadow((10, 16, 60, 60), 110, 3)
        c.poly([(32, 8), (56, 50), (8, 50)], fill=(175, 175, 168, 255), outline=(120, 120, 115, 255))
        c.poly([(32, 8), (56, 50), (32, 42)], fill=(140, 140, 134, 255))
    elif key in ("trench", "trench_snow"):
        edge = (95, 75, 50) if key == "trench" else (210, 215, 225)
        c.texture(edge, 0.12)
        c.rect((10, 0, 54, M), fill=(45, 35, 22, 255))
        for y in range(2, M, 7):
            c.rect((13, y, 51, y + 4), fill=(110, 85, 55, 255))
        c.line([(10, 0), (10, M)], fill=shade(edge, 0.6) + (255,), width=2)
        c.line([(54, 0), (54, M)], fill=shade(edge, 0.6) + (255,), width=2)
    elif key == "foxhole":
        c.ellipse((8, 8, 56, 56), fill=(120, 95, 60, 255))
        c.ellipse((16, 16, 48, 48), fill=(40, 30, 20, 255))
    elif key in ("crater", "crater_big"):
        big = key == "crater_big"
        c.ellipse((4, 4, 60, 60) if big else (10, 10, 54, 54), fill=(105, 85, 60, 255))
        c.ellipse((12, 12, 52, 52) if big else (18, 18, 46, 46), fill=(55, 42, 30, 255))
        c.speckle((70, 55, 40), 20)
    elif key == "spider_hole":
        c.texture(lighten(bg, 0.15), 0.14)
        c.speckle(shade(bg, 0.6), 25)
    elif key == "atditch":
        c.texture((110, 90, 60), 0.1)
        c.poly([(0, 10), (M, 10), (M, 54), (0, 54)], fill=(70, 55, 35, 255))
        c.line([(0, 32), (M, 32)], fill=(35, 28, 18, 255), width=4)
    elif key == "sign":
        c.line([(32, 30), (32, 58)], fill=(100, 75, 45, 255), width=3)
        c.rect((14, 12, 50, 32), fill=(230, 210, 80, 255), outline=(60, 50, 20, 255), width=2)
        c.line([(32, 16), (32, 25)], fill=(160, 30, 30, 255), width=3)
        c.ellipse((30, 27, 34, 30), fill=(160, 30, 30, 255))
    elif key == "canvas":
        c.texture((170, 158, 110), 0.08)
        c.poly([(0, 0), (M, 0), (M / 2, M / 2)], fill=(185, 172, 122, 255))
        c.poly([(0, M), (M, M), (M / 2, M / 2)], fill=(150, 138, 95, 255))
        c.line([(0, 0), (M, M)], fill=(120, 110, 75, 255))
        c.line([(M, 0), (0, M)], fill=(120, 110, 75, 255))
    elif key == "camo_net":
        c.blades(shade(bg, 1.4), 30, (3, 6))
        for k in range(0, M, 8):
            c.line([(k, 0), (k + 16, M)], fill=(60, 70, 40, 200), width=1)
            c.line([(k, 0), (k - 16, M)], fill=(60, 70, 40, 200), width=1)
        for _ in range(18):
            x, y = r.uniform(0, M), r.uniform(0, M)
            c.ellipse((x - 3, y - 2, x + 3, y + 2), fill=mix((80, 90, 45), (120, 110, 60), r.random()) + (255,))
    elif key == "fuel_drums":
        for x, y in ((8, 8), (34, 10), (18, 34), (40, 36)):
            c.shadow((x + 2, y + 4, x + 22, y + 24), 90, 2)
            c.ellipse((x, y, x + 18, y + 18), fill=(150, 60, 40, 255), outline=(90, 35, 25, 255), width=2)
            c.ellipse((x + 6, y + 6, x + 10, y + 10), fill=(60, 30, 20, 255))
    elif key == "antenna":
        c.line([(32, 4), (32, 60)], fill=(170, 170, 175, 255), width=3)
        for a in (-0.5, 0.5):
            c.line([(32, 20), (32 + 20 * a, 58)], fill=(130, 130, 135, 255), width=1)
        c.ellipse((28, 2, 36, 10), fill=(200, 60, 50, 255))
    elif key == "redcross":
        c.rect((6, 6, M - 6, M - 6), fill=(230, 230, 228, 255))
        c.rect((26, 12, 38, M - 12), fill=(200, 25, 25, 255))
        c.rect((12, 26, M - 12, 38), fill=(200, 25, 25, 255))
    elif key == "plane_parked":
        c.shadow((10, 16, 58, 58), 90, 3)
        body = (120, 130, 110)
        c.poly([(30, 4), (34, 4), (36, 58), (28, 58)], fill=body + (255,))
        c.poly([(4, 24), (60, 24), (60, 32), (4, 32)], fill=shade(body, 1.1) + (255,))
        c.poly([(20, 50), (44, 50), (44, 56), (20, 56)], fill=body + (255,))
    elif key in ("hull", "fuselage", "fuselage_holed"):
        col = {"hull": (110, 114, 124), "fuselage": (150, 156, 150), "fuselage_holed": (110, 112, 108)}[key]
        c.rect((0, 0, M, M), fill=col + (255,))
        for k in range(0, M, 16):
            c.line([(k, 0), (k, M)], fill=shade(col, 0.8) + (255,), width=1)
        for k in range(4, M, 8):
            c.ellipse((k - 1, 7, k + 1, 9), fill=lighten(col, 0.2) + (255,))
            c.ellipse((k - 1, 55, k + 1, 57), fill=lighten(col, 0.2) + (255,))
        if key == "fuselage_holed":
            for _ in range(6):
                x, y = r.uniform(8, 56), r.uniform(8, 56)
                c.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(30, 30, 30, 255))
    elif key == "railing":
        c.rect((0, 0, M, M), fill=(0, 0, 0, 0))
        c.line([(0, 30), (M, 30)], fill=(210, 210, 215, 255), width=3)
        c.line([(0, 44), (M, 44)], fill=(190, 190, 195, 255), width=2)
        for k in range(4, M, 20):
            c.line([(k, 24), (k, 50)], fill=(160, 160, 165, 255), width=3)
    elif key == "funnel":
        c.shadow((8, 12, 60, 62), 120, 4)
        c.ellipse((6, 6, 58, 58), fill=(70, 72, 76, 255), outline=(40, 40, 44, 255), width=3)
        c.ellipse((16, 16, 48, 48), fill=(20, 20, 22, 255))
    elif key in ("gun_turret", "gun_mount"):
        big = key == "gun_turret"
        c.shadow((6, 10, 62, 62), 120, 4)
        c.rect((4, 8, 60, 56) if big else (10, 12, 54, 52), fill=(128, 134, 142, 255), outline=(70, 74, 80, 255),
               width=3)
        c.rect((26, 0, 38, 12) if big else (28, 2, 36, 14), fill=(90, 94, 100, 255))
    elif key in ("torpedo_tubes", "torpedo_rack"):
        for yy in (14, 26, 38, 50):
            c.rect((4, yy - 4, 60, yy + 4), fill=(120, 132, 120, 255), outline=(60, 66, 60, 255), width=1)
    elif key == "depth_charges":
        for k in range(3):
            c.ellipse((6 + k * 18, 20, 22 + k * 18, 44), fill=(90, 100, 90, 255), outline=(40, 44, 40, 255), width=2)
    elif key == "bunk":
        c.rect((4, 4, 60, 60), fill=(70, 72, 80, 255))
        for yy in (8, 24, 40):
            c.rect((6, yy, 58, yy + 12), fill=(150, 150, 140, 255), outline=(90, 92, 98, 255), width=2)
            c.rect((8, yy + 2, 20, yy + 10), fill=(200, 200, 195, 255))
    elif key in ("locker", "ready_locker", "repair_locker"):
        col = {"locker": (110, 115, 125), "ready_locker": (170, 150, 70), "repair_locker": (190, 60, 50)}[key]
        c.rect((6, 6, 58, 58), fill=col + (255,), outline=shade(col, 0.6) + (255,), width=3)
        c.line([(32, 8), (32, 56)], fill=shade(col, 0.6) + (255,), width=2)
        if key == "repair_locker":
            c.rect((22, 26, 42, 38), fill=(240, 240, 240, 255))
    elif key in ("boiler", "turbine"):
        col = (150, 104, 86) if key == "boiler" else (130, 136, 148)
        c.shadow((6, 8, 62, 62), 110, 3)
        if key == "boiler":
            c.rect((6, 6, 58, 58), fill=col + (255,), outline=(70, 50, 40, 255), width=3)
            c.ellipse((20, 20, 44, 44), fill=(220, 120, 40, 255))
        else:
            c.ellipse((4, 14, 60, 50), fill=col + (255,), outline=(70, 74, 80, 255), width=3)
            c.line([(4, 32), (60, 32)], fill=(90, 94, 100, 255), width=3)
    elif key in ("ammo_rack", "avgas"):
        if key == "ammo_rack":
            for yy in range(6, 60, 12):
                for xx in range(6, 60, 10):
                    c.rect((xx, yy, xx + 7, yy + 9), fill=(190, 165, 80, 255), outline=(90, 80, 40, 255))
        else:
            c.ellipse((6, 6, 58, 58), fill=(190, 100, 60, 255), outline=(90, 50, 30, 255), width=3)
            c.rect((26, 24, 38, 40), fill=(240, 220, 120, 255))
    elif key in ("life_ring", "life_raft"):
        if key == "life_ring":
            c.ellipse((10, 10, 54, 54), fill=(240, 140, 50, 255))
            c.ellipse((22, 22, 42, 42), fill=(0, 0, 0, 0))
        else:
            c.rect((4, 16, 60, 48), fill=(220, 180, 60, 255), outline=(120, 100, 40, 255), width=3)
    elif key in ("radar_scope", "radio_set", "chart_table", "helm", "periscope", "lookout_post", "station",
                 "steering_gear"):
        col = {"radar_scope": (40, 180, 90), "radio_set": (120, 130, 120), "chart_table": (190, 180, 140),
               "helm": (200, 170, 90), "periscope": (180, 180, 150), "lookout_post": (210, 200, 150),
               "station": (190, 180, 140), "steering_gear": (140, 145, 150)}[key]
        c.texture(ground_color(tid), 0.05)
        if key == "helm":
            c.ellipse((12, 12, 52, 52), outline=col + (255,), width=4)
            for a in range(0, 360, 45):
                x = 32 + 22 * math.cos(math.radians(a))
                y = 32 + 22 * math.sin(math.radians(a))
                c.line([(32, 32), (x, y)], fill=col + (255,), width=3)
        elif key == "radar_scope":
            c.ellipse((10, 10, 54, 54), fill=(10, 30, 16, 255), outline=(90, 90, 90, 255), width=3)
            c.line([(32, 32), (50, 18)], fill=col + (255,), width=2)
        elif key == "lookout_post":
            c.rect((22, 26, 42, 38), fill=(40, 40, 40, 255))
            c.ellipse((18, 18, 30, 30), fill=(30, 30, 30, 255))
            c.ellipse((34, 18, 46, 30), fill=(30, 30, 30, 255))
        else:
            c.rect((12, 12, 52, 52), fill=col + (255,), outline=shade(col, 0.5) + (255,), width=3)
    elif key in ("wing", "engine_nacelle"):
        c.rect((0, 10, M, 54), fill=(150, 155, 150, 255))
        c.line([(0, 12), (M, 12)], fill=(190, 195, 190, 255), width=2)
        if key == "engine_nacelle":
            c.ellipse((8, 8, 56, 56), fill=(70, 70, 72, 255))
            c.ellipse((20, 20, 44, 44), fill=(170, 170, 175, 90))
    elif key == "bollard":
        c.texture((120, 120, 116), 0.05)
        c.ellipse((16, 16, 48, 48), fill=(40, 40, 44, 255), outline=(90, 90, 96, 255), width=3)
    elif key == "hatch_exit":
        c.texture((110, 110, 104), 0.05)
        c.ellipse((10, 10, 54, 54), fill=(40, 40, 40, 255), outline=(230, 180, 90, 255), width=4)
    elif key == "fire_curtain":
        c.texture((98, 101, 108), 0.05)
        c.rect((0, 26, M, 38), fill=(170, 90, 70, 255))
    elif not paint_place(c, key, tid, r):
        # fallback: painted glyph on its ground
        c.texture(lighten(bg, 0.1), 0.08)
    if solid:
        ground.stand(c)
        return ground
    return c


def paint_place(c: Canvas, key: str, tid: int, r) -> bool:
    """The landmarks and places (landmarks.py). False if the key isn't one of them."""
    fg = fg_color(tid)
    if key == "poplar":
        for i, col in enumerate((shade(fg, 0.75), fg, lighten(fg, 0.2))):
            for _ in range(4 - i):
                x, y = 32 + r.uniform(-4, 4) - i, 30 + r.uniform(-8, 8) - i * 2
                c.ellipse((x - 9 + i * 2, y - 16 + i * 3, x + 9 - i * 2, y + 16 - i * 3), fill=col + (255,))
    elif key == "wall_white":
        c.texture((222, 216, 200), 0.05, fine=0.06)
        for _ in range(4):
            x, y = r.uniform(0, M), r.uniform(0, M)
            c.line([(x, y), (x + r.uniform(-9, 9), y + r.uniform(4, 12))], fill=(160, 150, 135, 200), width=1)
        c.speckle((190, 180, 160), 10, (1, 2.5))
        c.rect((0, 0, M - 1, 3), fill=(245, 242, 232, 160))
        c.rect((0, M - 4, M - 1, M - 1), fill=(170, 162, 146, 160))
    elif key in ("sail", "sail2"):
        flip = key == "sail2"

        def P(x, y):
            return (M - x, y) if flip else (x, y)
        c.poly([P(-4, 6), P(6, -4), P(68, 58), P(58, 68)], fill=(120, 100, 70, 90))
        for t in range(-4, 70, 7):
            c.line([P(t - 5, t + 5), P(t + 5, t - 5)], fill=(210, 195, 160, 255), width=2)
        c.line([P(-4, 6), P(58, 68)], fill=(150, 120, 80, 255), width=3)
        c.line([P(6, -4), P(68, 58)], fill=(150, 120, 80, 255), width=3)
    elif key == "boxcar":
        c.rect((4, 12, 60, 52), fill=(150, 78, 55, 255), outline=(70, 36, 24, 255), width=2)
        for x in range(8, 60, 6):
            c.line([(x, 14), (x, 50)], fill=(120, 60, 42, 255), width=1)
        c.line([(4, 32), (60, 32)], fill=(185, 110, 80, 255), width=3)
    elif key == "locomotive":
        c.rect((6, 16, 58, 48), fill=(40, 40, 44, 255), outline=(15, 15, 16, 255), width=2)
        c.rect((10, 22, 40, 42), fill=(62, 62, 68, 255))
        c.ellipse((14, 26, 24, 38), fill=(20, 20, 20, 255), outline=(110, 110, 115, 255), width=2)
        c.rect((44, 12, 60, 52), fill=(55, 30, 26, 255), outline=(20, 12, 10, 255), width=2)
        c.line([(6, 32), (58, 32)], fill=(170, 40, 35, 255), width=1)
    elif key == "water_tower":
        for x, y in ((10, 10), (54, 10), (10, 54), (54, 54)):
            c.line([(32, 32), (x, y)], fill=(90, 85, 75, 255), width=3)
            c.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(70, 66, 60, 255))
        c.ellipse((14, 14, 50, 50), fill=(150, 140, 120, 255), outline=(80, 74, 64, 255), width=3)
        c.ellipse((22, 20, 36, 30), fill=(185, 175, 155, 255))
        c.line([(32, 14), (32, 4)], fill=(60, 56, 50, 255), width=2)
    elif key == "chimney":
        c.ellipse((10, 10, 54, 54), fill=(165, 85, 65, 255), outline=(90, 45, 35, 255), width=3)
        for rr in (17, 13):
            c.ellipse((32 - rr, 32 - rr, 32 + rr, 32 + rr), outline=(130, 65, 50, 255), width=1)
        c.ellipse((22, 22, 42, 42), fill=(25, 20, 18, 255))
        c.speckle((40, 36, 34), 10, (1, 2.5))
    elif key == "silo":
        c.ellipse((3, 3, 61, 61), fill=(185, 182, 170, 255), outline=(115, 112, 104, 255), width=3)
        c.ellipse((16, 16, 48, 48), fill=(200, 198, 188, 255), outline=(150, 148, 140, 255), width=2)
        c.ellipse((27, 27, 37, 37), fill=(120, 118, 110, 255))
        c.ellipse((10, 8, 30, 20), fill=(225, 224, 215, 120))
    elif key == "calvary":
        c.rect((18, 18, 46, 46), fill=(150, 146, 134, 255), outline=(100, 96, 88, 255), width=2)
        c.rect((29, 8, 35, 56), fill=(210, 205, 190, 255), outline=(120, 116, 106, 255))
        c.rect((18, 20, 46, 26), fill=(210, 205, 190, 255), outline=(120, 116, 106, 255))
        for _ in range(5):
            x, y = r.uniform(20, 44), r.uniform(46, 54)
            c.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(200, 40, 50, 255))
    elif key == "memorial":
        for i, col in enumerate(((150, 146, 136), (180, 176, 164), (205, 200, 188))):
            k = 6 + i * 8
            c.rect((k, k, M - k, M - k), fill=col + (255,), outline=shade(col, 0.7) + (255,), width=2)
        c.ellipse((26, 26, 38, 38), fill=(60, 110, 50, 255), outline=(180, 40, 45, 255), width=2)
    elif key == "fountain":
        c.ellipse((4, 4, 60, 60), fill=(160, 156, 146, 255), outline=(100, 96, 88, 255), width=3)
        c.ellipse((11, 11, 53, 53), fill=(70, 110, 160, 255))
        c.ellipse((27, 27, 37, 37), fill=(170, 166, 156, 255), outline=(110, 106, 98, 255), width=2)
        for a in range(0, 360, 45):
            x, y = 32 + 14 * math.cos(math.radians(a)), 32 + 14 * math.sin(math.radians(a))
            c.ellipse((x - 1.5, y - 1.5, x + 1.5, y + 1.5), fill=(210, 230, 250, 255))
    elif key == "vault":
        c.rect((8, 6, 56, 58), fill=(175, 170, 158, 255), outline=(105, 102, 94, 255), width=2)
        c.poly([(8, 6), (32, 18), (56, 6)], fill=(150, 146, 136, 255))
        c.line([(32, 18), (32, 58)], fill=(120, 116, 108, 255), width=2)
        c.rect((26, 44, 38, 58), fill=(50, 50, 55, 255))
        c.rect((29, 26, 35, 30), fill=(200, 196, 184, 255))
    elif key == "timber":
        for row, y in enumerate((10, 26, 42)):
            c.rect((4, y, 60, y + 13), fill=(150, 110, 70, 255), outline=(90, 62, 38, 255))
            for x in range(8 + (row % 2) * 6, 60, 12):
                c.ellipse((x - 5, y + 1, x + 5, y + 12), fill=(200, 160, 105, 255), outline=(120, 85, 50, 255))
    elif key == "sangar":
        c.shadow((6, 22, 60, 58), 90, 3)
        for k in range(9):
            a = math.pi * (0.1 + 0.8 * k / 8)
            x, y = 32 - math.cos(a) * 22, 44 - math.sin(a) * 22
            col = mix((150, 138, 112), (195, 182, 150), r.random())
            rr = r.uniform(5, 7)
            c.ellipse((x - rr, y - rr * 0.8, x + rr, y + rr * 0.8), fill=col + (255,), outline=(110, 100, 80, 255))
    elif key == "torii":
        c.shadow((6, 18, 62, 48), 80, 3)
        c.rect((2, 14, 62, 22), fill=(40, 30, 28, 255))
        c.rect((6, 24, 58, 30), fill=(205, 65, 48, 255))
        for x in (14, 50):
            c.ellipse((x - 5, 22, x + 5, 32), fill=(175, 50, 38, 255), outline=(90, 25, 20, 255))
    elif key == "stupa":
        for rr, col in ((30, (220, 208, 168)), (22, (236, 226, 190)), (13, (246, 238, 208)), (6, (215, 175, 60))):
            c.ellipse((32 - rr, 32 - rr, 32 + rr, 32 + rr), fill=col + (255,), outline=shade(col, 0.75) + (255,))
        c.ellipse((30, 30, 34, 34), fill=(250, 215, 90, 255))
    elif key == "oil_tank":
        c.ellipse((2, 2, 62, 62), fill=(165, 165, 160, 255), outline=(90, 90, 88, 255), width=3)
        for a in range(0, 360, 30):
            x, y = 32 + 28 * math.cos(math.radians(a)), 32 + 28 * math.sin(math.radians(a))
            c.line([(32, 32), (x, y)], fill=(135, 135, 130, 255), width=1)
        c.ellipse((26, 26, 38, 38), fill=(120, 120, 116, 255))
    elif key == "radar":
        c.ellipse((20, 20, 44, 44), fill=(80, 84, 80, 255))
        c.ellipse((6, 6, 58, 58), outline=(200, 205, 200, 255), width=3)
        for k in range(-20, 24, 8):
            c.line([(32 + k, 32 - math.sqrt(max(0, 26 * 26 - k * k))), (32 + k, 32 + math.sqrt(max(0, 26 * 26 - k * k)))],
                   fill=(170, 176, 170, 200), width=1)
            c.line([(32 - math.sqrt(max(0, 26 * 26 - k * k)), 32 + k), (32 + math.sqrt(max(0, 26 * 26 - k * k)), 32 + k)],
                   fill=(170, 176, 170, 200), width=1)
        c.line([(32, 32), (32, 14)], fill=(60, 60, 60, 255), width=3)
    elif key == "pole":
        c.line([(14, 30), (50, 30)], fill=(110, 85, 55, 255), width=4)
        for x in (16, 26, 38, 48):
            c.ellipse((x - 2, 27, x + 2, 33), fill=(220, 225, 230, 255))
        c.ellipse((27, 25, 37, 35), fill=(125, 95, 60, 255), outline=(70, 52, 32, 255))
    elif key == "ac_wreck":
        c.texture((48, 44, 40), 0.18)
        c.speckle((25, 22, 20), 30, (1, 3))
        for _ in range(7):
            x, y = r.uniform(6, 58), r.uniform(6, 58)
            a = r.uniform(0, math.pi)
            L = r.uniform(8, 20)
            col = mix((150, 150, 148), (90, 88, 84), r.random())
            c.poly([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L),
                    (x + math.cos(a + 0.4) * L * 0.6, y + math.sin(a + 0.4) * L * 0.6)], fill=col + (255,))
        c.speckle((200, 90, 30), 3, (0.6, 1.2))
    elif key == "tobruk":
        c.rect((8, 8, 56, 56), fill=(160, 160, 152, 255), outline=(110, 110, 104, 255), width=3)
        c.ellipse((18, 18, 46, 46), fill=(30, 30, 30, 255), outline=(190, 190, 184, 255), width=3)
    else:
        return False
    return True


OBJECT_KEYS = None


def is_object(key: str) -> bool:
    d = T.DEFS[T.ID[key]]
    if key in ("spider_hole", "gun_pit", "doorway", "crater_water"):
        return False
    if key in ("window", "window_broken", "embrasure", "door", "door_open", "fence", "fence_h", "low_wall",
               "wire", "sandbags", "trench", "trench_snow", "foxhole", "crater", "crater_big", "atditch",
               "hedgehog", "teeth", "sign", "canvas", "camo_net", "ammo_stack", "arms_rack", "fuel_drums", "antenna",
               "redcross", "plane_parked", "bridge", "rail", "rubble", "rubble_light", "rubble_heavy",
               "rubble_wood", "stump", "log", "grave", "well", "hay", "wreck", "machinery", "crates",
               "table", "pew", "altar", "bed", "stove", "boulder", "cliff", "hull", "funnel", "gun_turret",
               "gun_mount", "torpedo_tubes", "depth_charges", "bunk", "locker", "boiler", "turbine", "ammo_rack",
               "avgas", "ready_locker", "repair_locker", "life_ring", "life_raft", "radar_scope", "radio_set",
               "torpedo_rack", "steering_gear", "fuselage", "fuselage_holed", "wing", "engine_nacelle", "helm",
               "chart_table", "periscope", "lookout_post", "station", "hatch_exit", "fire_curtain", "railing",
               "bollard", "poplar", "wall_white", "sail", "sail2", "boxcar", "locomotive", "water_tower",
               "chimney", "silo", "calvary", "memorial", "fountain", "vault", "timber", "sangar", "torii", "stupa",
               "oil_tank", "radar", "pole", "tobruk", "ac_wreck"):
        return True
    if key.startswith("wall") or key.startswith("tree") or key in ("pine", "olive", "palm", "dead_tree",
                                                                    "bush", "bush_snow", "jungle", "bamboo",
                                                                    "scrub", "hedge", "garden_hedge"):
        return True
    return False


# newer tiles drawn by the painter of the tile they're most like (in their own colours)
SPRITE_ALIAS = {"ac_body": "dirt", "ac_engine": "dirt", "ac_wing": "dirt", "ac_tail": "dirt",
                "birch": "tree", "cypress": "pine", "fir": "pine", "apple_tree": "tree", "mangrove": "tree",
                "vineyard": "corn", "sugarcane": "corn", "drystone": "low_wall", "camelthorn": "scrub",
                "reeds": "tall_grass", "scree": "rock_ground", "outcrop": "boulder", "dune": "sand", "wadi": "sand",
                "tomb": "wall_stone", "stairs": "floor_wood", "trapdoor": "floor_wood",
                "waterlogged": "mud", "flooded_trench": "trench", "snow_drift": "deep_snow",
                "food_store": "crates", "medical_store": "crates", "spares_store": "crates",
                "transformer": "machinery", "hospital_bed": "bed", "market_stall": "table",
                "checkpoint": "sandbags", "shelter_floor": "floor_concrete", "supply_cache": "crates"}


def paint_terrain(tid: int, variant: int) -> np.ndarray:
    key = T.DEFS[tid].key
    key = SPRITE_ALIAS.get(key, key)
    c = Canvas(seed=tid * 97 + variant * 13 + 7)
    if key == "void":
        return np.zeros((M, M, 4), np.uint8)
    if is_object(key):
        c = paint_object(c, key, tid) or c
    else:
        paint_ground(c, key, tid)
    return c.array()


# ====================================================================== units

UNIFORM = {
    # nation: (uniform, helmet, helmet style, webbing)
    "usa": ((110, 105, 70), (85, 95, 60), "m1", (150, 135, 90)),
    "uk": ((135, 115, 75), (95, 90, 60), "brodie", (160, 145, 100)),
    "canada": ((135, 115, 75), (95, 90, 60), "brodie", (160, 145, 100)),
    "australia": ((145, 125, 80), (95, 90, 60), "brodie", (160, 145, 100)),
    "newzealand": ((135, 115, 75), (95, 90, 60), "brodie", (160, 145, 100)),
    "india": ((150, 130, 85), (95, 90, 60), "brodie", (160, 145, 100)),
    "ussr": ((125, 115, 75), (70, 90, 55), "ssh", (110, 90, 60)),
    "france": ((110, 120, 125), (80, 95, 110), "adrian", (100, 80, 50)),
    "poland": ((110, 110, 80), (80, 90, 60), "m1", (100, 80, 50)),
    "china": ((95, 105, 110), (90, 100, 95), "cap", (110, 90, 60)),
    "germany": ((95, 100, 90), (80, 85, 80), "stahlhelm", (45, 40, 35)),
    "italy": ((125, 120, 95), (100, 105, 85), "m33", (80, 65, 45)),
    "japan": ((145, 130, 85), (120, 110, 70), "type90", (100, 80, 50)),
    "finland": ((105, 110, 100), (95, 100, 95), "stahlhelm", (60, 55, 45)),
    "hungary": ((125, 110, 75), (95, 95, 70), "stahlhelm", (70, 55, 40)),
    "romania": ((120, 115, 85), (90, 95, 75), "stahlhelm", (70, 55, 40)),
}
SKIN = (205, 165, 130)


def paint_soldier(nation: str, role: str, stance: int, state: str = "ok", winter=False) -> np.ndarray:
    uni, helm, hstyle, web = UNIFORM.get(nation, UNIFORM["usa"])
    if winter:
        uni = mix(uni, (225, 228, 235), 0.7)
    c = Canvas(seed=hash((nation, role, stance, state)) & 0xFFFF)
    d = c.d
    gun = (40, 38, 36)
    wood = (120, 80, 45)
    if stance == 2 or state in ("downed", "dead"):
        # lying: body along the x axis, head to the right
        c.shadow((8, 30, 60, 46), 90, 2)
        if state == "downed":
            c.ellipse((16, 26, 50, 52), fill=(130, 10, 10, 200))
        c.ellipse((12, 28, 22, 40), fill=shade(uni, 0.8) + (255,))       # boots/legs
        c.ellipse((12, 36, 22, 48), fill=shade(uni, 0.8) + (255,))
        c.rect((18, 28, 44, 48), fill=uni + (255,))
        c.rect((24, 30, 38, 46), fill=web + (140,))
        c.ellipse((38, 28, 54, 46), fill=shade(uni, 1.05) + (255,))     # shoulders
        _helmet(c, hstyle, helm, 52, 37, 8)
        if state != "downed" and role not in ("medic",):
            _weapon(c, role, 44, 30, 62, 26, gun, wood)
        if state == "downed":
            c.line([(28, 30), (34, 44)], fill=(230, 230, 230, 255), width=2)
        return _enlarge(c.array(), (6, 10, 62, 66))
    small = 0.85 if stance == 1 else 1.0
    cx, cy = 32, 34
    c.shadow((cx - 16 * small, cy - 6, cx + 18 * small, cy + 20 * small), 90, 3)
    # pack
    if role not in ("tank_crew",):
        c.rect((cx - 9 * small, cy + 4, cx + 9 * small, cy + 16 * small), fill=shade(web, 0.8) + (255,))
    if role == "flamethrower":
        c.ellipse((cx - 11, cy + 2, cx - 1, cy + 18), fill=(100, 100, 90, 255))
        c.ellipse((cx + 1, cy + 2, cx + 11, cy + 18), fill=(100, 100, 90, 255))
    if role == "radioman":
        c.rect((cx - 10, cy + 2, cx + 10, cy + 18), fill=(80, 85, 60, 255), outline=(40, 40, 30, 255))
        c.line([(cx + 8, cy + 4), (cx + 22, cy - 22)], fill=(40, 40, 40, 255), width=1)
    # shoulders/torso
    c.ellipse((cx - 15 * small, cy - 8 * small, cx + 15 * small, cy + 10 * small), fill=uni + (255,),
              outline=shade(uni, 0.6) + (255,))
    # webbing straps
    c.line([(cx - 9 * small, cy - 6), (cx + 5 * small, cy + 8)], fill=web + (255,), width=2)
    c.line([(cx + 9 * small, cy - 6), (cx - 5 * small, cy + 8)], fill=web + (255,), width=2)
    if state == "surrendered":
        c.line([(cx - 12, cy - 4), (cx - 16, cy - 22)], fill=uni + (255,), width=5)
        c.line([(cx + 12, cy - 4), (cx + 16, cy - 22)], fill=uni + (255,), width=5)
        c.ellipse((cx - 19, cy - 26, cx - 13, cy - 20), fill=SKIN + (255,))
        c.ellipse((cx + 13, cy - 26, cx + 19, cy - 20), fill=SKIN + (255,))
    else:
        _weapon(c, role, cx - 4, cy + 2, cx + 18, cy - 20, gun, wood)
        c.ellipse((cx + 2, cy - 6, cx + 9, cy + 1), fill=SKIN + (255,))    # hand
    if role == "medic":
        c.rect((cx - 15 * small, cy - 4, cx - 10 * small, cy + 3), fill=(240, 240, 240, 255))
        c.line([(cx - 12.5 * small, cy - 3), (cx - 12.5 * small, cy + 2)], fill=(200, 20, 20, 255), width=2)
    _helmet(c, hstyle if role not in ("tank_crew",) else "cap", helm, cx, cy - 2, 9 * small,
            medic=(role == "medic"), officer=(role == "officer"))
    return _enlarge(c.array(), (11, 7, 55, 51))


def _enlarge(arr, box):
    """Crop to the figure and scale back up so small subjects fill the tile."""
    img = Image.fromarray(arr, "RGBA").crop(box).resize((M, M), Image.LANCZOS)
    return np.asarray(img, np.uint8)


def _helmet(c, style, col, x, y, r, medic=False, officer=False):
    d = c.d
    if style in ("brodie",):
        d.ellipse((x - r * 1.35, y - r * 1.35, x + r * 1.35, y + r * 1.35), fill=shade(col, 0.85) + (255,))
    elif style == "stahlhelm":
        d.ellipse((x - r * 1.2, y - r * 1.15, x + r * 1.2, y + r * 1.25), fill=shade(col, 0.8) + (255,))
    elif style == "adrian":
        d.ellipse((x - r * 1.15, y - r * 1.15, x + r * 1.15, y + r * 1.15), fill=shade(col, 0.85) + (255,))
    if style == "cap":
        d.ellipse((x - r * 0.9, y - r * 0.9, x + r * 0.9, y + r * 0.9), fill=col + (255,))
        d.rectangle((x - r * 0.3, y - r * 1.3, x + r * 0.3, y - r * 0.8), fill=shade(col, 0.6) + (255,))
    else:
        d.ellipse((x - r, y - r, x + r, y + r), fill=col + (255,), outline=shade(col, 0.6) + (255,))
        d.ellipse((x - r * 0.5, y - r * 0.7, x + r * 0.1, y - r * 0.2), fill=lighten(col, 0.25) + (255,))
    if style == "adrian":
        d.line([(x, y - r), (x, y + r)], fill=shade(col, 0.6) + (255,), width=2)
    if style == "type90":
        d.polygon([(x, y - 3), (x + 2, y + 1), (x - 2, y + 1)], fill=(220, 190, 60, 255))
    if medic:
        d.rectangle((x - r * 0.6, y - r * 0.15, x + r * 0.6, y + r * 0.15), fill=(210, 20, 20, 255))
        d.rectangle((x - r * 0.15, y - r * 0.6, x + r * 0.15, y + r * 0.6), fill=(210, 20, 20, 255))
    if officer:
        d.line([(x - r, y + r * 0.6), (x + r, y + r * 0.6)], fill=(220, 200, 90, 255), width=2)


def _weapon(c, role, x0, y0, x1, y1, gun, wood):
    d = c.d
    if role in ("lmg_gunner", "hmg_gunner"):
        d.line([(x0, y0), (x1 + 4, y1 - 4)], fill=gun + (255,), width=4)
        d.line([(x1 - 2, y1 + 2), (x1 + 4, y1 + 6)], fill=gun + (255,), width=2)
    elif role in ("at_soldier",):
        d.line([(x0 - 6, y0 + 6), (x1 + 4, y1 - 4)], fill=(80, 90, 55, 255), width=6)
    elif role in ("smg_gunner", "squad_leader", "tank_crew"):
        d.line([(x0 + 4, y0 - 4), (x1 - 4, y1 + 4)], fill=gun + (255,), width=3)
        d.line([(x0 + 10, y0 - 6), (x0 + 12, y0 + 2)], fill=gun + (255,), width=2)
    elif role in ("mortarman",):
        d.line([(x0, y0), (x1, y1)], fill=(70, 75, 60, 255), width=5)
    elif role in ("medic",):
        pass
    else:
        d.line([(x0 - 2, y0 + 2), (x0 + 8, y0 - 8)], fill=wood + (255,), width=4)
        d.line([(x0 + 8, y0 - 8), (x1 + 2, y1 - 2)], fill=gun + (255,), width=2)


def paint_ring(kind: str) -> np.ndarray:
    c = Canvas()
    if kind == "ring":
        c.ellipse((4, 34, 60, 62), fill=(255, 255, 255, 70), outline=(255, 255, 255, 255), width=5)
    elif kind == "leader":
        c.ellipse((4, 34, 60, 62), fill=(255, 255, 255, 70), outline=(255, 255, 255, 255), width=5)
        c.poly([(32, 0), (40, 10), (24, 10)], fill=(255, 255, 255, 255))
    elif kind == "player":
        c.ellipse((2, 32, 62, 63), fill=(255, 255, 255, 90), outline=(255, 255, 255, 255), width=6)
        c.poly([(32, 0), (42, 12), (22, 12)], fill=(255, 255, 255, 255))
    elif kind == "bracket":
        for (x, y, dx, dy) in ((3, 3, 1, 1), (60, 3, -1, 1), (3, 60, 1, -1), (60, 60, -1, -1)):
            c.line([(x, y), (x + dx * 12, y)], fill=(255, 255, 255, 255), width=3)
            c.line([(x, y), (x, y + dy * 12)], fill=(255, 255, 255, 255), width=3)
    elif kind == "cursor":
        for (x, y, dx, dy) in ((2, 2, 1, 1), (61, 2, -1, 1), (2, 61, 1, -1), (61, 61, -1, -1)):
            c.line([(x, y), (x + dx * 16, y)], fill=(255, 255, 255, 255), width=4)
            c.line([(x, y), (x, y + dy * 16)], fill=(255, 255, 255, 255), width=4)
    elif kind == "dot":
        c.ellipse((26, 26, 38, 38), fill=(255, 255, 255, 230))
    elif kind == "fill":
        c.rect((0, 0, M, M), fill=(255, 255, 255, 255))
    elif kind == "mine":
        c.ellipse((18, 18, 46, 46), fill=(90, 90, 80, 255), outline=(255, 255, 255, 255), width=3)
        c.line([(20, 20), (44, 44)], fill=(255, 255, 255, 255), width=3)
    return c.array()


CAMO = {
    "usa": (88, 98, 58), "uk": (95, 95, 65), "canada": (95, 95, 65), "australia": (100, 100, 70),
    "newzealand": (95, 95, 65), "india": (100, 95, 65), "ussr": (72, 92, 52), "france": (105, 110, 90),
    "poland": (95, 100, 70), "china": (90, 95, 75), "germany": (170, 150, 95), "germany_early": (75, 80, 85),
    "italy": (175, 155, 105), "japan": (140, 125, 80), "finland": (100, 105, 90), "hungary": (95, 100, 80),
    "romania": (100, 100, 75), "desert": (190, 170, 120), "winter": (215, 218, 222),
}


def paint_vehicle(vclass: str, camo: str, facing: int, part: str = "hull", burning=False, open_top=False) -> np.ndarray:
    """vclass: tank, heavy, ltank, tankette, td, spg, halftrack, truck, car, armcar, lc, amtrac,
    atgun, aagun, fieldgun.  part: hull or turret."""
    col = CAMO.get(camo, (90, 95, 70))
    c = Canvas(seed=hash((vclass, camo)) & 0xFFFF)
    ang = -facing * math.pi / 4     # octant 0 = east; screen y down
    dark = shade(col, 0.55)
    light = lighten(col, 0.2)
    track = (45, 45, 42)

    def P(pts):
        return rot(pts, ang)

    if part == "turret":
        if vclass in ("tank", "heavy", "ltank", "armcar", "tankette", "open_td"):
            r = {"tank": 11, "heavy": 13, "ltank": 8, "armcar": 7, "tankette": 5, "open_td": 14}[vclass]
            L = {"tank": 26, "heavy": 30, "ltank": 18, "armcar": 16, "tankette": 12, "open_td": 29}[vclass]
            c.poly(P([(32 - r, 32 - r * 0.9), (32 + r * 0.8, 32 - r * 0.9), (32 + r, 32), (32 + r * 0.8, 32 + r * 0.9),
                      (32 - r, 32 + r * 0.9)]), fill=col + (255,), outline=dark + (255,))
            c.line(P([(32 + r - 1, 32), (32 + L, 32)]), fill=dark + (255,), width=3 if vclass != "heavy" else 4)
            if open_top or vclass == "open_td":
                c.poly(P([(32 - r + 3, 32 - r * .7), (32 + r - 3, 32 - r * .6),
                          (32 + r - 3, 32 + r * .6), (32 - r + 3, 32 + r * .7)]),
                       fill=shade(col, .28) + (255,), outline=light + (255,))
            else:
                c.ellipse((28, 26, 34, 32), fill=light + (255,))
        elif vclass == "aa_halftrack":
            c.ellipse((25, 25, 39, 39), fill=dark + (255,), outline=light + (255,))
            for dy in (-5, -2, 2, 5):
                c.line(P([(30, 32 + dy), (51, 32 + dy)]), fill=(40, 43, 39, 255), width=2)
            for dy in (-8, 6):
                c.poly(P([(30, 32 + dy), (36, 32 + dy), (36, 34 + dy), (30, 34 + dy)]),
                       fill=col + (255,), outline=light + (255,))
        elif vclass in ("atgun", "fieldgun", "aagun"):
            c.ellipse((25, 25, 39, 39), fill=light + (255,), outline=dark + (255,))
            if vclass == "aagun":
                for dy in (-3, 3):
                    c.line(P([(29, 32 + dy), (58, 32 + dy)]), fill=dark + (255,), width=3)
            else:
                c.poly(P([(34, 18), (40, 18), (40, 46), (34, 46)]), fill=col + (255,), outline=dark + (255,))
                end = 58 if vclass == "atgun" else 54
                c.line(P([(26, 32), (end, 32)]), fill=dark + (255,), width=4 if vclass == "fieldgun" else 3)
        return c.array()
    if vclass in ("tank", "heavy", "ltank", "tankette", "td", "spg", "open_td"):
        size = {"tank": 1.0, "heavy": 1.12, "ltank": 0.82, "tankette": 0.6, "td": 1.0, "spg": 0.92, "open_td": 1.0}[vclass]
        hl, hw = 26 * size, 15 * size
        c.shadow((32 - hl, 32 - hw + 6, 32 + hl, 32 + hw + 8), 110, 3)
        # tracks
        c.poly(P([(32 - hl, 32 - hw), (32 + hl, 32 - hw), (32 + hl, 32 - hw + 6 * size), (32 - hl, 32 - hw + 6 * size)]), fill=track + (255,))
        c.poly(P([(32 - hl, 32 + hw - 6 * size), (32 + hl, 32 + hw - 6 * size), (32 + hl, 32 + hw), (32 - hl, 32 + hw)]), fill=track + (255,))
        for k in range(-4, 5):
            x = 32 + k * hl / 4.5
            c.line(P([(x, 32 - hw), (x, 32 - hw + 6 * size)]), fill=(80, 80, 75, 255), width=1)
            c.line(P([(x, 32 + hw - 6 * size), (x, 32 + hw)]), fill=(80, 80, 75, 255), width=1)
        # hull
        c.poly(P([(32 - hl + 2, 32 - hw + 5 * size), (32 + hl - 4, 32 - hw + 5 * size), (32 + hl, 32 - hw * 0.5),
                  (32 + hl, 32 + hw * 0.5), (32 + hl - 4, 32 + hw - 5 * size), (32 - hl + 2, 32 + hw - 5 * size)]),
               fill=col + (255,), outline=dark + (255,))
        c.poly(P([(32 - hl + 4, 32 - hw * 0.45), (32 - hl * 0.45, 32 - hw * 0.45), (32 - hl * 0.45, 32 + hw * 0.45),
                  (32 - hl + 4, 32 + hw * 0.45)]), fill=shade(col, 0.8) + (255,))   # engine deck
        if vclass in ("td", "spg"):
            # casemate and gun on the hull
            rear = 32 - hl * .6 if open_top else 32 - 4
            c.poly(P([(rear, 32 - hw * 0.6), (32 + hl * 0.55, 32 - hw * 0.6), (32 + hl * 0.7, 32),
                      (32 + hl * 0.55, 32 + hw * 0.6), (rear, 32 + hw * 0.6)]),
                   fill=(shade(col, .28) if open_top else light) + (255,), outline=light + (255,) if open_top else dark + (255,))
            L = 30 if vclass == "td" else 20
            c.line(P([(32 + hl * 0.6, 32), (32 + hl * 0.6 + L * 0.6, 32)]), fill=dark + (255,), width=4 if vclass == "spg" else 3)
    elif vclass in ("halftrack", "aa_halftrack"):
        hl, hw = 25, 11
        c.shadow((32 - hl, 32 - hw + 6, 32 + hl, 32 + hw + 8), 100, 3)
        for s in (-1, 1):
            c.poly(P([(32 - hl, 32 + s * hw - 3), (32 + 2, 32 + s * hw - 3), (32 + 2, 32 + s * hw + 3), (32 - hl, 32 + s * hw + 3)]), fill=track + (255,))
            c.ellipse(rot_box(32 + hl - 6, 32 + s * hw, 5, 3, ang), fill=(30, 30, 30, 255))
        c.poly(P([(32 - hl + 1, 32 - hw), (32 + hl - 8, 32 - hw), (32 + hl, 32 - hw * 0.5), (32 + hl, 32 + hw * 0.5),
                  (32 + hl - 8, 32 + hw), (32 - hl + 1, 32 + hw)]), fill=col + (255,), outline=dark + (255,))
        c.poly(P([(32 - hl + 4, 32 - hw + 3), (32 + 4, 32 - hw + 3), (32 + 4, 32 + hw - 3), (32 - hl + 4, 32 + hw - 3)]), fill=shade(col, 0.55) + (255,))
    elif vclass in ("truck", "car", "armcar"):
        hl, hw = {"truck": (26, 11), "car": (16, 9), "armcar": (22, 11)}[vclass]
        c.shadow((32 - hl, 32 - hw + 6, 32 + hl, 32 + hw + 8), 100, 3)
        for fx in (-0.6, 0.0, 0.6) if vclass != "car" else (-0.6, 0.6):
            for s in (-1, 1):
                c.ellipse(rot_box(32 + fx * hl, 32 + s * hw, 5, 3, ang), fill=(25, 25, 25, 255))
        c.poly(P([(32 - hl, 32 - hw + 2), (32 + hl, 32 - hw + 2), (32 + hl, 32 + hw - 2), (32 - hl, 32 + hw - 2)]), fill=col + (255,), outline=dark + (255,))
        if vclass == "truck":
            c.poly(P([(32 - hl + 1, 32 - hw + 3), (32 + hl * 0.35, 32 - hw + 3), (32 + hl * 0.35, 32 + hw - 3), (32 - hl + 1, 32 + hw - 3)]),
                   fill=lighten(col, 0.15) + (255,))
            for k in range(4):
                x = 32 - hl + 4 + k * 7
                c.line(P([(x, 32 - hw + 3), (x, 32 + hw - 3)]), fill=shade(col, 0.8) + (255,))
        elif vclass == "car":
            c.poly(P([(32 + 2, 32 - hw + 3), (32 + 4, 32 - hw + 3), (32 + 4, 32 + hw - 3), (32 + 2, 32 + hw - 3)]), fill=(150, 180, 200, 255))
    elif vclass == "ambulance":
        hl, hw = 24, 11
        c.shadow((32 - hl, 32 - hw + 6, 32 + hl, 32 + hw + 8), 100, 3)
        for fx in (-0.6, 0.6):
            for s in (-1, 1):
                c.ellipse(rot_box(32 + fx * hl, 32 + s * hw, 5, 3, ang), fill=(25, 25, 25, 255))
        c.poly(P([(32 - hl, 32 - hw + 2), (32 + hl, 32 - hw + 2), (32 + hl, 32 + hw - 2), (32 - hl, 32 + hw - 2)]),
               fill=col + (255,), outline=dark + (255,))
        c.poly(P([(32 - hl + 3, 32 - 7), (32 + 6, 32 - 7), (32 + 6, 32 + 7), (32 - hl + 3, 32 + 7)]), fill=(235, 235, 230, 255))
        c.poly(P([(32 - 12, 32 - 2), (32 - 2, 32 - 2), (32 - 2, 32 + 2), (32 - 12, 32 + 2)]), fill=(200, 30, 30, 255))
        c.poly(P([(32 - 9, 32 - 5), (32 - 5, 32 - 5), (32 - 5, 32 + 5), (32 - 9, 32 + 5)]), fill=(200, 30, 30, 255))
    elif vclass == "wagon":
        # a wagon behind a pair of horses
        c.shadow((10, 24, 58, 46), 80, 3)
        horse = (110, 75, 45)
        for s in (-5, 5):
            c.ellipse(rot_box(32 + 16, 32 + s, 9, 3.5, ang), fill=horse + (255,))
            c.ellipse(rot_box(32 + 26, 32 + s, 3, 2.2, ang), fill=shade(horse, 0.8) + (255,))
        c.line(P([(32 + 6, 32), (32 + 12, 32)]), fill=(90, 70, 45, 255), width=2)
        wood = (125, 100, 65)
        c.poly(P([(32 - 22, 32 - 9), (32 + 6, 32 - 9), (32 + 6, 32 + 9), (32 - 22, 32 + 9)]), fill=wood + (255,),
               outline=shade(wood, 0.6) + (255,))
        c.poly(P([(32 - 20, 32 - 7), (32 + 4, 32 - 7), (32 + 4, 32 + 7), (32 - 20, 32 + 7)]), fill=(185, 175, 150, 255))
        for fx in (-17, 1):
            for s in (-1, 1):
                c.ellipse(rot_box(32 + fx, 32 + s * 10, 4, 1.8, ang), fill=(60, 45, 30, 255))
    elif vclass == "motorcycle":
        c.shadow((18, 28, 48, 40), 80, 2)
        c.line(P([(32 - 12, 32), (32 + 12, 32)]), fill=(40, 40, 38, 255), width=4)
        for fx in (-12, 12):
            c.ellipse(rot_box(32 + fx, 32, 4, 2.5, ang), fill=(20, 20, 20, 255))
        c.ellipse(rot_box(32 - 2, 32, 4, 3, ang), fill=col + (255,))
    elif vclass in ("lc", "amtrac"):
        hl, hw = 27, 13
        c.shadow((32 - hl, 32 - hw + 6, 32 + hl, 32 + hw + 8), 60, 4)
        c.poly(P([(32 - hl, 32 - hw), (32 + hl - 6, 32 - hw), (32 + hl, 32 - hw + 3), (32 + hl, 32 + hw - 3), (32 + hl - 6, 32 + hw),
                  (32 - hl, 32 + hw)]), fill=(115, 120, 118, 255), outline=(60, 62, 60, 255))
        c.poly(P([(32 - hl + 5, 32 - hw + 3), (32 + hl - 8, 32 - hw + 3), (32 + hl - 8, 32 + hw - 3), (32 - hl + 5, 32 + hw - 3)]), fill=(70, 72, 70, 255))
        c.line(P([(32 + hl - 3, 32 - hw + 2), (32 + hl - 3, 32 + hw - 2)]), fill=(150, 150, 145, 255), width=3)
    elif vclass in ("atgun", "fieldgun", "aagun"):
        c.shadow((12, 22, 56, 50), 80, 3)
        if vclass == "aagun":
            c.ellipse((16, 16, 48, 48), fill=col + (255,), outline=dark + (255,), width=2)
            c.line(P([(10, 32), (54, 32)]), fill=dark + (255,), width=3)
            c.line(P([(32, 10), (32, 54)]), fill=dark + (255,), width=3)
        else:
            c.line(P([(32, 32), (8, 18)]), fill=dark + (255,), width=3)
            c.line(P([(32, 32), (8, 46)]), fill=dark + (255,), width=3)
            c.ellipse(rot_box(32, 20, 4, 5, ang), fill=(30, 30, 30, 255))
            c.ellipse(rot_box(32, 44, 4, 5, ang), fill=(30, 30, 30, 255))
    if burning:
        c.speckle((255, 140, 30), 12, (1, 3))
        c.speckle((40, 30, 25), 20, (2, 4), alpha=200)
    return c.array()


def _alpha_box(img, thresh=140):
    a = np.asarray(img.split()[3])
    ys, xs = np.where(a > thresh)
    if len(xs) == 0:
        return (0, 0, img.width, img.height)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def paint_vehicle_pieces(vclass, camo, L, W, hull_facing, facing, part="hull", burning=False, open_top=False) -> dict:
    """A vehicle drawn at the size of its footprint, rotated, and cut into tile-sized pieces.

    Returns {(dx, dy): 64x64 RGBA array}, offsets from the pivot tile."""
    from .footprint import rect_center
    base = Image.fromarray(paint_vehicle(vclass, camo, 0, "hull", burning, open_top), "RGBA")
    static = vclass in ("atgun", "fieldgun", "aagun")
    tur = Image.fromarray(paint_vehicle(vclass, camo, 0, "turret", open_top=open_top), "RGBA")
    bx0, by0, bx1, by1 = _alpha_box(Image.alpha_composite(base, tur) if static else base)
    sx = (L * M - 8) / max(1, bx1 - bx0)
    sy = (W * M - 8) / max(1, by1 - by0)
    if part == "hull":
        img = base.crop((bx0, by0, bx1, by1)).resize((max(1, int(round((bx1 - bx0) * sx))),
                                                      max(1, int(round((by1 - by0) * sy)))), Image.LANCZOS)
        ang = hull_facing
    elif static:
        img = tur.crop((bx0, by0, bx1, by1)).resize((round((bx1 - bx0) * sx), round((by1 - by0) * sy)), Image.LANCZOS)
        ang = facing
    else:
        s = (sx + sy) / 2 * 0.95
        img = tur.resize((max(1, int(M * s)), max(1, int(M * s))), Image.LANCZOS)
        ang = facing
    img = img.rotate(45 * (ang % 8), resample=Image.BICUBIC, expand=True)      # facings count anticlockwise
    cx, cy = rect_center(L, W, hull_facing)
    w, h = img.size
    out = {}
    R = max(L, W) + 2
    for dx in range(-R, R + 1):
        for dy in range(-R, R + 1):
            ix0 = int(round((dx - 0.5 - cx) * M + w / 2))
            iy0 = int(round((dy - 0.5 - cy) * M + h / 2))
            if ix0 >= w or iy0 >= h or ix0 + M <= 0 or iy0 + M <= 0:
                continue
            piece = Image.new("RGBA", (M, M), (0, 0, 0, 0))
            piece.paste(img.crop((ix0, iy0, ix0 + M, iy0 + M)), (0, 0))
            arr = np.asarray(piece, np.uint8)
            if arr[..., 3].max() < 12:
                continue
            out[(dx, dy)] = arr.copy()
    return out


def rot_box(x, y, rx, ry, ang):
    (cx, cy), = rot([(x, y)], ang)
    return (cx - rx, cy - rx, cx + rx, cy + rx)


def paint_aircraft(nation: str, direction: int, shadow=False) -> np.ndarray:
    c = Canvas()
    col = CAMO.get(nation, (100, 100, 100))
    if nation in ("usa",):
        col = (120, 125, 90)
    ang = -direction * math.pi / 2
    body = [(4, 30), (54, 29), (62, 32), (54, 35), (4, 34)]
    wing = [(26, 4), (36, 4), (40, 60), (30, 60)]
    tail = [(4, 20), (12, 20), (12, 44), (4, 44)]
    fill = (0, 0, 0, 110) if shadow else col + (255,)
    for poly in (wing, tail, body):
        c.poly(rot(poly, ang), fill=fill)
    if not shadow:
        dot = {"usa": (240, 240, 240), "uk": (40, 60, 160), "ussr": (200, 30, 30), "germany": (20, 20, 20),
               "japan": (200, 30, 30), "italy": (230, 230, 230)}.get(nation, (230, 230, 230))
        for x, y in ((31, 12), (35, 52)):
            (px, py), = rot([(x, y)], ang)
            c.ellipse((px - 3, py - 3, px + 3, py + 3), fill=dot + (255,))
    return c.array()


# parked aircraft (parked.py): paint scheme -> (upper surfaces, disruptive second colour or None)
AIR_CAMO = {
    "germany": ((70, 82, 60), (52, 60, 46)), "winter_germany": ((215, 218, 222), (80, 90, 70)),
    "desert_germany": ((190, 165, 115), (120, 110, 80)), "italy": ((175, 158, 110), (95, 105, 70)),
    "desert_italy": ((190, 170, 120), (110, 115, 80)), "japan": ((95, 105, 70), (70, 80, 55)),
    "naval_japan": ((160, 165, 150), None), "ussr": ((85, 105, 60), (45, 50, 40)),
    "winter_ussr": ((215, 218, 222), None), "usa": ((95, 100, 62), None), "metal": ((185, 188, 190), None),
    "naval_usa": ((72, 88, 115), None), "desert_usa": ((175, 150, 115), None), "uk": ((100, 95, 60), (70, 85, 55)),
    "desert_uk": ((175, 145, 100), (120, 90, 60)), "naval_uk": ((110, 115, 115), (80, 90, 90)),
    "desert_australia": ((175, 145, 100), (120, 90, 60)), "desert_india": ((175, 145, 100), (120, 90, 60)),
    "france": ((110, 105, 80), (80, 90, 70)), "poland": ((105, 105, 70), None), "finland": ((85, 95, 65), (45, 50, 40)),
    "winter_finland": ((215, 218, 222), (80, 90, 70)), "hungary": ((75, 85, 60), None), "romania": ((95, 95, 65), None),
    "china": ((150, 150, 140), None), "canada": ((100, 95, 60), (70, 85, 55)), "australia": ((100, 95, 60), (70, 85, 55)),
    "newzealand": ((80, 90, 110), None), "india": ((100, 95, 60), (70, 85, 55)),
}


def _insignia(d, cx, cy, r, nation):
    """The national marking on a wing, seen from above."""
    def disc(rr, col):
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=col + (255,))
    if nation in ("uk", "canada", "australia", "newzealand", "india"):
        disc(r, (40, 55, 130))
        disc(r * 0.45, (170, 40, 40))
    elif nation == "france":
        disc(r, (40, 55, 130)); disc(r * 0.66, (235, 235, 235)); disc(r * 0.33, (190, 40, 40))
    elif nation == "usa":
        disc(r, (40, 55, 110))
        pts = []
        for k in range(10):
            a = -math.pi / 2 + k * math.pi / 5
            rr = r * (0.9 if k % 2 == 0 else 0.38)
            pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
        d.polygon(pts, fill=(235, 235, 235, 255))
    elif nation == "japan":
        disc(r, (235, 235, 235)); disc(r * 0.8, (190, 30, 30))
    elif nation in ("ussr", "china"):
        col = (200, 35, 35) if nation == "ussr" else (40, 60, 150)
        if nation == "china":
            disc(r, col); disc(r * 0.5, (235, 235, 235))
            return
        pts = []
        for k in range(10):
            a = -math.pi / 2 + k * math.pi / 5
            rr = r * (1.0 if k % 2 == 0 else 0.42)
            pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
        d.polygon(pts, fill=col + (255,))
    elif nation in ("germany", "hungary", "romania", "finland"):
        w = r * 0.42
        edge = (235, 235, 235) if nation != "romania" else (230, 200, 50)
        d.rectangle((cx - r, cy - w - 3, cx + r, cy + w + 3), fill=edge + (255,))
        d.rectangle((cx - w - 3, cy - r, cx + w + 3, cy + r), fill=edge + (255,))
        core = (25, 25, 25) if nation != "finland" else (40, 70, 150)
        d.rectangle((cx - r + 3, cy - w, cx + r - 3, cy + w), fill=core + (255,))
        d.rectangle((cx - w, cy - r + 3, cx + w, cy + r - 3), fill=core + (255,))
    elif nation == "italy":
        disc(r, (235, 235, 235)); disc(r * 0.8, (35, 35, 35))
    elif nation == "poland":
        h = r * 0.7
        for i in range(2):
            for j in range(2):
                col = (200, 35, 35) if (i + j) % 2 == 0 else (235, 235, 235)
                d.rectangle((cx - h + i * h, cy - h + j * h, cx + i * h, cy + j * h), fill=col + (255,))


def paint_parked(model: str, scheme: str, nation: str, facing: int, folded: bool) -> dict:
    """A parked aircraft drawn whole from its planform (parked.py), then cut into its tiles: {(dx, dy): 64x64}."""
    from . import parked as PK
    parts, (shown, length) = PK.planform(model, folded)
    S, L, _g = PK.grid(model, folded)
    span, _ln, engines, _f, layout = PK.DIMS.get(model, PK.DIMS["bf109"])
    W, H = S * M, L * M
    sc = M / PK.TILE_M
    top, second = AIR_CAMO.get(scheme, AIR_CAMO.get(nation, ((110, 112, 100), None)))

    def P(poly):
        return [(W / 2 + x * sc, y * sc) for x, y in poly]
    rng = random.Random(hash((model, scheme)) & 0xFFFF)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # the shadow on the ground
    sh = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(sh)
    for part, poly in parts:
        sd.polygon([(x + 10, y + 12) for x, y in P(poly)], fill=120)
    sh = sh.filter(ImageFilter.GaussianBlur(4))
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    shadow.putalpha(sh)
    img = Image.alpha_composite(img, shadow)
    body = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(body)
    order = {"ac_wing": 0, "ac_tail": 1, "ac_engine": 3, "ac_body": 2}
    for part, poly in sorted(parts, key=lambda pp: order[pp[0]]):
        col = {"ac_wing": top, "ac_tail": top, "ac_body": shade(top, 0.92), "ac_engine": shade(top, 0.7)}[part]
        d.polygon(P(poly), fill=col + (255,), outline=shade(top, 0.55) + (255,))
    # disruptive camouflage over the upper surfaces
    if second is not None:
        mask = Image.new("L", (W, H), 0)
        md = ImageDraw.Draw(mask)
        for _ in range(int(S * L * 1.2)):
            x, y = rng.uniform(0, W), rng.uniform(0, H)
            rr = rng.uniform(0.5, 1.4) * M * 0.5
            md.polygon([(x + math.cos(a) * rr * rng.uniform(0.6, 1.2), y + math.sin(a) * rr * rng.uniform(0.6, 1.2))
                        for a in np.linspace(0, math.tau, 6, endpoint=False)], fill=255)
        alpha = np.minimum(np.asarray(mask), np.asarray(body)[..., 3])
        blot = Image.new("RGBA", (W, H), second + (255,))
        blot.putalpha(Image.fromarray(alpha.astype(np.uint8), "L"))
        body = Image.alpha_composite(body, blot)
        d = ImageDraw.Draw(body)
    fw = max(1.1, min(3.0, span * 0.085)) * sc
    from .data.vehicles import AIRCRAFT
    role = AIRCRAFT[model].role if model in AIRCRAFT else "fighter"
    n0 = PK.NOSE * sc
    # canopy / glazed nose, spine highlight
    if layout in ("twin", "four") and role in ("bomber", "heavybomber", "divebomber"):
        d.ellipse((W / 2 - fw * 0.45, n0, W / 2 + fw * 0.45, n0 + length * sc * 0.13), fill=(150, 185, 205, 255))
        d.ellipse((W / 2 - fw * 0.35, length * sc * 0.16, W / 2 + fw * 0.35, length * sc * 0.26),
                  fill=(120, 160, 185, 255))
    elif engines >= 2 and layout not in ("jet", "twinboom"):
        d.ellipse((W / 2 - fw * 0.4, length * sc * 0.08, W / 2 + fw * 0.4, length * sc * 0.15),
                  fill=(120, 160, 185, 255))
    else:
        cy0 = length * sc * (0.3 if layout != "twinboom" else 0.2)
        d.ellipse((W / 2 - fw * 0.3, cy0, W / 2 + fw * 0.3, cy0 + length * sc * 0.16), fill=(125, 165, 190, 255))
    d.line([(W / 2, length * sc * 0.5), (W / 2, length * sc * 0.95)], fill=lighten(top, 0.25) + (160,), width=2)
    # propellers: a grey blur of a disc and the blades, at every engine that has one
    if layout != "jet":
        for part, poly in parts:
            if part != "ac_engine":
                continue
            xs = [x for x, _ in poly]
            ys = [y for _, y in poly]
            cx, cy = W / 2 + (min(xs) + max(xs)) / 2 * sc, min(ys) * sc
            pr = (1.5 if engines == 1 else 1.7) * sc
            d.ellipse((cx - pr, cy - pr * 0.18, cx + pr, cy + pr * 0.18), fill=(40, 40, 40, 110))
            for k in range(3):
                a = rng.uniform(0, math.pi) + k * math.pi / 1.5
                d.line([(cx, cy), (cx + math.cos(a) * pr, cy + math.sin(a) * pr * 0.2)], fill=(30, 30, 30, 255),
                       width=3)
            d.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=(60, 60, 60, 255))
    # the markings on the wings
    if not folded:
        wy = None
        for part, poly in parts:
            if part == "ac_wing":
                wy = sum(y for _, y in poly) / len(poly)
                break
        if wy is not None:
            r = min(0.9, span * 0.045) * sc
            for s_ in (-1, 1):
                _insignia(d, W / 2 + s_ * span * 0.33 * sc, wy * sc, r, nation)
    # a dark rim round it all: you can't walk through it (the wings you can duck under)
    a = np.asarray(body)[..., 3]
    solid = Image.fromarray(np.where(a > 180, 255, 0).astype(np.uint8), "L")
    ring = solid.filter(ImageFilter.MaxFilter(5)).point(lambda v: int(v * 0.8))
    edge = Image.new("RGBA", (W, H), (12, 14, 10, 255))
    edge.putalpha(ring)
    img = Image.alpha_composite(Image.alpha_composite(img, edge), body)
    if facing == 1:
        img = img.transpose(Image.ROTATE_270)
    elif facing == 2:
        img = img.transpose(Image.ROTATE_180)
    elif facing == 3:
        img = img.transpose(Image.ROTATE_90)
    out = {}
    arr = np.asarray(img, np.uint8)
    for dy in range(arr.shape[0] // M):
        for dx in range(arr.shape[1] // M):
            out[(dx, dy)] = arr[dy * M:(dy + 1) * M, dx * M:(dx + 1) * M].copy()
    return out


def paint_item(kind: str, side_color=None) -> np.ndarray:
    c = Canvas(seed=hash(kind) & 0xFFFF)
    gun = (40, 38, 36)
    wood = (125, 85, 45)
    if kind == "rifle":
        c.shadow((8, 34, 58, 44), 70, 2)
        c.line([(8, 40), (24, 36)], fill=wood + (255,), width=5)
        c.line([(24, 36), (58, 30)], fill=gun + (255,), width=3)
    elif kind == "smg":
        c.line([(16, 38), (48, 32)], fill=gun + (255,), width=4)
        c.line([(30, 36), (32, 46)], fill=gun + (255,), width=3)
    elif kind == "pistol":
        c.line([(24, 34), (40, 32)], fill=gun + (255,), width=4)
        c.line([(26, 34), (26, 42)], fill=gun + (255,), width=4)
    elif kind == "mg":
        c.line([(6, 40), (58, 30)], fill=gun + (255,), width=5)
        c.line([(46, 32), (50, 44)], fill=gun + (255,), width=2)
    elif kind == "tube":
        c.line([(8, 42), (56, 28)], fill=(80, 90, 55, 255), width=7)
    elif kind == "ammo":
        c.rect((20, 26, 44, 42), fill=(95, 100, 60, 255), outline=(50, 55, 30, 255), width=2)
        c.rect((24, 30, 34, 33), fill=(210, 200, 120, 255))
    elif kind == "grenade":
        c.ellipse((26, 28, 38, 42), fill=(80, 90, 60, 255), outline=(40, 45, 30, 255))
        c.rect((30, 24, 34, 28), fill=(150, 150, 150, 255))
    elif kind == "live":
        c.ellipse((18, 20, 46, 50), fill=(255, 60, 30, 110))
        c.ellipse((26, 28, 38, 42), fill=(80, 90, 60, 255), outline=(255, 220, 80, 255), width=2)
    elif kind == "medical":
        c.rect((22, 26, 42, 42), fill=(235, 235, 230, 255), outline=(150, 150, 150, 255))
        c.line([(32, 28), (32, 40)], fill=(200, 20, 20, 255), width=3)
        c.line([(26, 34), (38, 34)], fill=(200, 20, 20, 255), width=3)
    elif kind == "tool":
        c.rect((22, 28, 42, 40), fill=(120, 110, 80, 255), outline=(70, 60, 40, 255), width=2)
    elif kind == "helmet":
        c.ellipse((20, 22, 44, 46), fill=(90, 100, 70, 255), outline=(50, 55, 40, 255), width=2)
    elif kind == "crate":
        c.rect((14, 18, 50, 46), fill=(120, 110, 60, 255), outline=(60, 55, 30, 255), width=3)
        c.line([(14, 18), (50, 46)], fill=(80, 70, 40, 255), width=2)
    elif kind == "corpse":
        col = side_color or (110, 105, 80)
        c.ellipse((10, 26, 56, 56), fill=(120, 0, 0, 150))
        c.rect((14, 32, 44, 46), fill=shade(col, 0.8) + (255,))
        c.ellipse((40, 31, 54, 45), fill=shade(col, 0.7) + (255,))
        c.ellipse((8, 32, 18, 40), fill=shade(col, 0.6) + (255,))
        c.ellipse((8, 39, 18, 47), fill=shade(col, 0.6) + (255,))
        return c.array()
    return _enlarge(c.array(), (10, 10, 54, 54))


def paint_effect(kind: str, frame: int = 0) -> np.ndarray:
    c = Canvas(seed=hash((kind, frame)) & 0xFFFF)
    r = c.rng
    if kind == "rain":
        slant = -8 if frame else 8
        for x, y in ((18, 10), (44, 30)):
            c.line([(x, y), (x + slant, y + 22)], fill=(190, 216, 235, 220), width=2)
    elif kind == "snow":
        for x, y in ((18, 16), (42, 38), (28, 52)):
            c.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(245, 248, 255, 210))
    elif kind == "dust":
        c.line([(8, 30), (54, 23)], fill=(210, 180, 125, 160), width=3)
        c.line([(24, 45), (59, 40)], fill=(220, 194, 142, 130), width=2)
    elif kind == "explosion":
        rad = 10 + frame * 7
        cols = [(255, 250, 200), (255, 200, 60), (240, 110, 30), (90, 80, 70)]
        for i, col in enumerate(cols[frame:]):
            rr = max(4, rad - i * 6)
            for _ in range(5):
                x, y = 32 + r.uniform(-6, 6), 32 + r.uniform(-6, 6)
                c.ellipse((x - rr, y - rr, x + rr, y + rr), fill=col + (220 - frame * 30,))
    elif kind == "flash":
        for k in range(8):
            a = k / 8 * math.tau
            c.line([(32, 32), (32 + math.cos(a) * 22, 32 + math.sin(a) * 22)], fill=(255, 240, 160, 220), width=3)
        c.ellipse((24, 24, 40, 40), fill=(255, 255, 220, 255))
    elif kind == "tracer":
        c.ellipse((27, 27, 37, 37), fill=(255, 230, 120, 120))
        c.ellipse((29, 29, 35, 35), fill=(255, 255, 210, 255))
    elif kind == "tracer_red":
        c.ellipse((27, 27, 37, 37), fill=(255, 90, 60, 120))
        c.ellipse((29, 29, 35, 35), fill=(255, 200, 180, 255))
    elif kind == "rocket":
        c.ellipse((22, 22, 42, 42), fill=(255, 170, 60, 150))
        c.ellipse((27, 27, 37, 37), fill=(255, 250, 220, 255))
    elif kind == "splash":
        for k in range(10):
            a = r.uniform(0, math.tau)
            L = r.uniform(8, 22)
            c.line([(32, 32), (32 + math.cos(a) * L, 32 + math.sin(a) * L)], fill=(230, 240, 255, 230), width=3)
    elif kind == "fire":
        for i in range(9):
            x = r.uniform(10, 54)
            h = r.uniform(18, 40)
            base = r.uniform(40, 58)
            col = [(255, 80, 20), (255, 150, 30), (255, 220, 90)][i % 3]
            c.poly([(x - 7, base), (x + 7, base), (x + r.uniform(-3, 3), base - h)], fill=col + (230,))
    elif kind == "smoke":
        for i in range(7):
            x, y = r.uniform(12, 52), r.uniform(12, 52)
            rr = r.uniform(12, 20)
            g = int(r.uniform(140, 190))
            c.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(g, g, g - 5, 150))
        c.img = c.img.filter(ImageFilter.GaussianBlur(3))
    elif kind == "blood":
        for _ in range(6):
            x, y = r.uniform(16, 48), r.uniform(16, 48)
            rr = r.uniform(4, 10)
            c.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(120, 0, 0, 200))
    elif kind == "scorch":
        c.ellipse((6, 6, 58, 58), fill=(20, 18, 15, 120))
        c.img = c.img.filter(ImageFilter.GaussianBlur(5))
    elif kind == "flame":
        for i in range(12):
            x, y = r.uniform(4, 60), r.uniform(20, 44)
            rr = r.uniform(6, 12)
            col = [(255, 90, 20), (255, 170, 40), (255, 235, 120)][i % 3]
            c.ellipse((x - rr, y - rr, x + rr, y + rr), fill=col + (200,))
    return c.array()


# ====================================================================== the bank

def vehicle_class(vt) -> str:
    v = vt.vtype
    if vt.id in ("horse_wagon", "panje_wagon"):
        return "wagon"
    if vt.id == "ambulance":
        return "ambulance"
    if vt.id == "motorcycle":
        return "motorcycle"
    if v == "td" and vt.open_top and vt.turret:
        return "open_td"
    if v == "halftrack" and vt.aa:
        return "aa_halftrack"
    if v == "tank" and vt.armor[0] >= 100:
        return "heavy"
    return {"tank": "tank", "ltank": "ltank", "tankette": "tankette", "td": "td", "spg": "spg",
            "halftrack": "halftrack", "truck": "truck", "car": "car", "armcar": "armcar", "lc": "lc",
            "amtrac": "amtrac", "atgun": "atgun", "aagun": "aagun", "fieldgun": "fieldgun"}.get(v, "tank")


def vehicle_camo(nation: str, year: float, climate: str) -> str:
    if climate == "winter":
        return "winter"
    if climate == "desert" and nation in ("uk", "australia", "newzealand", "india", "germany", "italy", "usa"):
        return "desert"
    if nation == "germany" and year < 1943:
        return "germany_early"
    return nation if nation in CAMO else "usa"


ROLE_STYLE = {"lmg_gunner": "lmg_gunner", "hmg_gunner": "hmg_gunner", "at_soldier": "at_soldier",
              "medic": "medic", "officer": "officer", "smg_gunner": "smg_gunner", "squad_leader": "squad_leader",
              "radioman": "radioman", "flamethrower": "flamethrower", "tank_crew": "tank_crew",
              "mortarman": "mortarman"}


class SpriteBank:
    """Paints sprites at master resolution and serves tcod tilesets of any size."""

    def __init__(self):
        self.master: dict[int, np.ndarray] = {}
        self.keys: dict = {}
        self.next_cp = DYN_BASE
        self.size = None
        self.tileset = None
        for tid in range(T.NUM):
            for v in range(VARIANTS):
                self.master[TERRAIN_BASE + tid * VARIANTS + v] = paint_terrain(tid, v)

    def _scale(self, arr):
        if self.size == M:
            return arr
        img = Image.fromarray(arr, "RGBA").resize((self.size, self.size), Image.LANCZOS)
        return np.asarray(img, np.uint8)

    def build(self, size: int):
        self.size = size
        ts = tcod.tileset.Tileset(size, size)
        for cp, arr in self.master.items():
            ts[cp] = self._scale(arr)
        self.tileset = ts
        return ts

    def _get(self, key, painter):
        cp = self.keys.get(key)
        if cp is None:
            cp = self.next_cp
            self.next_cp += 1
            self.keys[key] = cp
            arr = painter()
            self.master[cp] = arr
            if self.tileset is not None:
                self.tileset[cp] = self._scale(arr)
        return cp

    # ---- public lookups
    def terrain(self, tid, var):
        return TERRAIN_BASE + int(tid) * VARIANTS + int(var) % VARIANTS

    def figure(self, key):
        """A soldier drawn from his kit (see figures.py)."""
        from .figures import paint_figure
        return self._get(("fig",) + key, lambda: paint_figure(key))

    def soldier(self, nation, role, stance, state="ok", winter=False):
        role = ROLE_STYLE.get(role, "rifleman")
        return self._get(("soldier", nation, role, stance, state, winter),
                         lambda: paint_soldier(nation, role, stance, state, winter))

    def ring(self, kind="ring"):
        return self._get(("ring", kind), lambda: paint_ring(kind))

    def vehicle_pieces(self, vclass, camo, L, W, hull_facing, facing, part="hull", burning=False, open_top=False):
        """[(dx, dy, codepoint)] for a multi-tile vehicle (hull or turret)."""
        key = ("vbig", vclass, camo, L, W, hull_facing % 8, facing % 8 if part != "hull" else 0, part, burning, open_top)
        got = self.keys.get(key)
        if got is None:
            pieces = paint_vehicle_pieces(vclass, camo, L, W, hull_facing, facing, part, burning, open_top)
            got = []
            for (dx, dy), arr in sorted(pieces.items()):
                cp = self._get(key + (dx, dy), lambda a=arr: a)
                got.append((dx, dy, cp))
            self.keys[key] = got
        return got

    def vehicle_crew_pieces(self, figures):
        """All visible crew/passengers composited together, including people sharing a tile."""
        key = ("vehicle_crew", figures)
        got = self.keys.get(key)
        if got is None:
            from .vehicle_figures import paint_pieces
            got = []
            for (dx, dy), arr in sorted(paint_pieces(figures).items()):
                cp = self._get(key + (dx, dy), lambda a=arr: a)
                got.append((dx, dy, cp))
            self.keys[key] = got
        return got

    def parked_pieces(self, model, scheme, nation, facing, folded):
        """[(dx, dy, codepoint)] for a parked aircraft, drawn whole across its tiles."""
        key = ("parked", model, scheme, nation, facing % 4, bool(folded))
        got = self.keys.get(key)
        if got is None:
            got = []
            for (dx, dy), arr in sorted(paint_parked(model, scheme, nation, facing % 4, folded).items()):
                got.append((dx, dy, self._get(key + (dx, dy), lambda a=arr: a)))
            self.keys[key] = got
        return got

    def vehicle(self, vclass, camo, facing, part="hull", burning=False):
        return self._get(("veh", vclass, camo, facing % 8, part, burning),
                         lambda: paint_vehicle(vclass, camo, facing % 8, part, burning))

    def aircraft(self, nation, direction, shadow=False):
        return self._get(("air", nation, direction % 4, shadow), lambda: paint_aircraft(nation, direction % 4, shadow))

    def item(self, kind, side_color=None):
        return self._get(("item", kind, side_color), lambda: paint_item(kind, side_color))

    def effect(self, kind, frame=0):
        return self._get(("fx", kind, frame), lambda: paint_effect(kind, frame))
