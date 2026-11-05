# THOR-FEASIBILITY — Rolling Perception on AGX Thor (read-only probe)

Date: 2026-11-01 (AKST) · Method: SSH via `~/workspace/ssh/thor.config` (`thor`, user `caseydigennaro`), read-only except one throwaway compile/run in `/tmp/rp-probe` on the Thor, deleted and verified gone afterwards. No installs, no service changes, nothing written outside `/tmp` on the Thor.

## Hard numbers (measured, not from docs)

| Item | Result |
|---|---|
| Host / OS | `thor`, Linux 6.8.12-1021-tegra aarch64, Ubuntu (JetPack 7.x userland) |
| GPU | NVIDIA Thor, **compute capability 11.0 (sm_110)**, 20 SMs, integrated (`is_integrated=1`) |
| Driver | **595.78** (open kernel module, r595_00) |
| System / unified RAM | 122 GiB total (PyTorch reports GPU `total_memory=131,856,920,576` B — same physical LPDDR5X pool) |
| nvcc | **CUDA 13.2, V13.2.86** at `/usr/local/cuda/bin/nvcc` (`/usr/local/cuda-13.2`) |
| PyTorch | 2.11.0 in `~/ml/.venv`, built against CUDA 13.0, `cuda.is_available()=True`, capability `(11, 0)` |
| NVRTC | **YES** — `libnvrtc.so.13.2.86` (+ builtins, static) in `/usr/local/cuda-13.2/targets/sbsa-linux/lib/`, header `/usr/local/cuda/include/nvrtc.h`, runtime `nvrtcVersion = 13.2` |
| CUPTI | **YES (library + headers)** — `libcupti.so.13` / `libcupti.so.2026.1.2` in `targets/sbsa-linux/lib/`, headers `cupti*.h` in `/usr/local/cuda/include/`, samples/docs under `/usr/local/cuda-13.2/extras/CUPTI/`; `ncu` and `nsys` binaries also present |
| Rust | **YES, off-PATH** — `rustc 1.99.1 (58cf8f9c3, 2026-10-13)`, `cargo 1.99.1`, stable `aarch64-unknown-linux-gnu`, in `~/.cargo/bin` (not on non-login SSH PATH; prepend it). Extra toolchain `1.99-aarch64-unknown-linux-gnu` also installed |
| cudarc | Not a system dependency; crates **already in the local cargo registry cache: `cudarc-0.19.9.crate`, `cudarc-0.19.10.crate`** — vendoring/pinning is still the right move for reproducibility (see risks) |

## The one write test: sm_110 compile + run

- `nvcc -O2 -arch=sm_110` on a vector-add + device-properties probe: **PASS**.
- Ran correctly on-device: device props printed (below), and a `cudaMallocManaged` vector-add returned `c[42]=126.0` (expected 126), `cudaDeviceSynchronize = no error`: **PASS**.
- NVRTC runtime test (host C++ linked `-lnvrtc`): `nvrtcCreateProgram` OK, **`nvrtcCompileProgram` with `-arch=compute_110` (+ `--use_fast_math`) = NVRTC_SUCCESS**, empty log, PTX size 562 B for the trivial kernel: **PASS**. This confirms the installed NVRTC 13.2 accepts `compute_110` — the seed email's `sm_100`/`sm_101` targets are wrong for this box and unnecessary; target `compute_110` → PTX (driver JITs to sm_110) or CUBIN via `nvrtcGetCUBIN`.

Device properties from that probe (`cudaDeviceProp`):

```
cooperativeLaunch=1  concurrentManagedAccess=1  pageableMemoryAccess=1
unifiedAddressing=1  concurrentKernels=1        directManagedMemAccessFromHost=0
multiProcessorCount=20  integrated=1
```

Occupancy query for the test kernel: 6 active blocks/SM max (256 threads) — headroom exists, it is not a 1-block machine.

## Honest assessment by subsystem

