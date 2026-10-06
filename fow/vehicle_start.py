"""Explicit vehicle assignments at enlistment, independent of random battlefield spawns."""
from __future__ import annotations

from . import crew
from .data.vehicles import VEHICLES
from .data.theatres import theatre_year


def available(theatre=None):
    # Landing craft require a water battlefield; the land creator offers amphibians
    # and all ground vehicles/guns, including captured examples.
    return sorted((v for v in VEHICLES.values() if v.water != "water" and crew.stations(v)
                   and (theatre is None or v.years[0] <= theatre_year(theatre) < v.years[1])),
                  key=lambda v: (v.vtype, v.name))


def seats(vid):
    vt = VEHICLES[vid]
    return [(crew.name(vt, s), s) for s in crew.stations(vt)] + (
        [("Passenger", "passenger")] if vt.seats else [])


def prepare(game, role):
    """Provide an actual assigned machine even if the sector happened to spawn none."""
    vid = game.setup.get("vehicle")
    if not vid and role != "tank_crew":
        return
    from .spawn import pick_vehicle, edge_band_point, spot_and_facing
    if not vid:
        if any(v.active and v.side == game.player_side and v.vt.vtype in ("tank", "td", "ltank", "spg")
               for v in game.vehicles):
            return
        vid = pick_vehicle(game.rng, game.player_nation, game.year, "tank", include_zero=True)
        if not vid:
            raise ValueError("No tank model is available for this army and date. Choose a vehicle in the creator.")
    vt = VEHICLES.get(vid)
    if vt is None or vt not in available(game.theatre):
        raise ValueError("The chosen ground vehicle is unavailable at this battle date.")
    station = game.setup.get("station")
    if station and station not in dict((value, name) for name, value in seats(vid)):
        raise ValueError("That position does not exist in the chosen vehicle.")
    candidates = [v for v in game.vehicles if v.active and v.side == game.player_side and v.vt.id == vid]
    if candidates:
        v = candidates[0]
        if v.squad is None:
            from .ai import Squad, Order
            sq = Squad(game.player_side, game.player_nation, "atgun" if vt.static else "tank", vt.name + " crew")
            sq.vehicles, v.squad = [v], sq
            sq.initial = max(1, v.crew)
            sq.order = Order("hold", target=(v.x, v.y))
            game.squads.append(sq)
        game._starting_vehicle = v
        return
    from .entities import Vehicle
    from .ai import Squad, Order
    edge = game.home_edge(game.player_side) or "W"
    x, y = edge_band_point(game, edge, game.rng, depth=(5, 16))
    face = {"W": 2, "E": 6, "N": 4, "S": 0}[edge]
    spot, face = spot_and_facing(game, x, y, vt, radius=12, facing=face)
    if spot is None:
        # Search open ground across the sector, without erasing occupied terrain.
        for x in range(5, game.map.w - 5, 12):
            for y in range(5, game.map.h - 5, 12):
                spot, face = spot_and_facing(game, x, y, vt, radius=2, facing=face)
                if spot:
                    break
            if spot:
                break
    if spot is None:
        raise ValueError(f"No open ground for the {vt.name} in this sector; choose another battle.")
    v = Vehicle(vid, game.player_side, game.player_nation, *spot, facing=face)
    sq = Squad(game.player_side, game.player_nation, "atgun" if vt.static else "tank", vt.name + " crew")
    sq.vehicles, v.squad = [v], sq
    sq.initial = max(1, v.crew)
    sq.order = Order("hold", target=spot)
    game.squads.append(sq)
    game.add_vehicle(v)
    game._starting_vehicle = v


def assign(game, p, notes):
    v = game.__dict__.pop("_starting_vehicle", None)
    if v is None or not game.setup.get("vehicle"):
        return
    station = game.setup.get("station") or ("commander" if "commander" in crew.stations(v.vt)
                                           else crew.stations(v.vt)[0])
    old = p.vehicle
    if old is not v:
        if old is not None:
            if p in old.crew_actors:
                old.crew_actors.remove(p)
                old.crew = max(0, old.crew - 1)
                old.player_crewed, old.player_station = False, None
            if p in old.passengers:
                old.passengers.remove(p)
        game.remove_from_map(p)
        p.vehicle = v
    if p.squad is not v.squad:
        old_sq = p.squad
        if old_sq is not None:
            if p in old_sq.members:
                old_sq.members.remove(p)
            if old_sq.leader is p:
                old_sq.leader, old_sq.player_led = None, False
        p.squad = v.squad
        v.squad.members.append(p)
    # The assignment replaces an anonymous crew member; it doesn't add an extra man.
    if station == "passenger":
        if p in v.crew_actors:
            v.crew_actors.remove(p)
        if len(v.passengers) >= v.vt.seats:
            rider = v.passengers.pop()
            from .spawn import place
            rider.vehicle = None
            place(game, rider, v.x, v.y, 10)
        if p not in v.passengers:
            v.passengers.append(p)
        v.player_crewed, v.player_station = False, None
        v.ai["player_passenger_assignment"] = True
    else:
        if p in v.passengers:
            v.passengers.remove(p)
        if p not in v.crew_actors:
            v.crew_actors.append(p)
        v.crew = max(1, v.crew)
        v.player_crewed, v.player_station = True, station
    v.abandoned = False
    v.ai.pop("supply_run", None)
    p.x, p.y = v.x, v.y
    if station == "commander":
        v.squad.leader, v.squad.player_led = p, True
    elif v.squad.leader is p:
        v.squad.leader, v.squad.player_led = None, False
    notes[:] = [n for n in notes if not n.startswith(("You command a ", "You're the layer on a "))]
    notes.append(f"Assigned vehicle: {v.vt.name}. Position: {crew.name(v.vt, station)}. "
                 f"{crew.seat_help(v, station) if station != 'passenger' else 'The crew handles the vehicle.'} "
                 "Press e to change seats or get out.")
