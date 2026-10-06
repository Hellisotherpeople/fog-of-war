"""An explicit enlistment assignment must survive random spawns and scenario setup."""
import pickle
from unittest.mock import patch
import pytest
import tcod

from test_smoke import Game, FakeApp
from fow import crew, vehicle_start
from fow.ui import CreatorState
from fow.constants import SCREEN_W, SCREEN_H


@pytest.mark.parametrize("vid,station", [
    ("m4", "driver"), ("m4", "commander"), ("m4", "gunner"), ("m4", "loader"), ("m4", "mg1"),
    ("gmc", "driver"), ("gmc", "passenger"), ("jeep", "driver"), ("m3_ht", "passenger"),
    ("m1_57mm", "gunner"), ("lvt", "driver"), ("tiger", "driver"),
])
def test_exact_vehicle_and_seat(vid, station):
    g = Game("bocage44", "usa", seed=25, setup=dict(vehicle=vid, station=station,
             scenario="random", battlefield="standard", fair=True))
    p, v = g.player, g.player.vehicle
    assert v and v.vid == vid
    assert v.active and p.pos == (v.x, v.y)
    assert p.squad is v.squad and p in v.squad.members
    assert p not in g.soldier_at.values()
    assert all(g.vehicle_at.get(xy) is v for xy in v.cells())
    if station == "passenger":
        assert p in v.passengers and p not in v.crew_actors and not v.player_crewed
    else:
        assert crew.player_seat(v) == station and p in v.crew_actors
        assert station in crew.manned(v) and not crew.ai_manned(v, station)
        assert v.crew <= v.vt.crew
    loaded = pickle.loads(pickle.dumps(g))
    assert loaded.player.vehicle.vid == vid
    assert crew.player_seat(loaded.player.vehicle) == (None if station == "passenger" else station)
    for _ in range(3):
        g.world_turn()
    assert g.player.vehicle is v


def test_tank_role_receives_vehicle_when_sector_has_none():
    from fow.spawn import create_player
    g = Game("bocage44", "usa", "regiment_commander", seed=25, setup=dict(battlefield="standard"))
    g.vehicles.clear()
    g.vehicle_at.clear()
    for sq in g.squads:
        sq.vehicles.clear()
    vehicle_start.prepare(g, "tank_crew")
    p, _ = create_player(g, "usa", "tank_crew")
    assert p.role == "tank_crew" and p.vehicle and p.vehicle.active


def test_creator_filters_positions_dates_and_propagates_assignment():
    app = FakeApp()
    creator = CreatorState(app)
    creator.v.update(side="allies", theatre="bocage44", nation="usa", vehicle="m4", station="driver")
    assert {x[1] for x in creator.options("station")} == {None, "driver", "commander", "gunner", "loader", "mg1"}
    assert "m24" not in {x[1] for x in creator.options("vehicle")}
    creator.render(tcod.console.Console(SCREEN_W, SCREEN_H, order="F"))
    with patch.object(app, "start_game", create=True) as start:
        creator.start()
    assert start.call_args.args[3]["vehicle"] == "m4"
    assert start.call_args.args[3]["station"] == "driver"
    creator.v["vehicle"] = "jeep"
    creator.v["station"] = "loader"
    creator._fixup("vehicle")
    assert creator.v["station"] is None
    creator.v["service"] = "air"
    creator._fixup("service")
    assert creator.v["vehicle"] is None


def test_invalid_explicit_seat_fails_clearly():
    with pytest.raises(ValueError, match="position"):
        Game("bocage44", "usa", seed=25, setup=dict(vehicle="jeep", station="loader", battlefield="standard"))
