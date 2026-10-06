"""Leader-directed help uses observations, ordinary actions and finite carried kit.

    python tests/test_squadcare.py
"""
from __future__ import annotations

import pickle
from unittest.mock import patch

from test_smoke import Game, FakeApp
from fow import squadcare as SC, tiles as T, ai as AI
from fow.entities import Actor, Item
from fow.inventory import Inventory
from fow.gamemap import GameMap
from fow.body import Wound
from fow.ammo import spare_rounds


def kit(a, ammo=0, dressings=0):
    a.invent = Inventory()
    a.invent.slots['pack'] = Item('suitcase')
    gun = Item('thompson_m1a1')
    a.invent.slots['primary'] = gun
    a.weapon = gun
    a.skills = dict(first_aid=3., observation=7., leadership=7.)
    for _ in range(ammo):
        assert a.add_item(Item(gun.t.magtype)) is not None
    if dressings:
        assert a.add_item(Item('bandage', dressings)) is not None
    return gun


def index(g):
    g.soldier_at = {a.pos: a for a in g.actors if a.alive}
    g._arr_turn = -1
    g._enemy_arr = {}


def squad(g, x=6, y=12, dressings=0):
    sq = AI.Squad(g.player.side, 'usa', 'rifle', 'Support section')
    lead = Actor('usa', 'rifleman', 3, 'Sergeant Smith', x, y)
    helper = Actor('usa', 'rifleman', 0, 'Private Jones', x + 1, y)
    kit(lead)
    kit(helper, ammo=4, dressings=dressings)
    sq.members, sq.leader = [lead, helper], lead
    sq.order = AI.Order('hold', target=lead.pos)
    sq.state, sq.arrived = 'hold', True
    for a in sq.members:
        a.squad = sq
    g.actors += sq.members
    g.squads.append(sq)
    index(g)
    return sq, lead, helper


def scene(dressings=0):
    g = Game('bocage44', 'usa', seed=7, setup={'battlefield': 'standard'})
    g.map = GameMap(48, 48, 2)
    g.map.t[:] = T.ID['grass']
    g.map.refresh()
    g.map.visible[:] = True
    g.map.explored[:] = True
    g.map.gen_positions = []
    g.turn, g.clock = 100, 12 * 3600
    g._daylight_cache = g._moon_cache = None
    g.update_view_range()
    g.lit = None
    p = g.player
    p.x, p.y, p.z = 14, 12, 0
    p.vehicle, p.squad = None, None
    p.ai.clear()
    p.fired_turn = -999
    kit(p).loaded = 0
    g.actors, g.squads, g.vehicles, g.vehicle_at = [p], [], [], {}
    g.map.items.clear()
    for b in g.brains.values():
        b.exp_cost = None
    sq, lead, helper = squad(g, dressings=dressings)
    return g, sq, lead, helper


def hurt(a, bleed=1.):
    a.body.wounds.append(Wound('l_arm', bleed, 'gunshot'))


def credit_kill(g, lead):
    victim = Actor('germany', 'rifleman', 0, 'Opponent', 18, 12)
    g.actors.append(victim)
    index(g)
    with patch.object(g, 'body_falls'):
        g.kill(victim, g.player)
    assert SC.effectiveness(g, lead, g.player) > 0


def test_witnessed_effectiveness_prioritises_help_without_replacing_orders():
    g, sq, lead, helper = scene()
    other = Actor('usa', 'rifleman', 0, 'Another rifleman', 9, 12)
    kit(other).loaded = 0
    g.actors.append(other)
    credit_kill(g, lead)
    before = pickle.dumps(sq.order)
    SC.dispatch(g, sq)
    assert helper.ai['support_job']['target'] == g.player.id
    assert helper.ai['support_job']['kind'] == 'ammo'
    assert pickle.dumps(sq.order) == before
    assert any('seen your fire taking effect' in m.text for m in g.messages)


