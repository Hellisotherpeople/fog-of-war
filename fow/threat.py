"""What the war does to the ground you're standing on.

Nowhere is safe, but everywhere is dangerous in its own way.  In the front line the
enemy probes at night, raids trenches, puts snipers out, shells whatever moves - and
now and then comes over in strength, after a bombardment, at dawn.  Take a village
and expect it back before nightfall: counterattacks come fast.  A mile back it's
harassing fire and the odd patrol that got through.  In the rear it's the sky:
fighter-bombers hunting anything on the roads, bombers after the depots and the rail
yards, and at night the partisans come out of the woods.  On the coast, the enemy's
navy.  Behind enemy lines, once they know you're there, a search party.

The longer you stay put, the more the enemy knows about you and the more he brings.
Every minute the director looks at where you are and what's around, and rolls.
"""
from __future__ import annotations

from collections import Counter

from .constants import SIDES, other_side

# who fights behind the Axis lines, where
PARTISANS = {"barbarossa41": "ussr", "moscow41": "ussr", "kursk43": "ussr", "don43": "ussr",
             "stalingrad42": "ussr", "uranus42": "ussr", "normandy_airborne44": "france", "omaha44": "france",
             "bocage44": "france", "changsha41": "china", "poland39": "poland"}
# who does the long-range raiding
COMMANDOS = {"allies": ["uk", "usa", "ussr", "australia", "newzealand"], "axis": ["germany", "japan", "italy"]}
COMMANDO_NAME = {"uk": "Commando", "usa": "Ranger", "ussr": "razvedchiki", "australia": "independent company",
                 "newzealand": "LRDG patrol", "germany": "Brandenburger", "japan": "raiding party",
                 "italy": "arditi"}


def _state(game):
    st = game.__dict__.get("threat")
    if st is None or st.get("sector") != (game.sector.x, game.sector.y):
        st = game.threat = dict(sector=(game.sector.x, game.sector.y), since=game.turn, last=game.turn,
                                events=[], retire=[], warned=None)
    return st


def _friendly_spot(game, side):
    """Somewhere our troops are thick on the ground (what an enemy observer would pick)."""
    pts = [(a.x, a.y) for a in game.actors if a.side == side and a.active and a.vehicle is None]
    pts += [(v.x, v.y) for v in game.vehicles if v.side == side and not v.dead]
    if not pts:
        p = game.player
        return (p.x, p.y)
    best, bn = pts[0], -1
    for x, y in game.rng.sample(pts, min(12, len(pts))):
        n = sum(1 for (a, b) in pts if abs(a - x) + abs(b - y) <= 8)
        if n > bn:
            best, bn = (x, y), n
    return best


