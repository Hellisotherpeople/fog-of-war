"""Aboard: one man on a ship - or in a bomber - with the war at sea and in the air going on around him.

The ship is built at her real size, every deck of her (shipyard.py): the bridge or the island, the
main or flight deck, the hangar, the berthing and mess decks, the magazines, the fire and engine
rooms.  Ladders (< and >, or e) take you between them.  Her whole company is aboard, each man at
his station - by watch in cruising condition, at his battle station at general quarters - and the
decks you aren't on go on without you: fires burn, compartments flood, men are hit (shipboard.py
runs the routine, the watches and the jobs that come your way).

She is under way in the same world as every other ship and aircraft in this part of the war
(skysea.py).  Aircraft that come for her come for the deck you're standing on, if you're on an
open deck: the dive bombers, the torpedo planes low on the water, the fighters strafing, the
kamikaze.  Below decks you feel it instead - the whip of a torpedo hit, a bomb bursting two decks
up, the lights going out.  Shells and bombs burst on real plating and kill real men; torpedoes open
the hull and she floods compartment by compartment.  If she goes down, she goes down under you.

A bomber is the same, smaller and colder: nose, cockpit, top turret, radio room, waist and tail.

Scale: a deck tile is two metres, the same as a battlefield's; the sea and sky world is a hundred.
Directions aboard are the sailor's: ahead, astern, to port and to starboard.
"""
from __future__ import annotations

import math

import numpy as np

from . import tiles as T
from .ai import Order, Squad
from .constants import other_side
from .gamemap import GameMap
from .skysea import KNOT_TILES_S, SEC, Plane, Ship, angdiff, bearing

TILE_M = 2.0
K = 100.0 / TILE_M          # deck tiles to a sea tile
NAVY_ROLES = ("sailor", "petty_officer", "deck_officer", "ship_captain", "sub_commander", "admiral")


# ====================================================================== the decks
def decks(game):
    return game.aboard["decks"]


def deck(game, name=None):
    ab = game.aboard
    return ab["decks"][name or ab["deck"]]


def _store(game):
    """Put the deck you're leaving back as it is: its men, its guns, where everyone stands."""
    d = deck(game)
    d.map = game.map
    d.actors, d.vehicles, d.squads = game.actors, game.vehicles, game.squads
    d.soldier_at, d.vehicle_at = game.soldier_at, game.vehicle_at
    d.shells, d.explosives = game.shells, game.explosives


def _load(game, name):
    """Stand on another deck: its men and its guns are the ones around you now."""
    from .brain import SideBrain
    ab = game.aboard
    d = ab["decks"][name]
    ab["deck"] = name
    game.map = d.map
    game.actors, game.vehicles, game.squads = d.actors, d.vehicles, d.squads
    game.soldier_at, game.vehicle_at = d.soldier_at, d.vehicle_at
    game.shells, game.explosives = getattr(d, "shells", []), getattr(d, "explosives", [])
    game.pending_explosions, game.effects, game.sound_marks = [], [], []
    game._arr_turn = -1
    game._enemy_arr = {}
    if game.support is not None and not d.weather:
        game.support.aircraft = []
    game.brains = {s: SideBrain(game, s) for s in ("allies", "axis")}
    # men hit on this deck while you were elsewhere are lying where they fell
    for a in list(game.actors):
        if not a.alive and not a.ai.get("_dead_done"):
            a.ai["_dead_done"] = True
            try:
                game.kill(a, None)
            except Exception:
                if a in game.actors:
                    game.actors.remove(a)
    for b in game.brains.values():
        b.update(force=True)
    game.map.version += 1


def change_deck(game, name, x, y):
    """Up or down a ladder: you come out at the same place on the next deck."""
    from .spawn import place
    from . import shipboard as SB
    p = game.player
    ab = game.aboard
    arr = ab.get("arrivals")
    if arr:
        # the men still due on the deck you're leaving get there without you watching
        ship = ship_of(game)
        if ship is not None:
            SB.place_arrivals(game, ship, deck(game, ab["deck"]), arr, arrive=False)
        ab["arrivals"] = []
    _store(game)
    if p in game.actors:
        game.remove_actor(p)
    if p.squad is not None and p in p.squad.members and p.squad in game.squads and len(p.squad.members) == 1:
        game.squads.remove(p.squad)
    _load(game, name)
    place(game, p, x, y, 3)
    if p.squad is not None and p.squad not in game.squads:
        game.squads.append(p.squad)
    game.map.explored[:, :] |= _known(game)
    game.player_fov()
    from . import shipboard as SB
    SB.organise(game)
    game.update_orders(force=True)


def _known(game):
    """You know your own ship: every deck's layout is explored from the start."""
    m = game.map
    return m.t != T.ID["void"]


def weather_deck(game):
    """The open deck the aircraft come at: main, flight or casing."""
    for name in game.aboard["order"]:
        if deck(game, name).weather:
            return deck(game, name)
    return None


def on_open_deck(game):
    d = deck(game)
    return d.weather or d.name in ("bridge", "island")


