"""Vision, light and hearing."""
from __future__ import annotations

import math

import numpy as np
import tcod

from . import tiles as T
from .constants import COMPASS

DAY_RANGE = 62
NIGHT_RANGE = 7
WEATHER_VIS = {"clear": 1.0, "overcast": 0.92, "rain": 0.7, "snow": 0.6, "fog": 0.28,
               "sandstorm": 0.25}
WEATHER_SOUND = {"clear": 0, "overcast": 0, "rain": 6, "snow": 3, "fog": -2, "sandstorm": 10}


def daylight(game) -> float:
    """0 (night) .. 1 (full day) from the clock."""
    cache = getattr(game, "_daylight_cache", None)
    if cache is not None and cache[0] == game.clock:
        return cache[1]
    v = _daylight(game)
    game._daylight_cache = (game.clock, v)
    return v


def _daylight(game) -> float:
    h = game.hour_float()
    # rough mid-latitude summer/winter adjustment
    winter = game.month() in (11, 12, 1, 2)
    rise, set_ = (7.8, 16.6) if winter else (5.2, 21.3)
    if rise + 1 <= h <= set_ - 1:
        return 1.0
    if h < rise - 0.5 or h > set_ + 0.5:
        return 0.0
    if h < rise + 1:
        return max(0.0, (h - (rise - 0.5)) / 1.5)
    return max(0.0, ((set_ + 0.5) - h) / 1.5)


def base_view_range(game) -> float:
    d = daylight(game)
    r = NIGHT_RANGE + (DAY_RANGE - NIGHT_RANGE) * d
    r *= WEATHER_VIS.get(game.weather, 1.0)
    return max(4.0, r)


def viewer_range(game, viewer) -> float:
    r = game.view_range_cache
    if getattr(viewer, "vt", None) is not None:
        # vehicles: buttoned-up crews see less, and a short-handed crew sees less still
        r *= 0.8 if viewer.buttoned else 1.0
        if viewer.crew < viewer.vt.crew:
            r *= 0.85
        return r
    if not viewer.body.conscious:
        return 0
    if viewer.suppression > 40:
        r *= 1 - (viewer.suppression - 40) / 150
    if viewer.stance == 2:
        r *= 0.9
    if viewer.role in ("officer", "sniper", "squad_leader") and viewer.find(lambda i: i.t.tool == "binoculars"):
        r *= 1.25
    return r


def concealment_factor(game, viewer, target) -> float:
    """Multiplier on detection range for a target (1 = fully exposed)."""
    m = game.map
    if getattr(target, "vt", None) is not None:
        f = 1.0 - m.conceal[target.x, target.y] / 250.0
        if target.fired_turn >= game.turn - 3 or target.moved_turn >= game.turn - 1:
            f = 1.0
        return f
    c = m.conceal[target.x, target.y] / 100.0
    st = 2 if target.downed else target.stance
    c *= {0: 0.35, 1: 0.75, 2: 1.0}[st]
    f = 1.0 - c
    if st == 2:
        f *= 0.7
    elif st == 1:
        f *= 0.9
    from .stealth import camo_mult, fieldcraft
    f *= camo_mult(game, target)
    if target.moved_turn >= game.turn - 1:
        move = {"sneak": 0.05, "walk": 0.2, "run": 0.35, "sprint": 0.5}.get(target.ai.get("pace_now", "walk"), 0.2)
        f = min(1.0, f + move * (fieldcraft(target) if target.ai.get("pace_now") in ("sneak", "walk") else 1.0))
    if target.fired_turn >= game.turn - 2:
        # muzzle flash and noise give you away (a sniper with a flash hider less so)
        w = target.weapon
        quiet = w is not None and w.t.loud < 62
        f = max(f, 0.6 if quiet else 1.0)
    if "camouflaged" in target.traits:
        f *= 0.85
    return max(0.05, f)


def lit_at(game, x, y) -> bool:
    lit = game.lit
    return lit is not None and bool(lit[x, y])


