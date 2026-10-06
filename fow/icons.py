"""Pictures in the interface: the kit as it looks, not as a word for it.

Any screen can ask for a picture in a rectangle of text cells - `pic(x, y, w, h, key)` - and the renderer
(gfx.present) paints it at exactly the pixel size that rectangle has on screen, caches it, and draws it over
the text.  The text drawn underneath stays as it is: it's what shows without a renderer (the tests, a
terminal), and what a screen reader or a search finds.

Pictures are painted, not drawn by hand: each painter works in its own box of unit coordinates, at three
times the size it's shown, and is scaled down, so a rifle is a rifle at twenty pixels or two hundred.  Keys
say what to paint, and some carry state after a bar: "watch|06:15", "rounds|8|5|brass".

Two layers: "ui" pictures go over the interface console (the panel, the full-screen pages), "over" ones
over the overlay console (the kit screen, popups' neighbours) - see gfx.present.
"""
from __future__ import annotations

import math

import numpy as np

ENABLED = False                 # set when there's a renderer to draw them (gfx.Graphics)
SHOW = True                     # ... and the player wants them (Options: Pictures in the interface)
FRAME = {"under": [], "ui": [], "over": []}   # this frame's pictures: (x, y, w, h, key)
SS = 3                          # supersampling
_FONTS: dict = {}


def pic(x, y, w, h, key, layer="ui"):
    """Ask for a picture over text cells (x, y, w, h) this frame."""
    if not ENABLED or w <= 0 or h <= 0 or not key:
        return
    lst = FRAME[layer]
    if len(lst) < 4000:
        lst.append((x, y, w, h, key))


def clear():
    for v in FRAME.values():
        v.clear()


