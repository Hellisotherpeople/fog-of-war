"""Regressions for resource conservation, treatment and persistent battlefield state."""
from collections import Counter
from unittest.mock import Mock, patch
from types import SimpleNamespace

import pytest

from test_objective_completion import cemetery
from test_command_realism import soldier, move
from test_squadcare import scene, hurt, index
from fow import actions, ai, ammo, commander, medevac, medical, squadcare, streaming
from fow.body import Wound
from fow.entities import Item
from fow.inventory import Inventory, stack_max


@pytest.mark.parametrize("interruption", ["contested", "changed_side"])
def test_capture_requires_twenty_uninterrupted_seconds_by_one_side(interruption):
    g, sq, ob = cemetery()
    ob.owner = None
    with patch.object(g, "on_objective_taken") as taken:
        commander.update_objectives(g, 15)
        assert ob.hold_time == 15
        enemy = soldier(g, *ob.pos, nation="germany", role="rifleman")
        if interruption == "contested":
            commander.update_objectives(g, 5)
            move(g, enemy, (60, 50))
            expected = sq.side
        else:
            for a in sq.members:
                move(g, a, (5 + a.id % 4, 5))
            expected = enemy.side
        commander.update_objectives(g, 5)
        assert ob.owner is None and ob.hold_time == 5
        commander.update_objectives(g, 15)
        assert ob.owner == expected
        taken.assert_called_once_with(0, expected, None)


def test_seamless_sector_crossing_does_not_cancel_nearby_medical_errand():
    g, sq, lead, helper = scene(dressings=2)
    hurt(g.player, 4)
    squadcare.dispatch(g, sq)
    assert helper.ai["support_job"]["kind"] == "aid"
    # Both men still occupy the same live frame after the player crosses a cell.
    g.landscape = SimpleNamespace(frame=g.map)
    g.sector = g.strategic.at(g.sector.x + 1, g.sector.y, create=True)
    assert squadcare.claimed(g, g.player, "aid")
    helper.x, helper.y = g.player.x - 1, g.player.y
    index(g)
    assert squadcare.act(g, helper, [])
    assert g.player.body.bleed_rate() < 4


def test_repeat_surgery_never_regrows_an_amputated_limb_or_counts_it_as_a_new_wound():
    g, sq, surgeon, patient = scene()
    surgeon.role = "surgeon"
    b = patient.body
    b.hp["l_arm"] = 0
    b.amputated = {"l_arm"}
    patient.ai["amputated"] = ["l_arm"]
    b.hp["r_arm"] = 0
    # One new ruined limb, regardless of a prior amputation.
    expected = 600 + medical.missing_hp(b) * 22 + 900
    assert medical.surgery_time(b) == expected
    # Survive the operation and save the newly damaged arm.
    with patch.object(g.rng, "random", side_effect=[.99, .1]):
        assert medical.finish_surgery(g, surgeon, patient) == "saved"
    assert b.hp["l_arm"] == 0 and b.hp["r_arm"] > 0
    assert b.amputated == {"l_arm"}


def test_untreatable_wounds_do_not_claim_medics_or_award_free_experience():
    g, sq, lead, helper = scene()
    helper.role = "medic"
    helper.invent = Inventory()
    helper.add_item(Item("tourniquet"))
    g.player.body.wounds.append(Wound("torso", 6, "gunshot"))
    assert not medical.can_help(g, helper, g.player)
    with patch("fow.skills.use") as learned:
        assert medical.first_aid(g, helper, g.player) is None
        learned.assert_not_called()
    helper.invent.slots['pack'] = Item('suitcase')
    assert helper.add_item(Item("plasma"))
    g.player.body.blood = 2500
    assert medical.can_help(g, helper, g.player)
    assert medical.first_aid(g, helper, g.player)
    assert g.player.body.blood > 2500


