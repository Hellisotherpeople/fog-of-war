"""Weather fronts, exposure and the ground they leave behind.

The same conditions govern soldiers, supply roads, aircraft and ships. State lives
on the game/map so saving or leaving a sector doesn't dry it out.
"""
from __future__ import annotations

import math
import random
import time

from . import tiles as T

# precipitation, wind (m/s), visibility multiplier, noise masking (dB)
PROFILES = {"clear": (0, 3, 1, 0), "overcast": (0, 5, .92, 0),
            "rain": (.65, 7, .7, 6), "storm": (1, 17, .4, 14),
            "snow": (.45, 6, .6, 3), "blizzard": (.9, 18, .18, 12),
            "fog": (0, 1, .28, -2), "sandstorm": (0, 19, .2, 12)}


def state(game):
    st = game.__dict__.get("weather_state")
    if st is None:
        rain, wind, _, _ = PROFILES.get(game.weather, PROFILES["clear"])
        st = game.weather_state = dict(kind=game.weather, rain=rain, wind=wind, intensity=.7,
                                        next=game.turn + 900, last=game.turn, sea=wind / 4,
                                        rng=random.Random(game.sector.seed if game.sector else 1))
    return st


def precipitation(game):
    return PROFILES.get(game.weather, PROFILES["clear"])[0] * state(game)["intensity"]


def visibility(game):
    base = PROFILES.get(game.weather, PROFILES["clear"])[2]
    return 1 - (1 - base) * (.55 + .45 * state(game)["intensity"])


def masking(game):
    return PROFILES.get(game.weather, PROFILES["clear"])[3] * state(game)["intensity"]


def sheltered(game, a):
    if a.vehicle is not None:
        return not a.vehicle.vt.open_top
    m = game.map
    if game.__dict__.get("domain") == "aboard":
        ab = game.aboard or {}
        if ab.get("kind") == "plane":
            return True
        deck = ab.get("decks", {}).get(ab.get("deck"))
        if deck is not None:
            return not deck.weather
    return m is not None and m.in_bounds(a.x, a.y) and T.FLOOR[m.t[a.x, a.y]] and \
        not a.__dict__.get("z", 0) > 0


def exposure(game, a):
    return .12 if sheltered(game, a) else 1.0


def sea_state(game):
    return max(0.0, min(6.0, state(game)["sea"]))


def flight_factor(game):
    """Operational flying capacity: storms shut fields and carrier decks."""
    return max(.0, min(1., (visibility(game) - .22) / .65))


def road_factor(game):
    ground = getattr(game.map, "weather_ground", {}) if game.map is not None else {}
    return max(.35, 1 - .35 * ground.get("wet", 0) - .25 * ground.get("snow", 0) -
               .2 * (1 - visibility(game)))


def aim_penalty(game, a, distance):
    return exposure(game, a) * (state(game)["wind"] / 60 * min(2, distance / 50) +
                                precipitation(game) * .25)


def tick(game):
    st = state(game)
    dt = game.turn - st["last"]
    if dt < 30:
        return
    st["last"] = game.turn
    rng = st["rng"]                         # weather cannot consume combat's random sequence
    if game.turn >= st["next"]:
        weights = dict(game.theatre.get("weather", {"clear": 1}))
        climate = game.theatre.get("climate")
        if climate == "winter":
            weights["blizzard"] = max(.05, weights.get("snow", 0) * .25)
        elif climate != "desert":
            weights["storm"] = max(.03, weights.get("rain", 0) * .3)
        weights[game.weather] = weights.get(game.weather, .1) + sum(weights.values()) * .8
        game.weather = rng.choices(list(weights), list(weights.values()))[0]
        st["next"] = game.turn + rng.randint(1200, 3600)
        st["intensity"] = rng.uniform(.45, 1)
        game.wind = rng.choice(((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)))
    if game.weather != st["kind"]:
        st["kind"] = game.weather
        game.msg({"clear": "The sky clears; the ground will take longer to dry.",
                  "overcast": "Cloud closes over the sun.", "rain": "Rain rattles on roofs and helmets.",
                  "storm": "A squall arrives: heavy rain, gusts and rolling thunder.",
                  "snow": "Snow begins to settle.", "blizzard": "Blowing snow swallows the horizon.",
                  "fog": "Fog gathers in the low ground.",
                  "sandstorm": "Wind drives sand into clothes and weapons."}.get(game.weather, "The weather turns."),
                 "info")
        game.__dict__.pop("_moon_cache", None)
        game.update_view_range()
    wind = PROFILES.get(game.weather, PROFILES["clear"])[1] * (.6 + .4 * st["intensity"])
    st["wind"] += (wind - st["wind"]) * min(1, dt / 180)
    if not any(game.wind) and st["wind"] >= 2:
        game.wind = (1, 0)
    st["sea"] += (st["wind"] / 4 - st["sea"]) * min(1, dt / 900)
    if game.weather == "storm" and rng.random() < min(.5, dt / 180):
        p = game.player
        if p is not None:
            game.emit_sound(p.x, p.y, 55, "thunder", "thunder rolling overhead", None, None)
    ground_tick(game, dt)
    game.strategic.weather_transport = road_factor(game)