def under(con, x, y, w, h, key):
    """A picture beneath the text in cells (x, y, w, h): the cells' own background made see-through."""
    if not ENABLED:
        return
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(con.width, x + w), min(con.height, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    a = con.rgba["bg"][x0:x1, y0:y1, 3]
    a[:] = 0
    a[con.rgba["ch"][x0:x1, y0:y1] != 32] = 165      # (a dark label behind each letter: the ink stays legible)
    pic(x, y, w, h, key, "under")


def erase(x, y, w, h, layers=("ui", "over")):
    """Something has been drawn over (x, y, w, h) - a popup, a list: the pictures there go."""
    for ly in layers:
        FRAME[ly][:] = [p for p in FRAME[ly] if p[0] >= x + w or p[0] + p[2] <= x or p[1] >= y + h or p[1] + p[3] <= y]


def on() -> bool:
    return ENABLED and SHOW


def oriented(key, w, h) -> str:
    """The key turned a quarter if the picture is long one way and its rectangle the other (a rifle stood
    on end in a pack)."""
    base, bar, arg = key.partition("|")
    ent = PAINTERS.get(base) or PAINTERS.get(base.split(":")[0] + ":*")
    if ent is None or callable(ent[0]):
        return key
    box = (w * 0.55) / max(0.1, h)                   # (a text cell is about 0.55 as wide as it is tall)
    if (ent[0] > 1.3 and box < 0.8) or (ent[0] < 0.75 and box > 1.4):
        return base + "@r" + bar + arg
    return key


def badge(x, y, text, layer="over", tone="dim"):
    """A little label drawn over a picture: rounds left, how many."""
    if text:
        pic(x, y, len(text), 1, f"badge:{tone}|{text}", layer)


# ============================================================================ the canvas
class Canvas:
    """A painter's box: unit coordinates (0..aspect across, 0..1 down) on a supersampled RGBA image."""

    def __init__(self, pw, ph, aspect, margin=0.92):
        from PIL import Image, ImageDraw
        self.W, self.H = pw * SS, ph * SS
        self.img = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self._sheet = None
        # fit the painter's box (aspect : 1) into the image, centred, with a little margin (none for the
        # pictures that are the whole of their rectangle: a map square, the sky)
        box_h = min(self.H, self.W / aspect) * margin
        box_w = box_h * aspect
        self.s = box_h
        self.ox = (self.W - box_w) / 2
        self.oy = (self.H - box_h) / 2

    def p(self, x, y):
        return (self.ox + x * self.s, self.oy + y * self.s)

    def _pen(self, *cols):
        """The drawing surface for these colours: the image itself, or - for translucent ink, which PIL would
        paint over what's there instead of blending - a clear sheet that's laid over it afterwards."""
        if any(c is not None and len(c) > 3 and c[3] < 255 for c in cols):
            from PIL import Image, ImageDraw
            self._sheet = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
            return ImageDraw.Draw(self._sheet)
        self._sheet = None
        return self.d

    def _lay(self):
        if self._sheet is not None:
            self.img.alpha_composite(self._sheet)
            self._sheet = None

    def poly(self, pts, fill, outline=None, width=0.0):
        d = self._pen(fill, outline)
        d.polygon([self.p(x, y) for x, y in pts], fill=fill, outline=outline,
                  width=max(1, int(width * self.s)) if outline else 1)
        self._lay()

    def rect(self, x0, y0, x1, y1, fill, outline=None, width=0.0, r=0.0):
        a, b = self.p(x0, y0), self.p(x1, y1)
        d = self._pen(fill, outline)
        if r > 0:
            d.rounded_rectangle([a, b], radius=r * self.s, fill=fill, outline=outline,
                                width=max(1, int(width * self.s)) if outline else 1)
        else:
            d.rectangle([a, b], fill=fill, outline=outline, width=max(1, int(width * self.s)) if outline else 1)
        self._lay()

    def ell(self, x0, y0, x1, y1, fill, outline=None, width=0.0):
        d = self._pen(fill, outline)
        d.ellipse([self.p(x0, y0), self.p(x1, y1)], fill=fill, outline=outline,
                  width=max(1, int(width * self.s)) if outline else 1)
        self._lay()

    def line(self, pts, fill, width):
        d = self._pen(fill)
        d.line([self.p(x, y) for x, y in pts], fill=fill, width=max(1, int(width * self.s)))
        self._lay()

    def arc(self, x0, y0, x1, y1, a0, a1, fill, width):
        d = self._pen(fill)
        d.arc([self.p(x0, y0), self.p(x1, y1)], a0, a1, fill=fill, width=max(1, int(width * self.s)))
        self._lay()

    def text(self, x, y, s, fill, size):
        px = max(6, int(size * self.s))
        f = _FONTS.get(px)
        if f is None:
            from PIL import ImageFont
            from .fonts import TTF_BOLD
            try:
                f = ImageFont.truetype(TTF_BOLD, px)
            except Exception:
                f = ImageFont.load_default()
            _FONTS[px] = f
        self.d.text(self.p(x, y), s, fill=fill, font=f, anchor="mm")

    @property
    def width(self):
        """The box's width in its own units (its aspect)."""
        return (self.W - 2 * self.ox) / self.s

    def out(self, pw, ph):
        from PIL import Image
        im = self.img.resize((pw, ph), Image.LANCZOS)
        return np.asarray(im, np.uint8)


# ============================================================================ colours
WOOD = (122, 78, 42, 255)
WOOD_D = (86, 52, 28, 255)
STEEL = (58, 60, 62, 255)
STEEL_L = (96, 100, 104, 255)
BLUED = (40, 42, 48, 255)
OD = (92, 96, 60, 255)            # olive drab
OD_D = (66, 70, 42, 255)
FG = (98, 100, 86, 255)           # feldgrau
KHAKI = (150, 130, 88, 255)
BRASS = (196, 160, 72, 255)
BRASS_D = (140, 110, 46, 255)
COPPER = (170, 96, 60, 255)
PAPER = (222, 212, 184, 255)
PAPER_D = (170, 158, 128, 255)
INK = (60, 54, 44, 255)
WHITE = (236, 234, 226, 255)
RED = (176, 40, 34, 255)
BLACK = (24, 24, 24, 255)
TIN = (150, 150, 140, 255)
CLOTH = (200, 196, 180, 255)


PAINTERS: dict = {}
FULL = {"terrain", "sky", "rounds", "badge:dim", "badge:warn"}      # (edge to edge: no margin)


def painter(key, aspect):
    def deco(fn):
        PAINTERS[key] = (aspect, fn)
        return fn
    return deco


@painter("award", 0.8)
def _award(c, arg):
    from .awards import paint
    paint(c, arg)


def paint(key: str, pw: int, ph: int) -> np.ndarray | None:
    """RGBA (ph, pw, 4) for a key, or None if nothing paints it."""
    if pw < 2 or ph < 2:
        return None
    if key.startswith("~"):
        a = paint(key[1:], pw, ph)                  # a ghost: the place something goes, faintly
        if a is None:
            return None
        a = a.copy()
        g = a[..., :3].mean(axis=2, keepdims=True)
        a[..., :3] = (g * 0.6 + 60).astype(np.uint8)
        a[..., 3] = (a[..., 3] * 0.22).astype(np.uint8)
        return a
    base, _, arg = key.partition("|")
    rot = base.endswith("@r")
    if rot:
        base = base[:-2]
        pw, ph = ph, pw
    ent = PAINTERS.get(base)
    if ent is None:
        fam = base.split(":")[0] + ":*"
        ent = PAINTERS.get(fam)
        if ent is None:
            return None
    aspect, fn = ent
    if callable(aspect):
        aspect = aspect(arg, pw, ph)
    c = Canvas(pw, ph, aspect, 1.0 if base in FULL else 0.92)
    fn(c, arg)
    a = c.out(pw, ph)
    if rot:
        a = np.ascontiguousarray(np.rot90(a, 1))
    return a


# ============================================================================ guns
def _stock(c, x0, x1, y0, y1, col=WOOD):
    """A rifle butt: the wrist narrow, the heel deep."""
    c.poly([(x0, y0 + 0.05), (x1, y0 + 0.12), (x1, y1 - 0.05), (x0 + 0.05, y1), (x0, y1)], col)


@painter("gun:rifle", 7.0)
def _rifle(c, arg, scope=False, bayonet=False):
    c.poly([(0.0, 0.42), (2.2, 0.46), (2.4, 0.58), (2.2, 0.72), (0.15, 0.92), (0.0, 0.92)], WOOD)   # butt
    c.poly([(2.2, 0.46), (5.6, 0.44), (5.6, 0.58), (2.4, 0.62)], WOOD_D)                          # fore-end
    c.rect(2.1, 0.36, 7.0, 0.44, STEEL)                                                            # barrel
    c.rect(2.2, 0.32, 3.2, 0.46, STEEL_L)                                                          # receiver
    c.line([(2.9, 0.34), (3.15, 0.18)], STEEL, 0.05)                                               # bolt handle
    c.ell(3.05, 0.13, 3.25, 0.27, STEEL)
    c.rect(2.5, 0.58, 2.62, 0.72, STEEL)                                                           # trigger guard
    c.rect(6.75, 0.27, 6.82, 0.36, STEEL)                                                          # front sight
    if scope:
        c.rect(2.35, 0.08, 4.1, 0.24, BLUED, r=0.06)
        c.rect(2.2, 0.06, 2.45, 0.26, BLUED)
        c.rect(4.0, 0.04, 4.3, 0.28, BLUED)


@painter("gun:sniper", 7.0)
def _sniper(c, arg):
    _rifle(c, arg, scope=True)


@painter("gun:carbine", 5.0)
def _carbine(c, arg):
    c.poly([(0.0, 0.42), (1.7, 0.46), (1.9, 0.58), (1.7, 0.7), (0.1, 0.9), (0.0, 0.9)], WOOD)
    c.poly([(1.7, 0.46), (3.8, 0.44), (3.8, 0.58), (1.9, 0.6)], WOOD_D)
    c.rect(1.6, 0.36, 5.0, 0.44, STEEL)
    c.rect(1.7, 0.32, 2.5, 0.46, STEEL_L)
    c.rect(2.1, 0.58, 2.35, 0.82, STEEL)                                                           # short magazine
    c.rect(4.8, 0.28, 4.86, 0.36, STEEL)


@painter("gun:smg", 4.4)
def _smg(c, arg):
    drum = arg == "drum"
    wood = arg in ("wood", "drum")
    if wood:
        c.poly([(0.0, 0.4), (1.3, 0.44), (1.45, 0.62), (0.1, 0.86), (0.0, 0.86)], WOOD)
    else:
        c.line([(0.05, 0.42), (0.05, 0.8), (1.2, 0.56)], STEEL, 0.07)                              # wire stock
        c.line([(0.05, 0.42), (1.2, 0.46)], STEEL, 0.07)
    c.rect(1.2, 0.34, 3.2, 0.58, STEEL)                                                            # receiver
    c.rect(3.2, 0.4, 4.4, 0.48, STEEL_L)                                                           # barrel
    if arg == "jacket":
        for k in range(5):
            c.ell(3.3 + k * 0.2, 0.37, 3.42 + k * 0.2, 0.5, BLACK)
    c.rect(1.9, 0.58, 2.05, 0.78, STEEL)                                                           # grip
    if drum:
        c.ell(1.95, 0.52, 2.95, 1.0, BLUED, outline=STEEL_L, width=0.03)
    else:
        c.rect(2.25, 0.58, 2.45, 1.0, BLUED)                                                       # stick magazine


@painter("gun:assault", 5.2)
def _assault(c, arg):
    c.poly([(0.0, 0.36), (1.3, 0.4), (1.3, 0.62), (0.0, 0.86)], WOOD)
    c.rect(1.25, 0.32, 3.5, 0.56, STEEL)
    c.rect(3.5, 0.38, 5.2, 0.46, STEEL_L)
    c.poly([(2.2, 0.56), (2.6, 0.56), (2.75, 1.0), (2.4, 1.0)], BLUED)                             # curved magazine
    c.rect(1.8, 0.56, 1.95, 0.78, STEEL)


@painter("gun:shotgun", 6.0)
def _shotgun(c, arg):
    c.poly([(0.0, 0.42), (1.8, 0.46), (2.0, 0.6), (0.1, 0.9), (0.0, 0.9)], WOOD)
    c.rect(1.9, 0.36, 6.0, 0.46, STEEL)
    c.rect(3.0, 0.48, 4.4, 0.6, WOOD_D)
    c.rect(1.9, 0.48, 6.0, 0.54, STEEL_L)


@painter("gun:pistol", 1.6)
def _pistol(c, arg):
    revolver = arg == "revolver"
    c.rect(0.25, 0.18, 1.6, 0.4, BLUED)                                                            # slide
    if revolver:
        c.ell(0.45, 0.2, 0.85, 0.52, STEEL)
        c.rect(0.8, 0.24, 1.6, 0.34, BLUED)
    c.poly([(0.3, 0.38), (0.72, 0.38), (0.62, 0.95), (0.18, 0.95)], WOOD_D)                        # grip
    c.arc(0.62, 0.34, 0.95, 0.66, 0, 180, BLUED, 0.05)                                             # guard


@painter("gun:lmg", 6.4)
def _lmg(c, arg):
    c.poly([(0.0, 0.34), (1.4, 0.38), (1.4, 0.62), (0.0, 0.82)], WOOD if arg != "steel" else STEEL)
    c.rect(1.35, 0.3, 3.6, 0.56, STEEL)
    c.rect(3.6, 0.36, 6.4, 0.46, STEEL_L)
    if arg == "pan":
        c.ell(2.0, 0.08, 3.1, 0.34, BLUED, outline=STEEL_L, width=0.03)                             # pan magazine
    elif arg == "top":
        c.poly([(2.2, 0.3), (2.6, 0.3), (2.8, 0.0), (2.4, 0.0)], BLUED)                            # Bren: from the top
    else:
        c.rect(2.1, 0.56, 2.4, 0.9, BLUED)
    c.line([(4.8, 0.46), (4.4, 0.98)], STEEL, 0.05)                                                # bipod
    c.line([(4.8, 0.46), (5.2, 0.98)], STEEL, 0.05)
    c.rect(1.8, 0.56, 1.95, 0.78, STEEL)


@painter("gun:hmg", 4.2)
def _hmg(c, arg):
    water = arg == "water"
    c.rect(0.2, 0.18, 1.4, 0.44, STEEL)
    if water:
        c.rect(1.4, 0.16, 3.4, 0.46, OD, r=0.04)                                                   # water jacket
        c.rect(3.4, 0.26, 4.2, 0.34, STEEL_L)
    else:
        c.rect(1.4, 0.24, 4.2, 0.34, STEEL_L)
        for k in range(6):
            c.ell(1.6 + k * 0.25, 0.22, 1.72 + k * 0.25, 0.36, BLACK)
    c.line([(1.3, 0.44), (0.4, 1.0)], STEEL, 0.06)                                                 # tripod
    c.line([(1.3, 0.44), (2.3, 1.0)], STEEL, 0.06)
    c.line([(1.3, 0.44), (1.35, 1.0)], STEEL, 0.06)
    c.rect(0.5, 0.44, 0.9, 0.64, OD_D)                                                             # ammunition box


@painter("gun:mortar", 1.8)
def _mortar(c, arg):
    c.poly([(0.55, 0.05), (0.72, 0.02), (1.25, 0.86), (1.08, 0.92)], STEEL)                        # tube
    c.line([(0.9, 0.45), (0.45, 0.95)], STEEL_L, 0.05)                                             # bipod
    c.line([(0.9, 0.45), (0.7, 0.95)], STEEL_L, 0.05)
    c.ell(0.9, 0.84, 1.6, 1.0, STEEL)                                                              # baseplate


@painter("gun:at_rifle", 8.0)
def _atrifle(c, arg):
    c.poly([(0.0, 0.4), (1.6, 0.44), (1.6, 0.66), (0.0, 0.86)], WOOD_D)
    c.rect(1.5, 0.34, 3.0, 0.58, STEEL)
    c.rect(3.0, 0.4, 7.6, 0.5, STEEL_L)
    c.rect(7.4, 0.34, 8.0, 0.56, STEEL)                                                            # muzzle brake
    c.line([(5.4, 0.5), (5.0, 0.98)], STEEL, 0.06)
    c.line([(5.4, 0.5), (5.8, 0.98)], STEEL, 0.06)


@painter("gun:at_launcher", 6.0)
def _bazooka(c, arg):
    c.rect(0.0, 0.3, 6.0, 0.56, OD, r=0.1)
    c.rect(0.0, 0.26, 0.4, 0.6, STEEL)
    c.rect(2.2, 0.56, 2.38, 0.86, WOOD_D)
    c.rect(3.2, 0.56, 3.36, 0.8, WOOD_D)
    if arg == "shield":
        c.rect(3.8, 0.02, 4.6, 0.9, FG)                                                            # Panzerschreck


@painter("gun:at_disposable", 4.4)
def _faust(c, arg):
    c.rect(0.0, 0.42, 3.2, 0.56, (110, 110, 70, 255))
    c.poly([(3.1, 0.49), (3.5, 0.2), (4.2, 0.26), (4.4, 0.49), (4.2, 0.72), (3.5, 0.78)], (60, 64, 50, 255))
    c.rect(1.6, 0.3, 1.7, 0.42, BLACK)


@painter("gun:flamer", 2.6)
def _flamer(c, arg):
    c.rect(0.1, 0.08, 0.6, 0.96, OD, r=0.2)
    c.rect(0.7, 0.08, 1.2, 0.96, OD, r=0.2)
    c.line([(1.2, 0.6), (1.6, 0.8), (2.5, 0.5)], BLACK, 0.06)
    c.rect(1.7, 0.42, 2.6, 0.52, STEEL)


def gun_key(t) -> str:
    """Which silhouette a gun gets (and which variant of it)."""
    cat = t.cat
    i = t.id
    if cat == "smg":
        if "ppsh" in i or "ppd" in i or ("thompson" in i and "drum" in i) or t.mag >= 70:
            return "gun:smg|drum"
        if "thompson" in i or "suomi" in i or "beretta" in i or "type100" in i:
            return "gun:smg|wood"
        if "pps" in i:
            return "gun:smg|steel"
        if "sten" in i or "mp40" in i or "mp38" in i or "m3" in i or "owen" in i:
            return "gun:smg|steel"
        return "gun:smg|wood"
    if cat == "pistol":
        return "gun:pistol|revolver" if any(k in i for k in ("revolver", "webley", "enfield_no2", "nagant",
                                                              "m1917", "type26")) else "gun:pistol"
    if cat == "lmg":
        if "dp" in i or "lewis" in i:
            return "gun:lmg|pan"
        if "bren" in i or "zb" in i or "type96" in i or "type99" in i:
            return "gun:lmg|top"
        if "mg34" in i or "mg42" in i:
            return "gun:lmg|steel"
        return "gun:lmg"
    if cat == "hmg":
        return "gun:hmg|water" if any(k in i for k in ("vickers", "maxim", "m1917", "type92", "breda")) else "gun:hmg"
    if cat == "at_launcher":
        return "gun:at_launcher|shield" if "schreck" in i or "rpzb" in i else "gun:at_launcher"
    return "gun:" + cat


# ============================================================================ ammunition
@painter("mag:box", 0.42)
def _mag(c, arg):
    curved = arg == "curved"
    if curved:
        c.poly([(0.06, 0.05), (0.34, 0.05), (0.42, 0.95), (0.14, 0.95)], BLUED)
    else:
        c.rect(0.06, 0.05, 0.36, 0.95, BLUED, r=0.02)
    c.rect(0.1, 0.02, 0.3, 0.08, BRASS)                                                            # top round
    c.line([(0.2, 0.2), (0.2, 0.8)], STEEL_L, 0.02)


@painter("mag:drum", 1.0)
def _drum(c, arg):
    c.ell(0.05, 0.05, 0.95, 0.95, BLUED, outline=STEEL_L, width=0.05)
    c.ell(0.38, 0.38, 0.62, 0.62, STEEL_L)
    c.rect(0.44, 0.0, 0.56, 0.12, STEEL)


@painter("mag:pan", 1.6)
def _pan(c, arg):
    c.ell(0.05, 0.25, 1.55, 0.8, BLUED, outline=STEEL_L, width=0.04)
    c.ell(0.65, 0.42, 0.95, 0.62, STEEL_L)


@painter("mag:belt", 2.4)
def _belt(c, arg):
    for k in range(9):
        x = 0.05 + k * 0.26
        c.rect(x, 0.2, x + 0.14, 0.8, BRASS)
        c.rect(x, 0.2, x + 0.14, 0.34, COPPER)
    c.rect(0.0, 0.46, 2.4, 0.56, OD_D)


@painter("mag:box_ammo", 1.3)
def _ammobox(c, arg):
    c.rect(0.05, 0.2, 1.25, 0.95, OD_D, r=0.04)
    c.rect(0.05, 0.2, 1.25, 0.36, OD)
    c.rect(0.55, 0.08, 0.75, 0.22, STEEL)


@painter("clip:*", 1.0)
def _clip(c, arg):
    n = int(arg) if arg.isdigit() else 5
    n = max(3, min(10, n))
    w = 0.9 / n
    for k in range(n):
        x = 0.05 + k * w
        c.rect(x + w * 0.1, 0.12, x + w * 0.9, 0.82, BRASS)
        c.poly([(x + w * 0.1, 0.12), (x + w * 0.5, 0.0), (x + w * 0.9, 0.12)], COPPER)
    c.rect(0.02, 0.78, 0.98, 0.92, STEEL)


@painter("ammo:*", 1.2)
def _loose(c, arg):
    shell = arg == "shell"
    if shell:
        c.rect(0.35, 0.2, 0.85, 0.95, BRASS)
        c.poly([(0.35, 0.2), (0.6, 0.0), (0.85, 0.2)], OD)
        return
    c.rect(0.05, 0.3, 1.15, 0.95, (130, 110, 70, 255), r=0.04)                                     # a carton
    for k in range(5):
        x = 0.12 + k * 0.2
        c.rect(x, 0.05, x + 0.12, 0.36, BRASS)
        c.poly([(x, 0.05), (x + 0.06, -0.02), (x + 0.12, 0.05)], COPPER)


def mag_key(t) -> str:
    i = t.id
    if i.startswith("clip") or i.startswith("strip"):
        return f"clip:x|{t.mag}"                  # (an en-bloc clip is a magazine to the game, brass to the eye)
    if "belt" in i:
        return "mag:belt"
    if t.mag >= 70 or "drum" in i:
        return "mag:drum"
    if "pan" in i or "dp" in i or "lewis" in i:
        return "mag:pan"
    if "box" in i and t.mag >= 50:
        return "mag:box_ammo"
    if "stg" in i or "bren" in i or "ak" in i or "bar" in i:
        return "mag:box|curved" if "stg" in i or "bren" in i else "mag:box"
    return "mag:box"


# ============================================================================ grenades and explosives
@painter("grenade:frag", 0.7)
def _frag(c, arg):
    c.ell(0.05, 0.25, 0.65, 0.98, OD)
    for k in range(3):
        c.line([(0.05, 0.45 + k * 0.17), (0.65, 0.45 + k * 0.17)], OD_D, 0.025)
    c.line([(0.35, 0.25), (0.35, 0.98)], OD_D, 0.025)
    c.rect(0.25, 0.1, 0.45, 0.28, STEEL)
    c.line([(0.45, 0.14), (0.62, 0.55)], STEEL_L, 0.04)                                            # the spoon
    c.ell(0.02, 0.02, 0.2, 0.2, None, outline=STEEL_L, width=0.03)                                 # the ring


@painter("grenade:stick", 3.4)
def _stick(c, arg):
    c.rect(0.0, 0.36, 2.4, 0.62, WOOD)
    c.rect(2.3, 0.14, 3.4, 0.86, FG, r=0.05)
    c.rect(0.0, 0.4, 0.12, 0.58, STEEL)


@painter("grenade:smoke", 0.55)
def _smoke(c, arg):
    col = (80, 88, 80, 255) if arg != "wp" else (120, 120, 90, 255)
    c.rect(0.06, 0.18, 0.5, 0.98, col, r=0.05)
    c.rect(0.06, 0.4, 0.5, 0.5, (200, 200, 190, 255) if arg != "wp" else (220, 190, 60, 255))
    c.rect(0.18, 0.06, 0.38, 0.2, STEEL)
    c.line([(0.38, 0.1), (0.5, 0.5)], STEEL_L, 0.035)


@painter("grenade:gammon", 1.0)
def _gammon(c, arg):
    c.ell(0.05, 0.25, 0.95, 0.98, KHAKI)
    c.rect(0.4, 0.05, 0.6, 0.3, STEEL)


@painter("grenade:at", 0.7)
def _atgren(c, arg):
    c.rect(0.08, 0.3, 0.62, 0.98, (90, 90, 60, 255), r=0.06)
    c.rect(0.25, 0.02, 0.45, 0.32, WOOD)


@painter("grenade:molotov", 0.55)
def _molotov(c, arg):
    c.poly([(0.12, 0.98), (0.44, 0.98), (0.44, 0.42), (0.34, 0.3), (0.34, 0.1), (0.22, 0.1), (0.22, 0.3),
            (0.12, 0.42)], (90, 120, 80, 200))
    c.rect(0.12, 0.6, 0.44, 0.98, (170, 110, 40, 200))                                             # the petrol
    c.poly([(0.22, 0.1), (0.3, -0.02), (0.36, 0.1)], CLOTH)                                        # the rag


@painter("explosive:*", 1.4)
def _charge(c, arg):
    c.rect(0.05, 0.3, 1.35, 0.95, KHAKI, r=0.06)
    c.rect(0.05, 0.3, 1.35, 0.44, OD)
    c.line([(1.2, 0.3), (1.35, 0.05)], BLACK, 0.04)
    c.text(0.7, 0.66, "TNT" if arg != "mine" else "", INK, 0.26)


def grenade_key(t) -> str:
    g = t.gtype
    if g in ("smoke", "wp"):
        return "grenade:smoke" + ("|wp" if g == "wp" else "")
    if g in ("frag", "stick", "gammon", "at", "molotov"):
        return "grenade:" + g
    return "grenade:frag"


# ============================================================================ helmets and clothes
@painter("helmet:*", 1.5)
def _helmet(c, arg):
    col = {"m1": OD, "brodie": (108, 104, 70, 255), "stahlhelm": FG, "ssh40": (70, 88, 60, 255),
           "type90": (120, 110, 70, 255), "adrian": (90, 100, 110, 255), "it": (100, 100, 80, 255),
           "tank": (60, 50, 40, 255)}.get(arg, OD)
    if arg == "brodie":
        c.ell(0.05, 0.45, 1.45, 0.78, col)                                                         # the soup bowl
        c.ell(0.35, 0.18, 1.15, 0.7, col)
    elif arg == "stahlhelm":
        c.poly([(0.2, 0.7), (0.25, 0.3), (0.55, 0.12), (0.95, 0.12), (1.25, 0.3), (1.3, 0.62), (1.45, 0.82),
                (1.05, 0.72), (0.2, 0.72)], col)                                                   # the coal scuttle
    elif arg == "adrian":
        c.ell(0.1, 0.5, 1.4, 0.8, col)
        c.ell(0.3, 0.2, 1.2, 0.72, col)
        c.poly([(0.7, 0.05), (0.8, 0.05), (0.85, 0.3), (0.65, 0.3)], col)                          # the comb
    elif arg in ("cap", "peaked"):
        c.ell(0.25, 0.25, 1.25, 0.7, col if arg == "peaked" else KHAKI)
        c.poly([(0.2, 0.6), (1.35, 0.6), (1.45, 0.8), (0.9, 0.78)], BLACK if arg == "peaked" else OD_D)
    elif arg == "tank":
        c.ell(0.2, 0.15, 1.3, 0.85, col)
        c.rect(0.25, 0.5, 1.25, 0.62, (40, 34, 28, 255))
    else:
        c.poly([(0.12, 0.74), (0.2, 0.42), (0.45, 0.16), (1.05, 0.16), (1.3, 0.42), (1.38, 0.74)], col)
        c.rect(0.08, 0.7, 1.42, 0.8, col)
    c.line([(0.35, 0.6), (1.15, 0.6)], (0, 0, 0, 60), 0.02)


@painter("clothes:*", 1.0)
def _clothes(c, arg):
    col = {"civvies": (90, 80, 70, 255), "flight": (110, 70, 40, 255), "winter": (150, 150, 140, 255),
           "ghillie": (80, 90, 50, 255), "camo": (110, 110, 70, 255), "snow": (230, 230, 225, 255),
           "maewest": (220, 180, 40, 255)}.get(arg, OD)
    c.poly([(0.3, 0.08), (0.7, 0.08), (0.95, 0.25), (0.9, 0.5), (0.78, 0.45), (0.78, 0.95), (0.22, 0.95),
            (0.22, 0.45), (0.1, 0.5), (0.05, 0.25)], col)
    c.poly([(0.4, 0.08), (0.5, 0.25), (0.6, 0.08)], (0, 0, 0, 80))
    if arg in ("camo", "ghillie"):
        for x, y in ((0.35, 0.4), (0.6, 0.6), (0.4, 0.75), (0.65, 0.3)):
            c.ell(x - 0.07, y - 0.05, x + 0.07, y + 0.05, (60, 70, 40, 255))


# ============================================================================ webbing and packs
@painter("rig:belt", 3.0)
def _beltrig(c, arg):
    c.rect(0.0, 0.42, 3.0, 0.58, OD_D)
    n = 5
    for k in range(n):
        x = 0.15 + k * 0.56
        c.rect(x, 0.3, x + 0.44, 0.85, OD if arg != "de" else (60, 50, 40, 255), r=0.04)
        c.line([(x + 0.05, 0.42), (x + 0.39, 0.42)], (0, 0, 0, 80), 0.02)
    c.rect(1.38, 0.38, 1.62, 0.62, BRASS)                                                          # buckle


@painter("rig:bandolier", 3.0)
def _bando(c, arg):
    c.line([(0.1, 0.9), (2.9, 0.1)], KHAKI, 0.22)
    for k in range(6):
        x, y = 0.4 + k * 0.42, 0.8 - k * 0.12
        c.rect(x, y - 0.12, x + 0.3, y + 0.12, (140, 120, 80, 255))


@painter("rig:medic", 2.0)
def _medrig(c, arg):
    for x in (0.1, 1.1):
        c.rect(x, 0.2, x + 0.8, 0.9, (180, 176, 150, 255), r=0.06)
        c.rect(x + 0.33, 0.35, x + 0.47, 0.75, RED)
        c.rect(x + 0.2, 0.48, x + 0.6, 0.62, RED)


@painter("pack:*", 1.1)
def _pack(c, arg):
    col = {"tornister": (120, 90, 60, 255), "sack": (140, 125, 90, 255), "suitcase": (100, 64, 36, 255),
           "musette": KHAKI}.get(arg, OD)
    if arg == "suitcase":
        c.rect(0.05, 0.25, 1.05, 0.95, col, r=0.05)
        c.rect(0.4, 0.1, 0.7, 0.26, None, outline=BLACK, width=0.04)
        c.rect(0.05, 0.55, 1.05, 0.6, WOOD_D)
        return
    if arg == "sack":
        c.poly([(0.2, 0.3), (0.9, 0.3), (1.05, 0.95), (0.05, 0.95)], col)
        c.line([(0.3, 0.25), (0.55, 0.05), (0.8, 0.25)], KHAKI, 0.05)
        return
    c.rect(0.1, 0.12, 1.0, 0.95, col, r=0.1)
    c.rect(0.1, 0.12, 1.0, 0.42, tuple(max(0, v - 20) for v in col[:3]) + (255,), r=0.1)            # the flap
    c.rect(0.5, 0.35, 0.6, 0.55, STEEL)
    if arg == "tornister":
        for k in range(6):
            c.line([(0.2 + k * 0.14, 0.5), (0.25 + k * 0.14, 0.9)], (90, 64, 40, 255), 0.02)       # calfskin


# ============================================================================ blades and tools of the trade
@painter("blade:*", 4.0)
def _blade(c, arg):
    if arg == "sword":
        c.arc(-0.5, 0.15, 3.8, 2.0, 200, 290, STEEL_L, 0.1)
        c.rect(3.3, 0.18, 4.0, 0.34, BLACK)
        c.rect(3.2, 0.1, 3.3, 0.42, BRASS)
        return
    if arg == "kukri":
        c.poly([(0.4, 0.3), (1.6, 0.35), (2.8, 0.7), (2.9, 0.5), (1.8, 0.2)], STEEL_L)
        c.rect(2.9, 0.3, 4.0, 0.52, WOOD_D)
        return
    if arg == "shovel":
        c.rect(0.0, 0.42, 2.6, 0.56, WOOD)
        c.poly([(2.6, 0.2), (3.7, 0.2), (4.0, 0.49), (3.7, 0.8), (2.6, 0.8)], STEEL)
        return
    if arg in ("cosh", "knuckle", "garrote"):
        if arg == "garrote":
            c.line([(0.3, 0.5), (3.7, 0.5)], STEEL_L, 0.03)
            c.rect(0.0, 0.35, 0.4, 0.65, WOOD)
            c.rect(3.6, 0.35, 4.0, 0.65, WOOD)
        elif arg == "knuckle":
            for k in range(4):
                c.ell(1.2 + k * 0.42, 0.25, 1.6 + k * 0.42, 0.7, None, outline=BRASS, width=0.07)
        else:
            c.rect(0.5, 0.35, 3.5, 0.65, (40, 30, 24, 255), r=0.15)
        return
    long = arg == "bayonet"
    L = 3.1 if long else 2.2
    c.poly([(0.0, 0.49), (0.3, 0.36), (L, 0.36), (L, 0.62), (0.3, 0.62)], STEEL_L)
    c.rect(L, 0.24, L + 0.12, 0.74, STEEL)
    c.rect(L + 0.12, 0.34, 4.0, 0.64, WOOD_D if arg != "fs" else BRASS_D, r=0.05)


# ============================================================================ medical
@painter("med:*", 1.3)
def _med(c, arg):
    if arg == "bandage":
        c.rect(0.1, 0.3, 1.2, 0.9, (170, 160, 120, 255), r=0.06)
        c.text(0.65, 0.6, "+", RED, 0.5)
    elif arg == "morphine":
        c.rect(0.1, 0.44, 0.9, 0.62, (220, 220, 210, 255), r=0.06)
        c.rect(0.9, 0.5, 1.25, 0.56, STEEL_L)
        c.rect(0.1, 0.44, 0.3, 0.62, (120, 30, 30, 255))
    elif arg == "tourniquet":
        c.line([(0.1, 0.8), (0.5, 0.3), (0.9, 0.3), (1.2, 0.8)], (140, 120, 90, 255), 0.1)
        c.rect(0.55, 0.2, 0.85, 0.4, STEEL)
    elif arg == "sulfa":
        c.rect(0.35, 0.15, 0.95, 0.95, (230, 226, 210, 255), r=0.06)
        c.rect(0.35, 0.15, 0.95, 0.3, (120, 30, 30, 255))
    elif arg == "plasma":
        c.rect(0.4, 0.15, 0.9, 0.95, (200, 200, 190, 160), r=0.05)
        c.rect(0.4, 0.45, 0.9, 0.95, (210, 190, 120, 220), r=0.05)
        c.rect(0.55, 0.02, 0.75, 0.16, STEEL)
    else:                                                                                           # a bag
        c.rect(0.1, 0.25, 1.2, 0.95, (120, 110, 80, 255) if arg != "doctor" else (50, 34, 24, 255), r=0.08)
        c.rect(0.4, 0.1, 0.9, 0.28, None, outline=BLACK, width=0.04)
        c.rect(0.33, 0.45, 0.97, 0.75, WHITE)
        c.rect(0.58, 0.48, 0.72, 0.72, RED)
        c.rect(0.45, 0.54, 0.85, 0.66, RED)


# ============================================================================ the things in a soldier's pockets
def _paper(c, lines=4, col=PAPER, fold=False, stamp=None):
    c.poly([(0.1, 0.05), (0.8, 0.05), (0.95, 0.2), (0.95, 0.95), (0.1, 0.95)], col)
    c.poly([(0.8, 0.05), (0.8, 0.2), (0.95, 0.2)], PAPER_D)
    for k in range(lines):
        c.line([(0.2, 0.3 + k * 0.14), (0.85 - (0.2 if k == lines - 1 else 0), 0.3 + k * 0.14)], INK, 0.025)
    if fold:
        c.line([(0.1, 0.5), (0.95, 0.5)], PAPER_D, 0.02)
    if stamp:
        c.ell(0.55, 0.62, 0.9, 0.92, None, outline=stamp, width=0.04)


@painter("thing:*", 1.0)
def _thing(c, arg):
    a = arg
    if a in ("document", "orders", "dispatches", "cover_papers", "papers", "letter", "code"):
        _paper(c, 4, stamp=RED if a in ("orders", "dispatches", "cover_papers", "papers") else None)
        if a == "letter":
            c.line([(0.1, 0.05), (0.52, 0.5), (0.95, 0.05)], PAPER_D, 0.03)
    elif a == "paybook":
        c.rect(0.15, 0.1, 0.85, 0.95, (80, 70, 50, 255), r=0.03)
        c.rect(0.25, 0.3, 0.75, 0.42, PAPER)
    elif a == "newspaper":
        c.rect(0.05, 0.15, 0.95, 0.9, (205, 200, 185, 255))
        c.rect(0.12, 0.22, 0.88, 0.34, INK)
        for k in range(3):
            c.line([(0.12, 0.45 + k * 0.13), (0.88, 0.45 + k * 0.13)], (120, 116, 104, 255), 0.03)
    elif a == "map":
        c.rect(0.05, 0.1, 0.95, 0.9, (214, 206, 170, 255))
        c.line([(0.05, 0.6), (0.4, 0.45), (0.7, 0.55), (0.95, 0.3)], (60, 110, 160, 255), 0.04)     # a river
        c.line([(0.2, 0.1), (0.35, 0.9)], (170, 60, 40, 255), 0.03)                                  # a road
        c.line([(0.5, 0.1), (0.5, 0.9)], PAPER_D, 0.02)
    elif a == "photo":
        c.rect(0.12, 0.12, 0.88, 0.88, WHITE)
        c.rect(0.2, 0.2, 0.8, 0.72, (120, 110, 96, 255))
        c.ell(0.4, 0.28, 0.6, 0.5, (190, 176, 150, 255))
    elif a == "ration":
        c.rect(0.12, 0.25, 0.88, 0.9, TIN, r=0.08)
        c.rect(0.12, 0.25, 0.88, 0.36, (120, 120, 110, 255), r=0.08)
        c.rect(0.12, 0.5, 0.88, 0.7, OD)
    elif a == "k_ration":
        c.rect(0.08, 0.3, 0.92, 0.8, (170, 150, 100, 255))
        c.text(0.5, 0.55, "K", INK, 0.35)
    elif a == "chocolate":
        c.rect(0.12, 0.3, 0.88, 0.75, (90, 60, 40, 255))
        c.rect(0.12, 0.3, 0.88, 0.45, (170, 140, 80, 255))
    elif a == "canteen":
        c.ell(0.15, 0.2, 0.85, 0.95, (110, 110, 100, 255))
        c.rect(0.15, 0.4, 0.85, 0.95, OD, r=0.1)
        c.rect(0.42, 0.06, 0.58, 0.22, BLACK)
    elif a == "flask":
        c.rect(0.2, 0.15, 0.8, 0.9, STEEL_L, r=0.15)
        c.rect(0.42, 0.02, 0.58, 0.16, STEEL)
    elif a == "bottle":
        c.rect(0.3, 0.35, 0.7, 0.95, (80, 110, 70, 220), r=0.06)
        c.poly([(0.3, 0.35), (0.42, 0.18), (0.58, 0.18), (0.7, 0.35)], (80, 110, 70, 220))
        c.rect(0.43, 0.04, 0.57, 0.2, (120, 90, 60, 255))
        c.rect(0.3, 0.55, 0.7, 0.75, PAPER)
    elif a == "cigarettes":
        c.rect(0.2, 0.15, 0.8, 0.95, (180, 40, 30, 255) if arg else OD)
        c.rect(0.2, 0.15, 0.8, 0.3, WHITE)
        c.rect(0.32, 0.02, 0.42, 0.16, WHITE)
    elif a == "lighter":
        c.rect(0.3, 0.2, 0.7, 0.95, STEEL_L, r=0.05)
        c.line([(0.3, 0.45), (0.7, 0.45)], STEEL, 0.03)
        c.poly([(0.45, 0.2), (0.5, 0.02), (0.58, 0.2)], (240, 180, 60, 255))
    elif a == "watch":
        c.rect(0.4, 0.0, 0.6, 1.0, (90, 60, 40, 255))
        c.ell(0.18, 0.2, 0.82, 0.84, BRASS)
        c.ell(0.24, 0.26, 0.76, 0.78, WHITE)
        c.line([(0.5, 0.52), (0.5, 0.34)], BLACK, 0.035)
        c.line([(0.5, 0.52), (0.64, 0.56)], BLACK, 0.035)
    elif a == "compass":
        c.ell(0.1, 0.1, 0.9, 0.9, (60, 60, 50, 255))
        c.ell(0.18, 0.18, 0.82, 0.82, (220, 216, 196, 255))
        c.poly([(0.5, 0.2), (0.58, 0.5), (0.42, 0.5)], RED)
        c.poly([(0.5, 0.8), (0.58, 0.5), (0.42, 0.5)], INK)
    elif a == "binoculars":
        c.rect(0.05, 0.25, 0.45, 0.9, BLACK, r=0.08)
        c.rect(0.55, 0.25, 0.95, 0.9, BLACK, r=0.08)
        c.rect(0.4, 0.35, 0.6, 0.5, STEEL)
        c.ell(0.1, 0.72, 0.4, 0.92, (120, 150, 170, 255))
        c.ell(0.6, 0.72, 0.9, 0.92, (120, 150, 170, 255))
    elif a == "whistle":
        c.rect(0.2, 0.35, 0.75, 0.7, STEEL_L, r=0.15)
        c.rect(0.75, 0.42, 0.95, 0.56, STEEL_L)
        c.arc(0.05, 0.3, 0.35, 0.75, 90, 270, STEEL, 0.04)
    elif a == "dogtags":
        c.line([(0.2, 0.05), (0.5, 0.35), (0.8, 0.05)], STEEL_L, 0.02)
        c.rect(0.25, 0.3, 0.75, 0.65, STEEL_L, r=0.1)
        c.rect(0.3, 0.5, 0.8, 0.85, TIN, r=0.1)
    elif a == "harmonica":
        c.rect(0.05, 0.35, 0.95, 0.65, STEEL_L)
        for k in range(7):
            c.rect(0.1 + k * 0.12, 0.44, 0.16 + k * 0.12, 0.56, BLACK)
    elif a == "cards":
        c.rect(0.15, 0.2, 0.7, 0.9, WHITE, r=0.05)
        c.rect(0.3, 0.1, 0.85, 0.8, WHITE, outline=INK, width=0.02, r=0.05)
        c.text(0.57, 0.45, "A", RED, 0.3)
    elif a == "book":
        c.rect(0.2, 0.1, 0.8, 0.92, BLACK, r=0.03)
        c.rect(0.45, 0.25, 0.55, 0.6, BRASS)
        c.rect(0.35, 0.35, 0.65, 0.43, BRASS)
    elif a == "ironcross":
        k = 0.5
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            c.poly([(k, k), (k + dx * 0.4 + dy * 0.2, k + dy * 0.4 + dx * 0.2),
                    (k + dx * 0.4 - dy * 0.2, k + dy * 0.4 - dx * 0.2)], (200, 200, 205, 255))
            c.poly([(k, k), (k + dx * 0.34 + dy * 0.14, k + dy * 0.34 + dx * 0.14),
                    (k + dx * 0.34 - dy * 0.14, k + dy * 0.34 - dx * 0.14)], BLACK)
    elif a == "ribbon":
        c.rect(0.1, 0.35, 0.9, 0.65, (60, 90, 160, 255))
        c.rect(0.4, 0.35, 0.6, 0.65, WHITE)
        c.rect(0.46, 0.35, 0.54, 0.65, RED)
    elif a in ("rosary", "charm", "ring", "coin", "medal", "flag"):
        if a == "rosary":
            for k in range(10):
                ang = k / 10 * 2 * math.pi
                x, y = 0.5 + 0.3 * math.cos(ang), 0.4 + 0.25 * math.sin(ang)
                c.ell(x - 0.04, y - 0.04, x + 0.04, y + 0.04, (120, 80, 60, 255))
            c.rect(0.47, 0.62, 0.53, 0.95, BRASS)
            c.rect(0.4, 0.72, 0.6, 0.77, BRASS)
        elif a == "medal":
            c.rect(0.35, 0.02, 0.65, 0.35, RED)
            if arg == "medal":
                c.poly([(0.5, 0.35), (0.62, 0.5), (0.8, 0.52), (0.66, 0.66), (0.72, 0.9), (0.5, 0.76), (0.28, 0.9),
                        (0.34, 0.66), (0.2, 0.52), (0.38, 0.5)], BRASS)
        elif a == "flag":
            c.rect(0.1, 0.2, 0.9, 0.8, WHITE)
            c.ell(0.38, 0.38, 0.62, 0.62, RED)
            for k in range(4):
                c.line([(0.15, 0.28 + k * 0.14), (0.3, 0.28 + k * 0.14)], INK, 0.015)
        elif a == "charm":
            c.rect(0.3, 0.2, 0.7, 0.9, (180, 40, 40, 255), r=0.05)
            c.rect(0.38, 0.32, 0.62, 0.7, (220, 200, 120, 255))
        else:
            c.ell(0.2, 0.2, 0.8, 0.8, BRASS if a == "coin" else (210, 180, 80, 255))
            if a == "ring":
                c.ell(0.32, 0.32, 0.68, 0.68, (0, 0, 0, 0))
    elif a == "money":
        c.rect(0.05, 0.25, 0.9, 0.75, (150, 170, 130, 255))
        c.rect(0.12, 0.3, 0.95, 0.82, (170, 186, 150, 255))
        c.ell(0.42, 0.45, 0.65, 0.7, (120, 140, 100, 255))
    elif a in ("radio", "wireless", "handradio", "sphone"):
        if a == "handradio":
            c.rect(0.3, 0.2, 0.7, 0.95, OD, r=0.05)
            c.line([(0.4, 0.2), (0.4, 0.0)], STEEL, 0.04)
        elif a == "wireless":
            c.rect(0.05, 0.3, 0.95, 0.9, (80, 60, 40, 255), r=0.04)
            c.rect(0.15, 0.4, 0.5, 0.65, BLACK)
            for k in range(3):
                c.ell(0.6 + k * 0.1, 0.45, 0.66 + k * 0.1, 0.51, BRASS)
        else:
            c.rect(0.15, 0.25, 0.85, 0.95, OD, r=0.04)
            c.line([(0.7, 0.25), (0.85, 0.0)], STEEL, 0.03)
            c.rect(0.25, 0.35, 0.6, 0.5, BLACK)
            c.ell(0.25, 0.6, 0.4, 0.75, STEEL)
    elif a == "flaregun":
        c.rect(0.25, 0.25, 0.95, 0.5, (70, 70, 60, 255), r=0.03)
        c.poly([(0.3, 0.48), (0.55, 0.48), (0.45, 0.95), (0.2, 0.95)], WOOD_D)
    elif a == "wirecutters":
        c.line([(0.1, 0.9), (0.55, 0.4), (0.75, 0.1)], STEEL, 0.06)
        c.line([(0.4, 0.95), (0.55, 0.4), (0.95, 0.2)], STEEL, 0.06)
        c.line([(0.1, 0.9), (0.35, 0.62)], RED, 0.08)
    elif a == "torch":
        c.rect(0.1, 0.4, 0.7, 0.62, OD, r=0.04)
        c.poly([(0.7, 0.35), (0.92, 0.25), (0.92, 0.77), (0.7, 0.67)], STEEL_L)
    elif a == "camera":
        c.rect(0.1, 0.4, 0.9, 0.62, STEEL_L, r=0.04)
        c.ell(0.2, 0.44, 0.34, 0.58, BLACK)
    elif a in ("pills", "gum", "film", "sewing", "shave"):
        col = {"pills": (200, 60, 40, 255), "gum": (220, 190, 60, 255), "film": BLACK, "sewing": KHAKI,
               "shave": (160, 150, 130, 255)}[a]
        c.rect(0.15, 0.3, 0.85, 0.8, col, r=0.08)
        c.rect(0.15, 0.3, 0.85, 0.42, tuple(min(255, v + 40) for v in col[:3]) + (255,), r=0.08)
    elif a in ("crate", "shells", "sandbags", "wire", "detector", "hose", "shoring", "life_ring", "time_pencil",
               "brassard", "tool"):
        if a in ("crate", "shells"):
            c.rect(0.05, 0.25, 0.95, 0.9, OD_D if a == "crate" else WOOD_D)
            c.line([(0.05, 0.25), (0.95, 0.9)], (0, 0, 0, 70), 0.03)
        elif a == "sandbags":
            c.ell(0.05, 0.4, 0.95, 0.9, (170, 150, 110, 255))
        elif a == "wire":
            for k in range(4):
                c.ell(0.15 + k * 0.03, 0.2, 0.85 - k * 0.03, 0.9, None, outline=STEEL, width=0.03)
        elif a == "detector":
            c.line([(0.1, 0.1), (0.7, 0.75)], STEEL, 0.05)
            c.ell(0.55, 0.7, 0.95, 0.95, OD)
        elif a == "life_ring":
            c.ell(0.1, 0.1, 0.9, 0.9, None, outline=(230, 110, 40, 255), width=0.18)
        elif a == "brassard":
            c.rect(0.05, 0.3, 0.95, 0.7, WHITE)
            c.rect(0.43, 0.34, 0.57, 0.66, RED)
            c.rect(0.33, 0.44, 0.67, 0.56, RED)
        elif a == "time_pencil":
            c.rect(0.05, 0.44, 0.95, 0.56, BRASS_D)
            c.rect(0.8, 0.42, 0.95, 0.58, (60, 120, 200, 255))
        else:
            c.rect(0.2, 0.3, 0.8, 0.8, STEEL, r=0.05)
    else:
        c.rect(0.2, 0.2, 0.8, 0.8, (110, 110, 110, 255), r=0.1)


THING_OF_TOOL = {
    "ration": "ration", "document": "document", "flask": "flask", "cover_papers": "cover_papers", "wireless": "wireless",
    "newspaper": "newspaper", "handradio": "handradio", "map": "map", "money": "money", "radio": "radio",
    "watch": "watch", "cigarettes": "cigarettes", "photo": "photo", "rosary": "rosary", "trade": "tool",
    "chocolate": "chocolate", "stimulant": "pills", "lighter": "lighter", "charm": "charm", "medal": "medal",
    "wirecutters": "wirecutters", "binoculars": "binoculars", "flaregun": "flaregun", "compass": "compass",
    "orders": "orders", "ammo_load": "shells", "hose": "hose", "shoring": "tool", "life_ring": "life_ring",
    "whistle": "whistle", "wire": "wire", "sandbags": "sandbags", "detector": "detector", "canteen": "canteen",
    "letter": "letter", "dogtags": "dogtags", "shells": "shells", "dispatches": "dispatches", "brassard": "brassard",
    "harmonica": "harmonica", "coin": "coin", "cards": "cards", "bible": "book", "ammo_crate": "crate",
    "papers": "papers", "time_pencil": "time_pencil", "sphone": "sphone", "torch": "torch", "camera": "camera",
    "code": "code", "film": "film", "flag": "flag", "ring": "ring", "shave": "shave", "sewing": "sewing", "gum": "gum",
}

HELMET = {"helmet_m1": "m1", "helmet_brodie": "brodie", "helmet_mk3": "brodie", "stahlhelm": "stahlhelm",
          "ssh40": "ssh40", "type90": "type90", "adrian": "adrian", "m33_it": "it", "wz31": "adrian",
          "tanker_helmet": "tank", "soft_cap": "cap", "peaked_cap": "peaked"}
CLOTHES = {"civvies": "civvies", "flight_jacket": "flight", "winter_coat": "winter", "ghillie": "ghillie",
           "maskhalat": "camo", "tarnjacke": "camo", "foliage_cape": "ghillie", "snow_smock": "snow",
           "mae_west": "maewest"}
BLADE = {"bayonet": "bayonet", "katana": "sword", "dadao": "sword", "szabla": "sword", "kukri": "kukri",
         "shovel": "shovel", "garrote": "garrote", "knuckleduster": "knuckle", "cosh": "cosh", "fs_knife": "fs",
         "smatchet": "kukri"}
MED = {"bandage": "bandage", "morphine": "morphine", "tourniquet": "tourniquet", "sulfa": "sulfa",
       "plasma": "plasma", "doctors_bag": "doctor", "medkit": "bag", "surgical_kit": "doctor"}


def item_key(it) -> str | None:
    """The picture for an item (its family, and the variant), or None."""
    t = it.t
    k = t.kind
    i = t.id
    if k == "gun":
        return gun_key(t)
    if k == "mag":
        return mag_key(t)
    if k == "clip":
        return f"clip:x|{t.mag}"
    if k == "ammo":
        return "ammo:x|shell" if t.cal and any(ch.isdigit() for ch in t.cal) and "mm" in t.cal and \
            int("".join(ch for ch in t.cal.split("mm")[0] if ch.isdigit()) or 0) >= 20 else "ammo:x"
    if k == "grenade":
        return grenade_key(t)
    if k == "explosive":
        return "explosive:x|mine" if "mine" in i else "explosive:x"
    if k == "armor":
        if t.get("slot") == "head":
            return f"helmet:x|{HELMET.get(i, 'm1')}"
        return f"clothes:x|{CLOTHES.get(i, 'x')}"
    if k == "container":
        slot = t.get("slot")
        if slot == "pack":
            arg = "tornister" if "tornister" in i else "sack" if i in ("sack", "su_veshmeshok") else \
                "suitcase" if i == "suitcase" else "musette" if "musette" in i or "shoulder" in i else ""
            return f"pack:x|{arg}"
        if "medic" in i:
            return "rig:medic"
        if "bandolier" in i:
            return "rig:bandolier"
        return "rig:belt|de" if i.startswith("de_") else "rig:belt"
    if k == "melee":
        return f"blade:x|{BLADE.get(i, 'knife')}"
    if k == "medical":
        return f"med:x|{MED.get(i, 'bag')}"
    if k == "tool":
        tool = t.tool
        if tool == "ration" and i in ("k_ration", "d_ration"):
            return "thing:x|k_ration" if i == "k_ration" else "thing:x|chocolate"
        if tool == "document" and i == "paybook":
            return "thing:x|paybook"
        if tool == "flask" and i != "flask":
            return "thing:x|bottle"
        if tool == "shells":
            return "thing:x|shells"
        if tool == "medal":
            return "thing:x|ironcross" if i == "iron_cross" else "thing:x|ribbon"
        th = THING_OF_TOOL.get(tool)
        if th is None and i == "shovel":
            return "blade:x|shovel"
        return f"thing:x|{th or 'x'}"
    if k == "corpse":
        return None
    return None


def _badge_aspect(arg, pw, ph):
    return pw / max(1, ph)


def _badge(c, arg, fill=(24, 22, 16, 210), ink=(255, 230, 140, 255)):
    W = c.width                                     # (the badge fills its box: the aspect is the box's)
    n = max(1, len(arg))
    w = min(W, n * 0.46 + 0.2)                      # the lower half of its cell, at the right: the picture shows
    c.rect(W - w, 0.42, W, 1.0, fill, r=0.14)
    c.text(W - w / 2, 0.72, arg, ink, 0.56)


PAINTERS["badge:dim"] = (_badge_aspect, _badge)
PAINTERS["badge:warn"] = (_badge_aspect, lambda c, a: _badge(c, a, (120, 30, 20, 230), (255, 240, 200, 255)))


GHOST = {"head": "helmet:x|m1", "body": "clothes:x|x", "rig": "rig:belt", "pack": "pack:x|", "primary": "gun:rifle",
         "secondary": "gun:rifle", "holster": "gun:pistol", "melee": "blade:x|bayonet"}


# ============================================================================ the panel: you, as you'd know yourself
def _hex(s, alpha=255):
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), alpha)
    except Exception:
        return (150, 200, 140, alpha)


