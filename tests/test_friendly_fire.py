"""Intent, surviving witnesses and distinct attacks govern friendly-fire discipline."""
from unittest.mock import patch

import pytest

from test_command_realism import scene, soldier, move
from test_smoke import Game
from fow import actions, combat, conduct, orders, recognition
from fow.entities import Item, Vehicle


def field():
    g = scene()
    g.map.visible[1:65, 1:55] = True
    g.view_range_cache = 60
    g.player.hit_turn = -9999
    g.player.suppression = 0
    g.player.visible = []
    return g


def tank(g):
    v = Vehicle('m4', g.player.side, g.player.nation, *g.player.pos)
    g.player.vehicle = v
    v.player_crewed, v.player_station, v.crew = True, 'driver', 5
    g.vehicles.append(v)
    g.place_vehicle(v)
    return v


def shoot(g, victim, lethal=False, repeats=1):
    """Real trigger/burst bookkeeping and wounds, with a deterministic trajectory."""
    g.player.weapon = Item('m1_garand')

    def trajectory(*args, **kwargs):
        for _ in range(repeats):
            combat.hit_actor(g, victim, 500 if lethal else 2, 'gunshot', g.player,
                             'rifle', part='torso')
        return 'hit'

    with patch('fow.combat.trace_projectile', side_effect=trajectory):
        combat.fire_weapon(g, g.player, g.player.weapon, *victim.pos, victim)


def test_one_vehicle_explosion_cannot_make_driver_a_murderer():
    g = field()
    v = tank(g)
    friends = [soldier(g, 20 + i, 10, role='rifleman') for i in range(3)]
    rep, strikes = g.duty.rep, g.duty.strikes
    combat.explode(g, 21, 10, 1200, 4, attacker=v, source='tank HE')
    assert any(not a.alive for a in friends)
    assert not g.renegade and not g.duty.arrest
    assert (g.duty.rep, g.duty.strikes) == (rep, strikes)
    assert g.duty.ff_incidents == g.duty.murders == 0
    assert g.duty.ff_accidents == 1


@pytest.mark.parametrize('ordered', [False, True])
def test_aimed_enemy_shell_does_not_become_murder_when_enemy_dies_first(ordered):
    g = field()
    v = tank(g)
    enemy = soldier(g, 22, 10, nation='germany')
    friend = soldier(g, 22, 11)
    soldier(g, 16, 15)

    def fire(*args):
        combat.hit_actor(g, enemy, 500, 'blast', v, 'HE', part='torso')
        for _ in range(4):
            combat.hit_actor(g, friend, 4, 'blast', v, 'HE', part='l_arm')
        return True

    with patch('fow.combat._vehicle_fire_main', side_effect=fire):
        assert combat.vehicle_fire_main(g, v, *enemy.pos, enemy, 'he', ordered=ordered)
    assert not enemy.alive and friend.body.hp['l_arm'] < friend.body.max['l_arm']
    assert g.duty.ff_incidents == 0 and g.duty.rep == 0 and not g.renegade


def test_repeated_collateral_and_tracks_never_accrue_disciplinary_strikes():
    g = field()
    v = tank(g)
    for i in range(12):
        friend = soldier(g, 20, 10)
        combat.hit_actor(g, friend, 500, 'blunt', v, 'tracks', part='torso')
        g.turn += 5
    assert g.duty.ff_accidents == 12
    assert g.duty.rep == 0 and g.duty.strikes == 0
    assert not g.renegade and not g.duty.arrest


def test_one_burst_counts_once_and_a_fresh_attack_after_warning_is_required():
    g = field()
    friend = soldier(g, 14, 10)
    soldier(g, 12, 14)
    shoot(g, friend, repeats=5)
    assert g.duty.ff_incidents == 1 and not g.renegade
    g.turn += 1
    shoot(g, friend)
    assert g.duty.ff_incidents == 2 and g.renegade
    assert g.player in g.enemies_of(g.player.side)


def test_a_stale_warning_is_not_an_ongoing_armed_attack():
    g = field()
    friend = soldier(g, 14, 10)
    soldier(g, 12, 14)
    shoot(g, friend)
    g.turn += 300
    shoot(g, friend)
    assert g.duty.ff_incidents == 2 and not g.renegade


def test_surrender_preserves_rank_and_valor_restores_a_still_held_command():
    g = field()
    friend = soldier(g, 14, 10)
    soldier(g, 12, 14)
    rank, squad = g.player.rank, g.command.billet_squad
    shoot(g, friend, lethal=True)
    g.player.weapon = None
    g.duty._arrest_check(g)
    assert g.duty.disgraced and g.player.rank == rank and g.command.billet_squad is None
    g.turn += 1
    recognition.claim(g, 'objectives', 3, 'securing the crossing', (15, 10))
    assert not g.duty.disgraced and g.command.billet_squad is squad


