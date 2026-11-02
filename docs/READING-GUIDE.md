# Reading guide — where everything is, and the order to read it

This repo grew in one long day (2026-11-01) from a seed email into a
working stream platform. It is organised the way it was built: the
engine first, then the workload, then the product. This guide is the
map Casey asked for — everything pushed, nothing held back locally.

## The story in five stops

1. **The seed and the honest rebuild** — `PLAN.md` grades the original
   proposal keep/fix/drop; `DESIGN.md` is the architecture that
   survived grading. `docs/FEASIBILITY.md` + `docs/THOR-VERIFICATION.md`
   record what the Thor (sm_110, 20 SMs) actually does, measured.
2. **The engine** — `crates/` (see *Crates* below) and `docs/WAVE3.md`:
   rolling vs batched, the substrate rings, NVRTC hot-swap from Rust,
   adaptive staggering, and the first real workload.
3. **The product spec** — `docs/SPEC-STREAM-PLATFORM.md` (**Confluence**:
   a Thor as back-end superpower for thin devices; every stream a
   cell; budgets in embed-seconds and encode-fps), amended by
   `docs/SPEC-AMENDMENT-1.md` (thin devices first-class; one wiring
   model for the technician; converters are the platform's problem —
   *a translation becomes a conversion*) and
   `docs/SPEC-AMENDMENT-2.md` (presence: any browser lends its senses
   to the Thor).
4. **The adversarial panels** — `docs/SPEC-PANEL-1.md` and
   `slice2/SPEC-PANEL-2.md`: four cheap outside models attack the
   spec; a referee accepts/refuses each point. Raw answers live in
   `docs/panel-1/` and `slice2/panel-2/`. Round 1 cost $0.034,
   round 2 $0.054 — and round 2's cache design failed honestly
   (caching is per-model; one question per model never reuses a
   prefix), which is recorded rather than hidden.
5. **The measured results** — `docs/RESULTS.md`: every headline
   number in one ledger, each pointing at its source document,
   with the deficits section kept as prominently as the wins.

## Slices (the build, in the order it landed)

- `slice1/` — **live change feed**: `core/` is `confluence-watch`
  (Rust; live ingest → tile diff-gate → I-JEPA embeds → verdict
  ledger with health heartbeat), `console/` the one page (feed,
  shelf, corrections), `install/` the technician's pack.
  `slice1/README.md` is the record; `slice1/PROART-CAMERA.md` is the
  live-camera chapter: the ProArt webcam feeding the watch by
  outbound push, and the **48 h soak running from 2026-11-01
  18:18 AKST** (verdict due 2026-11-03).
- `slice2/` — **presence + serve**: `presence/` (browser terminal:
  hold-to-talk → STT → ledger-grounded brain → resident Piper;
  v3 adds a deterministic claim checker), `player/` (remux-first
  HLS with an encode-fps budget and a frame-counter watchdog),
  `NVENC-BENCH.md` (the bench that inverted the panel's premise:
  sessions never cap; aggregate encode-fps does), `BRAIN-BENCH.md`
  (every chat model already on the Thor's disk, scored; the winner
  was already owned).
- `slice3/` — **the library + the engine layer**: `BACKFILL-PASS1.md`
  (234 real items shelved; the house's whole video holding is
  65.9 s), `synth/` (the synthesiser experiment: maintained world
  state beats held samples 8–18× for late readers; snap rule v2
  with a decontaminated band).

## Crates (the engine, 55 workspace tests)

| crate | what it is |
|---|---|
| `rolling-substrate-core` | Disruptor rings, real graph Laplacian, bitmask+counts lineage, ROI gating |
| `rolling-perception` | batched vs rolling, identical work — the 10.39× TTFO measurement |
| `rolling-pipeline` | the five-stage cascade running through real rings |
| `rolling-adaptive` | lens-calibrated stagger; prediction p95 1.7 ms vs 854 ms under drift |
| `cuda-thor` | NVRTC-from-Rust on sm_110; 1,000/1,000 launch-boundary swaps |
| `harbor-watch` | wave 3: real frames, I-JEPA tile embeds, diff-gating, sheaf refine |
| `slice1/core` | `confluence-watch`, the live service built on harbor-watch |

## The rules of this repo

- **No claim without a test or a bench number.** Simulated numbers
  never share a table with measured ones.
- **Document the process in the body of the work** — decisions,
  dead ends, the moment a rig lied and how it was caught. A result
  without its process is a claim, not a record.
- **Deficits first.** Every results document carries its failures
  at the same prominence as its wins (see `docs/RESULTS.md`).
- The repo is **private until Casey calls the graduation**: working
  and useful on the Thor, docs polished, then public.
