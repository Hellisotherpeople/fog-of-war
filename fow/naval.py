"""The navy between battles: back to base to refuel, rearm and repair; new orders; liberty ashore.

When a sea mission ends, the task force commander decides what she does next, the way a real one
would: if she's short of fuel, has shot off her torpedoes or depth charges, lost half her air group
or taken damage, she goes back to base.  Otherwise there's always more work: another enemy force
reported, a coast to bombard, a convoy to take through, a submarine to hunt, a landing to cover
against air attack, men in the water to pick up.

At the base she anchors.  The oiler comes alongside, the ammunition lighters, the repair ship's
men; it takes as long as it takes (Z to let the hours pass).  Off watch, a sailor can go ashore on
liberty - to the naval base, with its port director, its clerk, its cook and its MPs - and had
better be back aboard by 0600, because when her sailing orders come she sails, with you or without.
"""
from __future__ import annotations

import math

from .constants import other_side

HOUR = 3600
DAY = 86400
SEC = 30                      # sea-world units (100 m) per sector

# the bases navies really used, by theatre: (allies, axis); otherwise "the anchorage off <somewhere>"
BASES = {"okinawa45": (["Kerama Retto", "Ulithi"], ["Kure"]), "iwojima45": (["Saipan", "Ulithi"], ["Chichi Jima"]),
         "guadalcanal42": (["Espiritu Santo", "Tulagi"], ["Rabaul", "Shortland"]),
         "kohima44": (["Chittagong"], ["Rangoon"]), "omaha44": (["Portland", "Plymouth"], ["Cherbourg"]),
         "bocage44": (["Portsmouth", "Plymouth"], ["Cherbourg", "Brest"]), "crete41": (["Alexandria"], ["Piraeus"]),
         "alamein42": (["Alexandria"], ["Tobruk", "Benghazi"]), "sicily43": (["Malta", "Bizerte"], ["Messina"]),
         "cassino44": (["Naples"], ["La Spezia"]), "karelia44": (["Kronstadt"], ["Helsinki"]),
         "stalingrad42": (["Astrakhan"], ["Rostov"])}
COMMAND = {"usa": "the task force commander", "uk": "the Admiralty", "canada": "the Admiralty",
           "australia": "the Admiralty", "germany": "Marinegruppe", "japan": "Combined Fleet",
           "italy": "Supermarina", "ussr": "fleet headquarters", "france": "the admiral"}
FOLLOW_UP = {"dd": ["surface", "asw", "convoy", "bombard", "rescue", "cover"],
             "de": ["asw", "convoy", "rescue"], "cl": ["surface", "bombard", "cover", "convoy"],
             "ca": ["surface", "bombard", "cover"], "bb": ["bombard", "surface", "cover"],
             "cv": ["carrier", "cover"], "cve": ["cover", "convoy", "asw"], "ss": ["sub"], "pt": ["surface", "rescue"],
             "ap": ["convoy"], "lst": ["cover"]}
NEW_TEXT = {"surface": "An enemy force has been reported. Find it and destroy it.",
            "carrier": "Scouts report enemy carriers. Strike before they find us.",
            "convoy": "Take a convoy through. The merchantmen must get there.",
            "bombard": "Bombard the enemy coast in support of the troops ashore.",
            "sub": "A new patrol area: find their shipping and sink it.",
            "asw": "A submarine has been reported in the area. Hunt it down.",
            "cover": "Cover the landings: stay on station and keep their aircraft off the beaches.",
            "rescue": "Men in the water - survivors of a sinking. Get there and pick them up."}


# ============================================================================ ports
def _has_sea_neighbour(st, s):
    for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0)):
        n = st.at(s.x + dx, s.y + dy)
        if n is not None and not n.playable:
            return (dx, dy)
    return None


