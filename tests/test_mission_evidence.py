"""Orders need the stated result; a boundary, an absent target or a timer is not that result."""
from unittest.mock import patch

from test_command_realism import scene, soldier
from test_smoke import Game
from fow import agents, mission_evidence as evidence, scenarios
from fow.entities import Vehicle


def mission(g, kind, stage, **fields):
    ms = dict(kind=kind, stage=stage, sid='encircled' if kind == 'breakout' else kind,
              start=g.turn, _start_sector=g.sector, authority=18, text='Carry out the mission.', **fields)
    g.mission = ms
    evidence.prepare(g, ms)
    return ms


def rally(g, ms):
    rec = dict(kind='hq', side=g.player.side, x=50, y=30, rect=(46,26,9,9))
    g.map.gen_positions.append(rec)
    g.sector.control = g.player.side
    g.sector.installations.append(['hq', g.player.side, True])
    ms['rally_destination'] = dict(kind='hq', label='friendly rally post', sector=(g.sector.x,g.sector.y),
        point=(50,30), world=(g.sector.x*g.map_w+50,g.sector.y*g.map_h+30))
    return soldier(g,51,30,role='adjutant',rank=8)


def test_one_step_and_sector_flag_cannot_complete_breakout_or_award_medal():
    g = scene()
    companion = soldier(g,12,10)
    ms = mission(g,'breakout','break',roster=[g.player.id,companion.id])
    rally(g,ms)
    # The former completion predicate would succeed merely because this object differs.
    ms['_start_sector'] = g.strategic.at(g.sector.x+1,g.sector.y,create=True)
    g.player.x += 1
    with patch.object(g.command,'_award') as award:
        scenarios.update(g)
    assert ms['stage'] == 'break' and not award.called
    assert not any('breakout worked' in m.text.lower() for m in g.messages)
    g.player.x,g.player.y = 50,30
    scenarios.update(g)
    assert ms['stage'] == 'break' and companion.id in ms['accounted']['missing']
    companion.x,companion.y = 49,30
    scenarios.update(g)
    assert ms['stage'] == 'done' and '2 reached friendly lines' in ms['outcome']
    assert not g.command.medals


def test_dead_rally_staff_cannot_report_a_success():
    g = scene()
    ms = mission(g,'evader','evade')
    staff = rally(g,ms)
    g.player.x,g.player.y = 50,30
    staff.body.dead = True
    scenarios.update(g)
    assert ms['stage'] != 'done'


def test_encircled_start_has_a_group_inside_the_field_and_real_blocking_units():
    g = Game('bocage44','usa',role='rifleman',seed=6,setup={'scenario':'encircled','seamless':False})
    assert min(g.player.x,g.player.y,g.map.w-1-g.player.x,g.map.h-1-g.player.y) > 20
    assert len(g.mission['roster']) > 1
    blockers = [sq for sq in g.squads if getattr(sq,'mission_cordon',False)]
    assert len(blockers) == 3 and all(sq.members for sq in blockers)
    assert scenarios.mission_point(g) is not None


def test_patrol_does_not_use_contacts_collected_by_the_rest_of_the_army():
    g = scene()
    ms = mission(g,'patrol','observe',need=2,base=0,home='S')
    g.brains[g.player.side].contacts = {i:object() for i in range(8)}
    with patch('fow.orders.governing', return_value={'key':'mission'}):
        scenarios.update(g)
    assert ms['stage'] == 'observe' and not ms['observations']
    for x in (15,28):
        soldier(g,x,10,nation='germany')
    g.map.visible[:] = True
    with patch('fow.orders.governing', return_value={'key':'mission'}):
        scenarios.update(g)
    assert ms['stage'] == 'return' and len(ms['observations']) == 2


def test_sniper_mission_counts_qualifying_enemy_targets_not_global_kills():
    g = scene()
    ms = mission(g,'sniper','hunt',need=2,base=0)
    g.player.kills = 50
    scenarios.update(g)
    assert ms['stage'] == 'hunt'
    private = soldier(g,12,10,nation='germany',rank=0,role='rifleman')
    officer = soldier(g,13,10,nation='germany',rank=8,role='officer')
    gunner = soldier(g,14,10,nation='germany',rank=0,role='lmg_gunner')
    for a in (private,officer,gunner):
        g.command.on_kill(g,a)
    scenarios.update(g)
    assert ms['stage'] == 'done' and set(ms['confirmed_targets']) == {officer.id,gunner.id}
    assert not g.command.medals


def test_empty_artillery_site_and_missing_assassination_target_are_not_destroyed():
    g = scene()
    ms = mission(g,'raid','destroy',base=0,rec=dict(kind='artillery',rect=(30,20,5,5),x=32,y=22))
    scenarios.update(g)
    assert ms['stage'] == 'destroy'
    ms = mission(g,'agent','kill',task='eliminate',mark=987654)
    scenarios.update(g)
    assert ms['stage'] == 'kill'


def test_hold_does_not_count_time_spent_away_and_capture_requires_enemy_armour_defeated():
    g = scene()
    for ob in g.map.objectives:
        ob.owner = g.player.side
    ms = mission(g,'hold','hold',until=g.turn+10)
    ob = g.map.objectives[0]
    g.player.x,g.player.y = ob.pos
    scenarios.update(g)
    g.player.x,g.player.y = 1,1
    g.turn += 20
    scenarios.update(g)
    assert ms['stage'] == 'hold' and ms['held_seconds'] == 0
    g.player.x,g.player.y = ob.pos
    scenarios.update(g)
    g.turn += 10
    scenarios.update(g)
    assert ms['stage'] == 'done'
    tank = Vehicle('m4','axis','germany',30,20)
    g.vehicles.append(tank)
    ms = mission(g,'take','take',armour_targets=[tank.id],capture_required=True)
    scenarios.update(g)
    assert ms['stage'] == 'take'
    tank.dead = True
    scenarios.update(g)
    assert ms['stage'] == 'done' and not g.command.medals


