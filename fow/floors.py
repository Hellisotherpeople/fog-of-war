"""Upstairs and down: every storey of a building is its own floor plan, and every one can come down.

The ground floor is the map itself.  Above it each storey is a separate plan of floors, walls,
windows, stairwells and - once the guns have been at the house - holes and broken edges.  A cellar
below is a third kind of plan, reached by its trapdoor.  Men, fire, grenades and shells all move
between the plans through stairs, stairwells, holes and the stairwell shaft.

Three things make the vertical war what it is:
  - height.  A man upstairs sees over hedges, walls and crops, and down into the street; the men in
    the street cannot see him at a window unless they get an angle.
  - cover.  A window sill, a parapet and a floor edge are real cover and cost the defender little.
  - the floor itself.  It is thin.  Shells, bursts of automatic fire and grenades put holes in it;
    a man over a hole falls, and a man on a collapsing floor goes down with the house.

The plans are kept out of the tile arrays on purpose: men on different storeys stand on different
ground at the same x, y, and a single array cannot hold both.  `tile_at(x, y, z)` is the question to
ask when a z matters.
"""
from __future__ import annotations

import math

import numpy as np

from . import tiles as T

OPEN_TOP = {"church", "desert_house", "barn", "white_church", "tower", "keep", "lighthouse", "pagoda", "elevator",
            "marabout", "white_house", "station", "abbey", "chateau", "windmill", "post_mill"}

UPPER_FLOOR = {"wood": "floorboards", "stone": "floor_stone_up", "concrete": "floor_concrete_up"}
UPPER_WALL = {"wood": "upper_wall_wood", "stone": "upper_wall", "concrete": "upper_wall"}


# ---------------------------------------------------------------- the plans
def open_top(game, a):
    """The rect of the building whose open top (belfry, roof, hayloft) a man is up on, or None."""
    z = getattr(a, "z", 0)
    if z <= 0 or a is None:
        return None
    m = game.map
    b = m.building_at(a.x, a.y)
    if b is None or z < b[1] - 1:
        return None
    styles = m.__dict__.get("_bstyle")
    key = (id(m.buildings), len(m.buildings))
    if styles is None or styles[0] != key:
        styles = (key, {tuple(bb[:4]): bb[4] for bb in m.buildings if len(bb) > 4})
        m.__dict__["_bstyle"] = styles
    style = styles[1].get(b[0], "")
    return b[0] if style in OPEN_TOP else None


def plans(m) -> dict:
    return m.__dict__.setdefault("storey_plan", {})


def plan(m, rect, z):
    """The tile-id array of one storey (z != 0), or None."""
    return (plans(m).get(tuple(rect)) or {}).get(z)


def _put(arr, m, rect, x, y, key):
    x0, y0 = rect[0], rect[1]
    arr[x - x0, y - y0] = T.ID[key]


def tile_at(m, x, y, z=0):
    """The tile under a man at (x, y, z): the ground, a storey plan, or a cellar.  None: air."""
    if not m.in_bounds(x, y):
        return None
    if z == 0:
        return m.tile(x, y)
    b = m.building_at(x, y)
    if b is None:
        return None
    arr = plan(m, b[0], z)
    if arr is None:
        return None
    tid = int(arr[x - b[0][0], y - b[0][1]])
    return T.DEFS[tid] if tid else None


def tid_at(m, x, y, z=0):
    d = tile_at(m, x, y, z)
    return d.id if d is not None else -1


def floor_under(m, x, y, z):
    d = tile_at(m, x, y, z)
    return bool(d is not None and d.walk and not d.key.startswith("floor_hole"))


def walkable(m, x, y, z):
    d = tile_at(m, x, y, z)
    return bool(d is not None and (d.walk or d.key in ("floor_hole", "window_broken", "upper_window_broken")))


def see_through(m, x, y, z):
    d = tile_at(m, x, y, z)
    if d is None:
        return True                    # out of the building: air, and the world beyond
    return bool(d.see or d.key in ("upper_window", "upper_window_broken", "upper_wall", "parapet",
                                   "floor_hole", "stairwell"))


def inside(rect, x, y) -> bool:
    x0, y0, bw, bh = rect
    return x0 <= x < x0 + bw and y0 <= y < y0 + bh