def test_unseen_friendly_and_prisoner_kills_do_not_earn_support_credit():
    g, sq, lead, helper = scene()
    victim = Actor('germany', 'rifleman', 0, 'Opponent', 20, 12)
    g.map.t[18, :] = T.ID['wall_stone']
    g.map.refresh()
    SC.witnessed_kill(g, g.player, victim)
    assert SC.effectiveness(g, lead, g.player) == 0
    g.map.t[18, :] = T.ID['grass']
    g.map.refresh()
    victim.state = 'surrendered'
    SC.witnessed_kill(g, g.player, victim)
    victim.state, victim.side = 'ok', g.player.side
    SC.witnessed_kill(g, g.player, victim)
    assert SC.effectiveness(g, lead, g.player) == 0
    victim.side = 'axis'
    SC.witnessed_kill(g, g.player, victim)
    assert SC.effectiveness(g, lead, g.player) > 0
    g.turn += 601
    assert SC.effectiveness(g, lead, g.player) == 0


def test_runner_reaches_player_and_transfers_finite_compatible_ammunition():
    g, sq, lead, helper = scene()
    mags = [i for i in helper.inv if i.t.kind == 'mag']
    for mag in mags:
        mag.condition = .7
    total = spare_rounds(helper, helper.weapon)
    AI.squad_update(g, sq)  # real squad update and soldier action paths must both reach the new behaviour
    assert helper.ai['support_job']
    costs = []
    for _ in range(20):
        cost = AI.soldier_act(g, helper)
        if cost:
            costs.append(cost)
        g.turn += 1
        if not helper.ai.get('support_job'):
            break
    assert costs and all(c > 0 for c in costs)
    assert SC.distance(helper, g.player) <= 1.5
    assert spare_rounds(g.player, g.player.weapon) == 60
    assert spare_rounds(helper, helper.weapon) == total - 60 == 60
    assert g.player.weapon.loaded == 0  # reload remains a player action with its normal time cost
    assert all(i.condition == .7 for i in g.player.inv if i.t.kind == 'mag')
    assert not helper.ai.get('support_job')


def test_first_aid_consumes_supplies_and_keeps_existing_wound_rules():
    g, sq, lead, helper = scene(dressings=2)
    hurt(g.player)
    hp, blood = dict(g.player.body.hp), g.player.body.blood
    SC.dispatch(g, sq)
    assert helper.ai['support_job']['kind'] == 'aid'
    helper.x, helper.y = 13, 12
    index(g)
    assert SC.act(g, helper, []) >= 200
    assert g.player.body.bleed_rate() == 0
    assert g.player.body.hp == hp and g.player.body.blood == blood
    assert sum(i.count for i in helper.inv if i.tid == 'bandage') == 1
    # An inbound runner must not prevent a medic already beside the casualty from helping.
    g, sq, lead, helper = scene(dressings=2)
    hurt(g.player)
    SC.dispatch(g, sq)
    doctor = Actor('usa', 'medic', 0, 'Corpsman', 13, 12)
    kit(doctor, dressings=1)
    g.actors.append(doctor)
    index(g)
    assert SC.claimed(g, g.player, 'aid')
    assert AI.medic_act(g, doctor, []) >= 200
    assert g.player.body.bleed_rate() == 0
    assert SC.act(g, helper, []) is None and not helper.ai.get('support_job')


def test_urgent_casualty_overrides_reputation_and_new_urgent_casualties_interrupt():
    g, sq, lead, helper = scene(dressings=3)
    hurt(g.player)
    for _ in range(4):
        credit_kill(g, lead)
    critical = Actor('usa', 'rifleman', 0, 'Casualty', 10, 13)
    kit(critical)
    hurt(critical, 5.)
    g.actors.append(critical)
    index(g)
    SC.dispatch(g, sq)
    assert helper.ai['support_job']['target'] == critical.id
    helper.ai.pop('support_job')
    critical.body.wounds.clear()
    g.turn += 6
    SC.dispatch(g, sq)
    assert helper.ai['support_job']['target'] == g.player.id
    hurt(critical, 5.)
    assert SC.act(g, helper, []) is None
    assert not helper.ai.get('support_job')


