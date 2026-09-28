"""The lie of the land: every sector has a real surface, and height matters.

A heightmap in metres (GameMap.elev) under every tile - gentle in Normandy's farmland, rolling on the
steppe and cut by balkas (the dry ravines men lived in at Kursk and Stalingrad), steep in the Italian
mountains and at Cassino, a volcanic cone on Iwo Jima, jungle ridges on Guadalcanal, near-flat in the
desert but for the long low ridges that decided Alamein.  Rivers run in their valleys; cliffs stand up.
The hills the staff named on their maps (Hill 112, Point 593, the Kurgan) are real hills.

What it does:
- sight: a crest hides what's behind it (dead ground, the reverse slope), from a man standing, a man in a
  turret, a man at an upper window, the same for everyone; a man higher up sees over hedges and crops
  that would hide the same field from a man at their level (viewshed, crest_clear);
- effort: going uphill costs time and breath (slope_mult, climb);
- what you can say about a spot: its height, if you've a map, or just above or below you (words).

The viewshed is the classic ring-by-ring sweep (XDraw): each cell's horizon comes from the two cells on
the ring inside it along the line from the eye - done in numba if it's installed, else in numpy.
"""
from __future__ import annotations

import math
import os

import numpy as np

EYE = {"standing": 1.6, "crouching": 1.1, "prone": 0.4}
BODY = {0: 1.7, 1: 1.1, 2: 0.45}            # a target's height by stance: standing, crouching, prone
FLOOR_H = 3.2                                # metres a storey

# (amplitude m, feature scale, small-scale roughness m)
PROFILE = {"farmland": (10, 0.010, 1.0), "farmland_light": (8, 0.010, 1.0), "bocage": (14, 0.012, 1.5),
           "village": (8, 0.010, 1.0), "town": (5, 0.010, 0.5), "city_ruins": (4, 0.010, 0.5),
           "factory": (3, 0.010, 0.3), "forest": (22, 0.012, 2.0), "steppe": (16, 0.008, 1.0),
           "desert": (5, 0.008, 0.8), "hills": (42, 0.012, 3.0), "mountain": (95, 0.011, 6.0),
           "abbey": (95, 0.011, 6.0), "marsh": (2, 0.010, 0.3), "jungle": (34, 0.014, 3.0),
           "volcanic": (24, 0.014, 2.5), "sea": (0, 0.01, 0.0), "beach": (10, 0.010, 1.0)}
HILL_NAMES = ("hill", "point", "ridge", "height", "kurgan", "mount", "col", "crest", "knoll", "peak")


# ============================================================================ making the land
def _blur(a, r):
    """A box blur of radius r (cumulative sums: fast, and good enough for hills)."""
    if r <= 0:
        return a
    k = 2 * r + 1
    p = np.pad(a, r, mode="edge").astype(np.float64)
    c = p.cumsum(0)
    c = np.vstack([c[k - 1:k], c[k:] - c[:-k]]) / k
    c = c.cumsum(1)
    c = np.hstack([c[:, k - 1:k], c[:, k:] - c[:, :-k]]) / k
    return c.astype(np.float32)


