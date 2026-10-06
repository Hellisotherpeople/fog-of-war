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
             captured_vehicle=vid == "tiger", scenario="random", battlefield="standard", fair=True))
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


def test_tiger_ii_defaults_to_germany_and_a_compatible_battle():
    from fow.data.theatres import THEATRES, theatre_year
    app = FakeApp()
    creator = CreatorState(app)
    creator.v.update(vehicle="kingtiger", station="driver")
    creator._fixup("vehicle")
    assert (creator.v["nation"], creator.v["side"]) == ("germany", "axis")
    with patch.object(app, "start_game", create=True) as start:
        for _ in range(30):
            creator.start()
            th, nat, role, setup = start.call_args.args
            assert nat == "germany" and theatre_year(THEATRES[th]) >= 1944.5
            assert setup["vehicle"] == "kingtiger" and not setup["captured_vehicle"]
    g = Game(th, nat, role, seed=25, setup={**setup, "battlefield": "standard"})
    assert g.player.nation == "germany" and g.player.vehicle.vid == "kingtiger"
    assert crew.player_seat(g.player.vehicle) == "driver"
    assert not g.player.vehicle.ai.get("captured")


def test_every_normal_vehicle_resolves_from_random_creator_without_wrong_side():
    from fow.data.vehicles import VEHICLES
    app = FakeApp()
    creator = CreatorState(app)
    with patch.object(app, "start_game", create=True) as start:
        for _, vid, _ in creator.options("vehicle"):
            if not vid:
                continue
            creator.v.update(vehicle=vid, nation="random", side="random", theatre="random")
            creator.start()
            th, nat, _, setup = start.call_args.args
            assert nat in VEHICLES[vid].nations, (vid, nat)
            assert vehicle_start.assignments(vid, theatre=th, nation=nat)
            assert setup["vehicle"] == vid


def test_captured_equipment_is_explicit_and_retains_crew_nation():
    app = FakeApp()
    creator = CreatorState(app)
    creator.v.update(nation="usa", side="allies", theatre="bocage44", captured_vehicle=True,
                     vehicle="tiger", station="driver")
    creator._fixup("vehicle")
    assert creator.v["nation"] == "usa"
    with patch.object(app, "start_game", create=True) as start:
        creator.start()
    th, nat, role, setup = start.call_args.args
    g = Game(th, nat, role, seed=25, setup={**setup, "battlefield": "standard"})
    assert g.player.nation == "usa" and g.player.vehicle.ai["captured"]
    assert g.player.vehicle.ai["fam"] < 1
    with pytest.raises(ValueError, match="captured equipment"):
        Game(th, nat, role, seed=25, setup={**setup, "captured_vehicle": False, "battlefield": "standard"})
    creator.v["captured_vehicle"] = False
    creator._fixup("captured_vehicle")
    assert creator.v["nation"] == "germany" and creator.v["side"] == "axis"


def test_changing_nation_clears_foreign_model_but_legitimate_operators_stay():
    creator = CreatorState(FakeApp())
    creator.v.update(vehicle="m4", nation="uk", side="allies", theatre="bocage44")
    creator._fixup("vehicle")
    assert creator.v["nation"] == "uk"
    creator.v.update(vehicle="kingtiger", station="driver")
    creator._fixup("vehicle")
    assert creator.v["nation"] == "germany"
    creator.v["nation"] = "uk"
    creator._fixup("nation")
    assert creator.v["vehicle"] is None and creator.v["station"] is None
    assert not vehicle_start.assignments("kingtiger", nation="romania")
