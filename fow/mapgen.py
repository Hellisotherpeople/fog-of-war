"""Procedural battlefield generation.

generate(spec) builds a GameMap for one strategic sector.  spec keys:
  biome, climate, seed, attacker_edge (N/S/E/W or None), defender_side, fort (0-3),
  river (None | 'h' | 'v'), sea_edge (None | edge), roads (list of edges to connect),
  intensity (pre-battle damage 0..2), name, special (set)
"""
from __future__ import annotations

import math
import random

import numpy as np
import tcod

from . import tiles as T
from .constants import MAP_H, MAP_W
from .gamemap import GameMap, Mine, Objective

OPP = {"N": "S", "S": "N", "E": "W", "W": "E"}

PALETTES = {
    "summer": dict(ground="grass", ground2="dirt", tall="tall_grass", tree="tree", tree2="tree",
                   bush="bush", field=("wheat", "wheat", "plowed", "tall_grass", "corn"),
                   road="road", water="shallow", deep="deep", trench="trench", mud="mud"),
    "autumn": dict(ground="grass_autumn", ground2="mud", tall="tall_grass", tree="tree_autumn",
                   tree2="tree", bush="bush", field=("plowed", "plowed", "grass_autumn", "mud"),
                   road="road", water="shallow", deep="deep", trench="trench", mud="mud"),
    "winter": dict(ground="snow", ground2="deep_snow", tall="deep_snow", tree="tree_snow",
                   tree2="pine", bush="bush_snow", field=("snow", "deep_snow", "snow"),
                   road="road", water="ice", deep="ice", trench="trench_snow", mud="snow"),
    "desert": dict(ground="sand", ground2="rock_ground", tall="scrub", tree="palm", tree2="palm",
                   bush="scrub", field=("sand", "rock_ground"), road="road", water="shallow",
                   deep="deep", trench="trench", mud="sand"),
    "mediterranean": dict(ground="grass_dry", ground2="rock_ground", tall="tall_grass_dry",
                          tree="olive", tree2="tree", bush="scrub",
                          field=("wheat", "grass_dry", "plowed", "tall_grass_dry"),
                          road="road", water="shallow", deep="deep", trench="trench",
                          mud="dirt"),
    "tropical": dict(ground="grass", ground2="mud", tall="kunai", tree="palm", tree2="tree",
                     bush="jungle", field=("paddy", "kunai", "tall_grass"), road="road",
                     water="shallow", deep="deep", trench="trench", mud="mud"),
    "volcanic": dict(ground="ash", ground2="rock_ground", tall="scrub", tree="dead_tree",
                     tree2="palm", bush="scrub", field=("ash", "rock_ground"), road="road",
                     water="shallow", deep="deep", trench="trench", mud="ash"),
}

# how many storeys (a church: its tower; a flat-roofed house: its roof; a barn: the hayloft)
STOREYS = {"farmhouse": 2, "house": 2, "townhouse": 3, "barn": 2, "church": 4, "factory": 2, "desert_house": 2,
           "abbey": 3, "izba": 1, "hut": 1, "shed": 1, "bunker": 1, "log_bunker": 1,
           # the landmarks (landmarks.py)
           "windmill": 3, "post_mill": 3, "chateau": 3, "station": 2, "chapel": 1, "kiln": 1, "elevator": 4,
           "bungalow": 1, "white_church": 3, "shrine": 1, "temple": 1, "pagoda": 5, "tower": 2, "white_house": 2,
           "marabout": 2, "keep": 3, "lighthouse": 4}
CELLARS = {"farmhouse": 0.7, "house": 0.6, "townhouse": 0.8, "church": 0.5, "abbey": 0.8, "izba": 0.4,
           "desert_house": 0.2, "factory": 0.4, "chateau": 0.95, "station": 0.3, "keep": 0.8, "white_house": 0.3}

STYLE = {
    # style: (wall, floor, window chance, furniture)
    "farmhouse": ("wall_stone", "floor_stone", 0.35, "house"),
    "house": ("wall_brick", "floor_wood", 0.45, "house"),
    "townhouse": ("wall_brick", "floor_wood", 0.55, "house"),
    "barn": ("wall_wood", "floor_wood", 0.1, "barn"),
    "shed": ("wall_wood", "dirt", 0.1, "barn"),
    "church": ("wall_stone", "floor_stone", 0.3, "church"),
    "izba": ("wall_log", "floor_wood", 0.3, "house"),
    "hut": ("wall_thatch", "dirt", 0.15, "hut"),
    "bunker": ("wall_concrete", "floor_concrete", 0.0, "bunker"),
    "factory": ("wall_factory", "floor_concrete", 0.25, "factory"),
    "desert_house": ("wall_stone", "floor_stone", 0.15, "house"),
    "abbey": ("wall_stone", "floor_stone", 0.25, "church"),
    "log_bunker": ("wall_log", "dirt", 0.0, "bunker"),
    # the landmarks (landmarks.py)
    "windmill": ("wall_stone", "floor_wood", 0.25, "mill"),
    "post_mill": ("wall_wood", "floor_wood", 0.2, "mill"),
    "chateau": ("wall_stone", "floor_wood", 0.55, "house"),
    "station": ("wall_brick", "floor_wood", 0.5, "station"),
    "chapel": ("wall_stone", "floor_stone", 0.2, "shrine"),
    "kiln": ("wall_brick", "dirt", 0.0, "none"),
    "elevator": ("wall_concrete", "floor_concrete", 0.12, "factory"),
    "bungalow": ("wall_wood", "floor_wood", 0.5, "house"),
    "white_church": ("wall_white", "floor_stone", 0.3, "church"),
    "shrine": ("wall_wood", "floor_wood", 0.15, "shrine"),
    "temple": ("wall_brick", "floor_stone", 0.2, "shrine"),
    "pagoda": ("wall_brick", "floor_wood", 0.3, "none"),
    "tower": ("wall_stone", "floor_stone", 0.3, "none"),
    "white_house": ("wall_white", "floor_stone", 0.2, "house"),
    "marabout": ("wall_white", "floor_stone", 0.0, "shrine"),
    "keep": ("wall_stone", "floor_stone", 0.25, "none"),
    "lighthouse": ("wall_white", "floor_stone", 0.2, "none"),
}


