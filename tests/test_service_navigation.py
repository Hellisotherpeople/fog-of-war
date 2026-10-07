"""Service arrows, driving and the orders book must agree on a stable destination."""
import pickle
from unittest.mock import patch

import pytest

from test_command_realism import scene, move, soldier
from test_smoke import FakeApp
from fow import orders, service, contacts
from fow.entities import Vehicle
from fow.play import PlayState, Key


def repair_ticket(g):
    ticket = dict(kind='repair', vehicle=0, issued=g.turn, authority=g.player.rank,
                  who='your crew', how='inspection', text='Report to the repair workshop.')
    g.player.ai['service_order'] = ticket
    return ticket


def driver():
    g = scene()
    m = g.map
    m.fill(0, 0, m.w, m.h, 'grass')
    m.refresh()
    g.soldier_at.clear()
    v = Vehicle('m4', g.player.side, 'usa', 15, 19)
    v.player_crewed, v.player_station = True, 'driver'
    v.crew_actors = [g.player]
    g.player.vehicle = v
    g.player.x, g.player.y = v.pos
    g.vehicles = [v]
    g.place_vehicle(v)
    g.brains[g.player.side].veh_maps.clear()
    ps = PlayState(FakeApp(), g)
    ps.act = lambda cost: True  # use real driving, without running an unrelated battle
    return g, ps, v


def test_exit_waypoint_does_not_chase_the_vehicle_or_change_when_occupied():
    g, ps, v = driver()
    m = g.map
    m.fill(m.w - 5, 0, m.w, m.h, 'deep')
    m.refresh()
    state = g.rng.getstate()
    points = []
    for x, y in [(m.w - 9, 20), (m.w - 8, 20), (m.w - 8, 19), (m.w - 8, 21)]:
        g.lift_vehicle(v)
        v.x, v.y = x, y
        g.player.x, g.player.y = x, y
        g.place_vehicle(v)
        points.append(orders.exit_point(g, 'E'))
    assert len(set(points)) == 1
    assert g.rng.getstate() == state
    point = points[0]
    g.soldier_at[point] = g.player
    assert orders.exit_point(g, 'E') == point
    loaded = pickle.loads(pickle.dumps(g))
    assert orders.exit_point(loaded, 'E') == point


def test_repair_assignment_survives_a_detour_and_retargets_destroyed_workshop():
    g = scene()
    ticket = repair_ticket(g)
    first = dict(kind='motor_pool', side=g.player.side, x=10, y=20)
    second = dict(kind='factory', side=g.player.side, x=30, y=20)
    g.map.gen_positions = [first, second]
    assert service.entry(g)['point'][:2] == (10, 20)
    move(g, g.player, (27, 20))  # an approach/detour which passes nearer another shop
    assert service.entry(g)['point'][:2] == (10, 20)
    first['destroyed'] = True
    assert service.entry(g)['point'][:2] == (30, 20)
    assert ticket['destination']['kind'] == 'factory'


def test_new_nearer_report_does_not_reverse_an_existing_cross_sector_assignment():
    g = scene()
    ticket = repair_ticket(g)
    x, y = g.sector.x, g.sector.y
    goal = g.strategic.at(x + 2, y, create=True)
    alt = g.strategic.at(x, y - 1, create=True)
    report = dict(control=g.player.side, installations=[('factory', g.player.side, True)])
    g.player.ai['map_reports'] = {(goal.x, goal.y): report}
    service.entry(g)
    assert ticket['destination']['sector'] == (goal.x, goal.y)
    g.player.ai['map_reports'][(alt.x, alt.y)] = report
    service.entry(g)
    assert ticket['destination']['sector'] == (goal.x, goal.y)
    g.sector = g.strategic.at(x + 1, y, create=True)
    service.entry(g)
    assert ticket['destination']['sector'] == (goal.x, goal.y)
    g.sector = goal
    g.map.gen_positions = [dict(kind='factory', side=g.player.side, x=20, y=20)]
    assert service.entry(g)['point'][:2] == (20, 20)


