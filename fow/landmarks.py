"""Landmarks: the places men steered by and fought over.

Every sector gets a few, chosen by its country and climate: a windmill on its rise, a railway station with
goods wagons on the siding, a château behind its park wall, the village cemetery, a brickworks chimney the
gunners register on, a quarry, a slag heap, the grain elevator on the steppe, a kolkhoz, a coconut plantation
and a mission church in the Solomons, a shrine behind its torii on Okinawa, a pagoda in China or Burma, a
desert fort and a marabout's tomb, a castle on its hill, a lighthouse on the coast, a Würzburg radar station,
a landing ground, an oasis, a sawmill in the forest, a tank farm, and the burnt-out tanks of the last attack.
Each one is a place on the map with a name - a candidate objective - and real terrain: walls that stop
bullets, towers you can climb, stacks that burn.

Then the smaller touches that make a country look like itself: a calvary at the crossroads, the memorial to
the last war in the square, named buildings in the village (the mairie, the Gasthaus, the kolkhoz office),
poplars along the road, telegraph poles across the steppe, and - after the defences are dug - Tobruk pits in
a German line and stone sangars where the ground's too hard to dig.

The builders draw on the map's own random stream but a private one (gen.rng is swapped for the duration), so
the rest of a sector's making is what it always was for its seed.
"""
from __future__ import annotations

import math
import random

import numpy as np
import tcod

from . import tiles as T

WEST = ("fr", "be", "nl", "de", "it", "gr", "pl", "en")
EAST = ("ru", "uk", "pl")
LATIN = ("fr", "be", "it")
CALVARY_LANGS = ("fr", "be", "it", "pl", "de", "nl")
MEMORIAL_LANGS = ("fr", "be", "de", "it", "nl", "en", "pl")
ROADISH = ("road", "paved", "cobble", "dirt", "gravel", "bridge", "rail", "runway")

BUILDING_NAMES = {
    "fr": ["the mairie", "the café", "the school", "the forge", "the bakery", "the post office", "the presbytery",
           "the inn", "the dairy"],
    "be": ["the town hall", "the café", "the school", "the brewery", "the forge", "the post office"],
    "nl": ["the town hall", "the café", "the school", "the dairy", "the bakery"],
    "de": ["the Gasthaus", "the Rathaus", "the school", "the smithy", "the bakery", "the post office",
           "the Forsthaus"],
    "it": ["the municipio", "the osteria", "the school", "the oil press", "the carabinieri post", "the canonica"],
    "gr": ["the kafeneion", "the school", "the olive press", "the gendarmerie"],
    "pl": ["the manor house", "the inn", "the school", "the smithy", "the dairy"],
    "ru": ["the kolkhoz office", "the school", "the smithy", "the village soviet", "the MTS workshop"],
    "uk": ["the kolkhoz office", "the school", "the smithy", "the village soviet", "the dairy"],
    "fi": ["the school", "the co-op store", "the parsonage"],
    "ar": ["the police post", "the mosque", "the souk", "the well-house"],
    "zh": ["the ancestral hall", "the school", "the teahouse", "the granary"],
    "ja": ["the school", "the village office", "the storehouse", "the sake brewery"],
    "in": ["the bungalow", "the club", "the rest house", "the school"],
    "my": ["the monastery", "the school", "the rice mill"],
    "mel": ["the trade store", "the mission house", "the copra shed"],
    "en": ["the pub", "the post office", "the school", "the smithy"],
}
MARABOUT_SAINTS = ("Rezegh", "Omar", "Abd el Rahman", "Mahmud", "Salim", "Ahmed", "Barrani", "Muftah")


# ============================================================================ small helpers
def _t(key):
    return T.ID[key]


def _in(gen, x, y, pad=1):
    return pad <= x < gen.w - pad and pad <= y < gen.h - pad


def put(gen, x, y, key, keep_water=True):
    if _in(gen, x, y) and not (keep_water and T.WATER[gen.m.t[x, y]] and key not in ("bridge",)):
        gen.m.t[x, y] = _t(key)
        return True
    return False


def ground(gen):
    return gen.key("ground")


def clear(gen, x0, y0, w, h, key=None):
    key = key or ground(gen)
    sub = gen.m.t[x0:x0 + w, y0:y0 + h]
    keep = T.WATER[sub] > 0
    sub[~keep] = _t(key)


def protect(gen, x0, y0, w, h, pad=1):
    gen.protected[max(0, x0 - pad):x0 + w + pad, max(0, y0 - pad):y0 + h + pad] = True


def poi(gen, name, x, y, rad=8):
    gen.poi.append((name, int(x), int(y), rad))


def rise(gen, x, y, height, radius):
    """Raise (or sink) the ground here when the heightmap is made (relief.make)."""
    gen.__dict__.setdefault("rises", []).append((int(x), int(y), float(height), float(radius)))


def spot(gen, w, h, margin=2, depth=(0.25, 0.92), tries=80, where=None, dense_ok=0.35, roads_ok=False):
    """Top-left corner of a free w x h rectangle of dry, open-ish ground, or None.  roads_ok: it may cross a
    road (an airstrip does), just not a building or the water."""
    r = gen.rng
    t = gen.m.t
    if w + 10 >= gen.w or h + 10 >= gen.h:
        return None
    roadish = np.isin(t, [_t(k) for k in ROADISH]) if roads_ok else None
    for _ in range(tries):
        x0 = r.randint(5, gen.w - w - 6)
        y0 = r.randint(5, gen.h - h - 6)
        if gen.att and depth is not None:
            d = gen.depth_coord(x0 + w / 2, y0 + h / 2)
            if not depth[0] <= d <= depth[1]:
                continue
        if roads_ok:
            sl = (slice(x0 - margin, x0 + w + margin), slice(y0 - margin, y0 + h + margin))
            if (gen.protected[sl] & ~roadish[sl]).any():
                continue
        elif not gen.area_free(x0 - margin, y0 - margin, x0 + w + margin, y0 + h + margin):
            continue
        sub = t[x0:x0 + w, y0:y0 + h]
        if T.WATER[sub].any() or (sub == _t("cliff")).any():
            continue
        if (~T.WALK[sub]).mean() > dense_ok:
            continue
        if where is not None and not where(x0, y0):
            continue
        return x0, y0
    return None


def track(gen, x, y, key="dirt", reach=80):
    """A cart track from (x, y) to the nearest road, around buildings and water; None if there's no road."""
    best, bd = None, reach
    for rd in gen.roads:
        for (px, py) in rd[::2]:
            d = abs(px - x) + abs(py - y)
            if d < bd:
                best, bd = (px, py), d
    if best is None:
        return None
    t = gen.m.t
    cost = np.full(t.shape, 3, np.int32)
    cost[~T.WALK[t]] = 9                                  # trees and scrub: cut through
    hard = T.HARD[t] | (T.WATER[t] >= 2) | np.isin(t, [_t(k) for k in ("wall_wood", "wall_thatch", "wall_log",
                                                                         "door", "window", "cliff")])
    cost[hard] = 0
    cost[T.WATER[t] == 1] = 14
    roadish = np.isin(t, [_t(k) for k in ROADISH])
    cost[gen.protected & ~roadish] = 0
    cost[roadish] = 1
    cost[x, y] = 1
    path = tcod.path.path2d(cost, start_points=[(x, y)], end_points=[best], cardinal=2, diagonal=3)
    pts = [tuple(int(v) for v in p) for p in path]
    if not pts:
        return None
    laid = []
    for px, py in pts:
        if roadish[px, py] and (px, py) != (x, y):
            break
        if T.WATER[t[px, py]] or not _in(gen, px, py, 0):
            continue
        t[px, py] = _t(key)
        laid.append((px, py))
    for px, py in laid:
        gen.protected[px, py] = True
    if laid:
        gen.roads.append(laid)
    return laid