def hexcol(rgb) -> str:
    return "%02x%02x%02x" % tuple(int(v) for v in rgb[:3])


@painter("doll", 0.5)
def _doll(c, arg):
    """The body: every part in the colour of how it is, the blood where it's coming out, the dressings on."""
    parts = {}
    wounds = {}
    for bit in arg.split(","):
        if ":" in bit:
            k, col, bl, nw = (bit.split(":") + ["", "", ""])[:4]
            parts[k] = (_hex(col), bl)
            wounds[k] = int(nw) if nw.isdigit() else 0
    shape = {"head": ("ell", 0.17, 0.0, 0.33, 0.16), "torso": ("rect", 0.14, 0.18, 0.36, 0.52),
             "l_arm": ("rect", 0.36, 0.19, 0.44, 0.5), "r_arm": ("rect", 0.06, 0.19, 0.14, 0.5),
             "l_leg": ("rect", 0.255, 0.53, 0.35, 0.98), "r_leg": ("rect", 0.15, 0.53, 0.245, 0.98)}
    for k, (kind, x0, y0, x1, y1) in shape.items():
        col, bl = parts.get(k, ((90, 90, 80, 255), ""))
        if kind == "ell":
            c.ell(x0, y0, x1, y1, col)
        else:
            c.rect(x0, y0, x1, y1, col, r=0.02)
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        for j in range(min(4, wounds.get(k, 0))):                                                   # each wound
            wy = y0 + (y1 - y0) * (0.25 + 0.18 * j)
            c.line([(mx - 0.035, wy - 0.012), (mx + 0.035, wy + 0.012)], (110, 10, 10, 255), 0.018)
        if bl == "B":
            c.rect(x0 - 0.005, my - 0.03, x1 + 0.005, my + 0.03, (236, 232, 220, 255))            # the dressing
        elif bl == "T":
            c.rect(x0 - 0.01, y0 + 0.02, x1 + 0.01, y0 + 0.06, (60, 40, 30, 255))                  # the tourniquet
        elif bl.startswith("b"):
            n = int(bl[1:] or 1)
            for j in range(n + 1):
                dx = (j - n / 2) * 0.05
                c.ell(mx + dx - 0.02, my + 0.02 * j, mx + dx + 0.02, my + 0.05 + 0.02 * j, (220, 20, 20, 255))


