"""The moving tactical frame preserves world state, paths and destinations."""
import pickle
from collections import Counter
from unittest.mock import patch
import numpy as np
import pytest
import tcod

from test_smoke import Game, FakeApp
from fow import streaming, tiles, service, orders
from fow.body import Wound
from fow.entities import Item
from fow.play import PlayState
from fow.constants import SCREEN_W, SCREEN_H


def world(seed=42, radius=120, theatre='bocage44'):
    g = Game(theatre, 'ussr' if theatre == 'stalingrad42' else 'usa', seed=seed,
             setup={'battlefield':'standard','reality_radius':radius})
    app = FakeApp()
    app.settings.update(autosave=False,fast_quiet=False)
    ps = PlayState(app,g)
    app.states = [ps]
    return g, ps, g.landscape


def reframe(g, st, dx=30, dy=0):
    g.remove_from_map(g.player)
    g.player.x += dx
    g.player.y += dy
    return st.refresh(g,force=True)


def test_radio_hunt_survives_a_detachment_leaving_the_detailed_circle():
    from types import SimpleNamespace as NS
    from fow import agents
    man = NS(active=False, body=NS(dead=False, unconscious=0), state='ok', _stream_dormant=True)
    van = NS(dead=False, x=9000, y=-7000, _stream_dormant=True)
    squad = NS(id=17, members=[man], vehicles=[van])
    hunt = {'squad':17, 'pos':(50,50), 'turn':10}
    def local_visibility(*args):
        pytest.fail('Dormant world coordinates must not be used as local visibility coordinates')
    g = NS(agent={'hunt':hunt, 'df':1100}, turn=20, squads=[],
           landscape=NS(squads={17:squad}), can_see=local_visibility)
    agents._hunt_tick(g)
    assert g.agent['hunt'] is hunt and g.agent['df'] == 1100
    man.body.dead = True
    agents._hunt_tick(g)
    assert g.agent['hunt'] is None and g.agent['df'] == 0


def test_reframe_preserves_people_wounds_ammo_terrain_orders_and_ordnance():
    g,ps,st = world()
    p = g.player
    a = next(a for a in g.actors if a is not p and a.vehicle is None and a.active and
             abs(a.x-p.x)<30 and abs(a.y-p.y)<30)
    original = st.world_pos(*a.pos)
    a.body.wounds.append(Wound('l_arm',1.,'gunshot'))
    a.ai['dig_at'] = a.pos
    a.known[123] = (*a.pos,g.turn,None)
    ammo = a.weapon.loaded if a.weapon else None
    px,py = p.pos
    marked = st.world_pos(px,py)
    g.map.set(px,py,'crater',refresh=True)
    marker = Item('bandage')
    g.map.add_item(px,py,marker)
    g.pending_explosions = [[px,py,50,2,0,5]]
    g.schedule_shell(px,py,5,50,2,0,0,p,'test shell')
    g.effects.append(dict(kind='tracer',x0=px,y0=py,x1=px+1,y1=py+1,t=g.turn))
    sq = a.squad
    sq.order.target = a.pos
    g.map.weather_ground = dict(wet=.8,snow=0.,changed={(px,py):(tiles.ID['grass'],tiles.ID['crater'])})
    reframe(g,st)
    assert st.world_pos(*a.pos) == original and st.actors[a.id] is a
    assert a.body.bleed_rate() == 1 and (a.weapon.loaded if a.weapon else None) == ammo
    assert st.world_pos(*a.ai['dig_at']) == original
    assert st.world_pos(*a.known[123][:2]) == original
    assert st.world_pos(*sq.order.target) == original
    local = marked[0]-st.origin[0], marked[1]-st.origin[1]
    assert g.map.tile(*local).key == 'crater' and marker in g.map.items[local]
    assert st.world_pos(*g.pending_explosions[0][:2]) == marked
    assert st.world_pos(g.shells[0]['x'],g.shells[0]['y']) == marked
    assert st.world_pos(g.effects[-1]['x0'],g.effects[-1]['y0']) == marked
    assert local in g.map.weather_ground['changed']
    with patch('fow.game.explode') as blast:
        for _ in range(6):
            g.turn += 1
            g._tick_shells()
        assert blast.call_count == 1 and blast.call_args.args[1:3] == local