def set_at(m, x, y, z, key):
    if z == 0:
        m.set(x, y, key)
        return True
    b = m.building_at(x, y)
    arr = plan(m, b[0], z) if b is not None else None
    if arr is None:
        return False
    arr[x - b[0][0], y - b[0][1]] = T.ID[key]
    m.version += 1
    return True


def cover_at(m, x, y, z):
    d = tile_at(m, x, y, z)
    return int(d.pos_cover) if d is not None else 0


# ---------------------------------------------------------------- generation
def storeys_of(m, rect):
    return (m.__dict__.get("storeys") or {}).get(tuple(rect), 1)


def build(m, rect, style, ruin, rng, storeys=None, furn=""):
    """Lay out the upper floors and the cellar of a building from its ground plan."""
    x0, y0, bw, bh = rect
    if not (0 <= x0 and 0 <= y0 and x0 + bw <= m.w and y0 + bh <= m.h):
        return
    storeys = storeys_of(m, rect) if storeys is None else storeys
    if storeys <= 1 and style not in ("house", "townhouse") and ruin <= 0:
        return
    wall_key = "wood" if "wood" in style or style in ("barn", "hut", "shed", "izba", "post_mill") else \
        "concrete" if style in ("factory", "elevator", "bunker", "log_bunker") else "stone"
    fkey = UPPER_FLOOR[wall_key]
    wkey = UPPER_WALL[wall_key]
    floors = {}
    stair = list(zip(*np.nonzero(m.t[x0:x0 + bw, y0:y0 + bh] == T.ID["stairs"])))
    stair = (stair[0][0] + x0, stair[0][1] + y0) if len(stair) else None
    open_top = style in OPEN_TOP
    for z in range(1, storeys):
        arr = np.zeros((bw, bh), np.uint16)
        for lx in range(bw):
            for ly in range(bh):
                g = m.tile(x0 + lx, y0 + ly)
                if g.key in ("stairs", "trapdoor", "door", "door_open", "doorway"):
                    arr[lx, ly] = T.ID["floorboards"] if wall_key == "wood" else T.ID[fkey]
                elif g.window:
                    arr[lx, ly] = T.ID["upper_window" if z < storeys - 1 else "upper_window_broken"]
                elif g.floor:
                    arr[lx, ly] = T.ID[fkey]
                elif g.key in ("wall_brick", "wall_stone", "wall_wood", "wall_log", "wall_concrete",
                               "wall_factory", "wall_white", "wall_thatch", "wall_mud", "wall_gabion"):
                    arr[lx, ly] = T.ID[wkey]
                # else: outline outside the building's shape stays air
        if stair is not None:
            lx, ly = stair[0] - x0, stair[1] - y0
            arr[lx, ly] = T.ID["stairwell"]
            # the stairs connect the storeys either side of this one
            if z > 1:
                below = floors[z - 1]
                below[lx, ly] = T.ID["stairwell"]
        # a roof instead of a last floor
        if z == storeys - 1 and open_top:
            for lx in range(bw):
                for ly in range(bh):
                    if arr[lx, ly] == T.ID[fkey]:
                        arr[lx, ly] = T.ID["roof_slate"]
                    elif arr[lx, ly] == T.ID[wkey]:
                        arr[lx, ly] = T.ID["parapet"]
            if stair is not None:
                arr[stair[0] - x0, stair[1] - y0] = T.ID["stairwell"]
        # the guns: holes and broken edges.  Higher floors are hit more and hold less.
        hurt = min(0.85, ruin * (0.35 + 0.16 * z) + (0.10 if z >= 3 else 0))
        for lx in range(bw):
            for ly in range(bh):
                if arr[lx, ly] not in (T.ID[fkey], T.ID["floorboards"], T.ID["floor_stone_up"],
                                       T.ID["floor_concrete_up"], T.ID["roof_slate"]):
                    continue
                edge = lx in (0, bw - 1) or ly in (0, bh - 1)
                if rng.random() < hurt * (0.35 if edge else 0.14):
                    arr[lx, ly] = T.ID["floor_hole"]
                elif rng.random() < hurt * 0.5:
                    arr[lx, ly] = T.ID["floor_broken"]
        if np.any(arr):
            floors[z] = arr
    # the cellar (always, when the house got a trapdoor)
    has_door = any(m.tile(x0 + lx, y0 + ly).key == "trapdoor" for lx in range(bw) for ly in range(bh))
    if has_door or rng.random() < (0.55 if style in ("townhouse", "chateau", "abbey", "house") else 0.2):
        cell = np.zeros((bw, bh), np.uint16)
        for lx in range(1, bw - 1):
            for ly in range(1, bh - 1):
                if m.tile(x0 + lx, y0 + ly).floor:
                    cell[lx, ly] = T.ID["floor_stone"]
        for lx in range(bw):
            for ly in (0, bh - 1):
                if m.tile(x0 + lx, y0 + ly).key.startswith("wall"):
                    cell[lx, ly] = T.ID["wall_stone"]
        for ly in range(bh):
            for lx in (0, bw - 1):
                if m.tile(x0 + lx, y0 + ly).key.startswith("wall"):
                    cell[lx, ly] = T.ID["wall_stone"]
        door = next(((lx, ly) for lx in range(bw) for ly in range(bh)
                     if m.tile(x0 + lx, y0 + ly).key == "trapdoor"), None)
        if door is not None:
            cell[door] = T.ID["floor_stone"]
        if np.any(cell):
            floors[-1] = cell
    if floors:
        plans(m)[tuple(rect)] = floors


