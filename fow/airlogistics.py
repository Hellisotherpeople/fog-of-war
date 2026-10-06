"""Transport sorties bring a finite load from one sector to another."""
from __future__ import annotations

import math


def load(game, base, plane):
    from .sustain import stores, take
    from .data.vehicles import AIRCRAFT
    stock = stores(base, plane.side)
    cargo = min(AIRCRAFT[plane.at_id].get("cargo", 60), int(min(stock[k] for k in ("food", "medical", "ammo")) * 3))
    plane.ai["cargo"] = cargo
    for k in ("food", "medical", "ammo"):
        take(base, plane.side, k, cargo / 3)
    return cargo


def drop_supplies(ss, plane):
    from .sustain import deliver
    from .weather import state, visibility
    m = ss.mission
    cargo = plane.ai.get("cargo", 0)
    if cargo <= 0:
        return False
    tx, ty = m["target_pt"]
    if math.hypot(plane.x - tx, plane.y - ty) > 8 or not 80 <= plane.alt <= 600 or plane.kmh > 300:
        ss.game.msg("Supply drop: get within 800 metres, at 80-600 metres altitude and below 300 km/h.", "info")
        return False
    dest = ss.game.strategic.at(*m["target_sector"])
    if dest is None or dest.control != plane.side:
        ss.game.msg("The dropping zone is no longer held by our troops. Bring the load home.", "warn")
        return False
    drift = state(ss.game)["wind"] * plane.alt / 6000
    wx, wy = ss.game.wind
    norm = max(1, math.hypot(wx, wy))
    miss = math.hypot(plane.x + wx * drift / norm - tx, plane.y + wy * drift / norm - ty)
    recovered = cargo * max(.15, 1 - miss / 12) * (.5 + .5 * visibility(ss.game))
    for k in ("food", "medical", "ammo"):
        deliver(dest, plane.side, k, recovered / 3)
    plane.ai["cargo"] = 0
    plane.ai["role"] = "home"
    plane.ai["wp"] = plane.home
    m["stage"] = "home"
    m["delivered"] = recovered
    m["text"] = f"Stores dropped at {dest.name}. Bring the transport home."
    ss.game.msg("Parachutes open behind you. Food, ammunition and dressings are down; wind scatters some of the load.",
                "good")
    return True
