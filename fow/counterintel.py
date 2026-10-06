"""Security troops work from sightings, intercepts and papers, not an agent's exact position."""
from __future__ import annotations

import math

from .constants import other_side


def state(game, side=None):
    side = side or game.sector.control or other_side(game.player.side)
    return game.sector.__dict__.setdefault("security", {}).setdefault(side,
        dict(heat=0., reports=[], searches=0, last_search=-3600, last_decay=game.turn,
             wanted=False, patrols=[], initialized=False, infiltration_at=game.turn + 3600))


def report(game, side, pos, strength, source):
    st = state(game, side)
    st["heat"] = min(100, st["heat"] + strength)
    # Even a radio bearing or a witness points to an area, not a man behind a particular wall.
    err = 18 if source == "wireless bearing" else 5
    xy = (max(1, min(game.map.w - 2, int(pos[0] + game.rng.uniform(-err, err)))),
          max(1, min(game.map.h - 2, int(pos[1] + game.rng.uniform(-err, err)))))
    st["reports"].append(dict(at=game.turn, pos=xy, source=source))
    st["reports"] = st["reports"][-12:]
    if side == game.player.side and game.player.has_tool("ci_log"):
        game.msg(f"Security report: {source}. Check the intercept log.", "radio")


def pressure(game):
    st = state(game, other_side(game.player.side))
    return st["heat"] / 100 + (.35 if st["wanted"] else 0)


def checkpoint(game, side, pos):
    from .spawn import make_soldier, place
    from .ai import Squad, Order
    from .entities import Item
    nat = game.side_nation(side)
    sq = Squad(side, nat, "rear", "counterintelligence checkpoint")
    sq.no_count = True
    sq.order = Order("hold", target=pos, radius=5)
    sq.arrived = True
    for role in ("mp", "mp", "intel"):
        a = make_soldier(game, nat, role)
        a.ai.update(security=True, post=pos)
        # Specialist training still varies; a sentry is not an infallible lie detector.
        if role == "intel":
            a.skills["observation"] = max(a.skills["observation"], game.rng.uniform(6.5, 9.))
            a.skills["languages"] = max(a.skills["languages"], game.rng.uniform(6., 8.5))
        a.squad = sq
        if role == "intel":
            a.add_item(Item("frequency_log"))
        if place(game, a, *pos, radius=4):
            sq.members.append(a)
    if sq.members:
        sq.leader = sq.members[0]
        sq.initial = len(sq.members)
        game.squads.append(sq)
        state(game, side)["patrols"].append(sq.id)
    return sq


def investigate(game, side):
    from .ai import Order
    st = state(game, side)
    reports = [r for r in st["reports"] if game.turn - r["at"] <= 3600]
    if not reports:
        return False
    pos = reports[-1]["pos"]
    patrols = [sq for sq in game.squads if sq.id in st["patrols"] and any(a.active for a in sq.members)]
    if not patrols and len(st["patrols"]) < 3:
        from .spawn import edge_band_point
        edge = game.home_edge(side) or "N"
        patrols = [checkpoint(game, side, edge_band_point(game, edge, game.rng))]
        patrols = [sq for sq in patrols if sq.members]
    if not patrols:
        return False
    sq = min(patrols, key=lambda sq: math.hypot(sq.leader.x - pos[0], sq.leader.y - pos[1]))
    sq.order = Order("move", target=pos, radius=12, issued=game.turn)
    sq.arrived = False
    st["last_search"] = game.turn
    st["searches"] += 1
    if side == game.player.side:
        game.msg("The security patrol sets off to search the reported area.", "radio")
    return True


