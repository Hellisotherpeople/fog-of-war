"""Aircraft on the ground, at their real size.

A parked aircraft is as big as it really was, at about two metres a tile: a Bf 109 or a Spitfire five tiles
by five, a Stuka seven by five, a He 111 eleven by eight, a Ju 52 fifteen by nine, a B-17 sixteen by eleven.
Each tile under it is a part, with that part's physics:
- the fuselage (you can't get through, it hides you and stops little);
- an engine (the one thing on an aircraft that stops a bullet);
- the wings (you can duck under, slowly; there's fuel in them);
- the tailplane.
The fuselage and wings burn and blow up when they're hit hard enough, and what's left is a burnt-out
wreck.

The same planform - wings, fuselage, nacelles, tailplane, from the real span, length and layout - decides
which tile is which part and is what sprites.paint_parked draws across the tiles.  The map keeps a record of
each aircraft (m.parked) so it can be drawn whole, named when you look at it, and saved with the sector.
Carrier aircraft on deck and in the hangar have their wings folded, as they were.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from . import tiles as T

TILE_M = 2.0          # metres a tile (yards() in play.py: 2.2 yards)

# id: (span m, length m, engines, folded span m or 0, layout)
# layout: "mono" single-engine; "twin"/"three"/"four" multi-engine; "twinboom" (P-38); "jet"; "biplane"
DIMS = {
    "p47": (12.4, 11.0, 1, 0, "mono"), "p51": (11.3, 9.8, 1, 0, "mono"), "p38": (15.9, 11.5, 2, 0, "twinboom"),
    "p40": (11.4, 9.7, 1, 0, "mono"), "f4u": (12.5, 10.2, 1, 5.2, "mono"), "sbd": (12.7, 10.1, 1, 0, "mono"),
    "b25": (20.6, 16.1, 2, 0, "twin"), "b17": (31.6, 22.7, 4, 0, "four"), "typhoon": (12.7, 9.7, 1, 0, "mono"),
    "spitfire": (11.2, 9.1, 1, 0, "mono"), "hurricane": (12.2, 9.8, 1, 0, "mono"),
    "beaufighter": (17.6, 12.6, 2, 0, "twin"), "blenheim": (17.2, 12.1, 2, 0, "twin"),
    "lancaster": (31.1, 21.1, 4, 0, "four"), "il2": (14.6, 11.6, 1, 0, "mono"), "yak9": (9.7, 8.5, 1, 0, "mono"),
    "i16": (9.0, 6.1, 1, 0, "mono"), "pe2": (17.2, 12.7, 2, 0, "twin"), "po2": (11.4, 8.2, 1, 0, "biplane"),
    "bf109": (9.9, 9.0, 1, 0, "mono"), "fw190": (10.5, 9.0, 1, 0, "mono"), "ju87": (13.8, 11.0, 1, 0, "mono"),
    "ju87g": (15.0, 11.5, 1, 0, "mono"), "hs129": (14.2, 9.8, 2, 0, "twin"), "ju88": (20.0, 14.4, 2, 0, "twin"),
    "he111": (22.6, 16.4, 2, 0, "twin"), "me262": (12.6, 10.6, 2, 0, "jet"), "mc202": (10.6, 8.9, 1, 0, "mono"),
    "cr42": (9.7, 8.3, 1, 0, "biplane"), "sm79": (21.2, 16.2, 3, 0, "three"), "zero": (12.0, 9.1, 1, 0, "mono"),
    "ki43": (10.8, 8.9, 1, 0, "mono"), "d3a": (14.4, 10.2, 1, 0, "mono"), "ki51": (12.1, 9.2, 1, 0, "mono"),
    "g4m": (25.0, 20.0, 2, 0, "twin"), "ms406": (10.6, 8.2, 1, 0, "mono"), "d520": (10.2, 8.8, 1, 0, "mono"),
    "br693": (15.4, 9.7, 2, 0, "twin"), "pzl11": (10.7, 7.6, 1, 0, "mono"), "karas": (13.9, 9.7, 1, 0, "mono"),
    "buffalo": (10.7, 8.0, 1, 0, "mono"), "iar80": (10.5, 8.9, 1, 0, "mono"), "re2000": (11.0, 8.0, 1, 0, "mono"),
    "f4f": (11.6, 8.8, 1, 4.4, "mono"), "f6f": (13.1, 10.2, 1, 5.0, "mono"), "tbf": (16.5, 12.5, 1, 5.8, "mono"),
    "sb2c": (15.2, 11.2, 1, 6.9, "mono"), "b24": (33.5, 20.6, 4, 0, "four"),
    "swordfish": (13.9, 10.9, 1, 5.3, "biplane"), "wellington": (26.3, 19.7, 2, 0, "twin"),
    "b5n": (15.5, 10.3, 1, 7.3, "mono"), "bf110": (16.3, 12.3, 2, 0, "twin"), "do17": (18.0, 15.8, 2, 0, "twin"),
    "la5": (9.8, 8.7, 1, 0, "mono"), "il4": (21.4, 14.8, 2, 0, "twin"), "ki84": (11.2, 9.9, 1, 0, "mono"),
    "halifax_sd": (31.8, 21.4, 4, 0, "four"), "b24_cb": (33.5, 20.6, 4, 0, "four"), "li2": (28.8, 19.7, 2, 0, "twin"),
    "ju52": (29.3, 18.9, 3, 0, "three"), "ki57": (22.6, 16.1, 2, 0, "twin"), "lysander": (15.2, 9.3, 1, 0, "mono"),
}
PART_KEYS = ("ac_body", "ac_engine", "ac_wing", "ac_tail")
DIMS.update({"a20": (18.7, 14.6, 2, 0, "twin"), "a26": (21.3, 15.2, 2, 0, "twin"),
             "b26": (21.6, 17.8, 2, 0, "twin"), "p61": (20.1, 15.1, 2, 0, "twinboom"),
             "c47": (29.0, 19.4, 2, 0, "twin"), "c46": (32.9, 23.3, 2, 0, "twin"),
             "pby": (31.7, 19.5, 2, 0, "twin"), "beaufort": (17.6, 13.5, 2, 0, "twin"),
             "barracuda": (15.0, 12.1, 1, 5.6, "mono"), "b6n": (14.9, 10.9, 1, 7.5, "mono"),
             "d4y": (11.5, 10.2, 1, 0, "mono"), "ju188": (22.0, 15.0, 2, 0, "twin")})
PART_WORD = {"ac_body": "the fuselage", "ac_engine": "an engine", "ac_wing": "a wing", "ac_tail": "the tailplane"}


def ids():
    return {T.ID[k] for k in PART_KEYS if k in T.ID}


# ====================================================================== the planform
def planform(model, folded=False):
    """The aircraft seen from above: [(part, [(x, y) metres])], x across (0 at the centreline, + to starboard
    as it faces up the page), y along from the nose (0) to the tail.  Also returns (span, length) in metres."""
    span, length, engines, fspan, layout = DIMS.get(model, DIMS["bf109"])
    big = engines >= 2
    fw = max(1.1, min(3.0, span * 0.085))          # fuselage width
    chord = max(1.9, min(6.2, span * 0.16))        # wing root chord
    le = length * (0.24 if not big else 0.3)       # leading edge at the root
    tail_c = max(1.4, length * 0.12)
    tail_s = span * (0.34 if not big else 0.3)
    parts = []
    half = span / 2
    shown = span
    wing = []
    if folded and fspan:
        shown = fspan
        stub = max(fw / 2 + 0.6, fspan / 2 - 0.9)
        # stubs out to the fold, and the outer panels folded back along the fuselage
        wing.append([(-stub, le), (stub, le), (stub, le + chord), (-stub, le + chord)])
        for s in (-1, 1):
            x0 = s * stub
            x1 = s * (stub + 0.9)
            wing.append([(x0, le + 0.2), (x1, le + 0.2), (x1, le + 0.2 + half - stub), (x0, le + 0.2 + half - stub)])
    else:
        sweep = 0.06 * span if layout != "biplane" else 0.0
        tip = chord * (0.45 if layout != "biplane" else 1.0)
        wing.append([(-half, le + sweep), (0, le), (half, le + sweep), (half, le + sweep + tip),
                     (0, le + chord), (-half, le + sweep + tip)])
        if layout == "biplane":
            wing.append([(-half * 0.92, le + 0.5), (half * 0.92, le + 0.5), (half * 0.92, le + chord * 0.9),
                         (-half * 0.92, le + chord * 0.9)])
    parts += [("ac_wing", w) for w in wing]
    # tailplane (between the booms for a twin-boom)
    ty = length - tail_c
    parts.append(("ac_tail", [(-tail_s / 2, ty), (tail_s / 2, ty), (tail_s / 2 * 0.8, length),
                              (-tail_s / 2 * 0.8, length)]))
    # fuselage: a spindle, nose to tail
    if layout == "twinboom":
        booms = [-span * 0.18, span * 0.18]
        for bx in booms:
            parts.append(("ac_body", [(bx - 0.5, le - 1.5), (bx + 0.5, le - 1.5), (bx + 0.35, length),
                                      (bx - 0.35, length)]))
        parts.append(("ac_body", [(-fw / 2, 0.8), (fw / 2, 0.8), (fw / 2, le + chord + 0.5),
                                  (-fw / 2, le + chord + 0.5)]))
    else:
        parts.append(("ac_body", [(0, 0), (fw / 2, length * 0.1), (fw / 2, length * 0.55),
                                  (fw * 0.18, length), (-fw * 0.18, length), (-fw / 2, length * 0.55),
                                  (-fw / 2, length * 0.1)]))
    # engines
    nac = []
    if layout in ("mono", "biplane") or (layout == "three"):
        nac.append((0.0, 0.0, max(1.0, fw * 0.55), 1.6))
    if layout in ("twin", "jet", "twinboom", "three"):
        off = span * (0.18 if layout != "three" else 0.2)
        for s in (-1, 1):
            nac.append((s * off, le - (1.6 if layout != "jet" else 0.6), 0.7 if layout != "jet" else 0.55,
                        chord + 1.2))
    if layout == "four":
        for off in (span * 0.16, span * 0.33):
            for s in (-1, 1):
                nac.append((s * off, le + 0.06 * span * off / half - 1.4, 0.65, chord * 0.9 + 1.0))
    for (cx, y0, hw, ln) in nac:
        parts.append(("ac_engine", [(cx - hw, y0), (cx + hw, y0), (cx + hw, y0 + ln), (cx - hw, y0 + ln)]))
    # room ahead of the nose for the propeller's arc
    parts = [(part, [(x, y + NOSE) for x, y in poly]) for part, poly in parts]
    return parts, (shown, length + NOSE)


NOSE = 0.6


def _size(shown, length):
    s = max(3, int(shown / TILE_M + 0.5))
    if s % 2 == 0:
        s += 1                                  # the fuselage down the middle column
    return s, max(3, int(length / TILE_M + 0.5))


_GRID = {}


def grid(model, folded=False):
    """(S tiles across, L tiles long, parts[i along][j across] -> tile key or None), nose at i = 0."""
    key = (model, bool(folded) and bool(DIMS.get(model, DIMS["bf109"])[3]))
    g = _GRID.get(key)
    if g is not None:
        return g
    parts, (shown, length) = planform(model, key[1])
    S, L = _size(shown, length)
    R = 8                                        # raster points a tile
    W, H = S * R, L * R
    sc = R / TILE_M
    masks = {}
    for part, poly in parts:
        im = masks.get(part)
        if im is None:
            im = masks[part] = Image.new("L", (W, H), 0)
        ImageDraw.Draw(im).polygon([(W / 2 + x * sc, y * sc) for x, y in poly], fill=255)
    cov = {p: np.asarray(im, np.float32).reshape(L, R, S, R).mean(axis=(1, 3)) / 255.0 for p, im in masks.items()}
    out = [[None] * S for _ in range(L)]
    for i in range(L):
        for j in range(S):
            for part, need in (("ac_engine", 0.18), ("ac_body", 0.2), ("ac_wing", 0.3), ("ac_tail", 0.3)):
                c = cov.get(part)
                if c is not None and c[i, j] >= need:
                    out[i][j] = part
                    break
    g = _GRID[key] = (S, L, out)
    return g


def cells(model, x0, y0, facing, folded=False):
    """[(x, y, part key)] for an aircraft whose bounding box has its top-left at (x0, y0); facing 0 nose up
    (north), 1 east, 2 south, 3 west."""
    S, L, g = grid(model, folded)
    out = []
    for i in range(L):
        for j in range(S):
            p = g[i][j]
            if p is None:
                continue
            if facing == 0:
                x, y = x0 + j, y0 + i
            elif facing == 2:
                x, y = x0 + (S - 1 - j), y0 + (L - 1 - i)
            elif facing == 1:
                x, y = x0 + (L - 1 - i), y0 + j
            else:
                x, y = x0 + i, y0 + (S - 1 - j)
            out.append((x, y, p))
    return out


def box(model, facing, folded=False):
    """(w, h) of the bounding box in tiles."""
    S, L, _ = grid(model, folded)
    return (S, L) if facing in (0, 2) else (L, S)


# ====================================================================== on the map
def fits(m, model, x0, y0, facing, folded=False, ok=None):
    w, h = box(model, facing, folded)
    if x0 < 1 or y0 < 1 or x0 + w >= m.w - 1 or y0 + h >= m.h - 1:
        return False
    for x, y, _p in cells(model, x0, y0, facing, folded):
        tid = int(m.t[x, y])
        if ok is not None:
            if not ok(x, y):
                return False
        elif not T.WALK[tid] or T.WATER[tid] or T.DOOR[tid] or T.FLOOR[tid] and T.DEFS[tid].key != "deck_inside":
            return False
    return True


def place(m, model, x0, y0, facing, nation, folded=False, scheme=None):
    """Stamp an aircraft onto the map and keep its record (for drawing, looking and saving)."""
    folded = bool(folded) and bool(DIMS.get(model, DIMS["bf109"])[3])
    cs = cells(model, x0, y0, facing, folded)
    under = {}
    for x, y, p in cs:
        under[(x, y)] = int(m.t[x, y])
        m.t[x, y] = T.ID[p]
    w, h = box(model, facing, folded)
    # what the ground under it is (drawn beneath the picture): the commonest tile it was put on
    vals = list(under.values())
    ground = max(set(vals), key=vals.count) if vals else T.ID["grass"]
    rec = dict(model=model, nation=nation, x=x0, y=y0, w=w, h=h, facing=facing, folded=folded,
               ground=int(ground), scheme=scheme or nation)
    m.__dict__.setdefault("parked", []).append(rec)
    if hasattr(m, "hp") and m.hp is not None and m.hp.shape == m.t.shape:
        for x, y, p in cs:
            m.hp[x, y] = T.HP[T.ID[p]]
    return rec


def at(m, x, y):
    """The parked aircraft whose box holds (x, y), or None."""
    for rec in m.__dict__.get("parked") or ():
        if rec["x"] <= x < rec["x"] + rec["w"] and rec["y"] <= y < rec["y"] + rec["h"]:
            return rec
    return None


def intact(m, rec) -> bool:
    """Anything left of it but wreckage?"""
    body = T.ID.get("ac_body")
    sub = m.t[rec["x"]:rec["x"] + rec["w"], rec["y"]:rec["y"] + rec["h"]]
    return bool((sub == body).any())


MARKINGS = {"germany": "Luftwaffe crosses", "italy": "Italian fasces roundels", "japan": "red hinomaru",
            "ussr": "red stars", "usa": "American stars", "uk": "RAF roundels", "canada": "RAF roundels",
            "australia": "RAAF roundels", "newzealand": "RNZAF roundels", "india": "RAF roundels",
            "france": "French roundels", "poland": "red-and-white checkers", "finland": "Finnish markings",
            "hungary": "Hungarian crosses", "romania": "Romanian crosses", "china": "Chinese sun roundels"}


def describe(m, x, y):
    """'The fuselage of a parked Bf 109, in Luftwaffe crosses' - what you'd see of it."""
    rec = at(m, x, y)
    if rec is None:
        return None
    from .data.vehicles import AIRCRAFT
    at_ = AIRCRAFT.get(rec["model"])
    name = at_.name if at_ is not None else "aircraft"
    key = T.DEFS[int(m.t[x, y])].key
    part = PART_WORD.get(key)
    folded = ", its wings folded" if rec.get("folded") else ""
    mk = MARKINGS.get(rec["nation"], "")
    what = f"a parked {name}{folded}" + (f", with {mk}" if mk else "")
    return f"{part} of {what}" if part else f"what's left of {what}"


