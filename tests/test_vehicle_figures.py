"""Visible crews follow the simulation and respect covered interiors and fog of war.

    python tests/test_vehicle_figures.py
"""
from __future__ import annotations

import math
import pickle
from functools import lru_cache

from test_smoke import Game  # isolated saves and headless SDL before importing renderers
from test_squadcare import scene
import numpy as np
import tcod

from fow import actions, vdamage
from fow.data.vehicles import VEHICLES
from fow.entities import Actor, Item, Vehicle
from fow.footprint import rect_center
from fow.render import Camera, draw_entities
from fow.render_sprites import draw_sprite_layers, N_LAYERS
from fow.sprites import SpriteBank, vehicle_class
from fow.vehicle_figures import appearance, occupants


@lru_cache(maxsize=1)
def bank():
    return SpriteBank()


def vehicle(vid="m3_ht", facing=0):
    return Vehicle(vid, "allies", "usa", 20, 20, facing)


def passenger(v):
    a = Actor(v.nation, "rifleman", 0, "Passenger", v.x, v.y)
    a.vehicle = v
    v.passengers.append(a)
    return a


def battlefield(vid="m3_ht"):
    g, _, _, _ = scene()
    g.actors, g.squads = [g.player], []
    g.soldier_at = {g.player.pos: g.player}
    g.effects, g.front_marks = [], []
    g.add_vehicle(v := vehicle(vid))
    cam = Camera()
    cam.configure(40, 36)
    cam.x0 = cam.y0 = 0
    return g, v, cam


def test_open_transports_show_actual_passengers_and_ignore_stale_references():
    for vid in ("m3_ht", "jeep", "lcvp", "lvt"):
        v = vehicle(vid)
        assert len(occupants(v)) == v.crew
        people = [passenger(v) for _ in range(v.vt.seats)]
        assert len(occupants(v)) == v.crew + len(people)
        people[0].body.dead = True
        people[1].vehicle = None
        assert len(occupants(v)) == v.crew + len(people) - 2


def test_boarding_and_dismounting_change_the_render_without_duplicate_soldiers():
    g, v, cam = battlefield()
    p = g.player
    g.remove_from_map(p)
    p.x, p.y = 20, 19
    g.place_on_map(p)
    assert actions.enter_vehicle(g, p, v) == 150
    assert len(occupants(v)) == v.crew + 1
    assert p.pos not in g.soldier_at
    layers = draw_sprite_layers(bank(), g, cam)
    assert not np.any(layers[4].ch)  # the mounted player isn't also drawn as an infantryman
    assert np.any(layers[6].ch)
    assert actions.exit_vehicle(g, p) == 150
    assert len(occupants(v)) == v.crew
    assert g.soldier_at[p.pos] is p
    assert np.any(draw_sprite_layers(bank(), g, cam)[4].ch)


def test_named_crew_replace_aggregate_figures_and_use_real_kit():
    g, v, _ = battlefield("bofors_us")
    v.crew = 0
    p = g.player
    g.remove_from_map(p)
    p.x, p.y = 20, 19
    g.place_on_map(p)
    p.invent.slots["body"] = Item("snow_smock")
    assert actions.enter_vehicle(g, p, v) == 200
    figures = occupants(v, "winter")
    assert len(figures) == v.crew == 1
    assert figures[0].appearance == appearance(v.nation, "winter", p)
    p.body.unconscious = 10
    assert occupants(v)[0].pose == "slumped"


def test_guns_show_remaining_crew_after_real_casualties():
    for vid in ("pak40_gun", "bofors_us", "flak88", "oerlikon", "m1_155"):
        g, v, _ = battlefield(vid)
        count = v.crew
        assert len(occupants(v)) == count
        vdamage.crew_hit(g, v, "gunner", None, "shell fragment", False)
        assert len(occupants(v)) == count - 1
        v.crew = 0
        assert occupants(v) == ()
        v.crew, v.abandoned = count, True
        assert occupants(v) == ()
        v.abandoned, v.dead = False, True
        assert occupants(v) == ()


def test_closed_hulls_hide_crew_but_show_open_hatch_and_actual_deck_riders():
    v = vehicle("m4")
    assert not occupants(v)
    v.buttoned = False
    assert [s.pose for s in occupants(v)] == ["hatch"]
    v.ai["seat_out"] = {"commander": 50}
    v.crew -= 1
    assert not occupants(v)
    v.buttoned = True
    for _ in range(4):
        passenger(v)
    assert len(occupants(v)) == 4
    for vid in ("gmc", "ambulance"):
        covered = vehicle(vid)
        for _ in range(3):
            passenger(covered)
        covered.buttoned = False
        assert not occupants(covered)


