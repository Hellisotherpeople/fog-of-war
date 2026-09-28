"""Vision, light and hearing."""
from __future__ import annotations

import math

import numpy as np
import tcod

from . import tiles as T
from .constants import COMPASS
from . import fastpath as FP
from .entities import riding
from .floors import inside
from .floors import open_top as _open_top
from .relief import body_height, crest_clear, elevation, eye_height, flat, over_the_top
from .stealth import camo_mult, fieldcraft
from .stealth import notice as _notice

DAY_RANGE = 62
NIGHT_RANGE = 7
WEATHER_VIS = {"clear": 1.0, "overcast": 0.92, "rain": 0.7, "snow": 0.6, "fog": 0.28,
               "sandstorm": 0.25}
WEATHER_SOUND = {"clear": 0, "overcast": 0, "rain": 6, "snow": 3, "fog": -2, "sandstorm": 10}


def daylight(game) -> float:
    """0 (night) .. 1 (full day), from where the sun really was: this battle's latitude and longitude,
    the date, and the clock the battle's times are given in."""
    cache = getattr(game, "_daylight_cache", None)
    if cache is not None and cache[0] == game.clock:
        return cache[1]
    v = _daylight(game)
    game._daylight_cache = (game.clock, v)
    return v


def _where(game):
    th = getattr(game, "theatre", None) or {}
    sun = th.get("sun")
    if sun is None:
        from .data.theatres import THEATRES
        sun = THEATRES.get(th.get("id"), {}).get("sun") or (50.0, 10.0, 1)
    return sun


def _sky(game):
    """(sun elevation, moon elevation, moon illuminated fraction), degrees and 0..1."""
    lat, lon, tz = _where(game)
    n = game.now()
    doy = n.timetuple().tm_yday
    t = n.hour + n.minute / 60 + n.second / 3600
    decl = -23.44 * math.cos(2 * math.pi / 365 * (doy + 10))
    b = 2 * math.pi * (doy - 81) / 364
    eot = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)       # minutes
    solar = t + (4 * lon - 60 * tz + eot) / 60
    ha = 15 * (solar - 12)
    la, de = math.radians(lat), math.radians(decl)

    def elev(h, d):
        return math.degrees(math.asin(max(-1.0, min(1.0, math.sin(la) * math.sin(d) +
                                                     math.cos(la) * math.cos(d) * math.cos(math.radians(h))))))
    sun = elev(ha, de)
    # the moon: its age from a known new moon (6 Jan 2000, 18:14 GMT); it trails the sun by its age, and
    # stands opposite the sun's declination when it's full
    import datetime as _dt
    utc = n - _dt.timedelta(hours=tz)
    age = ((utc - _dt.datetime(2000, 1, 6, 18, 14)).total_seconds() / 86400.0) % 29.530589
    ph = 2 * math.pi * age / 29.530589
    moon = elev(ha - 360 * age / 29.530589, de * math.cos(ph))
    return sun, moon, (1 - math.cos(ph)) / 2


def _daylight(game) -> float:
    e = _sky(game)[0]
    if e >= 5:
        return 1.0
    if e >= 0:
        return 0.85 + 0.03 * e                       # the sun on the horizon: long shadows, but day
    if e >= -6:
        return 0.4 + 0.45 * (e + 6) / 6              # civil twilight: you can see to work
    if e >= -12:
        return 0.08 + 0.32 * (e + 12) / 6            # nautical twilight: shapes against the sky
    if e >= -18:
        return 0.08 * (e + 18) / 6
    return 0.0


MOON_RANGE = 16                   # tiles the full moon, high in a clear sky, adds to what you can make out
MOON_CLOUD = {"clear": 1.0, "overcast": 0.3, "rain": 0.15, "snow": 0.3, "fog": 0.5, "sandstorm": 0.2}


