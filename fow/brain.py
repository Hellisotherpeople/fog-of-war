"""Side-level tactical knowledge expressed as Dijkstra maps.

Inspired by RogueBasin's "The Incredible Power of Dijkstra Maps": each side
keeps a handful of shared maps, and individual soldiers roll 'downhill' on a
weighted sum of them.  Different desires (reach the objective, stay out of
the enemy's field of fire, close with the enemy, keep at range, flee) are just
different weights.

  exposure[x,y]   how much danger a soldier lying at x,y is in from known enemies
                  (lines of fire, weapon type, directional cover, dug-in positions)
  safety          distance to the nearest reasonably safe tile, walking through
                  exposed ground is expensive
  threat_dist     distance to known enemies (approach / assault map)
  flee            threat_dist * -1.2 rescanned: flee intelligently, not into corners
  home            distance to our own map edge through covered ground (retreat)
  obj[i]          covered approach to objective i
  flank(...)      per squad: approach to tiles on the enemy's flank with a line of fire
"""
from __future__ import annotations

import math

import numpy as np
import tcod

from . import fastpath
from . import tiles as T
from .constants import BIG, OCTANT_VEC, other_side

THREAT_BY_KIND = {"inf": 1.0, "mg": 2.6, "hmg": 3.2, "sniper": 2.0, "tank": 3.5, "atgun": 2.2,
                  "vehicle": 1.6, "sound": 0.5, "bunker": 3.0, "mortar": 0.6, "officer": 1.0}
RANGE_BY_KIND = {"inf": 40, "mg": 65, "hmg": 75, "sniper": 90, "tank": 70, "atgun": 70,
                 "vehicle": 50, "sound": 30, "bunker": 70, "mortar": 40, "officer": 30}


class Contact:
    __slots__ = ("id", "x", "y", "turn", "kind", "threat", "ref", "sound")

    def __init__(self, id, x, y, turn, kind, ref=None, sound=False):
        self.id = id
        self.x = x
        self.y = y
        self.turn = turn
        self.kind = kind
        self.threat = THREAT_BY_KIND.get(kind, 1.0)
        self.ref = ref
        self.sound = sound


def contact_kind(e) -> str:
    if getattr(e, "vt", None) is not None:
        vt = e.vt
        if vt.vtype in ("tank", "td", "spg", "ltank", "tankette"):
            return "tank"
        if vt.vtype in ("atgun", "fieldgun", "aagun"):
            return "atgun"
        return "vehicle"
    w = e.weapon
    if w is not None and w.t.kind == "gun":
        c = w.t.cat
        if c == "hmg":
            return "hmg"
        if c == "lmg":
            return "mg"
        if c == "sniper":
            return "sniper"
        if c == "mortar":
            return "mortar"
    if e.role == "officer":
        return "officer"
    return "inf"


def dijkstra(goals: np.ndarray, cost: np.ndarray, goal_values=None) -> np.ndarray:
    dist = np.full(cost.shape, BIG, np.int32)
    if goal_values is None:
        dist[goals] = 0
    else:
        dist[goals] = goal_values[goals]
    fastpath.dijkstra2d(dist, cost.astype(np.int32, copy=False), 2, 3)
    return dist


def rescan(values: np.ndarray, cost: np.ndarray) -> np.ndarray:
    out = values.astype(np.int32).copy()
    fastpath.dijkstra2d(out, cost.astype(np.int32, copy=False), 2, 3)
    return out


