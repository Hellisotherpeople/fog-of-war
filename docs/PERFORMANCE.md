# Simulation performance and a native-core estimate

The game remains Python/tcod. Rust is the recommended language for a future native simulation
core, introduced in measured stages while retaining the Python interface and content. A complete
rewrite has **not** been performed or benchmarked. The estimates below concern full world turns,
not display FPS, and include no reduction in simulation fidelity.

## Measured on 12 October 2026

Apple M4 Pro: 10 performance CPU cores, 4 efficiency cores, 20 GPU cores, 48 GiB RAM.
Python 3.12.11, Numba enabled, Bocage 1944, USA, large force density, seed 42. Each run used a
fresh process, five warm-up turns and 180 timed world turns, with no concurrent test runs.
The player stayed stationary; NPCs fought, moved, expended ammunition and took casualties.

| Configuration | Initial people | Mean turn | p95 turn | Peak memory |
|---|---:|---:|---:|---:|
| Current default, radius 240 | 539 | 50.7 ms | 113.4 ms | 433.7 MiB |
| Maximum, radius 640, original full-roster queries | 2,965 | 379.8 ms | 1,050.6 ms | 2,413.3 MiB |
| Current maximum, radius 640 | 2,965 | 339.3 ms | 910.4 ms | 2,388.5 MiB |

Objective capture checks and aid-post surgeons now use the existing spatial index. Their
eligibility checks and original actor order remain intact. This removes repeated scans of
the whole population without skipping any actor's turn. Maximum-radius mean cost fell **10.7%**
(about 12% greater throughput), and p95 fell **13.3%** in this paired sample. Do not infer a memory
saving from the small RSS difference: the reference harness also loads the old function bodies.

Both maximum-radius runs ended with 2,875 people, 130 vehicles and exactly the same core-state
SHA-256 digest. The digest includes positions, wounds, ammunition, vehicle damage, squad orders,
objective ownership, terrain layers and random-generator state. This is meaningful replay
evidence, not a proof covering every subsystem or future campaign. The current maximum's slowest
turn was still 1.78 seconds. Initialization was 1.53 seconds at default and 4.98 seconds at maximum.
The maximum needs another **6.7× average speedup** to match today's default mean turn cost.

Raw results and profile excerpts: [benchmark data](benchmarks/2026-10-12-world.json).
The earlier radius sweep is in [the world notes](LIVING_WORLD.md). These single-seed samples
exclude rendering, speech synthesis, long-campaign storage growth and moving-buffer transitions;
they are not guarantees for every theatre or battle.

## What the profile shows

Before the two query changes, cProfile recorded 541 million calls over 180 turns. Instrumentation
increased wall time from roughly 69 seconds to 129 seconds, so its timings are diagnostic rather
than ordinary gameplay measurements. Soldier actions occupied 75.4 seconds cumulatively;
objective capture occupied another 14.7 seconds. Inside soldier actions, vision took 11.3 seconds
and surgeons 7.2 seconds. Eager and demand-driven distance-field work took about 14.4 seconds
across the turn. These branches overlap and must not be added together.

There is substantial Python object/property/dictionary overhead, but distance fields and sight
lines already have compiled Numba kernels, and tcod/NumPy already execute native work. Converting
the same algorithms to Rust will not accelerate those portions like interpreted Python loops.
The remaining opportunities include compact actor data, batched queries, fewer temporary arrays,
better field reuse, and parallel independent computations.

## Estimated rewrite gains

These are engineering planning ranges with considerable uncertainty, **not measured Rust results**.
They are relative to the current Python/Numba build on the same machine and the same workload.
The rows are alternative levels of work, not multipliers to stack.

| Implementation | Estimated whole-turn speedup | Current maximum workload would take |
|---|---:|---:|
| Careful full Rust port, similar algorithms, mostly one CPU thread | 2–4× | roughly 85–170 ms |
| Native core with compact data, batching and useful multicore work | 4–10× | roughly 34–85 ms |
| Additional GPU work | No credible whole-game multiplier yet | Requires a measured prototype |

