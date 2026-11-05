"""The trade.

Autopilot (A) hands your soldier to his training, and his training is his job.  A medic doesn't stand in the
line waiting to be told: he listens for the shouting, works through the casualties worst-first, and carries
the ones who can't walk back to the aid post.  An engineer goes at the wire.  The motor sergeant goes to the
tank with the thrown track.  A radioman keeps with the commander and the set.  A gunner gets on his gun.

It is the same AI every man on the field runs, and the same actions, pathing and costs; this only chooses
what a good man in that trade would do with his next few seconds, and says so in the panel so you can watch
the job being done and take it back.
"""
from __future__ import annotations

import math

CARD = "player_job"

# what a corporal would say he's doing it for
NARRATE = {
    "triage": "picks the worst case he can reach first and keeps his head down on the way",
    "treat": "works from the side the fire is coming from",
    "evac": "keeps the casualty's head below the parapet and takes the shortest way back",
    "sweep": "works forward by bounds, watching the hedge line",
    "supply": "fills his pouches before the next one, not after",
    "wire": "gets low and cuts from the side",
    "charge": "goes in with the fuse already broken",
    "fix": "looks at the job before he puts his hands in it",
    "lead": "keeps the section in hand and his own head down",
    "report": "goes to the leader rather than guessing",
    "eat": "eats while he can",
    "drink": "fills his canteen and drinks",
    "sleep": "sleeps with his boots on and his rifle under the edge of the blanket",
    "rest": "gets flat and rests his legs",
    "self": "dresses it himself rather than wait for a medic",
    "ammo": "tops up from the stack, keeping low",
    "orders": "moves on his orders without being chivvied",
    "post": "goes back to the aid station where he's wanted",
    "operate": "works down the table, worst first",
    "mount": "gets back to the machine before it goes on without him",
}


def card(game, kind, text, target=None, why="") -> None:
    """Put the current job on the panel, and say so once when it changes."""
    old = game.__dict__.get(CARD) or {}
    new = dict(kind=kind, text=text, target=target, why=why, since=game.turn if old.get("kind") != kind else
               old.get("since", game.turn))
    game.__dict__[CARD] = new
    if old.get("kind") != kind or old.get("text") != text:
        if kind != "fight":
            prefs = game.__dict__.get("_prefs") or {}
            note = NARRATE.get(kind) if prefs.get("autopilot_narrate", True) else None
            game.msg(f"You get on with the job: {text[0].lower() + text[1:]}" +
                     (f" - he {note}" if note else ""), "info")


def clear(game):
    game.__dict__.pop(CARD, None)


def _dist(a, x, y) -> int:
    return max(abs(a.x - x), abs(a.y - y))


def _go(game, a, x, y, margin=14, stance=None):
    from .ai import path_step, fix_stance
    c = path_step(game, a, x, y, margin=margin)
    if c and stance is not None:
        fix_stance(game, a, stance)
    return c


def _needs(a):
    return a.ai.setdefault("needs", dict(hunger=0., thirst=0., infection=0.))