# ====================================================================== going aboard
def board_ship(game, ship, role_station=None):
    """Go aboard `ship` (a skysea Ship): every deck of her, her whole company at their stations."""
    from . import shipyard as SY
    from . import shipboard as SB
    from .spawn import place
    rng = game.rng
    p = game.player
    if game.map is not None and game.sector is not None and game.__dict__.get("domain", "land") == "land":
        game._save_map()
        game.sector.units = game.local_units()
    dks, order, fr = SY.build(ship, rng)
    game.explosives, game.shells, game.pending_explosions, game.waves = [], [], [], []
    game.effects, game.sound_marks, game.smoke_sources = [], [], []
    if game.support is not None:
        game.support.queue, game.support.aircraft = [], []
    game.attacker = None
    game.aboard = dict(kind="ship", ship=ship.id, decks=dks, order=order, frame=fr, deck=order[0],
                       condition="III", since=game.turn, flood_done={}, sinking=None, drift=0.0,
                       complement=int(ship.st.get("crew", 200)), section=rng.randint(1, 3), task=None,
                       reported={})
    game.domain = "aboard"
    for name in order:
        d = dks[name]
        d.actors, d.vehicles, d.squads, d.soldier_at, d.vehicle_at = [], [], [], {}, {}
        d.shells, d.explosives = [], []
    # the guns on the open decks
    for name in order:
        d = dks[name]
        game.map, game.actors, game.vehicles, game.squads = d.map, d.actors, d.vehicles, d.squads
        game.soldier_at, game.vehicle_at = d.soldier_at, d.vehicle_at
        SB.mount_guns(game, ship, d)
    # her company, at their stations for the condition she's in
    SB.assign_player(game, ship, role_station)
    for name in order:
        d = dks[name]
        game.map, game.actors, game.vehicles, game.squads = d.map, d.actors, d.vehicles, d.squads
        game.soldier_at, game.vehicle_at = d.soldier_at, d.vehicle_at
        SB.populate(game, ship, d, "III")
    # and you
    start = game.aboard["watch_station"] or game.aboard["battle_station"]
    dname, sx, sy = start[0], start[1], start[2]
    _load(game, dname)
    if p in game.actors:
        game.remove_actor(p)
    p.vehicle = None
    place(game, p, sx, sy, 3)
    psq = Squad(ship.side, ship.nation, "rifle", "you")
    psq.members = [p]
    psq.leader = p
    psq.no_count = True
    psq.order = Order("hold", src="player")
    p.squad = psq
    game.squads.append(psq)
    SB.organise(game)
    game.player_fov()
    game.map.explored[:, :] |= _known(game)
    from .shipyard import DECK_NAME
    n = game.aboard["complement"]
    game.msg(f"Aboard {ship.name}, {n:,} men, {ship.kn:.0f} knots, course {int(ship.hdg):03d}. You're on "
             f"{DECK_NAME.get(dname, dname)}. " + SB.station_words(game), "info")
    game.update_orders(force=True)
    return game.aboard


# ====================================================================== each second
def ship_of(game):
    ab = game.__dict__.get("aboard")
    ss = game.__dict__.get("skysea")
    if not ab or ss is None or ab.get("kind") != "ship":
        return None
    return next((s for s in ss.ships if s.id == ab["ship"]), None)