# ---------------------------------------------------------------- the floor gives way
def hole(game, x, y, z, big=False):
    """Put a hole in a storey's floor.  Returns the storey if one was opened."""
    m = game.map
    b = m.building_at(x, y)
    if b is None:
        return None
    for zz in ([z] if z else []):
        arr = plan(m, b[0], zz)
        if arr is None:
            continue
        lx, ly = x - b[0][0], y - b[0][1]
        if arr[lx, ly] and arr[lx, ly] != T.ID["floor_hole"]:
            arr[lx, ly] = T.ID["floor_hole"]
            m.version += 1
            return zz
    return None


def breach(game, x, y, power=40, z=None):
    """A blast at a man's storey opens the floor under him (and maybe the one above)."""
    m = game.map
    p = game.player
    z = z if z is not None else (p.z if p is not None and math.hypot(p.x - x, p.y - y) < 2 else 0)
    if z > 0:
        hole(game, x, y, z, big=power > 60)
    elif z == 0:
        hole(game, x, y, 1, big=power > 60)


def fall(game, a, from_z=None):
    """A man over a hole, or on a floor that has gone: down, hard, one storey at a time."""
    m = game.map
    z = a.z if from_z is None else from_z
    if z == 0:
        return
    old_z = z
    dz = 0
    while z < 0:
        z += 1
        dz += 1
    if z > 0:
        nz = z - 1
        while nz > 0 and tile_at(m, a.x, a.y, nz) is not None and not floor_under(m, a.x, a.y, nz):
            nz -= 1
            dz += 1
        a.z = nz
    else:
        a.z = 0
        dz += 1
    a.stance = 2
    game.pop_actor_at(a, a.x, a.y, old_z)
    if a.z == 0:
        x, y = a.x, a.y
        if game.soldier_at.get((x, y)) is not None and game.soldier_at[(x, y)] is not a:
            for dx in (1, -1, 0, 0, 1, 1, -1, -1):
                for dy in (0, 0, 1, -1, 1, -1, 1, -1):
                    nx, ny = x + dx, y + dy
                    if m.in_bounds(nx, ny) and m.walk[nx, ny] and game.soldier_at.get((nx, ny)) is None:
                        x, y = nx, ny
                        break
        a.x, a.y = x, y
    game.set_actor_at(a, a.x, a.y, a.z)
    game.note_move(a)
    dmg = game.rng.uniform(10, 26) * max(1, dz)
    if a.z < 0:
        dmg *= 0.35
    if a.carrying is not None:
        from .actions import put_down
        put_down(game, a)
    from .combat import hit_actor
    hit_actor(game, a, dmg, "blunt", None, "a fall through a floor")
    if a.is_player and a.alive:
        game.msg("The floor gives way - you drop through into the wreckage!", "hurt")
        game.player_fov()