class SideBrain:
    EVERY = 8           # turns between routine refreshes of the maps (sooner when a new enemy shows up)
    URGENT = 4          # ... but never more often than this
    MAP_TTL = 16        # objective and home maps last this long (the ground doesn't move)
    REDRAW = 10         # after the ground changes, redraw the maps no more often than this

    def __init__(self, game, side: str):
        self.game = game
        self.side = side
        self.contacts: dict[int, Contact] = {}
        self.exposure = None
        self._safety = None
        self._threat = None
        self._threat_goals = None
        self.urgent = False
        self._flee = None
        self._home = None
        self._home_ready = False
        self._rout = None
        self.exp_cost = None
        self.obj_maps: dict = {}
        self.veh_maps: dict = {}
        self.flank_cache: dict = {}
        self.local_cache: dict = {}
        self.last_update = -999
        self.version = -1
        self.cost = None
        self.home_edge = None
        self.enemy_center = None
        self.axis_vec = (0.0, -1.0)
        self.arty_cooldown = 0

    # ------------------------------------------------------------ knowledge
    def report(self, e, turn, sound=False, x=None, y=None):
        if sound:
            key = -abs(hash((x // 4, y // 4)))
            c = self.contacts.get(key)
            if c is None or c.turn < turn:
                self.contacts[key] = Contact(key, x, y, turn, "sound", None, True)
            return
        c = self.contacts.get(e.id)
        if c is None:
            self.contacts[e.id] = Contact(e.id, e.x, e.y, turn, contact_kind(e), e)
            self.urgent = True             # someone new: redraw the picture soon
        else:
            c.x, c.y, c.turn, c.ref = e.x, e.y, turn, e

    def live_contacts(self, max_age=45, sounds=True):
        g = self.game
        out = []
        for c in self.contacts.values():
            if g.player is not None and c.id == g.player.id and self.side == g.player.side and not g.renegade:
                continue  # a late report cannot reopen settled friendly hostility
            if not 0 <= g.turn - c.turn <= (15 if c.sound else max_age):
                continue
            if c.sound and not sounds:
                continue
            ref = c.ref
            if ref is not None:
                if getattr(ref, "vt", None) is not None:
                    if ref.dead or ref.abandoned:
                        continue
                elif not ref.alive or ref.state != "ok":
                    continue
            out.append(c)
        return out

    def forget(self):
        g = self.game
        dead = [k for k, c in self.contacts.items()
                if g.turn - c.turn > 90 or (c.ref is not None and (
                    (getattr(c.ref, "vt", None) is not None and c.ref.dead) or
                    (getattr(c.ref, "vt", None) is None and (not c.ref.alive or c.ref.state != "ok"))))]
        for k in dead:
            del self.contacts[k]

    # ------------------------------------------------------------ maps
    def base_cost(self) -> np.ndarray:
        m = self.game.map
        known = [(x, y) for (x, y), mn in m.mines.items() if self.side in mn.known]
        key = (id(m), m.version, len(known))
        cached = self.__dict__.get("_cost_cache")
        if cached is not None and cached[0] == key:
            return cached[1]
        c = np.maximum(1, T.COST[m.t] // 50).astype(np.int32)
        c[~m.walk] = 0
        c[m.water >= 2] = 14          # swimming is a last resort
        for x, y in known:
            c[x, y] = 40
        self._cost_cache = (key, c)
        return c

    def due(self, turn) -> bool:
        """Time for a refresh: routinely every EVERY turns, sooner when someone new has been seen."""
        since = turn - self.last_update
        return since >= self.EVERY or (self.__dict__.get("urgent") and since >= self.URGENT)

    def update(self, force=False):
        g = self.game
        m = g.map
        wv = (id(m), m.__dict__.get("walk_version", m.version))
        if not force and g.turn - self.last_update < self.URGENT and self.version == wv:
            return
        # only a change to where men can walk redraws the ground (a shell hole in a field doesn't) - and in a
        # battle walls fall and trees come down every few seconds, so the maps are redrawn at most every
        # REDRAW turns: a stale map for a moment costs a man a slightly worse route, not a wrong one
        changed = self.version != wv
        if changed:
            self.__dict__.setdefault("_walk_changed", g.turn)
        moved = False
        if self.__dict__.get("_walk_changed") is not None and (
                g.turn - self.__dict__.get("_last_redraw", -999) >= self.REDRAW or
                self.version is None or not isinstance(self.version, tuple) or self.version[0] != wv[0]):
            moved = True
            self._walk_changed = None
            self._last_redraw = g.turn
        self.last_update = g.turn
        self.version = wv
        self.urgent = False
        self.forget()
        self.cost = self.base_cost()
        contacts = self.live_contacts()
        self._compute_exposure(contacts)
        exp_cost = self.cost + np.minimum(40, (self.exposure * 5).astype(np.int32))
        exp_cost[self.cost == 0] = 0
        self.exp_cost = exp_cost
        # safety and the distance to the enemy: worked out when somebody first asks
        self._safety = None
        self._threat = None
        self._flee = None
        real = [c for c in contacts if not c.sound]
        use = real or contacts
        if use:
            self._threat_goals = [(c.x, c.y) for c in use if m.in_bounds(c.x, c.y)]
            xs = [c.x for c in use]
            ys = [c.y for c in use]
            self.enemy_center = (sum(xs) / len(xs), sum(ys) / len(ys))
        else:
            self._threat_goals = None
            self.enemy_center = None
        # home edge
        edge = g.home_edge(self.side)
        if edge != self.home_edge or moved or g.turn - self.__dict__.get("_home_turn", -999) > self.MAP_TTL:
            self._home = None
            self._home_ready = False
        self.home_edge = edge
        # a routing man's way out doesn't need redrawing every few seconds
        if moved or g.turn - self.__dict__.get("_rout_turn", -999) > self.MAP_TTL:
            self._rout = None
        # objective maps are recomputed lazily, and kept a while
        if moved:
            self.obj_maps = {}
        else:
            # the plain way to an objective only changes with the ground; the covered way (which keeps out of
            # the enemy's sight) goes stale as the enemy moves
            self.obj_maps = {k: v for k, v in self.obj_maps.items()
                             if isinstance(v, tuple) and (not k[1] or g.turn - v[0] <= self.MAP_TTL * 2)}
        self.flank_cache = {k: v for k, v in self.flank_cache.items() if v[0] > g.turn}
        if moved or wv[0] != getattr(self, "_veh_version", (None,))[0]:
            self.veh_maps = {}
            self._veh_version = wv
        self.local_cache = {}
        if self.arty_cooldown > 0:
            self.arty_cooldown -= 4

    # lazily computed maps (only the men who need them pay for them)
    @property
    def safety(self):
        if self.__dict__.get("_safety") is None and self.cost is not None and self.exposure is not None:
            safe = (self.cost > 0) & (self.exposure < 0.35)
            self._safety = dijkstra(safe, self.exp_cost) if safe.any() else \
                np.zeros(self.game.map.t.shape, np.int32)
        return self.__dict__.get("_safety")

    @safety.setter
    def safety(self, v):
        self._safety = v

    @property
    def threat_dist(self):
        if self.__dict__.get("_threat") is None and self.__dict__.get("_threat_goals") and self.cost is not None:
            goals = np.zeros(self.game.map.t.shape, bool)
            for x, y in self._threat_goals:
                goals[x, y] = True
            self._threat = dijkstra(goals, self.cost)
        return self.__dict__.get("_threat")

    @threat_dist.setter
    def threat_dist(self, v):
        self._threat = v

    @property
    def home(self):
        if not self._home_ready:
            self._home_ready = True
            self._home_turn = self.game.turn
            m = self.game.map
            if self.home_edge and self.cost is not None:
                self._home = dijkstra(m.edge_mask(self.home_edge, 1) & (self.cost > 0), self.exp_cost)
            else:
                self._home = None
        return self._home

    @property
    def flee(self):
        if self._flee is None and self.threat_dist is not None:
            td = self.threat_dist
            fl = np.where(td < BIG, (td * -1.2).astype(np.int32), BIG)
            self._flee = rescan(fl, self.cost)
        return self._flee

    def rout_map(self):
        """Home and flee blended, then rescanned so there are no dead spots."""
        if self._rout is not None:
            return self._rout
        h = self.home
        f = self.flee
        if h is None:
            return f
        base = h.astype(np.int64)
        if f is not None:
            base = np.where((h < BIG) & (f < BIG), h + (f * 0.6).astype(np.int64), h)
        base = np.clip(base, -BIG + 1, BIG).astype(np.int32)
        self._rout = rescan(base, self.cost)
        self._rout_turn = self.game.turn
        return self._rout

    def _compute_exposure(self, contacts):
        g = self.game
        m = g.map
        w, h = m.w, m.h
        exp = np.zeros((w, h), np.float32)
        # prioritise the most threatening, most recent contacts
        contacts = sorted(contacts, key=lambda c: (-(c.threat), g.turn - c.turn))[:26]
        for ci, c in enumerate(contacts):
            if not m.in_bounds(c.x, c.y):
                continue
            r = RANGE_BY_KIND.get(c.kind, 40)
            r = int(min(r, g.view_range_cache + 10))
            x0, x1 = max(0, c.x - r), min(w, c.x + r + 1)
            y0, y1 = max(0, c.y - r), min(h, c.y + r + 1)
            see = m.see[x0:x1, y0:y1]
            vis = tcod.map.compute_fov(see, (c.x - x0, c.y - y0), radius=r, light_walls=True,
                                       algorithm=tcod.constants.FOV_SYMMETRIC_SHADOWCAST)
            if ci < 10:                                     # (the ten most dangerous: it's a sweep each)
                from .relief import viewshed
                vs = viewshed(m, c.x, c.y, r, 1.6, 1.2)    # behind the crest, out of his sight
                if vs is not None:
                    vis &= vs[x0:x1, y0:y1]
            xs = np.arange(x0, x1)[:, None]
            ys = np.arange(y0, y1)[None, :]
            dx = c.x - xs
            dy = c.y - ys
            dist = np.sqrt(dx * dx + dy * dy)
            oct_idx = (np.round(np.arctan2(-dy, dx) / (math.pi / 4)).astype(np.int32)) % 8
            cov = np.take_along_axis(m.cover_dir[:, x0:x1, y0:y1], oct_idx[None], axis=0)[0]
            pos = m.pos_cover[x0:x1, y0:y1]
            prot = np.maximum(cov, pos) / 100.0
            conceal = m.conceal[x0:x1, y0:y1] / 100.0
            fall = np.clip(1.0 - dist / (r + 1), 0.0, 1.0) ** 0.7
            age = max(0.3, 1 - (g.turn - c.turn) / 60)
            e = vis * (1.0 - prot * 0.92) * (1.0 - conceal * 0.3) * fall * c.threat * age
            exp[x0:x1, y0:y1] += e
        self.exposure = exp

    def objective_map(self, idx: int, covered=True) -> np.ndarray:
        key = (idx, covered)
        mp = self.obj_maps.get(key)
        if isinstance(mp, tuple):
            return mp[1]
        m = self.game.map
        o = m.objectives[idx]
        goals = np.zeros(m.t.shape, bool)
        r = max(2, o.radius // 3)
        goals[max(0, o.x - r):o.x + r + 1, max(0, o.y - r):o.y + r + 1] = True
        goals &= self.cost > 0
        if not goals.any():
            goals[o.x, o.y] = True
        cost = self.exp_cost if covered else self.cost
        if covered and o.owner != self.side:
            cost = cost + self._open_ground(o)
        mp = dijkstra(goals, cost)
        self.obj_maps[key] = (self.game.turn, mp)
        return mp

    def _open_ground(self, o):
        """Going for ground the enemy holds, a man keeps off the open fields in front of it whether or not
        he's seen anyone there yet: along the hedge, the wall, the edge of the wood, the dead ground - the
        covered approach.  Open ground near the objective costs extra (nothing where men can't walk)."""
        m = self.game.map
        key = ("open", o.x, o.y, m.__dict__.get("walk_version", m.version))
        c = self.__dict__.get("_open_cache")
        if c is not None and c[0] == key:
            return c[1]
        xs = np.arange(m.w)[:, None] - o.x
        ys = np.arange(m.h)[None, :] - o.y
        near = np.clip(1.0 - np.sqrt(xs * xs + ys * ys) / 60.0, 0.0, 1.0)
        beside = m.cover_dir.max(axis=0)                  # (the best cover beside the tile, from any side)
        bare = (1.0 - m.conceal / 100.0) * (1.0 - np.maximum(m.pos_cover, beside) / 100.0)
        pen = np.rint(near * np.clip(bare, 0.0, 1.0) * 5).astype(np.int32)
        pen[self.cost == 0] = 0
        self._open_cache = (key, pen)
        return pen

    def point_map(self, x: int, y: int, covered=True, radius=1) -> np.ndarray:
        key = ("pt", x // 2, y // 2, covered, radius)
        mp = self.local_cache.get(key)
        if mp is not None:
            return mp
        m = self.game.map
        goals = np.zeros(m.t.shape, bool)
        goals[max(0, x - radius):x + radius + 1, max(0, y - radius):y + radius + 1] = True
        goals &= self.cost > 0
        if not goals.any():
            goals[max(0, min(m.w - 1, x)), max(0, min(m.h - 1, y))] = True
        mp = dijkstra(goals, self.exp_cost if covered else self.cost)
        self.local_cache[key] = mp
        return mp

    def flank_map(self, key, tx: int, ty: int, from_x: float, from_y: float, rmin=6, rmax=22):
        """Approach map to tiles with a line of fire on (tx,ty) from a flank.

        The frontal axis is from the target toward (from_x, from_y) - where our
        main body is.  Goal tiles sit 50-130 degrees off that axis.
        """
        g = self.game
        cached = self.flank_cache.get(key)
        if cached is not None:
            return cached[1]
        m = g.map
        w, h = m.w, m.h
        r = rmax
        x0, x1 = max(0, tx - r), min(w, tx + r + 1)
        y0, y1 = max(0, ty - r), min(h, ty + r + 1)
        vis = tcod.map.compute_fov(m.see[x0:x1, y0:y1], (tx - x0, ty - y0), radius=r,
                                   algorithm=tcod.constants.FOV_SYMMETRIC_SHADOWCAST)
        xs = np.arange(x0, x1)[:, None] - tx
        ys = np.arange(y0, y1)[None, :] - ty
        dist = np.sqrt(xs * xs + ys * ys)
        ax, ay = from_x - tx, from_y - ty
        al = math.hypot(ax, ay) or 1.0
        cosang = (xs * ax + ys * ay) / (dist * al + 1e-6)
        goal_local = vis & (dist >= rmin) & (dist <= rmax) & (cosang < 0.62) & (cosang > -0.6)
        goals = np.zeros((w, h), bool)
        goals[x0:x1, y0:y1] = goal_local
        goals &= self.cost > 0
        # avoid goals that are exposed to other enemies
        if self.exposure is not None:
            goals &= self.exposure < 2.5
        if not goals.any():
            return None
        mp = dijkstra(goals, self.exp_cost)
        self.flank_cache[key] = (g.turn + 12, mp)
        return mp

    def vehicle_cost(self, crush: int, wheeled: bool, wide: bool = False) -> np.ndarray:
        key = ("vc", crush, wheeled, wide)
        c = self.veh_maps.get(key)
        if c is not None:
            return c
        m = self.game.map
        t = m.t
        c = np.maximum(1, T.VCOST[t] // 50).astype(np.int32)
        ok = T.WALK[t] | (T.CRUSH[t] <= crush) & (T.CRUSH[t] > 0)
        ok &= T.WATER[t] < 2
        ok &= T.CRUSH[t] < 9
        ok &= ~T.FLOOR[t] | (crush >= 3)
        blocked_by_crush = (~T.WALK[t]) & (T.CRUSH[t] > crush)
        ok &= ~blocked_by_crush
        # crushing through things is slow
        c = c + np.where(~T.WALK[t] & ok, 6, 0)
        c = c + np.where(T.WATER[t] == 1, 6, 0)
        if wheeled:
            rough = T.VCOST[t] > 120
            c = c + np.where(rough, 4, 0)
            ok &= ~np.isin(t, [T.ID["jungle"], T.ID["bamboo"], T.ID["marsh"], T.ID["mud"],
                               T.ID["deep_snow"]])
        if wide:
            # a vehicle two tiles wide needs its pivot a tile clear of anything it can't cross
            e = ok.copy()
            e[1:, :] &= ok[:-1, :]
            e[:-1, :] &= ok[1:, :]
            e[:, 1:] &= ok[:, :-1]
            e[:, :-1] &= ok[:, 1:]
            e[0, :] = e[-1, :] = False
            e[:, 0] = e[:, -1] = False
            ok = e
        # known mines (a single tile each: the lanes between them stay open)
        for (x, y), mn in m.mines.items():
            if self.side in mn.known and mn.kind == "at":
                ok[x, y] = False
        c = np.where(ok, c, 0).astype(np.int32)
        self.veh_maps[key] = c
        return c

    def vehicle_map(self, tx, ty, crush, wheeled, radius=2, wide=False, exact=False) -> np.ndarray:
        key = ("vm_exact", tx, ty, crush, wheeled, wide, radius) if exact else \
              ("vm", tx // 3, ty // 3, crush, wheeled, wide, radius)
        mp = self.veh_maps.get(key)
        if mp is not None:
            return mp
        cost = self.vehicle_cost(crush, wheeled, wide)
        m = self.game.map
        # the map is shared by every destination in this 3x3 bucket: aim at the bucket's centre so the
        # goal area is within 3 tiles of all of them (vehicles count <= 3 as arrived)
        if not exact:
            tx = min(m.w - 1, (tx // 3) * 3 + 1)
            ty = min(m.h - 1, (ty // 3) * 3 + 1)
        goals = np.zeros(m.t.shape, bool)
        goals[max(0, tx - radius):tx + radius + 1, max(0, ty - radius):ty + radius + 1] = True
        goals &= cost > 0
        if not goals.any():
            if exact:
                return None  # a service route must reach the order's actual arrival area
            goals |= (cost > 0) & (np.abs(np.arange(m.w)[:, None] - tx) + np.abs(np.arange(m.h)[None, :] - ty) < 12)
            if not goals.any():
                return None
        mp = dijkstra(goals, cost)
        self.veh_maps[key] = mp
        return mp

    # ------------------------------------------------------------ queries
    def exposure_at(self, x, y) -> float:
        if self.exposure is None:
            return 0.0
        return float(self.exposure[x, y])

    def nearest_contacts(self, x, y, n=5, max_age=30, sounds=False):
        cs = self.live_contacts(max_age, sounds)
        cs.sort(key=lambda c: (c.x - x) ** 2 + (c.y - y) ** 2)
        return cs[:n]

    def clusters(self, radius=6, min_size=3, max_age=12):
        """Groups of enemy contacts, for artillery and air targeting."""
        cs = [c for c in self.live_contacts(max_age, False)]
        out = []
        used = set()
        for c in cs:
            if c.id in used:
                continue
            group = [d for d in cs if (d.x - c.x) ** 2 + (d.y - c.y) ** 2 <= radius * radius]
            weight = sum(d.threat for d in group)
            if len(group) >= min_size or any(d.kind in ("bunker", "atgun", "hmg", "tank") for d in group):
                cx = sum(d.x for d in group) / len(group)
                cy = sum(d.y for d in group) / len(group)
                out.append((weight, int(cx), int(cy), group))
                used.update(d.id for d in group)
        out.sort(key=lambda t: -t[0])
        return out


def neighbors(x, y):
    for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)):
        yield x + dx, y + dy, dx, dy
