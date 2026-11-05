"""Battlefield tableaux: little scenes of the last few hours, laid down before the fighting starts.

A convoy shot up on the road, a dump that was meant to be further back, a farm burning, a gun pit
abandoned, an aircraft down in a field, a dressing station with its canvas still up.  They give a
sector something that happened on it, and something to use, burn or take cover behind.  Weighted
by the ground and how hard the battle has already been.
"""
from __future__ import annotations

import math
import random

from . import tiles as T


def _spot(gen, w, h):
    r = gen.rng
    for _ in range(60):
        x = r.randint(3, max(3, gen.w - w - 3))
        y = r.randint(3, max(3, gen.h - h - 3))
        sub = gen.m.t[x:x + w, y:y + h]
        if T.WATER[sub].any():
            continue
        if gen.protected[x:x + w, y:y + h].any():
            continue
        return x, y
    return None


def _scorch(gen, x, y, w, h):
    sc = getattr(gen.m, "scorch", None)
    if sc is not None:
        sc[max(0, x):x + w, max(0, y):y + h] = 1


def convoy(gen):
    r = gen.rng
    at = _spot(gen, 26, 16)
    if at is None:
        return False
    x0, y0 = at
    horiz = r.random() < 0.6
    for k in range(r.randint(2, 4)):
        cx = x0 + 2 + k * (6 if horiz else 0) + (0 if horiz else r.randint(0, 3))
        cy = y0 + 2 + k * (2 if horiz else 4) + (r.randint(0, 3) if horiz else 0)
        for dx in range(3):
            for dy in range(2):
                if r.random() < 0.85:
                    gen.m.t[cx + dx, cy + dy] = T.ID["wreck"]
        for _ in range(r.randint(2, 5)):
            xx, yy = cx + r.randint(-2, 4), cy + r.randint(-2, 3)
            gen.m.t[xx, yy] = T.ID[r.choice(("crates", "fuel_drums", "rubble_light"))]
        _scorch(gen, cx - 1, cy - 1, 5, 4)
    for _ in range(r.randint(5, 12)):
        gen.m.t[x0 + r.randint(0, 25), y0 + r.randint(0, 15)] = T.ID["crater"]
    gen.protected[x0:x0 + 26, y0:y0 + 16] = True
    gen.poi.append((r.choice(("the shot-up convoy", "the burnt convoy", "the ambushed column")), x0 + 13, y0 + 8, 9))
    return True


def dump(gen):
    r = gen.rng
    at = _spot(gen, 16, 12)
    if at is None:
        return False
    x0, y0 = at
    for x in range(x0 + 3, x0 + 13, 2):
        for y in range(y0 + 2, y0 + 6):
            if r.random() < 0.7:
                gen.m.t[x, y] = T.ID[r.choice(("ammo_stack", "fuel_drums", "crates"))]
    push = T.ID["sandbags"]
    for x in range(x0 + 2, x0 + 14):
        gen.m.t[x, y0 + 8] = push
    for _ in range(4):
        gen.m.t[x0 + 2, y0 + 2 + r.randint(0, 5)] = T.ID["canvas"]
    gen.protected[x0:x0 + 16, y0:y0 + 12] = True
    gen.poi.append(("the ammunition dump", x0 + 8, y0 + 4, 8))
    return True


def farm_fire(gen):
    r = gen.rng
    at = _spot(gen, 18, 14)
    if at is None:
        return False
    x0, y0 = at
    gen.building(x0 + 2, y0 + 2, 7, 5, "farmhouse", ruin=0.5)
    gen.building(x0 + 10, y0 + 4, 6, 5, "barn", ruin=0.75)
    for _ in range(12):
        xx, yy = x0 + r.randint(0, 17), y0 + r.randint(0, 13)
        gen.m.t[xx, yy] = T.ID[r.choice(("hay", "hay", "rubble_wood", "burnt"))]
    for _ in range(9):
        xx, yy = x0 + r.randint(1, 16), y0 + r.randint(1, 12)
        gen.m.fire[xx, yy] = r.randint(10, 60)
    _scorch(gen, x0, y0, 18, 14)
    gen.protected[x0:x0 + 18, y0:y0 + 14] = True
    gen.poi.append(("the burning farm", x0 + 9, y0 + 6, 8))
    return True


