"""Physical kit, fallible identity checks, search leads and material ballistics.

Run directly: python tests/test_identity_loot_ballistics.py
"""
from __future__ import annotations
import math
import pickle
from unittest.mock import patch
from test_smoke import FakeApp, Game
from fow import tiles as T, identity as ID
from fow.entities import Actor, Item, make_corpse
from fow.inventory import Inventory, container_grids
from fow.gamemap import GameMap
from fow.play import PlayState, Key
import tcod
import tcod.event as E


def scene():
    g = Game('bocage44', 'uk', role='agent', seed=3,
             setup={'battlefield': 'standard', 'scenario': 'agent'})
    g.map = GameMap(48, 48, 9)
    g.map.t[:] = T.ID['grass']
    g.map.refresh()
    g.map.visible[:] = True
    p = g.player
    p.x, p.y = 12, 12
    p.vehicle = None
    p.ai.update(disguise=True, suspicion=0)
    p.invent = Inventory()
    p.invent.slots['body'] = Item('civvies')
    p.add_item(Item('forged_papers'))
    p.weapon = None
    p.fired_turn = -99999
    guard = Actor('germany', 'intel', 4, 'Guard', 14, 12)
    guard.skills = dict(observation=8., languages=8.)
    guard.ai['papers_diligence'] = 0.
    g.actors = [p, guard]
    g.squads = []
    p.squad = None
    g.soldier_at = {a.pos: a for a in g.actors}
    g.vehicles = []
    g.vehicle_at = {}
    g._arr_turn = -1
    g.map.items.clear()
    g.identity_check = None
    for it in ID.documents(g):
        it.data.update(identity=dict(ID.legend(g)), paper_quality=1., stamp='clear district seal')
    app = FakeApp()
    app.settings.update(autosave=False, fast_quiet=False)
    ps = PlayState(app, g)
    app.states = [ps]
    return g, ps, guard


def answer_story(g, story=None):
    story = story or ID.legend(g)
    for _ in range(10):
        c = g.identity_check
        if not c or c['stage'] != 'questions':
            return
        field = c['questions'][c['step']]
        ID.answer(g, story[field])


def test_good_story_passes_and_papers_do_not_reroll():
    g, ps, guard = scene()
    docs = pickle.dumps([i.data for i in ID.documents(g)])
    assert ID.begin(g, guard)
    answer_story(g)
    assert g.identity_check is None and g.player.ai['disguise']
    assert guard.ai['identities'][ID.legend(g)['name']]['purpose'] == ID.legend(g)['purpose']
    assert pickle.dumps([i.data for i in ID.documents(g)]) == docs


def test_consistency_and_sentry_skill_change_outcome():
    g, ps, guard = scene()
    doc = ID.documents(g)[0]
    doc.data['identity']['origin'] = 'the wrong district'
    guard.role = 'rifleman'
    guard.skills.update(observation=0., languages=0.)
    ID.begin(g, guard)
    answer_story(g)
    assert g.identity_check is None  # inattentive sentry only checks the name
    guard.role = 'intel'
    guard.skills.update(observation=8., languages=8.)
    ID.begin(g, guard)
    while g.identity_check['step'] < len(g.identity_check['questions']) - 1:
        field = g.identity_check['questions'][g.identity_check['step']]
        ID.answer(g, ID.legend(g)[field])
    ID.answer(g, 'a completely different errand')
    assert g.identity_check['stage'] == 'explain'
    assert any('changed your answer' in s for s in g.identity_check['evidence'])
    assert any('origin' in s for s in g.identity_check['evidence'])
    ID.explain(g, 'clerical')
    assert g.identity_check['stage'] == 'search'  # an excuse does not erase multiple contradictions


def test_security_records_persist_and_esc_does_not_reset_check():
    g, ps, guard = scene()
    ID.begin(g, guard)
    ID.answer(g, ID.legend(g)['name'])
    ID.present(ps)
    score = g.identity_check['step']
    ps.on_key(Key(sym=E.KeySym.ESCAPE))
    assert ps.wants_tick()
    ps.tick()
    assert ps.popups and g.identity_check['step'] == score
    ps.popups.clear()
    answer_story(g)
    g = pickle.loads(pickle.dumps(g))
    guard = next(a for a in g.actors if a.role == 'intel')
    ID.begin(g, guard)
    story = dict(ID.legend(g), origin='an unrecorded district')
    answer_story(g, story)
    assert any('earlier checkpoint' in s for s in g.identity_check['evidence'])


