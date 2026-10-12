"""Field careers, ordinary-action objective travel, rescue and local voice delivery."""
from unittest.mock import patch
import pickle
import numpy as np
import pytest

from test_command_realism import scene, soldier, radio, unradio
from test_smoke import FakeApp
from fow import career, recognition, contacts, orders, objective_travel, prosody
from fow.data import rank_profiles as ranks
from fow.play import PlayState


def test_rank_branches_keep_identity_authority_and_save_choices():
    g = scene()
    p = g.player
    p.rank = 4
    radio(p)
    recognition.state(g)['credited'] = 100
    assert career.consider(g)
    assert career.accept(g, 'warrant:junior')
    assert p.rank_full == 'Warrant Officer (Junior Grade)' and p.command_grade < 2
    assert [r.key for r in career.options(g)] == ['warrant:chief', 'line:8']
    loaded = pickle.loads(pickle.dumps(g))
    assert loaded.player.rank_full == p.rank_full
    assert career.consider(loaded)
    assert career.accept(loaded, 'warrant:chief')
    assert all(r.branch == 'line' for r in career.options(loaded))
    assert 'Reichsmarschall' not in {r.title for r in ranks.catalog('germany', 'army')}
    assert {r.title for r in ranks.available('uk', 'army', 1944) if r.branch == 'warrant'} == {
        'Warrant Officer Class I', 'Warrant Officer Class II'}
    assert {'Jemadar','Subedar','Subedar Major'} <= {r.title for r in ranks.catalog('india')}
    assert 'Flight Officer' not in {r.title for r in ranks.available('usa','air',1941)}
    assert len([r for r in ranks.catalog('usa','navy') if r.branch.startswith('warrant')]) == 24


def test_runner_orders_require_real_arrival():
    g = scene()
    p = g.player
    p.rank = 2
    unradio(p)
    runner = soldier(g, 18, 10, role='rifleman', rank=0)
    unradio(runner)
    recognition.state(g)['credited'] = 50
    with patch('fow.dispatches.courier', return_value=runner):
        assert not career.consider(g)
    assert not career.accept(g, 'line:3')
    start = runner.pos
    for _ in range(30):
        assert career.runner_act(g, runner, []) > 0
        g.turn += 1
        if recognition.state(g)['pending'].get('delivered') is not None:
            break
    assert runner.pos != start
    assert max(abs(runner.x-p.x),abs(runner.y-p.y)) <= 2
    assert career.accept(g, 'line:3')


def test_promotion_aboard_preserves_crew_position_without_assigning_an_army_billet():
    from fow.game import Game
    g = Game('omaha44','usa',seed=7,setup={'service':'navy','scenario':'sea:carrier','rank':2})
    assert g.domain == 'aboard'
    radio(g.player)
    recognition.state(g)['credited'] = 50
    assert career.consider(g)
    role, billet = g.player.role, g.command.billet
    assert not career.accept(g,'line:3','command')
    assert career.accept(g,'line:3','keep')
    assert g.player.role == role and g.command.billet is billet


def test_promotion_screen_pauses_objective_travel_immediately():
    g = scene()
    g.player.rank = 2
    radio(g.player)
    recognition.state(g)['credited'] = 100
    ps = PlayState(FakeApp(), g)
    ps.objective_auto = True
    before = g.turn
    assert career.consider(g) and career.present(ps)
    assert ps.popups[-1].title == 'Field promotion — orders received'
    assert not ps.objective_auto and g.turn == before and g.player.rank == 2


def test_objective_travel_uses_normal_world_turns_and_stops_for_contact():
    g = scene()
    p = g.player
    staff = soldier(g, 22, 10, role='quartermaster')
    staff.squad.kind = 'staff'
    staff.ai['post'] = staff.pos
    g.map.explored[:] = True
    g.sector.control = p.side
    g.support.queue.clear()
    g.shells.clear()
    app = FakeApp()
    app.settings.update(fast_quiet=False, autosave=False)
    ps = PlayState(app, g)
    app.states = [ps]
    g.player_fov()
    with patch('fow.senses.player_can_see_actor', return_value=True):
        assert orders.focus(g, contacts.request(g, 'supply'))
        before = g.turn, p.pos, p.stamina
        with patch.object(g, 'world_turn', wraps=g.world_turn) as turns, patch.object(g, '_skip_time') as skip:
            objective_travel.start(ps)
            for _ in range(5):
                ps.anim = ps.anim_next = 0
                ps.tick()
            assert turns.called and not skip.called
        assert g.turn > before[0] and p.pos != before[1]
        stopped = p.pos
        with patch.object(g, 'seen_enemies', return_value=[object()]):
            ps.anim = ps.anim_next = 0
            ps.tick()
        assert not ps.objective_auto and p.pos == stopped


def test_autotravel_does_not_execute_fire_orders():
    g = scene()
    ps = PlayState(FakeApp(),g)
    ps.objective_auto = True
    ps.mark_interrupt()
    with patch('fow.objective_travel.active', return_value={'key':'fire'}), patch.object(ps,'cmd_do_order') as action:
        objective_travel.step(ps)
    assert not action.called and not ps.objective_auto


def test_medic_can_reach_casualty_beyond_old_search_range_and_uses_kit():
    from test_squadcare import scene as medical_scene, kit, hurt, index
    from fow.entities import Actor
    from fow import ai
    g, sq, lead, helper = medical_scene()
    p = g.player
    p.x,p.y = 42,12
    doctor = Actor('usa','medic',0,'Medic Smith',8,12)
    kit(doctor,dressings=2)
    doctor.skills['first_aid'] = 7
    hurt(p,3)
    g.actors.append(doctor)
    index(g)
    assert ai.medic_act(g,doctor,[]) > 0 and doctor.ai['patient'] == p.id
    # Actual path steps, not arrival teleportation.
    for _ in range(70):
        ai.medic_act(g,doctor,[])
        g.turn += 1
        if p.body.bleed_rate() == 0:
            break
    assert p.body.bleed_rate() == 0
    assert sum(i.count for i in doctor.inv if i.tid == 'bandage') == 1
    assert max(abs(doctor.x-p.x),abs(doctor.y-p.y)) <= 1


@pytest.mark.parametrize('style', sorted(prosody.STYLES))
def test_prosody_is_finite_local_deterministic_and_keeps_silence(style):
    sr = 22050
    x = (.2*np.sin(np.arange(sr,dtype=np.float32)*2*np.pi*180/sr)).astype(np.float32)
    a = prosody.shape(x,style,sr,17)
    assert a.dtype == np.float32 and np.isfinite(a).all() and np.max(np.abs(a)) <= .971
    assert np.array_equal(a,prosody.shape(x,style,sr,17))
    assert not prosody.shape(np.zeros(sr,dtype=np.float32),style,sr).any()
    assert len(prosody.shape(np.zeros(1,dtype=np.float32),style,sr)) == 1
    if style != 'talk':
        talk = prosody.shape(x,'talk',sr,17)
        assert a.shape != talk.shape or not np.allclose(a,talk)