@painter("stance", 1.5)
def _stance(c, arg):
    """How you're lying, and what's between you and them."""
    bits = arg.split("|") if arg else []
    st = bits[0] if bits else "0"
    cov = int(bits[1]) if len(bits) > 1 and bits[1].isdigit() else 0
    man = (120, 124, 84, 255)
    ground = (70, 60, 44, 255)
    c.rect(0.0, 0.92, 1.5, 1.0, ground)
    if st == "swim":
        c.rect(0.0, 0.6, 1.5, 1.0, (50, 80, 120, 255))
        c.ell(0.6, 0.42, 0.8, 0.62, man)
    elif st == "veh":
        c.rect(0.15, 0.4, 1.35, 0.9, (80, 84, 66, 255), r=0.06)
        c.ell(0.7, 0.18, 0.86, 0.36, man)
    elif st == "2":
        c.rect(0.2, 0.8, 1.05, 0.92, man, r=0.04)                                                  # flat
        c.ell(1.02, 0.74, 1.16, 0.88, man)
    elif st == "1":
        c.poly([(0.55, 0.92), (0.62, 0.62), (0.86, 0.58), (0.92, 0.92), (0.8, 0.92), (0.78, 0.72),
                (0.68, 0.74), (0.68, 0.92)], man)
        c.poly([(0.6, 0.62), (0.66, 0.36), (0.84, 0.36), (0.86, 0.6)], man)
        c.ell(0.68, 0.2, 0.84, 0.36, man)
    else:
        c.rect(0.64, 0.56, 0.72, 0.92, man)
        c.rect(0.74, 0.56, 0.82, 0.92, man)
        c.rect(0.6, 0.26, 0.86, 0.58, man, r=0.03)
        c.ell(0.66, 0.08, 0.8, 0.24, man)
    if cov > 0 and st not in ("swim", "veh"):
        h = 0.2 + 0.7 * min(1.0, cov / 100)
        col = (120, 104, 76, 255) if cov < 45 else (104, 100, 92, 255)
        c.rect(1.12, 0.92 - h, 1.42, 0.92, col, r=0.03)                                            # what shields you
        for k in range(int(h / 0.12)):
            c.line([(1.12, 0.9 - k * 0.12), (1.42, 0.9 - k * 0.12)], (0, 0, 0, 60), 0.012)


