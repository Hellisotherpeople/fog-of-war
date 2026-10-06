"""The theatre-level war: a grid of sectors, each a local battlefield.

Sectors hold abstract forces (counts of squads, tanks, guns) and installations.
Every strategic tick the war moves on everywhere except where the player is:
fronts push, reserves march toward the fighting, depots and batteries matter.
The player's sector is simulated in full; units flow in and out of it.
"""
from __future__ import annotations

import math
import random
from collections import Counter

import numpy as np
import tcod

from .constants import ALLIES, AXIS, SIDES, other_side

UNIT_POWER = {"inf": 1.0, "mg": 0.8, "mortar": 0.6, "at": 0.7, "hq": 0.5, "sniper": 0.4,
              "eng": 0.9, "tank": 4.0, "td": 3.0, "atgun": 1.4, "ht": 1.6}
UNIT_NAME = {"inf": "infantry squads", "mg": "MG teams", "mortar": "mortar teams",
             "at": "AT teams", "hq": "HQ sections", "sniper": "snipers", "eng": "engineer squads",
             "tank": "tanks", "td": "tank destroyers", "atgun": "AT guns", "ht": "half-tracks"}
BIOME_GLYPH = {"farmland": '"', "bocage": "#", "forest": "♣", "village": "⌂", "town": "▓",
               "city_ruins": "▒", "factory": "Σ", "steppe": ",", "desert": "~", "hills": "^",
               "mountain": "▲", "abbey": "Ω", "marsh": "≈", "jungle": "♠", "volcanic": "°",
               "sea": "≈", "beach": "░"}
BIOME_NAME = {"farmland": "farmland", "bocage": "bocage", "forest": "forest", "village": "village",
              "town": "town", "city_ruins": "ruined city", "factory": "factory district",
              "steppe": "steppe", "desert": "desert", "hills": "hills", "mountain": "mountains",
              "abbey": "abbey heights", "marsh": "marshland", "jungle": "jungle",
              "volcanic": "volcanic ash", "sea": "open sea", "beach": "beach"}
DIRS = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
OPP = {"N": "S", "S": "N", "E": "W", "W": "E"}


def power(units: Counter) -> float:
    return sum(UNIT_POWER.get(k, 1.0) * n for k, n in units.items())


class Sector:
    def __init__(self, x, y, biome):
        self.x = x
        self.y = y
        self.biome = biome
        self.name = ""
        self.control = None
        self.units = {ALLIES: Counter(), AXIS: Counter()}
        self.fort = 0
        self.installations: list[list] = []     # [kind, side, intact]
        self.river = None
        self.river_pos = 0.5
        self.sea_edge = None
        self.saved = None
        self.visited = False
        self.contested = False
        self.seed = 0
        self.inland = "farmland"
        self.news = []
        self.last_fight = -1

    @property
    def playable(self):
        return self.biome != "sea"

    def installs(self, side=None, kind=None):
        return [i for i in self.installations if i[2] and (side is None or i[1] == side)
                and (kind is None or i[0] == kind)]


def _partisan_theatres():
    from .threat import PARTISANS
    return PARTISANS