def tick(game):
    """One second aboard: the sea and sky world moves on; what it does to her happens here."""
    ab = game.__dict__.get("aboard")
    ss = game.__dict__.get("skysea")
    if ss is None or not ab:
        return
    if ab.get("kind") == "plane":
        return tick_plane(game)
    from . import shipboard as SB
    ship = ship_of(game)
    ss.hit_hook = lambda s, dmg, flood, what, fire, deck_: on_hit(game, s, dmg, flood, what, fire, deck_)
    ss.local_hook = lambda plane, tgt: take_attack(game, plane, tgt)
    ss.step(1, clock=False)
    if ship is not None and ship.alive:
        _sea_moves(game, ship)
        if game.turn % 5 == 0:
            _flooding(game, ship)
            _fires_elsewhere(game, ship)
        _aircraft_about(game, ship)
        _blasts_on_her(game, ship)
        burning = sum(int((deck(game, n).map.fire > 0).sum()) for n in ab["order"])
        ship.fires = 0 if burning == 0 else min(6, 1 + burning // 15)
    elif ship is not None and not ship.alive:
        _going_down(game)
    _overboard(game, ship)
    _damage_control(game)
    SB.tick(game, ship)
    if game.turn % 5 == 0:
        _contacts_line(game, ship)


def _sea_moves(game, ship):
    """The sea streams past her: the water's ripple slides aft with her speed."""
    m = game.map
    ab = game.aboard
    ab["drift"] = ab.get("drift", 0.0) + ship.kn * 0.514 / TILE_M
    k = int(ab["drift"])
    if k <= 0:
        return
    ab["drift"] -= k
    water = (m.t == T.ID["deep"]) | (m.t == T.ID["sea_below"])
    if water.any():
        m.var[water] = np.roll(m.var, k % m.w, axis=0)[water]


def _flooding(game, ship):
    """She takes water: the lowest decks fill first, compartment by compartment."""
    ab = game.aboard
    want = ship.flood / 100.0
    done_all = ab.setdefault("flood_done", {})
    order = [n for n in ab["order"] if not deck(game, n).weather and n not in ("bridge", "island")]
    rng = game.rng
    for i, name in enumerate(reversed(order)):
        # the bottom deck takes the first 60% of her flooding, the next deck the rest
        share = min(1.0, max(0.0, (want - i * 0.5) / 0.6))
        d = deck(game, name)
        done = done_all.get(name, 0.0)
        if share <= done + 0.03:
            continue
        m = d.map
        floor = np.argwhere((m.t == T.ID["deck_inside"]) | (m.t == T.ID["bunk"]) | (m.t == T.ID["ladder"]))
        if not len(floor):
            continue
        n = int(len(floor) * (share - done))
        idx = rng.sample(range(len(floor)), min(len(floor), max(0, n)))
        for k in idx:
            x, y = int(floor[k][0]), int(floor[k][1])
            m.t[x, y] = T.ID["shallow"] if share < 0.7 else T.ID["deep"]
        done_all[name] = share
        m.refresh()
        if name == ab["deck"] and n > 0:
            game.msg("Water's coming in - you can hear it roaring through the compartments.", "warn")


def _fires_elsewhere(game, ship):
    """Fires on the decks you aren't on: the repair parties fight them, or they spread."""
    ab = game.aboard
    for name in ab["order"]:
        if name == ab["deck"]:
            continue
        d = deck(game, name)
        f = d.map.fire
        if not (f > 0).any():
            continue
        dc = sum(1 for a in getattr(d, "actors", []) if a.alive and a.ai.get("dc") and not a.downed)
        f[f > 0] = np.maximum(0, f[f > 0].astype(np.int32) - (2 + 4 * min(6, dc))).astype(f.dtype)
        if dc == 0 and game.rng.random() < 0.2:
            ys, xs = np.nonzero(f.T > 0)
            if len(xs):
                k = game.rng.randrange(len(xs))
                x, y = int(xs[k]) + game.rng.randint(-1, 1), int(ys[k]) + game.rng.randint(-1, 1)
                if d.map.in_bounds(x, y) and T.WALK[d.map.t[x, y]]:
                    f[x, y] = max(int(f[x, y]), 40)


def _going_down(game):
    """The ship is sinking: every deck goes under, the lowest first, a little more each second."""
    ab = game.aboard
    if ab.get("sinking") is None:
        ab["sinking"] = game.turn
        ab["abandon"] = True
        game.msg("'ABANDON SHIP! ABANDON SHIP!' - up the ladders, over the side, and swim clear before she "
                 "takes you down!", "death")
        for a in game.actors:
            if not a.is_player and a.alive and a.state == "ok":
                a.ai["abandon"] = True
    t = game.turn - ab["sinking"]
    rng = game.rng
    for i, name in enumerate(reversed(ab["order"])):
        d = deck(game, name)
        m = d.map
        if t < i * 25:
            continue
        cells = list(d.cells)
        frac = min(1.0, (t - i * 25) / 80.0)
        for (x, y) in rng.sample(cells, min(len(cells), int(len(cells) * frac * 0.2) + 1)):
            if T.WATER[m.t[x, y]] < 2 and m.t[x, y] not in (T.ID["hull"],):
                m.t[x, y] = T.ID["deep"]
        m.refresh()


def _overboard(game, ship):
    """A man in the water is left astern - the ship doesn't stop for him."""
    ab = game.aboard
    d = deck(game)
    if not d.weather and ab.get("sinking") is None:
        return
    m = game.map
    kn = ship.kn if ship is not None and ship.alive else 0.0
    step = kn * 0.514 / TILE_M
    acc = ab.setdefault("man_drift", {})
    p = game.player
    for a in list(game.actors):
        if not a.alive or a.vehicle is not None:
            continue
        if m.water[a.x, a.y] < 2 or ((a.x, a.y) in d.cells and ab.get("sinking") is None):
            continue
        acc[a.id] = acc.get(a.id, 0.0) + step
        n = int(acc[a.id])
        if n <= 0:
            continue
        acc[a.id] -= n
        nx = a.x - n
        if nx < 1:
            if a.is_player:
                return _player_adrift(game, ship)
            game.remove_actor(a)
            continue
        if game.soldier_at.get((nx, a.y)) is None and m.water[nx, a.y] >= 2:
            if game.soldier_at.get((a.x, a.y)) is a:
                del game.soldier_at[(a.x, a.y)]
            a.x = nx
            game.soldier_at[(a.x, a.y)] = a
            game.note_move(a)
        if a.is_player and game.rng.random() < 0.02 and kn > 3:
            game.msg("The ship slides past - her side, her stern, her wake. Nobody throws you a line.", "warn")
    if ab.get("sinking") is not None and game.turn - ab["sinking"] > 150 and p.alive:
        if m.water[p.x, p.y] >= 2:
            return _player_adrift(game, ship)


def _player_adrift(game, ship):
    """You're in the sea, and she's gone (or going on without you)."""
    ss = game.skysea
    x, y = (ship.x, ship.y) if ship is not None else (ss.cx * SEC, ss.cy * SEC)
    ss.raft = (x, y)
    ss.over = "raft"
    game.aboard["gone"] = True
    game.msg("You're alone in the water. You find a floating hatch cover and cling to it.", "death")


def _damage_control(game):
    """The repair parties go for the fires on this deck."""
    m = game.map
    if game.turn % 3 != 0 or not (m.fire > 0).any():
        return
    fires = np.argwhere(m.fire > 0)
    for a in game.actors:
        if not a.ai.get("dc") or not a.active or a.downed:
            continue
        dd = np.abs(fires[:, 0] - a.x) + np.abs(fires[:, 1] - a.y)
        i = int(np.argmin(dd))
        fx, fy = int(fires[i][0]), int(fires[i][1])
        if max(abs(fx - a.x), abs(fy - a.y)) <= 1:
            m.fire[fx, fy] = max(0, int(m.fire[fx, fy]) - 30)      # hoses and foam
            a.ai["fighting_fire"] = game.turn
        elif dd[i] < 40 and a.squad is not None:
            a.squad.positions[a.id] = (fx + (1 if fx < a.x else -1), fy)


# ====================================================================== what the war does to her
HIT_DECKS = {"torpedo": ("third", "hull", "holds", "second", "below", "hangar"),
             "bomb": ("flight", "main", "casing", "hangar", "second"),
             "kamikaze": ("flight", "main", "casing"),
             "shell": ("main", "bridge", "island", "flight", "second", "casing", "hangar")}


def on_hit(game, s, dmg, flood, what, fire, deck_=False):
    """The sea-and-sky world says she's been hit: where, and what it does to the men there."""
    ab = game.__dict__.get("aboard")
    if not ab or ab.get("kind") != "ship" or ab.get("ship") != s.id:
        return
    rng = game.rng
    kind = "torpedo" if "torpedo" in what else "kamikaze" if "kamikaze" in what else \
        "bomb" if ("bomb" in what or "crashing" in what) else "shell"
    names = [n for n in HIT_DECKS[kind] if n in ab["decks"]] or ab["order"]
    # a heavy bomb goes down through a deck or two before it bursts
    name = names[0] if rng.random() < 0.55 else rng.choice(names)
    d = deck(game, name)
    cells = [c for c in d.cells if T.WALK[d.map.t[c]] or d.map.t[c] in (T.ID["plane_parked"], T.ID["bunk"])]
    if not cells:
        cells = list(d.cells)
    if kind == "torpedo":
        side = rng.choice((-1, 1))
        fr = ab["frame"]
        edge = [c for c in cells if (c[1] - fr.cy) * side >= fr.hullB / 2 - 1.5]
        x, y = rng.choice(edge or cells)
        power, radius, frags, f = 460, 4, 50, 20
    elif kind == "kamikaze":
        x, y = rng.choice(cells)
        power, radius, frags, f = 520, 5, 60, 70
    else:
        x, y = rng.choice(cells)
        power = int(min(420, 60 + dmg * 0.6))
        radius, frags, f = 2 + (1 if dmg > 150 else 0), int(power / 8), 30 if fire else 0
    here = name == ab["deck"]
    if here:
        game.schedule_shell(x, y, 1, power, radius, frags, 26, None, what, whistle=False, fire=f)
    else:
        _hit_elsewhere(game, d, x, y, power, radius, f)
        from .shipyard import DECK_NAME
        feel = {"torpedo": "The whole ship whips and shudders under you - a torpedo hit, somewhere below.",
                "bomb": f"A heavy blast from {DECK_NAME.get(name, name)} - dust sifts down, the lights flicker.",
                "kamikaze": "A roar and a crash overhead, and the smell of burning petrol comes down the ladders.",
                "shell": f"A shell bursts on {DECK_NAME.get(name, name)}; the deck jumps under your feet."}[kind]
        game.msg(feel, "death")
        for a in game.actors:
            if a.alive and a.vehicle is None and rng.random() < (0.3 if kind == "torpedo" else 0.08):
                a.stance = 2
                a.suppression = min(100.0, a.suppression + 30)
    game.aboard["last_hit"] = (game.turn, name, x, y, kind)
    game.map.version += 1


def _hit_elsewhere(game, d, x, y, power, radius, fire):
    """A blast on a deck you aren't standing on: plating torn, men hit, fire started - all waiting for you."""
    rng = game.rng
    m = d.map
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            xx, yy = x + dx, y + dy
            if not m.in_bounds(xx, yy) or dx * dx + dy * dy > radius * radius:
                continue
            m.hp[xx, yy] -= int(power * (1 - math.hypot(dx, dy) / (radius + 1)))
            if m.hp[xx, yy] <= 0 and T.INTO[m.t[xx, yy]] != m.t[xx, yy]:
                m.t[xx, yy] = T.INTO[m.t[xx, yy]]
            if fire and rng.random() < 0.5:
                m.fire[xx, yy] = max(int(m.fire[xx, yy]), fire)
    m.refresh()
    for a in getattr(d, "actors", []):
        if not a.alive:
            continue
        dist = math.hypot(a.x - x, a.y - y)
        if dist > radius + 2:
            continue
        amt = power * max(0.05, 1 - dist / (radius + 3)) * rng.uniform(0.15, 0.4)
        a.body.damage(rng, rng.choice(("torso", "head", "l_arm", "r_arm", "l_leg", "r_leg")), amt, "fragment")


def take_attack(game, plane, tgt):
    """An enemy aircraft starting its run on your ship: if you're on an open deck, it flies it over you."""
    ab = game.__dict__.get("aboard")
    if not ab or ab.get("kind") != "ship" or not isinstance(tgt, Ship) or tgt.id != ab.get("ship"):
        return False
    if not on_open_deck(game):
        return False
    from .data.vehicles import AIRCRAFT
    from .support import Aircraft
    sup = game.support
    if sup is None:
        return False
    fr = ab["frame"]
    m = game.map
    rng = game.rng
    role = plane.ai.get("role", plane.role)
    mode = {"dive": "dive", "torpedo": "torpedo", "kamikaze": "kamikaze", "attack": "strafe",
            "fighter": "strafe", "bomber": "bomb"}.get(role, "strafe")
    ship = ship_of(game)
    rel = math.radians(bearing(ship.x, ship.y, plane.x, plane.y) - ship.hdg)
    cx, cy = fr.x0 + fr.L // 2, int(fr.cy)
    sx = cx + math.cos(rel) * (m.w * 0.7)
    sy = cy + math.sin(rel) * (m.h * 0.9)
    wd = weather_deck(game)
    tx, ty = rng.choice(sorted(wd.cells)) if wd is not None else (cx, cy)
    at = AIRCRAFT[plane.at_id]
    ac = Aircraft(at, plane.side, plane.nation, sx, sy, tx, ty, "dive" if mode == "kamikaze" else
                  ("bomb" if mode == "torpedo" else mode))
    ac.skysea_id = plane.id
    ac.kind = mode
    if mode == "torpedo":
        ac.bombs = []
        ac.torpedo = True
    if mode == "kamikaze":
        ac.bombs = [[500, 5, 1]]
    sup.aircraft.append(ac)
    plane.ai["local"] = True
    game.audio("aircraft", cx, cy, 80)
    what = {"dive": "A dive bomber peels off and comes screaming down at us",
            "torpedo": "Torpedo plane, low on the water, coming in",
            "kamikaze": "He's not pulling out - he's coming straight in",
            "strafe": "Fighter coming in low, guns winking",
            "bomb": "Bombers overhead"}.get(mode, "Aircraft attacking")
    game.msg(f"{what} - {_relative(math.degrees(rel))}!", "death")
    return True


def _relative(deg):
    d = deg % 360
    if d < 22 or d >= 338:
        return "dead ahead"
    if d < 67:
        return "off the starboard bow"
    if d < 113:
        return "on the starboard beam"
    if d < 158:
        return "off the starboard quarter"
    if d < 202:
        return "dead astern"
    if d < 247:
        return "off the port quarter"
    if d < 292:
        return "on the port beam"
    return "off the port bow"


def _aircraft_about(game, ship):
    """Local aircraft over the deck: when their run is over - shot down, crashed into her, or gone - they
    go back into the wider war (and it hears what happened)."""
    ss = game.skysea
    sup = game.support
    if sup is None:
        return
    tracked = game.__dict__.setdefault("_aboard_ac", [])
    live = {id(ac) for ac in sup.aircraft}
    for ac in sup.aircraft:
        if getattr(ac, "skysea_id", None) is not None and ac not in tracked:
            tracked.append(ac)
        if getattr(ac, "kind", None) == "torpedo" and not getattr(ac, "dropped", False) and \
                math.hypot(ac.tx - ac.x, ac.ty - ac.y) < 30:
            ac.dropped = True
            _torpedo_run(game, ship, ac)
        if getattr(ac, "kind", None) == "kamikaze" and ac.attacked and not ac.dead:
            # he doesn't pull out
            ac.dead = True
            ac.done = True
            game.schedule_shell(int(ac.tx), int(ac.ty), 1, 520, 5, 60, 28, None, f"a {ac.at.name} crashing into the deck",
                                whistle=False, fire=80)
            game.msg(f"The {ac.at.name} goes straight into the ship - a sheet of flame across the deck!", "death")
    for ac in list(tracked):
        if id(ac) in live and not ac.dead and not ac.done:
            continue
        tracked.remove(ac)
        pl = next((q for q in ss.planes if q.id == getattr(ac, "skysea_id", None)), None)
        if pl is None or not pl.ai.get("local"):
            continue
        pl.ai.pop("local", None)
        if getattr(ac, "kind", None) == "kamikaze" and ac.attacked:
            ss._down(pl, "dived into the ship")
        elif ac.dead:
            ss._down(pl, "shot down by the ship's AA")
        elif not getattr(ac, "attacked", False) and not getattr(ac, "dropped", False):
            continue       # interrupted (you went below): the war at large finishes his attack, bombs and all
        else:
            pl.bombs, pl.torpedo = [], False
            pl.ai["role"] = "home"
            pl.ai["wp"] = pl.ai.get("home_pt")


def _blasts_on_her(game, ship):
    """What lands on her does her harm: bombs, rockets and crashing aircraft that burst on the deck plating
    (and near misses that open her seams)."""
    ab = game.aboard
    wd = deck(game)
    hull = wd.cells
    ss = game.skysea
    for sh in game.shells:
        if sh.get("_aboard") or sh["t"] > game.turn:
            continue
        sh["_aboard"] = True
        src = sh.get("source") or ""
        if not any(k in src for k in ("bomb", "rocket", "crashing")):
            continue
        x, y = sh["x"], sh["y"]
        on = (x, y) in hull
        near = on or any((x + dx, y + dy) in hull for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2))
        if not near:
            continue
        hook, ss.hit_hook = ss.hit_hook, None                   # the blast itself happens here, on the map
        try:
            # a 250 kg bomb on the flight deck costs a fleet carrier about a tenth of herself; a crashing
            # aircraft less; a near miss opens seams and lets the sea in
            k = 0.2 if "crashing" in src and "deck" not in src else 0.45
            if on:
                ss._ship_hit(ship, sh["power"] * k, sh["power"] * 0.08, src, fire=sh.get("fire", 0) > 0 or
                             game.rng.random() < 0.3, deck=True)
            else:
                ss._ship_hit(ship, sh["power"] * 0.04, sh["power"] * 0.12, "a near miss")
        finally:
            ss.hit_hook = hook