def _rounds_aspect(arg, pw, ph):
    return pw / max(1, ph)


# what "most", "about half"... mean, as fractions of a magazine (entities.Item.ammo_estimate's words)
BANDS = ((0.85, 1.0), (0.55, 0.85), (0.3, 0.55), (0.12, 0.3), (0.0, 0.12))


def rounds_key(w) -> str:
    """The magazine as you know it: counted (every round), or only as the estimate has it (a band of rounds
    you're not sure of - never the true count you haven't made)."""
    cap = max(1, w.t.mag)
    if w.known_rounds:
        return f"rounds|{w.loaded}|{w.loaded}|{cap}"
    if w.loaded <= 0:
        return f"rounds|0|0|{cap}"
    r = w.loaded / cap
    lo, hi = next(b for b in BANDS if r > b[0] or b[0] == 0.0)
    return f"rounds|{int(lo * cap)}|{max(1, int(round(hi * cap)))}|{cap}"


@painter("rounds", _rounds_aspect)
def _rounds(c, arg):
    """What's in the magazine, as you know it: rounds you're sure of in brass, the ones you're not faded."""
    bits = arg.split("|")
    try:
        lo, hi, cap = int(bits[0]), int(bits[1]), max(1, int(bits[2]))
    except Exception:
        return
    W = c.width
    unsure = (196, 160, 72, 90)
    if cap > 40:
        c.rect(0.0, 0.25, W, 0.8, (40, 38, 30, 255), r=0.1)
        if hi > lo:
            c.rect(0.02, 0.28, max(0.03, (W - 0.02) * hi / cap), 0.77, unsure, r=0.1)
        if lo > 0:
            c.rect(0.02, 0.28, max(0.03, (W - 0.02) * lo / cap), 0.77, BRASS, r=0.1)
        for k in range(1, 10):
            c.line([(W * k / 10, 0.25), (W * k / 10, 0.4)], (0, 0, 0, 120), 0.03)
        return
    step = min(0.5, W / cap)
    for k in range(cap):
        x = k * step
        if k < lo:
            col, tip = BRASS, COPPER
        elif k < hi:
            col, tip = unsure, (170, 96, 60, 90)
        else:
            col, tip = (60, 56, 44, 255), None
        c.rect(x + step * 0.15, 0.3, x + step * 0.85, 0.95, col)
        if tip is not None:
            c.poly([(x + step * 0.15, 0.3), (x + step * 0.5, 0.05), (x + step * 0.85, 0.3)], tip)


