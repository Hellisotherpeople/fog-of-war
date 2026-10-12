"""Native acceleration must preserve routes, visibility, smoke, saves and failure recovery."""
import pickle
import os

import numpy as np
import pytest
import tcod

N = pytest.importorskip('_fow_native')
from fow.constants import BIG


@pytest.fixture(autouse=True)
def native_enabled(monkeypatch):
    from fow import native
    monkeypatch.setattr(native, 'core', N)


def reference_routes(dist, cost, card=2, diag=3):
    out = dist.copy()
    return tcod.path.dijkstra2d(out, cost, card, diag, out=out)


@pytest.mark.parametrize('order', ['C', 'F', 'strided'])
@pytest.mark.parametrize('seed', range(4))
def test_native_routes_match_tcod(order, seed):
    rng = np.random.default_rng(seed)
    cost = rng.integers(0, 25, (60, 50), dtype=np.int32)
    cost[30, :-2] = 0
    cost[45, :] = 0
    dist = np.full(cost.shape, BIG, np.int32)
    # Multiple seeds, including negative flee values and a goal inside blocked ground.
    dist[2, 2], dist[4, 8], dist[45, 5] = -157, 17, 0
    cost[45, 5] = 0
    if order == 'strided':
        cost, dist = cost[::-1, ::-1], dist[::-1, ::-1]
    else:
        cost, dist = np.array(cost, order=order), np.array(dist, order=order)
    expected = reference_routes(dist, cost)
    N.dijkstra(dist, cost, 2, 3)
    np.testing.assert_array_equal(dist, expected)


def test_native_routes_extreme_costs_empty_and_no_goals():
    for cost in (np.empty((0, 2), np.int32), np.full((8, 9), 500000, np.int32),
                 np.ones((8, 9), np.int32)):
        dist = np.full(cost.shape, BIG, np.int32)
        N.dijkstra(dist, cost, 2, 3)
        assert (dist == BIG).all()
        if dist.size:
            dist[0, 0] = -500
            expected = reference_routes(dist, cost)
            N.dijkstra(dist, cost, 2, 3)
            np.testing.assert_array_equal(dist, expected)


def test_route_workspaces_are_private_to_calling_threads():
    from concurrent.futures import ThreadPoolExecutor
    jobs = []
    for seed in range(12):
        rng = np.random.default_rng(seed)
        cost = rng.integers(0, 5+seed, (63, 59), dtype=np.int32)
        dist = rng.integers(-100, 1000, cost.shape, dtype=np.int32)
        jobs.append((dist, cost, reference_routes(dist, cost)))
    def run(job):
        dist, cost, expected = job
        N.dijkstra(dist, cost, 2, 3)
        np.testing.assert_array_equal(dist, expected)
    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(run, jobs))


def test_native_lazy_detours_and_portable_save(monkeypatch):
    from fow import distancefield as D, native
    cost = np.ones((400, 400), np.int32)
    cost[220, :-2] = 0
    cost[380, :] = 0
    goals = np.zeros(cost.shape, bool)
    goals[200, 200] = goals[198, 210] = True
    dist = np.where(goals, 0, BIG).astype(np.int32)
    expected = reference_routes(dist, cost)
    field = D.RustDistanceField(goals, cost)
    assert field[201, 201] == expected[201, 201]
    assert np.count_nonzero(field.settled) < 200
    saved = pickle.dumps(field)
    assert pickle.loads(saved)[230, 200] == expected[230, 200]
    np.testing.assert_array_equal(field.materialize(), expected)
    # The exact same save works on a machine without Rust OR Numba.
    monkeypatch.setattr(native, 'core', None)
    monkeypatch.setattr(D, '_kernel', False)
    monkeypatch.setattr(D.fastpath, '_fast', False)
    np.testing.assert_array_equal(pickle.loads(saved), expected)


@pytest.mark.parametrize('maximum', [1, 255, 5000])
def test_lazy_cost_widths_and_strided_inputs(maximum):
    rng = np.random.default_rng(71)
    cost = rng.integers(0, maximum+1, (24, 21), dtype=np.uint16)[::-1, ::-1]
    goals = np.zeros(cost.shape, bool)
    goals[1, 1] = goals[-2, -2] = True
    expected = reference_routes(np.where(goals, 0, BIG).astype(np.int32), cost.astype(np.int32))
    field = N.DistanceField(goals, cost)
    np.testing.assert_array_equal(field.materialize(), expected)


def test_native_sight_matches_existing_compiled_kernel():
    from fow import fastpath as F
    F._compile_lines()
    if not F._lines:
        pytest.skip('Numba reference not installed')
    rng = np.random.default_rng(9)
    for order in ('C', 'F'):
        see = np.array(rng.random((80, 70)) > .08, order=order)
        high = np.array(see | (rng.random(see.shape) > .5), order=order)
        elev = np.array(rng.random(see.shape)*15, dtype=np.float32, order=order)
        for rel in (False, True):
            for ax, ay, h0, vh in ((0, 0, 1.6, False), (79, 69, .4, False), (30, 45, 4.8, True)):
                tx = rng.integers(0, 80, 400, dtype=np.int64)
                ty = rng.integers(0, 70, 400, dtype=np.int64)
                h1 = rng.choice([.45, 1.1, 1.7, 2.4, 5.6], size=400)
                thigh = rng.random(400) > .8
                args = (see, high, elev, rel, ax, ay, h0, vh, tx, ty, h1, thigh)
                expected = np.zeros(len(tx), bool)
                F._lines(*args, expected)
                np.testing.assert_array_equal(N.sight_lines(*args), expected)