def test_driving_reaches_the_same_arrival_radius_as_the_order():
    g, ps, v = driver()
    point = (20, 20)
    for _ in range(12):
        if max(abs(v.x - point[0]), abs(v.y - point[1])) <= 2:
            break
        service.drive_step(ps, point)
    assert max(abs(v.x - point[0]), abs(v.y - point[1])) <= 2


@pytest.mark.parametrize('kind,role,key', [
    ('supply', 'quartermaster', 'contact:supply'),
    ('medical', 'medic', 'contact:medical'),
    ('repairs', 'motor_sergeant', 'contact:repairs'),
    ('intel', 'intel', 'contact:intel'),
    ('hq', 'adjutant', 'personnel'),
])
def test_x_destinations_create_saved_orders_with_matching_arrow_and_enter(kind, role, key):
    from fow.ui import OrdersState
    import tcod
    from fow.constants import SCREEN_W, SCREEN_H
    g = scene()
    g.sector.control = g.player.side
    a = soldier(g, 25, 10, role=role, rank=9)
    if kind == 'hq':
        g.map.gen_positions = [dict(kind='hq', side=g.player.side, x=25, y=10)]
    app = FakeApp()
    ps = PlayState(app, g)
    app.states = [ps]
    with patch('fow.senses.player_can_see_actor', return_value=True), patch.object(ps, 'start_travel') as walk:
        ps.on_key(Key(char='X'))
        pop = ps.popups[-1]
        pop.sel = next(i for i, opt in enumerate(pop.options) if opt[1] == kind)
        ps.popup_select()
        order = next(o for o in orders.book(g) if o['key'] == key)
        assert order['active'] and not order['deferred'] and order['due'] is None
        assert orders.navigation(g)[:2] == a.pos and g.order_pointer()[:2] == a.pos
        assert walk.call_args.args[:2] == a.pos
        walk.reset_mock()
        ps._order_plan()[1]()
        assert walk.call_args.args[:2] == a.pos
        screen = OrdersState(app, ps)
        screen.sel = next(i for i, o in enumerate(screen.orders) if o['key'] == key)
        con = tcod.console.Console(SCREEN_W, SCREEN_H, order='F')
        screen.render(con)
        assert a.full_name in '\n'.join(''.join(map(chr, row)) for row in con.ch.T)
        loaded = pickle.loads(pickle.dumps(g))
        assert orders.active(loaded)['key'] == key
        assert orders.navigation(loaded)[:2] == a.pos


def test_contact_visit_stays_assigned_and_finishes_only_at_the_correct_person():
    g = scene()
    a = soldier(g, 20, 10, role='medic')
    b = soldier(g, 40, 10, role='medic')
    ps = PlayState(FakeApp(), g)
    with patch('fow.senses.player_can_see_actor', return_value=True):
        key = contacts.request(g, 'medical')
        assert orders.focus(g, key)
        move(g, g.player, (37, 10))
        assert orders.navigation(g)[:2] == a.pos
        move(g, g.player, (19, 10))
        action = ps._order_plan()[1]
        a.body.dead = True
        with patch('fow.talk.open_talk') as talk:
            action()
            assert 'medical' in g.player.ai['contact_orders'] and not talk.called
            assert orders.navigation(g)[:2] == b.pos
            move(g, g.player, (39, 10))
            ps._order_plan()[1]()
            talk.assert_called_once_with(ps, b)
        assert not any(o['key'] == key for o in orders.book(g))


def test_multiple_x_visits_remain_in_orders_and_can_be_cleared():
    g = scene()
    ps = PlayState(FakeApp(), g)
    soldier(g, 20, 10, role='medic')
    soldier(g, 25, 10, role='quartermaster')
    with patch('fow.senses.player_can_see_actor', return_value=True):
        keys = {contacts.request(g, kind) for kind in ('medical', 'supply')}
        assert keys <= {o['key'] for o in orders.book(g)}
        orders.focus(g, 'contact:supply')
        contacts.menu(ps)
        pop = ps.popups[-1]
        pop.sel = next(i for i, opt in enumerate(pop.options) if opt[1] == 'clear')
        ps.popup_select()
        assert not g.player.ai['contact_orders'] and not g.order_focus
        assert not keys & {o['key'] for o in orders.book(g)}


