"""Demolition consumes real charges, destroys real assets and survives withdrawal."""
import pickle
from unittest.mock import patch

import pytest

from test_command_realism import scene, move
from test_mission_evidence import mission
from test_smoke import Game
from test_streaming import world, reframe
from fow import actions, agents, demolition, intelligence, scenarios, tiles as T
from fow.entities import Item, Vehicle
from fow.inventory import Inventory
from fow.mapgen import Gen


def hq(g, x=35, y=25):
    rec = dict(kind='hq', side='axis', x=x, y=y, rect=(x-5, y-5, 11, 11))
    g.map.gen_positions.append(rec)
    g.map.set(x, y, 'radio_set')
    g.map.refresh()
    g.sector.installations.append(['hq', 'axis', True])
    return rec


def charge(g, x, y, pencil=False, tid='pe_808'):
    p = g.player
    p.invent = Inventory()
    p.invent.slots['pack'] = Item('backpack')
    item = Item(tid)
    assert p.add_item(item)
    if pencil:
        assert p.add_item(Item('time_pencil'))
    move(g, p, (x-1, y))
    cost = actions.place_charge(g, p, item, x, y)
    assert cost and item not in p.inv
    return g.explosives[-1]


def detonate(g):
    # Exercise the real countdown, dud check, blast and terrain damage.
    for _ in range(1000):
        if not g.explosives and not g.pending_explosions:
            break
        g.turn += 1
        g._tick_explosives()
        g._tick_pending()
    assert not g.explosives and not g.pending_explosions
    g.map.refresh()


def test_contact_demolition_breaches_masonry_and_accumulates_against_concrete():
    g = scene()
    g.map.set(35, 25, 'wall_brick')
    g.map.set(45, 25, 'wall_concrete')
    g.map.set(46, 25, 'wall_concrete')
    charge(g, 35, 25)
    move(g, g.player, (10, 10))
    detonate(g)
    assert g.map.t[35, 25] != T.ID['wall_brick']
    charge(g, 45, 25)
    move(g, g.player, (10, 10))
    detonate(g)
    # One small charge causes meaningful damage, but does not flatten a bunker.
    assert g.map.t[45, 25] == T.ID['wall_concrete']
    assert 2500 < g.map.hp[45, 25] < 3500
    assert g.map.hp[46, 25] > 4700   # Extra coupling applies only at contact.
    charge(g, 45, 25)
    move(g, g.player, (10, 10))
    detonate(g)
    assert 500 < g.map.hp[45, 25] < 1500
    charge(g, 45, 25, tid='limpet')
    move(g, g.player, (10, 10))
    detonate(g)
    assert g.map.t[45, 25] != T.ID['wall_concrete']
    assert g.map.t[46, 25] == T.ID['wall_concrete']


def test_picking_up_and_throwing_a_restored_charge_removes_contact_and_attachment():
    g = scene()
    g.map.set(35, 25, 'wall_concrete')
    e = charge(g, 35, 25, pencil=True)
    # Cold terrain deserialization preserves ID, not Python object identity.
    restored = pickle.loads(pickle.dumps(e['item']))
    restored.data['on_vehicle'] = 12345
    g.map.remove_item(35, 25, e['item'])
    assert g.player.add_item(restored)
    g.pick_live(restored, g.player)
    assert e['item'] is restored and e['holder'] is g.player
    assert not e['placed'] and not e['hidden'] and 'on_vehicle' not in restored.data
    g.player.remove_item(restored)
    g.drop_live(restored, 35, 25)
    g.map.add_item(35, 25, restored)
    move(g, g.player, (10, 10))
    detonate(g)
    assert g.map.t[35, 25] == T.ID['wall_concrete'] and g.map.hp[35, 25] > 4500
    assert restored not in g.map.items.get((35, 25), ())


def test_a_dud_never_causes_contact_damage():
    g = scene()
    g.map.set(35, 25, 'wall_concrete')
    e = charge(g, 35, 25)
    e['item'].condition = 0
    move(g, g.player, (10, 10))
    detonate(g)
    assert g.map.t[35, 25] == T.ID['wall_concrete'] and g.map.hp[35, 25] == 5000
    assert e['item'] in g.map.items[35, 25] and e['item'].data.get('dud')


@pytest.mark.parametrize('dud', [False, True])
def test_attached_charge_and_its_dud_follow_a_vehicle_even_after_it_is_wrecked(dud):
    g = scene()
    v = Vehicle('m4', 'axis', 'germany', 35, 25)
    g.vehicles.append(v)
    g.place_vehicle(v)
    e = charge(g, 35, 25, tid='limpet')
    assert e['item'].data['on_vehicle'] == v.id
    e['item'].condition = 0 if dud else 1
    g.lift_vehicle(v)
    v.x, v.y, v.dead = 45, 25, True
    g.map.set(35, 25, 'radio_set')
    g.map.set(45, 25, 'radio_set')
    move(g, g.player, (10, 10))
    detonate(g)
    assert g.map.t[35, 25] == T.ID['radio_set']
    assert e['item'] not in g.map.items.get((35, 25), ())
    if dud:
        assert e['item'] in g.map.items[45, 25] and g.map.t[45, 25] == T.ID['radio_set']
    else:
        assert g.map.t[45, 25] != T.ID['radio_set']