class Strategic:
    def __init__(self, theatre: dict, rng: random.Random, year: float, scale: float = 1.0):
        self.th = theatre
        self.rng = rng
        self.year = year
        self.scale = scale                          # troops per sector, against the standard battlefield
        self.w, self.h = theatre["om_size"]         # the battle's own map; the world goes on beyond it
        self.cells: dict = {}                       # (x, y) -> Sector, made as they're first needed
        self._by_lat: dict = {}                     # lateral line -> {depth: Sector} (for extending the front)
        self.seed = rng.randint(1, 2 ** 30)
        self.focus = None                           # the player's sector: the war is simulated around it
        self.sim_radius = 9
        self.attacker = theatre["attacker"]
        self.defender = other_side(self.attacker)
        self.att_from = theatre["attacker_from"]
        self.ticks = 0
        self.news: list[str] = []
        self.losses = {ALLIES: 0.0, AXIS: 0.0}
        self.player_orders = {}            # side -> the player's standing orders on the war map
        self.order_news: list[str] = []
        self._generate()

    # ------------------------------------------------------------ generation
    def _generate(self):
        th = self.th
        rng = self.rng
        w, h = self.w, self.h
        biomes = th["biomes"]
        noise = tcod.noise.Noise(2, seed=rng.randint(0, 10 ** 6))
        nv = noise.sample_ogrid([np.arange(w) * 0.4, np.arange(h) * 0.4])
        names = list(th.get("places", []))
        rng.shuffle(names)
        weights = [b[1] for b in biomes]
        for x in range(w):
            for y in range(h):
                r = (nv[x, y] + 1) / 2
                # noise-biased pick keeps similar terrain together
                idx = min(len(biomes) - 1, int(r * len(biomes) * 0.999))
                if rng.random() < 0.45:
                    b = rng.choices([bb[0] for bb in biomes], weights)[0]
                else:
                    b = biomes[idx][0]
                s = Sector(x, y, b)
                s.seed = rng.randint(1, 2 ** 30)
                self.cells[(x, y)] = s
        for f in th.get("features", []):
            kind = f[0]
            if kind == "sea":
                edge, depth = f[1], f[2]
                for s in self.sectors():
                    if self._depth_from(s, edge) < depth:
                        s.biome = "sea"
            elif kind == "beach":
                edge = f[1]
                for s in self.sectors():
                    if s.biome != "sea" and any(n.biome == "sea" for n in self.neighbors(s, edge_only=edge)):
                        s.inland = s.biome if s.biome not in ("sea",) else "farmland"
                        if s.inland in ("town", "city_ruins", "abbey"):
                            s.inland = "bocage"
                        s.sea_edge = edge
                        s.biome = "beach"
            elif kind == "river":
                orient, pos = f[1], f[2]
                for s in self.sectors():
                    if (orient == "v" and s.x == pos) or (orient == "h" and s.y == pos):
                        if s.biome not in ("sea",):
                            s.river = orient
                            s.river_pos = 0.5
            elif kind == "biome":
                _, x, y, b = f
                if 0 <= x < w and 0 <= y < h:
                    self.cells[(x, y)].biome = b
            elif kind == "city":
                _, cx, cy, r, b = f
                for s in self.sectors():
                    if abs(s.x - cx) + abs(s.y - cy) <= r:
                        s.biome = b
        # names
        pool = list(names)
        generic = ["Hill {n}", "Point {n}", "Farm {l}", "Crossroads {l}", "Wood {l}", "Ridge {l}"]
        for s in self.sectors():
            if s.biome == "sea":
                s.name = "open water"
                continue
            if pool:
                s.name = pool.pop()
            else:
                s.name = rng.choice(generic).format(n=rng.randint(60, 600), l="ABCDEFGHJK"[rng.randint(0, 9)])
        # control
        front = th.get("front", 0.35)
        att = self.attacker
        dfn = self.defender
        jitter = noise.sample_ogrid([np.arange(w) * 0.7 + 50, np.arange(h) * 0.7 + 50])
        span = h if self.att_from in ("N", "S") else w
        for s in self.sectors():
            d = self._depth_from(s, self.att_from) / max(1, span - 1)
            if s.biome == "sea":
                s.control = att if front == 0 or self._depth_from(s, self.att_from) == 0 else None
                continue
            s.control = att if d + jitter[s.x, s.y] * 0.08 < front else dfn
        self.pocket = None
        for f in th.get("features", []):
            if f[0] == "pocket":
                _, cx, cy, r = f
                self.pocket = (cx, cy, r)
                for s in self.sectors():
                    if s.biome == "sea":
                        continue
                    inside = max(abs(s.x - cx), abs(s.y - cy)) <= r
                    s.control = dfn if inside else att
        # forces
        self._initial_forces()
        for c in self.cells.values():
            self.scale_units(c.units, rng)
        if self.pocket is not None:
            cx, cy, r = self.pocket
            for s in self.sectors():
                if s.control == dfn and max(abs(s.x - cx), abs(s.y - cy)) <= r:
                    for k in list(s.units[dfn]):
                        s.units[dfn][k] = int(s.units[dfn][k] * 1.8) + 1
                    s.fort = max(s.fort, 2)
        self._installations()
        from .world import LANG
        for c in self.cells.values():
            c.lang = LANG.get(th.get("id", ""), "en")
            self._index(c)
        from .homefront import prepare
        for c in self.cells.values():
            prepare(self, c)

    def _depth_from(self, s, edge):
        return {"N": s.y, "S": self.h - 1 - s.y, "W": s.x, "E": self.w - 1 - s.x}[edge]

    def __setstate__(self, state):
        # saves from before the world was infinite: a fixed grid of sectors
        grid = state.pop("grid", None)
        self.__dict__.update(state)
        if "cells" not in state:
            self.cells = {}
            for col in grid or []:
                for c in col:
                    self.cells[(c.x, c.y)] = c
            self._by_lat = {}
            for c in self.cells.values():
                self._index(c)
            self.seed = random.randint(1, 2 ** 30)
            self.focus = None
            self.sim_radius = 9

    def sectors(self):
        """Every sector made so far."""
        return list(self.cells.values())

    def in_core(self, s) -> bool:
        return 0 <= s.x < self.w and 0 <= s.y < self.h

    def active(self):
        """The sectors where the war is being simulated: the battle's own map, and the ground around you."""
        f = self.focus
        if f is None:
            return list(self.cells.values())
        r = self.sim_radius
        return [c for c in self.cells.values()
                if (0 <= c.x < self.w and 0 <= c.y < self.h) or max(abs(c.x - f[0]), abs(c.y - f[1])) <= r]

    def at(self, x, y, create=False):
        c = self.cells.get((x, y))
        if c is None and create:
            c = self._make(x, y)
        return c

    def touch(self, x, y, r=2):
        """Make sure the ground around (x, y) exists, and centre the simulation there."""
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if (x + dx, y + dy) not in self.cells:
                    self._make(x + dx, y + dy)
        self.focus = (x, y)

    def neighbors(self, s, edge_only=None, create=False):
        out = []
        for e, (dx, dy) in DIRS.items():
            if edge_only and e != edge_only:
                continue
            n = self.at(s.x + dx, s.y + dy, create)
            if n is not None:
                out.append(n)
        return out

    # ------------------------------------------------------------ the world beyond the battle
    def _axes(self, x, y):
        """(lateral line, depth from the attacker's side) of a sector."""
        a = self.att_from
        if a == "W":
            return y, x
        if a == "E":
            return y, self.w - 1 - x
        if a == "N":
            return x, y
        return x, self.h - 1 - y

    def _index(self, c):
        lat, dep = self._axes(c.x, c.y)
        self._by_lat.setdefault(lat, {})[dep] = c

    def _formula_boundary(self, lat) -> float:
        from .world import noise
        span = self.h if self.att_from in ("N", "S") else self.w
        front = self.th.get("front", 0.35)
        if self.pocket is not None:
            front = 1.35              # beyond the ring round the pocket, the defenders' main line
        jitter = noise(lat, 50, self.seed, 0.7)
        base = (front - jitter * 0.08) * (span - 1)
        latspan = self.w if self.att_from in ("N", "S") else self.h
        beyond = max(0, -lat, lat - (latspan - 1))
        # away from the battle's own map the line wanders: salients, bulges, a river line held here and not there
        wander = noise(lat, 90, self.seed, 0.18) * 2.5 + noise(lat, 130, self.seed, 0.6) * 0.8
        return base + wander * min(1.0, beyond / 6)

    def _boundary(self, lat) -> float:
        """Where the front runs across lateral line lat: from the ground already known, else the theatre's shape."""
        vals = []
        form = self._formula_boundary(lat)
        own = self._by_lat.get(lat)
        for ln in ((lat,) if own else ()) + (lat - 1, lat + 1, lat - 2, lat + 2):
            line = self._by_lat.get(ln)
            if not line:
                continue
            att = [d for d, c in line.items() if c.control == self.attacker and c.playable
                   and not (self.pocket is not None and self.in_core(c))]
            dfn = [d for d, c in line.items() if c.control == self.defender and c.playable
                   and not (self.pocket is not None and self.in_core(c))]
            if att and dfn:
                vals.append((max(att) + min(dfn)) / 2)
            elif att:
                vals.append(max(form, max(att) + 0.5))
            elif dfn:
                vals.append(min(form, min(dfn) - 0.5))
            if len(vals) >= 2 or (own and vals):
                break
        if not vals:
            return form
        known = sum(vals) / len(vals)
        if own:
            return known
        # carry the line on from its neighbours, but let it drift toward the lie of the land
        return known * 0.65 + form * 0.35

    def _depth_xy(self, x, y, edge):
        return {"N": y, "S": self.h - 1 - y, "W": x, "E": self.w - 1 - x}[edge]

    def _sea_at(self, x, y) -> bool:
        from .world import coast_sea, island_sea
        for f in self.th.get("features", []):
            if f[0] == "sea" and self._depth_xy(x, y, f[1]) < f[2]:
                return True
        tid = self.th.get("id", "")
        return island_sea(tid, x, y) or coast_sea(tid, self.w, self.h, x, y)

    def predict_control(self, x, y):
        c = self.cells.get((x, y))
        if c is not None:
            return c.control
        if self._sea_at(x, y):
            return self.attacker if self.th.get("front", 0.35) == 0 or self._depth_xy(x, y, self.att_from) <= 0 \
                else None
        lat, dep = self._axes(x, y)
        return self.attacker if dep < self._boundary(lat) else self.defender

    def _make(self, x, y):
        """A sector nobody has needed until now."""
        from .world import noise, place_name, region
        th = self.th
        rng = random.Random(hash((self.seed, x, y)) & 0x7FFFFFFF)
        lang, pal = region(th.get("id", ""), self.w, self.h, x, y)
        sea = self._sea_at(x, y)
        if sea:
            b = "sea"
        else:
            biomes = th["biomes"] if pal in (None, "drift") else pal
            if pal == "drift" and rng.random() < 0.25:
                biomes = [("farmland", 3), ("village", 3), ("forest", 2), ("town", 1)] \
                    if th["climate"] not in ("desert", "tropical", "volcanic") else th["biomes"]
            r = (noise(x, y, self.seed, 0.4) + 1) / 2
            idx = min(len(biomes) - 1, int(r * len(biomes) * 0.999))
            if rng.random() < 0.45:
                b = rng.choices([bb[0] for bb in biomes], [bb[1] for bb in biomes])[0]
            else:
                b = biomes[idx][0]
            if b in ("abbey", "sea", "beach"):
                b = "hills"
        c = Sector(x, y, b)
        c.seed = rng.randint(1, 2 ** 30)
        c.lang = lang
        for f in th.get("features", []):
            if f[0] == "beach" and not sea and self._sea_at(x + DIRS[f[1]][0], y + DIRS[f[1]][1]):
                c.inland = b if b not in ("town", "city_ruins") else "bocage" if th["climate"] == "summer" else "farmland"
                c.sea_edge = f[1]
                c.biome = "beach"
            elif f[0] == "river" and not sea:
                if (f[1] == "v" and x == f[2]) or (f[1] == "h" and y == f[2]):
                    c.river = f[1]
        c.name = "open water" if sea else place_name(lang, rng)
        c.control = self.predict_control(x, y)
        self.cells[(x, y)] = c
        self._index(c)
        self._outer_forces(c, rng)
        from .homefront import prepare
        prepare(self, c)
        self.scale_units(c.units, rng)
        self._fd = None
        return c

    def _outer_forces(self, c, rng):
        th = self.th
        side = c.control
        if side is None or not c.playable:
            return
        enemy = other_side(side)
        lat, dep = self._axes(c.x, c.y)
        latspan = self.w if self.att_from in ("N", "S") else self.h
        lateral = max(0, -lat, lat - (latspan - 1))
        quiet = max(0.45, 1 - lateral * 0.04)        # the main effort was where the battle started
        front = any(self.predict_control(c.x + dx, c.y + dy) == enemy for dx, dy in DIRS.values())
        depth = abs(dep - self._boundary(lat))
        inten = th.get("intensity", 1.0) * quiet
        armor = th["armor"].get(side, 0.3)
        u = c.units[side]
        if front:
            u["inf"] += int(rng.randint(5, 9) * inten)
            u["mg"] += rng.randint(1, 2)
            u["mortar"] += rng.randint(0, 2)
            u["hq"] += 1
            u["at"] += rng.randint(0, 2) if th["armor"].get(enemy, 0) > 0.2 else 0
            if side == self.defender:
                c.fort = th.get("fort", 1)
                if th["armor"].get(self.attacker, 0) > 0.2:
                    u["atgun"] += rng.randint(0, 2)
        elif depth < 3.5:
            u["inf"] += int(rng.randint(2, 5) * inten)
            u["mg"] += rng.randint(0, 1)
            u["hq"] += 1 if rng.random() < 0.4 else 0
        else:
            # the rear: garrisons, security troops, men resting out of the line
            u["inf"] += rng.randint(0, 2)
            u["hq"] += 1 if rng.random() < 0.3 else 0
        if armor > 0 and (front or depth < 5):
            u["tank"] += int(rng.random() * armor * (4 if front else 3))
            if rng.random() < armor * 0.4:
                u["td"] += 1
            if rng.random() < armor * 0.6:
                u["ht"] += rng.randint(0, 1)
        u["sniper"] += 1 if front and rng.random() < 0.3 else 0
        u["eng"] += 1 if rng.random() < 0.2 else 0
        for k in [k for k, n in u.items() if n <= 0]:
            del u[k]
        # the rear is full of things armies need
        if depth >= 1.5 and not front:
            ins = c.installations
            for kind, p in (("depot", 0.08), ("aid", 0.08), ("hq", 0.04), ("aa", 0.05 if th["air"].get(enemy, 0) > 0.3 else 0),
                            ("artillery", 0.12 if depth <= 4.5 else 0.03),
                            ("motor_pool", 0.05 if armor > 0.35 else 0),
                            ("airfield", 0.04 if depth >= 4 and c.biome in ("farmland", "steppe", "desert", "volcanic", "hills")
                             else 0),
                            ("naval_base", 0.12 if c.sea_edge is not None and depth >= 2 else 0)):
                if len(ins) < 2 and rng.random() < p:
                    ins.append([kind, side, True])
        elif front and side == self.defender and th.get("fort", 0) >= 2 and rng.random() < 0.06:
            c.installations.append(["fortress", side, True])

    # ------------------------------------------------------------ how many men a sector holds
    def sc(self, n, rng=None) -> int:
        """n units on a standard battlefield, on this one (rounded by chance)."""
        v = n * self.__dict__.get("scale", 1.0)
        base = int(v)
        return base + (1 if (rng or self.rng).random() < v - base else 0)

    def scale_units(self, units, rng=None):
        sc = self.__dict__.get("scale", 1.0)
        if sc == 1.0:
            return
        for side in list(units):
            u = units[side]
            for k in list(u):
                u[k] = self.sc(u[k], rng)
                if u[k] <= 0:
                    del u[k]

    def _arrive(self, dst, side, units, src=None):
        """Units reaching a sector.  The player's sector is counted from the map every tick, so there
        they must come as a wave marching in (from the neighbour they left, or from their own rear)."""
        if dst is not None and dst is self.__dict__.get("_psec"):
            u = Counter({k: v for k, v in units.items() if v > 0})
            if u and self.__dict__.get("_events") is not None:
                self._events.append(("reinforce", side, u, self.neighbor_dir(dst, src) if src is not None else None))
            return
        dst.units[side].update(units)

    def neighbor_dir(self, s, n) -> str | None:
        for e, (dx, dy) in DIRS.items():
            if s.x + dx == n.x and s.y + dy == n.y:
                return e
        return None

    def is_front(self, s, side) -> bool:
        return s.control == side and any(n.control == other_side(side) and n.playable
                                         for n in self.neighbors(s))

    def _initial_forces(self):
        th = self.th
        rng = self.rng
        inten = th.get("intensity", 1.0)
        for s in self.sectors():
            side = s.control
            if side is None:
                continue
            front = self.is_front(s, side)
            armor = th["armor"].get(side, 0.3)
            if s.biome == "sea":
                # landing force staging offshore
                if side == self.attacker:
                    u = s.units[side]
                    u["inf"] += int(rng.randint(8, 12) * inten)
                    u["mg"] += rng.randint(1, 3)
                    u["eng"] += rng.randint(1, 3)
                    u["hq"] += 1
                    u["at"] += rng.randint(0, 2)
                    u["mortar"] += rng.randint(1, 2)
                    if armor > 0.15:
                        u["tank"] += rng.randint(0, 3)
                continue
            u = s.units[side]
            base = (rng.randint(6, 10) if front else rng.randint(2, 5)) * inten
            if side == self.attacker and front:
                base *= 1.3
            u["inf"] += int(base)
            u["mg"] += rng.randint(1, 2) if front else rng.randint(0, 1)
            u["mortar"] += rng.randint(0, 2) if front else 0
            u["hq"] += 1 if front or rng.random() < 0.4 else 0
            u["at"] += rng.randint(0, 2) if armor > 0.2 or th["armor"].get(other_side(side), 0) > 0.3 else 0
            u["sniper"] += 1 if rng.random() < 0.35 else 0
            u["eng"] += 1 if rng.random() < 0.3 else 0
            if armor > 0:
                u["tank"] += int(rng.random() * armor * (5 if front else 3))
                if rng.random() < armor * 0.5:
                    u["td"] += rng.randint(1, 2)
                if rng.random() < armor:
                    u["ht"] += rng.randint(0, 2)
            if side == self.defender and th["armor"].get(self.attacker, 0) > 0.2:
                u["atgun"] += rng.randint(1, 3) if front else rng.randint(0, 1)
            if side == self.defender:
                s.fort = th.get("fort", 1) if front else max(0, th.get("fort", 1) - 1)
            # Paradrop theatres: the attacker's first wave falls into enemy land
        if any(k.startswith("paradrop") for k in th.get("special", ())):
            pside = ALLIES if "paradrop_allies" in th["special"] else AXIS
            owned_by_enemy = [s for s in self.sectors() if s.control == other_side(pside) and s.playable]
            rng.shuffle(owned_by_enemy)
            for s in owned_by_enemy[: max(3, len(owned_by_enemy) // 3)]:
                s.units[pside]["inf"] += rng.randint(3, 7)
                s.units[pside]["mg"] += rng.randint(0, 1)
                s.units[pside]["hq"] += rng.randint(0, 1)
                s.units[pside]["at"] += rng.randint(0, 1)
                s.contested = True

    def _installations(self):
        rng = self.rng
        th = self.th
        for side in SIDES:
            owned = [s for s in self.sectors() if s.control == side and s.playable]
            if not owned:
                continue
            rear = sorted(owned, key=lambda s: -self._front_distance(s, side))
            fronts = [s for s in owned if self.is_front(s, side)]

            def place(kind, cands, n):
                cands = [c for c in cands if len(c.installations) < 2]
                rng.shuffle(cands)
                for c in cands[:n]:
                    c.installations.append([kind, side, True])

            depth = max(1, len(rear) // 2)
            place("depot", rear[:depth], rng.randint(1, 2))
            place("artillery", rear[:depth + 2], 1 + int(th["arty"].get(side, 0.5) * 3))
            if th["air"].get(other_side(side), 0) > 0.3:
                place("aa", rear[:depth + 2], rng.randint(1, 2))
            place("hq", rear[:depth], 1)
            place("aid", rear[:depth + 1], rng.randint(1, 2))
            if th["armor"].get(side, 0) > 0.35:
                place("motor_pool", rear[:depth], 1)
            if th["air"].get(side, 0) > 0.55 and rng.random() < 0.5:
                place("airfield", [r for r in rear[:depth] if r.biome in ("farmland", "steppe", "desert", "volcanic", "hills")], 1)
            if side == self.defender and th.get("fort", 0) >= 2:
                place("fortress", fronts, rng.randint(1, 3))
            # a navy's harbour, on its own shore well back from the fighting
            coast = [c for c in rear[:depth + 2] if c.sea_edge is not None and not self.is_front(c, side)]
            if coast:
                place("naval_base", coast, 1)

    def _front_distance(self, s, side) -> int:
        """Steps from s to the nearest enemy-held sector (99: nowhere near)."""
        from collections import deque
        fd = getattr(self, "_fd", None)
        if fd is None or fd[0] != self.ticks:
            fd = self._fd = (self.ticks, {})
        d = fd[1].get(side)
        if d is None:
            d = {}
            q = deque()
            for c in self.cells.values():
                if c.control == other_side(side) and c.playable:
                    d[(c.x, c.y)] = 0
                    q.append((c.x, c.y))
            while q:
                x, y = q.popleft()
                v = d[(x, y)]
                if v >= 40:
                    continue
                for dx, dy in DIRS.values():
                    k = (x + dx, y + dy)
                    if k in self.cells and k not in d:
                        d[k] = v + 1
                        q.append(k)
            fd[1][side] = d
        return d.get((s.x, s.y), 99)

    # ------------------------------------------------------------ queries
    def _priority(self, side, kind):
        for o in getattr(self, "player_orders", {}).get(side, ()):
            if o["kind"] == kind:
                return self.at(*o["src"])
        return None

    def priority_mult(self, side, kind, s) -> float:
        """Artillery / air priority given to a sector (and its neighbours) by the player's orders."""
        pr = self._priority(side, kind)
        if pr is None or s is None:
            return 1.0
        return 1.45 if abs(pr.x - s.x) + abs(pr.y - s.y) <= 1 else 0.8

    def support_mult(self, side, kind, current) -> float:
        if current is None:
            return 1.0
        if kind in ("arty", "air"):
            return self._support_mult(side, kind, current) * self.priority_mult(side, kind, current)
        return self._support_mult(side, kind, current)

    def _support_mult(self, side, kind, current) -> float:
        if kind == "arty":
            n = 0
            for s in self._around(current, 3):
                n += len(s.installs(side, "artillery"))
                n += 0.5 * len(s.installs(side, "depot"))
            return max(0.3, min(1.8, 0.45 + 0.35 * n))
        if kind == "air":
            enemy_aa = sum(len(s.installs(other_side(side), "aa")) for s in self._around(current, 2))
            own_fields = sum(len(s.installs(side, "airfield")) for s in self._around(current, 8))
            return max(0.2, min(1.5, 1.0 - 0.2 * enemy_aa + 0.15 * own_fields))
        if kind == "supply":
            n = sum(len(s.installs(side, "depot")) for s in self._around(current, 3))
            return max(0.3, min(1.5, 0.5 + 0.4 * n))
        return 1.0

    def _around(self, c, r):
        """Existing sectors within Manhattan distance r."""
        for dx in range(-r, r + 1):
            for dy in range(-(r - abs(dx)), r - abs(dx) + 1):
                o = self.cells.get((c.x + dx, c.y + dy))
                if o is not None:
                    yield o

    # ------------------------------------------------------------ supply lines
    def compute_supply(self):
        """How well each sector is supplied: from depots, command posts and the side's rear, through its own ground."""
        from collections import deque
        old = getattr(self, "supply", {}) or {}
        sup = {}
        par = {}
        cut = self.__dict__.setdefault("interdiction", {})
        rear_edge = {self.attacker: self.att_from, self.defender: OPP[self.att_from]}
        for side in SIDES:
            q = deque()
            best = {}
            for s in self.sectors():
                if s.control != side and not (s.biome == "sea" and side == self.attacker):
                    continue
                src = 0.0
                if any(k in ("depot", "hq") and sd == side and ok for k, sd, ok in s.installations):
                    src = 1.0
                e = rear_edge[side]
                if self._depth_from(s, e) <= 0:
                    src = max(src, 0.9)
                elif s.playable and not self.in_core(s):
                    # ground nobody's needed yet, behind our lines, is our rear
                    for dx, dy in DIRS.values():
                        if (s.x + dx, s.y + dy) not in self.cells and self.predict_control(s.x + dx, s.y + dy) == side:
                            src = max(src, 0.85)
                            break
                if s.biome == "sea" and side == self.attacker:
                    src = max(src, 0.8)               # supplied over the beach
                if src > 0:
                    best[(s.x, s.y)] = src
                    q.append(s)
            # a source whose own roads are cut sends less
            for k in list(best):
                best[k] = max(0.0, best[k] - 0.55 * cut.get((side,) + k, 0.0))
            while q:
                s = q.popleft()
                v = best[(s.x, s.y)]
                for n in self.neighbors(s):
                    if n.control != side and not (n.biome == "sea" and side == self.attacker):
                        continue
                    # every sector the supplies pass through costs a little; a cut road there, a lot
                    nv = v - 0.12 / max(.35, self.__dict__.get("weather_transport", 1.0)) - \
                        0.55 * cut.get((side, n.x, n.y), 0.0)
                    if nv > best.get((n.x, n.y), 0.0) + 1e-6:
                        best[(n.x, n.y)] = nv
                        par[(side, n.x, n.y)] = (s.x, s.y)
                        q.append(n)
            for s in self.sectors():
                if s.control == side:
                    sup[(side, s.x, s.y)] = max(0.0, best.get((s.x, s.y), 0.0))
        self.supply_parent = par
        # the traffic on each road: every front sector's supplies come up through the sectors behind it
        traffic = {}
        for side in SIDES:
            for s in self.sectors():
                if s.control != side or not s.playable or not self.is_front(s, side):
                    continue
                w = 1.0 + power(s.units[side]) / 12.0
                k = (s.x, s.y)
                seen = set()
                while k is not None and k not in seen:
                    seen.add(k)
                    traffic[(side,) + k] = traffic.get((side,) + k, 0.0) + w
                    k = par.get((side,) + k)
        self.traffic = traffic
        # news of pockets
        for (side, x, y), v in sup.items():
            if v <= 0.0 and old.get((side, x, y), 1.0) > 0.0:
                s = self.at(x, y)
                if s is not None and s.playable:
                    self.news.append(f"{s.name} is cut off. The {'Allied' if side == ALLIES else 'Axis'} troops there are on their own.")
        self.supply = sup
        return sup

    # ------------------------------------------------------------ the roads the supplies come up
    def lines(self, side, s):
        """How the supplies run through sector s: (the neighbour they come from or None - the rear or a depot
        here; the neighbours they go on to; how much traffic) - for convoys on the map (rear.py)."""
        par = self.__dict__.get("supply_parent") or {}
        src = par.get((side, s.x, s.y))
        up = self.at(*src) if src else None
        down = [n for n in self.neighbors(s) if par.get((side, n.x, n.y)) == (s.x, s.y) and n.control == side]
        return up, down, (self.__dict__.get("traffic") or {}).get((side, s.x, s.y), 0.0)

    def fed_by(self, side, s):
        """The front sectors whose supplies come up through s."""
        par = self.__dict__.get("supply_parent") or {}
        out = []
        for f in self.sectors():
            if f.control != side or not self.is_front(f, side):
                continue
            k = (f.x, f.y)
            seen = set()
            while k is not None and k not in seen:
                if k == (s.x, s.y):
                    out.append(f)
                    break
                seen.add(k)
                k = par.get((side,) + k)
        return out

    def interdict(self, side, s, amount, why=None):
        """The road through s cut, a convoy burned, a depot blown: the supplies for everything beyond it are
        short until it's repaired (it mends over hours: tick).  Returns the fronts it starves."""
        cut = self.__dict__.setdefault("interdiction", {})
        k = (side, s.x, s.y)
        before = cut.get(k, 0.0)
        cut[k] = min(1.0, before + amount)
        fronts = self.fed_by(side, s)
        if why and cut[k] >= 0.3 > before - 0.001:
            names = ", ".join(f.name for f in fronts[:3]) or "the line"
            self.news.append(f"{why} Supplies for {names} are held up.")
        self.compute_supply()
        return fronts

    def cut_of(self, side, s) -> float:
        return (self.__dict__.get("interdiction") or {}).get((side, s.x, s.y), 0.0)

    def supply_of(self, side, s) -> float:
        sup = getattr(self, "supply", None)
        if not sup:
            sup = self.compute_supply()
        return sup.get((side, s.x, s.y), 1.0 if s.control == side else 0.0)

    def side_power(self, side) -> float:
        return sum(power(s.units[side]) for s in self.sectors())

    # ------------------------------------------------------------ attacks in progress
    def note_attack(self, dst, side, src=None, planned=False):
        """Remember that `side` is attacking `dst` (from `src`): so it can be seen, heard and walked into."""
        at = self.__dict__.setdefault("attacks", {})
        k = (dst.x, dst.y)
        cur = at.get(k)
        if cur is None or cur["side"] != side:
            at[k] = dict(side=side, src=(src.x, src.y) if src is not None else None, since=self.ticks,
                         last=self.ticks, planned=planned)
        else:
            cur["last"] = self.ticks
            if src is not None:
                cur["src"] = (src.x, src.y)
            cur["planned"] = cur["planned"] or planned

    def attack_on(self, x, y):
        """The attack going in on (x, y) right now, if there is one."""
        at = self.__dict__.get("attacks", {}).get((x, y))
        if at is None or at["last"] < self.ticks - 1:
            return None
        c = self.at(x, y)
        if c is None:
            return None
        if c.control == at["side"] and power(c.units[other_side(at["side"])]) <= 0:
            return None                              # it's over: taken
        return at

    def attacks_near(self, s):
        """Attacks going in next door to s: [(neighbour, attack)]."""
        out = []
        for n in self.neighbors(s):
            a = self.attack_on(n.x, n.y)
            if a is not None:
                out.append((n, a))
        return out

    # ------------------------------------------------------------ simulation
    def tick(self, player_sector, local_units=None):
        """Advance the war one step.  Returns events touching the player's sector."""
        rng = self.rng
        self.ticks += 1
        events = []
        self._fd = None
        act = self.active()
        at = self.__dict__.setdefault("attacks", {})
        for k in [k for k, v in at.items() if v["last"] < self.ticks - 3]:
            del at[k]
        if local_units is not None and player_sector is not None:
            player_sector.units = {s: Counter(local_units.get(s, {})) for s in SIDES}
        # (anything sent into the player's sector this tick must arrive as men on the map: see _arrive)
        self._psec = player_sector
        self._events = events
        # cut roads are mended, convoys re-routed, the dumps restocked: a cut halves in about two hours
        cut = self.__dict__.setdefault("interdiction", {})
        for k in list(cut):
            cut[k] *= 0.94
            if cut[k] < 0.02:
                del cut[k]
        self._raid_the_roads(player_sector)
        self.compute_supply()
        from .sustain import strategic_tick as stock_tick
        stock_tick(self)
        # pockets wither: no food, no ammunition, no way out
        for s in act:
            for side in SIDES:
                if s is player_sector or s.control != side or not s.playable:
                    continue
                if self.supply_of(side, s) <= 0.0 and power(s.units[side]) > 0:
                    self._attrit(s.units[side], power(s.units[side]) * 0.03, side)
        # 0. the player's orders (for a commander of colonel's rank and up)
        planned = self._player_orders(player_sector, events)
        holding = set()
        for side, orders in getattr(self, "player_orders", {}).items():
            for o in orders:
                if o["kind"] == "hold":
                    s0 = self.at(*o["src"])
                    if s0 is not None:
                        holding.add(id(s0))
        # 1. combat between adjacent hostile sectors
        pairs = []
        for s in act:
            if not s.playable:
                continue
            for n in self.neighbors(s):
                if n.control is not None and s.control is not None and n.control != s.control:
                    pairs.append((s, n))
        rng.shuffle(pairs)
        # each sector is attacked at most once per tick, by its strongest hostile neighbour
        best_attacker = {}
        for a, b in pairs:
            if a.control is None or b.control is None or a.control == b.control:
                continue
            if id(a) in holding or id(b) in planned:
                continue
            cur = best_attacker.get(id(b))
            if cur is None or power(a.units[a.control]) > power(cur[0].units[cur[0].control]):
                best_attacker[id(b)] = (a, b)
        pairs = list(best_attacker.values())
        rng.shuffle(pairs)
        for a, b in pairs:
            side = a.control
            enemy = b.control
            if side is None or enemy is None or side == enemy:
                continue
            pa = power(a.units[side])
            pb = power(b.units[enemy]) * (1 + 0.25 * b.fort)
            if pa <= 0.5:
                continue
            aggressive = side == self.attacker
            ratio_needed = 1.2 if aggressive else 1.8
            if pa < pb * ratio_needed or rng.random() > (0.6 if aggressive else 0.3):
                continue
            if b is player_sector:
                # send an attack into the player's battle
                sent = self._detach(a.units[side], 0.4)
                if sum(sent.values()) > 0:
                    self.note_attack(b, side, a)
                    events.append(("reinforce", side, sent, self.neighbor_dir(b, a)))
                continue
            if a is player_sector:
                continue       # the player's battle is fought for real
            self._battle(a, b, side, enemy)
        # 1b. amphibious forces offshore push onto the beaches
        for s in act:
            if s.biome != "sea" or s.control != self.attacker or self.ticks % 2:
                continue
            u = s.units[self.attacker]
            if power(u) < 3:
                continue
            beaches = [n for n in self.neighbors(s) if n.biome == "beach"]
            if not beaches:
                continue
            b = rng.choice(beaches)
            wave = self._detach(u, 0.25)
            if b is player_sector:
                events.append(("reinforce", self.attacker, wave, self.neighbor_dir(b, s), "landing"))
            elif b.control == self.attacker:
                b.units[self.attacker].update(wave)
            else:
                b.units[self.attacker].update(wave)
                if power(b.units[self.defender]) > 0:
                    self._internal_battle(b)
        # 2. contested sectors (paradrops etc.) fight internally
        for s in act:
            if s is player_sector or not s.playable:
                continue
            pa, pb = power(s.units[ALLIES]), power(s.units[AXIS])
            if pa > 0 and pb > 0:
                self._internal_battle(s)
            elif pa > 0 and s.control != ALLIES:
                self._capture(s, ALLIES)
            elif pb > 0 and s.control != AXIS:
                self._capture(s, AXIS)
        # 3. reserves move toward the front
        self._move_reserves(player_sector, events)
        # 4. reinforcements from the rear / the sea
        if self.ticks % 2 == 0:
            self._reinforce(player_sector, events)
        self._psec = self._events = None
        return events

    def _raid_the_roads(self, player_sector):
        """Off your map, the other side goes for the roads too: fighter-bombers over the busiest supply routes,
        partisans on the railways in occupied country."""
        rng = self.rng
        th = self.th
        traffic = self.__dict__.get("traffic") or {}
        for side in SIDES:
            enemy = other_side(side)
            air = th.get("air", {}).get(enemy, 0.3)
            busy = sorted(((v, k) for k, v in traffic.items() if k[0] == side), reverse=True)[:6]
            for v, k in busy:
                s = self.at(k[1], k[2])
                if s is None or s is player_sector or self.is_front(s, side):
                    continue
                if rng.random() < air * 0.06:
                    what = rng.choice(["Fighter-bombers caught a convoy on the road at", "Aircraft strafed the columns at",
                                       "A supply column was bombed on the road through"])
                    self.interdict(side, s, rng.uniform(0.15, 0.35), f"{what} {s.name}.")
                elif side == AXIS and th.get("id") in _partisan_theatres() and rng.random() < 0.05:
                    self.interdict(side, s, rng.uniform(0.2, 0.45), f"Partisans blew the line and ambushed the "
                                                                     f"columns near {s.name}.")

    def _player_orders(self, player_sector, events):
        """Carry out the war-map orders.  Returns ids of sectors attacked by plan this tick."""
        rng = self.rng
        planned = set()
        for side, orders in getattr(self, "player_orders", {}).items():
            enemy = other_side(side)
            for o in orders:
                src = self.at(*o["src"])
                if src is None or src.control != side:
                    continue
                dst = self.at(*o["dst"]) if o.get("dst") else None
                k = o["kind"]
                if k == "hold":
                    if src.fort < 3 and rng.random() < 0.35:
                        src.fort += 1
                        self.order_news.append(f"{src.name} reports the new positions are dug in "
                                               f"(fortification {src.fort}/3).")
                elif k == "move" and dst is not None and dst.control == side:
                    if src is player_sector:
                        continue          # the troops here are fighting: command them on the ground
                    moved = self._detach(src.units[side], 0.5)
                    if sum(moved.values()) == 0:
                        self.order_news.append(f"{src.name} has nothing left to send.")
                        continue
                    if dst is player_sector:
                        events.append(("reinforce", side, moved, self.neighbor_dir(dst, src)))
                    else:
                        dst.units[side].update(moved)
                    self.order_news.append(f"Movement order: {sum(moved.values())} units march from "
                                           f"{src.name} to {dst.name}.")
                elif k == "attack" and dst is not None and dst.control == enemy:
                    if power(src.units[side]) < 1:
                        self.order_news.append(f"{src.name} can't attack: there's nobody left to send.")
                        continue
                    planned.add(id(dst))
                    self.note_attack(dst, side, src, planned=True)
                    if dst is player_sector:
                        sent = self._detach(src.units[side], 0.5)
                        events.append(("reinforce", side, sent, self.neighbor_dir(dst, src)))
                        continue
                    if src is player_sector:
                        # the troops on your battlefield form up and march off the edge into the attack
                        events.append(("sally", side, (dst.x, dst.y), self.neighbor_dir(src, dst)))
                        continue
                    before = dst.control
                    self._battle(src, dst, side, enemy, planned=True)
                    if dst.control == side and before != side:
                        self.order_news.append(f"Your attack from {src.name} has taken {dst.name}!")
                    else:
                        self.order_news.append(f"The attack on {dst.name} goes in. Heavy fighting; "
                                               f"{dst.name} still holds.")
        return planned

    def _detach(self, units: Counter, frac: float) -> Counter:
        out = Counter()
        for k, n in list(units.items()):
            take = int(n * frac + self.rng.random())
            take = min(take, n)
            if take > 0:
                out[k] = take
                units[k] -= take
                if units[k] <= 0:
                    del units[k]
        return out

    def _attrit(self, units: Counter, loss_power: float, side: str):
        rng = self.rng
        lost = 0.0
        keys = list(units.elements())
        rng.shuffle(keys)
        for k in keys:
            if lost >= loss_power:
                break
            units[k] -= 1
            if units[k] <= 0:
                del units[k]
            lost += UNIT_POWER.get(k, 1.0)
        self.losses[side] += lost

    def _battle(self, a, b, side, enemy, planned=False):
        """One tick of pressure across a border.  Fronts move slowly; odds decide the drift."""
        rng = self.rng
        th = self.th
        self.note_attack(b, side, a, planned)
        pa = power(a.units[side]) * (0.85 if planned else 0.7)    # not everything can be committed
        if planned:
            pa *= 1.2                                            # a prepared, coordinated attack
        pa *= self.priority_mult(side, "arty", b) * (0.5 + 0.5 * self.priority_mult(side, "air", b))
        pb_mult = self.priority_mult(enemy, "arty", b) * (0.55 + 0.45 * self.supply_of(enemy, b))
        pa *= 0.55 + 0.45 * self.supply_of(side, a)
        pb = power(b.units[enemy]) * pb_mult
        pa *= 1 + 0.25 * th["air"].get(side, 0.5) + 0.2 * th["arty"].get(side, 0.5)
        pb *= (1 + 0.2 * th["air"].get(enemy, 0.5) + 0.2 * th["arty"].get(enemy, 0.5)) * (1 + 0.3 * b.fort)
        if side == self.attacker:
            pa *= 1.2                           # initiative and concentration
        conc = getattr(self, "concentration", {}).get((b.x, b.y), 1)
        if planned and conc >= 2:
            pa *= 1 + 0.25 * (conc - 1)         # several divisions attacking together, on one plan
        odds = pa / max(0.1, pa + pb)
        # both sides bleed a little
        self._attrit(a.units[side], pb * rng.uniform(0.003, 0.009), side)
        self._attrit(b.units[enemy], pa * rng.uniform(0.003, 0.01), enemy)
        b.last_fight = self.ticks
        p_cap = max(0.0, odds - 0.55) * 0.35
        if power(b.units[enemy]) < 0.5:
            p_cap = 1.0
        if rng.random() < p_cap:
            survivors = b.units[enemy]
            retreat = [n for n in self.neighbors(b) if n.control == enemy and n.playable]
            if retreat and power(survivors) > 0:
                self._arrive(rng.choice(retreat), enemy, survivors, src=b)
            b.units[enemy] = Counter()
            b.units[side].update(self._detach(a.units[side], 0.5))
            self._capture(b, side)

    def _internal_battle(self, s):
        rng = self.rng
        pa, pb = power(s.units[ALLIES]), power(s.units[AXIS])
        if s.control in SIDES:
            self.note_attack(s, other_side(s.control))
        k = rng.uniform(0.1, 0.25)
        self._attrit(s.units[ALLIES], pb * k, ALLIES)
        self._attrit(s.units[AXIS], pa * k, AXIS)
        s.last_fight = self.ticks

    def _capture(self, s, side):
        prev = s.control
        from .sustain import stores, deliver
        if prev is not None and prev != side:
            stores(s, prev)
            stores(s, side)
        s.control = side
        self._fd = None
        if prev != side:
            s.captured_tick = self.ticks
        s.fort = max(0, s.fort - 1)
        s.contested = False
        from .homefront import FACILITIES
        for inst in s.installations:
            if inst[1] != side and inst[2]:
                if inst[0] in FACILITIES:
                    inst[1] = side     # intact works and hospitals survive a change of hands
                else:
                    inst[2] = False
        if prev is not None and prev != side:
            for kind, amount in stores(s, prev).items():
                deliver(s, side, kind, amount * .5)
                stores(s, prev)[kind] = 0.
            self.news.append(f"{s.name} has fallen to the {'Allies' if side == ALLIES else 'Axis'}.")

    def _move_reserves(self, player_sector, events):
        rng = self.rng
        for side in SIDES:
            moved_into = set()
            order = self.active()
            rng.shuffle(order)
            for s in order:
                if id(s) in moved_into:
                    continue
                if s.control != side or not s.playable and not (s.biome == "sea" and side == self.attacker):
                    continue
                if s is player_sector:
                    continue
                if self.is_front(s, side):
                    continue
                u = s.units[side]
                if power(u) < 2:
                    continue
                # step toward the nearest front
                best = None
                bd = self._front_distance(s, side)
                for n in self.neighbors(s):
                    if n.control != side or not n.playable:
                        continue
                    d = self._front_distance(n, side)
                    if d < bd:
                        bd, best = d, n
                if best is None:
                    continue
                moved = self._detach(u, 0.5)
                moved_into.add(id(best))
                if best is player_sector:
                    events.append(("reinforce", side, moved, self.neighbor_dir(best, s)))
                else:
                    best.units[side].update(moved)

    def _reinforce(self, player_sector, events):
        rng = self.rng
        th = self.th
        if not hasattr(self, "_last_losses"):
            self._last_losses = dict(self.losses)
        for side in SIDES:
            # replacements: roughly half of what was lost since last time comes back up the line
            lost = self.losses[side] - self._last_losses.get(side, 0)
            self._last_losses[side] = self.losses[side]
            repl = lost * 0.55 * (1.2 if side == self.attacker else 1.0)
            owned_f = [s for s in self.active() if s.control == side and s.playable and self.is_front(s, side)
                       and self.supply_of(side, s) > 0.2]
            while repl >= 1 and owned_f:
                tgt = min(owned_f, key=lambda s: power(s.units[side]) + rng.random())
                if rng.random() < 0.3 + 0.7 * self.supply_of(side, tgt):   # (the lorries that bring them up)
                    self._arrive(tgt, side, Counter({"inf": 1}))
                repl -= 1
            owned = [s for s in self.active() if s.control == side]
            if not owned:
                continue
            supply = self.support_mult(side, "supply", owned[0]) if owned else 1.0
            if side == self.attacker:
                supply *= 1.25       # the side with the initiative brought more
            fronts = [s for s in owned if self.is_front(s, side)]
            rear = sorted(fronts, key=lambda s: power(s.units[side]))[:3] or \
                sorted(owned, key=lambda s: -self._front_distance(s, side))[:2]
            if side == self.attacker and "landing" in th.get("special", ()):
                sea = [s for s in self.active() if s.biome == "sea"]
                if sea and rng.random() < 0.5:
                    rear = sea[:1]
            for s in rear:
                if rng.random() < 0.45 * th.get("intensity", 1.0) * supply * (0.4 + 0.6 * self.supply_of(side, s)):
                    add = Counter({"inf": self.sc(rng.randint(1, 2))})
                    if rng.random() < th["armor"].get(side, 0.3) * 0.5:
                        add["tank"] += self.sc(1)
                    if rng.random() < 0.2:
                        add["mg"] += self.sc(1)
                    self._arrive(s, side, add)

    def overview(self) -> dict:
        """Sectors held in the part of the war you can see from here."""
        act = self.active()
        return {"allies": sum(1 for s in act if s.control == ALLIES and s.playable),
                "axis": sum(1 for s in act if s.control == AXIS and s.playable)}
