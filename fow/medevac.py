"""Medical evacuation: a call on the radio, stretcher-bearers, the aid post, the hospital - and back.

Badly hit, out of the enemy's sight and fire, with a radio (your own, your tank's, or the radioman
beside you), you can ask for a litter team.  They're real men: four stretcher-bearers from the
battalion aid post - from the aid post on this ground if there is one, otherwise up from the rear -
who walk to you, get you onto the stretcher and carry you back, with all the risks of a walk across
a battlefield.  From the aid post it's the chain every army had (aid post, clearing station, field
hospital, general hospital) and weeks of mending, in which the war goes on without you.  Then you
report back for duty, whole - or, if you've lost a limb, you're sent home.
"""
from __future__ import annotations

import math

from .constants import other_side

TEAM = 4                      # bearers on a litter team (a stretcher over broken ground takes four)

CHAIN = {
    "usa": ["the battalion aid station", "the collecting company's ambulance", "a clearing station",
            "an evacuation hospital", "a general hospital"],
    "uk": ["the regimental aid post", "an advanced dressing station", "a casualty clearing station",
           "a general hospital"],
    "germany": ["the Truppenverbandplatz", "the Hauptverbandplatz", "a Feldlazarett", "a Kriegslazarett"],
    "ussr": ["the battalion medical post", "the divisional medical battalion", "a front-line field hospital",
             "an evacuation hospital in the rear"],
    "japan": ["the battalion dressing station", "the divisional field hospital", "a line-of-communication hospital"],
    "italy": ["the posto di medicazione", "an ospedale da campo", "a military hospital"],
}
RETURN = {"usa": "the replacement depot - the 'repple-depple' - and a truck back to the front",
          "uk": "a reinforcement holding unit, and a lorry forward",
          "germany": "the Genesenen-Kompanie, and a train back east" ,
          "ussr": "a reserve regiment, and a march to the front",
          "japan": "a replacement unit, and a ship back to the front"}


def _state(game):
    return game.__dict__.get("medevac")


def _hurt(p) -> bool:
    from . import medical as MED
    b = p.body
    return p.downed or MED.should_evacuate(b) or MED.needs_surgery(b) or \
        MED.missing_hp(b) > sum(b.max.values()) * 0.2


def _radio_near(game, p) -> bool:
    from .command import has_radio, vehicle_has_radio
    if has_radio(p):
        return True
    if p.vehicle is not None and vehicle_has_radio(game, p.vehicle):
        return True
    return any(a is not p and a.side == p.side and a.active and not a.downed and has_radio(a) and
               max(abs(a.x - p.x), abs(a.y - p.y)) <= 3 for a in game.actors)


def _safe(game, p) -> tuple[bool, str]:
    """Out of the enemy's sight and fire: nobody's carrying a stretcher into a fire-fight."""
    vis = [e for e in game.seen_enemies(40) if math.hypot(e.x - p.x, e.y - p.y) < 40]
    if vis:
        return False, "the enemy can see you"
    if p.suppression > 15 or game.turn - p.ai.get("hit_turn", -999) < 30:
        return False, "you're under fire"
    brain = game.brains[p.side]
    if brain.safety is not None and game.map.in_bounds(p.x, p.y) and int(brain.safety[p.x, p.y]) > 0:
        return False, "you're in the open where the enemy's guns reach"
    return True, ""


def can_call(game) -> tuple[bool, str]:
    p = game.player
    if game.__dict__.get("domain", "land") != "land" or game.map is None:
        return False, "(at sea, it's the ship's sickbay)"
    if _state(game) is not None:
        return False, "they're already coming"
    if not _hurt(p):
        return False, "you're not hurt badly enough to be taken out of the line"
    if not _radio_near(game, p):
        return False, "no radio: your own, your tank's, or a radioman beside you"
    ok, why = _safe(game, p)
    if not ok:
        return False, why
    return True, ""


def _source(game, side):
    """Where the bearers start: the aid post on this ground, or the rear edge they come up from."""
    for rec in getattr(game.map, "gen_positions", None) or []:
        if rec.get("kind") == "aid" and rec.get("side") == side:
            return (rec["x"], rec["y"]), "the aid post"
    e = game.home_edge(side)
    if e is None:
        return None, None
    from .spawn import edge_band_point
    return edge_band_point(game, e, game.rng, depth=(1, 3)), "the rear"