def tick(game):
    """Every few seconds: floor holes and failures catch the men standing on them, and the burned-out
    upper floors come down."""
    from .combat import hit_actor
    m = game.map
    for a in list(game.actors):
        if not a.alive or a.vehicle is not None:
            continue
        z = a.z
        if not z:
            continue
        d = tile_at(m, a.x, a.y, z)
        if d is None or d.key in ("floor_hole",):
            fall(game, a)
            continue
        if m.fire[a.x, a.y] > 0 or m.tile(a.x, a.y).key in ("rubble_heavy", "rubble"):
            if z > 0 and (m.fire[a.x, a.y] > 0 or d.hp <= 0):
                # a burning or shelled floor gives way under him
                if game.rng.random() < 0.35:
                    fall(game, a)


def collapse_rect(game, x0, y0, x1, y1, z):
    """Blow the floor out of a whole room."""
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            hole(game, x, y, z)
    for a in game.actors:
        if a.alive and a.z == z and x0 <= a.x <= x1 and y0 <= a.y <= y1:
            fall(game, a)


# ---------------------------------------------------------------- paths between storeys
def route_cells(game, a, tx, ty):
    """A whole BFS route across a storey (the player's walk-to), or None."""
    m = game.map
    b = m.building_at(a.x, a.y)
    if b is None:
        return None
    x0, y0, bw, bh = b[0]
    if not (x0 <= tx < x0 + bw and y0 <= ty < y0 + bh):
        st = _stairs_in(m, b[0])
        if st is None:
            return None
        tx, ty = st                          # (the way out is the stairs; then the ground route is yours)
    z = a.z
    prev = {(a.x, a.y): None}
    q = [(a.x, a.y)]
    for _ in range(1200):
        if not q:
            break
        cx, cy = q.pop(0)
        if (cx, cy) == (tx, ty):
            break
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if not (dx or dy):
                    continue
                nx, ny = cx + dx, cy + dy
                if (nx, ny) in prev or not (x0 <= nx < x0 + bw and y0 <= ny < y0 + bh):
                    continue
                if not walkable(m, nx, ny, z):
                    continue
                prev[(nx, ny)] = (cx, cy)
                q.append((nx, ny))
    if (tx, ty) not in prev:
        return None
    out = []
    cur = (tx, ty)
    while cur is not None:
        out.append(cur)
        cur = prev[cur]
    return list(reversed(out))[1:]


def step_path(game, a, tx, ty):
    """A small BFS inside the building's storey to (tx, ty), then one step of it.  None if unreachable."""
    m = game.map
    b = m.building_at(a.x, a.y)
    if b is None or (tx, ty) == (a.x, a.y):
        return None
    rect = b[0]
    x0, y0, bw, bh = rect
    if not (x0 <= tx < x0 + bw and y0 <= ty < y0 + bh):
        tx, ty = min(max(tx, x0 + 1), x0 + bw - 2), min(max(ty, y0 + 1), y0 + bh - 2)
    z = a.z
    seen = {(a.x, a.y): None}
    q = [(a.x, a.y)]
    goal = None
    for _ in range(600):
        if not q:
            break
        cx, cy = q.pop(0)
        if (cx, cy) == (tx, ty):
            goal = (cx, cy)
            break
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if not (dx or dy):
                    continue
                nx, ny = cx + dx, cy + dy
                if (nx, ny) in seen or not (x0 <= nx < x0 + bw and y0 <= ny < y0 + bh):
                    continue
                if not walkable(m, nx, ny, z):
                    continue
                o = game.actor_at(nx, ny, z)
                if o is not None and o.side != a.side:
                    continue
                seen[(nx, ny)] = (cx, cy)
                q.append((nx, ny))
    if goal is None:
        # unreachable: try the stairs on this floor, or a hole to drop through
        st = _stair_near(m, rect, a.x, a.y)
        if st is not None and st != (a.x, a.y):
            goal = st
        else:
            return None
    cur = goal
    while seen.get(cur) not in (None, (a.x, a.y)) and seen.get(cur) != (a.x, a.y):
        cur = seen[cur]
    if cur == (a.x, a.y):
        return None
    from . import actions as A
    c = A.move(game, a, cur[0] - a.x, cur[1] - a.y)
    return c


def _stair_near(m, rect, x, y):
    x0, y0, bw, bh = rect
    best = None
    for lx in range(x0, x0 + bw):
        for ly in range(y0, y0 + bh):
            if m.tile(lx, ly).key == "stairs":
                d = abs(lx - x) + abs(ly - y)
                if best is None or d < best[0]:
                    best = (d, (lx, ly))
    return best[1] if best else None