def ring(gen, x0, y0, w, h, key, gate=None, gaps=0.0, gate_w=1):
    """A wall or fence round a rectangle; `gate` is a side (N/S/E/W): a gap in the middle of it."""
    r = gen.rng
    gx = gy = None
    if gate in ("N", "S"):
        gx, gy = x0 + w // 2, (y0 if gate == "N" else y0 + h - 1)
    elif gate in ("E", "W"):
        gx, gy = (x0 if gate == "W" else x0 + w - 1), y0 + h // 2
    for x in range(x0, x0 + w):
        for y in (y0, y0 + h - 1):
            if gx is not None and gate in ("N", "S") and y == gy and abs(x - gx) < gate_w:
                continue
            if r.random() >= gaps:
                put(gen, x, y, key)
    for y in range(y0 + 1, y0 + h - 1):
        for x in (x0, x0 + w - 1):
            if gx is not None and gate in ("E", "W") and x == gx and abs(y - gy) < gate_w:
                continue
            if r.random() >= gaps:
                put(gen, x, y, key)
    return (gx, gy) if gx is not None else None


def outside(gate, side, d=1):
    """The tile just outside a gate on its side."""
    ox, oy = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}[side]
    return gate[0] + ox * d, gate[1] + oy * d


def facing_road(gen, x0, y0, w, h):
    """Which side of a rectangle faces the nearest road (or the defender's rear)."""
    cx, cy = x0 + w / 2, y0 + h / 2
    best, bd = None, 1e9
    for rd in gen.roads:
        for (px, py) in rd[::3]:
            d = abs(px - cx) + abs(py - cy)
            if d < bd:
                best, bd = (px, py), d
    if best is None:
        from .mapgen import OPP
        return OPP.get(gen.att, "S") if gen.att else "S"
    dx, dy = best[0] - cx, best[1] - cy
    if abs(dx) > abs(dy):
        return "E" if dx > 0 else "W"
    return "S" if dy > 0 else "N"


def _building(gen, x, y, w, h, style, **kw):
    gen.protected[max(0, x - 1):x + w + 1, max(0, y - 1):y + h + 1] = False
    return gen.building(x, y, w, h, style, **kw)


# ============================================================================ the landmarks
def windmill(gen):
    at = spot(gen, 13, 13)
    if at is None:
        return False
    x0, y0 = at
    clear(gen, x0, y0, 13, 13)
    wood = gen.spec.get("east") or gen.spec.get("lang") in ("ru", "uk", "pl", "nl", "fi")
    b = _building(gen, x0 + 4, y0 + 4, 5, 5, "post_mill" if wood else "windmill", door_side=gen.rng.choice("NSEW"))
    if not b:
        return False
    for k in range(3):
        put(gen, x0 + 3 - k, y0 + 3 - k, "sail")
        put(gen, x0 + 9 + k, y0 + 9 + k, "sail")
        put(gen, x0 + 9 + k, y0 + 3 - k, "sail2")
        put(gen, x0 + 3 - k, y0 + 9 + k, "sail2")
    if gen.rng.random() < 0.5:
        hx = x0 + (13 if gen.rng.random() < 0.5 else -9)
        if gen.area_free(hx - 1, y0 + 3, hx + 8, y0 + 10):
            _building(gen, hx, y0 + 4, 7, 6, "farmhouse" if not wood else "izba")
    track(gen, x0 + 6, y0 + 12)
    protect(gen, x0, y0, 13, 13)
    rise(gen, x0 + 6, y0 + 6, 9.0, 16)
    poi(gen, "the windmill", x0 + 6, y0 + 6, 8)
    return True


