"""Font tilesets: TrueType rasterised at the exact cell size, or the classic bitmap."""
from __future__ import annotations

import os
import unicodedata

import numpy as np
import tcod

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
TTF_REGULAR = os.path.join(ASSETS, "DejaVuSansMono.ttf")
TTF_BOLD = os.path.join(ASSETS, "DejaVuSansMono-Bold.ttf")
BITMAP = os.path.join(ASSETS, "terminal10x16_gs_ro.png")

# box drawing: (up, down, left, right) weights: 0 none, 1 light, 2 double
BOX = {
    "─": (0, 0, 1, 1), "│": (1, 1, 0, 0), "┌": (0, 1, 0, 1), "┐": (0, 1, 1, 0), "└": (1, 0, 0, 1),
    "┘": (1, 0, 1, 0), "├": (1, 1, 0, 1), "┤": (1, 1, 1, 0), "┬": (0, 1, 1, 1), "┴": (1, 0, 1, 1),
    "┼": (1, 1, 1, 1), "═": (0, 0, 2, 2), "║": (2, 2, 0, 0), "╔": (0, 2, 0, 2), "╗": (0, 2, 2, 0),
    "╚": (2, 0, 0, 2), "╝": (2, 0, 2, 0), "╠": (2, 2, 0, 2), "╣": (2, 2, 2, 0), "╦": (0, 2, 2, 2),
    "╩": (2, 0, 2, 2), "╬": (2, 2, 2, 2), "╒": (0, 1, 0, 2), "╓": (0, 2, 0, 1), "╕": (0, 1, 2, 0),
    "╖": (0, 2, 1, 0), "╘": (1, 0, 0, 2), "╙": (2, 0, 0, 1), "╛": (1, 0, 2, 0), "╜": (2, 0, 1, 0),
    "╞": (1, 1, 0, 2), "╟": (2, 2, 0, 1), "╡": (1, 1, 2, 0), "╢": (2, 2, 1, 0), "╤": (0, 1, 2, 2),
    "╥": (0, 2, 1, 1), "╧": (1, 0, 2, 2), "╨": (2, 0, 1, 1), "╪": (1, 1, 2, 2), "╫": (2, 2, 1, 1),
}
BLOCKS = "█▀▄▌▐░▒▓"

# bold letters live at a private codepoint above the ordinary ones: print bold("Tab") and it comes out in
# DejaVu Sans Mono Bold (with the bitmap font, the ordinary glyphs stand in)
BOLD_BASE = 0xF0000


def bold(s: str) -> str:
    return "".join(chr(BOLD_BASE + ord(c)) if 33 <= ord(c) < 127 else c for c in s)


def codepoints() -> set[int]:
    cps = set(int(c) for c in tcod.tileset.CHARMAP_CP437)
    cps |= set(range(32, 127))
    cps |= set(range(0xA0, 0x250))          # Latin-1, Latin Extended A/B (ł, ę, ō, ș, ő ...)
    cps |= {0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2026, 0x2022, 0x25AE, 0x2192,
            0x2190, 0x2191, 0x2193, 0x2195, 0x2194, 0x2605, 0x2606, 0x2715, 0x2713, 0x2716,
            0x25CF, 0x25CB, 0x25C6, 0x25C7, 0x2020, 0x2021, 0x266A, 0x221E, 0x2300, 0x2302,
            0x25B2, 0x25BC, 0x25C4, 0x25BA, 0x2588, 0x2196, 0x2197, 0x2198, 0x2199}
    cps |= set(ord(c) for c in BOX)
    cps |= set(ord(c) for c in BLOCKS)
    return cps