@painter("watch", 1.0)
def _watch(c, arg):
    """Your wristwatch: the time you'd read off it."""
    try:
        hh, mm = (int(v) for v in arg.split(":"))
    except Exception:
        hh, mm = 12, 0
    c.rect(0.38, 0.0, 0.62, 1.0, (80, 56, 36, 255))
    c.ell(0.1, 0.1, 0.9, 0.9, (150, 140, 110, 255))
    c.ell(0.16, 0.16, 0.84, 0.84, (232, 226, 206, 255))
    for k in range(12):
        a = k / 12 * 2 * math.pi
        c.line([(0.5 + 0.28 * math.sin(a), 0.5 - 0.28 * math.cos(a)), (0.5 + 0.32 * math.sin(a), 0.5 - 0.32 * math.cos(a))],
               INK, 0.025)
    ah = ((hh % 12) + mm / 60) / 12 * 2 * math.pi
    am = mm / 60 * 2 * math.pi
    c.line([(0.5, 0.5), (0.5 + 0.18 * math.sin(ah), 0.5 - 0.18 * math.cos(ah))], BLACK, 0.05)
    c.line([(0.5, 0.5), (0.5 + 0.28 * math.sin(am), 0.5 - 0.28 * math.cos(am))], BLACK, 0.03)


@painter("sky", 1.6)
def _sky(c, arg):
    """The sky as you see it: how light it is, where the sun or the moon is, the weather."""
    bits = arg.split("|")
    light = float(bits[0]) if bits and bits[0] else 1.0
    wx = bits[1] if len(bits) > 1 else "clear"
    sun = float(bits[2]) if len(bits) > 2 and bits[2] else 0.5          # 0 rising .. 1 setting
    top = tuple(int(a + (b - a) * light) for a, b in zip((14, 16, 30), (90, 130, 180))) + (255,)
    low = tuple(int(a + (b - a) * light) for a, b in zip((30, 26, 30), (190, 170, 120))) + (255,)
    for k in range(8):
        f = k / 7
        c.rect(0.0, f * 0.84, 1.6, f * 0.84 + 0.12, tuple(int(t + (l - t) * f) for t, l in zip(top[:3], low[:3])) + (255,))
    if wx in ("clear", "overcast") or light < 0.15:
        x = 0.15 + 1.3 * sun
        y = 0.75 - 0.55 * math.sin(math.pi * sun)
        if light > 0.2:
            c.ell(x - 0.12, y - 0.12, x + 0.12, y + 0.12, (255, 226, 120, 255))
        else:
            c.ell(x - 0.09, y - 0.09, x + 0.09, y + 0.09, (220, 220, 200, 255))
            c.ell(x - 0.05, y - 0.11, x + 0.11, y + 0.05, top)
    if wx in ("overcast", "rain", "snow", "fog", "sandstorm"):
        g = int(90 + 120 * light)
        cl = (g, g, g + 6, 235) if wx != "sandstorm" else (190, 160, 110, 235)
        for x0, y0 in ((0.1, 0.1), (0.55, 0.05), (0.95, 0.14), (0.35, 0.22)):
            c.ell(x0, y0, x0 + 0.6, y0 + 0.3, cl)
    if wx == "rain":
        for k in range(9):
            x = 0.1 + k * 0.17
            c.line([(x, 0.45), (x - 0.06, 0.7)], (150, 170, 200, 255), 0.02)
    if wx == "snow":
        for k in range(12):
            x, y = 0.08 + (k * 0.37) % 1.45, 0.42 + (k * 0.23) % 0.4
            c.ell(x - 0.02, y - 0.02, x + 0.02, y + 0.02, WHITE)
    if wx == "fog":
        c.rect(0.0, 0.3, 1.6, 0.9, (200, 200, 196, 150))
    c.rect(0.0, 0.84, 1.6, 1.0, (40, 44, 30, 255) if light > 0.3 else (14, 16, 12, 255))           # the treeline


@painter("pointer", 1.0)
def _pointer(c, arg):
    """Which way: a compass needle if you've got one, else the hand your leader pointed with."""
    bits = arg.split("|")
    try:
        ang = math.radians(float(bits[0]))
    except Exception:
        ang = 0.0
    kind = bits[1] if len(bits) > 1 else "hand"
    dx, dy = math.sin(ang), -math.cos(ang)
    if kind == "compass":
        c.ell(0.05, 0.05, 0.95, 0.95, (60, 58, 48, 255))
        c.ell(0.12, 0.12, 0.88, 0.88, (222, 216, 196, 255))
        c.text(0.5, 0.22, "N", INK, 0.2)
        px, py = -dy, dx
        c.poly([(0.5 + dx * 0.36, 0.5 + dy * 0.36), (0.5 + px * 0.08, 0.5 + py * 0.08),
                (0.5 - px * 0.08, 0.5 - py * 0.08)], RED)
        c.poly([(0.5 - dx * 0.3, 0.5 - dy * 0.3), (0.5 + px * 0.08, 0.5 + py * 0.08),
                (0.5 - px * 0.08, 0.5 - py * 0.08)], INK)
    else:
        # the way your leader pointed: roughly that way (no bearing without a compass)
        px, py = -dy, dx
        col = (245, 215, 110, 255)
        c.line([(0.5 - dx * 0.4, 0.5 - dy * 0.4), (0.5 + dx * 0.12, 0.5 + dy * 0.12)], col, 0.14)
        c.poly([(0.5 + dx * 0.44, 0.5 + dy * 0.44), (0.5 + dx * 0.08 + px * 0.26, 0.5 + dy * 0.08 + py * 0.26),
                (0.5 + dx * 0.08 - px * 0.26, 0.5 + dy * 0.08 - py * 0.26)], col)


@painter("man", 0.6)
def _man(c, arg):
    """One of your section, as he looks from here."""
    col = {"ok": (150, 200, 140, 255), "hurt": (220, 200, 90, 255), "wounded": (240, 120, 60, 255),
           "down": (240, 70, 60, 255), "dead": (110, 50, 44, 255), "pinned": (200, 160, 220, 255)}.get(arg, (140, 140, 130, 255))
    if arg in ("down", "dead"):
        c.rect(0.02, 0.72, 0.5, 0.9, col, r=0.03)
        c.ell(0.46, 0.68, 0.58, 0.88, col)
        if arg == "dead":
            c.line([(0.25, 0.3), (0.25, 0.62)], col, 0.05)
            c.line([(0.14, 0.4), (0.36, 0.4)], col, 0.05)
        return
    c.ell(0.2, 0.05, 0.4, 0.25, col)
    c.rect(0.16, 0.27, 0.44, 0.62, col, r=0.03)
    c.rect(0.17, 0.62, 0.28, 0.98, col)
    c.rect(0.32, 0.62, 0.43, 0.98, col)


@painter("emblem", 1.4)
def _emblem(c, arg):
    """Your army's mark, as it's painted on its vehicles."""
    n = arg
    if n in ("usa",):
        c.ell(0.2, 0.0, 1.2, 1.0, (40, 50, 90, 255))
        _star(c, 0.7, 0.5, 0.42, WHITE)
    elif n in ("uk", "canada", "australia", "newzealand", "india"):
        for r, col in ((0.5, (40, 60, 140, 255)), (0.34, WHITE), (0.18, (190, 40, 40, 255))):
            c.ell(0.7 - r, 0.5 - r, 0.7 + r, 0.5 + r, col)
    elif n in ("ussr",):
        _star(c, 0.7, 0.52, 0.48, (200, 30, 30, 255))
    elif n in ("germany",):
        c.rect(0.56, 0.02, 0.84, 0.98, WHITE)                                                      # the Balkenkreuz:
        c.rect(0.26, 0.36, 1.14, 0.64, WHITE)                                                      # black, edged white
        c.rect(0.62, 0.08, 0.78, 0.92, BLACK)
        c.rect(0.32, 0.42, 1.08, 0.58, BLACK)
    elif n in ("japan",):
        c.rect(0.1, 0.1, 1.3, 0.9, WHITE)
        c.ell(0.45, 0.25, 0.95, 0.75, (200, 30, 30, 255))
    elif n in ("italy",):
        for r, col in ((0.46, (40, 140, 60, 255)), (0.3, WHITE), (0.14, (200, 40, 40, 255))):
            c.ell(0.7 - r, 0.5 - r, 0.7 + r, 0.5 + r, col)
    elif n in ("france",):
        for r, col in ((0.46, (200, 40, 40, 255)), (0.3, WHITE), (0.14, (40, 60, 150, 255))):
            c.ell(0.7 - r, 0.5 - r, 0.7 + r, 0.5 + r, col)
    elif n in ("poland",):
        c.rect(0.3, 0.1, 1.1, 0.9, (200, 30, 30, 255))
        c.rect(0.3, 0.1, 0.7, 0.5, WHITE)
        c.rect(0.7, 0.5, 1.1, 0.9, WHITE)
    elif n in ("finland",):
        c.rect(0.2, 0.15, 1.2, 0.85, WHITE)
        c.rect(0.2, 0.42, 1.2, 0.58, (40, 70, 150, 255))
        c.rect(0.5, 0.15, 0.66, 0.85, (40, 70, 150, 255))
    elif n in ("hungary",):
        c.poly([(0.3, 0.1), (1.1, 0.1), (0.7, 0.9)], (200, 40, 40, 255))
        c.poly([(0.43, 0.2), (0.97, 0.2), (0.7, 0.72)], WHITE)
        c.poly([(0.56, 0.3), (0.84, 0.3), (0.7, 0.56)], (40, 140, 60, 255))
    elif n in ("romania",):
        for r, col in ((0.46, (40, 60, 150, 255)), (0.3, (230, 200, 40, 255)), (0.14, (200, 40, 40, 255))):
            c.ell(0.7 - r, 0.5 - r, 0.7 + r, 0.5 + r, col)
    elif n in ("china",):
        c.ell(0.2, 0.0, 1.2, 1.0, (40, 60, 150, 255))
        c.ell(0.5, 0.3, 0.9, 0.7, WHITE)
    else:
        c.ell(0.3, 0.1, 1.1, 0.9, (120, 120, 110, 255))


