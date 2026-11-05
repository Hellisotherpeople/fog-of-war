"""What a section remembers, and the men who come to fill the gaps.

A squad is not a roster.  It has old hands, a way of doing things, and names it says without thinking.  A
death leaves a gap that the survivors count: the man's mate takes it worst, the section goes quiet, and a
replacement walking up from the rear arrives into that - younger, greener, and looked at.  He is a 'new man'
until he has been through something with them, and the section is slower to trust him than the paperwork is.

All of it lives on the squad for the length of this battle.  Nothing follows the player to another world.
"""
from __future__ import annotations


def memory(sq) -> dict:
    return sq.rep.setdefault("memory", dict(lost=[], new={}, graves=[]))


def remember(game, sq, dead) -> None:
    if sq is None or dead is None:
        return
    mem = memory(sq)
    if dead.id in [i for i, _ in mem["lost"]]:
        return
    mem["lost"].append((dead.id, game.turn))
    mem["lost"] = mem["lost"][-12:]
    if game.map is not None and game.map.in_bounds(dead.x, dead.y):
        mem["graves"].append((dead.x, dead.y, dead.name))
        mem["graves"] = mem["graves"][-8:]
    sq.morale = max(0.0, sq.morale - 3)
    # the closer they were, the worse it is
    from .people import buddy, call_name
    for m in sq.members:
        if not m.alive or m is dead:
            continue
        d = max(abs(m.x - dead.x), abs(m.y - dead.y))
        if buddy(game, m) is dead:
            m.morale = max(0.0, m.morale - 12)
        elif d <= 12:
            m.morale = max(0.0, m.morale - 4)
    p = game.player
    if p is not None and sq is p.squad and p.alive and p is not dead:
        old = len([1 for i, _ in mem["lost"] if game.turn - _ < 1800])
        game.msg(f"The section has lost {call_name(dead)}. Nobody says much. That's {old} in the last half hour."
                 if old > 1 else f"The section has lost {call_name(dead)}. The gap in the line stays open.", "death")


def new_man(game, a, sq, why="replacement", green=True) -> None:
    """He comes up from the rear into a section that has been shot about."""
    if sq is None or a is None:
        return
    mem = memory(sq)
    mem["new"][a.id] = game.turn
    a.ai["new_to_section"] = dict(sq=sq.id, since=game.turn, why=why)
    if green:
        a.skill = max(0.3, a.skill * 0.62)
    a.morale = max(20.0, a.morale - (12 if green else 4))
    sq.morale = max(0.0, sq.morale - 1.5)
    # the old hands look him over
    old = [m for m in sq.members if m is not a and m.alive and m.ai.get("new_to_section") is None]
    for m in old[:4]:
        m.ai["op"] = max(-100.0, m.ai.get("op", 0.0) - 6)
    p = game.player
    if p is not None and sq is p.squad:
        game.msg(f"A replacement comes up to the section: {' '.join([a.rank_short, a.name])}. "
                 f"He's green. Nobody's spoken to him yet.", "info")


def settle(game, a) -> None:
    tag = a.ai.pop("new_to_section", None)
    if tag is None:
        return
    sq = next((q for q in game.squads if q.id == tag.get("sq")), None)
    if sq is not None:
        memory(sq)["new"].pop(a.id, None)
        a.skill = min(9.9, a.skill + 0.8)
        a.morale = min(100.0, a.morale + 8)
        p = game.player
        if p is not None and sq is p.squad:
            game.msg(f"{a.last_name} isn't the new man any more. He's one of the section.", "good")


def replacements(game, sq, most=5) -> int:
    """Men up from the replacement draft, to the edge or to the squad, and into its strength."""
    if sq is None or not sq.members:
        return 0
    from .spawn import make_soldier, place, free_tile_near
    nat = sq.nation
    n = 0
    anc = sq.anchor() or sq.members[0].pos
    for _ in range(most):
        role = "rifleman" if game.rng.random() < 0.8 else game.rng.choice(
            ("rifleman", "smg_gunner", "lmg_assistant", "medic"))
        a = make_soldier(game, nat, role)
        a.side = sq.side
        a.squad = sq
        spot = free_tile_near(game, anc[0], anc[1], 8)
        if spot is None:
            spot = anc
        place(game, a, spot[0], spot[1], 3)
        if a not in sq.members:
            sq.members.append(a)
        new_man(game, a, sq, why="draft")
        n += 1
    if n:
        sq.initial = max(sq.initial, len([m for m in sq.members if m.active]) + 2)
        game.command.organise(game)
    return n


def tick(game) -> None:
    """New men prove themselves with time or with a kill; the memory of the dead cools."""
    p = game.player
    for a in game.actors:
        tag = a.ai.get("new_to_section")
        if tag is None:
            continue
        sq = a.squad
        since = tag.get("since", game.turn)
        fought = game.turn - since > 600 or a.stats.get("kills", 0) > 0
        away = sq is None or sq.gone or a.ai.get("at_aid") is not None
        if fought or away or game.turn - since > 2400:
            settle(game, a)
    if p is not None and p.squad is not None and game.turn % 60 == 0:
        mem = p.squad.rep.get("memory")
        if mem:
            mem["lost"] = [(i, t) for i, t in mem["lost"] if game.turn - t < 7200]
            mem["graves"] = mem["graves"][-8:]