def ground_tick(game, dt):
    m = game.map
    if m is None or game.__dict__.get("domain", "land") != "land":
        return
    from .thermal import ambient
    ground = m.__dict__.setdefault("weather_ground", dict(wet=0., snow=0., changed={}))
    rain = precipitation(game)
    snowy = game.weather in ("snow", "blizzard")
    ground["wet"] = max(0., min(1., ground["wet"] + dt * (rain / 1800 if rain and not snowy else -1 / 14400)))
    ground["snow"] = max(0., min(1., ground["snow"] + dt * (rain / 3600 if snowy else
                                                         -max(0, ambient(game)) / 86400)))
    rng = state(game)["rng"]
    changes = ground["changed"]
    refreshed = False
    for pos, (original, overlay) in list(changes.items()):
        if m.t[pos] != overlay:
            del changes[pos]                 # a shell or a builder changed it: never restore that terrain
        elif (overlay == T.ID["snow_drift"] and ground["snow"] < .12) or \
                (overlay != T.ID["snow_drift"] and ground["wet"] < .2):
            m.set(*pos, T.DEFS[original].key)
            del changes[pos]
            refreshed = True
    for _ in range(min(500, max(12, int(dt * m.w * m.h / 90000)))):
        pos = rng.randrange(m.w), rng.randrange(m.h)
        tid = int(m.t[pos])
        key = T.DEFS[tid].key
        overlay = None
        if ground["snow"] > .2 and key in ("grass", "dirt", "snow", "road", "plowed"):
            overlay = "snow_drift"
        elif ground["wet"] > .4 and key in ("dirt", "plowed", "grass", "grass_autumn"):
            overlay = "waterlogged" if ground["wet"] > .8 else "mud"
        elif ground["wet"] > .65 and key in ("crater", "trench", "foxhole"):
            overlay = "flooded_trench"
        if overlay:
            changes[pos] = (tid, T.ID[overlay])
            m.set(*pos, overlay)
            refreshed = True
    if refreshed:
        m.refresh()


def description(game):
    st = state(game)
    wind = "still" if st["wind"] < 2 else "breeze" if st["wind"] < 7 else "strong wind" if st["wind"] < 14 else "gale"
    return f"{game.weather}, {wind}"


def particles(game, cam):
    """Sparse precipitation in visible open ground, without consuming simulation randomness."""
    if game.weather not in ("rain", "storm", "snow", "blizzard", "sandstorm"):
        return
    if game.__dict__.get("domain") == "aboard" and sheltered(game, game.player):
        return
    m = game.map
    snow = game.weather in ("snow", "blizzard")
    dust = game.weather == "sandstorm"
    ch = "." if snow or dust else ("/" if game.wind[0] < 0 else "\\")
    col = (210, 218, 228) if snow else (190, 163, 115) if dust else (118, 158, 185)
    phase = int(time.monotonic() * (5 if snow else 10))
    rng = random.Random(phase)
    count = int(cam.vw * cam.vh * .025 * state(game)["intensity"])
    for _ in range(count):
        x, y = cam.x0 + rng.randrange(cam.vw), cam.y0 + rng.randrange(cam.vh)
        if m.in_bounds(x, y) and m.visible[x, y] and not T.FLOOR[m.t[x, y]] and \
                (x, y) not in game.soldier_at and (x, y) not in game.vehicle_at:
            yield x, y, ch, col
