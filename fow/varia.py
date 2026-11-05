"""The country's furniture that isn't a landmark: sidings, canals, sunken lanes, kilns and cages.

Landmarks make the places people remember.  This makes the places people pass through - and the
things the war has done to them.  Each builder claims its own patch of free ground and protects it,
so anything after can work around it.  One rare set piece in six maps changes the shape of the
battle outright: an overrun strip, a flooded crossing, a rail junction.
"""
from __future__ import annotations

import numpy as np

from . import tiles as T


def _L():
    from . import landmarks
    return landmarks


def _in(gen, x, y, pad=1):
    return pad <= x < gen.w - pad and pad <= y < gen.h - pad


def _put(gen, x, y, key):
    if _in(gen, x, y) and not T.WATER[gen.m.t[x, y]]:
        gen.m.t[x, y] = T.ID[key]


def _line(gen, x0, y0, x1, y1, key, w=1):
    n = max(abs(x1 - x0), abs(y1 - y0))
    for i in range(n + 1):
        x = round(x0 + (x1 - x0) * i / max(1, n))
        y = round(y0 + (y1 - y0) * i / max(1, n))
        for dx in range(w):
            for dy in range(w):
                _put(gen, x + dx, y + dy, key)


def _band(gen, x0, y0, w, h, key):
    for x in range(x0, x0 + w):
        for y in range(y0, y0 + h):
            _put(gen, x, y, key)


# ============================================================================ the ordinary
def railway(gen):
    """A single-track line on its ballast, with a siding and the telegraph beside it."""
    L = _L()
    at = L.spot(gen, 22, 14, dense_ok=0.8, depth=(0.15, 0.85))
    if at is None:
        return False
    x0, y0 = at
    horizontal = gen.rng.random() < 0.5
    if horizontal:
        y = y0 + 7
        _band(gen, x0, y, 22, 1, "rail")
        _band(gen, x0, y - 1, 22, 3, "rail_ballast")
        for x in range(x0, x0 + 22, 3):
            _put(gen, x, y, "rail")
            _put(gen, x, y - 5, "telegraph_pole")
        # siding
        sy = y + 3
        _band(gen, x0 + 5, sy, 9, 1, "rail")
        _put(gen, x0 + 7, sy, "boxcar")
        for _ in range(4):
            _put(gen, x0 + gen.rng.randint(9, 13), sy + 1, gen.rng.choice(("sleeper_stack", "crates", "sacks")))
        _put(gen, x0 + 3, y, "level_crossing")
        _put(gen, x0 + 3, y, "culvert")
        L.poi(gen, "the railway", x0 + 11, y, 9)
    else:
        x = x0 + 7
        _band(gen, x, y0, 1, 22, "rail")
        _band(gen, x - 1, y0, 3, 22, "rail_ballast")
        for y in range(y0, y0 + 22, 3):
            _put(gen, x, y, "rail")
            _put(gen, x - 5, y, "telegraph_pole")
        sx = x + 3
        _band(gen, sx, y0 + 5, 1, 9, "rail")
        _put(gen, sx, y0 + 7, "boxcar")
        for _ in range(4):
            _put(gen, sx + 1, y0 + gen.rng.randint(9, 13), gen.rng.choice(("sleeper_stack", "crates", "sacks")))
        _put(gen, x, y0 + 3, "level_crossing")
        _put(gen, x, y0 + 3, "culvert")
        L.poi(gen, "the railway", x, y0 + 11, 9)
    L.protect(gen, x0, y0, 22, 14)
    return True


