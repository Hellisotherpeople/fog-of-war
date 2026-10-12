# Python/tcod with Rust compute

The game and interface remain Python/tcod. The optional `native/` package supplies PyO3
kernels for eager and demand-driven shortest paths, batched sight lines, smoke diffusion,
movement scoring, compact spatial indexes, and lighting. Version **0.2.0** adds the latter
three and shares one bounded worker pool across independent native workloads.
It includes headless GPU pathfinding and integer light masks through wgpu: **Metal on Apple Silicon**, **Vulkan on
Linux/Nvidia**, and **DirectX 12 or Vulkan on Windows/Nvidia**. No CUDA toolkit is required.
Rendering and speech keep their existing backends.

## Install

Install stable [Rust](https://rustup.rs/) and your platform's C linker (Xcode command-line
tools on macOS, Visual Studio C++ Build Tools on Windows, or a C toolchain on Linux). From
the game checkout, with the existing Python environment:

```sh
.venv/bin/python -m pip install ./native
```

If `cargo` is not on your current shell's path after installing Rust, run
`. "$HOME/.cargo/env"` on macOS/Linux, or open a new terminal on Windows.

On Windows use `.venv\Scripts\python -m pip install ./native`. This builds an optimized
extension, including GPU support. Normal Python dependencies still come from
`requirements.txt`; optional Numba remains useful for the relief viewshed kernel.
Restart the game after installing. Rust is only needed to **build** the extension; a
wheel built for the same Python/platform can be installed without a compiler.
For an environment managed by uv without pip, use `uv pip install --python
.venv/bin/python ./native` instead.

Developers can install `maturin` and run `maturin develop --release --manifest-path
native/Cargo.toml` in the activated game environment. Do not benchmark debug builds.
`maturin build --release --locked --manifest-path native/Cargo.toml` produces a wheel.
Add `--no-default-features` for a CPU-only build without wgpu. The lockfile pins the Rust
dependencies. The crate forbids unsafe code and uses release optimization and thin LTO.

## Backend selection

| Environment variable | Meaning |
|---|---|
| `FOW_NATIVE=auto` (default) | Use Rust if installed; otherwise original Python/Numba/tcod |
| `FOW_NATIVE=off` | Use the original implementation for comparisons or troubleshooting |
| `FOW_GPU=auto` (default) | Measure eligible route fields and heavy lighting workloads; require a measured advantage |
| `FOW_GPU=off` | Native CPU only; no GPU initialization |
| `FOW_GPU=on` | Force GPU route and lighting attempts, including CPU completion of unconverged routes |
| `FOW_NATIVE_THREADS=8` | Bound the shared smoke, route-batch, spatial-query and lighting pool; default is available CPUs minus two, capped at eight |
| `WGPU_BACKEND=metal`, `vulkan`, or `dx12` | Select an available compute API |
| `WGPU_ADAPTER_NAME=NVIDIA` | Select an adapter by a case-insensitive part of its name |

These are launch environment variables, not console commands. For example, on macOS/Linux:
`FOW_GPU=off .venv/bin/python main.py`. With Rust disabled, `FOW_NO_NUMBA=1` also disables
Numba, leaving the original tcod/NumPy path. Nothing downloads or builds during gameplay.

GPU creation is lazy. Auto mode considers only large, densely seeded fields. A sampled
frontier check declines long unseeded regions and varying negative flee gradients before
allocating a device; those usually need too many GPU wavefront passes. Calibration compares three
whole calls, including uploads, synchronization, readback and any CPU completion, and
requires a 20% margin over native CPU. It also checks exact results. Decisions are cached
per workload class for the process. Rejected GPU buffers are released. Initial calibration
has a one-time cost and may allocate a device even if CPU subsequently wins.

The compute shader uses integer costs and separate source/destination buffers. Four
parallel relaxation passes run in one submission. If the last pass changes any distance,
the CPU finishes the same monotone shortest-path problem. **There is no route-length,
detour or search-radius cutoff.** Buffers are reused for same-sized fields. Missing adapters,
unsupported limits, device loss and failed parity checks fall back to exact CPU routes.
Software GPU adapters are declined. `fow.native.status()` reports the adapter, timings,
selection, fallback reason and route counts without initializing a GPU.