@pytest.mark.parametrize('hidden', ['no witness', 'wall', 'dead witness', 'unseen target'])
def test_an_unseen_killing_cannot_prove_intent(hidden):
    g = field()
    victim = soldier(g, 14, 10)
    if hidden != 'no witness':
        witness = soldier(g, 12, 14)
        if hidden == 'wall':
            g.map.fill(9, 12, 17, 13, 'wall_stone')
            g.map.refresh()
        elif hidden == 'dead witness':
            witness.body.dead = True
        else:
            g.map.visible[victim.pos] = False
    shoot(g, victim, lethal=True)
    assert not victim.alive
    assert not g.renegade and not g.duty.arrest and g.duty.ff_incidents == 0


def test_arrest_does_not_turn_into_a_death_sentence_for_remaining_in_tank():
    g = field()
    victim = soldier(g, 14, 10)
    soldier(g, 12, 14)
    shoot(g, victim, lethal=True)
    assert g.duty.arrest and g.duty.murders == 1
    tank(g)
    g.turn += 120
    g.duty._arrest_check(g)
    assert not g.renegade and g.duty.arrest
    assert any(o['key'] == 'conduct' for o in orders.book(g))


def test_delayed_grenade_keeps_original_aim_and_surviving_witnesses(tmp_path):
    g = field()
    victim = soldier(g, 14, 10)
    soldier(g, 10, 16)
    grenade = Item('mk2')
    g.player.add_item(grenade)
    with patch.object(g.rng, 'gauss', return_value=0):
        assert actions.throw(g, g.player, grenade, *victim.pos)
    assert g.explosives and g.explosives[-1]['evidence']['deliberate']
    saved = tmp_path / 'grenade.pkl'
    g.save(str(saved))
    g = Game.load(str(saved))
    move(g, g.player, (7, 10))
    for _ in range(10):
        g.turn += 1
        g._tick_explosives()
    assert g.duty.ff_incidents == 1 and not g.renegade


def test_mortar_splash_keeps_the_enemy_target_when_the_battle_moves_on(tmp_path):
    g = field()
    enemy = soldier(g, 42, 10, nation='germany')
    friend = soldier(g, 42, 11)
    soldier(g, 30, 15)
    mortar = Item('m2_mortar')
    g.player.weapon = mortar
    g.player.invent.slots['pack'] = Item('backpack')
    assert g.player.add_item(Item('ammo_m60')) is not None
    assert g.player.ammo_for(mortar) is not None
    with patch.object(g.rng, 'gauss', return_value=0):
        assert combat.fire_weapon(g, g.player, mortar, *enemy.pos, enemy)
    assert g.shells and not g.shells[-1]['evidence']['deliberate']
    enemy.body.dead = True
    saved = str(tmp_path / 'shell.pkl')
    g.save(saved)
    g = Game.load(saved)
    friend = next(a for a in g.actors if a.id == friend.id)
    g.turn += 30
    g._tick_shells()
    assert friend.hit_turn == g.turn
    assert not g.renegade and g.duty.ff_incidents == 0 and g.duty.rep == 0


def test_uncontrolled_crew_fire_is_not_proof_against_the_driver():
    g = field()
    v = tank(g)
    friend = soldier(g, 18, 10)
    soldier(g, 15, 15)
    with patch('fow.combat._vehicle_fire_main', side_effect=lambda *a: combat.hit_actor(
            g, friend, 500, 'blast', v, 'HE', part='torso')):
        combat.vehicle_fire_main(g, v, *friend.pos, friend, 'he')
    assert not friend.alive and not g.duty.arrest and not g.renegade
    assert not g.duty.ff_incidents


def hostile(g):
    friend = soldier(g, 14, 10)
    soldier(g, 12, 14)
    shoot(g, friend)
    g.turn += 1
    shoot(g, friend)
    assert g.renegade
    g.turn += 1


def test_three_witnessed_enemy_kills_restore_cooperation_and_hq_order():
    g = field()
    hostile(g)
    from fow.brain import Contact
    from fow.intelligence import local_contacts
    friend = g.actors[2]
    friend.visible = [g.player]
    g.brains[g.player.side].contacts[g.player.id] = Contact(g.player.id, *g.player.pos, g.turn, 'inf', g.player)
    before = g.duty.ff_incidents
    for i in range(3):
        enemy = soldier(g, 20, 10, nation='germany', role='rifleman')
        combat.hit_actor(g, enemy, 500, 'gunshot', g.player, 'rifle', part='torso')
        g.turn += 1
        if i < 2:
            assert g.renegade
    assert not g.renegade and not g.duty.disgraced and not g.duty.arrest
    assert g.duty.rep >= 0 and g.player not in g.enemies_of(g.player.side)
    assert g.player.squad.player_led
    assert g.duty.ff_incidents == before  # the record has not been erased
    assert any(o['key'] == 'personnel' for o in orders.book(g))
    assert not any(o['key'] == 'conduct' for o in orders.book(g))
    assert g.player not in friend.visible
    # A stale report arriving after the stand-down must not revive the target.
    g.brains[g.player.side].contacts[g.player.id] = Contact(g.player.id, *g.player.pos, g.turn, 'inf')
    friend.ai['staff_contacts'] = {g.player.id: dict(id=g.player.id, turn=g.turn, x=10, y=10)}
    assert not g.brains[g.player.side].live_contacts()
    assert not local_contacts(g, friend.squad)


