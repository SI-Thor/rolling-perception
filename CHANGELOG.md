# Changelog

All notable changes to rolling-perception are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [SemVer](https://semver.org/) once the repo is public.
Measured numbers appear only with the machine and method that produced
them — the repo rule: no claim without a test or a bench number.

## [Unreleased] — wave 2 (v0.2 spikes + integration), 2026-11-01

### Added
- Tested quickstart (literal follow-through on the Thor: 9 doc failures
  found and fixed, second literal pass green), this changelog, a
  `results/` layout for measured runs, and a GitHub Actions workflow
  (x86_64 + aarch64 `cargo test`).
- `crates/cuda-thor` — **v0.2 Spikes 1+3 pass on the Thor.** NVRTC from
  Rust (thin FFI, no cudarc) compiles the perceive filter for
  compute_110 in 20–24 ms, bit-exact vs the CPU reference; 1,000/1,000
  launch-boundary module swaps verified with epoch retirement
  (`results/thor/2026-11-01-spike1-3.txt`). Root-cause find worth the
  spike: driver-API symbols need their `_v2` link names from Rust FFI.
- **Spike 2** (`results/thor/2026-11-01-spike2.md`): two-stream shadow
  arrangement is the recommended default; the persistent kernel loses
  for slice work (compute 9–27× slower — resident-grid starvation) and
  stream priorities have no effect. Both negatives stand as results.
- Persistent-kernel **soak: 600.1 s**, 5,981 requests, exact buffer,
  clean stop, GPU peak 46.4 °C at ~8–9 W (logs in
  `experiments/thor-cuda/spike2/`).
- `crates/rolling-pipeline` — integrated five-stage cascade through the
  real substrate rings (lineage = all stages exactly once, gating saved
  71.9% of perceive ops by counter, sheaf energy 132.75→95.97) plus a
  file-replay trace producer that reproduces synthetic runs exactly.
- `crates/rolling-adaptive` — lens-calibrated adaptive staggering:
  prediction p95 1,669 µs vs 854,285 µs (fixed) under jitter+drift;
  exact tie at zero jitter, stated in the README.
- Workspace is now 5 crates, **44 tests**, zero warnings.

## [0.1.0] — 2026-11-01

First assembled version. Commit `d528ba5` on `main`
(private repo `SI-Thor/rolling-perception`; initial commit `0471ea6`
was the auto-init README). Distilled from Casey's seed email
*"Rolling perception [muse]"* (2026-11-01): of ~15 distinct ideas in
5,318 lines, what survived grading against the actual hardware is here;
what failed is documented as drops, not silently forgotten.

### Added
- `PLAN.md` / `DESIGN.md` — keep/fix/drop grading of all 15 seed ideas,
  v0.1/v0.2 scopes, non-goals, invariants, failure modes, and a
  pre-committed acceptance gate (if rolling loses its home scenario,
  the negative result is the result and v0.2 is cancelled).
- `crates/rolling-perception` — batched vs rolling schedulers on
  identical lanes/work (perception → decision → attention-director →
  one diffusion step, plus a PCM audio lane), std-only, **6 tests**.
  Bench: TTFO 243.5 µs rolling vs 2,528.6 µs batched at 400 µs stagger
  (10.39×), checksums identical (Δ = 0.000000).
- `crates/rolling-substrate-core` — Disruptor-style 64-byte-aligned
  lock-free ring (multi-producer claim protocol), real graph-Laplacian
  consistency (energy `sᵀLs`, gradient step), lineage as visited-bitmask
  + saturating counts, ROI gating with exact skip counts; **23 tests**.
  The seed's PIR prime-product is kept only as a fenced autopsy, with a
  test demonstrating its u64-wrap false positive (3⁴³ mod-wrap makes
  prime 5 "divide" a history it was never in).
- `experiments/thor-cuda/` — four CUDA experiments + `PLAYLOG.md`:
  rolling vs batched GPU streams (first output **5.74 ms vs 21.41 ms**,
  3.7×; total completion unchanged); NVRTC hot-swap for compute_110
  (compile 54/30 ms off-path, swap at launch granularity); persistent
  kernel via pinned mapped memory (300 requests, one launch,
  **4.8 µs mean request→ack**, clean flag stop); viewport gating
  (early-exit blocks 1.3× vs launch-shaped grid **192×**, sentinel-
  verified zero outside-ROI touches). PLAYLOG also records the bench
  bug that lied (host-observation timestamps) and how it was caught.
- `docs/FEASIBILITY.md` — measured Thor platform probe: capability
  11.0 (sm_110), CUDA 13.2 / NVRTC `compute_110` compile PASS, Rust
  1.99.1, CUPTI present (stall metrics identified as ncu replay
  metrics — v1 telemetry is self-measured).
- `docs/THOR-VERIFICATION.md` — workspace run natively on the Thor:
  **29/29 tests pass on aarch64**, bench checksum `345101.1999`
  bit-identical to x86_64, Thor CPU TTFO ratio 15.78×.

### Dropped from the seed (with reasons in PLAN.md)
- Sheaf "enforcement" as a clamp (replaced by a real Laplacian),
  PIR prime-product lineage (overflow/count/order failures),
  mid-kernel function-pointer splicing (not a CUDA feature),
  `sm_100`/`sm_101` targets (Thor is sm_110), "<100 ns warp catch"
  (measured round trip is ~5 µs), CUPTI stall metrics as a live
  RLEF feed.
