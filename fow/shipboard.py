"""Shipboard life: the watches, general quarters, the ship's company at work - and the jobs that fall to you.

A ship at sea runs on a routine.  In cruising condition a third of her company is on watch - the
bridge, the lookouts, the ready guns, the engine and fire rooms - and the rest are asleep in their
bunks, eating, or at work about the ship.  When the enemy is reported the alarm goes - "General
quarters, general quarters, all hands man your battle stations!" - and everyone runs: up and
down the ladders, to the guns, the magazines, the repair lockers, the sickbay.  When it's over the
ship secures and the watches go back to the routine.

Your watch comes round every twelve hours (you're in one of three sections).  Be at your station
when it does, and at your battle station at general quarters; the chief will have something to
say if you aren't.  And there is always work:

    ammunition for a mount that's running dry - a load from the ready-service locker, carried
    fire - a hose from the repair locker, and the fire itself
    flooding - shoring timber from the repair locker, to the leak
    a wounded man - carried to the battle dressing station or the sickbay
    a man overboard - a life ring, thrown from the rail
    a lookout's report - you saw it first: tell the bridge

Enter does what you've been told (see play.py).  Off watch, turn in (e on a bunk) and the hours
go by; Z steams on until something happens.
"""
from __future__ import annotations

import math

from . import tiles as T
from .ai import Order, Squad
from .constants import other_side

# what men at each kind of station are
KIND_ROLE = {"gun": "sailor", "mount_captain": "petty_officer", "bridge": "petty_officer", "lookout": "sailor",
             "cic": "sailor", "radio": "sailor", "engine": "sailor", "magazine": "sailor", "dc": "sailor",
             "medical": "medic", "berth": "sailor", "mess": "sailor", "galley": "sailor", "plane_handler": "sailor",
             "hangar_crew": "sailor", "torpedo": "sailor", "depth_charge": "sailor", "air_ops": "deck_officer"}
KIND_SQUAD = {"gun": "Gun crews", "mount_captain": "Gun crews", "bridge": "Bridge watch", "lookout": "Lookouts",
              "cic": "Combat information", "radio": "Radio", "engine": "Engineering", "magazine": "Magazine crews",
              "dc": "Repair party", "medical": "Medical", "berth": "Off watch", "mess": "Off watch",
              "galley": "Galley", "plane_handler": "Flight deck crew", "hangar_crew": "Hangar crew",
              "torpedo": "Torpedomen", "depth_charge": "Depth charge crew", "air_ops": "Air department"}
# the player's battle station and watch station, by role (first that exists aboard)
BATTLE_PREF = {"sailor": ("gun", "plane_handler", "dc", "magazine", "torpedo"),
               "petty_officer": ("gun", "dc", "torpedo", "bridge"),
               "deck_officer": ("bridge",), "ship_captain": ("bridge",), "sub_commander": ("bridge",),
               "admiral": ("bridge",), "medic": ("medical",)}
WATCH_PREF = {"sailor": ("lookout", "gun", "plane_handler", "dc"), "petty_officer": ("gun", "bridge", "dc"),
              "deck_officer": ("bridge",), "ship_captain": ("bridge",), "sub_commander": ("bridge",),
              "admiral": ("bridge",), "medic": ("medical",)}
DECK_CAP = 170


# ====================================================================== the guns, and who stands where
def mount_guns(game, ship, d):
    """The light AA the shipyard sited on this deck, as crewable mounts."""
    from .data.vehicles import VEHICLES
    from .entities import Vehicle
    for x, y, gid in d.mounts:
        if gid not in VEHICLES:
            gid = "oerlikon"
        v = Vehicle(gid, ship.side, ship.nation, x, y, 2 if y < d.map.h / 2 else 6)
        if not all(d.map.in_bounds(int(cx), int(cy)) and T.WALK[d.map.t[int(cx), int(cy)]] for cx, cy in v.cells()):
            continue
        v.ai["mount"] = True
        v.he = 120 if gid in ("oerlikon", "flak38", "breda20", "type96_25") else 48
        sq = Squad(ship.side, ship.nation, "atgun", f"Mount {len(d.vehicles) + 1} ({VEHICLES[gid].name})")
        sq.no_count = True
        sq.order = Order("hold", target=(x, y), radius=400)
        sq.arrived = True
        v.squad = sq
        sq.vehicles.append(v)
        game.squads.append(sq)
        game.add_vehicle(v)