def _torpedo_run(game, ship, ac):
    """The torpedo drops, and runs at her."""
    rng = game.rng
    if rng.random() < 0.55:
        game.msg("The torpedo's in the water - the track's running straight at us!", "death")
        ship.order_kn = ship.st["speed"]
        game.skysea._ship_hit(ship, 450, 60, "a torpedo") if rng.random() < 0.5 else \
            game.msg("The track passes astern - it missed!", "good")
    else:
        game.msg("The torpedo porpoises and runs wild. Missed!", "good")


def _contacts_line(game, ship):
    """What the lookouts report: other ships and aircraft, by bearing from the bow."""
    ss = game.skysea
    if ship is None or not ship.alive:
        return
    near = []
    for e in ss.planes:
        if e.alive and e.side != ship.side and math.hypot(e.x - ship.x, e.y - ship.y) < 60 and e.id in ss.contacts:
            near.append(("aircraft", e, math.hypot(e.x - ship.x, e.y - ship.y)))
    for e in ss.ships:
        if e.alive and e is not ship and -e.id in ss.contacts and e.side != ship.side:
            near.append(("ship", e, math.hypot(e.x - ship.x, e.y - ship.y)))
    ab = game.aboard
    seen = ab.setdefault("reported", {})
    for kind, e, d in near:
        key = (kind, e.id)
        if game.turn - seen.get(key, -10 ** 6) < 600:
            continue
        seen[key] = game.turn
        rel = bearing(ship.x, ship.y, e.x, e.y) - ship.hdg
        where = _relative(rel)
        km = d * 0.1
        name = e.name if kind == "ship" else f"{e.name}{'s' if False else ''}"
        game.msg(f"Lookout: '{'Aircraft' if kind == 'aircraft' else 'Ship'} {where}, {km:.0f} kilometres - "
                 f"{name}!'", "radio")


