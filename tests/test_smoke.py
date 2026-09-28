"""Smoke tests: every battle starts and runs, every service starts, saves load, the war at sea goes on.

    python -m pytest tests            (pip install pytest)
    python tests/test_smoke.py        (no pytest needed)

These are not unit tests of numbers; they're "does the whole thing hold together" runs of the real
game, headless.  FOW_DEBUG=1 makes an exception inside any soldier's AI fail the test instead of
being swallowed.
"""
from __future__ import annotations

import math
import os
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("FOW_HOME", tempfile.mkdtemp(prefix="fow_home_"))   # never the player's saves or memorial
os.environ["FOW_DEBUG"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fow.settings as FS  # noqa: E402
FS.SETTINGS_PATH = os.path.join(tempfile.mkdtemp(prefix="fow_test_"), "settings.json")

from fow.data.theatres import THEATRES  # noqa: E402
from fow.data.items import ITEMS  # noqa: E402
from fow.game import Game  # noqa: E402


class FakeApp:
    """Just enough of the application for a PlayState to live in."""

    def __init__(self):
        self.settings = {"safe_mode": False}
        self.states = []
        self.show_numbers = False
        self.audio = None
        self.gfx = None

    def push(self, s):
        self.states.append(s)

    def pop(self):
        self.states.pop()

    def replace(self, s):
        self.states[-1:] = [s]


def _turns(g, n):
    for _ in range(n):
        g.player.moves = 0
        g.world_turn()


def test_every_theatre_starts_and_runs():
    for th, t in THEATRES.items():
        for side in ("allies", "axis"):
            nat = t["sides"][side][0][0]
            g = Game(th, nat, seed=11, setup={"battlefield": "standard"})
            _turns(g, 15)
            assert g.player is not None and g.actors, (th, nat)


def test_services_start():
    cases = [("guadalcanal42", "usa", "fighter_pilot", "air", "random"),
             ("bocage44", "uk", "bomber_pilot", "air", "air:strategic"),
             ("guadalcanal42", "japan", "admiral", "navy", "sea:carrier"),
             ("omaha44", "usa", "sailor", "navy", "random"),
             ("okinawa45", "usa", "sub_commander", "navy", "random"),
             ("crete41", "germany", "bombardier", "air", "random")]
    for th, nat, role, sv, sc in cases:
        g = Game(th, nat, role=role, seed=4, setup=dict(service=sv, scenario=sc, battlefield="standard"))
        _turns(g, 20)
        assert g.player.role == role, (th, role, g.player.role)


def test_save_and_load_aboard():
    d = tempfile.mkdtemp(prefix="fow_save_")
    for role, sc, sv, th in (("sailor", "sea:carrier", "navy", "okinawa45"),
                             ("bombardier", "air:strategic", "air", "bocage44")):
        g = Game(th, "usa", role=role, seed=7, setup={"battlefield": "standard", "service": sv, "scenario": sc})
        _turns(g, 30)
        path = os.path.join(d, role + ".pkl")
        g.save(path)
        g2 = Game.load(path)
        _turns(g2, 30)
        assert g2.domain == "aboard" and g2.aboard["kind"] == ("ship" if sv == "navy" else "plane")


def test_ship_is_full_size():
    from fow import aboard as AB
    g = Game("okinawa45", "usa", role="sailor", seed=7,
             setup={"battlefield": "standard", "service": "navy", "scenario": "sea:carrier"})
    ship = AB.ship_of(g)
    if ship.cls in ("cv", "cve"):
        assert "hangar" in g.aboard["decks"] and "flight" in g.aboard["decks"]
    fr = g.aboard["frame"]
    assert fr.L * 2 >= 100            # two metres a tile: nothing aboard is a toy


def test_carrier_battle_goes_somewhere():
    """With nobody conning her, the captain must take her into the fight - not steam off for ever."""
    from fow import aboard as AB, shipboard as SB
    from fow.play import PlayState
    fa = FakeApp()
    g = Game("okinawa45", "usa", role="sailor", seed=7,
             setup={"battlefield": "standard", "service": "navy", "scenario": "sea:carrier"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    ss, me = g.skysea, AB.ship_of(g)
    hp0 = {s.id: s.hp for s in ss.ships if s.side != me.side}
    scratched = False
    for _ in range(4 * 360):                       # four hours in 10-second steps
        SB.fast_step(g, 10)
        g.aboard["task"] = None
        # (hit at any time: a damaged ship may be patched up, or sunk and gone, by the end)
        scratched = scratched or any(s.hp < hp0.get(s.id, 0) for s in ss.ships if s.side != me.side) or \
            any(sid not in {s.id for s in ss.ships} for sid in hp0)
        if ss.over or not me.alive:
            break
    enemy = [s for s in ss.ships if s.side != me.side]
    assert scratched, "four hours and not a scratch on the enemy"
    if enemy:                                      # (none left: sunk, every one)
        near = min(math.hypot(s.x - me.x, s.y - me.y) for s in enemy)
        assert near < 400, f"the carrier wandered {near:.0f} tiles from the enemy"


def test_fast_forward_stops_for_the_watch():
    from fow import shipboard as SB
    from fow.play import PlayState
    fa = FakeApp()
    g = Game("okinawa45", "usa", role="sailor", seed=3,
             setup={"battlefield": "standard", "service": "navy", "scenario": "sea:convoy"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    t0 = g.turn
    stopped = False
    for _ in range(2000):
        if SB.fast_step(g, 30):
            stopped = True
            break
    assert stopped and g.turn > t0


def test_everyone_is_armed():
    """Every role in every army goes armed - except medics and chaplains, where their army sent them unarmed."""
    import random
    from fow.data.items import ITEMS
    from fow.data.nations import NATIONS
    from fow.data.roles import ROLES, build_kit
    rng = random.Random(3)
    for nat in NATIONS:
        for role in ROLES:
            for year, pac in ((1942.5, False), (1944.6, True)):
                k = build_kit(rng, nat, year, role, pacific=pac)
                arms = [k["wield"]] if k["wield"] else []
                arms += [i for i, _ in k["items"] if ITEMS[i].kind in ("gun", "melee")]
                if role not in ("medic", "chaplain"):
                    assert arms, (nat, role, year)
                if role == "medic" and (nat == "ussr" or pac and nat == "usa"):
                    pass                            # usually armed; not always
                if role == "medic" and not arms:
                    assert any(i == "brassard" for i, _ in k["items"]), (nat, role, "unarmed and no armband")


def test_nearby_list():
    from fow.play import PlayState, Key
    fa = FakeApp()
    g = Game("bocage44", "usa", seed=3, setup={"battlefield": "standard"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    _turns(g, 60)
    g.player_fov()
    if not g.player.alive or not g.player.body.conscious:
        return                                        # (shelled in the first minute: it happens)
    ps.popups = []
    ps.mode = "normal"
    ps.on_key(Key(char="V"))
    assert ps.mode == "nearby"
    lists = ps.nearby["lists"]
    assert set(lists) == {"Soldiers", "Items"}
    for e in lists["Soldiers"] + lists["Items"]:
        assert g.map.in_bounds(e["x"], e["y"])
    import tcod.event as E
    ps.on_key(Key(sym=E.KeySym.TAB))
    ps.on_key(Key(sym=E.KeySym.ESCAPE))
    assert ps.mode == "normal"


def test_base_staff_and_orders():
    """A headquarters has an adjutant who gives real orders, a clerk who pays you; staff stay at their posts."""
    from fow import base as BASE
    from fow.play import PlayState
    from fow.skysea_exit import to_land
    fa = FakeApp()
    g = Game("bocage44", "usa", seed=5, setup={"battlefield": "standard"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    s = next(s for s in g.strategic.sectors() if s.control == g.player.side and s.installs(g.player.side, "hq"))
    g.map = None
    to_land(g, s)
    roles = {a.role for a in BASE.staff_here(g)}
    assert {"adjutant", "clerk", "mp"} <= roles, roles
    adj = next(a for a in BASE.staff_here(g) if a.role == "adjutant")
    offers = BASE.offer_orders(g, adj)
    assert offers
    BASE.give_order(ps, adj, next(o for o in offers if o["kind"] == "guard"))
    assert g.base_order["kind"] == "guard" and "ORDERS" in g.player_orders
    assert ps._order_plan() is not None
    # staff come back on a revisit
    g.map = None
    to_land(g, s)
    assert {"adjutant", "clerk", "mp"} <= {a.role for a in BASE.staff_here(g)}


def test_navy_goes_back_to_base_and_sails_again():
    """Out of fuel after a win: back to base, anchor, refit, ashore on liberty and back, then new orders."""
    from fow import aboard as AB, naval as NV, shipboard as SB
    from fow.play import PlayState
    fa = FakeApp()
    g = Game("okinawa45", "usa", role="sailor", seed=3,
             setup={"battlefield": "standard", "service": "navy", "scenario": "sea:surface"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    ss, me = g.skysea, AB.ship_of(g)
    for sh in ss.ships:
        if sh.side != me.side:
            sh.hp, sh.sunk = -1, True
    me.fuel = 25.0
    for _ in range(200):
        SB.fast_step(g, 30)
        g.aboard["task"] = None
        if g.aboard.get("condition") == "port":
            break
    assert g.aboard["condition"] == "port", ss.mission
    for _ in range(40):
        if NV.can_go_ashore(g)[0]:
            break
        SB.fast_step(g, 600)
    NV.go_ashore(ps)
    assert g.domain == "land" and g.ship_ashore is not None
    NV.return_aboard(ps)
    assert g.domain == "aboard" and g.aboard["condition"] == "port"
    for _ in range(600):
        SB.fast_step(g, 300)
        g.aboard["task"] = None
        if g.aboard.get("condition") != "port" and g.skysea.mission.get("kind") != "rtb":
            break
    assert g.skysea.mission["kind"] != "rtb" and AB.ship_of(g).fuel >= 99


def _beside(g, v):
    cells = set(v.cells())
    for cx, cy in sorted(cells):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                x, y = cx + dx, cy + dy
                if (x, y) not in cells and g.map.in_bounds(x, y) and g.map.walk[x, y] and g.map.water[x, y] < 2 \
                        and g.soldier_at.get((x, y)) is None and g.vehicle_at.get((x, y)) is None:
                    return x, y
    return None


def _hush(g, v):
    """Nobody shooting at it for a while."""
    v.ai["hit_turn"] = -9999
    v.fired_turn = -9999
    v.visible = []
    if v.squad is not None:
        v.squad.last_contact = -9999


def test_tanks_are_repaired_rearmed_and_ridden():
    """A thrown track goes back on, a truck's shells go into the racks, infantry ride the hull, and a
    sergeant's order to carry shells is carried out with Enter."""
    from fow import maintenance as MT
    from fow.entities import Item, Vehicle, riding
    from fow.play import PlayState
    from fow.skysea_exit import to_land
    from fow.spawn import spot_and_facing
    fa = FakeApp()
    g = Game("kursk43", "ussr", seed=21, setup={"battlefield": "standard"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    p = g.player
    # a quiet sector behind the line, and a T-34 parked in it
    g.map = None
    to_land(g, next(s for s in g.strategic.sectors() if s.control == p.side and s.installs(p.side, "motor_pool")))
    v = Vehicle("t34_76", p.side, "ussr", 0, 0)
    (v.x, v.y), v.facing = spot_and_facing(g, p.x + 6, p.y, v.vt, 12, 0)
    g.add_vehicle(v)
    assert not v.vt.seats
    # the track: crew alone, in man-seconds
    v.tracks = False
    calls = int(MT.TRACK_WORK / (v.crew * MT.STEP)) + 2
    for _ in range(calls):
        _hush(g, v)
        MT._repair(g, v)
    assert v.tracks
    # not while it's being shot at
    v.tracks = False
    v.ai.pop("maint", None)
    v.ai["hit_turn"] = g.turn
    MT._repair(g, v)
    assert not v.ai.get("maint")
    v.tracks = True
    # shells from a truck
    v.ap, v.he = 0, 0
    MT.call_truck(g, p.side, target=(v.x, v.y), why="test")
    t = next(t for t in g.vehicles if t.ai.get("supply_run") and t.side == p.side)
    assert t.squad.kind == "supply"
    g.lift_vehicle(t)
    (t.x, t.y), t.facing = spot_and_facing(g, v.x, v.y, t.vt, 8, 0)
    g.place_vehicle(t)
    for _ in range(40):
        _hush(g, v)
        MT._rearm(g, v)
    assert v.ap + v.he > 0 and t.ai["cargo"] == MT.TRUCK_CARGO - (v.ap + v.he)
    # riding on the hull, and off again
    g.soldier_at.pop((p.x, p.y), None)
    p.x, p.y = _beside(g, v)
    g.soldier_at[(p.x, p.y)] = p
    ps._enter_vehicle(v)
    assert p.vehicle is v and riding(p) and p in v.passengers
    assert "jump down" in ps.context_hint()
    ps._vehicle_choice(v, ("exit", None))
    assert p.vehicle is None and not p.ai.get("rider")
    # carrying shells up: the order, and Enter
    sup = next(a for a in g.actors if a.side == p.side and a.alive and a is not p and a.rank > p.rank)
    g.duty.task = None
    g.duty.give(g, "shells", sup, (v.x, v.y), vid=v.id, base=v.ai.get("handed_by_player", 0))
    uid = g.duty._tasks()[-1]["uid"]
    it = Item("shell_crate")
    it.data = dict(rounds=MT.CRATE_ROUNDS)
    p.invent.hands = it
    plan = ps._order_plan()
    assert plan is not None and "hand" in plan[0], plan
    before = v.ai.get("handed_by_player", 0)
    plan[1]()
    assert v.ai["handed_by_player"] == before + MT.CRATE_ROUNDS and p.invent.hands is None
    g.duty.update(g)
    assert all(t["uid"] != uid for t in g.duty._tasks())      # done (he may want more: a new order)


def test_supply_run():
    """The motor sergeant's supply run: a truck of your own, driven to the tanks in the next sector."""
    from fow import base as BASE
    from fow import maintenance as MT
    from fow.play import PlayState
    from fow.skysea_exit import to_land
    fa = FakeApp()
    g = Game("kursk43", "ussr", seed=5, setup={"battlefield": "standard"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    p = g.player
    s = next(s for s in g.strategic.sectors() if s.control == p.side and s.installs(p.side, "motor_pool"))
    g.map = None
    to_land(g, s)
    who = next(a for a in BASE.staff_here(g) if a.role == "motor_sergeant")
    BASE._motor_choice(ps, who, "supply_run", [])
    o = g.base_order
    assert o and o["kind"] == "supply_run"
    t = BASE._supply_truck(g, o)
    assert t is not None and t.ai["cargo"] == MT.TRUCK_CARGO
    plan = ps._order_plan()
    assert "get in" in plan[0], plan
    plan[1]()
    for _ in range(400):
        if not ps.travel_path:
            break
        ps.anim = ps.anim_next = 0
        g.effects = []
        ps.tick()
    assert p.vehicle is t
    for _ in range(6):
        if (g.sector.x, g.sector.y) == tuple(o["sector"]):
            break
        g.travel(BASE._next_edge(g, o["sector"]))
    assert (g.sector.x, g.sector.y) == tuple(o["sector"]) and p.vehicle is t
    BASE.update(g)
    assert o.get("primed")


def test_dawn_light_and_seeing_from_a_tank():
    """The sun rises when it really rose (Kursk, 5 July 1943: about 04:20 Moscow time), twilight has no
    cliff in it, and a tank commander in a field of maize sees over it."""
    import numpy as np
    from fow import senses as S
    fa = FakeApp()
    g = Game("kursk43", "ussr", role="tank_crew", seed=3, setup={"battlefield": "standard", "scenario": "armour"})
    from fow.play import PlayState
    ps = PlayState(fa, g)
    fa.states = [ps]
    assert S.daylight(g) > 0.8 and not g.is_dark
    v = g.player.vehicle
    from fow.vdamage import hatch_user
    assert v is not None and v.player_station == hatch_user(v)     # (a two-man tank's gunner commands it)

    def reach():
        g.player_fov()
        xs, ys = np.nonzero(g.map.visible)
        return float(np.hypot(xs - v.x, ys - v.y).max()), len(xs)
    v.buttoned = False
    out, seen_out = reach()
    v.buttoned = True
    shut, seen_shut = reach()
    # (head out he sees far all round; buttoned up, less - except down a gunner-commander's sight)
    assert out > 45 and shut > 20 and seen_shut < seen_out, (out, shut, seen_out, seen_shut)
    # the view widens smoothly through twilight: no jump to a few yards when it's "dark"
    ranges = []
    for mins in range(-90, 30, 5):
        g._daylight_cache = g._moon_cache = None
        g.clock = mins * 60 - 10 * 60        # (the battle starts ten minutes after sunrise)
        g.update_view_range()
        ranges.append(g.view_range_cache)
    assert all(b >= a - 0.01 for a, b in zip(ranges, ranges[1:]))
    assert max(b - a for a, b in zip(ranges, ranges[1:])) < 8


def test_vehicle_parts():
    """A broken track stops it moving but not shooting; a jammed turret fires only where it points; a
    crewman hit leaves his seat empty until the others cover it; hovering shows the damage."""
    from fow import crew as CR
    from fow import vdamage as VD
    from fow.combat import vehicle_fire_main
    from fow.entities import Vehicle
    from fow.play import PlayState
    from fow.spawn import spot_and_facing
    fa = FakeApp()
    g = Game("bocage44", "usa", seed=3, setup={"battlefield": "standard"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    p = g.player
    v = Vehicle("m4", p.side, "usa", 0, 0)
    (v.x, v.y), v.facing = spot_and_facing(g, p.x + 8, p.y, v.vt, 15, 0)
    g.add_vehicle(v)
    e = Vehicle("panther", "axis", "germany", 0, 0)
    (e.x, e.y), e.facing = spot_and_facing(g, v.x + 12, v.y, e.vt, 15, 4)
    g.add_vehicle(e)
    v.parts["tracks"] = VD.OUT
    assert not v.mobile and not g.turn_vehicle(v, v.facing + 2)
    assert vehicle_fire_main(g, v, e.x, e.y, e, "ap")
    v.parts["tracks"] = VD.OK
    v.parts["turret"] = VD.OUT
    v.reload = 0
    v.turret = (v.facing + 4) % 8
    from fow.gamemap import octant
    if (octant(e.x - v.x, e.y - v.y) - v.turret) % 8 not in (0, 1, 7):
        assert not vehicle_fire_main(g, v, e.x, e.y, e, "ap")
    v.parts["turret"] = VD.OK
    VD.crew_hit(g, v, "gunner", None, "test", False)
    assert "gunner" not in CR.manned(v) and v.crew == v.vt.crew - 1
    g.turn += 100
    VD.tick(g)
    assert "gunner" in CR.manned(v)
    e.parts["tracks"] = VD.OUT
    assert any("track" in t for t, _ in ps._vehicle_state_lines(e, False, 20))
    assert "a track broken" not in " ".join(t for t, _ in ps._vehicle_state_lines(e, False, 20))
    v.parts["optics"] = VD.OUT
    assert "sights smashed" in ps._vehicle_state_lines(v, True, 5)[0][0]


def test_fire_support_comes_from_real_units():
    """A call for fire goes to a real battery, which fires the rounds it has; with every battery busy or empty
    the answer is no; aircraft come from a squadron, which has only so many."""
    from fow.play import PlayState
    fa = FakeApp()
    g = Game("bocage44", "usa", role="officer", seed=4, setup={"battlefield": "standard"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    p = g.player
    f = g.support.fires
    mine = [b for b in f.batteries if b.side == p.side]
    assert mine and all(b.name and b.guns > 0 and b.ammo > 0 for b in mine)
    e = next(a for a in g.actors if a.side != p.side and a.alive)
    before = {b.id: b.ammo for b in mine}
    assert g.support.request_fire(p.side, e.x, e.y, caller=p)
    b = next(b for b in mine if b.mission is not None and b.mission.get("player"))
    _turns(g, 200)
    assert b.ammo < before[b.id] and b.fired > 0
    for o in f.batteries:
        o.ammo = 0
    assert not g.support.request_fire(p.side, e.x, e.y, caller=p)
    q = next(q for q in f.squadrons if q.side == p.side)
    ready = sum(x.ready(g.turn) for x in f.squadrons if x.side == p.side)
    assert g.support.launch_sortie(p.side, target=(e.x, e.y))
    assert sum(x.ready(g.turn) for x in f.squadrons if x.side == p.side) < ready
    n = q.planes
    f.plane_lost(g, q)
    assert q.planes == n - 1


def test_gun_line_and_mortars():
    """An artilleryman on his gun gets fire missions and fires them with Enter; a mortarman in the battalion's
    mortar platoon gets his share of its missions."""
    from fow.play import PlayState
    fa = FakeApp()
    g = Game("alamein42", "uk", seed=6, setup={"battlefield": "standard", "scenario": "gunline"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    p = g.player
    f = g.support.fires
    assert p.role == "artilleryman" and p.vehicle is not None and p.vehicle.ai.get("battery")
    b = f.player_battery(g)
    assert b is not None and p.vehicle.id in b.vids
    fired = 0
    here = (g.sector.x, g.sector.y)
    tx = max(0, min(g.map.w - 1, p.x + 40))
    for a in list(g.actors):                         # (nobody of ours where the rounds will land)
        if a.side == p.side and a is not p and abs(a.x - tx) <= 15 and abs(a.y - p.y) <= 15:
            g.remove_actor(a)
    for o in f.batteries:                            # (their guns would find ours: counter-battery is real)
        if o.side != p.side:
            o.ammo = 0
    g.support.next_sortie = {k: 10 ** 9 for k in g.support.next_sortie}
    g.waves = []
    for _ in range(3000):
        if f.player_mission(g) is not None:
            assert "FIRE MISSION" in g.player_orders
            ps._order_plan()[1]()
            fired += 1
            if fired >= 3:
                break
            continue
        if b.mission is None:
            f.start(g, b, ("map", here, (tx, p.y)), None, 6, delay=5, silent=True)   # (the next call from the front)
        p.moves = 0
        g.world_turn()
    assert fired >= 3 and b.fired >= 3
    g2 = Game("kursk43", "germany", role="mortarman", seed=6, setup={"battlefield": "standard"})
    ps2 = PlayState(fa, g2)
    fa.states = [ps2]
    f2 = g2.support.fires
    pb = f2.player_battery(g2)
    assert pb is not None
    p2 = g2.player
    m = g2.map
    tx = max(0, min(m.w - 1, p2.x + (40 if p2.x < m.w // 2 else -40)))
    f2.start(g2, pb, ("map", (g2.sector.x, g2.sector.y), (tx, p2.y)), None, 8, delay=0, silent=True)
    _turns(g2, 2)
    assert f2.player_mission(g2) is not None and "FIRE MISSION" in (f2.order_text(g2) or "")
    ps2._order_plan()[1]()
    assert pb.mission is None or pb.mission.get("player_fired", 0) >= 1


def test_counter_battery_comes_from_real_guns():
    """Counter-battery fire on a gun line is fired by real enemy batteries, from their own rounds - and with
    none able to, none comes."""
    g = Game("alamein42", "uk", seed=6, setup={"battlefield": "standard", "scenario": "gunline"})
    f = g.support.fires
    mine = f.player_battery(g)
    enemy = [b for b in f.batteries if b.side != mine.side]
    for b in enemy:
        if b.mission is not None:
            f._end(g, b, "done")                     # (free to answer, whatever they were doing)
    before = {b.id: b.ammo for b in enemy}
    g._counter_battery = [(g.turn, enemy[0].side, *mine.pos)]
    _turns(g, 300)
    fired = [b for b in enemy if b.ammo < before[b.id]]
    assert fired and all(b.kind in ("gun", "rocket", "naval") for b in fired)
    assert all(f.km(g, b, mine.sec, mine.pos) <= f.reach_km(g, b) for b in fired)
    for b in enemy:
        b.ammo = 0
    g.shells = []
    g._counter_battery = [(g.turn, enemy[0].side, *mine.pos)]
    _turns(g, 60)
    assert not any(s.get("side") == enemy[0].side for s in g.shells)


def test_help_screen():
    """The help: every section draws; "Right now" knows where you are; / finds keys anywhere."""
    import tcod
    from fow.constants import SCREEN_H, SCREEN_W
    from fow.play import Key, PlayState
    from fow.ui import HelpState
    fa = FakeApp()
    g = Game("kursk43", "ussr", role="tank_crew", seed=3, setup={"battlefield": "standard", "scenario": "armour"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    h = HelpState(fa, play=ps)
    assert h.sections[0][0] == "Right now"
    from fow import crew as C
    seat = C.name(g.player.vehicle.vt, g.player.vehicle.player_station).lower()
    assert any(seat in str(r) for r in h.sections[0][1])
    con = tcod.console.Console(SCREEN_W, SCREEN_H, order="F")
    for i in range(len(h.sections)):
        h.sel = i
        h.render(con)
        assert h._lines
    h.on_key(Key(char="/"))
    for c in "hatch":
        h.on_key(Key(char=c))
    rows = h._rows()
    assert any(r[0] == "h" and r[1] == "Vehicles" for r in rows)
    h.render(con)


def test_orders_propose_targets_and_tasks():
    """Flank (and the other targeted orders) offer the next objective first, then what's known of the enemy;
    squads can be set to scavenge the dead, carry the wounded back and march prisoners off."""
    import tcod.event as E
    from fow import tasks as TK
    from fow.cmdui import proposals
    from fow.play import Key, PlayState
    from fow.spawn import free_tile_near, make_squad
    fa = FakeApp()
    g = Game("bocage44", "usa", role="squad_leader", seed=8, setup={"battlefield": "standard"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    p = g.player
    sq = p.squad
    for b in g.support.fires.batteries:              # (no shells: the dressings are for counting, not using)
        if b.side != p.side:
            b.ammo = 0
    g.support.next_sortie = {k: 10 ** 9 for k in g.support.next_sortie}
    _turns(g, 60)
    props = proposals(g, "flank", [sq], (p.x, p.y))
    assert props and "next objective" in props[0][0]
    ps.cmd_orders()
    pop = ps.popups[-1]
    pop.sel = next(i for i, o in enumerate(pop.options) if o[1] == "flank")
    ps.popup_select()
    assert ps.popups[-1].options[-1][1] == "pick"
    ps.on_key(Key(sym=E.KeySym.RETURN))
    assert sq.order.kind == "flank" and tuple(sq.order.target) == props[0][1]
    # the dead: their kit is there for the taking
    for i, e in enumerate([a for a in g.actors if a.side != p.side and a.alive][:4]):
        g.soldier_at.pop((e.x, e.y), None)
        e.x, e.y = free_tile_near(g, p.x + 6 + i * 2, p.y + 3, 6)
        g.soldier_at[(e.x, e.y)] = e
        e.body.dead = True
        g.kill(e, None)
    for a in list(g.actors):
        if a.side != p.side and a.alive:
            a.body.dead = True
            g.kill(a, None)
    assert TK.available(g, sq, (p.x, p.y))["medical"][0] > 0
    TK.assign(g, sq, "medical", by=p)
    job = sq.__dict__.get("task")
    for _ in range(90):
        _turns(g, 10)
        if sq.__dict__.get("task") is None:
            break
    assert sq.__dict__.get("task") is None
    # (what they gathered, not what's in their pouches after: they patch each other up as they go)
    assert sum(job["found"].values()) > 0
    # a man down: carried to the aid post
    w = next(m for m in sq.members if m is not p and m.active)
    w.body.hp["l_leg"] = w.body.hp["r_leg"] = 0
    TK.assign(g, sq, "casevac", by=p)
    for _ in range(150):
        _turns(g, 10)
        if w.ai.get("at_aid") is not None or w.ai.get("carried_by") is not None:
            break
    assert w.ai.get("at_aid") is not None or w.ai.get("carried_by") is not None
    # a man with his hands up: searched and marched off
    esq = make_squad(g, "axis", "germany", "rifle", p.x + 6, p.y + 6)
    pw = esq.members[0]
    pw.state = "surrendered"
    for m in esq.members[1:]:
        m.body.dead = True
        g.kill(m, None)
    TK.finish(g, sq)
    TK.assign(g, sq, "prisoners", by=p)
    for _ in range(150):
        _turns(g, 10)
        if pw.ai.get("searched") or pw not in g.actors:
            break
    assert pw.ai.get("searched") or pw not in g.actors


def test_medevac():
    """Badly hit, in cover, with a radio: stretcher-bearers come on foot, carry you back, and weeks later you're
    back at the front, whole."""
    from fow import medevac as MV
    from fow.entities import Item
    from fow.play import PlayState
    fa = FakeApp()
    g = Game("bocage44", "usa", seed=8, setup={"battlefield": "standard"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    p = g.player
    assert not MV.can_call(g)[0]                      # not hurt
    for a in list(g.actors):
        if a.side != p.side and a.alive:
            a.body.dead = True
            g.kill(a, None)
    g.brains[p.side].contacts.clear()
    _turns(g, 3)
    p.body.hp["l_leg"] = 3
    if p.add_item(Item("radio")) is None:
        bp = Item("backpack")                         # (a pack to carry the set in)
        p.invent.slots["pack"] = bp
        bp.where = "pack"
        assert p.add_item(Item("radio")) is not None
    ok, why = MV.can_call(g)
    assert ok, why
    day0 = g.now()
    MV.call(ps)
    carried = g.medevac is None                       # (they were close: it's all over by the time the call ends)
    if not carried:
        bearers = MV._bearers(g, g.medevac)
        assert len(bearers) == MV.TEAM and all(b in g.actors for b in bearers)
    for _ in range(4000):
        if g.medevac is None:
            break
        carried = carried or p.ai.get("carried_by") is not None
        p.moves = 0
        g.world_turn()
    assert carried and g.medevac is None
    assert (g.now() - day0).days >= 7
    assert all(p.body.hp[k] == p.body.max[k] for k in p.body.hp) and p in g.actors


def test_skills():
    """Every man's skills are a roll - any private might be a fine shot - but training puts a floor under what
    his job needs: snipers stalk and shoot, agents pass unseen, medics close wounds.  Practice brings them on,
    and they're used where they matter (being noticed, first aid)."""
    import statistics
    import tcod
    from fow import skills as SK
    from fow.constants import SCREEN_H, SCREEN_W
    from fow.spawn import make_soldier
    from fow.ui import StatusState
    fa = FakeApp()
    g = Game("bocage44", "usa", seed=4, setup={"battlefield": "standard"})
    rifles = [make_soldier(g, "usa", "rifleman") for _ in range(60)]
    snipers = [make_soldier(g, "usa", "sniper") for _ in range(20)]
    medics = [make_soldier(g, "usa", "medic") for _ in range(20)]
    for a in rifles + snipers + medics:
        assert set(a.skills) == set(SK.SKILLS) and all(0 <= v <= 10 for v in a.skills.values())
    # the floors: every sniper can stalk and shoot; every medic can dress a wound
    assert min(a.skills["marksmanship"] for a in snipers) >= 5.0
    assert min(a.skills["stealth"] for a in snipers) >= 4.5
    assert min(a.skills["first_aid"] for a in medics) >= 4.0
    # the roll: riflemen differ, and some untrained man is a natural at something
    st = [a.skills["stealth"] for a in rifles]
    assert statistics.pstdev(st) > 0.8 and max(st) > 4.0
    # on average a sniper is harder to notice than a rifleman
    assert statistics.mean(SK.stealth_mult(a) for a in snipers) < statistics.mean(SK.stealth_mult(a) for a in rifles)
    # practice: a little each time, less the better he is
    a = rifles[0]
    a.skills["first_aid"] = 2.0
    for _ in range(200):
        SK.use(g, a, "first_aid", 3)
    assert a.skills["first_aid"] > 2.5
    # the screen
    ss = StatusState(fa, g)
    ss.page = 1
    con = tcod.console.Console(SCREEN_W, SCREEN_H, order="F")
    ss.render(con)
    text = "".join(chr(c) for row in con.ch.T for c in row if 32 <= c < 0x10000)
    assert "SKILLS" in text


def test_hand_to_hand():
    """A blow lands somewhere real or is parried; two men can lock together (and then can't shoot a rifle); a
    man looking the other way can be taken silently; the right-click menu offers the moves with their odds."""
    from fow import melee as ML
    from fow.play import PlayState
    from fow.spawn import free_tile_near, make_soldier
    fa = FakeApp()
    g = Game("bocage44", "usa", role="rifleman", seed=3, setup={"battlefield": "standard"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    p = g.player
    for a in list(g.actors):
        if a.side != p.side and a.alive:
            a.body.dead = True
            g.kill(a, None)

    def enemy():
        e = make_soldier(g, "germany", "rifleman")
        e.side = "axis"
        spot = next(((p.x + dx, p.y + dy) for dx in (1, -1) for dy in (0, 1, -1)
                     if g.map.walk[p.x + dx, p.y + dy] and (p.x + dx, p.y + dy) not in g.soldier_at), None)
        e.x, e.y = spot or free_tile_near(g, p.x + 1, p.y, 1)
        g.add_actor(e)
        e.ai["aware"] = {p.id: (1.0, g.turn)}
        return e
    # a fight: blows are exchanged until one of them goes down (both are wounded somewhere real)
    e = enemy()
    hp0 = sum(e.body.hp.values())
    for _ in range(40):
        if not e.alive or e.downed:
            break
        g.turn += 1
        e.ai["aware"] = {p.id: (1.0, g.turn)}
        ML.attack(g, p, e, "butt")
    assert sum(e.body.hp.values()) < hp0
    g.remove_actor(e)
    # a clinch: both held, and the rifle can't be brought round
    e = enemy()
    for _ in range(30):
        g.turn += 1
        e.ai["aware"] = {p.id: (1.0, g.turn)}
        ML.attack(g, p, e, "grab")
        if ML.grappling(g, p) is e:
            break
    assert ML.grappling(g, p) is e and ML.grappling(g, e) is p
    from fow import actions as A
    if p.weapon is not None and p.weapon.t.cat != "pistol":
        assert A.fire(g, p, e.x, e.y, e) is None
    ML._release(p, e)
    g.remove_actor(e)
    # from behind, unseen: taken without a sound
    e = enemy()
    e.ai["aware"] = {}
    e.face = 1 if p.x < e.x else -1                  # looking away from you
    assert ML.surprised(g, e, p) and ML.moves_for(g, p, e)[0] in ("silent", "strangle")
    ML.attack(g, p, e)
    assert not e.alive or e.body.unconscious > 0 or ML.grappling(g, p) is e
    ML._release(p, e)
    if e in g.actors:
        g.remove_actor(e)                            # (the man you just took: out of the way)
    # the menu
    e2 = enemy()
    ps.context_menu(e2.x, e2.y, 10, 10)
    labels = [o[0] for o in ps.popups[-1].options]
    assert any("odds" in l or "certain" in l for l in labels)


def test_agents():
    """An agent has a career, a cover with the right papers and no soldier's kit; a timed charge hides its fuse;
    the wireless brings a drop from a real squadron, which drops only on lights and lands real containers;
    long transmissions bring the detector car."""
    from fow import agents as AG
    from fow.play import PlayState
    from fow.spawn import free_tile_near
    fa = FakeApp()
    g = None
    for seed in range(1, 40):
        g = Game("bocage44", "uk", role="agent", seed=seed, setup={"battlefield": "standard", "scenario": "agent"})
        if g.mission["task"] == "receive_drop":
            break
    ps = PlayState(fa, g)
    fa.states = [ps]
    p = g.player
    cv = AG.cover(g)
    assert cv and cv["career"] in AG.CAREERS and g.mission["kind"] == "agent"
    if cv.get("name"):
        assert not any(i.t.tool == "dogtags" for i in p.inv)                   # in plain clothes: nothing that says soldier
        assert all(any(i.tid == x for i in p.inv) for x in cv["papers"])
        assert any(i.t.tool == "papers" for i in p.inv) and p.ai.get("disguise")
    def quiet():
        g.waves = []
        g.shells = []
        for b in g.support.fires.batteries:          # (their guns and aircraft are real, and would find you)
            if b.side != p.side:
                b.ammo = 0
        g.support.next_sortie = {k: 10 ** 9 for k in g.support.next_sortie}
        for a in list(g.actors):
            if a.side != p.side and a.alive:
                a.body.dead = True
                g.kill(a, None)
    quiet()
    # a time pencil: a long fuse, and nobody runs from what they don't know is there
    from fow.entities import Item

    def give(tid):
        it = Item(tid)
        spare = [i for i in p.inv if i.t.kind in ("tool", "melee", "gun", "ammo", "mag") and
                 i.t.tool not in ("wireless", "torch", "sphone") and i is not p.weapon]
        while p.add_item(it) is None and spare:
            p.remove_item(spare.pop())               # (a full pack: something goes)
        return it
    give("pe_808")
    give("time_pencil")
    from fow import actions as A
    A.place_charge(g, p, next(i for i in p.inv if i.tid == "pe_808"), p.x, p.y)
    e = g.explosives[-1]
    assert e["fuse"] > 300 and e.get("hidden") and g.explosive_danger(p.x, p.y, 4) is None
    g.explosives.clear()
    # the drop: the squadron is real; over the field with the lights out, containers land
    d = g.agent["drops"][0]
    give("signal_torch")                              # (your own torch, if the committee's been shot)
    g.soldier_at.pop((p.x, p.y), None)
    p.x, p.y = free_tile_near(g, d["dz"][0] + 2, d["dz"][1], 3)
    g.soldier_at[(p.x, p.y)] = p
    for k in range(4000):
        p.moves = 0
        g.world_turn()
        if k % 5 == 0:
            quiet()
        if d["state"] in ("dropped", "no_lights", "lost"):
            break
    assert d["state"] == "dropped" and d["n_items"] > 0, d
    q = next(q for q in g.support.fires.squadrons if q.id == d["squadron"])
    assert q.at.role == "transport" and q.sorties >= 1
    # a message out; then on the air too long in one place, and the detector car comes
    st = g.agent
    st["df"] = 0.0
    AG.radio_choice(ps, "report")
    for k in range(AG.TX_TIME["report"] + 5):
        p.moves = 0
        g.world_turn()
        if k % 5 == 0:
            quiet()
    assert st["sent"] >= 1
    st["df"] = AG.DF_ALARM - 5
    AG.radio_choice(ps, "report")
    for k in range(20):
        p.moves = 0
        g.world_turn()
    assert st["hunt"] is not None and any(q.id == st["hunt"]["squad"] for q in g.squads)
    # the cover page draws
    import tcod
    from fow.constants import SCREEN_H, SCREEN_W
    from fow.ui import StatusState
    ss = StatusState(fa, g)
    ss.page = ss.PAGES.index("cover")
    ss.render(tcod.console.Console(SCREEN_W, SCREEN_H, order="F"))


def test_item_flavor():
    """Every rifle has a maker and a serial, tags are in their army's format, letters come from home, a paper
    carries the real news of its date, and each army carries its own things."""
    import datetime
    from fow import flavor as FL
    from fow.data.items import ITEMS
    from fow.data.roles import _personal
    from fow.entities import Item
    from fow.spawn import make_soldier
    g = Game("bocage44", "usa", seed=5, setup={"battlefield": "standard"})
    a = make_soldier(g, "usa", "rifleman")
    gun = a.weapon
    assert gun is not None and "serial" in (gun.data or {}).get("flavor", "")
    tags = next(i for i in a.inv if i.t.tool == "dogtags")
    assert a.name.upper() in tags.data["flavor"]
    let = Item("letter")
    FL.stamp(g, let, a)
    assert let.data["text"].startswith("A letter from")
    paper = Item("stars_and_stripes")
    FL.stamp(g, paper, a)
    if g.now().date() >= datetime.date(1944, 6, 6):
        assert "FRANCE" in paper.data["text"] or "PARIS" in paper.data["text"] or "ROME" in paper.data["text"]
    import random
    r = random.Random(2)
    jp = {_personal(r, "japan", 1944, ("charm", "flag")) for _ in range(30)}
    assert jp & {"senninbari", "omamori", "yosegaki"}
    assert all(ITEMS[i].freq == 0 for i in ("welrod", "pervitin", "senninbari"))   # never in the ordinary loot pools


def test_relief_and_floors():
    """The land has height: named hills stand up, a crest hides what's behind it, uphill is slow.  Buildings
    have floors: stairs up for the view, a cellar against the shells, the same for everyone."""
    import numpy as np
    from fow import actions as A
    from fow import relief as R
    from fow import tiles as T
    from fow.combat import explode
    from fow.play import PlayState
    g = Game("cassino44", "uk", seed=4, setup={"battlefield": "standard"})
    m = g.map
    e = m.elev
    assert e.max() - e.min() > 15
    hills = [o for o in m.objectives if any(k in o.name.lower() for k in R.HILL_NAMES)]
    for o in hills:
        assert e[o.x, o.y] > np.median(e)
    # somewhere a line is blocked by the ground alone
    import tcod
    hx, hy = (int(v) for v in np.unravel_index(int(np.argmax(e)), e.shape))
    top = float(e[hx, hy])
    blocked = False
    for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
        ends = []
        for sgn in (1, -1):
            x, y = hx, hy
            while m.in_bounds(x + sgn * dx, y + sgn * dy) and e[x, y] > top - 12:
                x, y = x + sgn * dx, y + sgn * dy
            ends.append((x, y))
        (x0, y0), (x1, y1) = ends
        if e[x0, y0] <= top - 12 and e[x1, y1] <= top - 12:
            if not R.crest_clear(m, tcod.los.bresenham((x0, y0), (x1, y1)), 1.6, 1.6):
                blocked = True                        # over the hill, the other side can't be seen
                break
    assert blocked
    assert R.climb(m, hx - 1, hy, hx, hy) > 1.0       # uphill is slow
    # floors, in a town
    fa = FakeApp()
    g = Game("stalingrad42", "ussr", seed=4, setup={"battlefield": "standard"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    m = g.map
    p = g.player
    stairs = [tuple(map(int, s)) for s in np.argwhere(m.t == T.ID["stairs"]) if tuple(map(int, s)) not in g.soldier_at]
    traps = [tuple(map(int, s)) for s in np.argwhere(m.t == T.ID["trapdoor"]) if tuple(map(int, s)) not in g.soldier_at]
    assert stairs and traps
    g.soldier_at.pop((p.x, p.y), None)
    p.x, p.y = stairs[0]
    g.soldier_at[stairs[0]] = p
    assert A.climb(g, p, 1) and p.z == 1 and R.eye_height(p) > 4
    assert A.climb(g, p, -1) and p.z == 0
    g.soldier_at.pop((p.x, p.y), None)
    p.x, p.y = traps[0]
    g.soldier_at[traps[0]] = p
    assert A.climb(g, p, -1) and p.z == -1
    assert A.move(g, p, 1, 0) is None                 # nowhere to walk in a cellar
    hp0 = sum(p.body.hp.values())
    explode(g, p.x + 3, p.y, 250, 4, frags=40, attacker=None, source="a test shell")   # (the trapdoor intact)
    assert sum(p.body.hp.values()) > hp0 - 30
    assert A.climb(g, p, 1) and p.z == 0


def test_walk_through_unseen_ground():
    """Click on ground you haven't seen, behind the hedges: the walk tries it, goes round what it finds in
    the way, and gets there."""
    import numpy as np
    from fow.play import PlayState
    fa = FakeApp()
    arrived = 0
    for seed in (1, 3):
        g = Game("bocage44", "usa", role="rifleman", seed=seed, setup={"battlefield": "standard"})
        ps = PlayState(fa, g)
        fa.states = [ps]
        p = g.player
        m = g.map
        for a in list(g.actors):
            if a.side != p.side and a.alive:
                a.body.dead = True
                g.kill(a, None)
        for v in g.vehicles:                          # (and their tanks: an MG in a hull kills as surely)
            if v.side != p.side:
                v.crew = 0
                v.abandoned = True
        g.waves = []
        for b in g.support.fires.batteries:
            b.ammo = 0
        g.support.next_sortie = {k: 10 ** 9 for k in g.support.next_sortie}
        g.player_fov()
        cand = np.argwhere(~m.explored & m.walk)
        tx, ty = (int(v) for v in max(cand[::97], key=lambda q: abs(q[0] - p.x) + abs(q[1] - p.y)))
        assert not m.explored[tx, ty] and ps.start_travel(tx, ty)
        for _ in range(3000):
            if not ps.travel_path or not p.alive:
                break
            ps.anim = ps.anim_next = ps.auto_wait = 0
            ps.mark_interrupt()
            ps.tick()
        arrived += max(abs(p.x - tx), abs(p.y - ty)) <= 1
    assert arrived >= 1


def test_rear_roads_and_supply():
    """Behind the line the roads are busy; cut them and the fronts they feed go short."""
    from fow import rear as RR
    from fow.combat import destroy_vehicle
    from fow.skysea_exit import to_land
    g = Game("kursk43", "ussr", seed=3, setup={"battlefield": "standard"})
    st = g.strategic
    p = g.player
    st.compute_supply()
    # interdiction on the war map: a busy road in the rear, cut, starves the fronts beyond it
    lanes = [(v, k) for k, v in st.traffic.items() if k[0] == p.side and
             not st.is_front(st.at(k[1], k[2]), p.side) and st.at(k[1], k[2]).playable]
    assert lanes
    v, k = max(lanes)
    s = st.at(k[1], k[2])
    fed = st.fed_by(p.side, s)
    assert fed
    before = {f.name: st.supply_of(p.side, f) for f in fed}
    st.interdict(p.side, s, 1.0, "a test")
    assert st.cut_of(p.side, s) > 0.9
    after = {f.name: st.supply_of(p.side, f) for f in fed}
    assert sum(after.values()) < sum(before.values()) - 0.05
    for _ in range(12):                                      # the engineers mend it, in a few hours
        st.interdiction = {kk: vv * 0.94 for kk, vv in st.interdiction.items()}
    st.interdiction = {kk: vv * 0.3 for kk, vv in st.interdiction.items()}
    st.compute_supply()
    assert sum(st.supply_of(p.side, f) for f in fed) > sum(after.values())
    st.interdiction = {}
    st.compute_supply()
    # and on the ground: convoys come and go, and a burnt-out lorry is a cut
    g.map = None
    to_land(g, s)
    assert RR.lanes(g, p.side) is not None
    kinds = set()
    trucks = []
    for i in range(4000):
        g.player.moves = 0
        g.world_turn()
        for c in g.__dict__.get("rear", {}).get("convoys", {}).values():
            kinds.add(c["kind"])
        if i % 50 == 0:
            trucks = [v for v in g.vehicles if v.ai.get("convoy") and not v.dead and v.side == p.side]
            if trucks and len(kinds) > 1:
                break
    assert kinds and trucks and RR.describe(trucks[0])
    cut0 = st.cut_of(p.side, s)
    destroy_vehicle(g, trucks[0], None, "a test")
    assert st.cut_of(p.side, s) > cut0


def test_orders_book_autopilot_and_succession():
    """Several orders at once, with who gave them and what follows; the autopilot; carrying on as someone
    else when you die."""
    import tcod
    from fow.combat import hit_actor
    from fow.constants import SCREEN_H, SCREEN_W
    from fow.orders import book
    from fow.play import Key, PlayState
    from fow import base as BASE
    fa = FakeApp()
    fa.settings.update(succession="on", succession_rule="squad", succession_side="own", succession_lives=0)
    g = Game("bocage44", "usa", role="rifleman", seed=5, setup={"battlefield": "standard"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    p = g.player
    sup = p.squad.leader
    g.duty.give(g, "dig", sup)
    g.duty.give(g, "scout", sup, (p.x + 10, p.y), leg="out")
    g.update_orders(force=True)
    b = book(g)
    duties = [o for o in b if o["key"].startswith("duty:")]
    assert len(duties) >= 2 and all(o["who"] and o["reward"] and o["penalty"] for o in duties)
    ps.on_key(Key(char="T"))
    assert type(fa.states[-1]).__name__ == "OrdersState"
    con = tcod.console.Console(SCREEN_W, SCREEN_H, order="F")
    fa.states[-1].render(con)
    fa.states[-1].on_key(Key(sym=tcod.event.KeySym.ESCAPE))
    assert fa.states[-1] is ps
    t = g.duty._tasks()[0]
    t["deadline"] = g.turn - 1
    t["nagged"] = True
    g.duty._check_task(g, t)
    assert BASE._state(g).get("fatigues", 0) > 0             # a chewing-out, and extra duty at the next base
    # the autopilot: he goes on without you
    for a in g.actors:
        if a.side != p.side and a.alive:
            a.body.dead = True
            g.kill(a, None)
    for b in g.support.fires.batteries:              # (their guns and aircraft are real, and would find him)
        if b.side != p.side:
            b.ammo = 0
    g.support.next_sortie = {k: 10 ** 9 for k in g.support.next_sortie}
    g.waves = []
    g.shells = []
    for v in list(g.vehicles):                       # (and their tanks: the crews are counted, not all actors)
        if v.side != p.side:
            g.remove_vehicle(v) if hasattr(g, "remove_vehicle") else setattr(v, "dead", True)
    ps.on_key(Key(char="A"))
    assert g.autopilot
    t0 = g.turn
    for _ in range(60):
        ps.anim = ps.anim_next = 0
        ps.tick()
    assert g.turn > t0 + 30, (g.turn - t0, p.state, g.autopilot, [m.text for m in list(g.messages)[-8:]])
    ps.on_key(Key(char="A"))
    assert not g.autopilot
    # succession: the war goes on
    ps.on_key(Key(char="A"))
    hit_actor(g, p, 999, "gunshot", None, "a test", part="head")
    assert not p.alive and g.player is not p and g.player.alive and not g.game_over
    assert not g.autopilot and len(g.lives) == 1 and g.player.side == p.side
    assert not p.is_player and g.player.is_player
    _turns(g, 20)
    fa.settings["succession"] = "choose"
    second = g.player
    hit_actor(g, second, 999, "gunshot", None, "a test", part="head")
    assert g.__dict__.get("succession_pending") and not g.game_over
    ps.anim = ps.anim_next = 0
    ps.tick()
    assert ps.popups
    ps.popup_select()
    assert g.player is not second and g.player.alive and len(g.lives) == 2
    fa.settings["succession_lives"] = 2
    hit_actor(g, g.player, 999, "gunshot", None, "a test", part="head")
    assert g.game_over                                        # (out of lives)


def test_sight_lines_compiled_match():
    """The compiled look-round (numba) sees exactly what the one-line-at-a-time path sees."""
    import math
    import numpy as np
    from fow import fastpath as FP
    from fow import senses as S
    from fow.relief import body_height, elevation, eye_height, flat
    if not FP.lines_ready():
        return                                    # (no numba: only the one path exists)
    n = bad = 0
    for th, nat in (("kursk43", "ussr"), ("stalingrad42", "germany")):
        g = Game(th, nat, seed=5, setup={"battlefield": "standard"})
        _turns(g, 40)
        m = g.map
        m.smoke[:] = 0
        m.update_see(force=True)
        for a in [x for x in g.actors if x.alive and x.vehicle is None and not getattr(x, "z", 0)][:60]:
            es = [e for e in g.actors if e.side != a.side and e.alive and not getattr(e, "z", 0) and
                  math.hypot(e.x - a.x, e.y - a.y) < 70][:30]
            if not es:
                continue
            ok = FP.sight_lines(m.see, m.high(), elevation(m), not flat(m), a.x, a.y, eye_height(a), S._high(a),
                                np.array([e.x for e in es], np.int64), np.array([e.y for e in es], np.int64),
                                np.array([body_height(e) for e in es], np.float64),
                                np.array([S._high(e) for e in es], np.bool_))
            for e, v in zip(es, ok):
                n += 1
                bad += bool(v) != bool(S._sight_line(g, a, e))
    assert n > 500 and bad == 0


def test_squad_tactics():
    """Being shot at is contact; the section leader calls the machine gun; a tank waits for its infantry."""
    from fow import ai as AI
    from fow.combat import suppress_line
    g = Game("bocage44", "usa", seed=3, setup={"battlefield": "standard"})
    for b in g.support.fires.batteries:
        b.ammo = 0
    sq = next(q for q in g.squads if q.side == g.player_side and q.kind == "rifle" and q.members and
              q is not g.player.squad)
    man = next(mm for mm in sq.members if mm.active)
    sq.last_contact = -999
    suppress_line(g, man.x + 30, man.y, man.x, man.y, 40, "axis" if man.side == "allies" else "allies")
    assert man.ai.get("fired_on") and man.ai["fired_on"][:2] == (man.x + 30, man.y)
    AI.squad_update(g, sq)
    assert sq.last_contact == g.turn and sq.__dict__.get("fired_from")
    # fire control: an enemy machine gunner in view
    mg = next(e for e in g.actors if e.side != sq.side and e.active and e.weapon is not None and
              e.weapon.t.cat in ("lmg", "hmg"))
    for mm in sq.members:
        mm.visible = [mg]
        mm.vis_turn = g.turn
    AI.designate(g, sq)
    assert sq.focus[0] == mg.id
    assert AI.choose_target(g, man, [mg] + [e for e in g.actors if e.side == mg.side][:3]) is not None
    # a tank far ahead of the riflemen going for the same place halts for them
    tanks = [v for v in g.vehicles if v.squad is not None and v.squad.kind == "tank" and not v.dead]
    assert tanks
    tank = tanks[0]
    inf = min((q for q in g.squads if q.side == tank.side and q.kind == "rifle" and q.anchor() is not None),
              key=lambda q: max(abs(q.anchor()[0] - tank.x), abs(q.anchor()[1] - tank.y)))
    for q in g.squads:                            # (only that one squad, 20 tiles behind the tank)
        if q is not inf and q.side == tank.side and q.kind == "rifle":
            q.gone = True
    g.soldier_at.pop((inf.leader.x, inf.leader.y), None)
    inf.leader.x, inf.leader.y = tank.x, max(0, tank.y - 20) if tank.y >= 20 else tank.y + 20
    anc = inf.anchor()
    ahead = (tank.x, tank.y + (tank.y - anc[1]) * 2)
    tank.ai.pop("inf_wait", None)
    tank.ai.pop("hit_turn", None)
    assert AI.waits_for_infantry(g, tank, ahead)
    tank.ai.pop("inf_wait", None)
    assert not AI.waits_for_infantry(g, tank, anc)                # (going back toward them: no waiting)


def test_interface_pictures():
    """Every picture the interface can ask for paints (the renderer hides a painter's error as a blank)."""
    from fow import icons as I
    from fow.data.items import ITEMS
    from fow.data.nations import NATIONS
    from fow.entities import Item
    from fow.strategic import BIOME_GLYPH
    n = 0
    for tid in ITEMS:
        try:
            it = Item(tid)
        except Exception:
            continue
        k = I.item_key(it)
        if k is None:
            continue
        for w, h in ((20, 4), (4, 2), (5, 2)):
            a = I.paint(I.oriented(k, w, h), w * 10, h * 19)
            assert a is not None and a.shape == (h * 19, w * 10, 4), (tid, k)
            n += 1
    keys = ["doll|head:96c88c:,torso:e6c850:b2:1,l_arm:f06e3c:B:1,r_arm:96c88c::0,l_leg:f04632:T:2,r_leg:96c88c::0",
            "stance|0|0", "stance|1|40", "stance|2|80", "stance|swim|0", "stance|veh|0", "rounds|4|8|8", "rounds|0|0|30",
            "rounds|120|180|250", "watch|06:15", "sky|0.3|overcast|0.1", "sky|0.05|clear|0.8", "sky|0.8|snow|0.5",
            "sky|0.7|fog|0.5", "pointer|135|compass", "pointer|300|hand", "man|ok", "man|dead", "man|down",
            "sight|0|40|40|0|1.0", "sight|2|0|85|1|0.2", "badge:dim|8/8", "badge:warn|LIVE!", "~gun:rifle",
            "vehicle|tank|green|driver:on,gunner:you,commander:off"]
    keys += [f"emblem|{nat}" for nat in NATIONS] + [f"recruit|{nat}|rifleman" for nat in NATIONS]
    keys += [f"recruit|usa|{r}" for r in I.ROLE_ARMS] + ["recruit||rifleman"]
    keys += [f"terrain|{b}|{c}|{sk}|3,4" for b in BIOME_GLYPH for c in ("ours", "theirs", "none", "unknown")
             for sk in (0, 1)]
    keys += [f"log:x|{c}" for c in ("sound", "radio", "shout", "hurt", "hit", "death", "good", "warn", "think",
                                     "combat")]
    keys += [f"how:x|{h}" for h in ("shouted", "by runner", "on the radio", "written orders", "briefing",
                                     "the fire direction centre's numbers")]
    keys += [f"sense:x|{s_}" for s_ in ("cold", "hot", "mild", "breath", "load", "nerves")]
    for k in keys:
        a = I.paint(k, 90, 57)
        assert a is not None and a[..., 3].max() > 0, k
        n += 1
    assert n > 1000


def test_machine_guns_pick_what_they_can_hurt():
    """A vehicle's machine gun fires at men and at what its rounds go through - not at a buttoned-up tank."""
    from fow import ai as AI
    from fow.entities import Vehicle
    g = Game("kursk43", "germany", seed=3, setup={"battlefield": "standard"})
    mine = next(v for v in g.vehicles if v.side == g.player_side and v.vt.mgs and not v.dead)
    idxs = [0]
    enemy = "allies" if mine.side == "axis" else "axis"
    nat = g.side_nation(enemy)
    heavy = Vehicle("kv1" if nat == "ussr" else "m4_sherman", enemy, nat, mine.x + 12, mine.y)
    heavy.buttoned = True
    lorry = Vehicle("studebaker", enemy, nat, mine.x, mine.y + 10)
    man = next(a for a in g.actors if a.side == enemy and a.active)
    mg = ITEMS[mine.vt.mgs[0]]
    if (mg.pen or 0) < 25:
        assert AI.mg_can_hurt(mine, idxs, heavy) == 0          # sparks off the plate
    assert AI.mg_can_hurt(mine, idxs, lorry) == 2
    assert AI.mg_can_hurt(mine, idxs, man) == 2
    heavy.buttoned = False
    heavy.x, heavy.y = mine.x + 8, mine.y
    assert AI.mg_can_hurt(mine, idxs, heavy) in (1, 2)          # a head out of the hatch, close enough


def test_talk_trade_and_the_noise_of_war():
    """Anyone near can be talked to - his life, his state, what he's seen, a trade; the wounded scream in their
    own language and their mates shout their names; valour wipes out the black marks."""
    from fow import people as PP
    from fow import social as SO
    from fow import talk as TK
    from fow import base as BASE
    from fow.combat import hit_actor
    from fow.entities import Item
    from fow.play import PlayState
    fa = FakeApp()
    g = Game("bocage44", "usa", role="rifleman", seed=5, setup={"battlefield": "standard"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    for b in g.support.fires.batteries:
        b.ammo = 0
    p = g.player
    mate = next(m for m in p.squad.members if m is not p and m.active)
    g.soldier_at.pop((mate.x, mate.y), None)
    mate.x, mate.y = p.x + 1, p.y
    g.soldier_at[(mate.x, mate.y)] = mate
    lf = PP.life(mate)
    assert lf["town"] and PP.life(mate) is lf                   # (the same man every time)

    def choose(value):
        pop = ps.popups[-1]
        k = next(i for i, o in enumerate(pop.options) if o[1] == value)
        pop.sel = k
        ps.popup_select()
    ps.popups = []
    TK.open_talk(ps, mate)
    choose("home")
    assert any(lf["town"] in m.text for m in list(g.messages)[-40:])
    ps.popups = []
    TK.open_talk(ps, mate)
    choose("state")
    # a trade: he'll take cigarettes for a clip (a smoker's price)
    mine = p.add_item(Item("cigarettes")) or p.find(lambda i: i.t.tool == "cigarettes") or Item("cigarettes")
    his = next(i for i in mate.inv if PP.tradeable(mate, i))
    assert PP.worth(g, mate, mine) > 0 and isinstance(PP.deal(g, mate, his, mine, 50), bool)
    # the noise: a man hit in the leg cries out, and his buddy shouts his name
    bd = PP.buddy(g, mate)
    if bd is not None:
        g.soldier_at.pop((bd.x, bd.y), None)
        bd.x, bd.y = mate.x + 2, mate.y
        g.soldier_at[(bd.x, bd.y)] = bd
        bd.ai.pop("said", None)
    mate.ai.pop("said", None)
    hit_actor(g, mate, 30, "gunshot", None, "a test", part="l_leg")
    assert mate.shout and mate.shout[0]
    if bd is not None and bd.active:
        assert PP.call_name(mate) in (bd.shout or ("",))[0]
    e = next(a for a in g.actors if a.side != p.side and a.active)
    e.ai.pop("said", None)
    from fow.data.chatter import C, UNIVERSAL
    from fow.data.phrases import lang
    assert SO.say(g, e, "hit_bad", "scream", gap=0)
    assert e.shout[0] in (C["hit_bad"].get(lang(e.nation)) or UNIVERSAL["hit_bad"])    # (in his own language)
    # a failed order, then the objective taken: the slate is wiped
    d = g.duty
    for _ in range(3):
        d.give(g, "dig", p.squad.leader)
        t = d._tasks()[-1]
        t["deadline"] = g.turn - 1
        t["nagged"] = True
        d._check_task(g, t)
    assert d.strikes >= 3 and BASE._state(g).get("fine_days")
    ob = g.map.objectives[0]
    g.soldier_at.pop((p.x, p.y), None)
    p.x, p.y = ob.x, ob.y
    g.soldier_at[(p.x, p.y)] = p
    g.command.on_objective(g, 0, p.side)
    g.command.on_objective(g, 0, p.side)
    assert d.strikes < 3 and not BASE._state(g).get("fine_days")


def test_use_things_where_they_lie():
    """A dressing on the ground, the dead man's morphine: used without picking them up first."""
    from fow.combat import hit_actor
    from fow.entities import Item
    from fow.play import PlayState
    fa = FakeApp()
    g = Game("bocage44", "usa", role="rifleman", seed=5, setup={"battlefield": "standard"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    for b in g.support.fires.batteries:
        b.ammo = 0
    p = g.player
    if p.vehicle is not None:                        # (riding a tank's hull: down first)
        ps._vehicle_choice(p.vehicle, ("exit", None))
    assert p.vehicle is None
    for i in list(p.inv):
        if i.t.kind == "medical":
            p.remove_item(i)
    g.map.add_item(p.x + 1, p.y, Item("bandage"))
    hit_actor(g, p, 30, "gunshot", None, "a test", part="l_arm")
    assert p.body.bleed_rate() > 0
    ps.popups = []
    ps.cmd_apply()
    pop = ps.popups[-1]
    k = next(i for i, o in enumerate(pop.options) if isinstance(o[1], tuple) and o[1][0] == "near" and
             o[1][1].tid == "bandage")
    pop.sel = k
    ps.popup_select()
    assert p.body.bleed_rate() == 0
    assert not any(i.tid == "bandage" for i in g.map.items_at(p.x + 1, p.y))    # (used up, off the ground)


def test_notable_units():
    """Serve in a famous division: its real regiments on your papers, its real commander above you."""
    from fow.data.nations import unit_designation
    from fow.data.notable import NOTABLE, division
    from fow.data.theatres import THEATRES
    from fow.hierarchy import Hierarchy
    import random
    for k, d in NOTABLE.items():
        assert d["theatres"] and all(t in THEATRES for t in d["theatres"]), k
        assert any(n == d["nation"] for t in d["theatres"] for side in THEATRES[t]["sides"].values()
                   for n, _w in side), k
    g = Game("omaha44", "usa", role="rifleman", seed=3, setup={"battlefield": "standard", "unit": "notable:us_1id"})
    p = g.player
    assert p.unit.endswith("1st Infantry Division") and any(r in p.unit for r in NOTABLE["us_1id"]["regiments"])
    chain = " ".join(w for _post, w in Hierarchy().chain_lines(g, p))
    assert "Huebner" in chain
    rng = random.Random(1)
    for _ in range(20):
        u = unit_designation(rng, "ussr", ["13th Guards Rifle Division"])
        assert any(r in u for r in NOTABLE["su_13gd"]["regiments"])
    assert division(NOTABLE["de_gd"], "france40") == "Infanterie-Regiment Großdeutschland"


def test_landmarks_and_the_going():
    """What you can't get through looks it (a rim and a shadow), what's slow says so, X tints the lot; and every
    country has its landmarks to fight over - windmills, stations, châteaux, forts, shrines, lighthouses."""
    import random
    import numpy as np
    from fow import floors, going, landmarks as L, sprites as S, tiles as T
    from fow.mapgen import Gen
    from fow.play import PlayState
    from fow.render import draw_map, Camera
    # every tile paints, and a tree stands out of the ground with a dark rim where the jungle lies flat
    for tid in range(T.NUM):
        assert S.paint_terrain(tid, tid % 4).shape == (64, 64, 4)

    def rim(key):
        a = S.paint_terrain(T.ID[key], 0).astype(int)
        return int(((a[..., :3].sum(axis=2) < 70) & (a[..., 3] > 200)).sum())
    assert rim("tree") > 3 * max(1, rim("jungle")) and rim("palm") > rim("bamboo")
    # the words, from the real costs
    fa = FakeApp()
    g = Game("kohima44", "uk", role="rifleman", seed=1, setup={"battlefield": "standard"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    m = g.map

    def first(key):
        pts = np.argwhere(m.t == T.ID[key])
        return (int(pts[0][0]), int(pts[0][1])) if len(pts) else None
    for key, word in (("tree", "No way through"), ("jungle", "slow going"), ("cliff", "No way through")):
        at = first(key)
        if at is not None:
            text, _col = going.words(g, *at)
            assert word.lower() in text.lower() and (key != "jungle" or "can't see" in text), (key, text)
    at = first("jungle")
    if at is not None:
        m.explored[at] = m.visible[at] = True
        fa.show_numbers = True
        assert any("\u00d7" in ln for ln, _c in ps.describe_tile(*at)[0])
    col, a = going.tint(g, slice(0, m.w), slice(0, m.h))
    assert (a[~m.walk] >= 0.5).all() and a[m.walk & (m.cost_foot <= 100)].max() == 0
    ps.cmd_going()
    assert ps.going_on()
    import tcod
    con = tcod.console.Console(80, 50, order="F")
    draw_map(con, g, Camera(), 0, going=True)
    ps.cmd_going()
    assert not ps.going_on()
    # landmarks by country: each map gets a few, and they're the objectives
    want = {("farmland", "summer", "fr"): ("the windmill", "the station", "the halt", "the château", "the cemetery",
                                           "the water tower", "the brickworks", "the radar station",
                                           "the landing strip", "the railway line", "the railway cutting"),
            ("desert", "desert", "ar"): ("the fort", "the marabout", "the landing ground", "the oasis", "the tomb"),
            ("jungle", "tropical", "mel"): ("the coconut plantation", "the plantation", "the mission", "the airstrip"),
            ("hills", "tropical", "ja"): ("the shrine",),
            ("steppe", "summer", "ru"): ("the grain elevator", "the kolkhoz", "the collective farm", "the windmill")}
    for (b, cl, lang), names in want.items():
        found = 0
        for seed in range(1, 5):
            spec = dict(w=180, h=120, biome=b, climate=cl, seed=seed, attacker_edge="N", defender_side="axis",
                        fort=1, lang=lang, east=lang == "ru", theatre="x", roads=["N", "S"], installations=[])
            gen = Gen(spec)
            mp = gen.run()
            pois = [p[0] for p in gen.poi]
            found += any(any(n in q for n in names) for q in pois)
            assert mp.objectives
        assert found >= 3, (b, lang)
    # a lighthouse on the bluff above a beach; towers you climb have open tops
    spec = dict(w=180, h=120, biome="bocage", climate="summer", seed=3, attacker_edge="S", defender_side="axis",
                fort=1, lang="fr", sea_edge="N", inland="bocage", roads=["S"], installations=[])
    gen = Gen(spec)
    gen.base_ground()
    gen.beach("N")
    gen.rng = random.Random(1)
    assert L.lighthouse(gen) and any(bb[4] == "lighthouse" for bb in gen.m.buildings)
    assert {"lighthouse", "tower", "keep"} <= floors.OPEN_TOP
    assert T.ID["oil_tank"] in T.EXPLODE and not T.WALK[T.ID["boxcar"]] and T.WALK[T.ID["platform"]]


def test_waiting_goes_quickly():
    """Z: a set time, until something happens, until orders - every second simulated, many to a frame; a new
    order stops it; without a watch the choices go by feel; aboard a quiet ship Z lets the hours go by."""
    from fow.play import Key, PlayState
    from fow.skysea_exit import to_land
    fa = FakeApp()
    g = Game("bocage44", "usa", role="rifleman", seed=3, setup={"battlefield": "standard"})
    ps = PlayState(fa, g)
    fa.states = [ps]
    p = g.player
    g.map = None
    to_land(g, next(s for s in g.strategic.sectors() if s.control == p.side and s.installs(p.side, "motor_pool")))
    ps.popups = []
    ps.cmd_wait()
    labels = [o[0] for o in ps.popups[-1].options]
    assert ("15 minutes" in labels) == (p.has_tool("watch") is not None)
    assert any("new orders" in lab for lab in labels) and any(k in " ".join(labels) for k in ("first light", "dark"))
    ps.popups[-1].sel = 1                          # five minutes / a few minutes
    ps.popup_select()
    t0, frames = g.turn, 0
    while ps.auto_wait > 0 and frames < 300:
        ps.anim, ps.anim_next = 0, 0
        ps.tick()
        frames += 1
    assert ps.auto_wait == 0 and ps.wait is None
    assert g.turn - t0 >= 20 and (g.turn - t0) / max(1, frames) > 3, (g.turn - t0, frames)
    # new orders end a wait
    ps.begin_wait("event", 3600)
    ps.tick()
    sup = next(a for a in g.actors if a.side == p.side and a.alive and a is not p and a.rank > p.rank)
    g.duty.give(g, "dig", sup)
    for _ in range(40):
        if ps.auto_wait <= 0:
            break
        ps.anim, ps.anim_next = 0, 0
        ps.tick()
    assert ps.auto_wait == 0 and any("New orders" in m.text or "catches your attention" in m.text
                                     for m in list(g.messages)[-6:])
    # z: a minute
    t0 = g.turn
    ps.cmd_rest()
    while ps.auto_wait > 0:
        ps.anim, ps.anim_next = 0, 0
        ps.tick()
    assert 0 < g.turn - t0 <= 61
    # aboard a quiet ship, Z is the long fast-forward again
    g2 = Game("okinawa45", "usa", role="sailor", seed=3,
              setup={"battlefield": "standard", "service": "navy", "scenario": "sea:convoy"})
    fa2 = FakeApp()
    ps2 = PlayState(fa2, g2)
    fa2.states = [ps2]
    ps2.on_key(Key(char="Z"))
    assert ps2.__dict__.get("ff_until") or ps2.popups


def test_parked_aircraft_are_full_size():
    """Aircraft on the ground are as big as they were (a B-17 sixteen tiles across), each tile the part it is;
    they're named when you look, kept with the sector when you leave it - and so are the hills and the floors."""
    import random
    import numpy as np
    from fow import parked as PK, tiles as T
    from fow import shipyard as SY
    from fow.skysea import Ship
    from fow.skysea_exit import to_land
    assert PK.box("bf109", 0) == (5, 5) and PK.box("b17", 0)[0] >= 15 and PK.box("f6f", 1, True) == (5, 3)
    S, L, g = PK.grid("he111")
    flat = [c for row in g for c in row]
    assert flat.count("ac_engine") >= 4 and flat.count("ac_body") >= L - 1 and flat.count("ac_wing") >= 6
    # an airfield behind our lines
    g = Game("bocage44", "usa", role="rifleman", seed=3, setup={"battlefield": "standard"})
    p = g.player
    s0 = next(s for s in g.strategic.sectors() if s.control == p.side and s.installs(p.side, "motor_pool"))
    s0.installations = [["airfield", p.side, True]]
    s0.saved = None
    g.map = None
    to_land(g, s0)
    m = g.map
    recs = m.__dict__.get("parked") or []
    assert len(recs) >= 3
    rec = recs[0]
    assert rec["w"] * rec["h"] >= 20 and rec["model"] not in PK.CARRIER_OK      # (no carrier types ashore in France)
    parts = PK.cells(rec["model"], rec["x"], rec["y"], rec["facing"], rec["folded"])
    assert all(T.DEFS[int(m.t[x, y])].key == k for x, y, k in parts)
    bx, by = next((x, y) for x, y, k in parts if k == "ac_body")
    assert "parked" in PK.describe(m, bx, by) and not T.WALK[m.t[bx, by]]
    wx, wy = next(((x, y) for x, y, k in parts if k == "ac_wing"), (None, None))
    if wx is not None:
        assert T.WALK[m.t[wx, wy]] and T.COST[m.t[wx, wy]] > 150
    # it burns: a fuselage destroyed goes up and leaves a wreck
    from fow.combat import damage_tile
    damage_tile(g, bx, by, 10000)
    assert T.DEFS[int(m.t[bx, by])].key == "ac_wreck" and g.pending_explosions
    # leave the sector and come back: the aircraft, the hills and the floors are all still there
    elev = m.elev.copy()
    storeys = dict(m.__dict__.get("storeys") or {})
    g._save_map()
    m2 = g._load_map(s0)
    assert len(m2.__dict__.get("parked") or []) == len(recs)
    assert np.allclose(m2.elev, elev) and dict(m2.__dict__.get("storeys") or {}) == storeys
    # a carrier's flight deck: the air group spotted aft, wings folded
    ship = Ship("essex", "allies", "usa", 0, 0, 0, rng=random.Random(1))
    decks, _order, _fr = SY.build(ship, random.Random(2))
    fl = decks["flight"].map.__dict__.get("parked") or []
    assert len(fl) >= 12 and all(r["folded"] or r["model"] == "sbd" for r in fl)
    assert any(r["model"] in ("sbd", "sb2c") for r in fl) and any(r["model"] == "tbf" for r in fl)


if __name__ == "__main__":
    import time
    tests = [(k, v) for k, v in dict(globals()).items() if k.startswith("test_") and callable(v)]
    bad = 0
    for name, fn in tests:
        t0 = time.perf_counter()
        try:
            fn()
            print(f"ok    {name}  ({time.perf_counter() - t0:.1f}s)")
        except Exception:
            import traceback
            bad += 1
            print(f"FAIL  {name}")
            traceback.print_exc()
    sys.exit(1 if bad else 0)
