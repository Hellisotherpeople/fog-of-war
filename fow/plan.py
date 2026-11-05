"""The company plan: what each side means to do with a piece of ground, and who does which part.

A side's commander makes one plan for each sector it is fighting in, not one order per squad.
An attack has a main effort, a supporting attack that fixes the next objective along, units
firing in support, and a reserve held back; it goes objective by objective, bound by bound, and
stops at a limit of advance. A defence puts an outpost forward, the main line on the ground
that matters, and a reserve behind it to counterattack. In a meeting both sides make for the
key ground. Holding the ground, with the other side too beaten to take it back, makes him give
the sector up.

Plans live in game.plans, keyed (side, sector), in world coordinates: the moving map never
needs to shift them. Squads that a plan has no part for fall back on commander.py's old rules.
"""
from __future__ import annotations

import math

from .ai import Order
from .constants import COMPASS_WORD, other_side
from .relief import HILL_NAMES

REVIEW = 600                 # a plan is made again after this long (sooner if the fight changes)
COLLAPSE_HOLD = 600          # the ground held this long, the other side this beaten, and he gives it up
WITHDRAWAL = 900             # how long a unit that's been told to pull out is left to get out
SUPPORT_KINDS = ("mg", "mortar", "atgun", "sniper", "at")
SKIP_KINDS = ("staff", "rear", "aid", "supply", "hq")    # (headquarters keep near their officer)

# what a named place is, as ground to fight for (and how much it matters)
KINDS = (
    ("height", 3, HILL_NAMES + ("rise", "slag")),
    ("crossing", 2, ("bridge", "causeway", "ford", "crossroads", "junction", "halt", "station", "railway",
                     "landing", "draw")),
    ("strongpoint", 2, ("bunker", "casemate", "strongpoint", "fortress", "fort", "castle", "battery",
                        "command post", "radar", "flak", "abbey")),
    ("village", 2, ("village", "town square", "square", "church", "mairie", "kolkhoz", "collective",
                    "château", "factory", "foundry", "brickworks", "elevator", "works")),
)


# ============================================================================ the ground
def classify(m, ob):
    """Kind and value of an objective, from its name (once; kept on it)."""
    if not ob.__dict__.get("_classed"):
        name = f" {ob.name.lower()} "
        ob.kind, ob.value = "point", 1
        for k, v, words in KINDS:
            if any(f" {w} " in name or f" {w}s " in name for w in words):
                ob.kind, ob.value = k, v
                break
        ob._classed = True
    return ob.kind, ob.value