def contacts(game):
    """(label, relative bearing degrees, distance km, kind, hostile) for the edge markers."""
    ss = game.skysea
    ship = ship_of(game)
    if ss is None or ship is None:
        return []
    out = []
    for e in ss.planes:
        if e.alive and e.id in ss.contacts and not e.ai.get("local"):
            d = math.hypot(e.x - ship.x, e.y - ship.y)
            if d < 80:
                out.append((e.name, bearing(ship.x, ship.y, e.x, e.y) - ship.hdg, d / 10.0, "air", e.side != ship.side))
    for e in ss.ships:
        if e.alive and e is not ship and (-e.id in ss.contacts or e.side == ship.side):
            d = math.hypot(e.x - ship.x, e.y - ship.y)
            if d < 250:
                out.append((e.name, bearing(ship.x, ship.y, e.x, e.y) - ship.hdg, d / 10.0, "sea", e.side != ship.side))
    return out


def status_line(game):
    ship = ship_of(game)
    if ship is None:
        return None
    hull = max(0, int(100 * ship.hp / ship.st["hp"]))
    anchored = (game.aboard or {}).get("condition") == "port" or \
        ((game.aboard or {}).get("base_condition") == "port")
    bits = [f"{ship.name}: at anchor" if anchored else f"{ship.name}: {ship.kn:.0f} kn, course {int(ship.hdg):03d}",
            f"hull {hull}%", f"fuel {int(getattr(ship, 'fuel', 100))}%"]
    if ship.flood > 5:
        bits.append(f"flooding {int(ship.flood)}%")
    if ship.fires:
        bits.append(f"{ship.fires} fire{'s' if ship.fires > 1 else ''}")
    return ", ".join(bits)


# ====================================================================== the player's doings aboard
def use_here(ps):
    """e aboard: the ladder, the helm, the plot, the periscope - or the rail (over the side)."""
    g = ps.game
    p = g.player
    ab = g.aboard
    if ab.get("kind") == "plane":
        return use_in_plane(ps)
    m = g.map
    key = T.DEFS[int(m.t[p.x, p.y])].key
    d = deck(g)
    if (p.x, p.y) in d.ladders:
        ways = d.ladders[(p.x, p.y)]
        if len(ways) == 1:
            return climb(ps, next(iter(ways)))
        from .render import Popup
        from .shipyard import DECK_NAME
        opts = [(f"Up to {DECK_NAME.get(ways['up'], ways['up'])}", "up", None, True),
                (f"Down to {DECK_NAME.get(ways['down'], ways['down'])}", "down", None, True)]
        ps.open_popup(Popup("Ladder", opts, ps._screen_anchor()), lambda w: climb(ps, w) if w else None)
        return True
    from . import shipboard as SB
    r = SB.use(ps)
    if r is not None:
        return r
    near = {T.DEFS[int(m.t[p.x + dx, p.y + dy])].key for dx in (-1, 0, 1) for dy in (-1, 0, 1)
            if m.in_bounds(p.x + dx, p.y + dy)}
    if key in ("helm", "chart_table", "periscope") or near & {"helm", "chart_table", "periscope"}:
        return take_the_conn(ps)
    if ab.get("condition") == "port" and (key == "railing" or "railing" in near):
        # the gangway: the liberty boat is alongside
        from . import naval as NV
        ok, why = NV.can_go_ashore(g)
        if not ok:
            g.msg(why, "info")
            return True
        from .render import Popup
        port = (ab.get("port") or {}).get("name", "the base")
        ps.open_popup(Popup("The gangway", [(f"Go ashore on liberty at {port} (back by 0500)", "go", (140, 190, 255),
                                             True)], ps._screen_anchor()),
                      lambda v: NV.go_ashore(ps) if v == "go" else None)
        return True
    if key == "railing":
        g.msg("Over the side? Walk on - into the sea. (Only if she's going down: nobody will stop for you.)",
              "warn")
        return True
    return None


