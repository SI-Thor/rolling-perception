# rolling-perception

A continuous perception substrate and stream platform for edge
hardware, built and measured on the NVIDIA Jetson AGX Thor. Batch
pipelines wait for a full frame — or a full set of stages — before
any work starts, and pay that wait on every cycle. Rolling
perception removes the wait: each stage processes its input as it
lands and emits output per stage completion, so the system perceives
a continuous stream instead of a stepped sequence of frames. For
identical work, first output arrives an order of magnitude earlier,
and the compute budget is spent only where the scene actually
changed.

## What it does

- **Rolling cascade (Rust).** A five-stage pipeline —
  perceive → decide → direct → refine → publish — wired through
  lock-free single-producer/single-consumer rings. Stages run as
  inputs land; nothing waits for a batch boundary. Output checksums
  are bit-identical to the batched schedule on both x86_64 and
  aarch64: rolling changes *when* results arrive, not *what* they
  are.
- **Hot-swappable GPU kernels (Thor).** CUDA kernels are compiled
  from Rust via NVRTC at runtime and swapped at launch boundaries,
  with epoch retirement of superseded modules. Two-stream shadow
  execution is the default scheduling mode.
- **Confluence stream platform.** A watcher service
  (`confluence-watch`) consumes camera streams on the Thor, embeds
  only the tiles whose content changed (diff-gating), and writes a
  text ledger of verdicts, state, and health. A web console renders
  the ledger, shows per-stream health with a heartbeat (a silent
  stream is reported as not-reporting, never as calm), and accepts
  human corrections. Work is budgeted in embed-seconds per stream.
- **Presence.** A browser lends the Thor its camera, microphone, and
  speaker; the Thor is the only mind. Spoken questions about the
  watched scene ("what changed in the last hour?") are answered from
  the ledger, and every factual claim in the answer is checked
  against the ledger by deterministic code before it is spoken.
  Nothing leaves the house.
- **Adaptive scheduling.** Per-lane timing self-models (period,
  jitter, phase) calibrate stagger and gating to each sensor's real
  cadence instead of a fixed frame clock.

## Measured results

All numbers below are measured on hardware; the full record, with
sources and deficits, is in `docs/RESULTS.md`.

| Measurement | Result |
|---|---|
| Time to first output, rolling vs batched (identical work) | 243.5 µs vs 2,528.6 µs — **10.39×** earlier |
| Output equivalence | Checksums bit-identical across schedules and across x86_64 / aarch64 |
| SPSC ring throughput | 6.7–11.4M messages/second |
| Cascade proof sweep | 1,000,000 / 1,000,000 frames published, zero drops |
| 48-hour live camera soak | 26.36 live hours recorded; gated embedding spend **4.43%** of embedding every frame |
| Diff-gating on real footage | Roughly half the embeddings of the ungated pipeline for the same verdicts |

## Architecture

- `rolling-substrate-core` — the SPSC ring (the cascade's only
  transport; an earlier queued design tore messages under load and
  was replaced), real Laplacian consistency checks, and bitmask
  lineage that records which stages touched each item.
- `rolling-pipeline` — the five-stage cascade over the substrate,
  with the director's gating decisions feeding the next cycle.
- `rolling-perception` — the scheduling core: batched vs rolling
  execution of identical lanes, used by the bench below.
- `rolling-adaptive` — lens-calibrated adaptive staggering.
- `cuda-thor` — NVRTC-from-Rust compilation and launch-boundary
  kernel swap for the Thor's sm_110 GPU.
- `harbor-watch` — change detection over real image embeddings
  (I-JEPA tiles): diff-gate, smooth, refine. The refine step is a
  sheaf-consistency pass; the semantic judge layer is advisory only
  and never gates.
- `slice1/core` (`confluence-watch`) — the production-form watcher
  service: ingest, gating, embedding, ledger, tenancy ladder (the
  watcher yields the shared GPU to foreign work in defined steps),
  and per-stream budget enforcement.