def test_x_visit_is_listed_but_does_not_override_a_field_mission():
    from fow.ui import OrdersState
    g = scene()
    soldier(g, 25, 10, role='quartermaster')
    g.field_order = dict(text='Defend this bridge', point=(40, 40), issued=g.turn, authority=17,
                         sector=(g.sector.x, g.sector.y), who='General', reason='Hold', edge=None)
    app = FakeApp()
    ps = PlayState(app, g)
    app.states = [ps]
    with patch('fow.senses.player_can_see_actor', return_value=True), patch.object(ps, 'start_travel') as walk:
        ps.on_key(Key(char='X'))
        pop = ps.popups[-1]
        pop.sel = next(i for i, opt in enumerate(pop.options) if opt[1] == 'supply')
        ps.popup_select()
        assert isinstance(app.states[-1], OrdersState)
        order = next(o for o in orders.book(g) if o['key'] == 'contact:supply')
        assert order['deferred'] and not walk.called
        assert orders.navigation(g)[:2] == (40, 40)


def test_contact_order_authorizes_its_marked_exit_and_keeps_it_while_moving():
    g = scene()
    goal = g.strategic.at(g.sector.x + 1, g.sector.y, create=True)
    g.player.ai['map_reports'] = {(goal.x, goal.y): dict(control=g.player.side,
        installations=[('depot', g.player.side, True)])}
    key = contacts.request(g, 'supply')
    assert orders.focus(g, key)
    from fow.base import _next_edge
    edge = _next_edge(g, (goal.x, goal.y))
    pt = orders.navigation(g)
    move(g, g.player, (17, 20))
    assert orders.navigation(g) == pt and orders.authorized_departure(g, edge)
    assert not orders.authorized_departure(g, {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}[edge])


def test_enter_drives_to_stable_exit_then_crosses_into_workshop_sector():
    g, ps, v = driver()
    repair_ticket(g)
    goal = g.strategic.at(g.sector.x + 1, g.sector.y, create=True)
    g.player.ai['map_reports'] = {(goal.x, goal.y): dict(control=g.player.side,
        installations=[('motor_pool', g.player.side, True)])}
    with patch('fow.base._next_edge', return_value='E'), patch.object(ps, '_travel_chosen') as travel:
        point = service.entry(g)['point']
        for _ in range(g.map.w + 10):
            assert service.entry(g)['point'] == point
            service.plan(ps)[1]()
            if travel.called:
                break
        travel.assert_called_once_with('E')
        assert max(abs(v.x - point[0]), abs(v.y - point[1])) <= 2


@pytest.mark.parametrize('kind,role', [('supply', 'quartermaster'), ('intel', 'intel'),
                                      ('medical', 'medic'), ('repairs', 'motor_sergeant')])
def test_normal_conversation_also_completes_a_service_visit(kind, role):
    from fow import qmui, talk, base
    g = scene()
    a = soldier(g, 25, 10, role=role)
    other = soldier(g, 13, 10, role=role)
    ps = PlayState(FakeApp(), g)
    open_contact = {'supply': qmui.open_quartermaster, 'intel': qmui.open_intel,
                    'medical': talk.open_talk, 'repairs': base.talk}[kind]
    with patch('fow.senses.player_can_see_actor', return_value=True):
        contacts.request(g, kind)
        # This request chose the nearer man, not somebody else with the same job.
        move(g, g.player, (24, 10))
        contacts.met(g, a)
        assert kind in g.player.ai['contact_orders']
        contacts.met(g, other)
        assert kind in g.player.ai['contact_orders']  # still too far from the assigned contact
        move(g, g.player, (12, 10))
        open_contact(ps, other)
        assert ps.popups and kind not in g.player.ai['contact_orders']
