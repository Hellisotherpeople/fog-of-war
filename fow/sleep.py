"""Sleep, and the rest that isn't sleep.

Soldiers live tired.  Sleep is a real state with a depth, a quality and a debt: it is taken lying down, in
cover, under a blanket or in a bed, and the war goes on a second at a time while it's taken.  A light doze
under a hedge restores little and a bed at the aid station restores a great deal; a man woken five minutes
in is groggy for a quarter of an hour; a man woken from deep sleep by a shout may not know where he is.

Sleep is interrupted by the things that interrupt it: a man shaking your shoulder, a burst of fire close
by, being hit, an enemy walking up, the cold, and the dawn.  Sentries stay awake so others can sleep, and
are relieved.  Sleep debt gnaws at speed and aim, and at ninety a man starts nodding off where he stands.

The player sleeps with N (or the Sleep order in the rest menu); autopilot sleeps at night or when he is
falling down, if there's cover and nobody close.
"""
from __future__ import annotations

import math

LIGHT, ORDINARY, DEEP = 0, 1, 2
STAGE_WORD = ("dozing", "asleep", "deep asleep")
STAGE_SECS = (300, 900, 2400)          # into light, ordinary and deep sleep
WAKE_SUPPRESSION = 35
GROGGY = 900                           # a quarter of an hour to shake off a bad waking

DREAMS = ("a kitchen you haven't seen in two years", "the boat, and the water under it", "being back at work "
          "with the same lunch tin", "a girl on a bicycle", "the dog, alive", "a field with nobody on it",
          "the sound of a screen door", "trying to run and getting nowhere", "your mother calling you in",
          "a pint going flat on a bar you can't reach")

SLEEP_WAKE = {"near": "You come awake with a start - someone's coming.",
              "shot": "The firing snaps you awake.",
              "hit": "You wake as the blow lands.",
              "shake": "A hand on your shoulder: \"Up. Up.\"",
              "dawn": "You wake with the grey light, cold and stiff.",
              "cold": "The cold gets into you and you wake shivering.",
              "enough": "You wake on your own, rested.",
              "order": "You're shaken awake and told to get up."}


def _state(a):
    return a.ai.get("sleeping")


def asleep(a) -> bool:
    return _state(a) is not None


def debt(a) -> float:
    return float(a.ai.get("sleep_debt", 0.0))


def can(game, a) -> tuple[bool, str]:
    if game.__dict__.get("domain", "land") != "land":
        return False, "not here"
    if a.vehicle is not None and a.vehicle.moved_turn >= game.turn - 1:
        return False, "not from a moving vehicle"
    if _state(a) is not None:
        return False, "already asleep"
    if not a.alive or a.body.dead or not a.body.conscious:
        return False, "out cold"
    if a.suppression > 30:
        return False, "under fire"
    if any(math.hypot(o.x - a.x, o.y - a.y) <= 8 for o in (game.seen_enemies(12) or ())):
        return False, "the enemy's too close"
    return True, ""


def quality(game, a) -> float:
    """How good the spot for it is: a bed, a blanket and a roof against wet grass and the cold."""
    m = game.map
    q = 0.25
    if a.stance == 2:
        q += 0.05
    if m.pos_cover[a.x, a.y] >= 25:
        q += 0.2
    if a.has_tool("blanket") and a.ai.get("blanket_until", 0) > game.turn:
        q += 0.25
    from . import tiles as T
    if m.in_bounds(a.x, a.y) and T.DEFS[int(m.t[a.x, a.y])].key in ("bed", "hospital_bed"):
        q += 0.55
    from .weather import precipitation, exposure
    if precipitation(game) > 0 and exposure(game, a) > 0.5:
        q -= 0.22
    if getattr(a.body, "temp", 37.0) < 35.6:
        q -= 0.18
    if a.has_tool("blanket") is False and game.is_night() and game.map.pos_cover[a.x, a.y] < 25:
        q -= 0.08
    return max(0.12, min(1.15, q))


def begin(game, a, why="sleep") -> bool:
    ok, _ = can(game, a)
    if not ok:
        return False
    a.stance = 2
    a.ai["sleeping"] = dict(since=game.turn, stage=LIGHT, entered=game.turn, quality=quality(game, a),
                            debt=debt(a))
    a.moved_turn = game.turn
    if a.is_player:
        game.msg("You lie down and close your eyes. (N or Esc: get up)", "info")
    return True