def nearest_port(game, near=None):
    """A friendly naval base near here.  If our side has none on this coast yet, one is designated on
    the nearest friendly shore that nobody has fought over (a quay and a harbour office go up)."""
    st = game.strategic
    side = game.player.side
    cx, cy = near if near is not None else (game.sector.x, game.sector.y)
    best = None
    for s in st.sectors():
        if s.playable and s.control == side and s.installs(side, "naval_base"):
            d = abs(s.x - cx) + abs(s.y - cy)
            if best is None or d < best[0]:
                best = (d, s)
    if best is not None:
        return best[1]
    cands = []
    for r in range(0, 10):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                s = st.at(cx + dx, cy + dy, create=True)
                if s is None or not s.playable or s.control != side:
                    continue
                v = _has_sea_neighbour(st, s)
                if s.sea_edge is None and v is None:
                    continue
                # best: a shore nobody has generated yet (the harbour gets built into it)
                cands.append((0 if s.saved is None else 1, 0 if s.sea_edge else 1, abs(dx) + abs(dy), s))
        if cands:
            break
    if not cands:
        return None
    cands.sort(key=lambda t: t[:3])
    s = cands[-1][3] if False else cands[0][3]
    if s.sea_edge is None and s.saved is None:
        v = _has_sea_neighbour(st, s)
        s.sea_edge = {(0, -1): "N", (0, 1): "S", (1, 0): "E", (-1, 0): "W"}[v]
        if s.biome in ("town", "city_ruins", "abbey"):
            s.inland = "bocage"
        else:
            s.inland = s.biome if s.biome not in ("sea", "beach") else "farmland"
        s.biome = "beach"
    if not s.installs(side, "naval_base"):
        s.installations.append(["naval_base", side, True])
    return s


def port_name(game, s) -> str:
    names = BASES.get(game.theatre.get("id"))
    if names:
        pool = names[0] if game.player.side == "allies" else names[1]
        return pool[(s.x * 7 + s.y * 13) % len(pool)]
    return f"the anchorage off {s.name}"


def port_point(game, s):
    """Where in the sea world a ship anchors off this base: just off its shore."""
    st = game.strategic
    v = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}.get(s.sea_edge) or _has_sea_neighbour(st, s) or (0, 1)
    x = (s.x + 0.5 + v[0] * 0.75) * SEC
    y = (s.y + 0.5 + v[1] * 0.75) * SEC
    return x, y


# ============================================================================ after the battle
def _needs(ship, m) -> list[str]:
    out = []
    st = ship.st
    if ship.hp < st["hp"] * 0.75 or ship.flood > 20 or getattr(ship, "turret_out", 0):
        out.append("repair")
    if getattr(ship, "fuel", 100.0) < 40:
        out.append("refuel")
    rearm = False
    if st.get("torps") and ship.torps < st["torps"][0] * 0.5:
        rearm = True
    if st.get("dc") and ship.dc < st["dc"] * 0.4:
        rearm = True
    if st.get("air") and ship.air is not None and sum(ship.air) < sum(st["air"]) * 0.6:
        rearm = True
    if rearm:
        out.append("rearm")
    if m.get("sorties", 0) >= 3:
        out.append("give the crew a rest")
    return out