def _stairs_in(m, rect):
    x0, y0, bw, bh = rect
    sid = T.ID["stairs"]
    for x in range(max(0, x0), min(m.w, x0 + bw)):
        for y in range(max(0, y0), min(m.h, y0 + bh)):
            if m.t[x, y] == sid:
                return (x, y)
    return None


# ---------------------------------------------------------------- sight and cover
def los_clear(game, v, t) -> bool:
    """The vertical part of a sight line: floor plans decide it, and height beats ground clutter."""
    m = game.map
    vt = tile_at(m, v.x, v.y, v.z)
    tt = tile_at(m, t.x, t.y, t.z)
    if vt is None and v.z != 0:
        return True
    if tt is None and t.z != 0:
        return True
    if v.z == t.z:
        if v.z <= 0:
            return True
        # same storey: trace the plan between them
        import tcod
        for x, y in tcod.los.bresenham((v.x, v.y), (t.x, t.y))[1:-1]:
            if not see_through(m, x, y, v.z):
                return False
        return True
    if v.z < 0 or t.z < 0:
        return False                     # a cellar sees nothing but its own
    # different upper storeys of the same building: only down the stairwell
    bv, bt = m.building_at(v.x, v.y), m.building_at(t.x, t.y)
    if bv is not None and bt is not None and bv[0] == bt[0]:
        st = _stairs_in(m, bv[0])
        if st is None:
            return False
        return max(abs(v.x - st[0]), abs(v.y - st[1])) <= 2 and \
            max(abs(t.x - st[0]), abs(t.y - st[1])) <= 2
    # from height: over the ground clutter, but not through another building's walls
    own = open_top(game, v) if v.z > 0 else None
    dx, dy = t.x - v.x, t.y - v.y
    n = max(abs(dx), abs(dy))
    for i in range(1, n):
        x = round(v.x + dx * i / n)
        y = round(v.y + dy * i / n)
        if own is not None and inside(own, x, y):
            continue                              # over the battlements: your own walls don't block you
        d = m.tile(x, y)
        if v.z > t.z:
            if d.key.startswith("wall") or d.see is False or d.tall and d.cover >= 90:
                return False
        else:
            if not d.see and d.tall:
                return False
    return True


def height_advantage(viewer, target) -> float:
    """How much easier a man above is to use: 1.0 at the same level, more from above."""
    dz = (getattr(viewer, "z", 0) or 0) - (getattr(target, "z", 0) or 0)
    return 1.0 + max(-0.35, min(0.5, dz * 0.12))


def cover_from(game, target, shooter) -> float:
    """Cover at the target's own storey, plus the sill of a window and the drop to a lower floor."""
    m = game.map
    base = cover_at(m, target.x, target.y, target.z)
    d = tile_at(m, target.x, target.y, target.z)
    if d is not None:
        if d.window:
            base = max(base, 55)
        if target.z > (shooter.z or 0):
            base = max(base, 35)                  # the floor edge between the two of you
    return base


# ---------------------------------------------------------------- AI and player movement
def move_z(game, a, dx, dy):
    """A step on an upper floor or in a cellar.  Returns an action cost, or None if blocked; may drop him."""
    m = game.map
    nx, ny = a.x + dx, a.y + dy
    if not m.in_bounds(nx, ny):
        return None
    b0 = m.building_at(a.x, a.y)
    if b0 is None or m.building_at(nx, ny) is None or m.building_at(nx, ny)[0] != b0[0]:
        if a.is_player:
            game.msg("You're upstairs: a window or the stairs are the way out.", "info")
        return None
    d = tile_at(m, nx, ny, a.z)
    if d is None:
        return None
    if d.key == "upper_window" and a.z > 0:
        # through a smashed window and out: you drop to the ground
        pass
    doorlike = d.key in ("upper_window_broken", "floor_hole")
    if not (d.walk or doorlike):
        return None
    if game.vehicle_at.get((nx, ny)) is not None:
        return None
    other = game.soldier_at.get((nx, ny))
    if other is not None and other is not a and other.z == a.z:
        return None
    from . import actions as A
    c = A.move(game, a, dx, dy)
    if c is None:
        return None
    if d.key == "floor_hole":
        fall(game, a)
    elif d.key in ("upper_window_broken",) and a.z > 0:
        # out of the window: the ground below
        game.pop_actor_at(a, a.x, a.y, a.z)
        a.z = 0
        a.stance = 2
        game.set_actor_at(a, a.x, a.y, 0)
        game.note_move(a)
        if a.is_player:
            game.msg("You swing out of the window and drop to the street.", "info")
    return c


