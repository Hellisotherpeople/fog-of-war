"""The minutes after a fight.

A section doesn't go straight on.  The firing dies, the wounded are seen to, pouches are filled from the
men who have too much and the men who have none, the dead are tagged and their papers taken, the enemy's
kit is turned over, a report goes back, and someone is told to watch the front while it happens.  Then the
line dresses itself and waits for the next thing.

This is the lull, not a scripted cutscene: every chore is the ordinary action machinery, the war carries on
around it, and a fresh contact ends it at once.
"""
from __future__ import annotations

import math

LULL = 120          # seconds since the last contact before a section settles
LENGTH = 300        # and how long the lull is worth having
RADIUS = 26
COOLDOWN = 900


def _enemy_close(game, sq, r=RADIUS + 14) -> bool:
    anc = sq.anchor()
    if anc is None:
        return True
    for a in game.near(anc[0], anc[1], r):
        if a.side != sq.side and a.alive and a.state == "ok":
            return True
    return False


def state(game) -> dict:
    return game.__dict__.setdefault("consolidate", {})


def begin(game, sq) -> None:
    if state(game).get(sq.id) is not None:
        return
    t = game.turn
    rec = dict(since=t, until=t + LENGTH, sq=sq.id)
    state(game)[sq.id] = rec
    sq.rep["consolidate"] = rec
    dead = [a for a in game.actors if not a.alive and a.side == sq.side and
            a.ai.get("at_aid") is None and max(abs(a.x - (sq.anchor() or (a.x, a.y))[0]),
                                               abs(a.y - (sq.anchor() or (a.y, a.y))[1])) <= RADIUS]
    # tasks for the lull, worst first
    wounded = [a for a in game.actors if a.alive and a.side == sq.side and a.downed and
               a.ai.get("carried_by") is None and a.ai.get("at_aid") is None]
    enemies = [a for a in game.actors if not a.alive and a.side != sq.side and
               max(abs(a.x - (sq.anchor() or (a.x, a.y))[0]), abs(a.y - (sq.anchor() or (a.y, a.y))[1])) <= RADIUS]
    men = [m for m in sq.members if m.active and not m.downed and m.vehicle is None]
    # the sentry is the steadiest man
    men.sort(key=lambda m: -m.morale)
    for i, m in enumerate(men):
        m.ai.pop("after", None)
        if i == 0 and len(men) > 2:
            m.ai["after"] = ("watch", t + LENGTH)
        elif wounded:
            m.ai["after"] = ("dress", t + LENGTH)
        elif dead:
            m.ai["after"] = ("tags", t + LENGTH)
        elif enemies:
            m.ai["after"] = ("search", t + LENGTH)
        else:
            m.ai["after"] = ("ammo", t + LENGTH)
    p = game.player
    if p is not None and sq is p.squad:
        game.msg("The firing's died down. 'Get the wounded seen to. Top up. Tags off the dead. Wynn, watch "
                 "the front.' The section moves like tired men.", "info")
        from . import diary
        diary.entry(game, "lull", "The lull after it. Wounded, pouches, tags, and someone watching the hedge.")


def end(game, sq, why="done") -> None:
    rec = state(game).pop(sq.id, None)
    sq.rep.pop("consolidate", None)
    if rec is None:
        return
    for m in sq.members:
        m.ai.pop("after", None)
    if why == "contact":
        p = game.player
        if p is not None and sq is p.squad:
            game.msg("That's the lull over - here they come again.", "warn")
    else:
        sq.rep["consolidated"] = game.turn
        sq.morale = min(100.0, sq.morale + 4)
        p = game.player
        if p is not None and sq is p.squad:
            game.msg("The section has its pouches full, its wounded dressed and the front watched. It can fight "
                     "again.", "good")
            from . import diary
            diary.entry(game, "lull", "We were given the minutes to put ourselves right. It helped.")