def gun_pit(gen):
    r = gen.rng
    at = _spot(gen, 14, 12)
    if at is None:
        return False
    x0, y0 = at
    for x in range(x0 + 2, x0 + 12):
        gen.m.t[x, y0 + 3] = T.ID["sandbags"]
    for y in range(y0 + 3, y0 + 8):
        gen.m.t[x0 + 2, y] = T.ID["sandbags"]
        gen.m.t[x0 + 11, y] = T.ID["sandbags"]
    gen.m.t[x0 + 6, y0 + 5] = T.ID["wreck"]
    for _ in range(5):
        gen.m.t[x0 + r.randint(3, 11), y0 + r.randint(4, 7)] = T.ID[r.choice(("ammo_stack", "crates",
                                                                              "rubble_light"))]
    for _ in range(4):
        gen.m.t[x0 + r.randint(0, 13), y0 + r.randint(0, 11)] = T.ID["crater"]
    gen.protected[x0:x0 + 14, y0:y0 + 12] = True
    gen.poi.append(("the gun pit", x0 + 6, y0 + 5, 7))
    return True


def crash(gen):
    from . import parked
    r = gen.rng
    at = _spot(gen, 16, 14)
    if at is None:
        return False
    x0, y0 = at
    th = gen.spec.get("theatre") or ""
    model, nation = (("zero", "japan") if th in ("guadalcanal42", "iwojima45", "okinawa45")
                     else ("il2", "ussr") if th in ("stalingrad42", "kursk43", "barbarossa41", "moscow41",
                                                    "berlin45", "karelia44", "uranus42", "don43")
                     else ("bf109", "germany") if th not in ("omaha44", "bocage44")
                     else ("p47", "usa"))
    facing = r.choice((0, 2))
    if not parked.fits(gen.m, model, x0 + 2, y0 + 2, facing):
        return False
    rec = parked.place(gen.m, model, x0 + 2, y0 + 2, facing, nation)
    parts = [(x, y) for x in range(rec["x"], rec["x"] + rec["w"]) for y in range(rec["y"], rec["y"] + rec["h"])
             if T.DEFS[int(gen.m.t[x, y])].key.startswith("ac_")]
    if parts:
        for x, y in r.sample(parts, k=max(1, len(parts) * 2 // 3)):
            gen.m.t[x, y] = T.ID[r.choice(("wreck", "rubble_light", "burnt"))]
    for _ in range(8):
        gen.m.t[x0 + r.randint(1, 14), y0 + r.randint(1, 12)] = T.ID["crater"]
    _scorch(gen, x0, y0, 16, 14)
    gen.protected[x0:x0 + 16, y0:y0 + 14] = True
    gen.poi.append(("the crashed aircraft", x0 + 8, y0 + 7, 8))
    return True


def dressing_station(gen):
    r = gen.rng
    at = _spot(gen, 13, 11)
    if at is None:
        return False
    x0, y0 = at
    for k in range(3):
        for dx in range(3):
            gen.m.t[x0 + 2 + k * 4 + dx, y0 + 2] = T.ID["canvas"]
    gen.m.t[x0 + 6, y0 + 3] = T.ID["checkpoint"]
    for _ in range(5):
        gen.m.t[x0 + r.randint(2, 10), y0 + r.randint(4, 8)] = T.ID["grave"]
    for _ in range(3):
        gen.m.t[x0 + r.randint(2, 10), y0 + r.randint(4, 8)] = T.ID["crates"]
    gen.protected[x0:x0 + 13, y0:y0 + 11] = True
    gen.poi.append(("the dressing station", x0 + 6, y0 + 4, 7))
    return True


TABLE = (
    (convoy, 1.5),
    (dump, 1.2),
    (farm_fire, 1.4),
    (gun_pit, 1.3),
    (crash, 0.9),
    (dressing_station, 1.0),
)


def place(gen):
    """One or two scenes, and more where the fighting has already been heavy."""
    r = gen.rng
    intensity = gen.spec.get("intensity", 0.5)
    n = 1 + (r.random() < intensity * 0.8) + (r.random() < intensity * 0.35)
    table = list(TABLE)
    if gen.m.biome in ("desert", "jungle"):
        table = [(f, w * (0.4 if f is farm_fire else 1.0)) for f, w in table]
    done = 0
    while table and done < n:
        tot = sum(w for _, w in table)
        pick = r.uniform(0, tot)
        for i, (f, w) in enumerate(table):
            pick -= w
            if pick <= 0:
                break
        f, _w = table.pop(i)
        try:
            if f(gen):
                done += 1
        except (IndexError, ValueError):
            pass