def test_hq_without_ammunition_is_achievable_with_one_real_timed_charge():
    g = scene()
    rec = hq(g)
    ms = mission(g, 'agent', 'plant', task='sabotage', target='rec', rec=rec, base=0)
    plan = demolition.prepare(g, ms)
    assert plan['need'] == 1 and scenarios.mission_point(g)[:2] == (35, 25)
    assert not demolition.achieved(g, ms)
    e = charge(g, 35, 25, pencil=True)
    assert e['fuse'] > 300 and not g.player.find(lambda i: i.t.tool == 'time_pencil')
    move(g, g.player, (10, 10))
    detonate(g)
    assert g.map.t[35, 25] != T.ID['radio_set']
    done = []
    agents._update_sabotage(g, ms, lambda *args: done.append(args), False, True)
    assert ms['stage'] == 'away' and not done
    assert rec['destroyed'] and not g.sector.installations[0][2]
    # This is a physical HQ loss: its enemy staff cannot use the site anymore.
    g.player.side = 'axis'
    move(g, g.player, (34, 25))
    assert intelligence.headquarters(g) is None
    assert ms['withdraw_world'] == plan['site_world']


def test_explosion_in_empty_ground_and_a_missing_target_are_not_success():
    g = scene()
    rec = hq(g)
    ms = mission(g, 'agent', 'plant', task='sabotage', target='rec', rec=rec, base=0)
    demolition.prepare(g, ms)
    charge(g, 42, 25)
    move(g, g.player, (10, 10))
    detonate(g)
    assert not demolition.achieved(g, ms)
    # An ungenerated location cannot turn into destruction evidence.
    ms['demolition']['tiles'][0]['world'] = (10**7, 10**7)
    assert not demolition.achieved(g, ms)


def test_empty_depot_is_skipped_for_a_real_headquarters_target():
    g = scene()
    rec = hq(g)
    g.map.gen_positions.insert(0, dict(kind='depot', side='axis', x=20, y=20, rect=(18, 18, 5, 5)))
    ms = dict(kind='agent', task='sabotage')
    agents._setup_sabotage(g, ms, [])
    assert ms['rec'] is rec and ms['demolition']['need'] == 1
    assert 'radio equipment or mast' in ms['text']


def test_raid_requires_its_briefed_equipment_not_an_unrelated_dead_guard_gun():
    g = scene()
    rec = hq(g)
    gun = Vehicle('pak40_gun', 'axis', 'germany', 37, 25)
    g.vehicles.append(gun)
    ms = mission(g, 'raid', 'destroy', rec=rec, base=0, home='W')
    demolition.assign(g, ms)
    gun.dead = True
    scenarios.update(g)
    assert ms['stage'] == 'destroy' and not rec.get('destroyed')
    charge(g, 35, 25)
    move(g, g.player, (10, 10))
    detonate(g)
    scenarios.update(g)
    assert ms['stage'] == 'exfil' and rec['destroyed']


def test_gun_only_raid_requires_its_real_guns_and_accepts_capture():
    g = scene()
    rec = dict(kind='artillery', side='axis', x=35, y=25, rect=(30, 20, 11, 11))
    g.map.gen_positions.append(rec)
    gun = Vehicle('pak40_gun', 'axis', 'germany', 35, 25)
    g.vehicles.append(gun)
    ms = mission(g, 'raid', 'destroy', rec=rec, base=0, home='W')
    plan = demolition.assign(g, ms)
    assert plan['need'] == 1 and not demolition.achieved(g, ms)
    assert scenarios.mission_point(g)[:2] == gun.pos
    gun.side = g.player.side
    scenarios.update(g)
    assert ms['stage'] == 'exfil'


def test_legacy_store_losses_are_not_forgotten_when_binding_remaining_targets():
    g = scene()
    rec = dict(kind='depot', side='axis', x=35, y=25, rect=(30, 20, 11, 11))
    g.map.set(35, 25, 'ammo_stack')
    ms = mission(g, 'agent', 'plant', task='sabotage', target='rec', rec=rec, base=4)
    assert demolition.achieved(g, ms)  # Three of the four originally briefed stacks are gone.
    empty = mission(g, 'raid', 'destroy', rec=rec, base=0)
    g.map.set(35, 25, 'grass')
    assert not demolition.achieved(g, empty)