def _installation_spot(game, side):
    """A depot, battery, HQ or aid post of ours on this map, if any."""
    recs = [r for r in (getattr(game.map, "gen_positions", None) or []) if r.get("side") == side and r.get("kind")
            in ("depot", "artillery", "hq", "aid", "motor_pool", "aa", "airfield", "naval_base")]
    if recs:
        r = game.rng.choice(recs)
        return (r.get("x", game.map.w // 2), r.get("y", game.map.h // 2)), r.get("kind")
    return None, None


def _enemy_edge(game, enemy):
    """Which edge the enemy comes from: toward his nearest held ground."""
    st = game.strategic
    s = game.sector
    best = None
    for e, (dx, dy) in (("N", (0, -1)), ("S", (0, 1)), ("E", (1, 0)), ("W", (-1, 0))):
        n = st.at(s.x + dx, s.y + dy)
        if n is not None and n.control == enemy and n.playable:
            from .strategic import power
            pw = power(n.units[enemy])
            if best is None or pw > best[1]:
                best = (e, pw, n)
    if best is not None:
        return best[0], best[2]
    return game.home_edge(enemy), None


def _say(game, text, kind="radio"):
    game.msg(text, kind)


def update(game):
    """Once a minute: does the war come to you?"""
    if game.game_over or getattr(game, "pow", None) is not None or game.sector is None:
        return
    p = game.player
    if p is None or not p.alive:
        return
    rng = game.rng
    st = game.strategic
    s = game.sector
    side = p.side
    enemy = other_side(side)
    T = _state(game)
    # squads sent in on a raid go home when their time's up
    for sid, until in list(T["retire"]):
        if game.turn >= until:
            for sq in game.squads:
                if sq.id == sid and sq.members:
                    from .ai import Order
                    sq.order = Order("retreat", issued=game.turn)
            T["retire"].remove((sid, until))
    if game.turn - T["last"] < 240:           # at least four minutes between visitations
        return
    wait = (game.turn - T["since"]) / 60.0    # minutes you've been here
    press = min(3.0, 1.0 + wait / 25.0)
    hour = game.hour_float()
    night = game.is_night()
    dawn = 4.0 <= hour <= 7.0
    held = s.control
    fd = 0 if held != side else st._front_distance(s, side)      # a battle for their ground is the front
    th = game.theatre
    arty = th["arty"].get(enemy, 0.5)
    air = th["air"].get(enemy, 0.5)
    armor = th["armor"].get(enemy, 0.3)
    edge, nb = _enemy_edge(game, enemy)
    from .strategic import power
    nb_power = power(nb.units[enemy]) if nb is not None else 0.0
    ours = sum(1 for a in game.actors if a.side == side and a.active)
    theirs_here = sum(1 for a in game.actors if a.side == enemy and a.active)
    weather_ok = game.weather not in ("fog", "sandstorm", "snow", "rain")
    recent_capture = getattr(s, "captured_tick", -99) >= st.ticks - 3 and held == side
    cut_off = held == side and st.supply_of(side, s) <= 0.0
    coastal = s.sea_edge is not None or any(n.biome == "sea" for n in st.neighbors(s))
    attacker = st.attacker == enemy

    rolls = []                                  # (weight, name)

    def add(name, w):
        if w > 0:
            rolls.append((w, name))

    behind = held != side and ours <= 6             # alone (or nearly) on their ground
    if behind:
        # behind their lines: they look for you once they've an idea you're there
        heat = min(1.0, getattr(game, "noise", 0.0) / 100.0) + (0.3 if theirs_here == 0 else 0.0)
        add("search", 0.02 * press * (0.3 + heat))
        add("air_raid", 0.004 * air if not night and weather_ok else 0)
    else:
        if fd <= 1 and nb is not None:
            dawn_bonus = 2.2 if dawn else 1.0
            add("assault", 0.006 * (nb_power / 8.0) * press * dawn_bonus * (1.4 if attacker else 0.7)
                * (1.8 if cut_off else 1.0))
            if recent_capture:
                add("counterattack", 0.05 * press)
            add("patrol", 0.012 * (2.0 if night else 0.5))
            add("raid", 0.006 * (2.5 if night else 0.2) * press)
            add("sniper", 0.008 * (0.3 if night else 1.0) * press)
        if fd <= 3:
            add("harass", 0.015 * arty * (1.0 if fd <= 1 else 0.6) * press)
        if not night and weather_ok and air > 0.2:
            add("air_raid", 0.01 * air * (1.5 if fd >= 2 else 1.0))
        if fd >= 3 and air > 0.5 and not night and weather_ok and game.year >= 1942.5 and \
                s.biome in ("town", "city_ruins", "factory", "village") and enemy == "allies":
            add("carpet", 0.004 * air)
        if night and fd >= 2 and air > 0.3:
            add("night_raid", 0.004 * air)
        part = PARTISANS.get(th.get("id", ""))
        if part and side == "axis" and fd >= 2 and s.biome in ("forest", "marsh", "village", "farmland", "hills",
                                                                "bocage", "steppe"):
            add("partisans", 0.012 * (2.2 if night else 0.6))
        if fd >= 2 and s.installations and night:
            add("commando", 0.003 * press)
        if coastal and enemy == "allies" and game.year >= 1942:
            add("naval", 0.004 * press)
    if not rolls:
        return
    total = sum(w for w, _ in rolls)
    if rng.random() > min(0.6, total):
        return
    ev = rng.choices([n for _, n in rolls], [w for w, _ in rolls])[0]
    T["last"] = game.turn
    T["events"].append((game.turn, ev))
    fire(game, ev, side, enemy, edge, nb)


def fire(game, ev, side, enemy, edge, nb):
    """Make it happen."""
    from .ai import Order
    from .spawn import edge_band_point, make_squad, pick_nation
    rng = game.rng
    st = game.strategic
    T = _state(game)
    radio = game.player_near_radio(side)
    enat = pick_nation(game, enemy)
    m = game.map

    def edge_pt(depth=(1, 4)):
        return edge_band_point(game, edge, rng, depth=depth) if edge else (rng.randint(5, m.w - 5), 2)

    if ev in ("assault", "counterattack"):
        units = Counter()
        if nb is not None:
            units = st._detach(nb.units[enemy], 0.45 if ev == "assault" else 0.35)
        if sum(units.values()) < 3 * game.__dict__.get("troop_scale", 1.0):
            units.update({"inf": st.sc(rng.randint(3, 6)), "mg": st.sc(1)})
            if game.theatre["armor"].get(enemy, 0) > 0.3 and rng.random() < 0.5:
                units["tank"] += st.sc(rng.randint(1, 2))
        delay = rng.randint(60, 180)
        tx, ty = _friendly_spot(game, side)
        if game.theatre["arty"].get(enemy, 0) > 0.2:
            game.support.barrage(enemy, tx, ty, 10, int(20 + 30 * game.theatre["arty"][enemy]),
                                 delay=max(5, delay - 90))
        game.schedule_wave(enemy, units, edge, delay=delay)
        if radio or game.rng.random() < 0.5:
            where = {"N": "north", "S": "south", "E": "east", "W": "west"}.get(edge, "front")
            if ev == "counterattack":
                _say(game, f"Radio: 'Enemy forming up to the {where} - they want it back. Counterattack expected. "
                           f"Dig in!'")
            else:
                _say(game, f"Radio: 'Observers report heavy movement to the {where}. "
                           f"{'Tanks heard. ' if units.get('tank') else ''}Stand to!'")
        else:
            _say(game, "The ground trembles with distant engines. Somewhere men are shouting orders in the "
                       "enemy's language.", "sound")
        return
    if ev in ("patrol", "raid", "search"):
        kind = {"patrol": "recon", "raid": "raid", "search": "raid"}[ev]
        x, y = edge_pt()
        if ev == "search":
            p = game.player
            c = game.brains[enemy].contacts.get(p.id)
            tgt = (c.x, c.y) if c is not None else (p.x + rng.randint(-15, 15), p.y + rng.randint(-15, 15))
        else:
            tgt = _friendly_spot(game, side)
        sq = make_squad(game, enemy, enat, kind, x, y, name={"patrol": "patrol", "raid": "raiding party",
                                                              "search": "search party"}[ev])
        sq.no_count = True
        sq.order = Order("attack" if ev != "patrol" else "move", target=tgt, radius=6, issued=game.turn)
        game.command.attach_squad(game, sq) if hasattr(game.command, "attach_squad") else None
        T["retire"].append((sq.id, game.turn + rng.randint(420, 900)))
        if ev == "search":
            _say(game, "Dogs barking, somewhere back along your trail. They're looking for you.", "warn")
        elif rng.random() < 0.35:
            _say(game, "A sentry hisses: 'Movement out front...'", "sound")
        return
    if ev == "sniper":
        # somewhere with a view and some cover
        for _ in range(30):
            x, y = edge_pt(depth=(8, 30))
            if m.in_bounds(x, y) and m.walk[x, y] and m.conceal[x, y] >= 30:
                break
        sq = make_squad(game, enemy, enat, "sniper", x, y, name="sniper")
        sq.no_count = True
        sq.order = Order("hold", target=(x, y), issued=game.turn)
        T["retire"].append((sq.id, game.turn + rng.randint(900, 1800)))
        return
    if ev == "harass":
        tx, ty = _friendly_spot(game, side)
        game.support.barrage(enemy, tx + rng.randint(-12, 12), ty + rng.randint(-12, 12), 6, rng.randint(4, 10),
                             delay=rng.randint(3, 15))
        return
    if ev in ("air_raid", "night_raid", "carpet"):
        spot, kind = _installation_spot(game, side)
        if spot is None or rng.random() < 0.5:
            spot = _friendly_spot(game, side)
        roles = {"air_raid": ("fighterbomber", "divebomber", "attacker", "fighter", "bomber"),
                 "night_raid": ("nightbomber",), "carpet": ("heavybomber", "bomber")}[ev]
        ok = game.support.launch_sortie(enemy, target=spot, roles=roles)
        if ok and ev == "carpet":
            for _ in range(rng.randint(1, 3)):
                game.support.launch_sortie(enemy, target=(spot[0] + rng.randint(-20, 20),
                                                          spot[1] + rng.randint(-12, 12)), roles=roles, quiet=True)
            _say(game, "The sky fills with the drone of hundreds of engines. Someone screams 'Bombers!'", "death")
        return
    if ev == "partisans":
        pnat = PARTISANS.get(game.theatre.get("id", ""))
        spots = [(x, y) for x, y in ((rng.randint(10, m.w - 10), rng.randint(10, m.h - 10)) for _ in range(60))
                 if m.walk[x, y] and m.conceal[x, y] >= 35]
        if not spots:
            return
        x, y = spots[0]
        sq = make_squad(game, other_side(side), pnat, "partisan", x, y, name="partisan detachment")
        sq.no_count = True
        tgt, kind = _installation_spot(game, side)
        sq.order = Order("ambush" if tgt is None else "attack", target=tgt or (x, y), radius=8, issued=game.turn)
        T["retire"].append((sq.id, game.turn + rng.randint(300, 700)))
        if game.rng.random() < 0.5:
            _say(game, "A shot from the treeline, then a ragged volley - partisans!", "warn")
        return
    if ev == "commando":
        cn = [n for n in COMMANDOS[enemy] if n in {nat for nat, _ in game.theatre["sides"][enemy]}] or \
            [game.side_nation(enemy)]
        cnat = rng.choice(cn)
        tgt, kind = _installation_spot(game, side)
        if tgt is None:
            tgt = _friendly_spot(game, side)
        x, y = edge_pt(depth=(1, 3))
        sq = make_squad(game, enemy, cnat, "commando", x, y, name=f"{COMMANDO_NAME.get(cnat, 'raiding')} party")
        sq.no_count = True
        sq.order = Order("attack", target=tgt, radius=4, issued=game.turn, roe="hold")
        T["retire"].append((sq.id, game.turn + rng.randint(600, 1100)))
        return
    if ev == "naval":
        sea = game.strategic
        s = game.sector
        e = s.sea_edge or next((d for d, (dx, dy) in (("N", (0, -1)), ("S", (0, 1)), ("E", (1, 0)), ("W", (-1, 0)))
                                if (n := sea.at(s.x + dx, s.y + dy)) is not None and n.biome == "sea"), None)
        tx, ty = _friendly_spot(game, side)
        if game.support.barrage(enemy, tx, ty, 12, rng.randint(12, 30), delay=rng.randint(20, 60), naval=True):
            _say(game, "Far out to sea, a ripple of flashes. Then the freight-train roar of heavy naval shells.",
                 "death")
        return
