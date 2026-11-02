# EXTRACTION-PLAN — the change-ledger core as a standalone tool

Lane: EXTRACTION-DESIGN, 2026-11-02. Design only — no code was
moved, renamed, or built by this lane. Casey ruling (2026-11-02):
the unique core is the change-ledger engine; it is to be
boilerplated into a standalone tool + toolkit. Presence, player,
and console are proof-of-concept interfaces ON TOP of it, not the
product. Anti-bloat is binding: this plan designs **no new
features**. The two reconstruction options (archived embeddings,
change-frame snapshots) are ruled OUT of the tool — roadmap
options only, not designed here.

Deficits first, per house standard: the core is not standalone
today. It leans on one specific embedder service on one specific
box (§2 names every seam), its ledger trust loop is open (§7 G3),
and two of its modules carry no unit tests (§7 G4). What it has
is a measured record no comparable tool ships with (§8).

---

## 1. THE CORE, defined by subtraction

**The core is this, and only this:** a program that watches a
video stream — live or a file — and writes a structured,
append-only text ledger of *what changed, where in the frame,
when, and how strongly*, while spending expensive perception only
where a cheap diff says something moved. The footage itself is
never copied or kept: the ledger's timestamps and frame numbers
are a **seek index into footage the user keeps elsewhere** (an
NVR recording, a file on disk), so "show me everything that
happened" becomes "here are the 14 moments worth opening, and
where they sit in your recording." When nothing changes, the
ledger says nothing — and that silence carries its basis
(`health.txt`: the lane is alive, frames are arriving, the
embedder is answering), so *quiet* is distinguishable from
*dead*. Everything else this project built — voice, player,
console, shelf — is a reader of that ledger, and is not the tool.

Mechanics, as they exist today (no redesign): frames are tiled
4×4 (`crates/harbor-watch/src/record.rs`: `GRID = 4`, `TILES =
16`); a mean-abs pixel diff nominates tiles (ingest); nominated
tiles are embedded by an external embedder (today: I-JEPA,
1280-dim); the cascade scores each tile by cosine distance vs
its previous published embedding, takes ONE sheaf-Laplacian
smoothing step over the tile grid (a lone noisy tile is pulled
toward stable neighbours; a real multi-tile change is not),
and publishes a verdict only for tiles fresh this frame —
*a verdict is a claim about this frame; stale tiles publish
stable* (`crates/harbor-watch/src/pipeline.rs` publish stage,
the rule the wave-3 stale-score bug bought).

### IN — the core (11 entries)

| # | File / crate | What it is in the tool |
|---|---|---|
| 1 | `crates/rolling-substrate-core/src/substrate.rs` | Disruptor-style ring; every cascade payload physically transits it |
| 2 | `crates/rolling-substrate-core/src/sheaf.rs` | The Laplacian refine step, with the D9/D10 guards (`try_smooth_step` refuses non-finite input; α validated vs the measured spectral bound, never clamped) |
| 3 | `crates/rolling-substrate-core/src/spsc.rs` | The §3.2 SPSC ring — per-lane queue placement per verdict D12 |
| 4 | `crates/rolling-substrate-core/src/lineage.rs` | Bitmask + per-node counts lineage (the PIR replacement; the flawed prime scheme stays fenced as a counterexample) |
| 5 | `crates/harbor-watch/src/record.rs` | The record schema + std-only JSONL codec (`InputRecord`, `parse_record`, `record_to_json`) — the ingest↔cascade contract |
| 6 | `crates/harbor-watch/src/pipeline.rs` | The batch cascade — the reference semantics the live form is parity-tested against |
| 7 | `crates/harbor-watch/src/rng.rs` | Small support module; carries `cosine_distance`, the decide stage's score |
| 8 | `slice1/core/src/live.rs` | `LivePipeline`: the same cascade, frame-at-a-time, for live sources |
| 9 | `slice1/core/src/ledger.rs` | The ledger writer: `events.jsonl` (append-only) + `lens.txt` / `state.txt` / `health.txt`, the embed-second meter, coverage, spend ratio, `silence_meaningful` |
| 10 | `slice1/core/src/config.rs` + `src/main.rs` | Plain `key = value` config (technician-editable, no tooling) + the thin CLI entry (`--config <file>`, one-line JSON summary out) |
| 11 | `slice1/core/ingest/ingest.py` | Acquisition behind one interface (`shot` / `mjpeg` / `staged` / `wave3`), tiling, the µs diff gate, the embedder client (`Emitter`) |

Notes on the boundary, honestly drawn:

- `rolling-substrate-core` ships as a whole crate; its
  `gating.rs` (ROI gating) is library surface the watch cascade
  does not call. It is carried, not claimed as a core feature.
- `slice1/core/src/service.rs` is IN with surgery (§2): the
  frame-assembly loop is core; its rack-lifecycle block is not.
- `harbor-watch/src/fixture.rs` and `ablation.rs` are not
  runtime — they are proof machinery, and travel with the
  toolkit (§5), not the core.

### OUT — not the tool (11 entries)

