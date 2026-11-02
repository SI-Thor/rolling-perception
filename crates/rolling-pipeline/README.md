# rolling-pipeline — the integrated cascade

The two sibling crates prove pieces in isolation: `rolling-perception`
has schedulers and lanes that call each other directly;
`rolling-substrate-core` has rings, a Laplacian, lineage and gating
that nothing routes a payload through. This crate wires them into the
one thing the seed email actually described — an end-to-end cascade
with a feedback loop:

```
producer ─ring─▶ perceive ─ring─▶ decide ─ring─▶ direct ─ring─▶ refine ─ring─▶ publish
                    ▲                                                              │
                    └──────── gate (viewport), set by direct, ◀───────────────────┘
                                consumed by perceive on its NEXT pass
```

## How it works

- **Data travels in rings, not calls.** One ring per stage edge,
  capacity 8, payload = one 8×8 f32 grid per message. Five edges are
  substrate-core `SpscRing`s; the last (`publish → world`) is a
  `FluidSubstrateBuffer` publish point — see **Ring placement**
  below for the audit behind the split. Every stage is the same
  skeleton (`src/lib.rs`): receive the one in-flight payload from
  its input lane, advance its lineage, work, send it down the
  output lane. Ticks are strictly sequential.
- **Lineage accumulates across edges.** On the SPSC edges the
  payload itself carries a `LineageSnapshot` (visited bitmask +
  per-stage counts — plain values); each stage advances it by its
  own visit before handing the payload on. On the final Disruptor
  edge the snapshot is replayed into the slot header (headers are
  cleared when a slot is re-leased, so the replay is what the
  header shows) and the completed lineage is captured back out.
  Either way the published payload genuinely shows every stage,
  exactly once: `perceive:1 decide:1 direct:1 refine:1 publish:1`,
  mask `11111`. A small control record (`TickMeta`) carries
  decide's signal summary alongside the rings, with the lineage
  snapshot mirrored into it as stages advance — control state, not
  payload data, and labelled as such.
- **Director with deadband + hysteresis.** `decide` computes the
  |value|-weighted centroid of the payload. `direct` rounds it to a
  target cell; if the target is within the deadband (1 cell, Chebyshev)
  of the current gate centre the gate is **held**, otherwise the centre
  moves at most 2 cells toward it. The resulting 4×4 viewport is what
  `perceive` gates on during the **next** tick — tick 0 perceives the
  full frame, every later tick perceives the director's gate.
- **Refine is a real sheaf step.** One Laplacian gradient step
  (α = 0.1, line graph over the 64 cells) per payload, with the energy
  asserted non-increasing *per payload* inside the stage — not sampled,
  not averaged: a single increase fails the run.
- **Savings are counted, not timed.** `perceive`'s kernel runs through
  substrate `gated_apply`, whose closure-call count is the op count.
  The demo reports `perceive gated / ungated baseline` from counters
  first (full frame = 64/payload, director gate = 16/payload); wall
  times appear afterwards and are never the proof.

## Ring placement (the D12 audit)

ARCHITECTURE claim D12, settled by `docs/RING-BENCH.md`: the
shipped Disruptor ring, consumed as a queue (poll `is_published` +
`read_published` — the only consumer its API offers), **tore
5–27% of a million reads silently** — it has no consumer release,
no drop policy, no counters. The §3.2 `SpscRing` is faster *and*
accounts for every message (INV-R4). So: **SPSC takes every
per-lane cascade queue; the Disruptor keeps only genuine
multi-producer junctions and latest-value publish points.**

This crate's topology, audited from the code (every edge is driven
by exactly one stage on each side; ticks are sequential):

| edge | producers | consumers | semantics | placement |
|---|---|---|---|---|
| producer → perceive (`in`) | 1 (the tick caller) | 1 (`perceive`) | ordered queue, exactly-once | **SpscRing** |
| perceive → decide (`perceived`) | 1 | 1 (`decide`) | ordered queue, exactly-once | **SpscRing** |
| decide → direct (`decided`) | 1 | 1 (`direct`) | ordered queue, exactly-once | **SpscRing** |
| direct → refine (`directed`) | 1 | 1 (`refine`) | ordered queue, exactly-once | **SpscRing** |
| refine → publish (`refined`) | 1 | 1 (`publish`) | ordered queue, exactly-once | **SpscRing** |
| publish → world (`ring_out`) | 1 | **0** (no queue consumer) | latest-value publish point | **Disruptor (kept)** |

