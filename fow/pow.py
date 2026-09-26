"""Captivity.

Surrender isn't the end.  Depending on who takes you (and what they've seen), you may
be shot where you kneel.  Otherwise you're searched, disarmed and marched to their rear
under guard - in real turns, and a guard will shoot a man who runs.  Then the camp:
days pass while the war goes on around it.  Rations, sickness, work details, Red Cross
parcels, the escape committee.  Men died of hunger and disease in their millions; many
more came home.  If your side takes the ground the camp stands on, you're liberated
and back in the war.
"""
from __future__ import annotations

import math

from .constants import SIDES, other_side

# (captor, prisoner) -> (daily chance of dying, ration quality 0..1, camp word)
CAMPS = {
    ("germany", "ussr"): (0.0030, 0.25, "Stalag (Soviet compound)"),
    ("germany", "poland"): (0.0012, 0.45, "Stalag"),
    ("germany", "*"): (0.00035, 0.60, "Stalag"),
    ("ussr", "germany"): (0.0012, 0.40, "NKVD camp"),
    ("ussr", "*"): (0.0012, 0.40, "NKVD camp"),
    ("japan", "*"): (0.0011, 0.30, "Japanese camp"),
    ("finland", "ussr"): (0.0010, 0.40, "prison camp"),
    ("*", "japan"): (0.00015, 0.70, "POW compound"),
    ("*", "*"): (0.0001, 0.75, "POW cage"),
}
RED_CROSS = {"usa", "uk", "canada", "australia", "newzealand", "france", "poland", "india"}   # parcels (in German camps)


def camp_for(captor, prisoner):
    for key in ((captor, prisoner), (captor, "*"), ("*", prisoner), ("*", "*")):
        if key in CAMPS:
            return CAMPS[key]
    return CAMPS[("*", "*")]


def begin_captivity(game) -> str:
    """You've put your hands up.  Returns 'shot', 'march' or 'camp'."""
    from .duty import EXECUTES
    rng = game.rng
    p = game.player
    enemy = other_side(p.side)
    near = [a for a in game.actors if a.side == enemy and a.active and max(abs(a.x - p.x), abs(a.y - p.y)) <= 12]
    captor = min(near, key=lambda a: max(abs(a.x - p.x), abs(a.y - p.y))) if near else None
    cnat = captor.nation if captor is not None else game.side_nation(enemy)
    rate = EXECUTES.get((cnat, p.nation), EXECUTES.get((cnat, "*"), 0.0))
    rate *= 1 + 0.6 * game.no_quarter.get(p.side, 0)
    if getattr(game.duty, "pow_shot", 0):
        rate = min(0.95, rate + 0.25)          # they've heard what you did to theirs
    if captor is not None and rng.random() < rate:
        return "shot"
    # searched: weapons, ammunition, anything worth having
    taken = []
    for it in list(p.inv):
        t = it.t
        if t.kind in ("gun", "grenade", "explosive", "mag", "clip", "ammo", "melee") or t.tool in ("watch", "binoculars",
                                                                                               "compass", "map",
                                                                                               "radio", "handradio"):
            p.remove_item(it)
            taken.append(it.name)
            if game.map.in_bounds(p.x, p.y):
                game.map.add_item(p.x, p.y, it)
        elif t.tool == "cigarettes" and rng.random() < 0.5:
            p.remove_item(it)
            taken.append(it.name)
    p.weapon = None
    p.state = "captive"
    camp = camp_for(cnat, p.nation)
    game.pow = dict(stage="march", guard=captor.id if captor is not None else None, captor=cnat,
                    start_turn=game.turn, camp=camp[2], death=camp[0], rations=camp[1], day=0, food=70.0,
                    sick=0, weak=0.0, events=[], warned=0, escape_plan=0.0, parcels=p.nation in RED_CROSS and cnat == "germany")
    if captor is not None:
        captor.ai["escort"] = p.id
    game.msg("They search you roughly" + (f" - your {', '.join(taken[:3])}{' and more' if len(taken) > 3 else ''} gone"
                                          if taken else "") + ". A rifle muzzle prods you toward their lines.", "warn")
    game.brains[enemy].contacts.pop(p.id, None)
    game._enemy_arr = {}
    return "march"