@pytest.mark.parametrize('shape', [(1, 1), (7, 9), (600, 500)])
@pytest.mark.parametrize('rain', [False, True])
def test_parallel_smoke_is_bit_exact(shape, rain):
    rng = np.random.default_rng(19)
    for wx, wy, drift in ((0, 0, False), (-2, 1, True), (1, -3, True)):
        sm = (rng.random(shape)*8).astype(np.float32)
        for _ in range(20):
            nb = np.zeros_like(sm)
            nb[1:, :] += sm[:-1, :]
            nb[:-1, :] += sm[1:, :]
            nb[:, 1:] += sm[:, :-1]
            nb[:, :-1] += sm[:, 1:]
            expected = sm*.55 + nb*.1
            if drift:
                expected = np.roll(np.roll(expected, wx, axis=0), wy, axis=1)*.97
            expected *= .9 if rain else .96
            expected[expected < .02] = 0
            actual = N.diffuse(sm, wx, wy, drift, rain)
            np.testing.assert_array_equal(actual.view(np.uint32), expected.view(np.uint32))
            sm = actual


@pytest.fixture(scope='module')
def gpu_device():
    try:
        return N.GpuRoutes()
    except (AttributeError, RuntimeError) as exc:
        if os.environ.get('FOW_REQUIRE_GPU'):
            pytest.fail(str(exc))
        pytest.skip(f'Physical compute GPU unavailable: {exc}')


@pytest.mark.parametrize('seed', range(4))
@pytest.mark.parametrize('iterations', [1, 4, 16])
def test_gpu_routes_exact_even_when_cpu_must_complete(gpu_device, seed, iterations):
    rng = np.random.default_rng(seed)
    cost = rng.integers(0, 18, (79, 67), dtype=np.int32)
    cost[40, :-1] = 0
    cost[60, :] = 0
    dist = np.full(cost.shape, BIG, np.int32)
    dist[3, 3] = -300
    dist[5, 5] = 0
    np.testing.assert_array_equal(gpu_device.solve(dist, cost, 2, 3, iterations), reference_routes(dist, cost))


def test_gpu_completes_dense_field_and_reallocates(gpu_device):
    for shape in ((600, 500), (15, 20), (500, 600)):
        cost = np.ones(shape, np.int32)
        dist = np.zeros(shape, np.int32)
        dist[::2, ::2] = BIG
        actual = gpu_device.solve(dist, cost, 2, 3, 4)
        assert gpu_device.completed_on_gpu
        np.testing.assert_array_equal(actual, reference_routes(dist, cost))


def test_gpu_device_failure_uses_cpu(monkeypatch):
    from fow import native
    class BrokenDevice:
        def solve(self, *args):
            raise RuntimeError('injected device loss')
    monkeypatch.setenv('FOW_GPU', 'on')
    monkeypatch.setattr(native, '_gpu', BrokenDevice())
    monkeypatch.setattr(native, '_gpu_failed', False)
    monkeypatch.setattr(native, '_reason', None)
    cost = np.ones((15, 20), np.int32)
    dist = np.full(cost.shape, BIG, np.int32)
    dist[0, 0] = 0
    expected = reference_routes(dist, cost)
    assert native.dijkstra(dist, cost, 2, 3)
    assert native._gpu_failed
    np.testing.assert_array_equal(dist, expected)


def test_bad_gpu_output_is_rejected_during_auto_selection(monkeypatch):
    from fow import native
    class IncorrectDevice:
        def solve(self, dist, *args):
            return np.full_like(dist, 47)
    monkeypatch.setenv('FOW_GPU', 'auto')
    monkeypatch.setattr(native, '_gpu', IncorrectDevice())
    monkeypatch.setattr(native, '_gpu_failed', False)
    monkeypatch.setattr(native, '_choices', {})
    monkeypatch.setattr(native, '_reason', None)
    cost = np.ones((600, 500), np.int32)
    dist = np.zeros(cost.shape, np.int32)
    dist[::2, ::2] = BIG
    expected = reference_routes(dist, cost)
    assert native.dijkstra(dist, cost, 2, 3)
    assert native._gpu_failed and 'parity' in native._reason
    np.testing.assert_array_equal(dist, expected)


def test_unknown_adapter_is_an_error_not_a_native_panic(monkeypatch):
    if not hasattr(N, 'GpuRoutes'):
        pytest.skip('CPU-only build')
    monkeypatch.setenv('WGPU_ADAPTER_NAME', 'fow_nonexistent_physical_adapter_1234')
    with pytest.raises(RuntimeError, match='no GPU adapter'):
        N.GpuRoutes()


def test_long_frontier_does_not_initialize_gpu(monkeypatch):
    from fow import native
    def unexpected_gpu():
        pytest.fail('long contiguous frontier should remain on CPU without allocating a GPU')
    monkeypatch.setenv('FOW_GPU', 'auto')
    monkeypatch.setattr(native, 'gpu', unexpected_gpu)
    monkeypatch.setattr(native, '_choices', {})
    monkeypatch.setattr(native, '_measurements', {})
    cost = np.ones((600, 500), np.int32)
    dist = np.zeros(cost.shape, np.int32)
    dist[200:400, 200:400] = BIG
    expected = reference_routes(dist, cost)
    assert native.dijkstra(dist, cost, 2, 3)
    np.testing.assert_array_equal(dist, expected)
