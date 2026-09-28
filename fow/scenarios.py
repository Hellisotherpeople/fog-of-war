"""Battle types: what kind of war you've been dropped into.

Most men spent the war in a line with other men.  Some spent it in a tank in the
middle of a thousand others; some crawled through no-man's land at night to count
the enemy's sentries; some parachuted into occupied country with a forged identity
card and a pistol they prayed they'd never draw; some lived in the forest and
ambushed trucks.  A battle type decides where you start, who's with you, what the
enemy has - and what you're there to do.
"""
from __future__ import annotations

from collections import Counter

from .constants import SIDES, other_side

SCENARIOS = {
    "front": dict(name="Front-line battle", role=None, w=40,
                  desc="The war as most men knew it: your squad, your company, a piece of ground the other side "
                       "wants. Attack or defend as the situation falls."),
    "assault": dict(name="The big push", role=None, w=8,
                    desc="You go over in the first wave against a prepared line: wire, bunkers, mines, machine "
                         "guns. The guns fire first. Then it's you."),
    "defence": dict(name="Hold the line", role=None, w=8,
                    desc="Dug in, and they're coming - in strength, after a bombardment, again and again. Hold."),
    "armour": dict(name="Tank battle", role="tank_crew", w=7,
                   desc="Steel on steel across open ground. Dozens of tanks, tank destroyers and half-tracks on "
                        "both sides; infantry crouching in their shadow."),
    "patrol": dict(name="Night patrol", role="squad_leader", w=5,
                   desc="Four or five of you, blackened faces, into the enemy's lines in the dark. Find out what's "
                        "there and bring the knowledge home. Shooting means you've failed."),
    "raid": dict(name="Commando raid", role="engineer", w=4,
                 desc="A small team far behind the line. There's a depot or a battery to destroy. Then get out."),
    "agent": dict(name="Behind the lines", role="agent", w=3,
                  desc="Alone, in civilian clothes, with forged papers. Their headquarters holds the plans for the "
                       "next offensive. Steal them and get them home - across the front."),
    "partisans": dict(name="Partisan ambush", role="partisan", w=3,
                      desc="The forest is yours at night. A convoy is coming down the road. Hit it and vanish."),
    "encircled": dict(name="Encircled", role=None, w=3,
                      desc="Cut off. The enemy's on three sides and closing. Break out to your own lines."),
    "rearguard": dict(name="Rearguard", role=None, w=3,
                      desc="The army is pulling back. Someone has to hold here long enough for it to get away."),
    "gunline": dict(name="The gun line", role="artilleryman", w=3,
                    desc="A battery of guns behind the front. The fire missions come down the wire and you lay "
                         "and fire at targets you'll never see - until the enemy's sound-rangers find you, or "
                         "the front comes to you."),
    "sniper": dict(name="Sniper's hunt", role="sniper", w=3,
                   desc="You and a spotter. Their officers, their machine gunners - and their sniper, who is "
                        "hunting you."),
    "evader": dict(name="Shot down", role="pilot", w=2,
                   desc="Your aircraft is burning in a field behind you. You're alive, deep in enemy country. "
                        "Get home."),
    "pow": dict(name="Prisoner of war", role=None, w=1,
                desc="The war goes on without you, beyond the wire. Survive. Escape, if you can."),
}


def eligible(sid, theatre, side) -> bool:
    th = theatre
    if sid.startswith(("air:", "sea:")):
        return True                         # checked for real (aircraft, ships, sea) when the game starts
    if sid == "armour":
        return th["armor"].get(side, 0) >= 0.2 and th["armor"].get(other_side(side), 0) >= 0.15
    if sid == "partisans":
        from .threat import PARTISANS
        return side == "allies" and th.get("id") in PARTISANS
    if sid in ("raid", "agent", "evader", "patrol"):
        return True
    return True


def pick(rng, theatre, side) -> str:
    ids = [k for k in SCENARIOS if eligible(k, theatre, side)]
    return rng.choices(ids, [SCENARIOS[k]["w"] for k in ids])[0]


