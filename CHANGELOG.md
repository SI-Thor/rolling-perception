# Changelog

All notable changes to rolling-perception are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [SemVer](https://semver.org/) once the repo is public.
Measured numbers appear only with the machine and method that produced
them — the repo rule: no claim without a test or a bench number.

## [Unreleased] — extraction rulings, 2026-11-02

- EXTRACTION-PLAN §10: Casey's five answers recorded — standalone
  name (not Confluence), new repo with clean history, third-party
  parts behind seams with bring-your-own docs (never incorporated
  under restrictive terms), configurable grid with the 4x4 default's
  measured rationale documented, permissive dual licence confirmed.

## [Unreleased] — extraction plan for the change-ledger core, 2026-11-02

- docs/EXTRACTION-PLAN.md: the core defined by subtraction (11 IN /
  11 OUT; the JEV rack demoted to one adapter behind an embedder
  seam), dependency surgery, toolkit surface, composition-docs
  outline, proof battery, production-grade gap list (the frozen-
  feed freshness defect is the core's #1 blocker), five worked
  examples from real runs, and a 10-step publish checklist whose
  publish step waits for Casey's explicit word.

## [Unreleased] — presence from-the-chair acceptance PERFORMED, 2026-11-02

- The Amendment-2 headline test is closed: Casey held a spoken
  conversation with the Thor through the ProArt's browser against
  the live soak ledger; the reply grounded in that morning's real
  verdicts passed every fence untouched (record:
  slice2/presence/README.md). The path there named a product
  requirement: browsers deny the mic on plain-http LAN origins —
  presence must ship a certificate story, and the page must say
  so instead of failing silently when the context is insecure.

## [Unreleased] — polish round: blockers worked, 2026-11-02

From docs/audits/POLISH-BACKLOG.md (worked addenda recorded there):

- **Licences added** (blocker 2): LICENSE + LICENSE-MIT +
  LICENSE-APACHE at the root, Apache text diffed section-by-section
  against the canonical source; all 7 crates' fields verified.
- **Executor rationale corrected** (ENGINE major): the refusal is
  now `GpuNotBuilt`, carrying the measured crossover bound; the
  five closed API gaps are fenced as history, not cited as current.
- **Workspace hygiene**: `cargo fmt --all` applied, all 4 clippy
  warnings fixed (clippy `--workspace --all-targets` zero warnings,
  `fmt --check` clean, 107 tests green); `.gitignore` now excludes
  `__pycache__/`/`*.pyc`/`.env` (history scrub of already-tracked
  bytecode is scheduled with the public flip, noted in AUDIT-OPS).
- **Stale numbers corrected**: README/READING-GUIDE test counts;
  RESULTS' fMP4 row (original preserved as a dated correction) and
  the soak snapshot row fenced as point-in-time with its source.
- **Install pack made real** (blocker 1): install.sh builds and
  installs `confluence-watch` under its true name, generates units
  matching the real deployment, and says plainly what it cannot
  automate; guide + SERVICE-CARD rewritten to the console's real
  port/routes. Proven in a scratch prefix (INSTALL-PROOF.md):
  installed binary ran the bundled fixtures end-to-end — 34 embeds
  exactly as ground truth predicts, verdicts on the right frames
  and tiles, console serving the installed ledger. (The embed
  layer there is a fenced test double; I-JEPA verdict semantics
  remain acceptance.sh-on-Thor territory.)
- **Console verdict-feed defect FIXED** (found by the install
  proof): the feed ignored the watcher's `changed_tiles` rows and
  their µs timestamps, silently dropping real verdicts. The parser
  now surfaces both row shapes (17/17 HTTP checks incl. the
  corrections hardening: unknown ids and malformed JSON → 400).
  Deployment of the fixed console to the Thor is a post-verdict
  decision; the soak's record is the ledger, which was always
  complete.
- **Presence live for its human acceptance** (2026-11-02): the v3
  stack runs against the live soak ledger via a read-only rendered
  view; the machine-checked loop grounded its reply in real
  verdicts and passed the claim checker untouched. The
  from-the-chair human test is the remaining step.

## [Unreleased] — phase 2b: fixtures cold, fMP4 wired, findings filed, 2026-11-02

- **Rehearsal blocker S2 cleared**: cold fixtures are bundled
  (`slice1/core/fixtures/`, 3.35 MB, the project's own wave-3
  frames recovered from the report HTML), ingest paths resolve
  `--fixtures-dir` → `$CONFLUENCE_FIXTURES_DIR` → bundled set, and
  the hardcoded Thor-home literals are gone (explicit env override
  only). Cold proof under an empty `$HOME`: cut 16/16, object
  exactly {5,6}, drift silent, all 11 C landings 16/16 — at the
  gate/diff layer; the verdict layer remains rack-dependent and
  `acceptance.sh` on a Thor-class box runs these fixtures by
  default. The synthetic flat-gradient fallback was deleted, not
  left as a trap.
- **fMP4 is a production player mode** (slice2/player/): HEVC
  sources now serve fragmented-MP4 HLS by remux — **0 encode-fps
  charged**, `verify_fmp4.py` encodes the spike's 41-check
  validation and passes end-to-end (EXTINF sum exactly 60.000 s,
  1800/1800 packets); the "house is busy" refusal still binds
  transcodes only. Measured fence: this box's V4L2 decoder rejects
  VP9/AV1/MJPEG inputs (recorded in RESULTS.md), so the transcode
  branch's reachable set is narrower than its probe suggests.
- **Findings note received**: `docs/FINDINGS-CFC-JEPA-V2.md`
  (filed by a sibling lane at Casey's direction) — the judge's
  advisor seat now measured from two sides (7/12 on outcome pairs,
  2/6 under fluency traps); calibration creep named as its own
  phenomenon. The soak verdict (2026-11-03) now includes a
  calibration-ageing analysis of the soak ledger against finding 2.

## [Unreleased] — phase 2: proof sweep, rehearsal, fMP4, 2026-11-01 (night)

- **Proof sweep — four claims closed, two real bugs caught by the
  probes**: D9 PROVEN (the sheaf step now refuses non-finite input
  with `SheafError::NonFinite` before mutating — the probe had
  shown NaN spreading to neighbours and α=NaN returning plausible
  finite energies); D10 PROVEN (α validated at construction against
  a measured spectral bound, never clamped; the α=10 divergence is
  refused); P13 PROVEN (full replay bit-identity — the assertion
  first caught the trace writer's `{:.6}` formatting destroying
  float bits in 384/384 values; the writer now round-trips);
  P5 PROVEN (`Published` carries per-tile stale-by-gate marks with
  last-computed ticks, cell-by-cell pinned). ARCHITECTURE updated.
- **fMP4 spike — the serve plane's converter debt is closable**
  (slice2/player/fmp4-spike/): spec-conformant fragmented-MP4 HLS
  with H.265 is producible on the Thor today by GStreamer remux —
  no new software — at ~0.09 s per 60 s item vs any encode path.
  Verdict discipline: "spec-conformant by checklist + probe"; no
  Apple-client playback claim. Deviations (no `styp`, brands,
  GOP-length segments) recorded in the spike results.
- **Graduation rehearsal** (slice1/install/REHEARSAL-LOG.md):
  fresh-clone stranger walk, 7 stumbles, 6 doc fixes verified by
  re-running the corrected instructions. The seventh is a code
  blocker, logged with reproduction: **Slice-1 acceptance is not
  reproducible from the repo** — ingest sources read hardcoded
  paths in the Thor's home directory and the repo ships no image
  fixtures. Bundling cold fixtures + path parameterisation is the
  named follow-on.
- Workspace tests 95 → **107**.

## [Unreleased] — round 3: migration, the GPU API, and DESIGN amended, 2026-11-01 (night)

- **Cascade migrated to SpscRing**: all five inter-stage edges of
  rolling-pipeline are 1-producer/1-consumer queues and now run on
  `SpscRing` (Block); `ring_out` has zero consumers and stays a
  Disruptor latest-value publish point, cited in code. The proof
  the old ring could not pass: **1,000,000 messages, 125,000 wraps
  per ring, produced == consumed == 1,000,000, zero drops**; the
  20,100-tick bench checksum is bit-identical pre/post and the
  tick got faster (~2.7 → ~2.1 µs).
- **cuda-thor's generic surface shipped**: public `compile`,
  `Module::load_named`, typed `KernelArg` launch (`launch_args`),
  byte-level upload + async/pinned downloads, `Gpu::new_stream()`.
  Thor proof through the new API only: an f64 sheaf stencil,
  **Laplacian bit-exact (max err 0.0)**, smooth step 1.4e-17,
  launched on the second stream. ARCHITECTURE D13's five gaps are
  closed; filling the pipeline's GPU executor is now possible —
  and still bounded by the crossover math (no win below ~4,096
  nodes), so it remains unbuilt by choice, not by blockage.
- **DESIGN.md Amendment A**: §3.2/§3.4 rewritten to the measured
  record (both rings placed; DropNewest's original text recorded
  as unimplementable and repaired), originals preserved verbatim
  as superseded history; §4 gains the D11 proof note. ARCHITECTURE
  D1 resolved, D4 partial→proven-for-SPSC, §5 refreshed.
- Workspace tests 90 → **95**.

## [Unreleased] — round 2: the book's findings, settled, 2026-11-01 (night)

### Measured
- **The ring fork (docs/RING-BENCH.md)**: DESIGN §3.2's `SpscRing`
  built as written. It beats the shipped Disruptor on speed
  (6.7–11.4 vs 2.6–5.6 M msgs/s; ping-pong 0.35–0.82 vs 1.47–1.58 µs)
  — and the shipped ring, consumed as a queue (the only consumer
  its API offers), **tore 5–27% of 1M reads silently in every run**.
  Verdict: both, placed differently; queued use of the shipped ring
  is refuted. Two design defects logged: §3.4 DropNewest is
  unimplementable as written (repaired via a gap signal);
  DropOldest needs consumer revalidation.
- **Sheaf allocation closed**: `laplacian_apply_into` — zero
  allocations proven by a counting-allocator test, bitwise parity
  with the legacy path; 1.81× at 16 nodes, ≈1.0× at 1,024 (the
  allocation was allocator traffic, not math cost). ARCHITECTURE
  claim D11: contradicted → **proven**.
- **GPU executor: blocked, precisely** — cuda-thor's public API
  cannot compile/load/launch any kernel but the hardcoded
  `perceive` (five named gaps). The executor probes real hardware
  and refuses typed (`GpuApiGap`), Thor-verified; the crossover
  bound shows GPU refine cannot win below ~4,096 nodes anyway.
  The five API additions that unblock it are specified in the
  rolling-pipeline README.
- **Panel round 3** (docs/SPEC-PANEL-3.md, $0.1085): the cache fix
  works on 3 of 4 models (~98% of a ~31k-token prefix on call 2;
  MiMo cached 0 — budgeted uncached from now on). Q1's convergence
  is superseded for queue use by the ring bench (referee
  addendum in the synthesis). Graduation bar (Q4): the repo
  currently graduates as a reference implementation / design
  record, not yet as a stranger-ready tool.
- Workspace tests 75 → **90**.

## [Unreleased] — low-level round: connect + harden + the engine book, 2026-11-01 (night)

### Connected
- **Adaptive → pipeline**: `run_rolling_adaptive` drives the cascade's
  release timing from the lens (rolling-adaptive needed zero changes —
  its surface was already right). On the drift stream (period 400→675 µs)
  outputs are identical to the fixed-stagger baseline while lens release
  p95 is **60.5 µs vs the fixed control's 7,425.0 µs**.
- **Executor seam** (`crates/rolling-pipeline/src/executor.rs`): the
  contract a GPU two-stream-shadow backend must satisfy, a compiling
  `gpu-shadow` stub behind an off-by-default feature, and
  `src/bin/endtoend.rs` — one asserted end-to-end run of the whole engine.
- Workspace tests **55 → 75** (pipeline 6→12, substrate-core 23→32,
  cuda-thor 3→8).

### Fixed (hardening pass — `crates/*/HARDENING.md` has the full audit)
- **Release-mode out-of-bounds host read** in cuda-thor `DevBuf::upload`:
  its length check was `debug_assert_eq!`-only; a short host slice would
  have made `cuMemcpyHtoD` read past the allocation. Now a hard `Err`;
  `Module::launch` also validates extents at runtime.
- `Lease::finalize` counter divergence at the 2⁶⁴ boundary (debug panic /
  release wrap) → `wrapping_add`, wrap behaviour test-pinned.
- `Gpu::new` context-retain leak on a failure path; `Viewport::area`
  underflow on inverted viewports; `gated_apply` mis-gating above
  u32::MAX grid width; 4× `CString::new().unwrap()` on FFI paths.
- `Event::record` / `Module::launch` are now `unsafe fn` with # Safety
  contracts (they dereference caller stream handles); ~30 unsafe blocks
  carry SAFETY comments; both crates are clippy `-D warnings` clean and
  `#![warn(missing_docs)]`-clean (52 doc warnings cleared).

### Documented
- **`docs/ARCHITECTURE.md`** — the engine book: real `cargo tree` map,
  claim→proof tracing of 34 load-bearing claims (**10 proven, 13 partial,
  10 unproven, 1 refuted**), per-crate invariants ledger. Headline
  divergence, now on the record: DESIGN §3.2's SPSC acquire/release ring
  was never built — the shipped ring is a multi-producer Disruptor
  claim/finalize design; and the "allocation-free" sheaf step allocates
  a Vec per call (`laplacian_apply`).

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