`ring_out` qualifies under D12's second clause: `publish` returns
the payload to the caller directly as `Published`; the ring is a
finalized publish surface whose slot header carries the completed
lineage, and nothing anywhere calls `is_published` /
`read_published` on it — the torn-read failure mode needs a queue
consumer, and there is none. There are no multi-producer junctions
in this cascade today; if one ever appears (e.g. several perceive
lanes feeding one decide), *that junction* is where a Disruptor
belongs, not the lanes feeding it.

The migrated edges run `Policy::Block`: the sequential cascade
never actually blocks (each lane holds at most one in-flight
payload), and Block is the policy whose semantics — nothing is
ever lost — the cascade was written against. A lost message is
now loud anyway: a stage receiving from an empty lane panics
naming the tick and edge, where the Disruptor would have handed
back a torn or stale slot.

Two consequences worth knowing:

- **Lineage moved into the payload.** SPSC slots have no header,
  so the snapshot rides inside the message (see *How it works*);
  the values are bit-for-bit the ones the header dance produced.
- **Conservation is now checkable.** `Pipeline::edge_stats()`
  exposes each migrated edge's INV-R4 counters. The proof lives in
  `tests/ring_stress.rs`: two pipelines in lockstep over 250,000
  payloads must agree bitwise on every checksum and payload
  element, then one continues to 1,000,000 messages (125,000 wraps
  of every ring), after which every edge must read
  `produced == consumed == 1,000,000` with zero drops — the test
  the old ring could not have passed, or even reported on. A side
  effect of dropping the per-handoff `Vec` copies: a tick costs
  ~2.1 µs (release, dev VM) against ~2.7 µs before the migration,
  with checksums bit-identical across the change.

## Schedulers

The same cascade runs under both schedules (semantics from
`rolling-perception`): **batched** waits for each cycle's last arrival
and emits one output per cycle; **rolling** runs each payload the
moment its own arrival lands and emits per payload. Work, op counts
and total checksum are asserted identical across the two — scheduling
is the only variable. The only `sleep` models sensor arrivals and is
labelled as such at the call site.

## Composition: adaptive timing + the executor seam

The wave crates were built as separate demos; this crate is where
two of them stop being demos and start composing.

**Adaptive → pipeline.** The schedulers above release payloads on
their *recorded* arrivals — a fixed-stagger assumption wearing the
trace as a costume. `run_rolling_adaptive` instead drives release
timing from `rolling-adaptive`'s `LensFile`: the cascade's input is
treated as one stream, the lens observes every arrival causally,
and each payload is released at the lens's prediction
(`max(arrival, prediction)` — an early prediction cannot release
data that has not landed; a late one delays the release by exactly
its error, the consequence the sibling crate's executor simulation
grades). Work, order and outputs are untouched, so the connected
system must publish bit-for-bit what the fixed-stagger baseline
publishes — and the test asserts it does. Measured under injected
drift (period 400 µs growing 25 µs/cycle to 675 µs, 60 payloads,
`tests/composition.rs`): per-payload checksums and counted ops
identical to the baseline, while release-prediction p95 is
**60.5 µs for the lens vs 7,425.0 µs for the fixed-stagger control**
graded on the identical stream in the same run; the lens's period
estimate ends at 635.1 µs against the true 675 µs. `rolling-adaptive`
needed no API additions — `LensFile::{predict_next_us, observe}` and
its `stats` were already the right surface.

**CUDA shadow → substrate, at the seam — measured, and blocked in
the open.** `src/executor.rs` is the trait seam where the GPU
backend lands: an `Executor` turns one payload into one
`Published` under a stated contract (identical outputs, complete
lineage, non-increasing sheaf energy, counted ops). `Pipeline`
implements it as `"cpu-rings"`, the shipped backend. The module's
execution notes record how the Thor spikes' **two-stream shadow**
arrangement (production stream + shadow stream, host one slice
ahead; persistent kernels lose for slice work) maps onto the
stages, and `intended_placement` encodes that map in code:

| stage | intended | actual today |
|---|---|---|
| perceive | GPU, production stream | CPU (no kernel exists) |
| decide | GPU, production stream | CPU (no kernel exists) |
| direct | CPU, permanently | CPU |
| refine | GPU, shadow stream | **not run — tick refused** |
| publish | CPU, permanently | CPU |

The `gpu-shadow` fill (2026-11-01, this round) wired the executor
for real up to the exact point `cuda-thor`'s public API (v0.2)
stops. Construction now probes the device through that API —
verified on the Thor itself: driver init + primary context +
`cuMemGetInfo` reported the device present (free 19,431,636,992 /
total 131,856,920,576 bytes at probe time) — and every attempted
tick appends a placement receipt (`TickReceipt`: per-stage
`StageRun`, refusal included). Every tick is then **refused,
typed**: `NoGpuBackend` when the probe finds no device,
`GpuApiGap` when it finds one. No stage closures run under the
GPU name; a fallback that did would print correct numbers on a
false receipt, which is worse than a refusal.