def partisan_nation(theatre):
    from .threat import PARTISANS
    return PARTISANS.get(theatre.get("id", ""))


# ====================================================================== choosing the ground

def _front_pair(game, side):
    """(one of our front sectors, the enemy sector next to it)."""
    st = game.strategic
    rng = game.rng
    fronts = [s for s in st.sectors() if s.playable and s.control == side and st.is_front(s, side)]
    rng.shuffle(fronts)
    for s in fronts:
        nb = [n for n in st.neighbors(s) if n.control == other_side(side) and n.playable]
        if nb:
            return s, rng.choice(nb)
    return None, None


def _deep(game, side, depth):
    """An enemy sector `depth` steps behind their front, straight back from one of ours."""
    from .strategic import DIRS, OPP
    st = game.strategic
    enemy = other_side(side)
    ours, theirs = _front_pair(game, side)
    if theirs is None:
        return None
    back = st.att_from if enemy == st.attacker else OPP[st.att_from]
    dx, dy = DIRS[back]
    best = theirs
    for k in range(1, depth + 1):
        c = st.at(theirs.x + dx * k, theirs.y + dy * k, create=True)
        if c is None or not c.playable:
            break
        if c.control == enemy:
            best = c
    return best


def _gun_line(game, side):
    """Our artillery position nearest the fighting (there's always one: if the map hasn't one, the division's
    guns are just behind the front)."""
    st = game.strategic
    arty = [s for s in st.sectors() if s.playable and s.control == side and s.installs(side, "artillery")]
    if not arty:
        ours, _theirs = _front_pair(game, side)
        if ours is None:
            return None
        back = [n for n in st.neighbors(ours) if n.control == side and n.playable and not st.is_front(n, side)] or [ours]
        s = game.rng.choice(back)
        s.installations.append(["artillery", side, True])
        arty = [s]
    s = min(arty, key=lambda c: st._front_distance(c, side))
    for sd in SIDES:
        if sd != side:
            s.units[sd] = Counter()                      # nobody's shooting at the guns - yet
    s.units[side]["inf"] = max(1, s.units[side].get("inf", 0))
    return s


def choose_start(game, sid, side):
    """The sector the battle is fought in, and adjustments to the forces there. None: the default logic."""
    st = game.strategic
    rng = game.rng
    enemy = other_side(side)
    if sid in ("front", "pow") or sid.startswith(("air:", "sea:")):
        return None
    if sid == "gunline":
        return _gun_line(game, side)
    ours, theirs = _front_pair(game, side)
    if ours is None:
        return None
    if sid == "assault":
        s = theirs
        s.units[side].update(st._detach(ours.units[side], 0.7))
        s.units[side]["inf"] += rng.randint(4, 8)
        s.units[side]["eng"] += 2
        s.fort = min(3, s.fort + 1)
        return s
    if sid == "defence":
        s = ours
        s.units[enemy].update(st._detach(theirs.units[enemy], 0.6))
        s.units[enemy]["inf"] += rng.randint(6, 10)
        s.units[enemy]["mg"] += 2
        s.fort = min(3, s.fort + 1)
        s.contested = True
        return s
    if sid == "armour":
        s = theirs if rng.random() < 0.5 else ours
        for sd in SIDES:
            u = s.units[sd]
            arm = game.theatre["armor"].get(sd, 0.3)
            u["tank"] += int(rng.randint(5, 9) * (0.5 + arm))
            u["td"] += rng.randint(1, 3)
            u["ht"] += rng.randint(2, 4)
            u["inf"] += rng.randint(3, 5)
            u["atgun"] += rng.randint(0, 2) if sd != side else 0
        return s
    if sid == "patrol":
        s = theirs
        s.units[side] = Counter()
        return s
    if sid in ("raid", "agent", "evader"):
        depth = {"raid": rng.randint(1, 3), "agent": rng.randint(3, 6), "evader": rng.randint(2, 5)}[sid]
        s = _deep(game, side, depth)
        if s is None:
            return None
        s.units[side] = Counter()
        s.units[enemy] = Counter({"inf": rng.randint(2, 5), "hq": 1, "mg": 1})
        if sid == "raid" and not s.installs(enemy):
            s.installations.append([rng.choice(["depot", "artillery"]), enemy, True])
        if sid == "agent" and not s.installs(enemy, "hq"):
            s.installations.append(["hq", enemy, True])
        return s
    if sid == "partisans":
        s = _deep(game, side, rng.randint(2, 4))
        if s is None:
            return None
        s.units[side] = Counter()
        s.units[enemy] = Counter({"inf": rng.randint(1, 3)})
        return s
    if sid in ("encircled", "rearguard"):
        s = ours
        s.units[enemy].update(st._detach(theirs.units[enemy], 0.7))
        s.units[enemy]["inf"] += rng.randint(8, 12)
        if game.theatre["armor"].get(enemy, 0) > 0.25:
            s.units[enemy]["tank"] += rng.randint(2, 5)
        s.units[side]["inf"] = max(3, int(s.units[side].get("inf", 4) * 0.6))
        return s
    if sid == "sniper":
        return ours
    return None


