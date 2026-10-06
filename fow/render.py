"""Drawing: map, entities, diegetic HUD, anchored popups, effects."""
from __future__ import annotations

import math
import textwrap

import numpy as np
import tcod

from . import tiles as T
from .constants import (SCREEN_H, SCREEN_W, DGREY, ENEMY_COLOR, FRIEND_COLOR, GREY, LGREY, LOG_H, MSG_COLORS, PANEL_W,
                        PLAYER_COLOR, SCREEN_H, SCREEN_W, UI_BG, UI_DIM, UI_FRAME, UI_HI, UI_SEL_BG,
                        UI_TEXT, VIEW_H, VIEW_W, WHITE)
from .data.nations import NATIONS
from .senses import daylight, player_can_see_actor

SQUAD_COLOR = (170, 255, 240)


EDGE_M = 14          # how far past the map's edge the view may look into the next sector


def view_window(m, cam, VW, VH):
    """The part of the view that's on this map: source origin, destination offset, size."""
    sx0, sy0 = max(0, cam.x0), max(0, cam.y0)
    ox, oy = sx0 - cam.x0, sy0 - cam.y0
    w = max(0, min(VW - ox, m.w - sx0))
    h = max(0, min(VH - oy, m.h - sy0))
    return sx0, sy0, ox, oy, w, h


def beyond_parts(game, cam, VW, VH):
    """The neighbouring sectors' ground showing in the view, as (dest slices, t, var, seen, lit)."""
    m = game.map
    s = getattr(game, "sector", None)
    if getattr(game, "__dict__", {}).get("domain") == "aboard":
        return []                  # at sea, the sea goes on (the deck plan already has it round her)
    if s is None or not hasattr(game, "neighbour_terrain") or (0 <= cam.x0 and cam.x0 + VW <= m.w
                                                               and 0 <= cam.y0 and cam.y0 + VH <= m.h):
        return []
    out = []
    for ndx in (-1, 0, 1):
        for ndy in (-1, 0, 1):
            if ndx == ndy == 0:
                continue
            wx0, wy0 = ndx * m.w, ndy * m.h
            ax0, ax1 = max(wx0, cam.x0), min(wx0 + m.w, cam.x0 + VW)
            ay0, ay1 = max(wy0, cam.y0), min(wy0 + m.h, cam.y0 + VH)
            if ax0 >= ax1 or ay0 >= ay1:
                continue
            ter = game.neighbour_terrain(s.x + ndx, s.y + ndy)
            n, k = ax1 - ax0, ay1 - ay0
            if ter == "sea" or ter is None:
                t = np.full((n, k), T.ID["deep"], dtype=m.t.dtype)
                var = np.zeros((n, k), dtype=np.int32)
            else:
                t = ter[0][ax0 - wx0:ax1 - wx0, ay0 - wy0:ay1 - wy0]
                var = ter[1][ax0 - wx0:ax1 - wx0, ay0 - wy0:ay1 - wy0] if ter[1] is not None else \
                    np.zeros((n, k), dtype=np.int32)
            # you see across where you've seen up to the edge; it's clearer where the edge is in view now
            xs = np.clip(np.arange(ax0, ax1), 0, m.w - 1)
            ys = np.clip(np.arange(ay0, ay1), 0, m.h - 1)
            seen = m.explored[np.ix_(xs, ys)]
            lit = m.visible[np.ix_(xs, ys)]
            # and less the further you look
            dx = np.maximum(0, np.maximum(-np.arange(ax0, ax1), np.arange(ax0, ax1) - (m.w - 1)))
            dy = np.maximum(0, np.maximum(-np.arange(ay0, ay1), np.arange(ay0, ay1) - (m.h - 1)))
            far = np.maximum(dx[:, None], dy[None, :])
            seen = seen & (far <= EDGE_M)
            dest = (slice(ax0 - cam.x0, ax1 - cam.x0), slice(ay0 - cam.y0, ay1 - cam.y0))
            out.append((dest, t, var, seen, lit, far))
    return out


def draw_beyond(con, game, cam, VW, VH):
    """The ground next door, grey with distance: you can see it, you're not there."""
    for dest, t, var, seen, lit, far in beyond_parts(game, cam, VW, VH):
        glyph = T.GLYPHS[t, var % T.MAXV]
        f = np.where(lit, 0.72, 0.5)[..., None] * (1 - np.clip(far / (EDGE_M * 2.2), 0, 0.4))[..., None]
        fg = T.FG[t].astype(np.float32)
        bg = T.BG[t].astype(np.float32)
        gray = fg.mean(axis=2, keepdims=True)
        fg = (fg * 0.5 + gray * 0.5) * f + np.array([10, 14, 26])
        bgg = bg.mean(axis=2, keepdims=True)
        bg = (bg * 0.5 + bgg * 0.5) * f * 0.75 + np.array([4, 6, 14])
        glyph = np.where(seen, glyph, ord(" "))
        fg = np.where(seen[..., None], fg, 0)
        bg = np.where(seen[..., None], bg, 0)
        con.rgb["ch"][dest] = glyph
        con.rgb["fg"][dest] = np.clip(fg, 0, 255).astype(np.uint8)
        con.rgb["bg"][dest] = np.clip(bg, 0, 255).astype(np.uint8)
    # a battle next door: smoke by day, the glow of fires and gun flashes by night
    night = game.is_night() if hasattr(game, "is_night") else False
    for mk in game.__dict__.get("front_marks") or ():
        sx, sy = cam.to_screen(mk["x"], mk["y"])
        if 0 <= sx < VW and 0 <= sy < VH:
            put(con, sx, sy, "░" if not night else "▒", (150, 146, 140) if not night else (210, 110, 50))