- `slice1/console`, `slice2/presence`, `slice2/player` — the Python
  services: ledger console, presence voice Q&A, and the budgeted
  HLS/fMP4 stream player.

The design documents live in `docs/`; `docs/ARCHITECTURE.md` is the
engine's reference and `docs/SPEC-STREAM-PLATFORM.md` specifies the
stream platform. `docs/ARCH-AGENT-COMMUNITY.md` is the top-level design
for the agent-community programme — one rolling percept of a shared
world, citizens drinking from it at earned temporal resolutions, and
System-Two smiths maintaining the repertoire — and `docs/CRAFTMIND-MAP.md`
maps the existing agent frameworks it builds on. `docs/READING-GUIDE.md`
maps the whole library.

## Quick start

The Rust workspace builds and tests on any machine (stable Rust,
edition 2021; the core crates are std-only). The GPU crates require
the Thor.

```sh
cargo test --release
cargo run --release -p rolling-perception -- --cycles 120 --stagger-us 400
# prints batched and rolling timings for identical work, ending with
# the time-to-first-output ratio and a checksum delta of 0
```

On the Thor over SSH, cargo and nvcc are not on the default PATH:

```sh
export PATH=$HOME/.cargo/bin:/usr/local/cuda/bin:$PATH
```

The watcher service runs from a config file (format and worked
examples in `slice1/`):

```sh
cargo run --release -p confluence-watch -- --config confluence-watch.conf
```

The Python services run under the Thor's ML environment; each has
its own README with exact configuration:

```sh
~/ml/.venv/bin/python slice1/console/app.py      # ledger console (web UI)
~/ml/.venv/bin/python slice2/presence/presence.py # presence voice Q&A, :8330
```

CUDA experiments (Thor only, sm_110, CUDA 13.2) live in
`experiments/thor-cuda/` with expected outputs in its `PLAYLOG.md`.

## telltape

The change-detection core of this platform has been extracted into
a standalone tool, **telltape**
(https://github.com/SuperInstance/telltape) — a single-purpose
watcher that indexes recorded or live footage into a queryable
change ledger, with an embedder seam that keeps the core
licence-clean. telltape is the hardened, separately versioned
extraction (v0.3.2) and is the recommended route for the
change-ledger capability on its own; this repository remains the
research platform it was extracted from.

## Repository map

- `crates/` — the Rust workspace crates listed above.
- `slice1/` — watcher service, console, install scripts, soak record.
- `slice2/` — presence voice Q&A and the stream player.
- `slice3/` — the synthesiser: maintained world state for late
  readers of a stream.
- `experiments/` — Thor CUDA experiments and workload drivers.
- `results/` — dated, measured run records.
- `docs/` — architecture, specification, results, and the study
  library (looped-model, weight-space, and auto-ontology studies
  among them).
- `PLAN.md`, `DESIGN.md`, `CHANGELOG.md` — design record.

## Status and limitations

This is a research platform, not a packaged product. The Rust
cascade, the watcher service, and the console have been run live
for days at a time on the Thor, including a 48-hour camera soak;
the presence loop has passed from-the-chair acceptance on the
hardware. Known limits, stated plainly:

- The diff-gate is a ranker, not a separator: it orders tiles by
  change likelihood under a budget; it does not guarantee a
  precision boundary. Per-stream precision depends on human
  corrections collected through the console.
- Presence currently runs over plain HTTP on the LAN; the
  certificate story for a packaged installer is not solved.
- The real-time, interruptible presence variant is designed
  (`slice2/presence/V4-DESIGN.md`) but not built.
- GPU components target the AGX Thor (sm_110) specifically; they
  are not portable CUDA.
- Several platform components (multi-stream reserved watching pool,
  automatic trust-based demotion of miscalibrated streams) are
  specified and partially built; see `docs/` for the state of each.

## Licence

Dual-licensed under either of MIT (`LICENSE-MIT`) or Apache-2.0
(`LICENSE-APACHE`), at your option.