Lighting uses integer circle tests and atomic writes of boolean light coverage, with no
floating-point approximation. Sources, output and readback buffers are reused between
calls. Auto mode considers GPU lighting only for large maps with substantial overlapping
illumination, compares complete CPU/GPU calls, checks exact masks and requires the same
20% advantage. Small/sparse workloads remain on CPU. The existing sources, lifetimes,
fire-lighting rules and visibility range are preserved.

## Simulation fidelity and memory

Soldier decisions, shared state and random draws remain in their existing turn order.
Workers compute independent smoke cells, complete independent route fields, batched nearby
queries and disjoint lighting rows. They own input snapshots and never touch live Python
actors or consume game randomness. Rust keeps
the same float32 operation order, without fast math or fused multiply-add. Sight-line
checks preserve Bresenham ties, roof rules and terrain crest tests. They borrow map arrays
under the GIL rather than copying millions of cells for each observer.

Lazy fields keep their queues in Rust and solve only until the requested cells are settled.
Costs use one or two bytes per tile; unknown distances use zero-filled pages. Save files
contain ordinary NumPy inputs, never extension objects, worker pools or GPU resources.
Loading on a Python-only installation reconstructs the same routes. Existing saves remain
readable. This adds acceleration without reducing actor turns or changing bubble boundaries.
Eager route queues reuse thread-local workspace across calls; this avoids the allocator
retention caused by repeatedly growing large seed/bucket vectors. Each calling thread owns
its workspace. Parallel route batches instead borrow from a shared cache of two queues,
so jobs moving among workers do not leave a large retained queue on every worker thread.
No Python or game objects are retained in either cache.

Movement scores the complete eligible neighborhood in one native call. Python applies the
same random tie-breaks, in the same order, then executes the existing movement action.
The native position indexes are derived compact arrays updated by the ordinary movement
hooks; actor objects remain authoritative. Query results retain roster order, including
vehicle occupants for objective observers. Indexes are discarded on save and rebuilt on load.

Unchanged safety, threat and flee fields survive routine refreshes only when their inputs
are exactly equal. Terrain sight caches invalidate crossed 32-tile blocks; distant changes
do not discard unrelated lines. Smoke still receives a live check. Light masks are reused
only while their complete source list is unchanged, including source expiration.

The moving terrain buffer uses padded NumPy slabs. A short reframe reuses the overlapping
cells as views and imports only incoming strips; reaching a slab edge compacts the overlap.
Authoritative replacement arrays (such as smoke output) are synchronized before shifting.
Terrain, objects and events keep the same world coordinates. Slab padding and native indexes
are transient, so saves do not duplicate them and Python-only machines can still load them.

## Verify and measure

```sh
.venv/bin/python -m pytest -q tests
FOW_REQUIRE_GPU=1 .venv/bin/python -m pytest -q tests/test_native.py
FOW_REQUIRE_GPU=1 .venv/bin/python -m pytest -q tests/test_native_expansion.py
.venv/bin/python tools/benchmark_native.py --size 1409 --repeats 5
.venv/bin/python tools/benchmark_world.py --radius 640 --turns 180 --digest
FOW_NATIVE=off .venv/bin/python tools/benchmark_world.py --radius 640 --turns 180 --digest
.venv/bin/python tools/benchmark_world.py --radius 240 --turns 180 --walk --digest
```

Run benchmarks sequentially, without another game, compiler or test process. Kernel timings
include transfers but are not whole-game speedups. World digests compare combat state and
random-generator state after real turns. `FOW_REQUIRE_GPU=1` makes an unavailable GPU a test
failure; ordinary tests skip hardware cases when a physical adapter is unavailable.
CI builds/tests the extension on macOS, Linux and Windows; hosted CI is not evidence of
physical Nvidia GPU validation. Measured hardware and results belong in
[PERFORMANCE.md](PERFORMANCE.md).