def call(ps):
    """The radio call: a litter team sets out."""
    from .ai import Order
    from .spawn import make_soldier, place
    from .ai import Squad
    g = ps.game
    p = g.player
    ok, why = can_call(g)
    if not ok:
        g.msg(f"Radio: 'Negative on stretcher-bearers - {why}.'" if why.startswith(("the ", "you're"))
              else f"You can't call for evacuation: {why}.", "radio")
        return
    src, where = _source(g, p.side)
    if src is None:
        g.msg("Radio: 'Negative - there's no way to get to you from here.'", "radio")
        return
    nat = g.side_nation(p.side)
    sq = Squad(p.side, nat, "litter", "litter team")
    sq.no_count = True
    sq.order = Order("hold", target=src, issued=g.turn)
    ids = []
    for _ in range(TEAM):
        a = make_soldier(g, nat, "medic")
        a.squad = sq
        sq.members.append(a)
        place(g, a, src[0] + g.rng.randint(-2, 2), src[1] + g.rng.randint(-2, 2), 6)
        a.ai["litter"] = True
        ids.append(a.id)
    sq.leader = sq.members[0]
    g.squads.append(sq)
    d = math.hypot(src[0] - p.x, src[1] - p.y) * 2.2
    from .senses import direction_word
    g.__dict__["medevac"] = dict(stage="coming", bearers=ids, called=g.turn, src=src, where=where, squad=sq.id)
    g.msg(f"You: 'Man down, need a litter team at my position, over.' Radio: 'Stretcher-bearers on the way from "
          f"{where} - {direction_word(src[0] - p.x, src[1] - p.y)}, about {int(round(d / 50.0) * 50) or 50} yards. "
          f"Stay where you are and keep your head down.'", "radio")
    g.update_orders(force=True)
    ps.act(300)


def order_line(game):
    st = _state(game)
    if st is None:
        return None
    if st["stage"] == "coming":
        return f"MEDEVAC: stretcher-bearers coming from {st['where']}. Stay where you are."
    return "MEDEVAC: you're on a stretcher, being carried back. Hang on."


def _bearers(game, st):
    return [a for a in game.actors if a.id in st["bearers"] and a.active and not a.downed]


def update(game):
    """Every couple of seconds: the team's still coming, or has you, or has been shot to pieces."""
    st = _state(game)
    if st is None:
        return
    p = game.player
    bs = _bearers(game, st)
    if not bs and st["stage"] != "arrived":
        if st["stage"] == "carrying" and p.ai.get("carried_by") is not None:
            from . import actions as A
            carrier = next((a for a in game.actors if a.id == p.ai.get("carried_by")), None)
            if carrier is not None:
                A.put_down(game, carrier)
        game.__dict__["medevac"] = None
        game.msg("Radio: 'The litter team's been hit. We'll try again when we can.'", "warn")
        game.update_orders(force=True)
        return
    if not p.alive:
        game.__dict__["medevac"] = None
        return


