"""Getting it out of a prisoner.

A prisoner's value is rarely what he says first.  It is his paybook, then his section's position,
then where the machine guns and the anti-tank gun are, then the marked map in his tunic, and - from
the right man - the operation order with the hour on it.

The methods are the ones the war actually used, described in the terms a soldier used: ask him
politely; a cigarette and a light; a mug of something hot; take him away from his mates so he has
only you to talk to; and, when he is frightened or stubborn, "a little pressure".  No lecture on
torture - a frightened man will say anything, and the game shows you which parts are solid and which
he was guessing at.
"""
from __future__ import annotations

from .brain import Contact
from .intelligence import _note

METHODS = {
    "ask": ("Ask him", 250, 0.0, "in his own language if you can"),
    "cigarette": ("A cigarette and a light", 320, 0.18, "needs a cigarette"),
    "brew": ("A mug of something hot", 400, 0.15, "needs a canteen with water"),
    "separate": ("Take him away from his mates", 600, 0.22, "he has only you to talk to"),
    "pressure": ("A little pressure", 500, 0.20, "quick, and he may say anything"),
}

ROLE_VALUE = {"officer": 4, "company_commander": 5, "battalion_commander": 6, "radioman": 4, "intel": 5,
              "squad_leader": 3, "platoon_sergeant": 3, "first_sergeant": 3, "sergeant_major": 4,
              "engineer": 2, "medic": 1, "at_soldier": 2, "mortarman": 2}
RANK_VALUE = [(12, 5), (9, 4), (5, 3), (3, 2)]


def value(game, a) -> int:
    v = ROLE_VALUE.get(a.role, 1)
    for rank, n in RANK_VALUE:
        if a.rank >= rank:
            v = max(v, n)
            break
    if a.ai.get("staff") or a.role in ("officer", "company_commander", "battalion_commander"):
        v = max(v, 5)
    return v


def can(game, p, a) -> bool:
    return (a.alive and a.state == "surrendered" and a.ai.get("captor") == p.id
            and a.body.conscious and not a.downed and not a.vehicle)


def needs(game, a, method) -> bool:
    p = game.player
    if method == "cigarette":
        return p.find(lambda i: i.t.tool == "cigarettes" and i.uses > 0) is not None
    if method == "brew":
        return p.find(lambda i: i.t.tool == "canteen" and i.uses > 0) is not None
    return True


def menu(ps, a):
    from .render import Popup
    g = ps.game
    p = g.player
    intr = a.ai.setdefault("interrogation", dict(rounds=0, methods=[], gave=set(), done=False))
    lines = [(f"{a.rank_full} {a.last_name}, {a.role_name}.", (210, 200, 170))]
    from .data.nations import NATIONS
    worth = "low" if value(g, a) <= 1 else "moderate" if value(g, a) < 4 else "high"
    lines.append((f"{NATIONS[a.nation]['army']}, {a.unit}. Value: {worth}", (190, 185, 160)))
    if a.ai.get("searched"):
        lines.append(("His pockets are out. His paybook is in your hand.", (200, 220, 170)))
    from .skills import level as _sk
    if _sk(p, "languages") < 2.0:
        lines.append(("You have almost no words in common. It will be hands, pointing and pencil.", (220, 170, 140)))
    if intr["rounds"]:
        lines.append((f"You've had {intr['rounds']} go at him. Methods used: " + ", ".join(intr["methods"]),
                      (190, 190, 160)))
    opts = []
    for k, (label, cost, bonus, note) in METHODS.items():
        ok = needs(g, a, k)
        opts.append((f"{label} - {note}", k, (230, 215, 160) if ok else (140, 135, 120), ok))
    opts.append(("Back", "back", None, True))
    from .textfit import wrap as _wrap
    flat = [(w, c) for text, c in lines for w in _wrap(text, 70)]
    ps.open_popup(Popup("Interrogation", opts, ps._screen_anchor(), width=74, lines=flat),
                  lambda v: _do(ps, a, v), cancel=lambda: None)


def _consume(game, p, method):
    if method == "cigarette":
        it = p.find(lambda i: i.t.tool == "cigarettes" and i.uses > 0)
        if it is not None:
            p.consume_use(it)
    elif method == "brew":
        it = p.find(lambda i: i.t.tool == "canteen" and i.uses > 0)
        if it is not None:
            p.consume_use(it)