def make(gen):
    """The heightmap for a freshly generated sector (mapgen.Gen.run calls this at the end, when the rivers,
    the cliffs and the named hills are all known)."""
    from . import tiles as T
    m = gen.m
    w, h = m.w, m.h
    rng = gen.rng
    b = m.biome
    spec = gen.spec
    sea = spec.get("sea_edge")
    amp, scale, rough = PROFILE.get(spec.get("inland", b) if sea else b, PROFILE["farmland"])
    n1 = gen.noise(scale, octaves=3, salt=901)
    n2 = gen.noise(scale * 3, octaves=1, salt=902)
    elev = amp * 0.5 * (n1 + 1.0) + rough * 0.5 * n2        # (the small bumps gentle: fields, not moonscape)
    xs = np.arange(w, dtype=np.float32)[:, None]
    ys = np.arange(h, dtype=np.float32)[None, :]
    if b == "steppe" or (b in ("farmland", "farmland_light") and gen.m.climate in ("winter", "steppe")):
        # the balkas: dry, steep-sided ravines, the only cover on the open steppe
        ridge = np.abs(gen.noise(0.018, octaves=3, salt=903))
        elev -= 9.0 * np.clip(1.0 - ridge / 0.07, 0.0, 1.0) ** 1.5
    if b == "volcanic":
        # a cone at one end (Suribachi stands 169 m over Iwo Jima's southern tip)
        cx = rng.choice([w * 0.12, w * 0.88])
        cy = rng.uniform(h * 0.25, h * 0.75)
        d = np.hypot(xs - cx, ys - cy)
        elev += 85.0 * np.clip(1.0 - d / (0.55 * w), 0.0, 1.0) ** 1.7
    if b in ("mountain", "abbey"):
        cx, cy = w / 2 + rng.uniform(-w * 0.2, w * 0.2), h / 2 + rng.uniform(-h * 0.2, h * 0.2)
        if b == "abbey":
            cx, cy = w / 2, h / 2
        d = np.hypot(xs - cx, ys - cy)
        elev += 45.0 * np.exp(-(d / (0.35 * w)) ** 2)
    if b == "jungle":
        ridge = np.abs(gen.noise(0.02, octaves=2, salt=904))
        elev += 22.0 * np.clip(1.0 - ridge / 0.12, 0.0, 1.0)
    if b == "desert":
        # a long low ridge across the field (Ruweisat, Miteirya, Alam Halfa)
        a = rng.uniform(0, math.pi)
        c0 = rng.uniform(0.3, 0.7)
        dist = np.abs((xs - w * c0) * math.sin(a) - (ys - h * 0.5) * math.cos(a))
        elev += 14.0 * np.exp(-(dist / (0.07 * w)) ** 2)
    # the hills the maps named
    for o in getattr(m, "objectives", []) or []:
        if any(k in o.name.lower() for k in HILL_NAMES):
            d = np.hypot(xs - o.x, ys - o.y)
            elev += max(12.0, amp * 0.6) * np.exp(-(d / (0.12 * w)) ** 2)
    # rivers and lakes lie in their valleys; the cliffs stand up
    water = T.WATER[m.t] >= 1
    if water.any():
        valley = _blur(water.astype(np.float32), 10)
        elev -= 6.0 * np.clip(valley * 3.0, 0.0, 1.0)
        low = float(np.percentile(elev[water], 20)) if water.sum() > 4 else float(elev.min())
        elev[water] = np.minimum(elev[water], low)
    cliff = m.t == T.ID.get("cliff", -1)
    if cliff.any():
        elev += 7.0 * _blur(cliff.astype(np.float32), 1) * 1.5
    # a beach runs up from the sea
    if sea:
        d = {"N": ys + 0 * xs, "S": (h - 1 - ys) + 0 * xs, "W": xs + 0 * ys, "E": (w - 1 - xs) + 0 * ys}[sea]
        elev = np.minimum(elev, 0.25 * np.maximum(0.0, d - 6.0))
        elev[T.WATER[m.t] >= 2] = 0.0
    # the edges settle to a middle height, so the sector next door meets this one
    base = float(np.median(elev))
    taper = np.clip(np.minimum(np.minimum(xs, w - 1 - xs), np.minimum(ys, h - 1 - ys)) / 18.0, 0.0, 1.0)
    if not sea:
        elev = base + (elev - base) * taper
    elev -= float(elev.min())
    m.elev = elev.astype(np.float32)
    m.__dict__.pop("_shade", None)


def elevation(m):
    """The map's heightmap (a flat one for a map from before there was relief)."""
    e = m.__dict__.get("elev")
    if e is None or e.shape != m.t.shape:
        e = m.elev = np.zeros(m.t.shape, np.float32)
    return e


def flat(m) -> bool:
    e = m.__dict__.get("elev")
    if e is None:
        return True
    f = m.__dict__.get("_flat")
    if f is None or f[0] is not e:
        f = m.__dict__["_flat"] = (e, bool(e.max() - e.min() < 0.5))
    return f[1]


