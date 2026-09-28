"""Jobs your men do between the fighting.

A leader doesn't only point at hedgerows.  When it goes quiet he sends men round the dead for the
rounds and grenades they won't need, for field dressings and morphine, for the papers and maps an
intelligence officer will pay for; he has the wounded carried back to the aid post; he has the men
who threw their hands up searched and marched to the rear; he lends the tank crews a few backs.

A task is set on the squad (squad.task) by an order - your own squad's ('O'), or any unit you can
reach ('C', through the same voices, signals, radio and runners as any other order).  Each man
works at it on his own when there's no enemy close, and stops to fight when there is; the squad's
leader reports what they found when it's done.  Everything taken is really taken: out of the dead
men's webbing and off the ground, into the finders' own.
"""
from __future__ import annotations

import math
from collections import Counter

RADIUS = 30               # tiles from the squad they'll go looking
DURATION = 900            # a quarter of an hour, then back to the war
CLOSE = 12                # an enemy nearer than this and it's rifles, not errands

TASKS = {
    "ammo": ("Scavenge for ammunition", "scrounge ammunition off the dead"),
    "medical": ("Scavenge for field dressings and morphine", "find dressings and medical kit"),
    "weapons": ("Scavenge for grenades and weapons", "pick up grenades and any weapons"),
    "papers": ("Search the enemy dead for papers and maps", "search the enemy dead for papers"),
    "casevac": ("Carry the wounded back to the aid post", "get the wounded back"),
    "prisoners": ("Search the men who've surrendered and march them back", "take the prisoners back"),
    "repair": ("Give the tank crews a hand", "give the tankers a hand"),
}
SCAVENGE = ("ammo", "medical", "weapons", "papers")


# ============================================================================ what's out there
def _wanted(kind, it, man) -> bool:
    t = it.t
    if kind == "ammo":
        w = man.weapon
        if t.kind == "grenade":
            return True
        if w is None or t.kind not in ("ammo", "mag", "clip"):
            return False
        from .ammo import compatible
        return compatible(it, w) and (t.kind != "mag" or it.loaded > 0)
    if kind == "medical":
        return t.kind == "medical"
    if kind == "weapons":
        return t.kind in ("grenade", "explosive") or (t.kind == "gun" and (man.weapon is None or man.weapon.t.kind != "gun"))
    if kind == "papers":
        return t.tool in ("document", "orders", "map") or it.tid == "paybook"
    return False


def _piles(game, kind, man, x0, y0, r=RADIUS):
    """Spots within reach with something he wants: (distance, x, y) nearest first - loose kit on the ground,
    and the dead (the enemy's, for papers; anyone's, for the rest)."""
    m = game.map
    out = []
    for (x, y), items in list(getattr(m, "items", {}).items()):
        if abs(x - x0) > r or abs(y - y0) > r:
            continue
        for it in items:
            if it.t.kind == "corpse":
                d = it.data or {}
                if kind == "papers" and d.get("side") == man.side:
                    continue
                inv = d.get("inv")
                if inv is not None and any(_wanted(kind, i, man) for i in inv.items()):
                    out.append((math.hypot(x - man.x, y - man.y), x, y))
                    break
            elif _wanted(kind, it, man):
                out.append((math.hypot(x - man.x, y - man.y), x, y))
                break
    out.sort()
    return out


def available(game, sq, origin):
    """For the menu: how much of each job there is within reach of the unit - {kind: (number, words)}."""
    from . import maintenance as MT
    ox, oy = origin
    side = sq.side
    man = next((a for a in sq.members if a.active and not a.is_player), None) or \
        next((a for a in sq.members if a.active), None)
    out = {}
    if man is not None:
        for k in SCAVENGE:
            n = len(_piles(game, k, man, ox, oy))
            out[k] = (n, f"{n} bod{'y' if n == 1 else 'ies'} or pile{'s' if n != 1 else ''} within reach" if n
                      else "nothing within reach")
    wounded = [a for a in game.actors if a.side == side and a.alive and a.downed and a.vehicle is None and
               a.ai.get("carried_by") is None and a.ai.get("at_aid") is None and
               math.hypot(a.x - ox, a.y - oy) <= RADIUS + 10]
    out["casevac"] = (len(wounded), f"{len(wounded)} wounded down" if wounded else "no wounded down near them")
    pws = [a for a in game.actors if a.alive and a.state == "surrendered" and a.side != side and
           math.hypot(a.x - ox, a.y - oy) <= RADIUS and _unguarded(game, a)]
    out["prisoners"] = (len(pws), f"{len(pws)} with their hands up" if pws else "nobody's surrendered near them")
    veh = [v for v in game.vehicles if v.side == side and not v.dead and not v.abandoned and
           math.hypot(v.x - ox, v.y - oy) <= RADIUS and _needs_hands(v, game)]
    out["repair"] = (len(veh), f"the {veh[0].vt.name}" if veh else "no vehicle needs a hand")
    if not _workers(sq):
        out = {k: (0, "no men on foot to send") for k in TASKS}
    from . import medical as MED
    if out["casevac"][0] and not MED.aid_posts(game, side):
        n = out["casevac"][0]
        out["casevac"] = (n, f"{n} wounded down - no aid post here: out of the line of fire, then")
    return out


