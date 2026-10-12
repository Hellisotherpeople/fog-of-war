"""Optional PyO3 kernels. No installation or GPU is required to run the game.

FOW_NATIVE=off selects the original NumPy/Numba/tcod implementations.
FOW_GPU=auto (default) measures whole calls, including transfers, before enabling
GPU routes for a workload class. off/on disables/forces GPU attempts. Failures
always fall back to the exact CPU result. No RNG or game state is used in tuning.
"""
from __future__ import annotations

import logging
import os
from time import perf_counter

import numpy as np

core = None
_reason = None
if os.environ.get('FOW_NATIVE', 'auto').lower() != 'off':
    try:
        import _fow_native as core
    except (ImportError, OSError) as exc:
        _reason = str(exc)

_gpu = None
_gpu_failed = False
_choices = {}
_measurements = {}
_counts = {'cpu_routes': 0, 'gpu_routes': 0, 'gpu_completed': 0}


def _local_frontier(dist, cost):
    """Cheap conservative preflight, not a restriction on the resulting paths.

    A large contiguous unseeded region cannot converge in four GPU passes.
    Sample the actual walkable frontier, not mostly already-solved terrain.
    The full CPU solver always handles fields we decline here.
    """
    if dist.min() < 0:
        return False  # Rescanning a varying flee gradient usually needs long wavefronts.
    cells = np.flatnonzero((dist >= 10**7) & (cost > 0))
    if not len(cells):
        return True
    sample = cells[np.linspace(0, len(cells)-1, min(64, len(cells)), dtype=np.intp)]
    h = dist.shape[1]
    for cell in sample:
        x, y = divmod(int(cell), h)
        if not np.any(dist[max(0,x-3):x+4, max(0,y-3):y+4] < 10**7):
            return False
    return True


def gpu():
    """Lazy, headless device creation; do not reserve a GPU for small battles."""
    global _gpu, _gpu_failed, _reason
    if core is None or _gpu_failed or os.environ.get('FOW_GPU', 'auto').lower() == 'off':
        return None
    if _gpu is None:
        try:
            _gpu = core.GpuRoutes()
        except (AttributeError, RuntimeError) as exc:
            _reason = str(exc)
            _gpu_failed = True
    return _gpu


def _disable_gpu(exc):
    global _gpu, _gpu_failed, _reason
    _reason = str(exc)
    _gpu_failed = True
    _gpu = None
    logging.getLogger(__name__).warning('GPU compute unavailable; using exact CPU routes: %s', exc)


def dijkstra(dist, cost, cardinal, diagonal):
    """Exact in-place routes; True means the native backend handled the request."""
    if core is None or dist.dtype != np.int32 or cost.dtype != np.int32 or dist.ndim != 2:
        return False
    mode = os.environ.get('FOW_GPU', 'auto').lower()
    eligible = mode == 'on'
    key = None
    if mode == 'auto' and dist.size >= 262144:
        fraction = np.count_nonzero(dist < 10**7) / dist.size
        # Sparse destinations need long wavefronts. Dense safety/retreat fields
        # can converge in a handful of parallel passes; measure that case only.
        if fraction >= .1:
            key = (dist.size.bit_length(), bool(fraction >= .9), bool(dist.min() < 0), cardinal, diagonal)
            eligible = _choices.get(key, True)
            if eligible and key not in _choices and not _local_frontier(dist, cost):
                eligible = _choices[key] = False
                _measurements[str(key)] = {'selected': 'cpu', 'reason': 'long or varying wavefront'}
    device = gpu() if eligible else None
    if device is not None:
        try:
            if mode == 'auto' and key not in _choices:
                # Warm the shader/buffers before measuring; three end-to-end samples.
                expected = dist.copy()
                core.dijkstra(expected, cost, cardinal, diagonal)
                device.solve(dist, cost, cardinal, diagonal, 4)
                cpu_times, gpu_times = [], []
                for _ in range(3):
                    reference = dist.copy()
                    start = perf_counter()
                    core.dijkstra(reference, cost, cardinal, diagonal)
                    cpu_times.append(perf_counter() - start)
                    start = perf_counter()
                    candidate = device.solve(dist, cost, cardinal, diagonal, 4)
                    gpu_times.append(perf_counter() - start)
                    if not np.array_equal(expected, candidate):
                        raise RuntimeError('GPU route parity check failed')
                cpu_s, gpu_s = float(np.median(cpu_times)), float(np.median(gpu_times))
                _choices[key] = gpu_s < cpu_s * .8
                _measurements[str(key)] = {'cpu_ms': cpu_s*1000, 'gpu_ms': gpu_s*1000,
                                           'selected': 'gpu' if _choices[key] else 'cpu'}
                if not _choices[key]:
                    device.release_buffers()
                dist[:] = expected
                _counts['cpu_routes'] += 1
                return True
            dist[:] = device.solve(dist, cost, cardinal, diagonal, 4)
            _counts['gpu_routes'] += 1
            _counts['gpu_completed'] += int(device.completed_on_gpu)
            return True
        except (RuntimeError, ValueError) as exc:
            _disable_gpu(exc)
    core.dijkstra(dist, cost, cardinal, diagonal)
    _counts['cpu_routes'] += 1
    return True


def status():
    """Diagnostics without initializing devices or changing backend selection."""
    return {'native': getattr(core, 'version', None), 'gpu_mode': os.environ.get('FOW_GPU', 'auto'),
            'adapter': _gpu.name if _gpu else None, 'backend': _gpu.backend if _gpu else None,
            'fallback_reason': _reason, 'calibration': dict(_measurements), **_counts}
