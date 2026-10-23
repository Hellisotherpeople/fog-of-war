"""HQ, workshop and staff visits must lead to staff who actually exist, and survive the walk there."""
from unittest.mock import patch

import pytest

from test_command_realism import scene, soldier, move
from test_smoke import FakeApp
from fow import contacts, debrief, orders, recognition, service
from fow.entities import Vehicle
from fow.intelligence import distance
from fow.play import PlayState


def unmapped(g):
    """No map sheet and no situation reports: only what the soldier can see or has been shown."""
    for it in list(g.player.inv):
        if it.t.tool == 'map':
            g.player.remove_item(it)
    g.player.ai['map_reports'] = {}


def post_with_staff(g, kind, role, x=40, y=20):
    g.sector.control = g.player.side
    g.map.gen_positions = [dict(kind=kind, side=g.player.side, x=x, y=y, rect=(x - 8, y - 6, 16, 12))]
    a = soldier(g, x + 2, y + 1, role=role, rank=9)
    a.squad.no_count = True
    return a


@pytest.mark.parametrize('kind,post,role', [('repairs', 'motor_pool', 'motor_sergeant'),
                                            ('supply', 'depot', 'quartermaster'),
                                            ('medical', 'aid', 'surgeon')])
def test_marked_post_visit_survives_walking_up_before_staff_are_in_sight(kind, post, role):
    """Approaching a marked post: its staff are not yet in view. That is not a lost appointment."""
    g = scene()
    unmapped(g)
    staff = post_with_staff(g, post, role)
    g.map.visible[40, 20] = True              # the post itself is in view; its staff are not
    key = contacts.request(g, kind)
    assert orders.focus(g, key)
    ticket = g.player.ai['contact_orders'][kind]
    assert ticket['destination']['person'] is None and ticket['destination']['point'] == (40, 20)
    # The player walks toward the post. Staff are behind a wall: out of sight, but at their post.
    with patch('fow.senses.player_can_see_actor', return_value=False):
        for x in range(12, 36, 3):
            move(g, g.player, (x, 20))
            contacts.entries(g)
            assert not ticket.get('destination_lost'), x
            assert orders.navigation(g)[:2] == (40, 20)    # the post, not the unseen man's live position
    # In speaking distance, with the staff in sight, the visit is to them.
    move(g, g.player, (staff.x - 2, staff.y))
    with patch('fow.senses.player_can_see_actor', return_value=True):
        contacts.entries(g)
        assert not ticket.get('destination_lost')
        assert orders.navigation(g)[:2] == staff.pos


def test_person_assigned_at_a_post_is_not_lost_when_line_of_sight_breaks():
    g = scene()
    staff = post_with_staff(g, 'motor_pool', 'motor_sergeant')
    contacts.request(g, 'repairs')
    ticket = g.player.ai['contact_orders']['repairs']
    move(g, g.player, (staff.x - 10, staff.y))
    with patch('fow.senses.player_can_see_actor', return_value=True):
        contacts.entries(g)
    assert ticket['destination']['person'] == staff.id
    move(g, g.player, (staff.x - 9, staff.y))
    with patch('fow.senses.player_can_see_actor', return_value=False):
        for _ in range(3):
            contacts.entries(g)
            assert not ticket.get('destination_lost')
    # ...but a post whose staff have really gone is still reported once the player is there.
    staff.body.dead = True
    move(g, g.player, (staff.x - 1, staff.y))
    with patch('fow.senses.player_can_see_actor', return_value=True):
        contacts.entries(g)
    assert ticket.get('destination_lost')


def test_hq_visit_can_be_completed_at_a_marked_headquarters_desk():
    g = scene()
    adj = post_with_staff(g, 'hq', 'adjutant', 30, 12)
    contacts.request(g, 'hq')
    order = debrief.entry(g)
    assert order['point'] is not None
    ticket = recognition.state(g)['report_order']
    with patch('fow.senses.player_can_see_actor', return_value=False):
        for x in range(12, 27, 2):
            move(g, g.player, (x, 12))
            debrief.entry(g)
            assert not ticket.get('destination_lost'), x
    move(g, g.player, (adj.x - 2, adj.y))
    with patch('fow.senses.player_can_see_actor', return_value=True):
        assert debrief.entry(g)['point'][:2] == adj.pos


def test_repair_service_order_points_at_the_fitters_not_only_the_post_centre():
    g = scene()
    sarge = post_with_staff(g, 'motor_pool', 'motor_sergeant')
    v = Vehicle('m4', g.player.side, 'usa', 15, 30)
    v.player_crewed, v.player_station = True, 'driver'
    v.crew_actors = [g.player]
    g.player.vehicle = v
    g.player.x, g.player.y = v.pos
    g.vehicles = [v]
    g.place_vehicle(v)
    g.player.ai['service_order'] = dict(kind='repair', vehicle=v.id, issued=g.turn, authority=g.player.rank,
                                        who='your crew', how='inspection', text='Take the vehicle to the motor pool.')
    entry = service.entry(g)
    assert entry['point'][:2] == (40, 20)
    ps = PlayState(FakeApp(), g)
    with patch('fow.service.drive_step') as drive:
        label, action = service.plan(ps)
        action()
    assert drive.called and 'repair workshop' in label
    # Arrived: the plan is to wait for the fitters' work, at the post.
    g.lift_vehicle(v)
    v.x, v.y = 38, 22
    g.player.x, g.player.y = v.pos
    g.place_vehicle(v)
    label, _ = service.plan(ps)
    assert 'fitters' in label


def test_remote_destination_is_not_offered_from_an_unmarked_sheet():
    """Without a map or an HQ visit, posts on other cells are not known."""
    g = scene()
    g.sector.control = g.player.side
    goal = g.strategic.at(g.sector.x + 2, g.sector.y, create=True)
    goal.control = g.player.side
    from fow.gamemap import GameMap
    m = GameMap(g.map_w, g.map_h, 1)
    m.gen_positions = [dict(kind='motor_pool', side=g.player.side, x=20, y=20)]
    g.__dict__.setdefault('_destination_maps', {})[(goal.x, goal.y)] = m
    g.player.ai['map_reports'] = {}
    assert service.destination(g, ('motor_pool', 'factory')) is None
    g.player.ai['map_reports'] = {(goal.x, goal.y): dict(control=g.player.side,
                                  installations=[('motor_pool', g.player.side, True)])}
    assert service.destination(g, ('motor_pool', 'factory'))['sector'] == (goal.x, goal.y)


def test_unknown_staff_in_view_are_found_and_staff_beyond_sight_are_not_a_target():
    g = scene()
    unmapped(g)
    medic = soldier(g, 30, 10, role='medic')
    with patch('fow.senses.player_can_see_actor', return_value=False):
        assert contacts.target(g, 'medical') is None
    with patch('fow.senses.player_can_see_actor', return_value=True):
        assert contacts.target(g, 'medical')['person'] == medic.id


def test_distance_helper_is_chebyshev():
    assert distance((0, 0), (3, -7)) == 7
