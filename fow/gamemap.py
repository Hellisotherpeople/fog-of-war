"""The local battlefield: terrain layers, derived lookup arrays, items, mines, effects."""
from __future__ import annotations

import numpy as np

from . import tiles as T
from .constants import OCTANT_VEC


class Mine:
    __slots__ = ("kind", "side", "known")

    def __init__(self, kind: str, side: str):
        self.kind = kind          # "ap", "smine", "at"
        self.side = side
        self.known = set()        # sides that know about it


class Objective:
    def __init__(self, name: str, x: int, y: int, radius: int = 6, kind: str = "point"):
        self.name = name
        self.x = x
        self.y = y
        self.radius = radius
        self.kind = kind
        self.owner = None         # side currently controlling it
        self.hold_time = 0        # consecutive turns held uncontested by the owner
        self.contested = False
        self.value = 1

    @property
    def pos(self):
        return (self.x, self.y)


class GameMap:
    def __init__(self, w: int, h: int, seed: int = 0):
        self.w = w
        self.h = h
        rng = np.random.default_rng(seed)
        self.t = np.full((w, h), T.ID["grass"], np.int32)
        self.hp = np.zeros((w, h), np.int32)
        self.var = rng.integers(0, 256, (w, h), dtype=np.int32)
        self.fire = np.zeros((w, h), np.int16)
        self.smoke = np.zeros((w, h), np.float32)
        self.blood = np.zeros((w, h), np.uint8)
        self.scorch = np.zeros((w, h), np.uint8)
        self.explored = np.zeros((w, h), bool)
        self.visible = np.zeros((w, h), bool)
        self.remembered_glyph = None
        self.items: dict[tuple[int, int], list] = {}
        self.mines: dict[tuple[int, int], Mine] = {}
        self.objectives: list[Objective] = []
        self.labels: list[tuple[str, int, int]] = []
        self.lights: list[list] = []        # [x, y, radius, until_turn]
        self.version = 0
        self.biome = "farmland"
        self.climate = "summer"
        self.name = "Unnamed sector"
        self.edges = {}                      # side -> edge letter
        self.buildings: list[tuple[int, int, int, int]] = []
        self.refresh()

    # ------------------------------------------------------------ basics
    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h

    def tile(self, x: int, y: int) -> T.TileDef:
        return T.DEFS[int(self.t[x, y])]

    def set(self, x: int, y: int, key_or_id, refresh: bool = False):
        tid = T.ID[key_or_id] if isinstance(key_or_id, str) else int(key_or_id)
        self.t[x, y] = tid
        self.hp[x, y] = T.HP[tid]
        if refresh:
            self.refresh_at(x, y)

    def fill(self, x0, y0, x1, y1, key):
        tid = T.ID[key]
        x0, x1 = max(0, x0), min(self.w, x1)
        y0, y1 = max(0, y0), min(self.h, y1)
        self.t[x0:x1, y0:y1] = tid
        self.hp[x0:x1, y0:y1] = T.HP[tid]

    def init_hp(self):
        self.hp = T.HP[self.t].astype(np.int32)

    # ------------------------------------------------------------ derived arrays
    def refresh(self):
        t = self.t
        self.walk = T.WALK[t]
        self.see_base = T.SEE[t]
        self.cover = T.COVER[t]
        self.tall = T.TALL[t]
        self.pos_cover = T.POS_COVER[t]
        self.conceal = T.CONCEAL[t]
        self.water = T.WATER[t]
        self.flam = T.FLAM[t]
        cost = T.COST[t].copy()
        cost[~self.walk] = 0
        self.cost_foot = cost
        vcost = T.VCOST[t].copy()
        self.crush = T.CRUSH[t]
        self.vcost = vcost
        self.update_see()
        self._compute_cover_dir()
        self.version += 1

    def refresh_at(self, x: int, y: int):
        # cheap enough to recompute everything; keeps derived state consistent
        self.refresh()

    def update_see(self):
        self.see = self.see_base & (self.smoke < 1.5)

    def _compute_cover_dir(self):
        """cover_dir[o, x, y] = protection at (x,y) from a threat in octant o."""
        w, h = self.w, self.h
        # obstacles: non-walkable non-see tiles are full cover; others use their cover value
        cov = self.cover.astype(np.float32)
        padded = np.zeros((w + 2, h + 2), np.float32)
        padded[1:-1, 1:-1] = cov
        out = np.zeros((8, w, h), np.float32)
        neigh = []
        for dx, dy in OCTANT_VEC:
            neigh.append(padded[1 + dx:1 + dx + w, 1 + dy:1 + dy + h])
        for o in range(8):
            a = neigh[o]
            b = neigh[(o + 1) % 8] * 0.6
            c = neigh[(o - 1) % 8] * 0.6
            out[o] = np.maximum(a, np.maximum(b, c))
        self.cover_dir = out

    # ------------------------------------------------------------ queries
    def is_walkable(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h and bool(self.walk[x, y])

    def is_transparent(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h and bool(self.see[x, y])

    def items_at(self, x: int, y: int) -> list:
        return self.items.get((x, y), [])

    def add_item(self, x: int, y: int, item):
        if self.water[x, y] >= 2:
            return  # sinks
        self.items.setdefault((x, y), []).append(item)

    def remove_item(self, x: int, y: int, item):
        lst = self.items.get((x, y))
        if lst and item in lst:
            lst.remove(item)
            if not lst:
                del self.items[(x, y)]

    def cover_toward(self, x: int, y: int, tx: int, ty: int) -> float:
        """Protection (0-100) at x,y from a threat at tx,ty."""
        o = octant(tx - x, ty - y)
        if o < 0:
            return float(self.pos_cover[x, y])
        return float(max(self.cover_dir[o, x, y], self.pos_cover[x, y]))

    def edge_tiles(self, edge: str, depth: int = 1):
        w, h = self.w, self.h
        if edge == "N":
            return [(x, y) for x in range(w) for y in range(depth)]
        if edge == "S":
            return [(x, y) for x in range(w) for y in range(h - depth, h)]
        if edge == "W":
            return [(x, y) for x in range(depth) for y in range(h)]
        return [(x, y) for x in range(w - depth, w) for y in range(h)]

    def edge_mask(self, edge: str, depth: int = 1) -> np.ndarray:
        m = np.zeros((self.w, self.h), bool)
        if edge == "N":
            m[:, :depth] = True
        elif edge == "S":
            m[:, self.h - depth:] = True
        elif edge == "W":
            m[:depth, :] = True
        else:
            m[self.w - depth:, :] = True
        return m

    def describe(self, x: int, y: int) -> str:
        d = self.tile(x, y)
        s = d.name
        if self.fire[x, y] > 0:
            s = "burning " + s
        if self.smoke[x, y] > 1.5:
            s += ", in thick smoke"
        elif self.smoke[x, y] > 0.5:
            s += ", hazy with smoke"
        if self.blood[x, y] > 0:
            s += ", blood-spattered"
        return s


def octant(dx: int, dy: int) -> int:
    """Octant index matching OCTANT_VEC for a direction vector (screen coordinates)."""
    if dx == 0 and dy == 0:
        return -1
    import math
    ang = math.atan2(-dy, dx)  # screen y is down
    o = int(round(ang / (math.pi / 4))) % 8
    return o
