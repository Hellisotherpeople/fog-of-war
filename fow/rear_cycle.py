"""The rear keeps the line alive: hot food, full canteens, and relief.

A company cannot fight for ever.  The field kitchen at the dump is a real cook with real rations, and men
down from the line get a hot meal and their canteens filled before they go back.  A section that has been
in it too long, is blown, and is down to a handful is relieved by a fresh one when there is a fresh one to
spare - the fresh men take over the ground and the fought-out men walk back.

Everything is counted: the rations come off the sector's food, the relieving section has to exist and be
nearby.  Relief is for AI-led sections on both sides; the player's own section is relieved by its chain of
command only if the player isn't leading it.
"""
from __future__ import annotations

from .constants import SIDES

FEED_RADIUS = 9
FED_TURNS = 3600
ROTATE_CONTACT = 900          # a quarter of an hour under fire
ROTATE_REST = 1800            # and the relief holds for half an hour before it can be swapped again


def _kitchens(game, side):
    for rec in getattr(game.map, "gen_positions", None) or []:
        if rec.get("side") == side and not rec.get("destroyed") and rec.get("kind") in (
                "depot", "food_depot", "hq"):
            yield rec


def feed(game) -> None:
    """The cooks dish up.  A man with a full belly and a full canteen fights better than one without."""
    from .sustain import stores, take
    for side in SIDES:
        cooks = [a for a in game.actors if a.side == side and a.alive and a.state == "ok" and
                 a.role in ("cook",) and not a.ai.get("civilian")]
        if not cooks:
            continue
        for cook in cooks:
            if game.turn - cook.ai.get("fed_turn", -9999) < 300:
                continue
            near_food = any(max(abs(cook.x - r["x"]), abs(cook.y - r["y"])) <= 6 for r in _kitchens(game, side))
            if not near_food:
                continue
            fed = 0
            p = game.player
            men = sorted(game.near(cook.x, cook.y, FEED_RADIUS, side),
                         key=lambda m: (m is not p, m.id))
            for m in men:
                if fed >= 12 or m is cook or not m.alive or m.state != "ok" or m.vehicle is not None:
                    continue
                if game.turn - m.ai.get("fed_turn", -9999) < FED_TURNS:
                    continue
                sec = game.sector_for(m)
                if stores(sec, side)["food"] < 0.1 or not take(sec, side, "food", 0.1):
                    break
                need = m.ai.setdefault("needs", dict(hunger=0., thirst=0., infection=0.))
                need["hunger"] = max(0.0, need["hunger"] - 30)
                need["thirst"] = max(0.0, need["thirst"] - 15)
                m.morale = min(100.0, m.morale + 1.5)
                m.fatigue = max(0.0, m.fatigue - 0.5)
                m.ai["fed_turn"] = game.turn
                fed += 1
            if fed:
                cook.ai["fed_turn"] = game.turn
                p = game.player
                if p is not None and p.side == side and max(abs(p.x - cook.x), abs(p.y - cook.y)) <= FEED_RADIUS:
                    game.msg(f"{cook.last_name} ladles out a hot meal and fills canteens. "
                             f"'Get it down you. You've got ten minutes.'", "good")


def rotate(game) -> None:
    """A section that has had enough is relieved by a fresh one, if there is one."""
    for side in SIDES:
        idle = [q for q in game.squads if q.side == side and q.members and not q.gone and not q.player_led and
                q.order.kind in ("hold", "defend", "idle") and q.anchor() is not None and
                q.strength() >= 5 and q.__dict__.get("initial", 0) and q.morale > 35 and
                game.turn - q.last_contact > 120 and not q.rep.get("relieved")]
        if not idle:
            continue
        for sq in list(game.squads):
            if sq.side != side or not sq.members or sq.gone or sq.player_led or sq.rep.get("relieved"):
                continue
            if game.turn - sq.last_contact < ROTATE_CONTACT:
                continue
            if sq.strength() > max(3, sq.__dict__.get("initial", 9) * 0.5):
                continue
            anc = sq.anchor()
            if anc is None:
                continue
            fresh = min(idle, key=lambda q: max(abs(q.anchor()[0] - anc[0]), abs(q.anchor()[1] - anc[1])))
            if max(abs(fresh.anchor()[0] - anc[0]), abs(fresh.anchor()[1] - anc[1])) > 45:
                continue
            # swap them over: the fresh section takes the ground and the order
            from .ai import Order
            fresh.order = Order(sq.order.kind, target=sq.order.target, obj=sq.order.obj,
                                radius=sq.order.radius, issued=game.turn, roe=sq.order.roe)
            fresh.arrived = False
            fresh.rep["relieved"] = game.turn + ROTATE_REST
            sq.order = Order("move", target=anc, radius=8, issued=game.turn)
            sq.arrived = False
            sq.rep["relieved"] = game.turn + ROTATE_REST
            sq.rep["relieved_by"] = fresh.id
            idle.remove(fresh)
            p = game.player
            if p is not None and (sq is p.squad or (p.squad is not None and sq.side == p.side and
                                                    max(abs(anc[0] - p.x), abs(anc[1] - p.y)) < 25)):
                game.msg(f"{fresh.name} comes up through you to take the ground over: you're relieved. "
                         f"Get back, get fed, and get your heads down.", "good")
            net = getattr(game, "opponents", None)
            if net is not None:
                from .opponent import net as say_net
                say_net(game, side, f"{sq.name.casefold()} relieved by {fresh.name.casefold()}; lines hold.")
            if not idle:
                break


def tick(game) -> None:
    if game.map is None or game.domain != "land":
        return
    if game.turn % 60 == 0:
        feed(game)
        rotate(game)