def _needs_hands(v, game) -> bool:
    """A track to put back on (any backs will do) - or rounds to pass up, if there are rounds to hand."""
    from . import maintenance as MT
    return "track" in MT.repairs(v) or (MT.shells_short(v) > 0 and
                                         (v.ai.get("rearming") or MT.source(game, v) is not None))


def _unguarded(game, pw) -> bool:
    """Nobody's taken charge of him (or whoever did is gone, or it's you and you've walked off)."""
    cap = pw.ai.get("captor")
    if cap is None:
        return True
    c = next((o for o in game.actors if o.id == cap), None)
    return c is None or not c.active or (c.is_player and max(abs(c.x - pw.x), abs(c.y - pw.y)) > 20)


# ============================================================================ giving the job
def menu_options(game, sq, origin):
    """The task list for a unit: [(label, kind, colour, enabled)] - greyed where there's nothing to do."""
    av = available(game, sq, origin)
    opts = []
    for k, (label, _say) in TASKS.items():
        n, words = av.get(k, (0, ""))
        opts.append((f"{label} ({words})", k, (220, 200, 140) if n else None, n > 0))
    if sq.__dict__.get("task") is not None:
        opts.append(("Stop what you're doing - back to your places", "stop", None, True))
    return opts


def assign(game, sq, kind, by=None):
    """Set a unit to a job.  The rest of its men hold where they are while the job's done."""
    from .ai import Order
    for a in sq.members:
        for k in ("task_pile", "task_done", "task_pw", "task_wounded", "task_bring"):
            a.ai.pop(k, None)
    anc = sq.anchor()
    sq.__dict__["task"] = dict(kind=kind, until=game.turn + DURATION, by=getattr(by, "id", None), found=Counter(),
                               start=game.turn, home=anc)
    if kind == "repair":
        from . import maintenance as MT
        needy = [v for v in game.vehicles if v.side == sq.side and not v.dead and not v.abandoned and
                 _needs_hands(v, game)]
        if anc is not None and needy:
            v = min(needy, key=lambda v: abs(v.x - anc[0]) + abs(v.y - anc[1]))
            sq.order = Order("hold", target=(v.x, v.y), radius=5, issued=game.turn, src="player")
            sq.__dict__["help_v"] = v.id
            sq.arrived = False
            sq.positions = {}
        sq.task["issued"] = sq.order.issued
        return
    if anc is not None and not sq.player_led:
        sq.order = Order("hold", target=anc, radius=8, issued=game.turn, src="player", roe=sq.order.roe)
        sq.arrived = True
    sq.task["issued"] = sq.order.issued


def _workers(sq):
    """Who goes: not the leader, not the gun team's gunner - and never more than half the squad for carrying."""
    return [a for a in sq.members if a.active and not a.downed and not a.is_player and a.vehicle is None
            and a is not sq.leader and a.role not in ("lmg_gunner", "hmg_gunner", "radioman")]


