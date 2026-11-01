# rolling-perception

**Status: PRIVATE — experimental, in active construction (2026-11-01).**
This repo graduates to public only when it is working and useful on our
AGX Thor and the documentation is polished (the SI-Thor rule).

Rolling perception is the honest rebuild of a seed idea: *don't batch the
world into frames.* Sensors and model stages become ready at staggered
times; a system that processes each stage as it lands and emits an output
per stage completion perceives a **continuous stream** instead of a
stepped sequence — with measurably earlier first outputs for identical work.

## What is proven, and where (all numbers measured, none simulated)

| Claim | Where | Result |
|---|---|---|
| Rolling beats batched on time-to-first-output, same work | `crates/rolling-perception` (CPU, std-only Rust) | TTFO 243 µs vs 2,529 µs at 400 µs stagger (**10.4×**); 35× at 2 ms stagger; 2.9× at zero stagger. Checksums identical (Δ = 0). 6/6 tests pass. |
| Same claim on the GPU | `experiments/thor-cuda` exp1 | Rolling outputs at 5.74 / 11.04 / 16.32 / 21.28 ms vs batched's single 21.41 ms (**3.7×** earlier first output). Total completion unchanged — a continuity win, not throughput. |
| Runtime kernel compilation + swap (sm_110) | exp2 | NVRTC compile 30–54 ms off-path, swap at launch granularity, outputs verified. No mid-kernel splicing — that claim is dropped. |
| Persistent kernel as tick substrate | exp3 | One launch, 300 requests via pinned mapped memory, **4.8 µs mean request→ack**, mid-run behaviour swap exact, clean stop. |
| Viewport gating | exp4 / exp4b | Early-exit blocks: 1.3×. Grid launched only over the ROI: **192×**, sentinel-verified zero outside touches. The gate decides what is *launched*. |
| Thor feasibility (sm_110, NVRTC, CUPTI, Rust) | `docs/FEASIBILITY.md` | All measured on the box: capability 11.0, CUDA 13.2, Rust 1.99.1. CUPTI stall metrics are ncu replay metrics — telemetry here is self-measured. |

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
- `experiments/thor-cuda` — the Thor play session, sources + `PLAYLOG.md`
  (including the bench bug that lied, and how it was caught).
- `docs/FEASIBILITY.md` — what the Thor actually supports, measured.

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
