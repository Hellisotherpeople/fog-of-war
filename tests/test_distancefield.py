"""Demand-driven navigation must have exactly the existing full-map distances."""
import pickle
from unittest.mock import patch
import numpy as np
import pytest
from fow import distancefield as D
from fow.brain import dijkstra


def test_lazy_distances_equal_full_dijkstra_including_detours_and_disconnected_ground():
    if not D._compile():
        pytest.skip('optional numba accelerator unavailable')
    for seed in range(6):
        rng = np.random.default_rng(seed)
        cost = rng.integers(1,30,(75,65),dtype=np.int32)
        cost[rng.random(cost.shape)<.18] = 0
        # A long wall with a distant opening defeats cropped/local-only searches.
        cost[35,:-4] = 0
        cost[55,:] = 0
        goals = np.zeros(cost.shape,bool)
        goals[3,3] = goals[5,30] = True
        expected = dijkstra(goals,cost)
        field = D.DistanceField(goals,cost)
        for x,y in [(4,4),(38,3),(20,40),(70,50),(0,0)]+[tuple(pt) for pt in rng.integers(0,60,(30,2))]:
            assert field[x,y] == expected[x,y]
        assert np.array_equal(field.materialize(),expected)


def test_query_does_not_solve_unused_ground_and_save_can_load_without_numba():
    if not D._compile():
        pytest.skip('optional numba accelerator unavailable')
    cost = np.ones((400,400),np.int32)
    goals = np.zeros(cost.shape,bool)
    goals[200,200] = True
    field = D.DistanceField(goals,cost)
    assert field[203,204] == 11
    assert np.count_nonzero(field.settled) < 400
    saved = pickle.dumps(field)
    restored = pickle.loads(saved)
    assert restored[0,0] == 600
    with patch.object(D,'_kernel',False):
        portable = pickle.loads(saved)
        assert portable[0,0] == 600 and portable[203,204] == 11


def test_vehicle_routes_expire_without_changing_distances_or_discarding_used_routes():
    from test_command_realism import scene
    g = scene()
    b = g.brains[g.player.side]
    b.update(force=True)
    old = b.vehicle_map(20,20,3,False,exact=True)
    kept = b.vehicle_map(25,20,3,False,exact=True)
    assert old is not None and kept is not None
    g.turn += b.MAP_TTL+1
    assert b.vehicle_map(25,20,3,False,exact=True) is kept
    b.update(force=True)
    assert not any(v is old for v in b.veh_maps.values())
    assert b.vehicle_map(25,20,3,False,exact=True) is kept
    fresh = b.vehicle_map(20,20,3,False,exact=True)
    assert np.array_equal(fresh,old)
