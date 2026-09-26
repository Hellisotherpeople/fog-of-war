"""Knowing your weapon.

A soldier drills with his own army's rifle until he can strip it blind.  Pick up the
enemy's and it's a puzzle: where's the safety, how does the magazine come out, why
won't the bolt close?  Everything takes longer and goes wrong more often - until you've
fired it, loaded it, cleared it a few times, and it starts to feel like yours.

The same goes for a captured tank: the crew fumble for the gears, the traverse, the
breech, the unfamiliar sight.  And your own side sees an enemy tank until someone
paints a big white star (or cross) on it.

Familiarity runs from 0 (never seen one) to 1 (issued it, trained on it).
"""
from __future__ import annotations

from .data.nations import NATIONS, equip_sources
from .data.ranks import same_army

# armies that trained on (or were issued) each other's weapons
FAMILY = {"usa": "west", "uk": "west", "canada": "west", "australia": "west", "newzealand": "west", "india": "west",
          "france": "west", "poland": "west", "germany": "axis_eu", "italy": "axis_eu", "hungary": "axis_eu",
          "romania": "axis_eu", "finland": "axis_eu", "ussr": "soviet", "china": "china", "japan": "japan"}
THRESHOLDS = ((0.5, "You're getting the hang of the {w}."), (0.85, "The {w} feels like your own now."))


def _base(a, t) -> float:
    nats = t.get("nations") or ()
    if not nats:
        return 1.0                                  # generic kit: a knife is a knife
    try:
        srcs = equip_sources(a.nation, 2000)
    except Exception:
        srcs = [a.nation]
    if a.nation in nats or any(s in nats for s in srcs):
        b = 1.0
        if t.kind == "gun" and t.cat in ("lmg", "hmg", "mortar", "at_launcher", "at_rifle", "flamer", "sniper") and \
                not _specialist(a, t):
            b = 0.6                                 # you've seen one; you haven't drilled on it
    elif any(same_army(a.nation, n) or FAMILY.get(n, n) == FAMILY.get(a.nation, a.nation) for n in nats):
        b = 0.5                                     # an ally's: similar enough, and you've seen them
    else:
        b = 0.15                                    # the enemy's
        if t.kind == "gun" and t.cat in ("pistol", "rifle", "carbine"):
            b = 0.25                                # a bolt is a bolt
    if b >= 1.0:
        return 1.0
    if "veteran" in a.traits:
        b += 0.15
    if "green" in a.traits:
        b -= 0.05
    return max(0.05, min(1.0, b + (a.skill - 5) * 0.02))


def _specialist(a, t) -> bool:
    role = getattr(a, "role", "")
    return (t.cat in ("lmg",) and role in ("lmg_gunner", "lmg_assistant", "smg_gunner")) or \
        (t.cat == "hmg" and role in ("hmg_gunner", "hmg_assistant")) or \
        (t.cat == "mortar" and role == "mortarman") or \
        (t.cat in ("at_launcher", "at_rifle") and role == "at_soldier") or \
        (t.cat == "flamer" and role == "flamethrower") or (t.cat == "sniper" and role == "sniper")


def level(a, t) -> float:
    fam = a.__dict__.get("familiar")
    if fam is None:
        fam = a.familiar = {}
    v = fam.get(t.id)
    if v is None:
        v = fam[t.id] = _base(a, t)
    return v


def learn(game, a, t, amount: float):
    """Practice makes it yours."""
    old = level(a, t)
    if old >= 1.0:
        return
    new = min(1.0, old + amount * (1.2 if "veteran" in a.traits else 1.0))
    a.familiar[t.id] = new
    if a.is_player:
        for thr, text in THRESHOLDS:
            if old < thr <= new:
                game.msg(text.format(w=t.name), "good")


def slow(a, t) -> float:
    """Time multiplier for working it: loading, clearing, aiming, the bolt."""
    return 1.0 + (1.0 - level(a, t)) * 0.9


def sloppy(a, t) -> float:
    """Extra degrees of error from not knowing the sights, the trigger, the kick."""
    return (1.0 - level(a, t)) * 0.7


def word(a, t) -> str | None:
    f = level(a, t)
    if f < 0.35:
        return "unfamiliar"
    if f < 0.7:
        return "getting used to it"
    return None


def first_look(game, a, t):
    """What you think the first time you pick one up."""
    f = level(a, t)
    if not a.is_player or t.kind != "gun" or f >= 0.7:
        return
    seen = a.__dict__.setdefault("seen_guns", set())
    if t.id in seen:
        return
    seen.add(t.id)
    if f < 0.35:
        game.msg(f"You turn the {t.name} over in your hands. You've never fired one - where's the safety?", "info")
    else:
        game.msg(f"A {t.name}. You've handled one or two; it'll take some getting used to.", "info")


# ---------------------------------------------------------------- captured vehicles

def vehicle_level(v) -> float:
    """How well the crew know the machine they're in."""
    if not v.ai.get("captured"):
        return 1.0
    return v.ai.get("fam", 0.15)


def vehicle_learn(v, amount):
    if v.ai.get("captured"):
        v.ai["fam"] = min(1.0, v.ai.get("fam", 0.15) + amount)


def mistakable(game, v, side) -> bool:
    """Could men of `side` still take this (captured, now friendly) vehicle for the enemy's?"""
    return (v.side == side and v.ai.get("captured") and not v.ai.get("marked")
            and v.ai.get("recognised", -1) <= game.turn and game.turn - v.ai.get("captured_turn", 0) < 600)