def test_assignments_deduplicate_across_squads_and_save_without_actor_references():
    g, sq, lead, helper = scene()
    sq2, lead2, helper2 = squad(g, 8, 14)
    SC.dispatch(g, sq)
    SC.dispatch(g, sq2)
    assert helper.ai.get('support_job') and not helper2.ai.get('support_job')
    loaded = pickle.loads(pickle.dumps(g))
    runner = next(a for a in loaded.actors if a.id == helper.id)
    assert runner.ai['support_job'] == helper.ai['support_job']
    loaded.turn += 91
    assert SC.act(loaded, runner, []) is None
    assert not runner.ai.get('support_job')
    helper.suppression = 80
    g.turn += 6
    SC.dispatch(g, sq2)
    assert helper2.ai.get('support_job')  # a pinned runner cannot reserve the job indefinitely


def test_dispatch_requires_visible_needs_and_same_floor_and_a_real_ammo_cue():
    g, sq, lead, helper = scene()
    g.player.x = 25
    index(g)
    SC.dispatch(g, sq)
    assert not helper.ai.get('support_job')  # cannot inspect distant pockets
    g.player.ai['ammo_call'] = g.turn
    g.player.z = 1
    g.turn += 6
    SC.dispatch(g, sq)
    assert not helper.ai.get('support_job')
    g.player.z = 0
    g.map.t[18, :] = T.ID['wall_stone']
    g.map.refresh()
    g.turn += 6
    SC.dispatch(g, sq)
    assert not helper.ai.get('support_job')
    g.map.t[18, :] = T.ID['grass']
    g.map.refresh()
    g.turn += 6
    SC.dispatch(g, sq)
    assert helper.ai['support_job']['target'] == g.player.id


def test_helpers_follow_last_seen_position_and_stop_when_need_or_orders_change():
    g, sq, lead, helper = scene()
    SC.dispatch(g, sq)
    last = g.player.pos
    g.player.x, g.player.y = 30, 30
    g.map.t[20, :] = T.ID['wall_stone']
    g.map.refresh()
    index(g)
    with patch.object(AI, 'path_step', return_value=100) as move:
        assert SC.act(g, helper, []) == 100
        assert move.call_args.args[2:] == last
    g.turn += 21
    assert SC.act(g, helper, []) is None and not helper.ai.get('support_job')
    g.player.x, g.player.y = last
    index(g)
    g.turn += 30  # give the runner a chance to find us again after abandoning the search
    SC.dispatch(g, sq)
    assert helper.ai.get('support_job')
    g.player.add_item(Item(g.player.weapon.t.magtype))
    assert SC.act(g, helper, []) is None and not helper.ai.get('support_job')
    g.player.invent = Inventory()
    kit(g.player).loaded = 0
    g.turn += 6
    SC.dispatch(g, sq)
    sq.order = AI.Order('retreat')
    assert SC.act(g, helper, []) is None and not helper.ai.get('support_job')
    g.turn += 6
    SC.dispatch(g, sq)
    assert not helper.ai.get('support_job')


def test_no_dispatch_of_busy_wounded_or_player_helpers_and_threats_take_precedence():
    g, sq, lead, helper = scene()
    for key in ('runner', 'litter', 'to_aid'):
        helper.ai[key] = (1, 2)
        SC.dispatch(g, sq)
        assert not helper.ai.get('support_job')
        helper.ai.pop(key)
        g.turn += 6
    hurt(helper)
    SC.dispatch(g, sq)
    assert not helper.ai.get('support_job')
    helper.body.wounds.clear()
    helper.is_player = True
    g.turn += 6
    SC.dispatch(g, sq)
    assert not helper.ai.get('support_job')
    helper.is_player = False
    g.turn += 6
    SC.dispatch(g, sq)
    threat = Actor('germany', 'rifleman', 0, 'Enemy', helper.x + 2, helper.y)
    with patch.object(AI, 'path_step') as move:
        assert SC.act(g, helper, [threat]) is None
        assert not move.called and helper.ai.get('support_job')