def tag_objectives(m):
    """Mapgen calls this once the heightmap is made: names, then the lie of the land."""
    for ob in m.objectives:
        ob.__dict__.pop("_classed", None)
        classify(m, ob)
    # the objective that looks down on the others is key terrain, whatever it's called
    e = m.__dict__.get("elev")
    obs = [o for o in m.objectives if m.in_bounds(o.x, o.y)]
    if e is None or len(obs) < 2:
        return
    hs = sorted((float(e[o.x, o.y]), i) for i, o in enumerate(obs))
    top, i = hs[-1]
    if top - hs[len(hs) // 2][0] >= 6:
        if obs[i].kind == "point":
            obs[i].kind = "height"
        obs[i].value = max(obs[i].value, 3)


def is_key(ob):
    return ob.value >= 3


# ============================================================================ where things are
def _landscape(game):
    ls = game.__dict__.get("landscape")
    return ls if ls is not None and ls.frame is game.map else None


def sector_key(game, x, y):
    ls = _landscape(game)
    if ls is None:
        s = game.sector
        return (s.x, s.y) if s is not None else (0, 0)
    wx, wy = ls.world_pos(x, y)
    return (math.floor(wx / ls.w), math.floor(wy / ls.h))


def ob_key(ob):
    """A name for an objective that survives the moving map reframing (indices don't)."""
    wp = ob.__dict__.get("_world_pos")
    return tuple(wp) if wp is not None else (ob.name, ob.x, ob.y)


def ob_sector(game, ob):
    ls = _landscape(game)
    wp = ob.__dict__.get("_world_pos")
    if ls is not None and wp is not None:
        return (math.floor(wp[0] / ls.w), math.floor(wp[1] / ls.h))
    return sector_key(game, ob.x, ob.y)


def to_world(game, p):
    ls = _landscape(game)
    return tuple(int(v) for v in ls.world_pos(*p)) if ls is not None else (int(p[0]), int(p[1]))


def to_local(game, p):
    ls = _landscape(game)
    if ls is None:
        return int(p[0]), int(p[1])
    return int(p[0] - ls.origin[0]), int(p[1] - ls.origin[1])


def sector_centre(game, key):
    """The middle of a sector, in local map coordinates."""
    ls = _landscape(game)
    if ls is None:
        return game.map.w // 2, game.map.h // 2
    return to_local(game, ((key[0] + 0.5) * ls.w, (key[1] + 0.5) * ls.h))


def _span(game):
    ls = _landscape(game)
    return ls.w if ls is not None else game.map.w


def _unit(v):
    d = math.hypot(*v)
    return (v[0] / d, v[1] / d) if d > 1e-6 else (0.0, 1.0)


def _dist(a, b):
    if a is None or b is None:
        return 9999
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _enemy_dir(game, side, key, stance, src):
    """Which way the enemy is from this sector's middle, as this side sees it."""
    from .strategic import DIRS
    if src is not None:
        v = (src[0] - key[0], src[1] - key[1])            # (the attack comes from, or goes in from, there)
        return _unit(v) if stance == "defend" else _unit((-v[0], -v[1]))
    s = game.sector
    if s is not None and key == (s.x, s.y) and game.att_edge in DIRS:
        dx, dy = DIRS[game.att_edge]
        return (float(dx), float(dy)) if game.attacker != side else (-float(dx), -float(dy))
    st = game.strategic
    enemy = other_side(side)
    v = [0.0, 0.0]
    for dx, dy in DIRS.values():
        n = st.at(key[0] + dx, key[1] + dy) if st is not None else None
        if n is None or n.control is None:
            continue
        sign = 1 if n.control == enemy else -1 if stance != "defend" else 0
        v[0] += dx * sign
        v[1] += dy * sign
    if v != [0.0, 0.0]:
        return _unit(v)
    cs = game.brains[side].live_contacts(300, False)
    if cs:
        ox, oy = sector_centre(game, key)
        return _unit((sum(c.x for c in cs) / len(cs) - ox, sum(c.y for c in cs) / len(cs) - oy))
    return (0.0, 1.0)


# ============================================================================ who's fighting where
def posture(game, side, key):
    """(attack | defend | meeting, the sector the attack comes from): this side, this sector."""
    st = game.strategic
    enemy = other_side(side)
    at = st.attack_on(*key) if st is not None and hasattr(st, "attack_on") else None
    if at is not None:
        src = tuple(at["src"]) if at.get("src") else None
        return ("attack" if at["side"] == side else "defend"), src
    s = game.sector
    if s is not None and key == (s.x, s.y) and (_landscape(game) is None or game.attacker is not None):
        if game.attacker == side:
            return "attack", None
        if game.attacker == enemy:
            return "defend", None
        if _landscape(game) is None:
            return "meeting", None
    sec = st.at(*key) if st is not None else None
    if sec is None or sec.control is None:
        return "meeting", None
    return ("defend" if sec.control == side else "attack"), None


def _groups(squads):
    """Platoons fight together; a squad without one goes on its own."""
    out, seen = [], {}
    for sq in squads:
        f = getattr(sq, "formation", None)
        if f is not None and f.echelon == "platoon" and f.special is None and sq is not f.hq:
            g = seen.get(f.id)
            if g is None:
                g = seen[f.id] = dict(name=f.name, squads=[])
                out.append(g)
            g["squads"].append(sq)
        else:
            out.append(dict(name=sq.short or sq.name, squads=[sq]))
    return out


def _gpos(g):
    pts = [p for p in (sq.anchor() for sq in g["squads"]) if p is not None]
    if not pts:
        return None
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def _gstr(g):
    return sum(sq.strength() for sq in g["squads"])


def _support(g):
    return all(sq.kind in SUPPORT_KINDS for sq in g["squads"])


def _known_enemy(game, side, key):
    """What this side knows is in the sector: its contacts, or failing those the war map's report."""
    tot = 0.0
    for c in game.brains[side].live_contacts(240, False):
        if sector_key(game, c.x, c.y) == key:
            tot += min(4.0, c.threat)
    if tot <= 0:
        st = game.strategic
        sec = st.at(*key) if st is not None else None
        if sec is not None:
            from .strategic import power
            tot = power(sec.units[other_side(side)]) * 2.0
    return tot


def _weight(cs, o):
    r2 = (o.radius + 10) ** 2
    return sum(min(4.0, c.threat) for c in cs if (c.x - o.x) ** 2 + (c.y - o.y) ** 2 <= r2)


# ============================================================================ making a plan
def _depth(game, ob, toward, key):
    """How far toward the enemy an objective lies."""
    ox, oy = sector_centre(game, key)
    return (ob.x - ox) * toward[0] + (ob.y - oy) * toward[1]


def _lane(game, ob, toward, key):
    ox, oy = sector_centre(game, key)
    left = (toward[1], -toward[0])
    lat = (ob.x - ox) * left[0] + (ob.y - oy) * left[1]
    span = _span(game) / 6
    return "left" if lat > span else "right" if lat < -span else "centre"


def make(game, side, key, squads, held, old=None):
    """A fresh plan for this side in this sector, from the ground, the odds and the doctrine."""
    from .intent import profile
    m = game.map
    obs = [ob for ob in m.objectives if ob_sector(game, ob) == key]
    for ob in obs:
        classify(m, ob)
    stance, src = posture(game, side, key)
    groups = _groups(squads)
    ratio = sum(_gstr(g) for g in groups) / max(1.0, _known_enemy(game, side, key))
    plan = dict(side=side, key=key, posture=stance, from_sector=src,
                toward=_enemy_dir(game, side, key, stance, src), made=game.turn, review=game.turn + REVIEW,
                phase=0, phases=[], main=None, fix=None, lane=None, limit=None, outpost=None, counter=None,
                roles={}, groups={}, posts={}, reserve_at=None, committed=False, scheme="",
                ratio=round(ratio, 2), log=[], driven_in=(old or {}).get("driven_in"))
    if not obs or not groups:
        return plan
    tactic = profile(squads[0].nation)[1]
    if stance == "attack":
        _plan_attack(game, plan, obs, held, groups, ratio, tactic)
    elif stance == "defend":
        _plan_defence(game, plan, obs, groups)
    else:
        _plan_meeting(game, plan, obs, groups)
    return plan


def _bounds(game, obs, toward, key):
    """Objectives in the order the attack comes to them, in bounds of one or two."""
    obs = sorted(obs, key=lambda o: _depth(game, o, toward, key))
    phases, cur, last = [], [], None
    for o in obs:
        d = _depth(game, o, toward, key)
        if cur and (len(cur) >= 2 or d - last > _span(game) / 5):
            phases.append(cur)
            cur = []
        cur.append(o)
        last = d
    if cur:
        phases.append(cur)
    return phases


def _plan_attack(game, plan, obs, held, groups, ratio, tactic):
    key, toward = plan["key"], plan["toward"]
    targets = [o for o in obs if not held.get(ob_key(o))]
    if not targets:
        plan["posture"], plan["scheme"] = "defend", "consolidate"
        _plan_defence(game, plan, obs, groups)
        return
    phases = _bounds(game, targets, toward, key)
    if ratio < 1.0 and len(phases) > 1:
        # not enough for the whole field: take what matters most within reach and stop there
        near = phases[0] + phases[1]
        best = max(near, key=lambda o: (o.value, -_depth(game, o, toward, key)))
        phases = [[best]]
        plan["scheme"] = "limited"
    else:
        plan["scheme"] = {"flank": "envelopment", "concentrate": "concentrated"}.get(tactic, "deliberate")
    plan["phases"] = [[ob_key(o) for o in ph] for ph in phases]
    plan["limit"] = ob_key(phases[-1][-1])
    _attack_tasks(game, plan, groups, phases[0], tactic, beyond=phases[1] if len(phases) > 1 else ())


def _attack_tasks(game, plan, groups, objectives, tactic, reserve=True, beyond=()):
    """Main effort, supporting attack, fire support and a reserve, for the objectives of this bound."""
    if not objectives:
        return
    cs = game.brains[plan["side"]].live_contacts(240, False)
    if tactic == "flank" and len(objectives) > 1:
        main = min(objectives, key=lambda o: (_weight(cs, o), -o.value))     # round where he's thinnest
    else:
        main = max(objectives, key=lambda o: (o.value, -_weight(cs, o)))     # at what matters most
    # the supporting attack pins whatever could fire into the main effort's flank: the rest of the
    # bound, or the nearest position behind it
    others = [o for o in objectives if o is not main] or \
        sorted(beyond, key=lambda o: _dist(o.pos, main.pos))[:1]
    fix = others[0] if others and tactic != "concentrate" else None
    plan["main"], plan["fix"] = ob_key(main), (ob_key(fix) if fix is not None else None)
    plan["lane"] = _lane(game, main, plan["toward"], plan["key"])
    support = [g for g in groups if _support(g)]
    manoeuvre = sorted((g for g in groups if not _support(g)), key=lambda g: _dist(_gpos(g), main.pos))
    n = len(manoeuvre)
    n_res = ((1 if n >= 3 else 0) + (1 if n >= 7 else 0)) if reserve and not plan["committed"] else 0
    n_fix = ((1 if n - n_res >= 2 else 0) + (1 if n >= 8 else 0)) if fix is not None else 0
    # the reserve is whoever's furthest back, the fixing force whoever's nearest the other objective
    res = manoeuvre[n - n_res:]
    rest = manoeuvre[:n - n_res]
    fixers = sorted(rest, key=lambda g: _dist(_gpos(g), fix.pos))[:n_fix] if n_fix else []
    for g in rest:
        _set(plan, g, "fix" if g in fixers else "main")
    for g in res:
        _set(plan, g, "reserve")
    for g in support:
        _set(plan, g, "support")
    if res:
        p = _gpos(res[0])
        plan["reserve_at"] = to_world(game, p) if p is not None else None


def _set(plan, g, role, post=None):
    head = g["squads"][0].id
    for sq in g["squads"]:
        plan["roles"][sq.id] = role
    plan["groups"][head] = dict(name=g["name"], role=role, ids=[sq.id for sq in g["squads"]])
    if post is not None:
        plan["posts"][head] = post


def _plan_defence(game, plan, obs, groups):
    """An outpost forward, the main line on the ground that matters, a reserve behind it."""
    key, toward = plan["key"], plan["toward"]
    fwd = sorted(obs, key=lambda o: -_depth(game, o, toward, key))
    support = [g for g in groups if _support(g)]
    manoeuvre = sorted((g for g in groups if not _support(g)), key=lambda g: -_gstr(g))
    n = len(manoeuvre)
    outpost = fwd[0] if len(fwd) >= 3 and n >= 4 and not is_key(fwd[0]) and \
        plan.get("driven_in") != ob_key(fwd[0]) else None
    line = [o for o in fwd if o is not outpost]
    n_res = 1 if n >= 3 else 0
    # the key ground first, then the rest, as far as there are men to hold it
    keep = sorted(line, key=lambda o: -o.value)[:max(1, min(len(line), n - n_res - (outpost is not None)))]
    if not plan["scheme"]:
        plan["scheme"] = "defence in depth" if outpost is not None else "defence"
    plan["main"] = ob_key(keep[0]) if keep else None
    plan["phases"] = [[ob_key(o) for o in keep]]
    plan["outpost"] = ob_key(outpost) if outpost is not None else None
    res = manoeuvre[n - n_res:]
    rest = manoeuvre[:n - n_res]
    if outpost is not None and rest:
        op = min(rest, key=lambda g: _dist(_gpos(g), outpost.pos))
        rest.remove(op)
        _set(plan, op, "outpost")
    load = {ob_key(o): 0 for o in keep}
    for g in rest:
        o = min(keep, key=lambda o: load[ob_key(o)] * 60 - o.value * 10 + _dist(_gpos(g), o.pos) * 0.3)
        load[ob_key(o)] += 1
        _set(plan, g, "line", ob_key(o))
    for g in res:
        _set(plan, g, "reserve")
    for g in support:
        _set(plan, g, "support", plan["main"])
    if res and keep:
        rear = min(keep, key=lambda o: _depth(game, o, toward, key))
        plan["reserve_at"] = to_world(game, rear.pos)


def _plan_meeting(game, plan, obs, groups):
    """Nobody holds it: make for the ground that matters before he does."""
    pos = [p for p in (_gpos(g) for g in groups) if p is not None]
    if not pos:
        return
    c = (sum(p[0] for p in pos) / len(pos), sum(p[1] for p in pos) / len(pos))
    want = sorted(obs, key=lambda o: (-o.value, _dist(c, o.pos)))[:1 if len(groups) < 4 else 2]
    plan["scheme"] = "meeting"
    plan["phases"] = [[ob_key(o) for o in want]]
    plan["limit"] = ob_key(want[-1])
    _attack_tasks(game, plan, groups, want, "fire")


def _fit_in(game, plan, sq):
    """A unit that's turned up since the plan was made gets the obvious part."""
    g = dict(name=sq.short or sq.name, squads=[sq])
    if plan["posture"] == "defend":
        _set(plan, g, "support" if sq.kind in SUPPORT_KINDS else "line", plan["main"])
    else:
        _set(plan, g, "support" if sq.kind in SUPPORT_KINDS else "main")


# ============================================================================ carrying it out
def _index(game):
    return {ob_key(o): i for i, o in enumerate(game.map.objectives)}


def _order(game, sq, kind, i=None, target=None, mission=None, risk="normal", freedom=None):
    """Give the order and the standing mission that goes with it, unless that's the one he's on.
    (While he's on it, the section's own leader decides how: flanking, fetching rounds, halting.)"""
    from .intent import profile
    objs = game.map.objectives
    tgt = objs[i].pos if i is not None else tuple(target)
    mission = mission or ("seize" if kind == "attack" else "defend")
    it = sq.rep.get("intent")
    if it and it.get("source") == "ai" and it.get("mission") == mission and _dist(it["target"], tgt) < 4:
        return False
    o = sq.order
    if i is not None:
        new = Order(kind, obj=i, radius=objs[i].radius, issued=game.turn, roe=o.roe)
    else:
        new = Order(kind, target=tuple(tgt), radius=6, issued=game.turn, roe=o.roe)
    game.command.apply(game, sq, new)
    sq.rep["intent"] = dict(mission=mission, target=tuple(tgt), freedom=freedom or profile(sq.nation)[2],
                            risk=risk, source="ai", issued=game.turn, strength=sq.strength(),
                            next=game.turn, completed=False)
    return True


def carry_out(game, plan, squads, held):
    """See how the plan's going, move it on, and give each unit its part. Returns the ids it ordered."""
    idx = _index(game)
    if plan["posture"] in ("attack", "meeting"):
        _attack_progress(game, plan, squads, held, idx)
    elif plan["posture"] == "defend":
        _defence_progress(game, plan, squads, held, idx)
    roles = plan["roles"]
    main_i = idx.get(plan["main"])
    fix_i = idx.get(plan["fix"])
    done = set()
    for sq in squads:
        role = roles.get(sq.id)
        post = idx.get(plan["posts"].get(_head(plan, sq.id)))
        if role is None or sq.player_led or getattr(sq.order, "src", "ai") == "player":
            continue                                # (the player is told his part; he gives his own orders)
        if plan["posture"] in ("attack", "meeting"):
            tgt = {"main": main_i, "support": main_i, "fix": fix_i if fix_i is not None else main_i}.get(role)
            if tgt is not None and held.get(ob_key(game.map.objectives[tgt])):
                _order(game, sq, "defend", tgt)              # (won: hold it until the plan moves on)
            elif tgt is not None:
                _order(game, sq, "attack", tgt, risk={"fix": "cautious", "support": "cautious"}.get(
                    role, "press" if plan["scheme"] == "concentrated" else "normal"))
            elif role == "reserve" and plan["reserve_at"] is not None:
                _order(game, sq, "defend", target=to_local(game, plan["reserve_at"]), mission="reserve",
                       freedom="restricted")
            elif role == "hold" and post is not None:
                _order(game, sq, "defend", post)
            else:
                continue
        else:
            if role == "outpost" and idx.get(plan["outpost"]) is not None:
                _order(game, sq, "defend", idx[plan["outpost"]], mission="screen", risk="cautious")
            elif role in ("line", "support", "hold") and (post if post is not None else main_i) is not None:
                _order(game, sq, "defend", post if post is not None else main_i)
            elif role == "reserve" and plan["reserve_at"] is not None:
                _order(game, sq, "defend", target=to_local(game, plan["reserve_at"]), mission="reserve",
                       freedom="restricted")
            elif role == "counter" and idx.get(plan["counter"]) is not None:
                _order(game, sq, "attack", idx[plan["counter"]], risk="press")
            else:
                continue
        done.add(sq.id)
    return done


def _head(plan, sid):
    for head, g in plan["groups"].items():
        if sid in g["ids"]:
            return head
    return sid


def _live_groups(plan, squads):
    by_id = {sq.id: sq for sq in squads}
    out = []
    for g in plan["groups"].values():
        sqs = [by_id[i] for i in g["ids"] if i in by_id]
        if sqs:
            out.append(dict(name=g["name"], role=g["role"], squads=sqs))
    return out


def _attack_progress(game, plan, squads, held, idx):
    phases = plan["phases"]
    if not phases or plan["main"] is None:
        return
    bound = phases[min(plan["phase"], len(phases) - 1)]
    if plan["fix"] is not None and held.get(plan["fix"]) and not held.get(plan["main"]):
        _news(game, plan, f"{_cap(_name(game, idx, plan['fix']))} is taken; the supporting attack "
                          f"joins the main effort on {_name(game, idx, plan['main'])}.")
        plan["fix"] = None
    if held.get(plan["main"]):
        left = [k for k in bound if not held.get(k)]
        if left:
            # the main effort's objective has fallen: it rolls on to the rest of the bound
            taken = plan["main"]
            plan["main"], plan["fix"] = left[0], None
            _news(game, plan, f"{_cap(_name(game, idx, taken))} is taken; the attack rolls on to "
                              f"{_name(game, idx, left[0])}.")
        elif plan["phase"] + 1 < len(phases):
            _next_bound(game, plan, squads, idx)
        else:
            plan["posture"], plan["scheme"] = "defend", "consolidate"
            plan["review"] = game.turn            # (the next round makes the defence of what's been won)
            _news(game, plan, "The objectives are taken. Consolidate: dig in and expect the counterattack.")
        return
    # the main effort has stopped: the reserve goes in where it's held up
    if not plan["committed"]:
        main = [sq for sq in squads if plan["roles"].get(sq.id) == "main"]
        if main and all(sq.rep.get("intent", {}).get("halted") or sq.morale < 25 for sq in main):
            res = [g for g in plan["groups"].values() if g["role"] == "reserve"]
            if res:
                plan["committed"] = True
                for g in res:
                    g["role"] = "main"
                    for sid in g["ids"]:
                        plan["roles"][sid] = "main"
                _news(game, plan, f"The attack on {_name(game, idx, plan['main'])} is held up. "
                                  f"The reserve is committed.")


def _next_bound(game, plan, squads, idx):
    """The bound is won. The reserve passes through to lead the next; the men who took it hold it."""
    from .intent import profile
    plan["phase"] += 1
    nxt = [game.map.objectives[idx[k]] for k in plan["phases"][plan["phase"]] if k in idx]
    groups = _live_groups(plan, squads)
    res = [g for g in groups if g["role"] == "reserve"]
    attackers = [g for g in groups if g["role"] in ("main", "fix")]
    taken = plan["main"]
    if res:
        plan["committed"] = True
        for g in attackers:
            _set(plan, g, "hold", taken)
        movers = res
    else:
        movers = attackers
    tactic = profile(squads[0].nation)[1] if squads else "fire"
    after = plan["phases"][plan["phase"] + 1] if plan["phase"] + 1 < len(plan["phases"]) else ()
    _attack_tasks(game, plan, movers + [g for g in groups if g["role"] == "support"], nxt, tactic,
                  reserve=False, beyond=[game.map.objectives[idx[k]] for k in after if k in idx])
    _news(game, plan, ("First bound won. " if plan["phase"] == 1 else "Bound won. ") +
          ("The reserve goes through to " if res else "On to ") + f"{_name(game, idx, plan['main'])}.")


def _defence_progress(game, plan, squads, held, idx):
    side = plan["side"]
    # the outpost falls back on the main line when he comes on in strength
    op = idx.get(plan["outpost"])
    if op is not None:
        ob = game.map.objectives[op]
        for g in list(plan["groups"].values()):
            if g["role"] != "outpost":
                continue
            mine = sum(sq.strength() for sq in squads if sq.id in g["ids"])
            if _enemy_near(game, side, ob) > mine * 1.5 or held.get(plan["outpost"]) is False:
                g["role"] = "line"
                for sid in g["ids"]:
                    plan["roles"][sid] = "line"
                plan["posts"][g["ids"][0]] = plan["main"]
                plan["driven_in"] = plan["outpost"]
                for sq in squads:
                    if sq.id in g["ids"]:
                        sq.rep["initiative_note"] = "Outpost driven in; falling back on the main line."
                _news(game, plan, f"The outpost at {ob.name} is driven in and falls back on the main line.")
    # a main-line position lost: the reserve counterattacks at once, before he's dug in, if it's enough
    if plan["counter"] is not None:
        if held.get(plan["counter"]):
            for g in plan["groups"].values():
                if g["role"] == "counter":
                    g["role"] = "line"
                    plan["posts"][g["ids"][0]] = plan["counter"]
                    for sid in g["ids"]:
                        plan["roles"][sid] = "line"
            _news(game, plan, f"{_cap(_name(game, idx, plan['counter']))} is ours again.")
            plan["counter"] = None
        return
    for k in plan["phases"][0] if plan["phases"] else []:
        if held.get(k) is not False or idx.get(k) is None:
            continue
        res = [g for g in plan["groups"].values() if g["role"] == "reserve"]
        ours = sum(sq.strength() for sq in squads if any(sq.id in g["ids"] for g in res))
        if res and ours >= max(1.0, _enemy_near(game, side, game.map.objectives[idx[k]])) * 1.2:
            plan["counter"] = k
            for g in res:
                g["role"] = "counter"
                for sid in g["ids"]:
                    plan["roles"][sid] = "counter"
            _news(game, plan, f"{_cap(_name(game, idx, k))} has fallen. The reserve counterattacks.")
        break


def _enemy_near(game, side, ob):
    r2 = (ob.radius + 12) ** 2
    return sum(min(4.0, c.threat) for c in game.brains[side].live_contacts(90, False)
               if (c.x - ob.x) ** 2 + (c.y - ob.y) ** 2 <= r2)


def _name(game, idx, okey):
    i = idx.get(okey)
    return game.map.objectives[i].name if i is not None else "the objective"


def _cap(s):
    return s[:1].upper() + s[1:]


def _news(game, plan, text):
    plan["log"].append((game.turn, text))
    del plan["log"][:-8]
    p = game.player
    if p is None or plan["side"] != p.side or not p.alive:
        return
    mine = p.squad is not None and p.squad.rep.get("plan_key") is not None and \
        tuple(p.squad.rep["plan_key"]) == plan["key"]
    if mine or game.command.billet is not None and sector_key(game, p.x, p.y) == plan["key"]:
        game.msg(f"Company net: {text}", "radio")


# ============================================================================ the commander's round
def plans(game):
    return game.__dict__.setdefault("plans", {})


def battles(game, side, squads):
    """Which sector each unit is fighting for: where it is, or where it was sent."""
    out = {}
    pl = plans(game)
    for sq in squads:
        anc = sq.anchor()
        if anc is None:
            continue
        key = sector_key(game, *anc)
        sent = sq.rep.get("plan_key")
        if sent is not None and tuple(sent) != key:
            p = pl.get((side, tuple(sent)))
            if p is not None and p["roles"].get(sq.id) not in (None, "hold"):
                key = tuple(sent)
        out.setdefault(key, []).append(sq)
    # an attack going in next door from here takes half the troops on this side of the line
    st = game.strategic
    if st is None or not hasattr(st, "attack_on") or _landscape(game) is None:
        return out
    from .strategic import DIRS
    sectors = {ob_sector(game, ob) for ob in game.map.objectives}
    for key in list(out):
        for dx, dy in DIRS.values():
            nk = (key[0] + dx, key[1] + dy)
            at = st.attack_on(*nk)
            if at is None or at["side"] != side or tuple(at.get("src") or ()) != key or nk in out \
                    or nk not in sectors:
                continue
            here = sorted((sq for sq in out[key] if sq.kind not in SUPPORT_KINDS),
                          key=lambda q: _dist(q.anchor(), sector_centre(game, nk)))
            go = here[:len(here) // 2]
            if go:
                out[nk] = go
                out[key] = [sq for sq in out[key] if sq not in go]
    return out


def _held_map(game, side, key, squads, owners):
    """What the commander can tell is ours, his, or not known, for each objective in the sector:
    the reports that reached him, and what his own units there can see for themselves."""
    from .intelligence import local_objective_owner, distance
    out = {}
    enemy = other_side(side)
    for i, ob in enumerate(game.map.objectives):
        if ob_sector(game, ob) != key:
            continue
        who = owners.get(i)
        for sq in squads:
            anc = sq.anchor()
            if anc is not None and distance(anc, ob.pos) <= ob.radius + 18:
                local = local_objective_owner(game, sq, i)
                if local is not None:
                    who = local
                    break
        out[ob_key(ob)] = True if who == side else False if who == enemy else None
    return out


def update(game, side, squads, owners, told=()):
    """Make or review each sector's plan and give the orders. Returns the ids of the squads it ordered.
    The told squads (the player's) are given a part in the plan but no orders."""
    ordered = set()
    if game.map is None or not game.map.objectives:
        return ordered
    pl = plans(game)
    for key, sqs in battles(game, side, list(squads) + [sq for sq in told if sq.anchor() is not None]).items():
        held = _held_map(game, side, key, sqs, owners)
        if not held:
            continue
        p = pl.get((side, key))
        stance = posture(game, side, key)[0]
        idx = _index(game)
        if p is not None and game.turn >= p["review"] and p["posture"] == stance:
            # a look at it again: a plan that's going on stays (the men know it), unless most of the
            # units it was made for are gone or it has as many again that it wasn't
            alive = sum(1 for sq in sqs if sq.id in p["roles"])
            if alive >= len(sqs) / 2 and alive >= len(set(p["roles"])) / 2:
                p["review"] = game.turn + REVIEW
        lost = p is not None and any(k is not None and k not in idx for k in (p["main"], p["fix"], p["outpost"]))
        if p is None or lost or game.turn >= p["review"] or \
                (p["posture"] != stance and p["scheme"] != "consolidate"):
            old = p
            p = make(game, side, key, sqs, held, old)
            if old is not None:
                p["log"] = old["log"]
                p["headline"] = old.get("headline")
                p["committed"] = old["committed"] and old["posture"] == p["posture"] == "attack"
            pl[(side, key)] = p
            head = brief(game, p, short=True) if p["main"] is not None else None
            if head and head != p.get("headline"):
                p["headline"] = head
                _news(game, p, head)
        for sq in sqs:
            if sq.id not in p["roles"] and p["main"] is not None:
                _fit_in(game, p, sq)
            sq.rep["plan_key"] = key
        ordered |= carry_out(game, p, sqs, held)
        _collapse(game, p, sqs)
    for k in [k for k, p in pl.items() if k[0] == side and game.turn - p["made"] > REVIEW * 6]:
        del pl[k]
    return ordered


# ============================================================================ the ground decides it
def _collapse(game, plan, squads):
    """One side holds the ground that matters, and what's left of the other is too beaten to take it
    back: he gives the sector up."""
    if not squads:
        return
    side, key = plan["side"], plan["key"]
    objs = [o for o in game.map.objectives if ob_sector(game, o) == key]
    hold = game.__dict__.setdefault("ground_held", {})
    if not objs:
        return
    total = sum(o.value for o in objs)
    ours = sum(o.value for o in objs if o.owner == side)
    enemy = other_side(side)
    there = [sq for sq in game.squads if sq.side == enemy and not sq.gone and sq.anchor() is not None
             and sq.kind not in SKIP_KINDS and not getattr(sq, "no_count", False)
             and sector_key(game, *sq.anchor()) == key]
    mine = sum(sq.strength() for sq in squads)
    his = sum(sq.strength() for sq in there)
    beaten = his <= 0.6 * sum(max(1, sq.initial) for sq in there)
    if not (there and ours >= total * 2 / 3 and all(o.owner == side for o in objs if is_key(o))
            and his <= mine * 0.5 and beaten):
        hold.pop((side, key), None)
        return
    since = hold.setdefault((side, key), game.turn)
    if game.turn - since >= COLLAPSE_HOLD:
        hold.pop((side, key), None)
        withdraw(game, enemy, key, there)


def withdraw(game, side, key, squads):
    """Give up a sector: back to the nearest of our own sectors next door, or off the field."""
    st = game.strategic
    from .strategic import DIRS
    dest = None
    if _landscape(game) is not None:
        here = sector_centre(game, key)
        for dx, dy in DIRS.values():
            n = st.at(key[0] + dx, key[1] + dy) if st is not None else None
            if n is not None and n.control == side:
                c = sector_centre(game, (n.x, n.y))
                if dest is None or _dist(c, here) < _dist(dest, here):
                    dest = c
    p = game.player
    moved = 0
    for sq in squads:
        if sq.player_led or getattr(sq.order, "src", "ai") == "player":
            continue                                # (the player decides whether his own men go)
        if dest is not None:
            game.command.apply(game, sq, Order("move", target=dest, radius=10, issued=game.turn))
        else:
            game.command.apply(game, sq, Order("retreat", issued=game.turn))
        sq.rep.pop("intent", None)
        sq.rep.pop("plan_key", None)
        sq.rep["withdrawing"] = game.turn + WITHDRAWAL     # (nobody turns them round on the way)
        moved += 1
    plans(game).pop((side, key), None)
    if not moved or p is None or sector_key(game, p.x, p.y) != key:
        return
    sec = st.at(*key) if st is not None else None
    name = sec.name if sec is not None else "the sector"
    if side == p.side:
        game.msg(f"Word comes down: {name} can't be held. Fall back!", "warn")
    else:
        game.msg(f"The enemy is giving up {name}: they're pulling back.", "good")


# ============================================================================ telling the men
ROLE_WORDS = {"main": "the main effort", "fix": "the supporting attack", "support": "fire support",
              "reserve": "in reserve", "outpost": "the outpost line", "line": "the main line",
              "counter": "the counterattack", "hold": "holding what we've won"}
SCHEME_WORDS = {"limited": "A limited attack", "envelopment": "We go round them",
                "concentrated": "Everything on one point", "deliberate": "A deliberate attack",
                "meeting": "Get there first", "consolidate": "Consolidate",
                "defence in depth": "Defence in depth", "defence": "Hold"}


def for_squad(game, sq):
    """(the plan, this unit's part in it), or (None, None)."""
    if sq is None or sq.rep.get("plan_key") is None:
        return None, None
    p = plans(game).get((sq.side, tuple(sq.rep["plan_key"])))
    if p is None:
        return None, None
    return p, p["roles"].get(sq.id)


def for_player(game):
    """(the plan as the player's company commander gives it to him, the point it's about), or None."""
    p = game.player
    sq = p.squad if p is not None else None
    if sq is None or game.map is None:
        return None
    pl, role = for_squad(game, sq)
    billet = game.command.billet
    if billet is not None and (pl is None or role is None):
        pl = plans(game).get((p.side, sector_key(game, p.x, p.y)))
        if pl is None or pl["main"] is None:
            return None
        mine = {s.id for s in billet.live_squads()}
        parts = []
        for g in pl["groups"].values():
            if mine & set(g["ids"]) and len(parts) < 5:
                parts.append(f"{g['name']}, {ROLE_WORDS.get(g['role'], g['role'])}")
        i = _index(game).get(pl["main"])
        text = brief(game, pl) + (f" Yours: {'; '.join(parts)}." if parts else "")
        return text, (game.map.objectives[i].pos if i is not None else None)
    if pl is None or role is None or pl["main"] is None:
        return None
    idx = _index(game)
    k = {"fix": pl["fix"], "outpost": pl["outpost"], "counter": pl["counter"]}.get(role) or \
        (pl["posts"].get(_head(pl, sq.id)) if role in ("line", "hold") else None) or pl["main"]
    i = idx.get(k)
    if role == "reserve" and pl["reserve_at"] is not None:
        pt = to_local(game, pl["reserve_at"])
    else:
        pt = game.map.objectives[i].pos if i is not None else None
    return brief(game, pl, sq), pt


def brief(game, plan, sq=None, short=False):
    """The plan in a few lines, as a company commander would give it out."""
    idx = _index(game)

    def nm(k):
        return _name(game, idx, k)
    head = SCHEME_WORDS.get(plan["scheme"], "Orders")
    parts = []
    if plan["posture"] == "attack":
        n = len(plan["phases"])
        lane = {"left": " on the left", "right": " on the right"}.get(plan["lane"], "")
        parts.append(f"{head}: {nm(plan['main'])}{lane}" + (f", bound {plan['phase'] + 1} of {n}" if n > 1 else "")
                     + ".")
        if short:
            return parts[0]
        if plan["fix"]:
            parts.append(f"A supporting attack fixes {nm(plan['fix'])}.")
        if plan["limit"] and plan["limit"] != plan["main"]:
            parts.append(f"Limit of advance: {nm(plan['limit'])}.")
        elif plan["limit"]:
            parts.append("No further than that.")
        if plan["reserve_at"] is not None and not plan["committed"]:
            parts.append("A reserve waits behind.")
        d = compass(plan["toward"])
        parts.append(f"The attack goes in to the {COMPASS_WORD.get(d, d)}.")
    elif plan["posture"] == "defend":
        line = [nm(k) for k in (plan["phases"][0] if plan["phases"] else [])]
        parts.append(f"{head}: the main line on {', '.join(line) or 'this ground'}.")
        if short:
            return parts[0]
        if plan["outpost"]:
            parts.append(f"An outpost forward at {nm(plan['outpost'])}: report, delay, fall back.")
        if plan["counter"]:
            parts.append(f"The reserve is counterattacking {nm(plan['counter'])}.")
        elif plan["reserve_at"] is not None:
            parts.append("A reserve behind the line to counterattack.")
        d = compass(plan["toward"])
        parts.append(f"Expect them from the {COMPASS_WORD.get(d, d)}.")
    else:
        parts.append(f"{head}: {nm(plan['main'])}, before they do.")
        if short:
            return parts[0]
    if sq is not None:
        role = plan["roles"].get(sq.id)
        if role is not None:
            g = plan["groups"].get(_head(plan, sq.id))
            p = game.player
            who = "Your section" if p is not None and sq is p.squad else g["name"] if g is not None else "You"
            if g is not None and len(g["ids"]) > 1 and who == "Your section":
                who = f"Your platoon ({g['name']})"
            parts.append(f"{who}: {ROLE_WORDS.get(role, role)}{_task(game, plan, role, sq, idx)}.")
    return " ".join(parts)


def _task(game, plan, role, sq, idx):
    k = {"main": plan["main"], "support": plan["main"], "fix": plan["fix"], "outpost": plan["outpost"],
         "counter": plan["counter"]}.get(role)
    if role in ("line", "hold"):
        k = plan["posts"].get(_head(plan, sq.id))
    if k is None:
        return ""
    return f", {'at' if role in ('line', 'hold', 'outpost') else 'on'} {_name(game, idx, k)}"


def compass(v):
    """A direction as a compass point (y grows to the south)."""
    a = math.degrees(math.atan2(v[0], -v[1])) % 360
    return ("N", "NE", "E", "SE", "S", "SW", "W", "NW")[int((a + 22.5) // 45) % 8]