def moonlight(game) -> float:
    """0..1: how much the moon lights the ground (its phase, its height, the cloud)."""
    c = getattr(game, "_moon_cache", None)
    if c is not None and c[0] == game.clock // 60:
        return c[1]
    _sun, moon, frac = _sky(game)
    v = frac * max(0.0, min(1.0, math.sin(math.radians(moon)) * 3)) * MOON_CLOUD.get(game.weather, 1.0)
    game._moon_cache = (game.clock // 60, v)
    return v


def night_range(game) -> float:
    """How far you can make a man out in the dark, before the light comes."""
    return (NIGHT_RANGE + MOON_RANGE * moonlight(game)) * WEATHER_VIS.get(game.weather, 1.0)


def base_view_range(game) -> float:
    d = daylight(game)
    nr = NIGHT_RANGE + MOON_RANGE * moonlight(game)
    r = nr + (DAY_RANGE - nr) * d
    r *= WEATHER_VIS.get(game.weather, 1.0)
    return max(4.0, r)


def viewer_range(game, viewer) -> float:
    r = game.view_range_cache
    if getattr(viewer, "vt", None) is not None:
        return r * vehicle_eye(viewer)
    if not viewer.body.conscious:
        return 0
    if viewer.suppression > 40:
        r *= 1 - (viewer.suppression - 40) / 150
    if viewer.stance == 2:
        r *= 0.9
    if viewer.role in ("officer", "sniper", "squad_leader"):
        # the binoculars round his neck (looked for now and then, not every time he looks up)
        bk = viewer.__dict__.get("_binoc")
        if bk is None or game.turn - bk[0] > 60 or game.turn < bk[0]:
            bk = viewer._binoc = (game.turn, viewer.find(lambda i: i.t.tool == "binoculars") is not None)
        if bk[1]:
            r *= 1.25
    return r


def vehicle_eye(v) -> float:
    """How far a vehicle's crew sees, against a man on foot.  The commander with his head out of the hatch
    (and binoculars round his neck, standing eight feet up) sees furthest; buttoned up, it's periscopes
    and vision blocks, and worse if they're cracked; with no commander, only the gunner's sight and the
    driver's visor.  Open-topped vehicles, guns and lorries see like the men in them."""
    from .vdamage import hatch_user, optics_mult
    seat = hatch_user(v)
    if seat is None:
        return 1.0
    from .crew import manned
    if seat in manned(v) or (v.player_crewed and v.player_station == seat):
        return 1.15 if not v.buttoned else 0.65 * optics_mult(v)
    return 0.5 * optics_mult(v)


def player_eye(game):
    """Where you can look from where you sit: (all-round multiple, [(angle, half-width, multiple)...]).
    On foot it's all round.  In a tank it's your seat: the commander (head out, or through the cupola);
    the gunner, his sight - a narrow magnified cone where the gun points, and nothing else; the driver,
    his visor forward; the bow gunner, his ball-mount sight; the loader, one periscope; a passenger in a
    closed hull, the vision ports.  Riders, open-topped vehicles and lorries: you see as you would on foot."""
    p = game.player
    v = p.vehicle
    if v is None or riding(p):
        return 1.0, []
    from .vdamage import hatch_user, optics_mult
    hatch = hatch_user(v)
    if hatch is None:
        return 1.0, []
    if not v.player_crewed:
        return 0.3, []
    seat = v.player_station
    om = optics_mult(v)
    from .footprint import FACING_VEC
    turret = math.atan2(FACING_VEC[v.turret % 8][1], FACING_VEC[v.turret % 8][0])
    hull = math.atan2(FACING_VEC[v.facing % 8][1], FACING_VEC[v.facing % 8][0])
    cones = []
    if seat == "gunner" and v.vt.main:
        cones.append((turret, math.radians(20), 1.3 * om))
    if seat == hatch:
        return (1.15 if not v.buttoned else 0.65 * om), cones
    if seat == "gunner":
        return 0.25, cones
    if seat == "driver":
        return 0.25, [(hull, math.radians(50), 0.7 * om)]
    if seat.startswith("mg"):
        return 0.25, [(hull, math.radians(25), 0.6 * om)]
    if seat == "loader":
        return 0.35 * om, []
    return 0.3, []


def eye_mult_at(game, x, y) -> float:
    """The player's looking multiple toward one tile (see player_eye)."""
    base, cones = game.__dict__.get("_peye") or player_eye(game)
    if not cones:
        return base
    p = game.player
    ox, oy = (p.vehicle.x, p.vehicle.y) if p.vehicle is not None else (p.x, p.y)
    if (x, y) == (ox, oy):
        return max([base] + [c[2] for c in cones])
    a = math.atan2(y - oy, x - ox)
    best = base
    for ang, half, mult in cones:
        d = abs((a - ang + math.pi) % (2 * math.pi) - math.pi)
        if d <= half and mult > best:
            best = mult
    return best


def concealment_factor(game, viewer, target) -> float:
    """Multiplier on detection range for a target (1 = fully exposed).  It's the target's: where he is,
    how he's lying, whether he's moving or firing - so it's worked out once per target per moment,
    not once per man looking at him."""
    key = (game.turn, target.x, target.y, getattr(target, "stance", -1), getattr(target, "moved_turn", -1),
           getattr(target, "fired_turn", -1), id(game.map))
    cc = target.__dict__.get("_conceal") if hasattr(target, "__dict__") else None
    if cc is not None and cc[0] == key:
        return cc[1]
    f = _concealment(game, target)
    try:
        target._conceal = (key, f)
    except AttributeError:
        pass
    return f


def _concealment(game, target) -> float:
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


def _line_clear(see, x0, y0, x1, y1, m=None, h0=1.6, h1=1.6) -> bool:
    pts = tcod.los.bresenham((x0, y0), (x1, y1))
    if len(pts) <= 2:
        return True
    inner = pts[1:-1]
    if not bool(see[inner[:, 0], inner[:, 1]].all()):
        return False
    if m is not None:
        return crest_clear(m, pts, h0, h1)          # and no crest between (relief.py)
    return True


def los_clear(game, x0, y0, x1, y1, high=False, h0=1.6, h1=1.6) -> bool:
    """Can a line be drawn between two tiles without hitting anything opaque?  `high`: one end is up in a
    vehicle, and sees over crops and undergrowth (see tiles.SEE_HIGH).  h0, h1: how high the eye and the
    target are above their ground, against the lie of the land between them (relief.py).

    Most soldiers stand still most of the time, so the answer for the terrain is kept until the
    terrain changes; smoke is checked on top, and only where there is smoke."""
    m = game.map
    if abs(x1 - x0) <= 1 and abs(y1 - y0) <= 1:
        return True
    rel = not flat(m)
    if rel and not high:
        high = over_the_top(m, x0, y0, x1, y1, h0) or over_the_top(m, x1, y1, x0, y0, h1)
    mm = m if rel else None
    sb = m.__dict__.get("smoke_box")
    if sb is not None and not (max(x0, x1) < sb[0] or min(x0, x1) > sb[2] or max(y0, y1) < sb[1] or
                               min(y0, y1) > sb[3]):
        return _line_clear(m.high() if high else m.see, x0, y0, x1, y1, mm, h0, h1)   # through smoke: no shortcuts
    slot = "_los_hi" if high else "_los"
    cache = m.__dict__.get(slot)
    ver = m.__dict__.get("see_base_version", m.version)
    if cache is None or cache[0] != ver or len(cache[1]) > 250000:
        cache = (ver, {})
        m.__dict__[slot] = cache
    if (x0, y0) <= (x1, y1):
        key, ha, hb = (x0, y0, x1, y1), h0, h1
    else:
        key, ha, hb = (x1, y1, x0, y0), h1, h0
    if rel:
        key = key + (int(ha * 2), int(hb * 2))
    v = cache[1].get(key)
    if v is None:
        v = cache[1][key] = _line_clear(m.high_base() if high else m.see_base, key[0], key[1], key[2], key[3],
                                        mm, ha, hb)
    return v


def _high(e) -> bool:
    """Up in (or on) a vehicle: a man there sees over the corn, and is seen over it."""
    return getattr(e, "vt", None) is not None or getattr(e, "vehicle", None) is not None


def can_detect(game, viewer, target, dist=None, r=None, conceal=None) -> bool:
    if getattr(viewer, "z", 0) < 0 or getattr(target, "z", 0) < 0:
        return False                                  # nobody in a cellar sees out, or is seen from outside
    if dist is None:
        dist = math.hypot(target.x - viewer.x, target.y - viewer.y)
    if r is None:
        r = viewer_range(game, viewer)
    if r <= 0:
        return False
    if conceal is None:
        conceal = concealment_factor(game, viewer, target)
    fr = r * conceal
    # in the dark (the eye range r already knows how dark: twilight, moon, cloud): a flash or a light
    # shows a man further off than you could otherwise make him out
    if game.is_dark:
        if target.fired_turn >= game.turn - 1:
            fr = max(fr, 45)
        if lit_at(game, target.x, target.y):
            fr = max(fr, DAY_RANGE * WEATHER_VIS.get(game.weather, 1.0) * 0.6 * conceal)
    pk = peek_point(target)
    if dist > fr:
        if pk is None:
            return False
    elif dist <= 1.5 or _sight_line(game, viewer, target):
        return True
    if pk is not None:
        # only a head and a shoulder round the corner: harder to spot
        pd = math.hypot(pk[0] - viewer.x, pk[1] - viewer.y)
        return pd <= fr * 0.55 and los_clear(game, viewer.x, viewer.y, pk[0], pk[1])
    return False


def _sight_line(game, viewer, target) -> bool:
    """The line between two men, for seeing: the terrain, the crests, and - for a man up in an open belfry or
    on a roof - not the walls of his own building."""
    tops = [r for r in (_open_top(game, viewer), _open_top(game, target)) if r is not None]
    if not tops:
        return los_clear(game, viewer.x, viewer.y, target.x, target.y, _high(viewer) or _high(target),
                         eye_height(viewer), body_height(target))
    m = game.map
    pts = tcod.los.bresenham((viewer.x, viewer.y), (target.x, target.y))
    see = m.high()
    for x, y in pts[1:-1]:
        if not see[x, y] and not any(inside(r, x, y) for r in tops):
            return False
    return crest_clear(m, pts, eye_height(viewer), body_height(target))


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
    r_eye = r
    if game.is_dark:
        r = max(r, 45)        # flashes and lit targets can be seen far off at night
    pos, ents = game.enemy_array(a.side)
    if len(ents) == 0:
        a.visible = vis
        return vis
    row = _distance_row(game, a, pos)
    idx = np.nonzero(row <= r + 2.0)[0]           # (+2: men move during the turn; exact below)
    if len(idx) > 40:
        idx = idx[np.argsort(row[idx])][:40]
    elif len(idx) > 1:
        idx = idx[np.argsort(row[idx])]
    ax, ay = a.x, a.y
    if getattr(a, "z", 0) < 0:
        a.visible = vis                               # (down in the cellar)
        return vis
    m = game.map
    batch = FP.lines_ready() and _open_top(game, a) is None
    seen = []                                         # (e, distance, concealment), nearest first
    wait = []                                         # ... the ones whose line of sight is still to be drawn
    if batch:
        dark = game.is_dark
        turn = game.turn
        for k in idx:
            e = ents[k]
            dk = math.hypot(e.x - ax, e.y - ay)
            if dk > r or getattr(e, "z", 0) < 0:
                continue
            cf = concealment_factor(game, a, e)
            if peek_point(e) is not None or _open_top(game, e) is not None:
                if can_detect(game, a, e, dk, r=r_eye, conceal=cf):
                    seen.append((e, dk, cf, True))
                continue
            fr = r_eye * cf                           # (as can_detect has it)
            if dark:
                if e.fired_turn >= turn - 1:
                    fr = max(fr, 45)
                if lit_at(game, e.x, e.y):
                    fr = max(fr, DAY_RANGE * WEATHER_VIS.get(game.weather, 1.0) * 0.6 * cf)
            if dk > fr:
                continue
            item = (e, dk, cf, dk <= 1.5)
            seen.append(item)
            if dk > 1.5:
                wait.append(item)
        if wait:
            ok = FP.sight_lines(m.see, m.high(), elevation(m), not flat(m), ax, ay, eye_height(a), _high(a),
                             np.array([w[0].x for w in wait], np.int64), np.array([w[0].y for w in wait], np.int64),
                             np.array([body_height(w[0]) for w in wait], np.float64),
                             np.array([_high(w[0]) for w in wait], np.bool_))
            clear = {id(w[0]): bool(v) for w, v in zip(wait, ok)}
            seen = [s_ if s_[3] else (s_[0], s_[1], s_[2], clear.get(id(s_[0]), False)) for s_ in seen]
    else:
        # (without numba: one line at a time)
        seen = []
        for k in idx:
            e = ents[k]
            dk = math.hypot(e.x - ax, e.y - ay)
            if dk > r:
                continue
            cf = concealment_factor(game, a, e)
            seen.append((e, dk, cf, can_detect(game, a, e, dk, r=r_eye, conceal=cf)))
    for e, dk, cf, ok in seen:
        if not ok:
            continue
        # in plain sight, or not yet made out: seeing takes a moment (see stealth.py)
        fr = r * cf if getattr(e, "vt", None) is None else r
        if not _notice(game, a, e, dk, fr):
            continue
        vis.append(e)
        a.known[e.id] = (e.x, e.y, game.turn, e)
    a.visible = vis
    return vis


def _distance_row(game, a, pos):
    """This man's distances to every enemy: one matrix per side per turn, not a numpy sum per man."""
    key = (game.turn, id(pos), len(pos))
    slots = game.__dict__.setdefault("_vis_mat", {})
    c = slots.get(a.side)
    if c is None or c[0] != key:
        viewers = [v for v in game.actors if v.side == a.side and v.alive and v.vehicle is None] + \
            [v for v in game.vehicles if v.side == a.side and not v.dead]
        vp = np.array([(v.x, v.y) for v in viewers], np.float32).reshape(-1, 2)
        dm = np.sqrt(((vp[:, None, :] - pos[None, :, :]) ** 2).sum(axis=2)) if len(vp) else None
        c = (key, dm, {id(v): i for i, v in enumerate(viewers)})
        slots[a.side] = c
    i = c[2].get(id(a))
    if i is None:
        return np.sqrt(((pos - np.array([a.x, a.y], np.float32)) ** 2).sum(axis=1))
    return c[1][i]


def player_fov(game):
    p = game.player
    m = game.map
    if p.vehicle is not None:
        ox, oy = p.vehicle.x, p.vehicle.y
    else:
        ox, oy = p.x, p.y
    if not p.body.conscious:
        m.visible[:] = False
        return
    if getattr(p, "z", 0) < 0:
        m.visible[:] = False                          # in the cellar: a candle, the others, the thud of shells
        m.visible[ox, oy] = True
        return
    eye = player_eye(game)
    game._peye = eye
    base, cones = eye
    top = max([base] + [c[2] for c in cones])
    R = float(game.view_range_cache)                   # daylight, twilight, moon and weather are all in it
    lit_r = max(45.0, DAY_RANGE * WEATHER_VIS.get(game.weather, 1.0) * 0.6) if game.is_dark else 0.0
    r = int(max(R * top, 8, lit_r * top)) + 2
    from .relief import viewshed
    eye_h = eye_height(p)
    up = p.vehicle is not None or eye_h >= 2.5 or _on_a_rise(m, ox, oy)
    see = m.high() if up else m.see              # up in a vehicle, a window or on a rise you see over the corn
    from .floors import open_top
    top = open_top(game, p)
    if top is not None:
        see = see.copy()                          # up in the belfry, on the roof: all round, over the walls
        tx0, ty0, tbw, tbh = top
        see[tx0:tx0 + tbw, ty0:ty0 + tbh] = True
    fov = tcod.map.compute_fov(see, (ox, oy), radius=r, light_walls=True,
                               algorithm=tcod.constants.FOV_SYMMETRIC_SHADOWCAST)
    vs = viewshed(m, ox, oy, r, eye_h, 1.2)       # and not over the crest of a hill (relief.py)
    if vs is not None:
        fov &= vs
    pk = peek_point(p)
    if pk is not None and m.in_bounds(*pk):
        # leaning out: you see what the corner hid
        fov |= tcod.map.compute_fov(m.see, pk, radius=r, light_walls=True,
                                    algorithm=tcod.constants.FOV_SYMMETRIC_SHADOWCAST)
    # how far you can look in each direction (your seat), and in the dark only as far as the light allows
    x0, x1 = max(0, ox - r), min(m.w, ox + r + 1)
    y0, y1 = max(0, oy - r), min(m.h, oy + r + 1)
    dx = (np.arange(x0, x1) - ox)[:, None].astype(np.float32)
    dy = (np.arange(y0, y1) - oy)[None, :].astype(np.float32)
    dist = np.sqrt(dx * dx + dy * dy)
    if cones:
        mult = np.full(dist.shape, base, np.float32)
        ang = np.arctan2(dy, dx)
        for a0, half, mu in cones:
            dd = np.abs((ang - a0 + math.pi) % (2 * math.pi) - math.pi)
            mult = np.where(dd <= half, np.maximum(mult, mu), mult)
        mult[ox - x0, oy - y0] = top
    else:
        mult = np.float32(base)
    reach = dist <= np.maximum(R * mult, 1.5)
    if lit_r and game.lit is not None:
        reach |= game.lit[x0:x1, y0:y1] & (dist <= lit_r * mult)
    win = np.zeros_like(fov)
    win[x0:x1, y0:y1] = reach
    fov &= win
    m.visible[:] = fov
    m.explored |= fov
    mem = m.memory()
    mem[fov] = m.t[fov]                            # (what you see now is what you'll remember)


def _on_a_rise(m, x, y) -> bool:
    """Standing well above the ground round about (a knoll, a crest): the crops below don't hide the field."""
    e = m.__dict__.get("elev")
    if e is None:
        return False
    x0, x1, y0, y1 = max(0, x - 6), min(m.w, x + 7), max(0, y - 6), min(m.h, y + 7)
    return float(e[x, y]) - float(e[x0:x1, y0:y1].mean()) >= 3.0


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
    r = game.view_range_cache * eye_mult_at(game, a.x, a.y)
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
