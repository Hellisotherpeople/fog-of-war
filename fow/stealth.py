"""Stealth: being seen is a process, not a switch.

A man in the open, moving, is seen at once.  A man lying still in a hedge bottom may be looked
at for a long time before anyone realises what they're looking at - and a trained sniper in a
ghillie suit, in long grass, may never be seen at all until he fires (and not always then).

Each observer builds up an awareness of each soldier it could see: fast if he's close, moving
or silhouetted, slowly if he's far, still and in cover; faster if the observer is alert and
expecting trouble.  Half-aware, the observer is suspicious - he looks, and tells his mates
there's something over there.  Fully aware, he's seen him.  Awareness fades when the man goes
out of sight.

Camouflage matters where it matches the ground (a ghillie in grass, a snow smock on snow;
either one, badly placed, draws the eye).  Fieldcraft matters more: snipers, scouts, commandos
and intelligence men move quietly and know how to use the ground.
"""
from __future__ import annotations

from . import tiles as T

VEG_KEYS = {"grass", "tall_grass", "wheat", "corn", "sunflower", "bush", "bush_snow", "hedge", "garden_hedge",
            "tree", "tree2", "pine", "olive", "palm", "jungle", "bamboo", "scrub", "kunai", "marsh", "dead_tree",
            "stump", "log", "orchard", "paddy", "hay"}
URBAN_KEYS = {"rubble", "rubble_light", "rubble_heavy", "rubble_wood", "floor_wood", "floor_stone",
              "floor_concrete", "cobble", "paved", "doorway", "crates", "wreck"}
# how quietly and well a man of this role uses the ground (lower is better)
FIELDCRAFT = {"sniper": 0.55, "scout": 0.7, "agent": 0.7, "intel": 0.8, "partisan": 0.75, "commando": 0.7,
              "pathfinder": 0.75}


def terrain_class(m, x, y) -> str:
    key = T.DEFS[int(m.t[x, y])].key
    if "snow" in key or key in ("ice",):
        return "snow"
    if key in VEG_KEYS or key.startswith("tree"):
        return "veg"
    if key in URBAN_KEYS or key.startswith("wall"):
        return "urban"
    if m.climate == "winter" and key in ("dirt", "mud", "plowed"):
        return "snow"
    return "open"


def camo_mult(game, a) -> float:
    """What his camouflage is worth on the ground he's on (1 = nothing)."""
    body = a.invent.slots.get("body") if hasattr(a, "invent") else None
    if body is None or not body.t.get("camo"):
        return 1.0
    m = game.map
    if not m.in_bounds(a.x, a.y):
        return 1.0
    return body.t.camo.get(terrain_class(m, a.x, a.y), 1.0)


def fieldcraft(a) -> float:
    """How much a man's movement and shape give him away: his stealth skill (skills.py) - about 1 for most
    soldiers, much less for the ones trained or born to go unseen."""
    from .skills import stealth_mult
    return stealth_mult(a)


def alertness(game, viewer) -> float:
    """How hard he's looking: a sentry expecting trouble notices; a man pinned down or asleep doesn't."""
    sq = getattr(viewer, "squad", None)
    a = 1.0
    if sq is not None and game.turn - sq.last_contact < 60:
        a *= 1.5
    elif sq is not None and getattr(sq, "state", "") in ("idle", "hold") and game.turn - sq.last_contact > 600:
        a *= 0.7
    if getattr(viewer, "suppression", 0) > 40:
        a *= 0.5
    if getattr(viewer, "vt", None) is not None:
        a *= 0.8 if getattr(viewer, "buttoned", False) else 1.1
    return a


def notice(game, viewer, target, dist, fr) -> bool:
    """One turn of looking.  True if the viewer now sees the target properly."""
    if getattr(target, "vt", None) is not None:
        return True                              # vehicles: seen or not (their bulk isn't subtle)
    t = game.turn
    # things nobody misses: right on top of you, running about, a muzzle flash
    if dist <= 2.5 or target.fired_turn >= t - 1:
        _set(viewer, target, 1.0, t)
        return True
    if target.moved_turn >= t - 1 and target.ai.get("pace_now") in ("run", "sprint"):
        _set(viewer, target, 1.0, t)
        return True
    close = dist / max(1.0, fr)
    if close <= 0.35:
        _set(viewer, target, 1.0, t)
        return True
    aw = viewer.ai.setdefault("aware", {})
    lvl, last = aw.get(target.id, (0.0, t))
    lvl = max(0.0, lvl - 0.08 * max(0, t - last - 1))      # it fades while he's out of sight
    rate = (0.12 + 0.6 * (1.0 - close)) * alertness(game, viewer)
    if target.moved_turn >= t - 1:
        rate *= 1.6
    rate *= 0.4 + 0.6 * fieldcraft(target)
    if hasattr(viewer, "body"):
        from .skills import observe_mult
        rate *= observe_mult(viewer)             # a sharp eye picks him out sooner
    target.ai["near_enemy_turn"] = t
    lvl = min(1.0, lvl + rate)
    aw[target.id] = (lvl, t)
    if lvl >= 1.0:
        return True
    if lvl >= 0.5 and not viewer.ai.get("suspect_turn", -99) >= t - 5:
        # "something moved over there": he looks, and says so
        viewer.ai["suspect_turn"] = t
        err = 2 + int(dist * 0.1)
        rng = game.rng
        x = max(0, min(game.map.w - 1, target.x + rng.randint(-err, err)))
        y = max(0, min(game.map.h - 1, target.y + rng.randint(-err, err)))
        game.brains[viewer.side].report(None, t, sound=True, x=x, y=y)
        if target.is_player:
            game.__dict__["_watched"] = t
    if target.is_player:
        w = game.__dict__.get("_watch_lvl", (0.0, -99))
        if w[1] < t or lvl > w[0]:
            game.__dict__["_watch_lvl"] = (lvl, t, viewer.x, viewer.y)
    return False


def _set(viewer, target, lvl, t):
    viewer.ai.setdefault("aware", {})[target.id] = (lvl, t)


def exposure_word(game, p):
    """How hidden you feel - what you'd judge for yourself, lying there."""
    from .senses import concealment_factor
    f = concealment_factor(game, None, p)
    t = game.turn
    seen = any(p in getattr(a, "visible", ()) for a in game.actors
               if a.side != p.side and a.active and a.vis_turn >= t - 2 and
               max(abs(a.x - p.x), abs(a.y - p.y)) < 60)
    lvl = game.__dict__.get("_watch_lvl", (0.0, -99))
    if seen and p.hit_turn >= t - 10:
        return "They've seen you!", (255, 90, 70)
    if lvl[1] >= t - 3 and lvl[0] >= 0.5 and len(lvl) >= 4:
        # (only from something you could have caught: movement where you can see, or close enough to hear)
        wx, wy = lvl[2], lvl[3]
        m = game.map
        if (m.in_bounds(wx, wy) and m.visible[wx, wy]) or max(abs(wx - p.x), abs(wy - p.y)) <= 8:
            return "You feel eyes on you", (250, 170, 90)
    if f < 0.3:
        return "Well hidden", (130, 200, 130)
    if f < 0.55:
        return "Concealed", (170, 200, 140)
    if f < 0.8:
        return "Partly exposed", (220, 200, 120)
    return "In the open", (240, 160, 100)
