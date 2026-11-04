# Sharing the box: the tenancy ladder, worked

A tutorial for the platform operator: what the yield ladder is, where
each rung lives in the code, how to prove it works on your own
machine, and how to read a yield in a real ledger. Everything quoted
below was run against `main` (commit e8a6102, "Yield ladder BUILT") on
a fresh clone; every output block is real, trimmed for length only.
Commands are run from the repo root. (If cargo is not on your PATH it
may live at `~/.cargo/bin/cargo`.)

## The problem in one page

Confluence watches streams on the Thor — a GPU box with one card and
an owner. Two doctrines collide there, and the spec (§2.3) resolves
them explicitly: the fleet says a powered-on idle GPU is a failure and
the queue must always carry a successor; the placement ruling says the
Thor is Casey's primary system, worked by him directly, and the
platform's lanes do not colonise it. The resolution is that **the
platform is a tenant with a yield contract**.

A tenant can fail in two opposite directions. A watcher that fights
the box's owner for the GPU — keeps embedding through the owner's
transcode, his game, his compile — is a bad tenant, and will be
evicted by a human. A watcher that *silently goes blind* when squeezed
— drops its embeds, publishes nothing, lets the change feed read
"all quiet" over a night it stopped perceiving — is a dangerous one,
because nothing announces the failure: the ledger just gets quiet, and
quiet is exactly what a calm night looks like too.

The ladder exists to be neither. When foreign work arrives, the
platform steps down a rung at a time — pausing backfill first, then
thinning its decision budget, then falling back to reflex-only diffs,
and only under memory pressure unloading its models — and every step
is receipted in the ledger, and the frames it can no longer perceive
still publish, explicitly marked `unperceived` with their basis in
plain words. The design rule that carries all of this: **yielded
silence must never lie.** When the box is clear again, recovery is
deliberately slow — one rung back per 60 s — because a ladder that
flaps is worse than a ladder that lags.

The budgets (§2.2) are the same story in the steady state:
per-stream embed-seconds over a rolling hour (default 300 embed-s/h,
the camera-class figure), with admission in diff-rank order — the
tiles most likely to matter embed first — and every tile the budget
refuses is counted as shed, never silently dropped.

## The ladder itself

Spec: §2.3 (the 2026-10-28 ruling) with the dated implementation note
(2026-11-03). Code: `slice1/core/src/tenancy.rs` (the ladder as a
pure state machine), the tenancy runtime inside
`slice1/core/src/service.rs` (sampling, receipts, rack actions), the
ledger fields in `slice1/core/src/ledger.rs`, and the ingest side of
the control file in `slice1/core/ingest/ingest.py`.

### The rungs

`Rung` (tenancy.rs) is L0–L4; what each rung permits is
`capabilities(rung) -> Capabilities`:

| Rung | What yields | Capabilities (the code's flags) | Where it bites |
|---|---|---|---|
| L0 | nothing | backfill ✓, reflective ✓, decision ×1.0 | — |
| L1 | backfill | `backfill_permitted = false` | `backfill_permitted` cleared in state.txt / control.json; the consumer is the §4 backfill process (this service runs no backfill) |
| L2 | + reflective sampling; decision budget halved | `reflective_permitted = false`, `decision_factor = 0.5` | `budget_embed_s_per_hour` halves in control.json → the ingest's admission |
| L3 | + the decision tier entirely (reflex-only) | `decision_factor = 0.0`, `decision_permitted = false` | the ingest embeds nothing and emits reflex lines; the ledger publishes `unperceived` verdicts; health carries `yield_rung` / `decision_tier` / `silence_basis` |
| L4 | + decision models unload (memory pressure required) | `unload_models = true` | `systemctl stop jev-rack` **iff this service started the rack**; a rack it does not own is receipted `yield_models_not_owned` and left running |

Step-down is one rung per fresh sample while pressure holds
(`Ladder::evaluate` returns at most one `Transition` per call, so
step-down cadence is the sampler's 2 s). Foreign pressure alone floors
at L3 — L4 is reserved for memory pressure, the spec's own L4 trigger.
Memory pressure on its own also walks the ladder down: a box out of
RAM is a tenancy emergency whether or not a GPU process caused it.

### The triggers, and why attribution is the whole game

`SystemProbe::sample()` builds one `LoadSample` per 2 s tick
(`tenancy_sample_ms`) from three sources, each best-effort:

- **Foreign GPU load, attributed per process**
  (`SystemProbe::foreign_gpu_pct`). The probe asks nvidia-smi for the
  compute-app PIDs on the card and checks them against the platform's
  own pid set — this service's process tree plus the MainPIDs of
  `tenancy_platform_units` (default `jev-rack`). Only if a compute
  process that is *not* platform is present does the reading carry the
  utilisation figure; otherwise it is 0.0. Aggregate GPU counters are
  deliberately never used: the platform's own embeds load the GPU, so
  a tenant reading the aggregate would yield to itself — and a tenant
  that yields to its own work is a feedback loop (embeds run → counter
  high → yield → counter drops → recover → embeds run…). Where no
  attributing source exists, the reading is "no data" (`None`), never
  the aggregate. On the Tegra machine this tutorial ran on, for
  instance, nvidia-smi exists but answers `[N/A]` to the utilisation
  query — so `foreign_gpu_pct` is `None` and the ladder there simply
  never yields on GPU load. That is the honest fallback, by design.
  Sustained foreign load above `foreign_gpu_threshold_pct` (20%) for
  longer than `sustain` (5 s) yields (`tenancy_sustain_s`).
- **Interactivity via IdleHint** (`SystemProbe::interactive`). Each
  graphical (wayland/x11) loginctl session is asked its `IdleHint`; a
  non-idle session means the user is at the bench. Presence alone must
  not yield — a logged-in-but-idle desktop is not the user working —
  and an active session yields on the first sample, without waiting
  out the 5 s sustain that GPU load must prove (§2.3: "or any
  interactive session activity signal"). A graphics-only foreign load
  (a game holding no compute context) is covered by this signal, not
  the GPU figure.
- **Memory pressure** (`SystemProbe::mem_available_pct`):
  MemAvailable from /proc/meminfo below `mem_pressure_pct` (10% of
  RAM — the spec names the trigger, the build chose the number and
  put it in config).

### Recovery: deliberately slow

`Ladder::evaluate`'s step-up half is the §2.3 hysteresis verbatim: a
full clear interval (`tenancy_recovery_s`, 60 s) before the first
step up, then one rung per further interval. Any pressure sample
resets the clear clock, so a workload straddling the threshold cannot
walk the ladder back up prematurely — the no-flap property is proved
by 30,000 alternating samples in the unit suite (below).

### The control file: how orders reach the ingest

`ControlState::write` (`tenancy.rs`) lays down
`<ledger_dir>/control.json` — the rung, `decision_enabled`, the
rung-factored `budget_embed_s_per_hour`, the reflective and backfill
flags, and the reason — before the ingest spawns, and on every
transition. The ingest polls it per frame (`Emitter._read_control`,
mtime-cached) and enforces both ends: decision off ⇒ embed nothing,
emit a reflex line naming the nominated tiles; budget set ⇒ admit
nominated tiles in diff-rank order (`Emitter.frame`) until the
rolling hour (`_window_spend_s`, 3600 s window, per-embed cost
estimated from the run's own measured `embed_ms`) would be spent, and
count the rest in `frame_end`'s `shed` field. The fail-open rule is
deliberate: a missing, torn, or unreadable control file reads as "no
orders" — decision on, no cap — because the yield system protects the
user's interactive work, and its own failure must not blind the
stream it was protecting. `tiles_shed` in state.txt carries the count.

## Run it

Three suites, one per layer: the pure ladder, the wired service, and
the real ingest. All three were run for this tutorial; here is what
they printed and what each piece proves.

### The integration scenarios (the wired service)

```sh
cargo test -p confluence-watch --test tenancy
```

```
running 3 tests
test memory_pressure_reaches_l4_and_reports_unowned_models ... ok
test alternating_pressure_never_yields ... ok
test ladder_yields_under_foreign_load_and_recovers_with_hysteresis ... ok

test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 1.76s
```

(The `BrokenPipeError` tracebacks that interleave in the raw output
come from the tests' own fake-ingest script when the service closes
its stdout at run end — scaffolding noise, not the product; the real
ingest is not in this path.)

What each scenario proves, driving the full service loop with a
scripted probe (`ScriptProbe` — host pressure as a recording) and a
fake ingest that honours the control file the way ingest.py does:

- **`ladder_yields_under_foreign_load_and_recovers_with_hysteresis`** —
  40 samples of 60% foreign GPU load, then clear forever: the ladder
  walks L0→L1→L2→L3 (three step-downs, no further), the feed keeps
  publishing through L3 as `unperceived` verdicts, embeds demonstrably
  fall below two-per-frame while the tier is off, and recovery climbs
  exactly one rung per clear interval back to L0, where health again
  reads `silence_basis = decision` and the control file says
  `decision_enabled: true`.
- **`memory_pressure_reaches_l4_and_reports_unowned_models`** —
  MemAvailable pinned at 2%: the ladder walks all four rungs to L4,
  and because the service did not start the (stub) rack, L4 must *not*
  stop it — the ledger receipts `yield_models_not_owned`, and health
  tells the whole truth: `yield_rung = L4`,
  `decision_tier = reflex_only`, `silence_basis = reflex`,
  `silence_meaningful = true`. L4's silence is reflex-tier silence,
  never a dead lane.
- **`alternating_pressure_never_yields`** — 400 samples alternating
  75% foreign / clear: zero `yield_rung` receipts, final rung L0, and
  every frame embedded both its tiles (`embeds == 2 × frames`).
  Boundary-straddling pressure must never yield.

### The ladder unit tests (the pure state machine)

```sh
cargo test -p confluence-watch --lib tenancy
```

```
running 8 tests
test tenancy::tests::foreign_load_must_sustain_before_it_yields ... ok
test tenancy::tests::capabilities_match_the_spec_rungs ... ok
test tenancy::tests::memory_pressure_alone_walks_the_ladder ... ok
test tenancy::tests::interactive_signal_yields_without_sustain ... ok
test tenancy::tests::memory_pressure_unlocks_l4 ... ok
test tenancy::tests::recovery_is_hysteretic_one_rung_per_interval ... ok
test tenancy::tests::ladder_walks_down_one_rung_per_evaluation_and_floors_at_l3 ... ok
test tenancy::tests::boundary_straddling_pressure_never_yields_or_flaps ... ok

test result: ok. 8 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.01s
```

Eight tests over the pure machine (the clock is injected, so the
spec's 5 s / 60 s run in milliseconds). The one to notice is
`boundary_straddling_pressure_never_yields_or_flaps`: **30,000
samples** alternating foreign 75% / clear every 20 ms — a simulated 10
minutes of a workload straddling the trigger — with an assertion at
every single step that the ladder returns no transition, plus 500
clear/foreign blips after a deliberate yield to L3 asserting it does
not step back up early. The sustain clock resets on every clear
sample; the recovery clock resets on every pressure sample. That is
the no-flap property as an exhaustive check, not a claim.

### The ingest control tests (the real Python code path)

```sh
python3 slice1/core/tests/test_ingest_control.py
```

```
PASS: budget admission (2 embedded, 14 shed, cut reflex-reported)
PASS: decision off (0 posts, reflex verdicts on frames 0 and 4)
PASS: no control file (32 posts, unchanged behaviour)
INGEST TENANCY-CONTROL PROOF: ALL PASS
```

The real `ingest.py` on the staged fixtures against a stub rack that
counts its POSTs and answers in a deliberate 200 ms, so the budget
arithmetic is deterministic:

- **Budget shedding is counted**: with a 0.5 embed-s/h budget, frame 0
  admits exactly 2 tiles and sheds 14 (frame_end says so), and the cut
  frame sheds all 16 and reports itself at the reflex tier instead of
  going silent.
- **Decision off means zero rack calls**: with
  `decision_enabled = false`, the stub rack receives 0 POSTs, the
  baseline and cut frames emit reflex lines naming their nominated
  tiles, and `shed` stays 0 — yielding is not shedding.
- **No control file**: the pre-ladder behaviour, byte for byte in
  counts (32 posts, no reflex lines) — the fail-open path leaves
  the stream running as it ran before the ladder existed.

## Read a yield in the record

The integration tests leave their ledgers behind (they do not clean
up), so you can read a real yield right after running them — the
artefact directories carry the test's PID; adjust to yours:

```sh
ls -d /tmp/confluence-watch-tenancy-*
grep '"yield_rung"' /tmp/confluence-watch-tenancy-l4-*/ledger/events.jsonl
```

```
{"kind":"service","event":"yield_rung","msg":"L0 -> L1 cause=memory_pressure foreign_gpu_pct=0.0 mem_available_pct=2.0 decision_factor=1.00","wall_us":1793759836126264}
{"kind":"service","event":"yield_rung","msg":"L1 -> L2 cause=memory_pressure foreign_gpu_pct=0.0 mem_available_pct=2.0 decision_factor=0.50","wall_us":1793759836138568}
{"kind":"service","event":"yield_rung","msg":"L2 -> L3 cause=memory_pressure foreign_gpu_pct=0.0 mem_available_pct=2.0 decision_factor=0.00","wall_us":1793759836163127}
{"kind":"service","event":"yield_rung","msg":"L3 -> L4 cause=memory_pressure foreign_gpu_pct=0.0 mem_available_pct=2.0 decision_factor=0.00","wall_us":1793759836199862}
```

Walk one line through — this is the audit trail an operator reads:

- `L2 -> L3` — the transition, one rung per receipt; a reader can
  reconstruct the ladder's whole walk from events.jsonl alone.
- `cause=memory_pressure` — one of `foreign_gpu_load`,
  `interactive_session`, `memory_pressure`, or `recovery`
  (`Cause` in tenancy.rs). Foreign causes carry their evidence:
- `foreign_gpu_pct=0.0 … mem_available_pct=2.0` — **the sample
  figures that caused the step**, verbatim. When a source has no
  reading the field says `unknown`, never an invented number.
- `decision_factor=0.00` — what the new rung does to the decision
  budget (1.00 / 0.5 / 0.0), the same number that lands in
  control.json and state.txt's `budget_effective_embed_s_per_hour`.
- `wall_us` — when, to the microsecond.

The reflex verdict the rung produces looks like this (one of the 46
the L4 run published):

```sh
grep '"unperceived":true' /tmp/confluence-watch-tenancy-l4-*/ledger/events.jsonl | head -1
```

```
{"kind":"verdict","stream":"tenancy-test","frame":4,"wall_us":1793759836175348,"t_capture_us":1793759836175237,"verdict_latency_ms":0.111,"unperceived":true,"basis":"decision tier yielded at rung L3 (memory_pressure); reflex diff only","changed_tiles":[0, 1],"focus":[],"lineage_mask":0,"embeds_this_frame":0,"tiles":[]}
```

Field by field — this is what "yielded silence must never lie" looks
like as data (`Ledger::record_reflex_frame` in ledger.rs):

- `unperceived: true` — no cascade ran on this frame. It is marked,
  not implied.
- `basis: "decision tier yielded at rung L3 (memory_pressure); reflex
  diff only"` — the reason in plain words, written into the event
  itself. A reader five years later needs no other file to know why
  this frame was not perceived.
- `changed_tiles: [0, 1]` — the diff gate's nominations: *something
  moved here*. The reflex tier cannot say what; it says where.
- `focus: []`, `lineage_mask: 0`, `embeds_this_frame: 0`, `tiles: []`
  — no attention ranking, no cascade stage touched the frame (mask 0
  of the 5-bit lineage), no embeds spent, no per-tile scores. The
  record cannot pretend perception happened.
- `verdict_latency_ms: 0.111` — reflex tier latency; the change feed
  degrades in resolution, never in liveness.

The supporting cast, at the same moment:

```sh
cat /tmp/confluence-watch-tenancy-l4-*/ledger/health.txt
grep -E 'yield|budget|tiles_shed|reflex' /tmp/confluence-watch-tenancy-l4-*/ledger/state.txt
cat /tmp/confluence-watch-tenancy-l4-*/ledger/control.json
```

```
embed_ms_p50 = 100.00
embed_ms_p99 = 100.00
embed_ms_n = 8
frames_pending_max = 0
last_frame_age_ms = 13.0
rack = up
yield_rung = L4
yield_reason = memory_pressure
decision_tier = reflex_only
silence_basis = reflex
silence_meaningful = true
updated_wall_us = 1793759836739565
tiles_shed = 0
reflex_events = 46
budget_embed_s_per_hour = 1000000000.0
budget_effective_embed_s_per_hour = 0.0
yield_rung = L4
yield_reason = memory_pressure
{"rung":"L4","decision_enabled":false,"budget_embed_s_per_hour":0.000,"reflective_enabled":false,"backfill_permitted":false,"reason":"memory_pressure","updated_wall_us":1793759836199893}
```

health.txt is the one-glance answer: `silence_basis = reflex` says
this stream's quiet speaks with the reflex tier's voice — diffs
counted, nothing embedded — and `silence_meaningful = true` says even
that quiet is honest (frames are being seen). `decision_tier` reads
`full` / `halved` / `reflex_only` / `reflex_only_models_unloaded`
(`Ledger::decision_tier`). state.txt adds the counters: `reflex_events
= 46`, `tiles_shed`, and the budget pair — base vs the rung-factored
effective figure (0.0 at L4). control.json is the same state as the
ingest sees it.

And because the run never cleans up, you can also read a *recovery*.
The yield test's ledger holds the full down-and-up chain — three
step-downs under 60% foreign load, then three `cause=recovery` steps
up as the clear interval elapsed — and the flap test's ledger holds
`0` `yield_rung` receipts after 400 alternating samples:

```sh
grep '"yield_rung"' /tmp/confluence-watch-tenancy-yield-*/ledger/events.jsonl
grep -c '"yield_rung"' /tmp/confluence-watch-tenancy-flap-*/ledger/events.jsonl
```

```
{"kind":"service","event":"yield_rung","msg":"L0 -> L1 cause=foreign_gpu_load foreign_gpu_pct=60.0 mem_available_pct=50.0 decision_factor=1.00","wall_us":1793759836163147}
{"kind":"service","event":"yield_rung","msg":"L1 -> L2 cause=foreign_gpu_load foreign_gpu_pct=60.0 mem_available_pct=50.0 decision_factor=0.50","wall_us":1793759836187671}
{"kind":"service","event":"yield_rung","msg":"L2 -> L3 cause=foreign_gpu_load foreign_gpu_pct=60.0 mem_available_pct=50.0 decision_factor=0.00","wall_us":1793759836224533}
{"kind":"service","event":"yield_rung","msg":"L3 -> L2 cause=recovery foreign_gpu_pct=0.0 mem_available_pct=50.0 decision_factor=0.50","wall_us":1793759837192568}
{"kind":"service","event":"yield_rung","msg":"L2 -> L1 cause=recovery foreign_gpu_pct=0.0 mem_available_pct=50.0 decision_factor=1.00","wall_us":1793759837291477}
{"kind":"service","event":"yield_rung","msg":"L1 -> L0 cause=recovery foreign_gpu_pct=0.0 mem_available_pct=50.0 decision_factor=1.00","wall_us":1793759837402772}
0
```

## The honest edges

Stated plainly, from the spec's implementation note and the code —
these are the limits an operator should know before relying on the
ladder:

- **L1/L2's reflective flags have no consumer inside slice 1.** The
  cascade built here (perceive → decide → direct → refine → publish)
  has no reflective stage, so `reflective_permitted = false` at L2 is
  computed and published — control.json, state.txt — and nothing in
  this service reads it. Who will read it, when built: the platform's
  reflective tier (§1's lanes — sampled judgment over decision
  output: chaptering and highlights for library titles, programme
  identification for live feeds, and the lens/ranker refit samples of
  §3.1) plus backfill Pass 3; those are co-located processes, and the
  flag is published precisely so they can gate on the ledger's own
  state files instead of a private channel. Until they exist, the
  flag is a promise kept to a consumer that has not been written.
- **L4's owned-rack unload path is code-reviewed, not test-covered.**
  The path runs `sudo -n systemctl stop jev-rack` (`systemctl` in
  service.rs) — real system state, with no injection seam. The
  integration tests run against a stub rack with
  `rack_autostart = false`, so the service never owns the rack and L4
  always takes the *not-owned* branch — which is test-covered and
  receipted (`yield_models_not_owned`). Covering the owned branch in
  a test would mean a suite that starts and stops a real systemd unit
  on whatever machine runs it. The owned path is receipted on both
  success (`rack_stop` / `rack_start`) and failure
  (`rack_stop_failed` / `rack_start_failed`), but its proof is
  review, not a test.
- **Yield latency is still TO-MEASURE** (§2.3 names it, alongside
  false-yield rate). What measuring it needs: a controlled foreign
  GPU workload started at a known timestamp on the real Thor (a box
  whose nvidia-smi can attribute — on this tutorial's Tegra machine
  the utilisation query answers `[N/A]`, so the probe correctly reads
  "no data" and the ladder never yields there), plus a marker for the
  last platform kernel (rack-side timing or nvidia-smi's query
  timestamps), differenced against the `yield_rung` receipt's
  `wall_us`. The end-to-end budget to expect is sampler cadence
  (≤2 s) + sustain (5 s) + in-flight embeds draining (one embed
  ≈173 ms — in-flight embeds finish, nothing new launches).
- **The reserved watching pool (§2.3 item 4) is multi-stream and
  unbuilt.** A stream the user is actively watching is to draw its
  decision budget from a reserved 10% of global that background
  streams cannot touch — watching is a tenancy signal, not a budget
  line. That needs the multi-stream scheduler; this service is one
  stream, and the implementation note says so.

## Operating rules of thumb

- **Yield is a receipted event, never a silent degradation.** Every
  rung move lands in events.jsonl with the sample figures that caused
  it; if a yield is not in the ledger, it did not happen.
- **Silence always carries its basis.** `silence_basis` and
  `decision_tier` in health.txt, `basis` in every unperceived
  verdict: a quiet stream at a reflex rung never gets read as a quiet
  stream that perceived nothing happening.
- **The box is left as found.** The rack is stopped only if this
  service started it; models it does not own are receipted and left
  running; the reload cost of an unload is paid on recovery, not by
  the user's work.
- **A ladder that flaps is worse than a ladder that lags.** The
  sustain gate, the 60 s clear interval, one rung per interval, and
  the 30,000-sample no-flap proof all exist so a bursty workload at
  the threshold cannot make perception oscillate.
- **The yield system fails open.** A control file that is missing,
  torn, or unreadable reads as "no orders" — decision on, no budget
  cap — because the protector's own failure must not blind the
  stream it protects. When you find such a run in a ledger, the
  pre-ladder behaviour is the explanation, not a bug in your ladder.