def bearer_act(game, a) -> int | None:
    """A stretcher-bearer's turn: to you, onto the stretcher, back to the aid post or the rear."""
    from . import actions as A
    from .ai import path_step
    st = _state(game)
    p = game.player
    if st is None or p is None or not p.alive:
        # the job's done (or can't be): back where they came from
        e = game.home_edge(a.side)
        if e is not None and game._edge_gap(e, a.x, a.y) <= 2:
            game.exit_map(a, "withdrew")
            return 100
        brain = game.brains[a.side]
        if brain.home is not None:
            from .ai import best_step, do_step
            return do_step(game, a, best_step(game, a, [(brain.home, 1.0)], crowd=False)) or 100
        return 100
    if st["stage"] == "coming":
        if max(abs(a.x - p.x), abs(a.y - p.y)) <= 1:
            if p.vehicle is not None:
                A.exit_vehicle(game, p)
            c = A.pick_up(game, a, p)
            if c:
                st["stage"] = "carrying"
                st["carrier"] = a.id
                game.msg(f"{a.rank_short} {a.last_name} and the others get you onto the stretcher. 'Easy now. "
                         f"You're going home, pal - for a while.'" if a.nation in ("usa", "uk", "canada", "australia",
                                                                                    "newzealand") else
                         "The stretcher-bearers lift you onto the stretcher. Every jolt is agony.", "info")
                game.update_orders(force=True)
                return c
            return 100
        return path_step(game, a, p.x, p.y, margin=30) or 100
    if st["stage"] == "arrived":
        return 100                                   # handing you over (medevac.hospital, between turns)
    # carrying: the man with you on his shoulder leads; the others walk beside.  If he's hit, he drops you,
    # and the nearest of the others takes the stretcher up again
    carrier = next((o for o in game.actors if o.id == st.get("carrier")), None)
    if carrier is not None and carrier.carrying is p and (carrier.downed or not carrier.active):
        A.put_down(game, carrier)
    if p.ai.get("carried_by") is None and a.carrying is None:
        if max(abs(a.x - p.x), abs(a.y - p.y)) <= 1:
            c = A.pick_up(game, a, p)
            if c:
                if carrier is not a and (carrier is None or not carrier.active or carrier.downed):
                    game.msg(f"{a.rank_short} {a.last_name} takes the stretcher up again.", "info")
                st["carrier"] = a.id
                return c
        return path_step(game, a, p.x, p.y) or 100
    if a.carrying is p:
        dest = st["src"]
        if st["where"] == "the rear":
            e = game.home_edge(a.side)
            if e is not None and game._edge_gap(e, a.x, a.y) <= 2:
                st["stage"] = "arrived"
                return 100
        elif max(abs(a.x - dest[0]), abs(a.y - dest[1])) <= 3:
            st["stage"] = "arrived"
            return 100
        brain = game.brains[a.side]
        if st["where"] == "the rear" and brain.home is not None:
            from .ai import best_step, do_step
            c = do_step(game, a, best_step(game, a, [(brain.home, 1.0)], exposure_w=2.0, crowd=False))
            if c:
                return c
        return path_step(game, a, dest[0], dest[1], margin=30) or 100
    carrier = next((o for o in game.actors if o.id == p.ai.get("carried_by")), None)
    if carrier is None:
        return path_step(game, a, p.x, p.y) or 100
    if max(abs(a.x - carrier.x), abs(a.y - carrier.y)) > 2:
        return path_step(game, a, carrier.x, carrier.y) or 100
    return 100


def _days(game, p) -> int:
    from . import medical as MED
    b = p.body
    rng = game.rng
    frac = MED.missing_hp(b) / max(1, sum(b.max.values()))
    if any(b.hp[k] <= 0 for k in b.hp):
        return rng.randint(45, 90)                  # a ruined limb saved, and learning to use it again
    if MED.needs_surgery(b):
        return rng.randint(21, 42)
    return max(7, int(10 + frac * 60 + rng.randint(0, 7)))


def hospital(game) -> int | None:
    """Off the map and down the evacuation chain; weeks in a ward; back to the war."""
    from . import actions as A
    p = game.player
    st = _state(game)
    carrier = next((o for o in game.actors if o.id == p.ai.get("carried_by")), None)
    if carrier is not None:
        A.put_down(game, carrier)
    for a in _bearers(game, st):
        game.exit_map(a, "withdrew")
    game.__dict__["medevac"] = None
    from .base import excused
    excused(game, "hospital")
    nat = p.nation
    chain = CHAIN.get(nat) or CHAIN.get(game.side_nation(p.side)) or CHAIN["usa"]
    amputated = set(p.ai.get("amputated", []))
    days = _days(game, p)
    game.msg(f"Down the line: {', then '.join(chain)}. Morphine, a surgeon, clean sheets.", "info")
    # the ground you were carried off stays as it was; the war goes on for the weeks you're away
    if game.map is not None and game.sector is not None:
        game._save_map()
        game.sector.units = game.local_units()
    game.remove_actor(p) if p in game.actors else None
    _pass_days(game, days)
    game.stats["days_in_hospital"] += days
    if amputated & {"l_leg", "r_leg", "l_arm", "r_arm"}:
        return _sent_home(game, days)
    _heal(p)
    _back_to_duty(game, days)
    return None


