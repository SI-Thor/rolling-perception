# rolling-perception

**Status: PRIVATE — experimental, in active construction (2026-11-01).**
This repo graduates to public only when it is working and useful on our
AGX Thor and the documentation is polished (the SI-Thor rule).

Rolling perception is the honest rebuild of a seed idea: *don't batch the
world into frames.* Sensors and model stages become ready at staggered
times; a system that processes each stage as it lands and emits an output
per stage completion perceives a **continuous stream** instead of a
stepped sequence — with measurably earlier first outputs for identical work.

## Prerequisites

- **Rust, stable, edition 2021** (developed/tested on rustc 1.99.1; any
  recent stable should work). No external crates — std only, so no
  network fetch is needed to build.
- **For the CUDA experiments only:** an NVIDIA AGX Thor (sm_110) with
  CUDA 13.2 (`nvcc`). The Rust workspace builds and tests anywhere,
  including x86_64.

## Quickstart (tested literally on the Thor — see QUICKSTART-TEST notes)

On the Thor over SSH, `cargo` and `nvcc` are **not on the default
(non-login) PATH**. Set this first, or every command below fails with
`command not found`:

```sh
export PATH=$HOME/.cargo/bin:/usr/local/cuda/bin:$PATH
```

From the **repository root**:

```sh
cargo test --release
# expect: 52 passed total — 6 (rolling-perception) + 23 (rolling-substrate-core)
#         + 6 (rolling-pipeline: 3 unit + 3 integration) + 6 (rolling-adaptive)
#         + 3 (cuda-thor CPU reference; its GPU tests need the Thor, see crates/cuda-thor)
#         + 8 (harbor-watch, the wave-3 real-workload crate)

cargo run --release -p rolling-perception -- --cycles 120 --stagger-us 400
# expect two lines (batched, rolling) ending with:
#   ttfo ratio (batched / rolling): <roughly 3x-16x, machine-dependent>
#   checksum delta |batched - rolling|: 0.000000
# Both schedulers' checksum is 345101.1999 on x86_64 and aarch64.
```

