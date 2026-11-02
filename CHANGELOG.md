# Changelog

All notable changes to rolling-perception are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [SemVer](https://semver.org/) once the repo is public.
Measured numbers appear only with the machine and method that produced
them — the repo rule: no claim without a test or a bench number.

## [Unreleased] — Confluence slices 1–3, 2026-11-01 (evening)

### Added
- **The Confluence spec** (`docs/SPEC-STREAM-PLATFORM.md`) + Amendment 1
  (thin devices first-class; one wiring model for the technician;
  converters are the platform's problem) + Amendment 2 (presence),
  and two refereed adversarial panel rounds (`docs/SPEC-PANEL-1.md`,
  `slice2/SPEC-PANEL-2.md`; raws in `docs/panel-1/`, `slice2/panel-2/`).
- **Slice 1** (`slice1/`): `confluence-watch` live service (parity-tested
  against the batch pipeline), console with a working corrections
  button, technician install pack (dry-run-first). Acceptance: staged
  cut 16/16 tiles in 3.35 s, object exactly {5,6} in 0.39 s, drift
  silent, spend 11.8% of embed-everything.
- **Live camera + 48 h soak** (`slice1/PROART-CAMERA.md`): the ProArt
  webcam feeds the watch by outbound push (Windows firewall blocks
  inbound); gate 3.0 night-calibrated, 0 steady-state nominations in
  1,199 frames. Soak runs 2026-11-01 18:18 → 2026-11-03 18:18 AKST.
- **Slice 2** (`slice2/`): NVENC bench (sessions don't cap; aggregate
  encode-fps ~580–640 does; V4L2 H.265 2.5–3.5× cheaper than ffmpeg
  nvenc), brain bench (Qwen3-Coder-30B already on disk wins the
  presence seat), presence v1–v3 (resident Piper: TTS 1,974 → 287 ms;
  verdict-only grounding; digest v2; deterministic claim checker),
  player spike (remux-first HLS, encode-fps budget with 429 refusal,
  frame-counter watchdog).
- **Slice 3** (`slice3/`): backfill pass 1+2 (234 real items shelved;
  the house's video holding is 65.9 s) and the synthesiser experiment
  (engine beats sampler at every reader lag, 8–18×; snap rule v2:
  3× against a decontaminated band recovers a reversal in 2.0 s with
  zero false snaps).
- **Reading guide + results ledger** (`docs/READING-GUIDE.md`,
  `docs/RESULTS.md`).

### Honest negatives kept on the record
- Panel round 2's prompt-cache design failed (per-model caching;
  one question per model) — round 3 owes ≥2 questions per model.
- The diff gate remains a ranker, not a separator; Jev remains
  advisor-only; presence has never been used by a human (all voice
  acceptance is synthesised-speech fixtures).

## [Wave 3] — first real workload: harbor-watch, 2026-11-01

### Added
- `crates/harbor-watch` — rolling visual change detection over real
  I-JEPA tile embeddings, full 1280-dim on the substrate rings
  (perceive → decide → direct → refine → publish), 8 tests including
  the refine ablation (fixture precision 0.60 → 1.00, recall 1.00)
  and the stale-score publish rule a failing test forced.
- **The wave-3 run** (`docs/WAVE3.md`, data in `experiments/wave3/`):
  real frames on the Thor through its own JEV rack. Diff-gating spent
  312 embeds vs ALL's 576 (−54% rack time; gradual turntable kept
  23/192). Cuts sequence: every cut flagged 16/16 tiles on the frame
  it landed; frame verdicts agree 1.0000 between strategies. Audit
  keeps the gate honest: it is a ranker (skipped drift 0.20 vs
  embedded 0.48), not a separator.
- HTML report tool (`experiments/wave3/report/`) — verdicts a human
  can open: frames with changed tiles overlaid, scoreboard vs truth.
- The reflective Jev lane (`experiments/wave3/jev/`), measured after
  the TypeSafe credential was reconnected: 15/15 calls, p50 0.47 s;
  Jev alone P=0.750/R=1.000, as tie-breaker it *lowered* the refined
  pipeline's perfect score, as gate it changed nothing. **Verdict:
  Jev earns the recorded-advisor seat, not the gate** — the sheaf
  refine is what fixed the false positives.
- Footprint note: the JEV rack was started for the run and stopped
  after — verified inactive. Nothing in wave 3 is resident.

## [0.2.0] — wave 2 (v0.2 spikes + integration), 2026-11-01

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
