"""One native neighborhood query; Python owns actors, mutations and random draws."""
import numpy as np
from . import native, tiles as T
from .constants import BIG

NEIGHBOURS = ((-1, -1), (0, -1), (1, -1), (-1, 0), (0, 0), (1, 0), (-1, 1), (0, 1), (1, 1))


def field(value):
    if isinstance(value, np.ndarray) and value.dtype == np.int32 and value.ndim == 2:
        return value
    return getattr(value, '_field', None)


def choose(game, a, maps, exp, exposure_w, cohesion, spread, stay_bias,
           avoid_fire, mates, keep_range, swap_cost, unit, crowd=True):
    core = native.core
    if core is None or not hasattr(core, 'step_scores'):
        return False, None
    live = []
    for mp, weight in maps:
        if mp is None or not weight:
            continue
        compiled = field(mp)
        if compiled is None:
            return False, None
        live.append((compiled, weight))
    keep = None
    if keep_range is not None and keep_range[0] is not None:
        compiled = field(keep_range[0])
        if compiled is None:
            return False, None
        keep = (compiled, keep_range[1], keep_range[2])
    occupancy, mines = [], []
    sa, va, known = game.soldier_at, game.vehicle_at, game.map.mines
    sa_get, mines_get = sa.get, known.get
    ax, ay, side = a.x, a.y, a.side
    index = game.__dict__.get("_native_near")
    if index is not None and hasattr(index, "context"):
        occupancy, mates = index.context(ax, ay, 0 if side == "allies" else 1, list(va), game.__dict__.get("_arr_index", {}).get(a.id, -1))
        if not crowd:
            mates = []
    else:
        vehicles = bool(va)
        for dx, dy in NEIGHBOURS:
            point = (ax + dx, ay + dy)
            other = sa_get(point)
            occupancy.append(-1 if (vehicles and point in va) or (other is not None and
                             (other.side != side or other.is_player or other.downed))
                             else 1 if other is not None else 0)
        mates = [(o.x, o.y) for o in game.near(ax, ay, 2, side) if o is not a] if crowd else None
    known_mines = bool(known)
    for dx, dy in NEIGHBOURS:
        if known_mines:
            mine = mines_get((ax + dx, ay + dy))
            mines.append(mine is not None and side in mine.known)
        else:
            mines.append(False)
    scores = core.step_scores(game.map.t, game.map.fire, T.WALK, T.DOOR, T.WATER,
        a.x, a.y, occupancy, mines, live, exp, exposure_w, cohesion, spread, stay_bias,
        avoid_fire, mates or [], keep, swap_cost, unit, BIG)
    best, best_score = None, None
    random = game.rng.random
    if scores and isinstance(scores[0], tuple):       # (an extension from before the flat score vector)
        for dx, dy, score in scores:
            score += random() * .5
            if best_score is None or score < best_score:
                best, best_score = (dx, dy), score
    else:
        for i, score in enumerate(scores):
            if score == float("inf"):
                continue
            score += random() * .5
            if best_score is None or score < best_score:
                dx, dy = divmod(i, 3)
                best, best_score = (dx - 1, dy - 1), score
    return True, None if best == (0, 0) else best