def climb(ps, way):
    """< or >: up or down the ladder you're standing on."""
    g = ps.game
    p = g.player
    d = deck(g)
    ways = d.ladders.get((p.x, p.y))
    if not ways or way not in ways:
        g.msg("There's no ladder " + ("up" if way == "up" else "down") + " here.", "info")
        return None
    if p.carrying is not None:
        g.msg("Not with a man over your shoulder - not up a ladder that steep.", "info")
        return None
    target = ways[way]
    change_deck(g, target, p.x, p.y)
    from .shipyard import DECK_NAME
    g.msg(f"You go {'up' if way == 'up' else 'down'} the ladder to {DECK_NAME.get(target, target)}.", "info")
    ps.recenter()
    return ps.act(400 if way == "up" else 300)


def take_the_conn(ps):
    """At the helm or the plot: command the ship on the chart (Esc to step back onto the deck)."""
    g = ps.game
    p = g.player
    ss = g.skysea
    if p.role not in ("ship_captain", "sub_commander", "admiral", "deck_officer"):
        ss.station = "plot"                      # watching, not commanding: the captain still has her
        g.msg("You look over the helmsman's shoulder at the plot. (Only officers take the conn - but you can "
              "watch.)", "info")
    else:
        ss.station = "bridge"
    from .skyseaui import SkySeaState
    st = SkySeaState(ps.app, g, ps)
    st.aboard = True
    ps._skysea_pushed = True
    ps.app.push(st)


def advance(ps, seconds):
    """Time passing at the chart table: the ship's life goes on around you, a second at a time."""
    for _ in range(int(seconds)):
        ps.act(100)
        g = ps.game
        if g.game_over or g.skysea is None or g.skysea.over:
            break


def ended(game):
    ss = game.__dict__.get("skysea")
    return ss is None or bool(ss.over)


# ====================================================================== the gun you're on
def aa_targets(game, v):
    """Aircraft within reach of this mount: (aircraft, distance in tiles)."""
    sup = game.support
    if sup is None:
        return []
    rng_t = 140 if v.vt.main in ("40mm_bofors",) else 90
    out = []
    for ac in sup.aircraft:
        if ac.dead or ac.done or ac.side == v.side:
            continue
        d = math.hypot(ac.x - v.x, ac.y - v.y)
        if d <= rng_t:
            out.append((ac, d))
    out.sort(key=lambda e: e[1])
    return out


def fire_aa(game, p, v, ac):
    """A burst from your mount at a diving aircraft: lead him, and hope."""
    rng = game.rng
    d = math.hypot(ac.x - v.x, ac.y - v.y)
    heavy = v.vt.main in ("40mm_bofors",)
    skill = getattr(p, "skill", 5)
    diving_at_you = math.hypot(ac.tx - v.x, ac.ty - v.y) < 12
    chance = (0.06 + 0.012 * skill) * (1.4 if diving_at_you else 1.0) * max(0.15, 1 - d / (150 if heavy else 95))
    if v.ai.get("captured"):
        chance *= 0.6
    game.emit_sound(v.x, v.y, 88 if heavy else 80, "cannon", "your mount hammering", p.side, v)
    game.effect_tracer(v.x, v.y, int(ac.x), int(ac.y), mg=True)
    v.he = max(0, getattr(v, "he", 0) - (4 if heavy else 10))
    if rng.random() < chance:
        ac.hp -= rng.uniform(25, 70) * (1.5 if heavy else 1.0)
        if ac.hp <= 0 and not ac.dead:
            ac.dead = True
            game.msg(f"Your burst walks into the {ac.at.name} - it flames, rolls over and goes into the sea!", "good")
            game.command.merit += 3
            p.stats["kills"] = p.stats.get("kills", 0) + 1
            cx = int(ac.x + ac.dx * rng.randint(3, 12))
            cy = int(ac.y + ac.dy * rng.randint(3, 12))
            if game.map.in_bounds(cx, cy):
                game.schedule_shell(cx, cy, 2, 200, 3, 20, 20, None, f"a crashing {ac.at.name}", whistle=False,
                                    fire=3, side=None)
        else:
            game.msg(f"Hits - pieces fly off the {ac.at.name}!", "good")
    else:
        game.msg("Tracers streaming past him - you're behind him. Lead him!", "info")
    return 100


# ====================================================================== aboard an aircraft
PLANE = {
    "heavybomber": dict(L=34, stations=[("nose gunner", 0.98, 0), ("bombardier", 0.95, 0), ("navigator", 0.9, -1),
                                         ("pilot", 0.84, -1), ("copilot", 0.84, 1), ("top turret", 0.78, 0),
                                         ("radio", 0.6, 0), ("ball turret", 0.44, 0), ("left waist", 0.34, -1),
                                         ("right waist", 0.34, 1), ("tail gunner", 0.02, 0)],
                        bay=(0.64, 0.74), hatches=[0.3, 0.88], wing=(0.62, 0.78), engines=4, span=28),
    "bomber": dict(L=24, stations=[("nose gunner", 0.97, 0), ("bombardier", 0.93, 0), ("pilot", 0.82, -1),
                                   ("copilot", 0.82, 1), ("top gunner", 0.6, 0), ("radio", 0.5, 0),
                                   ("tail gunner", 0.03, 0)],
                   bay=(0.6, 0.72), hatches=[0.36], wing=(0.58, 0.76), engines=2, span=20),
    "torpedo": dict(L=12, stations=[("pilot", 0.72, 0), ("radio", 0.5, 0), ("rear gunner", 0.28, 0)],
                    hatches=[0.5], wing=(0.55, 0.75), engines=1, span=14),
    "divebomber": dict(L=10, stations=[("pilot", 0.7, 0), ("rear gunner", 0.35, 0)], hatches=[0.5],
                       wing=(0.5, 0.72), engines=1, span=12),
}
AIRCREW_ROLE = {"pilot": "bomber_pilot", "copilot": "bomber_pilot", "bombardier": "bombardier", "navigator": "bombardier",
                "radio": "air_gunner"}


