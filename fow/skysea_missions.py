"""Missions in the air and at sea, and getting into (and out of) the sky and the sea.

Air: fighter sweep, interception of a bomber raid, bomber escort, ground attack, dive
bombing, torpedo attack, strategic bombing (you as pilot, bombardier or one of the
gunners), photo reconnaissance.  Sea: surface action, carrier battle, convoy escort,
submarine patrol, shore bombardment.  Every mission starts from a real place on the
war map - a friendly airfield, a carrier, a port - and ends by coming home, by going
down, or by drifting in a dinghy.
"""
from __future__ import annotations

import math

from .constants import other_side
from .data.ships import SHIPS, available
from .data.vehicles import AIRCRAFT
from .skysea import SEC, CARRIER_AIR, Plane, Ship, SkySea, _latest, bearing

AIR_MISSIONS = {
    "resupply": "Air supply: carry food, ammunition and medicine to troops short of supplies. Drop low and slow, then return.",
    "sweep": "Fighter sweep: over the front, find their fighters and fight them.",
    "intercept": "Interception: a raid is coming in. Get at the bombers before they reach the target.",
    "escort": "Escort: take the bombers to the target and bring them home. Stay with them.",
    "attack": "Ground attack: columns, guns and trucks behind their lines. Go in low.",
    "dive": "Dive bombing: put a bomb on the target. Point the aircraft at it and hold your nerve.",
    "torpedo": "Torpedo attack: the enemy fleet. Low, slow and straight at them through the flak.",
    "strategic": "Strategic bombing: the factories and rail yards deep in their country. Fly the stream, "
                 "hold formation, and when the bomb doors open, don't flinch.",
    "recon": "Photo reconnaissance: fly over the target, take the pictures, and get them home.",
    "kamikaze": "Special attack: find the enemy fleet, pick a carrier, and dive into it. There is no return leg.",
}
SEA_MISSIONS = {
    "surface": "Surface action: an enemy force is out there. Find it and sink it.",
    "carrier": "Carrier battle: find their carriers before they find yours. Launch the strike.",
    "convoy": "Convoy escort: the merchantmen must get through. The wolfpack is waiting.",
    "sub": "Submarine patrol: hunt the enemy's shipping. Stay alive when the escorts come.",
    "bombard": "Shore bombardment: the troops ashore need the big guns.",
}
AIR_ROLE_TYPES = {"sweep": ("fighter",), "intercept": ("fighter",), "escort": ("fighter",),
                  "resupply": ("transport",),
                  "attack": ("fighterbomber", "attacker", "fighter"), "dive": ("divebomber",),
                  "torpedo": ("torpedo",), "strategic": ("heavybomber", "bomber"), "recon": ("fighter",),
                  "kamikaze": ("fighterbomber", "fighter")}


def _planes_of(nation, year, roles):
    return [a for a in AIRCRAFT.values() if nation in a.nations and a.years[0] <= year < a.years[1] and a.role in roles]


def eligible_air(game, kind):
    if kind == "kamikaze" and not (game.player_nation == "japan" and game.year >= 1944.8 and has_sea(game)):
        return False
    return bool(_planes_of(game.player_nation, game.year, AIR_ROLE_TYPES[kind]))


def has_sea(game):
    st = game.strategic
    s = game.sector
    for dx in range(-8, 9):
        for dy in range(-8, 9):
            c = st.at(s.x + dx, s.y + dy, create=True)
            if c is not None and c.biome == "sea":
                return c
    return None


def eligible_sea(game, kind):
    n = game.player_nation
    if not available(n, game.year):
        return False
    if kind == "carrier":
        return bool(available(n, game.year, ("cv", "cve")))
    if kind == "sub":
        return bool(available(n, game.year, "ss"))
    return has_sea(game) is not None


# ====================================================================== the air

def _base_sector(game, side):
    """A friendly airfield (or at least friendly ground well back from the front)."""
    st = game.strategic
    s = game.sector
    best = None
    for dx in range(-6, 7):
        for dy in range(-6, 7):
            c = st.at(s.x + dx, s.y + dy, create=True)
            if c is None or c.control != side or not c.playable:
                continue
            score = (10 if c.installs(side, "airfield") else 0) + min(3, st._front_distance(c, side)) - \
                0.4 * (abs(dx) + abs(dy))
            if best is None or score > best[0]:
                best = (score, c)
    return best[1] if best else s


def _target_sector(game, side, depth, base=None):
    """An enemy sector about `depth` behind their front (never the one you take off from)."""
    from .scenarios import _deep
    st = game.strategic
    c = _deep(game, side, depth)
    if c is not None and (base is None or (c.x, c.y) != (base.x, base.y)):
        return c
    base = base or game.sector
    enemy = other_side(side)
    best = None
    for dx in range(-10, 11):
        for dy in range(-10, 11):
            o = st.at(base.x + dx, base.y + dy, create=True)
            if o is None or o.control != enemy or not o.playable or (dx, dy) == (0, 0):
                continue
            score = abs(abs(dx) + abs(dy) - (depth + 1))
            if best is None or score < best[0]:
                best = (score, o)
    return best[1] if best else base