# ====================================================================== after the player exists

def setup_player(game, sid, notes):
    """Shape the start: who's with you, where you are, what you carry, what you're for."""
    from .ai import Order
    from .spawn import edge_band_point, make_soldier, make_squad, place
    rng = game.rng
    p = game.player
    side = p.side
    enemy = other_side(side)
    m = game.map
    st = game.strategic
    home = game.home_edge(side) or _edge_toward_friends(game, side)
    game.mission = None
    if sid.startswith(("air:", "sea:")):
        return _launch_service(game, sid, notes)

    def strip_friends(keep):
        """Everyone of ours not in `keep` leaves the map - and stays off it (no reinforcements are coming:
        you're behind their lines)."""
        pv = p.vehicle
        if pv is not None:
            # out of whatever the start put him in (a landing craft far out to sea, say)
            if p in pv.passengers:
                pv.passengers.remove(p)
            if p in pv.crew_actors:
                pv.crew_actors.remove(p)
            p.vehicle = None
        for sq in list(game.squads):
            if sq.side != side or sq in keep:
                continue
            for a in list(sq.members):
                if a is not p:
                    game.remove_actor(a)
            for v in list(sq.vehicles):
                game.lift_vehicle(v)
                v.dead = True
                v.x = -99
            sq.members = []
            sq.vehicles = []
            sq.gone = True
        game.vehicles = [v for v in game.vehicles if not (v.dead and v.x == -99)]
        game.waves = [w for w in game.waves if w["side"] != side]
        game.sector.units[side] = Counter()

    def small_team(kind, n_extra, x, y, name):
        sq = p.squad
        for a in list(sq.members):
            if a is not p:
                sq.members.remove(a)
                game.remove_actor(a)
        extra = make_squad(game, side, p.nation, kind, x, y, name=name)
        for a in extra.members[:n_extra]:
            a.squad = sq
            a.unit = p.unit
            sq.members.append(a)
        for a in extra.members[n_extra:]:
            game.remove_actor(a)
        extra.members = []
        extra.gone = True
        sq.leader = p
        sq.player_led = True
        sq.order = Order("follow", issued=game.turn, src="player")
        strip_friends([sq])
        game.remove_actor(p)
        place(game, p, x, y, 3)
        for a in sq.members:
            if a is not p:
                game.remove_actor(a)
                place(game, a, p.x, p.y, 4)
        return sq

    if sid == "patrol":
        x, y = edge_band_point(game, home, rng, depth=(1, 3))
        small_team("recon", 4, x, y, "patrol")
        _set_night(game)
        need = rng.randint(3, 5)
        game.mission = dict(kind="patrol", need=need, base=len(game.brains[side].contacts), stage="observe",
                            text=f"Locate {need} enemy positions, then get back to our lines ({_edge_word(home)}).",
                            home=home)
        notes.append("Faces blackened, equipment taped so it won't rattle. The password is in your head.")
    elif sid == "raid":
        rec = _enemy_installation(game, enemy)
        x, y = edge_band_point(game, _far_edge(game, rec), rng, depth=(1, 3))
        small_team("commando", 5, x, y, "raiding party")
        for a in p.squad.members:
            a.add_item(_satchel(game, a.nation)) if a is not p else None
        p.add_item(_satchel(game, p.nation))
        _set_night(game)
        base = _explosive_count(m, rec)
        game.mission = dict(kind="raid", rec=rec, base=base, stage="destroy", home=home,
                            text=f"Destroy the enemy {rec['kind'] if rec else 'depot'} "
                                 f"({_where(game, rec)}), then get out.")
        notes.append("Charges primed, fuses in your breast pocket. No prisoners - they'd slow you down, and they'd "
                     "do the same to you.")
    elif sid == "agent":
        from .agents import setup as agent_setup
        agent_setup(game, notes, strip_friends)
    elif sid == "evader":
        strip_friends([])
        if p.squad is not None:
            p.squad.members = [p]
            p.squad.leader = p
            p.squad.player_led = True
        x, y = rng.randint(20, m.w - 20), rng.randint(15, m.h - 15)
        game.remove_actor(p)
        place(game, p, x, y, 8)
        from .combat import explode, ignite
        wx, wy = x + rng.randint(-8, 8), y + rng.randint(-6, 6)
        if m.in_bounds(wx, wy):
            ignite(game, wx, wy, 4)
        game.noise = 70.0                               # they saw you come down
        game.mission = dict(kind="evader", stage="evade", home=home,
                            text="Evade capture. Get back to friendly lines - across the front.")
        notes.append("Your parachute is tangled in a hedge. Bury it. They'll be looking for you already.")
    elif sid == "partisans":
        spots = [(xx, yy) for xx, yy in ((rng.randint(10, m.w - 10), rng.randint(10, m.h - 10)) for _ in range(80))
                 if m.walk[xx, yy] and m.conceal[xx, yy] >= 35]
        x, y = spots[0] if spots else (m.w // 2, m.h // 2)
        small_team("partisan", 6, x, y, "partisan detachment")
        from .agents import band_mission
        if not band_mission(game, notes):
            _set_night(game) if rng.random() < 0.5 else None
            game.mission = dict(kind="partisans", stage="wait", convoy_turn=game.turn + rng.randint(120, 300),
                                need=2, killed=0, home=home, text="Ambush the convoy on the road. Destroy two "
                                                                 "vehicles, then melt away into the woods.")
            notes.append("The road runs past the wood. Scouts say trucks come through most days.")
    elif sid in ("encircled", "rearguard"):
        for sq in game.squads:
            if sq.side == side:
                for a in sq.members:
                    if a is not p and rng.random() < 0.3:
                        a.body.damage(rng, rng.choice(("l_leg", "r_arm", "torso")), rng.uniform(8, 22), "fragment")
        e_edge = game.home_edge(enemy)
        for e in [x for x in ("N", "S", "E", "W") if x != home][:2]:
            game.schedule_wave(enemy, Counter({"inf": rng.randint(3, 5), "mg": 1}), e, delay=rng.randint(200, 600))
        if sid == "encircled":
            game.mission = dict(kind="breakout", stage="break", home=home,
                                text=f"Break out {_edge_word(home)} to our own lines. Bring the wounded if you can.")
            notes.append("The last radio message said the corridor is closing. Nobody is coming for you.")
        else:
            game.mission = dict(kind="rearguard", stage="hold", until=game.turn + rng.randint(1200, 2100), home=home,
                                text="Hold this ground until the withdrawal is complete. Then fall back.")
            notes.append("The column behind you is ten miles of trucks and horses. Every minute you hold is a "
                         "thousand men who get away.")
    elif sid == "sniper":
        sq = p.squad
        spot = make_soldier(game, p.nation, "rifleman")
        from .entities import Item
        spot.add_item(Item("binoculars"))
        spot.squad = sq
        spot.unit = p.unit
        sq.members.append(spot)
        place(game, spot, p.x, p.y, 2)
        game.mission = dict(kind="sniper", stage="hunt", need=rng.randint(3, 5), base=p.kills,
                            text="Kill their leaders: officers, NCOs, machine gunners. Don't be seen doing it.")
        notes.append("Your spotter has the binoculars and the patience. You have the rifle.")
    elif sid == "assault":
        game.mission = dict(kind="take", stage="take",
                            text="Take every objective on this field. The whole army is watching this attack.")
    elif sid == "defence":
        for i in range(3):
            game.schedule_wave(enemy, Counter({"inf": rng.randint(3, 6), "mg": 1,
                                               "tank": 1 if game.theatre["armor"].get(enemy, 0) > 0.3 else 0}),
                               game.home_edge(enemy), delay=600 + i * rng.randint(500, 900))
        game.mission = dict(kind="hold", stage="hold", until=game.turn + rng.randint(2400, 3600),
                            text="Hold every objective until relieved. They will come again and again.")
    elif sid == "armour":
        game.mission = dict(kind="take", stage="take", text="Destroy their armour and take the field.")
    if game.mission:
        game.mission["sid"] = sid
        game.mission["start"] = game.turn
        game.mission["_start_sector"] = game.sector


def _set_night(game):
    h = game.hour_float()
    if 5.0 <= h <= 21.0:
        game.advance_clock(int(((23.5 - h) % 24) * 3600))
        game.update_view_range()


def _edge_toward_friends(game, side):
    st = game.strategic
    s = game.sector
    for e, (dx, dy) in (("N", (0, -1)), ("S", (0, 1)), ("E", (1, 0)), ("W", (-1, 0))):
        n = st.at(s.x + dx, s.y + dy)
        if n is not None and n.control == side:
            return e
    return "S"


def _edge_word(e):
    return {"N": "north", "S": "south", "E": "east", "W": "west"}.get(e, "back")


def _enemy_installation(game, enemy, kind=None):
    recs = [r for r in (getattr(game.map, "gen_positions", None) or []) if r.get("side") == enemy and r.get("rect")
            and (kind is None or r.get("kind") == kind) and r.get("kind") in ("depot", "artillery", "hq", "aa",
                                                                              "motor_pool", "airfield")]
    return game.rng.choice(recs) if recs else None


def _far_edge(game, rec):
    m = game.map
    if rec is None:
        return "S"
    x, y = rec["x"], rec["y"]
    d = {"W": x, "E": m.w - x, "N": y, "S": m.h - y}
    return max(d, key=d.get)


def _where(game, rec):
    if rec is None:
        return "somewhere on this map"
    p = game.player
    from .senses import direction_word
    return f"to the {direction_word(rec['x'] - p.x, rec['y'] - p.y)}"


def _satchel(game, nation):
    from .data.items import ITEMS
    from .entities import Item
    for tid in ("satchel", "geballte"):
        if tid in ITEMS:
            return Item(tid)
    return Item("satchel")


def _explosive_count(m, rec):
    from . import tiles as T
    if rec is None:
        return 0
    x0, y0, sw, sh = rec["rect"]
    n = 0
    for x in range(max(0, x0), min(m.w, x0 + sw)):
        for y in range(max(0, y0), min(m.h, y0 + sh)):
            if T.EXPLODE.get(int(m.t[x, y])) if isinstance(T.EXPLODE, dict) else T.EXPLODE[int(m.t[x, y])]:
                n += 1
    return n


# ====================================================================== is the job done?

def update(game):
    """Every few seconds: progress on the mission."""
    ms = game.__dict__.get("mission")
    if not ms or ms.get("stage") in ("done", "failed"):
        return
    p = game.player
    if p is None or not p.alive:
        return
    rng = game.rng
    k = ms["kind"]
    side = p.side
    st = game.strategic
    home_side = game.sector.control == side and not ms.get("was_start_sector", False)

    def done(text, merit=6):
        ms["stage"] = "done"
        game.msg(text, "good")
        game.command.merit += merit
        game.duty.rep += merit
        if merit >= 6:
            game.command._award(game, 1 if merit < 10 else 2,
                                f"for the {ms.get('award_for') or SCENARIOS[ms['sid']]['name'].lower()}")
        game.update_orders(force=True)

    if "_start_sector" not in ms:
        ms["_start_sector"] = game.sector
    here = game.sector is ms["_start_sector"]          # objectives and targets are on the mission's own map
    friendly_ground = game.sector.control == side and not here
    if k == "patrol":
        seen = len(game.brains[side].contacts) - ms["base"]
        if ms["stage"] == "observe" and seen >= ms["need"]:
            ms["stage"] = "return"
            ms["text"] = f"You've seen enough. Get back to our lines ({_edge_word(ms['home'])}) and report."
            game.msg("You've seen what you came to see. Now get home alive.", "good")
            game.update_orders(force=True)
        elif ms["stage"] == "return" and friendly_ground:
            done("You make it back through the wire and report what you saw. The intelligence officer writes "
                 "everything down.", 8)
    elif k == "raid":
        if ms["stage"] == "destroy" and here:
            rec = ms.get("rec")
            left = _explosive_count(game.map, rec)
            guns = [v for v in game.vehicles if rec and not v.dead and v.side != side and v.vt.static
                    and rec["rect"][0] <= v.x < rec["rect"][0] + rec["rect"][2]
                    and rec["rect"][1] <= v.y < rec["rect"][1] + rec["rect"][3]]
            if (ms["base"] and left <= ms["base"] * 0.4) or (rec and rec.get("kind") == "artillery" and not guns):
                ms["stage"] = "exfil"
                ms["text"] = f"It's done. Get out - {_edge_word(ms['home'])}, back toward our lines."
                game.msg("Secondary explosions tear the night apart. The target is burning. Go!", "good")
                game.update_orders(force=True)
        elif ms["stage"] == "exfil" and (friendly_ground or game.sector is not ms["_start_sector"]):
            done("You slip away as the fires light the sky behind you. The raid is a success.", 10)
    elif k == "agent" and ms.get("task") not in (None, "steal_plans"):
        from .agents import update as agent_update
        agent_update(game, ms, done, friendly_ground, here)
    elif k == "agent":
        has = any(getattr(i, "iid", None) == ms["doc"] for i in p.inv)
        if ms["stage"] == "steal" and has:
            ms["stage"] = "home"
            ms["text"] = "You have the plans. Now get them to our side of the front - and to an intelligence officer."
            game.msg("The operation orders. Maps, timings, units. Men will live because of these - if you get "
                     "them home.", "good")
            game.update_orders(force=True)
        elif ms["stage"] == "home" and has and game.sector.control == side:
            done("You cross into your own lines and hand the plans to the first officer you find. Within the hour "
                 "they're on a staff car to Army headquarters.", 14)
            from .logistics import _enemy_plan
            plan = _enemy_plan(game, side)
            if plan:
                game.msg(f"Intelligence: the plans {plan}", "radio")
    elif k == "evader":
        if game.sector.control == side and game.sector is not ms["_start_sector"]:
            done("A sentry challenges you in your own language. You nearly weep. You're home.", 10)
    elif k == "partisans":
        if ms["stage"] == "wait" and game.turn >= ms["convoy_turn"]:
            _spawn_convoy(game, ms)
            ms["stage"] = "ambush"
            game.msg("Engines on the road - the convoy is coming.", "warn")
        elif ms["stage"] == "ambush":
            dead = sum(1 for v in game.vehicles if v.id in ms.get("convoy", []) and (v.dead or v.abandoned))
            if dead >= ms["need"]:
                ms["stage"] = "vanish"
                ms["until"] = game.turn + 240
                ms["text"] = "Enough. Melt away into the woods before their reaction force arrives."
                game.msg("Trucks burning on the road. Now go, before they come.", "good")
                game.update_orders(force=True)
        elif ms["stage"] == "vanish":
            enemy_near = any(a.side != side and a.active and max(abs(a.x - p.x), abs(a.y - p.y)) < 20
                             for a in game.actors)
            if game.turn >= ms["until"] and not enemy_near:
                done("By dawn you're ten miles away. Somewhere behind you, they're burning a village for it.", 8)
    elif k == "breakout":
        if game.sector.control == side and game.sector is not ms["_start_sector"]:
            done("You stagger into friendly lines with what's left. The breakout worked.", 10)
    elif k == "rearguard":
        if ms["stage"] == "hold" and game.turn >= ms["until"]:
            ms["stage"] = "withdraw"
            ms["text"] = f"The withdrawal is complete. Fall back {_edge_word(ms['home'])}!"
            game.msg("Radio: 'Withdrawal complete. Rearguard, pull out - pull out now!'", "radio")
            game.update_orders(force=True)
        elif ms["stage"] == "withdraw" and game.sector is not ms["_start_sector"]:
            done("You break contact and fall back. Thousands got away because you held.", 10)
    elif k == "sniper":
        if p.kills - ms["base"] >= ms["need"]:
            done("Word is the enemy won't show his head anywhere on this front. Your spotter carves another notch.",
                 8)
    elif k == "hold":
        objs = game.map.objectives
        if here and game.turn >= ms["until"] and objs and all(o.owner == side for o in objs):
            done("Relief arrives. You held.", 10)
    elif k == "take":
        objs = game.map.objectives
        if here and objs and all(o.owner == side for o in objs):
            done("The field is ours.", 8)


def _spawn_convoy(game, ms):
    """Trucks and an escort, down the road from one edge toward the other."""
    from .ai import Order
    from .spawn import make_vehicle_squad, pick_nation
    rng = game.rng
    m = game.map
    enemy = other_side(game.player.side)
    nat = pick_nation(game, enemy)
    roads = getattr(m, "roads", None) or []
    ends = None
    if hasattr(game.map, "gen_roads"):
        ends = game.map.gen_roads
    e0, e1 = rng.choice([("W", "E"), ("E", "W"), ("N", "S"), ("S", "N")])
    from .spawn import edge_band_point
    ids = []
    for cls in ("truck", "truck", "ht" if game.theatre["armor"].get(enemy, 0) > 0.2 else "truck"):
        x, y = edge_band_point(game, e0, rng, depth=(1, 2))
        sq = make_vehicle_squad(game, enemy, nat, cls, x, y, 1, edge=e0)
        if sq is None:
            continue
        tx, ty = edge_band_point(game, e1, rng, depth=(0, 1))
        sq.order = Order("move", target=(tx, ty), issued=game.turn)
        sq.no_count = True
        ids += [v.id for v in sq.vehicles]
    ms["convoy"] = ids


def mission_line(game) -> str | None:
    ms = game.__dict__.get("mission")
    if not ms:
        return None
    if ms.get("stage") == "done":
        return None
    return ms.get("text")


# ====================================================================== the air force and the navy

STATION = {"fighter_pilot": "pilot", "bomber_pilot": "pilot", "pilot": "pilot", "bombardier": "bombardier",
           "air_gunner": "tail gunner", "sailor": "aa gun", "petty_officer": "main battery", "deck_officer": "bridge",
           "ship_captain": "bridge", "sub_commander": "bridge", "admiral": "bridge"}
AIR_FOR_ROLE = {"fighter_pilot": ["sweep", "intercept", "escort", "recon", "attack"],
                "bomber_pilot": ["strategic", "dive", "torpedo", "attack"], "bombardier": ["strategic"],
                "air_gunner": ["strategic", "dive", "torpedo"]}
SEA_FOR_ROLE = {"sub_commander": ["sub"], "admiral": ["carrier", "surface"], "ship_captain": ["surface", "convoy",
                                                                                              "bombard", "carrier"],
                "sailor": ["surface", "convoy", "carrier", "bombard"], "petty_officer": ["surface", "convoy", "bombard"],
                "deck_officer": ["surface", "convoy", "bombard", "carrier"]}


def pick_service_mission(game, service, role):
    from .skysea_missions import eligible_air, eligible_sea
    rng = game.rng
    if service == "air":
        kinds = [k for k in AIR_FOR_ROLE.get(role, ["sweep", "intercept", "escort", "strategic"]) if eligible_air(game, k)]
        return ("air:" + rng.choice(kinds)) if kinds else None
    kinds = [k for k in SEA_FOR_ROLE.get(role, ["surface", "convoy"]) if eligible_sea(game, k)]
    return ("sea:" + rng.choice(kinds)) if kinds else None


def _launch_service(game, sid, notes):
    from .skysea_missions import AIR_MISSIONS, SEA_MISSIONS, eligible_air, eligible_sea, launch_air, put_to_sea
    p = game.player
    kind = sid[4:]
    station = STATION.get(p.role, "pilot" if sid.startswith("air:") else "bridge")
    if sid.startswith("air:"):
        if not eligible_air(game, kind):
            alt = pick_service_mission(game, "air", p.role)
            if alt is None:
                notes.append("There are no aircraft here for you. You wait on the ground.")
                return
            kind = alt[4:]
        from .data.special import SPECIAL
        at_id = SPECIAL.get(p.__dict__.get("unit_type"), {}).get("aircraft")
        from .data.vehicles import AIRCRAFT
        if at_id not in AIRCRAFT:
            at_id = None
        ss = launch_air(game, kind, at_id=at_id, station=station)
        if p.__dict__.get("unit_type") == "night_witches" and not game.is_night():
            h = game.hour_float()
            game.advance_clock(int(((23.0 - h) % 24) * 3600))
        if ss is None:
            notes.append("There is nothing here for you to fly.")
            return
        if station not in [c["station"] for c in ss.player_plane.crew]:
            ss.station = next((c["station"] for c in ss.player_plane.crew if c.get("turret")), "pilot")
        notes.append(f"You're airborne in a {ss.player_plane.name} ({ss.station}). {AIR_MISSIONS[kind]}")
        # a crew of several: you're one of them, in the fuselage (aboard.py); a fighter pilot flies alone
        from . import aboard as AB
        if AB.multi_crew(ss.player_plane):
            AB.board_plane(game, ss.player_plane)
    else:
        if not eligible_sea(game, kind):
            alt = pick_service_mission(game, "navy", p.role)
            if alt is None:
                notes.append("No ship of your navy is anywhere near. You wait on the beach.")
                return
            kind = alt[4:]
        sid_ship = None
        from .data.ships import available
        want = {"sub_commander": ("ss",), "admiral": ("cv", "bb", "ca")}.get(p.role)
        if want:
            opts = available(p.nation, game.year, want)
            if opts:
                sid_ship = game.rng.choice(opts)["id"]
        ss = put_to_sea(game, kind, sid=sid_ship, station=station)
        if ss is None:
            notes.append("There's no sea here to put to.")
            return
        ss.player_ship.ai["auto_fire"] = True
        notes.append(f"You're aboard {ss.player_ship.name} ({ss.player_ship.st['name']}). {SEA_MISSIONS[kind]}")
        # you're a man on her deck, not the ship itself: go aboard (aboard.py)
        from . import aboard as AB
        AB.board_ship(game, ss.player_ship)
        ss.station = "deck"
    game.mission = None