def compute_light(game):
    """Light mask for night: flares, fires, burning vehicles, muzzle flashes."""
    m = game.map
    if daylight(game) > 0.6:
        game.lit = None
        return
    lit = np.zeros((m.w, m.h), bool)
    xs = np.arange(m.w)[:, None]
    ys = np.arange(m.h)[None, :]
    keep = []
    for L in m.lights:
        x, y, r, until = L
        if until < game.turn:
            continue
        keep.append(L)
        x0, x1 = max(0, x - r), min(m.w, x + r + 1)
        y0, y1 = max(0, y - r), min(m.h, y + r + 1)
        sub = (xs[x0:x1] - x) ** 2 + (ys[:, y0:y1] - y) ** 2 <= r * r
        lit[x0:x1, y0:y1] |= sub
    m.lights = keep
    # fires light their surroundings
    fx, fy = np.nonzero(m.fire > 0)
    for x, y in zip(fx[:200], fy[:200]):
        lit[max(0, x - 3):x + 4, max(0, y - 3):y + 4] = True
    game.lit = lit


def los_clear(game, x0, y0, x1, y1) -> bool:
    see = game.map.see
    pts = tcod.los.bresenham((x0, y0), (x1, y1))
    if len(pts) <= 2:
        return True
    inner = pts[1:-1]
    return bool(see[inner[:, 0], inner[:, 1]].all())


def can_detect(game, viewer, target, dist=None) -> bool:
    if dist is None:
        dist = math.hypot(target.x - viewer.x, target.y - viewer.y)
    r = viewer_range(game, viewer)
    if r <= 0:
        return False
    fr = r * concealment_factor(game, viewer, target)
    # at night: need light, closeness or a flash
    if game.is_dark:
        night_r = max(NIGHT_RANGE * WEATHER_VIS.get(game.weather, 1.0), 3)
        flashing = target.fired_turn >= game.turn - 1
        lit = lit_at(game, target.x, target.y)
        if dist > night_r and not flashing and not lit:
            return False
        if flashing:
            fr = max(fr, 45)
        if lit:
            fr = max(fr, DAY_RANGE * WEATHER_VIS.get(game.weather, 1.0) * 0.6 * concealment_factor(game, viewer, target))
    pk = peek_point(target)
    if dist > fr:
        if pk is None:
            return False
    elif dist <= 1.5 or los_clear(game, viewer.x, viewer.y, target.x, target.y):
        return True
    if pk is not None:
        # only a head and a shoulder round the corner: harder to spot
        pd = math.hypot(pk[0] - viewer.x, pk[1] - viewer.y)
        return pd <= fr * 0.55 and los_clear(game, viewer.x, viewer.y, pk[0], pk[1])
    return False


def peek_point(a):
    """Where a soldier leaning out of cover has his head, or None."""
    pk = getattr(a, "peek", None)
    if not pk or a.vehicle is not None or not a.alive or a.downed:
        return None
    return a.x + pk[0], a.y + pk[1]


def update_actor_vision(game, a):
    """Refresh what an AI soldier or vehicle can see."""
    if a.vis_turn == game.turn:
        return a.visible
    a.vis_turn = game.turn
    vis = []
    r = viewer_range(game, a)
    if r <= 0:
        a.visible = vis
        return vis
    if game.is_dark:
        r = max(r, 45)        # flashes and lit targets can be seen far off at night
    pos, ents = game.enemy_array(a.side)
    if len(ents) == 0:
        a.visible = vis
        return vis
    d = np.sqrt(((pos - np.array([a.x, a.y], np.float32)) ** 2).sum(axis=1))
    idx = np.nonzero(d <= r)[0]
    from .stealth import notice
    for k in idx[np.argsort(d[idx])][:40]:
        e = ents[k]
        dk = float(d[k])
        if can_detect(game, a, e, dk):
            # in plain sight, or not yet made out: seeing takes a moment (see stealth.py)
            fr = r * concealment_factor(game, a, e) if getattr(e, "vt", None) is None else r
            if not notice(game, a, e, dk, fr):
                continue
            vis.append(e)
            a.known[e.id] = (e.x, e.y, game.turn, e)
    a.visible = vis
    return vis