Scope, because the same words do different things in different folders:
`cargo test` at the root tests **all** crates (52 tests); inside
`crates/rolling-perception/` it tests 6; inside
`crates/rolling-substrate-core/` it tests 23. `cargo run` needs
`-p rolling-perception` at the root (or run it from that crate's folder).

### CUDA experiments (Thor only)

```sh
cd experiments/thor-cuda
nvcc -O2 -arch=sm_110 exp1_rolling_vs_batched.cu -o exp1 && ./exp1
nvcc -O2 -arch=sm_110 exp1b_small_lanes.cu     -o exp1b && ./exp1b  # exp1, small-lane regime
nvcc -O2 -arch=sm_110 exp2_nvrtc_swap.cu -o exp2 -lnvrtc -lcuda && ./exp2
nvcc -O2 -arch=sm_110 exp3_persistent.cu -o exp3_persistent && timeout 60 ./exp3_persistent
nvcc -O2 -arch=sm_110 exp4_gating.cu       -o exp4  && ./exp4   # gating, early-exit blocks
nvcc -O2 -arch=sm_110 exp4b_gating_grid.cu -o exp4b && ./exp4b  # gating, launch-shaped grid (the 192x version)
```

`exp3_persistent` is safe to run: it serves 300 requests and stops
itself via its stop flag (about 1.6 ms of work); the `timeout 60` is a
belt-and-braces guard, and each experiment leaves nothing resident.
What each experiment means, and the numbers to expect, are in
`experiments/thor-cuda/PLAYLOG.md`. Formal run records live in
`results/` (see `results/README.md`); release notes in `CHANGELOG.md`.

## What is proven, and where (all numbers measured, none simulated)

| Claim | Where | Result |
|---|---|---|
| Rolling beats batched on time-to-first-output, same work | `crates/rolling-perception` (CPU, std-only Rust) | TTFO 243 µs vs 2,529 µs at 400 µs stagger (**10.4×**); 35× at 2 ms stagger; 2.9× at zero stagger. Checksums identical (Δ = 0). 6/6 tests pass. |
| Same claim on the GPU | `experiments/thor-cuda` exp1 | Rolling outputs at 5.74 / 11.04 / 16.32 / 21.28 ms vs batched's single 21.41 ms (**3.7×** earlier first output). Total completion unchanged — a continuity win, not throughput. |
| Runtime kernel compilation + swap (sm_110) | exp2 | NVRTC compile 30–54 ms off-path, swap at launch granularity, outputs verified. No mid-kernel splicing — that claim is dropped. |
| Persistent kernel as tick substrate | exp3 | One launch, 300 requests via pinned mapped memory, **4.8 µs mean request→ack**, mid-run behaviour swap exact, clean stop. |
| Viewport gating | exp4 / exp4b | Early-exit blocks: 1.3×. Grid launched only over the ROI: **192×**, sentinel-verified zero outside touches. The gate decides what is *launched*. |
| Thor feasibility (sm_110, NVRTC, CUPTI, Rust) | `docs/FEASIBILITY.md` | All measured on the box: capability 11.0, CUDA 13.2, Rust 1.99.1. CUPTI stall metrics are ncu replay metrics — telemetry here is self-measured. |
| NVRTC from Rust + swap (v0.2 Spikes 1+3) | `crates/cuda-thor`, `results/thor/2026-11-01-spike1-3.txt` | Compile for compute_110 in 20–24 ms from Rust FFI; output **bit-exact** vs CPU reference. **1,000/1,000 launch-boundary swaps verified**, epoch retirement, no leak (structural gate — cuMemGetInfo swings ±150 MB on this shared box, so a byte-exact leak gate is unmeasurable and is not claimed). Control: sm_100 *PTX* runs (forward-compatible); sm_100 *CUBIN* fails, error 209. |
| Launch vs shadow vs persistent (v0.2 Spike 2) | `results/thor/2026-11-01-spike2.md` | Launch pickup p50 1.1 µs. **Two-stream shadow is the recommended default** (same pickup, better wall: 3.6→3.0 ms big slices). Persistent kernel *loses* for slice work — its compute runs 9–27× slower (resident-grid starvation); its niche is the tiny-buffer ack path. Stream priorities: **no effect** (medians identical to 0.01 ms) — not a design dependency. |
| Persistent soak, 10 min (Spike 2) | `experiments/thor-cuda/spike2/` | 600.1 s, 5,981 requests, buffer exact, clean flag stop, process verified gone. GPU 39→46 °C peak, ~8–9 W. Ack p50 5.4 µs at a realistic 100 ms cadence, p95 1.83 ms — the tail is reported, and a foreign all-core CPU burn mid-soak is attributed, not hidden. |
| Integrated cascade end-to-end | `crates/rolling-pipeline` | perceive→decide→direct→refine→publish through real rings: published lineage = all 5 stages exactly once; gating saved **71.9%** of perceive ops (counted); sheaf energy 132.75→95.97; file-replay reproduces the synthetic run exactly. |
| Lens-calibrated adaptive stagger | `crates/rolling-adaptive` | Per-lane LensFile (period/jitter/phase self-model as text). On jitter+drift traces: prediction p95 **1,669 µs vs 854,285 µs** fixed (fixed stagger's error compounds under drift); jitter-only: 11.4× and freshness 32%→57%. On zero-jitter traces: **exact tie** — stated, not spun. |
| **Real workload: harbor-watch (wave 3)** | `crates/harbor-watch`, `docs/WAVE3.md`, `experiments/wave3/` | Real frames perceived by the Thor's own I-JEPA (p50 173 ms/embed): diff-gating spent **312 embeds vs 576** (−54% rack time) and follows ground truth per sequence (gradual turntable: 23/192 kept). Through the Rust cascade: **every scene cut flagged 16/16 tiles the frame it landed**; gradual rotation near-silent (2/192); frame verdicts agree between strategies 1.0000 on the cuts sequence. The gate is a ranker, not a separator (audit: skipped drift 0.20 vs embedded 0.48) — stated in `docs/WAVE3.md`, with the reflective Jev layer honestly unmeasured (credential). |

## Layout

- `PLAN.md` — the real plan: keep / fix / drop grading of every seed idea,
  v0.1 / v0.2 scopes, non-goals, and a pre-committed acceptance gate
  (if rolling loses its home scenario, the negative result is the result).
- `DESIGN.md` — module layout, slot protocol, invariants, failure modes.
- `crates/rolling-perception` — CPU scheduling experiment (batched vs
  rolling on identical lanes/work, plus the PCM audio lane).
- `crates/rolling-substrate-core` — lock-free ring, real Laplacian
  consistency, bitmask+counts lineage (with the seed's PIR kept as a
  fenced autopsy), ROI gating.
- `crates/rolling-pipeline` — the integrated cascade: all five stages
  wired through the substrate rings, director deadband policy feeding
  the next tick's gate, file-replay trace producer.
- `crates/rolling-adaptive` — lens-calibrated adaptive staggering vs
  fixed stagger on identical jittered/drifting traces.
- `crates/cuda-thor` — v0.2 GPU executor (feature-gated, Thor-only):
  NVRTC-from-Rust, launch-boundary module swap with epoch retirement.
- `crates/harbor-watch` — wave 3: the first real workload. Rolling
  change detection over real I-JEPA tile embeddings at full 1280-dim
  on the substrate rings; see `docs/WAVE3.md`.
- `experiments/wave3/` — the wave-3 driver (Thor, JEV rack), the
  reflective-judge lane (TypeSafe Jev — runner ready, unmeasured),
  and the HTML report tool that renders verdicts for a human.
- `experiments/thor-cuda` — the Thor play session, sources + `PLAYLOG.md`
  (including the bench bug that lied, and how it was caught), plus the
  Spike 2 sources and soak logs.
- `results/` — dated, measured run records (`results/README.md` is the index).
- `docs/FEASIBILITY.md` — what the Thor actually supports, measured.
- `CHANGELOG.md` — release notes, including what each wave actually proved.

## The rule

No claim without a test or a bench number attached. Simulated numbers
never share a table with measured ones. Process is documented in the
body of the work as it happens (`PLAYLOG.md`, PLAN §0).

## Source

Distilled from Casey's seed email *"Rolling perception [muse]"*
(2026-11-01) — a 5,318-line multi-generation LLM chain. Roughly 15% of it
was distinct ideas; this repo is what survived grading against the
hardware. Seed claims that failed grading (sheaf clamp, PIR lineage,
mid-kernel pointer splicing, sm_100 targets, <100 ns warp catch) are
documented as drops in `PLAN.md`, not silently forgotten.
