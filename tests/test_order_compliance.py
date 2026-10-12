"""Time spent obeying or surviving must not become disciplinary evidence."""
from test_command_realism import scene, soldier
from fow import actions, orders
from fow.entities import Item


def digging_order():
    g = scene()
    p = g.player
    p.rank = 0
    p.add_item(Item('shovel'))
    sup = soldier(g,12,10,rank=4)
    g.duty.give(g,'dig',sup)
    return g,g.duty.task


def test_dig_deadline_accounts_for_actual_work_and_active_work_cannot_be_punished():
    g,t = digging_order()
    required = actions.digging_seconds(g,g.player)
    assert t['deadline'] - g.turn >= required
    # Reproduce an old save's eight-minute deadline and keep actually digging past it.
    t['deadline'] = g.turn + 500
    rep = g.duty.rep
    for _ in range(900):
        assert actions.dig(g,g.player)
        g.turn += 1
        g.duty._check_task(g,t)
    assert t in g.duty.tasks and g.player.dig_progress > 0
    assert not t['nagged'] and g.duty.strikes == 0 and g.duty.rep == rep
    assert t['compliance'] == 'work in progress'


def test_cover_and_higher_orders_pause_work_with_time_to_return():
    g,t = digging_order()
    actions.dig(g,g.player)
    g.duty._check_task(g,t)
    t['deadline'] = g.turn+10
    g.player.suppression = 40
    g.player.x += 5
    g.turn += 600
    g.duty._check_task(g,t)
    assert t in g.duty.tasks and not t['nagged'] and not g.duty.strikes
    g.player.suppression = 0
    g.turn += 60
    g.duty._check_task(g,t)
    assert 'returning' in t['compliance']
    g.field_order = dict(text='Withdraw to the rear.',issued=g.turn+1,authority=18,edge='S',
                        sector=(g.sector.x,g.sector.y),point=(10,30),who='HQ',reason='Enemy attack')
    g.turn += 1200
    g.duty._check_task(g,t)
    assert t in g.duty.tasks and not g.duty.strikes
    assert t['compliance'] == 'higher-priority orders'


def test_unstarted_order_can_still_be_flagged_and_existing_cover_does_not_count_as_digging():
    g,t = digging_order()
    g.map.set(g.player.x,g.player.y,'rubble')
    g.map.refresh()
    assert g.map.tile(*g.player.pos).key != 'foxhole'
    g.turn = t['deadline']+1
    g.duty._check_task(g,t)
    assert t in g.duty.tasks and t['nagged']
    g.turn = t['deadline']+1
    g.duty._check_task(g,t)
    assert t not in g.duty.tasks and g.duty.strikes == 1


def test_real_foxhole_completes_the_order_and_no_shovel_is_not_disobedience():
    g,t = digging_order()
    for item in list(g.player.inv):
        if item.t.tool == 'shovel':
            g.player.remove_item(item)
    g.turn = t['deadline']+1
    g.duty._check_task(g,t)
    assert t in g.duty.tasks and not g.duty.strikes
    g.map.set(*t['target'],'foxhole')
    g.map.refresh()
    g.duty._check_task(g,t)
    assert t not in g.duty.tasks and g.duty.done == 1


def test_active_work_on_an_already_expired_legacy_deadline_is_not_reprimanded():
    g,t = digging_order()
    t['deadline'] = g.turn-1000
    t['_priority_checked'] = g.turn
    actions.dig(g,g.player)
    g.duty._check_task(g,t)
    assert t in g.duty.tasks and not t['nagged'] and not g.duty.strikes
    assert t['deadline'] > g.turn