def player_fov(game):
    p = game.player
    m = game.map
    if p.vehicle is not None:
        ox, oy = p.vehicle.x, p.vehicle.y
    else:
        ox, oy = p.x, p.y
    r = int(max(game.view_range_cache, 8)) + 2
    if game.is_dark:
        r = max(r, 50)
    if not p.body.conscious:
        m.visible[:] = False
        return
    fov = tcod.map.compute_fov(m.see, (ox, oy), radius=r, light_walls=True,
                               algorithm=tcod.constants.FOV_SYMMETRIC_SHADOWCAST)
    pk = peek_point(p)
    if pk is not None and m.in_bounds(*pk):
        # leaning out: you see what the corner hid
        fov |= tcod.map.compute_fov(m.see, pk, radius=r, light_walls=True,
                                    algorithm=tcod.constants.FOV_SYMMETRIC_SHADOWCAST)
    if game.is_dark:
        nr = max(NIGHT_RANGE * WEATHER_VIS.get(game.weather, 1.0), 3)
        xs = np.arange(m.w)[:, None]
        ys = np.arange(m.h)[None, :]
        near = (xs - ox) ** 2 + (ys - oy) ** 2 <= nr * nr
        mask = near
        if game.lit is not None:
            mask = mask | game.lit
        fov &= mask
    m.visible[:] = fov
    m.explored |= fov


def player_can_see_actor(game, a) -> bool:
    p = game.player
    if a is p:
        return True
    if a.vehicle is not None:
        return False
    m = game.map
    if not m.visible[a.x, a.y]:
        return False
    if a.side == p.side:
        return True
    viewer = p.vehicle if p.vehicle is not None else p
    dist = math.hypot(a.x - viewer.x, a.y - viewer.y)
    if dist <= 2:
        return True
    r = game.view_range_cache
    if p.vehicle is None and p.suppression > 40:
        r *= 1 - (p.suppression - 40) / 150
    if game.player_binoculars:
        r *= 1.6
    fr = r * concealment_factor(game, p, a)
    if game.is_dark:
        if a.fired_turn >= game.turn - 1:
            fr = max(fr, 45)
        if lit_at(game, a.x, a.y):
            fr = max(fr, DAY_RANGE * WEATHER_VIS.get(game.weather, 1.0) * 0.6 * concealment_factor(game, p, a))
    return dist <= fr


# ====================================================================== hearing

def sound_at(game, sx, sy, loud, lx, ly) -> float:
    d = math.hypot(lx - sx, ly - sy)
    level = loud - 20 * math.log10(max(1.0, d)) - WEATHER_SOUND.get(game.weather, 0)
    if d > 3 and loud < 90:
        # walls between muffle the sound
        pts = tcod.los.bresenham((sx, sy), (lx, ly))[1:-1]
        if len(pts):
            att = T.SOUND[game.map.t[pts[:, 0], pts[:, 1]]].sum()
            level -= min(30, att * 0.5)
    return level


HEAR_THRESHOLD = 12


def direction_word(dx, dy) -> str:
    if dx == 0 and dy == 0:
        return "right here"
    ang = math.atan2(dy, dx)
    o = int(round(ang / (math.pi / 4))) % 8
    vec = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)][o]
    return COMPASS[vec]


def distance_word(d) -> str:
    if d < 6:
        return "very close"
    if d < 18:
        return "close by"
    if d < 45:
        return "nearby"
    if d < 110:
        return "in the distance"
    return "far off"


ONOMATOPOEIA = {
    "gunfire": "crack", "mg": "brrrt", "smg": "rat-tat", "explosion": "BOOM", "cannon": "BOOM",
    "mortar": "thunk", "rocket": "whoosh", "flamer": "WHOOSH", "ping": "ping", "click": "click",
    "glass": "tinkle", "melee": "!", "engine": "rumble", "ricochet": "clang", "footsteps": "...",
    "penetration": "CLANG", "scream": "AAH", "whistle": "fweee", "aircraft": "drone",
    "shell": "shriek", "shout": "!", "wire": "clink", "digging": "chk",
}