def test_rail_sabotage_needs_actual_rails_destroyed_and_escape_needs_distance():
    g = scene()
    for x in range(25,35):
        g.map.set(x,20,'rail')
    g.map.refresh()
    ms = mission(g,'agent','plant',task='sabotage',target='rail',tx=30,ty=20,
                 rail_tiles=[(x,20) for x in range(26,35)])
    done = []
    agents._update_sabotage(g,ms,lambda *args:done.append(args),False,True)
    assert ms['stage'] == 'plant'   # ordinary dirt around intact rails is not sabotage
    g.map.set(29,20,'crater')
    g.map.set(30,20,'crater')
    agents._update_sabotage(g,ms,lambda *args:done.append(args),False,True)
    assert ms['stage'] == 'away'
    agents._update_sabotage(g,ms,lambda *args:done.append(args),False,False)
    assert not done                # crossing the sector flag alone is no escape


def test_destroyed_drop_is_not_recovered_supplies():
    g = scene()
    ms = mission(g,'agent','collect',task='receive_drop')
    g.agent = dict(drops=[dict(id=123,mission=True,state='dropped',n_items=10,dz=(20,20))])
    done = []
    agents._update_drop(g,ms,lambda *args:done.append(args),True)
    assert not done


def test_drop_recovery_carries_real_items_into_cover():
    from collections import Counter
    from fow.entities import Item
    from fow.tasks import _gather_drop
    g = scene()
    p = g.player
    item = Item('bandage')
    item.data = dict(drop=123)
    g.map.add_item(11,10,item)
    task = dict(drop=123,found=Counter(),drop_stash=(23,10))
    assert _gather_drop(g,p,p.squad,task) == 600
    assert item in p.inv and item not in g.map.items_at(11,10)
    start = p.pos
    for _ in range(30):
        _gather_drop(g,p,p.squad,task)
        if item.data.get('recovered'):
            break
    assert p.pos != start and item.data.get('recovered')
    assert item not in p.inv and item in g.map.items_at(23,10)


def sea_scene():
    g = Game('okinawa45','usa',role='sailor',seed=3,
             setup={'battlefield':'standard','service':'navy','scenario':'sea:convoy'})
    return g, g.skysea


def test_convoy_needs_physical_arrival_not_elapsed_time():
    from fow.skysea_missions import check
    g, ss = sea_scene()
    ms, ship = ss.mission, ss.player_ship
    point = ms['target_pt']
    ss.t = ms['start'] + 3600
    check(ss)
    assert ms['stage'] != 'done'
    ss._captain(ship,[])
    from fow.skysea import bearing
    assert ship.order_hdg == bearing(ship.x,ship.y,*point) and ship.order_kn > 0
    for eid in ms['convoy']:
        c = ss.entity(-eid)
        c.x,c.y = point
    check(ss)
    assert ms['stage'] == 'done' and not g.command.medals


def test_air_cover_requires_time_actually_on_station():
    from fow.skysea_missions import check
    g, ss = sea_scene()
    ship = ss.player_ship
    ss.mission = dict(kind='cover',stage='watch',start=0,until=120,
                      cover_pt=(ship.x+100,ship.y),station_checked=0)
    ss.t = 180
    check(ss)
    assert ss.mission.get('station_time',0) == 0 and ss.mission['stage'] != 'done'
    ship.x,ship.y = ss.mission['cover_pt']
    ss.t += 1
    check(ss)
    assert ss.mission['stage'] != 'done'
    ss.t += 120
    check(ss)
    assert ss.mission['stage'] == 'done'


def test_sea_rescue_requires_slowing_and_recovery_work():
    from fow.skysea_missions import check
    g, ss = sea_scene()
    ship = ss.player_ship
    ss.mission = dict(kind='rescue',stage='search',until=1000,survivors=10,
                      rescue_pt=(ship.x,ship.y),rescue_checked=0)
    ship.kn, ss.t = 20, 120
    check(ss)
    assert ss.mission['stage'] != 'done'
    ss._captain(ship,[])
    assert ship.order_kn == 0
    ship.kn = 0
    ss.t += 30
    check(ss)
    assert ss.mission['stage'] != 'done'
    ss.t += 30
    check(ss)
    assert ss.mission['stage'] == 'done' and ship.ai['rescued_survivors'] == 10


def test_flight_return_uses_landing_approach_and_does_not_land_at_cruise_altitude():
    from fow.skysea import SkySea, Plane
    from fow.skysea_missions import check
    g = scene()
    ss = SkySea(g,g.sector.x,g.sector.y)
    plane = Plane('p47',g.player.side,'usa',1,1,0,2000,kmh=300,rng=g.rng)
    plane.player = True
    plane.ai = dict(role='home',home_pt=(1,1))
    ss.planes,ss.player_plane = [plane],plane
    ss.mission = dict(kind='recon',stage='home',target_pt=(100,100),base_pt=(1,1),
                      base=(g.sector.x,g.sector.y))
    ss._pilot_ai(plane)
    check(ss)
    assert plane.state == 'flying' and ss.mission['stage'] == 'home'
    plane.alt = 100
    check(ss)
    assert ss.mission['stage'] == 'home' and plane.ai['landing_assist']
    ss._fly(plane)
    check(ss)
    assert plane.state == 'landed' and ss.mission['stage'] == 'done'