def test_generated_headquarters_contains_real_destructible_communications():
    gen = Gen(dict(seed=73, biome='desert', climate='desert', attacker_edge='W', defender_side='axis'))
    rec = gen.installation('hq', 'axis')
    x, y, w, h = rec['rect']
    assert any(gen.m.t[xx, yy] == T.ID['radio_set']
               for xx in range(x, x+w) for yy in range(y, y+h))
    assert T.HP[T.ID['radio_set']] > 0


def test_legacy_hq_save_gets_a_physical_target_and_clear_briefing(tmp_path):
    g = scene()
    rec = hq(g)
    # Legacy HQs have a mast, even though the old ammunition count was zero.
    g.map.set(35, 25, 'antenna')
    ms = mission(g, 'agent', 'plant', task='sabotage', target='rec', rec=rec, base=0)
    g.save(str(tmp_path / 'old.pkl'))
    restored = Game.load(str(tmp_path / 'old.pkl'))
    assert ms.get('demolition') is None
    assert restored.mission['demolition']['need'] == 1
    assert 'radio equipment or mast' in restored.mission['text']
    assert scenarios.mission_point(restored)[:2] == (35, 25)


def test_long_fuse_reactivates_distant_ground_and_survives_compression_and_save(tmp_path):
    g, ps, land = world()
    x, y = g.player.x+6, g.player.y
    g.map.fill(x-3, y-3, x+4, y+4, 'grass')
    rec = hq(g, x, y)
    # The helper must not attribute a new fixture site to a different strategic cell.
    ms = mission(g, 'agent', 'plant', task='sabotage', target='rec', rec=rec, base=0)
    plan = demolition.prepare(g, ms)
    target = plan['tiles'][0]['world']
    initial_sector = g.sector
    e = charge(g, x, y, pencil=True)
    item_id = e['item'].iid
    # Three seconds remain after the withdrawal; the item is now in a cold cell.
    e['fuse'] = 3
    reframe(g, land, dx=450)
    key = target[0]//land.w, target[1]//land.h
    assert isinstance(land.maps[key], bytes)
    assert not g.map.in_bounds(e['x'], e['y'])
    assert g.sector is not initial_sector
    g.save(str(tmp_path / 'fuse.pkl'))
    g = Game.load(str(tmp_path / 'fuse.pkl'))
    land = g.landscape
    ms = g.mission
    assert ms['demolition']['tiles'][0]['world'] == target
    for _ in range(3):
        g.world_turn()                 # Full simulation, including AI around the returning blast site.
    assert not any(e['item'].iid == item_id for e in g.explosives)
    assert demolition.tile_at(g, target) != T.ID['radio_set']
    assert not any(it.iid == item_id for pile in g.map.items.values() for it in pile)
    assert demolition.achieved(g, ms)
    assert g.map.w > 2*(land.radius+land.margin)+1
    g.world_turn()                    # Release the extra terrain once the distant blast resolves.
    assert g.map.w == 2*(land.radius+land.margin)+1
    assert demolition.achieved(g, ms)  # Destruction survives putting the target back into storage.
    agents._update_sabotage(g, ms, lambda *args: None, False, False)
    assert ms['stage'] == 'away' and ms['withdraw_world'] == target
    done = []
    with patch('fow.mission_evidence.quiet', return_value=True):
        agents._update_sabotage(g, ms, lambda *args: done.append(args), False, False)
    assert done                          # Already clear when it went off: no second arbitrary retreat.


def test_vehicle_charge_does_not_leave_a_live_copy_in_its_old_compressed_cell():
    g, ps, land = world()
    x, y = g.player.x+6, g.player.y
    g.map.fill(x-3, y-3, x+4, y+4, 'grass')
    original = land.world_pos(x, y)
    v = Vehicle('m4', 'axis', 'germany', x, y)
    g.add_vehicle(v)
    e = charge(g, x, y, pencil=True, tid='limpet')
    e['item'].condition = 0  # A physical dud must also be left at the vehicle's new position.
    iid = e['item'].iid
    reframe(g, land, dx=450)
    key = original[0]//land.w, original[1]//land.h
    assert isinstance(land.maps[key], bytes) and v.__dict__.get('_stream_dormant')
    v.x, v.y = land.world_pos(g.player.x+6, g.player.y)
    v.dead = True
    e['fuse'] = 2
    land.refresh(g, force=True)
    assert not g.map.in_bounds(e['x'], e['y']) and v in g.vehicles
    for _ in range(2):
        g.world_turn()
    assert not any(e['item'].iid == iid for e in g.explosives)
    old = land.preload(g, key)
    assert not any(it.iid == iid for pile in old.items.values() for it in pile)
    assert any(it.iid == iid and it.data.get('dud') for it in g.map.items.get(v.pos, ()))