def test_empty_broken_or_last_spare_magazines_are_not_donated():
    from fow.ammo import hand_over_possible
    g, sq, lead, helper = scene()
    mags = [i for i in helper.inv if i.t.kind == 'mag']
    mags[0].loaded = 0
    mags[1].condition = 0
    assert not hand_over_possible(helper, g.player.weapon)  # the two remaining loaded magazines are reserved
    SC.dispatch(g, sq)
    assert not helper.ai.get('support_job')


def test_corpsman_minor_wound_treatment_consumes_a_real_dressing():
    g, sq, lead, helper = scene(dressings=1)
    helper.role = 'medic'
    b = g.player.body
    b.hp['l_arm'] = int(b.max['l_arm'] * .5)
    before = b.hp['l_arm']
    SC.dispatch(g, sq)
    assert helper.ai['support_job']['kind'] == 'aid'
    helper.x, helper.y = g.player.x - 1, g.player.y
    index(g)
    assert SC.act(g, helper, []) >= 400
    assert before < b.hp['l_arm'] <= int(b.max['l_arm'] * .7)
    assert helper.medical('bandage') is None


def test_full_inventory_delivery_stays_on_ground_and_does_not_clone_items():
    g, sq, lead, helper = scene()
    p = g.player
    p.invent.slots['pack'] = None
    for grid in p.invent.pockets:
        item = Item('ration')
        grid.place(item, *grid.find_spot(item))
    before = {i.iid for i in helper.inv if i.t.kind == 'mag'}
    SC.dispatch(g, sq)
    helper.x, helper.y = p.x - 1, p.y
    index(g)
    assert SC.act(g, helper, []) == 120
    floor = [i for i in g.map.items_at(*p.pos) if i.t.kind == 'mag']
    carried = [i for i in helper.inv if i.t.kind == 'mag']
    assert len(floor) == len(carried) == 2
    assert {i.iid for i in floor + carried} == before
    assert spare_rounds(p, p.weapon) == 0
    assert any('at your feet' in m.text for m in g.messages)


def test_shout_menu_ammunition_call_and_visible_helper_status():
    from fow.play import PlayState
    import tcod
    from fow.render import draw_popup
    g, sq, lead, helper = scene()
    app = FakeApp()
    app.settings.update(autosave=False, realtime=False)
    ps = PlayState(app, g)
    app.states = [ps]
    ps.cmd_yell()
    pop = ps.popups[-1]
    pop.sel = next(i for i, o in enumerate(pop.options) if o[1] == 'ammo')
    con = tcod.console.Console(160, 80, order='F')
    draw_popup(con, pop)
    text = '\n'.join(''.join(chr(c) for c in con.ch[:, y]) for y in range(80))
    assert 'Need ammunition!' in text
    with patch.object(g, 'player_done'):
        ps.popup_select()
    assert g.player.ai['ammo_call'] == g.turn
    SC.dispatch(g, sq)
    from fow.nearby import gather
    assert any('Ammo for you' in e['label'] for e in gather(g)['Soldiers'])
    lines, _ = ps.describe_tile(helper.x, helper.y)
    assert any('Bringing ammunition to you.' == line for line, _ in lines)


if __name__ == '__main__':
    import traceback
    tests = [(name, fn) for name, fn in list(globals().items()) if name.startswith('test_') and callable(fn)]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print('ok   ', name, flush=True)
        except Exception:
            failures += 1
            print('FAIL ', name, flush=True)
            traceback.print_exc()
    print(f'{len(tests) - failures}/{len(tests)} tests passed')
    raise SystemExit(bool(failures))