def test_live_area_is_radial_and_negative_world_coordinates_are_unbounded():
    g,ps,st = world()
    # A chunk boundary cannot contain the active actors; nearby men share one frame.
    pworld = st.world_pos(*g.player.pos)
    assert all((st.world_pos(*a.pos)[0]-pworld[0])**2+(st.world_pos(*a.pos)[1]-pworld[1])**2 <= st.radius**2
               for a in g.actors if a.vehicle is None and a.ai.get('carried_by') is None)
    g.player.x,g.player.y = -st.w*3-st.origin[0], -st.h*2-st.origin[1]
    st.refresh(g,force=True)
    assert (g.sector.x,g.sector.y) == (-3,-2)
    assert st.world_pos(*g.player.pos) == (-st.w*3,-st.h*2)
    assert len(st.tactical_keys) < len(st.maps)
    assert any(isinstance(m,bytes) for m in st.maps.values())


def test_crossing_is_ordinary_movement_with_time_and_same_player_squad():
    from fow import actions
    g,ps,st = world()
    sec = g.sector
    wx = (sec.x+1)*st.w-1
    wy = sec.y*st.h+st.h//2
    g.player.x,g.player.y = wx-st.origin[0],wy-st.origin[1]
    st.refresh(g,force=True)
    p = g.player
    sq, hp, clock = p.squad,dict(p.body.hp),g.clock
    g.map.fill(p.x-2,p.y-2,p.x+5,p.y+3,'grass')
    g.map.refresh()
    g.soldier_at.pop((p.x+1,p.y),None)
    g.vehicle_at.pop((p.x+1,p.y),None)
    with patch.object(g,'travel',side_effect=AssertionError('sector teleport')):
        cost = actions.move(g,p,1,0)
        assert cost and cost > 0
        ps.act(cost)
    assert (g.sector.x,g.sector.y) == (sec.x+1,sec.y)
    assert st.world_pos(*p.pos) == (wx+1,wy)
    assert p.squad is sq and g.clock > clock


def test_preloaded_post_is_fixed_when_reached_and_loss_is_explicit():
    g,ps,st = world()
    key = (g.sector.x+4,g.sector.y)
    sec = g.strategic.at(*key,create=True)
    sec.control = g.player.side
    sec.installations.append(['motor_pool',g.player.side,True])
    m = st.preload(g,key)
    rec = next(r for r in m.gen_positions if r['kind']=='motor_pool' and r['side']==g.player.side)
    dest = service.post_destination(g,sec,rec)
    assert dest['point'] is not None and dest['world']
    ticket = dict(destination=dest)
    target = dest['world']
    g.player.x,g.player.y = target[0]-st.origin[0],target[1]-st.origin[1]
    st.refresh(g,force=True)
    assert service.assigned_destination(g,ticket,('motor_pool',)) is dest
    assert st.world_pos(*dest['point']) == target
    live = next(r for r in g.map.gen_positions if st.world_pos(r['x'],r['y']) == target)
    live['destroyed'] = True
    assert service.assigned_destination(g,ticket,('motor_pool',)) is None
    assert ticket['destination'] is dest and ticket['destination_lost']


def test_removed_actor_stays_removed_and_save_restores_identity(tmp_path):
    g,ps,st = world()
    a = next(a for a in g.actors if a is not g.player)
    aid = a.id
    g.remove_actor(a)
    reframe(g,st)
    assert aid not in st.actors and a not in g.actors
    path = str(tmp_path/'world.sav')
    g.save(path)
    loaded = Game.load(path)
    assert loaded.landscape.frame is loaded.map
    assert loaded.landscape.actors[loaded.player.id] is loaded.player
    loaded.world_turn()


def test_buildings_and_rendering_survive_multiple_frames():
    g,ps,st = world(theatre='stalingrad42')
    console = tcod.console.Console(SCREEN_W,SCREEN_H,order='F')
    for _ in range(3):
        for x,y in np.argwhere(g.map.t == tiles.ID['stairs']):
            assert g.map.building_at(int(x),int(y)) is not None
        ps.render(console)
        reframe(g,st,24,5)
        g.player_fov()
        for _ in range(5):
            g.world_turn()


def test_coarse_simulation_does_not_attrit_the_live_copy():
    g,ps,st = world()
    units = st.sector_units(g)
    for key,counts in units.items():
        if key in g.strategic.materialized:
            g.strategic.at(*key).units = counts
    with patch.object(g.strategic,'_attrit',wraps=g.strategic._attrit) as attrit:
        g.strategic.tick(g.sector,g.local_units())
    active_counters = {id(u) for key in st.tactical_keys for u in g.strategic.at(*key).units.values()}
    assert all(id(call.args[0]) not in active_counters for call in attrit.call_args_list)


