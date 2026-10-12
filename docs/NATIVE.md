# Python/tcod with Rust compute

The game and interface remain Python/tcod. The optional `native/` package supplies PyO3
kernels for eager and demand-driven shortest paths, batched sight lines, and smoke diffusion.
It includes headless GPU pathfinding through wgpu: **Metal on Apple Silicon**, **Vulkan on
Linux/Nvidia**, and **DirectX 12 or Vulkan on Windows/Nvidia**. No CUDA toolkit is required.
Rendering and speech keep their existing backends.

## Install

Install stable [Rust](https://rustup.rs/) and your platform's C linker (Xcode command-line
tools on macOS, Visual Studio C++ Build Tools on Windows, or a C toolchain on Linux). From
the game checkout, with the existing Python environment:

```sh
.venv/bin/python -m pip install ./native
```

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
| `FOW_GPU=auto` (default) | Measure eligible dense route fields; use GPU only with a measured advantage |
| `FOW_GPU=off` | Native CPU only; no GPU initialization |
| `FOW_GPU=on` | Force GPU route attempts, including CPU completion of unconverged fields |
| `FOW_NATIVE_THREADS=8` | Override the bounded smoke worker pool; default is available CPUs minus two, capped at eight |
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

## Simulation fidelity and memory

Soldier decisions, shared state and random draws remain in their existing turn order.
The workers only compute independent smoke cells from an owned input snapshot. Rust keeps
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
its workspace, and no Python or game objects are retained in it.

## Verify and measure

```sh
.venv/bin/python -m pytest -q tests
FOW_REQUIRE_GPU=1 .venv/bin/python -m pytest -q tests/test_native.py
.venv/bin/python tools/benchmark_native.py --size 1409 --repeats 5
.venv/bin/python tools/benchmark_world.py --radius 640 --turns 180 --digest
FOW_NATIVE=off .venv/bin/python tools/benchmark_world.py --radius 640 --turns 180 --digest
```

Run benchmarks sequentially, without another game, compiler or test process. Kernel timings
include transfers but are not whole-game speedups. World digests compare combat state and
random-generator state after real turns. `FOW_REQUIRE_GPU=1` makes an unavailable GPU a test
failure; ordinary tests skip hardware cases when a physical adapter is unavailable.
CI builds/tests the extension on macOS, Linux and Windows; hosted CI is not evidence of
physical Nvidia GPU validation. Measured hardware and results belong in
[PERFORMANCE.md](PERFORMANCE.md).
