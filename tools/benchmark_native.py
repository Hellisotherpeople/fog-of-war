#!/usr/bin/env python3
"""End-to-end native kernel benchmark, including copies, dispatch and readback.

Run without concurrent games/tests/builds. Results do not predict whole-turn gains.
"""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from fow import fastpath, native
from fow.constants import BIG


def measure(fn, repeats):
    fn()
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        result = fn()
        samples.append((time.perf_counter()-start)*1000)
    return result, round(statistics.median(samples), 3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--size', type=int, default=1409)
    parser.add_argument('--repeats', type=int, default=5)
    args = parser.parse_args()
    if native.core is None:
        parser.error('Build/install native/ first')
    core = native.core
    device = native.gpu()
    fastpath._compile()
    rng = np.random.default_rng(42)
    cost = rng.integers(1, 20, (args.size, args.size), dtype=np.int32)
    cost[rng.random(cost.shape) < .12] = 0
    records = []
    for fraction in (1/cost.size, .1, .9):
        dist = np.full(cost.shape, BIG, np.int32)
        dist[rng.random(cost.shape) < fraction] = 0
        dist[0, 0] = 0
        def cpu():
            out = dist.copy()
            core.dijkstra(out, cost, 2, 3)
            return out
        expected, cpu_ms = measure(cpu, args.repeats)
        row = {'kernel': 'routes', 'tiles': cost.size, 'seed_fraction': fraction, 'rust_cpu_ms': cpu_ms}
        if fastpath._fast:
            def numba():
                out = dist.copy()
                fastpath._fast(out, cost, 2, 3, fastpath.BIG)
                return out
            result, row['numba_ms'] = measure(numba, args.repeats)
            np.testing.assert_array_equal(result, expected)
        if device:
            result, row['gpu_ms'] = measure(lambda: device.solve(dist, cost, 2, 3, 4), args.repeats)
            np.testing.assert_array_equal(result, expected)
            row['gpu_converged'] = device.completed_on_gpu
        records.append(row)
    smoke = (rng.random(cost.shape)*6).astype(np.float32)
    def numpy_smoke():
        nb = np.zeros_like(smoke)
        nb[1:] += smoke[:-1]
        nb[:-1] += smoke[1:]
        nb[:, 1:] += smoke[:, :-1]
        nb[:, :-1] += smoke[:, 1:]
        out = np.roll(np.roll(smoke*.55+nb*.1, 1, axis=0), -1, axis=1)*.97
        out *= .96
        out[out < .02] = 0
        return out
    expected, numpy_ms = measure(numpy_smoke, args.repeats)
    result, rust_ms = measure(lambda: core.diffuse(smoke, 1, -1, True, False), args.repeats)
    np.testing.assert_array_equal(result, expected)
    records.append({'kernel': 'smoke', 'tiles': cost.size, 'numpy_ms': numpy_ms, 'rust_ms': rust_ms})
    if hasattr(core, 'light_mask'):
        for count, radius in ((200,16),(4000,16),(2000,80)):
            lights = [(int(x),int(y),radius,0) for x,y in rng.integers(0,args.size,(count,2))]
            expected, cpu_ms = measure(lambda: core.light_mask(args.size,args.size,lights),args.repeats)
            row = {'kernel':'lighting','tiles':cost.size,'sources':count,'radius':radius,'rust_cpu_ms':cpu_ms}
            if device and hasattr(device,'light_mask'):
                result, row['gpu_ms'] = measure(lambda: device.light_mask(args.size,args.size,lights),args.repeats)
                np.testing.assert_array_equal(result,expected)
            records.append(row)
    print(json.dumps({'adapter': device.name if device else None, 'backend': device.backend if device else None,
                      'size': args.size, 'repeats': args.repeats, 'results': records}, sort_keys=True))


if __name__ == '__main__':
    main()
