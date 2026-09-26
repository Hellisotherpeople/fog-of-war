"""Cold and heat.

Moscow in December 1941 was thirty below; the desert at noon was forty above and at
night near freezing; the jungle never dried.  Your core temperature follows the air,
your clothes, whether you're wet, whether you're moving, and whether there's a roof
or a tank hull over you.  Cold brings shivering hands, then stumbling, then sleep;
frostbite takes fingers and toes.  Heat brings exhaustion, then collapse.
"""
from __future__ import annotations

import math

from . import tiles as T

# (day, night) air temperature, degrees C, by theatre climate
CLIMATE = {"winter": (-12, -24), "summer": (23, 12), "autumn": (8, 1), "desert": (36, 9), "tropical": (32, 24),
           "mediterranean": (27, 16), "volcanic": (21, 15)}
THEATRE_TWEAK = {"moscow41": -8, "uranus42": -4, "don43": -6, "stalingrad42": -2, "bastogne44": 2, "karelia44": -6,
                 "kohima44": -4}


def ambient(game) -> float:
    from .senses import daylight
    day, night = CLIMATE.get(game.theatre.get("climate", "summer"), (18, 10))
    d = daylight(game)
    t = night + (day - night) * d
    t += THEATRE_TWEAK.get(game.theatre.get("id", ""), 0)
    t += {"rain": -4, "snow": -3, "fog": -2, "sandstorm": 3, "overcast": -1}.get(game.weather, 0)
    return t


def insulation(a) -> float:
    """How warm the clothes are (1 = a wool uniform)."""
    ins = 1.0
    body = a.invent.slots.get("body") if hasattr(a, "invent") else None
    if body is not None:
        ins += body.t.get("warmth", 0) * 0.8 or 0.3
    for it in a.inv:
        if it.t.kind == "armor" and it.t.get("warmth") and it is not body:
            ins += it.t.warmth * 0.25        # carried, not worn: a bit, if you put it round you
    if a.helmet is not None:
        ins += 0.1
    return ins


def feels_like(game, a) -> float:
    m = game.map
    t = ambient(game)
    if a.vehicle is not None:
        t = max(t, t + 10)                    # out of the wind, engine heat
    elif m.in_bounds(a.x, a.y) and T.FLOOR[m.t[a.x, a.y]]:
        t = t + 8 if t < 15 else t - 4       # a roof: warmer in the cold, cooler in the sun
    fire = m.fire[max(0, a.x - 2):a.x + 3, max(0, a.y - 2):a.y + 3] if m.in_bounds(a.x, a.y) else None
    if fire is not None and fire.size and fire.max() > 0:
        t += 15
    return t


def update(game, a, dt=30):
    """dt seconds of weather on a man."""
    b = a.body
    if not hasattr(b, "temp"):
        b.temp, b.wet, b.frost = 37.0, 0.0, 0.0
    m = game.map
    air = feels_like(game, a)
    # wet: rain, snow, water
    if m.in_bounds(a.x, a.y) and m.water[a.x, a.y] >= 1 and a.vehicle is None:
        b.wet = 100.0 if m.water[a.x, a.y] >= 2 or a.stance == 2 else max(b.wet, 60.0)
    elif game.weather in ("rain", "snow") and a.vehicle is None and not (m.in_bounds(a.x, a.y) and T.FLOOR[m.t[a.x, a.y]]):
        # rain soaks you; wet snow near freezing does too; dry powder at thirty below barely does
        rate = 1.5 if game.weather == "rain" else (0.8 if air > -4 else 0.05)
        b.wet = min(85.0, b.wet + rate * dt / 30)
    else:
        b.wet = max(0.0, b.wet - (0.4 + max(0, air) * 0.05) * dt / 30)
    ins = insulation(a) * (1 - 0.6 * b.wet / 100)
    moving = a.moved_turn >= game.turn - 3
    work = 4.0 if moving else 0.0
    if getattr(a, "stamina", 100) < 60 and moving:
        work += 3.0
    # the body's balance: comfortable between about 8 and 26 degrees felt, clothed
    felt = air + 7 * ins + work - (4 if a.stance == 2 and air < 5 else 0)
    target = 37.0
    if felt < 12:
        target = 37.0 - (12 - felt) * 0.35
    elif felt > 28:
        target = 37.0 + (felt - 28) * 0.18 * (1.4 if a.carried_weight() > 25 else 1.0)
    rate = 0.006 * dt / 30 * (2.0 if b.wet > 50 and felt < 12 else 1.0)
    b.temp += max(-rate * 3, min(rate * 3, (target - b.temp) * 0.08 * dt / 30))
    b.temp = max(24.0, min(43.0, b.temp))
    # frostbite in hard cold: fingers and toes
    if air < -8 and (b.temp < 36.3 or b.wet > 40) and a.vehicle is None:
        b.frost = min(100.0, b.frost + (0.4 + b.wet / 100) * dt / 30)
        if b.frost > 60 and game.rng.random() < 0.02:
            part = game.rng.choice(("l_arm", "r_arm", "l_leg", "r_leg"))
            b.hp[part] = max(1, b.hp[part] - 1)
    else:
        b.frost = max(0.0, b.frost - 0.1 * dt / 30)
    events = []
    if b.temp < 30.0:
        b.dead = True
        b.cause = "the cold"
    elif b.temp < 32.0 and game.rng.random() < 0.05:
        b.unconscious = max(b.unconscious, 60)
        events.append("collapse_cold")
    elif b.temp > 41.5 and game.rng.random() < 0.08:
        b.unconscious = max(b.unconscious, 90)
        events.append("collapse_heat")
    if b.temp > 39.0 and hasattr(a, "stamina"):
        a.stamina = max(0.0, a.stamina - 1.5 * dt / 30)
    return events


def aim_penalty(a) -> float:
    b = a.body
    t = getattr(b, "temp", 37.0)
    return (0.6 if t < 35.5 else 0) + (0.8 if t < 34 else 0) + (0.4 if getattr(b, "frost", 0) > 50 else 0) + \
        (0.3 if t > 39.5 else 0)


def speed_mult(a) -> float:
    t = getattr(a.body, "temp", 37.0)
    m = 1.0
    if t < 34.5:
        m -= 0.15
    if t < 33:
        m -= 0.2
    if t > 39.5:
        m -= 0.15
    return m


def words(a) -> tuple[str, tuple]:
    t = getattr(a.body, "temp", 37.0)
    if t < 32:
        return "Freezing to death", (120, 160, 255)
    if t < 34:
        return "Hypothermic - clumsy, confused", (140, 180, 255)
    if t < 35.5:
        return "Shivering hard", (170, 200, 255)
    if t < 36.4:
        return "Cold", (200, 220, 255)
    if t > 40.5:
        return "Heatstroke", (255, 90, 60)
    if t > 39.3:
        return "Heat exhaustion", (255, 140, 80)
    if t > 38.0:
        return "Overheating", (255, 190, 110)
    return "Comfortable", (150, 210, 150)