def test_one_witnessed_enemy_vehicle_knockout_restores_cooperation():
    g = field()
    hostile(g)
    v = Vehicle('kingtiger', 'axis', 'germany', 20, 10)
    g.vehicles.append(v)
    g.place_vehicle(v)
    combat.destroy_vehicle(g, v, g.player, 'AP hit')
    assert v.dead and not g.renegade
    assert recognition.state(g)['claims'][-1]['weight'] == .6


def test_finishing_an_incapacitated_enemy_does_not_restore_trust():
    g = field()
    hostile(g)
    for _ in range(4):
        enemy = soldier(g, 20, 10, nation='germany')
        enemy.body.hp['l_leg'] = enemy.body.hp['r_leg'] = 0
        assert enemy.downed
        combat.hit_actor(g, enemy, 500, 'gunshot', g.player, 'rifle', part='torso')
    assert g.renegade and conduct.state(g)['valor'] == 0


@pytest.mark.parametrize('deliberate', [False, True])
def test_civilian_losses_affect_the_district_but_accidents_do_not_punish_the_player(deliberate):
    g = field()
    victim = soldier(g, 14, 10, nation='germany')
    victim.ai['civilian'] = True
    soldier(g, 12, 14)
    g.sector.homefront = dict(casualties=0, goodwill=0)
    merit = g.command.merit
    if deliberate:
        shoot(g, victim, lethal=True)
    else:
        combat.hit_actor(g, victim, 500, 'blast', g.player, 'shell fragments', part='torso')
    assert g.sector.homefront['casualties'] == 1 and g.sector.homefront['goodwill'] < 0
    assert g.command.merit == merit
    assert bool(g.duty.arrest) == deliberate
    assert (g.duty.rep < 0) == deliberate


def test_unwitnessed_kills_prisoners_and_old_credit_cannot_rehabilitate():
    g = field()
    g.renegade = True
    g.duty.rep = -60
    for i in range(4):
        enemy = soldier(g, 20, 10, nation='germany')
        combat.hit_actor(g, enemy, 500, 'gunshot', g.player, 'rifle', part='torso')
    soldier(g, 12, 14)
    prisoner = soldier(g, 20, 10, nation='germany')
    prisoner.state = 'surrendered'
    combat.hit_actor(g, prisoner, 500, 'gunshot', g.player, 'rifle', part='torso')
    recognition.state(g)['credited'] = 500
    recognition.process(g)
    assert g.renegade and conduct.state(g)['valor'] == 0


def test_witnessed_rescue_restores_trust_without_erasing_other_punishments():
    g = field()
    hostile(g)
    soldier(g, 20, 10, nation='germany')
    casualty = soldier(g, 11, 10)
    g.player.suppression = 30
    g.wanted = 'desertion'
    g.duty.strikes = 3
    g.duty.good_deed(g, 'rescue', casualty)
    assert not g.renegade and g.duty.rep >= 0
    assert g.wanted == 'desertion' and g.duty.strikes == 3


def test_treating_your_deliberate_victim_cannot_buy_rehabilitation():
    g = field()
    hostile(g)
    casualty = g.soldier_at[14, 10]
    g.player.suppression = 30
    for _ in range(5):
        g.duty.good_deed(g, 'rescue', casualty)
    assert g.renegade and conduct.state(g)['valor'] == 0


def test_old_unsubstantiated_accusations_are_repaired_once_on_load(tmp_path):
    g = field()
    del g.duty.conduct
    g.duty.ff_incidents, g.duty.murders = 5, 3
    g.duty.rep = -150
    g.renegade = True
    g.duty.pow_shot = 2
    g.duty.strikes = 3
    saved = str(tmp_path / 'legacy.pkl')
    g.save(saved)
    g = Game.load(saved)
    assert not g.renegade and g.duty.rep == 0 and g.duty.murders == 0
    assert g.duty.pow_shot == 2 and g.duty.strikes == 3
    assert g.duty.conduct['legacy_unclassified']['deaths'] == 3
    hostile(g)
    g.save(saved)
    g = Game.load(saved)
    assert g.renegade and g.duty.ff_incidents == 2