def test_near_spatial_index_matches_exhaustive_queries_after_moves():
    g,ps,st = world()
    g.actor_array()
    for a in g.actors[::7]:
        a.x += 17
        g.note_move(a)
    for r in (1,3,7,25,48,70):
        x,y = g.player.pos
        expected = [a for a in g.actors if a.alive and a.vehicle is None and abs(a.x-x)<=r and abs(a.y-y)<=r]
        assert g.near(x,y,r) == expected


def test_dormant_squad_members_do_not_become_casualties_or_trigger_succession():
    from test_squadcare import scene
    from fow.ai import squad_update
    g,sq,leader,helper = scene()
    strength = sq.strength()
    leader._stream_dormant = True
    assert not leader.active and sq.strength() == strength
    with patch.object(g.command,'on_leader_change') as succession:
        squad_update(g,sq)
        assert sq.leader is leader and not succession.called
    leader.body.dead = True
    squad_update(g,sq)
    assert sq.leader is not leader and sq.strength() < strength


def test_fire_mission_retains_world_target_across_frames():
    g,ps,st = world()
    fires = g.support.fires
    b = next(b for b in fires.batteries if b.kind in ('gun','naval'))
    target = (g.player.x+20,g.player.y+5)
    world_target = st.world_pos(*target)
    fires.start(g,b,('map',(g.sector.x,g.sector.y),target),rounds=2,delay=0,silent=True)
    canonical = b.mission['target']
    before = fires.km(g,b,canonical[1],canonical[2])
    reframe(g,st)
    assert b.mission['target'] == canonical
    kind,sec,pos = fires._concrete(g,b,b.mission)
    assert kind == 'map' and st.world_pos(*pos) == world_target
    assert fires.km(g,b,canonical[1],canonical[2]) == before
    with patch.object(g,'schedule_shell') as shell:
        fires._fire_round(g,b,0,b.mission)
        assert shell.called
        actual = st.world_pos(*shell.call_args.args[:2])
        assert abs(actual[0]-world_target[0]) < 100


def test_land_scene_survives_ship_return_and_hospital_reassignment():
    from fow.gamemap import GameMap
    from fow.skysea_exit import to_land
    from fow.medevac import _back_to_duty
    g,ps,st = world()
    p,sector = g.player,g.sector
    friend = next(a for a in g.actors if a is not p and a.side == p.side and a.vehicle is None)
    position = st.world_pos(*friend.pos)
    friend.body.wounds.append(Wound('l_arm',.2,'gunshot'))
    g._save_map()
    g.map = GameMap(30,20)
    g.actors,g.vehicles,g.squads = [p],[],[]
    g.aboard = {'kind':'ship'}
    to_land(g,sector,frac=(.5,.5))
    assert st.frame is g.map and g.player is p
    assert st.actors[friend.id] is friend
    assert (st.world_pos(*friend.pos) if friend.id in st.active_actors else friend.pos) == position
    assert friend.body.bleed_rate() == .2
    assert st.sector_at(g,*p.pos) is sector
    g.world_turn()
    _back_to_duty(g,1)
    assert st.frame is g.map and st.actors[p.id] is p and p in g.actors
    assert st.sector_at(g,*p.pos) is g.sector
    g.world_turn()


def test_coarse_transfer_moves_original_people_without_duplicate_arrivals():
    g,ps,st = world()
    source = (g.sector.x+7,g.sector.y)
    dest = (source[0]+1,source[1])
    side = g.player.side
    src = g.strategic.at(*source,create=True)
    dst = g.strategic.at(*dest,create=True)
    for sector in (src,dst):
        sector.control = side
        sector.units = {s:Counter() for s in sector.units}
    src.units[side] = Counter(inf=1)
    st.preload(g,source)
    sq = next(sq for sq in st.squads.values() if st.squad_key(sq) == source and not getattr(sq,'no_count',False))
    identities = list(sq.members)
    dst.units[side] = Counter(inf=1)
    moved = st.transfer(g,source,dest,side,Counter(inf=1))
    assert moved == Counter(inf=1)
    assert st.squad_key(sq) == dest and sq.members == identities
    groups = [q for q in st.squads.values() if st.squad_key(q) == dest and not getattr(q,'no_count',False)]
    assert groups == [sq]


def test_enemy_spatial_candidates_match_full_scan_including_moving_targets():
    g,ps,st = world()
    for a in g.actors[::13]:
        for radius in (12,45,110):
            pos,ents = g.enemy_array(a.side)
            distances = np.sqrt(((pos-(a.x,a.y))**2).sum(axis=1))
            expected = np.nonzero(distances <= radius)[0]
            expected = expected[np.argsort(distances[expected])][:40]
            assert list(g.enemy_candidates(a,radius)) == list(expected)
    enemy = next(a for a in g.actors if a.side != g.player.side)
    enemy.x,enemy.y = g.player.x+1,g.player.y
    g.note_move(enemy)
    _,ents = g.enemy_array(g.player.side)
    assert ents.index(enemy) in g.enemy_candidates(g.player,5)


