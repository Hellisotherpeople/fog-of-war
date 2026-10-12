#!/usr/bin/env python3
"""Reproducible real-AI world benchmark; no damage, action or turn shortcuts.

Run each radius in a fresh process, without concurrent tests:
  .venv/bin/python tools/benchmark_world.py --radius 240 --turns 180
Radius 0 selects the old bounded scene for comparison. FOW_CODE_ROOT can point
at an archived revision, allowing the same harness to measure the baseline.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import resource
import sys
import tempfile
import time

os.environ.setdefault('FOW_HOME', tempfile.mkdtemp(prefix='fow_benchmark_'))
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ['FOW_DEBUG'] = '1'
sys.path.insert(0, os.environ.get('FOW_CODE_ROOT', str(Path(__file__).resolve().parents[1])))
import numpy as np
from fow.game import Game

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--radius',type=int,default=240)
parser.add_argument('--turns',type=int,default=180)
parser.add_argument('--seed',type=int,default=42)
parser.add_argument('--theatre',default='bocage44')
parser.add_argument('--battlefield',default='large')
a = parser.parse_args()
t0 = time.perf_counter()
g = Game(a.theatre,'usa',seed=a.seed,setup={'battlefield':a.battlefield,'reality_radius':a.radius})
if a.radius:
    from fow.streaming import ensure
    ensure(g)
init = time.perf_counter()-t0
initial = len(g.actors)
# Warm compiled routines separately; the actual fight keeps running.
for _ in range(5):
    g.player.moves = 0
    g.world_turn()
samples = []
for _ in range(a.turns):
    g.player.moves = 0
    start = time.perf_counter()
    g.world_turn()
    samples.append((time.perf_counter()-start)*1000)
print(json.dumps(dict(python=platform.python_version(),machine=platform.machine(),theatre=a.theatre,
    seed=a.seed,battlefield=a.battlefield,radius=a.radius,turns=a.turns,initial_actors=initial,
    final_actors=len(g.actors),vehicles=len(g.vehicles),terrain_tiles=g.map.w*g.map.h,
    initialization_s=round(init,3),mean_ms=round(float(np.mean(samples)),3),
    p95_ms=round(float(np.percentile(samples,95)),3),max_ms=round(max(samples),3),
    peak_rss_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024),1)),sort_keys=True))