def test_papers_check_reaches_ui_and_charges_time():
    g, ps, guard = scene()
    g.player.ai['suspicion'] = 100
    guard.z = 1
    g._disguise_tick()
    assert not g.identity_check
    guard.z = 0
    g._disguise_tick()
    assert g.identity_check
    ps.tick()
    assert ps.popups[-1].title == 'Papers check'
    field = g.identity_check['questions'][0]
    pop = ps.popups[-1]
    pop.sel = next(i for i, o in enumerate(pop.options) if o[1] == ('answer', ID.legend(g)[field]))
    moves = g.player.moves
    with patch.object(g, 'player_done') as advance:
        ps.popup_select()
        assert advance.called and g.player.moves == moves - 300
    assert g.identity_check['step'] == 1
    con = tcod.console.Console(160, 80, order='F')
    from fow.render import draw_popup
    draw_popup(con, ps.popups[-1])
    for contraband in (False, True):
        g, ps, guard = scene()
        if contraband:
            g.player.invent.hands = Item('welrod')
        ID.begin(g, guard)
        g.identity_check['stage'] = 'search'
        ID.present(ps)
        pop = ps.popups[-1]
        pop.sel = next(i for i, o in enumerate(pop.options) if o[1] == ('search', None))
        moves = g.player.moves
        with patch.object(g, 'player_done'):
            ps.popup_select()
        assert g.player.moves == moves - 800 and not g.identity_check
        assert len(ps.popups) == int(contraband)
        if contraband:
            assert ps.popups[-1].title == "'Hands up!'" and not g.player.ai['disguise']


def test_counterintelligence_interview_needs_evidence_and_physical_search():
    from fow.counterintel import interview
    g, ps, suspect = scene()
    p = g.player
    p.role = 'intel'
    p.skills.update(observation=9., languages=9.)
    suspect.ai.update(civilian=True, covert=True, occupation='traveller', cover_quality=.4)
    suspect.invent = Inventory()
    assert suspect.add_item(Item('time_pencil'))
    def choose(value):
        pop = ps.popups[-1]
        i = next(i for i, o in enumerate(pop.options) if o[1] == value)
        assert pop.options[i][3]
        pop.sel = i
        with patch.object(g, 'player_done'):
            ps.popup_select()
    interview(ps, suspect)
    assert not next(o[3] for o in ps.popups[-1].options if o[1] == 'detain')
    choose('route')
    choose('repeat')
    choose('search')
    assert len(suspect.ai['interview']['evidence']) == 2
    choose('detain')
    assert suspect.state == 'surrendered' and not suspect.ai.get('covert')
    innocent = Actor('germany', 'civilian', 0, 'Resident', 13, 12)
    innocent.ai.update(civilian=True, occupation='labourer')
    ps.popups.clear()
    interview(ps, innocent)
    for option in ('trade', 'route', 'repeat', 'papers', 'search'):
        choose(option)
    assert not innocent.ai['interview']['evidence']


def test_pending_check_save_and_missing_set_cannot_transmit():
    from fow import agents
    g, ps, guard = scene()
    ID.begin(g, guard)
    ID.answer(g, ID.legend(g)['name'])
    loaded = pickle.loads(pickle.dumps(g))
    assert loaded.identity_check == g.identity_check
    agents.radio_choice(ps, 'report')
    assert g.agent.get('tx') is None
    g.player.invent.hands = Item('paraset')
    g.player.invent.hands.condition = .5
    agents.radio_choice(ps, 'report')
    assert g.agent['tx']['left'] == 2 * agents.TX_TIME['report']
    g.player.invent.hands.condition = 0
    agents.tick(g)
    assert g.agent['tx'] is None


def test_search_leads_are_areas_not_hidden_actor_trackers():
    from fow.leads import initialize
    from fow.scenarios import mission_point
    from fow import orders
    from fow.ai import Order, Squad
    g, ps, guard = scene()
    airman = Actor('uk', 'air_gunner', 0, 'Airman', 33, 29)
    sq = Squad(g.player.side, 'uk', 'rifle', 'evader')
    sq.order = Order('hold', target=airman.pos)
    airman.squad = sq
    g.actors.append(airman)
    g.mission = dict(kind='agent', task='rescue_airman', stage='find', text='Find the missing airman.', airman=airman.id,
                     home='S', _start_sector=g.sector)
    initialize(g, g.mission)
    point = mission_point(g)
    assert point and 'search within' in point[2]
    assert max(abs(point[0] - airman.x), abs(point[1] - airman.y)) <= 16
    airman.x += 10
    assert mission_point(g) == point
    assert 'last reported area' in orders.book(g)[0]['text']
    g.mission['stage'] = 'out'
    assert 'friendly lines' in mission_point(g)[2]
    g.mission = dict(kind='agent', task='photograph', stage='photo', text='Photograph installations.', shot=[])
    g.map.gen_positions = [dict(kind='hq', side=guard.side, rect=(25, 25, 8, 8), x=29, y=29)]
    assert mission_point(g)[:2] == (29, 29)
    g.mission['shot'] = ['hq@29,29']
    assert mission_point(g) is None