### 1. Persistent kernel + Cooperative Groups on sm_110 — FEASIBLE, with limits
- `cooperativeLaunch=1`, so Cooperative Groups grid synchronisation is hardware/driver-supported. A cooperative launch must fit the resident-grid limit (blocks ≤ occupancy × SMs); a persistent design should launch ≤1 cooperative grid sized from `cudaOccupancyMaxActiveBlocksPerMultiprocessor`, not an arbitrary grid.
- A simpler non-cooperative persistent kernel (few blocks spinning on a flag in mapped host-pinned memory) needs no special support and is the lower-risk v1: it demonstrably fits the execution model (spin + atomic flag is exactly what the probe's second kernel shape was written for, though only the cooperative/managed paths were executed).
- Costs/unknowns: a spinning kernel permanently occupies its SMs (of only 20), burns power/heat on a passively-constrained SoC, and can starve the very models it is meant to schedule. Long-duration behaviour (hours, thermals, any Tegra watchdog/preemption) is **untested** — needs a soak test before claiming "resident forever."

### 2. NVRTC runtime compilation for sm_110 — FEASIBLE, proven above
- NVRTC 13.2 present, `compute_110` compiles clean at runtime. The hot-swap loop in the seed (compile candidate → shadow-test → swap) has a real compiler to stand on.
- Prefer emitting PTX for `compute_110` first (forward-compatible, driver JIT) and only chase CUBIN/`sm_110`-exact output once a kernel actually needs arch-specific features (e.g. specific Blackwell/Tensor-Core intrinsics, NVFP4 paths — unverified via NVRTC here).

### 3. Shadow stream + host atomic swap — FEASIBLE, but reframe what "swap" means
- `concurrentKernels=1`; multiple CUDA streams genuinely run concurrently, so Stream A (production) + Stream B (shadow benchmark of a candidate kernel) is sound — provided the persistent/production work leaves SM headroom for Stream B, otherwise the "shadow" measurement is just contention.
- The host-side `AtomicPtr::swap` in the seed is trivially real in Rust — but it swaps a *pointer the host reads at launch time*. It does **not** retarget a kernel already resident on the GPU. Honest v1 semantics: (a) between launches, host atomically swaps the `CUfunction`/module handle used for the next launch — zero-downtime at launch granularity; or (b) a persistent kernel polls a kernel-index/flag slot in mapped memory each iteration and branches to the selected in-device implementation — swap at iteration granularity, all variants compiled in (or loaded as device functions) up front. Claiming mid-kernel function-pointer splicing, as the email does, is not a CUDA feature.

### 4. Unified memory (`cudaMallocManaged`) on Thor — FEASIBLE, proven, one caveat
- Integrated SoC, single LPDDR5X pool shared CPU↔GPU: the seed's core premise (memcpy is waste) is correct here, and managed vadd with CPU-side initialisation ran correctly with no explicit prefetch.
- Support flags are as good as Thor gets: `concurrentManagedAccess=1`, `pageableMemoryAccess=1`, `unifiedAddressing=1`.
- Caveat: `directManagedMemAccessFromHost=0` — the host cannot directly dereference managed memory *while a kernel is concurrently accessing it* in the general case. For the rolling ring: use managed memory for bulk tensors (with `cudaMemPrefetchAsync`/`cudaMemAdvise` in the hot path and fault-cost measured), and **host-pinned mapped memory (`cudaHostAlloc` + mapped) for the small control/flag/lineage slots** that CPU and a persistent kernel touch simultaneously. Do not build the lock-free ring purely on managed allocations and assume zero-cost coherence.

### 5. CUPTI / RLEF telemetry — PARTIALLY FEASIBLE, metric names need correction
- CUPTI library/headers/samples are installed, so activity tracing, callback and range-profiler collection are available in principle.
- The seed's headline metric (`smsp__warp_issue_status_stalled_memory_dependency`, cache-hit %, register stalls) is **Nsight Compute (`ncu`) profiler terminology, not a CUPTI activity counter you can stream cheaply in-process**. `ncu` is present, but it is a replay-based, privileged profiler — wrong shape for a continuous in-loop RLEF feed, and perf-counter access on Tegra/driver 595 is unverified. v1 telemetry should be timings the runtime measures itself (per-kernel durations via CUDA events, ring occupancy, fault counts) and treat CUPTI/ncu as an offline diagnostic, not the live critique source.

### 6. Rust / cudarc build path — FEASIBLE
- Rust 1.99.1 stable aarch64 is installed and current. Build/run on the Thor itself is viable (no cross-compile needed).
- cudarc 0.19.x crates are already cached locally, which hints at prior fleet use, but: cudarc's CUDA-version feature gating vs CUDA 13.2 / sm_110, and its NVRTC wrapper coverage, are **unverified**. Lower-risk v1: thin direct FFI to `libcuda` (driver API) + `libnvrtc`, or pin cudarc, vendor it (`cargo vendor`), and prove a hello-kernel through it before building on it. Either way, vendor — do not depend on network fetch at build time on the Thor.

## Risks / unknowns

1. **Persistent-kernel soak**: thermals, power, SM starvation of co-resident models, and any long-run preemption/watchdog on Tegra — untested; needs an hours-long burn-in with temperature logging before "always resident" is claimed.
2. **Perf-counter access**: whether CUPTI range profiling / `ncu` can collect SM metrics on this driver/Tegra without elevated privileges or a driver setting — unverified; do not architect v1 around live stall metrics.
3. **Managed-memory fault costs in the hot loop**: correctness proven, latency not measured. First-touch and migration faults could destroy the µs-scale stagger budget; ring design needs prefetch/advise + measurement, and control slots on pinned mapped memory (see §4).
4. **Cooperative-grid ceiling**: grid-sync designs are capped by cooperative occupancy (20 SMs); a perception+decision+diffusion cooperative grid may not fit — phase-interleaved *separate* launches/streams (the email's title idea) sidestep this and are the safer v1.
5. **cudarc vs CUDA 13.2**: version/feature compatibility unverified; raw driver-API FFI is the fallback and arguably the better v1.
6. **NVRTC arch-specific features**: plain `compute_110` PTX proven; NVFP4/WMMA intrinsics, cooperative-groups device code, and CUBIN output via NVRTC are not yet probed.
7. **GPU contention with Casey's own Thor work**: the box is actively used (35 GiB RAM used at probe time, resident models/agents). Any resident kernel competes with his work; the repo's runtime must be explicitly start/stop, small-footprint by default, and never auto-started.
8. **Numbers in the seed email are not a spec**: <100 ns warp catch, sub-µs gating, "2,070 TFLOPS" sustained — none measured here or there; treat all latency claims as hypotheses to bench (CUDA events + `nsys`), starting from the stagger/interleave claim, which is the one worth testing first.

## Bottom line

The real, buildable core is feasible on this exact box today: Rust 1.99 + NVRTC 13.2 compiling for `compute_110`, managed/pinned unified-memory ring, phase-interleaved launches across streams, between-launch (or per-iteration flag) kernel swapping, and self-measured timing telemetry. The parts to drop or demote from the seed: sheaf-Laplacian "enforcement" (a clamp), PIR lineage (wrapping u64 modulo), mid-kernel pointer splicing, CUPTI stall metrics as a live RLEF feed, and all `sm_100/sm_101` targets — Thor is `sm_110`, and that path is now compile- and run-proven.
