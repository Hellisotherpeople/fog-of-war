"""How much ground a vehicle or a big gun covers.

A tile is about two metres.  A Sherman (5.8 m by 2.6 m) is three tiles long and
two wide; a jeep is two by one; a landing craft five by two; an 88 on its
cruciform mount three by three.  Footprints are rectangles rotated to the
vehicle's facing and rasterised onto the grid; the vehicle's (x, y) is its pivot,
a tile near the middle.
"""
from __future__ import annotations

import math
from functools import lru_cache

from .constants import OCTANT_VEC

# the game's facings: 0 east, counting anticlockwise on the screen (1 north-east, 2 north ... 7 south-east)
FACING_VEC = OCTANT_VEC


def _cal(vt):
    from .data.vehicles import MOUNTS
    m = MOUNTS.get(vt.main) if vt.main else None
    return m.cal_mm if m is not None else 0


def vehicle_size(vt) -> tuple[int, int]:
    """(length, width) in tiles."""
    k = vt.vtype
    front = vt.armor[0] if vt.armor else 0
    if k in ("tank", "td", "spg"):
        return (4, 2) if front >= 150 else (3, 2)
    if k == "ltank":
        return (2, 1) if front < 40 else (3, 1)
    if k == "tankette":
        return (2, 1)
    if k in ("halftrack", "truck"):
        return (3, 1)
    if k == "armcar":
        return (3, 1) if front >= 25 else (2, 1)
    if k == "car":
        return (2, 1)
    if k == "lc":
        return (5, 2)
    if k == "amtrac":
        return (4, 2)
    cal = _cal(vt)
    if k == "atgun":
        return (2, 1) if cal < 50 else (2, 2) if cal < 80 else (3, 2)
    if k == "fieldgun":
        return (2, 2) if cal < 80 else (3, 2)
    if k == "aagun":
        if cal >= 75:
            return (3, 3)
        if cal >= 30 or "vierling" in vt.id:
            return (2, 2)
        return (1, 1)
    return (1, 1)


@lru_cache(maxsize=None)
def offsets(length: int, width: int, facing: int) -> tuple:
    """Tiles covered, relative to the pivot, for a rectangle facing one of 8 directions."""
    if length <= 1 and width <= 1:
        return ((0, 0),)
    fx, fy = FACING_VEC[facing % 8]
    n = math.hypot(fx, fy)
    ux, uy = fx / n, fy / n
    px, py = -uy, ux
    # the rectangle's centre sits half a tile off the pivot when a side is even
    cx = (0.5 * ux if length % 2 == 0 else 0) + (0.5 * px if width % 2 == 0 else 0)
    cy = (0.5 * uy if length % 2 == 0 else 0) + (0.5 * py if width % 2 == 0 else 0)
    diag = facing % 2 == 1
    slack = 0.2 if diag else 0.01
    hl, hw = length / 2 + slack, width / 2 + slack
    R = max(length, width) + 1
    cells = []
    for dx in range(-R, R + 1):
        for dy in range(-R, R + 1):
            qx, qy = dx - cx, dy - cy
            a = abs(qx * ux + qy * uy)
            b = abs(qx * px + qy * py)
            if a <= hl and b <= hw:
                cells.append((dx, dy))
    if (0, 0) not in cells:
        cells.append((0, 0))
    return tuple(sorted(cells))


def rect_center(length: int, width: int, facing: int):
    """Where the middle of the vehicle is, in tiles from the centre of its pivot tile."""
    fx, fy = FACING_VEC[facing % 8]
    n = math.hypot(fx, fy)
    ux, uy = fx / n, fy / n
    px, py = -uy, ux
    cx = (0.5 * ux if length % 2 == 0 else 0) + (0.5 * px if width % 2 == 0 else 0)
    cy = (0.5 * uy if length % 2 == 0 else 0) + (0.5 * py if width % 2 == 0 else 0)
    return cx, cy


def front_of(length: int, facing: int, x: int, y: int):
    """The tile the nose of the vehicle is on (for barrels, ramps and headlights)."""
    fx, fy = FACING_VEC[facing % 8]
    k = length // 2
    return x + fx * k, y + fy * k
