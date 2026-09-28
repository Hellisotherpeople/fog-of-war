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

    def __setstate__(self, d):
        e = d.get("elev")
        if e is not None and e.dtype != np.float32:
            d["elev"] = e.astype(np.float32)      # (saved at half precision: a few centimetres)
        self.__dict__.update(d)

    def __getstate__(self):
        d = dict(self.__dict__)
        if d.get("elev") is not None:
            d["elev"] = d["elev"].astype(np.float16)
        d.pop("_los", None)                  # the line-of-sight caches: rebuilt as men look about
        d.pop("_los_hi", None)
        d.pop("_shade", None)
        d.pop("_slope", None)
        d.pop("_flat", None)
        d.pop("_bidx", None)
        return d

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
        """Bring the derived arrays up to date with the terrain.  Only the part that changed is recomputed:
        the tiles are compared with the last refresh's, and a shell hole costs a few dozen cells, not the
        whole battlefield.  `version` counts terrain changes, `walk_version` changes to where men can walk
        (what the Dijkstra maps care about), `see_version` changes to what blocks sight."""
        t = self.t
        prev = self.__dict__.get("_t_prev")
        if prev is not None and prev.shape == t.shape and "walk" in self.__dict__:
            diff = t != prev
            if not diff.any():
                self.update_see()
                return
            xs = np.nonzero(diff.any(axis=1))[0]
            ys = np.nonzero(diff.any(axis=0))[0]
            x0, x1, y0, y1 = int(xs[0]), int(xs[-1]) + 1, int(ys[0]), int(ys[-1]) + 1
            if (x1 - x0) * (y1 - y0) < t.size // 4:
                self._refresh_rect(x0, y0, x1, y1)
                prev[x0:x1, y0:y1] = t[x0:x1, y0:y1]
                self.version += 1
                return
        old_walk = self.__dict__.get("walk")
        self.walk = T.WALK[t]
        self.see_base = T.SEE[t]
        self.see_high_base = T.SEE_HIGH[t]
        self.cover = T.COVER[t]
        self.tall = T.TALL[t]
        self.pos_cover = T.POS_COVER[t]
        self.conceal = T.CONCEAL[t]
        self.water = T.WATER[t]
        self.flam = T.FLAM[t]
        cost = T.COST[t].copy()
        sm = self.slope_mult()
        if sm is not None:
            cost = (cost * sm).astype(cost.dtype)     # steep ground is slow going (relief.py)
        cost[~self.walk] = 0
        self.cost_foot = cost
        vcost = T.VCOST[t].copy()
        self.crush = T.CRUSH[t]
        self.vcost = vcost
        self.see_base_version = self.__dict__.get("see_base_version", 0) + 1
        self.update_see(force=True)
        self._compute_cover_dir()
        self.version += 1
        if old_walk is None or old_walk.shape != self.walk.shape or not np.array_equal(old_walk, self.walk):
            self.walk_version = self.__dict__.get("walk_version", 0) + 1
        self._t_prev = t.copy()

    def _refresh_rect(self, x0, y0, x1, y1):
        """The derived arrays for tiles [x0:x1, y0:y1] (the cover directions one tile beyond)."""
        sl = (slice(x0, x1), slice(y0, y1))
        t = self.t[sl]
        walk = T.WALK[t]
        if not np.array_equal(walk, self.walk[sl]):
            self.walk_version = self.__dict__.get("walk_version", 0) + 1
        self.walk[sl] = walk
        see_base = T.SEE[t]
        see_changed = not np.array_equal(see_base, self.see_base[sl])
        self.see_base[sl] = see_base
        hb = self.high_base()
        high = T.SEE_HIGH[t]
        see_changed = see_changed or not np.array_equal(high, hb[sl])
        hb[sl] = high
        self.cover[sl] = T.COVER[t]
        self.tall[sl] = T.TALL[t]
        self.pos_cover[sl] = T.POS_COVER[t]
        self.conceal[sl] = T.CONCEAL[t]
        self.water[sl] = T.WATER[t]
        self.flam[sl] = T.FLAM[t]
        cost = T.COST[t].copy()
        sm = self.slope_mult()
        if sm is not None:
            cost = (cost * sm[sl]).astype(cost.dtype)
        cost[~walk] = 0
        self.cost_foot[sl] = cost
        self.vcost[sl] = T.VCOST[t]
        self.crush[sl] = T.CRUSH[t]
        self.see[sl] = see_base & (self.smoke[sl] < 1.5)
        if "see_high" in self.__dict__:
            self.see_high[sl] = high & (self.smoke[sl] < 1.5)
        if see_changed:
            self.see_version = self.__dict__.get("see_version", 0) + 1
            self.see_base_version = self.__dict__.get("see_base_version", 0) + 1
        # cover directions depend on the neighbours: redo a one-tile border
        cx0, cy0, cx1, cy1 = max(0, x0 - 1), max(0, y0 - 1), min(self.w, x1 + 1), min(self.h, y1 + 1)
        self.cover_dir[:, cx0:cx1, cy0:cy1] = self._cover_dir_window(cx0, cy0, cx1, cy1)

    def refresh_at(self, x: int, y: int):
        self.refresh()

    def update_see(self, force=False):
        """Smoke and terrain together block sight.  Counts a change only when something actually changed."""
        thick = self.smoke >= 1.5
        if thick.any():
            xs = np.nonzero(thick.any(axis=1))[0]
            ys = np.nonzero(thick.any(axis=0))[0]
            self.smoke_box = (int(xs[0]), int(ys[0]), int(xs[-1]), int(ys[-1]))
        else:
            self.smoke_box = None
        new = self.see_base & ~thick
        old = self.__dict__.get("see")
        if force or old is None or old.shape != new.shape or not np.array_equal(old, new):
            self.see_version = self.__dict__.get("see_version", 0) + 1
        self.see = new
        self.see_high = self.high_base() & ~thick

    def slope_mult(self):
        """The steepness multiple on the cost of crossing each tile, or None on flat ground (made once)."""
        e = self.__dict__.get("elev")
        if e is None:
            return None
        c = self.__dict__.get("_slope")
        if c is None or c[0] is not e:
            from .relief import flat, slope_mult
            c = self.__dict__["_slope"] = (e, None if flat(self) else slope_mult(self))
        return c[1]

    def high_base(self):
        """Sight for a man sitting high, before smoke (maps saved before there was one: worked out now)."""
        hb = self.__dict__.get("see_high_base")
        if hb is None or hb.shape != self.t.shape:
            hb = self.see_high_base = T.SEE_HIGH[self.t]
        return hb

    def high(self):
        sh = self.__dict__.get("see_high")
        if sh is None or sh.shape != self.t.shape:
            sh = self.see_high = self.high_base() & (self.smoke < 1.5)
        return sh

    def _compute_cover_dir(self):
        """cover_dir[o, x, y] = protection at (x,y) from a threat in octant o."""
        self.cover_dir = self._cover_dir_window(0, 0, self.w, self.h)

    def _cover_dir_window(self, x0, y0, x1, y1):
        """cover_dir for the tiles [x0:x1, y0:y1]: each tile's protection is the cover of its neighbour
        toward the threat (or 0.6 of the neighbours either side of it)."""
        w, h = x1 - x0, y1 - y0
        # the window plus a one-tile border (zero beyond the map's edge)
        padded = np.zeros((w + 2, h + 2), np.float32)
        px0, py0 = max(0, x0 - 1), max(0, y0 - 1)
        px1, py1 = min(self.w, x1 + 1), min(self.h, y1 + 1)
        padded[px0 - (x0 - 1):px1 - (x0 - 1), py0 - (y0 - 1):py1 - (y0 - 1)] = self.cover[px0:px1, py0:py1]
        out = np.empty((8, w, h), np.float32)
        neigh = [padded[1 + dx:1 + dx + w, 1 + dy:1 + dy + h] for dx, dy in OCTANT_VEC]
        for o in range(8):
            out[o] = np.maximum(neigh[o], np.maximum(neigh[(o + 1) % 8], neigh[(o - 1) % 8]) * 0.6)
        return out

    # ------------------------------------------------------------ buildings and their floors
    def building_at(self, x: int, y: int):
        """The building a tile is inside (its rect and how many storeys), or None."""
        idx = self.__dict__.get("_bidx")
        if idx is None or idx[0] != len(self.buildings):
            arr = np.full((self.w, self.h), -1, np.int32)
            for k, b in enumerate(self.buildings):
                x0, y0, bw, bh = b[:4]
                arr[max(0, x0):x0 + bw, max(0, y0):y0 + bh] = k
            idx = self.__dict__["_bidx"] = (len(self.buildings), arr)
        k = int(idx[1][x, y]) if self.in_bounds(x, y) else -1
        if k < 0:
            return None
        b = self.buildings[k]
        rect = tuple(b[:4])
        return rect, (self.__dict__.get("storeys") or {}).get(rect, 1)

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

    def memory(self):
        """The ground as you last saw it: out of sight, a remembered tile is what it was then, not what the
        shells have made of it since (senses.player_fov keeps it up to date where you can see)."""
        mm = self.__dict__.get("mem")
        if mm is None or mm.shape != self.t.shape:
            mm = self.mem = self.t.copy()
        return mm

    def seen_t(self, xs, ys):
        """The tiles of a window as you know them: live where you can see, remembered elsewhere."""
        mm = self.__dict__.get("mem")
        t = self.t[xs, ys]
        if mm is None or mm.shape != self.t.shape:
            return t
        return np.where(self.visible[xs, ys], t, mm[xs, ys])

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