def march_update(game):
    """Each turn of the march: keep up with the guard, or be shot trying."""
    pw = game.pow
    p = game.player
    if pw is None or pw["stage"] != "march" or not p.alive:
        return
    enemy = other_side(p.side)
    guard = next((a for a in game.actors if a.id == pw.get("guard")), None)
    if guard is None or not guard.active:
        # the guard's dead or gone: a new one, or a chance
        near = [a for a in game.actors if a.side == enemy and a.active and max(abs(a.x - p.x), abs(a.y - p.y)) <= 15]
        if near:
            guard = min(near, key=lambda a: max(abs(a.x - p.x), abs(a.y - p.y)))
            pw["guard"] = guard.id
            guard.ai["escort"] = p.id
        else:
            if not pw.get("free_msg"):
                pw["free_msg"] = True
                game.msg("Nobody's watching you. Your guard is gone. (Run for it - or wait for them.)", "warn")
            _check_freedom(game)
            return
    d = max(abs(guard.x - p.x), abs(guard.y - p.y))
    if d > 6:
        pw["warned"] += 1
        if pw["warned"] in (1, 4):
            guard.say(game.shout(guard, "contact"), game.turn, 3)
            game.msg("The guard shouts at you and levels his rifle.", "warn")
        elif pw["warned"] > 6 and game.rng.random() < 0.3:
            from .actions import fire
            game.msg("The guard fires!", "death")
            if guard.weapon is not None and guard.weapon.t.kind == "gun" and guard.weapon.loaded > 0:
                fire(game, guard, p.x, p.y, p)
    else:
        pw["warned"] = max(0, pw["warned"] - 1)
    brain = game.brains[enemy]
    if brain.home is not None and int(brain.home[p.x, p.y]) <= 3 * 4:
        pw["stage"] = "camp"
        pw["camp_turn"] = game.turn
        guard.ai.pop("escort", None)
        _place_camp(game)
    _check_freedom(game)


def _check_freedom(game):
    """Reached your own lines while nobody was escorting you: you've got away."""
    p = game.player
    pw = game.pow
    brain = game.brains[p.side]
    if brain.home is not None and int(brain.home[p.x, p.y]) <= 3 * 4 and pw.get("free_msg"):
        free(game, "You stumble into your own lines, hands still raised. They nearly shoot you.")


def _place_camp(game):
    """The camp stands somewhere in the enemy's rear."""
    st = game.strategic
    p = game.player
    enemy = other_side(p.side)
    # somewhere well behind their lines: a day or two's journey by truck and train
    from .strategic import DIRS, OPP
    back = st.att_from if enemy == st.attacker else OPP[st.att_from]
    dx, dy = DIRS[back]
    far = None
    here = game.sector
    for k in range(game.rng.randint(7, 11), 2, -1):
        c = st.at(here.x + dx * k, here.y + dy * k, create=True)
        if c is not None and c.playable and c.control == enemy:
            far = c
            break
    if far is None:
        rear = [s for s in st.sectors() if s.control == enemy and s.playable]
        far = max(rear, key=lambda s: st._front_distance(s, enemy)) if rear else None
    if far is not None:
        game.pow["sector"] = (far.x, far.y)
        game.pow["sector_name"] = far.name
    game.msg(f"You're loaded into a truck with other prisoners. Behind the lines, the {game.pow['camp']}.", "warn")


def free(game, text):
    p = game.player
    game.pow = None
    p.state = "ok"
    game.msg(text, "good")
    game.update_orders(force=True)