The gap is five specific absences in `cuda-thor/src/gpu.rs`, each
independently sufficient to stop the refine stencil (an `f64`
graph Laplacian step — the pipeline's only kernel-shaped stage):

1. `nvrtc_compile` is a private fn — no public kernel compilation.
2. `Module::load` hardcodes the kernel name `"perceive"`.
3. `Module::launch` hardcodes the perceive signature
   (`f32` in → `f32` out, `i32 n`, grid from `n`) — no edge list,
   no `alpha`, no `f64` buffers.
4. `DevBuf::upload` takes `&[f32]` only — an `f64` section cannot
   even be staged; there is no public async download either.
5. `Gpu` owns exactly one stream and exposes no stream creation —
   the two-stream shadow has no second stream.

**The smallest cuda-thor additions that unblock the fill**
(specified here, not implemented — that crate is another lane's):
(a) make the existing compile path public
(`pub fn compile(source, arch_flag, want_cubin)` over
`nvrtc_compile`); (b) `Module::load_named(image, kernel_name)`;
(c) one generic launch,
`unsafe fn launch_args(&self, stream, args: &mut [*mut c_void], grid, block)`;
(d) byte-level copies: `DevBuf::upload_bytes(&[u8])` and a
`cuMemcpyDtoHAsync` wrapper; (e) `Gpu::new_stream()` returning an
RAII stream handle. All five wrap FFI that already exists in
`gpu.rs`; none changes existing behaviour.

**The crossover, as far as it can honestly be measured today.**
The GPU side is unmeasurable until the gap closes, so what was
measured is the bar it must clear — CPU `smooth_step` medians on
the Thor (release build, `tests/gpu_shadow.rs`): **0.268 µs at
the fixture's line(64) graph; 10.04 µs at line(4,096)**. Against
that bar: the wave-2 spikes measured launch-bound pickup at
p50 1.1 µs — one launch's pickup alone is ~4× the entire CPU
stencil at fixture scale, before any upload, download, or sync.
Verdict: GPU refine **cannot win at the fixture's scale**, and at
4,096 nodes a win would need the round trip (two copies + launch
+ sync) to fit inside ~10 µs, which the measured pickup makes
implausible for one-shot launches; if a crossover exists for this
stencil it lies above 4,096 nodes or behind a batched/persistent
arrangement the spikes already rejected for slice work. That is
a reasoned bound from measured parts, labelled as such — not a
GPU measurement, because there isn't one.

**One end-to-end demo.** `src/bin/endtoend.rs` runs the whole
composition over the fixture stream and prints the per-tick trace
(stage durations, lineage mask, sheaf energy before/after, release
error, checksum) that `tests/composition.rs` asserts invariants
over (mask `11111` and energy down on *every* tick; verdict set
equal to the plain sequential cascade's):

```sh
cargo run --release -p rolling-pipeline --bin endtoend
cargo test  -p rolling-pipeline          # incl. composition tests
cargo check -p rolling-pipeline --features gpu-shadow   # type-checks anywhere
# on the Thor (the only place a gpu-shadow build links):
cargo test --release -p rolling-pipeline --features gpu-shadow -- --nocapture
#   -> real-device probe, the typed GpuApiGap refusal, CPU stencil medians
```

## Trace files (file-replay producer)

Format **rolling-trace v1**, plain text:

```
# rolling-trace v1
# columns: arrival_us, then 64 payload floats (8x8 row-major)
0 0.912331 0.031204 ... (64 floats total)
400 0.884120 ...
```

- Lines starting with `#` and blank lines are ignored.
- `arrival_us` is the offset in microseconds from the trace's start;
  the demo re-bases arrivals per cycle chunk.
- Payload floats are whitespace-separated, row-major 8×8.

Generate one with the bundled tool, then replay it:

```sh
cargo run --release --bin trace-gen -- --out trace.txt --entries 24 --stagger-us 400
cargo run --release --bin pipeline-demo -- --trace trace.txt
cargo run --release --bin pipeline-demo            # synthetic, same generator in memory
cargo test
```

The generated trace is deterministic: a Gaussian hotspot drifting
across the grid over LCG noise — a signal with somewhere to go, so the
director's moves and deadband holds are both exercised.

## What this does not claim

Single-threaded CPU cascade. The rings are the substrate's real
rings (five §3.2 SPSC queues, one Disruptor publish point), but
this crate drives them sequentially — the concurrency claim
belongs to substrate-core's own tests (including the SPSC ring's
two-thread property test), and the GPU claims belong to the Thor
experiments. Nothing here sleeps *as* compute, mocks a kernel, or
reports a simulated number as measured.
