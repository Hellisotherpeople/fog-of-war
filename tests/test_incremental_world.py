"""Exact cache invalidation and zero-copy terrain shifts preserve a changing world."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from fow import senses, streaming
from fow.gamemap import GameMap
from fow.terrain_window import TerrainWindow


def test_sight_cache_survives_unrelated_damage_but_invalidates_crossed_blocks():
    m=GameMap(160,160)
    g=SimpleNamespace(map=m)
    with patch('fow.senses._line_clear',wraps=senses._line_clear) as trace:
        assert senses.los_clear(g,10,10,25,10)
        m.set(120,120,'wall_brick',refresh=True)
        assert senses.los_clear(g,10,10,25,10)
        assert trace.call_count==1
        m.set(20,10,'wall_brick',refresh=True)
        assert not senses.los_clear(g,10,10,25,10)
        assert trace.call_count==2
        m.set(20,10,'grass',refresh=True)
        assert senses.los_clear(g,10,10,25,10)
        m.smoke[20,10]=2
        m.update_see()
        assert not senses.los_clear(g,10,10,25,10)


def test_equal_route_inputs_reuse_results_and_terrain_changes_recompute():
    from test_command_realism import scene
    g=scene()
    brain=g.brains[g.player.side]
    brain.contacts.clear()
    brain.update(force=True)
    before=brain.safety
    g.turn+=brain.EVERY
    brain.update(force=True)
    assert brain.safety is before
    g.map.set(16,16,'wall_brick',refresh=True)
    g.turn+=brain.EVERY
    brain.update(force=True)
    assert brain.safety is not before
    from fow.brain import dijkstra
    expected=dijkstra((brain.cost>0)&(brain.exposure<.35),brain.exp_cost)
    np.testing.assert_array_equal(brain.safety,expected)


def test_light_cache_processes_expiry_new_fires_and_removed_sources():
    m=GameMap(80,70)
    g=SimpleNamespace(map=m,turn=10,lit=None)
    m.lights=[[20,20,5,12]]
    with patch('fow.senses.daylight',return_value=0):
        senses.compute_light(g)
        first=g.lit
        assert first[20,20] and not first[40,40]
        g.turn=11
        senses.compute_light(g)
        assert g.lit is first
        m.fire[40,40]=30
        senses.compute_light(g)
        assert g.lit[40,40]
        g.turn=13
        senses.compute_light(g)
        assert not g.lit[20,20] and g.lit[40,40] and not m.lights
        m.fire[:]=0
        senses.compute_light(g)
        assert not g.lit.any()


def fresh_window(self,old,old_origin,origin,size,layers):
    return ({name:np.zeros((size,size),dtype=getattr(old,name).dtype if hasattr(old,name) else np.float32)
             for name in layers}, [(0,0,size,size)])


def test_reused_terrain_matches_full_rebuild_through_travel_mutation_save_and_return():
    from test_streaming import world,reframe
    import pickle
    g,ps,land=world(radius=96)
    reference=deepcopy(g)
    for step,(dx,dy) in enumerate(((24,0),(24,12),(-24,-12),(110,0),(-140,36),(24,-36))):
        for game in (g,reference):
            x,y=game.player.pos
            game.map.set(x,y,'crater',refresh=True)
            game.map.smoke=game.map.smoke.copy()  # a kernel may replace this slab-backed array
            game.map.smoke[x,y]=step+.125
            game.map.fire[x,y]=step+1
            game.map.blood[x,y]=step+2
        reframe(g,g.landscape,dx,dy)
        with patch.object(TerrainWindow,'prepare',fresh_window):
            reframe(reference,reference.landscape,dx,dy)
        for name in streaming.LAYERS+('walk','see','cost_foot','cover_dir'):
            np.testing.assert_array_equal(getattr(g.map,name),getattr(reference.map,name),err_msg=f'{step} {name}')
        assert [(a.id,a.pos,a.alive) for a in g.actors]==[(a.id,a.pos,a.alive) for a in reference.actors]
        if step==2:
            assert g.landscape._terrain_window.reused>0
            g=pickle.loads(pickle.dumps(g))
            assert '_terrain_window' not in g.landscape.__dict__


def test_objective_observer_query_includes_vehicle_crew_and_live_eligibility():
    from test_command_realism import scene,soldier,radio
    from fow.entities import Vehicle
    from fow.intelligence import objective_owner
    g=scene()
    ob=g.map.objectives[0]
    ob.x,ob.y,ob.owner=40,40,g.player.side
    crew=soldier(g,40,41)
    crew.vehicle=Vehicle('m4',crew.side,crew.nation,40,41)
    radio(crew)
    assert crew in g.near_people_many([(40,40,ob.radius+6)])[0]
    with patch('fow.senses.los_clear',return_value=True):
        assert objective_owner(g,crew.side,0)==ob.owner
        crew.body.unconscious=20
        ob.owner='axis'
        assert objective_owner(g,crew.side,0)!=ob.owner