def multi_crew(plane):
    return plane.role in PLANE


def build_plane(plane, rng):
    pl = PLANE.get(plane.role, PLANE["bomber"])
    L = pl["L"]
    span = pl["span"]
    W, H = L + 30, span + 10
    m = GameMap(W, H, rng.randint(1, 2 ** 30))
    m.biome, m.climate, m.name = "sky", "summer", plane.name
    m.t[:, :] = T.ID["sky"]
    x0 = 15
    cy = H // 2
    # the wing and engines, the tail plane
    wa, wb = x0 + int(pl["wing"][0] * L), x0 + int(pl["wing"][1] * L)
    for x in range(wa, wb + 1):
        for y in range(cy - span // 2, cy + span // 2 + 1):
            m.t[x, y] = T.ID["wing"]
    for k in range(pl["engines"]):
        side = -1 if k % 2 == 0 else 1
        off = 3 + 4 * (k // 2) if pl["engines"] > 1 else 0
        if pl["engines"] == 1:
            m.t[x0 + L, cy] = T.ID["engine_nacelle"]
            continue
        ex, ey = wb, cy + side * off
        m.t[ex, ey] = T.ID["engine_nacelle"]
        m.t[ex + 1, ey] = T.ID["engine_nacelle"]
    for y in range(cy - span // 5, cy + span // 5 + 1):
        m.t[x0, y] = T.ID["wing"]
        m.t[x0 + 1, y] = T.ID["wing"]
    # the fuselage: a skin two tiles either side of the walkway
    cells = []
    for i in range(L):
        x = x0 + i
        m.t[x, cy - 1] = T.ID["fuselage"]
        m.t[x, cy + 1] = T.ID["fuselage"]
        m.t[x, cy] = T.ID["plane_floor"]
        cells.append((x, cy))
    m.t[x0 - 1, cy] = T.ID["fuselage"]
    m.t[x0 + L, cy] = T.ID["fuselage"] if pl["engines"] > 1 else m.t[x0 + L, cy]
    meta = dict(kind="plane", x0=x0, L=L, cy=cy, stations={}, links={}, hull=cells, mounts=[], rooms={},
                below=(0, 0, 0, 0), H1=H)
    for a, b in [pl.get("bay")] if pl.get("bay") else []:
        for x in range(x0 + int(a * L), x0 + int(b * L)):
            m.t[x, cy] = T.ID["catwalk"]
    for name, fr, side in pl["stations"]:
        x = x0 + int(fr * (L - 1))
        y = cy + side
        m.t[x, y] = T.ID["station"]
        meta["stations"][name] = (x, y)
    for fr in pl["hatches"]:
        x = x0 + int(fr * (L - 1))
        m.t[x, cy] = T.ID["hatch_exit"]
        meta["stations"].setdefault("hatch", (x, cy))
        meta["rooms"].setdefault("hatches", []).append((x, cy))
    m.init_hp()
    m.refresh()
    return m, meta


def board_plane(game, plane):
    """Aboard a bomber: the crew at their stations, the sky outside, the war at 3,000 metres."""
    from .spawn import make_soldier, place
    rng = game.rng
    p = game.player
    ss = game.skysea
    if game.map is not None and game.sector is not None and game.__dict__.get("domain", "land") == "land":
        game._save_map()
        game.sector.units = game.local_units()
    m, meta = build_plane(plane, rng)
    game.map = m
    game.actors, game.vehicles, game.squads = [], [], []
    game.soldier_at, game.vehicle_at = {}, {}
    game.explosives, game.shells, game.pending_explosions, game.waves = [], [], [], []
    game.effects, game.sound_marks, game.smoke_sources = [], [], []
    if game.support is not None:
        game.support.queue, game.support.aircraft = [], []
    game.attacker = None
    from .brain import SideBrain
    game.brains = {s: SideBrain(game, s) for s in ("allies", "axis")}
    game.aboard = dict(kind="plane", plane=plane.id, meta=meta, since=game.turn, local={})
    game.domain = "aboard"
    mine = ss.station
    sq = Squad(plane.side, plane.nation, "rifle", f"{plane.name} crew")
    sq.order = Order("hold", issued=game.turn)
    sq.arrived = True
    game.squads.append(sq)
    for name, (x, y) in meta["stations"].items():
        if name == "hatch" or name == mine:
            continue
        role = AIRCREW_ROLE.get(name, "air_gunner")
        a = make_soldier(game, plane.nation, role)
        a.service = "air"
        a.ai["station"] = name
        a.squad = sq
        sq.members.append(a)
        place(game, a, x, y, 1)
    sq.leader = sq.members[0] if sq.members else None
    if p in game.actors:
        game.remove_actor(p)
    p.vehicle = None
    p.ai["station"] = mine
    spot = meta["stations"].get(mine) or meta["hull"][len(meta["hull"]) // 2]
    place(game, p, spot[0], spot[1], 2)
    p.squad = sq
    sq.members.append(p)
    ss.station = "cabin"                  # the pilot's at the controls; you're a man in the fuselage
    if mine == "pilot":
        game.aboard["push_station"] = "pilot"      # ...unless you're the pilot: you're flying her
    for b in game.brains.values():
        b.update(force=True)
    game.player_fov()
    m.explored[:, :] = True
    game.msg(f"In the {plane.name} at {int(plane.alt)} metres, {int(plane.kmh)} km/h. "
             f"Your station: {mine}. (e at a station to take it; e at the hatch to bail out)", "info")
    game.update_orders(force=True)


def plane_of(game):
    ab = game.__dict__.get("aboard")
    ss = game.__dict__.get("skysea")
    if not ab or ab.get("kind") != "plane" or ss is None:
        return None
    return next((q for q in ss.planes if q.id == ab["plane"]), None)


def tick_plane(game):
    ss = game.skysea
    pl = plane_of(game)
    ss.hit_hook = None
    ss.plane_hook = lambda e, dmg, part: on_plane_hit(game, e, dmg, part)
    ss.step(1, clock=False)
    m = game.map
    if pl is None:
        return
    # the sky streams past (and cloud)
    ab = game.aboard
    ab["drift"] = ab.get("drift", 0.0) + min(3.0, pl.kmh / 120.0)
    k = int(ab["drift"])
    if k:
        ab["drift"] -= k
        sky = (m.t == T.ID["sky"]) | (m.t == T.ID["cloud"])
        t = np.roll(m.t, k, axis=0)
        m.t[sky] = np.where(np.roll(sky, k, axis=0)[sky], t[sky], T.ID["sky"])
        if game.rng.random() < 0.08:
            y = game.rng.randrange(0, m.h)
            for dy in range(game.rng.randint(1, 3)):
                if 0 <= y + dy < m.h and m.t[0, y + dy] == T.ID["sky"]:
                    m.t[0, y + dy] = T.ID["cloud"]
        m.refresh()
    # flak: black bursts beside you, the airframe ringing with fragments
    in_flak = [f for f in ss.flak if f["side"] != pl.side and math.hypot(f["x"] - pl.x, f["y"] - pl.y) < f["r"]]
    rng = game.rng
    if in_flak and rng.random() < 0.25:
        x = rng.randrange(0, m.w)
        y = rng.choice((rng.randrange(0, max(1, meta_cy(game) - 2)), rng.randrange(meta_cy(game) + 2, m.h)))
        game.effect_explosion(x, y, 1)
        game.emit_sound(x, y, 95, "explosion", "flak bursting", None, None, power=80)
        if rng.random() < 0.3:
            hx, hy = rng.choice(ab["meta"]["hull"])
            for yy in (hy - 1, hy + 1):
                if m.t[hx, yy] == T.ID["fuselage"]:
                    m.t[hx, yy] = T.ID["fuselage_holed"]
                    break
            from .combat import hit_actor
            for a in list(game.actors):
                if a.alive and max(abs(a.x - hx), abs(a.y - hy)) <= 1 and rng.random() < 0.5:
                    hit_actor(game, a, rng.uniform(8, 35), "fragment", None, "flak")
            m.refresh()
    _crew_sync(game, pl)
    if pl.state == "down" and not ab.get("down_msg"):
        ab["down_msg"] = True
        game.msg("She's going down - get to a hatch and get out! (e at the hatch)", "death")
    if getattr(pl, "_doomed", False) and not ab.get("doom_msg"):
        ab["doom_msg"] = True
        game.msg("'We're going down - bail out, bail out!' The pilot rings the bell.", "death")


def meta_cy(game):
    return game.aboard["meta"]["cy"]


def _crew_sync(game, pl):
    """The crew in the sky world and the men in the fuselage are the same men."""
    ab = game.aboard
    from .combat import hit_actor
    by = {a.ai.get("station"): a for a in game.actors if a.ai.get("station")}
    for c in pl.crew:
        a = by.get(c["station"])
        if a is None or a.is_player:
            continue
        if not c["alive"] and a.alive:
            hit_actor(game, a, 120, "gunshot", None, "cannon shells through the fuselage")
        elif c["alive"] and not a.alive:
            c["alive"] = False


def on_plane_hit(game, e, dmg, part):
    """Bullets and cannon shells through your aircraft: holes in the skin, and sometimes in the men."""
    pl = plane_of(game)
    if pl is None or e is not pl:
        return
    rng = game.rng
    m = game.map
    hull = game.aboard["meta"]["hull"]
    for _ in range(1 + int(dmg // 40)):
        hx, hy = rng.choice(hull)
        yy = hy + rng.choice((-1, 1))
        if m.t[hx, yy] == T.ID["fuselage"]:
            m.t[hx, yy] = T.ID["fuselage_holed"]
        game.effect_tracer(hx + rng.randint(-20, 20), hy + rng.choice((-10, 10)), hx, hy, mg=True)
        a = game.soldier_at.get((hx, hy))
        from .combat import hit_actor
        if a is not None and a.alive and rng.random() < 0.35:
            hit_actor(game, a, dmg * rng.uniform(0.2, 0.6), "gunshot", None, "fire through the fuselage")
    if pl.fire:
        wx = game.aboard["meta"]["x0"] + int(0.65 * game.aboard["meta"]["L"])
        m.fire[wx, game.aboard["meta"]["cy"]] = max(int(m.fire[wx, game.aboard["meta"]["cy"]]), 30)
    m.refresh()


def take_station(ps, here):
    g = ps.game
    ss = g.skysea
    ss.station = here
    from .skyseaui import SkySeaState
    st = SkySeaState(ps.app, g, ps)
    st.aboard = True
    ps._skysea_pushed = True
    ps.app.push(st)


def use_in_plane(ps):
    """e in the fuselage: take a station (the controls, a turret, the bombsight) - or the hatch."""
    g = ps.game
    p = g.player
    ss = g.skysea
    meta = g.aboard["meta"]
    pl = plane_of(g)
    key = T.DEFS[int(g.map.t[p.x, p.y])].key
    if key == "hatch_exit":
        if pl is None or pl.state != "flying":
            ss.chute = (pl.x, pl.y, max(200.0, pl.alt)) if pl is not None else None
        else:
            r = ss.bail_out(pl)
            if r:
                g.msg(r, "warn")
                return
        g.msg("You go out through the hatch into the slipstream. The chute cracks open above you.", "warn")
        _leave_plane(g, "air")
        return True                              # (no turn on the fuselage map: it's gone - the sky view has him)
    here = next((n for n, pos in meta["stations"].items() if pos == (p.x, p.y) and n != "hatch"), None)
    if here is None:
        return None
    crew = [c["station"] for c in pl.crew] if pl is not None else []
    if here not in crew and here not in ("pilot",):
        g.msg(f"The {here}'s position. Nothing here for you to work.", "info")
        return
    ss.station = here
    from .skyseaui import SkySeaState
    st = SkySeaState(ps.app, g, ps)
    st.aboard = True
    ps._skysea_pushed = True
    ps.app.push(st)
    g.msg({"pilot": "You take the controls.", "bombardier": "You settle over the bombsight."}.get(
        here, f"You squeeze into the {here}'s position and grip the guns."), "info")


def _leave_plane(game, domain):
    """Out of the aircraft (into the air, under a parachute, or on the ground)."""
    game.domain = domain
    game.aboard = None
    game.map = None
    p = game.player
    # the crew and the fuselage belong to the aircraft's map, which has gone with it
    game.actors = [p] if p is not None else []
    game.vehicles = []
    game.squads = [sq for sq in game.squads if p is not None and p in sq.members]
    game.soldier_at = {}
    game.vehicle_at = {}
