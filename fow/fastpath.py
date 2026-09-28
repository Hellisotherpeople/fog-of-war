"""Dijkstra maps, fast.

Every side's AI leans on whole-battlefield Dijkstra maps (brain.py): the way to each objective, to
cover, away from the enemy.  tcod's dijkstra2d does the job in C, but the costs here are small
integers, which is exactly the case for Dial's algorithm - a bucket queue instead of a heap, every
cell touched a handful of times - and compiled with numba it is several times faster.

numba is optional (it's a large install).  With it:   pip install numba
Without it, or with FOW_NO_NUMBA=1 in the environment, tcod does the work - with identical results.
"""
from __future__ import annotations

import os

import numpy as np
import tcod

BIG = 10 ** 7
_fast = None


def _compile():
    global _fast
    if os.environ.get("FOW_NO_NUMBA"):
        _fast = False
        return
    try:
        import numba
    except Exception:
        _fast = False
        return

    @numba.njit(cache=True, nogil=True)
    def dial(dist, cost, card, diag, big):
        w, h = cost.shape
        maxc = 1
        for x in range(w):
            for y in range(h):
                if cost[x, y] > maxc:
                    maxc = cost[x, y]
        nb = maxc * max(card, diag) + 1
        # the starting cells, in order of their values (they needn't all be zero: see brain.rescan)
        n0 = 0
        for x in range(w):
            for y in range(h):
                if dist[x, y] < big:
                    n0 += 1
        seeds = np.empty(n0, np.int64)
        vals = np.empty(n0, np.int64)
        k = 0
        for x in range(w):
            for y in range(h):
                if dist[x, y] < big:
                    seeds[k] = x * h + y
                    vals[k] = dist[x, y]
                    k += 1
        order = np.argsort(vals, kind="mergesort")
        # a ring of buckets: everything waiting is within nb of the current distance
        cap = np.full(nb, 64, np.int64)
        size = np.zeros(nb, np.int64)
        store = [np.empty(64, np.int64) for _ in range(nb)]
        dxs = np.array([-1, 0, 1, -1, 1, -1, 0, 1])
        dys = np.array([-1, -1, -1, 0, 0, 1, 1, 1])
        si = 0
        pending = 0
        cur = vals[order[0]] if n0 > 0 else 0
        while pending > 0 or si < n0:
            if pending == 0 and si < n0 and vals[order[si]] > cur:
                cur = vals[order[si]]                     # nothing in flight: jump to the next start
            while si < n0 and vals[order[si]] == cur:
                idx = seeds[order[si]]
                b = cur % nb
                if size[b] == cap[b]:
                    ns = np.empty(cap[b] * 2, np.int64)
                    ns[:size[b]] = store[b][:size[b]]
                    store[b] = ns
                    cap[b] *= 2
                store[b][size[b]] = idx
                size[b] += 1
                pending += 1
                si += 1
            b = cur % nb
            while size[b] > 0:
                size[b] -= 1
                pending -= 1
                idx = store[b][size[b]]
                x = idx // h
                y = idx - x * h
                d = dist[x, y]
                if d != cur:
                    continue                              # already settled closer
                for n in range(8):
                    nx = x + dxs[n]
                    ny = y + dys[n]
                    if nx < 0 or ny < 0 or nx >= w or ny >= h:
                        continue
                    c = cost[nx, ny]
                    if c <= 0:
                        continue
                    nd = d + c * (diag if dxs[n] != 0 and dys[n] != 0 else card)
                    if nd < dist[nx, ny]:
                        dist[nx, ny] = nd
                        bb = nd % nb
                        if size[bb] == cap[bb]:
                            ns = np.empty(cap[bb] * 2, np.int64)
                            ns[:size[bb]] = store[bb][:size[bb]]
                            store[bb] = ns
                            cap[bb] *= 2
                        store[bb][size[bb]] = nx * h + ny
                        size[bb] += 1
                        pending += 1
            cur += 1
        return dist

    _fast = dial


def dijkstra2d(dist: np.ndarray, cost: np.ndarray, cardinal: int = 2, diagonal: int = 3) -> np.ndarray:
    """In place, like tcod.path.dijkstra2d(dist, cost, cardinal, diagonal, out=dist): each cell ends up at
    the cheapest (its start value, or a neighbour's value plus the cost of stepping onto it)."""
    if _fast is None:
        _compile()
    if _fast and dist.dtype == np.int32 and cost.dtype == np.int32 and dist.ndim == 2:
        if (dist < BIG).any():
            _fast(dist, cost, cardinal, diagonal, BIG)
        return dist
    tcod.path.dijkstra2d(dist, cost, cardinal, diagonal, out=dist)
    return dist


def accelerated() -> bool:
    if _fast is None:
        _compile()
    return bool(_fast)