def _ground_targets(ss, c, side, kind):
    rng = ss.rng()
    cx, cy = (c.x + 0.5) * SEC, (c.y + 0.5) * SEC
    out = []
    names = {"column": "supply column", "tanks": "tank column", "artillery": "artillery battery", "depot": "supply depot",
             "bridge": "bridge", "factory": "factory", "railyard": "rail yards", "rail_yard": "rail yards",
             "power_station": "power station", "food_depot": "food warehouse", "airfield": "airfield"}
    kinds = {"attack": ["column", "column", "tanks", "artillery"], "dive": ["bridge", "depot", "artillery"],
             "strategic": ["factory", "railyard", "factory"], "recon": ["depot"]}.get(kind, ["depot"])
    if kind == "strategic":
        kinds = list(dict.fromkeys(k for k, sd, ok in c.installations if sd != side and ok and
                                  k in ("factory", "rail_yard", "power_station", "food_depot", "depot", "airfield")))
        kinds = kinds or ["column"]
    for i, k in enumerate(kinds):
        out.append(dict(id=10_000 + len(ss.ground) + i, kind=k, x=cx + rng.uniform(-8, 8), y=cy + rng.uniform(-8, 8),
                        hp={"column": 300, "tanks": 500, "artillery": 400, "depot": 900, "bridge": 700,
                            "factory": 2500, "railyard": 2000, "rail_yard": 2000, "power_station": 1200,
                            "food_depot": 900, "airfield": 1500}[k],
                        side=other_side(side), name=f"{names[k]} at {c.name}", sector=(c.x, c.y), dead=False))
    ss.ground += out
    return out