def assign_player(game, ship, role_station=None):
    """Your battle station and your watch station, from your rate and the ship's."""
    ab = game.aboard
    p = game.player
    role = p.role
    decks = ab["decks"]
    rng = game.rng

    def find(prefs):
        for kind in prefs:
            cands = [(name, s) for name in ab["order"] for s in decks[name].slots if s["kind"] == kind]
            if cands:
                name, s = rng.choice(cands) if kind != "bridge" else cands[0]
                return (name, s["x"], s["y"], kind)
        return None

    if role in ("ship_captain", "sub_commander", "admiral", "deck_officer"):
        for name in ab["order"]:
            st = decks[name].stations
            if "bridge" in st:
                x, y = st["bridge"]
                ab["battle_station"] = (name, x, y, "bridge")
                break
        else:
            ab["battle_station"] = find(("bridge",))
    else:
        ab["battle_station"] = find(BATTLE_PREF.get(role, BATTLE_PREF["sailor"]))
    ab["watch_station"] = find(WATCH_PREF.get(role, WATCH_PREF["sailor"])) \
        if role not in ("ship_captain", "admiral") else ab["battle_station"]
    if ab["battle_station"] is None:
        name = ab["order"][0]
        c = sorted(decks[name].cells)[len(decks[name].cells) // 2]
        ab["battle_station"] = (name, c[0], c[1], "none")
    if ab["watch_station"] is None:
        ab["watch_station"] = ab["battle_station"]
    # take the slot out of the crew's hands: it's yours
    for key in ("battle_station", "watch_station"):
        name, x, y, kind = ab[key]
        for s in decks[name].slots:
            if s["x"] == x and s["y"] == y and s["kind"] == kind:
                s["player"] = True
                break


def _wanted(d, condition):
    if condition == "GQ":
        return [s for s in d.slots if s["gq"] and not s.get("player")]
    out = [s for s in d.slots if s["watch"] and not s.get("player")]
    if condition == "port":
        # harbour routine: a lighter watch, and a third of the ship ashore on liberty
        out = out[::2]
    k = 0
    for s in d.slots:
        if s["kind"] in ("berth", "mess") and not s.get("player"):
            k += 1
            if s["kind"] == "berth" and k % (2 if condition != "port" else 3) == 0 or \
                    s["kind"] == "mess" and k % 4 == 0:
                out.append(s)
    return out


def populate(game, ship, d, condition, arrive=False):
    """Men at their stations on this deck (the deck being the one `game` points at)."""
    from .spawn import make_soldier, place
    rng = game.rng
    want = _wanted(d, condition)[:DECK_CAP]
    squads = {}
    for sq in d.squads:
        if sq.name in KIND_SQUAD.values():
            squads[sq.name] = sq
    for s in want:
        name = KIND_SQUAD.get(s["kind"], "Deck hands")
        sq = squads.get(name)
        if sq is None:
            sq = squads[name] = Squad(ship.side, ship.nation, "rifle", name)
            sq.no_count = True
            sq.order = Order("hold", target=(s["x"], s["y"]), radius=400, issued=game.turn)
            sq.arrived = True
            game.squads.append(sq)
        role = KIND_ROLE.get(s["kind"], "sailor")
        a = make_soldier(game, ship.nation, role)
        a.service = "navy"
        a.ai["post"] = (s["x"], s["y"])
        a.ai["post_kind"] = s["kind"]
        if s["kind"] == "dc":
            a.ai["dc"] = True
        a.squad = sq
        sq.members.append(a)
        if sq.leader is None:
            sq.leader = a
        sq.positions[a.id] = (s["x"], s["y"])
        if arrive and d.ladders:
            lx, ly = rng.choice(list(d.ladders))
            place(game, a, lx, ly, 3)
        else:
            place(game, a, s["x"], s["y"], 2)
        if s["kind"] in ("berth",) and not arrive:
            a.stance = 2
            a.ai["asleep"] = True


def organise(game):
    """The command tree for the deck you're on: the ship, her departments, the parties here."""
    from .command import Formation
    cmd = game.command
    ab = game.aboard
    ship = _ship(game)
    if ship is None:
        return
    p = game.player
    cmd.roots, cmd.bases, cmd.pending, cmd.known, cmd.attached = {}, {}, [], {}, set()
    cmd.billet, cmd.billet_squad = None, None
    root = Formation(cmd.fid(), ship.side, ship.nation, "battalion", ship.name)
    depts = {}
    for sq in game.squads:
        if sq is p.squad:
            continue
        dept = ("Gunnery department" if sq.name.startswith(("Mount", "Gun", "Magazine", "Torpedo", "Depth"))
                else "Engineering department" if sq.name in ("Engineering", "Repair party")
                else "Medical department" if sq.name == "Medical"
                else "Air department" if sq.name in ("Flight deck crew", "Hangar crew", "Air department")
                else "Deck department")
        f = depts.get(dept)
        if f is None:
            f = depts[dept] = Formation(cmd.fid(), ship.side, ship.nation, "company", dept, root)
        f.squads.append(sq)
        sq.formation = f
        sq.short = sq.name[:16]
    cmd.roots[ship.side] = root
    cmd.bases[ship.side] = root
    if p.role in ("ship_captain", "sub_commander", "admiral"):
        root.commander = p
        cmd.billet = root
        root.hq = p.squad
    else:
        root.offmap = (13, "the captain")


def station_words(game):
    ab = game.aboard
    from .shipyard import DECK_NAME
    bn, bx, by, bk = ab["battle_station"]
    wn, wx, wy, wk = ab["watch_station"]
    word = {"gun": "an AA mount", "plane_handler": "the flight deck crew", "dc": "a repair party",
            "magazine": "a magazine", "torpedo": "the torpedo mounts", "bridge": "the bridge",
            "lookout": "a lookout post", "medical": "the sickbay"}
    return (f"Battle station: {word.get(bk, bk)} on {DECK_NAME.get(bn, bn)}. "
            f"Watch: {word.get(wk, wk)}, section {ab['section']}.")


def _ship(game):
    from .aboard import ship_of
    return ship_of(game)


# ====================================================================== the routine
def on_watch(game):
    ab = game.aboard
    h = game.now().hour
    return (h // 4) % 3 == ab["section"] - 1


def tick(game, ship):
    """Every second aboard: the condition, the men moving to their stations, the work, your jobs."""
    if ship is None:
        return
    ab = game.aboard
    t = game.turn
    if t % 5 == 0:
        _condition(game, ship)
    _moving_men(game)
    if t % 4 == 0:
        _loaders(game)
    if t % 3 == 1:
        _lookout(game, ship)
        _tasks(game, ship)
    if t % 30 == 7:
        _watch_change(game)
    if t % 600 == 0 and ab["condition"] == "III" and game.rng.random() < 0.08:
        _man_overboard(game)
    if t % 60 == 11:
        _homeward(game)


def _homeward(game):
    """Between jobs (fow/naval.py): when one ends, the signal for the next - more work, or back to base to
    refuel, rearm and repair; at the base, the refit and then her sailing orders."""
    from . import naval as NV
    ss = game.skysea
    m = ss.mission or {}
    ship = _ship(game)
    if ship is None or not ship.alive:
        return
    ab = game.aboard
    if m.get("stage") in ("done", "failed") and not m.get("decided"):
        m["decided"] = True
        NV.after_action(game, ss, ship)
        return
    if m.get("kind") == "rtb" and m.get("stage") == "arrived" and ab.get("condition") != "port":
        if ab.get("condition") == "GQ":
            return                                   # not while there are aircraft about
        NV.enter_port(game, ship)
        return
    if ab.get("refit"):
        NV.port_tick(game, ship)


def _enemy_near(game, ship):
    """A raid closing (25 km), or enemy ships within gun range (18 km): that's general quarters."""
    ss = game.skysea
    for e in ss.planes:
        if e.alive and e.side != ship.side and e.id in ss.contacts and math.hypot(e.x - ship.x, e.y - ship.y) < 250:
            return True
    for e in ss.ships:
        if e.alive and e.side != ship.side and -e.id in ss.contacts and math.hypot(e.x - ship.x, e.y - ship.y) < 180:
            return True
    return False


def _condition(game, ship):
    ab = game.aboard
    hit = ab.get("last_hit")
    threat = _enemy_near(game, ship) or (hit is not None and game.turn - hit[0] < 120)
    if threat:
        ab["quiet_since"] = None
        if ab["condition"] != "GQ":
            general_quarters(game, ship)
    elif ab["condition"] == "GQ":
        if ab.get("quiet_since") is None:
            ab["quiet_since"] = game.turn
        elif game.turn - ab["quiet_since"] > 900 and not any((d.map.fire > 0).any() for d in ab["decks"].values()):
            secure(game, ship)


def general_quarters(game, ship):
    """'General quarters, general quarters - all hands man your battle stations!'"""
    ab = game.aboard
    ab["condition"] = "GQ"
    ab["gq_turn"] = game.turn
    game.audio("siren", game.player.x, game.player.y, 90)
    game.msg("BONG-BONG-BONG... 'General quarters, general quarters! All hands man your battle stations!' "
             "Men pour up and down the ladders.", "death")
    _transition(game, ship, "GQ")
    game.update_orders(force=True)


def secure(game, ship):
    ab = game.aboard
    back = ab.get("base_condition", "III")
    ab["condition"] = back
    game.msg("'Secure from general quarters. " + ("Set the in-port watch.'" if back == "port" else
                                                  "Set condition three.'") + " The off-watch sections go below.",
             "info")
    _transition(game, ship, back)
    game.update_orders(force=True)


def _transition(game, ship, condition):
    """Every deck: the men who aren't needed go; the men who are come - running, here where you can see."""
    from .aboard import deck
    ab = game.aboard
    cur = ab["deck"]
    for name in ab["order"]:
        d = deck(game, name)
        if name == cur:
            continue
        keep = [a for a in d.actors if a.is_player or not a.alive or a.downed or a.state != "ok"]
        gone = [a for a in d.actors if a not in keep]
        for a in gone:
            d.soldier_at.pop((a.x, a.y), None)
        d.actors[:] = keep
        for sq in d.squads:
            sq.members = [a for a in sq.members if a in keep]
        saved = (game.map, game.actors, game.vehicles, game.squads, game.soldier_at, game.vehicle_at)
        game.map, game.actors, game.vehicles, game.squads = d.map, d.actors, d.vehicles, d.squads
        game.soldier_at, game.vehicle_at = d.soldier_at, d.vehicle_at
        populate(game, ship, d, condition)
        (game.map, game.actors, game.vehicles, game.squads, game.soldier_at, game.vehicle_at) = saved
    # this deck: some leave by the ladders, others arrive by them
    d = deck(game)
    want = _wanted(d, condition)
    wanted_kinds = {}
    for s in want:
        wanted_kinds[s["kind"]] = wanted_kinds.get(s["kind"], 0) + 1
    have = {}
    for a in game.actors:
        k = a.ai.get("post_kind")
        if k is None or a.is_player or not a.alive or a.downed:
            continue
        have[k] = have.get(k, 0) + 1
        if have[k] > wanted_kinds.get(k, 0) and d.ladders:
            a.ai["leaving"] = min(d.ladders, key=lambda c: abs(c[0] - a.x) + abs(c[1] - a.y))
            if a.squad is not None:
                a.squad.positions[a.id] = a.ai["leaving"]
            a.ai.pop("asleep", None)
            a.stance = 0
    arrivals = []
    got = dict(have)
    for s in want:
        k = s["kind"]
        if got.get(k, 0) > 0:
            got[k] -= 1
            continue
        arrivals.append(s)
    ab["arrivals"] = arrivals[:DECK_CAP]


def _moving_men(game):
    """Men arriving on this deck come down (or up) the ladders; men leaving go up (or down) them."""
    ab = game.aboard
    from .aboard import deck
    d = deck(game)
    ship = _ship(game)
    arr = ab.get("arrivals") or []
    if arr and d.ladders and ship is not None:
        batch = arr[:2]
        ab["arrivals"] = arr[2:]
        place_arrivals(game, ship, d, batch, arrive=True)
    for a in list(game.actors):
        lv = a.ai.get("leaving")
        if lv and max(abs(a.x - lv[0]), abs(a.y - lv[1])) <= 1:
            game.remove_actor(a)
            if a.squad is not None and a in a.squad.members:
                a.squad.members.remove(a)


def place_arrivals(game, ship, d, slots, arrive=True):
    """Put men at these slots on the current deck (coming down the ladders if `arrive`).  The slots were
    already chosen for the condition (see _transition), so they're filled as they are - not filtered again."""
    d.slots_backup = None
    tmp = d.slots
    d.slots = [dict(s, gq=True, watch=True) for s in slots]
    try:
        populate(game, ship, d, "GQ", arrive=arrive)
    finally:
        d.slots = tmp


def _loaders(game):
    """The loaders keep the mounts fed from the ready-service lockers - unless that's your job right now."""
    ab = game.aboard
    task = ab.get("task")
    for v in game.vehicles:
        if not v.ai.get("mount") or v.dead:
            continue
        full = 120 if v.vt.main in ("20mm_flak", "20mm_jp") else 48
        if task and task.get("kind") == "ammo" and task.get("mount") == v.id:
            continue
        crew = [a for a in game.actors if a.alive and not a.downed and a.ai.get("post_kind") == "gun" and
                max(abs(a.x - v.x), abs(a.y - v.y)) <= 3]
        if crew and v.he < full and game.rng.random() < 0.25 * len(crew) / 2:
            v.he = min(full, v.he + (30 if full == 120 else 8))


def _watch_change(game):
    ab = game.aboard
    now = on_watch(game)
    if ab.get("was_on_watch") is None:
        ab["was_on_watch"] = now
        return
    if now != ab["was_on_watch"]:
        ab["was_on_watch"] = now
        if now:
            game.msg("'Now relieve the watch. Section " + str(ab["section"]) + ", on watch!' It's your watch.", "radio")
        else:
            game.msg("You're relieved. Off watch: eat, sleep - turn in (e on a bunk) or Z to let the hours go.",
                     "info")


def _man_overboard(game):
    """Someone's gone over the side."""
    from .aboard import deck, weather_deck
    ab = game.aboard
    wd = weather_deck(game)
    if wd is None:
        return
    ab["overboard"] = dict(turn=game.turn, deck=wd.name, saved=False)
    game.msg("'MAN OVERBOARD! MAN OVERBOARD, PORT SIDE!' - a life ring, from the rail, quick!", "death")


# ====================================================================== the lookout
def _lookout(game, ship):
    """At a lookout post, you may see what the ship hasn't yet - a speck in the sky, smoke on the horizon."""
    from .aboard import _relative, deck
    ab = game.aboard
    p = game.player
    m = game.map
    near_post = any(m.in_bounds(p.x + dx, p.y + dy) and m.t[p.x + dx, p.y + dy] == T.ID["lookout_post"]
                    for dx in (-1, 0, 1) for dy in (-1, 0, 1))
    if not near_post or ab.get("spotted"):
        return
    ss = game.skysea
    night = game.is_night()
    rng = game.rng
    best = None
    for e in list(ss.planes) + list(ss.ships):
        if not e.alive or e.side == ship.side:
            continue
        eid = e.id if e in ss.planes else -e.id
        if eid in ss.contacts:
            continue
        d = math.hypot(e.x - ship.x, e.y - ship.y)
        limit = (150 if e in ss.planes else 260) * (0.3 if night else 1.0)
        if d > limit:
            continue
        chance = 0.12 * (1 - d / limit) * (1.4 if p.has_tool("binoculars") else 1.0) * (0.6 + p.skill * 0.06)
        if rng.random() < chance and (best is None or d < best[1]):
            best = (e, d, eid)
    if best is None:
        return
    e, d, eid = best
    rel = bearing_rel(ship, e)
    what = "aircraft - a speck, then several, high up" if e in ss.planes else "smoke - a smudge on the horizon"
    ab["spotted"] = dict(eid=eid, turn=game.turn, text=f"{what}, {_relative(rel)}, about {d / 10:.0f} km")
    game.msg(f"You catch something through the glasses: {ab['spotted']['text']}. (Enter to report it)", "warn")


def bearing_rel(ship, e):
    from .skysea import bearing
    return bearing(ship.x, ship.y, e.x, e.y) - ship.hdg


def report(game):
    """'Bridge, lookout: aircraft bearing two-two-zero, high!'"""
    ab = game.aboard
    sp = ab.pop("spotted", None)
    if not sp:
        return None
    ss = game.skysea
    ab.setdefault("reported_ids", set()).add(sp["eid"])
    ss.contacts.add(sp["eid"])
    game.player.say("Bridge, lookout! " + sp["text"].split(",")[0].capitalize() + "!", game.turn, 3)
    game.msg(f"You report it. The bridge answers: 'Very well.' A moment later the alarm goes.", "good")
    game.command.merit += 2
    game.duty.rep += 1
    ship = _ship(game)
    if ship is not None and ab["condition"] != "GQ":
        general_quarters(game, ship)
    return 150


# ====================================================================== your jobs
TASK_TEXT = {"station": "Man your battle station!", "watch": "You're on watch - get to your station.",
             "ammo": "Mount {n} needs ammunition - get a load from the ready locker and feed it!",
             "fire": "Fire! Get a hose from the repair locker and put it out!",
             "shore": "We're flooding - get shoring timber from the repair locker and shore up that leak!",
             "casevac": "Get him to the dressing station!",
             "overboard": "Man overboard - a life ring, from the rail!",
             "report": "You've seen something - report it to the bridge!"}


def _give(game, kind, **data):
    ab = game.aboard
    ab["task"] = dict(kind=kind, issued=game.turn, deadline=game.turn + {"station": 120, "watch": 240, "ammo": 150,
                                                                         "fire": 240, "shore": 300, "casevac": 240,
                                                                         "overboard": 90, "report": 40}[kind], **data)
    txt = TASK_TEXT[kind].format(**{k: v for k, v in data.items() if isinstance(v, (int, str))})
    game.msg(("Chief: '" if kind not in ("report", "overboard") else "") + txt + ("'" if kind not in ("report", "overboard")
                                                                              else ""), "radio")
    game.update_orders(force=True)


def at(game, where, r=1):
    """Is the player at (deck, x, y) within r tiles?"""
    ab = game.aboard
    p = game.player
    return where is not None and where[0] == ab["deck"] and max(abs(p.x - where[1]), abs(p.y - where[2])) <= r


def _tasks(game, ship):
    ab = game.aboard
    p = game.player
    t = ab.get("task")
    if t is not None:
        return _check(game, ship, t)
    if not p.alive or p.state != "ok":
        return
    if ab.get("spotted") and game.turn - ab["spotted"]["turn"] < 40:
        return _give(game, "report")
    ov = ab.get("overboard")
    if ov and not ov["saved"] and game.turn - ov["turn"] < 90 and ab["deck"] == ov["deck"]:
        return _give(game, "overboard")
    bs = ab["battle_station"]
    if ab["condition"] == "GQ" and not at(game, bs, 2):
        return _give(game, "station", target=bs)
    if ab["condition"] in ("III", "port") and on_watch(game) and not at(game, ab["watch_station"], 3) and \
            game.turn - ab.get("watch_nag", -9999) > 300:
        ab["watch_nag"] = game.turn
        return _give(game, "watch", target=ab["watch_station"])
    m = game.map
    # a mount near you running dry
    for v in game.vehicles:
        if v.ai.get("mount") and not v.dead and v.he < 20 and max(abs(v.x - p.x), abs(v.y - p.y)) < 25 and \
                ab["condition"] == "GQ":
            return _give(game, "ammo", mount=v.id, n=int(v.squad.name.split()[1]) if v.squad else 0)
    # fire on this deck
    if (m.fire > 0).any():
        import numpy as np
        f = np.argwhere(m.fire > 0)
        d = abs(f[:, 0] - p.x) + abs(f[:, 1] - p.y)
        i = int(d.argmin())
        if d[i] < 40:
            return _give(game, "fire", at=(int(f[i][0]), int(f[i][1])))
    # water coming in on this deck
    leaks = [(x, y) for x in range(max(0, p.x - 30), min(m.w, p.x + 30)) for y in range(max(0, p.y - 12),
                                                                                         min(m.h, p.y + 12))
             if m.water[x, y] >= 1 and T.DEFS[int(m.t[x, y])].key in ("shallow", "deep") and
             not T.DEFS[int(m.t[x, y])].key.startswith("sea")]
    if leaks and not game.aboard["decks"][ab["deck"]].weather:
        c = min(leaks, key=lambda c: abs(c[0] - p.x) + abs(c[1] - p.y))
        if not ab.setdefault("shored", {}).get(ab["deck"]):
            return _give(game, "shore", at=c)
    # a wounded man with nobody seeing to him
    for a in game.actors:
        if a is p or not a.alive or not a.downed or a.side != p.side or a.ai.get("carried_by"):
            continue
        if max(abs(a.x - p.x), abs(a.y - p.y)) <= 10 and not a.ai.get("at_aid"):
            return _give(game, "casevac", who=a.id)


def _check(game, ship, t):
    ab = game.aboard
    k = t["kind"]
    p = game.player
    done = False
    if k == "station":
        done = at(game, ab["battle_station"], 2) or ab["condition"] != "GQ"
    elif k == "watch":
        done = at(game, ab["watch_station"], 3) or not on_watch(game)
    elif k == "ammo":
        v = next((v for v in game.vehicles if v.id == t.get("mount")), None)
        done = v is None or v.dead or v.he >= 40
    elif k == "fire":
        m = game.map
        x, y = t["at"]
        done = not (m.fire[max(0, x - 3):x + 4, max(0, y - 3):y + 4] > 0).any()
    elif k == "shore":
        done = ab.get("shored", {}).get(ab["deck"], False)
    elif k == "casevac":
        a = next((a for a in game.actors if a.id == t.get("who")), None)
        done = a is None or not a.alive or a.ai.get("at_aid") is not None or not a.downed
    elif k == "overboard":
        ov = ab.get("overboard") or {}
        done = ov.get("saved", True)
    elif k == "report":
        done = "spotted" not in ab
    if done:
        ab["task"] = None
        reward = {"station": 0.5, "watch": 0.2, "ammo": 2, "fire": 3, "shore": 3, "casevac": 2, "overboard": 3,
                  "report": 0}[k]
        if reward and not (k == "station" and game.turn - t["issued"] > 90):
            game.command.merit += reward
            game.duty.rep += reward / 2
        if k in ("ammo", "fire", "shore", "casevac", "overboard"):
            game.msg({"ammo": "The mount's firing again. 'That's the way.'", "fire": "The fire's out. Steam and "
                      "black water everywhere.", "shore": "The shoring holds. The pumps start to gain.",
                      "casevac": "The corpsmen take him.", "overboard": "They haul him in, blue and choking."}[k],
                     "good")
        game.update_orders(force=True)
        return
    if game.turn > t["deadline"]:
        ab["task"] = None
        if k in ("station", "ammo", "fire", "shore"):
            game.duty.rep -= 2
            game.msg("The chief finds you: 'Where the hell were you?' That goes on your record.", "warn")
        game.update_orders(force=True)


def task_line(game):
    t = game.aboard.get("task")
    if not t:
        return None
    return TASK_TEXT[t["kind"]].format(**{k: v for k, v in t.items() if isinstance(v, (int, str))})


# ====================================================================== what you do with your hands
def use(ps):
    """e aboard, beside something: a ready locker, a repair locker, a mount (with a load), a fire, a leak,
    a life ring, the rail, a bunk.  Returns None if there's nothing of the kind here."""
    g = ps.game
    p = g.player
    ab = g.aboard
    m = g.map
    near = [(p.x + dx, p.y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if m.in_bounds(p.x + dx, p.y + dy)]
    keys = {c: T.DEFS[int(m.t[c])].key for c in near}
    def carrying(tool):
        h = p.invent.hands
        if h is not None and h.t.tool == tool:
            return h
        return p.find(lambda i: i.t.tool == tool)
    from .entities import Item

    def carry(it):
        """Into your kit if it fits; in your arms if it doesn't."""
        if p.add_item(it) is not None:
            return True
        if p.invent.hands is None:
            p.invent.hands = it
            it.where = "carried"
            return True
        return False
    # feeding a mount
    load = carrying("ammo_load")
    if load is not None:
        for v in g.vehicles:
            if v.ai.get("mount") and not v.dead and any(max(abs(cx - p.x), abs(cy - p.y)) <= 1 for cx, cy in v.cells()):
                full = 120 if v.vt.main in ("20mm_flak", "20mm_jp") else 48
                _drop_from(p, load)
                v.he = min(full, v.he + (60 if full == 120 else 16))
                g.msg(f"You heave the load into the mount's ready rack. The loader slaps a magazine on.", "good")
                return ps.act(150)
    if "ready_locker" in keys.values():
        if load is None:
            if not carry(Item("ammo_load")):
                g.msg("Your hands are full.", "info")
                return True
            g.msg("You drag a load of ready ammunition out of the locker - heavy - and stagger with it.", "info")
            return ps.act(200)
    if "repair_locker" in keys.values():
        from .render import Popup
        opts = [("A fire hose and a foam applicator", "fire_hose", None, carrying("hose") is None),
                ("Shoring timber and wedges", "shoring", None, carrying("shoring") is None)]

        def take(v):
            if v and carry(Item(v)):
                g.msg(f"You take the {Item(v).name} from the repair locker.", "info")
                ps.act(120)
        ps.open_popup(Popup("Repair locker", opts, ps._screen_anchor()), take)
        return True
    if "life_ring" in keys.values() and carrying("life_ring") is None:
        carry(Item("life_ring_item"))
        g.msg("You wrench the life ring off its bracket.", "info")
        return ps.act(60)
    # a fire in reach, and a hose in your hands
    if carrying("hose") is not None and any(m.fire[c] > 0 for c in near):
        for c in near:
            m.fire[c] = max(0, int(m.fire[c]) - 60)
        g.msg("You open the nozzle and drive the fire back with foam and fog.", "good")
        return ps.act(150)
    # shoring a leak
    if carrying("shoring") is not None and not ab["decks"][ab["deck"]].weather and \
            any(keys[c] in ("shallow", "deep") for c in near):
        _drop_from(p, carrying("shoring"))
        ab.setdefault("shored", {})[ab["deck"]] = True
        ship = _ship(g)
        if ship is not None:
            ship.flood = max(0.0, ship.flood - 8)
        g.msg("You and two others jam the timber against the split plating and drive the wedges home. It holds.",
              "good")
        return ps.act(900)
    # throwing a life ring to the man in the water
    ring = carrying("life_ring")
    ov = ab.get("overboard")
    if ring is not None and ov and not ov["saved"] and any(keys[c] == "railing" for c in near) | \
            (T.DEFS[int(m.t[p.x, p.y])].key == "railing"):
        _drop_from(p, ring)
        ov["saved"] = True
        g.msg("You hurl the ring. He gets an arm through it. They haul him along the side to a scramble net.", "good")
        return ps.act(100)
    # turning in
    if T.DEFS[int(m.t[p.x, p.y])].key == "bunk":
        return turn_in(ps)
    return None


def turn_in(ps):
    g = ps.game
    ab = g.aboard
    if ab["condition"] == "GQ":
        g.msg("At general quarters? Get to your station.", "warn")
        return True
    if on_watch(g):
        g.msg("You're on watch. The chief would have your hide.", "warn")
        return True
    g.player.stance = 2
    g.msg("You climb into your rack, boots and all, and are asleep before your head's down.", "info")
    ps.fast_forward(sleep=True)
    return True


# ====================================================================== time going by quickly
def quiet(game):
    """Nothing needing you this minute: no job, nothing overhead (at general quarters: you're at your station)."""
    ab = game.aboard
    if ab.get("task") or ab.get("spotted") or (game.support is not None and game.support.aircraft):
        return False
    if ab["condition"] == "GQ" and not at(game, ab["battle_station"], 2):
        return False
    return True


def fast_step(game, secs=30):
    """Time passes in big steps when nothing's happening: the ship steams on, the watches change."""
    from .constants import STRATEGIC_TICK
    ss = game.skysea
    ship = _ship(game)
    ab = game.aboard
    before = set(ss.contacts)
    watch0 = on_watch(game)
    cond0 = ab["condition"]
    mis0 = (id(ss.mission), (ss.mission or {}).get("stage"))
    hit0 = ab.get("last_hit")
    if cond0 == "GQ":
        secs = min(secs, 10)                     # standing by at general quarters: shorter steps
    t0 = game.turn
    ss.hit_hook = None
    from .aboard import on_hit, take_attack
    ss.hit_hook = lambda s, dmg, flood, what, fire, deck_: on_hit(game, s, dmg, flood, what, fire, deck_)
    ss.local_hook = lambda plane, tgt: False
    ss.step(secs, clock=False)
    game.turn += secs
    game.clock += secs
    game._weather_tick()
    for k in range(t0 // STRATEGIC_TICK + 1, game.turn // STRATEGIC_TICK + 1):
        try:
            game._strategic_tick()
        except Exception:
            pass
    p = game.player
    if ab.get("sleeping"):
        p.fatigue = max(0.0, getattr(p, "fatigue", 0.0) - secs * 0.004)
        p.stamina = 100.0
    if ship is not None and ship.alive:
        from .aboard import _flooding, _fires_elsewhere
        _flooding(game, ship)
        _fires_elsewhere(game, ship)
        _condition(game, ship)
        _watch_change(game)
    # stop for an enemy you haven't seen before (contacts come and go as the range opens and closes)
    seen = ab.setdefault("ff_seen", set())
    fresh = set()
    if ship is not None:
        for e in ss.planes:
            if e.alive and e.side != ship.side and e.id in ss.contacts and e.id not in seen:
                fresh.add(e.id)
        for e in ss.ships:
            if e.alive and e.side != ship.side and -e.id in ss.contacts and -e.id not in seen:
                fresh.add(-e.id)
    seen |= fresh
    if fresh:
        game.msg("A report from the bridge: contact - " + ("aircraft" if any(i > 0 for i in fresh) else "ships") +
                 ".", "radio")
    del before
    _homeward(game)
    if (id(ss.mission), (ss.mission or {}).get("stage")) != mis0 or ab.pop("ff_stop", None):
        return True                              # new orders, the anchorage, the sailing signal
    if on_watch(game) and not watch0:
        return True                              # your watch: go and stand it
    return bool(fresh) or ab["condition"] != cond0 or ab.get("last_hit") != hit0 or ss.over or \
        (ship is not None and not ship.alive) or ab.get("task") is not None or \
        any(p2.alive and p2.side != ship.side and math.hypot(p2.x - ship.x, p2.y - ship.y) < 60
            for p2 in ss.planes) if ship is not None else True


def _drop_from(p, it):
    if p.invent.hands is it:
        p.invent.hands = None
    else:
        p.remove_item(it)


# ====================================================================== Enter: doing the job
def route(ps, where, then=None, stop_short=0):
    """Walk to (deck, x, y) - up and down the ladders as needed - and do `then` on arrival."""
    from .aboard import climb, deck
    g = ps.game
    ab = g.aboard
    p = g.player
    dname, x, y = where[0], where[1], where[2]
    if dname == ab["deck"]:
        return ps.start_travel(x, y, then=then, stop_short=stop_short)
    order = ab["order"]
    up = order.index(dname) < order.index(ab["deck"])
    way = "up" if up else "down"
    d = deck(g)
    lads = [c for c, w in d.ladders.items() if way in w]
    if not lads:
        g.msg("You can't see the way from here.", "info")
        return False
    lx, ly = min(lads, key=lambda c: abs(c[0] - p.x) + abs(c[1] - p.y))

    def go_on():
        climb(ps, way)
        k = ps.__dict__.get("_order_retry", 0)
        if k < 8:
            ps.cmd_do_order(retry=k + 1)
    return ps.start_travel(lx, ly, then=go_on)


def _nearest(game, key):
    m = game.map
    p = game.player
    import numpy as np
    pts = np.argwhere(m.t == T.ID[key])
    if not len(pts):
        return None
    d = abs(pts[:, 0] - p.x) + abs(pts[:, 1] - p.y)
    i = int(d.argmin())
    return int(pts[i][0]), int(pts[i][1])


def _beside(game, x, y):
    """A walkable tile next to (x, y) nearest you."""
    m = game.map
    p = game.player
    best = None
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            xx, yy = x + dx, y + dy
            if (dx or dy) and m.in_bounds(xx, yy) and T.WALK[m.t[xx, yy]] and m.water[xx, yy] < 2:
                d = abs(xx - p.x) + abs(yy - p.y)
                if best is None or d < best[0]:
                    best = (d, xx, yy)
    return (best[1], best[2]) if best else (x, y)


def plan(ps):
    """(what Enter will do, the doing of it) for the job you've been given aboard."""
    from .entities import Item
    g = ps.game
    ab = g.aboard
    p = g.player
    t = ab.get("task")
    here = ab["deck"]

    def holding(tool):
        h = p.invent.hands
        return (h is not None and h.t.tool == tool) or p.find(lambda i: i.t.tool == tool) is not None

    def use_now():
        use(ps)
    if t is None:
        if ab["condition"] == "GQ" and not at(g, ab["battle_station"], 2):
            return ("go to your battle station", lambda: route(ps, ab["battle_station"]))
        if on_watch(g) and ab["condition"] in ("III", "port") and not at(g, ab["watch_station"], 3):
            return ("go to your watch station", lambda: route(ps, ab["watch_station"]))
        return None
    k = t["kind"]
    if k in ("station", "watch"):
        return (f"go to your {'battle' if k == 'station' else 'watch'} station", lambda: route(ps, t["target"]))
    if k == "report":
        return ("report what you saw to the bridge", lambda: ps.act(report(g) or 50))
    if k == "ammo":
        v = next((v for v in g.vehicles if v.id == t.get("mount")), None)
        if v is None:
            return None
        if holding("ammo_load"):
            return ("carry the load to the mount and feed it",
                    lambda: ps.start_travel(*_beside(g, v.x, v.y), then=use_now))
        lk = _nearest(g, "ready_locker")
        if lk is None:
            return None
        return ("get a load from the ready-service locker", lambda: ps.start_travel(*_beside(g, *lk), then=use_now))
    if k in ("fire", "shore"):
        tool = "hose" if k == "fire" else "shoring"
        if holding(tool):
            x, y = t["at"]
            return ("go at the fire with the hose" if k == "fire" else "shore up the leak",
                    lambda: ps.start_travel(*_beside(g, x, y), then=use_now))
        lk = _nearest(g, "repair_locker")
        if lk is None:
            return None

        def draw():
            if p.add_item(Item("fire_hose" if k == "fire" else "shoring")) is None and p.invent.hands is None:
                it = Item("fire_hose" if k == "fire" else "shoring")
                p.invent.hands = it
                it.where = "carried"
            g.msg("You draw " + ("a hose" if k == "fire" else "shoring timber") + " from the repair locker.", "info")
            ps.act(120)
        return ("get " + ("a hose" if k == "fire" else "shoring timber") + " from the repair locker",
                lambda: ps.start_travel(*_beside(g, *lk), then=draw))
    if k == "casevac":
        a = next((a for a in g.actors if a.id == t.get("who")), None)
        if a is None:
            return None
        if p.carrying is a:
            posts = [r for r in (getattr(g.map, "gen_positions", None) or []) if r.get("kind") == "aid"]
            beds = _nearest(g, "bed")
            if beds is None:
                return None

            def lay():
                from . import actions as A
                A.put_down(g, p, _beside(g, *beds))
                a.ai["at_aid"] = g.turn
                a.ai["to_aid"] = g.turn
                g.msg(f"You lay him down by the corpsmen.", "good")
            return ("carry him to the dressing station", lambda: ps.start_travel(*_beside(g, *beds), then=lay))

        def lift():
            from . import actions as A
            c = A.pick_up(g, p, a)
            if c:
                g.msg("You get him over your shoulder.", "info")
                ps.act(c)
        return ("go to him and pick him up", lambda: ps.start_travel(a.x, a.y, then=lift, stop_short=1))
    if k == "overboard":
        if holding("life_ring"):
            wd = ab["decks"][here]
            rails = sorted(c for c in wd.cells if g.map.t[c] == T.ID["railing"] and c[1] < ab["frame"].cy)
            if not rails:
                return None
            r = min(rails, key=lambda c: abs(c[0] - p.x) + abs(c[1] - p.y))
            return ("throw the life ring from the rail", lambda: ps.start_travel(*_beside(g, *r), then=use_now))
        lr = _nearest(g, "life_ring")
        if lr is None:
            return None
        return ("get a life ring", lambda: ps.start_travel(*_beside(g, *lr), then=use_now))
    return None