| # | What | One-line reason |
|---|---|---|
| 1 | `slice2/presence/` (voice-to-voice, brain, Piper, claim checker) | A demo interface that *reads* the ledger aloud — proof the ledger is askable, not the technology |
| 2 | `slice2/player/` (HLS/fMP4 serve) | A serve demo; the tool's contract ends at the index, playback is the user's existing player |
| 3 | `slice1/console/` (FastAPI page, corrections button) | One projection of the ledger; the ledger is canonical, any UI is replaceable |
| 4 | `slice3/synth/` (synthesiser experiment) | A different idea (maintained world state for late readers) with its own record; not change detection |
| 5 | `slice3/backfill_pass1.py` + the shelf | Library-building over the house's files; the toolkit's file-index mode (§3) is the reusable residue |
| 6 | `slice1/install/` (install.sh, units, technician pack) | Site-specific packaging for one Thor + systemd + the fleet rack; a standalone install story is written against the extracted tool, not carried |
| 7 | `crates/cuda-thor/` | GPU research lane; the cascade is CPU and the measured crossover says GPU refine cannot win below ~4,096 nodes — a 16-tile grid never gets there |
| 8 | `crates/rolling-perception/` | The wave-1 rolling-vs-batched bench — the founding measurement, kept as history, not runtime |
| 9 | `crates/rolling-adaptive/` | The lens/stagger timing experiment; `confluence-watch` does not depend on it (its `Cargo.toml` names only harbor-watch + substrate-core) |
| 10 | `crates/rolling-pipeline/` | The generic executor framework + demo bins; the watch uses the harbor-watch cascade directly — extracting both would ship two pipelines |
| 11 | The JEV rack service itself, `thor-admit`, the ProArt Windows pusher, the Jev judge experiments (`experiments/wave3/jev/`) | Fleet/site machinery and an external provider: the rack becomes *one adapter* behind the embedder seam (§2); the judge measured advisor-only (P = 0.750 vs refine's 1.000) and earns no seat in the tool |

---

## 2. DEPENDENCY SURGERY — making it standalone

Every fleet dependency the core has today, and the seam that
replaces it. No behaviour changes; adapters and renames only.

### 2.1 The embedder seam (the one real dependency)

Today: `slice1/core/ingest/ingest.py`, `Emitter.embed()` —
hardcodes `POST {rack_url}/embed/image`, multipart field
`file` (tile as PNG), expects `{"embedding": [...]}`, and
asserts `len(emb) == 1280`. The Rust side is already innocent:
`LivePipeline::new(dim, …)` takes the dimension from the first
record, and `record.rs` treats the embedding as an opaque
`Vec<f32>` (`DEFAULT_DIM = 1280` is a constant, not a constraint).

Surgery, file-level:

- `ingest/ingest.py`: extract `Emitter.embed()` behind a small
  embedder interface — `embed(tile_png_bytes) -> (vector,
  embed_ms)` — with three adapters:
  - `JevRackEmbedder` — today's code, moved verbatim. The fleet
    rack becomes one adapter, no longer the definition.
  - `HttpEmbedder` — generic: URL, multipart field name, and
    response key from config. Covers any HTTP embedding service
    shaped like the rack's without code.
  - `OnnxEmbedder` — **new-thin**: local ONNX model via
    onnxruntime, no service at all. This is the stranger's
    zero-infrastructure path; it is an adapter, not a feature.
- The `assert len == 1280` becomes a config value (`embed_dim`,
  default 1280) checked against the adapter at startup, so a
  different embedder with a different width fails once, loudly,
  at start — not per tile.
- The test doubles already prove the seam's shape:
  `prove_fixtures.py` replaces exactly this one method with a
  recorder, and the install proof ran the full pipeline against
  a byte-hash double (34 embeds, exact verdicts — §5). Both
  become shipped adapters for tests (`FixtureEmbedder`), not
  lane tricks.

### 2.2 The rack lifecycle (fleet systemctl in the service loop)

Today: `slice1/core/src/service.rs` — `rack_health()` probes
`{rack_url}/health`; `systemctl()` runs `sudo -n systemctl
<action> jev-rack`; `run()` refuses to start unless the rack is
healthy, and stops it on exit iff it started it. That is fleet
tenancy policy welded into the tool.

Surgery:

- Delete `systemctl()` and the `jev-rack` name. Lifecycle
  becomes two config strings, `embedder_start_cmd` /
  `embedder_stop_cmd`, **empty by default** (start nothing, stop
  nothing; the box is left exactly as found — the current
  default behaviour for any embedder the tool didn't start).
- `rack_health()` generalises to an optional health URL from
  config; an in-process adapter (ONNX) reports healthy by
  construction. The service's refusal becomes: *no working
  embedder, no run* — the honest invariant, minus the fleet.
- Config renames in `slice1/core/src/config.rs`, with the old
  keys accepted as aliases for one release: `rack_url` →
  `embed_url`, `rack_autostart` → `embedder_autostart`,
  `stop_rack_on_exit` → `stop_embedder_on_exit`. The default
  `rack_url = http://127.0.0.1:8077` (the fleet rack's port)
  becomes **no default**: an unset embedder is a startup error
  naming the missing key, not a silent dial to a stranger's
  port that happens to be ours.

### 2.3 Paths and config hygiene

- Verified clean already: no `/home/…` literal is a default
  anywhere in `slice1/core/src/` or `ingest/ingest.py`;
  `fixtures_dir()` resolves `--fixtures-dir` →
  `$CONFLUENCE_FIXTURES_DIR` → the bundled set relative to the
  script file, never the CWD or `$HOME`.
  `CONFLUENCE_WAVE3_*_GLOB` / `_B_FILE` overrides are
  explicit-only and stay that way.
- `ledger_dir` stays a relative-or-absolute config value
  (default `ledger`). `ingest_cmd` stays a shell string in
  config — documented as such, since a technician composing
  sources is the intended use.
- The 4×4 grid is a **v1 format constant**, stated as such in
  the ledger spec (§3): tile numbers in published ledgers mean
  row-major cells of a 4×4 grid. Changing the grid later is a
  format version bump, not a config knob — strangers' indexes
  must stay interpretable.
- Python dependencies of the ingest (`numpy`, `requests`,
  `Pillow`) get a declared `requirements.txt`; today they are
  ambient (the Thor's ml venv), which no stranger has.

### 2.4 Workspace shape after extraction

Root `Cargo.toml` members shrink from 7 to the core set
(rolling-substrate-core, harbor-watch, the watch crate). The
watch crate keeps its path dependencies on the other two —
all three are std-only Rust, no network fetch to build, which
is already the cold-clone property the rehearsal verified.

---

## 3. TOOLKIT SURFACE — the smallest useful kit

Four pieces. Each marked: **exists** / **extract** (code exists,
needs lifting out of a demo) / **new-thin** (a wrapper over
existing machinery, no new capability).

### 3.1 CLI — one binary, four verbs

The binary today is `confluence-watch --config <file>`
(`slice1/core/src/main.rs`, 38 lines). The toolkit keeps that
shape and adds verbs as subcommands of the same binary:

| Verb | Does | Status |
|---|---|---|
| `watch` | Live source → ledger (today's whole behaviour: config file, ingest spawn, frame loop, ledger write, one-line JSON summary) | **exists** (is `main.rs` + `service::run`) |
| `index` | Existing footage → ledger: a file or image sequence replayed through the *identical* pipeline (the `wave3`/`staged` sources already prove replay parity — `tests/live.rs` asserts live ≡ batch verdicts). A video-file source is an ingest adapter that decodes frames at a cadence (ffmpeg or PIL imageio) and feeds the same `Emitter.frame()` path — acquisition only | **extract + new-thin source**: replay exists; the video-file frame source is new-thin |
| `query` | Read a ledger: events between two times, events touching a tile, spend/coverage summary — printed as text or JSON. Today this reading exists twice inside demos (the console's `/api/state` projection, presence's digest) and nowhere a stranger can call | **extract**: a reader over `events.jsonl` + `state.txt` + `health.txt`; no new data, no new format |
| `export` | Ledger → seek index in the formats other tools eat: CSV (time, frame, tiles, score), ffmpeg `ffmetadata` chapters, and a plain JSON event list. The chapter export is the composition primitive for §4 | **new-thin**: three renderers over the verdict rows of §3.2 |

### 3.2 The ledger format — documented spec (as written today)

Extracted from `slice1/core/src/ledger.rs` (`record_frame`'s
`writeln!`) — this is the format as it exists in real
`events.jsonl` rows, not an aspiration. A ledger directory holds
four files; only `events.jsonl` is append-only, the rest are
rewritten whole per frame (they are small).

**`events.jsonl` — verdict row** (written *only* when a frame
published a change; silence is the default):

| field | type | meaning |
|---|---|---|
| `kind` | `"verdict"` | row type (`"service"` rows carry `event`, `msg`, `wall_us`) |
| `stream` | string | the config's `stream_id` |
| `frame` | u32 | frame number in the source's own sequence — the seek key into file footage |
| `wall_us` | u64 | ledger-write time, epoch µs |
| `t_capture_us` | u64 | frame capture time, epoch µs — the seek key into timestamped footage |
| `verdict_latency_ms` | f64, 3 dp | capture → ledger write, including that frame's embed time |
| `changed_tiles` | [u32] | tiles published changed, row-major 0–15 on the 4×4 grid |
| `focus` | [u32] | the director's top-`focus_k` tiles by raw score (attention record; does not gate compute in v1) |
| `lineage_mask` | u64 | bitmask of cascade stages that touched the verdict (bits 0–4: perceive, decide, direct, refine, publish; a full pass = 31) |
| `stage_ms` | object | per-stage wall ms: `perceive_decide`, `direct`, `refine`, `publish` |
| `embeds_this_frame` | u64 | embedder calls spent on this frame — the cost receipt |
| `energy_before` / `energy_after` | f64, 4 dp | sheaf energy across the refine step (after ≤ before is debug-asserted) |
| `tiles` | [object ×16] | per tile: `tile`, `raw` (cosine distance or `null`), `smoothed` (post-refine or `null`), `changed`, `stale`, `lineage_mask` |

**`state.txt`** — `key = value`: `frames_seen`,
`frames_changed`, `events_published`, `tiles_nominated`,
`tiles_embedded`, `coverage` (embedded ÷ nominated),
`embeds_spent_s`, `embed_everything_estimate_s` (what watching
without the gate would have cost), `spend_ratio`,
`updated_wall_us`. **`lens.txt`** — `period_ms` / `jitter_ms`
EMAs, `threshold`, `alpha`, `gate_diff`, per-tile score EMAs:
the stream's learned normal, human-readable. **`health.txt`** —
`embed_ms_p50` / `embed_ms_p99`, `last_frame_age_ms`, and
`silence_meaningful` (true only when the embedder is up and
frames have been seen): **the basis of silence**, without which
an empty `events.jsonl` proves nothing.

Known format wart, recorded not hidden: in soak mode
`state.txt` carries `precision_self_report = placeholder …`
— trust accounting does not exist yet (§7 G3). The extracted
spec documents the line as a placeholder, verbatim.

### 3.3 Library reuse

- **exists**: `harbor_watch::pipeline::run_records` (batch) and
  `confluence_watch::live::LivePipeline` (incremental) are
  already a Rust library API over `InputRecord`s; `record.rs`'s
  codec is the documented wire format between any producer and
  the cascade. A Rust consumer can embed the cascade and write
  their own ledger, or none.
- **exists**: `rolling-substrate-core` is a standalone std-only
  crate (rings + sheaf) with its own tests and hardening record.
- **new-thin**: a worked library example (records in → verdicts
  out, ~50 lines) in the docs — the fixture generator
  (`harbor_watch::fixture`) already produces the synthetic
  records such an example needs.

---

## 4. COMPOSITION DOCS PLAN — "use it with tools you already have"

The adoption story is not a platform pitch; it is six short
workflow documents, each: the tool you already run, the one
command the extracted tool adds, and the artifact that comes
back. Outline (docs to be written at extraction, against the
real CLI of §3):

1. **Your NVR already records everything; this tells you where
   to look.** Point `index` at a camera's exported recording
   (Frigate / Blue Iris / Shinobi / a UniFi export — any file).
   One ledger per camera. `export` emits an `ffmetadata` chapter
   file; `ffmpeg -i recording.mp4 -i chapters.ffmeta -map_metadata
   1 -codec copy out.mp4` (remux, no re-encode) produces the
   same footage with every change event as a chapter — seekable
   in VLC, mpv, and every editor. The NVR keeps doing storage
   and retention; the tool never touches the footage.
2. **Cut the highlight reel with ffmpeg, from the ledger.**
   `query --since/--until` → CSV; a 10-line shell loop turns
   rows into `ffmpeg -ss <t_capture> -i … -t 10` clips, or one
   concat list. Worked end-to-end in the doc with real output.
3. **Cameras that speak HTTP today.** IP-Webcam-style `/shot.jpg`
   and MJPEG `/video` endpoints are the live sources that exist
   (`shot`, `mjpeg`). For an RTSP-only camera the doc says so
   plainly — RTSP ingest is **not built** (audits, D-I1) — and
   gives the interim that works: the camera's snapshot URL, or
   OBS (below). No workflow in these docs may depend on an
   unbuilt source.
4. **OBS as the universal adapter.** OBS already ingests
   anything (window capture, capture cards, RTSP via media
   source). OBS records → `index` the recording, or OBS's
   snapshot/virtual-camera path feeds `watch`. The doc's point:
   if OBS can see it, the ledger can index it, with OBS doing
   the format conversion the platform doctrine assigns to
   converters.
5. **Files, not streams.** Trail-cam SD cards, dashcam loops,
   a phone's camera roll, a folder of clips: `index` per file,
   one ledger per file, `query` across them with `jq` over
   `events.jsonl` (three worked `jq` recipes: all events, events
   per hour, the spend summary from `state.txt`). This is the
   backfill idea (§1 OUT #5) reduced to its reusable core.
6. **Asking the ledger questions.** A pointer chapter, fenced
   as demo: the presence build (§1 OUT #1) shows a voice
   conversation answered *only* from a live ledger, with a
   claim checker fencing the model's sentences (§8 E4). It is
   documented as "what a reader can be," never as part of the
   tool — the tool's promise ends at a ledger other software
   can trust.

Each doc carries its own measured numbers from §8 where it
makes a claim, and names its limits in the same paragraph
(gate is a ranker, §8 E2; daylight recalibration, §8 E3).

---

## 5. PROOF BATTERY — how the extracted tool proves itself, standalone

Cold-clone discipline is the existing house rule and carries
over unchanged: a fresh clone, an empty `$HOME`, no fleet
services, no Thor. Layers, cheapest first — each layer states
exactly what it does and does not prove:

| # | Check | Proves | Status |
|---|---|---|---|
| P1 | `cargo test` on the extracted workspace | Cascade, rings, sheaf guards, ledger files, live≡batch parity (`slice1/core/tests/live.rs`: identical verdicts incl. lineage masks and the stale-publish rule) | **exists** — 107 tests workspace-wide today; the extracted subset is re-counted at extraction and the new count published, not inherited |
| P2 | `python3 prove_fixtures.py` (bundled fixtures, 3.35 MB, no embedder) | The gate/diff layer cold: baseline nominates 16, cut frame nominates 16/16, object frame nominates exactly {5,6}, drift nominates none, every wave-3 C landing nominates 16/16. Embeddings are placeholders — **no verdict claim is made from this layer** (the script says so in its header) | **exists** |
| P3 | Full staged acceptance against a shipped test-double embedder (byte-hash embeddings, deterministic) | The verdict layer end-to-end with zero external services: 18 frames → 34 embeds (= 16 + 16 + 2 + 0, exactly as ground truth predicts), verdict at frame 4 (16 tiles) and frame 7 (exactly {5,6}), drift silent | **extract** — performed as the install proof (2026-11-02, `slice1/install/INSTALL-PROOF.md`); promoted to a shipped acceptance script at extraction |
| P4 | Staged acceptance against a real embedder (acceptance.sh shape) | The measured headline: cut 16/16 tiles, object exactly {5,6}, drift silent, spend ratio 0.118 vs embed-everything, lineage mask 31 | **exists** (`slice1/core/acceptance.sh`, ALL PASS on the Thor 2026-11-01); at extraction it must pass against the §2.1 `HttpEmbedder` adapter, not the fleet path |
| P5 | Ledger golden-file test | A fixed record stream produces a byte-stable `events.jsonl` verdict row with exactly the §3.2 fields — the format strangers will parse is pinned by a test, not by prose | **new-thin** |
| P6 | Frozen-source test | The soak incident as a regression (§8 E3): a source that repeats one frame must not accumulate "frames seen" as evidence of life — freshness is proven by image novelty or the health file says the lane is stale | **new-thin**, and it is also gap G1: the battery does not pass until G1 closes |
| P7 | Cold-clone rehearsal, walked as a stranger | The graduation-rehearsal pattern (`slice1/install/REHEARSAL-LOG.md`): clone → build → P1–P3 green → first ledger produced, with every stumble written down and either fixed or listed | **exists as a practice**; re-run against the extracted tree before any publish step (§9) |

Simulated numbers never share a table with measured ones —
P2/P3 outputs are labelled gate-layer and test-double wherever
they are quoted.

---

## 6. RISKS / OPEN QUESTIONS for Casey (5)

1. **Name.** The binary is `confluence-watch` and the platform
   is Confluence; the extracted tool is smaller than both. Keep
   the name (recognition inside the fleet) or give the tool its
   own (a stranger's first impression)? Casey's call.
2. **Repo home.** New repo for the extracted tool (clean history,
   the demos stay behind) vs in-place flip of
   SI-Thor/rolling-perception (one history, panels and all)?
   §9 is written to work either way; the choice is Casey's.
3. **The stranger's default embedder.** `OnnxEmbedder` (§2.1)
   needs a model a stranger may download — I-JEPA weights and
   their licence terms decide whether the zero-infrastructure
   path ships at v0.1 or waits, leaving HTTP-adapter-only first.
4. **Grid size.** 4×4 is baked into the ledger format (§2.3).
   Ship it as the v1 constant, or pay for configurability
   *before* strangers build indexes whose tile numbers must
   keep meaning?
5. **Licence — already present, one confirmation.** Root
   `LICENSE` + `LICENSE-MIT` + `LICENSE-APACHE` exist and all
   crates declare `MIT OR Apache-2.0` (polish round, 2026-11-02).
   No action needed unless Casey wants a different licence for
   the extracted tool specifically.

---

## 7. PRODUCTION-GRADE GAP LIST — what stands between the core and a stranger's trust

Core only. Items touching the demo interfaces stay with the
demos (the player's 0-frame readiness wart, AUDIT-PRODUCT, is
the serve demo's own debt — its core analogue is G1). Severity
and effort use the audits' scales (S/M/L).

### G1 — Freshness / readiness honesty in the core — MAJOR, effort M

The soak incident (§8 E3) is the evidence: when the camera
pusher died, the watch kept polling the receiver's last frame
and counting polls as frames for ~13 h. `frames_seen` is a poll
counter, not a freshness proof, and `health.txt`'s
`last_frame_age_ms` (`slice1/core/src/ledger.rs`, `health_text`)
measures the poll, not the image — so `silence_meaningful`
stayed true over a frozen feed. The service loop
(`slice1/core/src/service.rs`, the `frame_end` path) accepts a
frame boundary without any novelty check. **Production
meaning:** the tool's central promise — *silence you can
trust* — is exactly the thing this defect counterfeits. Fix
shape (design only): freshness proven by image novelty (a
cheap frame hash at ingest; a repeated frame advances a
`stale_source` counter in `health.txt` and flips
`silence_meaningful` false), plus the P6 regression test.
Nothing else in this list outranks it.

### G2 — Error-type consistency on the core's own surfaces — MAJOR, effort M

AUDIT-ENGINE #4, core subset: `service::run`
(`slice1/core/src/service.rs`) returns `Result<_, String>`;
the cascade's entry points panic on caller error instead of
refusing — `LivePipeline::process_frame` asserts embedding
dimension and tile bounds (`slice1/core/src/live.rs`), and
`harbor_watch::pipeline::run_records` `expect`s a non-empty
record set (`crates/harbor-watch/src/pipeline.rs:358`). The
workspace's own standard is typed errors (`SheafError`,
`ConfigError`, `ParseError` all implement `Display` +
`std::error::Error`). **Production meaning:** a library
consumer cannot match on failure kinds, and a malformed
record stream can panic a long-running watch instead of
degrading it. (cuda-thor's ~25 string-typed functions are the
audit's larger instance and are OUT of the tool — §1.)

### G3 — The ledger trust loop is open — HIGH (spec), effort S–M

Corrections are written (by the console demo) and **never
read**: no auto-demotion, no trust accounting (AUDIT-DOCS
D-A3 + D-LN4, POLISH-BACKLOG major 7). The core's own
confession is in `slice1/core/src/ledger.rs` (`state_text`,
soak branch): `precision_self_report = placeholder (events
fired and spend below; labels pending)`. The design exists
(panel round 3: demote on judged-window precision per stream,
never on event count) — the code does not. **Production
meaning:** the spec's trust target (≤1 false event/stream/day)
is currently unmeasurable from the ledger alone; a stranger
running the tool for a month gets counts, not a precision
number. For the extracted tool the honest v1 scope is the
accounting half (events / confirmed / dismissed computed into
`state.txt` from a corrections file in the documented format);
auto-demotion stays a named spec-debt, not a silent absence.

### G4 — Test deserts in core modules — MAJOR, effort M

AUDIT-ENGINE #3: `harbor-watch` has **zero** unit tests in
every `src` module (`pipeline.rs` 361 ln, `record.rs`,
`ablation.rs`, `fixture.rs`, `rng.rs`) — all cover is 8
integration tests; `slice1/core`'s `config.rs` (139 ln),
`ledger.rs` (353 ln) and `service.rs` (279 ln) have no unit
tests, only the 3 integration tests in `tests/live.rs`.
**Production meaning:** the ledger text formats are the
tool's contract with every future reader (§3.2), and nothing
pins them below integration level — a refactor can change
the published format and stay green. P5 (§5) is part of the
close; per-module unit tests for `ledger.rs` and `record.rs`
are the rest.

### G5 — Path / config hygiene (core residue after §2) — MAJOR, effort S

Beyond the §2 surgery: the shipped *examples* still teach
fleet values — `slice1/core/acceptance.sh` and the core
README's configs assume the rack on `:8077` with
`rack_autostart = true` (correct on the fleet Thor, wrong as
a stranger's default), and `slice1/install/INSTALL.md` — the
technician doc a reader finds first — still shows the phone
example at a personal LAN address (G6). The extracted tool's
shipped configs must default to the test-double or the ONNX
adapter, with the HTTP/rack profile as an explicitly named
example file.

### G6 — Publication hygiene — mixed severity, effort S (scrub: M)

From AUDIT-OPS, re-verified against this tree:

- **Git-history bytecode — MAJOR, M to purge.** ≥10 tracked
  `__pycache__/*.pyc` blobs are in history (named in AUDIT-OPS
  H2: `slice1/core/__pycache__/`, `slice1/core/ingest/
  __pycache__/`, eight under `slice2/presence/__pycache__/`).
  Bytecode embeds build-machine absolute paths. The
  `.gitignore` half is FIXED (`__pycache__/`, `*.pyc`, `.env`
  present); the history scrub is deliberately scheduled *with*
  the publish (§9), not before — the repo is private and the
  blobs carry only build paths.
- **Home-LAN addresses in shipped docs — MAJOR, S.**
  `<thor-lan-ip>` (the Thor) in: `docs/SPEC-STREAM-PLATFORM.md`,
  `slice1/PROART-CAMERA.md`, and the duplicated spec copies
  `slice2/panel-2/_prefix.md` + `slice2/panel-2/q1-presence-brain.md`,
  `q2-session-budget.md`, `q3-synthesiser-risk.md`,
  `q4-technician-failure.md` (the panel prefix is the spec text
  duplicated — one fact, six homes). `<lan-ip>` (a personal
  phone) in `slice1/install/INSTALL.md` (three occurrences,
  the IP-Webcam example). RFC1918 — not routable, but it is the
  owner's home topology and a personal device. Replace with
  `thor.local` / placeholders in the extracted tree.
- **Personal paths — MINOR, S.** The owner's username in
  absolute paths in 2 files: `docs/FEASIBILITY.md` and
  `experiments/wave3/driver/driver.log` (three log lines,
  `/home/<user>/image-studio/outputs/…`). Redact to `~/…` or
  drop the log (its numbers are quoted in the wave docs).
  Whether either file travels to the extracted repo is a §9
  step-1 decision; the redaction applies either way at flip.
- **SECURITY.md / CONTRIBUTING.md — MINOR, S.** Both absent
  (verified: neither file exists at root). AUDIT-OPS H4:
  SECURITY.md (how to report) is the day-one one for a public
  repo. Written at §9 step 5, not before — no fake boilerplate
  while the repo is private.
- **Not gaps, checked so nobody "fixes" them:** licence files
  exist (§6 Q5); zero live secrets in the tree (AUDIT-OPS S1,
  full grep sweep); CI exists (`.github/workflows/ci.yml`);
  the near-empty `Cargo.lock` is correct for a path-only
  workspace. No `rust-version`/MSRV is declared in any
  `Cargo.toml` (AUDIT-ENGINE #13, MINOR/S) — declare one at
  extraction.

**Explicitly not gaps for the tool** (doctrine of the platform
spec, excluded by the §1 subtraction — listing them here so
their absence from the tool is a decision, not an oversight):
the yield ladder and budget *enforcement* (the tool meters
spend in embed-seconds and reports it; tenancy on a shared box
is the host's job), cross-stream attention, profiles, and
perception-backed search (AUDIT-DOCS spec-debt menu — that
menu belongs to Confluence-the-platform, not to this tool).

---

## 8. WORKED EXAMPLES — specific real runs (the EXAMPLES doc set)

Drawn only from runs already documented in this repo. Each:
what was pointed at it, what it produced, the numbers, and the
failure or limit it exposed. These become the extracted tool's
EXAMPLES section verbatim in spirit — honesty is the brand.

### E1 — The staged acceptance: cut, object, drift (2026-11-01)

- **Pointed at:** an 18-frame staged sequence composited from
  real photos (bundled fixtures): frames 0–3 scene A, a hard
  cut to scene B at frame 4, a real-photo object pasted over
  tiles {5,6} at frame 7, then 8 frames of gradual brightening.
- **Produced:** a verdict at frame 4 flagging **16/16 tiles**
  (3,347.6 ms, 16 embeds); a verdict at frame 7 flagging
  **exactly tiles {5,6}** (392.8 ms, 2 embeds); **nothing** for
  the drift frames. 34 embeds total; spend 13.4 s vs a 113.2 s
  embed-everything estimate — **spend ratio 0.118**. Lineage
  mask 31 (all five stages) on the verdicts.
- **Limit it exposed:** the *first* version of this rig used
  synthetic flat-gradient scenes and the cut published
  **nothing** — I-JEPA embeds two flat fields nearly
  identically (probe distances after the rebuild: cut min
  0.299 / mean 0.491; object tiles 0.588 / 0.651; non-object
  max 0.027). A staged scene the perception model cannot tell
  apart tests nothing; the rig is real-photo composites
  permanently, and the fixtures ship with the tool (§5 P2).
  Source: `slice1/core/README.md`, `slice1/README.md`.

### E2 — Wave-3 sequence C: a real cut at every boundary (2026-11-01)

- **Pointed at:** two real frame sets — A (12 burst photos of
  one scene), B (12 turntable frames of another) — interleaved
  A/B/A/B…, i.e. a genuine scene cut at **all 11 boundaries**,
  embedded by the real I-JEPA (rack latency p50 173 ms /
  p95 200 ms).
- **Produced:** every landing frame flagged **16/16 tiles**;
  scoreboard **precision 1.000 / recall 1.000** on C. The
  diff gate's economics on the full material: ALL = 576 embeds
  / 119.6 s vs CHANGED = **312 embeds / 55.0 s (−54%)**, with
  frame-verdict agreement between the two strategies of
  **1.0000** on C; on the gradual turntable (B) the gate kept
  23/192 embeds (−88%) and stayed near-silent (2/192 tiles
  flagged). The sheaf refine ablation on the controlled
  fixture: precision **0.60 → 1.00** at recall 1.00 — the
  refine step earns its place by measurement.
- **Limit it exposed:** the gate is **a ranker, not a
  separator** — skipped tiles' drift (0.20) vs embedded tiles'
  (0.48) overlap; no pixel threshold cleanly splits changed
  from unchanged, so per-scene gate calibration is real,
  recurring work. Sequence A is kept in the record as the
  honest counterweight: regenerated "burst" frames that
  genuinely differ in embedding space flagged 148/192 tiles —
  the detector believed the embeddings, and it was right to.
  Source: `docs/RESULTS.md` (wave-3 rows), `experiments/wave3/`.

### E3 — The live 48-hour soak, IN PROGRESS — including the frozen feed (2026-11-01 → )

- **Pointed at:** a real room, via the ProArt's webcam dialling
  OUT to the Thor (the Windows Firewall drops unsolicited
  inbound; the camera side pushes ~2 JPEG/s to a receiver the
  watch polls through its ordinary `shot` source). Gate
  calibrated on the still night room first: 1,200 frames,
  nominations only on the baseline frame, **0 events, spend
  ratio 0.0008**.
- **Produced (so far):** the soak started 2026-11-01 18:18
  AKST, completes 2026-11-03 18:18 AKST, verdict due after.
  It live-detected the homeowner arriving at the desk that
  evening (events 43 → 48 as he crossed the frame and sat; the
  gate then reabsorbed seated-him into the baseline). At the
  last full check the ledger was still advancing and events
  were in the hundreds.
- **The failure, in the record on purpose:** on 2026-11-02 the
  owner noticed the camera light was off. The Thor side was
  alive and counting — but the feed was **frozen**: two
  `/shot.jpg` grabs 10 s apart were byte-identical, the Windows
  pusher (a foreground window) had died, and the watch had
  spent ~13 h (2026-11-01 ≈21:05 → 2026-11-02 ≈10:03 AKST)
  re-polling the receiver's last frame and counting polls as
  frames. The owner relaunched the pusher; live frames and
  events resumed within minutes (393 → 415). The soak's end
  time does not move; the verdict must fence the gap.
- **Limit it exposed:** `frames_seen` counts polls, not fresh
  images — the defect is now gap **G1** (§7) with a regression
  test owed (**P6**, §5). A tool whose product is trustworthy
  silence was caught manufacturing it; the example ships with
  the tool because that is the standard the tool is held to.
  Source: `slice1/PROART-CAMERA.md`; incident recorded
  2026-11-02, verdict pending at the time of writing.

### E4 — A conversation *about* the ledger: presence from the chair (2026-11-02)

- **Pointed at:** the live soak ledger itself — read-only,
  through a rendered per-stream view; the soak's files were
  never written. A browser page on the ProArt lent the Thor
  its mic and speaker; the brain was **Qwen3-Coder-30B-A3B**,
  the bench-proven coder that won the presence brain bench
  (grounded all content questions, refused the planted trick,
  quoted figures exactly — `slice2/BRAIN-BENCH.md`); speech in
  via faster-whisper (`tiny.en`, CPU), out via a resident
  Piper worker; every factual sentence fenced by a
  deterministic claim checker before it was spoken.
- **Produced:** the owner asked aloud, *"What has changed in
  the last hour?"* Transcript exact (STT 436 ms; brain
  2,620 ms; TTS 252 ms). The spoken reply cited that morning's
  real verdicts — `[proart-cam-114023]`, tiles 12, 11:43 AM,
  plus two more 11:4x events (the owner's own activity at the
  desk while setting up). Grounding violation: **null**;
  claim violations: **[]**; `reply_raw == reply` — every fence
  passed the model's raw answer untouched, and the voice was
  heard in the room.
- **Limits it exposed, both recorded in the repo:** the first
  attempt failed *silently* — browsers deny `getUserMedia` on
  plain-http LAN origins (secure-context rule), so the talk
  button was dead until a browser flag was set; a household
  member cannot be asked to do that, and the page must say so
  instead of failing quietly (a named product requirement —
  and, for this plan, a demo-interface debt, not a core gap).
  The performed reply's last sentence was clipped mid-phrase
  by the 64-token brevity cap ("…at 11:"). Status in this
  plan: **demo on top of the core** (§1 OUT #1) — it is in the
  examples because it proves the ledger is a thing other
  software can build on, which is the tool's whole claim.
  Source: `slice2/presence/README.md` (from-the-chair section).

### E5 — Reconstructing a morning from ledger numbers alone (2026-11-02)

- **Pointed at:** nothing but the soak's `events.jsonl` —
  no footage exists to consult (the receiver holds only the
  latest frame; frames were never archived, by design).
- **Produced:** the owner's arrival at his desk, read cold
  off the tile grid (4×4, row-major): 11:38:07 — six tiles
  fire at once (5, 6, 9, 10, 13, 14, the frame's centre-left
  mass); 11:38–11:39 — activity settles into the lower-centre
  tiles (9, 10, 13, 14); 11:41:46 and 11:43:24 — corner tile
  12 (bottom-left) pulses alone, twice, ~90 s apart; from
  11:44 — the bottom rows churn (15, then 14+15, a wide burst
  at 11:44:25) through the presence conversation at 11:44:48.
  35 verdict rows in the 11:38–11:50 window. Read as a
  sentence: *something large crossed the middle of the room,
  work concentrated at the bottom of the frame where the desk
  is, one corner kept being disturbed, then sustained activity
  at the desk.* That is precisely what happened.
- **Limit it exposed — the honest boundary of the whole
  tool:** the tape yields a **choreography, not a scene**. It
  cannot say it was a person, let alone who; "a man sat down"
  and "a coat was hung on the chair" produce near-identical
  rows if they move the same tiles. Sixteen cells is the
  finest spatial resolution that will ever exist for that
  morning, and the within-tile content is gone by design.
  This is why the two reconstruction options were ruled
  *wonderful but not necessary* (2026-11-02): paired with
  footage the user keeps, the ledger is already a seek index
  (E5's timestamps are E1's `t_capture_us`); without footage,
  it is a change-witness, not a recorder — which is what makes
  it safe to keep forever and hand to any reader, as E4 did.
  Source: live-ledger reading, 2026-11-02 (soak ledger,
  `run-proart`); the soak verdict (§9 of the soak record) is
  where this reading gets its final fence.

---

## 9. PUBLISH PACKAGE CHECKLIST — prepared now, published on Casey's word

Ordered. Steps 1–8 are preparation and are completed **before**
anyone asks Casey for the tap; step 9 is the tap.

1. **Repo-home decision recorded** (§6 Q2) and name confirmed
   (§6 Q1). Everything below is written to work for either
   answer; the scrub in step 3 differs (new repo: no scrub
   needed — the extracted tree starts clean; in-place flip:
   scrub is mandatory).
2. **Freeze the scope to §1.** The extracted tree contains the
   11 IN entries, the toolkit (§3), the proof battery (§5),
   and the docs (§4 outlines + §8 examples). OUT items stay in
   the origin repo; the extracted README links them as demos,
   once, in a "built on top" section — they are not copied.
3. **History hygiene (in-place route only).** Scrub the ≥10
   tracked `__pycache__/*.pyc` blobs (G6) with a history
   rewrite on the publish clone; verify with `git ls-tree`
   over all refs that no `.pyc` remains. (New-repo route:
   verify the fresh tree contains none — the `.gitignore`
   already prevents recurrence.)
4. **Privacy + secrets scan, re-run on the extracted tree.**
   The AUDIT-OPS grep set (key shapes, `BEGIN .*PRIVATE`,
   `.env`, credential filenames) must return zero, and the
   G6 redactions must be verified by grep, not by memory:
   no `192.168.0.` anywhere (files named in G6), no personal
   absolute paths (`docs/FEASIBILITY.md`,
   `experiments/wave3/driver/driver.log` — if either travels).
   This step is a scan with output filed, not an assurance.
5. **Front door.** README: one paragraph (the §1 definition),
   the cold quickstart (clone → P1/P2 → first ledger in
   minutes), EXAMPLES (§8) linked from the first screen,
   the ledger spec (§3.2) as a first-class doc, `SECURITY.md`
   and `CONTRIBUTING.md` added (G6), MSRV declared (G5/G6),
   licence files confirmed present (§6 Q5).
6. **Gap gate.** G1 must be **closed** before publish (it is
   the promise of the tool); G2–G5 either closed or carried
   into the published repo as filed issues with the audits'
   severity labels intact — nothing silently dropped.
7. **Cold-clone verification of the extracted tree.** Fresh
   clone, empty `$HOME`, no fleet services: P1–P4 green
   (P4 against the HTTP adapter), P5–P6 green, the §4
   workflow #1 (chapters into a real recording) executed
   end-to-end once. Numbers recorded in the release notes
   with their machine and method.
8. **Tag and verify the artifact.** Tag `v0.1.0`; build the
   release *from the tag*; clone the tag fresh and re-run
   P1–P3 against that artifact (the house rule: "tested"
   names the released artifact, not the working tree that
   built it). Checksums recorded.
9. ⛔ **PUBLISH — waits for Casey's explicit word.** Flip the
   repo public (or push the new repo) — and nothing in steps
   1–8 is represented to anyone as having published anything.
   The graduation gate has always been his call; this plan
   prepares the package, it does not tap it.
10. **Post-publish, same day.** Verify GitHub detects the
    licence; revisit branch protection (unavailable on the
    private plan — AUDIT-OPS H4); confirm every README link
    resolves from the public side; file the carried G-items
    (step 6) as the repo's first issues.

---

*End of plan. Sources: `slice1/core/src/{config,ledger,live,service,main}.rs`,
`slice1/core/ingest/ingest.py`, `crates/harbor-watch/src/{record,pipeline,rng}.rs`,
`crates/rolling-substrate-core/src/lib.rs`, `docs/RESULTS.md`,
`docs/audits/{AUDIT-ENGINE,AUDIT-PRODUCT,AUDIT-DOCS,AUDIT-OPS,POLISH-BACKLOG}.md`,
`slice1/{README,PROART-CAMERA}.md`, `slice1/core/{README,fixtures/README}.md`,
`slice1/install/INSTALL-PROOF.md`, `slice2/{BRAIN-BENCH}.md`,
`slice2/presence/README.md`. The flagged `docs/WAVE3.md` read was
not used as a source for any number above; wave-3 figures are
cited from `docs/RESULTS.md` and the slice records.*

---

## 10. RULINGS (Casey, 2026-11-02 12:54 AKST — answers to §6)

1. **Name:** the standalone tool gets a standalone name — not
   Confluence, not confluence-watch. (Name itself: Casey's to
   pick from candidates; the build proceeds under a working
   title.)
2. **Repo home:** NEW repo, clean history. "Keep things clean
   and new." The §9 scrub steps apply to any material carried
   over; nothing inherits the old history.
3. **Third-party licence posture:** the tool must not be limited
   by another party's licence. Where the best part carries
   restrictive terms (the I-JEPA case), the part is NOT
   incorporated into our code or distribution: the seam ships,
   the docs explain how to move the best part in, the user
   brings it under their own terms. The shipped default path
   is licence-clean and fully usable.
4. **Grid:** configurable — with documentation of WHY 4x4 was
   the default (the measured record behind the choice ships
   as part of the docs, so a user who changes it knows what
   they are trading).
5. **Our licence:** permissive, confirmed. Others may use it
   in all ways, build on it, and make it better — we benefit
   from their improvements and innovations. MIT OR Apache-2.0
   dual, as already in the tree.