def tick(game):
    if game.__dict__.get("domain", "land") != "land" or game.sector.control is None:
        return
    side = game.sector.control
    st = state(game, side)
    if not st["initialized"]:
        st["initialized"] = True
        hf = game.sector.__dict__.get("homefront", {})
        garrison = any(a.side == side and a.active and not a.ai.get("civilian") for a in game.actors)
        if garrison and (hf.get("depth", 0) >= 3 or game.player.ai.get("disguise")):
            recs = [r for r in getattr(game.map, "gen_positions", []) if r.get("side") == side]
            if recs:
                rec = recs[0]
                checkpoint(game, side, (rec["x"], rec["y"]))
    elapsed = max(0, game.turn - st["last_decay"])
    st["heat"] = max(0, st["heat"] - elapsed / 600)
    st["last_decay"] = game.turn
    p = game.player
    # A local informant must actually see a conspicuous act. Quiet civilians aren't omniscient.
    if p.side != side and game.player.ai.get("disguise"):
        from .agents import transmitting
        from .senses import los_clear
        conspicuous = transmitting(game) or p.fired_turn >= game.turn - 30 or p.stance == 2
        witnesses = [a for a in game.near(p.x, p.y, 12) if a.ai.get("civilian") and a.active and
                     not a.ai.get("covert") and los_clear(game, a.x, a.y, p.x, p.y)]
        goodwill = game.sector.__dict__.get("homefront", {}).get("goodwill", 0)
        if conspicuous and witnesses and game.rng.random() < max(.02, .3 - goodwill / 200):
            report(game, side, p.pos, 12, "a resident's sighting")
    if st["heat"] >= 25 and game.turn - st["last_search"] >= 600:
        investigate(game, side)
    for sq in game.squads:
        if sq.id not in st["patrols"]:
            continue
        if sq.arrived and st["heat"] >= 25 and st["reports"] and \
                game.turn - st["reports"][-1]["at"] <= 3600 and \
                game.turn >= sq.__dict__.get("security_sweep_at", 0):
            from .ai import Order
            x, y = st["reports"][-1]["pos"]
            pos = (max(1, min(game.map.w - 2, x + game.rng.randint(-10, 10))),
                   max(1, min(game.map.h - 2, y + game.rng.randint(-10, 10))))
            sq.order = Order("move", target=pos, radius=2, issued=game.turn)
            sq.arrived = False
            sq.security_sweep_at = game.turn + 120
        for guard in sq.members:
            if not guard.active:
                continue
            # Friendly security can uncover the enemy's infiltrators too.
            for a in game.near(guard.x, guard.y, 3):
                from .senses import los_clear
                if a.ai.get("covert") and a.side != side and a.ai.get("checked", -9999) < game.turn - 600 and \
                        los_clear(game, guard.x, guard.y, a.x, a.y):
                    examine(game, guard, a)
    if game.turn >= st["infiltration_at"]:
        st["infiltration_at"] = game.turn + game.rng.randint(3600, 10800)
        infiltrate(game, side)
    for a in list(game.actors):
        if a.ai.get("covert") and a.active:
            target = a.ai.get("sabotage_target")
            if target and math.hypot(a.x - target[0], a.y - target[1]) < 6 and \
                    game.turn >= a.ai["sabotage_at"]:
                game.strategic.interdict(side, game.sector, .3, "Sabotage has cut a rear supply route.")
                from .combat import damage_tile
                damage_tile(game, *target, 180)
                report(game, side, a.pos, 35, "sabotage at the stores")
                a.ai["sabotage_at"] = game.turn + 3600


def infiltrate(game, side):
    from .entities import Actor, Item
    from .spawn import edge_band_point, place
    from .data.nations import random_name
    if any(a.ai.get("covert") and a.alive for a in game.actors):
        return
    recs = [r for r in getattr(game.map, "gen_positions", []) if r.get("side") == side and
            r.get("kind") in ("depot", "factory", "rail_yard", "airfield", "hq") and not r.get("destroyed")]
    if not recs or game.strategic.is_front(game.sector, side):
        return
    r = game.rng.choice(recs)
    target = (r.get("targets") or [(r["x"], r["y"])])[0]
    enemy = other_side(side)
    nat = game.side_nation(enemy)
    a = Actor(nat, "civilian", 0, random_name(game.rng, game.side_nation(side)))
    a.side = enemy
    a.ai.update(civilian=True, covert=True, home=target, sabotage_target=target, sabotage_at=game.turn + 900,
                occupation="traveller", cover_quality=game.rng.uniform(.2, .75))
    a.invent.slots["body"] = Item("civvies")
    a.add_item(Item("forged_papers"))
    a.add_item(Item("time_pencil"))
    xy = edge_band_point(game, game.home_edge(side) or "N", game.rng)
    if place(game, a, *xy):
        game.sector.__dict__.setdefault("civilians", []).append(a)
        # First lead is a coarse intercept; security still has to find and identify its owner.
        report(game, side, xy, 15, "unidentified wireless traffic")


def examine(game, examiner, person):
    person.ai["checked"] = game.turn
    if not person.ai.get("covert"):
        if examiner.is_player:
            game.msg("The name, permit and local details agree. You have no evidence against this person.", "info")
        return False
    from .identity import acuity
    chance = .2 + acuity(examiner) * .075
    if game.rng.random() > max(.15, min(.95, chance - person.ai.get("cover_quality", .5) * .25)):
        if examiner.is_player:
            game.msg("The papers appear to be in order.", "info")
        return False
    person.ai.pop("civilian", None)
    person.ai.pop("covert", None)
    person.role = "agent"
    person.state = "surrendered"
    person.ai["captor"] = examiner.id
    game._arr_turn = -1
    game._enemy_arr = {}
    if examiner.side == game.player.side:
        game.msg("The permit contradicts the cover story. A search turns up sabotage stores: an agent is detained.", "good")
        game.command.merit += .5
    return True


