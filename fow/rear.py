"""Behind the line: the roads full of what the front lives on.

A sector the supplies come up through (Strategic.lines) has traffic on its roads, in proportion to how many
fronts depend on it: ammunition and fuel lorries, ration trucks and horse-drawn wagons (most of the German and
Soviet armies' supplies moved at a horse's walk), lorry-loads of replacements and tanks going up, ambulances
and prisoners coming back, a dispatch rider, a staff car.  Military police direct the traffic at the
crossroads; engineers fill the shell holes in the road; linemen string telephone wire along it.  The same for
the enemy's rear, when you're behind his lines.

Each convoy is real: vehicles and men on the map, with a cargo and a destination you can read off them (your
own side's).  Reaching the far edge, replacements and tanks join the front they were sent to.  Destroyed, a
convoy is a cut in that road on the war map (Strategic.interdict): the fronts beyond it are short of shells
and fuel and men until it's mended - and that decides battles.  Blow up a depot and its sector stops supplying
anything at all.
"""
from __future__ import annotations

import math

from .constants import SIDES, other_side

EDGE_VEC = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
OPP = {"N": "S", "S": "N", "E": "W", "W": "E"}

# what goes up the road, and how often (weights)
KINDS = {"ammunition": 5, "fuel": 2, "rations": 2, "troops": 3, "wounded": 3, "armour": 1, "march": 2,
         "prisoners": 1, "dispatch": 2, "staff": 1, "medical": 2, "spares": 2, "materials": 2}
CARGO = {"ammunition": ["artillery shells", "small-arms ammunition and grenades", "mortar bombs", "tank rounds"],
         "fuel": ["petrol in jerrycans", "fuel drums"], "rations": ["rations and water", "bread and tinned meat"],
         "troops": ["replacements"], "wounded": ["wounded from the front"], "armour": ["tanks going up"],
         "march": ["replacements on foot"], "prisoners": ["prisoners going back"], "dispatch": ["dispatches"],
         "staff": ["staff officers"], "medical": ["dressings, plasma and surgical stores"],
         "spares": ["vehicle spares and workshop tools"], "materials": ["timber, cement, wire and engineer stores"]}
RESOURCE = {"ammunition": "ammo", "fuel": "fuel", "rations": "food", "medical": "medical", "spares": "parts", "materials": "materials"}
TRUCKS = {"usa": ["gmc"], "france": ["gmc", "laffly"], "uk": ["bedford"], "canada": ["bedford"], "australia": ["bedford"],
          "newzealand": ["bedford"], "india": ["bedford"], "poland": ["bedford", "pf621"], "ussr": ["zis5", "studebaker"],
          "germany": ["opel_blitz"], "hungary": ["opel_blitz"], "romania": ["opel_blitz"], "italy": ["fiat626"],
          "japan": ["type94_truck"]}
# the share of an army's supply columns that were horse-drawn
HORSES = {"germany": 0.55, "ussr": 0.45, "japan": 0.5, "italy": 0.35, "poland": 0.6, "hungary": 0.6, "romania": 0.6,
          "finland": 0.7, "china": 0.8}
# how much of the road a destroyed vehicle of each kind of convoy takes out
CUT = {"ammunition": 0.12, "fuel": 0.14, "rations": 0.07, "troops": 0.08, "armour": 0.1, "wounded": 0.02,
       "march": 0.03, "prisoners": 0.0, "dispatch": 0.03, "staff": 0.04}


def _state(game) -> dict:
    s = game.__dict__.get("rear")
    here = (game.sector.x, game.sector.y) if game.sector is not None else None
    if s is None or s.get("sector") != here:
        s = game.rear = dict(sector=here, next={}, posts=False, convoys={}, depots={})
    return s