def canal(gen):
    L = _L()
    at = L.spot(gen, 20, 13, dense_ok=0.85)
    if at is None:
        return False
    x0, y0 = at
    horizontal = gen.rng.random() < 0.5
    if horizontal:
        y = y0 + 6
        _band(gen, x0, y, 20, 2, "shallow")
        _band(gen, x0, y + 2, 20, 1, "dirt")
        _put(gen, x0 + 4, y, "lock_gate")
        _put(gen, x0 + 14, y, "barge")
        _put(gen, x0 + 14, y + 1, "barge")
        _put(gen, x0 + 16, y, "culvert")
    else:
        x = x0 + 6
        _band(gen, x, y0, 2, 20, "shallow")
        _band(gen, x + 2, y0, 1, 20, "dirt")
        _put(gen, x, y0 + 4, "lock_gate")
        _put(gen, x, y0 + 14, "barge")
        _put(gen, x + 1, y0 + 14, "barge")
        _put(gen, x, y0 + 16, "culvert")
    L.poi(gen, "the canal", x0 + 10, y0 + 6, 9)
    L.protect(gen, x0, y0, 20, 13)
    return True


def sunken_lane(gen):
    L = _L()
    at = L.spot(gen, 20, 9, dense_ok=0.9)
    if at is None:
        return False
    x0, y0 = at
    y = y0 + 4
    _band(gen, x0, y, 20, 1, "dirt")
    for x in range(x0, x0 + 20):
        for yy in (y - 1, y + 1):
            if gen.rng.random() < 0.85:
                _put(gen, x, yy, "hedge")
        if gen.rng.random() < 0.15:
            _put(gen, x, y, "mud")
    for x in (x0 + 3, x0 + 9, x0 + 16):
        _put(gen, x, y - 1, "gate")
    L.poi(gen, "the sunken lane", x0 + 10, y, 7)
    L.protect(gen, x0, y0, 20, 9)
    return True


def crossroads_hamlet(gen):
    L = _L()
    at = L.spot(gen, 16, 14, dense_ok=0.6)
    if at is None:
        return False
    x0, y0 = at
    cx, cy = x0 + 8, y0 + 7
    _band(gen, x0, cy, 16, 1, "dirt")
    _band(gen, cx, y0, 1, 14, "dirt")
    for dx, dy, style in ((-5, -4, "house"), (2, -5, "barn"), (2, 2, "house")):
        L._building(gen, cx + dx, cy + dy, 4, 4, style, rooms=False)
    _put(gen, cx + 1, cy + 1, "well")
    _put(gen, cx - 1, cy, "sign")
    _put(gen, cx + 4, cy - 1, "haystack")
    _put(gen, cx - 4, cy + 3, "handcart")
    L.poi(gen, "the crossroads", cx, cy, 8)
    L.protect(gen, x0, y0, 16, 14)
    return True


def orchard_rows(gen):
    L = _L()
    at = L.spot(gen, 15, 12, dense_ok=0.4)
    if at is None:
        return False
    x0, y0 = at
    L.clear(gen, x0, y0, 15, 12, "orchard_ground")
    tree = gen.rng.choice(("apple_tree", "olive", "tree"))
    for x in range(x0 + 1, x0 + 15, 3):
        for y in range(y0 + 1, y0 + 12, 3):
            _put(gen, x, y, tree)
    for x in range(x0, x0 + 15):
        _put(gen, x, y0, "low_wall" if gen.rng.random() < 0.5 else "fence_h")
        _put(gen, x, y0 + 11, "fence_h")
    L.poi(gen, "the orchard", x0 + 7, y0 + 6, 7)
    L.protect(gen, x0, y0, 15, 12)
    return True


def hop_garden(gen):
    L = _L()
    at = L.spot(gen, 14, 10, dense_ok=0.4)
    if at is None:
        return False
    x0, y0 = at
    L.clear(gen, x0, y0, 14, 10, gen.key("tall"))
    for x in range(x0 + 1, x0 + 14, 2):
        for y in range(y0 + 1, y0 + 10):
            if gen.rng.random() < 0.6:
                _put(gen, x, y, "hop_poles")
    for y in (y0, y0 + 9):
        _band(gen, x0, y, 14, 1, "fence_h")
    L.poi(gen, "the hop garden", x0 + 7, y0 + 5, 6)
    L.protect(gen, x0, y0, 14, 10)
    return True