def _draw_box(ch: str, w: int, h: int) -> np.ndarray:
    a = np.zeros((h, w), np.uint8)
    up, down, left, right = BOX[ch]
    t = max(1, int(round(h / 16)))
    gap = max(2, t * 2)
    cx, cy = w // 2, h // 2

    def vline(x0, y0, y1):
        a[max(0, y0):max(0, y1), max(0, x0):max(0, x0 + t)] = 255

    def hline(y0, x0, x1):
        a[max(0, y0):max(0, y0 + t), max(0, x0):max(0, x1)] = 255

    # centre offsets for double lines
    def offs(weight):
        return [0] if weight == 1 else [-gap // 2 - t // 2, gap // 2 + (t + 1) // 2 - t]

    vx = cx - t // 2
    hy = cy - t // 2
    v_weight = max(up, down)
    h_weight = max(left, right)
    for o in (offs(up) if up else []):
        end = hy + t + (gap // 2 + t if h_weight == 2 else 0) if (left or right) else cy + 1
        vline(vx + o, 0, max(end, cy + t))
    for o in (offs(down) if down else []):
        start = hy - (gap // 2 + t if h_weight == 2 else 0) if (left or right) else cy
        vline(vx + o, min(start, cy - 0), h)
    for o in (offs(left) if left else []):
        end = vx + t + (gap // 2 + t if v_weight == 2 else 0) if (up or down) else cx + 1
        hline(hy + o, 0, max(end, cx + t))
    for o in (offs(right) if right else []):
        start = vx - (gap // 2 + t if v_weight == 2 else 0) if (up or down) else cx
        hline(hy + o, min(start, cx), w)
    return a


def _draw_block(ch: str, w: int, h: int) -> np.ndarray:
    a = np.zeros((h, w), np.uint8)
    if ch == "█":
        a[:] = 255
    elif ch == "▀":
        a[: h // 2] = 255
    elif ch == "▄":
        a[h // 2:] = 255
    elif ch == "▌":
        a[:, : w // 2] = 255
    elif ch == "▐":
        a[:, w // 2:] = 255
    else:
        # shades: a dot texture a few pixels across so it reads as a pattern at any size
        p = max(1, h // 12)
        yy, xx = np.mgrid[0:h, 0:w]
        cell = ((xx // p) + (yy // p) * 3)
        if ch == "░":
            a[(cell % 4) == 0] = 255
        elif ch == "▒":
            a[((xx // p) + (yy // p)) % 2 == 0] = 255
        else:
            a[(cell % 4) != 0] = 255
    return a


def fit_font_size(path: str, cw: int, ch: int) -> int:
    from PIL import ImageFont
    lo, hi = 4, 400
    best = 4
    while lo <= hi:
        mid = (lo + hi) // 2
        f = ImageFont.truetype(path, mid)
        asc, desc = f.getmetrics()
        adv = f.getlength("M")
        if asc + desc <= ch * 1.04 and adv <= cw + 0.25:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def ttf_tileset(cw: int, ch: int, bold: bool = False) -> tcod.tileset.Tileset:
    from PIL import Image, ImageDraw, ImageFont
    path = TTF_BOLD if bold and os.path.exists(TTF_BOLD) else TTF_REGULAR
    size = fit_font_size(path, cw, ch)
    font = ImageFont.truetype(path, size)
    asc, desc = font.getmetrics()
    adv = font.getlength("M")
    xoff = (cw - adv) / 2.0
    yoff = (ch - (asc + desc)) / 2.0
    ts = tcod.tileset.Tileset(cw, ch)
    rgba = np.zeros((ch, cw, 4), np.uint8)
    rgba[..., :3] = 255
    for cp in sorted(codepoints()):
        c = chr(cp)
        if c in BOX:
            alpha = _draw_box(c, cw, ch)
        elif c in BLOCKS:
            alpha = _draw_block(c, cw, ch)
        elif cp == 32:
            alpha = np.zeros((ch, cw), np.uint8)
        else:
            img = Image.new("L", (cw, ch), 0)
            d = ImageDraw.Draw(img)
            try:
                d.text((xoff, yoff), c, font=font, fill=255)
            except Exception:
                continue
            alpha = np.asarray(img, np.uint8)
            if alpha.max() == 0:
                continue
        tile = rgba.copy()
        tile[..., 3] = alpha
        ts.set_tile(cp, tile)
    if os.path.exists(TTF_BOLD):
        bfont = ImageFont.truetype(TTF_BOLD, fit_font_size(TTF_BOLD, cw, ch))
        basc, bdesc = bfont.getmetrics()
        bxoff = (cw - bfont.getlength("M")) / 2.0
        byoff = (ch - (basc + bdesc)) / 2.0
        for cp in range(33, 127):
            img = Image.new("L", (cw, ch), 0)
            ImageDraw.Draw(img).text((bxoff, byoff), chr(cp), font=bfont, fill=255)
            tile = rgba.copy()
            tile[..., 3] = np.asarray(img, np.uint8)
            ts.set_tile(BOLD_BASE + cp, tile)
    return ts


def bitmap_tileset() -> tcod.tileset.Tileset:
    ts = tcod.tileset.load_tilesheet(BITMAP, 16, 16, tcod.tileset.CHARMAP_CP437)
    # accented letters the CP437 sheet lacks fall back to their base letter
    cp437 = list(tcod.tileset.CHARMAP_CP437)
    index = {c: i for i, c in enumerate(cp437)}
    for cp in range(0xA0, 0x250):
        if cp in index:
            continue
        base = unicodedata.normalize("NFKD", chr(cp))[:1]
        if base and ord(base) in index:
            i = index[ord(base)]
            ts.remap(cp, i % 16, i // 16)
    for cp in range(33, 127):
        if cp in index:
            ts.remap(BOLD_BASE + cp, index[cp] % 16, index[cp] // 16)
    for cp, sub in ((0x25AE, "█"), (0x2014, "-"), (0x2013, "-"), (0x2018, "'"), (0x2019, "'"),
                    (0x201C, '"'), (0x201D, '"'), (0x2026, "."), (0x2605, "*"), (0x2196, "▲"), (0x2197, "▲"),
                    (0x2198, "▼"), (0x2199, "▼"),
                    # map glyphs the sheet lacks (tiles.py): water tower, telegraph pole, bamboo, radar dish,
                    # Tobruk pit, wayside cross, war memorial
                    (0x0166, "T"), (0x01C2, "┼"), (0x00A6, "|"), (0x00A4, "o"), (0x00D8, "Φ"), (0x2020, "+"),
                    (0x2021, "╪")):
        i = index.get(ord(sub))
        if i is not None:
            ts.remap(cp, i % 16, i // 16)
    return ts


def make_tileset(kind: str, cw: int, ch: int) -> tcod.tileset.Tileset:
    if kind == "ttf":
        try:
            return ttf_tileset(cw, ch)
        except Exception:
            pass
    return bitmap_tileset()