# ---------------------------------------------------------------- start of battle
def place_upstairs(game):
    """Defenders' snipers and machine gunners go upstairs - the tower top, the upper windows - where the
    ground cannot see them."""
    from . import tiles as T_
    m = game.map
    rng = game.rng
    for sq in list(game.squads):
        if sq.order.kind not in ("hold", "defend", "dig", "ambush"):
            continue
        for a in list(sq.members):
            if not a.alive or a.vehicle is not None or a.z:
                continue
            keen = a.role == "sniper" or (a.role in ("lmg_gunner", "hmg_gunner") and rng.random() < 0.45) or \
                (a.role in ("at_soldier", "mortarman") and rng.random() < 0.3) or \
                (a.role in ("officer", "intel", "radioman") and rng.random() < 0.35) or \
                (a.role == "rifleman" and rng.random() < 0.12)
            if not keen:
                continue
            b = m.building_at(a.x, a.y)
            if b is None or b[1] < 2:
                continue
            st = _stairs_in(m, b[0])
            if st is None or game.actor_at(st[0], st[1], 1) is not None:
                continue
            top = b[1] - 1 if a.role == "sniper" else rng.randint(1, b[1] - 1)
            spot = _upper_spot(game, b[0], top, rng)
            if spot is None:
                if game.actor_at(st[0], st[1], 1) is not None:
                    continue
                spot = st
                top = 1
            game.pop_actor_at(a, a.x, a.y, 0)
            a.x, a.y = spot
            a.z = top
            a.stance = 1
            game.set_actor_at(a, spot[0], spot[1], top)


def _upper_spot(game, rect, z, rng):
    """A window with a sill, a parapet, or failing those the stairwell."""
    m = game.map
    x0, y0, bw, bh = rect
    cands = []
    for x in range(x0, x0 + bw):
        for y in range(y0, y0 + bh):
            d = tile_at(m, x, y, z)
            if d is None or game.actor_at(x, y, z) is not None:
                continue
            if d.key in ("parapet", "upper_window", "upper_window_broken"):
                cands.append((x, y))
    if not cands:
        for x in range(x0, x0 + bw):
            for y in range(y0, y0 + bh):
                d = tile_at(m, x, y, z)
                if d is not None and d.walk and game.actor_at(x, y, z) is None:
                    cands.append((x, y))
    return rng.choice(cands) if cands else None