def test_open_turrets_show_only_exposed_stations():
    for vid in ("m10", "m18", "m36"):
        v = vehicle(vid)
        assert len(occupants(v)) == 3  # turret team; driver and assistant are under armour
    v = vehicle("m16_mgmc")
    assert len(occupants(v)) == v.crew
    vc = vehicle_class(v.vt)
    assert bank().vehicle_pieces(vc, v.nation, *v.size, 0, 2, "turret", open_top=True)


def test_riders_stay_with_hull_and_turret_crew_follow_traverse():
    v = vehicle("m4")
    for _ in range(4):
        passenger(v)
    before = occupants(v)
    v.turret = 2
    assert occupants(v) == before
    for facing in range(8):
        v.facing = facing
        cx, cy = rect_center(*v.size, facing)
        c0x, c0y = rect_center(*v.size, 0)
        ang = -facing * math.pi / 4
        for source, turned in zip(before, occupants(v)):
            x, y = source.x - c0x, source.y - c0y
            assert abs(turned.x - cx - (x * math.cos(ang) - y * math.sin(ang))) < .001
            assert abs(turned.y - cy - (x * math.sin(ang) + y * math.cos(ang))) < .001
    v = vehicle("m10")
    before = occupants(v)
    v.turret = 2
    assert occupants(v) != before and len(occupants(v)) == len(before)


def test_gun_traverse_keeps_carriage_fixed_and_loading_changes_poses():
    g, v, cam = battlefield("pak40_gun")
    first = draw_sprite_layers(bank(), g, cam)
    v.facing = 2
    turned = draw_sprite_layers(bank(), g, cam)
    assert np.array_equal(first[3].ch, turned[3].ch)
    assert not np.array_equal(first[5].ch, turned[5].ch)
    v.reload = 8
    assert any(s.pose == "load" for s in occupants(v, turn=2))
    v.reload = 0
    assert all(s.pose != "load" for s in occupants(v, turn=2))


def test_crew_do_not_reveal_unseen_tiles_and_smoke_covers_them():
    g, v, cam = battlefield("bofors_us")
    full = draw_sprite_layers(bank(), g, cam)
    assert len(full) == N_LAYERS and np.any(full[6].ch)
    g.map.visible[:] = False
    assert not np.any(draw_sprite_layers(bank(), g, cam)[6].ch)
    g.map.visible[v.pos] = True
    partial = draw_sprite_layers(bank(), g, cam)
    mask = partial[6].ch != 0
    assert not np.any(mask & ~g.map.visible[:cam.vw, :cam.vh])
    g.map.visible[:] = True
    g.map.smoke[v.pos] = 2
    smoky = draw_sprite_layers(bank(), g, cam)
    assert smoky[7].ch[v.pos] == bank().effect("smoke", 0)
    assert smoky[7].rgba["fg"][v.pos][3] > 0


def test_text_renderer_marks_occupied_areas_without_losing_vehicle_type():
    g, v, cam = battlefield()
    for _ in range(6):
        passenger(v)
    con = tcod.console.Console(160, 80, order="F")
    draw_entities(con, g, cam)
    assert con.ch[cam.to_screen(*v.pos)] == ord(v.vt.glyph)
    marks = {(x, y) for x, y in v.cells() if con.ch[cam.to_screen(x, y)] == ord("@")}
    assert marks
    v.passengers.clear()
    v.crew, v.abandoned = 0, True
    con.clear()
    draw_entities(con, g, cam)
    assert all(con.ch[cam.to_screen(*pos)] != ord("@") for pos in marks)


def test_all_exposed_types_paint_in_every_direction_and_cache_without_state_changes():
    b = bank()
    for vid, vt in VEHICLES.items():
        if not (vt.static or vt.open_top):
            continue
        v = vehicle(vid)
        v.reload = 5
        for facing in range(8):
            v.facing = v.base_facing = v.turret = facing
            figures = occupants(v, turn=2)
            if vt.static:
                assert len(figures) == vt.crew, vid
            if not figures:
                continue
            pieces = b.vehicle_crew_pieces(figures)
            assert pieces and all(np.any(b.master[cp][..., 3]) for _, _, cp in pieces), vid
            before = pickle.dumps(v)
            allocated = b.next_cp
            assert b.vehicle_crew_pieces(occupants(v, turn=6)) == pieces
            assert b.next_cp == allocated and pickle.dumps(v) == before


if __name__ == "__main__":
    import traceback
    tests = [(name, fn) for name, fn in list(globals().items()) if name.startswith("test_") and callable(fn)]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print("ok   ", name, flush=True)
        except Exception:
            failures += 1
            print("FAIL ", name, flush=True)
            traceback.print_exc()
    print(f"{len(tests) - failures}/{len(tests)} tests passed")
    raise SystemExit(bool(failures))
