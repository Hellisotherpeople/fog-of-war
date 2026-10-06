"""Physical reporting, useful rewards and full careers without instant rank jumps."""
from copy import deepcopy
import pickle
from unittest.mock import patch

import pytest

from test_command_realism import scene, soldier, radio, unradio, move
from test_smoke import FakeApp, Game
from fow import debrief as D, contacts as C, recognition as R, dispatches as S, intelligence as I, orders
from fow.entities import Item, Vehicle
from fow.play import PlayState
from fow.sustain import stores
from fow.brain import Contact


def hq(g):
    g.map.gen_positions.append(dict(kind='hq', side=g.player.side, x=10, y=10))
    g.sector.control = g.player.side
    a = soldier(g, 12, 10, role='adjutant', rank=10)
    a.squad.no_count = True
    return a


def desk_time(g, seconds):
    for _ in range(seconds // 30):
        g.turn += 30
        D.tick(g)


def test_debrief_routes_to_staff_checks_witnesses_and_pauses_away():
    g = scene()
    adj = hq(g)
    witness = soldier(g, 14, 10, role='rifleman')
    assert R.claim(g, 'kills', 12, 'a witnessed action', (14, 10))
    report = next(o for o in orders.book(g) if o['key'] == 'personnel')
    assert report['point'] == (*adj.pos, adj.full_name)
    assert report['due'] is None and not report['deferred']
    assert D.review(g)
    D.tick(g)
    desk_time(g, 150)
    assert not D.requests(g)
    move(g, g.player, (30, 30))
    desk_time(g, 300)
    assert R.state(g)['debrief_work'] == 150
    move(g, g.player, (10, 10))
    desk_time(g, 150)
    assert R.state(g)['credited'] == 12 and D.requests(g) == 1
    assert R.state(g)['reviewed']['kills'] == 1
    assert 'report_order' not in R.state(g)
    restored = pickle.loads(pickle.dumps(g))
    assert D.requests(restored) == 1
    assert D.review(restored)
    desk_time(restored, 300)
    assert D.requests(restored) == 1  # a second interview is not a second deed


def test_broken_vehicle_radio_crew_can_report_in_person():
    g = scene()
    hq(g)
    v = Vehicle('m4', g.player.side, 'usa', 10, 10)
    v.parts['radio'] = 0
    g.vehicles.append(v)
    g.player.vehicle = v
    v.crew = 5
    ledger = R.state(g)
    ledger['claims'] = [dict(kind='kills', weight=5, why='crew evidence', witnesses=[('crew', v.id)],
                             turn=g.turn, reported=None, sector=(g.sector.x, g.sector.y))]
    R.process(g)
    assert ledger['claims'][0]['due'] == g.turn + 300
    g.turn += 300
    R.process(g)
    assert ledger['credited'] == 5


def test_full_private_to_five_star_career_banks_service_and_requires_time():
    g = scene()
    hq(g)
    p, ledger = g.player, R.state(g)
    p.rank = 0
    p.skills['leadership'] = 7
    ledger.update(credited=1000, last_debrief=g.turn, last_promotion=g.turn)
    assert not D.apply_career(g)
    ranks = [p.rank]
    spent = 0
    while p.rank < 18:
        old = p.rank
        g.turn += 86400 if old < 8 else 7 * 86400
        assert D.apply_career(g)
        assert p.rank == old and ledger['pending']
        spent += g.command.promotion_need(old)
        g.turn = ledger['pending']['due']
        assert R.consider(g)
        assert p.rank == (8 if old == 4 else old + 1)
        assert ledger['spent'] == spent and ledger['credited'] == 1000
        ranks.append(p.rank)
    assert ranks == [0, 1, 2, 3, 4, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
    assert D.career_offer(g)[0] is None
    assert len(g.command.promotions) == len(ranks) - 1


def test_approved_awards_wait_for_staff_and_create_an_order():
    g = scene()
    unradio(g.player)
    R.recommend_award(g, 4, 'for gallantry')
    g.turn += 86400
    radio(g.player)
    R.process(g)
    assert not g.command.medals
    assert D.entry(g)['key'] == 'personnel'
    adj = hq(g)
    adj.body.dead = True
    R.process(g)
    assert not g.command.medals
    adj.body.dead = False
    R.process(g)
    assert len(g.command.medals) == 1 and not R.state(g)['awards']
    D.finish_review(g)
    assert D.requests(g) == 4
    D.finish_review(g)
    assert D.requests(g) == 4


def test_support_is_an_existing_unit_and_equipment_authority_costs_an_allocation():
    g = scene()
    hq(g)
    R.state(g)['support_earned'] = 2
    a = soldier(g, 16, 10)
    before = len(g.actors)
    assert D.allocate(g, 'support', a.squad)
    assert a.squad.leader is a and a.squad.id in g.command.attached
    assert len(g.actors) == before and D.requests(g) == 1
    assert not D.allocate(g, 'support', a.squad)
    from fow.qmui import credit
    amount = credit(g)
    assert D.allocate(g, 'kit')
    assert credit(g) == amount + 120 and g.player.ai['hq_equipment']
    assert not D.allocate(g, 'kit') and D.requests(g) == 0


def test_hq_refit_reserves_finite_stores_and_never_repairs_hull_instantly():
    g = scene()
    hq(g)
    v = Vehicle('m4', g.player.side, 'usa', 10, 10)
    g.vehicles.append(v)
    g.player.vehicle = v
    v.crew = 5
    v.ap = v.he = v.mg_ammo = 0
    v.hp -= 100
    damaged_hp = v.hp
    v.ai.update(fuel=0, field_parts=0)
    stock = stores(g.sector, g.player.side)
    stock.update(ammo=0, fuel=0, parts=0)
    R.state(g)['support_earned'] = 1
    assert not D.allocate(g, 'refit') and D.requests(g) == 1
    stock.update(ammo=2, fuel=2, parts=3)
    assert D.allocate(g, 'refit')
    assert stock['ammo'] == stock['fuel'] == stock['parts'] == 0
    assert v.ap + v.he == 0 and v.hp == damaged_hp
    D.tick(g)
    desk_time(g, 150)
    v.x, v.y = 40, 40
    desk_time(g, 300)
    assert v.ai['hq_refit']['work'] == 150 and v.ap + v.he == 0
    v.x, v.y = 10, 10
    desk_time(g, 150)
    assert v.ap + v.he == 8 and v.ai['fuel'] == 10 and v.ai['field_parts'] == 3
    assert v.hp == damaged_hp and 'hq_refit' not in v.ai


def papers(g, side='axis'):
    g.player.invent.slots['pack'] = Item('backpack')
    it = Item('marked_map')
    it.data = dict(side=side, written=g.turn, positions=[])
    assert g.player.add_item(it) is not None
    return it


def test_captured_intelligence_gets_order_retargets_and_requires_physical_handover():
    g = scene()
    g.sector.control = g.player.side
    first = soldier(g, 13, 10, role='intel', rank=9)
    second = soldier(g, 17, 10, role='intel', rank=9)
    doc = papers(g)
    ps = PlayState(FakeApp(), g)
    ps.act = lambda cost: None
    with patch('fow.contacts.people', wraps=C.people), patch('fow.senses.player_can_see_actor', return_value=True):
        entry = next(o for o in orders.book(g) if o['key'] == 'intelligence')
        assert entry['point'][:2] == first.pos
        first.body.dead = True
        assert C.entry(g)['point'][:2] == second.pos
    from fow.qmui import hand_over_papers, credit
    before = credit(g)
    hand_over_papers(ps, second)
    assert doc in g.player.inv and credit(g) == before
    move(g, second, (12, 10))
    g.player_fov()
    label, action = C.go(ps)
    action()
    assert doc not in g.player.inv and credit(g) > before and R.state(g)['credited'] > 0
    assert C.entry(g) is None
    after = credit(g)
    hand_over_papers(ps, second)
    assert credit(g) == after
    own = papers(g, side=g.player.side)
    assert C.entry(g) is None
    hand_over_papers(ps, second)
    assert own in g.player.inv


def test_report_does_not_release_active_operational_orders():
    g = scene()
    hq(g)
    R.state(g)['credited'] = 12
    g.field_order = dict(text='Defend the bridge', point=(40, 40), issued=g.turn, authority=17,
                         sector=(g.sector.x, g.sector.y), who='General', reason='Hold', edge=None)
    entries = orders.book(g)
    assert next(o for o in entries if o['key'] == 'personnel')['deferred']
    assert not orders.focus(g, 'personnel')


def map_packet(g, side=None, turn=None):
    side = side or g.player.side
    r = I._snapshot(g.strategic, g.sector, side, g.turn if turn is None else turn)
    key = (g.sector.x, g.sector.y)
    g.strategic.situation_reports = {side: {key: r}}
    g.player.ai.pop('map_reports', None)
    return key, r


@pytest.mark.parametrize('via', ['personal radio', 'nearby radioman', 'nearby vehicle crew'])
def test_staff_radio_and_vehicle_packets_freeze_and_need_working_delivery(via):
    g = scene()
    unradio(g.player)
    key, report = map_packet(g)
    if via == 'personal radio':
        r = radio(g.player)
    elif via == 'nearby radioman':
        r = radio(soldier(g, 12, 10, role='radioman'))
    else:
        v = Vehicle('m4', g.player.side, 'usa', 12, 10)
        v.crew = 5
        v.ai['radio'] = True
        g.vehicles.append(v)
    assert S.channel(g, g.player) == via
    S.tick(g)
    assert key not in g.player.ai.get('map_reports', {})
    report['turn'] += 60  # a newer HQ update after transmission starts
    g.turn += 30
    S.tick(g)
    assert g.player.ai['map_reports'][key]['turn'] == g.turn - 30
    assert g.player.ai['staff_update']['via'] == via
    # A subsequent transmission fails if the equipment goes out before receipt.
    g.turn += 180
    S.tick(g)
    if via == 'nearby vehicle crew':
        v.parts['radio'] = 0
    else:
        r.condition = 0
    g.turn += 30
    S.tick(g)
    assert g.player.ai['map_reports'][key]['turn'] < report['turn']


@pytest.mark.parametrize('nation', ['usa', 'germany'])
def test_physical_runner_delivers_saved_snapshot_to_either_army(nation):
    g = scene()
    recipient = g.player if nation == 'usa' else soldier(g, 10, 10, nation=nation, role='officer', rank=13)
    unradio(recipient)
    key, report = map_packet(g, recipient.side)
    runner = soldier(g, 35, 10, nation=nation, role='rifleman', rank=2)
    unradio(runner)
    g.map.gen_positions = [dict(kind='hq', side=recipient.side, x=35, y=10)]
    g.actors = [recipient, runner]
    g.brains[recipient.side].contacts[987] = Contact(987, 22, 20, g.turn, 'tank')
    g.brains[recipient.side].contacts[988] = Contact(988, 24, 20, g.turn, 'gun', sound=True)
    S.tick(g)
    assert recipient.ai['staff_courier'] == runner.id
    assert key not in recipient.ai.get('map_reports', {})
    report['turn'] += 500
    g = pickle.loads(pickle.dumps(g))
    recipient, runner = g.actors
    # Actual movement, not an ETA which reveals the report while the courier is elsewhere.
    for _ in range(60):
        g.turn += 1
        S.act(g, runner, [])
        if recipient.ai.get('staff_update'):
            break
    assert I.distance(recipient.pos, runner.pos) <= 2
    assert recipient.ai['map_reports'][key]['turn'] == 1000
    assert recipient.ai['staff_contacts'][987]['x'] == 22 and 988 not in recipient.ai['staff_contacts']
    assert any(r['id'] == 987 for r in I.local_contacts(g, recipient.squad, age=600))
    assert runner.ai['situation_dispatch']['returning']


def test_dead_runner_and_no_available_courier_leave_old_map_intact():
    g = scene()
    unradio(g.player)
    key, report = map_packet(g)
    runner = soldier(g, 35, 10, role='rifleman', rank=2)
    unradio(runner)
    g.map.gen_positions = [dict(kind='hq', side=g.player.side, x=35, y=10)]
    S.tick(g)
    runner.body.dead = True
    g.turn += 300
    S.tick(g)
    assert not g.player.ai.get('staff_update') and not g.player.ai.get('staff_courier')
    assert key not in g.player.ai.get('map_reports', {})


def test_old_packet_cannot_overwrite_new_map_and_courier_cannot_track_hidden_commander():
    g = scene()
    unradio(g.player)
    key, report = map_packet(g)
    old = S.packet(g, g.player.side)
    report['turn'] += 100
    I.merge_map(g.player, {key: report})
    S.deliver(g, g.player, old, 'runner')
    assert g.player.ai['map_reports'][key]['turn'] == report['turn']
    runner = soldier(g, 40, 10, role='rifleman')
    runner.ai['situation_dispatch'] = dict(recipient=g.player.id, data=old, origin=runner.pos, target=(10, 10))
    move(g, g.player, (10, 45))
    with patch('fow.ai.path_step', return_value=100) as path:
        S.act(g, runner, [])
    assert path.call_args.args[2:4] == (10, 10)


def test_commander_steering_voice_is_sparse_but_urgent_speech_still_works():
    g = Game('bocage44', 'usa', seed=25, setup=dict(vehicle='m4', station='commander', battlefield='standard'))
    ps = PlayState(FakeApp(), g)
    p, v = g.player, g.player.vehicle
    ps.act = lambda cost: True
    g.turn = 1000
    with patch.object(g, 'try_move_vehicle', return_value=100), patch.object(p, 'say', wraps=p.say) as say, \
            patch('fow.play.time.monotonic', return_value=1000):
        for dx, dy in [(1, 0), (1, 0), (0, 1), (-1, 0), (0, -1)] * 5:
            ps.drive(dx, dy)
            g.turn += 10
        assert say.call_count == 1
        p.say('Bail out!', g.turn, tone='panic')
        assert say.call_count == 2
    with patch.object(g, 'try_move_vehicle', return_value=100), patch.object(p, 'say', wraps=p.say) as say, \
            patch('fow.play.time.monotonic', return_value=1010):
        ps.drive(1, 0)
        assert say.call_count == 1


def test_hq_shortcut_and_command_search_reach_menu_without_stealing_run_left():
    from fow.play import Key
    g = scene()
    hq(g)
    ps = PlayState(FakeApp(), g)
    ps.on_key(Key(char='Q'))
    assert ps.popups and ps.popups[-1].title == 'HQ — service review and support'
    ps.popups.clear()
    ps.on_key(Key(char='H'))
    assert ps.running == (-1, 0) and not ps.popups


def test_repeated_completed_citation_does_not_create_more_presentation_errands():
    g = scene()
    hq(g)
    g.command._award(g, 4, 'for gallantry')
    g.command._award(g, 4, 'for gallantry')
    assert R.recommend_award(g, 4, 'for gallantry') is None
    assert not R.state(g)['awards']