def terraces(gen):
    L = _L()
    at = L.spot(gen, 16, 12, dense_ok=0.5)
    if at is None:
        return False
    x0, y0 = at
    for y in range(y0 + 1, y0 + 12, 3):
        _band(gen, x0, y, 16, 1, "low_wall")
        for x in range(x0 + 1, x0 + 15, 2):
            _put(gen, x, y - 1, "plowed_ridges" if gen.rng.random() < 0.6 else "terrace")
        if gen.rng.random() < 0.6:
            _put(gen, x0 + gen.rng.randint(2, 13), y, "stile")
    L.poi(gen, "the terraces", x0 + 8, y0 + 6, 7)
    L.protect(gen, x0, y0, 16, 12)
    return True


def drainage(gen):
    L = _L()
    at = L.spot(gen, 16, 12, dense_ok=0.6)
    if at is None:
        return False
    x0, y0 = at
    for y in range(y0 + 2, y0 + 12, 4):
        _band(gen, x0, y, 16, 1, "shallow")
        for x in range(x0, x0 + 16):
            if gen.rng.random() < 0.5:
                _put(gen, x, y - 1, "waterlogged")
        for x in range(x0 + 2, x0 + 16, 5):
            _put(gen, x, y, "dirt")
    for _ in range(3):
        _put(gen, gen.rng.randint(x0 + 1, x0 + 14), gen.rng.randint(y0 + 1, y0 + 11), "reeds")
    L.protect(gen, x0, y0, 16, 12)
    return True


def kilns(gen):
    L = _L()
    at = L.spot(gen, 13, 10, dense_ok=0.6)
    if at is None:
        return False
    x0, y0 = at
    L.clear(gen, x0, y0, 13, 10, "cinder")
    L._building(gen, x0 + 2, y0 + 2, 3, 3, "factory", ruin=0.3)
    _put(gen, x0 + 2, y0 + 2, "kiln")
    _put(gen, x0 + 4, y0 + 2, "lime_kiln")
    for _ in range(7):
        _put(gen, gen.rng.randint(x0 + 6, x0 + 12), gen.rng.randint(y0 + 1, y0 + 8),
             gen.rng.choice(("cordwood", "coal_heap", "brick_pile" if "brick_pile" in T.ID else "rubble")))
    L.poi(gen, "the kilns", x0 + 6, y0 + 5, 7)
    L.protect(gen, x0, y0, 13, 10)
    return True


def charcoal_burn(gen):
    L = _L()
    at = L.spot(gen, 11, 10, dense_ok=0.3)
    if at is None:
        return False
    x0, y0 = at
    L.clear(gen, x0, y0, 11, 10, "burnt")
    for _ in range(4):
        _put(gen, gen.rng.randint(x0 + 1, x0 + 9), gen.rng.randint(y0 + 1, y0 + 8), "charcoal_stack")
    for _ in range(6):
        _put(gen, gen.rng.randint(x0, x0 + 10), gen.rng.randint(y0, y0 + 9), "dead_tree")
    L.poi(gen, "the charcoal burn", x0 + 5, y0 + 5, 6)
    L.protect(gen, x0, y0, 11, 10)
    return True


def sheepfold(gen):
    L = _L()
    at = L.spot(gen, 12, 10, dense_ok=0.4)
    if at is None:
        return False
    x0, y0 = at
    L.clear(gen, x0, y0, 12, 10, gen.key("ground"))
    gate = L.ring(gen, x0 + 1, y0 + 1, 8, 7, "sheepfold", gate="S", gaps=0.12)
    L._building(gen, x0 + 2, y0 + 2, 3, 3, "shed", ruin=0.2)
    _put(gen, x0 + 7, y0 + 3, "water_trough")
    if gate:
        _put(gen, *L.outside(gate, "S"), "gate")
    L.poi(gen, "the sheepfold", x0 + 5, y0 + 5, 6)
    L.protect(gen, x0, y0, 12, 10)
    return True


