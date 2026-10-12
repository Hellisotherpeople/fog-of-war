"""Side commanders: objective control and squad orders."""
from __future__ import annotations

from .ai import Order
from .constants import SIDES, other_side


def _presence(game, ob):
    present = {s: 0 for s in SIDES}
    r2 = ob.radius * ob.radius
    for a in game.near(ob.x, ob.y, ob.radius):
        if not a.active or a.downed or a.vehicle is not None or a.ai.get("civilian"):
            continue
        if (a.x - ob.x) ** 2 + (a.y - ob.y) ** 2 <= r2:
            present[a.side] += 1
    for v in game.vehicles:
        if v.active and (v.x - ob.x) ** 2 + (v.y - ob.y) ** 2 <= r2:
            present[v.side] += 2
    return present


def consolidate_objective(game, sq, index=None):
    """Recognize secured ground locally; neither a capture award nor a radio transmission."""
    from .intelligence import local_objective_owner
    o = sq.order
    if index is None:
        if o.kind not in ("attack", "assault"):
            return False
        index = o.obj
    if index is None or not 0 <= index < len(game.map.objectives):
        return False
    ob = game.map.objectives[index]
    if ob.owner != sq.side or ob.contested or local_objective_owner(game, sq, index) != sq.side:
        return False
    # Squad updates can run between the five-second capture checks. An enemy who
    # just entered the area still contests it, even before ob.contested is refreshed.
    if _presence(game, ob)[other_side(sq.side)]:
        return False
    intent = sq.rep.get("intent")
    if intent and intent.get("mission") == "seize" and tuple(intent["target"]) == ob.pos:
        intent["completed"] = True
    game.command.apply(game, sq, Order("defend", obj=index, radius=ob.radius,
                                      issued=game.turn, src=o.src, roe=o.roe))
    sq.rep["objective_secured_turn"] = game.turn
    sq.rep["initiative_note"] = f"{ob.name.capitalize()} secured; holding the ground."
    if sq is game.player.squad:
        game.msg(f"Your section has secured {ob.name} and is holding the position.", "good")
        game.update_orders(force=True)
    return True


def update_objectives(game, interval: int):
    m = game.map
    for i, o in enumerate(m.objectives):
        present = _presence(game, o)
        sides_here = [s for s in SIDES if present[s] > 0]
        o.contested = len(sides_here) == 2
        if len(sides_here) == 1:
            s = sides_here[0]
            if o.owner != s:
                if getattr(o, "capturing_side", None) != s:
                    o.hold_time = 0
                o.capturing_side = s
                o.hold_time += interval
                if o.hold_time >= 20:
                    prev = o.owner
                    o.owner = s
                    o.hold_time = 0
                    o.capturing_side = None
                    game.on_objective_taken(i, s, prev)
            else:
                o.hold_time = 0
                o.capturing_side = None
        else:
            o.hold_time = 0
            o.capturing_side = None