def corpse_scene(g):
    a = Actor('germany', 'rifleman', 0, 'Dead soldier', *g.player.pos)
    a.invent.slots['primary'] = Item('mp40')
    from fow.data.items import RIGS, PACKS
    a.invent.slots['rig'] = Item(RIGS['germany']['smg'])
    a.invent.slots['pack'] = Item(PACKS['germany'])
    mag = Item(Item('mp40').t.magtype)
    assert a.add_item(mag, 'rig')
    secret = Item('forged_papers')
    assert a.add_item(secret, 'pack')
    body = make_corpse(a)
    g.map.add_item(*a.pos, body)
    return body, mag, secret


def test_v_lists_visible_body_kit_with_compatible_colours_and_hides_closed_pack():
    from fow.nearby import gather, AMMO_PRIMARY
    g, ps, guard = scene()
    body, mag, secret = corpse_scene(g)
    g.player.invent.slots['primary'] = Item('mp40')
    entries = [e for e in gather(g)['Items'] if e.get('body') is body]
    assert any(e['color'] == AMMO_PRIMARY and e['label'].startswith('[P]') for e in entries)
    assert not any(secret.name in e['label'] for e in entries)
    assert any('MP 40' in e['label'] for e in entries)
    body.data['searched'] = True
    assert any(secret.name in e['label'] for e in gather(g)['Items'] if e.get('body') is body)
    g.map.visible[g.player.pos] = False
    assert not gather(g)['Items']


def test_body_search_cost_hidden_grids_and_inventory_keys_visible():
    from fow.constants import SCREEN_W, SCREEN_H
    from fow.invui import HELP_LINES
    g, ps, guard = scene()
    body, mag, secret = corpse_scene(g)
    ps.cmd_inventory(focus_body=body)
    inv = ps.inv_screen
    pane = inv.loot
    assert all(loc == 'rig' for _, gs in inv._kit_blocks(pane) for _, loc in gs)
    with patch.object(g, 'player_done') as advance:
        moves = g.player.moves
        inv.search_body(pane)
        assert advance.called and g.player.moves == moves - 600
    assert body.data['searched']
    assert any(loc == 'pack' for _, gs in inv._kit_blocks(pane) for _, loc in gs)
    from fow import icons
    with patch.object(icons, 'on', return_value=False):
        con = tcod.console.Console(SCREEN_W, SCREEN_H, order='F')
        inv.render(con)
        text = '\n'.join(''.join(chr(c) for c in con.ch[:, y]) for y in range(SCREEN_H))
        assert all(line in text for line in HELP_LINES)


def test_logical_stores_and_no_random_kit_on_quiet_empty_ground():
    from fow.loot import scatter
    g, ps, guard = scene()
    g.map.buildings = []
    g.map.gen_positions = []
    with patch.object(g.strategic, 'is_front', return_value=False), patch.object(g.strategic, 'neighbors', return_value=[]):
        g.sector.last_fight = -1
        assert scatter(g) == 0 and not g.map.items
        g.map.gen_positions = [dict(kind='depot', side=g.player.side, x=24, y=24, rect=(15, 15, 18, 18))]
        count = scatter(g)
        assert count >= 75 and len(g.map.items) <= 12
        assert all(15 < x < 32 and 15 < y < 32 for x, y in g.map.items)
        assert any(it.t.kind == 'gun' for pile in g.map.items.values() for it in pile)
        assert any(T.DEFS[int(g.map.t[xy])].key == 'arms_rack' for xy in g.map.items)


def test_blast_scatter_damage_shielding_and_bag_spill_conserve_items():
    from fow.equipment import blast, damage
    g, ps, guard = scene()
    g.actors = []
    rifle = Item('mp40')
    g.map.add_item(22, 20, rifle)
    g.map.t[24, :] = T.ID['wall_stone']
    protected = Item('mp40')
    g.map.add_item(25, 20, protected)
    g.map.refresh()
    blast(g, 20, 20, 280, 6)
    assert 0 < rifle.condition < 1 and protected.condition == 1
    assert sum(rifle is i for pile in g.map.items.values() for i in pile) == 1
    assert not any(rifle is i for i in g.map.items_at(22, 20))
    bag = Item('suitcase')
    child = Item('compass')
    grid = container_grids(bag)[0]
    grid.place(child, *grid.find_spot(child))
    assert damage(g, bag, 140, 10, 10)
    assert bag.condition == 0 and not grid.items
    assert child in g.map.items_at(10, 10) and 0 < child.condition < 1
    loaded = pickle.loads(pickle.dumps(bag))
    assert loaded.condition == 0 and container_grids(loaded)[0].find_spot(Item('ration')) is None