def paddy_terraces(gen):
    L = _L()
    at = L.spot(gen, 16, 12, dense_ok=0.7)
    if at is None:
        return False
    x0, y0 = at
    for y in range(y0, y0 + 12, 3):
        _band(gen, x0, y, 16, 2, "paddy")
        _band(gen, x0, y + 2, 16, 1, "terrace")
        for x in range(x0, x0 + 16, 4):
            _put(gen, x, y + 2, "paddy_stubble")
    for _ in range(5):
        _put(gen, gen.rng.randint(x0, x0 + 15), gen.rng.randint(y0, y0 + 11), "reeds")
    L.poi(gen, "the paddies", x0 + 8, y0 + 6, 7)
    L.protect(gen, x0, y0, 16, 12)
    return True


def coconut_grove(gen):
    L = _L()
    at = L.spot(gen, 14, 11, dense_ok=0.4)
    if at is None:
        return False
    x0, y0 = at
    L.clear(gen, x0, y0, 14, 11, "grass")
    for x in range(x0 + 1, x0 + 14, 3):
        for y in range(y0 + 1, y0 + 11, 3):
            if gen.rng.random() < 0.8:
                _put(gen, x, y, "palm")
    for _ in range(3):
        _put(gen, gen.rng.randint(x0 + 2, x0 + 11), gen.rng.randint(y0 + 2, y0 + 8), "bush")
    L.poi(gen, "the palms", x0 + 7, y0 + 5, 6)
    L.protect(gen, x0, y0, 14, 11)
    return True


def supply_point(gen):
    L = _L()
    at = L.spot(gen, 12, 9, dense_ok=0.6)
    if at is None:
        return False
    x0, y0 = at
    L.clear(gen, x0, y0, 12, 9, "dirt")
    for _ in range(6):
        _put(gen, gen.rng.randint(x0 + 1, x0 + 10), gen.rng.randint(y0 + 1, y0 + 7),
             gen.rng.choice(("crates", "sacks", "fuel_drums", "ammo_stack")))
    for _ in range(4):
        _put(gen, gen.rng.randint(x0 + 1, x0 + 10), gen.rng.randint(y0 + 1, y0 + 7), "camo_net")
    gate = gen.rng.choice(("N", "S", "E", "W"))
    x, y = L.outside((x0 + 6, y0 + 4), gate)
    _put(gen, x, y, "checkpoint")
    L.poi(gen, "the supply point", x0 + 6, y0 + 4, 6)
    L.protect(gen, x0, y0, 12, 9)
    return True


def aid_station(gen):
    L = _L()
    at = L.spot(gen, 12, 10, dense_ok=0.6)
    if at is None:
        return False
    x0, y0 = at
    L.clear(gen, x0, y0, 12, 10, "dirt")
    for x, y in ((x0 + 2, y0 + 2), (x0 + 7, y0 + 2)):
        gen.building(x, y, 4, 3, "shed")
        _put(gen, x, y, "canvas")
    _put(gen, x0 + 3, y0 + 6, "redcross")
    for x in (x0 + 2, x0 + 5, x0 + 8):
        _put(gen, x, y0 + 7, "hospital_bed")
    for _ in range(3):
        _put(gen, gen.rng.randint(x0 + 1, x0 + 9), y0 + 5, "medical_store")
    L.poi(gen, "the aid station", x0 + 5, y0 + 5, 7)
    L.protect(gen, x0, y0, 12, 10)
    return True


def pow_cage(gen):
    L = _L()
    at = L.spot(gen, 12, 10, dense_ok=0.5)
    if at is None:
        return False
    x0, y0 = at
    L.clear(gen, x0, y0, 12, 10, "mud")
    L.ring(gen, x0 + 1, y0 + 1, 9, 8, "wire", gate="S", gaps=0.1)
    for x, y in ((x0 + 2, y0 + 2), (x0 + 6, y0 + 2), (x0 + 2, y0 + 6), (x0 + 6, y0 + 6)):
        gen.building(x, y, 2, 2, "hut", rooms=False)
    _put(gen, x0 + 1, y0 + 1, "lookout_post")
    _put(gen, x0 + 5, y0 + 4, "sign")
    L.poi(gen, "the prisoner cage", x0 + 5, y0 + 5, 7)
    L.protect(gen, x0, y0, 12, 10)
    return True


