"""Weather, the home front, counterintelligence and finite supplies, using real game state.

    python tests/test_expansion.py       (also collected by pytest)
"""
from __future__ import annotations

import os
import random
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_smoke import FakeApp, Game  # establishes isolated saves and dummy SDL drivers

from fow import tiles as T
from fow.entities import Actor, Item, Vehicle
from fow import weather as W, sustain as S


def game():
    return Game("kursk43", "ussr", seed=37, setup={"battlefield": "standard"})


def rear(g, side):
    st = g.strategic
    for delta in (-24, 24):
        xy = (st.w // 2, st.h // 2 + delta) if st.att_from in ("N", "S") else \
            (st.w // 2 + delta, st.h // 2)
        s = st.at(*xy, create=True)
        if s.playable and s.control == side:
            return s
    raise AssertionError("No inland rear sector on this side")


def test_weather_changes_ground_and_survives_saves():
    g = game()
    from fow.gamemap import GameMap
    g.map = GameMap(32, 32, 1)
    g.weather = "storm"
    W.state(g)["intensity"] = 1.
    W.ground_tick(g, 1800)
    assert g.map.weather_ground["wet"] == 1
    assert (g.map.t == T.ID["waterlogged"]).any()
    pos = next(iter(g.map.weather_ground["changed"]))
    g.map.set(*pos, "crater")               # a shell hole must never revert to the old grass
    wet_cost = T.COST[T.ID["waterlogged"]]
    assert wet_cost > T.COST[T.ID["grass"]]
    g.weather = "clear"
    W.ground_tick(g, 30)
    assert g.map.weather_ground["wet"] > .9 and g.map.t[pos] == T.ID["crater"]
    g._save_map()
    restored = g._load_map(g.sector)
    assert restored.weather_ground == g.map.weather_ground
    g.map = restored
    W.ground_tick(g, 15000)
    assert not g.map.weather_ground["changed"]
    assert g.map.t[pos] == T.ID["crater"]
    assert (g.map.walk == T.WALK[g.map.t]).all()
    g.weather = "blizzard"
    W.ground_tick(g, 3600)
    assert (g.map.t == T.ID["snow_drift"]).any()
    assert W.flight_factor(g) == 0 and W.visibility(g) < .2


def test_shelter_waterproof_kit_and_weather_audio():
    from fow.thermal import update
    from fow.audio import Bank
    import numpy as np
    g = game()
    p = g.player
    g.weather = "storm"
    W.state(g)["intensity"] = 1.
    g.map.set(p.x, p.y, "grass")
    g.map.refresh()
    p.body.temp, p.body.wet, p.body.frost = 37., 0., 0.
    update(g, p, 60)
    wet = p.body.wet
    assert wet > 0
    p.body.wet = 0
    p.invent.slots["body"] = Item("rain_cape")
    update(g, p, 60)
    assert 0 < p.body.wet < wet
    g.map.set(p.x, p.y, "floor_wood")
    g.map.refresh()
    p.body.wet = 30
    update(g, p, 60)
    assert p.body.wet < 30 and W.sheltered(g, p)
    bank = Bank()
    for samples in (bank.s["thunder"][0], bank.loops["rain"], bank.loops["wind"]):
        assert np.isfinite(samples).all() and np.max(np.abs(samples)) > 0


def test_nearby_ammo_uses_real_feed_and_weapon_slots():
    from fow.nearby import ammo_match, gather, AMMO_PRIMARY, AMMO_SECONDARY, AMMO_BOTH
    from fow.data.items import ITEMS
    g = game()
    p = g.player
    p.invent.slots.update(primary=Item("thompson_m1a1"), secondary=None, holster=Item("m1911"))
    primary = Item(ITEMS["thompson_m1a1"].magtype, full=False)
    secondary = Item(ITEMS["m1911"].magtype)
    wrong = Item(ITEMS["mp40"].magtype)
    assert ammo_match(p, primary) == ("P", AMMO_PRIMARY)
    assert ammo_match(p, secondary) == ("S", AMMO_SECONDARY)
    assert not ammo_match(p, wrong)[0]
    from fow.data.items import ammo_id
    assert ammo_match(p, Item(ammo_id(ITEMS["m1911"].cal))) == ("P/S", AMMO_BOTH)
    g.map.visible[p.pos] = True
    g.map.items[p.pos] = [Item("ration"), primary, secondary, wrong]
    entry = next(e for e in gather(g)["Items"] if (e["x"], e["y"]) == p.pos)
    assert entry["color"] == AMMO_BOTH and entry["label"].startswith("[P]")
    assert any(n.startswith("[S]") for n in entry["names"])


def test_forced_wait_ignores_events_but_cancels_and_stops_at_death():
    from fow.play import Key, PlayState
    from fow.skysea_exit import to_land
    g = game()
    to_land(g, rear(g, g.player.side))
    app = FakeApp()
    ps = PlayState(app, g)
    app.states = [ps]
    ps.cmd_wait()
    assert any(o[1] == "forced" for o in ps.popups[-1].options)
    ps.popups.clear()
    p = g.player
    p.body.unconscious = 500
    p.suppression = 80
    start = g.turn
    ps.begin_wait("forced", 120)
    g.msg("Incoming fire and new orders!", "warn")
    assert ps._wait_stop() is None
    for _ in range(1000):
        if not ps.auto_wait:
            break
        ps.anim = ps.anim_next = 0
        ps.tick()
    assert g.turn == start + 120 and ps.wait is None, (g.turn, start, ps.wait)
    ps.begin_wait("forced", 3600)
    ps.on_key(Key(char="x"))
    assert ps.auto_wait == 0
    ps.begin_wait("forced", 3600)
    g.game_over = True
    ps._wait_tick()
    assert ps.auto_wait == 0 and ps.wait is None


def test_homefront_both_sides_civilians_capture_and_damage():
    from fow.skysea_exit import to_land
    from fow.homefront import FACILITIES, tick
    from fow.constants import other_side
    g = game()
    rears = {side: rear(g, side) for side in ("allies", "axis")}
    for side, s in rears.items():
        assert s.homefront["depth"] >= 16 and s.homefront["damage"] < .04
        assert len([k for k, _, ok in s.installations if k in FACILITIES and ok]) >= 3
        to_land(g, s)
        facilities = [r for r in g.map.gen_positions if r.get("homefront")]
        assert facilities, (side, s.installations)
        assert all(g.map.t[pos] == r["target_tile"] for r in facilities for pos in r["targets"])
        civilians = [a for a in g.actors if a.ai.get("civilian")]
        assert civilians
        assert all(a not in g.enemies_of(other_side(side)) for a in civilians)
        victim = civilians[0]
        kills = g.player.kills
        g.kill(victim, g.player)
        assert g.player.kills == kills and s.homefront["casualties"] == 1
        g._save_map()
        g.map = None
        to_land(g, s)
        assert victim not in g.actors
        rec = next(r for r in g.map.gen_positions if r.get("homefront") and r["kind"] != "hospital")
        for xy in rec["targets"]:
            g.map.set(*xy, "rubble")
        tick(g)
        assert rec["destroyed"]
        assert not any(k == rec["kind"] and sd == side and ok for k, sd, ok in s.installations)
        intact = [i[0] for i in s.installations if i[0] in FACILITIES and i[2]]
        stock = S.stores(s, side)
        old_ammo = stock["ammo"]
        captured = S.stores(s, other_side(side))["ammo"]
        g._save_map()
        g.strategic._capture(s, other_side(side))
        assert all([kind, other_side(side), True] in s.installations for kind in intact)
        assert stock["ammo"] == 0
        assert S.stores(s, other_side(side))["ammo"] == min(500, captured + old_ammo / 2)
        loaded = g._load_map(s)
        assert all(r["side"] == other_side(side) for r in loaded.gen_positions
                   if r.get("homefront") and not r.get("destroyed"))


def test_security_needs_evidence_and_can_detain_an_infiltrator():
    from fow import counterintel as CI
    from fow.skysea_exit import to_land
    g = game()
    to_land(g, rear(g, g.player.side))
    side = g.player.side
    assert not CI.investigate(g, side)
    CI.report(g, side, g.player.pos, 35, "wireless bearing")
    assert CI.investigate(g, side)
    st = CI.state(g, side)
    assert st["searches"] == 1 and st["patrols"]
    assert st["reports"][-1]["pos"] != g.player.pos
    # A stale bearing cannot dispatch another search.
    st["reports"][-1]["at"] = g.turn - 3601
    assert not CI.investigate(g, side)
    citizen = next(a for a in g.actors if a.ai.get("civilian"))
    assert not CI.examine(g, g.player, citizen) and citizen.state == "ok"
    # A rear installation attracts a real saboteur, with a position and cover identity.
    g.map.gen_positions.append(dict(kind="factory", side=side, x=20, y=20, targets=[(20, 20)]))
    CI.infiltrate(g, side)
    spy = next(a for a in g.actors if a.ai.get("covert"))
    assert spy in g.sector.civilians and spy not in g.enemies_of(side)
    with patch.object(g.rng, "random", return_value=0):
        assert CI.examine(g, g.player, spy)
    assert spy.state == "surrendered" and not spy.ai.get("covert")
    assert citizen.ai["civilian"] and citizen.state == "ok"
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "security.pkl")
        g.save(path)
        restored = Game.load(path)
        assert CI.state(restored, side)["heat"] == st["heat"]
        assert any(a.state == "surrendered" and a.role == "agent" for a in restored.actors)


def test_civilians_do_not_block_capture_and_can_cross_sectors_with_you():
    from fow.play import PlayState
    from fow.skysea_exit import to_land
    from fow.commander import update_objectives
    from fow.constants import other_side
    from fow.gamemap import Objective
    from fow.spawn import place
    g = game()
    to_land(g, rear(g, g.player.side))
    p = g.player
    civilian = next(a for a in g.actors if a.ai.get("civilian"))
    civilian.side = other_side(p.side)
    for a in list(g.actors):
        if a not in (p, civilian):
            g.remove_actor(a)
    g.vehicles = []
    g.vehicle_at = {}
    g.waves = []
    g.map.set(p.x + 1, p.y, "grass")
    g.map.set(p.x, p.y, "grass")
    g.map.refresh()
    g.remove_actor(civilian)
    assert place(g, civilian, p.x + 1, p.y, 0)
    app = FakeApp()
    ps = PlayState(app, g)
    app.states = [ps]
    hp = dict(civilian.body.hp)
    ps.do_move(1, 0)
    assert civilian.body.hp == hp and civilian.alive
    o = Objective("town square", p.x, p.y, 8)
    g.map.objectives = [o]
    update_objectives(g, 20)
    assert o.owner == p.side and not o.contested
    g.sector.control = other_side(p.side)
    g._battle_check()
    assert g.sector.control == p.side
    civilian.ai.update(following=True, needs=dict(hunger=72., thirst=50., infection=10.))
    previous = g.sector
    assert g.travel("E")
    assert civilian in g.actors and civilian in g.sector.civilians and civilian not in previous.civilians
    assert civilian.ai["civilian"] and civilian.ai["following"] and civilian.ai["needs"]["hunger"] >= 72
    assert civilian.squad is None


def test_supplies_limit_resupply_healing_repairs_and_fuel():
    from fow.actions import resupply
    from fow.medical import recover
    from fow.maintenance import _repair, JOBS
    from fow import vdamage
    from fow.skysea_exit import to_land
    from fow.ammo import sources
    g = game()
    to_land(g, rear(g, g.player.side))
    p = g.player
    stock = S.stores(g.sector, p.side)
    for it in sources(p, p.weapon):
        p.invent.remove(it)
    stock["ammo"] = .17
    before = p.ammo_count(p.weapon)
    g.map.add_item(p.x, p.y, Item("ammo_crate"))
    resupply(g, p)
    added = p.ammo_count(p.weapon) - before
    assert 0 < added <= 17 and abs(stock["ammo"] - (.17 - added / 100)) < 1e-6
    stock["ammo"] = 0
    assert resupply(g, p) is None
    # Same wound and rest, with and without a stocked hospital.
    g.map.gen_positions = [dict(kind="hospital", side=p.side, x=p.x, y=p.y,
                                rect=(p.x - 3, p.y - 3, 6, 6))]
    p.body.hp["torso"] = p.body.max["torso"] - 20
    p.body.wounds.clear()
    p.body.blood = 4000
    hp0 = p.body.hp["torso"]
    stock["medical"] = 0
    recover(g, p, 300)
    without = p.body.hp["torso"] - hp0
    assert p.body.blood == 4000
    stock["medical"] = 10
    recover(g, p, 300)
    assert p.body.hp["torso"] - hp0 > without and p.body.blood > 4000
    assert stock["medical"] < 10
    v = Vehicle("t34_76", p.side, p.nation, p.x + 1, p.y)
    g.vehicles = [v]
    v.ai["fuel"] = 0
    assert not vdamage.can_move(v) and g.try_move_vehicle(v, 1, 0) is None
    class Use:
        game = g
        def act(self, cost):
            self.cost = cost
    use = Use()
    can = Item("fuel_can")
    p.add_item(can)
    S.use(use, can)
    assert v.ai["fuel"] == 25 and vdamage.can_move(v) and use.cost > 0
    g.map.gen_positions.append(dict(kind="motor_pool", side=p.side, x=v.x, y=v.y, rect=(v.x-3, v.y-3, 6, 6)))
    v.parts["tracks"] = 1
    v.parts["engine"] = vdamage.OUT
    v.ai["maint"] = {"engine": JOBS["engine"][1]}
    v.hit_turn = -99999
    stock["parts"] = 0
    _repair(g, v)
    assert not vdamage.can_move(v)
    stock["parts"] = 1
    _repair(g, v)
    assert vdamage.can_move(v) and stock["parts"] < 1


def test_encircled_depot_consumes_its_reserves_without_imports():
    from fow.constants import other_side
    g = game()
    st = g.strategic
    side = g.player.side
    s = st.at(st.w // 2, st.h // 2, create=True)
    s.control = side
    s.installations = [["depot", side, True]]
    for n in st.neighbors(s, create=True):
        n.control = other_side(side)
    st.focus = (s.x, s.y)
    st.compute_supply()
    stock = S.stores(s, side)
    stock.update({k: 10. for k in S.RESOURCES})
    S.strategic_tick(st)
    assert all(0 <= value < 10 for value in stock.values())


def test_papers_checks_cannot_see_through_walls():
    from fow.gamemap import GameMap
    g = game()
    p = g.player
    guard = Actor("germany", "mp", 1, "Guard", 7, 5)
    g.map = GameMap(32, 32, 9)
    p.x, p.y = 5, 5
    g.actors = [p, guard]
    g.turn = 1000
    p.ai.update(disguise=True, suspicion=0.)
    p.invent.slots["body"] = Item("civvies")
    p.weapon = None
    p.fired_turn = -99999
    g.map.t[6, :] = T.ID["wall_stone"]
    g.map.refresh()
    for _ in range(20):
        g._disguise_tick()
    assert p.ai["disguise"] and p.ai["suspicion"] == 0
    g.map.set(6, 5, "grass")
    g.map.refresh()
    g._disguise_tick()
    assert p.ai["suspicion"] > 0


def test_air_and_sea_deliver_real_finite_stores():
    from fow.skysea import Plane, Ship, SkySea
    from fow.airlogistics import load, drop_supplies
    from fow.sealogistics import tick
    g = game()
    g.weather = "clear"
    W.state(g).update(intensity=1., wind=0., sea=0.)
    base = g.sector
    dest = rear(g, g.player.side)
    base.control = g.player.side
    ss = SkySea(g, base.x, base.y)
    plane = Plane("c47", g.player.side, "usa", 10, 10, 0, 300, kmh=200)
    stock = S.stores(base, plane.side)
    stock.update(food=20., medical=20., ammo=20.)
    for k in ("food", "medical", "ammo"):
        S.stores(dest, plane.side)[k] = 0
    cargo = load(g, base, plane)
    assert cargo == 60 and stock["food"] == stock["medical"] == stock["ammo"] == 0
    ss.mission = dict(kind="resupply", target_sector=(dest.x, dest.y), target_pt=(10, 10))
    plane.alt = 900
    assert not drop_supplies(ss, plane)
    plane.alt = 300
    assert drop_supplies(ss, plane)
    assert S.stores(dest, plane.side)["medical"] == 20
    assert not drop_supplies(ss, plane) and ss.mission["delivered"] == 60
    oiler = Ship("cimarron", "allies", "usa", 0, 0, 0)
    escort = Ship("cannon", "allies", "usa", 1, 0, 0)
    repair = Ship("vestal", "allies", "usa", 0, 1, 0)
    ss.ships = [oiler, escort, repair]
    for s in ss.ships:
        s.kn = 0
    escort.fuel = 10
    escort.hp -= 10
    tick(ss)
    assert escort.fuel == 13 and oiler.ai["cargo"]["fuel"] == 597
    assert escort.hp > escort.st["hp"] - 10 and repair.ai["cargo"]["parts"] < 250
    W.state(g)["sea"] = 5
    tick(ss)
    assert escort.fuel == 13
    W.state(g)["sea"] = 0
    oiler.ai["cargo"]["fuel"] = 0
    tick(ss)
    assert escort.fuel == 13


def test_new_aircraft_and_ships_have_playable_layouts():
    from fow.data.vehicles import AIRCRAFT
    from fow.data.ships import SHIPS
    from fow.parked import DIMS, CARRIER_OK
    from fow.skysea import Plane, Ship, _latest, CARRIER_AIR
    from fow.shipyard import build
    for ident in ("a20", "a26", "b26", "p61", "c47", "c46", "pby", "beaufort", "barracuda", "b6n", "d4y", "ju188"):
        at = AIRCRAFT[ident]
        plane = Plane(ident, "allies", at.nations[0], 0, 0, 0, 1000)
        assert len(plane.hp["engine"]) == DIMS[ident][2]
    assert {"b6n", "d4y", "barracuda"} <= CARRIER_OK
    assert _latest("japan", 1944, CARRIER_AIR["japan"][1]) == "d4y"
    for ident in ("cannon", "evarts", "independence", "sangamon", "cimarron", "vestal", "river_frigate", "matsu"):
        ship = Ship(ident, "allies", SHIPS[ident]["nations"][0], 0, 0, 0)
        decks, order, frame = build(ship, random.Random(3))
        assert frame.L >= 40 and len(order) >= 3 and all(d.map.walk.any() for d in decks.values())


def test_transport_pilot_can_drop_and_aborted_load_returns_to_stock():
    from fow.skysea_missions import launch_air, check, _base_sector
    from fow.skysea import bearing
    g = Game("bocage44", "usa", seed=9, setup={"battlefield": "standard"})
    g.weather = "clear"
    W.state(g).update(intensity=1., wind=0., sea=0.)
    base = _base_sector(g, g.player.side)
    base_stock = S.stores(base, g.player.side)
    base_stock.update(ammo=100., food=100., medical=100.)
    ss = launch_air(g, "resupply", at_id="c46", base=base)
    assert ss is not None and ss.player_plane.ai["cargo"] > 0
    plane = ss.player_plane
    tx, ty = ss.mission["target_pt"]
    plane.x, plane.y, plane.alt, plane.kmh = tx, ty + 12, 350, 330
    plane.hdg = bearing(plane.x, plane.y, tx, ty)
    ss.station = "deck"
    for _ in range(120):
        ss._fly(plane)
        if ss.mission.get("delivered"):
            break
    assert ss.mission.get("delivered", 0) > 0 and plane.ai["cargo"] == 0
    # A lost dropping zone sends the aircraft home with its actual remaining cargo.
    base_stock.update(ammo=100., food=100., medical=100.)
    ss = launch_air(g, "resupply", at_id="c47", base=base)
    plane = ss.player_plane
    target = g.strategic.at(*ss.mission["target_sector"])
    target.control = "axis"
    merit = g.command.merit
    check(ss)
    assert ss.mission["stage"] == "home" and ss.mission["aborted"]
    plane.x, plane.y = ss.mission["base_pt"]
    plane.state = "landed"
    check(ss)
    assert plane.ai["cargo"] == 0 and base_stock["medical"] == 100
    assert ss.over == ("landed", (base.x, base.y)) and g.command.merit == merit
    base_stock["medical"] = 0
    assert launch_air(g, "resupply", at_id="c47", base=base) is None


if __name__ == "__main__":
    import time
    import traceback
    bad = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            start = time.perf_counter()
            try:
                fn()
                print(f"ok    {name} ({time.perf_counter() - start:.1f}s)", flush=True)
            except Exception:
                bad += 1
                print("FAIL ", name, flush=True)
                traceback.print_exc()
    sys.exit(bool(bad))
