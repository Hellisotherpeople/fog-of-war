"""The going: what a man on foot - or the vehicle you're in - can get through, and how fast.

In words for the look ("Slow going - you can't see into it"), and as a tint over the ground when you read it
(X): red where there's no way through, amber where it's slow, deepening with how slow.  The numbers are the
real ones the pathing uses (the tile's cost with the slope on it), not a separate guess.
"""
from __future__ import annotations

import numpy as np

from . import tiles as T

BLOCKED = (205, 62, 50)
SLOW = (225, 175, 45)
GOOD = (150, 200, 120)


def _vehicle(game):
    p = game.player
    return p.vehicle if p is not None and p.vehicle is not None else None


STRUGGLE = (225, 120, 50)


def words(game, x, y, numbers=False, tid=None):
    """(text, colour) about getting across tile (x, y), or None where it's ordinary going.  tid: the tile as
    you remember it (out of sight), rather than as it is."""
    m = game.map
    remembered = tid is not None
    tid = int(m.t[x, y]) if tid is None else int(tid)
    d = T.DEFS[tid]
    v = _vehicle(game)
    if v is not None:
        vt = v.vt
        if d.water >= 2 and vt.water != "amphib":
            return "Too deep for the vehicle.", BLOCKED
        if not d.walk and d.water < 1:
            if d.crush and d.crush <= vt.crush:
                return "The vehicle can smash through it.", SLOW
            return "No way through for the vehicle.", BLOCKED
        r = (int(m.vcost[x, y]) if not remembered else int(T.VCOST[tid])) / 100.0
    else:
        if not d.walk:
            s = "No way through"
            if 0 < d.crush <= 3:
                s += " on foot - a tank could push through it"
            if d.see and d.key not in ("sky", "sea_below", "deck_below"):
                s += "; you can see past it"
            return s + ".", BLOCKED
        if d.water >= 2:
            return "Deep water: you'd have to swim for it.", BLOCKED
        r = (int(m.cost_foot[x, y]) if not remembered else int(T.COST[tid])) / 100.0
    if r <= 0.95:
        word, col = "Good going", GOOD
    elif r < 1.2:
        word, col = None, None
    elif r < 1.6:
        word, col = "Slowish going", SLOW
    elif r < 2.2:
        word, col = "Slow going", SLOW
    elif r < 3.2:
        word, col = "Very slow going", SLOW
    else:
        word, col = "A struggle to get through", STRUGGLE       # (slow, not impassable: not the red of no way)
    blind = not d.see and v is None
    if word is None and not blind:
        return None
    s = word or "Easy enough going"
    if numbers and word:
        s += f" (×{r:.1f} the time)"
    if blind:
        s += " - you can't see into it"
        col = col or SLOW
    return s + ".", col


def tint(game, xs, ys):
    """Colour and strength (0..1) of the going tint over the map window [xs, ys] (slices)."""
    m = game.map
    t = m.seen_t(xs, ys)
    vis = m.visible[xs, ys]
    v = _vehicle(game)
    if v is not None:
        vt = v.vt
        water = T.WATER[t]
        crush = T.CRUSH[t]
        blocked = (~T.WALK[t] & (water < 1) & ~((crush > 0) & (crush <= vt.crush)))
        if vt.water != "amphib":
            blocked |= water >= 2
        cost = np.where(vis, m.vcost[xs, ys], T.VCOST[t]).astype(np.float32)
    else:
        blocked = ~T.WALK[t] | (T.WATER[t] >= 2)
        cost = np.where(vis, m.cost_foot[xs, ys], T.COST[t]).astype(np.float32)
    slow = np.clip((cost - 115.0) / 260.0, 0.0, 1.0)
    slow[blocked] = 0
    col = np.zeros(t.shape + (3,), np.float32)
    col[...] = SLOW
    col[blocked] = BLOCKED
    a = np.where(blocked, 0.5, np.where(slow > 0, 0.14 + slow * 0.32, 0.0)).astype(np.float32)
    return col, a