def slope_mult(m):
    """How much harder each tile is to cross for its steepness (for the Dijkstra maps: direction-blind)."""
    e = elevation(m)
    gx = np.abs(np.gradient(e, axis=0))
    gy = np.abs(np.gradient(e, axis=1))
    g = np.hypot(gx, gy)                       # metres of height per 2 m tile
    return (1.0 + np.clip(g, 0.0, 2.5) * 0.7).astype(np.float32)


def climb(m, x0, y0, x1, y1) -> float:
    """The time multiple for one step: uphill hard, downhill a little easier (until it's steep)."""
    e = m.__dict__.get("elev")
    if e is None:
        return 1.0
    dz = float(e[x1, y1] - e[x0, y0])
    if dz > 0:
        return 1.0 + min(2.0, dz * 0.6)
    return max(0.85, 1.0 + dz * 0.08) if dz > -1.2 else 1.0 + min(1.0, (-dz - 1.2) * 0.4)


# ============================================================================ seeing over it
def eye_height(a) -> float:
    """How high above the ground a man's eyes are: his stance, a vehicle, an upper floor or a tower."""
    if getattr(a, "vt", None) is not None:
        return 2.6
    if getattr(a, "vehicle", None) is not None:
        return 2.8
    z = getattr(a, "z", 0) or 0
    base = {0: 1.6, 1: 1.1, 2: 0.4}.get(getattr(a, "stance", 0), 1.6)
    if z > 0:
        return 1.6 + z * FLOOR_H
    return base


def body_height(a) -> float:
    if getattr(a, "vt", None) is not None:
        return 2.4
    z = getattr(a, "z", 0) or 0
    if z > 0:
        return 1.2 + z * FLOOR_H
    return BODY.get(getattr(a, "stance", 0), 1.7)


def crest_clear(m, pts, h0, h1) -> bool:
    """Along a line of tiles (Bresenham points, ends included): does the ground rise above the sight line?"""
    e = m.__dict__.get("elev")
    if e is None or len(pts) <= 2 or flat(m):
        return True
    z = e[pts[:, 0], pts[:, 1]]
    n = len(pts) - 1
    za = float(z[0]) + h0
    zb = float(z[-1]) + h1
    t = np.arange(1, n, dtype=np.float32) / n
    line = za + (zb - za) * t
    return bool((z[1:-1] <= line + 0.25).all())


def over_the_top(m, x0, y0, x1, y1, h0) -> bool:
    """A man well above the ground between him and what he's looking at sees over the crops and the hedges
    there (tiles.SEE_HIGH), as a man in a turret does."""
    e = m.__dict__.get("elev")
    if h0 >= 2.5:
        return True
    if e is None or flat(m):
        return False
    mx, my = (x0 + x1) // 2, (y0 + y1) // 2
    return float(e[x0, y0]) + h0 - float(e[mx, my]) >= 4.0


_vs = None