def mortar_pits(gen):
    L = _L()
    at = L.spot(gen, 12, 10, dense_ok=0.6)
    if at is None:
        return False
    x0, y0 = at
    for dx, dy in ((2, 2), (7, 3), (4, 6)):
        _put(gen, x0 + dx, y0 + dy, "gun_pit")
        _put(gen, x0 + dx + 1, y0 + dy, "ammo_stack")
        for ox, oy in ((0, -1), (1, -1), (-1, 0), (2, 0)):
            if gen.rng.random() < 0.7:
                _put(gen, x0 + dx + ox, y0 + dy + oy, "sandbags")
    for _ in range(4):
        _put(gen, gen.rng.randint(x0, x0 + 11), gen.rng.randint(y0 + 7, y0 + 9), "camo_net")
    L.poi(gen, "the mortar pits", x0 + 5, y0 + 5, 7)
    L.protect(gen, x0, y0, 12, 10)
    return True


def wrecked_column(gen):
    L = _L()
    at = L.spot(gen, 18, 9, dense_ok=0.8, roads_ok=True)
    if at is None:
        return False
    x0, y0 = at
    y = y0 + 4
    for x in range(x0, x0 + 18):
        _put(gen, x, y, "dirt")
        if gen.rng.random() < 0.3:
            _put(gen, x, y + gen.rng.choice((-1, 1)), "crater")
    for x in (x0 + 2, x0 + 8, x0 + 14):
        _put(gen, x, y, "wreck")
        for _ in range(2):
            _put(gen, x + gen.rng.randint(-1, 1), y + gen.rng.choice((-1, 1)),
                 gen.rng.choice(("crates", "sacks", "fuel_drums", "rubble_wood")))
    _put(gen, x0 + 5, y + 1, "dead_tree")
    _put(gen, x0 + 11, y - 1, "dead_tree")
    L.poi(gen, "the wrecked column", x0 + 8, y, 9)
    L.protect(gen, x0, y0, 18, 9)
    return True


def mine_strip(gen):
    L = _L()
    at = L.spot(gen, 16, 8, dense_ok=0.8)
    if at is None:
        return False
    x0, y0 = at
    y = y0 + 4
    for x in range(x0, x0 + 16):
        if gen.rng.random() < 0.6:
            _put(gen, x, y, "wire")
        if x % 4 == 0:
            _put(gen, x, y - 1, "sign")
    _put(gen, x0 + 8, y + 2, "sangar")
    L.poi(gen, "the minefield", x0 + 8, y, 8)
    L.protect(gen, x0, y0, 16, 8)
    return True


def tank_traps(gen):
    L = _L()
    at = L.spot(gen, 18, 8, dense_ok=0.85)
    if at is None:
        return False
    x0, y0 = at
    y = y0 + 4
    for x in range(x0, x0 + 18):
        if x % 7 in (0, 1):
            continue
        _put(gen, x, y, gen.rng.choice(("teeth", "hedgehog")))
        if gen.rng.random() < 0.4:
            _put(gen, x, y + 1, "tank_ditch")
    L.poi(gen, "the anti-tank line", x0 + 9, y, 8)
    L.protect(gen, x0, y0, 18, 8)
    return True


def dugout_line(gen):
    L = _L()
    at = L.spot(gen, 18, 9, dense_ok=0.85)
    if at is None:
        return False
    x0, y0 = at
    y = y0 + 5
    _band(gen, x0, y, 18, 1, "trench")
    for x in range(x0 + 2, x0 + 17, 5):
        _put(gen, x, y - 1, "dugout")
        _put(gen, x + 1, y - 1, "sandbags")
    _put(gen, x0 + 1, y + 1, "wire")
    _put(gen, x0 + 9, y + 1, "sign")
    L.poi(gen, "the dugouts", x0 + 9, y, 8)
    L.protect(gen, x0, y0, 18, 9)
    return True