# ============================================================================ doing it
def act(game, a, vis, sq) -> int | None:
    """One man's part in his squad's task, or None to get on with the war."""
    t = sq.__dict__.get("task")
    if t is None or a.is_player:
        return None
    if game.turn > t["until"]:
        finish(game, sq, "time")
        return None
    if "issued" in t and sq.order.issued != t["issued"]:
        finish(game, sq, "orders")                   # new orders: the job's dropped
        return None
    if vis and min(math.hypot(e.x - a.x, e.y - a.y) for e in vis) < CLOSE:
        return None                                  # fight first; the job keeps
    if a not in _workers(sq) or a.ai.get("task_done"):
        _maybe_finished(game, sq)
        return None
    k = t["kind"]
    if k == "drop":
        return _gather_drop(game, a, sq, t)
    if k in SCAVENGE:
        return _scavenge(game, a, sq, t)
    if k == "casevac":
        return _casevac(game, a, sq, t)
    if k == "prisoners":
        return _prisoners(game, a, sq, t)
    _maybe_finished(game, sq)                        # (repair: maintenance.help_act does the work)
    return None


def _scavenge(game, a, sq, t):
    from . import actions as A
    k = t["kind"]
    home = t.get("home") or sq.anchor() or (a.x, a.y)
    if a.ai.get("task_bring"):
        return _bring_papers(game, a, sq, t)
    tgt = a.ai.get("task_pile")
    if tgt is None:
        piles = [pp for pp in _piles(game, k, a, home[0], home[1])
                 if not any(o is not a and o.ai.get("task_pile") == (pp[1], pp[2]) for o in sq.members)]
        if not piles:
            if k == "papers" and any((getattr(i, "data", None) or {}).get("scavenged") for i in a.inv):
                return _bring_papers(game, a, sq, t)
            a.ai["task_done"] = True
            _maybe_finished(game, sq)
            return None
        tgt = a.ai["task_pile"] = (piles[0][1], piles[0][2])
    x, y = tgt
    if (a.x, a.y) != (x, y):
        if max(abs(a.x - x), abs(a.y - y)) <= 1 and (x, y) in game.soldier_at:
            pass                                     # someone's standing on it: work from beside
        else:
            from .ai import path_step
            c = path_step(game, a, x, y)
            if c:
                return c
            if max(abs(a.x - x), abs(a.y - y)) > 1:
                a.ai.pop("task_pile", None)
                return None
    # at the pile: take what he came for
    took = 0
    for it in list(game.map.items_at(x, y)):
        if it.t.kind == "corpse":
            inv = (it.data or {}).get("inv")
            if inv is None or (k == "papers" and (it.data or {}).get("side") == a.side):
                continue
            for i in list(inv.items()):
                if not _wanted(k, i, a):
                    continue
                n = i.count if i.t.kind != "mag" else 1      # (counted before it goes in: a stack merges and empties)
                name = i.t.name
                inv.remove(i)
                if k == "papers":
                    i.data = dict(i.data or {}, scavenged=True, owner=(it.data or {}).get("name", "a dead man"))
                if a.add_item(i) is None:
                    inv.add(i)
                    break
                t["found"][name] += n
                took += 1
        elif _wanted(k, it, a):
            n = it.count if it.t.kind != "mag" else 1
            if A.pickup(game, a, it, x, y) is None:
                break
            t["found"][it.t.name] += n
            took += 1
    a.ai.pop("task_pile", None)
    if not took:
        # there was something there he wanted and he couldn't take it: his webbing's full
        a.ai["task_done"] = True
        if k == "papers" and any((getattr(i, "data", None) or {}).get("scavenged") for i in a.inv):
            a.ai.pop("task_done", None)
            a.ai["task_bring"] = True
        _maybe_finished(game, sq)
        return 100
    return 200 if k == "papers" else 250


def _gather_drop(game, a, sq, t):
    """A reception committee's night: each man to a container, open it, carry it to the cart - off the field
    before the enemy comes (agents.py)."""
    did = t.get("drop")
    m = game.map
    tgt = a.ai.get("task_pile")
    if tgt is None:
        taken = {o.ai.get("task_pile") for o in sq.members if o is not a}
        piles = []
        for (x, y), items in list(getattr(m, "items", {}).items()):
            if (x, y) in taken:
                continue
            if any((it.data or {}).get("drop") == did for it in items):
                piles.append((math.hypot(x - a.x, y - a.y), x, y))
        if not piles:
            a.ai["task_done"] = True
            _maybe_finished(game, sq)
            return None
        piles.sort()
        tgt = a.ai["task_pile"] = (piles[0][1], piles[0][2])
    x, y = tgt
    if max(abs(a.x - x), abs(a.y - y)) > 1:
        from .ai import path_step
        c = path_step(game, a, x, y)
        if c:
            return c
        a.ai.pop("task_pile", None)
        return None
    for it in list(m.items_at(x, y)):
        if (it.data or {}).get("drop") == did:
            m.remove_item(x, y, it)
            t["found"]["containers' worth of stores hidden"] += 1
    a.ai.pop("task_pile", None)
    return 600                                        # unbuckling a parachute harness from a container, and away


