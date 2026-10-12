# Simulation performance and the native core

The game remains Python/tcod, with an optional **implemented Rust/PyO3 core** for route finding,
line-of-sight batches, smoke, movement scoring, spatial queries and lighting. Portable GPU
route and light-mask computation uses wgpu/Metal/Vulkan/DX12.
[Installation and backend controls](NATIVE.md). A complete Rust rewrite has **not** been performed;
most actor decisions still execute in Python. The older full-port estimates below remain estimates,
not measured gains from the implemented stages.

## Second native stage: all six implementation areas

The 0.2.0 extension and game changes implement these six areas while preserving the
ordinary action loop, random-draw order, actor eligibility and existing tactical radius:

| Area | Implemented behavior |
|---|---|
| Exact nearby queries | Objective observers use batched spatial queries including vehicle crew; nearby actors and enemy candidates use roster-ordered native indexes with normal movement updates. |
| Native movement and packed hot data | Rust scores the full eligible movement neighborhood in one call. Compact native position indexes accelerate repeated queries; Python actors remain authoritative and Python retains random tie-breaks and action execution. |
| More CPU concurrency | A bounded Rayon pool runs independent nearby-query batches, home/threat route pairs, lighting rows and smoke cells. Workers never mutate soldiers or consume game randomness. |
| Exact reuse | Equal safety/threat/flee inputs retain their fields. Sight caches use regional terrain versions; smoke is still checked live. Light masks retain results until sources, fires or expiry change them. |
| Reusable terrain storage | Padded array views reuse overlapping terrain on short reframes; only incoming strips are imported. Periodic compaction handles larger shifts. Mutable replacement arrays are synchronized, and padding is omitted from saves. |
| Additional GPU computation | Integer light masks use Metal/Vulkan/DX12 with persistent buffers, exact parity checks, failure recovery and automatic selection by complete CPU/GPU call cost. Ordinary sparse lighting stays on CPU. |

This is not a full Rust actor-AI port. Native positions are derived query data, not a second
simulation state. Reloads, medicine, action frequency, strategic abstraction and bubble
boundaries keep their existing rules. Scheduling fewer soldier turns is not part of the change.
Regional invalidation and reusable terrain also work without the optional extension.

### Measured second-stage results, 12 October 2026

Apple M4 Pro (10 performance + 4 efficiency cores, 20 GPU cores, 48 GiB), CPython 3.12.11,
release extension, Numba installed. These comparisons are against the **preceding hybrid game**,
not the original Python build. Sequential fresh processes used seed 42, large forces and five
warm-up turns, with no concurrent local tests or builds. Rendering and speech are excluded.

| Scenario | Initial people | Previous mean | New mean | Mean cost reduction | Previous → new peak RSS |
|---|---:|---:|---:|---:|---:|
| Bocage, radius 240, 180 turns | 539 | 42.64 ms | **39.48 ms** | 7.4% | 477.8 → 447.4 MiB |
| Bocage, radius 640, 180 turns | 2,965 | 280.74 ms | **247.36 ms** | 11.9% | 2,417.7 → 2,607.9 MiB |
| Real travel, radius 240, 180 actions | 539 | 50.33 ms/action | **46.65 ms/action** | 7.3% | 482.9 → 481.5 MiB |
| Normandy night, radius 240, 180 turns | 552 | 36.45 ms | **32.78 ms** | 10.1% | 475.5 → 436.2 MiB |
| Bocage, radius 240, 1,200 turns | 539 | 32.61 ms | **30.89 ms** | 5.3% | 516.5 → 501.3 MiB |

The maximum battle's p95 fell from **733.63 to 529.82 ms** (27.8%); its slowest turn was
976.69 ms. Mean throughput increased 13.5%. That case consumed **190.2 MiB more peak RAM**
(7.9%); faster execution does not mean lower memory use at every radius. Earlier development
samples of the same maximum battle measured 253–255 ms and 2,504–2,556 MiB. These are individual
measurements, not confidence intervals or guarantees. The maximum still takes about 6.3 times
the new default's average turn time; this work does not establish default-like latency for
3,000 fully detailed people or justify automatically increasing everyone's radius.

All five pairs produced matching recorded core-state digests. Real travel used normal path
steps and action costs: 180 actions advanced **183 world turns** and moved **120 world tiles**.
The streamed terrain window reused 1,066,046 overlapping cells during that run. The 1,200-turn
comparison also matched after combat, casualties and repeated terrain refreshes. The digest
covers selected actor, wound, ammunition, vehicle, squad/order, objective, terrain and Python RNG
state; it is replay evidence alongside the regression tests, not an exhaustive proof of every
subsystem. No actor turns or game outcomes are skipped to obtain these timings.

The stationary baselines used native 0.1.0. Later travel, night and long-run baselines used
the archived game code with the installed 0.2.0 library through its old API, keeping library
builds identical within those pairs. The final maximum and long-run samples include the last
bounded route-workspace allocation cleanup; the other samples preceded it. Exact versions,
digests, repeat measurements and limitations are recorded in the
[raw second-stage results](benchmarks/2026-10-12-native-expansion.json).