def flooded_meadow(gen):
    L = _L()
    at = L.spot(gen, 16, 11, dense_ok=0.7)
    if at is None:
        return False
    x0, y0 = at
    for _ in range(5):
        cx, cy = gen.rng.randint(x0 + 2, x0 + 13), gen.rng.randint(y0 + 2, y0 + 8)
        rad = gen.rng.randint(2, 4)
        for x in range(cx - rad, cx + rad + 1):
            for y in range(cy - rad, cy + rad + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= rad * rad:
                    _put(gen, x, y, "shallow" if gen.rng.random() < 0.6 else "waterlogged")
    for _ in range(4):
        _put(gen, gen.rng.randint(x0, x0 + 15), gen.rng.randint(y0, y0 + 10), "reeds")
    L.poi(gen, "the floodwater", x0 + 8, y0 + 5, 7)
    L.protect(gen, x0, y0, 16, 11)
    return True


def labour_camp(gen):
    """A wire enclosure of long huts: a work camp, and its small stone marker."""
    L = _L()
    at = L.spot(gen, 20, 14, dense_ok=0.5)
    if at is None:
        return False
    x0, y0 = at
    L.clear(gen, x0, y0, 20, 14, "mud")
    L.ring(gen, x0 + 1, y0 + 1, 18, 12, "wire", gate="S", gaps=0.06)
    for k in range(3):
        gen.building(x0 + 3, y0 + 2 + k * 4, 10, 2, "hut", rooms=False)
    _put(gen, x0 + 1, y0 + 1, "lookout_post")
    _put(gen, x0 + 16, y0 + 3, "marker")
    _put(gen, x0 + 15, y0 + 6, "well")
    _put(gen, x0 + 9, y0 + 12, "sign")
    gen.positions.append(dict(kind="history", side=None, x=x0 + 16, y=y0 + 3,
                              name="a work camp", note="Barbed wire, long huts, and a plain marker for those "
                              "who did not leave it."))
    L.poi(gen, "the camp", x0 + 10, y0 + 7, 10)
    L.protect(gen, x0, y0, 20, 14)
    return True


# ============================================================================ rare set pieces
def overrun_airstrip(gen):
    L = _L()
    at = L.spot(gen, 30, 20, dense_ok=0.9, roads_ok=True)
    if at is None:
        return False
    x0, y0 = at
    _band(gen, x0, y0 + 8, 30, 5, "runway")
    for _ in range(4):
        _put(gen, gen.rng.randint(x0 + 2, x0 + 27), y0 + gen.rng.choice((6, 14)), "plane_parked")
    for _ in range(5):
        _put(gen, gen.rng.randint(x0 + 1, x0 + 28), y0 + gen.rng.randint(1, 18),
             gen.rng.choice(("fuel_drums", "avgas", "crates", "canvas", "wreck")))
    for _ in range(6):
        _put(gen, gen.rng.randint(x0, x0 + 29), y0 + gen.rng.randint(0, 19), "crater")
    L.poi(gen, "the overrun strip", x0 + 15, y0 + 10, 12)
    L.protect(gen, x0, y0, 30, 20)
    return True


def rail_junction(gen):
    L = _L()
    at = L.spot(gen, 24, 20, dense_ok=0.9, roads_ok=True)
    if at is None:
        return False
    x0, y0 = at
    _band(gen, x0, y0 + 6, 24, 3, "rail_ballast")
    _band(gen, x0, y0 + 7, 24, 1, "rail")
    _band(gen, x0 + 12, y0, 3, 20, "rail_ballast")
    _band(gen, x0 + 13, y0, 1, 20, "rail")
    _put(gen, x0 + 13, y0 + 7, "level_crossing")
    for k in range(3):
        _band(gen, x0 + 2, y0 + 11 + k * 2, 9, 1, "rail")
        _put(gen, x0 + 3, y0 + 11 + k * 2, "boxcar")
    for _ in range(5):
        _put(gen, gen.rng.randint(x0, x0 + 23), gen.rng.randint(y0, y0 + 19), "sleeper_stack")
    _put(gen, x0 + 5, y0 + 8, "station")
    _put(gen, x0 + 18, y0 + 4, "signal" if "signal" in T.ID else "telegraph_pole")
    L.poi(gen, "the rail junction", x0 + 12, y0 + 10, 12)
    L.protect(gen, x0, y0, 24, 20)
    return True


def flooded_crossing(gen):
    L = _L()
    at = L.spot(gen, 22, 16, dense_ok=0.9)
    if at is None:
        return False
    x0, y0 = at
    _band(gen, x0, y0 + 7, 22, 3, "shallow")
    _band(gen, x0, y0 + 8, 22, 1, "deep")
    _put(gen, x0 + 11, y0 + 7, "bridge")
    _put(gen, x0 + 11, y0 + 8, "bridge")
    _put(gen, x0 + 10, y0 + 7, "culvert")
    _put(gen, x0 + 10, y0 + 8, "culvert")
    _band(gen, x0, y0 + 6, 22, 1, "wet_sand")
    for _ in range(8):
        _put(gen, gen.rng.randint(x0, x0 + 21), gen.rng.randint(y0, y0 + 15), "reeds")
    for _ in range(3):
        _put(gen, gen.rng.randint(x0, x0 + 21), y0 + 7, "barge")
    L.poi(gen, "the crossing", x0 + 11, y0 + 7, 11)
    L.protect(gen, x0, y0, 22, 16)
    return True


def field_hospital(gen):
    L = _L()
    at = L.spot(gen, 20, 16, dense_ok=0.7)
    if at is None:
        return False
    x0, y0 = at
    L.clear(gen, x0, y0, 20, 16, "dirt")
    for k in range(3):
        gen.building(x0 + 2, y0 + 2 + k * 4, 8, 3, "shed")
        _put(gen, x0 + 2, y0 + 2 + k * 4, "canvas")
    for k in range(3):
        gen.building(x0 + 12, y0 + 2 + k * 4, 6, 3, "shed")
        _put(gen, x0 + 12, y0 + 2 + k * 4, "canvas")
    _put(gen, x0 + 9, y0 + 1, "redcross")
    for x in range(x0 + 2, x0 + 18, 3):
        _put(gen, x, y0 + 14, "hospital_bed")
    for _ in range(6):
        _put(gen, gen.rng.randint(x0 + 1, x0 + 18), gen.rng.randint(y0 + 12, y0 + 15), "medical_store")
    L.poi(gen, "the field hospital", x0 + 10, y0 + 8, 12)
    L.protect(gen, x0, y0, 20, 16)
    return True


def burning_forest(gen):
    L = _L()
    at = L.spot(gen, 20, 16, dense_ok=0.2)
    if at is None:
        return False
    x0, y0 = at
    for x in range(x0, x0 + 20):
        for y in range(y0, y0 + 16):
            if gen.rng.random() < 0.45:
                _put(gen, x, y, "dead_tree")
            elif gen.rng.random() < 0.5:
                _put(gen, x, y, "burnt")
    for _ in range(8):
        _put(gen, gen.rng.randint(x0, x0 + 19), gen.rng.randint(y0, y0 + 15), "crater")
    L.poi(gen, "the burnt wood", x0 + 10, y0 + 8, 9)
    L.protect(gen, x0, y0, 20, 16)
    return True


def rare(gen):
    """One set piece, weighted by ground, or None."""
    r = gen.rng
    b = gen.m.biome
    cl = gen.m.climate
    opts = []
    if b not in ("sea", "desert"):
        opts += [(1.0, field_hospital) if b in ("factory", "town", "city_ruins") else (0.35, field_hospital)]
        opts += [(1.2, overrun_airstrip) if b in ("farmland", "farmland_light", "steppe", "village", "volcanic")
                 else (0.2, overrun_airstrip)]
        opts += [(0.8, railway), (0.7, rail_junction) if b in ("factory", "town", "city_ruins", "village") else (0.15, rail_junction)]
        opts += [(0.6, burning_forest)]
        if b in ("forest", "hills", "mountain"):
            opts += [(1.4, burning_forest)]
    if b in ("marsh", "farmland", "farmland_light", "village") or gen.spec.get("river"):
        opts += [(0.8, flooded_crossing)]
    if b == "tropical":
        opts += [(0.9, paddy_terraces), (0.7, coconut_grove), (0.5, flooded_crossing)]
    if b in ("desert", "steppe"):
        opts += [(0.8, tank_traps), (0.6, mine_strip)]
    if not opts:
        return None
    tot = sum(w for w, _ in opts)
    pick = r.uniform(0, tot)
    for w, f in opts:
        pick -= w
        if pick <= 0:
            return f
    return opts[-1][1]


def menu(gen):
    """(weight, builder) of the small country furniture for this ground."""
    L = _L()
    b = gen.m.biome
    cl = gen.m.climate
    lang = gen.spec.get("lang") or "en"
    east = bool(gen.spec.get("east")) or lang in ("ru", "uk")
    tropical = cl == "tropical" or b == "jungle"
    desert = cl == "desert" or b == "desert"
    open_country = b in ("farmland", "farmland_light", "village", "steppe", "hills", "bocage")
    urban = b in ("factory", "town", "city_ruins", "abbey")
    wooded = b in ("forest", "hills", "mountain", "jungle")
    wet = b in ("marsh", "farmland", "farmland_light", "jungle") or bool(gen.spec.get("river"))
    m = []

    def add(w, f):
        if w > 0:
            m.append((w, f))

    if b in ("sea", "city_ruins"):
        return m
    if not tropical and not desert:
        add(1.5 * (open_country or urban), railway)
        add(1.0 * (lang in ("nl", "be", "de", "it") and open_country) + 0.5 * wet, canal)
        add(1.2 * (b in ("bocage", "village", "farmland")), sunken_lane)
        add(1.0 * open_country, crossroads_hamlet)
        add(1.2 * (open_country or wooded), orchard_rows)
        add(0.8 * (lang in ("be", "de", "en") and open_country), hop_garden)
        add(1.2 * (b in ("hills", "mountain", "abbey")), terraces)
        add(1.0 * (lang in ("nl", "be", "it") and open_country) + 0.5 * wet, drainage)
        add(0.7 * (b in ("factory", "village", "farmland", "hills")), kilns)
        add(1.1 * (wooded or east), charcoal_burn)
        add(1.0 * (b in ("hills", "mountain") or (open_country and lang in ("gr", "it", "es"))), sheepfold)
        add(1.0 * (east and open_country), L.kolkhoz)
        add(0.8 * urban, supply_point)
        add(0.8 * urban, aid_station)
        add(0.6 * (east and not urban), pow_cage)
        add(0.9 * (b in ("hills", "village", "farmland")), mortar_pits)
        add(0.8 * (open_country or urban), wrecked_column)
        add(0.7 * (open_country and gen.spec.get("fort", 0)), mine_strip)
        add(0.8 * (open_country and gen.spec.get("fort", 0)), tank_traps)
        add(0.7 * (gen.spec.get("fort", 0) >= 2), dugout_line)
        add(0.6 * east, labour_camp)
        add(0.6 * wet, flooded_meadow)
    if tropical:
        add(1.4, paddy_terraces)
        add(1.0, coconut_grove)
        add(0.8, crossroads_hamlet)
        add(0.6, drainage)
        add(0.5, railway)
        add(0.5, aid_station)
    if desert:
        add(0.9, tank_traps)
        add(0.9, mine_strip)
        add(0.6, supply_point)
        add(0.5, crossroads_hamlet)
    return m