def after_action(game, ss, ship, _again=False):
    """The signal comes: back to base, or the next job."""
    m = ss.mission or {}
    who = COMMAND.get(ship.nation, "the admiral")
    needs = _needs(ship, m)
    if needs:
        sx, sy = int(ship.x // SEC), int(ship.y // SEC)
        port = nearest_port(game, near=(sx, sy))
        if port is not None:
            px, py = port_point(game, port)
            name = port_name(game, port)
            ss.mission = dict(kind="rtb", stage="rtb", start=ss.t, port=(port.x, port.y), port_pt=(px, py),
                              port_name=name, home=(px, py), enemies=[], sorties=m.get("sorties", 0),
                              text=f"Return to {name} to {', '.join(needs)}.")
            game.msg(f"Signal from {who}: '{ship.name}, return to {name} to {_and(needs)}.' "
                     f"(Z to let the hours go by)", "radio")
            game.update_orders(force=True)
            return
    cls = ship.cls
    kinds = FOLLOW_UP.get(cls, ["surface"])
    kind = game.rng.choice(kinds)
    from .skysea_missions import new_orders
    if new_orders(ss, game, kind, sorties=m.get("sorties", 0) + 1, home=m.get("home")):
        game.msg(f"Signal from {who}: '{NEW_TEXT.get(kind, 'New orders.')}'", "radio")
    else:
        # nothing doing on this coast: home it is (once - if there's no port either, she simply steams on)
        m["stage"] = "failed"
        ss.mission["sorties"] = 99
        if not _again:
            return after_action(game, ss, ship, _again=True)
    game.update_orders(force=True)


def _and(xs):
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


# ============================================================================ in port
def enter_port(game, ship):
    """She anchors: the refit begins, and the watch goes to harbour routine."""
    from . import shipboard as SB
    ab = game.aboard
    ss = game.skysea
    m = ss.mission
    t = game.turn
    st = ship.st
    dmg = max(0.0, 1 - ship.hp / st["hp"])
    ab["refit"] = dict(since=t, fuel=t + int((6 + (100 - getattr(ship, "fuel", 100)) / 20) * HOUR),
                       ammo=t + 10 * HOUR, repair=t + int((4 + dmg * 60) * HOUR))
    ab["base_condition"] = "port"
    ab["port"] = dict(name=m.get("port_name", "the anchorage"), sector=m.get("port"), liberty=True)
    m["stage"] = "port"
    ab["condition"] = "port"
    SB._transition(game, ship, "port")
    game.msg(f"{ship.name} comes to anchor at {m.get('port_name', 'the anchorage')}. The oiler is already standing by. "
             f"'Set the in-port watch.' Off watch, you can go ashore on liberty - e at the rail by the gangway.",
             "info")
    game.update_orders(force=True)


def refit_left(game) -> dict:
    r = (game.aboard or {}).get("refit") or {}
    return {k: max(0, v - game.turn) for k, v in r.items() if k != "since"}


def port_tick(game, ship):
    """Hour by hour in port: the oiler, the lighters, the repair gangs - and then her orders."""
    ab = game.aboard
    r = ab.get("refit")
    if not r or ab.get("condition") not in ("port", "GQ"):
        return
    t = game.turn
    st = ship.st
    if t >= r["fuel"] and getattr(ship, "fuel", 100) < 100:
        ship.fuel = 100.0
        game.msg("The oiler casts off: tanks full.", "info")
    if t >= r["ammo"] and not r.get("ammo_done"):
        r["ammo_done"] = True
        if st.get("torps"):
            ship.torps = st["torps"][0]
        if st.get("dc"):
            ship.dc = st["dc"]
        if st.get("air") and ship.air is not None:
            ship.air = list(st["air"])
        for d in ab["decks"].values():
            for v in d.vehicles:
                if v.ai.get("mount"):
                    v.he = 120 if "20" in v.vt.name else 48
        game.msg("The last ammunition lighter pulls away: magazines, torpedoes and ready lockers full"
                 + (", and replacement aircraft flown aboard." if st.get("air") else "."), "info")
    if t < r["repair"]:
        frac = min(1.0, (t - r["since"]) / max(1, r["repair"] - r["since"]))
        ship.hp = max(ship.hp, st["hp"] * (0.5 + 0.5 * frac) if ship.hp < st["hp"] else ship.hp)
        ship.flood = max(0.0, ship.flood - 2)
        ship.fires = 0
    elif not r.get("repair_done"):
        r["repair_done"] = True
        ship.hp = st["hp"]
        ship.flood = 0.0
        ship.fires = 0
        if hasattr(ship, "turret_out"):
            ship.turret_out = 0
        ab["flood_done"] = {}
        ab["shored"] = {}
        game.msg("The repair party from the tender signs off the last of the damage.", "info")
    ready = r.get("ammo_done") and r.get("repair_done") and getattr(ship, "fuel", 100) >= 100
    if ready and "sail_at" not in r:
        r["sail_at"] = _sail_time(game, r)
        ab["port"]["sail_at"] = r["sail_at"]
        wait = r["sail_at"] - t
        when = "tomorrow" if wait < DAY else "the day after"
        game.msg(f"Sailing orders: {ship.name} gets under way at 0600 {when}. Liberty expires at 0500.", "radio")
        ab["ff_stop"] = True
        game.update_orders(force=True)
    if r.get("sail_at") is not None and t >= r["sail_at"]:
        sail(game, ship)


def _sail_time(game, r) -> int:
    """Her sailing time: the first 0600 at least twelve hours after the refit is really finished."""
    import datetime as dt
    ready = max(r.get("fuel", 0), r.get("ammo", 0), r.get("repair", 0))
    when = game.now() + dt.timedelta(seconds=ready - game.turn)
    wait = ((6 - when.hour) % 24) * HOUR - when.minute * 60 - when.second
    if wait < 12 * HOUR:
        wait += DAY
    return ready + wait


def sail(game, ship):
    from . import shipboard as SB
    ab = game.aboard
    ss = game.skysea
    m = ss.mission or {}
    ab["refit"] = None
    ab["port"] = None
    ab["base_condition"] = "III"
    ab["condition"] = "III"
    SB._transition(game, ship, "III")
    game.msg(f"'Special sea and anchor detail!' {ship.name} weighs anchor and stands out to sea.", "info")
    m["sorties"] = 0
    after_ship = dict(m)
    after_ship["stage"] = "done"
    ss.mission = after_ship
    kind = game.rng.choice(FOLLOW_UP.get(ship.cls, ["surface"]))
    from .skysea_missions import new_orders
    home = m.get("port_pt") or m.get("home")
    if new_orders(ss, game, kind, sorties=0, home=home):
        game.msg(f"Once clear of the anchorage, the captain reads out the orders: {NEW_TEXT.get(kind, '')}", "radio")
    game.update_orders(force=True)


def status_words(game) -> str | None:
    """For the orders panel, in port."""
    ab = game.aboard or {}
    if ab.get("condition") != "port" and ab.get("base_condition") != "port":
        return None
    left = refit_left(game)
    bits = []
    ship = None
    try:
        from .aboard import ship_of
        ship = ship_of(game)
    except Exception:
        pass
    if ship is not None and getattr(ship, "fuel", 100) < 100:
        bits.append(f"fuelling ({left.get('fuel', 0) // HOUR} h)")
    r = ab.get("refit") or {}
    if not r.get("ammo_done"):
        bits.append(f"ammunitioning ({left.get('ammo', 0) // HOUR} h)")
    if not r.get("repair_done"):
        bits.append(f"repairs ({left.get('repair', 0) // HOUR} h)")
    port = (ab.get("port") or {}).get("name", "the anchorage")
    txt = f"IN PORT at {port}. " + ("; ".join(bits) + ". " if bits else "Refit complete. ")
    if r.get("sail_at"):
        txt += "Sailing at 0600. "
    return txt


# ============================================================================ liberty
def ship_ashore(game):
    return game.__dict__.get("ship_ashore")


def can_go_ashore(game) -> tuple[bool, str]:
    from . import shipboard as SB
    ab = game.aboard or {}
    if ab.get("kind") != "ship" or ab.get("condition") != "port":
        return False, "Not at sea, you don't."
    if SB.on_watch(game):
        return False, "You're on watch. Liberty is for the off-watch sections."
    if ab.get("task"):
        return False, "You've a job to finish first."
    return True, ""


def go_ashore(ps):
    """Down the gangway into the liberty boat, and ashore at the naval base."""
    from .aboard import _store, ship_of
    from .skysea_exit import to_land
    g = ps.game
    ok, why = can_go_ashore(g)
    if not ok:
        g.msg(why, "info")
        return
    ab = g.aboard
    ss = g.skysea
    ship = ship_of(g)
    port = ab.get("port") or {}
    key = port.get("sector") or (ss.mission or {}).get("port")
    s = g.strategic.at(*key) if key else None
    if s is None:
        g.msg("There's nowhere to go ashore to.", "info")
        return
    now = g.now()
    back = ((5 - now.hour) % 24) * HOUR - now.minute * 60
    if back < HOUR:
        back += DAY
    _store(g)
    p = g.player
    g.__dict__["ship_ashore"] = dict(skysea=ss, aboard=ab, ship_name=ship.name if ship else "the ship",
                                     left=g.turn, back_by=g.turn + back, sail_at=port.get("sail_at"),
                                     port=(s.x, s.y), deck=ab["deck"])
    if p in g.actors:
        g.actors.remove(p)
    g.soldier_at.pop((p.x, p.y), None)
    if p.squad is not None and p in p.squad.members:
        p.squad.members.remove(p)               # (his shipboard squad stays aboard)
    g.domain = "land"
    g.aboard = None
    g.skysea = None
    g.map = None
    to_land(g, s)
    _to_the_pier(g)
    _make_sure_of_the_boat(g, s)
    g.msg(f"The liberty boat puts you ashore at {port.get('name', 'the naval base')}. Be back aboard by 0500. "
          f"(The port director's office is by the quay.)", "info")
    ps._skysea_pushed = False
    ps.recenter()
    g.update_orders(force=True)


def _make_sure_of_the_boat(g, s):
    """A shore whose map was made before it was a harbour: the landing stage is where he comes ashore -
    a port director and his people in a tent, and the boat."""
    from .base import spawn_staff, staff_here
    if staff_here(g, "port_officer"):
        return
    p = g.player
    rec = dict(kind="naval_base", side=p.side, x=p.x, y=p.y, rect=(p.x - 6, p.y - 6, 12, 12),
               name="the landing stage", spots=[("pier", p.x, p.y)])
    spawn_staff(g, rec)
    recs = getattr(g.map, "gen_positions", None)
    if recs is None:
        g.map.gen_positions = recs = []
    recs.append(rec)


def _to_the_pier(g):
    """Stand him on the quay, if the base has one on this map."""
    from .spawn import free_tile_near
    p = g.player
    for rec in getattr(g.map, "gen_positions", []) or []:
        if rec.get("kind") == "naval_base":
            pier = next(((x, y) for k, x, y in rec.get("spots", []) if k == "pier"), (rec["x"], rec["y"]))
            pt = free_tile_near(g, pier[0], pier[1], 5)
            if pt is not None:
                g.soldier_at.pop((p.x, p.y), None)
                p.x, p.y = pt
                g.soldier_at[pt] = p
                g.player_fov()
            return


def return_aboard(ps):
    """The liberty boat back out to her."""
    from . import aboard as AB
    from . import shipboard as SB
    g = ps.game
    ctx = ship_ashore(g)
    if ctx is None:
        g.msg("You haven't a ship to go back to.", "info")
        return
    p = g.player
    late = g.turn > ctx["back_by"]
    # leave the land behind as it is
    if g.__dict__.get("domain") == "land" and g.map is not None:
        g._save_map()
        g.sector.units = g.local_units()
    if p.squad is not None and p in p.squad.members:
        p.squad.members.remove(p)
    if p in g.actors:
        g.actors.remove(p)
    g.soldier_at.pop((p.x, p.y), None)
    g.skysea = ctx["skysea"]
    g.aboard = ctx["aboard"]
    g.domain = "aboard"
    g.__dict__["ship_ashore"] = None
    ab = g.aboard
    ss = g.skysea
    ss.t += max(0, g.turn - ctx["left"])
    weather = next((n for n in ab["order"] if AB.deck(g, n).weather), ab["order"][0])
    d = AB.deck(g, weather)
    fr = ab["frame"]
    spot = min(d.cells, key=lambda c: (abs(c[0] - (fr.x0 + fr.L * 0.45)) + abs(c[1] - (fr.cy + fr.B / 2.0))))
    AB._load(g, weather)
    ab["deck"] = weather
    p.x, p.y = spot
    g.actors.append(p)
    g.soldier_at[(p.x, p.y)] = p
    from .ai import Squad, Order
    sq = Squad(p.side, p.nation, "rifle", "you")
    sq.player_led = True
    sq.no_count = True
    sq.order = Order("follow")
    sq.members.append(p)
    sq.leader = p
    p.squad = sq
    g.squads.append(sq)
    SB.organise(g)
    g.player_fov()
    ship = AB.ship_of(g)
    if late:
        g.msg(f"You come up the gangway {(g.turn - ctx['back_by']) // 60} minutes adrift. The officer of the deck "
              f"takes your name. Captain's mast in the morning.", "warn")
        g.duty.rep -= 4
        g.duty.strikes += 1
    else:
        g.msg(f"The liberty boat brings you back alongside {ship.name if ship else 'her'}. Up the gangway, "
              f"salute the colours, report aboard.", "info")
    ps._skysea_pushed = False
    ps.recenter()
    g.update_orders(force=True)


def land_tick(game):
    """Ashore on liberty: the ship sails at her time, with or without you."""
    ctx = ship_ashore(game)
    if ctx is None:
        return
    ab = ctx["aboard"]
    r = ab.get("refit") or {}
    sail_at = r.get("sail_at")
    # the refit goes on without you watching it
    if sail_at is None and r:
        ship = next((s for s in ctx["skysea"].ships if s.id == ab.get("ship")), None)
        if ship is not None:
            saved_ab, saved_ss = game.aboard, game.skysea
            try:
                game.aboard, game.skysea = ab, ctx["skysea"]
                _refit_only(game, ship)
            finally:
                game.aboard, game.skysea = saved_ab, saved_ss
            sail_at = r.get("sail_at")
    if sail_at is not None and game.turn >= sail_at:
        game.msg(f"From the quay you watch {ctx['ship_name']} weigh anchor and stand out to sea - without you. "
                 f"You've missed your ship's movement. The shore patrol will be looking for you.", "death")
        game.__dict__["ship_ashore"] = None
        game.__dict__["awol"] = True
        game.duty.rep -= 8
        game.update_orders(force=True)


def _refit_only(game, ship):
    """port_tick without the sailing (which can't happen with nobody aboard to see it)."""
    ab = game.aboard
    r = ab.get("refit")
    if not r:
        return
    t = game.turn
    st = ship.st
    if t >= r["fuel"]:
        ship.fuel = 100.0
    if t >= r["ammo"]:
        r["ammo_done"] = True
        if st.get("torps"):
            ship.torps = st["torps"][0]
        if st.get("dc"):
            ship.dc = st["dc"]
        if st.get("air") and ship.air is not None:
            ship.air = list(st["air"])
    if t >= r["repair"]:
        r["repair_done"] = True
        ship.hp = st["hp"]
        ship.flood = 0.0
    if r.get("ammo_done") and r.get("repair_done") and "sail_at" not in r:
        r["sail_at"] = _sail_time(game, r)
        if ab.get("port") is not None:
            ab["port"]["sail_at"] = r["sail_at"]
        game.msg(f"Word at the base: {ship.name} sails at 0600.", "radio")