def open_log(ps):
    from .render import Popup
    from .constants import UI_TEXT
    g = ps.game
    st = state(g, g.player.side)
    lines = [(f"District alert: {'routine' if st['heat'] < 25 else 'searches in progress' if st['heat'] < 60 else 'high alert'}.",
              UI_TEXT)]
    lines += [(f"{r['source'].capitalize()}: near {r['pos'][0]}, {r['pos'][1]} (area only).", UI_TEXT)
              for r in st["reports"][-5:]]
    opts = [("Dispatch a patrol to the latest report", "patrol", None, bool(st["reports"]))]
    opts += [("Check " + a.name + "'s papers", a, None, True) for a in g.near(g.player.x, g.player.y, 2)
             if a.ai.get("civilian") and a.alive]

    def choose(v):
        if v == "patrol":
            if not investigate(g, g.player.side):
                g.msg("No fresh lead or available patrol.", "info")
        elif v:
            return interview(ps, v)
        ps.act(300)
    ps.open_popup(Popup("Counterintelligence reports", opts, ps._screen_anchor(), lines=lines, width=65), choose)


def interview(ps, person):
    """A player investigation records answers and evidence before an arrest."""
    from .render import Popup
    from .constants import UI_TEXT, UI_DIM
    from .skills import level
    from .senses import los_clear
    import textwrap
    g, p = ps.game, ps.game.player
    if not person.active or max(abs(person.x - p.x), abs(person.y - p.y)) > 2 or \
            not los_clear(g, p.x, p.y, person.x, person.y):
        g.msg("That person is no longer close enough to question.", "info")
        return
    st = person.ai.setdefault("interview", dict(asked={}, evidence=[], transcript=[]))
    quality = person.ai.get("cover_quality", .9)
    trained = .6 * level(p, "observation") + .4 * level(p, "languages")
    lines = [(line, UI_TEXT) for text in st["transcript"][-3:] for line in textwrap.wrap(text, 62)]
    lines += [(line, UI_DIM) for text in st["evidence"] for line in textwrap.wrap("Evidence: " + text, 62)]
    opts = [("Ask about their occupation", "trade", None, True), ("Ask where they came from", "route", None, True),
            ("Repeat the question about their route", "repeat", None, "route" in st["asked"]),
            ("Compare the permit with their answers", "papers", None, bool(st["asked"])),
            ("Search their bag", "search", None, p.role in ("mp", "intel") or bool(st["evidence"])),
            ("Detain on the evidence", "detain", None, len(st["evidence"]) >= 2),
            ("Let them go", "leave", None, True)]

    def choose(v):
        if not person.active or max(abs(person.x - p.x), abs(person.y - p.y)) > 2 or \
                not los_clear(g, p.x, p.y, person.x, person.y):
            return
        if v == "leave":
            return
        suspect = person.ai.get("covert")
        discovered = None
        if v == "trade":
            st["asked"]["trade"] = person.ai.get("occupation", "traveller")
            st["transcript"].append("'I'm a " + st["asked"]["trade"] + ". Looking for work.'")
        elif v in ("route", "repeat"):
            first = st["asked"].setdefault("route", "the farms outside town")
            changed = v == "repeat" and suspect and quality < .6
            st["transcript"].append("'From " + ("the railway district" if changed else first) + ".'")
            if changed and trained >= 3:
                discovered = "Their route changed when asked again."
        elif v == "papers":
            if suspect and trained >= 2 + quality * 6:
                discovered = "The issuing district does not match the claimed journey."
            st["transcript"].append(discovered or "The permit agrees with the answers you can verify.")
        elif v == "search":
            # A physical search finds physical objects, rather than consulting the covert flag.
            found = next((i for i in person.inv if i.functional and (i.t.kind == "explosive" or
                         i.t.tool in ("time_pencil", "code"))), None)
            if found:
                discovered = "Concealed equipment: " + found.t.name + "."
            st["transcript"].append(discovered or "Clothes and ordinary belongings. Nothing incriminating.")
        elif v == "detain" and len(st["evidence"]) >= 2:
            person.ai.pop("civilian", None)
            person.ai.pop("covert", None)
            person.state = "surrendered"
            person.ai["captor"] = p.id
            g._arr_turn = -1
            g._enemy_arr = {}
            g.msg("You detain the suspect on the recorded contradictions and seized equipment.", "good")
            g.command.merit += .5 if suspect else 0
            ps.act(300)
            return
        if discovered and discovered not in st["evidence"]:
            st["evidence"].append(discovered)
        ps.act(600 if v == "search" else 200)
        if p.alive:
            interview(ps, person)
    ps.open_popup(Popup("Identity interview: " + person.name, opts, ps._screen_anchor(), lines=lines, width=68), choose)
