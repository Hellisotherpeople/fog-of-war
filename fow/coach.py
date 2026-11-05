"""A quiet teacher: one in-voice line the first time something is about to kill the player.

Not a tutorial popup.  The man beside you says it, or the message log does in the game's voice.  Each
lesson fires once per battle, and only when the condition is actually true, so it teaches the thing
the player is just about to learn the hard way.  Off with the key hints option.
"""
from __future__ import annotations

SAID = ("first_cover", "get_down", "reload", "bleed", "open_ground", "aid", "dry")


def _say(game, key, text, voice=None):
    said = game.__dict__.setdefault("coach_said", set())
    if key in said:
        return False
    if not (game.__dict__.get("_prefs") or {}).get("hints", True):
        return False
    from .difficulty import assist
    if not assist(game, "hints", True):
        return False
    said.add(key)
    if voice is not None and voice.active and not voice.is_player:
        voice.say(text, game.turn, 5, tone="talk")
        game.msg(f"{voice.last_name}: '{text}'", "info")
    else:
        game.msg(text, "info")
    return True


def tick(game):
    p = game.player
    if p is None or not p.alive or game.__dict__.get("drill") is not None:
        return
    if game.__dict__.get("domain", "land") != "land":
        return
    m = game.map
    if m is None:
        return
    near = [a for a in game.near(p.x, p.y, 7, p.side) if a is not p and a.active and not a.downed]
    mate = min(near, key=lambda a: max(abs(a.x - p.x), abs(a.y - p.y))) if near else None
    cover = float(m.pos_cover[p.x, p.y])
    exposed = cover < 30
    # stand-up-under-fire
    if p.suppression > 25 and p.stance == 0 and exposed:
        _say(game, "get_down", "Get down, you idiot! On your belly!", mate)
        return
    # empty magazine in the open
    w = p.weapon
    if w is not None and w.t.kind == "gun" and w.loaded <= 0 and exposed:
        _say(game, "dry", "You're dry! Reload behind something, not out here.", mate)
        return
    # first time on the ground
    if game.turn < 8 and cover < 25:
        _say(game, "first_cover", "Don't stand about. Find a ditch, a wall, anything - and get in it.", mate)
        return
    # bleeding without a dressing
    if p.body.wounds and p.body.bleed_rate() > 0.8 and not p.__dict__.get("coach_bleed", 0) > game.turn:
        p.coach_bleed = game.turn + 40
        _say(game, "bleed", "You're bleeding. B - a dressing, now, while you can still use your hands.")
        return
    # walking into the open with plenty in sight
    seen = len([e for e in (p.visible or ()) if getattr(e, "vt", None) is None and getattr(e, "alive", True)])
    if seen >= 3 and exposed and p.moved_turn >= game.turn - 1:
        _say(game, "open_ground", "Too many eyes on this ground. Bound to cover; don't walk it.")
