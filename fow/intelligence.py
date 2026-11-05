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


def objective_owner(game, side, index, observers=None):
    """Start-line briefing, then nearby observations that can reach command."""
    ob = game.map.objectives[index]
    known = game.map.__dict__.setdefault("objective_reports", {s: {} for s in SIDES})[side]
    # Reports belong to the persistent landmark, not its index in a moving terrain window.
    reports = ob.__dict__.setdefault("reported_owners", {})
    if side not in reports:
        reports[side] = known.get(index, ob.owner if game.turn < 30 else None)
    from .senses import los_clear
    if observers is None:
        observers = game.near_people_many([(ob.x, ob.y, ob.radius + 6)])[0]
    if any(a.side == side and a.active and not a.downed and distance(a.pos, (ob.x, ob.y)) <= ob.radius + 6
           and radio_link(game, a) and los_clear(game, a.x, a.y, ob.x, ob.y) for a in observers):
        reports[side] = ob.owner
    known[index] = reports[side]
    return known[index]


def local_objective_owner(game, squad, index):
    """A leader can use his section's nearby observations without informing distant HQ."""
    from .command import leader_of
    from .senses import los_clear
    leader = leader_of(squad)
    if leader is None or not leader.active or leader.downed:
        return None
    ob = game.map.objectives[index]
    for a in squad.members:
        if (not a.active or a.downed or a.ai.get("civilian") or a.side != squad.side
                or distance(a.pos, ob.pos) > ob.radius + 6):
            continue
        if not los_clear(game, *a.pos, *ob.pos):
            continue
        if (a is leader or distance(a.pos, leader.pos) <= 12 and los_clear(game, *a.pos, *leader.pos)
                or radio_link(game, a) and radio_link(game, leader)):
            return ob.owner
    return None


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


# ------------------------------------------------------------------ reading captured papers

# what each captured paper can be made to say, and the glyph it leaves on the ground
DOC_INTEL = {"paybook": 0, "notebook": 1, "field_orders": 2, "marked_map": 3, "op_orders": 4}
INTEL_GLYPH = {"bunker": "B", "mg_nest": "M", "trench": "·", "foxhole": "·", "hq": "H", "depot": "D",
               "artillery": "A", "aa": "F", "aid": "+", "motor_pool": "P", "airfield": "W", "fortress": "#",
               "naval_base": "N", "inf": "·"}
FORT_DAYS = 1800            # how long pencil notes are worth acting on


def _note(game, player, x, y, kind, age=0):
    """A pencilled position on the player's map, deduplicated against what he already has."""
    notes = player.ai.setdefault("map_intel", [])
    for n in notes:
        if n["kind"] == kind and max(abs(n["x"] - x), abs(n["y"] - y)) <= 2:
            n["turn"] = max(n["turn"], game.turn - age)
            return
    notes.append(dict(x=x, y=y, kind=kind, turn=game.turn - age))
    if len(notes) > 240:
        del notes[:-240]


def map_intel(game, player):
    """The notes still worth trusting, freshest first."""
    return [n for n in player.ai.get("map_intel", ()) if game.turn - n["turn"] <= FORT_DAYS]


def study(game, player, it) -> list[str]:
    """Read a captured paper.  Returns what it told you, level by level."""
    from .brain import Contact
    d = it.data or {}
    enemy = d.get("side")
    if not enemy or enemy == player.side:
        return ["Ours, not theirs. Nothing on it you don't already know."]
    if (it.data or {}).get("studied_by") == player.id and game.turn - (it.data or {}).get("studied", 0) < 600:
        return ["You've read this one already; the pencil hasn't changed."]
    level = DOC_INTEL.get(it.tid, 0)
    rng = game.rng
    out = []
    brain = game.brains[player.side]
    written = d.get("written", game.turn)
    # everyone's papers say whose they are
    if d.get("unit"):
        out.append(f"the unit: {d['unit']}")
    elif level >= 1:
        out.append("their section and its job")
    # the positions written into it, with the error of a hurried pencil
    positions = d.get("positions") or ()
    if level >= 2 and positions:
        placed = 0
        for aid, x, y in positions[:60]:
            sx = x + rng.randint(-2, 2)
            sy = y + rng.randint(-2, 2)
            brain.contacts[aid] = Contact(aid, sx, sy, max(0, written - 60), "inf")
            _note(game, player, sx, sy, "inf", age=60)
            placed += 1
        if placed:
            out.append(f"{placed} of their positions still roughly where they were written")
    # a marked map carries the defensive layout of this very field
    if level >= 3:
        here = game.sector
        found = 0
        for rec in game.map.gen_positions:
            if rec.get("side") != enemy or rec.get("destroyed"):
                continue
            kind = rec.get("kind", "inf")
            sx = rec["x"] + rng.randint(-1, 1)
            sy = rec["y"] + rng.randint(-1, 1)
            _note(game, player, sx, sy, kind, age=rng.randint(0, 120))
            if kind in ("bunker", "mg_nest", "hq", "depot", "artillery", "aa", "motor_pool", "airfield", "fortress"):
                cid = -1 - len(brain.contacts)
                brain.contacts[cid] = Contact(cid, sx, sy, max(0, written - 120),
                                              {"mg_nest": "mg", "hq": "inf", "aid": "inf"}.get(kind, "bunker"
                                                                                               if kind == "bunker"
                                                                                               else "atgun"
                                                                                               if kind in ("artillery",
                                                                                                           "aa")
                                                                                               else "inf"))
            found += 1
        for (mx, my), mn in game.map.mines.items():
            if mn.side == enemy:
                mn.known.add(player.side)
        for i, ob in enumerate(game.map.objectives):
            reports = game.map.__dict__.setdefault("objective_reports", {s: {} for s in SIDES})[player.side]
            if ob.owner is not None:
                reports[i] = ob.owner
                ob.__dict__.setdefault("reported_owners", {})[player.side] = ob.owner
        if found:
            out.append(f"their defences: {found} posts, holding posts and obstacles on this field")
        # and the situation round here, as their staff wrote it
        from copy import deepcopy
        reports = {}
        for s in game.strategic.neighbors(here) + [here]:
            snap = _snapshot(game.strategic, s, enemy, written)
            reports[(s.x, s.y)] = snap
        for report in reports.values():
            report["source"] = "captured map"
            report["enemy_known"] = True
        merge_map(player, deepcopy(reports))
        out.append("their strength in the neighbouring sectors")
    # operation orders: what they mean to do next
    if level >= 4:
        from .logistics import _enemy_plan
        plan = _enemy_plan(game, player.side)
        if plan:
            out.append(plan)
        for s in game.strategic.sectors():
            if s.control == enemy:
                n = _snapshot(game.strategic, s, enemy, written)
                n["source"] = "captured operation orders"
                n["enemy_known"] = True
                merge_map(player, {(s.x, s.y): n})
        out.append("every sector they hold, marked with what is in it")
    if it.data is None:
        it.data = {}
    it.data["studied"] = game.turn
    it.data["studied_by"] = player.id
    return out


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
