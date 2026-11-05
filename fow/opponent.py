"""The man on the other side of the hill.

A battle has a mind over it, and it belongs to a person.  Each side's commander is drawn at the start from
his army's school: how hard he pushes, how much he prepares, whether he likes the dark, what he does with a
beaten company.  He keeps a memory of the ground lost and the patrols sent, and he acts on it: a standing
patrol when the line goes quiet, a preparation shoot before an assault, a counter-attack into ground just
taken, relief for a battalion that has come apart.

None of it is a cheat.  The patrols are real squads with real orders, the shells come off the same support
establishment, the replacements come up the same road.  What the player hears of it is what his own signals
can hear: the enemy net is a voice, not a map.
"""
from __future__ import annotations

import math
import random

from .ai import Order
from .constants import other_side

# the schools, roughly: (push, preparation, night work, relief of the broken, patience)
SCHOOLS = {
    "germany": (0.65, 0.7, 0.7, 0.7, 0.55),
    "ussr": (0.8, 0.6, 0.6, 0.3, 0.3),
    "japan": (0.85, 0.35, 0.85, 0.2, 0.25),
    "usa": (0.45, 0.8, 0.35, 0.7, 0.7),
    "uk": (0.4, 0.8, 0.5, 0.65, 0.8),
    "canada": (0.5, 0.7, 0.4, 0.65, 0.65),
    "australia": (0.6, 0.55, 0.55, 0.6, 0.5),
    "newzealand": (0.55, 0.6, 0.5, 0.6, 0.6),
    "india": (0.5, 0.55, 0.4, 0.5, 0.6),
    "italy": (0.35, 0.55, 0.35, 0.45, 0.3),
    "france": (0.4, 0.6, 0.35, 0.55, 0.5),
    "poland": (0.55, 0.5, 0.6, 0.45, 0.4),
    "finland": (0.6, 0.5, 0.8, 0.5, 0.7),
    "hungary": (0.45, 0.45, 0.4, 0.4, 0.35),
    "romania": (0.4, 0.45, 0.35, 0.3, 0.3),
    "china": (0.4, 0.35, 0.7, 0.3, 0.5),
}
SCHOOL_WORD = {
    "germany": ("a methodical staff officer who rehearses everything and hates the dark", "method"),
    "ussr": ("a driver who will spend men like shells and is not moved by the bill", "mass"),
    "japan": ("a night fighter who wants the bayonet and will not call off an attack", "banzai"),
    "usa": ("a careful, well-supported commander who prepares the ground before he moves on it", "fire"),
    "uk": ("a deliberate, dry man who plans by the book and does not hurry", "set_piece"),
}


def state(game, side):
    vs = game.__dict__.setdefault("opponents", {})
    st = vs.get(side)
    if st is None:
        nat = game.side_nation(side)
        rng = random.Random(f"{side}:{nat}:{game.seed}:commander")     # (a persona, not the battle's die)
        base = SCHOOLS.get(nat, (0.5, 0.5, 0.4, 0.5, 0.5))
        jitter = lambda v: max(0.0, min(1.0, v + rng.uniform(-0.12, 0.12)))
        st = vs[side] = dict(nation=nat, push=jitter(base[0]), prep=jitter(base[1]), night=jitter(base[2]),
                             relief=jitter(base[3]), patience=jitter(base[4]), probes=0, losses=[],
                             probe_turn=-999, relief_turn=-999, fire_turn=-999, net_turn=-999, told=False)
        st["word"] = SCHOOL_WORD.get(nat, ("a competent, ordinary commander", "ordinary"))[0]
    return st


def net(game, side, text, important=False):
    """What the player's own signals can hear of that side's voice."""
    p = game.player
    if p is None or not p.alive:
        return
    st = state(game, side)
    if not important and game.turn - st["net_turn"] < 90:
        return
    st["net_turn"] = game.turn
    from .command import has_radio
    heard = any(a.side == p.side and a.active and not a.downed and has_radio(a)
                for a in game.near(p.x, p.y, 8))
    if heard and state(game, side).get("told_enemy", True):
        game.msg(f"Enemy net: {text}", "radio")


def _rear(game, side):
    e = game.home_edge(side)
    return e