def _pass_days(game, days):
    """A coarse day at a time of the war going on (the camp does the same, behind its wire)."""
    st = game.strategic
    for _ in range(days):
        game.advance_clock(86400)
        game.turn += 86400
        for _ in range(4):
            st.tick(None)
        try:
            game.support.fires.strategic_tick(game) if game.support is not None and game.sector is not None else None
        except Exception:
            pass
    st.news = st.news[-6:]


def _heal(p):
    b = p.body
    for k in b.hp:
        b.hp[k] = b.max[k]
    b.wounds = []
    from .body import BLOOD_MAX
    b.blood = BLOOD_MAX
    for attr, v in (("pain", 0.0), ("shock", 0.0), ("unconscious", 0), ("temp", 37.0), ("wet", 0.0)):
        if hasattr(b, attr):
            setattr(b, attr, v)
    p.fatigue = 0.0
    p.stamina = 100.0
    p.morale = max(p.morale, 75.0)
    p.suppression = 0.0
    p.state = "ok"
    for k in [k for k in p.ai if k.startswith("_heal_") or k in ("recovering", "at_aid", "to_aid", "surgery",
                                                                  "carried_by", "hit_turn")]:
        p.ai.pop(k, None)


def _back_to_duty(game, days):
    """Discharged fit: through the replacement system and back to a unit at the front."""
    st = game.strategic
    p = game.player
    side = p.side
    cands = [s for s in st.sectors() if s.control == side and s.playable and st.is_front(s, side)] or \
            [s for s in st.sectors() if s.control == side and s.playable]
    if not cands:
        return
    sector = min(cands, key=lambda s: abs(s.x - game.sector.x) + abs(s.y - game.sector.y))
    via = RETURN.get(p.nation, "a replacement depot, and a truck back to the front")
    game.enter_sector(sector, entry_edge=None)
    from .spawn import edge_band_point, place
    edge = game.home_edge(side)
    x, y = edge_band_point(game, edge, game.rng, depth=(4, 12)) if edge else (game.map.w // 2, game.map.h // 2)
    place(game, p, x, y, 8)
    game.add_actor(p) if p not in game.actors else None
    p.squad = None
    # a replacement goes where he's put: the nearest squad of his kind that's short of men
    kind = {"lmg_gunner": "rifle", "lmg_assistant": "rifle", "rifleman": "rifle", "smg_gunner": "rifle",
            "medic": "rifle", "mortarman": "mortar", "hmg_gunner": "mg", "hmg_assistant": "mg",
            "at_soldier": "at", "engineer": "engineer", "radioman": "hq", "officer": "hq", "sniper": "sniper"}.get(
        p.role, "rifle")
    sqs = [q for q in game.squads if q.side == side and q.members and not q.player_led and q.kind == kind] or \
          [q for q in game.squads if q.side == side and q.members and not q.player_led and q.kind == "rifle"]
    if sqs:
        sq = min(sqs, key=lambda q: (len(q.members) >= getattr(q, "initial", 10),
                                     abs((q.anchor() or (x, y))[0] - x) + abs((q.anchor() or (x, y))[1] - y)))
        sq.members.append(p)
        p.squad = sq
        p.unit = sq.members[0].unit if sq.members and getattr(sq.members[0], "unit", None) else p.unit
    game.command.organise(game)
    from .base import back_in_service
    from .data.roles import service_of
    if service_of(p.role) != "army":
        if p.squad is not None and p in p.squad.members:
            p.squad.members.remove(p)
        p.squad = None
        game.command.organise(game)
        game.msg(f"{days} days later you're discharged, fit for duty: {via}.", "good")
        back_in_service(game, "hospital")
    else:
        game.msg(f"{days} days later you're discharged, fit for duty: {via}. You report to {sector.name}"
                 + (f" and join {p.squad.name}" if p.squad is not None else "") + ". The faces are new; the war isn't.",
                 "good")
    game.update_orders(force=True)
    game.player_fov()


def _sent_home(game, days):
    """A lost limb: the war is over for you."""
    p = game.player
    game.victory_text = (f"After {days} days in hospital you are invalided out of the army - "
                         f"{'a leg' if set(p.ai.get('amputated', [])) & {'l_leg', 'r_leg'} else 'an arm'} gone. "
                         f"You go home. The war goes on without you.")
    game.game_over = True
    game.death_text = game.victory_text
    return None