def launch_air(game, kind, at_id=None, station="pilot", base=None):
    """Take off on a mission. Creates the sky world and puts you in it."""
    rng = game.rng
    p = game.player
    side = p.side
    enemy = other_side(side)
    nat = p.nation
    yr = game.year
    if at_id is None:
        cands = _planes_of(nat, yr, AIR_ROLE_TYPES.get(kind, ("fighter",)))
        if kind == "resupply" and not cands:
            game.msg("No transport aircraft is available for an air supply sortie.", "info")
            return None
        if not cands:
            cands = _planes_of(nat, yr, ("fighter", "fighterbomber"))
        if not cands:
            return None
        at_id = rng.choices([a.id for a in cands], [max(1, a.freq) for a in cands])[0]
    base = base or _base_sector(game, side)
    if kind == "resupply":
        from .sustain import stores
        if AIRCRAFT[at_id].role != "transport" or min(stores(base, side)[k] for k in ("ammo", "food", "medical")) < 1 / 3:
            game.msg("Air supply needs a transport and ammunition, food and medical stores to load.", "warn")
            return None
    ss = SkySea(game, base.x, base.y)
    bx, by = (base.x + 0.5) * SEC, (base.y + 0.5) * SEC
    tgt_c = _target_sector(game, side, {"strategic": rng.randint(4, 7), "recon": rng.randint(2, 4),
                                        "attack": rng.randint(1, 2), "dive": rng.randint(1, 3)}.get(kind, 1), base)
    if kind == "resupply":
        candidates = [s for s in game.strategic.sectors() if s.control == side and s.playable and s is not base]
        tgt_c = min(candidates, key=lambda s: (game.strategic.supply_of(side, s),
                    abs(s.x - base.x) + abs(s.y - base.y)), default=base)
    tx, ty = (tgt_c.x + 0.5) * SEC, (tgt_c.y + 0.5) * SEC
    hdg = bearing(bx, by, tx, ty)
    me = Plane(at_id, side, nat, bx, by, hdg, 600, rng=rng)
    me.player = True
    me.home = (bx, by)
    me.crew[0]["skill"] = p.skill
    ss.planes.append(me)
    ss.player_plane = me
    ss.station = station if any(c["station"] == station for c in me.crew) else "pilot"
    ss.build_flak(side, radius=8)
    mission = dict(kind=kind, base=(base.x, base.y), base_pt=(bx, by), target_sector=(tgt_c.x, tgt_c.y),
                   target_pt=(tx, ty), stage="outbound", start=ss.t, kills0=me.kills, text=AIR_MISSIONS[kind])
    enat = game.side_nation(enemy)
    efighters = _planes_of(enat, yr, ("fighter",)) or _planes_of(enat, yr, ("fighterbomber",))

    def enemy_fighters(n, x, y, alt, role="fighter"):
        for i in range(n):
            if not efighters:
                return
            at = rng.choice(efighters).id
            e = Plane(at, enemy, enat, x + rng.uniform(-4, 4), y + rng.uniform(-4, 4), rng.uniform(0, 360),
                      alt + rng.uniform(-300, 500), rng=rng)
            e.ai = dict(role=role, station=(x, y), alt=alt)
            ss.planes.append(e)

    if kind in ("sweep", "recon", "attack", "dive", "resupply"):
        enemy_fighters(rng.randint(1, 4) if kind != "recon" else rng.randint(0, 2), tx, ty, 3000)
    if kind == "sweep":
        mission["need"] = rng.randint(1, 3)
    if kind == "intercept":
        # a raid heading for our base
        bombers = _planes_of(enat, yr, ("bomber", "heavybomber", "divebomber"))
        if bombers:
            n = rng.randint(4, 9)
            ldr = None
            for i in range(n):
                at = rng.choice(bombers).id
                b = Plane(at, enemy, enat, tx + (i % 3) * 1.5, ty + (i // 3) * 1.5, bearing(tx, ty, bx, by),
                          3500, rng=rng)
                b.ai = dict(role="bomber", wp=(bx, by), alt=3500, home_pt=(tx, ty))
                if ldr is not None:
                    b.ai["leader"] = ldr.id
                    b.ai["offset"] = ((i % 3) * 1.5 - 1.5, (i // 3) * 1.5)
                else:
                    ldr = b
                ss.planes.append(b)
            mission["raid"] = [p2.id for p2 in ss.planes if p2.side == enemy]
            enemy_fighters(rng.randint(2, 4), tx, ty, 4200, role="escort")
            for e in ss.planes:
                if e.ai.get("role") == "escort" and ldr is not None:
                    e.ai["leader"] = ldr.id
        mission["text"] += f" They're coming from the {_dirword(bx, by, tx, ty)}."
    if kind in ("escort", "strategic"):
        bombers = _planes_of(nat, yr, ("heavybomber", "bomber"))
        heavies = [b for b in bombers if b.role == "heavybomber"] or bombers
        ldr = None
        if kind == "strategic" and me.role in ("bomber", "heavybomber"):
            ldr = me
            me.ai = dict(role="bomber", wp=(tx, ty), alt=5500)
            me.alt = 5500
        n = rng.randint(6, 12)
        for i in range(n):
            if not heavies:
                break
            at = rng.choice(heavies).id
            b = Plane(at, side, nat, bx + (i % 4) * 1.2 - 2, by + (i // 4) * 1.2 + 1.5, hdg, 5500, rng=rng)
            b.ai = dict(role="bomber", wp=(tx, ty), alt=5500, home_pt=(bx, by))
            if ldr is not None:
                b.ai["leader"] = ldr.id
                b.ai["offset"] = ((i % 4) * 1.2 - 2, (i // 4) * 1.2 + 1.5)
            else:
                ldr = b
            ss.planes.append(b)
        mission["bombers"] = [b.id for b in ss.planes if b.side == side and b.role in ("bomber", "heavybomber")]
        if kind == "escort":
            me.alt = 6500
        enemy_fighters(rng.randint(4, 8), (bx + tx) / 2 + (tx - bx) * 0.3, (by + ty) / 2 + (ty - by) * 0.3, 6000,
                       role="intercept")
        _ground_targets(ss, tgt_c, side, "strategic")
    if kind in ("attack", "dive", "recon"):
        _ground_targets(ss, tgt_c, side, kind)
    if kind == "kamikaze":
        me.bombs = [[250, 5, 1]]
    if kind in ("torpedo", "kamikaze") or (kind == "dive" and rng.random() < 0.4 and has_sea(game)):
        sea = has_sea(game) or tgt_c
        _enemy_fleet(ss, game, enemy, (sea.x + 0.5) * SEC, (sea.y + 0.5) * SEC,
                     "carrier" if kind == "kamikaze" else rng.choice(("task", "convoy")))
        mission["target_pt"] = ((sea.x + 0.5) * SEC, (sea.y + 0.5) * SEC)
        mission["ships"] = [s.id for s in ss.ships if s.side == enemy]
    if not me.ai:
        # the aircraft flies its mission whoever's at the controls (the pilot, when you're elsewhere in her)
        role = {"resupply": "resupply", "strategic": "bomber", "dive": "dive", "torpedo": "torpedo", "attack": "attack", "recon": "recon",
                "kamikaze": "kamikaze"}.get(kind, "cap" if kind in ("sweep", "intercept", "escort") else "fighter")
        me.ai = dict(role=role, wp=mission["target_pt"], home_pt=(bx, by),
                     alt=5500 if role == "bomber" else 3000, station=mission["target_pt"])
    if kind == "resupply":
        from .airlogistics import load
        me.ai["alt"] = 350
        me.alt = 350
        me.throttle = .65
        load(game, base, me)
    ss.mission = mission
    game.skysea = ss
    game.domain = "air"
    return ss


def _dirword(x0, y0, x1, y1):
    from .skysea import compass
    return compass(bearing(x0, y0, x1, y1))


# ====================================================================== the sea

def _enemy_fleet(ss, game, side, x, y, kind):
    rng = ss.rng()
    nat = game.side_nation(side)
    yr = game.year
    comp = {"task": [("bb", "ca"), ("ca", "cl"), ("dd",), ("dd",), ("dd",)],
            "carrier": [("cv",), ("cv", "cve"), ("ca", "bb"), ("cl", "ca"), ("dd",), ("dd",), ("dd",)],
            "convoy": [("ap",), ("ap",), ("ap",), ("ap",), ("ap", "lst"), ("de", "dd"), ("de", "dd")],
            "subs": [("ss",), ("ss",), ("ss",)]}[kind]
    ldr = None
    made = []
    for i, classes in enumerate(comp):
        opts = available(nat, yr, classes) or available("usa" if side == "allies" else "japan", yr, classes)
        if not opts:
            continue
        st = rng.choices(opts, [o["freq"] for o in opts])[0]
        s = Ship(st["id"], side, nat, x + (i % 3) * 2 - 2, y + (i // 3) * 2, rng.uniform(0, 360), rng=rng)
        s.name = _ship_name(game, nat, s, ss)
        s.ai = dict(role="sub" if st["cls"] == "ss" else "screen" if st["cls"] in ("dd", "de") else "line")
        if ldr is None and st["cls"] != "ss":
            ldr = s
            s.ai["wp"] = (x + rng.uniform(-60, 60), y + rng.uniform(-60, 60))
        elif st["cls"] != "ss":
            s.ai["leader"] = ldr.id
            s.ai["offset"] = ((i % 3) * 2 - 2, (i // 3) * 2 + 2)
        ss.ships.append(s)
        made.append(s)
    return made


def put_to_sea(game, kind, sid=None, station="bridge"):
    """Go to sea: your ship (and the others), where the mission is."""
    rng = game.rng
    p = game.player
    side = p.side
    enemy = other_side(side)
    nat = p.nation
    yr = game.year
    sea = has_sea(game)
    if sea is None:
        return None
    ss = SkySea(game, sea.x, sea.y)
    x, y = (sea.x + 0.5) * SEC, (sea.y + 0.5) * SEC
    want = {"surface": ("dd", "cl", "ca", "bb"), "carrier": ("cv", "cve"), "convoy": ("dd", "de"),
            "sub": ("ss",), "bombard": ("bb", "ca", "cl", "dd")}[kind]
    if sid is None:
        opts = available(nat, yr, want) or available(nat, yr)
        if not opts:
            return None
        rank = p.rank
        # the more senior you are, the bigger the ship you're on
        big = [o for o in opts if o["cls"] in ("bb", "cv", "ca")]
        small = [o for o in opts if o["cls"] in ("dd", "de", "ss", "pt", "cl")]
        pool = big if rank >= 13 and big else small if rank < 11 and small else opts
        sid = rng.choices([o["id"] for o in pool], [o["freq"] for o in pool])[0]
    me = Ship(sid, side, nat, x, y, rng.uniform(0, 360), rng=rng)
    me.player = True
    me.ai = dict(role="line", auto_fire=True)
    me.name = _ship_name(game, nat, me, ss)
    ss.ships.append(me)
    ss.player_ship = me
    ss.station = station
    # our own force
    friends = {"surface": [("dd",), ("dd",), ("cl", "ca")], "carrier": [("ca", "bb"), ("dd",), ("dd",), ("cl",)],
               "convoy": [("ap",), ("ap",), ("ap",), ("ap",), ("ap",), ("de", "dd")], "sub": [],
               "bombard": [("dd",), ("dd",)]}[kind]
    for i, classes in enumerate(friends):
        opts = available(nat, yr, classes)
        if not opts:
            continue
        st = rng.choices(opts, [o["freq"] for o in opts])[0]
        # a screen a kilometre or so out (ships didn't steam in each other's pockets)
        off = ((i % 3) * 9 - 9, 8 + (i // 3) * 9)
        f = Ship(st["id"], side, nat, x + off[0], y + off[1], me.hdg, rng=rng)
        f.name = _ship_name(game, nat, f, ss)
        f.ai = dict(role="screen" if st["cls"] in ("dd", "de") else "line", leader=me.id, offset=off)
        ss.ships.append(f)
    # the enemy
    # somewhere over the horizon, on open water
    ex = ey = None
    for tries in range(60):
        d = rng.uniform(150, 240)
        ang = rng.uniform(0, 2 * math.pi)
        cx2, cy2 = x + math.cos(ang) * d, y + math.sin(ang) * d
        if all(ss.is_sea(cx2 + ox, cy2 + oy) for ox, oy in ((0, 0), (6, 0), (-6, 0), (0, 6), (0, -6))):
            ex, ey = cx2, cy2
            break
    if ex is None:
        ex, ey = x + 150, y
    ekind = {"surface": "task", "carrier": "carrier", "convoy": "subs", "sub": "convoy", "bombard": "task"}[kind]
    if kind != "bombard" or rng.random() < 0.5:
        _enemy_fleet(ss, game, enemy, ex, ey, ekind)
    mission = dict(kind=kind, stage="search", start=ss.t, text=SEA_MISSIONS[kind], home=(x, y),
                   enemies=[s.id for s in ss.ships if s.side == enemy])
    if kind == "bombard":
        land = _coast_target(ss, game, side)
        if land is not None:
            mission["shore"] = land
            mission["text"] += f" Target: {land[2]}."
    if kind == "convoy":
        mission["convoy"] = [s.id for s in ss.ships if s.side == side and s.cls == "ap"]
        mission["until"] = ss.t + 1800
    ss.mission = mission
    game.skysea = ss
    game.domain = "sea"
    return ss


# the jobs a ship is given after her first (fow/naval.py): not offered at the start of a game
EXTRA_SEA = {
    "rtb": "Return to base.",
    "cover": "Cover the landings: stay on station and keep their aircraft off the beaches.",
    "asw": "A submarine has been reported in the area. Hunt it down.",
    "rescue": "Men in the water - survivors of a sinking. Get there and pick them up.",
}


def _open_water(ss, x, y, dmin, dmax, rng):
    for tries in range(80):
        d = rng.uniform(dmin, dmax)
        ang = rng.uniform(0, 2 * math.pi)
        cx2, cy2 = x + math.cos(ang) * d, y + math.sin(ang) * d
        if all(ss.is_sea(cx2 + ox, cy2 + oy) for ox, oy in ((0, 0), (6, 0), (-6, 0), (0, 6), (0, -6))):
            return cx2, cy2
    return None


def new_orders(ss, game, kind, sorties=0, home=None) -> bool:
    """The next job for the force you're already in: the same ships (what's left of them), a new enemy."""
    rng = game.rng
    me = ss.player_ship
    if me is None or not me.alive:
        return False
    side = me.side
    enemy = other_side(side)
    # the last fight is over: the dead are gone, their survivors have withdrawn
    ss.ships = [sh for sh in ss.ships if sh.alive and sh.side == side]
    ss.planes = [pl for pl in ss.planes if pl.alive and pl.side == side]
    ss.torps = []
    x, y = me.x, me.y
    m = dict(kind=kind, stage="search", start=ss.t, home=home or (x, y), enemies=[], sorties=sorties,
             text=EXTRA_SEA.get(kind) or SEA_MISSIONS.get(kind, "New orders."))
    if kind in ("surface", "carrier", "sub", "convoy", "asw", "bombard"):
        spot = _open_water(ss, x, y, 150 if kind != "asw" else 60, 240 if kind != "asw" else 120, rng)
        if spot is None:
            return False
        ekind = {"surface": "task", "carrier": "carrier", "sub": "convoy", "convoy": "subs", "asw": "subs",
                 "bombard": "task"}[kind]
        if kind != "bombard" or rng.random() < 0.4:
            made = _enemy_fleet(ss, game, enemy, spot[0], spot[1], ekind)
            if kind == "asw":
                for sh in made[1:]:
                    ss.ships.remove(sh)            # one boat reported, not a wolfpack
                made = made[:1]
            m["enemies"] = [sh.id for sh in made]
    if kind == "carrier" and not m["enemies"]:
        return False
    if kind == "bombard":
        cx, cy = int(x // SEC), int(y // SEC)
        land = None
        st = game.strategic
        for r in range(0, 8):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    c = st.at(cx + dx, cy + dy, create=True)
                    if land is None and c is not None and c.control == enemy and c.playable and any(
                            n.biome == "sea" for n in st.neighbors(c, create=True)):
                        land = ((c.x + 0.5) * SEC, (c.y + 0.5) * SEC, c.name, (c.x, c.y))
            if land:
                break
        if land is None:
            return False
        m["shore"] = land
        m["text"] += f" Target: {land[2]}."
    if kind == "convoy":
        opts = available(me.nation, game.year, ("ap",)) or available("usa" if side == "allies" else "japan",
                                                                   game.year, ("ap",))
        conv = []
        for i in range(4 if opts else 0):
            st_ = rng.choices(opts, [o["freq"] for o in opts])[0]
            off = ((i % 2) * 8 - 4, 10 + (i // 2) * 8)
            sh = Ship(st_["id"], side, me.nation, x + off[0], y + off[1], me.hdg, rng=rng)
            sh.name = _ship_name(game, me.nation, sh, ss)
            sh.ai = dict(role="line", leader=me.id, offset=off)
            ss.ships.append(sh)
            conv.append(sh.id)
        m["convoy"] = conv
        m["until"] = ss.t + 1800
    if kind == "cover":
        spot = _open_water(ss, x, y, 30, 80, rng) or (x, y)
        m["cover_pt"] = spot
        m["until"] = ss.t + 4 * 3600
        m["next_raid"] = ss.t + rng.randint(900, 2400)
    if kind == "rescue":
        spot = _open_water(ss, x, y, 40, 90, rng)
        if spot is None:
            return False
        m["rescue_pt"] = spot
        m["survivors"] = rng.randint(6, 140)
        m["until"] = ss.t + 8 * 3600
    ss.mission = m
    return True


def air_raid(ss, game, target):
    """An enemy strike coming in at the force: dive bombers, torpedo planes, a few fighters - and, late in the
    Pacific war, men who won't pull out."""
    from .skysea import Plane
    rng = ss.rng()
    side = other_side(target.side)
    nat = game.side_nation(side)
    yr = game.year
    roles = [("divebomber", "dive"), ("divebomber", "dive"), ("torpedo", "torpedo"), ("fighter", "strafe"),
             ("divebomber", "dive"), ("torpedo", "torpedo")]
    if nat == "japan" and yr >= 1944.8:
        roles += [("fighter", "kamikaze"), ("fighterbomber", "kamikaze")]
    ang = rng.uniform(0, 2 * math.pi)
    n = rng.randint(3, 6)
    made = 0
    for i in range(n):
        role, how = roles[i % len(roles)]
        types = _planes_of(nat, yr, (role,)) or _planes_of(nat, yr, ("fighter",))
        if not types:
            continue
        at = rng.choices(types, [t.freq if getattr(t, "freq", 0) else 1 for t in types])[0]
        a = ang + rng.uniform(-0.3, 0.3)
        pl = Plane(at.id, side, nat, target.x + math.cos(a) * 45, target.y + math.sin(a) * 45, 0,
                   2500 if how == "dive" else 400 if how == "torpedo" else 1500, rng=rng)
        pl.ai = dict(role=how if how != "strafe" else "attack", target=-target.id, wp=(target.x, target.y))
        if how == "kamikaze":
            pl.bombs = [[250, 3, 1]]
        ss.planes.append(pl)
        made += 1
    return made


def _coast_target(ss, game, side):
    st = game.strategic
    for dx in range(-6, 7):
        for dy in range(-6, 7):
            c = st.at(ss.cx + dx, ss.cy + dy, create=True)
            if c is not None and c.control == other_side(side) and c.playable and any(
                    n.biome == "sea" for n in st.neighbors(c, create=True)):
                return ((c.x + 0.5) * SEC, (c.y + 0.5) * SEC, c.name, (c.x, c.y))
    return None


SHIP_NAMES = {
    "usa": {"dd": ["USS Kidd", "USS Johnston", "USS Laffey", "USS O'Bannon", "USS Hoel", "USS Heermann", "USS Fletcher",
                   "USS Nicholas", "USS Radford"], "de": ["USS Samuel B. Roberts", "USS England", "USS Buckley"],
            "cl": ["USS Helena", "USS Boise", "USS Atlanta", "USS Juneau", "USS Cleveland", "USS Montpelier"],
            "ca": ["USS San Francisco", "USS Portland", "USS Chicago", "USS Baltimore", "USS Canberra"],
            "bb": ["USS Washington", "USS South Dakota", "USS North Carolina", "USS Iowa", "USS Missouri"],
            "cv": ["USS Enterprise", "USS Hornet", "USS Yorktown", "USS Essex", "USS Lexington", "USS Intrepid"],
            "cve": ["USS Gambier Bay", "USS St. Lo", "USS Kalinin Bay"], "ss": ["USS Wahoo", "USS Barb", "USS Tang",
                                                                                "USS Archerfish"],
            "pt": ["PT-109", "PT-59", "PT-41"], "ap": ["SS Jeremiah O'Brien", "SS John W. Brown"], "lst": ["LST-325"]},
    "uk": {"dd": ["HMS Kelly", "HMS Javelin", "HMS Onslow", "HMS Jervis", "HMS Kashmir"],
           "de": ["HMS Snowflake", "HMS Starling", "HMCS Sackville"], "cl": ["HMS Belfast", "HMS Sheffield", "HMS Dido"],
           "ca": ["HMS Exeter", "HMS Norfolk", "HMAS Australia"], "bb": ["HMS Duke of York", "HMS King George V",
                                                                         "HMS Warspite"],
           "cv": ["HMS Illustrious", "HMS Victorious", "HMS Formidable"], "ss": ["HMS Upholder", "HMS Tally-Ho"],
           "pt": ["MTB 102"], "ap": ["SS Ohio", "SS Empire Star"]},
    "germany": {"dd": ["Z 23", "Z 26", "Z 30", "Z 39"], "ca": ["Admiral Hipper", "Prinz Eugen"],
                "bb": ["Scharnhorst", "Gneisenau", "Bismarck", "Tirpitz"], "ss": ["U-48", "U-99", "U-96", "U-47", "U-110"],
                "pt": ["S-38", "S-100"]},
    "japan": {"dd": ["Yukikaze", "Amatsukaze", "Hatsuzuki", "Shigure", "Ayanami"], "ca": ["Chōkai", "Myōkō", "Haguro"],
              "bb": ["Kirishima", "Haruna", "Kongō", "Yamato", "Musashi"], "cv": ["Shōkaku", "Zuikaku", "Hiryū"],
              "ss": ["I-19", "I-58", "I-26"], "ap": ["Kinugawa Maru", "Yamaura Maru"]},
    "italy": {"dd": ["Artigliere", "Lanciere"], "ca": ["Zara", "Pola", "Fiume"], "bb": ["Littorio", "Vittorio Veneto"]},
    "ussr": {"dd": ["Soobrazitelny", "Bodry"], "cl": ["Kirov", "Maxim Gorky"], "ss": ["Shch-213", "Shch-406"]},
    "france": {"dd": ["Le Terrible", "Le Fantasque"]},
}


def _ship_name(game, nat, s, ss=None):
    rng = game.rng
    by = SHIP_NAMES.get(nat, {})
    world = ss or getattr(game, "skysea", None)
    used = {x.name for x in world.ships} if world is not None else set()
    pool = [n for n in by.get(s.cls, []) if n not in used]
    if pool:
        return rng.choice(pool)
    return s.name


def _old_ship_name(game, nat, s):
    rng = game.rng
    names = {"usa": ["USS Kidd", "USS Johnston", "USS Laffey", "USS O'Bannon", "USS Helena", "USS Boise",
                     "USS San Francisco", "USS Washington", "USS Enterprise", "USS Hornet", "USS Wahoo",
                     "USS Barb", "USS Hoel", "USS Heermann", "USS Atlanta"],
             "uk": ["HMS Kelly", "HMS Javelin", "HMS Onslow", "HMS Belfast", "HMS Sheffield", "HMS Duke of York",
                    "HMS Illustrious", "HMS Upholder", "HMS Jervis", "HMS Warspite", "HMS Exeter"],
             "germany": ["Z 23", "Z 26", "Admiral Hipper", "Prinz Eugen", "Scharnhorst", "Bismarck", "U-48",
                         "U-99", "U-96", "S-38"],
             "japan": ["Yukikaze", "Amatsukaze", "Kirishima", "Haruna", "Chōkai", "Shōkaku", "Zuikaku", "I-19",
                       "I-58", "Yamato", "Hatsuzuki"],
             "italy": ["Artigliere", "Zara", "Pola", "Littorio", "Vittorio Veneto", "Scirè"],
             "ussr": ["Soobrazitelny", "Kirov", "Marat", "Shch-213", "Bodry"],
             "france": ["Le Terrible", "Le Fantasque", "Dunkerque"]}.get(nat, [])
    used = {x.name for x in game.skysea.ships} if getattr(game, "skysea", None) else set()
    pool = [n for n in names if n not in used]
    return rng.choice(pool) if pool else s.name


# ====================================================================== is it done?

def check(ss: SkySea):
    m = ss.mission
    if not m or m.get("stage") in ("done", "failed"):
        return
    g = ss.game
    k = m["kind"]
    me = ss.player_plane
    ship = ss.player_ship
    rng = ss.rng()

    def done(text, merit=6):
        m["stage"] = "done"
        g.msg(text, "good")
        g.command.merit += merit
        g.duty.rep += 2
        if merit >= 8:
            g.command._award(g, 1, f"for the {k} mission")

    def fail(text):
        m["stage"] = "failed"
        g.msg(text, "warn")

    # the air
    if k in AIR_MISSIONS and me is not None:
        tx, ty = m["target_pt"]
        d = math.hypot(tx - me.x, ty - me.y)
        if k == "resupply" and m["stage"] == "outbound":
            dest = g.strategic.at(*m["target_sector"])
            if dest is None or dest.control != me.side:
                m.update(stage="home", aborted=True, text="The dropping zone has fallen. Bring the load home.")
                me.ai.update(role="home", wp=me.home)
                g.msg(m["text"], "warn")
        if k == "sweep" and me.kills - m["kills0"] >= m.get("need", 1) and m["stage"] != "home":
            m["stage"] = "home"
            m["text"] = "Good hunting. Now get home."
            g.msg("That's enough for one day. Turn for home.", "good")
        elif k == "intercept":
            raid = [ss.entity(i) for i in m.get("raid", [])]
            alive = [b for b in raid if b is not None and b.alive]
            if raid and len(alive) <= len(raid) // 2 and m["stage"] != "home":
                m["stage"] = "home"
                m["text"] = "The raid is broken up. Get home."
                g.msg("The raid is breaking up - they're jettisoning their bombs and running!", "good")
        elif k in ("escort", "strategic"):
            bombers = [ss.entity(i) for i in m.get("bombers", [])]
            if m["stage"] == "outbound" and any(b is not None and b.ai.get("drop") for b in bombers) or \
                    (me.role in ("bomber", "heavybomber") and not me.bombs and m["stage"] == "outbound"):
                m["stage"] = "home"
                m["text"] = "Bombs away over the target. Now the long way home."
                hit = sum(1 for g2 in ss.ground if g2["dead"])
                g.msg(f"Bombs away! Below, the target erupts. ({hit} aiming point{'s' if hit != 1 else ''} destroyed)",
                      "good")
        elif k in ("attack", "dive"):
            hit = any(g2["dead"] for g2 in ss.ground) or any(s.sunk for s in ss.ships if s.side != me.side)
            if m["stage"] != "home" and (hit or not me.bombs):
                m["stage"] = "home"
                m["text"] = "Target destroyed. Get home." if hit else "You've done what you can. Get home."
        elif k == "torpedo":
            if (not me.torpedo) and m["stage"] != "home":
                m["stage"] = "home"
                m["text"] = "Torpedo gone. Get out of the flak and home."
        elif k == "kamikaze" and m["stage"] != "done":
            for s in ss.ships:
                if s.alive and s.side != me.side and me.alt < 80 and \
                        any(math.hypot(cx - me.x, cy - me.y) < 0.8 for cx, cy in s.cells()):
                    ss._ship_hit(s, 600, 200, "a kamikaze", fire=True)
                    m["stage"] = "done"
                    g.msg(f"You hold the dive until the {s.name}'s deck fills the windscreen.", "death")
                    g.command.merit += 20
                    g.player.body.dead = True
                    g.player.body.cause = f"a special attack on {s.name}"
                    ss.over = "dead"
                    return
        elif k == "recon":
            if d < 2.5 and m["stage"] == "outbound":
                m["stage"] = "home"
                m["text"] = "Photographs taken. Get them home."
                g.msg("You make your runs over the target, cameras clicking. Now get home.", "good")
        # landing (or the autopilot put it down)
        bx, by = m["base_pt"]
        landed = me.state == "landed" or (math.hypot(bx - me.x, by - me.y) < 2 and me.alt < 150 and me.kmh < 320)
        if k == "resupply" and me.state == "landed":
            m["stage"] = "home"
        if k == "resupply" and m["stage"] == "home" and landed:
            from .sustain import deliver
            base = g.strategic.at(*m["base"])
            cargo = me.ai.get("cargo", 0)
            if base is not None and base.control == me.side and cargo:
                for resource in ("ammo", "food", "medical"):
                    deliver(base, me.side, resource, cargo / 3)
                me.ai["cargo"] = 0
            done("Transport home. " + ("The stores reached our troops." if m.get("delivered") else
                                        "The sortie ended without a delivery."), 8 if m.get("delivered") else 0)
            ss.over = ("landed", m["base"])
            return
        if me.state == "landed" and m["stage"] == "home":
            done(f"{'The pilot puts' if g.__dict__.get('domain') == 'aboard' and ss.station != 'pilot' else 'You bring'} "
                 f"the {me.name} down onto the field. Mission complete.", 8)
            ss.over = ("landed", m["base"])
            return
        if m["stage"] == "home" and math.hypot(bx - me.x, by - me.y) < 2 and me.alt < 150 and me.kmh < 320:
            done(f"You bring the {me.name} down onto the field. Mission complete.", 8)
            ss.over = ("landed", m["base"])
    # the sea
    if (k in SEA_MISSIONS or k in EXTRA_SEA) and ship is not None:
        enemies = [ss.entity(-i) for i in m.get("enemies", [])]
        alive = [e for e in enemies if e is not None and e.alive]
        if k == "rtb":
            px, py = m["port_pt"]
            if m.get("stage") == "rtb" and math.hypot(px - ship.x, py - ship.y) < 3:
                m["stage"] = "arrived"                 # shipboard.py brings her to anchor
            return
        if k == "cover":
            if ss.t >= m.get("next_raid", 1e18) and ss.t < m["until"] - 600:
                n = air_raid(ss, g, ship)
                m["next_raid"] = ss.t + rng.randint(2700, 5400)
                if n and (ship.player or -ship.id in ss.contacts):
                    g.msg("Radar: 'Bogeys, many bogeys, closing from the " +
                          ("north" if rng.random() < 0.5 else "west") + "!'", "radio")
            if ss.t >= m["until"]:
                done("Relieved on station. The beachhead held, and their aircraft didn't get through to it.", 8)
            return
        if k == "rescue":
            rx, ry = m["rescue_pt"]
            if math.hypot(rx - ship.x, ry - ship.y) < 2.5:
                done(f"Scrambling nets over the side: you pull {m['survivors']} men out of the oil and the water.", 7)
            elif ss.t >= m["until"]:
                fail("By the time she gets there, there's nobody left alive in the water.")
            return
        if k == "asw" and enemies and not alive:
            done("An oil slick, wreckage, and then nothing. The submarine is gone.", 8)
        elif k == "asw" and ss.t - m.get("start", 0) > 6 * 3600:
            fail("The contact is lost. The hunt is called off.")
        if k in ("surface", "carrier", "sub") and enemies and not alive:
            done("The enemy force is gone - sunk or scattered. Well done.", 12)
        elif k in ("surface", "carrier", "sub", "bombard") and enemies and ss.t - m.get("start", 0) > 10 * 3600:
            # nobody fights for ever: after a day of it the other side breaks off
            sunk = len(enemies) - len(alive)
            if sunk:
                done(f"The enemy turns away, {sunk} ship{'s' if sunk != 1 else ''} the poorer. The force is "
                     f"ordered home.", 6 + 2 * sunk)
            else:
                fail("The enemy has slipped away. The force is ordered home.")
        elif k == "convoy":
            convoy = [ss.entity(-i) for i in m.get("convoy", [])]
            lost = sum(1 for c in convoy if c is None or not c.alive)
            if ss.t >= m["until"]:
                if lost <= len(convoy) // 3:
                    done(f"The convoy makes port. {lost} ship{'s' if lost != 1 else ''} lost.", 10)
                else:
                    fail(f"The convoy is scattered: {lost} ships lost.")
        elif k == "bombard" and m.get("shore") and m.get("shots", 0) >= 6:
            done("Ashore, the troops are going forward behind your shells.", 8)
        elif k == "bombard" and ss.t - m.get("start", 0) > 6 * 3600:
            if m.get("shots", 0) >= 2:
                done("The shoot is called off: the army has what it needs.", 5)
            else:
                fail("The bombardment is called off. The troops ashore went in without you.")