class Gen:
    def __init__(self, spec: dict):
        self.spec = spec
        self.seed = spec.get("seed", 1)
        self.rng = random.Random(self.seed)
        self.w = spec.get("w", MAP_W)
        self.h = spec.get("h", MAP_H)
        self.m = GameMap(self.w, self.h, self.seed)
        self.m.biome = spec.get("biome", "farmland")
        self.m.climate = spec.get("climate", "summer")
        self.m.name = spec.get("name", "sector")
        self.pal = PALETTES.get(self.m.climate, PALETTES["summer"])
        self.roads: list[list[tuple[int, int]]] = []
        self.protected = np.zeros((self.w, self.h), bool)   # don't overwrite (roads, water)
        self.positions: list[dict] = []                     # defensive positions for spawns
        self.poi: list[tuple[str, int, int, int]] = []      # candidate objectives
        self.att = spec.get("attacker_edge")
        self.fort = spec.get("fort", 0)
        self.k = (self.w * self.h) / float(MAP_W * MAP_H)    # how much more country than the standard field

    # ---------------------------------------------------------------- helpers
    def key(self, name: str) -> str:
        return self.pal.get(name, name)

    def noise(self, scale=0.05, octaves=4, salt=0) -> np.ndarray:
        n = tcod.noise.Noise(2, algorithm=tcod.noise.Algorithm.SIMPLEX, octaves=octaves,
                             seed=(self.seed * 7919 + salt) & 0x7FFFFFFF)
        ox, oy = self.rng.uniform(0, 1000), self.rng.uniform(0, 1000)
        return n.sample_ogrid([np.arange(self.w) * scale + ox, np.arange(self.h) * scale + oy])

    def put(self, x, y, key, force=False):
        if 0 <= x < self.w and 0 <= y < self.h and (force or not self.protected[x, y]):
            self.m.t[x, y] = T.ID[key]

    def get(self, x, y) -> str:
        return T.DEFS[int(self.m.t[x, y])].key

    def area_free(self, x0, y0, x1, y1) -> bool:
        if x0 < 1 or y0 < 1 or x1 >= self.w - 1 or y1 >= self.h - 1:
            return False
        return not self.protected[x0:x1 + 1, y0:y1 + 1].any()

    def mask_where(self, keys) -> np.ndarray:
        ids = [T.ID[k] for k in keys]
        return np.isin(self.m.t, ids)

    def defender_half(self) -> np.ndarray:
        """Boolean mask of the half of the map nearest the defender (away from attacker)."""
        m = np.zeros((self.w, self.h), bool)
        a = self.att
        if a == "N":
            m[:, self.h // 2:] = True
        elif a == "S":
            m[:, :self.h // 2] = True
        elif a == "W":
            m[self.w // 2:, :] = True
        elif a == "E":
            m[:self.w // 2, :] = True
        else:
            m[:] = True
        return m

    def depth_coord(self, x, y) -> float:
        """0 at attacker edge, 1 at defender edge."""
        a = self.att
        if a == "N":
            return y / self.h
        if a == "S":
            return 1 - y / self.h
        if a == "W":
            return x / self.w
        if a == "E":
            return 1 - x / self.w
        return 0.5

    def point_at_depth(self, depth: float, lateral: float) -> tuple[int, int]:
        a = self.att or "N"
        if a in ("N", "S"):
            y = int(depth * (self.h - 1)) if a == "N" else int((1 - depth) * (self.h - 1))
            return int(lateral * (self.w - 1)), y
        x = int(depth * (self.w - 1)) if a == "W" else int((1 - depth) * (self.w - 1))
        return x, int(lateral * (self.h - 1))

    # ---------------------------------------------------------------- base layers
    def base_ground(self, tall_amt=0.15, mud_amt=0.08):
        n1 = self.noise(0.06, salt=1)
        n2 = self.noise(0.11, salt=2)
        g = T.ID[self.key("ground")]
        self.m.t[:] = g
        self.m.t[n1 > 1 - tall_amt * 2.2] = T.ID[self.key("tall")]
        self.m.t[n2 > 1 - mud_amt * 2.5] = T.ID[self.key("ground2")]

    def forests(self, amount=0.2, density=0.55, scale=0.035, bush=0.35, salt=3,
                tree=None, tree2=None):
        n = self.noise(scale, salt=salt)
        thresh = 1 - amount * 2.2
        mask = (n > thresh) & ~self.protected
        r = np.random.default_rng(self.seed + salt)
        rnd = r.random((self.w, self.h))
        t1 = T.ID[tree or self.key("tree")]
        t2 = T.ID[tree2 or self.key("tree2")]
        b = T.ID[self.key("bush")]
        inner = mask & (n > thresh + 0.12)
        self.m.t[mask & (rnd < density * 0.6)] = t1
        self.m.t[inner & (rnd < density) & (rnd >= density * 0.6)] = t2
        self.m.t[mask & (rnd >= density) & (rnd < density + bush * (1 - density))] = b
        return mask

    def scatter(self, key, prob, where=None):
        r = np.random.default_rng(self.rng.randint(0, 10 ** 9))
        mask = r.random((self.w, self.h)) < prob
        mask &= ~self.protected
        if where is not None:
            mask &= where
        self.m.t[mask] = T.ID[key]

    # ---------------------------------------------------------------- roads & rivers
    def road(self, start, end, width=1, key=None, meander=12.0, salt=10, sunken=False):
        key = key or self.key("road")
        n = self.noise(0.08, salt=salt + len(self.roads))
        cost = (1 + (n + 1) * meander).astype(np.int32)
        cost[self.m.t == T.ID["deep"]] = 40
        path = tcod.path.path2d(cost, start_points=[start], end_points=[end], cardinal=2,
                                diagonal=3)
        pts = [tuple(p) for p in path]
        rid = T.ID[key]
        for x, y in pts:
            for dx in range(width):
                for dy in range(width):
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < self.w and 0 <= yy < self.h:
                        if T.WATER[self.m.t[xx, yy]] >= 1 and self.get(xx, yy) != "marsh":
                            self.m.t[xx, yy] = T.ID["bridge"]
                        else:
                            self.m.t[xx, yy] = rid
                        self.protected[xx, yy] = True
        if sunken:
            # hedges on both sides (bocage sunken lane)
            for x, y in pts[2:-2]:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    xx, yy = x + dx * width, y + dy * width
                    if 0 < xx < self.w - 1 and 0 < yy < self.h - 1 and not self.protected[xx, yy]:
                        if self.rng.random() < 0.8:
                            self.m.t[xx, yy] = T.ID["hedge"]
        self.roads.append(pts)
        return pts

    def edge_point(self, edge: str, frac: float | None = None) -> tuple[int, int]:
        f = frac if frac is not None else self.rng.uniform(0.15, 0.85)
        if edge == "N":
            return int(f * (self.w - 1)), 0
        if edge == "S":
            return int(f * (self.w - 1)), self.h - 1
        if edge == "W":
            return 0, int(f * (self.h - 1))
        return self.w - 1, int(f * (self.h - 1))

    def road_point(self, edge):
        """Where a road leaves the map: fixed per border, so it meets the next sector's road."""
        return self.edge_point(edge, (self.spec.get("road_fracs") or {}).get(edge))

    def road_network(self, n_roads=2, key=None, width=1, sunken=False):
        edges = list(self.spec.get("roads") or ["N", "S", "E", "W"])
        pairs = []
        if len(edges) >= 2:
            self.rng.shuffle(edges)
        center = (self.w // 2 + self.rng.randint(-25, 25), self.h // 2 + self.rng.randint(-18, 18))
        for i in range(max(n_roads, len(edges))):
            e = edges[i % len(edges)]
            pairs.append((self.road_point(e), center))
        # through road
        if n_roads >= 2:
            thru = [ab for ab in (("N", "S"), ("E", "W")) if ab[0] in edges and ab[1] in edges]
            if thru:
                a, b = self.rng.choice(thru)
                pairs.append((self.road_point(a), self.road_point(b)))
        for s, e in pairs:
            self.road(s, e, width=width, key=key, sunken=sunken)
        # crossroads is an objective candidate
        self.poi.append(("the crossroads", center[0], center[1], 7))
        return center

    def river(self, orient="v", pos=0.5, width=None, key_deep=None, key_shallow=None, bridges=1):
        width = width or self.rng.randint(4, 9)
        deep = T.ID[key_deep or self.key("deep")]
        shallow = T.ID[key_shallow or self.key("water")]
        n = self.noise(0.03, octaves=2, salt=20)
        cells = []
        if orient == "v":
            for y in range(self.h):
                cx = int(pos * self.w + n[int(pos * self.w), y] * 14)
                for x in range(cx - width // 2 - 1, cx + width // 2 + 2):
                    if 0 <= x < self.w:
                        edge = abs(x - cx) >= width // 2
                        self.m.t[x, y] = shallow if edge else deep
                        self.protected[x, y] = True
                        cells.append((x, y))
        else:
            for x in range(self.w):
                cy = int(pos * self.h + n[x, int(pos * self.h)] * 10)
                for y in range(cy - width // 2 - 1, cy + width // 2 + 2):
                    if 0 <= y < self.h:
                        edge = abs(y - cy) >= width // 2
                        self.m.t[x, y] = shallow if edge else deep
                        self.protected[x, y] = True
                        cells.append((x, y))
        # banks: mud and reeds
        for x, y in cells[:: 3]:
            for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2), (3, 0), (-3, 0), (0, 3), (0, -3)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < self.w and 0 <= yy < self.h and not self.protected[xx, yy]:
                    if self.rng.random() < 0.25:
                        self.m.t[xx, yy] = T.ID[self.key("tall")]
        self.river_orient = orient
        self.river_pos = pos
        return cells

    def bridge_over(self, orient, pos, frac=None):
        """A road crossing the river with a bridge."""
        frac = frac if frac is not None else self.rng.uniform(0.3, 0.7)
        if orient == "v":
            s, e = (0, int(frac * self.h)), (self.w - 1, int(frac * self.h) + self.rng.randint(-10, 10))
        else:
            s, e = (int(frac * self.w), 0), (int(frac * self.w) + self.rng.randint(-10, 10), self.h - 1)
        pts = self.road(s, e, width=2)
        bx = [p for p in pts if self.get(*p) == "bridge"]
        if bx:
            mx, my = bx[len(bx) // 2]
            self.poi.append(("the bridge", mx, my, 6))
        return pts

    # ---------------------------------------------------------------- buildings
    def building(self, x0, y0, bw, bh, style="house", ruin=0.0, door_side=None, rooms=True):
        if bw < 3 or bh < 3:
            return None
        if x0 < 1 or y0 < 1 or x0 + bw >= self.w - 1 or y0 + bh >= self.h - 1:
            return None
        wall, floor, win_p, furn = STYLE[style]
        m = self.m
        wid, fid = T.ID[wall], T.ID[floor]
        m.t[x0:x0 + bw, y0:y0 + bh] = wid
        m.t[x0 + 1:x0 + bw - 1, y0 + 1:y0 + bh - 1] = fid
        # partitions
        if rooms and bw >= 9 and bh >= 7 and furn in ("house", "church") and self.rng.random() < 0.8:
            px = x0 + self.rng.randint(3, bw - 4)
            m.t[px, y0 + 1:y0 + bh - 1] = wid
            gy = self.rng.randint(y0 + 1, y0 + bh - 2)
            m.t[px, gy] = T.ID["door_open"] if self.rng.random() < 0.6 else T.ID["door"]
            if bh >= 9 and self.rng.random() < 0.6:
                py = y0 + self.rng.randint(3, bh - 4)
                side = self.rng.choice([(x0 + 1, px), (px + 1, x0 + bw - 1)])
                m.t[side[0]:side[1], py] = wid
                gx = self.rng.randint(side[0], side[1] - 1)
                m.t[gx, py] = T.ID["doorway"]
        # perimeter positions (non-corner)
        perim = []
        for x in range(x0 + 1, x0 + bw - 1):
            perim.append((x, y0, "N"))
            perim.append((x, y0 + bh - 1, "S"))
        for y in range(y0 + 1, y0 + bh - 1):
            perim.append((x0, y, "W"))
            perim.append((x0 + bw - 1, y, "E"))
        # windows
        if furn == "bunker":
            face = self.att or "N"
            emb = [p for p in perim if p[2] == face]
            self.rng.shuffle(emb)
            for x, y, _ in emb[: max(1, len(emb) // 2)]:
                m.t[x, y] = T.ID["embrasure"]
            # side embrasures
            for x, y, s in perim:
                if s not in (face, OPP[face]) and self.rng.random() < 0.25:
                    m.t[x, y] = T.ID["embrasure"]
            door_side = door_side or OPP[face]
        else:
            for x, y, s in perim:
                if self.rng.random() < win_p and (x + y) % 2 == 0:
                    m.t[x, y] = T.ID["window"]
        # doors
        sides = [door_side] if door_side else ["N", "S", "E", "W"]
        if door_side is None:
            self.rng.shuffle(sides)
        ndoors = 1 if furn in ("bunker", "hut") else self.rng.randint(1, 2)
        placed = 0
        for s in sides:
            cands = [(x, y) for x, y, ss in perim if ss == s]
            if not cands:
                continue
            x, y = self.rng.choice(cands[1:-1] or cands)
            ox, oy = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}[s]
            if not (0 <= x + ox < self.w and 0 <= y + oy < self.h):
                continue
            if furn == "barn" and bw > 5:
                m.t[x, y] = T.ID["doorway"]
                if s in ("N", "S") and x + 1 < x0 + bw - 1:
                    m.t[x + 1, y] = T.ID["doorway"]
            elif furn == "bunker":
                m.t[x, y] = T.ID["doorway"]
            else:
                m.t[x, y] = T.ID["door"] if self.rng.random() < 0.75 else T.ID["door_open"]
            # keep the approach clear
            ax, ay = x + ox, y + oy
            if not T.WALK[m.t[ax, ay]] or T.TALL[m.t[ax, ay]]:
                m.t[ax, ay] = T.ID[self.key("ground")] if furn != "bunker" else T.ID[self.key("trench")]
            placed += 1
            if placed >= ndoors:
                break
        # furniture
        self._furnish(x0, y0, bw, bh, furn)
        # the stairs up, and a trapdoor to the cellar (against a wall, where they'd be)
        storeys = STOREYS.get(style, 1)
        inner = [(x, y) for x in range(x0 + 1, x0 + bw - 1) for y in range(y0 + 1, y0 + bh - 1)
                 if T.FLOOR[m.t[x, y]] and self._against_wall(x, y)]
        self.rng.shuffle(inner)
        if storeys > 1 and inner:
            sx, sy = inner.pop()
            m.t[sx, sy] = T.ID["stairs"]
        if inner and self.rng.random() < CELLARS.get(style, 0):
            cx, cy = inner.pop()
            m.t[cx, cy] = T.ID["trapdoor"]
        # ruin
        if ruin > 0:
            self.ruin_rect(x0, y0, bw, bh, ruin)
        self.m.buildings.append((x0, y0, bw, bh, style))
        self.m.__dict__.setdefault("storeys", {})[(x0, y0, bw, bh)] = storeys
        self.protected[x0 - 1:x0 + bw + 1, y0 - 1:y0 + bh + 1] = True
        return (x0, y0, bw, bh)

    def _furnish(self, x0, y0, bw, bh, furn):
        m = self.m
        inner = [(x, y) for x in range(x0 + 1, x0 + bw - 1) for y in range(y0 + 1, y0 + bh - 1)
                 if T.FLOOR[m.t[x, y]] or T.ID["dirt"] == m.t[x, y]]
        if not inner:
            return
        r = self.rng
        if furn == "house":
            for _ in range(max(1, len(inner) // 14)):
                x, y = r.choice(inner)
                if self._against_wall(x, y):
                    m.t[x, y] = T.ID[r.choice(["table", "bed", "stove", "table", "crates"])]
        elif furn == "barn":
            for _ in range(max(1, len(inner) // 8)):
                x, y = r.choice(inner)
                m.t[x, y] = T.ID[r.choice(["hay", "hay", "crates"])]
        elif furn == "church":
            cx = x0 + bw // 2
            m.t[cx, y0 + 2] = T.ID["altar"]
            for y in range(y0 + 4, y0 + bh - 2, 2):
                for x in range(x0 + 2, x0 + bw - 2):
                    if abs(x - cx) > 0 and r.random() < 0.8:
                        m.t[x, y] = T.ID["pew"]
        elif furn == "factory":
            for y in range(y0 + 3, y0 + bh - 3, 4):
                for x in range(x0 + 3, x0 + bw - 3):
                    if r.random() < 0.55:
                        m.t[x, y] = T.ID["machinery"]
            for _ in range(len(inner) // 30):
                x, y = r.choice(inner)
                m.t[x, y] = T.ID["crates"]
        elif furn == "hut":
            if r.random() < 0.5:
                x, y = r.choice(inner)
                m.t[x, y] = T.ID["crates"]
        elif furn == "mill":
            m.t[x0 + bw // 2, y0 + bh // 2] = T.ID["machinery"]        # the millstones and the gearing
        elif furn == "station":
            for _ in range(max(2, len(inner) // 10)):
                x, y = r.choice(inner)
                if self._against_wall(x, y):
                    m.t[x, y] = T.ID[r.choice(["pew", "pew", "table", "crates"])]
        elif furn == "shrine":
            m.t[x0 + bw // 2, y0 + 1] = T.ID["altar"]

    def _against_wall(self, x, y):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if not T.WALK[self.m.t[x + dx, y + dy]] and not T.DOOR[self.m.t[x + dx, y + dy]]:
                return True
        return False

    def ruin_rect(self, x0, y0, bw, bh, ruin):
        m = self.m
        r = self.rng
        for x in range(x0, x0 + bw):
            for y in range(y0, y0 + bh):
                k = self.get(x, y)
                d = T.DEFS[T.ID[k]]
                if d.key.startswith("wall") or d.window or d.door:
                    if r.random() < ruin:
                        m.t[x, y] = T.ID["rubble_heavy" if r.random() < 0.35 else "rubble"]
                    elif d.window and r.random() < 0.7:
                        m.t[x, y] = T.ID["window_broken"]
                elif d.floor or k == "dirt":
                    if r.random() < ruin * 0.35:
                        m.t[x, y] = T.ID[r.choice(["rubble", "rubble_light", "rubble_light", "rubble_heavy"])]
                    elif r.random() < ruin * 0.05:
                        m.t[x, y] = T.ID["crater"]

    # ---------------------------------------------------------------- settlements
    def village(self, cx, cy, n=8, styles=("farmhouse", "house", "barn", "shed"), ruin=0.0,
                church=True, spread=22):
        built = []
        # prefer spots near roads
        road_pts = [p for rd in self.roads for p in rd
                    if abs(p[0] - cx) < spread * 1.3 and abs(p[1] - cy) < spread]
        if church and self.rng.random() < 0.7:
            for _ in range(30):
                bw, bh = self.rng.randint(9, 13), self.rng.randint(14, 18)
                if self.rng.random() < 0.5:
                    bw, bh = bh, bw
                x, y = cx + self.rng.randint(-8, 8) - bw // 2, cy + self.rng.randint(-8, 8) - bh // 2
                if self.area_free(x - 1, y - 1, x + bw + 1, y + bh + 1):
                    b = self.building(x, y, bw, bh, "church", ruin=ruin)
                    if b:
                        built.append(b)
                        self.poi.append(("the church", x + bw // 2, y + bh // 2, 9))
                        # churchyard
                        for _ in range(12):
                            gx = x + self.rng.randint(-4, bw + 3)
                            gy = y + self.rng.randint(-4, bh + 3)
                            if 0 < gx < self.w - 1 and 0 < gy < self.h - 1 and not self.protected[gx, gy]:
                                self.m.t[gx, gy] = T.ID["grave"]
                        break
        tries = 0
        while len(built) < n and tries < n * 25:
            tries += 1
            style = self.rng.choice(styles)
            if style in ("barn",):
                bw, bh = self.rng.randint(7, 12), self.rng.randint(6, 9)
            elif style == "shed":
                bw, bh = self.rng.randint(4, 6), self.rng.randint(4, 5)
            elif style == "hut":
                bw, bh = self.rng.randint(4, 7), self.rng.randint(4, 6)
            else:
                bw, bh = self.rng.randint(6, 11), self.rng.randint(6, 9)
            if self.rng.random() < 0.5:
                bw, bh = bh, bw
            if road_pts and self.rng.random() < 0.7:
                rx, ry = self.rng.choice(road_pts)
                off = self.rng.choice([(2, 2), (-bw - 2, 2), (2, -bh - 2), (-bw - 2, -bh - 2)])
                x, y = rx + off[0] + self.rng.randint(-2, 2), ry + off[1] + self.rng.randint(-2, 2)
            else:
                x = cx + self.rng.randint(-spread, spread) - bw // 2
                y = cy + self.rng.randint(-spread, spread) - bh // 2
            if not self.area_free(x - 1, y - 1, x + bw + 1, y + bh + 1):
                continue
            b = self.building(x, y, bw, bh, style, ruin=ruin)
            if b:
                built.append(b)
                if style in ("farmhouse", "house", "izba") and self.rng.random() < 0.4:
                    self._garden(x, y, bw, bh)
        if built:
            self.poi.append(("the village", cx, cy, 12))
        if self.rng.random() < 0.5:
            wx, wy = cx + self.rng.randint(-6, 6), cy + self.rng.randint(-6, 6)
            if 0 < wx < self.w - 1 and 0 < wy < self.h - 1 and not self.protected[wx, wy]:
                self.m.t[wx, wy] = T.ID["well"]
        return built

    def _garden(self, x, y, bw, bh):
        side = self.rng.choice(["N", "S", "E", "W"])
        gw, gh = bw, self.rng.randint(4, 7)
        if side in ("E", "W"):
            gw, gh = self.rng.randint(4, 7), bh
        gx = x if side in ("N", "S") else (x - gw if side == "W" else x + bw)
        gy = y if side in ("E", "W") else (y - gh if side == "N" else y + bh)
        hedge = self.rng.choice(["garden_hedge", "fence", "low_wall"])
        for xx in range(gx, gx + gw):
            for yy in range(gy, gy + gh):
                if not (0 < xx < self.w - 1 and 0 < yy < self.h - 1) or self.protected[xx, yy]:
                    continue
                border = xx in (gx, gx + gw - 1) or yy in (gy, gy + gh - 1)
                if border and self.rng.random() < 0.85:
                    k = hedge
                    if hedge == "fence":
                        k = "fence" if xx in (gx, gx + gw - 1) else "fence_h"
                    self.m.t[xx, yy] = T.ID[k]
                elif not border and self.rng.random() < 0.15:
                    self.m.t[xx, yy] = T.ID[self.key("tree")]

    def town(self, ruin=0.0, block=(14, 22), street=3, square=True, style="townhouse",
             region=None):
        x0, y0, x1, y1 = region or (4, 4, self.w - 4, self.h - 4)
        m = self.m
        road = T.ID["cobble"] if self.m.climate not in ("desert",) else T.ID["road"]
        xs = [x0]
        while xs[-1] < x1:
            xs.append(xs[-1] + self.rng.randint(*block) + street)
        ys = [y0]
        while ys[-1] < y1:
            ys.append(ys[-1] + self.rng.randint(block[0] - 2, block[1] - 4) + street)
        # streets
        for x in xs:
            m.t[max(0, x - street):min(self.w, x), y0 - 4:y1 + 4] = road
            self.protected[max(0, x - street):min(self.w, x), max(0, y0 - 4):min(self.h, y1 + 4)] = True
        for y in ys:
            m.t[x0 - 4:x1 + 4, max(0, y - street):min(self.h, y)] = road
            self.protected[max(0, x0 - 4):min(self.w, x1 + 4), max(0, y - street):min(self.h, y)] = True
        # square
        sq = None
        if square and len(xs) > 3 and len(ys) > 3:
            i, j = len(xs) // 2 - 1, len(ys) // 2 - 1
            sq = (xs[i], ys[j], xs[i + 1] - street, ys[j + 1] - street)
        for i in range(len(xs) - 1):
            for j in range(len(ys) - 1):
                bx0, by0 = xs[i], ys[j]
                bx1, by1 = xs[i + 1] - street, ys[j + 1] - street
                if bx1 - bx0 < 5 or by1 - by0 < 5:
                    continue
                if bx1 >= self.w - 1 or by1 >= self.h - 1:
                    continue
                if sq and (bx0, by0) == sq[:2]:
                    m.t[bx0:bx1, by0:by1] = road
                    cw, ch = min(11, bx1 - bx0 - 2), min(15, by1 - by0 - 2)
                    self.protected[bx0:bx1, by0:by1] = False
                    self.building(bx0 + 1, by0 + 1, cw, ch, "church", ruin=ruin * 0.8)
                    self.poi.append(("the church", bx0 + 1 + cw // 2, by0 + 1 + ch // 2, 9))
                    self.poi.append(("the town square", (bx0 + bx1) // 2, (by0 + by1) // 2, 10))
                    continue
                self._town_block(bx0, by0, bx1, by1, ruin, style)
        return xs, ys

    def _town_block(self, bx0, by0, bx1, by1, ruin, style):
        """Row houses sharing walls around a courtyard."""
        m = self.m
        r = self.rng
        depth = r.randint(5, 8)
        wid = T.ID[STYLE[style][0]]
        # courtyard fill
        m.t[bx0:bx1, by0:by1] = T.ID[self.key("ground2") if r.random() < 0.5 else "dirt"]
        # split frontage into houses along top and bottom
        for (yy, hh) in ((by0, depth), (by1 - depth, depth)):
            x = bx0
            while x < bx1 - 3:
                wdt = min(r.randint(5, 9), bx1 - x)
                if wdt < 4:
                    break
                if r.random() < 0.9:
                    self.protected[x - 1:x + wdt + 1, yy - 1:yy + hh + 1] = False
                    self.building(x, yy, wdt, hh, style, ruin=ruin, rooms=False,
                                  door_side="N" if yy == by0 else "S")
                x += wdt - 1
        # side buildings
        if by1 - by0 - 2 * depth > 4:
            for xx in (bx0, bx1 - depth):
                if r.random() < 0.6:
                    self.building(xx, by0 + depth - 1, depth, by1 - by0 - 2 * depth + 2, style,
                                  ruin=ruin, rooms=False)
        # courtyard clutter
        for _ in range(r.randint(0, 3)):
            cx, cy = r.randint(bx0 + 1, bx1 - 2), r.randint(by0 + depth, max(by0 + depth, by1 - depth - 1))
            if T.WALK[m.t[cx, cy]] and not T.FLOOR[m.t[cx, cy]]:
                m.t[cx, cy] = T.ID[r.choice(["crates", "tree", "wreck", "rubble"])]
        del wid

    def factory_district(self, ruin=0.4):
        m = self.m
        r = self.rng
        # rail lines
        for _ in range(r.randint(1, 2)):
            if r.random() < 0.5:
                y = r.randint(10, self.h - 10)
                m.t[:, y] = T.ID["rail"]
                self.protected[:, y] = True
            else:
                x = r.randint(10, self.w - 10)
                m.t[x, :] = T.ID["rail"]
                self.protected[x, :] = True
        # big halls
        halls = 0
        for _ in range(60):
            bw, bh = r.randint(20, 40), r.randint(14, 26)
            x, y = r.randint(3, self.w - bw - 3), r.randint(3, self.h - bh - 3)
            if self.area_free(x - 2, y - 2, x + bw + 2, y + bh + 2):
                self.building(x, y, bw, bh, "factory", ruin=ruin)
                halls += 1
                if halls == 1:
                    self.poi.append(("the assembly hall", x + bw // 2, y + bh // 2, 12))
                elif halls == 2:
                    self.poi.append(("the foundry", x + bw // 2, y + bh // 2, 12))
                if halls >= 6:
                    break
        # yards: crates, wrecks, rubble, small offices
        for _ in range(12):
            bw, bh = r.randint(5, 9), r.randint(5, 8)
            x, y = r.randint(3, self.w - bw - 3), r.randint(3, self.h - bh - 3)
            if self.area_free(x - 1, y - 1, x + bw + 1, y + bh + 1):
                self.building(x, y, bw, bh, "house", ruin=ruin)
        self.scatter("crates", 0.01)
        self.scatter("rubble", 0.05)
        self.scatter("rubble_heavy", 0.01)
        self.scatter("wreck", 0.002)

    # ---------------------------------------------------------------- field systems
    def fields(self, style="open", region=None, min_size=14, max_size=30):
        x0, y0, x1, y1 = region or (0, 0, self.w, self.h)
        rects = []

        def split(ax, ay, bx, by, depth=0):
            w, h = bx - ax, by - ay
            if (w <= max_size and h <= max_size and self.rng.random() < 0.6) or w < min_size * 2 and h < min_size * 2:
                rects.append((ax, ay, bx, by))
                return
            if w > h:
                if w < min_size * 2:
                    rects.append((ax, ay, bx, by))
                    return
                c = self.rng.randint(ax + min_size, bx - min_size)
                split(ax, ay, c, by, depth + 1)
                split(c, ay, bx, by, depth + 1)
            else:
                if h < min_size * 2:
                    rects.append((ax, ay, bx, by))
                    return
                c = self.rng.randint(ay + min_size, by - min_size)
                split(ax, ay, bx, c, depth + 1)
                split(ax, c, bx, by, depth + 1)

        split(x0, y0, x1, y1)
        m = self.m
        crops = self.pal["field"]
        for (ax, ay, bx, by) in rects:
            crop = self.rng.choice(crops + (self.key("ground"),))
            cid = T.ID[crop]
            sub = m.t[ax:bx, ay:by]
            free = ~self.protected[ax:bx, ay:by]
            sub[free] = cid
            if style == "bocage":
                border_id = T.ID["hedge"]
                gaps = self.rng.randint(1, 3)
            elif style == "fenced":
                border_id = None
                gaps = 3
            elif style == "walls":
                border_id = T.ID["low_wall"]
                gaps = 3
            else:
                continue
            # borders
            edges = [[(x, ay) for x in range(ax, bx)], [(x, by - 1) for x in range(ax, bx)],
                     [(ax, y) for y in range(ay, by)], [(bx - 1, y) for y in range(ay, by)]]
            for ei, edge in enumerate(edges):
                gap_at = set()
                for _ in range(gaps):
                    g = self.rng.randint(2, max(2, len(edge) - 3))
                    for k in range(g, min(len(edge), g + self.rng.randint(2, 3))):
                        gap_at.add(k)
                for k, (x, y) in enumerate(edge):
                    if k in gap_at or not (0 <= x < self.w and 0 <= y < self.h):
                        continue
                    if self.protected[x, y]:
                        continue
                    if style == "fenced":
                        if self.rng.random() < 0.7:
                            m.t[x, y] = T.ID["fence" if ei >= 2 else "fence_h"]
                    else:
                        m.t[x, y] = border_id
                        if style == "bocage" and self.rng.random() < 0.08:
                            m.t[x, y] = T.ID[self.key("tree")]
        self.field_rects = rects
        return rects

    def orchard(self, x0, y0, bw, bh, key=None):
        k = T.ID[key or self.key("tree")]
        for x in range(x0, x0 + bw, 3):
            for y in range(y0, y0 + bh, 3):
                if 0 < x < self.w - 1 and 0 < y < self.h - 1 and not self.protected[x, y]:
                    self.m.t[x, y] = k
        self.poi.append(("the orchard", x0 + bw // 2, y0 + bh // 2, 8))

    # ---------------------------------------------------------------- defences
    def defences(self, level: int, side_edge: str | None = None):
        """Trenches, wire, bunkers, MG nests and mines for the defender."""
        if level <= 0 or not self.att:
            return
        r = self.rng
        att = self.att
        # main line at 55-70% depth (from attacker edge)
        lines = 1 + (level >= 2) + (level >= 3 and r.random() < 0.6)
        depths = sorted(r.uniform(0.52, 0.72) for _ in range(lines))
        for li, depth in enumerate(depths):
            self._trench_line(depth, level, first=(li == 0))
        # bunkers
        nb = {1: 0, 2: r.randint(1, 2), 3: r.randint(2, 4)}.get(level, 0)
        for _ in range(nb):
            self._bunker(r.uniform(0.5, 0.68), r.uniform(0.1, 0.9))
        # MG nests
        for _ in range(level + r.randint(0, 2)):
            self._mg_nest(r.uniform(0.5, 0.75), r.uniform(0.05, 0.95))
        # foxholes
        for _ in range(8 * level + r.randint(0, 8)):
            x, y = self.point_at_depth(r.uniform(0.5, 0.85), r.uniform(0.02, 0.98))
            if 0 < x < self.w - 1 and 0 < y < self.h - 1 and T.DIG[self.m.t[x, y]] and not self.protected[x, y]:
                self.m.t[x, y] = T.ID["foxhole"]
                self.positions.append(dict(kind="foxhole", x=x, y=y))
        # AT obstacles on roads
        if level >= 2:
            for rd in self.roads:
                for x, y in rd:
                    d = self.depth_coord(x, y)
                    if 0.45 < d < 0.5 and r.random() < 0.4:
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            xx, yy = x + dx * 2, y + dy * 2
                            if 0 < xx < self.w - 1 and 0 < yy < self.h - 1 and T.WALK[self.m.t[xx, yy]]:
                                self.m.t[xx, yy] = T.ID["teeth" if r.random() < 0.5 else "hedgehog"]
        # AT ditch (deep defence belts)
        if level >= 3 and self.m.biome in ("steppe", "farmland") and r.random() < 0.6:
            self._line_feature(r.uniform(0.35, 0.45), "atditch", gap_every=35)

    def _line_points(self, depth, jitter=4, zig=5):
        pts = []
        a = self.att
        n = self.w if a in ("N", "S") else self.h
        off = 0
        for i in range(n):
            if i % zig == 0:
                off = self.rng.randint(-jitter, jitter)
            lat = i / (n - 1)
            x, y = self.point_at_depth(depth, lat)
            if a in ("N", "S"):
                y += off
            else:
                x += off
            pts.append((x, y))
        # connect consecutive points
        full = []
        for p, q in zip(pts, pts[1:]):
            for pt in tcod.los.bresenham(p, q)[:-1]:
                full.append((int(pt[0]), int(pt[1])))
        return full

    def _line_feature(self, depth, key, gap_every=40):
        pts = self._line_points(depth, jitter=1, zig=20)
        for i, (x, y) in enumerate(pts):
            if gap_every and (i % gap_every) < 3:
                continue
            if 0 <= x < self.w and 0 <= y < self.h and not self.protected[x, y]:
                self.m.t[x, y] = T.ID[key]

    def _trench_line(self, depth, level, first=True):
        r = self.rng
        pts = self._line_points(depth)
        tr = T.ID[self.key("trench")]
        segs = []
        cur = []
        for i, (x, y) in enumerate(pts):
            if not (1 <= x < self.w - 1 and 1 <= y < self.h - 1):
                continue
            k = self.get(x, y)
            if T.WATER[self.m.t[x, y]] or not (T.DIG[self.m.t[x, y]] or k in ("road", "rubble", "rubble_light")):
                if cur:
                    segs.append(cur)
                    cur = []
                continue
            if self.protected[x, y] and k not in ("road",):
                continue
            # occasional gaps in the line
            if r.random() < 0.015:
                if cur:
                    segs.append(cur)
                cur = []
                continue
            self.m.t[x, y] = tr
            cur.append((x, y))
        if cur:
            segs.append(cur)
        fx, fy = {"N": (0, -1), "S": (0, 1), "W": (-1, 0), "E": (1, 0)}[self.att]
        for seg in segs:
            if len(seg) < 4:
                continue
            mid = seg[len(seg) // 2]
            self.positions.append(dict(kind="trench", x=mid[0], y=mid[1], tiles=seg))
            # parapet sandbags facing the enemy
            for x, y in seg:
                if r.random() < 0.25 * level:
                    xx, yy = x + fx, y + fy
                    if 0 < xx < self.w - 1 and 0 < yy < self.h - 1 and T.WALK[self.m.t[xx, yy]] \
                            and self.m.t[xx, yy] != tr:
                        self.m.t[xx, yy] = T.ID["sandbags"]
        # wire belt in front
        if first and level >= 1:
            wire_depth_off = r.randint(5, 9)
            for x, y in pts:
                xx, yy = x + fx * wire_depth_off, y + fy * wire_depth_off
                if 0 < xx < self.w - 1 and 0 < yy < self.h - 1 and not self.protected[xx, yy] \
                        and T.WALK[self.m.t[xx, yy]] and r.random() < 0.8:
                    self.m.t[xx, yy] = T.ID["wire"]
                    if level >= 2 and r.random() < 0.6:
                        x2, y2 = xx + fx, yy + fy
                        if 0 < x2 < self.w - 1 and 0 < y2 < self.h - 1 and T.WALK[self.m.t[x2, y2]]:
                            self.m.t[x2, y2] = T.ID["wire"]
            # minefield in front of the wire
            if level >= 2 or "minefields" in self.spec.get("special", ()):
                dens = 0.05 * level
                for x, y in pts:
                    for k in range(wire_depth_off + 2, wire_depth_off + 2 + 4 * level):
                        xx, yy = x + fx * k, y + fy * k
                        if 0 < xx < self.w - 1 and 0 < yy < self.h - 1 and r.random() < dens \
                                and T.WALK[self.m.t[xx, yy]] and not self.protected[xx, yy]:
                            self.add_mine(xx, yy, "smine" if r.random() < 0.3 else "ap")
                    if r.random() < 0.004:
                        xx, yy = x + fx * (wire_depth_off + 1), y + fy * (wire_depth_off + 1)
                        if 0 < xx < self.w - 1 and 0 < yy < self.h - 1 and T.WALK[self.m.t[xx, yy]]:
                            self.m.t[xx, yy] = T.ID["sign"]

    def add_mine(self, x, y, kind):
        side = self.spec.get("defender_side")
        mn = Mine(kind, side)
        if side:
            mn.known.add(side)
        self.m.mines[(x, y)] = mn

    def _bunker(self, depth, lat):
        r = self.rng
        style = "log_bunker" if self.m.biome in ("jungle", "forest") or self.m.climate in ("tropical",) \
            and r.random() < 0.6 else "bunker"
        bw, bh = r.randint(5, 7), r.randint(5, 6)
        if self.att in ("E", "W"):
            bw, bh = bh, bw
        x, y = self.point_at_depth(depth, lat)
        x -= bw // 2
        y -= bh // 2
        if not self.area_free(x - 1, y - 1, x + bw + 1, y + bh + 1):
            self.protected[max(0, x - 1):x + bw + 1, max(0, y - 1):y + bh + 1] = False
            if x < 2 or y < 2 or x + bw > self.w - 2 or y + bh > self.h - 2:
                return
        b = self.building(x, y, bw, bh, style)
        if b:
            n = len([p for p in self.positions if p["kind"] == "bunker"]) + 1
            label = f"bunker {r.choice(['WN', 'Stp', 'B', 'DOT'])}-{r.randint(1, 99)}"
            self.positions.append(dict(kind="bunker", x=x + bw // 2, y=y + bh // 2, rect=b, name=label))
            self.poi.append((label, x + bw // 2, y + bh // 2, 6))
            del n

    def _mg_nest(self, depth, lat):
        x, y = self.point_at_depth(depth, lat)
        if not (3 < x < self.w - 3 and 3 < y < self.h - 3) or self.protected[x, y]:
            return
        fx, fy = {"N": (0, -1), "S": (0, 1), "W": (-1, 0), "E": (1, 0)}[self.att]
        self.m.t[x, y] = T.ID["foxhole"] if T.DIG[self.m.t[x, y]] else self.m.t[x, y]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == dy == 0:
                    continue
                # leave the rear open
                if (dx, dy) == (-fx, -fy) or (fx == 0 and dy == -fy) or (fy == 0 and dx == -fx):
                    continue
                xx, yy = x + dx, y + dy
                if T.WALK[self.m.t[xx, yy]]:
                    self.m.t[xx, yy] = T.ID["sandbags"]
        self.positions.append(dict(kind="mg_nest", x=x, y=y))

    # ---------------------------------------------------------------- damage
    def battle_damage(self, intensity: float):
        r = self.rng
        n = int(intensity * r.randint(15, 40))
        for _ in range(n):
            x, y = r.randint(2, self.w - 3), r.randint(2, self.h - 3)
            rad = r.choice((0, 0, 1, 1, 2))
            for dx in range(-rad, rad + 1):
                for dy in range(-rad, rad + 1):
                    if dx * dx + dy * dy > rad * rad + 1:
                        continue
                    xx, yy = x + dx, y + dy
                    d = self.m.tile(xx, yy)
                    if d.dig and not self.protected[xx, yy] and d.key not in ("trench", "foxhole"):
                        self.m.t[xx, yy] = T.ID["crater_big" if rad >= 2 and dx == dy == 0 else "crater"]
                    elif d.key.startswith("tree") or d.key in ("pine", "olive", "palm"):
                        self.m.t[xx, yy] = T.ID["dead_tree" if r.random() < 0.6 else "stump"]
                    elif d.key.startswith("wall") and r.random() < 0.5:
                        self.m.t[xx, yy] = T.ID["rubble"]
            self.m.scorch[max(0, x - rad - 1):x + rad + 2, max(0, y - rad - 1):y + rad + 2] = 1
        # wrecks
        for _ in range(int(intensity * r.randint(0, 4))):
            x, y = r.randint(5, self.w - 6), r.randint(5, self.h - 6)
            if T.WALK[self.m.t[x, y]] and not T.FLOOR[self.m.t[x, y]] and not T.WATER[self.m.t[x, y]]:
                self.m.t[x, y] = T.ID["wreck"]

    # ---------------------------------------------------------------- beach
    def beach(self, sea_edge: str):
        """Sea along one edge, then surf, wet sand, dry sand, shingle, bluffs."""
        r = self.rng
        n = self.noise(0.04, octaves=2, salt=31)
        depth_len = self.h if sea_edge in ("N", "S") else self.w
        lat_len = self.w if sea_edge in ("N", "S") else self.h
        sea_d = r.randint(18, 26)
        bands = [("deep", sea_d), ("surf", 3), ("shallow", r.randint(8, 12)),
                 ("wet_sand", r.randint(12, 18)), ("sand", r.randint(10, 16))]
        if self.m.climate != "volcanic":
            bands.append(("shingle", r.randint(2, 4)))
        else:
            bands = [(b if b != "sand" else "ash", d) for b, d in bands]
            bands = [(b if b != "wet_sand" else "ash", d) for b, d in bands]
        total = sum(d for _, d in bands)
        self.beach_depth = total
        for lat in range(lat_len):
            off = int(n[min(lat, self.w - 1) if sea_edge in ("N", "S") else 0,
                        0 if sea_edge in ("N", "S") else min(lat, self.h - 1)] * 4)
            d = 0
            for key, bd in bands:
                for k in range(bd + (off if key == "deep" else 0)):
                    if d >= depth_len:
                        break
                    x, y = self._beach_xy(sea_edge, d, lat)
                    self.m.t[x, y] = T.ID[key]
                    self.protected[x, y] = True
                    d += 1
        # bluffs: scrub, tall grass, rock outcrops with draws (gaps)
        bluff0 = total
        bluff_d = r.randint(8, 14)
        draws = [r.randint(10, lat_len - 10) for _ in range(r.randint(2, 4))]
        for lat in range(lat_len):
            in_draw = any(abs(lat - dr) < 4 for dr in draws)
            for k in range(bluff_d):
                x, y = self._beach_xy(sea_edge, bluff0 + k, lat)
                if not (0 <= x < self.w and 0 <= y < self.h):
                    continue
                if in_draw:
                    self.m.t[x, y] = T.ID["road" if abs(lat - min(draws, key=lambda d: abs(d - lat))) < 1 else self.key("tall")]
                else:
                    rr = r.random()
                    self.m.t[x, y] = T.ID["cliff" if rr < 0.12 and 2 < k < bluff_d - 2 else
                                          self.key("tall") if rr < 0.6 else self.key("bush")
                                          if self.m.climate != "volcanic" else "rock_ground"]
                self.protected[x, y] = True
        # beach obstacles
        for lat in range(3, lat_len - 3, 3):
            for band_start, band_len, prob in ((sea_d + 3, 10, 0.35), (sea_d + 13, 12, 0.25)):
                if r.random() < prob:
                    d = band_start + r.randint(0, band_len)
                    x, y = self._beach_xy(sea_edge, d, lat + r.randint(-1, 1))
                    if 0 <= x < self.w and 0 <= y < self.h:
                        self.m.t[x, y] = T.ID["hedgehog"]
                        if r.random() < 0.3:
                            ax, ay = self._beach_xy(sea_edge, d + 1, lat)
                            if 0 <= ax < self.w and 0 <= ay < self.h:
                                self.add_mine(ax, ay, "at")
        # mines on the dry sand and wire at the shingle
        for lat in range(lat_len):
            if r.random() < 0.12:
                x, y = self._beach_xy(sea_edge, total - r.randint(1, 12), lat)
                if 0 <= x < self.w and 0 <= y < self.h:
                    self.add_mine(x, y, "ap")
            if r.random() < 0.7:
                x, y = self._beach_xy(sea_edge, total + 1, lat)
                if 0 <= x < self.w and 0 <= y < self.h and T.WALK[self.m.t[x, y]]:
                    self.m.t[x, y] = T.ID["wire"]
        # strongpoints on the bluffs
        for i, dr in enumerate(draws):
            dd = bluff0 + bluff_d + r.randint(0, 6)
            x, y = self._beach_xy(sea_edge, dd, dr + r.choice((-8, 8)))
            bw, bh = r.randint(6, 8), r.randint(5, 6)
            if sea_edge in ("E", "W"):
                bw, bh = bh, bw
            x = max(2, min(self.w - bw - 3, x - bw // 2))
            y = max(2, min(self.h - bh - 3, y - bh // 2))
            self.protected[x - 1:x + bw + 1, y - 1:y + bh + 1] = False
            b = self.building(x, y, bw, bh, "bunker")
            if b:
                label = f"WN {r.randint(60, 74)}"
                self.positions.append(dict(kind="bunker", x=x + bw // 2, y=y + bh // 2, rect=b, name=label))
                self.poi.append((f"strongpoint {label}", x + bw // 2, y + bh // 2, 7))
        # trench along the bluff top
        self.beach_inland = bluff0 + bluff_d
        self.poi.append(("the draw", *self._beach_xy(sea_edge, bluff0 + bluff_d // 2, draws[0]), 7))
        return total

    def _beach_xy(self, edge, d, lat):
        if edge == "N":
            return lat, d
        if edge == "S":
            return lat, self.h - 1 - d
        if edge == "W":
            return d, lat
        return self.w - 1 - d, lat

    # ---------------------------------------------------------------- terrain features
    def ridges(self, amount=0.08, key="cliff", scale=0.03, salt=40):
        n = self.noise(scale, octaves=3, salt=salt)
        ridge = np.abs(n) < amount
        ridge &= ~self.protected
        # passes
        n2 = self.noise(0.1, salt=salt + 1)
        ridge &= n2 < 0.45
        self.m.t[ridge] = T.ID[key]
        return ridge

    def lakes(self, amount=0.08, salt=50):
        n = self.noise(0.025, octaves=3, salt=salt)
        lake = (n > 1 - amount * 2.5) & ~self.protected
        shore = (n > 1 - amount * 2.5 - 0.06) & ~lake & ~self.protected
        self.m.t[lake] = T.ID[self.key("deep")]
        self.m.t[shore] = T.ID[self.key("water")]
        self.protected |= lake

    # ---------------------------------------------------------------- biomes
    def gen_farmland(self):
        self.base_ground()
        self.road_network(self.rng.randint(1, 3))
        self.fields(style=self.rng.choice(["open", "fenced", "fenced", "walls"]))
        self.forests(amount=0.12)
        vx, vy = self.w // 2 + self.rng.randint(-40, 40), self.h // 2 + self.rng.randint(-25, 25)
        self.village(vx, vy, n=self.rng.randint(4, 9))
        for _ in range(self.rng.randint(0, 2)):
            ox, oy = self.rng.randint(10, self.w - 30), self.rng.randint(10, self.h - 25)
            if self.area_free(ox, oy, ox + 18, oy + 12):
                self.orchard(ox, oy, 18, 12)
        self.scatter("hay", 0.002, self.mask_where(["wheat", "plowed"]))
        self.scatter(self.key("tree"), 0.004)

    def gen_bocage(self):
        self.base_ground(tall_amt=0.1)
        self.road_network(self.rng.randint(1, 2), sunken=True)
        self.fields(style="bocage", min_size=12, max_size=26)
        for _ in range(self.rng.randint(1, 3)):
            fx, fy = self.rng.randint(15, self.w - 30), self.rng.randint(15, self.h - 25)
            self.village(fx, fy, n=self.rng.randint(2, 4), styles=("farmhouse", "barn", "shed"),
                         church=False, spread=10)
            if self.rng.random() < 0.6:
                self.poi.append(("the farm", fx, fy, 9))
        for _ in range(self.rng.randint(1, 3)):
            ox, oy = self.rng.randint(10, self.w - 25), self.rng.randint(10, self.h - 20)
            if self.area_free(ox, oy, ox + 14, oy + 10):
                self.orchard(ox, oy, 14, 10)
        self.forests(amount=0.06)

    def gen_forest(self):
        self.base_ground(tall_amt=0.05)
        if self.rng.random() < 0.8:
            self.road_network(1)
        self.forests(amount=0.55, density=0.5, scale=0.02, bush=0.45,
                     tree=self.key("tree2") if self.m.climate != "summer" else "pine",
                     tree2=self.key("tree"))
        # clearings
        for _ in range(self.rng.randint(2, 5)):
            cx, cy = self.rng.randint(15, self.w - 15), self.rng.randint(15, self.h - 15)
            rad = self.rng.randint(5, 12)
            for x in range(cx - rad, cx + rad):
                for y in range(cy - rad, cy + rad):
                    if (x - cx) ** 2 + (y - cy) ** 2 < rad * rad and 0 < x < self.w - 1 and 0 < y < self.h - 1 \
                            and not self.protected[x, y]:
                        self.m.t[x, y] = T.ID[self.key("ground") if self.rng.random() < 0.8 else self.key("tall")]
            self.poi.append(("the clearing", cx, cy, 8))
        if self.m.climate == "summer" and self.rng.random() < 0.5:
            self.lakes(0.05)
        self.scatter("log", 0.004)
        self.scatter("boulder", 0.002)
        if self.rng.random() < 0.4:
            vx, vy = self.rng.randint(30, self.w - 30), self.rng.randint(25, self.h - 25)
            self.village(vx, vy, n=self.rng.randint(2, 5), styles=("izba", "barn", "shed")
                         if self.m.climate == "winter" else ("farmhouse", "barn", "shed"), church=False)
        # tree bursts - shattered trees
        self.scatter("dead_tree", 0.004, self.mask_where([self.key("tree"), self.key("tree2"), "pine"]))

    def gen_village(self):
        self.gen_farmland_light()
        cx, cy = self.w // 2 + self.rng.randint(-20, 20), self.h // 2 + self.rng.randint(-12, 12)
        izba = self.spec.get("east", False)
        styles = ("izba", "izba", "barn", "shed") if izba else ("farmhouse", "house", "barn", "shed")
        if self.m.climate == "desert":
            styles = ("desert_house",)
        if self.m.climate == "tropical":
            styles = ("hut", "hut", "house")
        self.village(cx, cy, n=self.rng.randint(10, 18), styles=styles,
                     ruin=self.spec.get("ruin", 0.1), spread=30)

    def gen_farmland_light(self):
        self.base_ground()
        self.road_network(self.rng.randint(2, 3))
        self.fields(style=self.rng.choice(["open", "fenced"]))
        self.forests(amount=0.08)

    def gen_town(self, ruin=None):
        self.base_ground()
        ruin = self.spec.get("ruin", 0.12) if ruin is None else ruin
        mx, my = self.rng.randint(8, 25), self.rng.randint(8, 20)
        self.town(ruin=ruin, region=(mx, my, self.w - mx, self.h - my))
        # outskirts
        self.forests(amount=0.05)
        # roads leading out
        for e in (self.spec.get("roads") or []):
            self.road(self.road_point(e), (self.w // 2, self.h // 2), key="cobble")

    def gen_city_ruins(self):
        self.base_ground(tall_amt=0.02, mud_amt=0.2)
        self.m.t[:] = np.where(self.m.t == T.ID[self.key("ground")], T.ID["rubble_light"], self.m.t)
        self.town(ruin=self.rng.uniform(0.35, 0.6), block=(12, 18), region=(3, 3, self.w - 3, self.h - 3))
        self.scatter("crater", 0.02, self.mask_where(["cobble", "rubble_light", "dirt", "mud"]))
        self.scatter("rubble_heavy", 0.01)
        self.scatter("wreck", 0.002)
        self.scatter("dead_tree", 0.003)
        # barricades
        for _ in range(self.rng.randint(4, 10)):
            x, y = self.rng.randint(5, self.w - 6), self.rng.randint(5, self.h - 6)
            horiz = self.rng.random() < 0.5
            for k in range(self.rng.randint(3, 6)):
                xx, yy = (x + k, y) if horiz else (x, y + k)
                if T.WALK[self.m.t[xx, yy]] and not T.FLOOR[self.m.t[xx, yy]]:
                    self.m.t[xx, yy] = T.ID[self.rng.choice(["sandbags", "rubble_heavy", "hedgehog", "crates"])]

    def gen_factory(self):
        self.base_ground(tall_amt=0.02, mud_amt=0.3)
        self.m.t[:] = np.where(self.m.t == T.ID[self.key("ground")], T.ID["rubble_light"], self.m.t)
        self.factory_district(ruin=self.rng.uniform(0.25, 0.55))
        self.scatter("crater", 0.02, self.mask_where(["rubble_light", "dirt", "mud", "rail"]))

    def gen_steppe(self):
        self.base_ground(tall_amt=0.3)
        if self.m.climate == "summer":
            self.fields(style="open", min_size=30, max_size=70)
            crops = self.mask_where(["wheat", "corn"])
            self.scatter("sunflower", 0.8, crops & (self.noise(0.05, salt=77) > 0.3))
        self.road_network(self.rng.randint(1, 2))
        # balkas: winding gullies of scrub and trees
        for _ in range(self.rng.randint(1, 3)):
            s = self.edge_point(self.rng.choice("NSEW"))
            e = (self.rng.randint(20, self.w - 20), self.rng.randint(20, self.h - 20))
            n = self.noise(0.08, salt=90)
            cost = (1 + (n + 1) * 10).astype(np.int32)
            path = tcod.path.path2d(cost, start_points=[s], end_points=[e], cardinal=2, diagonal=3)
            for x, y in path:
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        xx, yy = x + dx, y + dy
                        if 0 < xx < self.w - 1 and 0 < yy < self.h - 1 and not self.protected[xx, yy]:
                            rr = self.rng.random()
                            self.m.t[xx, yy] = T.ID[self.key("bush") if rr < 0.45 else
                                                    self.key("tree") if rr < 0.55 else self.key("tall")]
            self.poi.append(("the balka", e[0], e[1], 8))
        self.forests(amount=0.04)
        vx, vy = self.rng.randint(30, self.w - 30), self.rng.randint(25, self.h - 25)
        self.village(vx, vy, n=self.rng.randint(4, 9), styles=("izba", "izba", "barn", "shed"),
                     spread=18)
        self.scatter("hay", 0.001)

    def gen_desert(self):
        self.base_ground(tall_amt=0.12, mud_amt=0.15)
        self.road_network(self.rng.randint(0, 2))
        # escarpment
        if self.rng.random() < 0.6:
            self.ridges(amount=0.03, key="cliff", scale=0.02)
        self.scatter("boulder", 0.004)
        self.scatter("scrub", 0.03)
        # small stone buildings / fort
        if self.rng.random() < 0.5:
            cx, cy = self.rng.randint(30, self.w - 30), self.rng.randint(25, self.h - 25)
            self.village(cx, cy, n=self.rng.randint(1, 4), styles=("desert_house",), church=False,
                         spread=8)
            self.poi.append(("the bir", cx, cy, 8))
        if self.rng.random() < 0.3:
            ox, oy = self.rng.randint(20, self.w - 20), self.rng.randint(20, self.h - 20)
            for _ in range(20):
                x, y = ox + self.rng.randint(-6, 6), oy + self.rng.randint(-5, 5)
                if 0 < x < self.w - 1 and 0 < y < self.h - 1:
                    self.m.t[x, y] = T.ID["palm"]
        self.poi.append(("the ridge", self.w // 2 + self.rng.randint(-30, 30),
                         self.h // 2 + self.rng.randint(-20, 20), 10))

    def gen_hills(self):
        self.base_ground(tall_amt=0.25, mud_amt=0.25)
        self.road_network(self.rng.randint(1, 2))
        self.ridges(amount=0.035, key="cliff", scale=0.025)
        self.scatter("boulder", 0.006)
        self.forests(amount=0.12, density=0.35)
        if self.m.climate in ("mediterranean", "desert"):
            self.fields(style="walls", min_size=10, max_size=20,
                        region=(10, 10, self.w // 2, self.h // 2))
        vx, vy = self.rng.randint(30, self.w - 30), self.rng.randint(25, self.h - 25)
        st = ("farmhouse", "farmhouse", "shed") if self.m.climate != "tropical" else ("hut",)
        self.village(vx, vy, n=self.rng.randint(2, 5), styles=st, church=False, spread=12)
        self.poi.append((f"Hill {self.rng.randint(80, 600)}", self.w // 2 + self.rng.randint(-40, 40),
                         self.h // 2 + self.rng.randint(-25, 25), 10))

    def gen_mountain(self):
        self.m.t[:] = T.ID["rock_ground"]
        n = self.noise(0.05, salt=5)
        self.m.t[n > 0.45] = T.ID[self.key("tall")]
        self.m.t[n < -0.5] = T.ID[self.key("ground")]
        self.road_network(1)
        self.ridges(amount=0.07, key="cliff", scale=0.028)
        self.ridges(amount=0.03, key="cliff", scale=0.05, salt=45)
        self.scatter("boulder", 0.02)
        self.scatter("scrub", 0.03)
        self.forests(amount=0.08, density=0.3, tree="olive" if self.m.climate == "mediterranean" else None)
        for _ in range(self.rng.randint(1, 3)):
            vx, vy = self.rng.randint(25, self.w - 25), self.rng.randint(20, self.h - 20)
            self.village(vx, vy, n=self.rng.randint(1, 3), styles=("farmhouse", "shed"),
                         church=False, spread=8, ruin=0.4)
        self.poi.append((f"Point {self.rng.randint(400, 700)}", self.rng.randint(40, self.w - 40),
                         self.rng.randint(30, self.h - 30), 8))

    def gen_abbey(self):
        self.gen_mountain()
        cx, cy = self.w // 2, self.h // 2
        self.protected[cx - 30:cx + 30, cy - 20:cy + 20] = False
        self.m.t[cx - 28:cx + 28, cy - 18:cy + 18] = T.ID["rock_ground"]
        self.building(cx - 24, cy - 14, 48, 28, "abbey", ruin=0.55)
        self.building(cx - 8, cy - 10, 16, 20, "church", ruin=0.6)
        self.poi.append(("the abbey", cx, cy, 14))
        self.scatter("crater_big", 0.01, self.mask_where(["rock_ground", "rubble_light", "rubble"]))

    def gen_marsh(self):
        self.base_ground()
        n = self.noise(0.04, salt=60)
        self.m.t[n > 0.1] = T.ID["marsh"]
        self.m.t[n > 0.45] = T.ID[self.key("water")]
        self.m.t[n > 0.7] = T.ID[self.key("deep")]
        self.road_network(1)       # a causeway
        self.forests(amount=0.08)
        if self.rng.random() < 0.5:
            self.village(self.rng.randint(30, self.w - 30), self.rng.randint(25, self.h - 25),
                         n=self.rng.randint(2, 4), church=False)
        self.poi.append(("the causeway", *self.roads[0][len(self.roads[0]) // 2], 8)
                        if self.roads else ("the marsh", self.w // 2, self.h // 2, 10))

    def gen_jungle(self):
        self.base_ground(tall_amt=0.35)
        n = self.noise(0.035, salt=70)
        mask = n > -0.35
        r = np.random.default_rng(self.seed + 71)
        rnd = r.random((self.w, self.h))
        self.m.t[mask & (rnd < 0.62)] = T.ID["jungle"]
        self.m.t[mask & (rnd >= 0.62) & (rnd < 0.72)] = T.ID["tree"]
        self.m.t[mask & (rnd >= 0.72) & (rnd < 0.8)] = T.ID["palm"]
        self.m.t[(n > 0.55) & (rnd < 0.3)] = T.ID["bamboo"]
        # trails
        for _ in range(self.rng.randint(1, 3)):
            a, b = self.rng.choice([("N", "S"), ("E", "W"), ("N", "E"), ("S", "W")])
            self.road(self.edge_point(a), self.edge_point(b), key="dirt", meander=25)
        if self.rng.random() < 0.6:
            self.river(self.rng.choice("hv"), self.rng.uniform(0.3, 0.7), width=self.rng.randint(3, 5))
        self.ridges(amount=0.025, key="cliff", scale=0.03)
        if self.rng.random() < 0.5:
            vx, vy = self.rng.randint(30, self.w - 30), self.rng.randint(25, self.h - 25)
            for x in range(vx - 14, vx + 14):
                for y in range(vy - 10, vy + 10):
                    if 0 < x < self.w - 1 and 0 < y < self.h - 1 and not self.protected[x, y]:
                        self.m.t[x, y] = T.ID["kunai" if self.rng.random() < 0.3 else "grass"]
            self.village(vx, vy, n=self.rng.randint(3, 6), styles=("hut",), church=False, spread=10)
        self.poi.append(("the ridge", self.rng.randint(40, self.w - 40), self.rng.randint(30, self.h - 30), 9))

    def gen_volcanic(self):
        self.m.t[:] = T.ID["ash"]
        n = self.noise(0.05, salt=80)
        self.m.t[n > 0.4] = T.ID["rock_ground"]
        self.m.t[n < -0.55] = T.ID["scrub"]
        self.ridges(amount=0.04, key="cliff", scale=0.03)
        self.scatter("boulder", 0.015)
        self.scatter("dead_tree", 0.004)
        if self.rng.random() < 0.5:
            y = self.rng.randint(30, self.h - 30)
            self.m.t[10:self.w - 10, y:y + 6] = T.ID["runway"]
            self.protected[10:self.w - 10, y:y + 6] = True
            self.poi.append(("the airfield", self.w // 2, y + 3, 12))
        self.road_network(1)
        # spider holes everywhere
        self.scatter("spider_hole", 0.004, self.mask_where(["ash", "rock_ground"]) & self.defender_half())

    # ---------------------------------------------------------------- installations
    INSTALLATION_NAMES = {
        "depot": "supply depot", "artillery": "artillery battery", "aa": "flak position",
        "hq": "command post", "aid": "aid station", "motor_pool": "motor pool",
        "airfield": "airfield", "fortress": "fortress", "naval_base": "naval base",
    }

    def installation(self, kind: str, side: str, depth: float | None = None, lat: float | None = None):
        """Place a base/installation belonging to `side`.  Returns its record."""
        r = self.rng
        defender = self.spec.get("defender_side")
        if depth is None:
            if not self.att:
                depth = r.uniform(0.3, 0.7)
            elif side == defender:
                depth = r.uniform(0.8, 0.9)
            else:
                depth = r.uniform(0.1, 0.2)
        lat = lat if lat is not None else r.uniform(0.2, 0.8)
        cx, cy = self.point_at_depth(depth, lat)
        size = {"depot": (34, 22), "artillery": (40, 18), "aa": (26, 18), "hq": (26, 20),
                "aid": (24, 16), "motor_pool": (34, 22), "airfield": (150, 30),
                "fortress": (70, 34), "naval_base": (44, 34)}[kind]
        sw, sh = size
        if self.att in ("E", "W") and kind not in ("airfield", "naval_base"):
            sw, sh = sh, sw
        x0 = max(3, min(self.w - sw - 3, cx - sw // 2))
        y0 = max(3, min(self.h - sh - 3, cy - sh // 2))
        if kind == "naval_base":
            sea = self.spec.get("sea_edge")
            if sea is None:
                kind = "depot"                   # no water on this map: a naval supply depot inland
                sw, sh = 34, 22
            else:
                # on the waterline: find where the land starts, halfway along the shore
                lat_i = int((self.w if sea in ("N", "S") else self.h) * r.uniform(0.3, 0.7))
                shore = 0
                for d in range(0, (self.h if sea in ("N", "S") else self.w) // 2):
                    x, y = self._beach_xy(sea, d, lat_i)
                    if not T.WATER[self.m.t[x, y]]:
                        shore = d
                        break
                along, deep = (44, 34) if sea in ("N", "S") else (34, 44)
                sw, sh = along, deep
                sx, sy = self._beach_xy(sea, max(0, shore - 12), lat_i)
                if sea == "N":
                    x0, y0 = sx - sw // 2, sy
                elif sea == "S":
                    x0, y0 = sx - sw // 2, sy - sh + 1
                elif sea == "W":
                    x0, y0 = sx, sy - sh // 2
                else:
                    x0, y0 = sx - sw + 1, sy - sh // 2
                x0 = max(1, min(self.w - sw - 1, x0))
                y0 = max(1, min(self.h - sh - 1, y0))
                self.naval_shore = (sea, shore, lat_i)
        if kind == "airfield":
            x0, sw = 10, self.w - 20
        rec = dict(kind=kind, side=side, x=x0 + sw // 2, y=y0 + sh // 2, rect=(x0, y0, sw, sh),
                   name=f"the {self.INSTALLATION_NAMES[kind]}", spots=[])
        # clear the ground (but keep water)
        urban = self.m.biome in ("town", "city_ruins", "factory", "abbey")
        for x in range(x0, x0 + sw):
            for y in range(y0, y0 + sh):
                if not T.WATER[self.m.t[x, y]]:
                    if urban:
                        self.m.t[x, y] = T.ID["dirt"] if r.random() < 0.7 else T.ID["rubble_light"]
                    else:
                        self.m.t[x, y] = T.ID[self.key("ground")] if r.random() < 0.8 else T.ID["dirt"]
        self.protected[x0:x0 + sw, y0:y0 + sh] = False
        getattr(self, f"_inst_{kind}")(rec, x0, y0, sw, sh)
        self.protected[x0 - 1:x0 + sw + 1, y0 - 1:y0 + sh + 1] = True
        self.positions.append(rec)
        self.poi.append((rec["name"], rec["x"], rec["y"], max(8, min(sw, sh) // 2)))
        return rec

    def _perimeter(self, x0, y0, sw, sh, key="wire", gate_side=None, gaps=2):
        gate_side = gate_side or (self.att and OPP[self.att]) or "S"
        pts = []
        for x in range(x0, x0 + sw):
            pts.append((x, y0, "N"))
            pts.append((x, y0 + sh - 1, "S"))
        for y in range(y0 + 1, y0 + sh - 1):
            pts.append((x0, y, "W"))
            pts.append((x0 + sw - 1, y, "E"))
        side_pts = [p for p in pts if p[2] == gate_side]
        gate = side_pts[len(side_pts) // 2] if side_pts else pts[0]
        for x, y, sd in pts:
            if abs(x - gate[0]) + abs(y - gate[1]) <= 1:
                continue
            if self.rng.random() < 0.03 * gaps:
                continue
            if T.WALK[self.m.t[x, y]]:
                self.m.t[x, y] = T.ID[key]
        return gate

    def _tent(self, x, y, tw=5, th=4, cots=True):
        for xx in range(x, x + tw):
            for yy in range(y, y + th):
                if not (0 < xx < self.w - 1 and 0 < yy < self.h - 1):
                    return
        self.m.t[x:x + tw, y:y + th] = T.ID["canvas"]
        self.m.t[x + 1:x + tw - 1, y + 1:y + th - 1] = T.ID["dirt"]
        self.m.t[x + tw // 2, y + th - 1] = T.ID["doorway"]
        if cots:
            for xx in range(x + 1, x + tw - 1, 2):
                self.m.t[xx, y + 1] = T.ID["bed"]

    def _gun_pit(self, x, y, ring="sandbags", open_side=None):
        open_side = open_side or (self.att and OPP[self.att]) or "S"
        ox, oy = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}[open_side]
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                xx, yy = x + dx, y + dy
                if not (0 < xx < self.w - 1 and 0 < yy < self.h - 1):
                    continue
                edge = max(abs(dx), abs(dy)) == 2
                if edge:
                    if (dx * ox + dy * oy) == 2 and abs(dx * oy + dy * ox) <= 1:
                        self.m.t[xx, yy] = T.ID["gun_pit"]
                    elif self.rng.random() < 0.85:
                        self.m.t[xx, yy] = T.ID[ring]
                else:
                    self.m.t[xx, yy] = T.ID["gun_pit"]

    def _inst_depot(self, rec, x0, y0, sw, sh):
        gate = self._perimeter(x0, y0, sw, sh, "wire")
        r = self.rng
        # stacks in rows with aisles
        for y in range(y0 + 3, y0 + sh - 3, 4):
            for x in range(x0 + 3, x0 + sw - 3):
                if (x - x0) % 7 in (0, 1, 2, 3) and r.random() < 0.8:
                    self.m.t[x, y] = T.ID["ammo_stack" if r.random() < 0.65 else "fuel_drums"]
                    if r.random() < 0.5:
                        self.m.t[x, y + 1] = T.ID["ammo_stack" if r.random() < 0.65 else "crates"]
        self._tent(x0 + sw - 8, y0 + 2, 6, 4, cots=False)
        # camouflage nets over part of it
        for _ in range(sw * sh // 25):
            x, y = r.randint(x0 + 1, x0 + sw - 2), r.randint(y0 + 1, y0 + sh - 2)
            if self.get(x, y) in (self.key("ground"), "dirt"):
                self.m.t[x, y] = T.ID["camo_net"]
        self._mg_nest_at(gate[0] + {"N": 0, "S": 0, "E": 2, "W": -2}.get(gate[2], 0),
                         gate[1] + {"N": -2, "S": 2}.get(gate[2], 0))
        rec["spots"] += [("truck", x0 + 4 + i * 5, y0 + sh - 3) for i in range(r.randint(1, 3))]
        rec["spots"].append(("crate", x0 + sw // 2, y0 + sh // 2))
        rec["spots"].append(("qm", x0 + sw - 5, y0 + 7))

    def _mg_nest_at(self, x, y):
        if not (2 < x < self.w - 3 and 2 < y < self.h - 3):
            return
        self.m.t[x, y] = T.ID["gun_pit"]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if (dx or dy) and self.rng.random() < 0.75:
                    self.m.t[x + dx, y + dy] = T.ID["sandbags"]
        self.positions.append(dict(kind="mg_nest", x=x, y=y))

    def _inst_artillery(self, rec, x0, y0, sw, sh):
        r = self.rng
        n = r.randint(3, 4)
        horiz = self.att in ("N", "S") or not self.att
        for i in range(n):
            if horiz:
                gx, gy = x0 + 5 + i * (sw - 10) // max(1, n - 1), y0 + sh // 2 - 2
            else:
                gx, gy = x0 + sw // 2 - 2, y0 + 5 + i * (sh - 10) // max(1, n - 1)
            self._gun_pit(gx, gy)
            rec["spots"].append(("howitzer", gx, gy))
            for _ in range(8):
                nx, ny = gx + r.randint(-4, 4), gy + r.randint(-4, 4)
                if self.get(nx, ny) in (self.key("ground"), "dirt"):
                    self.m.t[nx, ny] = T.ID["camo_net"]
        # ammunition bunker and crew dugouts behind the line
        bx, by = (x0 + sw // 2 - 3, y0 + sh - 7) if horiz else (x0 + sw - 8, y0 + sh // 2 - 3)
        self.building(bx, by, 6, 5, "log_bunker", door_side=None)
        for x in range(bx + 1, bx + 5):
            if T.FLOOR[self.m.t[x, by + 2]] or self.get(x, by + 2) == "dirt":
                self.m.t[x, by + 2] = T.ID["ammo_stack"]
        for _ in range(6):
            fx, fy = x0 + r.randint(2, sw - 3), y0 + r.randint(2, sh - 3)
            if T.DIG[self.m.t[fx, fy]]:
                self.m.t[fx, fy] = T.ID["foxhole"]
        self._tent(x0 + 2, y0 + 1, 5, 4)
        rec["spots"].append(("crate", bx + 3, by - 2))

    def _inst_aa(self, rec, x0, y0, sw, sh):
        r = self.rng
        pts = [(x0 + 5, y0 + 5), (x0 + sw - 6, y0 + 5), (x0 + 5, y0 + sh - 6), (x0 + sw - 6, y0 + sh - 6)]
        r.shuffle(pts)
        for gx, gy in pts[: r.randint(2, 4)]:
            self._gun_pit(gx, gy)
            rec["spots"].append(("aagun", gx, gy))
        self._tent(x0 + sw // 2 - 3, y0 + sh // 2 - 2, 6, 4, cots=False)
        self.m.t[x0 + sw // 2, y0 + sh // 2 - 3] = T.ID["antenna"]
        for _ in range(5):
            x, y = r.randint(x0 + 1, x0 + sw - 2), r.randint(y0 + 1, y0 + sh - 2)
            if self.get(x, y) in (self.key("ground"), "dirt"):
                self.m.t[x, y] = T.ID["ammo_stack"]

    def _inst_hq(self, rec, x0, y0, sw, sh):
        r = self.rng
        if r.random() < 0.5:
            b = self.building(x0 + 4, y0 + 4, sw - 8, sh - 10, "farmhouse")
        else:
            b = self.building(x0 + sw // 2 - 4, y0 + sh // 2 - 3, 9, 7, "bunker")
        self.protected[x0:x0 + sw, y0:y0 + sh] = False
        if b:
            ax, ay = b[0] + b[2], b[1] - 1
            if 0 < ax < self.w - 1 and 0 < ay < self.h - 1:
                self.m.t[ax, ay] = T.ID["antenna"]
        self._perimeter(x0, y0, sw, sh, "sandbags" if r.random() < 0.4 else "wire", gaps=4)
        self._tent(x0 + 2, y0 + sh - 5, 5, 4)
        rec["spots"] += [("car", x0 + sw - 4, y0 + sh - 3), ("guards", x0 + sw // 2, y0 + sh - 2),
                         ("intel", x0 + sw // 2, y0 + sh // 2)]

    def _inst_naval_base(self, rec, x0, y0, sw, sh):
        """A quay along the shore, piers out into the water, a harbour office, a warehouse, fuel tanks."""
        r = self.rng
        m = self.m
        sea, shore, lat_i = getattr(self, "naval_shore", (None, 0, 0))
        if sea is None:
            return self._inst_depot(rec, x0, y0, sw, sh)
        L = sw if sea in ("N", "S") else sh              # along the shore
        a0 = x0 if sea in ("N", "S") else y0

        def xy(d, a):                                   # d: depth from the sea edge, a: along the shore
            return self._beach_xy(sea, d, a)

        def put(d, a, key):
            x, y = xy(d, a)
            if 0 < x < self.w - 1 and 0 < y < self.h - 1:
                m.t[x, y] = T.ID[key]
        # the quay: a paved strip on the waterline
        for a in range(a0, a0 + L):
            for d in range(shore - 1, shore + 3):
                put(d, a, "paved")
            put(shore - 1, a, "paved")
        for a in range(a0 + 2, a0 + L - 2, 6):
            put(shore - 1, a, "bollard")
        # piers out into the water
        piers = [a0 + L // 4, a0 + (3 * L) // 4]
        for pa in piers:
            for d in range(max(1, shore - 12), shore):
                put(d, pa, "pier")
                put(d, pa + 1, "pier")
            put(max(1, shore - 12), pa - 1, "bollard")
        # behind the quay: the harbour office, a warehouse, fuel tanks, stacks of stores
        off = None
        bx, by = xy(shore + 5, a0 + 3)
        bx2, by2 = xy(shore + 12, a0 + 12)
        ox0, oy0 = min(bx, bx2), min(by, by2)
        off = self.building(ox0, oy0, 10, 8, "house", rooms=False)
        wx, wy = xy(shore + 5, a0 + L - 18)
        wx2, wy2 = xy(shore + 14, a0 + L - 4)
        self.building(min(wx, wx2), min(wy, wy2), max(3, abs(wx2 - wx)), max(3, abs(wy2 - wy)), "barn", rooms=False)
        for k in range(8):
            put(shore + 18 + k % 3, a0 + L // 2 - 3 + k // 3 * 2, "fuel_drums")
        for k in range(6):
            put(shore + 5 + k // 2, a0 + L // 2 - 2 + k % 2 * 3, "crates")
        self.protected[x0:x0 + sw, y0:y0 + sh] = False
        # wire round the landward side only (the water is the other wall)
        cx0, cy0 = xy(shore + 3, a0)
        cx1, cy1 = xy(min(shore + 3 + 24, (self.h if sea in ("N", "S") else self.w) - 2), a0 + L - 1)
        ix0, iy0, ix1, iy1 = min(cx0, cx1), min(cy0, cy1), max(cx0, cx1), max(cy0, cy1)
        if ix1 - ix0 > 4 and iy1 - iy0 > 4:
            self._perimeter(ix0, iy0, ix1 - ix0 + 1, iy1 - iy0 + 1, "wire", gaps=3)
            for x in range(ix0, ix1 + 1):
                for y in range(iy0, iy1 + 1):
                    if m.t[x, y] == T.ID["wire"] and self._near_quay(x, y):
                        m.t[x, y] = T.ID["paved"]          # the quay stays open end to end
        px, py = xy(shore, piers[0])
        ofx, ofy = (off[0] + off[2] // 2, off[1] + off[3] // 2) if off else xy(shore + 8, a0 + 8)
        rec["spots"] += [("pier", px, py), ("guards", *xy(shore + 20, a0 + L // 2)), ("crate", *xy(shore + 4, a0 + L // 2)),
                         ("truck", *xy(shore + 16, a0 + L - 8))]
        rec["staff_at"] = {"port_officer": (ofx, ofy), "clerk": (ofx + 1, ofy),
                           "mp": xy(shore + 3, piers[0] + 3), "cook": xy(shore + 16, a0 + 6)}

    def _near_quay(self, x, y):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if 0 <= x + dx < self.w and 0 <= y + dy < self.h and \
                        self.m.t[x + dx, y + dy] in (T.ID["paved"], T.ID["bollard"]):
                    return True
        return False

    def _inst_aid(self, rec, x0, y0, sw, sh):
        r = self.rng
        for i in range(r.randint(2, 3)):
            self._tent(x0 + 2 + i * 7, y0 + 3, 6, 5, cots=True)
        cx, cy = x0 + sw // 2, y0 + sh - 4
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            self.m.t[cx + dx, cy + dy] = T.ID["redcross"]
        rec["spots"] += [("ambulance", x0 + sw - 3, y0 + sh - 2), ("medkit", x0 + 4, y0 + 5),
                         ("medkit", x0 + 11, y0 + 5), ("aidstaff", cx, cy - 2)]

    def _inst_motor_pool(self, rec, x0, y0, sw, sh):
        r = self.rng
        self.building(x0 + 2, y0 + 2, min(18, sw - 6), min(10, sh - 8), "barn")
        self._perimeter(x0, y0, sw, sh, "fence_h", gaps=5)
        for _ in range(8):
            x, y = r.randint(x0 + 2, x0 + sw - 3), r.randint(y0 + sh // 2, y0 + sh - 3)
            if self.get(x, y) in (self.key("ground"), "dirt"):
                self.m.t[x, y] = T.ID["fuel_drums" if r.random() < 0.5 else "crates"]
        for i in range(r.randint(2, 4)):
            rec["spots"].append(("tank_parked", x0 + 5 + i * 7, y0 + sh - 5))
        rec["spots"].append(("crate", x0 + sw - 4, y0 + 4))

    def side_nation(self, side):
        """The main air force / army of a side in this theatre, and the year (for which aircraft)."""
        from .data.theatres import THEATRES
        th = THEATRES.get(self.spec.get("theatre") or "")
        if th is None:
            return ("germany" if side == "axis" else "usa"), 1943.5
        dt = th.get("date", (1943, 6))
        try:
            nat = th["sides"][side][0][0]
        except (KeyError, IndexError, TypeError):
            nat = "germany" if side == "axis" else "usa"
        return nat, dt[0] + (dt[1] - 1) / 12.0

    def _inst_airfield(self, rec, x0, y0, sw, sh):
        from . import parked as PK
        r = self.rng
        ry = y0 + sh // 2 - 4
        self.m.t[x0:x0 + sw, ry:ry + 6] = T.ID["runway"]
        # hangars along the top
        for i in range(r.randint(2, 3)):
            hx = x0 + 10 + i * (sw // 3)
            self.building(hx, y0 + 1, 18, 9, "factory")
        self.protected[x0:x0 + sw, y0:y0 + sh] = False
        # the dispersal below the runway: aircraft at their real size, noses to the runway, the fighters in
        # earth revetments
        nat, year = self.side_nation(rec.get("side"))
        sch = PK.scheme(nat, year, self.m.climate)
        dy0 = ry + 7
        x = x0 + 8
        want = r.randint(4, 8)
        placed = 0
        while x < x0 + sw - 12 and placed < want:
            roles = ("fighter", "fighterbomber") if r.random() < 0.65 else \
                ("bomber", "divebomber", "attacker", "transport", "torpedo")
            pac = self.m.climate == "tropical" or self.spec.get("lang") in ("ja", "mel")
            model = PK.pick(nat, year, roles, r, pacific=pac)
            if model is None:
                break
            w, h = PK.box(model, 0)
            if dy0 + h >= y0 + sh - 1 or not PK.fits(self.m, model, x, dy0, 0):
                model = PK.pick(nat, year, ("fighter", "fighterbomber"), r, pacific=pac)
                if model is None:
                    break
                w, h = PK.box(model, 0)
                if dy0 + h >= y0 + sh - 1 or not PK.fits(self.m, model, x, dy0, 0):
                    x += 3
                    continue
            PK.place(self.m, model, x, dy0, 0, nat, scheme=sch)
            placed += 1
            if w <= 9:
                for yy in range(dy0 + 1, dy0 + h + 1):
                    for xx in (x - 1, x + w):
                        if T.WALK[self.m.t[xx, yy]] and self.m.t[xx, yy] not in PK.ids():
                            self.m.t[xx, yy] = T.ID["rubble_earth"]
                for xx in range(x - 1, x + w + 1):
                    if T.WALK[self.m.t[xx, dy0 + h]] and self.m.t[xx, dy0 + h] not in PK.ids():
                        self.m.t[xx, dy0 + h] = T.ID["rubble_earth"]
            elif r.random() < 0.5:
                for xx in range(x, x + w, 2):
                    if T.WALK[self.m.t[xx, dy0 + h]] and self.m.t[xx, dy0 + h] not in PK.ids():
                        self.m.t[xx, dy0 + h] = T.ID["camo_net"]
            x += w + r.randint(3, 5)
        for _ in range(12):
            x, y = x0 + r.randint(2, sw - 3), y0 + sh - r.randint(1, 3)
            if 0 < y < self.h - 1 and self.get(x, y) in (self.key("ground"), "dirt"):
                self.m.t[x, y] = T.ID["fuel_drums" if r.random() < 0.6 else "ammo_stack"]
        for gx, gy in ((x0 + 4, y0 + sh - 4), (x0 + sw - 5, y0 + sh - 4)):
            self._gun_pit(gx, gy)
            rec["spots"].append(("aagun", gx, gy))

    def _inst_fortress(self, rec, x0, y0, sw, sh):
        """A strongpoint complex: casemates, bunkers, trenches, obstacles."""
        r = self.rng
        att = self.att or "N"
        horiz = att in ("N", "S")
        front = {"N": y0, "S": y0 + sh - 1, "W": x0, "E": x0 + sw - 1}[att]
        # dragon's teeth / AT ditch line in front
        for k in range(sw if horiz else sh):
            x, y = (x0 + k, front) if horiz else (front, y0 + k)
            if k % 9 not in (4,) and 0 < x < self.w - 1 and 0 < y < self.h - 1:
                self.m.t[x, y] = T.ID["teeth" if r.random() < 0.7 else "hedgehog"]
        fx, fy = {"N": (0, 1), "S": (0, -1), "W": (1, 0), "E": (-1, 0)}[att]  # into the fortress
        # wire belt and mines just inside the teeth
        for k in range(sw if horiz else sh):
            bx, by = (x0 + k, front) if horiz else (front, y0 + k)
            for d in (2, 3):
                x, y = bx + fx * d, by + fy * d
                if 0 < x < self.w - 1 and 0 < y < self.h - 1 and r.random() < 0.85:
                    self.m.t[x, y] = T.ID["wire"]
            for d in range(4, 8):
                x, y = bx + fx * d, by + fy * d
                if 0 < x < self.w - 1 and 0 < y < self.h - 1 and r.random() < 0.12:
                    self.add_mine(x, y, "smine" if r.random() < 0.4 else "ap")
        # casemates (AT guns) and MG bunkers along a line
        nb = r.randint(3, 5)
        bunkers = []
        for i in range(nb):
            lat = (i + 0.5) / nb
            if horiz:
                bx, by = x0 + int(lat * sw) - 3, (y0 + 10 if att == "N" else y0 + sh - 16)
            else:
                bx, by = (x0 + 10 if att == "W" else x0 + sw - 16), y0 + int(lat * sh) - 3
            bwid, bhgt = (7, 6) if horiz else (6, 7)
            b = self.building(bx, by, bwid, bhgt, "bunker")
            self.protected[x0:x0 + sw, y0:y0 + sh] = False
            if b:
                bunkers.append(b)
                cx, cy = bx + bwid // 2, by + bhgt // 2
                label = f"casemate {r.choice(['WN', 'Stp', 'Wn'])}-{r.randint(1, 99)}"
                kind = "casemate" if i % 2 == 0 else "bunker"
                self.positions.append(dict(kind="bunker", x=cx, y=cy, rect=b, name=label))
                if kind == "casemate":
                    # the gun sits just behind the embrasure
                    gx, gy = cx - fx * 1, cy - fy * 1
                    rec["spots"].append(("atgun", gx, gy))
        # connecting trench behind the bunkers
        if len(bunkers) >= 2:
            tr = T.ID[self.key("trench")]
            for a, b in zip(bunkers, bunkers[1:]):
                p = (a[0] + a[2] // 2 + fx * (a[3] // 2 + 2), a[1] + a[3] // 2 + fy * (a[3] // 2 + 2))
                q = (b[0] + b[2] // 2 + fx * (b[3] // 2 + 2), b[1] + b[3] // 2 + fy * (b[3] // 2 + 2))
                for pt in tcod.los.bresenham(p, q):
                    x, y = int(pt[0]), int(pt[1])
                    if 0 < x < self.w - 1 and 0 < y < self.h - 1 and T.WALK[self.m.t[x, y]]:
                        self.m.t[x, y] = tr
            self.positions.append(dict(kind="trench", x=(p[0] + q[0]) // 2, y=(p[1] + q[1]) // 2))
        # command bunker at the rear
        rx, ry = (x0 + sw // 2 - 4, y0 + sh - 9) if att == "N" else \
                 (x0 + sw // 2 - 4, y0 + 2) if att == "S" else \
                 (x0 + sw - 11, y0 + sh // 2 - 3) if att == "W" else (x0 + 2, y0 + sh // 2 - 3)
        self.building(rx, ry, 9, 7, "bunker")
        self.protected[x0:x0 + sw, y0:y0 + sh] = False
        self.m.t[min(self.w - 2, rx + 9), max(1, ry - 1)] = T.ID["antenna"]
        rec["spots"].append(("guards", rx + 4, ry + 3))
        for _ in range(4):
            self._mg_nest_at(x0 + r.randint(4, sw - 5), y0 + r.randint(4, sh - 5))

    # ---------------------------------------------------------------- objectives
    def _fill_out(self, b):
        """A bigger battlefield is more of the same country: outlying farms and hamlets, orchards,
        copses - not the standard one's features spread thin."""
        k = self.k
        if k < 1.3 or b in ("town", "city_ruins", "factory", "abbey", "sea", "volcanic", "desert"):
            return
        r = self.rng
        cl = self.m.climate
        if self.spec.get("east") or b == "steppe":
            styles = ("izba", "barn", "shed")
        elif cl == "tropical" or b == "jungle":
            styles = ("hut",)
        elif cl == "desert":
            styles = ("desert_house",)
        else:
            styles = ("farmhouse", "barn", "shed")
        for _ in range(int((k - 1) * 2.2 + r.random())):
            for _try in range(12):
                x, y = r.randint(20, self.w - 20), r.randint(16, self.h - 16)
                if self.area_free(x - 10, y - 8, x + 10, y + 8) and not self.protected[x, y]:
                    break
            else:
                continue
            self.village(x, y, n=r.randint(1, 4), styles=styles, church=False, spread=9)
            if r.random() < 0.5:
                self.poi.append((r.choice(("the farm", "the outlying farm", "the hamlet")), x, y, 8))
        if b in ("farmland", "bocage", "village", "hills") and cl not in ("winter", "desert"):
            for _ in range(int((k - 1) * 1.5 + r.random())):
                ox, oy = r.randint(10, self.w - 25), r.randint(10, self.h - 20)
                if self.area_free(ox, oy, ox + 14, oy + 10):
                    self.orchard(ox, oy, 14, 10)
        if b in ("steppe", "farmland", "hills", "marsh"):
            for _ in range(int(k - 1 + r.random())):
                x, y = r.randint(20, self.w - 20), r.randint(20, self.h - 20)
                self.poi.append((r.choice(("the copse", "the gully", "the rise", "the crossroads")), x, y, 8))

    def pick_objectives(self, n=None):
        n = n or self.rng.randint(3, 4) + (1 if self.k >= 1.8 else 0) + (1 if self.k >= 3.5 else 0)
        poi = list(self.poi)
        self.rng.shuffle(poi)
        chosen: list[Objective] = []
        if self.att:
            # the fight is for the middle and the defender's ground, not the attacker's own rear
            poi = [p for p in poi if self.depth_coord(p[1], p[2]) >= 0.3] or poi
        attacker_side = None
        if self.spec.get("defender_side"):
            attacker_side = "allies" if self.spec["defender_side"] == "axis" else "axis"
        own_rear = {r["name"] for r in self.positions if r.get("side") == attacker_side and r.get("spots") is not None}
        poi = [p for p in poi if p[0] not in own_rear] or poi

        def priority(p):
            name = p[0]
            pr = 0
            if any(k in name for k in ("battery", "depot", "command post", "flak", "airfield", "fortress",
                                       "church", "bunker", "casemate", "strongpoint", "bridge", "abbey",
                                       "hall", "foundry", "square", "windmill", "station", "château", "cemetery",
                                       "castle", "fort", "lighthouse", "radar", "elevator", "kolkhoz",
                                       "collective", "brickworks", "quarry", "slag", "plantation", "mission",
                                       "shrine", "pagoda", "marabout", "tomb", "oasis", "landing", "airstrip",
                                       "sawmill", "oil tanks", "tank farm", "water tower", "calvary", "tanks",
                                       "graveyard", "halt", "railway")):
                pr -= 1
            return (pr, -self.depth_coord(p[1], p[2]) * 0.5 + self.rng.random() * 0.6)

        # ensure spread
        for name, x, y, rad in sorted(poi, key=priority):
            if not (5 <= x < self.w - 5 and 5 <= y < self.h - 5):
                continue
            if any(abs(o.x - x) + abs(o.y - y) < 35 for o in chosen):
                continue
            if any(o.name == name for o in chosen):
                name = f"the {'north' if y < self.h / 2 else 'south'}{'west' if x < self.w / 2 else 'east'}ern {name[4:] if name.startswith('the ') else name}"
            chosen.append(Objective(name, x, y, rad))
            if len(chosen) >= n:
                break
        # fill with generic points if needed
        while len(chosen) < (3 if self.k >= 1.8 else 2):
            d = self.rng.uniform(0.45, 0.8)
            x, y = self.point_at_depth(d, self.rng.uniform(0.2, 0.8))
            x, y = max(5, min(self.w - 6, x)), max(5, min(self.h - 6, y))
            chosen.append(Objective(self.rng.choice(["the treeline", "the high ground", "the hedgerow",
                                                     "the road junction"]), x, y, 8))
        self.m.objectives = chosen

    # ---------------------------------------------------------------- run
    def run(self) -> GameMap:
        b = self.m.biome
        spec = self.spec
        sea = spec.get("sea_edge")
        if sea and b != "sea":
            self.base_ground()
            self.beach(sea)
            inland = self.beach_inland
            # generate inland terrain in the remainder using the inland biome
            sub = spec.get("inland", "bocage")
            region = {"N": (0, inland + 2, self.w, self.h), "S": (0, 0, self.w, self.h - inland - 2),
                      "W": (inland + 2, 0, self.w, self.h), "E": (0, 0, self.w - inland - 2, self.h)}[sea]
            if sub == "bocage":
                self.fields(style="bocage", region=region, min_size=12, max_size=24)
            elif sub in ("volcanic",):
                pass
            else:
                self.fields(style="open", region=region)
            self.forests(amount=0.08)
            cx = (region[0] + region[2]) // 2 + self.rng.randint(-30, 30)
            cy = (region[1] + region[3]) // 2 + self.rng.randint(-10, 10)
            if sub not in ("volcanic", "jungle"):
                self.village(cx, cy, n=self.rng.randint(3, 7), styles=("farmhouse", "house", "barn"))
            if sub == "volcanic":
                self.scatter("spider_hole", 0.003, self.mask_where(["ash", "rock_ground"]))
                self.scatter("boulder", 0.006, self.mask_where(["ash"]))
            if sub == "jungle":
                self.forests(amount=0.35, tree="palm", tree2="tree")
        else:
            getattr(self, f"gen_{b}", self.gen_farmland)()
            self._fill_out(b)
        self.regional()                           # the country's own: vines, birches, dunes, reeds, cane
        if spec.get("river") and b not in ("sea",):
            orient = spec["river"]
            pos = spec.get("river_pos", self.rng.uniform(0.35, 0.65))
            self.river(orient, pos)
            self.bridge_over(orient, pos)
        from . import landmarks
        if b != "sea":
            landmarks.place(self)                 # windmills, stations, châteaux, cemeteries... (landmarks.py)
        self.defences(self.fort)
        landmarks.fortify(self)
        for kind, side in spec.get("installations", []):
            try:
                self.installation(kind, side)
            except (IndexError, ValueError):
                pass
        self.battle_damage(spec.get("intensity", 0.5))
        self.pick_objectives()
        from .relief import make as relief
        relief(self)                              # the lie of the land, with the named hills real hills
        self.dress_slopes()
        # clear edges so units can enter: first/last rows walkable where possible
        self._clear_spawn_edges()
        self.m.init_hp()
        self.m.refresh()
        self.m.gen_positions = self.positions
        return self.m

    # ---------------------------------------------------------------- the country's own
    def regional(self):
        """What makes this country look like itself: Italian vineyards and cypresses behind dry-stone walls,
        birch woods in Russia, spruce plantations in the Hürtgen, Norman apple orchards, dunes and wadis and
        camel thorn in the desert, reeds at the water's edge, sugar cane and mangroves in the Pacific."""
        m = self.m
        t = m.t
        clim = m.climate
        lang = self.spec.get("lang")
        east = self.spec.get("east")
        rnd = np.random.default_rng(self.seed + 501).random((self.w, self.h))
        free = ~self.protected

        def swap(src, dst, p, mask=None):
            if src not in T.ID:
                return
            sel = (t == T.ID[src]) & (rnd < p) & free
            if mask is not None:
                sel &= mask
            t[sel] = T.ID[dst]
        if clim == "mediterranean":
            patch = self.noise(0.03, octaves=2, salt=510) > 0.15
            for crop in ("wheat", "plowed"):
                swap(crop, "vineyard", 1.0, patch)
            swap("tree", "cypress", 0.3)
            swap("low_wall", "drystone", 1.0)
        if east and clim in ("summer", "autumn"):
            swap("tree", "birch", 0.45)
            swap("tree_autumn", "birch", 0.35)
        if clim == "autumn" and lang in ("de", "be", "nl"):
            swap("tree", "fir", 0.65)
            swap("tree_autumn", "fir", 0.55)
        if lang == "fr" and clim == "summer":
            near = np.zeros(t.shape, bool)
            for (x0, y0, bw, bh, _st) in m.buildings:
                near[max(0, x0 - 12):x0 + bw + 12, max(0, y0 - 12):y0 + bh + 12] = True
            swap("tree", "apple_tree", 0.7, near)
        if clim == "desert":
            ridges = np.abs(self.noise(0.035, octaves=2, salt=511)) < 0.05
            swap("sand", "dune", 1.0, ridges)
            swap("scrub", "camelthorn", 0.7)
            if self.rng.random() < 0.75:
                a, b = self.rng.choice([("N", "S"), ("E", "W"), ("N", "E"), ("W", "S")])
                self.road(self.edge_point(a), self.edge_point(b), width=2, key="wadi", meander=30, salt=512)
        wet = np.isin(t, [T.ID[k] for k in ("shallow", "marsh", "paddy") if k in T.ID])
        if wet.any():
            edge = np.zeros(t.shape, bool)
            edge[1:, :] |= wet[:-1, :]
            edge[:-1, :] |= wet[1:, :]
            edge[:, 1:] |= wet[:, :-1]
            edge[:, :-1] |= wet[:, 1:]
            edge &= ~wet
            for g in ("grass", "tall_grass", "grass_dry", "grass_autumn", "kunai", "mud"):
                swap(g, "reeds", 0.45, edge)
            if clim == "tropical":
                swap("tree", "mangrove", 0.8, edge)
                swap("palm", "mangrove", 0.4, edge)
        if clim == "tropical" and lang == "ja":
            patch = self.noise(0.03, octaves=2, salt=513) > 0.2
            for crop in ("kunai", "tall_grass", "paddy"):
                swap(crop, "sugarcane", 1.0, patch & (t != T.ID["paddy"]) if crop != "paddy" else patch & (rnd < 0.0))

    def dress_slopes(self):
        """After the heightmap: scree and bare rock on the steep hillsides; Okinawa's tombs on its slopes."""
        m = self.m
        e = m.__dict__.get("elev")
        if e is None:
            return
        t = m.t
        g = np.hypot(np.gradient(e, axis=0), np.gradient(e, axis=1))
        rnd = np.random.default_rng(self.seed + 520).random((self.w, self.h))
        free = ~self.protected
        ground = np.isin(t, [T.ID[k] for k in ("rock_ground", "grass_dry", "grass", "ash", "scrub", "tall_grass_dry")
                             if k in T.ID])
        if m.biome in ("mountain", "abbey", "hills", "volcanic") and m.climate != "tropical":
            t[ground & free & (g > 1.1) & (rnd < 0.55)] = T.ID["scree"]
            t[ground & free & (g > 1.4) & (rnd > 0.985)] = T.ID["outcrop"]
        if self.spec.get("lang") == "ja":
            cand = np.argwhere(ground & free & (g > 0.25) & (g < 1.2) & (rnd < 0.004))
            for x, y in cand[:14]:
                t[x, y] = T.ID["tomb"]
                if x + 1 < self.w and free[x + 1, y] and T.WALK[t[x + 1, y]]:
                    t[x + 1, y] = T.ID["tomb"]

    def _clear_spawn_edges(self):
        m = self.m
        for edge in ("N", "S", "E", "W"):
            for x, y in m.edge_tiles(edge, 2):
                d = m.tile(x, y)
                if not d.walk and d.key not in ("deep", "cliff") and not d.key.startswith("wall") \
                        and d.key not in ("embrasure", "window"):
                    m.t[x, y] = T.ID[self.key("ground")]


def generate(spec: dict) -> GameMap:
    return Gen(spec).run()