def pick(nation, year, roles=None, rng=None, carrier=False, pacific=False):
    """A model this air force flew then, of the roles asked (fighter first).  Ashore, the carrier types only in
    the Pacific (the Marines flew them from Henderson Field); the special-duties aircraft never."""
    from .data.vehicles import AIRCRAFT
    roles = roles or ("fighter", "fighterbomber")

    def ok(a):
        if a.id not in DIMS or nation not in a.nations or not a.years[0] <= year < a.years[1]:
            return False
        if a.id in ("halifax_sd", "b24_cb"):
            return False
        if carrier:
            return a.id in CARRIER_OK
        return pacific or a.id not in CARRIER_OK or nation not in ("usa", "uk")
    cands = [a.id for a in AIRCRAFT.values() if ok(a) and a.role in roles]
    if not cands:
        cands = [a.id for a in AIRCRAFT.values() if ok(a) and a.role not in ("heavybomber",)]
    if not cands:
        return None
    return (rng.choice(cands) if rng is not None else cands[0])


CARRIER_OK = {"zero", "d3a", "sbd", "f4f", "f6f", "tbf", "sb2c", "b5n", "swordfish", "f4u",
              "b6n", "d4y", "barracuda"}
CARRIER_AIR = {"usa": (("f4f", "f6f"), ("sbd", "sb2c"), ("tbf",)),
               "uk": (("f4f", "f6f"), ("swordfish", "barracuda"), ("swordfish", "barracuda")),
               "japan": (("zero",), ("d3a", "d4y"), ("b5n", "b6n"))}


def carrier_model(nation, year, slot, rng):
    """A carrier's aircraft: slot 0 fighters, 1 dive bombers, 2 torpedo bombers - what she carried that year."""
    from .data.vehicles import AIRCRAFT
    opts = CARRIER_AIR.get(nation, CARRIER_AIR["usa"])[min(2, slot)]
    ok = [k for k in opts if k in AIRCRAFT and AIRCRAFT[k].years[0] <= year < AIRCRAFT[k].years[1]]
    if not ok:
        return opts[-1]
    ok.sort(key=lambda k: AIRCRAFT[k].years[0])
    return ok[-1] if rng.random() < 0.85 else rng.choice(ok)     # the current type, the odd old one


def scheme(nation, year, climate, naval=False):
    """Which paint: desert sand, naval blue-grey, bare metal (the Americans from 1944), or the air force's own."""
    if naval:
        return f"naval_{nation}" if nation in ("usa", "uk", "japan") else nation
    if climate == "desert" and nation in ("uk", "germany", "italy", "usa", "australia", "india"):
        return f"desert_{nation}"
    if nation == "usa" and year >= 1944:
        return "metal"
    if climate == "winter" and nation in ("ussr", "germany", "finland"):
        return f"winter_{nation}"
    return nation
