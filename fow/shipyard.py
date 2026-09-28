"""The shipyard: ships built at their real size, every deck of them.

One deck tile is two metres, the same as a battlefield tile, so a Fletcher-class destroyer is 57
tiles from stem to stern and six across, and an Essex-class carrier 134 long with a flight deck
22 wide.  Every deck a man could walk is here, from the bridge (or a carrier's island) down to
the magazines and the engine rooms:

    destroyer:   bridge / main deck / second deck (berthing, mess, magazines, fire and engine rooms)
    cruiser, battleship:   bridge / main deck / second deck / third deck
    carrier:     island / flight deck / hangar deck / second deck / third deck
    submarine:   bridge (atop the sail) / casing / pressure hull
    PT boat:     deck / below        transport, LST:   bridge / main deck / holds

All decks share one frame (the same width and height), so a ladder at (x, y) on one deck comes
out at (x, y) on the next.  Each deck comes with its compartments (named, with their use) and its
stations: the places the ship's company stands - by watch, and at general quarters.
"""
from __future__ import annotations

import math

import numpy as np

from . import tiles as T
from .gamemap import GameMap

MX, MY = 20, 12

# class: length and beam in tiles (the real ship in two-metre tiles), decks top to bottom
SPEC = {
    "dd": dict(L=58, B=6, decks=["bridge", "main", "second"]),
    "de": dict(L=46, B=5, decks=["bridge", "main", "second"]),
    "cl": dict(L=92, B=10, decks=["bridge", "main", "second", "third"]),
    "ca": dict(L=102, B=10, decks=["bridge", "main", "second", "third"]),
    "bb": dict(L=135, B=16, decks=["bridge", "main", "second", "third"]),
    "cv": dict(L=134, B=22, hullB=14, decks=["island", "flight", "hangar", "second", "third"]),
    "cve": dict(L=78, B=16, hullB=10, decks=["island", "flight", "hangar", "second"]),
    "ss": dict(L=48, B=4, decks=["bridge", "casing", "hull"]),
    "pt": dict(L=12, B=3, decks=["main", "below"]),
    "ap": dict(L=68, B=9, decks=["bridge", "main", "holds"]),
    "lst": dict(L=50, B=8, decks=["bridge", "main", "holds"]),
}
WEATHER = {"main", "flight", "casing"}
DECK_NAME = {"bridge": "the bridge", "island": "the island", "main": "the main deck", "flight": "the flight deck",
             "hangar": "the hangar deck", "second": "the second deck", "third": "the third deck",
             "casing": "the casing", "hull": "the pressure hull", "below": "below", "holds": "the holds"}
AA_GUN = {"usa": ("oerlikon", "bofors_us"), "uk": ("oerlikon", "pompom"), "canada": ("oerlikon", "pompom"),
          "australia": ("oerlikon", "pompom"), "newzealand": ("oerlikon", "pompom"), "germany": ("flak38", "flak_c38"),
          "japan": ("type96_25",), "italy": ("breda20",), "ussr": ("61k",), "france": ("oerlikon",)}


def spec(cls):
    return SPEC.get(cls, SPEC["dd"])


def half_beam(i, L, B):
    """Half the beam at station i (0 = the stern): a fine bow, a rounded stern."""
    t = i / max(1, L - 1)
    f = 1.0
    if t > 0.8:
        f = max(0.0, (1.0 - t) / 0.2) ** 0.8
    elif t < 0.06:
        f = 0.7 + 0.3 * t / 0.06
    return (B / 2.0) * f


class Frame:
    def __init__(self, cls):
        sp = spec(cls)
        self.cls = cls
        self.L, self.B = sp["L"], sp["B"]
        self.hullB = sp.get("hullB", sp["B"])
        self.W = self.L + 2 * MX
        self.H = self.B + 2 * MY
        self.x0 = MX
        self.cy = MY + self.B / 2.0 - 0.5

    def at(self, frac):
        return self.x0 + int(round(frac * (self.L - 1)))

    def cells(self, beam=None, square=False):
        """The deck's outline at a given beam: a set of (x, y)."""
        B = beam or self.B
        out = set()
        for i in range(self.L):
            hb = half_beam(i, self.L, B) if not square else (B / 2.0 if 0.03 < i / self.L < 0.97 else B / 2.6)
            if hb < 0.45:
                continue
            for y in range(int(self.cy - B), int(self.cy + B) + 2):
                if abs(y - self.cy) <= hb:
                    out.add((self.x0 + i, y))
        return out


class Deck:
    """One deck: its map, what's on it, and where the men go."""

    def __init__(self, name, frame, seed):
        self.name = name
        self.map = GameMap(frame.W, frame.H, seed)
        self.map.climate = "summer"
        self.map.biome = "ship"
        self.rooms = []            # dict(name, kind, rect=(x0, y0, x1, y1))
        self.slots = []            # dict(x, y, kind, gq, watch)
        self.ladders = {}          # (x, y) -> {"up": deck, "down": deck}
        self.mounts = []           # (x, y, gun id)
        self.stations = {}         # name -> (x, y): helm, plot, periscope...
        self.cells = set()
        self.weather = name in WEATHER

    def slot(self, x, y, kind, gq=True, watch=False, n=1):
        for _ in range(n):
            self.slots.append(dict(x=x, y=y, kind=kind, gq=gq, watch=watch))

    def room(self, name, kind, x0, y0, x1, y1):
        self.rooms.append(dict(name=name, kind=kind, rect=(x0, y0, x1, y1)))

    def room_at(self, x, y):
        for r in self.rooms:
            x0, y0, x1, y1 = r["rect"]
            if x0 <= x <= x1 and y0 <= y <= y1:
                return r
        return None


