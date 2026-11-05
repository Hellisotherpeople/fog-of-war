"""Work on a position: what a section does when nobody is shooting at it.

A held line is not a row of statues.  Men deepen their holes, cut and lay camouflage, clean their
weapons, top each other up from their pouches, register the ground with the machine gun, check the
wire, and - when there's time - brew up, eat and write home.  A leader rotates two sentries so the
rest can rest.

The routine is deliberately slow and mostly quiet, so the player isn't told about every spadeful.
A unit in contact stops all of it.  Chores use the same action clock as digging or reloading, so
they are real time, and a man doing one is not watching his front.

Which work a section is set to depends on what it is: engineers have wire and mines, the gun
numbers range the ground, the medic restocks his satchel, everyone else improves what they stand in.
"""
from __future__ import annotations

import math

QUIET = 45                  # seconds since contact before the section settles to work
CHORE_SECONDS = {"watch": 0, "dig": 0, "cam": 12, "clean": 10, "ammo": 6, "rest": 0, "brew": 18,
                 "letter": 20, "range": 8}
CHORE_WORD = {"dig": "deepening his hole", "cam": "cutting camouflage", "clean": "cleaning his weapon",
              "ammo": "topping up pouches", "rest": "resting", "brew": "brewing up",
              "letter": "writing home", "range": "registering the ground", "watch": "on sentry"}


def _spare(game, a, mate):
    """Can a hand ammunition to this mate: same weapon, and he's low and you're not."""
    from .ammo import hand_over_possible, spare_rounds
    w = mate.weapon
    return w is not None and hand_over_possible(a, w) and spare_rounds(a, w) > 0


def assign(game, sq):
    """The leader's routine for the next spell: sentries out, work where it's useful, the rest resting."""
    t = game.turn
    men = [m for m in sq.members if m.active and not m.downed and not m.is_player and m.vehicle is None
           and m.ai.get("to_aid") is None and m.ai.get("at_aid") is None]
    if not men:
        return
    sq.rep["routine"] = (t, )
    play = game.player.side == sq.side
    # two sentries on the enemy side of the position, awake; the rest get work or rest
    men.sort(key=lambda m: m.id)
    sentries = men[:2] if len(men) > 3 else men[:1]
    for m in sentries:
        m.ai["chore"] = ("watch", t + 120)
    others = [m for m in men if m not in sentries]
    engineer = [m for m in others if m.role in ("engineer", "seabee", "pioneer")]
    guns = [m for m in others if m.role in ("lmg_gunner", "hmg_gunner", "at_soldier", "mortarman")
            or (m.weapon is not None and m.weapon.t.cat in ("lmg", "hmg", "at_rifle", "mortar"))]
    close = game.seen_enemies(40)
    night = game.is_night() and not close
    from . import sleep as SL
    for i, m in enumerate(others):
        was_asleep = m.ai.get("sleeping") is not None
        m.ai.pop("chore", None)
        if m.weapon is not None and m.weapon.condition < 0.8:
            m.ai["chore"] = ("clean", t + 90)
        elif m.weapon is not None and m.weapon.loaded < m.weapon.t.mag and m.ammo_for(m.weapon) is not None:
            m.ai["chore"] = ("ammo", t + 60)
        elif any(_spare(game, m, o) for o in others if o is not m):
            m.ai["chore"] = ("ammo", t + 60)
        elif game.map.pos_cover[m.x, m.y] < 45 and m.has_tool("shovel") and game.map.tile(m.x, m.y).dig:
            m.ai["chore"] = ("dig", t + 120)
        elif engineer and m in engineer and i % 3 == 0:
            m.ai["chore"] = ("cam", t + 90)
        elif m in guns[:2]:
            m.ai["chore"] = ("range", t + 120)
        elif m.fatigue > 20 or m.stamina < 60 or (night and t % 60 < 30 and SL.debt(m) > 15):
            m.ai["chore"] = ("rest", t + 120)
            if night and (m.fatigue > 20 or SL.debt(m) > 25):
                SL.begin(game, m)
        elif play and game.rng.random() < 0.10:
            m.ai["chore"] = (game.rng.choice(("brew", "letter")), t + 90)
        elif game.rng.random() < 0.35:
            m.ai["chore"] = ("cam", t + 90)
        if was_asleep:
            if m.ai.get("chore", ("",))[0] != "rest":
                SL.shake(game, m, "order")
            elif m.ai.get("sleeping") is None and night:
                SL.begin(game, m)


def _clear(game, a):
    c = a.ai.get("chore")
    if c is None:
        return True
    if c[1] <= game.turn:
        a.ai.pop("chore", None)
        return True
    return False