def wake(game, a, why="enough") -> None:
    st = a.ai.pop("sleeping", None)
    if st is None:
        return
    if st["since"] < game.turn - 240:
        a.ai["groggy_until"] = game.turn + GROGGY
    if a.is_player:
        game.msg(SLEEP_WAKE.get(why, "You wake."), "warn" if why in ("near", "shot", "hit", "order") else "info")


def shake(game, a, why="shake") -> None:
    if _state(a) is not None:
        wake(game, a, why)


def act(game, a) -> int:
    """One second of sleep.  Returns the cost (always the full second)."""
    st = _state(a)
    if st is None:
        return 100
    b = a.body
    m = game.map
    t = game.turn
    # what wakes a man
    if b.dead:
        a.ai.pop("sleeping", None)
        return 100
    if m.water[a.x, a.y] >= 2 or m.fire[a.x, a.y] > 0:
        wake(game, a, "shot")
        return 100
    if game.explosives and game.explosive_danger(a.x, a.y, 4) is not None:
        wake(game, a, "shot")
        return 100
    if b.burning or a.hit_turn >= t - 2:
        wake(game, a, "hit")
        return 100
    if a.suppression > WAKE_SUPPRESSION:
        wake(game, a, "shot")
        return 100
    close = [o for o in game.near(a.x, a.y, 12) if o.side != a.side and o.alive]
    if close and (any(abs(o.x - a.x) + abs(o.y - a.y) <= 10 for o in close) or game.turn % 3 == 0):
        # (the sentry's challenge, boots, a twig: it reaches you a moment late)
        if game.can_see(a.x, a.y) or any(abs(o.x - a.x) + abs(o.y - a.y) <= 6 for o in close):
            wake(game, a, "near")
            return 100
    if a.ai.get("wake"):
        a.ai.pop("wake")
        wake(game, a, "shake")
        return 100
    # the cold
    if getattr(b, "temp", 37.0) < 35.2 and game.turn % 30 == 0:
        wake(game, a, "cold")
        return 100
    # depth
    if st["stage"] < DEEP and t - st["entered"] >= STAGE_SECS[st["stage"]]:
        st["stage"] += 1
        st["entered"] = t
        if a.is_player:
            game.msg("You slip deeper under.", "info")
            if game.rng.random() < 0.5:
                game.msg(f"You dream of {game.rng.choice(DREAMS)}.", "think")
    q = st["quality"]
    mult = (1.0, 1.7, 2.4)[st["stage"]]
    a.fatigue = max(0.0, a.fatigue - (0.01 + 0.028 * q) * mult)
    a.suppression = max(0, a.suppression - 2)
    a.stamina = min(100.0, a.stamina + 2.5 * mult)
    a.ai["sleep_debt"] = max(0.0, debt(a) - (100 / 28800) * mult)      # (eight hours clears the debt)
    # deep sleep mends a little of what rest mends
    if st["stage"] == DEEP and t % 90 == 0:
        parts = [p for p in b.hp if 0 < b.hp[p] < b.max[p] * 0.9]
        if parts:
            p = min(parts, key=lambda p: b.hp[p] / b.max[p])
            b.hp[p] = min(b.max[p], b.hp[p] + 1)
    # enough: after about eight hours, or at first light
    if t - st["since"] > 28800 or (game.is_night() is False and 5 <= game.now().hour <= 7 and
                                   t - st["since"] > 1800 and game.rng.random() < 0.01):
        wake(game, a, "dawn" if t - st["since"] > 1800 else "enough")
    return 100


def tick(game) -> None:
    """The sleep debt, for everyone awake; sentries shake the next relief when the watch turns over."""
    if game.__dict__.get("domain", "land") != "land":
        return
    for a in game.actors:
        if not a.alive:
            continue
        if _state(a) is None:
            a.ai["sleep_debt"] = min(100.0, debt(a) + 100 / 57600)     # (sixteen waking hours)
        if a.ai.get("groggy_until", 0) <= game.turn:
            a.ai.pop("groggy_until", None)
    p = game.player
    if p is not None and _state(p) is not None and p.is_player and game.rng.random() < 0.002:
        # a mate mutters at the snoring; quiet company keeps
        pass


def groggy(a) -> bool:
    return a.ai.get("groggy_until", 0) > 0


def words(a) -> tuple[str, tuple] | tuple[None, None]:
    st = _state(a)
    if st is None:
        if a.ai.get("groggy_until", 0) > 0:
            return "Groggy", (220, 180, 120)
        return None, None
    return {LIGHT: "Dozing", ORDINARY: "Asleep", DEEP: "Deep asleep"}[st["stage"]], (150, 180, 210)
