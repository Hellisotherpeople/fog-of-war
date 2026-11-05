"""The trade, as an order: the things a good specialist does without being told twice.

Leaders don't only shout 'follow me'.  They use the man for what he is: the medic is sent to the man
bleeding behind the hedge, the sapper to the wire, the fitter to the thrown track.  These are real orders
in the same book as any other - who gave it, how long you have, what it's worth - and the man who does
them is known by his trade, which is how specialists get made up.

The role AI does much of this on its own.  This is the part with a name attached to it, and a sergeant
watching whether you did it.
"""
from __future__ import annotations

# (kind, who, words, how long, worth)
DUTIES = {
    "medic": ("evac", "restock", "help"),
    "surgeon": ("restock",),
    "engineer": ("wire", "charge"),
    "seabee": ("wire", "charge"),
    "motor_sergeant": ("recover", "track"),
    "tank_crew": ("track",),
    "radioman": ("relay",),
    "officer": ("rally",),
    "squad_leader": ("rally",),
    "platoon_sergeant": ("rally",),
    "first_sergeant": ("rally",),
}


def _count(game, a, pred) -> int:
    return sum(1 for i in a.inv if pred(i))


def _medical(a) -> int:
    return _count(None, a, lambda i: i.t.kind == "medical" or i.t.tool == "antiseptic")


def find(game, role, sup):
    """A trade duty worth giving right now: (kind, target, data) or None."""
    p = game.player
    if p.role != role:
        return None
    kinds = DUTIES.get(role, ())
    if not kinds:
        return None
    from . import medical as MED
    # a stable casualty who can't walk, and an aid post to take him to
    if "evac" in kinds and p.carrying is None and MED.nearest_aid(game, p) is not None:
        for o in game.near(p.x, p.y, 16, p.side):
            if o is p or not o.alive or o.state != "ok" or o.vehicle is not None:
                continue
            if not o.downed or o.ai.get("carried_by") is not None or o.ai.get("at_aid") is not None:
                continue
            if o.body.bleed_rate() > 0.4:
                continue
            return "evac", o.id, dict(need=1)
    # empty pouches, and the aid post has stock
    if "restock" in kinds and _medical(p) < 2:
        post = MED.nearest_aid(game, p)
        if post is not None and max(abs(post[0] - p.x), abs(post[1] - p.y)) <= 30:
            return "restock", (post[0], post[1]), {}
    # wire
    if "wire" in kinds and p.has_tool("wirecutters"):
        from . import tiles as T
        m = game.map
        best = None
        for dx in range(-10, 11):
            for dy in range(-10, 11):
                x, y = p.x + dx, p.y + dy
                if not m.in_bounds(x, y) or T.DEFS[int(m.t[x, y])].key != "wire":
                    continue
                d = abs(dx) + abs(dy)
                if best is None or d < best[0]:
                    best = (d, x, y)
        if best is not None:
            return "wire", best[1:], {}
    # a charge, on something worth it
    if "charge" in kinds and p.find(lambda i: i.t.kind == "explosive") is not None:
        for e in game.seen_enemies(14):
            if getattr(e, "vt", None) is not None and not e.dead:
                return "charge", (e.x, e.y), dict(vid=e.id)
        from . import tiles as T
        m = game.map
        for dx in range(-14, 15):
            for dy in range(-14, 15):
                x, y = p.x + dx, p.y + dy
                if m.in_bounds(x, y) and "bunker" in T.DEFS[int(m.t[x, y])].key:
                    return "charge", (x, y), {}
    # a broken vehicle, and this man's the fitter
    if "recover" in kinds:
        from . import maintenance as MT
        best = None
        for v in game.vehicles:
            if v.side != p.side or v.dead or v.abandoned:
                continue
            jobs = MT.repairs(v)
            if not jobs:
                continue
            d = v.near(p.x, p.y)
            if d <= 30 and (best is None or d < best[0]):
                best = (d, v, jobs[0])
        if best is not None:
            return "recover", (best[1].x, best[1].y), dict(vid=best[1].id, job=best[2])
    # a message, when the radio's no good to them
    if "relay" in kinds:
        sq = p.squad
        if sq is not None and game.turn - sq.last_contact > 90:
            others = [q for q in game.squads if q.side == p.side and q is not sq and q.members and
                      q.anchor() is not None and abs(q.anchor()[0] - p.x) + abs(q.anchor()[1] - p.y) < 45]
            if others:
                q = min(others, key=lambda q: abs(q.anchor()[0] - p.x) + abs(q.anchor()[1] - p.y))
                return "relay", q.leader.id if q.leader is not None else q.anchor(), {}
    # a shaken man who needs a hand on the shoulder
    if "rally" in kinds:
        for o in game.near(p.x, p.y, 8, p.side):
            if o is not p and o.alive and o.morale < 35 and o.suppression > 45:
                return "rally", o.id, {}
    return None


def check(game, t) -> bool:
    """Is it done?  (False also means 'not this kind'.)"""
    p = game.player
    k = t["kind"]
    tgt = t.get("target")
    if k == "evac":
        a = _actor(game, tgt)
        if a is None or not a.alive:
            return bool(t.get("tried"))
        return a.ai.get("at_aid") is not None or a.ai.get("carried_by") is not None
    if k == "restock":
        return _medical(p) >= 3
    if k == "wire":
        from . import tiles as T
        m = game.map
        x, y = (tgt[0], tgt[1]) if isinstance(tgt, (tuple, list)) else (p.x, p.y)
        return not any(m.in_bounds(p.x + dx, p.y + dy) and
                       T.DEFS[int(m.t[p.x + dx, p.y + dy])].key == "wire"
                       for dx in (-1, 0, 1) for dy in (-1, 0, 1))
    if k == "charge":
        return p.ai.get("last_charge", -1) >= t["issued"]
    if k == "recover":
        from . import maintenance as MT
        v = next((v for v in game.vehicles if v.id == t.get("vid")), None)
        if v is None or v.dead or v.abandoned:
            return False
        return t.get("job") not in MT.repairs(v)
    if k == "relay":
        a = _actor(game, tgt) if not isinstance(tgt, (tuple, list)) else None
        if a is not None:
            return max(abs(a.x - p.x), abs(a.y - p.y)) <= 2
        if isinstance(tgt, (tuple, list)):
            return max(abs(tgt[0] - p.x), abs(tgt[1] - p.y)) <= 3
        return False
    if k == "rally":
        a = _actor(game, tgt)
        return a is None or not a.alive or (a.suppression < 25 and a.morale > 35)
    return False


def _actor(game, aid):
    return next((a for a in game.actors if a.id == aid), None)


def credit(game, kind) -> None:
    """The record knows what a man is for."""
    tr = game.__dict__.setdefault("trade", {})
    tr[kind] = tr.get(kind, 0) + 1
    game.command.merit += 1.5 if kind in ("evac", "charge", "recover") else 1.0


def summary(game) -> list[str]:
    tr = game.__dict__.get("trade") or {}
    words = {"evac": "casualties carried out", "restock": "dressings drawn", "wire": "wire cut",
             "charge": "charges placed", "recover": "vehicles put right", "relay": "messages carried",
             "rally": "men steadied", "help": "comrades dressed"}
    return [f"{n} {words.get(k, k)}" for k, n in sorted(tr.items()) if n]
