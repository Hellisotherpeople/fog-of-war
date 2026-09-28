"""Upstairs and down: the floors of buildings, for everyone.

The map is one floor plan; a building's upper storeys have the same walls and windows as the ground floor,
three metres higher (actor.z = 1, 2...).  From up there a man sees - and shoots - over the hedges, walls
and crops outside that hide the same field from the street; the top of a church tower, a flat roof and a
barn's hayloft door are open, so up there the building's own walls don't block the view at all.  A cellar
(z = -1, through a trapdoor) is where you go when the shells come: nothing sees in or out, and nothing short
of the house falling in reaches you.

Stairs and trapdoors are tiles (mapgen puts them in); everyone climbs the same way (actions.climb).  A
floor blown out from under a man drops him to the ground.  Defenders' snipers and machine gunners are put
upstairs when a battle starts, as they were - a sniper in the church tower is the oldest story of the war.
"""
from __future__ import annotations

OPEN_TOP = {"church", "desert_house", "barn", "white_church", "tower", "keep", "lighthouse", "pagoda", "elevator",
            "marabout", "white_house"}


def open_top(game, a):
    """The rect of the building whose open top (belfry, roof, hayloft) a man is up on, or None."""
    z = getattr(a, "z", 0)
    if z <= 0 or a is None:
        return None
    m = game.map
    b = m.building_at(a.x, a.y)
    if b is None or z < b[1] - 1:
        return None
    style = next((bb[4] for bb in m.buildings if tuple(bb[:4]) == b[0]), "")
    return b[0] if style in OPEN_TOP else None


def inside(rect, x, y) -> bool:
    x0, y0, bw, bh = rect
    return x0 <= x < x0 + bw and y0 <= y < y0 + bh


def tick(game):
    """Every few seconds: anyone upstairs whose floor has been blown away comes down with it."""
    from . import tiles as T
    from .combat import hit_actor
    m = game.map
    for a in game.actors:
        z = getattr(a, "z", 0)
        if not z or not a.alive:
            continue
        if not T.FLOOR[m.t[a.x, a.y]] or m.building_at(a.x, a.y) is None:
            a.z = 0
            if z > 0:
                a.stance = 2
                hit_actor(game, a, game.rng.uniform(12, 30) * z, "blunt", None, "a fall through a shattered floor")
                if a.is_player and a.alive:
                    game.msg("The floor gives way - you fall through into the rubble below!", "hurt")
            elif a.is_player:
                game.msg("The house above has fallen in. You claw your way up out of the cellar.", "warn")
            game.note_move(a)
            if a.is_player:
                game.player_fov()


def ai_act(game, a, vis, sq):
    """A soldier upstairs or in a cellar: come down when the squad moves off or the building's burning; go down
    into a cellar when the shelling's bad and there's one beside you, and come up when it's over."""
    from . import actions as A
    from .ai import path_step
    m = game.map
    z = getattr(a, "z", 0)
    order = sq.order.kind if sq is not None else "hold"
    moving = order in ("move", "attack", "assault", "retreat", "flank", "follow", "mount", "regroup")
    if z < 0:
        if a.suppression < 20 and game.turn - a.ai.get("shelled", -999) > 60:
            return A.climb(game, a, 1)
        return 100
    if z > 0:
        burning = m.fire[a.x, a.y] > 0
        if not (moving or burning or a.suppression > 85):
            return None                               # holding his window: the usual business
        if m.tile(a.x, a.y).key == "stairs":
            return A.climb(game, a, -1)
        b = m.building_at(a.x, a.y)
        st = _stairs_in(m, b[0]) if b else None
        if st is not None:
            return path_step(game, a, st[0], st[1]) or 100
        return None
    # on the ground floor, the shells falling: the cellar, if there's a trapdoor within a step or two
    if a.suppression > 70 and not moving and game.turn - a.ai.get("shelled", -999) < 20:
        t = m.tile(a.x, a.y).key
        if t == "trapdoor":
            return A.climb(game, a, -1)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                x, y = a.x + dx, a.y + dy
                if m.in_bounds(x, y) and m.tile(x, y).key == "trapdoor" and (x, y) not in game.soldier_at:
                    return A.move(game, a, dx, dy)
    return None


def _stairs_in(m, rect):
    from . import tiles as T
    x0, y0, bw, bh = rect
    sid = T.ID["stairs"]
    for x in range(x0, x0 + bw):
        for y in range(y0, y0 + bh):
            if m.t[x, y] == sid:
                return (x, y)
    return None


def place_upstairs(game):
    """At the start of a battle: the defenders' snipers, and some of their machine gunners, are upstairs in
    the buildings they hold - the top of the tower if there is one."""
    from . import tiles as T
    m = game.map
    rng = game.rng
    for sq in game.squads:
        if sq.order.kind not in ("hold", "defend", "dig", "ambush"):
            continue
        for a in sq.members:
            if not a.alive or a.vehicle is not None or getattr(a, "z", 0):
                continue
            keen = a.role == "sniper" or (a.role in ("lmg_gunner", "hmg_gunner") and rng.random() < 0.4) or \
                (a.role == "rifleman" and rng.random() < 0.06)
            if not keen:
                continue
            b = m.building_at(a.x, a.y)
            if b is None or b[1] < 2:
                continue
            st = _stairs_in(m, b[0])
            if st is None or st in game.soldier_at or not T.FLOOR[m.t[st]]:
                continue
            game.soldier_at.pop((a.x, a.y), None)
            a.x, a.y = st
            game.soldier_at[st] = a
            a.z = b[1] - 1 if a.role == "sniper" else 1