class Camera:
    """Maps world tiles to the map view (map cells) and to UI text cells."""

    def __init__(self):
        self.x0 = 0
        self.y0 = 0
        self.vw = VIEW_W
        self.vh = VIEW_H
        self.tx = 1.0          # text cells per map cell (1 in ASCII mode)
        self.ty = 1.0
        self.fx0 = None        # the true (fractional) left/top edge of the view, when scrolling smoothly
        self.fy0 = None

    def set_float(self, fx0, fy0):
        """Put the view's top-left corner at a fractional world position (smooth scrolling)."""
        self.fx0, self.fy0 = fx0, fy0
        self.x0, self.y0 = math.floor(fx0), math.floor(fy0)

    def frac(self):
        if self.fx0 is None:
            return 0.0, 0.0
        return self.fx0 - self.x0, self.fy0 - self.y0

    def world_at(self, ftx, fty):
        """Text-cell position -> world tile."""
        if self.fx0 is None:
            return math.floor(ftx / self.tx) + self.x0, math.floor(fty / self.ty) + self.y0
        return math.floor(self.fx0 + ftx / self.tx), math.floor(self.fy0 + fty / self.ty)

    def configure(self, vw, vh, tx=1.0, ty=1.0):
        self.vw, self.vh, self.tx, self.ty = vw, vh, tx, ty

    def _clamp(self, game):
        """Keep the view on the map - give or take a strip of the ground next door (see draw_beyond)."""
        m = game.map
        e = EDGE_M if getattr(game, "sector", None) is not None and getattr(game, "pow", None) is None and \
            game.__dict__.get("domain") != "aboard" else 0
        self.x0 = max(-e, min(max(-e, m.w - self.vw + e), self.x0))
        self.y0 = max(-e, min(max(-e, m.h - self.vh + e), self.y0))

    def focus(self, game, fx=None, fy=None):
        p = game.player
        if fx is None:
            if p.vehicle is not None:
                fx, fy = p.vehicle.x, p.vehicle.y
            else:
                fx, fy = p.x, p.y
        self.x0 = fx - self.vw // 2
        self.y0 = fy - self.vh // 2
        self._clamp(game)

    def ensure_visible(self, game, x, y, margin=4):
        """Scroll only as much as needed to keep (x, y) on screen."""
        mx = min(margin, self.vw // 4)
        my = min(margin, self.vh // 4)
        if x < self.x0 + mx:
            self.x0 = x - mx
        elif x >= self.x0 + self.vw - mx:
            self.x0 = x - self.vw + mx + 1
        if y < self.y0 + my:
            self.y0 = y - my
        elif y >= self.y0 + self.vh - my:
            self.y0 = y - self.vh + my + 1
        self._clamp(game)

    def to_screen(self, x, y):
        return x - self.x0, y - self.y0

    def to_text(self, x, y):
        if self.fx0 is not None:
            return int((x - self.fx0 + 0.5) * self.tx), int((y - self.fy0 + 0.5) * self.ty)
        sx, sy = x - self.x0, y - self.y0
        if self.tx == 1.0 and self.ty == 1.0:
            return sx, sy
        return int((sx + 0.5) * self.tx), int((sy + 0.5) * self.ty)

    def to_map(self, sx, sy):
        return sx + self.x0, sy + self.y0

    def on_screen(self, x, y):
        sx, sy = x - self.x0, y - self.y0
        return 0 <= sx < self.vw and 0 <= sy < self.vh


# ====================================================================== map

def _view(con):
    """The part of a console the map occupies: all of a map console, the map area of the UI console."""
    if con.width == SCREEN_W and con.height == SCREEN_H:
        return VIEW_W, VIEW_H
    return con.width, con.height


def draw_map(con, game, cam, frame=0, going=False):
    m = game.map
    VW, VH = _view(con)
    x0, y0, ox, oy, w, h = view_window(m, cam, VW, VH)
    # the whole view blank first (the map console lives from frame to frame): then the ground next door,
    # then this map over it
    con.rgb["ch"][:VW, :VH] = ord(" ")
    con.rgb["fg"][:VW, :VH] = 0
    con.rgb["bg"][:VW, :VH] = 0
    draw_beyond(con, game, cam, VW, VH)
    if w <= 0 or h <= 0:
        return
    t = m.seen_t(slice(x0, x0 + w), slice(y0, y0 + h))      # (out of sight: as you last saw it)
    var = m.var[x0:x0 + w, y0:y0 + h]
    glyph = T.GLYPHS[t, var % T.MAXV].copy()
    jit = ((var % 17) - 8).astype(np.float32)[..., None]
    fg = T.FG[t].astype(np.float32) + jit * 1.6
    bg = T.BG[t].astype(np.float32) + jit * 0.6
    from .relief import shade
    sh = shade(m)
    if sh is not None:
        # the lie of the land: slopes lit from the north-west, contour lines, the tops a touch lighter
        s = sh[x0:x0 + w, y0:y0 + h][..., None]
        bg *= s
        fg *= 0.5 + 0.5 * s
    vis = m.visible[x0:x0 + w, y0:y0 + h]
    exp = m.explored[x0:x0 + w, y0:y0 + h]
    # decals
    blood = m.blood[x0:x0 + w, y0:y0 + h].astype(np.float32)[..., None] / 255.0
    bg = bg * (1 - blood * 0.6) + np.array([110, 0, 0], np.float32) * blood * 0.6
    fg = fg * (1 - blood * 0.3) + np.array([160, 20, 20], np.float32) * blood * 0.3
    scorch = m.scorch[x0:x0 + w, y0:y0 + h].astype(np.float32)[..., None]
    bg *= (1 - scorch * 0.35)
    fg *= (1 - scorch * 0.2)
    # fire
    fire = m.fire[x0:x0 + w, y0:y0 + h]
    burning = (fire > 0) & vis
    if burning.any():
        n = int(burning.sum())
        rnd = np.random.default_rng(game.turn * 7 + frame)
        flick = rnd.integers(0, 3, n)
        glyph[burning] = np.array([ord("^"), ord("*"), ord("≈")])[flick]
        cols = np.array([[255, 80, 20], [255, 170, 30], [255, 230, 90]], np.float32)
        fg[burning] = cols[rnd.integers(0, 3, n)]
        bg[burning] = np.array([120, 30, 0], np.float32)
    # smoke
    smoke = m.smoke[x0:x0 + w, y0:y0 + h]
    sm = np.clip(smoke / 2.5, 0, 1)[..., None] * vis[..., None]
    smoke_col = np.array([150, 150, 145], np.float32)
    bg = bg * (1 - sm * 0.8) + smoke_col * 0.5 * sm * 0.8
    fg = fg * (1 - sm * 0.7) + smoke_col * sm * 0.7
    thick = (smoke > 1.6) & vis
    glyph[thick] = ord("▒")
    # light
    d = daylight(game)
    if d < 0.95:
        lit = game.lit[x0:x0 + w, y0:y0 + h] if game.lit is not None else np.zeros_like(vis)
        base = 0.35 + 0.65 * d
        lf = np.where(lit, np.maximum(base, 0.85), base).astype(np.float32)[..., None]
        # moonlight blue shift
        fg = fg * lf + (1 - lf) * np.array([10, 15, 40], np.float32)
        bg = bg * lf
    # weather tint
    if game.weather == "fog":
        fg = fg * 0.8 + 40
        bg = bg * 0.8 + 30
    elif game.weather in ("snow", "blizzard"):
        fg = fg * 0.9 + 20
    elif game.weather == "sandstorm":
        fg = fg * 0.75 + np.array([60, 45, 20])
        bg = bg * 0.75 + np.array([50, 35, 10])
    # memory: explored but not visible
    mem = exp & ~vis
    gray = fg.mean(axis=2, keepdims=True)
    fg = np.where(mem[..., None], gray * 0.38 + np.array([6, 8, 14]), fg)
    bgg = bg.mean(axis=2, keepdims=True)
    bg = np.where(mem[..., None], bgg * 0.22, bg)
    if going:
        # reading the ground (X): red where there's no way through, amber where it's slow
        from .going import tint
        gcol, ga = tint(game, slice(x0, x0 + w), slice(y0, y0 + h))
        ga = np.where(ga >= 0.5, 0.75, ga * 1.3)[..., None]      # the glyphs are small: tint the cell hard
        bg = bg * (1 - ga) + gcol * ga * 0.85
        fg = fg * (1 - ga * 0.3) + gcol * ga * 0.3
    unk = ~exp
    glyph[unk] = ord(" ")
    fg[unk] = 0
    bg[unk] = 0
    con.rgb["ch"][ox:ox + w, oy:oy + h] = glyph
    con.rgb["fg"][ox:ox + w, oy:oy + h] = np.clip(fg, 0, 255).astype(np.uint8)
    con.rgb["bg"][ox:ox + w, oy:oy + h] = np.clip(bg, 0, 255).astype(np.uint8)
    from .weather import particles
    for x, y, ch, col in particles(game, cam):
        put(con, *cam.to_screen(x, y), ch, col)


def put(con, sx, sy, ch, fg=None, bg=None):
    VW, VH = _view(con)
    if 0 <= sx < VW and 0 <= sy < VH:
        if isinstance(ch, str):
            ch = ord(ch)
        con.rgb["ch"][sx, sy] = ch
        if fg is not None:
            con.rgb["fg"][sx, sy] = fg
        if bg is not None:
            con.rgb["bg"][sx, sy] = bg


ITEM_PRIORITY = {"corpse": 0, "gun": 1, "explosive": 2, "grenade": 2, "melee": 3, "tool": 4,
                 "medical": 4, "ammo": 5, "armor": 6}


def draw_entities(con, game, cam, frame=0):
    m = game.map
    p = game.player
    # items
    for (x, y), items in m.items.items():
        if not items or not cam.on_screen(x, y) or not m.visible[x, y]:
            continue
        top = min(items, key=lambda i: ITEM_PRIORITY.get(i.t.kind, 9))
        sx, sy = cam.to_screen(x, y)
        col = top.t.color
        glyph = top.t.glyph
        if top.data and top.data.get("live") is not None and (frame // 2) % 2 == 0:
            col = (255, 60, 60)
            glyph = "*"
        put(con, sx, sy, glyph, col)
    # known mines
    for (x, y), mn in m.mines.items():
        if p.side in mn.known and cam.on_screen(x, y) and m.visible[x, y]:
            sx, sy = cam.to_screen(x, y)
            put(con, sx, sy, "^", (230, 60, 60))
    # vehicles and big guns: the whole hull, the type letter on it, the barrel sticking out
    from .footprint import FACING_VEC
    for v in game.vehicles:
        if v.dead:
            continue
        cells = v.cells()
        seen = p.vehicle is v or any(m.in_bounds(cx, cy) and m.visible[cx, cy] for cx, cy in cells)
        if not seen or not any(cam.on_screen(cx, cy) for cx, cy in cells):
            continue
        if p.vehicle is v:
            col = PLAYER_COLOR
        elif v.side == p.side:
            col = FRIEND_COLOR
        else:
            col = ENEMY_COLOR
        if v.abandoned or v.crew <= 0:
            col = tuple(int(c * 0.55) for c in col)
        hull_bg = tuple(int(c * 0.32) for c in col) if not v.burning else (130, 40, 0)
        hull_fg = tuple(int(c * 0.7) for c in col)
        fill = "▒" if v.vt.vtype not in ("atgun", "fieldgun", "aagun") else "·"
        for cx, cy in cells:
            if cam.on_screen(cx, cy):
                sx, sy = cam.to_screen(cx, cy)
                put(con, sx, sy, fill, hull_fg, hull_bg)
        if v.vt.main:
            fx, fy = FACING_VEC[(v.turret if v.vt.turret and not v.static else v.facing) % 8]
            mine = set(cells)
            bx, by = v.x, v.y
            for k in range(1, 6):
                bx, by = v.x + fx * k, v.y + fy * k
                if (bx, by) in mine:
                    continue
                if cam.on_screen(bx, by) and (bx, by) not in game.soldier_at:
                    sx, sy = cam.to_screen(bx, by)
                    put(con, sx, sy, "─" if fy == 0 else "│" if fx == 0 else ("\\" if fx == fy else "/"), col)
                break
        if cam.on_screen(v.x, v.y):
            sx, sy = cam.to_screen(v.x, v.y)
            put(con, sx, sy, v.vt.glyph, col, hull_bg)
        # At text resolution an occupied area gets one crew marker. Keep the type
        # letter readable; sprites resolve individual men within that same tile.
        from .vehicle_figures import occupants
        marked = set()
        for figure in occupants(v, m.climate, game.turn):
            cx, cy = v.x + round(figure.x), v.y + round(figure.y)
            if (cx, cy) == v.pos or (cx, cy) in marked or (cx, cy) in game.soldier_at:
                continue
            if cam.on_screen(cx, cy) and m.in_bounds(cx, cy) and (p.vehicle is v or m.visible[cx, cy]):
                sx, sy = cam.to_screen(cx, cy)
                put(con, sx, sy, "@", col, hull_bg if (cx, cy) in cells else None)
                marked.add((cx, cy))
    # soldiers
    for a in game.actors:
        if not a.alive or a.vehicle is not None or not cam.on_screen(a.x, a.y):
            continue
        if not player_can_see_actor(game, a):
            continue
        sx, sy = cam.to_screen(a.x, a.y)
        bg = None
        if a is p:
            col = PLAYER_COLOR
        elif a.ai.get("civilian"):
            col = (220, 200, 155)
        elif a.side == p.side:
            col = SQUAD_COLOR if (p.squad is not None and a.squad is p.squad) else FRIEND_COLOR
        else:
            col = ENEMY_COLOR
        ch = "@"
        if a.state == "surrendered":
            col, bg = (240, 240, 240), (90, 90, 90)
        elif a.downed:
            col = tuple(int(c * 0.6) for c in col)
            bg = (90, 0, 0)
        elif a.stance == 2 and a is not p:
            col = tuple(int(c * 0.8) for c in col)
        put(con, sx, sy, ch, col, bg)
    # aircraft
    for ac in game.support.aircraft:
        x, y = int(ac.x), int(ac.y)
        if cam.on_screen(x, y):
            sx, sy = cam.to_screen(x, y)
            col = FRIEND_COLOR if ac.side == p.side else ENEMY_COLOR
            put(con, sx, sy, ac.glyph, (255, 255, 255), None)
            # shadow on the ground, trailing
            shx, shy = sx - int(round(ac.dx * 2)), sy - int(round(ac.dy * 2)) + 1
            put(con, shx, shy, "·", col)


def draw_aboard(con, game, cam):
    """Aboard: what the lookouts see, by bearing from the bow (the bow is to the right of the plan),
    and the ship's state along the top."""
    from . import aboard as AB
    W = int(cam.vw * cam.tx)
    H = int(cam.vh * cam.ty)
    line = AB.status_line(game)
    if line:
        con.print(1, 0, f" {line} "[:W - 2], fg=(230, 220, 180), bg=(20, 26, 34))
    cx, cy = W / 2.0, H / 2.0
    used = set()
    rows = {}
    if (game.aboard or {}).get("kind") == "ship" and not AB.on_open_deck(game):
        return                          # below decks you see steel, not the sea
    for name, rel, km, kind, hostile in sorted(AB.contacts(game), key=lambda c: c[2])[:10]:
        a = math.radians(rel)
        dx, dy = math.cos(a), math.sin(a)             # 0 = ahead (right), 90 = starboard (down)
        t = min((W / 2 - 2) / max(1e-6, abs(dx)), (H / 2 - 2) / max(1e-6, abs(dy)))
        ex, ey = int(cx + dx * t), int(cy + dy * t)
        while (ex, ey) in used and ey < H - 2:
            ey += 1
        used.add((ex, ey))
        col = (255, 110, 90) if hostile else (140, 190, 255)
        glyph = "✈" if kind == "air" else "▲"
        lab = f"{glyph} {name} {km:.1f} km"
        lx = ex - len(lab) if ex > cx else ex + 1
        lx = max(0, min(W - len(lab), lx))
        ly = ey
        # find a row where the label doesn't sit on another one
        for _ in range(6):
            spans = rows.get(ly, [])
            if all(lx + len(lab) < a or lx > b for a, b in spans):
                break
            ly = ly + 1 if ly < H - 2 else ly - 6
        rows.setdefault(ly, []).append((lx, lx + len(lab)))
        put(con, ex, ey, arrow_for(dx, dy), (20, 20, 20), col)
        con.print(lx, ly, lab[:W], fg=col, bg=(16, 20, 28))


def draw_overlays(con, game, cam, ui, sprites=False):
    """Text drawn over the map: sound guesses, map marks, speech bubbles."""
    m = game.map
    p = game.player
    if game.__dict__.get("domain") == "aboard":
        draw_aboard(con, game, cam)

    def edge_text(x, y):
        sx, sy = cam.to_screen(x, y)
        ex = max(0, min(cam.vw - 1, sx))
        ey = max(0, min(cam.vh - 1, sy))
        arrow = "►" if sx >= cam.vw else "◄" if sx < 0 else "▼" if sy >= cam.vh else "▲"
        return cam.to_text(ex + cam.x0, ey + cam.y0), arrow

    # sound markers (only where you can't see)
    if p.body.deaf <= 0:
        for snd in game.sound_marks:
            if cam.on_screen(snd.x, snd.y):
                if m.in_bounds(snd.x, snd.y) and m.visible[snd.x, snd.y] and snd.kind not in ("explosion", "shell"):
                    continue
                tx, ty = cam.to_text(snd.x, snd.y)
                for i, ch in enumerate(snd.text):
                    put(con, tx + i, ty, ch, snd.color)
            else:
                (tx, ty), arrow = edge_text(snd.x, snd.y)
                put(con, tx, ty, arrow, snd.color)
    # objective markers: only if you carry a map (grease pencil marks)
    if p.has_tool("map") is not None:
        for i, o in enumerate(m.objectives):
            letter = "ABCDEFGH"[i]
            col = (140, 200, 255) if o.owner == p.side else (255, 140, 120) if o.owner else (230, 220, 120)
            if cam.on_screen(o.x, o.y):
                tx, ty = cam.to_text(o.x, o.y)
                if sprites or (game.turn // 2) % 3 != 0 or not m.visible[o.x, o.y]:
                    put(con, tx, ty, letter, col, (30, 30, 30))
            else:
                (tx, ty), _ = edge_text(o.x, o.y)
                put(con, tx, ty, letter, col, (20, 20, 20))
    draw_order_pointer(con, game, cam)
    # where your head is when you lean out of cover
    pk = getattr(p, "peek", None)
    if pk and p.vehicle is None and cam.on_screen(p.x + pk[0], p.y + pk[1]):
        tx, ty = cam.to_text(p.x + pk[0], p.y + pk[1])
        put(con, tx, ty, "°", (255, 240, 170))
    # speech bubbles (only from people you can actually see)
    for a in game.actors:
        if a.shout is None or a.shout[1] < game.turn or not a.alive or a.vehicle is not None or a is p:
            continue
        if not cam.on_screen(a.x, a.y) or not player_can_see_actor(game, a):
            continue
        text = a.shout[0]
        if not text:
            continue
        tx, ty = cam.to_text(a.x, a.y)
        col = (250, 250, 200) if a.side == p.side else (255, 180, 170)
        bw = len(text) + 2
        bx = max(0, min(VIEW_W - bw, tx - bw // 2))
        above = ty >= 3
        by = ty - 2 if above else ty + 2
        con.print(bx, by, f" {text} ", fg=(20, 20, 20), bg=col)
        put(con, tx, ty - 1 if above else ty + 1, "," if above else "'", col)
    # auto-travel destination
    if ui is not None and getattr(ui, "travel_dest", None) is not None and cam.on_screen(*ui.travel_dest) and not sprites:
        sx, sy = cam.to_text(*ui.travel_dest)
        put(con, sx, sy, "X", (255, 255, 120))


ARROWS = {(0, -1): "↑", (1, -1): "↗", (1, 0): "→", (1, 1): "↘", (0, 1): "↓", (-1, 1): "↙", (-1, 0): "←",
          (-1, -1): "↖"}
ORDER_COL = (245, 215, 110)


def arrow_for(dx, dy):
    if dx == 0 and dy == 0:
        return "·"
    ang = math.atan2(dy, dx)
    o = int(round(ang / (math.pi / 4))) % 8
    vec = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)][o]
    return ARROWS[vec]


def draw_player_pointer(con, game, cam):
    """When the view is elsewhere: an arrow at its edge pointing back to you (Home to return)."""
    p = game.player
    px, py = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
    if cam.on_screen(px, py) or not p.alive:
        return
    W, H = min(int(cam.vw * cam.tx), VIEW_W), min(int(cam.vh * cam.ty), VIEW_H)
    sx, sy = W // 2, H // 2
    tx, ty = cam.to_text(px, py)
    dx, dy = tx - sx, ty - sy
    t = 1.0
    for v, lo, hi, dv in ((sx, 1, W - 2, dx), (sy, 1, H - 2, dy)):
        if dv > 0:
            t = min(t, (hi - v) / dv)
        elif dv < 0:
            t = min(t, (lo - v) / dv)
    ex, ey = max(0, min(W - 1, int(round(sx + dx * t)))), max(0, min(H - 1, int(round(sy + dy * t))))
    col = (120, 230, 255)
    put(con, ex, ey, arrow_for(px - (cam.fx0 or cam.x0) - cam.vw / 2, py - (cam.fy0 or cam.y0) - cam.vh / 2),
        (10, 10, 20), col)
    text = "you - Home"
    lx = ex - len(text) - 1 if ex > W // 2 else ex + 2
    lx = max(0, min(W - len(text), lx))
    ly = ey if 0 < ey < H - 1 else (ey + 1 if ey == 0 else ey - 1)
    con.print(lx, ly, text, fg=col)


def draw_order_pointer(con, game, cam):
    """Where your orders point: a grease-pencil X on the spot, or an arrow at the edge of your view."""
    ptr = game.order_pointer()
    p = game.player
    if ptr is None or not p.body.conscious:
        return
    x, y, label = ptr
    px, py = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
    d = math.hypot(x - px, y - py)
    yd = int(round(d * 2.2 / 50.0) * 50) or 50
    how_far = f"{yd} yd" if (p.has_tool("map") or p.has_tool("compass")) else "that way"
    text = f"{label} - {how_far}"
    W, H = int(cam.vw * cam.tx), int(cam.vh * cam.ty)
    W, H = min(W, VIEW_W), min(H, VIEW_H)
    # the exact spot: marked on your map - or where you can see the place he pointed at; otherwise just the way
    known = p.has_tool("map") is not None or (game.map.in_bounds(x, y) and game.map.visible[x, y])
    if cam.on_screen(x, y) and known:
        tx, ty = cam.to_text(x, y)
        put(con, tx, ty, "X", ORDER_COL, (70, 55, 15))
        lx = max(0, min(W - len(text) - 1, tx - len(text) // 2))
        ly = ty - 1 if ty > 1 else ty + 1
        if 0 <= ly < H:
            con.print(lx, ly, text, fg=ORDER_COL)
        return
    # off screen: where the line from the middle of the view to it leaves the view
    sx, sy = W // 2, H // 2
    tx, ty = cam.to_text(x, y)
    dx, dy = tx - sx, ty - sy
    t = 1.0
    for v, lo, hi, dv in ((sx, 1, W - 2, dx), (sy, 1, H - 2, dy)):
        if dv > 0:
            t = min(t, (hi - v) / dv)
        elif dv < 0:
            t = min(t, (lo - v) / dv)
    ex = int(round(sx + dx * t))
    ey = int(round(sy + dy * t))
    ex = max(0, min(W - 1, ex))
    ey = max(0, min(H - 1, ey))
    put(con, ex, ey, arrow_for(x - px, y - py), (20, 20, 20), ORDER_COL)
    # the label sits inside the view, next to the arrow
    lx = ex - len(text) - 1 if ex > W // 2 else ex + 2
    lx = max(0, min(W - len(text), lx))
    ly = ey if 0 < ey < H - 1 else (ey + 1 if ey == 0 else ey - 1)
    con.print(lx, ly, text, fg=ORDER_COL, bg=(25, 22, 12))


def draw_effects(con, game, cam, frame):
    """Animate the shots and blasts of the last turn(s)."""
    for e in game.effects:
        k = e["kind"]
        if k == "tracer":
            pts = tcod.los.bresenham((e["x0"], e["y0"]), (e["x1"], e["y1"]))
            n = len(pts)
            if n < 2:
                continue
            # a moving streak
            head = int(min(n - 1, (frame + 1) * max(3, n // 3)))
            tail = max(1, head - (4 if not e["mg"] else 6))
            dx, dy = e["x1"] - e["x0"], e["y1"] - e["y0"]
            ang = math.atan2(dy, dx)
            ch = "-" if abs(dx) > 2 * abs(dy) else "|" if abs(dy) > 2 * abs(dx) else ("\\" if dx * dy > 0 else "/")
            if e.get("rocket"):
                ch = "*"
            col = (255, 240, 150) if not e["mg"] else (255, 200, 90)
            for i in range(tail, head + 1):
                x, y = int(pts[i][0]), int(pts[i][1])
                if game.map.in_bounds(x, y) and game.map.visible[x, y]:
                    sx, sy = cam.to_screen(x, y)
                    put(con, sx, sy, ch if not e.get("rocket") or i == head else "·", col)
        elif k == "flash":
            if frame == 0:
                sx, sy = cam.to_screen(e["x"], e["y"])
                put(con, sx, sy, "*", (255, 255, 200))
        elif k == "explosion":
            r = e["r"]
            rr = min(r, frame + 1) if r else 0
            cx, cy = e["x"], e["y"]
            cols = [(255, 255, 200), (255, 200, 60), (255, 120, 30), (200, 60, 20)]
            for dx in range(-rr, rr + 1):
                for dy in range(-rr, rr + 1):
                    d = math.hypot(dx, dy)
                    if d > rr + 0.3:
                        continue
                    x, y = cx + dx, cy + dy
                    if not game.map.in_bounds(x, y) or not game.map.visible[x, y]:
                        continue
                    sx, sy = cam.to_screen(x, y)
                    ci = min(3, int(d) + frame // 2)
                    ch = "*" if d < 1 else ("O" if d < rr - 0.5 else "o")
                    put(con, sx, sy, ch, cols[ci], (int(cols[ci][0] * 0.4), int(cols[ci][1] * 0.2), 0))
            if not r:
                sx, sy = cam.to_screen(cx, cy)
                put(con, sx, sy, "*", (255, 220, 120))
        elif k == "splash":
            sx, sy = cam.to_screen(e["x"], e["y"])
            put(con, sx, sy, "≈" if frame % 2 else "*", (220, 240, 255))
        elif k == "flame":
            for i, (x, y) in enumerate(e["pts"][: frame * 3 + 3]):
                if game.map.in_bounds(x, y) and game.map.visible[x, y]:
                    sx, sy = cam.to_screen(x, y)
                    put(con, sx, sy, "*" if i % 2 else "≈", (255, 140 + (i * 17) % 100, 30), (120, 30, 0))
        elif k == "throw":
            pts = tcod.los.bresenham((e["x0"], e["y0"]), (e["x1"], e["y1"]))
            n = len(pts)
            i = min(n - 1, int((frame + 1) * n / 3))
            x, y = int(pts[i][0]), int(pts[i][1])
            if game.map.in_bounds(x, y) and game.map.visible[x, y]:
                sx, sy = cam.to_screen(x, y)
                put(con, sx, sy, "*", (200, 220, 120))


def apply_condition_filters(con, game, flash_red=False):
    """Suppression tunnels your vision; blood loss drains colour; pain flashes red."""
    p = game.player
    VW, VH = _view(con)
    fg = con.rgb["fg"][:VW, :VH].astype(np.float32)
    bg = con.rgb["bg"][:VW, :VH].astype(np.float32)
    sup = p.suppression / 100.0
    if sup > 0.2:
        xs = (np.arange(VW) - VW / 2) / (VW / 2)
        ys = (np.arange(VH) - VH / 2) / (VH / 2)
        r = np.sqrt(xs[:, None] ** 2 + ys[None, :] ** 2)
        inner = 1.05 - sup * 0.8
        f = np.clip(1 - (r - inner) * 2.2 * sup, 0.15, 1.0)[..., None]
        fg *= f
        bg *= f
    lost = max(0.0, (4600 - p.body.blood) / 2200)
    if lost > 0:
        lost = min(0.85, lost)
        g1 = fg.mean(axis=2, keepdims=True)
        g2 = bg.mean(axis=2, keepdims=True)
        fg = fg * (1 - lost) + g1 * lost * 0.8
        bg = bg * (1 - lost) + g2 * lost * 0.8
    if flash_red:
        bg = bg * 0.6 + np.array([90, 0, 0])
    con.rgb["fg"][:VW, :VH] = np.clip(fg, 0, 255).astype(np.uint8)
    con.rgb["bg"][:VW, :VH] = np.clip(bg, 0, 255).astype(np.uint8)


# ====================================================================== panel

DOLL = [
    ("  O  ", {2: "head"}),
    (" /|\\ ", {1: "l_arm", 2: "torso", 3: "r_arm"}),
    (" / \\ ", {1: "l_leg", 3: "r_leg"}),
]


def _book(game):
    """The orders book, worked out once a turn (orders.py)."""
    c = game.__dict__.get("_book_cache")
    if c is None or c[0] != game.turn or c[2] != game.player_orders:
        from .orders import book
        try:
            c = game.__dict__["_book_cache"] = (game.turn, book(game), game.player_orders)
        except Exception:
            import os
            if os.environ.get("FOW_DEBUG"):
                raise
            c = (game.turn, [], game.player_orders)
    return c[1]


def draw_panel(con, game):
    p = game.player
    x0 = VIEW_W
    con.draw_rect(x0, 0, PANEL_W, SCREEN_H, ord(" "), bg=UI_BG)
    for y in range(SCREEN_H):
        con.print(x0, y, "│", fg=(60, 55, 40), bg=UI_BG)
    x = x0 + 2
    wdt = PANEL_W - 3
    y = 0
    con.print(x, y, p.full_name[:wdt], fg=UI_HI, bg=UI_BG)
    y += 1
    from .data.ranks import STARS
    st_ = STARS.get(p.rank, "")
    con.print(x, y, p.role_name[:wdt - len(st_) - 1], fg=UI_DIM, bg=UI_BG)
    if st_:
        con.print(x0 + PANEL_W - 1 - len(st_), y, "★" * len(st_), fg=(240, 210, 110), bg=UI_BG)
    y += 1
    nat = NATIONS[p.nation]["adj"]
    con.print(x, y, f"{nat}"[:wdt], fg=UI_DIM, bg=UI_BG)
    y += 2
    # body doll
    b = p.body
    from . import icons
    pics = icons.on()
    if pics:
        bits = []
        for part in ("head", "torso", "l_arm", "r_arm", "l_leg", "r_leg"):
            _, col = b.part_status(part)
            bl = b.part_bleeding(part)
            code = {"bleeding": "b1", "bleeding badly": "b2", "gushing blood": "b3", "bandaged": "B",
                    "tourniquet": "T"}.get(bl, "")
            bits.append(f"{part}:{icons.hexcol(col)}:{code}")
        icons.pic(x, y, 5, 6, "doll|" + ",".join(bits))
    else:
        for row, (text, parts) in enumerate(DOLL):
            for i, ch in enumerate(text):
                part = parts.get(i)
                col = UI_DIM
                if part:
                    _, col = b.part_status(part)
                    bl = b.part_bleeding(part)
                    if bl and bl not in ("bandaged", "tourniquet") and (game.turn % 2 == 0):
                        col = (255, 30, 30)
                con.print(x + i, y + row, ch, fg=col, bg=UI_BG)
    # part list
    ly = y
    for part, label in (("head", "Head"), ("torso", "Torso"), ("l_arm", "L.arm"), ("r_arm", "R.arm"),
                        ("l_leg", "L.leg"), ("r_leg", "R.leg")):
        st, col = b.part_status(part)
        bl = b.part_bleeding(part)
        txt = f"{label:6}{st}"
        con.print(x + 6, ly, txt[:wdt - 6], fg=col, bg=UI_BG)
        if bl:
            bcol = (255, 60, 60) if bl not in ("bandaged", "tourniquet") else (200, 200, 200)
            con.print(x + 6, ly, "", bg=UI_BG)
            short = {"bleeding": "~", "bleeding badly": "~~", "gushing blood": "~~~", "bandaged": "+",
                     "tourniquet": "T"}[bl]
            con.print(x0 + PANEL_W - 1 - len(short), ly, short, fg=bcol, bg=UI_BG)
        ly += 1
    y = max(y + 4, ly) + 0
    for text, col in b.feel()[:3]:
        for line in textwrap.wrap(text, wdt):
            con.print(x, y, line, fg=col, bg=UI_BG)
            y += 1
    y += 1
    # stance and nerves
    st = {0: "Standing", 1: "Crouching", 2: "Prone"}[p.stance]
    if p.vehicle is not None:
        st = "Inside " + p.vehicle.vt.name
    elif getattr(p, "z", 0):
        from .actions import floor_word
        st += " - " + floor_word(game, p)
    elif game.map.water[p.x, p.y] >= 2:
        st = "Swimming!"
    elif game.map.pos_cover[p.x, p.y] >= 45:
        st += ", dug in"
    if getattr(p, "peek", None) and p.vehicle is None:
        st += ", leaning out"
    if p.vehicle is None and getattr(p, "pace", "walk") != "walk":
        from .pace import effective
        real = effective(p, p.pace, game.turn)
        st += {"run": ", running", "sprint": ", sprinting", "sneak": ", creeping"}.get(real, "") \
            if real != "walk" else f" ({p.pace}: can't)"
    sx = x
    if pics:
        # you, the way you're lying, and what's between you and the nearest trouble
        m = game.map
        if p.vehicle is not None:
            pose = "veh"
        elif m.water[p.x, p.y] >= 2:
            pose = "swim"
        else:
            pose = str(p.stance)
        cov = 0
        if p.vehicle is None:
            cov = int(m.pos_cover[p.x, p.y])
            ec = game.brains[p.side].enemy_center if game.brains.get(p.side) is not None else None
            if ec is not None:
                cov = max(cov, int(m.cover_toward(p.x, p.y, int(ec[0]), int(ec[1]))))
        icons.pic(x, y, 5, 2, f"stance|{pose}|{cov // 10 * 10}")
        sx = x + 6
    con.print(sx, y, st[:wdt - (sx - x)], fg=UI_TEXT, bg=UI_BG)
    y += 1
    if p.vehicle is None and game.map.in_bounds(p.x, p.y):
        # how hidden you are - as you'd judge it yourself (stealth.py)
        from .stealth import exposure_word
        ew, ecol = exposure_word(game, p)
        con.print(sx, y, ew[:wdt - (sx - x)], fg=ecol, bg=UI_BG)
        y += 1
    elif pics:
        y += 1
    sup = p.suppression
    if sup > 70:
        nerves, col = "PINNED DOWN", (255, 60, 60)
    elif sup > 40:
        nerves, col = "Under heavy fire", (255, 140, 60)
    elif sup > 15:
        nerves, col = "Under fire", (240, 200, 90)
    elif p.morale < 25:
        nerves, col = "Shaking", (220, 160, 100)
    else:
        nerves, col = "Steady", (150, 200, 140)
    con.print(x, y, nerves, fg=col, bg=UI_BG)
    bw = p.breath_word()
    if bw:
        y += 1
        bcol = (255, 90, 70) if bw == "Exhausted" else (240, 170, 80) if bw == "Winded" else (220, 210, 140)
        con.print(x, y, bw, fg=bcol, bg=UI_BG)
    from .pace import fatigue_word
    fw, fcol = fatigue_word(p)
    if fw:
        y += 1
        con.print(x, y, fw, fg=fcol, bg=UI_BG)
    if p.vehicle is None:
        # how quickly you can do anything: move, aim, load (moves gained per second)
        y += 1
        spd = p.speed(game.turn)
        why = []
        from .sustain import needs_words
        why.extend(needs_words(p))
        if p.encumbrance(game.turn) < 0.98:
            why.append("load")
        if p.body.speed_mult() < 0.97:
            why.append("hurt")
        if getattr(p, "stamina", 100.0) < 30:
            why.append("blown")
        if "temp" in p.body.__dict__:
            from .thermal import words
            tw, tc = words(p)
            if tw != "Comfortable":
                why.append(tw.split(" -")[0].lower())
        line = f"Speed {spd}" + (f" ({', '.join(why)})" if why else "")
        col = UI_DIM if spd >= 95 else (230, 190, 100) if spd >= 70 else (255, 110, 80)
        con.print(x, y, line[:wdt], fg=col, bg=UI_BG)
    y += 2
    # weapon (diegetic: estimate unless counted)
    if p.vehicle is not None and p.vehicle.player_crewed:
        v = p.vehicle
        con.print(x, y, v.vt.name[:wdt], fg=UI_HI, bg=UI_BG)
        y += 1
        if pics:
            # the vehicle from above, and its crew at their seats
            from . import crew as C
            from .sprites import vehicle_camo, vehicle_class
            seat = C.player_seat(v)
            man = C.manned(v)
            seats = ",".join(f"{st}:{'you' if st == seat else 'on' if st in man else 'off'}" for st in C.stations(v.vt))
            icons.pic(x, y, 12, 3, f"vehicle|{vehicle_class(v.vt)}|{vehicle_camo(v.nation, game.year, game.map.climate)}"
                                   f"|{seats}")
            y += 3
        from .vdamage import damage_list, hatch_user
        dmg = damage_list(v)
        if v.burning:
            dmg.insert(0, "ON FIRE")
        if not dmg:
            con.print(x, y, "no damage"[:wdt], fg=UI_DIM, bg=UI_BG)
            y += 1
        for line in dmg[:5]:
            con.print(x, y, line[:wdt], fg=(240, 90, 60) if line == "ON FIRE" or "immobilised" in line or
                      "out" in line or "dead" in line or "jammed" in line else (230, 170, 110), bg=UI_BG)
            y += 1
        if hatch_user(v) is not None:
            con.print(x, y, ("buttoned up" if v.buttoned else "commander's hatch open")[:wdt], fg=UI_DIM, bg=UI_BG)
            y += 1
        if v.mount:
            ready = "loaded" if v.reload <= 0 else "loading..."
            con.print(x, y, f"{v.mount.name[:wdt]}", fg=UI_TEXT, bg=UI_BG)
            y += 1
            con.print(x, y, f"{ready}  [{v.ammo_choice.upper()}]", fg=(200, 220, 150), bg=UI_BG)
            y += 1
            con.print(x, y, f"AP {v.ap}  HE {v.he}", fg=UI_DIM, bg=UI_BG)
            y += 1
        from . import crew as C
        seat = C.player_seat(v)
        man = C.manned(v)
        con.print(x, y, f"You: {C.name(v.vt, seat)}"[:wdt] if seat else "Passenger", fg=(220, 200, 140), bg=UI_BG)
        y += 1
        cx = x
        for st in C.stations(v.vt):
            tag = C.SHORT.get(st, st)
            col = (240, 220, 120) if st == seat else (150, 190, 140) if st in man else (120, 70, 60)
            if cx + len(tag) > x + wdt:
                break
            con.print(cx, y, tag, fg=col, bg=UI_BG)
            cx += len(tag) + 1
        y += 1
        if v.vt.mgs:
            con.print(x, y, f"MG belts: {v.mg_ammo // 250}", fg=UI_DIM, bg=UI_BG)
            y += 1
        if v.ai.get("hold_fire"):
            con.print(x, y, "HOLD FIRE", fg=(240, 150, 80), bg=UI_BG)
            y += 1
        y += 1
    else:
        w = p.weapon
        if w is None:
            con.print(x, y, "Empty-handed", fg=UI_DIM, bg=UI_BG)
            y += 1
        else:
            wx0 = x
            key = icons.item_key(w) if pics else None
            if key is not None:
                icons.pic(x, y, 7, 2, icons.oriented(key, 7, 2))
                wx0 = x + 8
            nm = w.t.name
            room = wdt - (wx0 - x)
            con.print(wx0, y, nm if len(nm) <= room else nm[: room - 1] + "…", fg=UI_HI, bg=UI_BG)
            y += 1
            if w.t.kind == "gun":
                est = w.ammo_estimate()
                mode = w.mode_name
                col = (255, 80, 80) if est in ("JAMMED", "empty", "spent") else (200, 220, 150)
                line = f"{est}" + (f"  [{mode}]" if len(w.t.modes) > 1 else "")
                if w.heat > 70:
                    line += " HOT"
                con.print(wx0, y, line[:room], fg=col, bg=UI_BG)
                y += 1
                if pics and w.t.mag > 1 and w.t.cat not in ("mortar", "at_launcher", "at_disposable", "flamer") \
                        and not (w.t.get("magtype") and w.mag_item is None):
                    icons.pic(x, y, wdt, 1, icons.rounds_key(w))      # the rounds, as you know them
                    y += 1
                from .familiar import word
                fw = word(p, w.t)
                if fw:
                    con.print(x, y, f"({fw})"[:wdt], fg=(220, 170, 110), bg=UI_BG)
                    y += 1
                if w.t.cat not in ("at_disposable",):
                    from .ammo import spare_description
                    s = spare_description(p, w)
                    for line in textwrap.wrap(s, wdt)[:2]:
                        con.print(x, y, line, fg=UI_DIM, bg=UI_BG)
                        y += 1
            elif key is not None:
                y += 1
        gr = p.grenades()
        if gr:
            n = sum(g.count for g in gr)
            con.print(x, y, f"Grenades: {n}", fg=UI_DIM, bg=UI_BG)
            if pics:
                gx = x + 12
                for g in gr:
                    for _ in range(g.count):
                        if gx + 2 > x + wdt:
                            break
                        icons.pic(gx, y, 2, 1, icons.grenade_key(g.t))
                        gx += 2
            y += 1
        y += 1
    # time & weather (a watch tells the time, otherwise the sky)
    if p.has_tool("watch"):
        tstr = game.now().strftime("%H:%M")
    else:
        tstr = game.time_feel()
    from .weather import description as weather_description
    wx = weather_description(game)
    if pics:
        from .senses import daylight
        n = game.now()
        hrs = n.hour + n.minute / 60
        sun = max(0.0, min(1.0, (hrs - 5.0) / 15.0)) if 5 <= hrs <= 20 else (0.3 if hrs > 20 else 0.7)
        icons.pic(x, y, 5, 2, f"sky|{round(daylight(game), 1)}|{game.weather}|{round(sun, 1)}")
        tx = x + 6
        if p.has_tool("watch"):
            icons.pic(tx, y, 4, 2, f"watch|{n.strftime('%H:%M')}")
            tx += 5
        con.print(tx, y, tstr[:wdt - (tx - x)], fg=UI_TEXT, bg=UI_BG)
        con.print(tx, y + 1, wx[:wdt - (tx - x)], fg=UI_DIM, bg=UI_BG)
        y += 3
    else:
        con.print(x, y, f"{tstr}, {wx}"[:wdt], fg=UI_TEXT, bg=UI_BG)
        y += 2
    rt = game.__dict__.get("_realtime_label")
    if rt:
        for line in textwrap.wrap(rt, wdt)[:2]:
            con.print(x, y, line, fg=(140, 205, 210), bg=UI_BG)
            y += 1
    # orders: the one you're on, and the others you hold (T: the orders book)
    book = _book(game)
    from .orders import summary as order_summary
    order_text = (order_summary(game, book) if game.__dict__.get("domain", "land") == "land" and
                  not getattr(game, "renegade", False) else None) or game.player_orders
    con.print(x, y, "Orders" + (f" ({len(book)})  T: all" if len(book) > 1 else ""), fg=UI_FRAME, bg=UI_BG)
    y += 1
    for line in textwrap.wrap(order_text or "None.", wdt)[:9 if game.__dict__.get("aboard") else 4]:
        con.print(x, y, line, fg=(200, 190, 150), bg=UI_BG)
        y += 1
    shown = order_text or ""
    more = [o for o in book if (o["text"] or "")[:30] not in shown][:2]
    for o in more:
        who = o["who"].split(",")[0]
        con.print(x, y, f"{o['status']}: {who}: {o['text']}"[:wdt],
                  fg=(160, 150, 120) if o["deferred"] else (190, 200, 150), bg=UI_BG)
        y += 1
    hint = game.__dict__.get("_order_hint")
    if hint:
        for line in textwrap.wrap(hint, wdt)[:2]:
            con.print(x, y, line, fg=(150, 200, 140), bg=UI_BG)
            y += 1
    ctx = game.__dict__.get("_ctx_hint")
    if ctx:
        for line in textwrap.wrap(ctx, wdt)[:3]:
            con.print(x, y, line, fg=(140, 180, 210), bg=UI_BG)
            y += 1
    ptr = game.order_pointer()
    if ptr is not None:
        from .senses import direction_word
        px, py = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
        dxo, dyo = ptr[0] - px, ptr[1] - py
        yd = int(round(math.hypot(dxo, dyo) * 2.2 / 50.0) * 50) or 50
        known = p.has_tool("map") or p.has_tool("compass")
        way = f"{direction_word(dxo, dyo)}, {yd} yards" if known else "the ordered direction"
        if pics:
            ang = math.degrees(math.atan2(dxo, -dyo)) % 360
            icons.pic(x, y, 3, 2, f"pointer|{int(ang)}|{'compass' if p.has_tool('compass') else 'hand'}")
            for k, line in enumerate(textwrap.wrap(way, wdt - 4)[:2]):
                con.print(x + 4, y + k, line, fg=(245, 215, 110), bg=UI_BG)
            y += 2
        else:
            con.print(x, y, f"{arrow_for(dxo, dyo)} {way}"[:wdt], fg=(245, 215, 110), bg=UI_BG)
            y += 1
    y += 1
    # command
    cmd = getattr(game, "command", None)
    if cmd is not None and cmd.billet is not None and y < SCREEN_H - 8:
        con.print(x, y, "Command", fg=UI_FRAME, bg=UI_BG)
        y += 1
        for line in textwrap.wrap(cmd.billet_title(game), wdt)[:2]:
            con.print(x, y, line, fg=(200, 190, 150), bg=UI_BG)
            y += 1
        n = len(cmd.chain_squads(game))
        pend = len(cmd.pending)
        con.print(x, y, (f"{n} unit{'s' if n != 1 else ''}" + (f", {pend} order{'s' if pend != 1 else ''} out"
                                                              if pend else "") + "  (C)")[:wdt],
                  fg=UI_DIM, bg=UI_BG)
        y += 2
    # squad (only those you can see or hear nearby)
    sq = p.squad
    if sq is not None and len(sq.members) > 1:
        con.print(x, y, "Squad", fg=UI_FRAME, bg=UI_BG)
        y += 1
        for mbr in sq.members:
            if mbr is p or y >= SCREEN_H - 3:
                continue
            close = mbr.vehicle is None and mbr.alive and (
                math.hypot(mbr.x - p.x, mbr.y - p.y) < 8 or
                (game.map.visible[mbr.x, mbr.y] and math.hypot(mbr.x - p.x, mbr.y - p.y) < 40))
            if not close:
                continue
            if not mbr.alive:
                col, st = (120, 40, 40), "dead"
            elif mbr.downed:
                col, st = (240, 80, 80), "down!"
            elif mbr.state != "ok":
                col, st = UI_DIM, mbr.state
            else:
                worst = min(mbr.body.hp[k] / mbr.body.max[k] for k in mbr.body.hp)
                col = (150, 220, 150) if worst > 0.8 else (230, 200, 80) if worst > 0.4 else (240, 110, 60)
                st = "ok" if worst > 0.8 else "hurt" if worst > 0.4 else "wounded"
                if mbr.suppression > 60:
                    st = "pinned"
            nm = f"{mbr.last_name}"[:wdt - 8]
            if pics:
                icons.pic(x, y, 1, 1, "man|" + {"down!": "down"}.get(st, st))
                con.print(x + 2, y, f"{nm}"[: wdt - 10], fg=SQUAD_COLOR, bg=UI_BG)
            else:
                con.print(x, y, f"{nm}", fg=SQUAD_COLOR, bg=UI_BG)
            con.print(x0 + PANEL_W - 1 - len(st), y, st, fg=col, bg=UI_BG)
            y += 1
    # sector
    yb = SCREEN_H - 2
    if p.has_tool("map"):
        con.print(x, yb, f"{game.sector.name}"[:wdt], fg=UI_DIM, bg=UI_BG)
    else:
        con.print(x, yb, f"Somewhere near {game.theatre['name']}"[:wdt], fg=UI_DIM, bg=UI_BG)
    con.print(x, yb + 1, "? help  Esc menu"[:wdt], fg=(90, 85, 70), bg=UI_BG)


def draw_log(con, game, scroll=0):
    y0 = VIEW_H
    con.draw_rect(0, y0, VIEW_W, LOG_H, ord(" "), bg=(8, 8, 7))
    con.print(0, y0, "─" * VIEW_W, fg=(60, 55, 40), bg=(8, 8, 7))
    msgs = list(game.messages)
    from . import icons
    pics = icons.on()
    lx = 4 if pics else 1                       # (a sign for what kind of news each line is, at its left)
    lines = []
    for mm in msgs[-40:]:
        txt = mm.text + (f" (x{mm.count})" if mm.count > 1 else "")
        col = MSG_COLORS.get(mm.cat, UI_TEXT)
        age = game.turn - mm.turn
        fade = 1.0 if age < 2 else 0.8 if age < 10 else 0.6
        col = tuple(int(c * fade) for c in col)
        for i, line in enumerate(textwrap.wrap(txt, VIEW_W - 1 - lx) or [""]):
            lines.append((line if i == 0 else "  " + line, col, mm.cat if i == 0 else None))
    scroll = max(0, min(scroll, max(0, len(lines) - (LOG_H - 1))))
    show = lines[max(0, len(lines) - (LOG_H - 1) - scroll): len(lines) - scroll if scroll else None]
    for i, (line, col, cat) in enumerate(show[-(LOG_H - 1):]):
        con.print(lx, y0 + 1 + i, line, fg=col, bg=(8, 8, 7))
        if pics and cat is not None and cat not in ("info", "system"):
            icons.pic(1, y0 + 1 + i, 2, 1, f"log:x|{cat}")


# ====================================================================== popups

LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


class Popup:
    """A menu box anchored to a point on the map (usually your @)."""

    def __init__(self, title, options, anchor, *, footer="", width=None, kind="menu", data=None,
                 lines=None, letters=True):
        self.title = title
        self.options = options      # list of (label, value, color|None, enabled)
        self.anchor = anchor        # screen coords of the thing it comes from
        self.sel = 0
        self.footer = footer
        self.width = width
        self.kind = kind
        self.data = data or {}
        self.lines = lines or []
        self.letters = letters
        self.rect = (0, 0, 0, 0)
        self.scroll = 0
        # skip disabled/headers
        self._fix_sel(1)

    def _fix_sel(self, step):
        n = len(self.options)
        if n == 0:
            return
        for _ in range(n):
            if self.options[self.sel][3]:
                return
            self.sel = (self.sel + step) % n

    def move(self, d):
        if not self.options:
            return
        self.sel = (self.sel + d) % len(self.options)
        self._fix_sel(1 if d > 0 else -1)

    def letter_of(self, idx):
        k = 0
        for i, o in enumerate(self.options):
            if not o[3]:
                continue
            if i == idx:
                return LETTERS[k] if k < len(LETTERS) else " "
            k += 1
        return " "

    def index_of_letter(self, ch):
        k = 0
        for i, o in enumerate(self.options):
            if not o[3]:
                continue
            if LETTERS[k:k + 1] == ch:
                return i
            k += 1
        return None

    def layout(self):
        w = self.width or max([len(self.title) + 4] + [len(o[0]) + 6 for o in self.options] +
                              [len(l[0]) + 3 for l in self.lines] + [len(self.footer) + 3])
        w = min(w, VIEW_W - 4)
        max_rows = VIEW_H - 6
        body = len(self.lines) + len(self.options)
        h = min(max_rows, body) + 2 + (1 if self.footer else 0)
        ax, ay = self.anchor
        # prefer to the right of the anchor, with a gap for the connector
        if ax + 3 + w < VIEW_W:
            x = ax + 3
        elif ax - 3 - w >= 0:
            x = ax - 3 - w
        else:
            x = max(0, min(VIEW_W - w, ax - w // 2))
        y = max(0, min(VIEW_H - h, ay - 2))
        self.rect = (x, y, w, h)
        return self.rect

    def item_at(self, sx, sy):
        x, y, w, h = self.rect
        if not (x < sx < x + w - 1 and y < sy < y + h - 1):
            return None
        body_row = sy - y - 1 - len(self.lines)
        avail = h - 2 - len(self.lines) - (1 if self.footer else 0)
        if body_row < 0 or body_row >= avail:
            return None
        row = body_row + self.scroll
        if 0 <= row < len(self.options) and self.options[row][3]:
            return row
        return None


def draw_popup(con, pop: Popup):
    x, y, w, h = pop.layout()
    ax, ay = pop.anchor
    # connector from the anchor to the box edge
    if 0 <= ax < VIEW_W and 0 <= ay < VIEW_H:
        edge_x = x if x > ax else x + w - 1
        ty = max(y + 1, min(y + h - 2, ay))
        step = 1 if edge_x > ax else -1
        cx = ax + step
        while cx != edge_x:
            ch = "─"
            con.print(cx, ay, ch, fg=UI_FRAME)
            cx += step
        if ty != ay:
            yy = ay
            s2 = 1 if ty > ay else -1
            while yy != ty:
                yy += s2
                con.print(edge_x - step, yy, "│", fg=UI_FRAME)
            con.print(edge_x - step, ay, "┐" if (step == 1 and s2 == 1) else "┘" if (step == 1) else
                      "┌" if s2 == 1 else "└", fg=UI_FRAME)
        con.print(ax, ay, chr(con.rgb["ch"][ax, ay]), bg=(90, 80, 40))
    con.draw_frame(x, y, w, h, title="", clear=True, fg=UI_FRAME, bg=UI_BG)
    if pop.title:
        con.print(x + 2, y, f" {pop.title[:w - 6]} ", fg=UI_HI, bg=UI_BG)
    row = y + 1
    for text, col in pop.lines:
        if row >= y + h - 1:
            break
        con.print(x + 1, row, text[:w - 2], fg=col or UI_TEXT, bg=UI_BG)
        row += 1
    avail = y + h - 1 - (1 if pop.footer else 0) - row
    if pop.sel - pop.scroll >= avail:
        pop.scroll = pop.sel - avail + 1
    if pop.sel < pop.scroll:
        pop.scroll = pop.sel
    for i, (label, value, col, enabled) in enumerate(pop.options[pop.scroll:pop.scroll + avail], start=pop.scroll):
        sel = i == pop.sel
        bg = UI_SEL_BG if sel else UI_BG
        if not enabled:
            con.print(x + 1, row, label[:w - 2], fg=col or UI_FRAME, bg=UI_BG)
        else:
            letter = pop.letter_of(i) if pop.letters else " "
            con.print(x + 1, row, " " * (w - 2), bg=bg)
            con.print(x + 1, row, f"{letter}) " if pop.letters else "  ", fg=UI_DIM, bg=bg)
            con.print(x + 4, row, label[:w - 5], fg=col or (UI_HI if sel else UI_TEXT), bg=bg)
        row += 1
    if pop.footer:
        con.print(x + 1, y + h - 2, pop.footer[:w - 2], fg=UI_DIM, bg=UI_BG)
    from . import icons
    icons.erase(x, y, w, h)                       # (nothing painted earlier shows through the box)


def draw_tooltip(con, anchor, lines, title=None):
    """A small box pointing at a map tile."""
    ax, ay = anchor
    w = min(VIEW_W - 2, max([len(t) for t, _ in lines] + [len(title or "") + 2]) + 2)
    h = len(lines) + 2
    x = ax + 2 if ax + 2 + w < VIEW_W else ax - 2 - w
    y = ay - h - 1 if ay - h - 1 >= 0 else ay + 2
    if y + h > VIEW_H:
        y = max(0, VIEW_H - h)
    x = max(0, x)
    # leader line
    lx = x if x > ax else x + w - 1
    con.print(ax + (1 if lx > ax else -1), ay, "·", fg=UI_FRAME)
    con.draw_frame(x, y, w, h, clear=True, fg=(110, 100, 70), bg=(16, 15, 12))
    from . import icons
    icons.erase(x, y, w, h)
    if title:
        con.print(x + 1, y, f" {title[:w - 4]} ", fg=UI_HI, bg=(16, 15, 12))
    for i, (t, col) in enumerate(lines):
        con.print(x + 1, y + 1 + i, t[:w - 2], fg=col or UI_TEXT, bg=(16, 15, 12))
    return x, y, w, h


def draw_line(con, game, cam, x0, y0, x1, y1, color_fn=None):
    pts = tcod.los.bresenham((x0, y0), (x1, y1))
    blocked = False
    m = game.map
    for i, (x, y) in enumerate(pts[1:], 1):
        x, y = int(x), int(y)
        if not cam.on_screen(x, y):
            continue
        sx, sy = cam.to_screen(x, y)
        if not (0 <= sx < con.width and 0 <= sy < con.height):
            continue
        if m.in_bounds(x, y) and not m.see[x, y]:
            blocked = True
        col = (220, 60, 60) if blocked else ((230, 230, 120) if i < len(pts) - 1 else (255, 255, 255))
        if m.in_bounds(x, y) and m.cover[x, y] > 40 and not blocked:
            col = (240, 160, 60)
        ch = con.rgb["ch"][sx, sy] if i == len(pts) - 1 else ord("·") if con.rgb["ch"][sx, sy] in (ord(" "), ord("."), ord(","), ord("'"), ord("`")) else con.rgb["ch"][sx, sy]
        con.rgb["ch"][sx, sy] = ch
        con.rgb["fg"][sx, sy] = col
        if i == len(pts) - 1:
            con.rgb["bg"][sx, sy] = (90, 70, 20)
    return blocked


def draw_cursor(con, cam, x, y, color=(255, 255, 255)):
    if cam.on_screen(x, y):
        sx, sy = cam.to_screen(x, y)
        if not (0 <= sx < con.width and 0 <= sy < con.height):
            return
        con.rgb["bg"][sx, sy] = (120, 100, 40)
        con.rgb["fg"][sx, sy] = color


def draw_center_box(con, title, lines, width=None, footer=None, top=None):
    w = width or min(SCREEN_W - 6, max([len(t) for t, _ in lines] + [len(title) + 4]) + 4)
    h = min(SCREEN_H - 2, len(lines) + 4)
    x = (SCREEN_W - w) // 2
    y = top if top is not None else (SCREEN_H - h) // 2
    con.draw_frame(x, y, w, h, clear=True, fg=UI_FRAME, bg=UI_BG)
    from . import icons
    icons.erase(x, y, w, h)
    con.print(x + 2, y, f" {title} ", fg=UI_HI, bg=UI_BG)
    for i, (t, col) in enumerate(lines[: h - 4]):
        con.print(x + 2, y + 2 + i, t[: w - 4], fg=col or UI_TEXT, bg=UI_BG)
    if footer:
        con.print(x + 2, y + h - 1, f" {footer} ", fg=UI_DIM, bg=UI_BG)
