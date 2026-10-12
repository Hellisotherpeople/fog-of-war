"""One native neighborhood query; Python owns actors, mutations and random draws."""
import numpy as np
from . import native, tiles as T
from .constants import BIG


def field(value):
    if isinstance(value, np.ndarray) and value.dtype == np.int32 and value.ndim == 2:
        return value
    return getattr(value, '_field', None)


def choose(game, a, maps, exp, exposure_w, cohesion, spread, stay_bias,
           avoid_fire, mates, keep_range, swap_cost, unit):
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
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            point = a.x+dx, a.y+dy
            other = sa.get(point)
            occupancy.append(-1 if point in va or (other is not None and
                             (other.side != a.side or other.is_player or other.downed))
                             else 1 if other is not None else 0)
            mine = known.get(point)
            mines.append(mine is not None and a.side in mine.known)
    scores = core.step_scores(game.map.t, game.map.fire, T.WALK, T.DOOR, T.WATER,
        a.x, a.y, occupancy, mines, live, exp, exposure_w, cohesion, spread, stay_bias,
        avoid_fire, mates or [], keep, swap_cost, unit, BIG)
    best, best_score = None, None
    for dx, dy, score in scores:
        score += game.rng.random() * .5
        if best_score is None or score < best_score:
            best, best_score = (dx, dy), score
    return True, None if best == (0, 0) else best
