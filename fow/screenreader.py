"""A text feed for a screen reader.

When the option is on, the game narrates the things a blind player can't see: messages as they arrive,
the panel in brief, and the name of each screen that opens.  It writes to stdout, line by line, so any
screen reader attached to the terminal picks it up.  It is deliberately sparse - a wall of text is worse
than none.
"""
from __future__ import annotations

import time

_last = [0.0]


def on() -> bool:
    return True


def say(text: str) -> None:
    try:
        print(f"[FOW] {text}", flush=True)
    except (OSError, ValueError):
        pass


def screen(title: str) -> None:
    if time.monotonic() - _last[0] < 0.2:
        return
    _last[0] = time.monotonic()
    say(f"— {title} —")


def status(game) -> None:
    p = game.player
    if p is None:
        return
    from . import renown
    nick = renown.title(game)
    bits = [f"{p.rank_short} {p.name}", p.role_name + (f", {nick}" if nick else ""), f"{int(p.body.blood)} blood",
            {0: "standing", 1: "crouching", 2: "prone"}.get(p.stance, "")]
    if p.weapon is not None:
        bits.append(f"{p.weapon.t.name}, {p.weapon.ammo_estimate()}")
    od = game.player_orders
    if od:
        bits.append(f"orders: {od}")
    say("; ".join(b for b in bits if b))