def _compile():
    global _vs
    if os.environ.get("FOW_NO_NUMBA"):
        _vs = False
        return
    try:
        import numba
    except Exception:
        _vs = False
        return

    @numba.njit(cache=True, nogil=True)
    def sweep(E, lx, ly, r, e0, tgt, vis):
        W, H = E.shape
        hz = np.full((W, H), -1e9, np.float32)
        vis[lx, ly] = True
        for k in range(1, r + 1):
            for side in range(4):
                for i in range(-k, k + 1):
                    if side == 0:
                        dx, dy = i, -k
                    elif side == 1:
                        dx, dy = i, k
                    elif side == 2:
                        if i == -k or i == k:
                            continue
                        dx, dy = -k, i
                    else:
                        if i == -k or i == k:
                            continue
                        dx, dy = k, i
                    x, y = lx + dx, ly + dy
                    if x < 0 or y < 0 or x >= W or y >= H:
                        continue
                    if k == 1:
                        href = -1e9
                    else:
                        f = (k - 1) / k
                        if side < 2:
                            rx = dx * f
                            ry = dy * f
                            fx = int(np.floor(rx))
                            wgt = rx - fx
                            yy = ly + int(round(ry))
                            a = hz[lx + fx, yy] if 0 <= lx + fx < W and 0 <= yy < H else -1e9
                            b = hz[lx + fx + 1, yy] if 0 <= lx + fx + 1 < W and 0 <= yy < H else -1e9
                        else:
                            rx = dx * f
                            ry = dy * f
                            fy = int(np.floor(ry))
                            wgt = ry - fy
                            xx = lx + int(round(rx))
                            a = hz[xx, ly + fy] if 0 <= xx < W and 0 <= ly + fy < H else -1e9
                            b = hz[xx, ly + fy + 1] if 0 <= xx < W and 0 <= ly + fy + 1 < H else -1e9
                        href = a * (1 - wgt) + b * wgt if a > -1e8 and b > -1e8 else max(a, b)
                    d = np.sqrt(dx * dx + dy * dy)
                    s_ground = (E[x, y] - e0) / d
                    s_tgt = (E[x, y] + tgt - e0) / d
                    vis[x, y] = s_tgt >= href
                    hz[x, y] = max(href, s_ground)
        return vis

    _vs = sweep


def viewshed(m, ox, oy, r, eye=1.6, tgt=1.2):
    """The ground that isn't hidden by the lie of the land from an eye at (ox, oy), within r: a boolean array
    the size of the map (True everywhere on a flat map)."""
    if flat(m):
        return None
    if _vs is None:
        _compile()
    e = elevation(m)
    w, h = e.shape
    x0, x1 = max(0, ox - r), min(w, ox + r + 1)
    y0, y1 = max(0, oy - r), min(h, oy + r + 1)
    E = np.ascontiguousarray(e[x0:x1, y0:y1])
    lx, ly = ox - x0, oy - y0
    e0 = float(E[lx, ly]) + eye
    vis = np.zeros(E.shape, np.bool_)
    if _vs:
        _vs(E, lx, ly, int(r), e0, float(tgt), vis)
    else:
        _sweep_numpy(E, lx, ly, int(r), e0, float(tgt), vis)
    out = np.ones((w, h), bool)
    out[x0:x1, y0:y1] = vis
    return out


def _sweep_numpy(E, lx, ly, r, e0, tgt, vis):
    """The same sweep, a ring at a time in numpy (no numba)."""
    W, H = E.shape
    hz = np.full((W, H), -1e9, np.float32)
    vis[lx, ly] = True
    for k in range(1, r + 1):
        i = np.arange(-k, k + 1)
        j = np.arange(-k + 1, k)
        dxs = np.concatenate([i, i, np.full(len(j), -k), np.full(len(j), k)])
        dys = np.concatenate([np.full(len(i), -k), np.full(len(i), k), j, j])
        horiz = np.concatenate([np.ones(2 * len(i), bool), np.zeros(2 * len(j), bool)])
        xs, ys = lx + dxs, ly + dys
        ok = (xs >= 0) & (ys >= 0) & (xs < W) & (ys < H)
        dxs, dys, xs, ys, horiz = dxs[ok], dys[ok], xs[ok], ys[ok], horiz[ok]
        if not len(xs):
            continue
        if k == 1:
            href = np.full(len(xs), -1e9, np.float32)
        else:
            f = (k - 1) / k
            rx, ry = dxs * f, dys * f
            # along the ring's long side the reference falls between two cells of the ring inside
            fa = np.where(horiz, np.floor(rx), np.floor(ry)).astype(np.int64)
            wgt = np.where(horiz, rx - fa, ry - fa)
            ax = np.where(horiz, lx + fa, lx + np.round(rx).astype(np.int64))
            ay = np.where(horiz, ly + np.round(ry).astype(np.int64), ly + fa)
            bx = np.where(horiz, ax + 1, ax)
            by = np.where(horiz, ay, ay + 1)

            def at(px, py):
                good = (px >= 0) & (py >= 0) & (px < W) & (py < H)
                v = np.full(len(px), -1e9, np.float32)
                v[good] = hz[px[good], py[good]]
                return v
            a, b = at(ax, ay), at(bx, by)
            both = (a > -1e8) & (b > -1e8)
            href = np.where(both, a * (1 - wgt) + b * wgt, np.maximum(a, b)).astype(np.float32)
        d = np.sqrt(dxs * dxs + dys * dys).astype(np.float32)
        ez = E[xs, ys]
        vis[xs, ys] = (ez + tgt - e0) / d >= href
        hz[xs, ys] = np.maximum(href, (ez - e0) / d)
    return vis