### Additional GPU lighting measurements

Complete-call medians over five warmed calls, 1,985,281 tiles, physical M4 Pro/Metal:

| Light workload | Native CPU | Metal GPU |
|---|---:|---:|
| 200 lights, radius 16 | **0.108 ms** | 0.525 ms |
| 4,000 lights, radius 16 | **0.548 ms** | 1.334 ms |
| 2,000 lights, radius 80 (stress case) | 3.129 ms | **2.576 ms** |

The synthetic heavy case benefits from the GPU, but its 17.7% improvement in this sample is
below the automatic selector's 20% margin. Normal sparse lighting is faster on CPU. Forcing
Metal in the night battle exercised **130 GPU lighting calls** and produced the same digest,
but took 34.42 ms/turn versus auto's 32.78 ms. Auto retained CPU lighting while using GPU
routes for a separately measured suitable route workload. GPU dispatch is an optional exact
backend, not a presumed whole-game speed multiplier. Nvidia Vulkan/DX12 support is implemented;
physical Nvidia timing and validation remain unavailable on this machine.

The local full suite passed 345 tests with physical GPU availability required. After the final
allocation cleanup and additional GPU-failure regression, all 76 focused native, incremental-world
and streaming tests passed. Pure-Python checks passed 27 tests with Rust and Numba disabled
(two optional Numba cases skipped). Rust formatting, Clippy with warnings denied and CPU-only
compilation passed.
The [final source CI run](https://github.com/Hellisotherpeople/fog-of-war/actions/runs/38301158750)
passed on all three operating systems: **346 tests on macOS**, **332 tests plus 14 hardware-GPU
skips on Linux and Windows**, and **29 original-backend/save checks on each platform**.

## First hybrid stage measured on 12 October 2026

Apple M4 Pro, 10 performance and 4 efficiency CPU cores, 20 GPU cores, 48 GiB RAM; CPython 3.12.11.
Release Rust build, Numba installed for remaining kernels. Each configuration used a fresh process,
five warm-up turns and 180 timed real turns in Bocage 1944, large forces, USA, seed 42. Runs were
sequential with no concurrent tests or compiler. The player remained stationary while NPCs fought.

| Configuration | Initial people | Mean turn | p95 turn | Slowest turn | Peak RSS |
|---|---:|---:|---:|---:|---:|
| Original Python/Numba, radius 240 | 539 | 47.24 ms | 107.38 ms | 134.52 ms | 440.5 MiB |
| Hybrid auto, radius 240 | 539 | **41.74 ms** | **77.48 ms** | **93.64 ms** | 448.2 MiB |
| Original Python/Numba, radius 640 | 2,965 | 323.88 ms | 885.03 ms | 1,710.83 ms | 2,364.3 MiB |
| Hybrid auto, radius 640 | 2,965 | **276.98 ms** | **740.04 ms** | **1,053.88 ms** | 2,479.0 MiB |
| Hybrid forced Metal, radius 240 | 539 | 44.92 ms | 86.08 ms | 107.97 ms | 461.8 MiB |

Mean turn cost fell **11.6% at default radius and 14.5% at maximum** (13.2% and 16.9% more
throughput). p95 fell **27.8% and 16.4%**. Peak memory increased by 7.7 MiB and 114.7 MiB
(1.7% and 4.9%). Native eager queues reuse workspace: an earlier allocating version accumulated
roughly 300 MiB of additional allocator-retained memory in the default battle; that version is
not shipped. Maximum-radius turns still sometimes exceed one second. Matching the original
default's average with this maximum population still needs roughly another **5.9×** speedup.

Both backends produced identical core-state digests at both radii. The forced-Metal battle also
matched and exercised 88 GPU route calls; 86 required exact CPU completion after the bounded GPU
passes. Auto mode correctly leaves these long wavefronts on CPU without allocating a GPU.
No actor turns, path detours, wounds, random draws or simulation-radius rules were removed.

### Where the GPU helps

Five warmed calls per case, 1,985,281 tiles. Timings include array transfer, dispatch, synchronization,
readback and any CPU completion. These are synthetic kernel workloads, **not battle speedups**.

| Kernel | Existing backend | Native CPU | Metal GPU |
|---|---:|---:|---:|
| Sparse-goal routes | 65.13 ms (Numba) | 48.47 ms | 57.68 ms, plus CPU completion included |
| Routes with 10% randomly distributed seeds | 61.59 ms (Numba) | 44.22 ms | 52.66 ms, plus CPU completion included |
| Routes with 90% randomly distributed seeds | 60.16 ms (Numba) | 29.35 ms | **6.04 ms**, converged on GPU |
| Smoke diffusion and wind | 3.13 ms (NumPy) | **1.65 ms**, bounded Rayon pool | Runs on CPU |

The suitable dense route field is **4.86× faster on Metal than native CPU**; smoke is 1.90× faster
than NumPy. Auto mode measures eligible workload classes and requires a 20% advantage before
selecting GPU. Sparse/long routes remain on CPU. The shader uses exact integers and CPU completion
for unresolved paths, rather than assuming a fixed number of passes is a complete solution.

Physical **Apple M4 Pro/Metal** validation passed. Nvidia support is implemented through
**Vulkan and DirectX 12**, without a CUDA dependency. No physical Nvidia machine was available
for local testing or timing; portable backend support is not a claim of Nvidia performance validation.
The installed release wheel passed **330 tests**, including 42 native tests with physical GPU
availability required. Rust formatting, Clippy with warnings denied, and CPU-only compilation passed.
The original backend also passed 19 focused tests with both Rust and Numba disabled (two optional
Numba cases skipped).
The subsequent [cross-platform CI run](https://github.com/Hellisotherpeople/fog-of-war/actions/runs/38293643975)
passed on macOS, Linux and Windows: 331 tests on macOS, 318 plus 13 hardware-GPU skips on Linux
and Windows, and another 22 original-backend/save checks on each platform. That run includes a
regression for keeping a real radio detector squad tracked outside the detailed simulation circle.

Raw results: [native benchmark data](benchmarks/2026-10-12-native.json).
Parity checks cover tcod/reference routes, negative flee seeds, walls, disconnected terrain,
lazy queries, threaded workspace reuse, portable saves, strided arrays, sight lines, bit-exact
smoke, GPU completion, invalid adapter selection and device/parity failures. These single-seed
world samples exclude rendering, voice synthesis, moving-buffer transitions and long campaigns.
They establish a measured first native stage; they do not establish the older projected full-port gains.

## Earlier Python optimization baseline, 12 October 2026

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
They were relative to the earlier Python/Numba baseline above (339.3 ms at radius 640), before
either native stage, on the same machine and workload. They are not updated forecasts for 0.2.0.
The rows are alternative levels of work, not multipliers to stack with the measured gains.

| Implementation | Estimated whole-turn speedup | Current maximum workload would take |
|---|---:|---:|
| Careful full Rust port, similar algorithms, mostly one CPU thread | 2–4× | roughly 85–170 ms |
| Native core with compact data, batching and useful multicore work | 4–10× | roughly 34–85 ms |
| Additional GPU work | No credible whole-game multiplier yet | Route prototype measured above; benefits depend on workload |

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

## Remaining CPU and GPU work without changing the war

[Rayon](https://docs.rs/rayon/latest/rayon/) now distributes independent route pairs, spatial-query
batches, lighting rows and large smoke stencils across a bounded thread pool. PyO3 detaches owned
native computations from Python's GIL. For further kernels, benchmark worker counts instead of
assuming fourteen equal cores or a fourteen-fold gain. Leave capacity for rendering and speech.
Expand independent precomputation with live-state revalidation before attempting concurrent
mutation of each soldier's state.

Today soldiers act in a shuffled but ordered sequence against shared state. A naive parallel
rewrite could change who fires first, what somebody sees, who takes ammunition, or which medic
reaches a casualty. Keep order-sensitive resolution and random draws deterministic. Parallel
precomputation needs dependency checks and revalidation before ordered application. Fixed-seed
replay comparisons must cover movement, terrain, weapons, inventories, medical care, objectives,
save/load and streaming before expanding the tactical radius.

Beyond the integer route and lighting implementations measured above, GPU candidates include
large regular grids for smoke/fire, weather and batched visibility. Those additional kernels still
need measured prototypes and cross-device numerical parity checks. Branch-heavy decisions,
inventories and small searches generally belong on the CPU. [wgpu](https://docs.rs/wgpu/latest/wgpu/)
provides the implemented compute access through Metal, Vulkan and DirectX 12. Apple Silicon's
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
.venv/bin/python tools/benchmark_world.py --radius 240 --turns 180 --walk --digest
.venv/bin/python tools/benchmark_world.py --radius 240 --turns 180 --theatre normandy_airborne44 --digest
.venv/bin/python tools/benchmark_world.py --radius 240 --turns 1200 --digest
.venv/bin/python tools/benchmark_world.py --radius 640 --turns 180 --profile /tmp/world.prof
.venv/bin/python tools/benchmark_native.py --size 1409 --repeats 5
```

`FOW_CODE_ROOT=/path/to/archived/revision` selects an older game for the same world benchmark
harness. It does not replace the installed native extension; preserve its reported version when
comparing results. `--walk` times normal player actions and reports actual world turns separately.

For the recorded full-scan reference, only the candidate loops in `commander.update_objectives`
and `ai.surgeon_act` used `game.actors` instead of `game.near(...)`; their remaining code and the
rest of the game were identical. Digest calculation runs after timing. Profiled times include
instrumentation overhead and should not be compared directly with ordinary runs.
