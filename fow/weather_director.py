"""Fronts with a warning, and the light discipline that goes with them.

Weather already changes; this gives it a shape.  A front is seen coming - a glass falling, cloud building
in the west, the birds going quiet - and then it arrives with the ground it leaves behind.  Night and first
light are handled too: stand-to, sentries up, weapons ready, before the light changes and again at dusk.

None of it is scripted to the player.  Both sides live under the same sky; the warning is a real few minutes
in which a wise man gets his kit under cover and his section in a hole.
"""
from __future__ import annotations

DANGER = {"storm": "a squall", "blizzard": "blowing snow", "sandstorm": "a sandstorm", "fog": "fog",
          "rain": "rain", "snow": "snow"}
WARN = {
    "storm": ["The glass is falling. There's weather coming.", "Thunderheads building in the west.",
              "The wind's backing. A squall on the way."],
    "blizzard": ["The sky's gone flat and the wind has teeth. Snow coming, heavy.",
                 "The glass is down hard. Blizzard weather."],
    "fog": ["The low ground is hazing over. Fog coming.", "Damp and still. Fog by the hour."],
    "rain": ["Cloud building. Rain coming.", "The glass is falling. Get your kit under cover."],
    "snow": ["It's turning cold and flat. Snow coming.", "The sky's low. Snow."],
    "sandstorm": ["The wind's up and the dust with it. Sandstorm coming."],
}
STAND_HOURS = (5, 19)       # first and last light, roughly


def state(game) -> dict:
    st = game.__dict__.get("fronts")
    if st is None:
        st = game.__dict__["fronts"] = dict(warned=0.0, front=None, stand=0.0)
    return st


def tick(game) -> None:
    if game.map is None or game.domain != "land":
        return
    if game.turn % 60:
        return
    st = state(game)
    from . import weather
    w = weather.state(game)
    # a front is scheduled: warn, then it arrives
    if st["front"] is None and game.turn < w["next"] - 600:
        pass
    elif st["front"] is None and game.turn >= w["next"] - 600:
        st["front"] = w["next"]
        kind = game.weather
        if kind in DANGER:
            game.msg(game.rng.choice(WARN.get(kind, ["Weather coming."])), "info")
            from . import diary
            diary.entry(game, "weather", "The weather is turning.")
    if st["front"] is not None and game.turn >= w["next"]:
        st["front"] = None
    # stand-to
    hr = game.now().hour
    key = game.now().toordinal() * 24 + hr
    if hr in STAND_HOURS and st["stand"] != key:
        st["stand"] = key
        stand_to(game, hr)
    # the light: night work is warned once, so a section can post its sentries
    if game.is_night() and st["warned"] < 1 and game.turn > 60:
        st["warned"] = 1
        p = game.player
        if p is not None and p.side == game.player_side:
            game.msg("Last light. Post the sentries and get the men down; the dark is the enemy's.", "info")


def stand_to(game, hour: int) -> None:
    """The section stands to: everyone up, sentries out, weapons ready, before the light changes."""
    p = game.player
    if p is None or not p.alive:
        return
    dawn = hour < 12
    from . import sleep
    woke = 0
    for a in game.near(p.x, p.y, 40, p.side):
        if a.ai.get("sleeping") is not None:
            sleep.wake(game, a, "order")
            woke += 1
        a.stance = 1 if dawn else a.stance
        a.ai["stand_to"] = game.turn + 900
    if game.player.squad is not None:
        for m in game.player.squad.members:
            m.ai["stand_to"] = game.turn + 900
    game.msg("Stand-to: the section is up, weapons off the ground, watching the light." if dawn else
             "Stand-to at last light. Sentries out; the rest stand by their weapons.", "info")
    if woke:
        game.msg(f"{woke} men shaken awake for it.", "info")
    from . import diary
    diary.entry(game, "stand_to", "Stood to before the light changed.")
