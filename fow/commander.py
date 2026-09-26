"""Side commanders: objective control and squad orders."""
from __future__ import annotations

from .ai import Order
from .constants import SIDES, other_side


def update_objectives(game, interval: int):
    m = game.map
    for i, o in enumerate(m.objectives):
        present = {s: 0 for s in SIDES}
        r2 = o.radius * o.radius
        for a in game.actors:
            if not a.active or a.downed or a.vehicle is not None:
                continue
            if (a.x - o.x) ** 2 + (a.y - o.y) ** 2 <= r2:
                present[a.side] += 1
        for v in game.vehicles:
            if v.active and (v.x - o.x) ** 2 + (v.y - o.y) ** 2 <= r2:
                present[v.side] += 2
        sides_here = [s for s in SIDES if present[s] > 0]
        o.contested = len(sides_here) == 2
        if len(sides_here) == 1:
            s = sides_here[0]
            if o.owner != s:
                o.hold_time += interval
                if o.hold_time >= 20:
                    prev = o.owner
                    o.owner = s
                    o.hold_time = 0
                    game.on_objective_taken(i, s, prev)
            else:
                o.hold_time = 0
        elif not sides_here:
            o.hold_time = 0


def commander_update(game, side: str):
    squads = [sq for sq in game.squads if sq.side == side and (sq.members or sq.vehicles)]
    if not squads:
        return
    m = game.map
    objs = m.objectives
    if not objs:
        return
    enemy = other_side(side)
    attacker = game.attacker
    my_str = sum(sq.strength() for sq in squads)
    en_str = sum(sq.strength() for sq in game.squads if sq.side == enemy)
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
    for sq in squads:
        if sq.player_led or sq.order.kind == "retreat" or getattr(sq.order, "src", "ai") == "player":
            continue
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
        o = sq.order
        if side == attacker or game.attacker is None:
            targets = [i for i, ob in enumerate(objs) if ob.owner != side]
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
            best = min(targets, key=lambda i: ((objs[i].x - anc[0]) ** 2 + (objs[i].y - anc[1]) ** 2) ** 0.5
                       + 35 * load[i] - 45 * mates.get(i, 0) + rng.random() * 10)
            if o.obj is not None and o.obj in load:
                load[o.obj] -= 1
            load[best] += 1
            sq.order = Order("attack", obj=best, radius=objs[best].radius, issued=game.turn)
            sq.arrived = False
        else:
            # defender
            if o.kind == "defend" and o.obj is not None and objs[o.obj].owner == enemy:
                # lost it - counterattack if strong enough, else fall back to another
                if sq.morale > 40 and sq.strength() >= 4 and rng.random() < 0.6:
                    sq.order = Order("attack", obj=o.obj, radius=objs[o.obj].radius, issued=game.turn)
                    sq.arrived = False
                    continue
                mine = [i for i, ob in enumerate(objs) if ob.owner == side]
                if mine:
                    best = min(mine, key=lambda i: (objs[i].x - anc[0]) ** 2 + (objs[i].y - anc[1]) ** 2)
                    sq.order = Order("defend", obj=best, radius=objs[best].radius, issued=game.turn)
                    sq.arrived = False
                continue
            if o.kind == "attack" and o.obj is not None and objs[o.obj].owner == side:
                sq.order = Order("defend", obj=o.obj, radius=objs[o.obj].radius, issued=game.turn)
                continue
            if o.kind in ("hold", "move") and sq.kind not in ("mg", "mortar", "sniper", "hq", "atgun"):
                best = min(range(len(objs)), key=lambda i: load[i] * 40 +
                           ((objs[i].x - anc[0]) ** 2 + (objs[i].y - anc[1]) ** 2) ** 0.5)
                load[best] += 1
                sq.order = Order("defend", obj=best, radius=objs[best].radius, issued=game.turn)
                sq.arrived = False
