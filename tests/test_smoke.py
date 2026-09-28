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
    for _ in range(4 * 360):                       # four hours in 10-second steps
        SB.fast_step(g, 10)
        g.aboard["task"] = None
        if ss.over or not me.alive:
            break
    enemy = [s for s in ss.ships if s.side != me.side]
    assert any(s.hp < hp0[s.id] for s in enemy), "four hours and not a scratch on the enemy"
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
    it = Item("shell_crate")
    it.data = dict(rounds=MT.CRATE_ROUNDS)
    p.invent.hands = it
    plan = ps._order_plan()
    assert plan is not None and "hand" in plan[0], plan
    before = v.ai.get("handed_by_player", 0)
    plan[1]()
    assert v.ai["handed_by_player"] == before + MT.CRATE_ROUNDS and p.invent.hands is None
    g.duty.update(g)
    assert g.duty.task is None


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
    for _ in range(2000):
        if f.player_mission(g) is not None:
            assert "FIRE MISSION" in g.player_orders
            ps._order_plan()[1]()
            fired += 1
            if fired >= 3:
                break
            continue
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
    before = sum(i.count for m in sq.members for i in m.inv if i.t.kind == "medical")
    for _ in range(90):
        _turns(g, 10)
        if sq.__dict__.get("task") is None:
            break
    assert sq.__dict__.get("task") is None
    assert sum(i.count for m in sq.members for i in m.inv if i.t.kind == "medical") > before
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
    p.add_item(Item("radio"))
    ok, why = MV.can_call(g)
    assert ok, why
    day0 = g.now()
    MV.call(ps)
    bearers = MV._bearers(g, g.medevac)
    assert len(bearers) == MV.TEAM and all(b in g.actors for b in bearers)
    carried = False
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
