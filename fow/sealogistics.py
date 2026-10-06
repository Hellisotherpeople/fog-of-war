"""Oil and workshop ships transfer finite stores when a ship comes alongside."""
import math


def tick(ss):
    from .weather import sea_state
    if sea_state(ss.game) > 3:
        return
    for donor in ss.ships:
        if not donor.alive or donor.kn > 6 or not donor.st.get("cargo"):
            continue
        stock = donor.ai.setdefault("cargo", dict(donor.st["cargo"]))
        for ship in ss.ships:
            if ship is donor or not ship.alive or ship.side != donor.side or ship.kn > 6 or ship.depth or \
                    math.hypot(ship.x - donor.x, ship.y - donor.y) > 3:
                continue
            fuel = min(100 - ship.fuel, stock.get("fuel", 0), 3)
            repair = min(ship.st["hp"] - ship.hp, stock.get("parts", 0), ship.st["hp"] * .003)
            if fuel > 0:
                ship.fuel += fuel
                stock["fuel"] -= fuel
            if repair > 0 and ship.fires == 0:
                ship.hp += repair
                stock["parts"] -= repair
                ship.flood = max(0, ship.flood - .3)
            if (fuel > 0 or repair > 0) and ship.player and not ship.ai.get("alongside_reported"):
                ship.ai["alongside_reported"] = True
                ss.game.msg(f"Alongside {donor.name}: hoses and repair boats are across. Keep below six knots.", "info")