def _weak_squad(game, side, squads):
    cands = [q for q in squads if q.members and q.order.kind in ("hold", "idle") and q.kind not in
             ("hq", "staff", "rear", "aid", "supply", "tank") and not q.player_led]
    if not cands:
        return None
    return min(cands, key=lambda q: (q.strength(), q.id))


def _enemy_objective(game, side):
    """Ground of the other side worth walking at, nearest first: their weak point or an unknown one."""
    from .intelligence import objective_owner
    objs = game.map.objectives
    enemy = other_side(side)
    if not objs:
        return None
    scored = []
    for i, ob in enumerate(objs):
        owner = objective_owner(game, side, i)
        scored.append((0 if owner == enemy else 1 if owner is None else 2, i))
    scored.sort()
    return objs[scored[0][1]] if scored else None


def probe(game, side, squads):
    """A standing patrol, sent to find out what the quiet means."""
    st = state(game, side)
    if game.turn - st["probe_turn"] < 240 + int((1 - st["push"]) * 500):
        return
    if game.is_night() and st["night"] < 0.35:
        return
    sq = _weak_squad(game, side, squads)
    ob = _enemy_objective(game, side)
    if sq is None or ob is None or sq.anchor() is None:
        return
    if game.turn - sq.last_contact < 120 or sq.order.kind in ("attack", "assault"):
        return
    st["probe_turn"] = game.turn
    st["probes"] += 1
    sq.rep["probe"] = game.turn + 300
    sq.order = Order("move", target=(ob.x, ob.y), radius=max(4, ob.radius // 2), issued=game.turn)
    sq.arrived = False
    net(game, side, f"patrol out toward {ob.name.casefold()}; report by radio.")


def prepare(game, side, squads, owners):
    """A shoot before the assault - if this commander is the sort, and the guns are in range."""
    st = state(game, side)
    if game.turn - st["fire_turn"] < 420 or st["prep"] < 0.55:
        return
    from .intelligence import objective_owner
    objs = game.map.objectives
    enemy = other_side(side)
    aims = [o for i, o in enumerate(objs) if objective_owner(game, side, i) == enemy and not o.contested]
    if not aims:
        return
    at = min(aims, key=lambda o: min((q.anchor() is not None and
                                      math.hypot(q.anchor()[0] - o.x, q.anchor()[1] - o.y) or 999)
                                     for q in squads) if squads else 999)
    support = getattr(game, "support", None)
    if support is None:
        return
    took = support.barrage(side, at.x, at.y, at.radius, 8, delay=30, kinds=("gun", "rocket", "naval"))
    if took:
        st["fire_turn"] = game.turn
        net(game, side, f"fire plan on {at.name.casefold()}; report when the shoot lifts.", important=True)


def relieve(game, side, squads):
    """A company that has come apart is pulled out and made up from the replacement draft."""
    st = state(game, side)
    if game.turn - st["relief_turn"] < 600 or st["relief"] < 0.35:
        return
    broken = [q for q in squads if q.members and q.anchor() is not None and not q.player_led and
              q.order.kind not in ("retreat", "resupply") and
              q.strength() < max(2, q.__dict__.get("initial", 9) * 0.35)]
    if not broken:
        return
    sq = min(broken, key=lambda q: q.strength())
    st["relief_turn"] = game.turn
    from .bonds import replacements
    n = replacements(game, sq)
    if not n:
        return
    e = _rear(game, side)
    if e is not None:
        sq.order = Order("move", target=sq.anchor(), radius=8, issued=game.turn)
        sq.arrived = False
    sq.rep["relieved"] = game.turn
    sq.morale = min(100.0, sq.morale + 12)
    net(game, side, f"{sq.name.casefold()} relieved and made up to strength; {n} replacements up.",
        important=True)


def counter_need(game, side) -> float:
    """How much superiority a defender wants before counter-attacking into lost ground."""
    st = state(game, side)
    if st["push"] > 0.7:
        return 1.05
    if st["push"] < 0.3:
        return 1.5
    return 1.25


def tick(game, side, squads, owners):
    """One pass of the commander's mind.  Called from commander_update; cheap."""
    if game.map is None or not squads or game.turn < 60:
        return
    st = state(game, side)
    if not st["told"]:
        st["told"] = True
        net(game, side, "net check.", important=False)
    st["losses"] = [(t, w) for t, w in st["losses"] if game.turn - t < 3600]
    probe(game, side, squads)
    prepare(game, side, squads, owners)
    relieve(game, side, squads)