def test_damaged_equipment_degrades_functions_and_rounds_keep_condition():
    from fow.combat import dispersion, fire_weapon
    from fow.ammo import fill_magazine, unload
    g, ps, guard = scene()
    gun = Item('mp40')
    before = dispersion(g, g.player, gun, 25, 25)
    gun.condition = .5
    assert dispersion(g, g.player, gun, 25, 25) > before
    gun.condition = 0
    shots = g.player.stats['shots']
    fire_weapon(g, g.player, gun, 25, 25)
    assert g.player.stats['shots'] == shots
    p = g.player
    p.invent = Inventory()
    p.invent.slots['pack'] = Item('suitcase')
    ammo = Item('ammo_9mm', 20)
    ammo.condition = .4
    assert p.add_item(ammo)
    mag = Item(Item('mp40').t.magtype, full=False)
    assert fill_magazine(p, mag) == 20
    assert mag.data['rounds_condition'] == .4
    gun.mag_item, gun.loaded = mag, mag.loaded
    unload(p, gun)
    assert any(i is mag and i.data['rounds_condition'] == .4 for i in p.inv)
    radio = Item('paraset')
    radio.condition = 0
    p.invent.hands = radio
    assert not p.has_tool('wireless')
    from fow.actions import unjam
    gun.condition = 1
    gun.jammed = True
    broken = Item(gun.t.magtype)
    broken.condition = 0
    gun.mag_item, gun.loaded = broken, broken.loaded
    assert mag.loaded < gun.loaded
    p.invent.slots['primary'] = gun
    p.weapon = gun
    assert unjam(g, p) > 0
    assert gun.mag_item is mag and not gun.jammed
    # Both timed and impact fuses lose reliability; throwing a dud again cannot reroll it.
    with patch.object(g.rng, 'random', return_value=.5), patch('fow.game.explode') as detonate:
        for tid in ('gammon', 'mills'):
            grenade = Item(tid)
            grenade.condition = .2
            g.land_explosive(grenade, 20, 20, p)
            for _ in range(8):
                g._tick_explosives()
            assert grenade.data.get('dud') and grenade in g.map.items_at(20, 20)
            assert not detonate.called
        g.map.remove_item(20, 20, grenade)
        grenade.condition = 1
        g.land_explosive(grenade, 20, 20, p)
        for _ in range(8):
            g._tick_explosives()
        assert not detonate.called
        g.land_explosive(Item('gammon'), 20, 20, p)
        assert detonate.called


def test_material_angle_energy_and_actual_ricochet_path():
    from fow.ballistics import impact
    from fow.combat import trace_projectile
    glass, wood, stone = (T.DEFS[T.ID[k]] for k in ('window', 'wall_wood', 'wall_stone'))
    assert impact(glass, 50, 3)[0] == 'penetrate'
    assert impact(wood, 70, 3)[0] == 'penetrate'
    assert impact(wood, 20, 1)[0] == 'stop'
    assert impact(stone, 70, 3)[0] == 'stop'
    direction = (.3, math.sqrt(1 - .3 ** 2))
    result, retain, outgoing = impact(stone, 70, 3, direction, (1., 0.), roll=0.)
    assert result == 'ricochet' and 0 < retain < 1 and outgoing[0] < 0 < outgoing[1]
    assert impact(wood, 70, 3, direction, (1., 0.), roll=0.)[0] == 'stop'
    assert impact(T.DEFS[T.ID['sandbags']], 70, 3, direction, (1., 0.), roll=0.)[0] == 'stop'
    g, ps, guard = scene()
    g.actors, g.soldier_at = [], {}
    g.map.t[20, :] = T.ID['wall_stone']
    g.map.refresh()
    with patch.object(g.rng, 'random', return_value=0.), patch.object(g, 'effect_tracer') as tracer, \
            patch.object(g, 'emit_sound') as sound:
        trace_projectile(g, 17, 8, math.atan2(direction[1], direction[0]), 35, 70, 3, 'bullet', None, None, 'test round')
        assert tracer.call_count >= 2
        assert any(call.args[3] == 'ricochet' for call in sound.call_args_list)
        reflected = tracer.call_args_list[0].args
        assert reflected[2] < reflected[0]  # reflected path heads back away from the wall


if __name__ == '__main__':
    import traceback
    failures = 0
    tests = [(name, fn) for name, fn in list(globals().items()) if name.startswith('test_') and callable(fn)]
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
