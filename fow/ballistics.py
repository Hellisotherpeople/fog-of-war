"""Material impacts for small arms, in the simulation's existing energy/armour units."""
from __future__ import annotations

import math

from . import tiles as T


def surface_normal(m, x, y, direction, previous=None):
    """Infer a wall's face from adjoining solid tiles; isolated objects use their entry face."""
    def solid(px, py):
        return m.in_bounds(px, py) and T.COVER[m.t[px, py]] >= 50 and T.ARMOR[m.t[px, py]] > 10
    vertical = int(solid(x, y - 1)) + int(solid(x, y + 1))
    horizontal = int(solid(x - 1, y)) + int(solid(x + 1, y))
    if vertical > horizontal:
        return (1., 0.)
    if horizontal > vertical:
        return (0., 1.)
    if previous is not None:
        dx, dy = x - previous[0], y - previous[1]
        if dx and not dy:
            return (1., 0.)
        if dy and not dx:
            return (0., 1.)
    return (1., 0.) if abs(direction[0]) >= abs(direction[1]) else (0., 1.)


def impact(tile, energy, penetration, direction=(1., 0.), normal=(1., 0.), kind="bullet", roll=1.):
    """Outcome, retained energy fraction, outgoing direction. Nothing creates energy."""
    incidence = max(.1, abs(direction[0] * normal[0] + direction[1] * normal[1]))
    if tile.key == "window":
        return "penetrate", .94, direction
    resistance = max(.5, tile.armor) / incidence
    capacity = max(0., energy * (.6 if kind == "bullet" else .4) + penetration * 2)
    if capacity > resistance:
        retained = max(.08, min(.97, 1 - .75 * resistance / capacity))
        return "penetrate", retained, direction
    soft = tile.key in ("sandbags", "checkpoint", "hedge", "rubble_earth") or \
        any(k in tile.key for k in ("wood", "thatch", "snow", "mud", "sand"))
    hard = not soft and (tile.hard or any(k in tile.key for k in ("steel", "metal", "concrete", "stone", "brick", "rock")))
    # Shallow impacts may glance; soft earth, wood and vegetation absorb or admit the projectile.
    chance = max(0., (.55 - incidence) * 1.7) if hard and kind == "bullet" else 0.
    if energy >= 12 and roll < chance:
        dot = direction[0] * normal[0] + direction[1] * normal[1]
        reflected = (direction[0] - 2 * dot * normal[0], direction[1] - 2 * dot * normal[1])
        return "ricochet", min(.55, .2 + .4 * (1 - incidence)), reflected
    return "stop", 0., direction