def station(gen):
    """A railway right across the sector, the station and its platform, goods wagons on the siding."""
    t = gen.m.t
    horiz = gen.w >= gen.h
    r = gen.rng
    if horiz:
        a, b = (0, int(gen.h * r.uniform(0.3, 0.7))), (gen.w - 1, int(gen.h * r.uniform(0.3, 0.7)))
    else:
        a, b = (int(gen.w * r.uniform(0.3, 0.7)), 0), (int(gen.w * r.uniform(0.3, 0.7)), gen.h - 1)
    cost = np.full(t.shape, 2, np.int32)
    cost[~T.WALK[t]] = 8
    roadish = np.isin(t, [_t(k) for k in ROADISH])
    cost[gen.protected & ~roadish] = 0
    cost[roadish] = 3
    cost[T.WATER[t] >= 1] = 12
    cost[t == _t("cliff")] = 0
    path = tcod.path.path2d(cost, start_points=[a], end_points=[b], cardinal=2, diagonal=0)
    pts = [tuple(int(v) for v in p) for p in path]
    if len(pts) < (gen.w if horiz else gen.h) * 0.8:
        return False
    for x, y in pts:
        k = T.DEFS[int(t[x, y])].key
        if k in ("road", "paved", "cobble"):
            continue                                        # a level crossing
        t[x, y] = _t("bridge" if T.WATER[t[x, y]] else "rail")
        gen.protected[x, y] = True
    gen.__dict__.setdefault("rails", []).append(pts)
    # the station: halfway along, where the ground beside the line is free
    mid = len(pts) // 2
    for off in range(0, len(pts) // 3, 3):
        for i in (mid + off, mid - off):
            if not 10 <= i < len(pts) - 10:
                continue
            x, y = pts[i]
            for side in (1, -1):
                if horiz:
                    bx, by, bw, bh = x - 7, (y + 3 if side > 0 else y - 9), 14, 7
                    px0, py0, pw, ph = x - 9, (y + 1 if side > 0 else y - 2), 18, 2
                else:
                    bx, by, bw, bh = (x + 3 if side > 0 else x - 9), y - 7, 7, 14
                    px0, py0, pw, ph = (x + 1 if side > 0 else x - 2), y - 9, 2, 18
                if not gen.area_free(bx - 1, by - 1, bx + bw + 1, by + bh + 1):
                    continue
                sub = t[px0:px0 + pw, py0:py0 + ph]
                if T.WATER[sub].any():
                    continue
                clear(gen, px0, py0, pw, ph, "platform")
                door = ("N" if side > 0 else "S") if horiz else ("W" if side > 0 else "E")
                _building(gen, bx, by, bw, bh, "station", door_side=door)
                # the siding on the far side of the line, and what's standing on it
                sd = -side
                seg = pts[max(0, i - 14):i + 14]
                for k2, (sx, sy) in enumerate(seg):
                    qx, qy = (sx, sy + 2 * sd) if horiz else (sx + 2 * sd, sy)
                    if _in(gen, qx, qy) and not gen.protected[qx, qy] and not T.WATER[t[qx, qy]]:
                        t[qx, qy] = _t("rail")
                        gen.protected[qx, qy] = True
                wagons = seg[4:4 + r.randint(4, 12)]
                loco = r.random() < 0.35
                for k2, (sx, sy) in enumerate(wagons):
                    qx, qy = (sx, sy + 2 * sd) if horiz else (sx + 2 * sd, sy)
                    if k2 % 4 != 3 and _in(gen, qx, qy) and t[qx, qy] == _t("rail"):
                        t[qx, qy] = _t("locomotive" if loco and k2 < 2 else "boxcar")
                # the water tower at the end of the platform
                wx, wy = (px0 + pw + 1, py0 + (1 if side > 0 else 0)) if horiz else (px0, py0 + ph + 1)
                if _in(gen, wx, wy) and not gen.protected[wx, wy]:
                    put(gen, wx, wy, "water_tower")
                track(gen, bx + bw // 2, (by + bh if side > 0 else by - 1) if horiz else by + bh // 2, "gravel")
                protect(gen, bx, by, bw, bh)
                poi(gen, "the station" if r.random() < 0.7 else "the halt", x, y, 10)
                poles(gen, pts, side=sd * 4)
                return True
    poi(gen, "the railway cutting" if r.random() < 0.5 else "the railway line", *pts[mid], 8)
    return True


def chateau(gen):
    r = gen.rng
    for W, H in ((34, 26), (30, 22), (26, 20)):
        at = spot(gen, W, H, dense_ok=0.5)
        if at is not None:
            break
    else:
        return False
    x0, y0 = at
    clear(gen, x0, y0, W, H, "grass" if gen.m.climate != "winter" else ground(gen))
    gate_side = facing_road(gen, x0, y0, W, H)
    gate = ring(gen, x0, y0, W, H, "wall_stone", gate=gate_side, gaps=0.04, gate_w=2)
    # the house at the back, the drive up to it, the fountain in the forecourt
    hw, hh = min(16, W - 12), min(10, H - 10)
    back = {"N": "S", "S": "N", "E": "W", "W": "E"}[gate_side]
    if gate_side in ("N", "S"):
        hx = x0 + (W - hw) // 2
        hy = y0 + 3 if back == "N" else y0 + H - hh - 3
    else:
        hy = y0 + (H - hh) // 2
        hx = x0 + 3 if back == "W" else x0 + W - hw - 3
    _building(gen, hx, hy, hw, hh, "chateau", door_side=gate_side)
    hcx, hcy = hx + hw // 2, hy + hh // 2
    front = {"N": (hcx, hy - 1), "S": (hcx, hy + hh), "W": (hx - 1, hcy), "E": (hx + hw, hcy)}[gate_side]
    line = tcod.los.bresenham(gate, front).tolist()
    tree = "poplar" if r.random() < 0.5 else gen.key("tree")
    for k, (lx, ly) in enumerate(line):
        put(gen, lx, ly, "gravel")
        if gate_side in ("N", "S"):
            put(gen, lx + 1, ly, "gravel")
            if k % 2 == 0 and 2 < k < len(line) - 4:
                put(gen, lx - 2, ly, tree)
                put(gen, lx + 3, ly, tree)
        else:
            put(gen, lx, ly + 1, "gravel")
            if k % 2 == 0 and 2 < k < len(line) - 4:
                put(gen, lx, ly - 2, tree)
                put(gen, lx, ly + 3, tree)
    if len(line) > 8:
        fx, fy = line[-4]
        put(gen, fx, fy, "fountain")
    # formal garden squares and an outbuilding
    for _ in range(4):
        gx, gy = r.randint(x0 + 2, x0 + W - 6), r.randint(y0 + 2, y0 + H - 5)
        sub = gen.m.t[gx:gx + 4, gy:gy + 3]
        if (sub == _t("grass")).all() or (sub == _t(ground(gen))).all():
            for xx in range(gx, gx + 4):
                for yy in range(gy, gy + 3):
                    if xx in (gx, gx + 3) or yy in (gy, gy + 2):
                        put(gen, xx, yy, "garden_hedge")
    for _ in range(8):
        sx, sy = r.randint(x0 + 2, x0 + W - 10), r.randint(y0 + 2, y0 + H - 8)
        if (gen.m.t[sx - 1:sx + 10, sy - 1:sy + 7] == _t("grass")).all():
            _building(gen, sx, sy, 9, 6, "barn")
            break
    out = outside(gate, gate_side)
    track(gen, *out, key="gravel")
    protect(gen, x0, y0, W, H)
    poi(gen, "the château", hcx, hcy, 12)
    return True


def cemetery(gen):
    r = gen.rng
    at = spot(gen, 22, 16, dense_ok=0.5)
    if at is None:
        return False
    x0, y0 = at
    lang = gen.spec.get("lang")
    east = gen.spec.get("east") or lang in ("ru", "uk", "fi")
    clear(gen, x0, y0, 22, 16, "grass" if gen.m.climate not in ("winter", "desert") else ground(gen))
    side = facing_road(gen, x0, y0, 22, 16)
    wall = "fence" if east else ("wall_stone" if lang in LATIN and r.random() < 0.7 else "low_wall")
    gate = ring(gen, x0, y0, 22, 16, wall if wall != "fence" else "fence_h", gate=side, gaps=0.05, gate_w=1)
    if wall == "fence":
        for y in range(y0 + 1, y0 + 15):
            for x in (x0, x0 + 21):
                if gen.m.t[x, y] == _t("fence_h"):
                    gen.m.t[x, y] = _t("fence")
    for x in range(x0 + 2, x0 + 20, 2):
        for y in range(y0 + 2, y0 + 14):
            if y == y0 + 8 or x == x0 + 11:
                put(gen, x, y, "gravel")
                continue
            if r.random() < 0.75:
                put(gen, x, y, "grave")
    for _ in range(0 if east else r.randint(3, 6)):
        vx, vy = r.randint(x0 + 2, x0 + 19), r.randint(y0 + 2, y0 + 13)
        put(gen, vx, vy, "vault")
    tree = "birch" if east else "cypress" if lang in ("it", "gr") or gen.m.climate == "mediterranean" else \
        gen.key("tree")
    for _ in range(5):
        put(gen, r.randint(x0 + 1, x0 + 20), r.randint(y0 + 1, y0 + 14), tree)
    if not east and r.random() < 0.55:
        _building(gen, x0 + 8, y0 + 3, 7, 5, "chapel", door_side="S")
    if gate:
        track(gen, *outside(gate, side))
    protect(gen, x0, y0, 22, 16)
    poi(gen, "the cemetery", x0 + 11, y0 + 8, 10)
    return True


def water_tower(gen):
    at = spot(gen, 8, 8)
    if at is None:
        return False
    x0, y0 = at
    clear(gen, x0, y0, 8, 8)
    put(gen, x0 + 4, y0 + 4, "water_tower")
    _building(gen, x0 + 1, y0 + 1, 4, 3, "shed")
    track(gen, x0 + 4, y0 + 7)
    protect(gen, x0, y0, 8, 8)
    poi(gen, "the water tower", x0 + 4, y0 + 4, 7)
    return True


def brickworks(gen):
    r = gen.rng
    at = spot(gen, 30, 20, dense_ok=0.5)
    if at is None:
        return False
    x0, y0 = at
    clear(gen, x0, y0, 30, 20, "dirt")
    # the clay pit
    for x in range(x0 + 1, x0 + 11):
        for y in range(y0 + 1, y0 + 9):
            d = ((x - x0 - 6) / 5.0) ** 2 + ((y - y0 - 5) / 4.0) ** 2
            if d < 0.45:
                put(gen, x, y, "shallow", keep_water=False)
            elif d < 1.0:
                put(gen, x, y, "mud")
    for k in range(r.randint(2, 3)):
        kx = x0 + 13 + k * 6
        _building(gen, kx, y0 + 2, 5, 5, "kiln", door_side="S")
    put(gen, x0 + 13 + 3 * 6, y0 + 4, "chimney")
    if r.random() < 0.5:
        put(gen, x0 + 12, y0 + 9, "chimney")
    _building(gen, x0 + 13, y0 + 11, 14, 5, "barn")
    for _ in range(6):
        put(gen, r.randint(x0 + 2, x0 + 11), r.randint(y0 + 11, y0 + 18), "crates")
    track(gen, x0 + 20, y0 + 19)
    protect(gen, x0, y0, 30, 20)
    poi(gen, "the brickworks", x0 + 18, y0 + 6, 10)
    return True


def quarry(gen):
    r = gen.rng
    at = spot(gen, 26, 20, dense_ok=0.6)
    if at is None:
        return False
    x0, y0 = at
    cx, cy = x0 + 13, y0 + 10
    ramp = r.choice("NSEW")
    for x in range(x0, x0 + 26):
        for y in range(y0, y0 + 20):
            d = ((x - cx) / 12.5) ** 2 + ((y - cy) / 9.5) ** 2
            if d > 1.0:
                continue
            onramp = {"N": y < cy and abs(x - cx) <= 1, "S": y > cy and abs(x - cx) <= 1,
                      "E": x > cx and abs(y - cy) <= 1, "W": x < cx and abs(y - cy) <= 1}[ramp]
            if d > 0.78 and not onramp:
                put(gen, x, y, "cliff" if r.random() < 0.85 else "scree")
            else:
                put(gen, x, y, "rock_ground" if r.random() < 0.7 else "scree")
    for _ in range(6):
        put(gen, r.randint(cx - 8, cx + 8), r.randint(cy - 5, cy + 5), "boulder")
    put(gen, cx - 2, cy, "machinery")
    put(gen, cx - 1, cy, "machinery")
    ex = {"N": (cx, y0 - 1), "S": (cx, y0 + 20), "E": (x0 + 26, cy), "W": (x0 - 1, cy)}[ramp]
    track(gen, *ex)
    protect(gen, x0, y0, 26, 20)
    rise(gen, cx, cy, -7.0, 9)
    poi(gen, "the quarry", cx, cy, 9)
    return True


def slag_heap(gen):
    r = gen.rng
    at = spot(gen, 26, 22, dense_ok=0.5)
    if at is None:
        return False
    x0, y0 = at
    cx, cy = x0 + 11, y0 + 11
    for x in range(x0, x0 + 22):
        for y in range(y0, y0 + 22):
            if ((x - cx) / 10.5) ** 2 + ((y - cy) / 10.5) ** 2 < 1.0:
                put(gen, x, y, "slag")
    # the pithead beside it: the winding house, its chimney, the headframe's gear
    _building(gen, x0 + 22, y0 + 3, 4, 8, "kiln")
    put(gen, x0 + 23, y0 + 12, "chimney")
    put(gen, x0 + 24, y0 + 14, "machinery")
    put(gen, x0 + 24, y0 + 15, "machinery")
    track(gen, x0 + 24, y0 + 17)
    protect(gen, x0, y0, 26, 22)
    rise(gen, cx, cy, 20.0, 9)
    poi(gen, "the slag heap", cx, cy, 10)
    return True


def grain_elevator(gen):
    at = spot(gen, 24, 14, dense_ok=0.5)
    if at is None:
        return False
    x0, y0 = at
    clear(gen, x0, y0, 24, 14, "dirt")
    _building(gen, x0 + 1, y0 + 3, 12, 8, "elevator", door_side="S")
    for x in range(x0 + 14, x0 + 22, 2):
        for y in (y0 + 3, y0 + 5, y0 + 7, y0 + 9):
            put(gen, x, y, "silo")
            put(gen, x + 1, y, "silo")
    track(gen, x0 + 7, y0 + 12)
    protect(gen, x0, y0, 24, 14)
    poi(gen, "the grain elevator", x0 + 12, y0 + 7, 10)
    return True


def kolkhoz(gen):
    r = gen.rng
    at = spot(gen, 36, 26, dense_ok=0.5)
    if at is None:
        return False
    x0, y0 = at
    clear(gen, x0, y0, 36, 26, "dirt" if gen.m.climate != "winter" else "snow")
    ring(gen, x0, y0, 36, 26, "fence_h", gate=facing_road(gen, x0, y0, 36, 26), gaps=0.25, gate_w=2)
    for y in range(y0 + 1, y0 + 25):
        for x in (x0, x0 + 35):
            if gen.m.t[x, y] == _t("fence_h"):
                gen.m.t[x, y] = _t("fence")
    for k in range(r.randint(2, 3)):
        _building(gen, x0 + 3, y0 + 3 + k * 7, 16, 5, "barn")
    _building(gen, x0 + 22, y0 + 3, 9, 7, "izba")
    for y in (y0 + 13, y0 + 15):
        put(gen, x0 + 24, y, "silo")
        put(gen, x0 + 25, y, "silo")
    for _ in range(r.randint(2, 4)):
        put(gen, r.randint(x0 + 21, x0 + 33), r.randint(y0 + 17, y0 + 24), "wreck")
    for _ in range(8):
        put(gen, r.randint(x0 + 2, x0 + 33), r.randint(y0 + 20, y0 + 24), "hay")
    track(gen, x0 + 18, y0 + 25)
    protect(gen, x0, y0, 36, 26)
    poi(gen, "the kolkhoz" if r.random() < 0.6 else "the collective farm", x0 + 18, y0 + 12, 12)
    return True


def plantation(gen):
    r = gen.rng
    at = spot(gen, 40, 28, dense_ok=0.9)
    if at is None:
        return False
    x0, y0 = at
    clear(gen, x0, y0, 40, 28, "grass")
    for x in range(x0 + 1, x0 + 40, 3):
        for y in range(y0 + 1, y0 + 28, 3):
            if r.random() < 0.92:
                put(gen, x, y, "palm")
            elif r.random() < 0.5:
                put(gen, x, y, "stump")
    # the manager's bungalow and the copra sheds, in a clearing at one corner
    cx0, cy0 = x0 + 26, y0 + 16
    clear(gen, cx0, cy0, 14, 12, "grass")
    _building(gen, cx0 + 1, cy0 + 1, 8, 6, "bungalow", door_side="S")
    _building(gen, cx0 + 1, cy0 + 8, 11, 4, "shed")
    track(gen, cx0 + 5, cy0 + 7)
    protect(gen, x0, y0, 40, 28)
    poi(gen, "the coconut plantation" if r.random() < 0.6 else "the plantation", x0 + 20, y0 + 14, 12)
    return True


def mission(gen):
    r = gen.rng
    at = spot(gen, 24, 18, dense_ok=0.9)
    if at is None:
        return False
    x0, y0 = at
    clear(gen, x0, y0, 24, 18, "grass")
    _building(gen, x0 + 2, y0 + 2, 9, 13, "white_church", door_side="S")
    _building(gen, x0 + 13, y0 + 2, 8, 6, "bungalow")
    _building(gen, x0 + 13, y0 + 10, 7, 5, "hut")
    for _ in range(10):
        put(gen, r.randint(x0 + 12, x0 + 22), r.randint(y0 + 15, y0 + 17), "grave")
    track(gen, x0 + 6, y0 + 16)
    protect(gen, x0, y0, 24, 18)
    poi(gen, "the mission", x0 + 6, y0 + 8, 10)
    return True


def shrine(gen):
    r = gen.rng
    at = spot(gen, 18, 14, dense_ok=0.8)
    if at is None:
        return False
    x0, y0 = at
    clear(gen, x0, y0, 18, 14)
    for x in range(x0 + 4, x0 + 14):
        for y in range(y0 + 2, y0 + 8):
            put(gen, x, y, "gravel")
    _building(gen, x0 + 6, y0 + 2, 6, 5, "shrine", door_side="S")
    for k, y in enumerate(range(y0 + 8, y0 + 14)):
        put(gen, x0 + 9, y, "gravel")
        put(gen, x0 + 8, y, "gravel")
        if k % 2 == 0:
            put(gen, x0 + 8, y, "torii")
            put(gen, x0 + 9, y, "torii")
    for _ in range(10):
        x, y = r.randint(x0, x0 + 17), r.randint(y0, y0 + 13)
        if gen.m.t[x, y] == _t(ground(gen)):
            put(gen, x, y, "pine" if r.random() < 0.6 else gen.key("tree"))
    track(gen, x0 + 9, y0 + 13)
    protect(gen, x0, y0, 18, 14)
    poi(gen, "the shrine", x0 + 9, y0 + 5, 8)
    return True


def pagoda(gen):
    r = gen.rng
    at = spot(gen, 22, 18, dense_ok=0.8)
    if at is None:
        return False
    x0, y0 = at
    clear(gen, x0, y0, 22, 18, "gravel")
    burma = gen.spec.get("lang") in ("my", "in") or gen.m.climate == "tropical"
    gate = ring(gen, x0, y0, 22, 18, "low_wall", gate="S", gate_w=2)
    if burma:
        cx, cy = x0 + 11, y0 + 7
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                put(gen, cx + dx, cy + dy, "stupa")
        for dx, dy in ((-5, -4), (5, -4), (-5, 4), (5, 4)):
            put(gen, cx + dx, cy + dy, "stupa")
        _building(gen, x0 + 3, y0 + 11, 9, 5, "temple", door_side="E")
    else:
        _building(gen, x0 + 8, y0 + 2, 7, 7, "pagoda", door_side="S")
        _building(gen, x0 + 3, y0 + 11, 14, 5, "temple", door_side="N")
    if gate:
        track(gen, *outside(gate, "S"))
    protect(gen, x0, y0, 22, 18)
    poi(gen, "the pagoda", x0 + 11, y0 + 7, 9)
    return True


def fort(gen):
    r = gen.rng
    at = spot(gen, 24, 24, dense_ok=0.4)
    if at is None:
        return False
    x0, y0 = at
    clear(gen, x0, y0, 24, 24)
    wall = "wall_white" if r.random() < 0.5 else "wall_stone"
    side = facing_road(gen, x0 + 2, y0 + 2, 20, 20)
    gate = ring(gen, x0 + 2, y0 + 2, 20, 20, wall, gate=side, gate_w=2)
    for tx, ty in ((x0, y0), (x0 + 19, y0), (x0, y0 + 19), (x0 + 19, y0 + 19)):
        _building(gen, tx, ty, 5, 5, "tower")
    bx0 = {"N": (x0 + 6, y0 + 15), "S": (x0 + 6, y0 + 4), "E": (x0 + 4, y0 + 6), "W": (x0 + 15, y0 + 6)}[side]
    if side in ("N", "S"):
        _building(gen, bx0[0], bx0[1], 12, 5, "white_house")
    else:
        _building(gen, bx0[0], bx0[1], 5, 12, "white_house")
    put(gen, x0 + 12, y0 + 12, "well")
    for _ in range(5):
        put(gen, r.randint(x0 + 5, x0 + 18), r.randint(y0 + 5, y0 + 18), "crates")
    if gen.fort >= 1:
        ring(gen, x0 - 3 if x0 > 6 else x0, y0 - 3 if y0 > 6 else y0, 30 if x0 > 6 else 24, 30 if y0 > 6 else 24,
             "wire", gate=side, gaps=0.1, gate_w=2)
    if gate:
        track(gen, *outside(gate, side, 4))
    protect(gen, x0, y0, 24, 24)
    poi(gen, "the fort", x0 + 12, y0 + 12, 12)
    return True


def marabout(gen):
    r = gen.rng
    at = spot(gen, 12, 12)
    if at is None:
        return False
    x0, y0 = at
    clear(gen, x0, y0, 12, 12)
    _building(gen, x0 + 4, y0 + 4, 5, 5, "marabout")
    for _ in range(r.randint(6, 12)):
        x, y = r.randint(x0, x0 + 11), r.randint(y0, y0 + 11)
        if gen.m.t[x, y] == _t(ground(gen)):
            put(gen, x, y, "grave")
    if r.random() < 0.5:
        put(gen, x0 + 1, y0 + 2, "palm")
    protect(gen, x0, y0, 12, 12)
    name = "the marabout" if r.random() < 0.5 else f"the tomb of Sidi {r.choice(MARABOUT_SAINTS)}"
    poi(gen, name, x0 + 6, y0 + 6, 7)
    return True


def castle(gen):
    r = gen.rng
    at = spot(gen, 28, 22, dense_ok=0.6)
    if at is None:
        return False
    x0, y0 = at
    clear(gen, x0, y0, 28, 22, "rock_ground" if r.random() < 0.5 else ground(gen))
    side = facing_road(gen, x0, y0, 28, 22)
    gate = ring(gen, x0 + 2, y0 + 2, 24, 18, "wall_stone", gate=side, gaps=0.0, gate_w=2)
    for tx, ty in ((x0, y0), (x0 + 23, y0), (x0, y0 + 17), (x0 + 23, y0 + 17)):
        _building(gen, tx, ty, 5, 5, "tower", ruin=0.3)
    _building(gen, x0 + 10, y0 + 6, 9, 9, "keep", ruin=0.2)
    # centuries of neglect and a week of shelling: breaches in the curtain wall
    for x in range(x0 + 2, x0 + 26):
        for y in range(y0 + 2, y0 + 20):
            if gen.m.t[x, y] == _t("wall_stone") and r.random() < 0.18:
                gen.m.t[x, y] = _t("rubble_heavy" if r.random() < 0.5 else "rubble")
    if gate:
        track(gen, *outside(gate, side, 3))
    protect(gen, x0, y0, 28, 22)
    rise(gen, x0 + 14, y0 + 11, 14.0, 18)
    poi(gen, "the castle", x0 + 14, y0 + 11, 12)
    return True


def lighthouse(gen):
    sea = gen.spec.get("sea_edge")
    if not sea:
        return False
    r = gen.rng
    t = gen.m.t
    along = gen.w if sea in ("N", "S") else gen.h
    across = gen.h if sea in ("N", "S") else gen.w
    inland = gen.__dict__.get("beach_inland")
    for _ in range(20):
        lat = int(along * r.choice((r.uniform(0.08, 0.3), r.uniform(0.7, 0.92))))
        if inland:
            d = inland + 6                       # up on the bluff above the beach
        else:
            for d in range(across // 2):
                x, y = {"N": (lat, d), "S": (lat, gen.h - 1 - d), "W": (d, lat), "E": (gen.w - 1 - d, lat)}[sea]
                if not T.WATER[t[x, y]]:
                    break
            else:
                continue
            d += 5
        cx, cy = {"N": (lat, d), "S": (lat, gen.h - 1 - d), "W": (d, lat), "E": (gen.w - 1 - d, lat)}[sea]
        x0, y0 = cx - 6, cy - 6
        if not (5 <= x0 and x0 + 13 < gen.w - 5 and 5 <= y0 and y0 + 13 < gen.h - 5):
            continue
        if gen.protected[x0:x0 + 13, y0:y0 + 13].sum() > 20 or T.WATER[t[x0 + 4:x0 + 9, y0 + 4:y0 + 9]].any():
            continue
        clear(gen, x0 + 1, y0 + 1, 11, 11, "rock_ground")
        _building(gen, cx - 2, cy - 2, 5, 5, "lighthouse", door_side=OPP_SIDE[sea])
        hx, hy = (cx + 4, cy - 2) if sea in ("N", "S") else (cx - 2, cy + 4)
        _building(gen, hx, hy, 6, 5, "house")
        protect(gen, x0, y0, 13, 13)
        poi(gen, "the lighthouse", cx, cy, 8)
        return True
    return False


OPP_SIDE = {"N": "S", "S": "N", "E": "W", "W": "E"}


def radar_station(gen):
    r = gen.rng
    at = spot(gen, 30, 22, dense_ok=0.4)
    if at is None:
        return False
    x0, y0 = at
    clear(gen, x0, y0, 30, 22)
    side = facing_road(gen, x0, y0, 30, 22)
    ring(gen, x0, y0, 30, 22, "wire", gate=side, gaps=0.05, gate_w=2)
    dishes = [(x0 + 7, y0 + 7), (x0 + 22, y0 + 7), (x0 + 15, y0 + 15)][:r.randint(2, 3)]
    for dx, dy in dishes:
        for ox in (-2, -1, 0, 1, 2):
            for oy in (-2, -1, 0, 1, 2):
                if max(abs(ox), abs(oy)) == 2 and r.random() < 0.8:
                    put(gen, dx + ox, dy + oy, "low_wall")
        put(gen, dx, dy, "radar")
    b1 = _building(gen, x0 + 3, y0 + 14, 7, 5, "bunker")
    b2 = _building(gen, x0 + 20, y0 + 14, 7, 5, "bunker")
    for b in (b1, b2):
        if b:
            gen.positions.append(dict(kind="bunker", x=b[0] + b[2] // 2, y=b[1] + b[3] // 2, rect=b,
                                      name="the radar station"))
    put(gen, x0 + 15, y0 + 3, "antenna")
    for tx, ty in ((x0 + 2, y0 + 2), (x0 + 27, y0 + 2), (x0 + 2, y0 + 19), (x0 + 27, y0 + 19)):
        put(gen, tx, ty, "tobruk")
    track(gen, *({"N": (x0 + 15, y0 - 1), "S": (x0 + 15, y0 + 22), "E": (x0 + 30, y0 + 11),
                  "W": (x0 - 1, y0 + 11)}[side]))
    protect(gen, x0, y0, 30, 22)
    poi(gen, "the radar station", x0 + 15, y0 + 10, 12)
    return True


def airstrip(gen):
    r = gen.rng
    horiz = gen.w >= gen.h
    L = int(min(110, (gen.w if horiz else gen.h) * 0.55))
    W = 5
    w, h = (L, W + 8) if horiz else (W + 8, L)
    at = spot(gen, w, h, dense_ok=0.8, depth=(0.3, 0.95), tries=120, roads_ok=True)
    if at is None:
        return False
    x0, y0 = at
    desert = gen.m.climate == "desert"
    surf = "dirt" if desert else ("runway" if r.random() < 0.4 else "dirt")
    keep = np.isin(gen.m.t[x0:x0 + w, y0:y0 + h], [_t(k) for k in ROADISH])
    before = gen.m.t[x0:x0 + w, y0:y0 + h].copy()
    clear(gen, x0, y0, w, h, ground(gen))
    if horiz:
        clear(gen, x0, y0 + 4, L, W, surf)
    else:
        clear(gen, x0 + 4, y0, W, L, surf)
    sub = gen.m.t[x0:x0 + w, y0:y0 + h]
    sub[keep & (sub == _t(ground(gen)))] = before[keep & (sub == _t(ground(gen)))]     # the road still crosses
    # dispersal: revetments with wrecks and the odd aircraft still in them, drums, a tent, the control hut
    for k in range(r.randint(3, 6)):
        f = r.uniform(0.1, 0.9)
        px, py = (x0 + int(f * L), y0 + 1) if horiz else (x0 + 1, y0 + int(f * L))
        put(gen, px, py, "plane_parked" if r.random() < 0.25 else "wreck")
        for ox, oy in ((-1, 0), (1, 0), (-1, -1), (0, -1), (1, -1)) if horiz else ((0, -1), (0, 1), (-1, -1),
                                                                                    (-1, 0), (-1, 1)):
            if gen.m.t[px + ox, py + oy] == _t(ground(gen)):
                put(gen, px + ox, py + oy, "sandbags")
    for _ in range(r.randint(2, 4)):
        f = r.uniform(0.05, 0.95)
        px, py = (x0 + int(f * L), y0 + h - 2) if horiz else (x0 + w - 2, y0 + int(f * L))
        put(gen, px, py, "fuel_drums")
    # the strip's edges marked out with painted drums, every hundred yards or so
    for k in range(0, L, 14):
        for e in (3, 4 + W):
            px, py = (x0 + k, y0 + e) if horiz else (x0 + e, y0 + k)
            if gen.m.t[px, py] == _t(ground(gen)):
                put(gen, px, py, "fuel_drums")
    hx, hy = (x0 + 2, y0 + h - 3) if horiz else (x0 + w - 3, y0 + 2)
    gen.m.t[hx:hx + 4, hy:hy + 3] = _t("canvas")
    gen.m.t[hx + 1:hx + 3, hy + 1] = _t("dirt")
    put(gen, (x0 + L - 3) if horiz else x0 + w - 2, (y0 + h - 2) if horiz else y0 + L - 3, "antenna")
    protect(gen, x0, y0, w, h, pad=0)
    lang = gen.spec.get("lang")
    name = "the landing ground" if desert or lang == "ar" else \
        "the airstrip" if gen.m.climate == "tropical" or lang in ("mel", "ja", "in", "my") else "the landing strip"
    poi(gen, name, x0 + w // 2, y0 + h // 2, 12)
    return True


def oasis(gen):
    r = gen.rng
    at = spot(gen, 26, 20, dense_ok=0.4)
    if at is None:
        return False
    x0, y0 = at
    cx, cy = x0 + 13, y0 + 10
    for x in range(x0, x0 + 26):
        for y in range(y0, y0 + 20):
            d = ((x - cx) / 5.0) ** 2 + ((y - cy) / 3.2) ** 2
            if d < 0.35:
                put(gen, x, y, "deep", keep_water=False)
            elif d < 1.0:
                put(gen, x, y, "shallow", keep_water=False)
            elif d < 1.6:
                put(gen, x, y, "reeds" if r.random() < 0.5 else "grass")
            elif d < 5.5 and r.random() < 0.18:
                put(gen, x, y, "palm")
            elif d < 5.5 and r.random() < 0.3:
                put(gen, x, y, "grass_dry")
    gen.protected[cx - 6:cx + 7, cy - 4:cy + 5] = True
    for _ in range(r.randint(2, 3)):
        bx, by = r.randint(x0, x0 + 20), r.choice((y0 - 1, y0 + 15))
        if gen.area_free(bx - 1, by - 1, bx + 7, by + 6):
            _building(gen, bx, by, 6, 5, "desert_house")
    protect(gen, x0, y0, 26, 20)
    poi(gen, "the oasis", cx, cy, 10)
    return True


def wrecks(gen):
    """Where the last attack died: burnt-out tanks and the shell holes round them."""
    r = gen.rng
    at = spot(gen, 22, 16, dense_ok=0.3, depth=(0.3, 0.8))
    if at is None:
        return False
    x0, y0 = at
    n = r.randint(3, 6)
    for _ in range(n):
        wx, wy = r.randint(x0 + 2, x0 + 18), r.randint(y0 + 2, y0 + 13)
        horiz = r.random() < 0.5
        for dx in range(3 if horiz else 2):
            for dy in range(2 if horiz else 3):
                put(gen, wx + dx, wy + dy, "wreck")
        sc = getattr(gen.m, "scorch", None)
        if sc is not None:
            sc[max(0, wx - 2):wx + 5, max(0, wy - 2):wy + 5] = 1
    for _ in range(14):
        put(gen, r.randint(x0, x0 + 21), r.randint(y0, y0 + 15), r.choice(("crater", "crater", "crater_big")))
    protect(gen, x0, y0, 22, 16, pad=0)
    poi(gen, r.choice(("the burnt-out tanks", "the knocked-out tanks", "the tank graveyard")), x0 + 11, y0 + 8, 9)
    return True


def sawmill(gen):
    r = gen.rng
    at = spot(gen, 26, 18, dense_ok=1.0)
    if at is None:
        return False
    x0, y0 = at
    for x in range(x0, x0 + 26):
        for y in range(y0, y0 + 18):
            put(gen, x, y, "stump" if r.random() < 0.08 else "dirt" if r.random() < 0.6 else ground(gen))
    _building(gen, x0 + 2, y0 + 2, 12, 7, "barn")
    for k in range(r.randint(4, 6)):
        sx, sy = x0 + 16 + (k % 2) * 4, y0 + 2 + (k // 2) * 4
        for dy in range(3):
            put(gen, sx, sy + dy, "timber")
            put(gen, sx + 1, sy + dy, "timber")
    for _ in range(6):
        put(gen, r.randint(x0 + 2, x0 + 14), r.randint(y0 + 11, y0 + 16), "log")
    track(gen, x0 + 8, y0 + 17)
    protect(gen, x0, y0, 26, 18)
    poi(gen, "the sawmill", x0 + 12, y0 + 8, 9)
    return True


def oil_tanks(gen):
    r = gen.rng
    at = spot(gen, 30, 20, dense_ok=0.6)
    if at is None:
        return False
    x0, y0 = at
    clear(gen, x0, y0, 30, 20, "dirt")
    ring(gen, x0, y0, 30, 20, "wire", gate=facing_road(gen, x0, y0, 30, 20), gaps=0.08, gate_w=2)
    for gx in range(x0 + 4, x0 + 27, 7):
        for gy in (y0 + 5, y0 + 13):
            if r.random() < 0.85:
                for ox in range(-2, 3):
                    for oy in range(-2, 3):
                        if max(abs(ox), abs(oy)) == 2:
                            put(gen, gx + ox, gy + oy, "rubble_earth")
                        elif max(abs(ox), abs(oy)) <= 1:
                            put(gen, gx + ox, gy + oy, "oil_tank")
    track(gen, x0 + 15, y0 + 19)
    protect(gen, x0, y0, 30, 20)
    poi(gen, "the oil tanks" if r.random() < 0.5 else "the tank farm", x0 + 15, y0 + 10, 10)
    return True


# ============================================================================ which, where
def menu(gen):
    """(weight, builder) for this sector's country and ground."""
    b = gen.m.biome
    cl = gen.m.climate
    lang = gen.spec.get("lang") or "en"
    east = bool(gen.spec.get("east")) or lang in ("ru", "uk")
    sea = gen.spec.get("sea_edge")
    th = gen.spec.get("theatre") or ""
    tropical = cl == "tropical" or b == "jungle"
    desert = cl == "desert" or b == "desert" or lang == "ar"
    open_country = b in ("farmland", "farmland_light", "village", "steppe", "hills", "bocage")
    m = []

    def add(w, f):
        if w > 0:
            m.append((w, f))
    if b in ("sea", "town", "city_ruins"):
        return m
    if not tropical and not desert:
        add((3 if lang in ("nl", "be", "fr", "gr", "uk", "ru") else 1.5) * (open_country or b == "marsh"), windmill)
        add(2 * (b in ("farmland", "farmland_light", "village", "steppe", "marsh", "factory")) +
            0.8 * (b in ("hills", "forest")), station)
        add(3 * (lang in ("fr", "be")) * (b in ("farmland", "bocage", "village", "forest", "hills",
                                                 "farmland_light")), chateau)
        add(2 * (open_country or b in ("forest", "mountain")), cemetery)
        add(1 * (open_country or b == "factory"), water_tower)
        add(1.5 * (lang in ("fr", "be", "nl", "de", "pl", "ru", "uk", "it")) * (open_country or b == "factory")
            + 2 * (b == "factory"), brickworks)
        add(2 * (b in ("hills", "mountain", "abbey")) + 0.8 * (cl == "mediterranean" and open_country), quarry)
        add(3 * (b == "factory") + 1.2 * (lang in ("be", "de", "pl", "uk")) * open_country, slag_heap)
        add(3.5 * east * (b in ("steppe", "farmland", "village", "factory")), grain_elevator)
        add(3 * east * (b in ("steppe", "farmland", "village", "farmland_light")), kolkhoz)
        add(2 * (lang in ("it", "fr", "de", "gr", "be")) * (b in ("hills", "mountain", "farmland", "village"))
            + 1.5 * (b == "abbey"), castle)
        add(2.5 * (b == "forest") + 0.6 * (b in ("hills", "mountain")), sawmill)
        add(2 * (b == "factory") + 1.0 * bool(sea), oil_tanks)
        add((1.5 + 2 * bool(sea)) * (lang in ("fr", "be", "nl", "de")) * (th not in ("france40", "poland39"))
            * (b in ("farmland", "bocage", "village", "hills", "farmland_light", "marsh")), radar_station)
        add(1.2 * (lang in ("fr", "it", "be", "nl")) * (b in ("farmland", "farmland_light", "village", "bocage")),
            airstrip)
    if tropical:
        add(3 * (lang in ("mel",)) + 0.8, plantation)
        add(2 * (lang in ("mel", "in", "my")) + 0.5, mission)
        add(4 * (lang == "ja"), shrine)
        add(3 * (lang in ("my", "zh")) + 1.0 * (lang == "in"), pagoda)
        add(2.5, airstrip)
    elif lang == "ja":
        add(4, shrine)
    if lang == "zh" and not tropical:
        add(3, pagoda)
    if desert:
        add(3, fort)
        add(3, marabout)
        add(2.5, airstrip)
        add(2 * (b == "desert"), oasis)
        add(1, water_tower)
        add(1.5 * (b in ("desert", "village")), station)
    if sea and b not in ("sea",):
        add(3, lighthouse)
    intensity = gen.spec.get("intensity", 0.5)
    if intensity >= 0.75 and not tropical and b not in ("forest", "mountain", "marsh"):
        add(1.5, wrecks)
    return m


def place(gen):
    """Build this sector's landmarks (mapgen.Gen.run calls this once the ground, the villages and the rivers
    are down, before the defences are dug)."""
    saved = gen.rng
    gen.rng = random.Random((gen.seed * 1000003 + 77) & 0x7FFFFFFF)
    try:
        r = gen.rng
        opts = menu(gen)
        n = int(round(1 + gen.k * 0.9 + r.random() * 0.8))
        done = 0
        while opts and done < n:
            tot = sum(w for w, _ in opts)
            pick = r.uniform(0, tot)
            for i, (w, f) in enumerate(opts):
                pick -= w
                if pick <= 0:
                    break
            w, f = opts.pop(i)
            try:
                if f(gen):
                    done += 1
            except (IndexError, ValueError):
                pass
        dress(gen)
    finally:
        gen.rng = saved


# ============================================================================ the smaller touches
def dress(gen):
    b = gen.m.biome
    lang = gen.spec.get("lang") or "en"
    name_buildings(gen, lang)
    if lang in MEMORIAL_LANGS:
        memorials(gen)
    if lang in CALVARY_LANGS and b not in ("sea", "desert", "jungle"):
        calvaries(gen)
    if lang in ("fr", "it", "be", "nl") and b in ("farmland", "farmland_light", "village", "hills"):
        poplars(gen)
    if b in ("steppe", "desert", "farmland", "farmland_light", "village") and gen.roads:
        longest = max(gen.roads, key=len)
        if len(longest) > 40:
            poles(gen, longest, side=2)


def name_buildings(gen, lang):
    r = gen.rng
    names = list(BUILDING_NAMES.get(lang) or BUILDING_NAMES["en"])
    r.shuffle(names)
    houses = [bb for bb in gen.m.buildings if bb[4] in ("house", "farmhouse", "townhouse", "izba", "desert_house",
                                                          "hut", "bungalow")]
    r.shuffle(houses)
    n = min(len(names), len(houses), 1 + (gen.k > 1.5) + (gen.k > 3) + (gen.m.biome in ("village", "town")))
    for bb, name in zip(houses[:n], names):
        x0, y0, bw, bh = bb[:4]
        poi(gen, name, x0 + bw // 2, y0 + bh // 2, 6)


def memorials(gen):
    """The memorial to the last war, where a commune has its church and its square; the first one a name on
    the map."""
    t = gen.m.t
    churches = [(x, y) for name, x, y, _ in gen.poi if name == "the church"]
    named = False
    for name, x, y, _rad in list(gen.poi):
        if name not in ("the village", "the town square"):
            continue
        if name == "the village" and not any(abs(cx - x) + abs(cy - y) < 30 for cx, cy in churches):
            continue
        for rr in range(0, 5):
            done = False
            for dx in range(-rr, rr + 1):
                for dy in range(-rr, rr + 1):
                    xx, yy = x + dx, y + dy
                    if not _in(gen, xx, yy, 2):
                        continue
                    k = T.DEFS[int(t[xx, yy])]
                    if not k.walk or k.floor or k.water or k.door:
                        continue
                    if gen.m.building_at(xx, yy) is not None:
                        continue
                    if any(T.DOOR[t[xx + ox, yy + oy]] for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                        continue
                    t[xx, yy] = _t("memorial")
                    if not named:
                        poi(gen, "the war memorial", xx, yy, 6)
                        named = True
                    if name == "the town square" and _in(gen, xx + 3, yy + 2, 2) and T.WALK[t[xx + 3, yy + 2]] \
                            and not T.FLOOR[t[xx + 3, yy + 2]]:
                        t[xx + 3, yy + 2] = _t("fountain")
                    done = True
                    break
                if done:
                    break
            if done:
                break


def calvaries(gen):
    t = gen.m.t
    r = gen.rng
    for i, (name, x, y, rad) in enumerate(list(gen.poi)):
        if name != "the crossroads":
            continue
        cands = []
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                xx, yy = x + dx, y + dy
                if not _in(gen, xx, yy, 2) or gen.protected[xx, yy]:
                    continue
                if not T.WALK[t[xx, yy]] or T.WATER[t[xx, yy]] or T.FLOOR[t[xx, yy]]:
                    continue
                if any(T.DEFS[int(t[xx + ox, yy + oy])].key in ("road", "paved", "cobble")
                       for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    cands.append((xx, yy))
        if not cands:
            continue
        cx, cy = r.choice(cands)
        t[cx, cy] = _t("calvary")
        gen.protected[cx, cy] = True
        if r.random() < 0.5:
            gen.poi[i] = ("the calvary", x, y, rad)


def poplars(gen):
    if not gen.roads:
        return
    t = gen.m.t
    rd = max(gen.roads, key=len)
    if len(rd) < 50:
        return
    r = gen.rng
    s = r.randint(5, max(6, len(rd) - 45))
    for i in range(s, min(len(rd) - 2, s + r.randint(30, 60)), 2):
        (ax, ay), (bx, by) = rd[i - 1], rd[i + 1]
        dx, dy = bx - ax, by - ay
        px, py = (-dy, dx) if (dx or dy) else (0, 1)
        n = max(1, int(round(math.hypot(px, py))))
        px, py = int(round(px / n)), int(round(py / n))
        x, y = rd[i]
        for sgn in (1, -1):
            xx, yy = x + px * 2 * sgn, y + py * 2 * sgn
            if _in(gen, xx, yy, 2) and not gen.protected[xx, yy] and T.WALK[t[xx, yy]] and not T.WATER[t[xx, yy]] \
                    and not T.FLOOR[t[xx, yy]]:
                t[xx, yy] = _t("poplar")


def poles(gen, pts, side=2, every=9):
    """Telegraph poles along a road or railway."""
    t = gen.m.t
    for i in range(every // 2, len(pts) - 1, every):
        (ax, ay), (bx, by) = pts[max(0, i - 1)], pts[min(len(pts) - 1, i + 1)]
        dx, dy = bx - ax, by - ay
        px, py = (-dy, dx) if (dx or dy) else (0, 1)
        n = max(1, abs(px) + abs(py))
        px, py = int(round(px / n)), int(round(py / n))
        x, y = pts[i][0] + px * side, pts[i][1] + py * side
        if _in(gen, x, y, 2) and not gen.protected[x, y] and T.WALK[t[x, y]] and not T.WATER[t[x, y]] \
                and not T.FLOOR[t[x, y]]:
            t[x, y] = _t("pole")


def fortify(gen):
    """After the defences are dug: Tobruk pits in a German line, stone sangars where the ground is rock."""
    if gen.fort < 1 or not gen.att:
        return
    r = random.Random((gen.seed * 7919 + 41) & 0x7FFFFFFF)
    t = gen.m.t
    axis = gen.spec.get("defender_side") == "axis"
    lang = gen.spec.get("lang")
    rocky = gen.m.climate == "desert" or gen.m.biome in ("mountain", "abbey", "hills", "volcanic") \
        and gen.m.climate != "tropical"
    if axis and gen.fort >= 2 and lang in ("fr", "be", "nl", "de", "it") and gen.m.biome not in ("jungle",):
        fh = _t("foxhole")
        for rec in gen.positions:
            if rec.get("kind") == "foxhole" and t[rec["x"], rec["y"]] == fh and r.random() < 0.3:
                t[rec["x"], rec["y"]] = _t("tobruk")
    if rocky:
        sb = _t("sandbags")
        sel = (t == sb) & (np.random.default_rng(gen.seed + 43).random(t.shape) < 0.6)
        t[sel] = _t("sangar")