def test_vehicle_crosses_boundary_through_driving_with_crew_intact():
    g = Game('kursk43','ussr',role='tank_crew',seed=3,
             setup={'battlefield':'standard','scenario':'armour','reality_radius':120})
    app = FakeApp()
    app.settings.update(autosave=False,fast_quiet=False)
    ps = PlayState(app,g)
    app.states = [ps]
    st,p = g.landscape,g.player
    v,crew = p.vehicle,list(p.vehicle.crew_actors)
    old = g.sector
    wx,wy = (old.x+1)*st.w-1,old.y*st.h+st.h//2
    g.vehicle_at = {pos:other for pos,other in g.vehicle_at.items() if other is not v}
    v.x,v.y = wx-st.origin[0],wy-st.origin[1]
    for a in [p]+crew+list(v.passengers):
        a.x,a.y = v.x,v.y
    st.refresh(g,force=True)
    g.map.fill(p.x-12,p.y-12,p.x+16,p.y+13,'grass')
    g.map.refresh()
    for pos,ob in list(g.vehicle_at.items()):
        if ob is not v and abs(pos[0]-p.x)<15 and abs(pos[1]-p.y)<15:
            g.vehicle_at.pop(pos)
    for pos in list(g.soldier_at):
        if abs(pos[0]-p.x)<15 and abs(pos[1]-p.y)<15:
            g.soldier_at.pop(pos)
    before = g.clock
    with patch.object(g,'travel',side_effect=AssertionError('vehicle teleport')):
        for _ in range(12):
            ps.drive(1,0)
            if g.sector.x == old.x+1:
                break
    assert g.sector.x == old.x+1 and g.clock > before
    assert p.vehicle is v and v.crew_actors == crew
    assert all(a.vehicle is v for a in crew)


def test_distant_incoming_shell_activates_people_before_impact():
    g,ps,st = world()
    a = next(a for a in st.actors.values() if a.id not in st.active_actors and a.alive and
             g.map.in_bounds(a.x-st.origin[0],a.y-st.origin[1]))
    world_pos = a.pos
    local = (a.x-st.origin[0],a.y-st.origin[1])
    g.schedule_shell(*local,4,30,2,0,0,g.player,'distant impact')
    g.world_turn()
    assert a.id in st.active_actors and st.actors[a.id] is a
    assert st.world_pos(*a.pos) == world_pos or a.moves < 100


def test_staff_visit_marks_a_real_route_without_skipping_time():
    g,ps,st = world()
    before = (g.turn,g.clock,st.world_pos(*g.player.pos))
    destination = (g.sector.x+1,g.sector.y)
    with patch.object(g,'_skip_time',side_effect=AssertionError('time skip')):
        g.go_forward(destination)
    assert (g.turn,g.clock,st.world_pos(*g.player.pos)) == before
    assert g.field_order['journey'] == destination
    assert g.field_order['edge'] is not None


def test_briefed_mission_does_not_expand_with_the_loaded_world():
    from fow import scenarios
    g = Game('bocage44','usa',seed=42,setup={'scenario':'assault','reality_radius':120})
    original = list(g.map.objectives)
    app = FakeApp()
    ps = PlayState(app,g)
    st = g.landscape
    assert len(scenarios.mission_objectives(g)) == len(original)
    assert set(g.mission['briefed_objectives']) == {o._world_pos for o in original}
    reframe(g,st,24,0)
    assert {o._world_pos for o in scenarios.mission_objectives(g)} == set(g.mission['briefed_objectives'])
    for ob in scenarios.mission_objectives(g):
        ob.owner = g.player.side
    assert scenarios.mission_point(g) is None


def test_pending_orders_and_lean_direction_survive_frame_change():
    from fow.ai import Order
    g,ps,st = world()
    p = g.player
    p.peek = (1,0)
    p.aim_target = p.pos
    target = st.world_pos(*p.pos)
    order = Order('move',target=p.pos)
    g.command.pending.append(dict(order=order,due=g.turn+100))
    reframe(g,st)
    assert st.world_pos(*order.target) == target
    assert st.world_pos(*p.aim_target) == target
    assert p.peek == (1,0) and g.peek_at[(p.x+1,p.y)] is p
