"""Dated reports, carried map sheets, and working command posts.

The strategic simulation abstracts outlying reporting parties. On the loaded
battlefield, an actual soldier and a working communication route are required.
"""
from __future__ import annotations

from collections import Counter
from copy import copy, deepcopy

from .constants import SIDES, other_side


def distance(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def radio_link(game, actor):
    from .command import has_radio, vehicle_has_radio
    if not getattr(actor, "active", False) or getattr(actor, "downed", False):
        return False
    if hasattr(actor, "vt"):
        return vehicle_has_radio(game, actor)
    if has_radio(actor):
        return True
    if actor.vehicle is not None and vehicle_has_radio(game, actor.vehicle):
        return True
    return any(a is not actor and a.active and not a.downed and has_radio(a)
               and distance(a.pos, actor.pos) <= 3 for a in game.near(actor.x, actor.y, 3, actor.side))


def headquarters(game, actor=None):
    a = actor or game.player
    if game.__dict__.get("domain", "land") != "land":
        return None
    from . import tiles as T
    for rec in game.map.gen_positions:
        if rec.get("kind") != "hq" or rec.get("side") != a.side or rec.get("destroyed"):
            continue
        # A constructed headquarters ceases to work when its radio room is destroyed.
        if rec.get("built") and game.map.t[rec["x"], rec["y"]] != T.ID["radio_set"]:
            continue
        if distance(a.pos, (rec["x"], rec["y"])) <= 8:
            return rec
    return None


def local_contacts(game, squad, age=60):
    """What this unit saw, without borrowing another unit's unreported sightings."""
    contacts = squad.rep.setdefault("local_contacts", {})
    from .command import leader_of
    leader = leader_of(squad)
    if leader is None:
        return []
    observers = {a.id: a for a in squad.members if a.active and not a.downed}
    seen = [v for v in contacts.values() if 0 <= game.turn - v["turn"] <= age
            and (a := observers.get(v["observer"])) is not None
            and (a is leader or distance(a.pos, leader.pos) <= 12 or
                 radio_link(game, a) and radio_link(game, leader))]
    # A delivered staff message can inform either army's subordinate commander.
    for r in leader.ai.get("staff_contacts", {}).values():
        if 0 <= game.turn - r["turn"] <= age and not any(v["id"] == r["id"] for v in seen):
            seen.append(r)
    p = game.player
    return [r for r in seen if p is None or r['id'] != p.id or squad.side != p.side or game.renegade]


def observe(game, observer, target):
    """Record a sighting locally and dispatch a frozen report over a working net."""
    from .brain import contact_kind
    sq = observer.squad
    report = dict(id=target.id, x=target.x, y=target.y, turn=game.turn,
                  kind=contact_kind(target), observer=observer.id, observer_vehicle=hasattr(observer, "vt"))
    if sq is not None:
        local = sq.rep.setdefault("local_contacts", {})
        local[target.id] = report
        if len(local) > 100:
            sq.rep["local_contacts"] = {k: v for k, v in local.items() if game.turn - v["turn"] < 120}
    if not radio_link(game, observer):
        return
    pending = game.__dict__.setdefault("intel_pending", {})
    key = (observer.side, target.id)
    brain = game.brains[observer.side]
    prior = brain.contacts.get(target.id)
    if key not in pending and (prior is None or game.turn - prior.turn >= 15):
        pending[key] = dict(report, side=observer.side, due=game.turn + 15)


def tick(game):
    from .brain import Contact
    pending = game.__dict__.setdefault("intel_pending", {})
    for key, r in list(pending.items()):
        if game.turn < r["due"]:
            continue
        del pending[key]
        pool = game.vehicles if r.get("observer_vehicle") else game.actors
        a = next((a for a in pool if a.id == r["observer"] and a.side == r["side"]), None)
        if a is None or not radio_link(game, a):
            continue
        brain = game.brains[r["side"]]
        brain.contacts[r["id"]] = Contact(r["id"], r["x"], r["y"], r["turn"], r["kind"])
        brain.urgent = True
    if game.turn % 60 == 0 and headquarters(game):
        copy_map(game)
    if game.turn % 30 == 0:
        from .dispatches import tick as dispatch_tick
        dispatch_tick(game)


def objective_owner(game, side, index):
    """Start-line briefing, then nearby observations that can reach command."""
    ob = game.map.objectives[index]
    known = game.map.__dict__.setdefault("objective_reports", {s: {} for s in SIDES})[side]
    if index not in known:
        known[index] = ob.owner if game.turn < 30 else None
    from .senses import los_clear
    if any(a.side == side and a.active and not a.downed and distance(a.pos, (ob.x, ob.y)) <= ob.radius + 6
           and radio_link(game, a) and los_clear(game, a.x, a.y, ob.x, ob.y) for a in game.actors):
        known[index] = ob.owner
    return known[index]


def _snapshot(strategic, sector, side, turn):
    """Outlying reconnaissance reports estimates, never an enemy order of battle."""
    import random
    rng = random.Random(f"{strategic.seed}:{sector.x}:{sector.y}:{side}:{turn // 600}")
    own = Counter(sector.units[side])
    enemy = Counter()
    # A friendly detachment in contact, or a patrol from the adjacent friendly sector.
    scouts = bool(own) or any(n.control == side and n.units[side] and strategic.supply_of(side, n) > .1
                             for n in strategic.neighbors(sector))
    if scouts:
        enemy = Counter({k: max(1, round(n * rng.uniform(.5, 1.6)))
                         for k, n in sector.units[other_side(side)].items() if n})
    return dict(turn=turn, source="unit situation report" if own else "patrol report",
                control=sector.control, units={side: own, other_side(side): enemy},
                installations=[i for i in sector.installations if i[1] == side],
                fort=sector.fort if sector.control == side else 0, enemy_known=scouts,
                supply=strategic.supply_of(side, sector) if sector.control == side else None)


def strategic_reports(game, initial=False):
    """Both armies have the same reporting lag and dependence on supply routes."""
    st = game.strategic
    reports = st.__dict__.setdefault("situation_reports", {s: {} for s in SIDES})
    pending = st.__dict__.setdefault("situation_pending", [])
    for side, key, report, due in list(pending):
        if game.turn >= due:
            reports[side][key] = report
            pending.remove((side, key, report, due))
    for side in SIDES:
        for s in st.active():
            own = s.control == side and st.supply_of(side, s) > .1
            front = any(n.control == side and n.units[side] and st.supply_of(side, n) > .1
                        for n in st.neighbors(s))
            if not (own or front):
                continue
            report = _snapshot(st, s, side, game.turn)
            key = (s.x, s.y)
            if initial:
                report["source"] = "departure briefing"
                reports[side][key] = report
            elif not any(p[0] == side and p[1] == key for p in pending):
                pending.append((side, key, report, game.turn + (600 if own else 1200)))


def merge_map(actor, reports):
    """A delayed packet cannot erase newer notes already on a carried map."""
    known = actor.ai.setdefault("map_reports", {})
    fresh = {k: r for k, r in reports.items() if k not in known or r["turn"] > known[k]["turn"]}
    known.update(deepcopy(fresh))
    return len(fresh)


def copy_map(game):
    reports = game.strategic.__dict__.get("situation_reports", {}).get(game.player.side, {})
    merge_map(game.player, reports)


def map_report(game, sector):
    return game.player.ai.get("map_reports", {}).get((sector.x, sector.y))


def map_sector(game, sector):
    if sector is None:
        return None
    view = copy(sector)
    r = map_report(game, sector)
    view.control = r["control"] if r else None
    view.units = r["units"] if r else {s: Counter() for s in SIDES}
    view.installations = r["installations"] if r else []
    view.fort = r["fort"] if r else 0
    return view


def report_age(game, sector):
    r = map_report(game, sector)
    if r is None:
        return "No situation report. Terrain only."
    age = max(0, game.turn - r["turn"])
    return f"{r['source'].capitalize()}: {age // 60} min old" + (" - may be obsolete" if age >= 1800 else "")