def act(game, a, sq, vis) -> int | None:
    """Do the chore.  None: nothing doing, carry on as usual."""
    from . import actions as A
    t = game.turn
    if not a.ai.get("chore") or _clear(game, a):
        return None
    if vis and a.ai["chore"][0] not in ("watch", "rest", "range"):
        return None                       # somebody in sight: eyes up
    kind = a.ai["chore"][0]
    m = game.map
    if kind == "watch":
        A.set_stance(game, a, 1 if a.stance == 0 else a.stance)
        return 100
    if kind == "rest":
        if game.is_night() and not vis and a.ai.get("sleeping") is None:
            from .sleep import begin, can
            if can(game, a)[0]:
                begin(game, a)
                return 100
        if a.stance < 2 and m.pos_cover[a.x, a.y] > 25:
            return A.set_stance(game, a, 2) or 100
        a.stamina = min(100, a.stamina + 1.5)
        a.fatigue = max(0, a.fatigue - 0.05)
        return 100
    if kind == "dig":
        return A.dig(game, a)
    if kind == "clean":
        w = a.weapon
        if w is None or w.condition >= 0.995:
            a.ai.pop("chore", None)
            return None
        w.condition = min(1.0, w.condition + 0.025)
        a.stamina = max(0, a.stamina - 0.2)
        return CHORE_SECONDS["clean"] * 100
    if kind == "ammo":
        w = a.weapon
        low = [o for o in sq.members if o is not a and o.active and not o.downed and _spare(game, a, o)]
        if not low or w is None:
            a.ai.pop("chore", None)
            return None
        mate = min(low, key=lambda o: max(abs(o.x - a.x), abs(o.y - a.y)))
        if max(abs(mate.x - a.x), abs(mate.y - a.y)) > 1:
            from .ai import path_step
            c = path_step(game, a, mate.x, mate.y)
            if c:
                return c
            a.ai.pop("chore", None)
            return None
        from .ammo import hand_over
        hand_over(game, a, mate, mate.weapon, max_items=1)
        a.ai.pop("chore", None)
        return 600
    if kind == "cam":
        if m.conceal[a.x, a.y] >= 70:
            a.ai.pop("chore", None)
            return None
        m.conceal[a.x, a.y] = min(95, m.conceal[a.x, a.y] + 6)
        a.stamina = max(0, a.stamina - 0.3)
        return CHORE_SECONDS["cam"] * 100
    if kind == "range":
        # the gun number paces the ground and writes the ranges; the gun's aim against still targets improves
        a.ai["ranged"] = t + 600
        a.ai.pop("chore", None)
        return CHORE_SECONDS["range"] * 100
    if kind == "brew":
        if not a.ai.get("brew_made"):
            a.ai["brew_made"] = t
            a.morale = min(100.0, a.morale + 3)
            for o in sq.members:
                if o.active and not o.downed and max(abs(o.x - a.x), abs(o.y - a.y)) <= 5:
                    o.morale = min(100.0, o.morale + 1.5)
            if game.player.side == a.side and a.is_player is False:
                game.msg(f"{a.rank_short} {a.last_name} gets a brew on.", "info")
        a.ai.pop("chore", None)
        return CHORE_SECONDS["brew"] * 100
    if kind == "letter":
        a.morale = min(100.0, a.morale + 2)
        a.ai.pop("chore", None)
        return CHORE_SECONDS["letter"] * 100
    a.ai.pop("chore", None)
    return None


def tick(game):
    """Give quiet sections a routine again, and let go of men who are needed elsewhere."""
    if game.turn % 30:
        return
    for sq in game.squads:
        if sq.gone or sq.player_led or sq.state not in ("hold", "idle"):
            continue
        if sq.order.kind not in ("defend", "hold", "dig", "ambush") or sq.rep.get("construction"):
            continue
        if sq.leader is None or not sq.leader.active:
            continue
        if game.turn - sq.last_contact < QUIET or game.turn - sq.last_contact < 0:
            continue
        anc = sq.anchor()
        if anc is None:
            continue
        if game.brains[sq.side].exposure_at(anc[0], anc[1]) > 1.2:
            continue
        if len(sq.rep.get("routine", ())) and game.turn - sq.rep["routine"][0] < 90:
            continue
        # an engineer section on a quiet line improves the obstacle plan, not just its own holes
        if game.turn % 120 == 0 and not sq.rep.get("construction") and \
                any(a.active and a.role in ("engineer", "seabee") and a.has_tool("shovel") for a in sq.members):
            from .fieldworks import assign as assign_work, valid_site
            for kind in ("wire", "sandbags"):
                for dx, dy in ((4, 0), (-4, 0), (0, 4), (0, -4), (6, 3), (-6, 3)):
                    pt = (anc[0] + dx, anc[1] + dy)
                    if valid_site(game, kind, pt)[0]:
                        assign_work(game, sq, kind, pt, automatic=True)
                        break
                if sq.rep.get("construction"):
                    break
        assign(game, sq)


def routine_word(sq):
    chores = [m.ai["chore"][0] for m in sq.members if m.ai.get("chore")]
    if not chores:
        return ""
    best = max(set(chores), key=chores.count)
    if chores.count("watch") >= max(1, len(chores) // 2):
        return "on sentry"
    return CHORE_WORD.get(best, "")
