"""How good a gun is, and how rare.

Quality is read off the thing itself - its punch, its reach, its sights, how badly it
scatters, how often it jams, how fast it is worked.  Rarity is how often it turns up in
the first place.  Both are shown to the player and used by the AI when it chooses what
to carry; a rifle that is better than the one in your hands is worth going over for.

Nothing here changes the simulation on its own: the numbers are the same numbers the
ballistics use, only weighed against each other.
"""
from __future__ import annotations

QUALITY = ("Rough", "Serviceable", "Well made", "Fine", "Exceptional")
RARITY = ("Plentiful", "Common", "Uncommon", "Scarce", "Special issue")

COLOR = ((150, 150, 140), (190, 190, 175), (220, 215, 180), (246, 210, 120), (255, 176, 90))
RARE_COLOR = ((120, 120, 112), (145, 145, 135), (175, 175, 160), (205, 195, 160), (230, 190, 135))


def score(t) -> float:
    """A comparable worth for a firearm.  Higher is better; only guns get one."""
    if getattr(t, "kind", "") != "gun":
        return 0.0
    dps = t.dmg * max(1, t.burst)
    s = t.dmg * 0.5 + dps * 0.15 + t.rng * 0.35 + t.pen * 0.35 + min(t.mag, 40) * 0.5
    if "auto" in t.modes:
        s += 10.0
    if t.scope:
        s += 8.0
    s -= t.disp * 9.0 + t.jam * 500.0 + t.weight + t.shot_cost / 45.0 + t.reload_cost / 70.0
    return s


def tier(t) -> int:
    """0 (rough) to 4 (exceptional), by score."""
    q = score(t)
    if q >= 75:
        return 4
    if q >= 52:
        return 3
    if q >= 34:
        return 2
    if q >= 5:
        return 1
    return 0


def rarity(t) -> int:
    """0 (plentiful) to 4 (special issue), by how often it's issued."""
    f = getattr(t, "freq", 10)
    if f <= 0:
        return 4
    if f <= 1:
        return 3
    if f <= 3:
        return 2
    if f <= 6:
        return 1
    return 0


def words(t) -> str:
    """The two words, for the look-it-over box and the hover: quality first, then rarity."""
    if getattr(t, "kind", "") != "gun":
        return ""
    return f"{QUALITY[tier(t)]}, {RARITY[rarity(t)].lower()}."


def color(t) -> tuple:
    return COLOR[tier(t)]


def rarity_color(t) -> tuple:
    return RARE_COLOR[rarity(t)]


def better(a, b) -> int:
    """-1 if gun a is worse than b, 1 if better (by a useful margin), else 0."""
    if a is None:
        return 1
    if b is None:
        return -1
    d = score(a) - score(b)
    return 1 if d >= 6 else -1 if d <= -6 else 0


def against(t, carried) -> str:
    """What this is next to what the player already holds."""
    if getattr(t, "kind", "") != "gun" or carried is None or getattr(carried, "kind", "") != "gun":
        return ""
    d = score(t) - score(carried)
    if d >= 6:
        return "Better than what you carry."
    if d <= -6:
        return "Worse than what you carry."
    return "Much the same as what you carry."
