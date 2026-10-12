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
parser.add_argument('--profile',help='Write cProfile data for measured turns (timings then include profiler overhead)')
parser.add_argument('--digest',action='store_true',help='Hash core simulation results after timing for optimization comparisons')
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
if a.profile:
    import cProfile
    profiler = cProfile.Profile()
    profiler.enable()
for _ in range(a.turns):
    g.player.moves = 0
    start = time.perf_counter()
    g.world_turn()
    samples.append((time.perf_counter()-start)*1000)
if a.profile:
    profiler.disable()
    profiler.dump_stats(a.profile)
try:
    from fow.native import status as native_status
except ImportError:  # Archived game revisions predate the optional native module.
    native_status = lambda: {'native': None}
result = dict(acceleration=native_status(),python=platform.python_version(),machine=platform.machine(),theatre=a.theatre,
    seed=a.seed,battlefield=a.battlefield,radius=a.radius,turns=a.turns,initial_actors=initial,profiled=bool(a.profile),
    final_actors=len(g.actors),vehicles=len(g.vehicles),terrain_tiles=g.map.w*g.map.h,
    initialization_s=round(init,3),mean_ms=round(float(np.mean(samples)),3),
    p95_ms=round(float(np.percentile(samples,95)),3),max_ms=round(max(samples),3),
    peak_rss_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024),1))
if a.digest:
    import hashlib
    def scalar(value):
        if isinstance(value,np.generic):
            return value.item()
        if isinstance(value,np.ndarray):
            return value.tolist()
        raise TypeError(f'Unsupported simulation digest value: {type(value).__name__}')
    def ref(value):
        return getattr(value,'id',value)
    actors = [(p.id,p.pos,p.side,p.role,p.rank,p.state,p.stance,p.moves,p.morale,p.stamina,p.kills,
               ref(p.vehicle),ref(p.carrying),p.body.hp,p.body.blood,p.body.pain,p.body.morphine,
               p.body.unconscious,p.body.dead,ref(p.body.killer),
               [tuple(getattr(w,k) for k in w.__slots__) for w in p.body.wounds],
               [(i.tid,i.count,i.loaded,i.condition,i.where) for i in p.inv]) for p in g.actors]
    vehicles = [(v.id,v.pos,v.facing,v.side,v.hp,v.parts,v.dead,v.he,v.ap,v.mg_ammo) for v in g.vehicles]
    squads = [(s.id,[p.id for p in s.members],ref(s.leader),s.state,s.morale,
               [getattr(s.order,k) for k in s.order.__slots__]) for s in g.squads]
    objectives = [(o.pos,o.owner,o.contested,o.hold_time) for o in g.map.objectives]
    payload = json.dumps((g.turn,g.clock,g.rng.getstate(),actors,vehicles,squads,objectives),
                         sort_keys=True,default=scalar).encode()
    digest = hashlib.sha256(payload)
    for layer in ('t','hp','fire','smoke','blood','scorch','elev'):
        digest.update(getattr(g.map,layer).tobytes())
    result['state_digest'] = digest.hexdigest()
print(json.dumps(result,sort_keys=True))