def ai_act(game, a, vis, sq):
    """A soldier upstairs or in a cellar: move about the storey, use windows, come down or get under
    cover when the house is being shot up, and go below when the shells fall."""
    from . import actions as A
    m = game.map
    z = a.z
    order = sq.order.kind if sq is not None else "hold"
    moving = order in ("move", "attack", "assault", "retreat", "flank", "follow", "mount", "regroup", "rally")
    if z < 0:
        if a.suppression < 20 and game.turn - a.ai.get("shelled", -999) > 60:
            return A.climb(game, a, 1)
        return 100
    if z == 0:
        # standing at the stairs: get above the ground floor when it's the safer or ordered thing
        if m.tile(a.x, a.y).key == "stairs":
            b = m.building_at(a.x, a.y)
            up = b is not None and b[1] > 1 and tile_at(m, a.x, a.y, 1) is not None and \
                game.actor_at(a.x, a.y, 1) is None
            if up:
                hold = order in ("hold", "defend", "ambush", "dig")
                squad_up = sq is not None and any(o is not a and o.alive and o.z > 0 for o in sq.members)
                if (hold and a.suppression < 60 and game.rng.random() < 0.3) or \
                        (moving and squad_up and game.rng.random() < 0.5) or \
                        ((a.suppression > 55 or m.fire[a.x, a.y] > 0) and game.rng.random() < 0.35):
                    return A.climb(game, a, 1)
        d = m.tile(a.x, a.y)
    else:
        d = tile_at(m, a.x, a.y, z)
    if d is not None and (d.key == "floor_hole" or d.key == "floor_broken"):
        # step off the hole, or across the broken edge, if there is somewhere good to go
        c = step_path(game, a, a.x, a.y + 1) or step_path(game, a, a.x + 1, a.y)
        if c:
            return c
    if d is None:
        fall(game, a)
        return 100
    burning = m.fire[a.x, a.y] > 0 or (z > 0 and d.key == "roof_slate" and game.weather in ("rain", "storm"))
    if z > 0 and (moving or burning or a.suppression > 80):
        if d.key in ("stairwell",):
            return A.climb(game, a, -1)
        if burning and game.rng.random() < 0.25:
            st = _stairs_in(m, m.building_at(a.x, a.y)[0]) if m.building_at(a.x, a.y) else None
            if st:
                c = step_path(game, a, st[0], st[1])
                if c:
                    return c
        if moving and a.suppression < 60:
            # follow the squad's business on this floor, or come down to it
            anc = sq.anchor() if sq is not None else None
            if anc is not None and m.building_at(*anc) and m.building_at(*anc)[0] == m.building_at(a.x, a.y)[0]:
                c = step_path(game, a, anc[0], anc[1])
                if c:
                    return c
            st = _stairs_in(m, m.building_at(a.x, a.y)[0])
            if st and (st[0], st[1]) != (a.x, a.y):
                c = step_path(game, a, st[0], st[1])
                if c:
                    return c
            if d.key == "stairwell":
                return A.climb(game, a, -1)
        return None
    # holding a window: lean into it, keep down between shots
    if z > 0 and d is not None:
        if d.key in ("upper_window", "upper_window_broken", "parapet") and a.stance != 0:
            a.stance = 0
        elif d.key not in ("upper_window", "upper_window_broken", "parapet") and vis and a.stance == 0:
            a.stance = 1
        if not vis and not moving and game.rng.random() < 0.02:
            # shift to another window in the same room now and then
            b = m.building_at(a.x, a.y)
            if b is not None:
                spot = _upper_spot(game, b[0], z, game.rng)
                if spot and spot != (a.x, a.y):
                    c = step_path(game, a, spot[0], spot[1])
                    if c:
                        return c
        return None
    # on the ground, the shells falling: the cellar, if there's a trapdoor within a step or two
    if a.suppression > 65 and not moving and game.turn - a.ai.get("shelled", -999) < 20:
        if m.tile(a.x, a.y).key == "trapdoor":
            return A.climb(game, a, -1)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                x, y = a.x + dx, a.y + dy
                if m.in_bounds(x, y) and m.tile(x, y).key == "trapdoor" and (x, y) not in game.soldier_at:
                    return A.move(game, a, dx, dy)
    return None


# ---------------------------------------------------------------- render
def overlay(game, arr_t, arr_glyph, arr_fg, arr_bg, x0, y0, w, h, z):
    """Paint a storey over the ground window.  Cells outside the plan keep the ground, dimmed."""
    m = game.map
    p = game.player
    if p is None:
        return
    seen = m.seen_t(slice(x0, x0 + w), slice(y0, y0 + h))
    for yy in range(h):
        for xx in range(w):
            x, y = x0 + xx, y0 + yy
            if not m.explored[x, y]:
                arr_glyph[yy, xx] = ord(" ")
                arr_fg[yy, xx] = 0
                arr_bg[yy, xx] = 0
                continue
            d = tile_at(m, x, y, z)
            if d is None:
                arr_glyph[yy, xx] = ord("·") if m.explored[x, y] else ord(" ")
                arr_fg[yy, xx] = np.array([60, 58, 52]) if m.explored[x, y] else np.array([0, 0, 0])
                arr_bg[yy, xx] = arr_bg[yy, xx] * 0.45
                continue
            v = int(m.var[x, y]) % T.MAXV
            arr_glyph[yy, xx] = T.GLYPHS[d.id, v]
            arr_fg[yy, xx] = T.FG[d.id]
            arr_bg[yy, xx] = T.BG[d.id]
            # your own storey: lit normally.  Below and above you: faint.
            if z != 0 and not m.visible[x, y]:
                arr_fg[yy, xx] = arr_fg[yy, xx] * 0.5 + 30