def _do(ps, a, method):
    g = ps.game
    p = g.player
    if method == "back" or method is None:
        return
    if not needs(g, a, method):
        return
    intr = a.ai.setdefault("interrogation", dict(rounds=0, methods=[], gave=set(), done=False))
    _consume(g, p, method)
    intr["rounds"] += 1
    intr["methods"].append(method)
    from .skills import level, use
    chance = 0.28 + 0.05 * value(g, a) + METHODS[method][2]
    chance += level(p, "languages") * 0.05
    chance += (1 - a.morale / 130.0) * 0.12            # frightened men talk
    chance -= 0.10 * max(0, intr["methods"].count(method) - 1)
    chance += 0.10 if a.body.bleed_rate() > 0.3 else 0
    from . import renown
    chance += renown.prisoner_worth(g)
    if a.side == g.player.side:
        chance *= 0.6
    use(g, p, "languages", 0.1)
    g.msg(f"You {METHODS[method][0].lower()} {a.him}.", "info")
    if g.rng.random() > min(0.92, chance):
        g.msg(g.rng.choice(["He shakes his head.", "He says his name, rank and number, and stops.",
                            "He looks past you and says nothing.", "He shrugs. He has told it all before."]),
              "info")
        ps.act(METHODS[method][1])
        return
    gave = intr["gave"]
    # what he can actually give, in order of what he knows
    if "unit" not in gave and not a.ai.get("searched"):
        gave.add("unit")
        g.msg(f"He gives his unit: {a.unit}.", "good")
    elif "mates" not in gave and value(g, a) <= 2:
        gave.add("mates")
        placed = 0
        for o in g.actors:
            if o.side == a.side and o.alive and o is not a and max(abs(o.x - a.x), abs(o.y - a.y)) <= 40:
                g.brains[p.side].contacts[o.id] = Contact(o.id, o.x, o.y, g.turn, "inf")
                _note(g, p, o.x, o.y, "inf")
                placed += 1
                if placed >= 6:
                    break
        g.msg(f"He points out where his section was: {placed} of them.", "good")
    elif "positions" not in gave:
        gave.add("positions")
        placed = 0
        for rec in g.map.gen_positions:
            if rec.get("side") != a.side or rec.get("destroyed"):
                continue
            if max(abs(rec["x"] - a.x), abs(rec["y"] - a.y)) > 70:
                continue
            g.brains[p.side].contacts[-abs(hash((a.id, placed))) or -1] = Contact(
                -abs(hash((a.id, placed))) or -1, rec["x"], rec["y"], g.turn, rec.get("kind", "inf"))
            _note(g, p, rec["x"], rec["y"], rec.get("kind", "inf"))
            placed += 1
            if placed >= 8:
                break
        g.msg(f"He marks their posts on your map: {placed} of them, he says. Some he is sure of.", "good")
    elif "mines" not in gave and g.map.mines:
        gave.add("mines")
        near = [(x, y) for (x, y) in list(g.map.mines)[:80]
                if max(abs(x - a.x), abs(y - a.y)) <= 60]
        for x, y in near[:12]:
            _note(g, p, x, y, "mine")
            brain = g.brains[p.side]
            brain.contacts[-abs(hash((a.id, x, y))) or -1] = Contact(
                -abs(hash((a.id, x, y))) or -1, x, y, g.turn, "mine")
        g.msg(f"He draws the mine belt in the dirt: {min(len(near), 12)} roughly where he says.", "good")
    elif "map" not in gave and value(g, a) >= 3:
        gave.add("map")
        from .entities import Item
        it = Item("marked_map")
        it.data = dict(side=a.side, written=g.turn, unit=a.unit,
                       positions=[(o.id, o.x, o.y) for o in g.actors
                                  if o.side == a.side and o.alive][:40])
        p.invent.add(it, prefer="pack")
        g.msg("He gives up his marked map. It is going in your pocket.", "good")
        g.command.merit += 2
    elif "orders" not in gave and value(g, a) >= 4:
        gave.add("orders")
        g.__dict__["enemy_plan_warning"] = dict(turn=g.turn, side=a.side, sector=(g.sector.x, g.sector.y))
        # the road he names: the nearest running toward their own rear
        home = g.home_edge(a.side)
        road = None
        for r in range(6, 60):
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                x, y = a.x + dx * r, a.y + dy * r
                if g.map.in_bounds(x, y) and g.map.tile(x, y).key == "road":
                    road = (x, y)
                    break
            if road:
                break
        if road:
            _note(g, p, road[0], road[1], "attack")
        g.msg("He has the operation order in his head: the counter-attack is expected within the hour, "
              "along the road" + (" - it's marked now" if road else "") +
              ". You should get this back to intelligence.", "good")
        g.command.merit += 4
        intr["done"] = True
    else:
        gave.add("again")
        g.msg("He has nothing more you can use.", "info")
        intr["done"] = True
    if intr["done"]:
        g.command.merit += 1
    ps.act(METHODS[method][1] + 120)