def test_partial_clip_reload_preserves_every_round_and_its_condition_when_pockets_are_full():
    g, sq, lead, helper = scene()
    p = g.player
    p.invent = Inventory()
    gun = Item("kar98k")
    gun.loaded = gun.t.mag - 1
    p.weapon = gun
    p.add_item(gun)
    clip = Item(gun.t.stripper)
    clip.condition = .4
    assert p.add_item(clip)
    while p.add_item(Item("bandage")) is not None:
        pass
    total = gun.loaded + ammo.spare_rounds(p, gun)
    assert ammo.reload(g, p, gun)
    leftovers = [it for it in p.inv + g.map.items_at(*p.pos) if it.t.kind == "ammo"]
    assert gun.loaded + sum(it.count for it in leftovers) == total
    assert all(it.condition == .4 for it in leftovers)


@pytest.mark.parametrize('quality', [.4, 1.])
def test_stripping_a_magazine_preserves_ammunition_quality_and_full_action_cost(quality):
    from fow.invui import InventoryScreen
    from fow.data.items import ammo_id
    g, sq, lead, helper = scene()
    p = g.player
    magazine = Item(p.weapon.t.magtype)
    magazine.data = {'rounds_condition': quality}
    assert p.add_item(magazine)
    assert p.add_item(Item(ammo_id(magazine.t.cal), 1))
    count = magazine.loaded
    ps = SimpleNamespace(game=g, act=Mock())
    InventoryScreen(ps).do_unload(magazine)
    loose = [it for it in p.inv if it.t.kind == 'ammo']
    assert magazine.loaded == 0 and sum(it.count for it in loose) == count + 1
    assert sum(it.count * it.condition for it in loose) == pytest.approx(count * quality + 1)
    ps.act.assert_called_once_with(40 * max(1, count // 3))


def test_removed_magazine_does_not_reveal_an_unknown_round_count():
    g, sq, lead, helper = scene()
    gun = g.player.weapon
    gun.loaded, gun.known_rounds = 7, False
    magazine = gun.mag_item
    ammo.unload(g.player, gun)
    assert magazine.loaded == 7 and not magazine.known_rounds


def test_inventory_preserves_partial_consumables_and_rejects_foreign_removal():
    inv, other = Inventory(), Inventory()
    partial, full = Item("cigarettes"), Item("cigarettes")
    partial.uses = 2
    assert inv.add(full) and inv.add(partial)
    packs = [i for grid, _ in inv.grids() for i in grid.items]
    assert sum(i.uses + (i.count - 1) * i.t.uses for i in packs) == 22
    assert not other.remove(partial)
    assert inv.contains(partial)


def test_inventory_splits_oversized_stacks_and_preserves_overflow():
    inv = Inventory()
    it = Item("bandage", 100)
    initial = it.count
    assert inv.add(it) is None
    carried = [i for grid, _ in inv.grids() for i in grid.items]
    assert carried and all(i.count <= stack_max(i.t) for i in carried)
    assert sum(i.count for i in carried) + it.count == initial


def test_banknotes_keep_their_defined_bundle_capacity():
    inv = Inventory()
    money = Item('francs', 500)
    assert inv.add(money) and inv.contains(money) and money.count == 500
    assert stack_max(money.t) == 500


def test_using_or_splitting_a_packet_preserves_unopened_packets():
    g, sq, lead, helper = scene()
    p = g.player
    p.invent = Inventory()
    cig = Item('cigarettes', 2)
    cig.uses = 1
    p.add_item(cig)
    assert p.consume_use(cig)
    assert cig.count == 1 and cig.uses == 20 and p.invent.contains(cig)
    assert p.consume_use(cig)
    assert cig.uses == 19
    # Partial packets in older saves can still be stacked with unopened ones.
    cig.count, cig.uses = 2, 3
    taken = p.remove_item(cig, 1)
    assert taken.uses == 3 and cig.uses == 20 and cig.count == 1


@pytest.mark.parametrize('share', [False, True])
def test_player_smoking_and_sharing_use_one_cigarette_and_preserve_the_next_packet(share):
    from fow.play import PlayState
    g, sq, lead, helper = scene()
    p = g.player
    p.invent = Inventory()
    cig = Item('cigarettes', 2)
    cig.uses = 1
    assert p.add_item(cig)
    ps = SimpleNamespace(game=g, act=Mock())
    if share:
        PlayState._give(ps, helper, 'give_smoke')
    else:
        PlayState.use_tool(ps, cig)
    assert p.invent.contains(cig) and cig.count == 1 and cig.uses == 20
    ps.act.assert_called_once_with(90 if share else 300)


def test_empty_canteens_cannot_remove_thirst():
    g, sq, lead, helper = scene()
    p = g.player
    canteen = Item('canteen')
    assert p.add_item(canteen)
    canteen.uses = 0
    p.ai['needs'] = dict(hunger=0., thirst=80., infection=0.)
    assert actions.drink(g, p, canteen) == 0
    assert p.ai['needs']['thirst'] == 80


def test_partial_pickup_costs_time_and_leaves_only_the_actual_overflow():
    g, sq, lead, helper = scene()
    p = g.player
    p.invent = Inventory()
    item = Item('bandage', 100)
    g.map.add_item(*p.pos, item)
    assert actions.pickup(g, p, item) > 0
    assert item in g.map.items_at(*p.pos) and 0 < item.count < 100
    assert sum(it.count for it in p.inv) + item.count == 100
    before = item.count
    assert actions.pickup(g, p, item) is None and item.count == before


def test_failed_trade_is_atomic_even_with_oversized_stacks_from_an_old_save():
    from fow.social import _swap
    g, sq, lead, helper = scene()
    p = g.player
    p.invent = Inventory()
    offered = Item('cigarettes')
    assert p.add_item(offered)
    requested = Item('bandage')
    assert helper.add_item(requested)
    requested.count = 100
    assert not _swap(p, offered, helper, requested)
    assert p.inv == [offered] and helper.invent.contains(requested)
    assert requested.count == 100


def fill_pockets(inv):
    while True:
        filler = Item('bandage')
        filler.condition = .9  # keep each filler distinct from the stack under test
        if inv.add(filler) is None:
            return


def test_quartermaster_cannot_issue_unpaid_supplies_through_a_partial_merge():
    from fow import qmui
    g, sq, lead, helper = scene()
    p = g.player
    p.invent = Inventory()
    dressing = Item('bandage', 2)
    p.add_item(dressing)
    fill_pockets(p.invent)
    g.command.credit = 100
    ps = SimpleNamespace(game=g, act=Mock())
    before = sum(it.count for it in p.inv)
    with patch.object(qmui.L, 'stock', return_value=([dressing.t], 1, 1)), \
         patch.object(qmui.L, 'price', return_value=10), patch.object(qmui, '_draw_list'):
        qmui._draw(ps, lead, dressing.t, ('medical',))
    assert dressing.count == 2 and g.command.credit == 100
    assert sum(it.count for it in p.inv) == before and not ps.act.called
    # With space for the whole purchase, both the credit and physical stores pay.
    filler = next(it for it in p.inv if it is not dressing)
    p.remove_item(filler)
    with patch.object(qmui.L, 'stock', return_value=([dressing.t], 1, 1)), \
         patch.object(qmui.L, 'price', return_value=10), patch.object(qmui, '_draw_list'), \
         patch('fow.sustain.take') as stock:
        qmui._draw(ps, lead, dressing.t, ('medical',))
    assert g.command.credit == 90 and sum(it.count for it in p.inv) == before + 1
    stock.assert_called_once()
    ps.act.assert_called_once_with(60)


def test_partial_grenade_resupply_debits_exactly_the_received_quantity():
    from fow import sustain
    g, sq, lead, helper = scene()
    p = g.player
    p.invent = Inventory()
    fill_pockets(p.invent)
    p.remove_item(p.inv[0])
    g.map.add_item(*p.pos, Item('ammo_crate'))
    reserve = sustain.stores(g.sector, p.side)
    reserve['ammo'] = 10
    with patch('fow.data.roles.pick_grenade', return_value='mk2'):
        assert actions.resupply(g, p) == 400
    assert sum(it.count for it in p.grenades()) == 1 and reserve['ammo'] == 9.5


def test_inventory_screen_cannot_transfer_part_of_a_stack_without_spending_time():
    from fow.invui import InventoryScreen, Pane
    g, sq, lead, helper = scene()
    p = g.player
    p.invent = Inventory()
    dressing = Item('bandage', 2)
    p.add_item(dressing)
    fill_pockets(p.invent)
    donor = Inventory()
    bundle = Item('bandage', 3)
    assert donor.add(bundle)
    ps = SimpleNamespace(game=g, act=Mock())
    pane = Pane('Kit on the ground', donor)
    screen = InventoryScreen(ps, [pane])
    screen.quick_move(bundle, {'pane': pane})
    assert dressing.count == 2 and bundle.count == 3 and donor.contains(bundle)
    ps.act.assert_not_called()


@pytest.mark.parametrize('source', ['ground', 'corpse'])
def test_scavenging_counts_only_ammunition_physically_collected(source):
    from fow import tasks
    from fow.data.items import ammo_id
    g, sq, lead, helper = scene()
    gun = helper.weapon
    helper.invent = Inventory()
    helper.add_item(gun)
    item = Item(ammo_id(gun.t.cal), 1000)
    if source == 'ground':
        g.map.add_item(*helper.pos, item)
    else:
        inv = Inventory()
        item.count = 1
        assert inv.add(item)
        item.count = 1000  # an old save's oversized stack
        corpse = Item('corpse')
        corpse.data = {'inv': inv, 'name': 'A rifleman'}
        g.map.add_item(*helper.pos, corpse)
    helper.ai['task_pile'] = helper.pos
    task = dict(kind='ammo', home=helper.pos, found=Counter())
    assert tasks._scavenge(g, helper, sq, task) == 250
    gathered = sum(it.count for it in helper.inv if it.t.kind == 'ammo')
    assert 0 < gathered < 1000 and task['found'][item.t.name] == gathered
    remainder = sum(it.count for it in g.map.items_at(*helper.pos) if it.t.kind == 'ammo')
    if source == 'corpse':
        remainder += sum(it.count for it in inv.items())
    assert gathered + remainder == 1000


def test_medevac_recognizes_recent_hits_and_hospital_clears_drugs():
    g, sq, lead, helper = scene()
    p = g.player
    p.hit_turn = g.turn
    with patch.object(g, 'seen_enemies', return_value=[]):
        assert medevac._safe(g, p) == (False, "you're under fire")
    p.body.morphine, p.body.alcohol = 120, 2
    p.body.amputated = {'l_arm'}
    p.ai['amputated'] = ['l_arm']
    p.body.hp['l_arm'] = 0
    medevac._heal(p)
    assert p.body.morphine == 0 and p.body.alcohol == 0
    assert p.body.hp['l_arm'] == 0


def test_suppressed_helper_does_not_block_a_closer_medic_from_urgent_care():
    from test_squadcare import squad
    g, sq, lead, helper = scene(dressings=2)
    hurt(g.player, 5)
    squadcare.dispatch(g, sq)
    other_sq, other_lead, distant = squad(g, x=20, y=12, dressings=2)
    distant.ai['support_job'] = dict(helper.ai['support_job'])
    helper.x, helper.y, helper.suppression = g.player.x - 1, g.player.y, 70
    lead.x, lead.y = g.player.x - 2, g.player.y
    index(g)
    g._support_claims = None
    assert squadcare.claimed(g, g.player, 'aid', lead)
    assert not squadcare.aid_claimed(g, g.player, lead)


def test_squad_fire_danger_coordinates_follow_the_world_frame():
    g, sq, lead, helper = scene()
    sq.beaten = (10, 12, 8, 300)
    sq.fired_from = (20, 25, 100)
    streaming.squad(sq, -30, 50, set())
    assert sq.beaten == (-20, 62, 8, 300)
    assert sq.fired_from == (-10, 75, 100)


@pytest.mark.parametrize("kind", ["rifle", "mg"])
def test_defensive_positions_handle_targets_outside_the_live_frame(kind):
    g, sq, lead, helper = scene()
    sq.kind = kind
    sq.order = ai.Order("attack", target=(g.map.w + 50, 20))
    ai.assign_positions(g, sq)
    assert all(g.map.in_bounds(*pos) for pos in sq.positions.values())