# ============================================================================ drawing and words
def shade(m):
    """A hillshade (light from the north-west) and contour lines, as a brightness multiple per tile
    (render.draw_map), made once per map."""
    c = m.__dict__.get("_shade")
    e = m.__dict__.get("elev")
    if c is not None and c[0] is e:
        return c[1]
    if e is None or flat(m):
        s = None
    else:
        gx = np.gradient(e, axis=0) / 2.0
        gy = np.gradient(e, axis=1) / 2.0
        # a surface normal lit from the north-west, 45 degrees up
        nz = 1.0 / np.sqrt(1 + gx * gx + gy * gy)
        lit = (nz * 0.707 + (-gx * -0.5 + -gy * -0.5) * nz * 0.707)
        s = 0.84 + 0.30 * np.clip(lit, 0, 1)
        # contours every 5 m: a faint line where the band changes
        band = np.floor(e / 5.0)
        edge = np.zeros(e.shape, bool)
        edge[:-1, :] |= band[:-1, :] != band[1:, :]
        edge[:, :-1] |= band[:, :-1] != band[:, 1:]
        s = np.where(edge, s * 0.88, s)
        # height itself, a touch: the tops are lighter than the valleys
        rng = float(e.max() - e.min()) or 1.0
        s = s * (0.94 + 0.10 * (e - e.min()) / rng)
        s = s.astype(np.float32)
    m.__dict__["_shade"] = (e, s)
    return s


def words(game, x, y) -> str:
    """How a spot stands: its height from the map if you carry one, else just up or down from you."""
    m = game.map
    e = m.__dict__.get("elev")
    if e is None or flat(m) or not m.in_bounds(x, y):
        return ""
    p = game.player
    here = float(e[p.x, p.y]) if m.in_bounds(p.x, p.y) else float(e[x, y])
    dz = float(e[x, y]) - here
    base = sector_alt(game)
    if p.has_tool("map"):
        return f"{int(round(base + float(e[x, y])))} m on the map" + (f", {abs(int(round(dz)))} m {'above' if dz > 0 else 'below'} you"
                                                                     if abs(dz) >= 2 else "")
    if abs(dz) < 2:
        return ""
    return f"{'up' if dz > 0 else 'down'} the slope from you" if abs(dz) < 8 else \
        f"well {'above' if dz > 0 else 'below'} you"


ALT = {"mountain": (380, 900), "abbey": (380, 520), "hills": (90, 320), "forest": (60, 450), "steppe": (140, 260),
       "desert": (15, 90), "marsh": (5, 140), "jungle": (10, 160), "volcanic": (0, 20), "city_ruins": (20, 150),
       "town": (20, 200), "factory": (20, 150), "bocage": (30, 140), "farmland": (20, 180), "village": (20, 200)}


def sector_alt(game) -> int:
    """The height above the sea of this sector's lowest ground: a property of the world (the same every time you
    come back), by the kind of country it is."""
    s = game.sector
    a = s.__dict__.get("alt")
    if a is None:
        import random
        lo, hi = ALT.get(getattr(game.map, "biome", "farmland"), (20, 180))
        if getattr(s, "sea_edge", None):
            lo, hi = 0, 8
        a = s.alt = random.Random(hash((s.x, s.y, game.theatre_id)) & 0xFFFFFF).randint(lo, hi)
    return a