def camp_day(game) -> list[str]:
    """One day in the camp.  Returns what happened."""
    rng = game.rng
    pw = game.pow
    p = game.player
    b = p.body
    out = []
    pw["day"] += 1
    # the war goes on: a day of strategic time
    game.advance_clock(86400)
    st = game.strategic
    if pw.get("sector"):
        st.touch(*pw["sector"], 2)                     # the war as it's heard from behind the wire
    for _ in range(max(1, 86400 // (600 * 12))):         # a coarse day of fighting elsewhere
        st.tick(None)
    for n in st.news[-2:]:
        if rng.random() < 0.3:
            out.append(f"Rumour in the camp: {n}")
    st.news = []
    # food
    ration = pw["rations"]
    if pw.get("parcels") and rng.random() < 0.12:
        pw["food"] = min(100.0, pw["food"] + 25)
        out.append("A Red Cross parcel: tinned meat, chocolate, cigarettes. You eat like a king for a day.")
    pw["food"] = max(0.0, min(100.0, pw["food"] + (ration - 0.55) * 10 + rng.uniform(-2, 2)))
    if pw["food"] < 30:
        pw["weak"] += 0.6
        if rng.random() < 0.2:
            out.append("Watery soup and a crust again. Your ribs are showing.")
    elif pw["weak"] > 0:
        pw["weak"] = max(0.0, pw["weak"] - 0.3)
    # sickness
    if pw["sick"] <= 0 and rng.random() < 0.02 + (0.03 if pw["food"] < 30 else 0):
        pw["sick"] = rng.randint(4, 14)
        out.append(rng.choice(["Dysentery. You can't keep anything down.", "Fever. The camp doctor has nothing to give you.",
                               "Typhus is going through the huts."]))
    if pw["sick"] > 0:
        pw["sick"] -= 1
        pw["weak"] += 0.4
    # wounds heal slowly without care
    from .medical import recover
    recover(game, p, 3000)
    # work details and the guards
    if rng.random() < 0.3:
        out.append(rng.choice(["A work detail: breaking stones on the road.", "A work detail at the railway yard.",
                               "Roll call in the rain for three hours.", "Nothing. Another day of nothing."]))
    if rng.random() < 0.03:
        out.append("A guard beats a man in your hut for no reason you can see.")
        p.morale -= 5
    # death
    risk = pw["death"] * (1 + pw["weak"] / 10) * (2.5 if pw["sick"] > 0 else 1.0)
    if rng.random() < risk:
        cause = "typhus" if pw["sick"] > 0 else "starvation and exhaustion" if pw["food"] < 25 else "illness"
        b.dead = True
        b.cause = cause
        return out + ["__dead__:" + cause]
    # liberation: our side takes the ground the camp stands on
    sec = pw.get("sector")
    if sec is not None:
        s = st.at(*sec)
        if s is not None and s.control == p.side:
            return out + ["__liberated__"]
    return out


def try_escape(game) -> str:
    """The escape committee has a plan.  Returns 'escaped', 'caught' or 'shot'."""
    rng = game.rng
    pw = game.pow
    p = game.player
    base = 0.08 + pw.get("escape_plan", 0.0) * 0.02
    if "camouflaged" in p.traits:
        base += 0.05
    if pw["captor"] in ("japan", "ussr"):
        base *= 0.5              # a long way home, and nowhere to hide
    base *= max(0.3, 1 - pw["weak"] / 12)
    if rng.random() < base:
        return "escaped"
    if rng.random() < (0.25 if pw["captor"] in ("japan", "ussr") else 0.08):
        p.body.dead = True
        p.body.cause = "shot while escaping"
        return "shot"
    pw["weak"] += 1.5
    return "caught"


def return_to_war(game, how):
    """Liberated or escaped: back to your own side, in a friendly sector near the front."""
    st = game.strategic
    p = game.player
    side = p.side
    cands = [s for s in st.sectors() if s.control == side and s.playable]
    if how == "liberated" and game.pow.get("sector"):
        s0 = st.at(*game.pow["sector"])
        if s0 is not None and s0.control == side:
            cands = [s0]
    if not cands:
        return False
    sector = min(cands, key=lambda s: st._front_distance(s, side)) if how != "liberated" else cands[0]
    game.pow = None
    p.state = "ok"
    p.morale = 40.0
    p.stamina = 60.0
    game.remove_actor(p) if p in game.actors else None
    game.enter_sector(sector, entry_edge=None)
    from .spawn import place
    edge = game.home_edge(side)
    from .spawn import edge_band_point
    x, y = edge_band_point(game, edge, game.rng, depth=(3, 10)) if edge else (game.map.w // 2, game.map.h // 2)
    place(game, p, x, y, 8)
    game.add_actor(p) if p not in game.actors else None
    p.squad = None
    game.command.organise(game)
    game.update_orders(force=True)
    game.player_fov()
    return True


def start_in_camp(game) -> str:
    """Begin the war behind the wire (the prisoner-of-war battle type)."""
    p = game.player
    enemy = other_side(p.side)
    cnat = game.side_nation(enemy)
    camp = camp_for(cnat, p.nation)
    for it in list(p.inv):
        if it.t.kind in ("gun", "grenade", "explosive", "mag", "clip", "ammo", "melee") or \
                it.t.tool in ("binoculars", "compass", "map", "radio", "handradio"):
            p.remove_item(it)
    p.weapon = None
    p.state = "captive"
    game.pow = dict(stage="camp", guard=None, captor=cnat, start_turn=game.turn, camp=camp[2], death=camp[0],
                    rations=camp[1], day=game.rng.randint(20, 200), food=55.0, sick=0, weak=1.5, events=[],
                    warned=0, escape_plan=0.0, parcels=p.nation in RED_CROSS and cnat == "germany",
                    camp_turn=game.turn)
    _place_camp(game)
    return (f"You were taken prisoner {game.pow['day']} days ago. This is the {camp[2]}. The war goes on "
            f"without you - for now.")