def _bring_papers(game, a, sq, t):
    """Papers go to the man who asked for them."""
    by = next((o for o in game.actors if o.id == t.get("by") and o.alive), None) or sq.leader
    if by is None or by is a:
        a.ai["task_done"] = True
        return None
    if max(abs(by.x - a.x), abs(by.y - a.y)) > 1:
        from .ai import path_step
        return path_step(game, a, by.x, by.y) or 100
    papers = [i for i in a.inv if (getattr(i, "data", None) or {}).get("scavenged")]
    for i in papers:
        a.remove_item(i)
        if by.add_item(i) is None:
            game.map.add_item(by.x, by.y, i)
    if by.is_player and papers:
        game.msg(f"{a.rank_short} {a.last_name} hands you {len(papers)} lot{'s' if len(papers) != 1 else ''} of papers "
                 f"taken off the enemy dead.", "good")
    a.ai["task_done"] = True
    a.ai.pop("task_bring", None)
    return 150


def _casevac(game, a, sq, t):
    from . import actions as A
    from .ai import evacuate_act, path_step
    if a.carrying is not None:
        return evacuate_act(game, a, [])
    carrying = sum(1 for o in sq.members if o.carrying is not None or o.ai.get("task_wounded"))
    if carrying >= max(1, len([o for o in sq.members if o.active]) // 2) and not a.ai.get("task_wounded"):
        return None                                  # half the squad stays in the fight
    home = t.get("home") or sq.anchor() or (a.x, a.y)
    wid = a.ai.get("task_wounded")
    w = next((o for o in game.actors if o.id == wid and o.alive and o.downed and o.ai.get("carried_by") is None), None)
    if w is None:
        a.ai.pop("task_wounded", None)
        taken = {o.ai.get("task_wounded") for o in game.actors if o is not a}
        moved = t.setdefault("carried", set())      # (with no aid post, a man set down in cover stays there)
        cands = [o for o in game.actors if o.side == a.side and o.alive and o.downed and o.vehicle is None and
                 o.ai.get("carried_by") is None and o.ai.get("at_aid") is None and o.id not in taken and
                 o.id not in moved and math.hypot(o.x - home[0], o.y - home[1]) <= RADIUS + 10]
        if not cands:
            a.ai["task_done"] = True
            _maybe_finished(game, sq)
            return None
        w = min(cands, key=lambda o: math.hypot(o.x - a.x, o.y - a.y))
        a.ai["task_wounded"] = w.id
    if max(abs(w.x - a.x), abs(w.y - a.y)) <= 1:
        c = A.pick_up(game, a, w)
        if c:
            a.ai.pop("task_wounded", None)
            if w.id not in t.setdefault("carried", set()):
                t["carried"].add(w.id)
                t["found"]["wounded carried back"] += 1
            return c
        return None
    return path_step(game, a, w.x, w.y)


def _prisoners(game, a, sq, t):
    from . import prisoners as PW
    from .ai import path_step
    if a.ai.get("escort_prisoner"):
        return None                                  # ai.prisoner_escort_act walks him back
    home = t.get("home") or sq.anchor() or (a.x, a.y)
    pid = a.ai.get("task_pw")
    pw = next((o for o in game.actors if o.id == pid and o.alive and o.state == "surrendered"), None)
    if pw is None:
        a.ai.pop("task_pw", None)
        taken = {o.ai.get("task_pw") for o in game.actors if o is not a}
        cands = [o for o in game.actors if o.alive and o.state == "surrendered" and o.side != a.side and
                 _unguarded(game, o) and o.id not in taken and math.hypot(o.x - home[0], o.y - home[1]) <= RADIUS]
        if not cands:
            a.ai["task_done"] = True
            _maybe_finished(game, sq)
            return None
        pw = min(cands, key=lambda o: math.hypot(o.x - a.x, o.y - a.y))
        a.ai["task_pw"] = pw.id
    d = max(abs(pw.x - a.x), abs(pw.y - a.y))
    if d <= 8 and pw.ai.get("captor") != a.id:
        pw.ai["captor"] = a.id                       # 'Sit! Stay there!' - he's taken charge of him
        pw.ai["pw_order"] = "stay"
    if d > 1:
        return path_step(game, a, pw.x, pw.y)
    if not pw.ai.get("searched"):
        PW.search(game, a, pw)                       # weapons in a pile, papers to the searcher
        return PW.SEARCH_TIME * 100
    # then back to the rear with him - and any others still standing about unguarded near him
    a.ai.pop("task_pw", None)
    a.ai["escort_prisoner"] = pw.id
    group = [pw] + [o for o in game.actors if o is not pw and o.alive and o.state == "surrendered" and o.side != a.side
                    and _unguarded(game, o) and max(abs(o.x - pw.x), abs(o.y - pw.y)) <= 5][:2]
    by = t.get("by")
    for o in group:
        o.ai["captor"] = a.id
        o.ai["pw_order"] = "follow"
        if by is not None:
            o.ai["credit"] = by                      # your order, your credit
    t["found"]["prisoners marched back"] += len(group)
    a.ai["task_done"] = True
    return 100


def _maybe_finished(game, sq):
    t = sq.__dict__.get("task")
    if t is None:
        return
    ws = _workers(sq)
    if t["kind"] == "repair":
        if sq.__dict__.get("help_v") is None:
            finish(game, sq, "done")
        return
    busy = any(a.carrying is not None or a.ai.get("task_pile") or a.ai.get("task_wounded") or a.ai.get("task_pw")
               or a.ai.get("task_bring") for a in ws)
    if all(a.ai.get("task_done") for a in ws) and not busy:
        finish(game, sq, "done")


def finish(game, sq, why="done"):
    """The job's over: the leader says what they got, and the men go back to their places."""
    t = sq.__dict__.pop("task", None)
    if t is None:
        return
    for a in sq.members:
        for k in ("task_pile", "task_done", "task_pw", "task_wounded", "task_bring", "helping_v"):
            a.ai.pop(k, None)
    if t["kind"] == "repair" and sq.__dict__.pop("help_v", None) is not None and why != "orders":
        home = t.get("home") or sq.anchor()
        if home is not None and not sq.player_led:
            from .ai import Order
            sq.order = Order("hold", target=home, radius=8, issued=game.turn, src="player", roe=sq.order.roe)
            sq.arrived = False
            sq.positions = {}
    p = game.player
    if p is None or t.get("by") != p.id or why == "orders":
        return
    found = t["found"]
    if found:
        def word(what, n):
            if what == "prisoners marched back":
                return f"{n} prisoner{'s' if n != 1 else ''} marched back"
            if what == "wounded carried back":
                return f"{n} wounded carried back"
            if what.startswith("containers"):
                return f"{n} loads of stores carried off the field"
            return f"{n} x {what}"
        bits = [word(what, n) for what, n in found.most_common(6)]
        text = ("Right - back to our places. We got " if why == "stopped" else "Done. ") + ", ".join(bits) + "."
    else:
        text = {"ammo": "Nothing worth having - they'd shot it all off.", "medical": "Not a dressing left on any of them.",
                "weapons": "Nothing but empty rifles.", "papers": "No papers on any of them.",
                "casevac": "No one left to carry.", "prisoners": "Nobody left to take back.",
                "repair": "Done."}.get(t["kind"], "Done.")
        if why == "stopped":
            text = "Right - back to our places."
    ld = sq.leader
    who = f"{ld.rank_short} {ld.last_name}" if ld is not None and ld is not p else "Your men"
    near = ld is not None and max(abs(ld.x - p.x), abs(ld.y - p.y)) <= 15
    from .command import squad_has_radio
    if near or squad_has_radio(game, sq):
        game.msg(f"{who}{'' if near else ' (radio)'}: '{text}'", "radio" if not near else "shout")


def tick(game):
    """Every few seconds: jobs that have run their time, or have nobody left to do them, are over."""
    for sq in game.squads:
        t = sq.__dict__.get("task")
        if t is not None and (game.turn > t["until"] or not _workers(sq)):
            finish(game, sq, "time")