def commander_update(game, side: str):
    squads = [sq for sq in game.squads if sq.side == side and (sq.members or sq.vehicles)]
    if not squads:
        return
    m = game.map
    objs = m.objectives
    if not objs:
        return
    from .intelligence import objective_owner, local_objective_owner, distance
    observers = game.near_people_many([(o.x, o.y, o.radius + 6) for o in objs])
    owners = {i: objective_owner(game, side, i, observers[i]) for i in range(len(objs))}
    enemy = other_side(side)
    attacker = game.attacker
    my_str = sum(sq.strength() for sq in squads)
    en_str = sum(c.threat for c in game.brains[side].live_contacts(120, False))
    init = game.initial_strength.get(side, 1)
    # general withdrawal
    if my_str < init * 0.25 and en_str > my_str * 2.5 and game.turn > 300:
        if not game.withdrawing.get(side):
            game.withdrawing[side] = True
            game.on_withdrawal(side)
        top = getattr(game, "command", None)
        player_top = top is not None and side == game.player_side and top.is_top_commander(game)
        for sq in squads:
            if sq.player_led or (player_top and getattr(sq.order, "src", "ai") == "player"):
                continue            # the player decides whether their men pull out
            sq.order = Order("retreat", issued=game.turn)
        return
    load = {i: 0 for i in range(len(objs))}
    for sq in squads:
        if sq.order.obj is not None and sq.order.obj in load:
            load[sq.order.obj] += 1
    rng = game.rng
    from .command import low_on_ammo, nearest_ammo
    held = _strength_at(game, side, objs)
    for sq in squads:
        if sq.player_led or sq.order.kind == "retreat" or getattr(sq.order, "src", "ai") == "player":
            continue
        if sq.rep.get("construction") or sq.order.src == "staff":
            continue
        if sq.kind in ("staff", "rear", "aid", "supply") or sq.__dict__.get("convoy"):
            continue                # quartermasters, clerks and surgeons stay at their posts; trucks do their run
        if sq.order.kind == "resupply" and game.turn - sq.order.issued < 500:
            continue
        # quiet moment and the pouches are empty: back to the dump
        if game.turn - sq.last_contact > 60 and sq.members and low_on_ammo(sq):
            q = nearest_ammo(game, sq, max_d=70)
            if q is not None:
                sq.order = Order("resupply", target=q, radius=3, issued=game.turn)
                sq.arrived = False
                continue
        anc = sq.anchor()
        if anc is None:
            continue
        if consolidate_objective(game, sq):
            continue
        o = sq.order
        if (o.kind == "defend" and o.obj is not None and not objs[o.obj].contested
                and objs[o.obj].owner == side
                and game.turn - sq.rep.get("objective_secured_turn", -999) < 60):
            continue
        # This unit's own observations can correct its instructions without revealing them
        # to other units. In particular, an unknown HQ report is not an order to retake
        # friendly ground that the section can see it already holds.
        local_owners = dict(owners)
        for i, ob in enumerate(objs):
            if distance(anc, ob.pos) <= ob.radius + 18:
                local = local_objective_owner(game, sq, i)
                if local is not None:
                    local_owners[i] = local
        if side == attacker or game.attacker is None:
            targets = [i for i, ob in enumerate(objs) if local_owners[i] != side]
            if not targets:
                # everything taken: consolidate
                if o.kind != "defend":
                    best = min(range(len(objs)), key=lambda i: (objs[i].x - anc[0]) ** 2 + (objs[i].y - anc[1]) ** 2)
                    sq.order = Order("defend", obj=best, radius=objs[best].radius, issued=game.turn)
                    sq.arrived = False
                continue
            if o.kind == "attack" and o.obj in targets and game.turn - o.issued < 900:
                continue
            # platoons fight together: prefer the objective the rest of the platoon is going for
            mates = {}
            f = getattr(sq, "formation", None)
            if f is not None and f.echelon == "platoon":
                for o2 in f.squads:
                    if o2 is not sq and not o2.gone and o2.order.kind == "attack" and o2.order.obj is not None:
                        mates[o2.order.obj] = mates.get(o2.order.obj, 0) + 1
            # where they're weakest, and a real weight of attack there (a Schwerpunkt, not a squad at every
            # objective): what we know is holding each one, and up to three squads together
            best = min(targets, key=lambda i: ((objs[i].x - anc[0]) ** 2 + (objs[i].y - anc[1]) ** 2) ** 0.5
                       + 5 * held[i] - 14 * min(3, load[i]) + 35 * max(0, load[i] - 3)
                       - 45 * mates.get(i, 0) + rng.random() * 10)
            if o.obj is not None and o.obj in load:
                load[o.obj] -= 1
            load[best] += 1
            sq.order = Order("attack", obj=best, radius=objs[best].radius, issued=game.turn)
            sq.arrived = False
        else:
            # defender
            if o.kind == "defend" and o.obj is not None and local_owners[o.obj] == enemy:
                # lost it - counterattack at once, before they've dug in, if what's left of us here can beat
                # what we know is there (the German Gegenstoss); else fall back to another
                near = [q for q in squads if q.order.obj == o.obj and q.anchor() is not None]
                ours = sum(q.strength() for q in near)
                if sq.morale > 30 and sq.strength() >= 3 and ours >= held[o.obj] * 1.2:
                    sq.order = Order("attack", obj=o.obj, radius=objs[o.obj].radius, issued=game.turn)
                    sq.arrived = False
                    continue
                mine = [i for i, ob in enumerate(objs) if local_owners[i] == side]
                if mine:
                    best = min(mine, key=lambda i: (objs[i].x - anc[0]) ** 2 + (objs[i].y - anc[1]) ** 2)
                    sq.order = Order("defend", obj=best, radius=objs[best].radius, issued=game.turn)
                    sq.arrived = False
                continue
            if o.kind == "attack" and o.obj is not None and local_owners[o.obj] == side:
                sq.order = Order("defend", obj=o.obj, radius=objs[o.obj].radius, issued=game.turn)
                continue
            if o.kind in ("hold", "move") and sq.kind not in ("mg", "mortar", "sniper", "hq", "atgun"):
                best = min(range(len(objs)), key=lambda i: load[i] * 40 +
                           ((objs[i].x - anc[0]) ** 2 + (objs[i].y - anc[1]) ** 2) ** 0.5)
                load[best] += 1
                sq.order = Order("defend", obj=best, radius=objs[best].radius, issued=game.turn)
                sq.arrived = False

    from .intent import defaults
    for sq in squads:
        defaults(game, sq)


def _strength_at(game, side, objs) -> dict:
    """How much of the enemy this side knows is at each objective (its contacts there, weighted)."""
    brain = game.brains[side]
    out = {i: 0.0 for i in range(len(objs))}
    cs = brain.live_contacts(60, False)
    for i, ob in enumerate(objs):
        r2 = (ob.radius + 10) ** 2
        out[i] = sum(min(4.0, c.threat) for c in cs if (c.x - ob.x) ** 2 + (c.y - ob.y) ** 2 <= r2)
    return out