def _star(c, cx, cy, r, col):
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.4
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    c.poly(pts, col)


# ============================================================================ the log: what kind of news it is
@painter("log:*", 1.1)
def _logsign(c, arg):
    a = arg
    if a == "sound":                                                                               # an ear
        c.arc(0.2, 0.08, 0.9, 0.92, 200, 90, (170, 170, 210, 255), 0.1)
        c.arc(0.38, 0.3, 0.72, 0.64, 180, 70, (170, 170, 210, 255), 0.07)
    elif a == "radio":                                                                             # a handset
        c.line([(0.25, 0.2), (0.85, 0.8)], (140, 220, 140, 255), 0.14)
        c.ell(0.1, 0.05, 0.42, 0.37, (140, 220, 140, 255))
        c.ell(0.7, 0.65, 1.02, 0.97, (140, 220, 140, 255))
    elif a == "shout":                                                                             # a speech bubble
        c.ell(0.08, 0.1, 1.02, 0.72, (240, 240, 170, 255))
        c.poly([(0.3, 0.6), (0.2, 0.95), (0.5, 0.66)], (240, 240, 170, 255))
    elif a in ("hurt", "hit"):                                                                     # a drop of blood
        col = (255, 70, 70, 255) if a == "hurt" else (255, 140, 100, 255)
        c.poly([(0.55, 0.05), (0.8, 0.55), (0.3, 0.55)], col)
        c.ell(0.3, 0.35, 0.8, 0.95, col)
    elif a == "death":                                                                             # a cross
        c.rect(0.47, 0.05, 0.63, 0.95, (255, 60, 60, 255))
        c.rect(0.25, 0.28, 0.85, 0.42, (255, 60, 60, 255))
    elif a == "good":                                                                              # a tick
        c.line([(0.15, 0.55), (0.45, 0.85), (0.95, 0.15)], (140, 240, 140, 255), 0.14)
    elif a == "warn":                                                                              # a triangle
        c.poly([(0.55, 0.05), (1.05, 0.95), (0.05, 0.95)], (255, 200, 60, 255))
        c.rect(0.5, 0.35, 0.6, 0.7, BLACK)
        c.rect(0.5, 0.78, 0.6, 0.88, BLACK)
    elif a == "think":                                                                             # a thought
        for x, y, r in ((0.6, 0.35, 0.3), (0.25, 0.75, 0.1), (0.1, 0.92, 0.06)):
            c.ell(x - r, y - r, x + r, y + r, (175, 165, 140, 255))
    elif a == "combat":                                                                            # a muzzle flash
        pts = []
        for k in range(12):
            ang = k * math.pi / 6
            r = 0.45 if k % 2 == 0 else 0.18
            pts.append((0.55 + r * math.cos(ang), 0.5 + r * math.sin(ang)))
        c.poly(pts, (230, 200, 160, 255))
    else:
        c.ell(0.4, 0.35, 0.7, 0.65, (120, 120, 110, 255))


@painter("sense:*", 1.0)
def _sense(c, arg):
    """The headings of how you are: heat and cold, breath, load, nerves."""
    a = arg
    if a == "cold":
        for k in range(3):
            ang = k * math.pi / 3
            dx, dy = 0.42 * math.cos(ang), 0.42 * math.sin(ang)
            c.line([(0.5 - dx, 0.5 - dy), (0.5 + dx, 0.5 + dy)], (170, 200, 255, 255), 0.08)
    elif a == "hot":
        c.ell(0.28, 0.28, 0.72, 0.72, (255, 200, 80, 255))
        for k in range(8):
            ang = k * math.pi / 4
            c.line([(0.5 + 0.3 * math.cos(ang), 0.5 + 0.3 * math.sin(ang)),
                    (0.5 + 0.45 * math.cos(ang), 0.5 + 0.45 * math.sin(ang))], (255, 200, 80, 255), 0.06)
    elif a == "mild":
        c.rect(0.42, 0.08, 0.58, 0.72, (200, 196, 180, 255), r=0.08)
        c.ell(0.32, 0.62, 0.68, 0.96, (200, 80, 60, 255))
        c.rect(0.46, 0.4, 0.54, 0.75, (200, 80, 60, 255))
    elif a == "breath":
        c.ell(0.1, 0.25, 0.46, 0.95, (220, 150, 150, 255))
        c.ell(0.54, 0.25, 0.9, 0.95, (220, 150, 150, 255))
        c.rect(0.45, 0.05, 0.55, 0.45, (200, 190, 180, 255))
    elif a == "load":
        _pack(c, "")
    elif a == "nerves":
        c.ell(0.1, 0.15, 0.55, 0.6, (210, 60, 60, 255))
        c.ell(0.45, 0.15, 0.9, 0.6, (210, 60, 60, 255))
        c.poly([(0.12, 0.45), (0.88, 0.45), (0.5, 0.95)], (210, 60, 60, 255))
    elif a == "blood":
        _logsign(c, "hurt")


@painter("how:*", 1.3)
def _how(c, arg):
    """How an order reached you."""
    a = arg
    if a in ("shouted", "told you"):
        _logsign(c, "shout")
    elif a in ("by runner", "a runner"):                                                           # a running man
        m = (120, 124, 84, 255)
        c.ell(0.62, 0.02, 0.8, 0.2, m)
        c.poly([(0.55, 0.22), (0.78, 0.22), (0.7, 0.55), (0.48, 0.55)], m)
        c.line([(0.55, 0.55), (0.3, 0.75), (0.2, 0.98)], m, 0.08)
        c.line([(0.62, 0.55), (0.85, 0.78), (1.05, 0.72)], m, 0.08)
        c.line([(0.6, 0.3), (0.35, 0.4)], m, 0.07)
        c.line([(0.72, 0.3), (0.95, 0.4)], m, 0.07)
        c.rect(0.9, 0.3, 1.1, 0.44, PAPER)                                                         # the message
    elif a in ("on the radio", "the radio", "the battalion net"):
        _thing(c, "radio")
    elif a in ("written orders", "a warrant", "liberty card", "detailed at the guardroom"):
        _paper(c, 4, stamp=RED)
    elif a == "briefing":
        _thing(c, "map")
    elif a == "the fire direction centre's numbers":
        c.rect(0.1, 0.1, 1.2, 0.9, PAPER)
        for k, t in enumerate(("AZ 1600", "QE 0320", "CH 3")):
            c.text(0.65, 0.25 + k * 0.25, t, INK, 0.2)
    else:
        _paper(c, 3)


# ============================================================================ the war map: a map sheet, in ink
MAP_PAPER = (214, 204, 170, 255)
MAP_INK = (96, 80, 58, 255)
MAP_GREEN = (110, 140, 90, 255)
MAP_WATER = (110, 150, 180, 255)


def _terrain_aspect(arg, pw, ph):
    return pw / max(1, ph)


@painter("terrain", _terrain_aspect)
def _terrain(c, arg):
    """One sector of the map sheet: its ground in the conventions of a 1940s map, and who holds it in grease
    pencil.  arg: biome|control (ours/theirs/none/unknown)|sketch (a pencilled sketch, not a printed map)."""
    bits = arg.split("|")
    biome = bits[0]
    ctl = bits[1] if len(bits) > 1 else "none"
    sketch = len(bits) > 2 and bits[2] == "1"
    W = c.width
    import random
    import zlib
    rng = random.Random(zlib.crc32(("|".join([biome] + bits[3:4])).encode()))     # (its own layout, every session)
    paper = MAP_PAPER if not sketch else (226, 222, 204, 255)
    c.rect(0.0, 0.0, W, 1.0, paper)
    if ctl == "unknown":
        if not sketch:
            c.line([(W - 0.005, 0.0), (W - 0.005, 1.0)], (120, 108, 84, 255), 0.012)
            c.line([(0.0, 0.995), (W, 0.995)], (120, 108, 84, 255), 0.012)
        return
    ink = MAP_INK if not sketch else (120, 120, 120, 255)
    green = MAP_GREEN if not sketch else (140, 140, 140, 255)
    if biome == "sea":
        c.rect(0.0, 0.0, W, 1.0, (120, 160, 190, 255))
        for k in range(4):
            y = 0.2 + k * 0.2
            c.arc(0.1 + (k % 2) * 0.3, y, 0.5 + (k % 2) * 0.3, y + 0.15, 200, 340, (220, 230, 240, 255), 0.02)
        return
    if biome in ("forest", "jungle", "bocage"):
        n = 18 if biome != "bocage" else 0
        for _ in range(n):
            x, y = rng.uniform(0.05, W - 0.05), rng.uniform(0.1, 0.9)
            c.ell(x - 0.06, y - 0.06, x + 0.06, y + 0.06, green)
        if biome == "bocage":
            for k in range(4):
                x = W * (k + 0.5) / 4 + rng.uniform(-0.1, 0.1)
                c.line([(x, 0.05), (x + rng.uniform(-0.15, 0.15), 0.95)], green, 0.04)
            for k in range(2):
                y = 0.33 + k * 0.33
                c.line([(0.05, y), (W - 0.05, y + rng.uniform(-0.1, 0.1))], green, 0.04)
    elif biome in ("farmland", "steppe"):
        for k in range(6):
            y = 0.12 + k * 0.15
            c.line([(0.1, y), (W - 0.1, y)], (170, 160, 110, 255) if biome == "farmland" else (190, 180, 130, 255), 0.015)
    elif biome in ("hills", "mountain", "abbey", "volcanic"):
        for k in range(3 if biome == "hills" else 4):
            r = 0.15 + k * 0.12
            c.ell(W / 2 - r * 1.6, 0.5 - r, W / 2 + r * 1.6, 0.5 + r, None, outline=(150, 110, 70, 255), width=0.015)
        if biome == "abbey":
            c.rect(W / 2 - 0.12, 0.35, W / 2 + 0.12, 0.6, ink)
    elif biome == "marsh":
        for _ in range(10):
            x, y = rng.uniform(0.1, W - 0.1), rng.uniform(0.15, 0.85)
            c.line([(x - 0.08, y), (x + 0.08, y)], MAP_WATER, 0.02)
            c.line([(x, y), (x, y - 0.06)], green, 0.015)
    elif biome in ("desert", "beach"):
        for _ in range(8):
            x, y = rng.uniform(0.1, W - 0.1), rng.uniform(0.15, 0.85)
            c.arc(x - 0.12, y - 0.04, x + 0.12, y + 0.08, 200, 340, (180, 150, 100, 255), 0.015)
        if biome == "beach":
            c.rect(0.0, 0.7, W, 1.0, (120, 160, 190, 255))
    if biome in ("village", "town", "city_ruins", "factory"):
        n = {"village": 5, "town": 10, "city_ruins": 14, "factory": 6}[biome]
        for _ in range(n):
            x, y = rng.uniform(0.1, W - 0.25), rng.uniform(0.15, 0.75)
            s = rng.uniform(0.08, 0.14) if biome != "factory" else rng.uniform(0.14, 0.24)
            c.rect(x, y, x + s, y + s * 0.8, ink if biome != "city_ruins" else (130, 100, 80, 255))
        c.line([(0.0, 0.85), (W, 0.8)], (170, 60, 40, 255), 0.03)                                  # the road
    # who holds it: a grease-pencil wash and a line round it (ours blue, theirs red)
    col = {"ours": (60, 90, 170), "theirs": (180, 50, 40)}.get(ctl)
    if col is not None:
        c.rect(0.0, 0.0, W, 1.0, col + (46,))
        c.rect(0.03, 0.04, W - 0.03, 0.96, None, outline=col + (170,), width=0.035)
    c.line([(W - 0.005, 0.0), (W - 0.005, 1.0)], (120, 108, 84, 255), 0.012)                    # the grid
    c.line([(0.0, 0.995), (W, 0.995)], (120, 108, 84, 255), 0.012)