def tick(game) -> None:
    if game.map is None or game.domain != "land":
        return
    if game.turn % 20:
        return
    for sq in list(game.squads):
        if sq.gone or not sq.members:
            continue
        rec = state(game).get(sq.id)
        if rec is not None:
            if game.turn - sq.last_contact < 15 and _enemy_close(game, sq, 15):
                end(game, sq, "contact")
            elif game.turn >= rec["until"]:
                end(game, sq)
            continue
        if sq.rep.get("consolidated") and game.turn - sq.rep["consolidated"] < COOLDOWN:
            continue
        if sq.player_led and sq is not game.player.squad:
            pass
        if game.turn - sq.last_contact < LULL or sq.last_contact < 0:
            continue
        if sq.order.kind in ("retreat", "rout", "resupply") or sq.__dict__.get("task"):
            continue
        if _enemy_close(game, sq):
            continue
        if any(a.ai.get("sleeping") is not None for a in sq.members):
            continue
        begin(game, sq)


def act(game, a, vis, sq) -> int | None:
    """A chore in the lull.  None: nothing for him, get on with the ordinary life of the section."""
    after = a.ai.get("after")
    if after is None:
        return None
    kind = after[0]
    t = game.turn
    if vis:
        return None                       # eyes up: the lull can wait a moment
    if kind == "watch":
        a.stance = 1 if a.stance == 0 else a.stance
        return 100
    if kind == "dress":
        hurt = [o for o in game.near(a.x, a.y, 20, a.side)
                if o.alive and o.downed and o.ai.get("carried_by") is None and o.ai.get("at_aid") is None
                and o.body.bleed_rate() > 0.05]
        if not hurt:
            a.ai["after"] = ("ammo", t + 120)
            return None
        o = min(hurt, key=lambda o: math.hypot(o.x - a.x, o.y - a.y))
        if max(abs(o.x - a.x), abs(o.y - a.y)) > 1:
            from .ai import path_step
            return path_step(game, a, o.x, o.y)
        from . import medical as MED
        if MED.can_help(game, a, o):
            return MED.first_aid(game, a, o)
        a.ai["after"] = ("ammo", t + 120)
        return None
    if kind in ("tags", "search"):
        side = a.side if kind == "tags" else None
        bodies = [o for o in game.near(a.x, a.y, 18)
                  if not o.alive and (side is None or o.side == a.side) and max(abs(o.x - a.x), abs(o.y - a.y)) > 0]
        if not bodies:
            a.ai["after"] = ("ammo", t + 120)
            return None
        o = min(bodies, key=lambda o: math.hypot(o.x - a.x, o.y - a.y))
        if max(abs(o.x - a.x), abs(o.y - a.y)) > 1:
            from .ai import path_step
            return path_step(game, a, o.x, o.y)
        if kind == "tags":
            from .entities import Item
            if not any(i.t.tool == "dogtags" and (i.data or {}).get("owner") == o.name for i in a.inv):
                it = Item("dogtags", 1)
                it.data = dict(owner=o.name, name=o.name, nation=o.nation)
                a.add_item(it)
                a.ai["after"] = ("ammo", t + 120)
                return 100
            a.ai["after"] = ("ammo", t + 120)
            return None
        # search the enemy dead for ammunition
        for it in list(game.map.items_at(o.x, o.y)):
            if it.t.kind in ("ammo", "mag", "clip") and a.weapon is not None and a.ammo_for(a.weapon) is not None:
                from . import actions as A
                A.pickup(game, a, it, o.x, o.y)
                return 100
        a.ai["after"] = ("ammo", t + 120)
        return None
    if kind == "ammo":
        from .ammo import spare_rounds
        w = a.weapon
        if w is None or spare_rounds(a, w) <= 0:
            a.ai["after"] = (a.ai["after"][0], t + 60)
            return None
        for o in game.near(a.x, a.y, 8, a.side):
            if o is a or not o.active or o.downed or o.weapon is None:
                continue
            if o.ammo_count(o.weapon) >= o.weapon.t.mag * 2:
                continue
            if max(abs(o.x - a.x), abs(o.y - a.y)) > 1:
                from .ai import path_step
                return path_step(game, a, o.x, o.y)
            from .ammo import hand_over
            hand_over(game, a, o, o.weapon, max_items=1)
            return 120
        a.ai["after"] = ("watch" if a is sq.members[0] else "search", t + 120)
        return None
    a.ai.pop("after", None)
    return None


def line(game, sq) -> str | None:
    rec = state(game).get(sq.id) if sq is not None else None
    if rec is None:
        return None
    left = max(0, rec["until"] - game.turn)
    return f"consolidating ({left // 60}m{left % 60:02d} left)"