def lanes(game, side):
    """(entry edge, exit edges, traffic) for side's supplies through this sector, or None if none run here."""
    st = game.strategic
    s = game.sector
    if st is None or s is None or s.control != side or not s.playable:
        return None
    up, down, traffic = st.lines(side, s)
    if traffic <= 0 or st.is_front(s, side):
        return None                       # (the fighting sectors have their own traffic: ammunition trucks)
    e_in = st.neighbor_dir(s, up) if up is not None else game.home_edge(side)
    outs = [st.neighbor_dir(s, d) for d in down if st.neighbor_dir(s, d)]
    if e_in is None:
        e_in = game.home_edge(side) or "S"
    if not outs:
        outs = [OPP.get(e_in, "N")]
    return e_in, outs, traffic


def _road_point(game, edge):
    """Where a road crosses this edge of the map (else somewhere along it)."""
    from . import tiles as T
    from .spawn import edge_band_point
    m = game.map
    roads = {T.ID[k] for k in ("road", "paved", "cobble") if k in T.ID}
    if edge in ("N", "S"):
        y = 1 if edge == "N" else m.h - 2
        xs = [x for x in range(2, m.w - 2) if int(m.t[x, y]) in roads]
        if xs:
            return min(xs, key=lambda x: abs(x - m.w // 2)), y
    else:
        x = 1 if edge == "W" else m.w - 2
        ys = [y for y in range(2, m.h - 2) if int(m.t[x, y]) in roads]
        if ys:
            return x, min(ys, key=lambda y: abs(y - m.h // 2))
    return edge_band_point(game, edge, game.rng, depth=(1, 2))


# ============================================================================ each few seconds
def tick(game):
    """Convoys set off along the supply roads through this sector, arrive at the far edge, and are counted."""
    if game.map is None or game.__dict__.get("domain", "land") != "land" or game.strategic is None:
        return
    st = _state(game)
    if not st["posts"]:
        st["posts"] = True
        _posts(game)
    for side in SIDES:
        ln = lanes(game, side)
        if ln is None:
            continue
        e_in, outs, traffic = ln
        nxt = st["next"].get(side)
        cut = game.strategic.cut_of(side, game.sector)
        gap = int(max(200, min(1600, 900 / (0.4 + traffic * 0.35))) * (1 + 2.5 * cut))
        from .weather import road_factor
        gap = int(gap / road_factor(game))
        if nxt is None:
            st["next"][side] = game.turn + game.rng.randint(30, gap)
            continue
        live = [c for c in st["convoys"].values() if c["side"] == side]
        if game.turn >= nxt and len(live) < 3:
            st["next"][side] = game.turn + int(gap * game.rng.uniform(0.6, 1.4))
            _launch(game, side, e_in, game.rng.choice(outs))
    _arrivals(game)
    _depots(game)


def _launch(game, side, e_in, e_out):
    """One convoy (or column) onto the road."""
    from .ai import Order
    rng = game.rng
    nat = game.side_nation(side)
    kinds = dict(KINDS)
    if game.theatre["armor"].get(side, 0.3) < 0.2:
        kinds["armour"] = 0
    kind = rng.choices(list(kinds), list(kinds.values()))[0]
    frm, to = (e_out, e_in) if kind in ("wounded", "prisoners") else (e_in, e_out)
    x, y = _road_point(game, frm)
    tx, ty = _road_point(game, to)
    cargo = rng.choice(CARGO[kind])
    dest_s = game.strategic.at(game.sector.x + EDGE_VEC[to][0], game.sector.y + EDGE_VEC[to][1])
    dest = dest_s.name if dest_s is not None else "the front"
    info = dict(kind=kind, side=side, cargo=cargo, dest=dest, to=to, sq=None, start=game.turn,
                n=0, lost=0)
    if kind in ("march", "prisoners"):
        sq = _column(game, side, nat, kind, x, y, tx, ty, info)
    else:
        sq = _vehicles(game, side, nat, kind, x, y, tx, ty, info)
    if sq is None:
        return None
    if kind in RESOURCE:
        from .sustain import stores, take
        resource = RESOURCE[kind]
        info["payload"] = min(stores(game.sector, side)[resource], max(1, info["n"]) * 12)
        take(game.sector, side, resource, info["payload"])
    sq.order = Order("move", target=(tx, ty), radius=3, issued=game.turn)
    sq.no_count = True
    sq.__dict__["convoy"] = info
    info["sq"] = sq.id
    _state(game)["convoys"][sq.id] = info
    p = game.player
    if p is not None and side == p.side and game.rng.random() < 0.5 and kind not in ("dispatch",):
        game.emit_sound(x, y, 50, "engine", {"march": "boots on the road, a lot of them",
                                             "prisoners": "a column of men shuffling along the road"}
                        .get(kind, "a convoy's engines on the road"), side, None)
    return sq


def _vehicles(game, side, nat, kind, x, y, tx, ty, info):
    from .ai import Squad
    from .data.vehicles import VEHICLES
    from .entities import Vehicle
    from .spawn import make_soldier, pick_vehicle, spot_and_facing, facing_toward_edge
    rng = game.rng
    horse = rng.random() < HORSES.get(nat, 0.0) and kind in ("ammunition", "rations") and game.year < 1945.5
    if kind == "wounded":
        ids, n = ["ambulance"], rng.randint(1, 2)
    elif kind == "dispatch":
        ids, n = ["motorcycle"], 1
    elif kind == "staff":
        ids, n = [pick_vehicle(rng, nat, game.year, "car") or "jeep"], 1
    elif kind == "armour":
        ids, n = [pick_vehicle(rng, nat, game.year, "tank") or "gmc"], rng.randint(1, 3)
    elif horse:
        ids, n = (["horse_wagon", "panje_wagon"] if nat in ("ussr", "germany", "poland") else ["horse_wagon"]), \
            rng.randint(3, 6)
    else:
        ids = [t for t in TRUCKS.get(nat, []) if t in VEHICLES and VEHICLES[t].years[0] <= game.year] or \
            [pick_vehicle(rng, nat, game.year, "truck") or "gmc"]
        n = rng.randint(2, 5) if kind != "troops" else rng.randint(2, 3)
    sq = Squad(side, nat, "supply", f"{info['cargo']} for {info['dest']}")
    face = facing_toward_edge(info["to"]) if kind not in ("wounded",) else facing_toward_edge(info["to"])
    for i in range(n):
        vid = rng.choice(ids)
        if vid not in VEHICLES:
            continue
        pt, f = spot_and_facing(game, x - EDGE_VEC[info["to"]][0] * i * 6, y - EDGE_VEC[info["to"]][1] * i * 6,
                                VEHICLES[vid], 8, face)
        if pt is None:
            continue
        v = Vehicle(vid, side, nat, pt[0], pt[1], f)
        v.squad = sq
        v.ai["convoy"] = info
        sq.vehicles.append(v)
        game.add_vehicle(v)
        if kind == "troops" and VEHICLES[vid].seats:
            for _ in range(min(8, VEHICLES[vid].seats)):
                a = make_soldier(game, nat, "rifleman")
                a.x, a.y = v.x, v.y
                a.vehicle = v
                a.squad = sq
                v.passengers.append(a)
                sq.members.append(a)
                game.actors.append(a)
    if not sq.vehicles:
        return None
    info["n"] = len(sq.vehicles)
    sq.initial = len(sq.vehicles)
    game.squads.append(sq)
    return sq


def _column(game, side, nat, kind, x, y, tx, ty, info):
    """Men on foot: replacements marching up; prisoners marched back under guard."""
    from .spawn import make_squad
    rng = game.rng
    if kind == "march":
        sq = make_squad(game, side, nat, "rifle", x, y, name=f"replacements for {info['dest']}")
        info["n"] = len(sq.members)
        return sq
    enemy = other_side(side)
    guards = make_squad(game, side, nat, "rifle", x, y, name="prisoner escort")
    for a in guards.members[3:]:
        game.remove_actor(a)
    guards.members = guards.members[:3]
    pws = make_squad(game, enemy, game.side_nation(enemy), "rifle", x, y, name="prisoners")
    pws.no_count = True
    for a in pws.members:
        a.state = "surrendered"
        a.weapon = None
        for it in list(a.inv):
            if it.t.kind in ("gun", "grenade", "mag", "ammo", "clip", "explosive"):
                a.remove_item(it)
        a.ai["captor"] = guards.members[0].id if guards.members else None
        a.ai["pw_order"] = "follow"
        a.ai["searched"] = True
    info["n"] = len(guards.members)
    info["pws"] = pws.id
    return guards


def _arrivals(game):
    """Convoys at the far edge: gone on to where they were going - and the replacements and tanks there join
    that front."""
    st = _state(game)
    strat = game.strategic
    for sid, info in list(st["convoys"].items()):
        sq = next((q for q in game.squads if q.id == sid), None)
        if sq is None:
            del st["convoys"][sid]
            continue
        e = info["to"]
        left = [v for v in sq.vehicles if not v.dead]
        men = [a for a in sq.members if a.active and a.vehicle is None]
        gone_any = False
        for v in left:
            if game._edge_gap(e, v.x, v.y) <= 6:       # (the lead lorry turning onto the road out: the next moves up)
                dest = strat.at(game.sector.x + EDGE_VEC[e][0], game.sector.y + EDGE_VEC[e][1])
                if dest is not None and dest.control == info["side"] and info["kind"] in RESOURCE:
                    from .sustain import deliver
                    deliver(dest, info["side"], RESOURCE[info["kind"]], info.get("payload", 0) / max(1, info["n"]))
                for a in list(v.passengers):
                    game.remove_actor(a)
                    a.state = "departed"
                    if a in sq.members:
                        sq.members.remove(a)
                game.lift_vehicle(v)
                v.x = v.y = -99
                if v in game.vehicles:
                    game.vehicles.remove(v)
                sq.vehicles.remove(v)
                gone_any = True
        for a in men:
            if game._edge_gap(e, a.x, a.y) <= 4:
                game.remove_actor(a)
                a.state = "departed"
                sq.members.remove(a)
                gone_any = True
        if info["kind"] == "prisoners" and info.get("pws"):
            pw = next((q for q in game.squads if q.id == info["pws"]), None)
            for a in list(pw.members if pw else ()):
                if a.alive and game._edge_gap(e, a.x, a.y) <= 4:
                    game.remove_actor(a)
                    a.state = "departed"
                    pw.members.remove(a)
        if gone_any and sq.state == "hold":
            sq.arrived = False                         # (the rest follow on)
            sq.state = "advance"
        if gone_any and not sq.vehicles and not [a for a in sq.members if a.active]:
            dest = strat.at(game.sector.x + EDGE_VEC[e][0], game.sector.y + EDGE_VEC[e][1])
            if dest is not None and dest.control == info["side"] and dest is not game.sector:
                add = {"troops": {"inf": 1}, "armour": {"tank": 1}, "march": {"inf": 1}}.get(info["kind"])
                if add:
                    from collections import Counter
                    dest.units[info["side"]].update(Counter(add))
            sq.gone = True
            del st["convoys"][sid]
        elif game.turn - info["start"] > 4000:
            del st["convoys"][sid]                     # stuck somewhere: it's just part of the scenery now


def convoy_hit(game, v, attacker=None):
    """A convoy vehicle destroyed (combat.destroy_vehicle calls this): a cut in the road on the war map."""
    info = v.ai.get("convoy")
    if not info or game.strategic is None or info.get("counted_" + str(v.id)):
        return
    info["counted_" + str(v.id)] = True
    info["lost"] = info.get("lost", 0) + 1
    side = info["side"]
    amount = CUT.get(info["kind"], 0.05)
    s = game.sector
    word = {"ammunition": "An ammunition convoy", "fuel": "A fuel convoy", "rations": "A supply column",
            "troops": "A lorry-load of replacements", "armour": "Tanks going up", "wounded": "An ambulance",
            "dispatch": "A dispatch rider", "staff": "A staff car"}.get(info["kind"], "A convoy")
    fronts = game.strategic.interdict(side, s, amount, f"{word} was destroyed on the road through {s.name}.")
    p = game.player
    if p is None:
        return
    if attacker is p or (p.vehicle is not None and attacker is p.vehicle):
        if side != p.side:
            if info["kind"] == "wounded":
                _ambulance(game)
            elif info["lost"] == 1:
                # (what you can see of it burning - not where it was going)
                game.msg(f"It was carrying {info['cargo']}: it's burning all over the road.", "good")
    elif side == p.side and game.can_see(v.x, v.y) and info["lost"] == 1:
        game.msg(f"The {info['cargo']} for {info['dest']} is burning on the road.", "warn")


def _ambulance(game):
    """An ambulance - the red crosses on its sides.  Armies that cared about the Geneva Convention cared."""
    from .duty import CARES_POW
    p = game.player
    game.msg("An ambulance. The red crosses were on its sides and roof.", "warn")
    care = CARES_POW.get(p.nation, 0.5)
    duty = getattr(game, "duty", None)
    if duty is not None and care > 0.5 and duty.watcher(game) is not None:
        duty.rep -= 10 * care
        duty.strikes += 1
        game.msg("Your officer saw it. There'll be questions.", "warn")


# ============================================================================ the fixtures of a rear area
def _posts(game):
    """Military police at the crossroads, engineers mending the road, linemen on the wire: behind each side's
    line where its supplies run."""
    from .ai import Order
    from .spawn import free_tile_near, make_soldier, place, pick_nation
    from .ai import Squad
    from . import tiles as T
    import numpy as np
    m = game.map
    rng = game.rng
    for side in SIDES:
        if lanes(game, side) is None:
            continue
        nat = pick_nation(game, side)
        roads = np.argwhere(np.isin(m.t, [T.ID[k] for k in ("road", "paved", "cobble") if k in T.ID]))
        if not len(roads):
            continue
        jobs = [("mp", 2, "traffic control post"), ("engineer", 3, "road repair party"), ("radioman", 2, "linemen")]
        for role, n, name in jobs:
            if rng.random() < 0.3:
                continue
            x, y = (int(v) for v in roads[rng.randrange(len(roads))])
            pt = free_tile_near(game, x, y, 3)
            if pt is None:
                continue
            sq = Squad(side, nat, "rear", name)
            sq.no_count = True
            sq.order = Order("hold", target=pt, radius=2)
            sq.arrived = True
            for _ in range(n):
                a = make_soldier(game, nat, role)
                a.squad = sq
                sq.members.append(a)
                place(game, a, pt[0], pt[1], 2)
                a.ai["post"] = (a.x, a.y)
            sq.leader = sq.members[0] if sq.members else None
            sq.initial = len(sq.members)
            if sq.members:
                game.squads.append(sq)


def _depots(game):
    """A depot on this map blown up (its ammunition stacks mostly gone): its sector supplies nothing, until the
    war map's own reckoning sets up another."""
    from . import tiles as T
    st = _state(game)
    s = game.sector
    if game.turn % 30:
        return
    ammo = T.ID.get("ammo_stack")
    for r in getattr(game.map, "gen_positions", None) or []:
        if r.get("kind") != "depot" or not r.get("rect"):
            continue
        x0, y0, bw, bh = r["rect"]
        n = int((game.map.t[x0:x0 + bw, y0:y0 + bh] == ammo).sum())
        key = (x0, y0, r.get("side"))
        base = st["depots"].setdefault(key, n)
        if base and n <= base * 0.35 and not r.get("destroyed"):
            r["destroyed"] = True
            side = r.get("side")
            for inst in s.installations:
                if inst[0] == "depot" and inst[1] == side:
                    inst[2] = False
            game.strategic.interdict(side, s, 1.0, f"The {('Allied' if side == 'allies' else 'Axis')} supply depot "
                                                   f"at {s.name} has gone up.")
            game.msg("The depot goes up in a roar that shakes the ground for a mile. Whatever the front was going "
                     "to be fed from this week, it won't be this.", "good" if side != game.player.side else "death")


def describe(v) -> str | None:
    """A convoy vehicle's load and destination, for the look text (your own side's: you'd know, or ask)."""
    info = v.ai.get("convoy")
    if not info:
        return None
    return f"{info['cargo']} for {info['dest']}"