# ============================================================================ the sight picture
@painter("sight", 1.0)
def _sight(c, arg):
    """Through your sights: the man, as much of him as shows over his cover, and the spread of your rounds
    - a circle the size the chance of a hit says (a sure thing: tight on him; a prayer: all round him)."""
    bits = arg.split("|")
    stance = bits[0] if bits else "0"
    cov = int(bits[1]) if len(bits) > 1 else 0
    p = max(0.02, min(0.97, int(bits[2]) / 100 if len(bits) > 2 else 0.3))
    scope = len(bits) > 3 and bits[3] == "1"
    light = float(bits[4]) if len(bits) > 4 else 1.0
    sky = tuple(int(a + (b - a) * light) for a, b in zip((20, 22, 32), (150, 170, 190))) + (255,)
    ground = tuple(int(a + (b - a) * light) for a, b in zip((16, 18, 12), (110, 104, 70))) + (255,)
    c.ell(0.0, 0.0, 1.0, 1.0, sky)
    c.poly([(0.0, 0.58), (1.0, 0.56), (1.0, 1.0), (0.0, 1.0)], ground)
    man = (60, 62, 44, 255)
    cx, base = 0.5, 0.66
    if stance == "2":
        w, h = 0.3, 0.08
        c.rect(cx - w / 2, base - h, cx + w / 2, base, man, r=0.02)
        c.ell(cx - w / 2 - 0.05, base - h - 0.02, cx - w / 2 + 0.03, base, man)
    elif stance == "1":
        w, h = 0.12, 0.3
        c.rect(cx - 0.06, base - h + 0.07, cx + 0.06, base, man, r=0.02)
        c.ell(cx - 0.045, base - h, cx + 0.045, base - h + 0.08, man)
    else:
        w, h = 0.12, 0.48
        c.rect(cx - 0.06, base - h + 0.08, cx + 0.06, base, man, r=0.02)
        c.ell(cx - 0.045, base - h, cx + 0.045, base - h + 0.09, man)
    if cov > 0:
        ch_ = h * min(0.9, cov / 100 * 0.9)
        c.rect(cx - 0.3, base - ch_, cx + 0.3, base + 0.02, (96, 84, 60, 255), r=0.02)          # his cover
    area = w * h * (1 - min(0.9, cov / 100 * 0.8))
    r = math.sqrt(area / (math.pi * p))
    my = base - h / 2
    c.ell(cx - r, my - r, cx + r, my + r, (220, 60, 40, 60), outline=(240, 90, 60, 220), width=0.012)
    if scope:
        c.line([(0.0, 0.5), (1.0, 0.5)], BLACK, 0.008)
        c.line([(0.5, 0.5), (0.5, 1.0)], BLACK, 0.012)
    else:
        c.poly([(0.47, 1.0), (0.47, my + 0.02), (0.5, my - 0.01), (0.53, my + 0.02), (0.53, 1.0)], BLACK)  # the post
    c.ell(-0.02, -0.02, 1.02, 1.02, None, outline=(10, 10, 10, 255), width=0.06)                # the aperture


# ============================================================================ the recruit: who you'll be
UNIFORM = {"usa": (112, 104, 70), "uk": (122, 104, 70), "canada": (122, 104, 70), "australia": (130, 110, 72),
           "newzealand": (122, 104, 70), "india": (140, 120, 80), "germany": (98, 100, 86), "ussr": (132, 122, 82),
           "japan": (138, 124, 72), "italy": (112, 114, 92), "france": (142, 122, 80), "poland": (112, 112, 82),
           "china": (98, 108, 116), "finland": (104, 104, 92), "hungary": (122, 112, 82), "romania": (112, 106, 82)}
NATION_HELMET = {"usa": "m1", "uk": "brodie", "canada": "brodie", "australia": "brodie", "newzealand": "brodie",
                 "india": "brodie", "germany": "stahlhelm", "finland": "stahlhelm", "china": "stahlhelm",
                 "hungary": "stahlhelm", "ussr": "ssh40", "japan": "type90", "italy": "it", "france": "adrian",
                 "poland": "adrian", "romania": "adrian"}
ROLE_ARMS = {"rifleman": "gun:rifle", "squad_leader": "gun:smg|wood", "lmg_gunner": "gun:lmg",
             "lmg_assistant": "gun:rifle", "smg_gunner": "gun:smg|steel", "at_soldier": "gun:at_launcher",
             "medic": "", "surgeon": "", "chaplain": "", "officer": "gun:pistol", "intel": "gun:pistol",
             "radioman": "gun:carbine", "sniper": "gun:sniper", "engineer": "gun:carbine", "mortarman": "gun:mortar",
             "artilleryman": "gun:carbine", "hmg_gunner": "gun:hmg", "hmg_assistant": "gun:rifle",
             "flamethrower": "gun:flamer", "tank_crew": "gun:smg|steel", "agent": "gun:pistol", "partisan": "gun:rifle",
             "quartermaster": "gun:pistol", "politruk": "gun:pistol"}


@painter("recruit", 0.62)
def _recruit(c, arg):
    """You, as the paybook would have you: your army's cloth and helmet, the arm your job is issued - or a
    shape with a question mark, while it's left to chance."""
    from PIL import Image
    bits = arg.split("|")
    nat = bits[0] if bits else ""
    role = bits[1] if len(bits) > 1 else ""
    unknown = nat not in UNIFORM
    cloth = UNIFORM.get(nat, (70, 70, 66)) + (255,)
    dark = tuple(max(0, v - 26) for v in cloth[:3]) + (255,)
    skin = (190, 150, 120, 255) if not unknown else (90, 90, 86, 255)
    c.ell(0.23, 0.11, 0.39, 0.27, skin)                                                            # head
    c.rect(0.19, 0.27, 0.43, 0.6, cloth, r=0.03)                                                   # tunic
    c.rect(0.19, 0.5, 0.43, 0.54, (60, 46, 30, 255) if not unknown else dark)                      # belt
    c.rect(0.2, 0.6, 0.3, 0.92, dark)                                                              # legs
    c.rect(0.32, 0.6, 0.42, 0.92, dark)
    c.rect(0.19, 0.9, 0.31, 0.97, (40, 30, 22, 255))                                              # boots
    c.rect(0.31, 0.9, 0.43, 0.97, (40, 30, 22, 255))
    c.rect(0.12, 0.28, 0.19, 0.56, cloth, r=0.03)                                                  # arms
    c.rect(0.43, 0.28, 0.5, 0.56, cloth, r=0.03)
    if role in ("medic", "surgeon") and not unknown:
        c.rect(0.12, 0.33, 0.19, 0.39, WHITE)                                                      # the armband
        c.rect(0.145, 0.33, 0.165, 0.39, RED)
    if unknown:
        c.text(0.31, 0.44, "?", (150, 150, 140, 255), 0.18)
        return
    hel = "tank" if role == "tank_crew" else "peaked" if role in ("officer", "intel", "politruk", "surgeon") else \
        "cap" if role in ("agent", "partisan") else NATION_HELMET.get(nat, "m1")
    hw = paint(f"helmet:x|{hel}", int(c.s * 0.26 / SS * 1.5) + 2, int(c.s * 0.26 / SS) + 2)
    if hw is not None:
        im = Image.fromarray(hw).resize((int(c.s * 0.26 * 1.5), int(c.s * 0.26)), Image.LANCZOS)
        x, y = c.p(0.31 - 0.195, 0.03)
        c.img.alpha_composite(im, (int(x), int(y)))
    arms = ROLE_ARMS.get(role, "gun:rifle")
    if arms:
        big = arms in ("gun:hmg", "gun:mortar", "gun:flamer")
        L = 0.5 if not big else 0.36
        gw, gh = int(c.s * L * 2.2 / SS) + 2, int(c.s * L * 0.42 / SS) + 2
        ga = paint(arms, gw, gh)
        if ga is not None:
            im = Image.fromarray(ga).resize((int(c.s * L * 2.2), int(c.s * L * 0.42)), Image.LANCZOS)
            im = im.rotate(35 if not big else 0, expand=True, resample=Image.BICUBIC)
            x, y = c.p(0.05 if not big else 0.32, 0.26 if not big else 0.62)
            c.img.alpha_composite(im, (max(0, int(x)), max(0, int(y))))


# ============================================================================ your vehicle, from above, with its crew
SEAT_AT = {"driver": (0.74, 0.3), "gunner": (0.46, 0.34), "commander": (0.36, 0.5), "loader": (0.46, 0.66),
           "radio": (0.74, 0.7), "bow_mg": (0.74, 0.7), "hull_mg": (0.74, 0.7), "mg": (0.3, 0.72),
           "aa_mg": (0.3, 0.28)}


@painter("vehicle", 2.0)
def _vehicle(c, arg):
    """Your vehicle from above, and where each man sits: you (yellow), manned (green), empty (red)."""
    from PIL import Image
    from .sprites import paint_vehicle
    bits = arg.split("|")
    vclass, camo = (bits + ["tank", ""])[:2]
    seats = bits[2].split(",") if len(bits) > 2 and bits[2] else []
    try:
        hull = paint_vehicle(vclass, camo, 0, "hull")
        tur = paint_vehicle(vclass, camo, 0, "turret")
    except Exception:
        return
    W, H = c.W - 2 * c.ox, c.s
    him = Image.fromarray(np.ascontiguousarray(hull))
    box = him.split()[3].point(lambda v: 255 if v > 90 else 0).getbbox()     # (the hull, not its shadow)
    if box is None:
        return
    k = min(W * 0.96 / (box[2] - box[0]), H * 0.96 / (box[3] - box[1]))
    left = c.ox + (W - (box[2] - box[0]) * k) / 2 - box[0] * k
    top = c.oy + (H - (box[3] - box[1]) * k) / 2 - box[1] * k
    for a in (hull, tur):
        if a is None:
            continue
        im = Image.fromarray(np.ascontiguousarray(a))
        im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
        c.img.alpha_composite(im, (int(left), int(top)))
    # the seats, on the hull as it's drawn
    hx0, hy0 = left + box[0] * k, top + box[1] * k
    hw, hh = (box[2] - box[0]) * k, (box[3] - box[1]) * k
    r = max(2, hh * 0.1)
    for s_ in seats:
        name, _, st = s_.partition(":")
        fx, fy = SEAT_AT.get(name, (0.3, 0.5))
        col = {"you": (255, 220, 90, 255), "on": (140, 220, 140, 255)}.get(st, (220, 70, 60, 255))
        px, py = hx0 + fx * hw, hy0 + fy * hh
        c.d.ellipse([px - r, py - r, px + r, py + r], fill=col, outline=BLACK, width=max(1, int(r * 0.25)))


# ============================================================================ unit symbols, as on a 1940s staff map
@painter("unit:*", 1.6)
def _unit(c, arg):
    """The conventional sign for a unit (the box and what's in it), framed in the colour of how it's doing."""
    bits = arg.split("|")
    kind = bits[0]
    col = _hex(bits[1]) if len(bits) > 1 else (200, 200, 200, 255)
    ink = (20, 20, 20, 255)
    c.rect(0.05, 0.1, 1.55, 0.9, (236, 230, 210, 255), outline=col, width=0.1)
    if kind in ("rifle", "assault", "inf", "mg", "sniper", "recon", "raid", "commando", "para"):
        c.line([(0.1, 0.15), (1.5, 0.85)], ink, 0.07)                                              # infantry: X
        c.line([(0.1, 0.85), (1.5, 0.15)], ink, 0.07)
        if kind == "mg":
            c.line([(0.4, 0.5), (1.2, 0.5)], ink, 0.07)
    elif kind in ("tank", "armour"):
        c.ell(0.3, 0.3, 1.3, 0.7, None, outline=ink, width=0.07)                                   # armour: the track
    elif kind in ("mortar", "arty", "artillery", "gun"):
        c.ell(0.65, 0.35, 0.95, 0.65, ink)                                                         # artillery: a dot
    elif kind in ("atgun", "at"):
        c.poly([(0.2, 0.85), (0.8, 0.2), (1.4, 0.85)], None, outline=ink, width=0.07)             # anti-tank: the ^
    elif kind in ("hq", "staff"):
        c.line([(0.1, 0.9), (0.1, 0.0)], ink, 0.07)
        c.rect(0.1, 0.12, 1.0, 0.5, ink)                                                           # the flag
    elif kind in ("aid",):
        c.rect(0.7, 0.2, 0.9, 0.8, (180, 30, 30, 255))
        c.rect(0.45, 0.4, 1.15, 0.6, (180, 30, 30, 255))
    elif kind in ("engineer",):
        c.rect(0.4, 0.35, 1.2, 0.65, None, outline=ink, width=0.07)
        c.line([(0.8, 0.35), (0.8, 0.65)], ink, 0.07)
    elif kind in ("supply", "rear"):
        c.line([(0.1, 0.8), (1.5, 0.8)], ink, 0.07)
    else:
        c.line([(0.1, 0.15), (1.5, 0.85)], ink, 0.07)