def _low_ammo(a) -> bool:
    w = a.weapon
    if w is None or w.t.kind != "gun" or not getattr(w.t, "mag", 0):
        return False
    return a.ammo_count(w) < max(3, w.t.mag // 2)


def _sup(game, a, radius=25):
    """The nearest man it's proper to ask for orders (a leader, not a private)."""
    best = None
    for o in game.near(a.x, a.y, radius, a.side):
        if o is a or not o.active or o.downed or o.rank < a.rank + 1:
            continue
        d = _dist(a, o.x, o.y)
        if d > 1 and (best is None or d < best[0]):
            if o.rank >= 4 or o.role in ("squad_leader", "platoon_sergeant", "officer", "first_sergeant"):
                best = (d, o)
    return None if best is None else best[1]


def _survival(game, a, vis, near_enemy):
    """Eat, drink, dress a wound, rest, top up the pouches - what a man does without being told.

    These come before the trade: nobody goes on a casualty sweep for a medic with an empty canteen and a
    head full of static."""
    n = _needs(a)
    quiet = near_enemy > 35
    from . import actions as A
    # drink
    if n["thirst"] > 55:
        it = a.find(lambda i: i.t.tool == "canteen" and i.uses > 0)
        if it is not None:
            card(game, "drink", "Drinking")
            A.drink(game, a, it)
            return 150
    # food
    if n["hunger"] > 55:
        it = a.find(lambda i: i.t.tool == "ration")
        if it is not None:
            card(game, "eat", "Eating a ration")
            n["hunger"] *= 1 - it.condition
            A._consume(a, it)
            a.morale = min(100, a.morale + 3)
            return 400
    if max(n["hunger"], n["thirst"]) > 45 and quiet:
        # nothing in the pouches: the dump, or a tin on the ground
        src = None
        for r in getattr(game.map, "gen_positions", None) or []:
            if r.get("side") == a.side and not r.get("destroyed") and r.get("kind") in ("depot", "food_depot", "hq"):
                d = _dist(a, r["x"], r["y"])
                if d <= 8:
                    src = ("depot", r)
                    break
                if d <= 35 and src is None:
                    src = ("goto", r)
        if src is None:
            for (x, y), items in list(getattr(game.map, "items", {}).items()):
                if abs(x - a.x) > 22 or abs(y - a.y) > 22:
                    continue
                if any(i.t.tool in ("ration", "canteen") for i in items):
                    src = ("ground", (x, y))
                    break
        if src is not None and src[0] == "goto":
            card(game, "hunger", "Going back for food", (src[1]["x"], src[1]["y"]))
            return _go(game, a, src[1]["x"], src[1]["y"])
        if src is not None and src[0] == "ground":
            x, y = src[1]
            card(game, "hunger", "Getting food off the ground", (x, y))
            if _dist(a, x, y) <= 1:
                it = next((i for i in game.map.items_at(x, y) if i.t.tool in ("ration", "canteen")), None)
                if it is not None:
                    return A.pickup(game, a, it, x, y)
            else:
                return _go(game, a, x, y)
        if src is not None and src[0] == "depot":
            from .sustain import stores, take
            if stores(game.sector_for(a), a.side)["food"] > 0.4 and take(game.sector_for(a), a.side, "food", .4):
                from .entities import Item
                it = Item("ration" if n["hunger"] >= n["thirst"] else "canteen")
                if a.add_item(it) is not None:
                    game.msg(f"You draw a {'ration' if it.t.tool == 'ration' else 'canteen'} at the dump.", "good")
                    return 300
    # a dressing on your own wound
    if any(not w.bandaged and not w.tourniquet and w.bleed > 0.2 for w in a.body.wounds):
        if a.medical("pressure") or a.medical("bandage") or a.medical("tourniquet"):
            card(game, "self", "Dressing your own wound")
            c = A.treat(game, a, a)
            if c:
                return c
    # sleep: at night, or when he's falling down, if there's cover and nothing close
    if a.carrying is None and a.fatigue > 55 and near_enemy > 45:
        from . import sleep as SL
        from . import tiles as T
        bed = T.DEFS[int(game.map.t[a.x, a.y])].key in ("bed", "hospital_bed")
        covered = bed or game.map.pos_cover[a.x, a.y] >= 20 or a.has_tool("blanket")
        if (game.is_night() or a.fatigue > 85 or SL.debt(a) > 60) and covered and SL.can(game, a)[0]:
            card(game, "sleep", "Getting his head down" if game.is_night() else "Sleeping where he stands")
            SL.begin(game, a)
            return 100
    # rest: prone, out of the sights, when there's nothing to do about it
    if a.fatigue > 82 and near_enemy > 40:
        a.stance = 2
        a.fatigue = max(0.0, a.fatigue - 0.12)
        a.stamina = min(100.0, a.stamina + 0.4)
        card(game, "rest", "Resting - dead on your feet")
        return 300
    # ammunition
    if _low_ammo(a) and near_enemy > 20:
        from . import tiles as T
        spot = None
        m = game.map
        for (x, y), items in list(getattr(m, "items", {}).items()):
            if abs(x - a.x) > 24 or abs(y - a.y) > 24:
                continue
            if any(i.functional and i.tid == "ammo_crate" for i in items):
                spot = (x, y)
                break
        if spot is None:
            best = None
            for dx in range(-24, 25):
                for dy in range(-24, 25):
                    x, y = a.x + dx, a.y + dy
                    if not m.in_bounds(x, y) or T.DEFS[int(m.t[x, y])].key != "ammo_stack":
                        continue
                    d = abs(dx) + abs(dy)
                    if best is None or d < best[0]:
                        best = (d, x, y)
            if best is not None:
                spot = best[1:]
        if spot is not None:
            card(game, "ammo", "Topping up your pouches", spot)
            if _dist(a, *spot) <= 1:
                return A.resupply(game, a)
            return _go(game, a, *spot)
    return None


def _medical_low(a) -> bool:
    return a.medical("bandage") is None and a.medical("pressure") is None and a.medical("tourniquet") is None \
        and a.medical("kit") is None


def _draw_supplies(game, a) -> bool:
    """At the aid post, fill the pouches out of the stores (a real draw, off the sector's medical stock)."""
    from .sustain import stores, take
    from .medical import at_aid_post
    if not at_aid_post(game, a):
        return False
    sec = game.sector_for(a)
    if stores(sec, a.side)["medical"] < 0.2:
        return False
    got = 0
    for _ in range(4):
        if not _medical_low(a) and got >= 2:
            break
        if stores(sec, a.side)["medical"] < 0.2:
            break
        from .entities import Item
        it = Item("bandage")
        if a.add_item(it) is None:
            break
        take(sec, a.side, "medical", 0.2)
        got += 1
    if got:
        game.msg(f"You draw {got} field dressing{'s' if got != 1 else ''} at the aid post.", "good")
    return bool(got)


def _loose_medical(game, a, radius=22):
    """Field dressings off the dead and the ground, when the pouches are empty."""
    best = None
    m = game.map
    for (x, y), items in list(getattr(m, "items", {}).items()):
        if abs(x - a.x) > radius or abs(y - a.y) > radius:
            continue
        for it in items:
            if it.t.kind == "medical" or it.t.tool in ("kit", "antiseptic"):
                d = math.hypot(x - a.x, y - a.y)
                if best is None or d < best[0]:
                    best = (d, x, y)
                break
    for o in game.near(a.x, a.y, radius, a.side):
        if o.alive and o.state == "ok" and o.vehicle is None and o is not a and o.ai.get("at_aid") is not None:
            pass
    return best


# ============================================================================ the jobs
def _medic(game, a, vis, sq, near_enemy):
    from . import medical as MED
    from . import ai

    if a.carrying is not None:
        c = a.carrying
        post = MED.nearest_aid(game, a)
        word = "an aid post" if post is None else "the aid post"
        card(game, "evac", f"Carrying {game.name_of(c) if c.is_player is False else 'you'} to {word}",
             post and post[:2])
        return ai.evacuate_act(game, a, vis)

    if _medical_low(a):
        if MED.at_aid_post(game, a):
            card(game, "supply", "Drawing dressings at the aid post")
            if _draw_supplies(game, a):
                return 220
        loose = _loose_medical(game, a)
        if loose is not None:
            _, x, y = loose
            card(game, "supply", "Getting dressings off the ground", (x, y))
            if _dist(a, x, y) <= 1:
                it = next((i for i in game.map.items_at(x, y)
                           if i.t.kind == "medical" or i.t.tool in ("kit", "antiseptic")), None)
            else:
                it = None
            if it is not None:
                from . import actions as A
                return A.pickup(game, a, it, x, y)
            c = _go(game, a, x, y)
            if c:
                return c

    # a casualty named by a call, or one you can see: the same triage every medic runs
    pid = a.ai.get("patient")
    before = pid
    c = ai.medic_act(game, a, vis, near_enemy)
    if a.ai.get("patient") is not None and a.ai.get("patient") != before:
        o = next((q for q in game.near(a.x, a.y, 50, a.side) if q.id == a.ai.get("patient")), None)
        if o is not None:
            post = MED.nearest_aid(game, a)
            card(game, "triage", f"Going to {game.name_of(o)} - {MED.TRIAGE[MED.triage(o.body)]}",
                 (o.x, o.y), why="an aid post" if post else "")
    elif c:
        o = next((q for q in game.near(a.x, a.y, 4, a.side) if q.id == a.ai.get("patient")), None)
        card(game, "treat", f"Treating {game.name_of(o)}" if o is not None and o is not a else "Treating a casualty")
    if c:
        return c

    # nothing in sight: sweep toward the nearest wounded man you know of (the shouter, the last one seen)
    best = None
    for o in game.actors:
        if o.side != a.side or not o.alive or o.state != "ok" or o is a or o.vehicle is not None:
            continue
        if not o.downed and not MED.needs_care(o.body):
            continue
        if o.ai.get("at_aid") is not None or o.ai.get("carried_by") is not None:
            continue
        d = math.hypot(o.x - a.x, o.y - a.y)
        if d > 70:
            continue
        if best is None or d < best[0]:
            best = (d, o)
    if best is not None:
        o = best[1]
        card(game, "sweep", f"Sweeping for {game.name_of(o)}, down ahead", (o.x, o.y))
        c = _go(game, a, o.x, o.y, stance=1)
        if c:
            return c
    return None


def _engineer(game, a, vis, sq):
    from . import ai
    from . import tiles as T
    m = game.map
    if a.has_tool("wirecutters"):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                x, y = a.x + dx, a.y + dy
                if m.in_bounds(x, y) and T.DEFS[int(m.t[x, y])].key == "wire":
                    card(game, "wire", "Cutting the wire", (x, y))
                    c = ai.engineer_act(game, a, vis, sq)
                    if c:
                        return c
    if a.find(lambda i: i.t.kind == "explosive") is not None:
        card(game, "demolish", "Going in with a charge")
        c = ai.engineer_act(game, a, vis, sq)
        if c:
            return c
    # no target for a charge: wire to clear, or the position to improve
    for r in range(2, 12):
        for dx in range(-r, r + 1):
            for dy in (-r, r):
                x, y = a.x + dx, a.y + dy
                if m.in_bounds(x, y) and T.DEFS[int(m.t[x, y])].key == "wire":
                    card(game, "wire", "Going to the wire", (x, y))
                    c = _go(game, a, x, y, stance=1)
                    if c:
                        return c
                    break
    if sq is not None and sq.rep.get("construction"):
        from .fieldworks import act as build_act
        card(game, "works", "Working on the position")
        c = build_act(game, a, vis)
        if c:
            return c
    return None


def _fitter(game, a, vis):
    from . import maintenance as MT
    best = None
    for v in game.vehicles:
        if v.side != a.side or v.dead or v.abandoned or not MT.repairs(v) and not MT.shells_short(v):
            continue
        d = v.near(a.x, a.y)
        if d > 40:
            continue
        need = len(MT.repairs(v)) * 10 + (MT.shells_short(v) / 20)
        if best is None or need / (1 + d * 0.1) > best[0]:
            best = (need / (1 + d * 0.1), v)
    if best is None:
        return None
    v = best[1]
    jobs = MT.repairs(v)
    if v.near(a.x, a.y) <= 1:
        a.ai["helping"] = v.id
        card(game, "fix", f"Working on the {v.vt.name}" + (f" - {MT.REPAIR_WORD[jobs[0]]}" if jobs else " - rounds"))
        return 100
    a.ai.pop("helping", None)
    card(game, "fix", f"Going to the {v.vt.name}", (v.x, v.y))
    cells = set(v.cells())
    spots = [(cx + dx, cy + dy) for cx, cy in cells for dx in (-1, 0, 1) for dy in (-1, 0, 1)
             if (cx + dx, cy + dy) not in cells and game.map.in_bounds(cx + dx, cy + dy)
             and game.map.walk[cx + dx, cy + dy] and (cx + dx, cy + dy) not in game.vehicle_at]
    if not spots:
        return None
    tx, ty = min(spots, key=lambda q: _dist(a, q[0], q[1]))
    return _go(game, a, tx, ty, stance=1)


def _crew(game, a):
    """On foot between machines: get back to your own tank."""
    best = None
    for v in game.vehicles:
        if v.side != a.side or v.dead or v.abandoned:
            continue
        if v.crew >= v.vt.crew + v.vt.seats and v.vt.seats:
            continue
        d = v.near(a.x, a.y)
        if d > 30:
            continue
        if best is None or d < best[0]:
            best = (d, v)
    if best is None:
        return None
    v = best[1]
    if v.near(a.x, a.y) <= 1:
        from . import actions as A
        c = A.enter_vehicle(game, a, v)
        if c:
            v.player_crewed = False              # (autopilot: the crew keeps the machine, you keep watching)
            card(game, "mount", f"Climbing into the {v.vt.name}")
        return c
    card(game, "mount", f"Going back to the {v.vt.name}", (v.x, v.y))
    cells = set(v.cells())
    spots = [(cx + dx, cy + dy) for cx, cy in cells for dx in (-1, 0, 1) for dy in (-1, 0, 1)
             if (cx + dx, cy + dy) not in cells and game.map.in_bounds(cx + dx, cy + dy)
             and game.map.walk[cx + dx, cy + dy] and (cx + dx, cy + dy) not in game.vehicle_at]
    if not spots:
        return None
    return _go(game, a, *min(spots, key=lambda q: _dist(a, q[0], q[1])))


def _officer(game, a, vis, sq):
    from . import ai
    if sq is not None and sq.leader is a:
        card(game, "lead", "Leading the section")
    else:
        card(game, "lead", "With the command group")
    c = ai.officer_act(game, a, vis, sq)
    if c:
        return c
    if sq is not None and sq.leader is not None and sq.leader is not a and sq.leader.active:
        if _dist(a, sq.leader.x, sq.leader.y) > 3:
            return _go(game, a, sq.leader.x, sq.leader.y, stance=1)
    return None


def _surgeon(game, a, vis):
    from . import medical as MED
    from . import ai
    if not MED.at_aid_post(game, a):
        post = MED.nearest_aid(game, a)
        if post is not None:
            card(game, "post", "Getting back to the aid station", post[:2])
            return _go(game, a, post[0], post[1])
        return None
    card(game, "operate", "At the aid station")
    return ai.surgeon_act(game, a, vis)


ROLE_JOBS = {
    "medic": _medic,
    "surgeon": lambda g, a, v, s, n: _surgeon(g, a, v),
    "engineer": lambda g, a, v, s, n: _engineer(g, a, v, s),
    "seabee": lambda g, a, v, s, n: _engineer(g, a, v, s),
    "motor_sergeant": lambda g, a, v, s, n: _fitter(g, a, v),
    "tank_crew": lambda g, a, v, s, n: None if a.vehicle is not None else _crew(g, a),
    "officer": lambda g, a, v, s, n: _officer(g, a, v, s),
    "squad_leader": lambda g, a, v, s, n: _officer(g, a, v, s),
    "platoon_sergeant": lambda g, a, v, s, n: _officer(g, a, v, s),
    "first_sergeant": lambda g, a, v, s, n: _officer(g, a, v, s),
    "sergeant_major": lambda g, a, v, s, n: _officer(g, a, v, s),
    "radioman": lambda g, a, v, s, n: _officer(g, a, v, s),
}


def act(game, a, vis, sq, sstate, near_enemy):
    """One turn of your trade.  None hands it back to the ordinary soldier AI."""
    if not a.is_player or not game.__dict__.get("autopilot"):
        return None
    after = a.ai.get("after")
    if after is not None and sq is not None:
        from .consolidate import act as lull_act
        labels = {"watch": "Watching the front", "dress": "Seeing to the wounded", "tags": "Taking the tags",
                  "search": "Turning over the enemy dead", "ammo": "Filling pouches"}
        card(game, "lull", labels.get(after[0], "Setting the section right"))
        c = lull_act(game, a, vis, sq)
        if c:
            return c
    c = _survival(game, a, vis, near_enemy)
    if c:
        return c
    job = ROLE_JOBS.get(a.role)
    if job is not None:
        c = job(game, a, vis, sq, near_enemy)
        if c:
            return c
    if near_enemy > 12:
        from .orders import active, navigation
        o = active(game)
        nav = navigation(game) if o is not None else None
        if nav is not None and _dist(a, nav[0], nav[1]) > 2:
            card(game, "orders", f"Your orders: {nav[2]}", nav[:2])
            c = _go(game, a, nav[0], nav[1])
            if c:
                return c
        elif o is None and near_enemy > 30:
            sup = _sup(game, a)
            if sup is not None:
                card(game, "report", f"Reporting to {game.name_of(sup)} for orders", (sup.x, sup.y))
                if _dist(a, sup.x, sup.y) > 1:
                    c = _go(game, a, sup.x, sup.y, stance=1)
                    if c:
                        return c
                return 100
    if a.role in ("rifleman", "smg_gunner", "partisan", "volkssturm"):
        card(game, "fight" if vis and near_enemy < 40 else "march",
             "In the fight" if vis and near_enemy < 40 else "With the section")
    return None