# ====================================================================== building blocks
def _fill(m, cells, key):
    tid = T.ID[key]
    for (x, y) in cells:
        m.t[x, y] = tid


def _edge(cells):
    return {(x, y) for (x, y) in cells
            if any((x + dx, y + dy) not in cells for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)))}


def _box(m, xa, xb, ya, yb, wall="wall_steel", floor="deck_inside", door=None):
    for x in range(xa, xb + 1):
        for y in range(ya, yb + 1):
            m.t[x, y] = T.ID[wall if (x in (xa, xb) or y in (ya, yb)) else floor]
    if door:
        m.t[door[0], door[1]] = T.ID["door"]


def _interior(d, fr, beam, rooms, rng, passage=True):
    """An enclosed deck: hull all round, a passageway fore and aft, compartments off it."""
    m = d.map
    cells = fr.cells(beam)
    d.cells = cells
    m.t[:, :] = T.ID["void"]
    _fill(m, cells, "deck_inside")
    _fill(m, _edge(cells), "hull")
    cy = int(round(fr.cy))
    ys = [y for (_, y) in cells]
    top, bot = min(ys) + 1, max(ys) - 1
    total = sum(f for _, _, f in rooms)
    x = fr.x0 + 1
    placed = []
    wide = (bot - top) >= 5
    for name, kind, f in rooms:
        ln = max(3, int((fr.L - 3) * f / total))
        xa, xb = x, min(fr.x0 + fr.L - 2, x + ln - 1)
        if xa >= fr.x0 + fr.L - 3:
            break
        placed.append((name, kind, xa, xb))
        x = xb + 1
    for name, kind, xa, xb in placed:
        # the bulkhead at the forward end, with a watertight door through it on the passageway
        for y in range(top - 1, bot + 2):
            if (xb, y) in cells and m.t[xb, y] != T.ID["hull"]:
                m.t[xb, y] = T.ID["wall_steel"]
        m.t[xb, cy] = T.ID["door"]
        if wide and passage and kind not in ("hangar", "fireroom", "engine", "magazine", "hold", "torpedo"):
            # a passageway down the centreline; the compartment either side of it
            for xx in range(xa, xb):
                for yy in (top + (bot - top) // 2 - 1, top + (bot - top) // 2 + 1):
                    if (xx, yy) in cells and m.t[xx, yy] == T.ID["deck_inside"]:
                        m.t[xx, yy] = T.ID["wall_steel"]
            for yy in (top + (bot - top) // 2 - 1, top + (bot - top) // 2 + 1):
                dx = xa + (xb - xa) // 2
                if (dx, yy) in cells:
                    m.t[dx, yy] = T.ID["door"]
        d.room(name, kind, xa, top, xb - 1, bot)
        _furnish(d, kind, xa, top, xb - 1, bot, cy, rng, wide)
    return placed


def _free(m, x, y):
    return m.t[x, y] == T.ID["deck_inside"]


def _furnish(d, kind, xa, ya, xb, yb, cy, rng, wide):
    m = d.map
    inner = [(x, y) for x in range(xa, xb + 1) for y in range(ya, yb + 1) if _free(m, x, y)]
    side = [(x, y) for (x, y) in inner if abs(y - cy) >= 2 or not wide]
    if kind == "berthing":
        # racks along both sides, three and four high: every one of them a man off watch
        for (x, y) in side:
            if (x - xa) % 3 != 2 and abs(y - cy) >= 1:
                m.t[x, y] = T.ID["bunk"]
                d.slot(x, y, "berth", gq=False, watch=False)
    elif kind == "mess":
        for (x, y) in side:
            if (x - xa) % 3 == 1 and abs(y - cy) >= 1:
                m.t[x, y] = T.ID["table"]
        for (x, y) in side:
            if _free(m, x, y) and any(m.t[x + dx, y] == T.ID["table"] for dx in (-1, 1)):
                d.slot(x, y, "mess", gq=False, watch=False)
    elif kind == "galley":
        for (x, y) in side[: max(2, len(side) // 4)]:
            m.t[x, y] = T.ID["stove"]
        for (x, y) in side[len(side) // 4: len(side) // 4 + 2]:
            d.slot(x, y, "galley", gq=False, watch=True)
    elif kind == "sickbay":
        for (x, y) in side[::2]:
            m.t[x, y] = T.ID["bed"]
        free = [c for c in inner if _free(m, *c)]
        for (x, y) in free[:4]:
            d.slot(x, y, "medical", gq=True, watch=len(free) and (x, y) == free[0])
    elif kind in ("wardroom", "officers"):
        for (x, y) in side[::4]:
            m.t[x, y] = T.ID["table"] if kind == "wardroom" else T.ID["bunk"]
        for (x, y) in side[1::5]:
            if _free(m, x, y):
                d.slot(x, y, "berth", gq=False)
    elif kind == "magazine":
        for (x, y) in inner:
            if (x - xa) % 3 != 1 and y != cy:
                m.t[x, y] = T.ID["ammo_rack"]
        free = [c for c in inner if _free(m, *c)]
        for (x, y) in free[:6]:
            d.slot(x, y, "magazine", gq=True, watch=False)
    elif kind == "fireroom":
        for (x, y) in inner:
            if (x - xa) % 4 in (1, 2) and abs(y - cy) >= 1:
                m.t[x, y] = T.ID["boiler"]
        free = [c for c in inner if _free(m, *c)]
        for i, (x, y) in enumerate(free[:8]):
            d.slot(x, y, "engine", gq=True, watch=i % 2 == 0)
    elif kind == "engine":
        for (x, y) in inner:
            if (x - xa) % 5 in (1, 2, 3) and abs(y - cy) == 1:
                m.t[x, y] = T.ID["turbine"]
        free = [c for c in inner if _free(m, *c)]
        for i, (x, y) in enumerate(free[:8]):
            d.slot(x, y, "engine", gq=True, watch=i % 2 == 0)
    elif kind == "repair":
        if side:
            x, y = side[0]
            m.t[x, y] = T.ID["repair_locker"]
            d.stations.setdefault("repair", (x, y))
            d.stations[f"repair_{len([k for k in d.stations if k.startswith('repair')])}"] = (x, y)
        free = [c for c in inner if _free(m, *c)]
        for (x, y) in free[:9]:
            d.slot(x, y, "dc", gq=True, watch=False)
        for (x, y) in free[9:11]:
            d.slot(x, y, "dc", gq=True, watch=True)
    elif kind == "store":
        for (x, y) in side[::2]:
            m.t[x, y] = T.ID["crates"]
        free = [c for c in inner if _free(m, *c)]
        for (x, y) in free[:2]:
            d.slot(x, y, "mess", gq=False, watch=True)          # a working party breaking out stores
    elif kind == "steering":
        if inner:
            x, y = inner[len(inner) // 2]
            m.t[x, y] = T.ID["steering_gear"]
        free = [c for c in inner if _free(m, *c)]
        for (x, y) in free[:1]:
            d.slot(x, y, "engine", gq=True, watch=True)
    elif kind == "avgas":
        for (x, y) in inner:
            if (x + y) % 2 == 0 and y != cy:
                m.t[x, y] = T.ID["avgas"]
    elif kind == "radio":
        for (x, y) in side[:3]:
            m.t[x, y] = T.ID["radio_set"]
        free = [c for c in inner if _free(m, *c)]
        for (x, y) in free[:2]:
            d.slot(x, y, "radio", gq=True, watch=True)
    elif kind == "cic":
        for (x, y) in side[:4]:
            m.t[x, y] = T.ID["radar_scope"]
            d.slot(x, y, "cic", gq=True, watch=True)
    elif kind == "torpedo":
        for (x, y) in inner:
            if y != cy:
                m.t[x, y] = T.ID["torpedo_rack"]
        free = [c for c in inner if _free(m, *c)]
        for (x, y) in free[:5]:
            d.slot(x, y, "torpedo", gq=True, watch=False)
        for (x, y) in [c for c in inner if m.t[c] == T.ID["torpedo_rack"]][::2]:
            pass
    elif kind == "control":
        free = [c for c in inner if _free(m, *c)]
        if free:
            x, y = free[len(free) // 2]
            m.t[x, y] = T.ID["periscope"]
            d.stations["periscope"] = (x, y)
            if len(free) > 3:
                hx, hy = free[len(free) // 2 + 1]
                m.t[hx, hy] = T.ID["helm"]
                d.stations["helm"] = (hx, hy)
                px, py = free[len(free) // 2 - 1]
                m.t[px, py] = T.ID["chart_table"]
                d.stations["plot"] = (px, py)
        for (x, y) in free[:4]:
            d.slot(x, y, "bridge", gq=True, watch=True)
    elif kind == "hold":
        for (x, y) in inner[::3]:
            m.t[x, y] = T.ID["crates"]


def _link(decks, frame, fracs, a, b, rng, near_y=None):
    """Ladders between decks a (upper) and b (lower) at these fractions of the length."""
    da, db = decks[a], decks[b]
    made = []
    for fr in fracs:
        x = frame.at(fr)
        ys = sorted({y for (xx, y) in da.cells if xx == x} & {y for (xx, y) in db.cells if xx == x},
                    key=lambda y: abs(y - (near_y if near_y is not None else frame.cy)))
        for y in ys:
            ta, tb = da.map.t[x, y], db.map.t[x, y]
            ok = T.WALK[ta] and T.WALK[tb] and ta not in (T.ID["door"],) and tb not in (T.ID["door"],)
            if ok and (x, y) not in da.ladders and (x, y) not in db.ladders:
                da.map.t[x, y] = T.ID["hatch"] if da.weather else T.ID["ladder"]
                db.map.t[x, y] = T.ID["ladder"]
                da.ladders.setdefault((x, y), {})["down"] = b
                db.ladders.setdefault((x, y), {})["up"] = a
                made.append((x, y))
                break
    return made


# ====================================================================== the decks
def _weather_deck(d, fr, ship, rng, deck_key):
    """The main deck: open to the sky, the sea over the rail, guns, funnels, boats, the deckhouse."""
    m = d.map
    m.t[:, :] = T.ID["deep"]
    cells = fr.cells()
    d.cells = cells
    _fill(m, cells, deck_key)
    _fill(m, _edge(cells), "railing")
    cls = fr.cls
    cy = int(round(fr.cy))
    return m, cells, cy


def deck_main(d, fr, ship, rng):
    cls = fr.cls
    m, cells, cy = _weather_deck(d, fr, ship, rng, "deck_wood" if cls in ("bb",) else "deck_steel")
    deck = (T.ID["deck_steel"], T.ID["deck_wood"])
    B = fr.B
    # the deckhouse under the bridge (and a ladder up to it)
    bridge_at = {"dd": 0.64, "de": 0.62, "cl": 0.7, "ca": 0.68, "bb": 0.64, "ap": 0.4, "lst": 0.14, "pt": 0.52}
    bf = bridge_at.get(cls, 0.62)
    ln = {"dd": 9, "de": 7, "cl": 14, "ca": 16, "bb": 20, "ap": 10, "lst": 10, "pt": 3}.get(cls, 8)
    hw = max(1, min(B // 2 - 1, 3 if B > 6 else 1))
    xa, xb = fr.at(bf) - ln // 2, fr.at(bf) + ln // 2
    _box(m, xa, xb, cy - hw, cy + hw, door=(xa, cy))
    d.room("deckhouse", "deckhouse", xa + 1, cy - hw + 1, xb - 1, cy + hw - 1)
    if hw >= 2:
        d.room("galley", "galley", xa + 1, cy - hw + 1, xa + ln // 2, cy + hw - 1)
        for y in range(cy - hw + 1, cy + hw):
            if m.t[xa + 2, y] == T.ID["deck_inside"] and y != cy:
                m.t[xa + 2, y] = T.ID["stove"]
        d.slot(xa + 3, cy, "galley", gq=False, watch=True)
    d.stations["deckhouse_ladder"] = (xb - 1, cy)
    # funnels
    for f in {"dd": [0.5, 0.4], "de": [0.48], "cl": [0.52, 0.44], "ca": [0.52, 0.44], "bb": [0.52],
              "ap": [0.3], "lst": [0.08]}.get(cls, []):
        fx = fr.at(f)
        for x in range(fx - 1, fx + 2):
            for y in range(cy - (1 if B > 6 else 0), cy + (2 if B > 6 else 1)):
                if m.t[x, y] in deck:
                    m.t[x, y] = T.ID["funnel"]
    # the main battery
    guns = {"dd": [(0.88, 1), (0.8, 1), (0.22, 1), (0.14, 1), (0.06, 1)], "de": [(0.86, 1), (0.1, 1)],
            "cl": [(0.9, 2), (0.83, 2), (0.2, 2), (0.12, 2)], "ca": [(0.88, 2), (0.8, 2), (0.14, 2)],
            "bb": [(0.86, 3), (0.77, 3), (0.18, 3)], "pt": []}.get(cls, [])
    for k, (gf, sz) in enumerate(guns):
        gx = fr.at(gf)
        tid = T.ID["gun_mount"] if sz == 1 else T.ID["gun_turret"]
        for x in range(gx - sz, gx + sz + 1):
            for y in range(cy - sz, cy + sz + 1):
                if (x, y) in cells and m.t[x, y] in deck:
                    m.t[x, y] = tid
        # the mount's crew: most inside, the loaders and the mount captain on deck behind it
        behind = gx - sz - 1 if gf > 0.5 else gx + sz + 1
        for y in range(cy - sz, cy + sz + 1):
            if (behind, y) in cells and m.t[behind, y] in deck:
                d.slot(behind, y, "gun", gq=True, watch=(k == 0 and y == cy))
    # torpedo mounts, depth charges
    for tf in {"dd": [0.55, 0.3], "de": [0.4], "cl": [0.35], "ca": [0.34], "pt": [0.78, 0.25]}.get(cls, []):
        tx = fr.at(tf)
        for x in range(tx - 2, tx + 2):
            if m.t[x, cy] in deck:
                m.t[x, cy] = T.ID["torpedo_tubes"]
        for y in (cy - 1, cy + 1):
            if m.t[tx + 2, y] in deck:
                d.slot(tx + 2, y, "torpedo", gq=True, watch=False)
            if m.t[tx - 3, y] in deck:
                d.slot(tx - 3, y, "torpedo", gq=True, watch=False)
    if cls in ("dd", "de"):
        for y in (cy - 1, cy + 1):
            if m.t[fr.x0 + 2, y] in deck:
                m.t[fr.x0 + 2, y] = T.ID["depth_charges"]
                d.slot(fr.x0 + 3, y, "depth_charge", gq=True, watch=False)
    # the holds of a transport
    if cls in ("ap", "lst"):
        for hf in ([0.8, 0.62, 0.22] if cls == "ap" else [0.5]):
            hx = fr.at(hf)
            for x in range(hx - 3, hx + 3):
                for y in range(cy - 2, cy + 3):
                    if m.t[x, y] in deck:
                        m.t[x, y] = T.ID["crates"]
    # boats, life rings, ready lockers
    top = min(y for (_, y) in cells) + 1
    bot = max(y for (_, y) in cells) - 1
    for k in range({"dd": 2, "de": 2, "cl": 4, "ca": 4, "bb": 6, "ap": 4, "lst": 2}.get(cls, 0)):
        bx = fr.at(0.3 + 0.35 * (k // 2) / max(1, k // 2 + 1))
        by = top if k % 2 == 0 else bot
        if m.t[bx, by] in deck:
            m.t[bx, by] = T.ID["life_raft"]
    for k in range(max(2, fr.L // 25)):
        rx = fr.at(0.1 + 0.8 * k / max(1, fr.L // 25 - 1))
        for ry in (top, bot):
            if m.t[rx, ry] in deck:
                m.t[rx, ry] = T.ID["life_ring"]
                break
    _aa_mounts(d, fr, ship, rng, cells, cy, top, bot)
    # a working party about the deck in cruising condition: chipping, painting, splicing, cleaning guns
    free = [c for c in sorted(cells) if m.t[c] in deck]
    for c in free[:: max(1, len(free) // 6)][:6]:
        d.slot(c[0], c[1], "mess", gq=False, watch=True)


def _aa_mounts(d, fr, ship, rng, cells, cy, top, bot, deck_ids=None):
    """Light AA along both sides - as many as she really carried - each with a ready-service locker."""
    m = d.map
    deck = deck_ids or (T.ID["deck_steel"], T.ID["deck_wood"], T.ID["catwalk"])
    guns = AA_GUN.get(ship.nation, ("oerlikon",))
    n = max(2, min(40, (ship.st.get("aa") or (4, 0))[0] // 2))
    placed = 0
    for k in range(n * 3):
        if placed >= n:
            break
        fr_ = 0.08 + 0.84 * ((k * 0.618) % 1.0)
        x = fr.at(fr_)
        side = -1 if k % 2 == 0 else 1
        ys = sorted((y for (xx, y) in cells if xx == x and m.t[x, y] in deck), key=lambda y: -side * y)
        for y in ys[:3]:
            if abs(y - cy) < 1:
                continue
            nb = [m.t[x + dx, y + dy] for dx in (-1, 0, 1) for dy in (-1, 0, 1) if m.in_bounds(x + dx, y + dy)]
            if any(t in (T.ID["gun_mount"], T.ID["gun_turret"], T.ID["funnel"], T.ID["ready_locker"]) for t in nb):
                continue
            if any(abs(mx - x) <= 2 and abs(my - y) <= 1 for mx, my, _ in d.mounts):
                continue
            gid = guns[(placed // 3) % len(guns)] if len(guns) > 1 and placed % 3 == 2 else guns[0]
            d.mounts.append((x, y, gid))
            inward = 1 if y < cy else -1
            ly = y + inward
            if m.t[x - 1, ly] in deck:
                m.t[x - 1, ly] = T.ID["ready_locker"]
            if m.t[x + 1, ly] in deck:              # (a man's station is on the deck, not in the bulkhead)
                d.slot(x + 1, ly, "gun", gq=True, watch=(placed % 3 == 0))
            if m.t[x, ly] in deck:
                d.slot(x, ly, "gun", gq=True, watch=False)
            if gid in ("bofors_us", "pompom", "flak_c38", "61k"):
                # a quad 40mm had a crew of eleven: the pointer, the trainer, loaders, passers
                for dx in (-1, 2):
                    if m.t[x + dx, ly] in deck:
                        d.slot(x + dx, ly, "gun", gq=True, watch=False)
            placed += 1
            break


def deck_bridge(d, fr, ship, rng, below):
    """The bridge: pilot house, chart house, radio room, CIC, and the open wings with the lookouts."""
    m = d.map
    m.t[:, :] = T.ID["sea_below"]
    for (x, y) in below.cells:
        m.t[x, y] = T.ID["deck_below"]
    cls = fr.cls
    cy = int(round(fr.cy))
    bf = {"dd": 0.64, "de": 0.62, "cl": 0.7, "ca": 0.68, "bb": 0.64, "ap": 0.4, "lst": 0.14, "ss": 0.56}.get(cls, 0.62)
    ln = {"dd": 9, "de": 7, "cl": 14, "ca": 16, "bb": 20, "ap": 10, "lst": 10, "ss": 5}.get(cls, 8)
    hw = max(1, min(fr.B // 2 - 1, 3 if fr.B > 6 else 1))
    xa, xb = fr.at(bf) - ln // 2, fr.at(bf) + ln // 2
    wing = min(fr.B // 2 + 1, hw + 3)
    # the open bridge wings, athwartships at the forward end
    for x in range(xb - 2, xb + 1):
        for y in range(cy - wing, cy + wing + 1):
            m.t[x, y] = T.ID["deck_steel"]
            d.cells.add((x, y))
    _box(m, xa, xb - 3, cy - hw, cy + hw, door=(xb - 3, cy))
    for x in range(xa, xb + 1):
        for y in range(cy - hw, cy + hw + 1):
            d.cells.add((x, y))
    hx, hy = xb - 4, cy
    m.t[hx, hy] = T.ID["helm"]
    d.stations["helm"] = (hx, hy)
    d.slot(hx, hy + (1 if hw > 1 else 0), "bridge", gq=True, watch=True)
    if ln >= 7:
        # a one-tile-wide pilot house (a destroyer's) puts the chart table against the bulkhead, not across
        # the only passage to the ladder
        py = hy if hw > 1 else hy - 1
        m.t[hx - 2, py] = T.ID["chart_table"]
        d.stations["plot"] = (hx - 2, py)
        d.slot(hx - 1, hy, "bridge", gq=True, watch=True)
    d.stations["bridge"] = (hx - 1, hy)
    d.room("pilot house", "bridge", xa + 1, cy - hw + 1, xb - 4, cy + hw - 1)
    if hw >= 2 and ln >= 12:
        m.t[xa + 2, cy - hw + 1] = T.ID["radar_scope"]
        m.t[xa + 3, cy - hw + 1] = T.ID["radar_scope"]
        d.slot(xa + 2, cy - hw + 2, "cic", gq=True, watch=True, n=2)
        m.t[xa + 2, cy + hw - 1] = T.ID["radio_set"]
        d.slot(xa + 3, cy + hw - 1, "radio", gq=True, watch=True)
    for y in (cy - wing, cy + wing):
        m.t[xb - 1, y] = T.ID["lookout_post"]
        d.slot(xb - 1, y, "lookout", gq=True, watch=True)
        d.stations.setdefault("lookouts", []).append((xb - 1, y))
    for y in (cy - wing + 1, cy + wing - 1):
        d.slot(xb, y, "lookout", gq=True, watch=False)
    # the rest of the bridge watch: officer of the deck, junior officer, quartermaster, talkers, messenger
    inside = [(x, y) for x in range(xa + 1, xb - 3) for y in range(cy - hw + 1, cy + hw)
              if m.t[x, y] == T.ID["deck_inside"]]
    for i, (x, y) in enumerate(inside[:6]):
        d.slot(x, y, "bridge", gq=True, watch=i < 3)
    d.stations["bridge_ladder"] = (xa + 1, cy)


def deck_island(d, fr, ship, rng, below):
    """A carrier's island: the navigating bridge, flag plot, primary flight control, the lookouts."""
    m = d.map
    m.t[:, :] = T.ID["sea_below"]
    for (x, y) in below.cells:
        m.t[x, y] = T.ID["deck_below"]
    cy = int(round(fr.cy))
    bot = max(y for (_, y) in below.cells) - 1
    xc = fr.at(0.56 if fr.cls == "cv" else 0.62)
    ln = 16 if fr.cls == "cv" else 10
    xa, xb = xc - ln // 2, xc + ln // 2
    ya, yb = bot - 4, bot
    _box(m, xa, xb, ya, yb, door=(xa + (xb - xa) // 2, ya))     # out onto the lookouts' catwalk
    for x in range(xa, xb + 1):
        for y in range(ya, yb + 1):
            d.cells.add((x, y))
    hx, hy = xb - 1, ya + 2
    m.t[hx, hy] = T.ID["helm"]
    m.t[hx - 2, hy] = T.ID["chart_table"]
    m.t[xa + 2, ya + 1] = T.ID["radar_scope"]
    m.t[xa + 3, ya + 1] = T.ID["radar_scope"]
    d.stations.update(helm=(hx, hy), plot=(hx - 2, hy), bridge=(hx - 1, hy), flag=(xa + 4, ya + 2),
                      prifly=(xa + 2, ya + 3))
    d.room("navigating bridge", "bridge", xa + 1, ya + 1, xb - 1, yb - 1)
    d.slot(hx, hy + 1, "bridge", gq=True, watch=True)
    d.slot(hx - 1, hy - 1, "bridge", gq=True, watch=True)
    d.slot(xa + 2, ya + 2, "cic", gq=True, watch=True, n=2)
    d.slot(xa + 5, ya + 3, "air_ops", gq=True, watch=True)
    for x in (xa, xb):
        pass
    # lookouts on the island's catwalks
    for x in (xa + 2, xb - 2):
        m.t[x, ya - 1] = T.ID["lookout_post"]
        d.cells.add((x, ya - 1))
        d.slot(x, ya - 1, "lookout", gq=True, watch=True)
        d.stations.setdefault("lookouts", []).append((x, ya - 1))
    for x in range(xa + 1, xb):
        if m.t[x, ya - 1] == T.ID["deck_below"]:
            m.t[x, ya - 1] = T.ID["catwalk"]
            d.cells.add((x, ya - 1))
    d.stations["island_ladder"] = (xa + 1, yb - 1)


def deck_flight(d, fr, ship, rng):
    """The flight deck: aircraft spotted aft, arresting wires, elevators, catapults, and the island to starboard."""
    m = d.map
    m.t[:, :] = T.ID["deep"]
    cells = fr.cells(square=True)
    d.cells = cells
    _fill(m, cells, "deck_wood")
    edge = _edge(cells)
    cy = int(round(fr.cy))
    top = min(y for (_, y) in cells)
    bot = max(y for (_, y) in cells)
    # the gallery catwalks along the edges carry the guns
    for (x, y) in cells:
        if y in (top, bot) or (x, y) in edge:
            m.t[x, y] = T.ID["catwalk"]
    xc = fr.at(0.56 if fr.cls == "cv" else 0.62)
    ln = 16 if fr.cls == "cv" else 10
    xa, xb = xc - ln // 2, xc + ln // 2
    _box(m, xa, xb, bot - 4, bot, door=(xa, bot - 2))
    d.room("island (base)", "deckhouse", xa + 1, bot - 3, xb - 1, bot - 1)
    d.stations["island_ladder"] = (xa + 1, bot - 1)
    # elevators, wires, catapults
    for ef, w in ((0.72, 5), (0.42, 5)):
        ex = fr.at(ef)
        for x in range(ex - w // 2, ex + w // 2 + 1):
            for y in range(cy - 2, cy + 3):
                m.t[x, y] = T.ID["elevator"]
        d.stations.setdefault("elevators", []).append((ex, cy))
    for k in range(6 if fr.cls == "cv" else 4):
        wx = fr.at(0.08 + 0.03 * k)
        for y in range(top + 2, bot - 1):
            if m.t[wx, y] == T.ID["deck_wood"]:
                m.t[wx, y] = T.ID["arrest_wire"]
    for y in (cy - 2, cy + 2):
        for x in range(fr.at(0.86), fr.at(0.97)):
            if m.t[x, y] == T.ID["deck_wood"]:
                m.t[x, y] = T.ID["catapult"]
    # aircraft spotted aft, folded wings, ready to fly
    n = min(36, sum(ship.air) if ship.air else 12)
    k = 0
    for x in range(fr.at(0.16), fr.at(0.4), 3):
        for y in range(top + 2, bot - 5, 3):
            if k >= n:
                break
            if m.t[x, y] == T.ID["deck_wood"]:
                m.t[x, y] = T.ID["plane_parked"]
                d.slot(x + 1, y + 1, "plane_handler", gq=True, watch=False)
                k += 1
    d.stations["spot"] = (fr.at(0.28), cy)
    for k in range(3):
        d.slot(fr.at(0.5 + 0.1 * k), top + 2, "plane_handler", gq=True, watch=True)
    for y in (top, bot):
        for k in range(max(2, fr.L // 25)):
            rx = fr.at(0.1 + 0.8 * k / max(1, fr.L // 25 - 1))
            if m.t[rx, y] == T.ID["catwalk"]:
                m.t[rx, y] = T.ID["life_ring"]
    _aa_mounts(d, fr, ship, rng, cells, cy, top, bot, deck_ids=(T.ID["catwalk"],))


def deck_hangar(d, fr, ship, rng):
    """The hangar deck: the aircraft below, the elevator wells, the fire curtains - and the fuel."""
    rooms = [("fantail", "store", 0.06), ("after hangar bay", "hangar", 0.28), ("midships hangar bay", "hangar", 0.24),
             ("forward hangar bay", "hangar", 0.24), ("forecastle", "store", 0.12)]
    _interior(d, fr, fr.hullB, rooms, rng, passage=False)
    m = d.map
    cy = int(round(fr.cy))
    fs = [c for c in d.cells if m.t[c] == T.ID["deck_inside"]]
    k = 0
    n = min(40, sum(ship.air) if ship.air else 20)
    for x in range(fr.at(0.12), fr.at(0.8), 3):
        for y in range(min(y for _, y in fs) + 1, max(y for _, y in fs), 3):
            if k >= n:
                break
            if m.t[x, y] == T.ID["deck_inside"] and abs(y - cy) >= 2:
                m.t[x, y] = T.ID["plane_parked"]
                if k % 3 == 0:
                    d.slot(x + 1, y, "hangar_crew", gq=True, watch=k % 6 == 0)
                k += 1
    for r in d.rooms:
        if r["kind"] == "hangar":
            xb = r["rect"][2] + 1
            for y in range(r["rect"][1], r["rect"][3] + 1):
                if m.t[xb, y] in (T.ID["wall_steel"], T.ID["door"]):
                    m.t[xb, y] = T.ID["fire_curtain"]
    for ef in (0.72, 0.42):
        ex = fr.at(ef)
        for x in range(ex - 2, ex + 3):
            for y in range(cy - 2, cy + 3):
                if m.t[x, y] in (T.ID["deck_inside"], T.ID["plane_parked"]):
                    m.t[x, y] = T.ID["elevator"]
    # repair party and a battle dressing station in the hangar
    r0 = next(r for r in d.rooms if r["kind"] == "hangar")
    x, y = r0["rect"][0] + 1, r0["rect"][1]
    m.t[x, y] = T.ID["repair_locker"]
    d.stations["repair"] = (x, y)
    for k in range(4):
        d.slot(x + 1 + k, y + 1, "dc", gq=True, watch=k == 0)
    d.room("battle dressing station", "sickbay", r0["rect"][0] + 1, r0["rect"][3] - 1, r0["rect"][0] + 3,
           r0["rect"][3])
    d.slot(r0["rect"][0] + 2, r0["rect"][3] - 1, "medical", gq=True, watch=False)


def deck_second(d, fr, ship, rng):
    cls = fr.cls
    big = cls in ("cv", "bb", "ca", "cl", "cve")
    rooms = [("steering gear", "steering", 0.04), ("after crew berthing", "berthing", 0.14), ("after repair", "repair", 0.05),
             ("wardroom", "wardroom", 0.07), ("officers' country", "officers", 0.08), ("sickbay", "sickbay", 0.07),
             ("mess deck", "mess", 0.12), ("galley", "galley", 0.05), ("midships crew berthing", "berthing", 0.14),
             ("forward repair", "repair", 0.05), ("forward crew berthing", "berthing", 0.12), ("stores", "store", 0.07)]
    if not big:
        # a destroyer's second deck is where everything is
        rooms = [("steering gear", "steering", 0.05), ("after magazine", "magazine", 0.08),
                 ("after crew berthing", "berthing", 0.12), ("after engine room", "engine", 0.1),
                 ("after fireroom", "fireroom", 0.1), ("forward engine room", "engine", 0.1),
                 ("forward fireroom", "fireroom", 0.1), ("repair", "repair", 0.05), ("mess deck", "mess", 0.08),
                 ("sickbay", "sickbay", 0.05), ("forward crew berthing", "berthing", 0.1),
                 ("forward magazine", "magazine", 0.07)]
    beam = fr.hullB if cls in ("cv", "cve") else fr.B
    _interior(d, fr, beam, rooms, rng)


def deck_third(d, fr, ship, rng):
    rooms = [("shaft alley", "store", 0.06), ("after magazine", "magazine", 0.1), ("after engine room", "engine", 0.12),
             ("after fireroom", "fireroom", 0.11), ("midships repair", "repair", 0.04),
             ("forward engine room", "engine", 0.12), ("forward fireroom", "fireroom", 0.11),
             ("forward magazine", "magazine", 0.1), ("pump room", "store", 0.05)]
    if fr.cls in ("cv", "cve"):
        rooms.insert(-1, ("aviation fuel", "avgas", 0.08))
    beam = fr.hullB if fr.cls in ("cv", "cve") else fr.B
    _interior(d, fr, beam, rooms, rng, passage=False)


def deck_casing(d, fr, ship, rng):
    """A submarine's casing: the slatted deck over the pressure hull, the deck gun, the sail."""
    m, cells, cy = _weather_deck(d, fr, ship, rng, "deck_steel")
    xs = fr.at(0.56)
    _box(m, xs - 3, xs + 2, cy - 1, cy + 1, door=(xs - 3, cy))
    d.room("sail", "deckhouse", xs - 2, cy, xs + 1, cy)
    d.stations["sail_ladder"] = (xs - 2, cy)
    gx = fr.at(0.68)
    m.t[gx, cy] = T.ID["gun_mount"]
    d.slot(gx - 1, cy, "gun", gq=True, watch=False, n=2)
    d.mounts.append((xs + 3, cy, AA_GUN.get(ship.nation, ("oerlikon",))[0]))
    d.slot(xs + 4, cy, "gun", gq=True, watch=False)


def deck_hull(d, fr, ship, rng):
    rooms = [("after torpedo room", "torpedo", 0.12), ("maneuvering room", "engine", 0.08),
             ("after engine room", "engine", 0.12), ("forward engine room", "engine", 0.12),
             ("crew's mess and galley", "mess", 0.1), ("crew berthing", "berthing", 0.1),
             ("control room", "control", 0.12), ("officers' quarters", "officers", 0.08),
             ("forward torpedo room", "torpedo", 0.16)]
    _interior(d, fr, fr.B, rooms, rng, passage=False)


def deck_below_pt(d, fr, ship, rng):
    rooms = [("engine room", "engine", 0.5), ("crew quarters", "berthing", 0.5)]
    _interior(d, fr, fr.B, rooms, rng, passage=False)


def deck_holds(d, fr, ship, rng):
    rooms = [("engine room", "engine", 0.2), ("after hold", "hold", 0.25), ("crew quarters", "berthing", 0.12),
             ("forward hold", "hold", 0.3), ("forepeak", "store", 0.08)]
    if fr.cls == "lst":
        rooms = [("engine room", "engine", 0.18), ("crew quarters", "berthing", 0.1), ("tank deck", "hold", 0.65),
                 ("bow doors", "store", 0.07)]
    _interior(d, fr, fr.B, rooms, rng, passage=False)


# ====================================================================== the whole ship
def build(ship, rng):
    """Every deck of `ship`.  Returns (decks: {name: Deck}, order: [names top to bottom], frame)."""
    fr = Frame(ship.cls)
    sp = spec(ship.cls)
    order = list(sp["decks"])
    decks = {}
    seed = rng.randint(1, 2 ** 30)
    for i, name in enumerate(order):
        decks[name] = Deck(name, fr, seed + i)
    for name in order:
        d = decks[name]
        if name == "main":
            if fr.cls == "pt":
                deck_main(d, fr, ship, rng)
            else:
                deck_main(d, fr, ship, rng)
        elif name == "flight":
            deck_flight(d, fr, ship, rng)
        elif name == "hangar":
            deck_hangar(d, fr, ship, rng)
        elif name == "second":
            deck_second(d, fr, ship, rng)
        elif name == "third":
            deck_third(d, fr, ship, rng)
        elif name == "casing":
            deck_casing(d, fr, ship, rng)
        elif name == "hull":
            deck_hull(d, fr, ship, rng)
        elif name == "below":
            deck_below_pt(d, fr, ship, rng)
        elif name == "holds":
            deck_holds(d, fr, ship, rng)
    below = decks.get("main") or decks.get("flight") or decks.get("casing")
    for name in order:
        d = decks[name]
        if name == "bridge":
            deck_bridge(d, fr, ship, rng, below)
        elif name == "island":
            deck_island(d, fr, ship, rng, below)
    # ladders between each pair of decks
    for a, b in zip(order, order[1:]):
        da, db = decks[a], decks[b]
        if a in ("bridge", "island"):
            st = da.stations.get("bridge_ladder") or da.stations.get("island_ladder")
            if st is not None:
                x, y = st
                if T.WALK[db.map.t[x, y]] or db.map.t[x, y] == T.ID["deck_inside"]:
                    db.map.t[x, y] = T.ID["ladder"]
                    da.map.t[x, y] = T.ID["ladder"]
                    da.ladders.setdefault((x, y), {})["down"] = b
                    db.ladders.setdefault((x, y), {})["up"] = a
                    continue
            _link(decks, fr, [0.6, 0.64, 0.56], a, b, rng)
        else:
            n = 3 if fr.L > 40 else 1
            fr_list = [0.2, 0.5, 0.78][:n] if n > 1 else [0.5]
            got = _link(decks, fr, fr_list, a, b, rng)
            if not got:
                _link(decks, fr, [0.3, 0.45, 0.6, 0.7], a, b, rng)
    for d in decks.values():
        d.map.init_hp()
        d.map.refresh()
    return decks, order, fr