The upper end requires substantial design work. For perspective, making 80% of a turn ten times
faster only gives `1 / (0.20 + 0.80/10) = 3.57×` overall. This explains why isolated 20× or 100×
kernel benchmarks would not justify those claims for the whole game. A faster renderer or a new
engine framework alone would not remove the measured simulation cost.

Rust offers a useful balance of native performance and auditable ownership/type rules. A small
core exposed through [PyO3](https://pyo3.rs/main/parallelism) and packaged with
[maturin](https://www.maturin.rs/) can preserve Python/tcod development. Pass arrays or whole work
batches across that boundary, rather than making a Python/Rust call for every property of every
soldier. Use explicit types for world positions, buffer positions, entity IDs and time units.

Keep hot actor fields in compact arrays, retain stable entity IDs, and preserve the existing
spatial index's ordering rules. Profile optimized builds with representative battles, then compare
[release/LTO settings](https://doc.rust-lang.org/cargo/reference/profiles.html) and
[profile-guided optimization](https://doc.rust-lang.org/rustc/profile-guided-optimization.html).
Compiler settings should earn their place through measurements; relaxed floating-point arithmetic
must not silently alter wounds, sight or ballistics.

## CPU and GPU use without changing the war

[Rayon](https://docs.rs/rayon/latest/rayon/) can distribute independent native work across a bounded
thread pool, and PyO3 can detach that work from Python's GIL. Benchmark worker counts instead of
assuming fourteen equal cores or a fourteen-fold gain. Leave capacity for rendering and speech.
Independent distance fields, spatial queries and batches of sight lines are better first targets
than concurrent mutation of each soldier's state.

Today soldiers act in a shuffled but ordered sequence against shared state. A naive parallel
rewrite could change who fires first, what somebody sees, who takes ammunition, or which medic
reaches a casualty. Keep order-sensitive resolution and random draws deterministic. Parallel
precomputation needs dependency checks and revalidation before ordered application. Fixed-seed
replay comparisons must cover movement, terrain, weapons, inventories, medical care, objectives,
save/load and streaming before expanding the tactical radius.

The M4 Pro's GPU could help with large regular grids: smoke/fire updates, lighting, weather and
batched visibility computations. Exact distance-field algorithms are another research candidate;
branch-heavy decisions, inventories and small heap searches generally belong on the CPU. This is
an assessment of this workload, not a measured GPU result. [wgpu](https://docs.rs/wgpu/latest/wgpu/)
provides compute access through Metal on macOS and other backends elsewhere. Apple Silicon's
[shared memory](https://developer.apple.com/documentation/metal/mtlstoragemode/shared) still requires
[CPU/GPU synchronization](https://developer.apple.com/documentation/metal/resource-synchronization).
Keep fields resident and batch work; frequent readbacks or tiny dispatches can make it slower.

If a GPU made a component occupying 20% of runtime twenty times faster, the whole turn would gain
only `1 / (0.80 + 0.20/20) = 1.23×`, before synchronization costs. GPU priorities should be
reassessed after the CPU work, since the bottleneck will move.

At roughly fixed density and linear per-area cost, 4× throughput buys about 2× radius, not 4×.
Battle interactions, path caches, terrain allocation and streaming can break that approximation.
The first useful native target is today's roughly 3,000-person maximum at default-like latency;
tens of thousands of fully detailed people remain a larger engineering target, not a promise.
Unbounded world coordinates do not imply infinite detailed simulation in finite hardware.

## Reproduction

Run separately, with other tests and benchmark processes stopped:

```sh
.venv/bin/python tools/benchmark_world.py --radius 240 --turns 180 --digest
.venv/bin/python tools/benchmark_world.py --radius 640 --turns 180 --digest
.venv/bin/python tools/benchmark_world.py --radius 640 --turns 180 --profile /tmp/world.prof
```

For the recorded full-scan reference, only the candidate loops in `commander.update_objectives`
and `ai.surgeon_act` used `game.actors` instead of `game.near(...)`; their remaining code and the
rest of the game were identical. Digest calculation runs after timing. Profiled times include
instrumentation overhead and should not be compared directly with ordinary runs.
