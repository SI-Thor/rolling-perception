# Rolling Perception — Design (v0.1, with v0.2 seams)

**Status:** Private design record, companion to `PLAN.md` in this directory.
**Scope of this document:** module layout, data structures, the ring's sequence
protocol, scheduler and clock design, invariants, concurrency reasoning, and
failure modes for the pure-Rust CPU implementation (v0.1). The v0.2 CUDA
executor is specified only as a *seam* (§9) — enough that v0.1 code does not
paint it into a corner, not so much that we design a GPU system we have not
measured yet.
**Binding rule (from `PLAN.md` §8):** no claim without a test or bench. Where
this document states a property, it names the test that enforces it. Where it
states a hope, it says **hypothesis**.

---

## 0. Process — how this design was reached, in the body

1. **Started from the email's structures and stress-read them as concurrent
   code.** The seed's `FluidSubstrateBuffer` was the natural starting point:
   a power-of-two ring, `#[repr(align(64))]` slots, atomic sequence IDs, a PIR
   token per slot. Three defects fell out of a careful read (§3.3), and fixing
   them — rather than taste — drove most of this design.
2. **Dead end: Vyukov bounded MPMC queue as the v0.1 ring.** It is a known-good
   algorithm and would have matched the email's "multi-producer" story. Rejected
   for v0.1 after listing what it costs us: (a) its correctness argument is
   subtle enough that reviewing fleet-seat code against it is unrealistic
   without loom models we would have to build anyway; (b) no v0.1 consumer
   needs two producers writing the *same* ring — each lane has exactly one
   producer by construction. Per-lane SPSC keeps the interesting protocol
   questions (sequencing, wrap, backpressure) and deletes the unneeded ones.
   MPMC returns in v0.4 only behind a loom-verified design (PLAN §7).
3. **Dead end: payload in a seqlock-protected shared buffer ("latest value"
   semantics instead of a queue).** Attractive for perception (only the newest
   frame matters, right?) — rejected as the *only* channel because benches
   need to account for every produced slice (dropped work must be counted, or
   the rolling-vs-batched comparison is rigged). Kept as a *policy*: the ring
   with drop-oldest + counters gives latest-value behaviour with accounting.
4. **Dead end: prime-product lineage with a wider integer (u128 / bignum).**
   Considered while trying to salvage PIR "as designed, just bigger". It fixes
   nothing that matters: counts are still lost at any width, and ordering is
   lost at any width. Width was never the (only) problem; the encoding itself
   answers a weaker question ("did p ever divide S?") than the one we need
   ("which nodes ran, how many times, in which slot generation?"). Counted
   lineage (§5) answers the real question for ~130 bytes. Autopsy tests for
   PIR are specified in PLAN §5.4.
5. **Settled on:** one crate, plain modules, SPSC rings, a `Node` trait with
   two schedulers over it, a logical clock for determinism, counted lineage,
   graph-consensus sheaf, tile gate with op counting. Every choice below lists
   the alternative it beat and why, briefly, at the point of decision.

---

## 1. Module layout

Single crate in v0.1 (PLAN §4 — splitting is earned, not assumed).

| Module | Responsibility | Must not do |
|---|---|---|
| `clock.rs` | `Clock` trait; `LogicalClock` (tick counter, deterministic) and `MonoClock` (`std::time::Instant`, benches only) | Never let wall time leak into deterministic mode |
| `slot.rs` | `SlotHeader`, slot state machine, `CacheAligned<T>` wrapper | No policy (no drop/block decisions here) |
| `ring.rs` | `SpscRing<P>` — bounded ring of slots over a payload type; claim/publish/acquire/release; backpressure policy enforcement + counters | No knowledge of nodes, lanes, or payload meaning |
| `lineage.rs` | `NodeRegistry`, `NodeId`, `Lineage` (bitset + saturating counts + overflow flag) | No primes (see `pir.rs`) |
| `pir.rs` | **Experiment only.** The email's scheme, fenced, with failure-demonstrating tests | Never imported by non-test, non-example code; enforced by a CI grep on `use` sites |
| `sheaf.rs` | Overlap graph (CSR), incidence application, Laplacian energy, relaxation step, spectral bound estimate | No allocation in the step (buffers pre-allocated) |
| `gate.rs` | `TileGrid`, `Gate` (tile bitset), gate policies' shared geometry, `OpCounter` | No scheduling decisions |
| `node.rs` | `Node` trait, `NodeCtx`, stage IDs for the perceive/decide/direct/refine/publish pipeline | No I/O, no threads |
| `workloads.rs` | The real-arithmetic node implementations + naive references for each | No timing, no `sleep` |
| `scheduler.rs` | `Scheduler` trait, `BatchedScheduler`, `RollingScheduler`, phase tables | No arithmetic of its own (all work happens inside nodes, so op counts stay honest) |
| `metrics.rs` | `MetricsSink`, histograms (TTFU, inter-update, staleness), snapshot/age types | No formatting/IO beyond serialising recorded data |
| `replay.rs` | Input trace recording/loading; deterministic replay driver | No wall clock |
| `lib.rs` | Public surface, crate docs, claim labels for anything the docs assert | — |

Binaries/examples: `examples/rolling_demo.rs`. Benches under `benches/` mirror
the PLAN §5 suites: `rolling_vs_batched`, `gating`, `sheaf`, `ring`.

**Dependency budget:** std only for the lib, plus dev-dependencies `criterion`,
`proptest`, and `loom` (cfg-gated). If a proposed dependency does not serve a
test or a bench, it does not enter v0.1.

---

## 2. Core vocabulary types

```rust
pub struct LaneId(pub u8);          // producer lane, registry-assigned
pub struct NodeId(pub u8);          // compute stage instance, registry-assigned (<= 64 in v0.1)
pub struct Seq(pub u64);            // per-lane monotonic sequence, starts at 0, never reused
pub struct Tick(pub u64);           // logical-clock tick
pub struct Stamp { pub seq: Seq, pub tick: Tick, pub mono_ns: Option<u64> }
                                    // mono_ns present only in bench (non-deterministic) mode
```

`Stamp` is where Casey's *dated readings* live: every payload carries when it
was produced and in which order, so a consumer can always answer "how old is
this, and what is it missing?" — staleness is computed from stamps, never
inferred from arrival order.

---

## 3. The slot and the ring

### 3.1 Slot layout

Two allocations per slot, deliberately separated:

```
SlotHeader — exactly one cache line, #[repr(C, align(64))], 64 bytes total:
 offset  size  field
 0       8     sequence: AtomicU64      — protocol state (see 3.2), NOT the payload's Seq
 8       8     stamp_seq: u64           — payload's Seq, written before publish
 16      8     stamp_tick: u64          — payload's logical tick
 24      4     len: u32                 — valid elements in payload
 28      4     lane: LaneId + flags: u8 (HAS_OVERFLOWED_LINEAGE etc.) + _pad: [u8; 2]
 32     24     lineage_present: [u64; 1] is folded into lineage block below — see note
 ...
 32     32     (reserved for lineage summary + backpressure counters snapshot)
 56      8     _tail_pad to 64

Payload — separately allocated Box<[f32]>-equivalent buffer, 64-byte aligned start,
           capacity fixed at ring construction (the "section" a stage reads/writes).
           Kept out of the header allocation so producer writes to payload and
           consumer reads of the header state do not share a cache line.
```

Implementation notes that matter more than the exact offsets (offsets are
fixed by a `const` size assertion test: `size_of::<SlotHeader>() == 64`):

- `Lineage` in full (bitset + 64 × u16 counts ≈ 136 bytes) does **not** fit a
  single cache line, and pretending otherwise is how false economy starts.
  Decision: the header carries a `lineage_version: u64` and the full `Lineage`
  lives at the head of the payload allocation, written before publish, read
  after acquire. The header stays one line; the lineage rides with the data it
  describes. Alternative rejected: shrinking counts to u8 to fit — saturation
  at 255 is reachable by a fast stage in a single slot generation in our own
  scenarios (§5), which would make the overflow path the common path.
- Alignment is asserted, not assumed: `assert_eq!(align_of::<SlotHeader>(), 64)`
  and an allocation test checks the payload base address mod 64 == 0. What we
  may claim from this is narrow and we claim only it: header state and the
  neighbouring slot's header do not share a cache line *on machines with
  64-byte lines*, which the test verifies for the build target's reported line
  size where available. "Prevents false sharing, therefore fast" is a bench
  question (PLAN §5, `ring` bench), not a layout conclusion.

### 3.2 Sequence protocol (per slot, SPSC)

> **Amendment A (2026-11-01) — drafted from measurement, Casey's
> approval on record in the build chat.** Evidence:
> `docs/RING-BENCH.md` (the §3.2 ring implemented as written in
> `crates/rolling-substrate-core/src/spsc.rs`, property-tested, and
> benched head-to-head against the shipped ring); status tracked as
> claim D12 in `docs/ARCHITECTURE.md`.
>
> **The engine has two rings, in two placements:**
>
> 1. **Per-lane cascade queues — `SpscRing`, the protocol specified
>    below.** Each lane has exactly one producer by construction
>    (§0.2's premise, still true), and on those links the consumer is
>    a protocol party: its release store *creates* the producer's
>    next claim right, so a slow stage gets **backpressure instead
>    of silent data loss**, and the ring carries the INV-R4
>    conservation accounting of §3.4
>    (`produced == consumed + dropped_newest + dropped_oldest +
>    in_flight`, exposed via `RingStats`, asserted at drain in tests
>    for all three drop policies). Measured on the pipeline's
>    message pattern (`[f32; 8]`, 1M messages, two threads,
>    RING-BENCH §4): throughput **6.65–11.37 M msgs/s** across four
>    pairings vs the shipped ring's 2.59–5.55; ping-pong median
>    **0.35 / 0.82 µs** vs 1.47 / 1.58 µs.
> 2. **Genuine multi-producer junctions and latest-value publish
>    points — the shipped Disruptor claim/finalize ring**
>    (`substrate.rs`). Several producers finalizing into one buffer
>    via a `fetch_add` claim is the one capability SPSC refuses, and
>    at a latest-value point an overwritten sample is the *intended*
>    behaviour, not a loss. There its costs (atomic claim, no
>    consumer accounting) buy the right thing.
>
> **Refuted placement:** the shipped Disruptor ring consumed as a
> paced queue. It has no consumer release, no drop policy, and no
> counters; benched the only way its API allows (poll
> `is_published`, then read), it **tore 5.2–27.4% of 1M reads
> silently in every run** (52k–274k reads). That use does not
> survive this amendment; a call site that polls `is_published`
> from another thread is to be treated the way this repo treats a
> failed test.
>
> §3.4's drop policies required two repairs this section never
> stated (RING-BENCH ambiguities A1/A2); they are recorded in
> Amendment A at §3.4. The original §3.2 text follows verbatim.

#### Original §3.2 (superseded — preserved verbatim)

One producer thread and one consumer thread per ring in v0.1. Each slot cycles
through generations. Slot `i` has a protocol counter `sequence` with this
meaning (a simplified, SPSC-specialised descendant of the Disruptor/Vyukov
per-slot sequence scheme):

- **Initialisation:** `sequence[i] = i` (slot is free for generation `i`).
- **Producer claim:** for message with global per-lane counter `n`, target slot
  is `i = n & mask` (capacity is a power of two, asserted at construction).
  The producer may write the slot iff `sequence[i] == n` (slot free for this
  generation), subject to the backpressure policy (§3.4) if it is not.
  It then writes payload, stamps, and lineage — plain writes, no atomics —
  because SPSC + the acquire/release pairing below gives it exclusive access.
- **Publish:** `sequence[i].store(n + 1, Release)`. State `n + 1` means
  "generation `n` is ready to read".
- **Consumer acquire:** consumer expecting message `m` (its own per-lane read
  counter, starting at 0) polls/blocks on slot `j = m & mask` until
  `sequence[j].load(Acquire) == m + 1`. It then reads payload/stamps/lineage.
- **Release:** after reading, `sequence[j].store(m + capacity, Release)`,
  i.e. "free for generation `m + capacity`" — exactly the value the producer
  of that future generation will claim against.
- **Ordering discipline:** only the `sequence` word is atomic. `Release` on
  publish pairs with `Acquire` on acquire, so all payload writes that happened
  before publish happen-before the consumer's reads; likewise release/acquire
  on the free transition protects the next generation's writes. Counters in
  `metrics` are the only `Relaxed` atomics permitted, and they are never used
  for synchronisation. Any PR touching an `Ordering` must justify it (PLAN §8.5).

**Proof sketch (the level a reviewer should demand, no more):** exclusivity
follows because `sequence[i]` takes each generation's values in a fixed order
(free-for-n → ready-n → free-for-(n+cap)) and each transition is performed by
exactly one party (producer does free→ready, consumer does ready→free), with
the value acting as the token. The loom model (§8) enumerates the interleavings
for capacity 2 / 3 messages and asserts: no read of a slot in the wrong
generation, no overwrite of an unread slot under the block policy, exactly-once
in-order delivery.

### 3.3 What was wrong with the email's protocol (analysis, preserved)

Reading `lease_slot_for_execution` / `finalize_write` in the seed as a protocol:

1. `finalize_write(slot)` ignores which lease it is finalising: it loads the
   *current global* `write_cursor` (advanced by every later lease, possibly on
   other threads) and stores `cursor + capacity` as the slot's sequence. Two
   concurrent leases therefore publish sequences derived from whichever cursor
   value wins the race — a slot can become "ready" with a sequence no consumer
   is waiting for, or never become ready at all.
2. `lease_slot` spins while `sequence_id != current_cursor`, but a slot's
   initial `sequence_id` is its *index*, while cursors are global and grow past
   capacity immediately; on the second wrap the awaited equality may have
   already passed (the finaliser stored `cursor + capacity`, not `cursor`),
   giving a spin that waits for a value the protocol will never write again —
   a livelock, not a lock-free success.
3. There is no consumer-side protocol at all in the listing: no acquire, no
   release, no statement of who may read a slot or when it may be reused.
   "Multiple models read and write identical addresses with zero lock overhead"
   is asserted over a protocol that does not define concurrent reading.
4. The payload behind `data_pointer` is handed out as a raw `*mut f32` to any
   caller with no lifetime or generation check — use-after-reuse is available
   to correct-looking call sites.

Lesson recorded for reviewers: the failure mode was not "Rust was wrong" —
individual lines are plausible — it was that *the protocol as a whole was never
stated*, so no line could be checked against it. Hence §3.2 states ours before
any code, and §7 ties each invariant to its test.

### 3.4 Backpressure policy (per ring, chosen at construction)

> **Amendment A (2026-11-01) — drafted from measurement, Casey's
> approval on record in the build chat.** Evidence and full
> ambiguity log: `docs/RING-BENCH.md` §2 (A1–A5). The policies below
> are `SpscRing`'s, as built and property-tested; the shipped
> Disruptor ring has no drop policies and no counters (§3.2
> Amendment A), so the INV-R4 invariant stated under the original
> table holds for `SpscRing` and is asserted at drain in its tests
> for all three policies.
>
> - **`DropNewest` as originally written is unimplementable**
>   (A1). A dropped generation is never published *and never
>   released*, so the slot's free-value for generation
>   `m + capacity` is a number no party ever stores — one drop
>   wedges the ring permanently. **Shipped semantics:** (a) a
>   producer-head gap signal — the producer publishes its next
>   counter in a ring-level `producer_head` atomic, stored
>   `Release` *after* the publish or drop it describes and read
>   `Acquire` only for gap detection, never for payload
>   synchronisation, which remains solely the slot sequence's job
>   as §3.2 demands; (b) consumer release-on-skip — a consumer
>   skipping a dropped generation performs that generation's
>   release store (`m + capacity`). Proven against a naive queue
>   model under random schedules (400 messages; counters meet
>   exactly at drain; sends succeed after a gap — the wedge case).
> - **`DropOldest` is a policy override of §3.2's claim
>   precondition** (A2): the producer reclaims when
>   `sequence[i] == n − capacity + 1` (published, unread),
>   destroying the stale payload in place. **Caveat:** a consumer
>   caught mid-copy by a reclaim revalidates the slot sequence
>   after copying and discards a torn copy (counted as
>   `dropped_oldest`); a formally race-free treatment would need
>   a consumer-progress signal §3.2 does not provide, and that gap
>   is stated, not papered over. Threaded property tests exercise
>   `Block` (the policy INV-R2/R3 are stated under); `DropOldest`
>   is verified against the naive model single-threaded and under
>   random schedules.
> - **`Block`** (A3): "park" names no primitive in the original.
>   Shipped form is spin (`spin_loop`) escalating to `yield_now`,
>   no park; the `blocked_ns` accounting in the table is
>   implemented as specified.
>
> The original §3.4 follows verbatim.

#### Original §3.4 (superseded — preserved verbatim)

| Policy | Producer behaviour when the target slot is not free | Accounting |
|---|---|---|
| `Block` | Spin-with-backoff, then park (bench mode: spin only, and say so) | `blocked_ns` total recorded |
| `DropNewest` | Abandon this message, advance producer counter past it | `dropped_newest += 1`; consumer sees a sequence gap of known size |
| `DropOldest` | Consumer-side: when acquiring, if the producer has lapped it, skip the read counter to the oldest surviving generation | `dropped_oldest += skipped`; gaps visible in consumer's sequence |

Invariant across all three: **loss is always exactly accounted** — for any run,
`produced == consumed + dropped_newest + dropped_oldest + in_flight`, asserted
by a test at shutdown and by the bench harness before it accepts a result.
A policy that loses silently does not get added.

---

## 4. Shared state and the sheaf module

- The shared state is a set of **sections**: one payload-sized `f32` block per
  (lane, stage-output) pair registered at pipeline construction, each with its
  own `Stamp` and `Lineage`. Sections are *not* one global array: the overlap
  graph (§ below) is what relates them, and unrelated sections never interact.
  (This is the honest residue of the email's "Global Latent Manifold": a named
  set of blocks + an explicit relation graph, nothing mystical.)
- `sheaf.rs` data structures:
  - `OverlapGraph { n_sections, edges: CSR (offsets, neighbours, edge_id) }` —
    built once, immutable thereafter in v0.1.
  - Incidence application without materialising $D$: for edge $e=(a,b)$ over an
    overlap coordinate set $O_e$, $(Ds)_e = s_a[O_e] - s_b[O_e]$ (identity
    restriction maps — the consensus special case, PLAN §5.3). For v0.1 the
    overlap set is "the whole section" or a fixed coordinate range per edge;
    both are represented, the general per-element map is not.
  - `energy(s) -> f64`: accumulates $\lVert Ds \rVert^2$ in `f64` even though
    sections are `f32` — energy is a diagnostic and must not drown in the data's
    own rounding; the tolerance in the monotonicity test is stated against this.
  - `step(s, alpha, scratch)`: $s \leftarrow s - \alpha L s$ computed as
    $s - \alpha D^{T}(Ds)$ using a pre-allocated edge scratch buffer; no
    allocation (asserted by a counting-allocator test in debug builds).
  - **Amendment A note (2026-11-01):** the no-allocation property above was contradicted by the first build (`laplacian_apply` allocated a fresh `Vec` per call); it is now **proven** — `laplacian_apply_into` writes into a pre-allocated output with zero allocations in steady state, asserted by the counting-allocator test `crates/rolling-substrate-core/tests/sheaf_alloc.rs` with bitwise parity against the legacy path (`docs/ARCHITECTURE.md`, claim D11).
  - `spectral_bound(graph) -> f64`: power iteration on $L$ at setup (fixed
    iteration count, recorded); step sizes are validated `0 < alpha <= 2/lambda`
    and construction with an out-of-range `alpha` is an error, not a clamp.
- **Invariants:**
  - INV-S1: `energy(s) >= 0` for all `s` (property test).
  - INV-S2: for a connected graph and valid `alpha`, one step does not increase
    energy beyond the stated FP tolerance (property test, PLAN §5.3).
  - INV-S3: the averaging form preserves the per-component weighted mean
    exactly (up to FP tolerance); the gradient form's invariant is energy
    monotonicity only — the code and docs must not claim mean preservation for
    the form that does not have it.
  - INV-S4: NaN in any section ⇒ energy returns NaN *and* the step refuses to
    run, surfacing `SheafError::NonFinite` (failure mode F6, §8). Silently
    "correcting" NaNs would make a broken producer invisible.

---

## 5. Lineage

```rust
pub const MAX_NODES: usize = 64;               // v0.1 registry bound
pub struct Lineage {
    pub present: u64,                          // bit k set iff node k ran on this slot generation
    pub counts: [u16; MAX_NODES],              // exact visit counts, saturating
    pub overflowed: bool,                      // set the first time any count saturates
}
impl Lineage {
    pub fn record(&mut self, n: NodeId) {      // O(1), branch-light, no allocation
        let k = n.0 as usize;
        self.present |= 1u64 << k;
        let (v, sat) = self.counts[k].overflowing_add(1); // conceptually; impl uses checked/saturating
        self.counts[k] = if sat { u16::MAX } else { v };
        self.overflowed |= sat;
    }
    pub fn visited(&self, n: NodeId) -> bool;
    pub fn visits(&self, n: NodeId) -> u16;    // exact unless overflowed; consult the flag
}
```

- Memory: 8 + 128 + padding ≈ 144 bytes per slot, stored with the payload
  (§3.1). The bench suite prices this: ring throughput with lineage recording
  on vs. off is a reported pair, so the cost of provenance is a number, not a
  posture. **Hypothesis:** <5% on the ring bench; if it is far worse, the design
  revisits (e.g. lineage only on publish, not per stage) — with the revisit
  recorded in `NOTES.md`, not silently applied.
- Registry: `NodeRegistry` assigns `NodeId`s at pipeline construction and owns
  the human-readable names for traces/replay. Hand-assigned IDs (and *a
  fortiori* hand-assigned primes) in node code are forbidden; an unregistered
  node cannot run because `NodeCtx` is only minted by the registry.
- Ordering within a generation is recoverable in *replay mode only*, from the
  replay log (`replay.rs` records the execution sequence); `Lineage` itself
  deliberately does not encode order. Decision recorded: order-in-the-slot was
  the PIR scheme's false promise; the honest split is counts in the slot
  (cheap, always on) and order in the log (exact, opt-in, priced).

---

## 6. Gate

```rust
pub struct TileGrid { pub width_tiles: u16, pub height_tiles: u16, pub tile: u16 /* px per side */ }
pub struct Gate { pub tiles: BitSet /* over width*height */, pub stamp: Stamp }
pub struct OpCounter(pub u64);   // incremented by workloads for every scalar op performed
```

- Nodes receive `Option<&Gate>`: `None` = ungated (reference path, op-counted
  the same way); `Some(g)` = process only tiles in `g`, leave other tiles'
  outputs untouched, and report them in the snapshot as `stale_by_gate` with
  their last-computed tick (PLAN §5.2 contract).
- Gating granularity is the tile, never the element: per-element branchless
  masks are the email's claim, but on a CPU a per-tile skip is the version
  whose savings are countable and whose overhead is one bitset test per tile.
  Whether per-element masking wins anywhere is a bench question for a later
  version, not a v0.1 assumption.
- The director policy (`direct` node) operates on per-tile response values
  from `decide`, selects a tile cluster, and applies a **deadband**: the gate
  does not move unless the best cluster's centroid has moved by more than
  `band_tiles` *and* the challenger has won for `yaw_ticks` consecutive ticks
  (Casey's band + yaw, implemented as two named parameters with tests for
  gate-churn bounds). Gate churn (tiles changed per tick) is a first-class
  metric in `metrics.rs`.

---

## 7. Nodes, schedulers, clocks

### 7.1 Node trait

```rust
pub trait Node {
    fn id(&self) -> NodeId;
    fn process(&mut self, ctx: &mut NodeCtx, input: &Section, out: &mut Section)
        -> Result<(), NodeError>;
}
pub struct NodeCtx<'a> {
    pub tick: Tick,
    pub gate: Option<&'a Gate>,
    pub ops: &'a mut OpCounter,
    pub lineage: &'a mut Lineage,   // node records itself via ctx, scheduler verifies
}
```

Every node's arithmetic goes through `ctx.ops` counting at the granularity
PLAN §5.2 defines (the workload author counts inner-loop iterations in bulk —
`ops.add(n)` per tile/row — not per scalar increment, which would tax the very
thing being measured; the counting granularity is documented per workload and
the reference implementation uses the same granularity, keeping the comparison
honest).

### 7.2 The two schedulers

Both implement `Scheduler::run(trace) -> Vec<Snapshot>` over the same rings,
nodes, and input trace:

- **Batched:** wait until every lane has produced for barrier generation `g`;
  run perceive→decide→direct→refine once over the full sections; publish one
  snapshot stamped with `g`. Gate applies from the *next* barrier (its natural
  semantics — stated, because it is one of batching's real costs and hiding it
  would rig S1).
- **Rolling:** lanes carry phase offsets `phi[lane]` (in ticks, from the
  scenario config). At each tick, for each lane whose phase fires and whose
  ring has a ready slice: run the stage chain over *that lane's slice* (with
  the current gate), apply one refine (sheaf) step to the affected sections,
  and publish a snapshot immediately — partial snapshots are first-class and
  carry per-section stamps/ages so partiality is visible, never disguised.
- **Fairness enforcement lives in the harness, not the schedulers:** it counts
  ops per scheduler run and rejects a comparison whose ungated totals differ,
  checks both consumed the identical trace, and interleaves repetitions (PLAN
  §5.1). Schedulers themselves contain no timing code.

### 7.3 Clocks

- `LogicalClock`: a `u64` tick advanced by the scheduler. All v0.1 tests and
  the replay path use it exclusively; phase offsets, sensor periods, and
  deadbands are expressed in ticks, so a scenario is fully specified by
  integers and reproduces bit-identically anywhere.
- `MonoClock`: wraps `Instant`; used by benches to translate a logical
  scenario into wall time under a stated tick duration, and to measure the
  four PLAN metrics in nanoseconds. Its readings go into `Stamp.mono_ns` and
  are ignored by deterministic comparisons.
- Sensor arrival in wall-clock benches is modelled by producer threads pacing
  themselves to the scenario period — the single sanctioned use of `sleep` in
  the codebase (PLAN §0 dead end C), fenced to the bench harness and examples,
  and greppable as such (PLAN §8.2).

### 7.4 Invariants (consolidated; each names its test)

| ID | Invariant | Enforced by |
|---|---|---|
| INV-R1 | A consumer never reads a slot before its publish for that generation | `tests/ring_protocol.rs` + loom model |
| INV-R2 | Under `Block`, a producer never overwrites an unread slot | loom + stress test (8 slots / 100k msgs) |
| INV-R3 | Per-lane delivery is in-order and exactly-once under `Block` | sequence assertions in stress test |
| INV-R4 | `produced == consumed + dropped + in_flight` for every policy, always | shutdown assert + harness check |
| INV-L1 | `Lineage` matches a reference log exactly, except flagged saturation | property test (PLAN §5.4) |
| INV-S1..S4 | Sheaf energy/properties (§4) | property + unit tests (PLAN §5.3) |
| INV-G1 | Gated output inside the gate == ungated output, bit-identical | `tests/gate_correctness.rs` |
| INV-G2 | Tiles outside the gate are never modified by a gated run | same test, sentinel values |
| INV-D1 | Same trace + logical clock ⇒ bit-identical snapshot sequence, both schedulers | `tests/scheduler_fairness.rs` |
| INV-D2 | Gate churn ≤ bound implied by deadband parameters for a stated input class | churn test with oscillating argmax input |
| INV-M1 | Ungated batched and rolling runs perform identical counted ops | harness rejection test (feed it a rigged node; it must refuse) |

---

## 8. Failure modes

| ID | Failure | Detection | Behaviour by design |
|---|---|---|---|
| F1 | Producer outruns consumer (slow stage) | Slot not free at claim time | Per policy (§3.4): block, or accounted drop. Never overwrite-and-hope |
| F2 | Consumer stalls / dies | Producer blocks or drops mount; `in_flight` stops draining | In library use: run ends with INV-R4 assert naming the lane. No silent thread leak: producer threads are joined by the harness; a panicked consumer propagates as `Err`, not a hang — watchdog in the harness, stated timeout in tests |
| F3 | Node panics mid-pipeline | `catch_unwind` at the scheduler boundary (library returns `Err` by default; the boundary exists so *binaries* can choose) | The slot being built is never published (publish happens only after the full chain succeeds — a half-written section must not become `Ready`); the failed generation is counted as `aborted`, preserving INV-R4 with the extra term documented |
| F4 | Node returns `Err` / produces NaN or inf | Workload post-check in test/reference mode; sheaf refuses NaN (INV-S4) | Snapshot for that tick is skipped and counted; in strict mode the run aborts with the node's identity and tick |
| F5 | Lineage saturation (a node visits one slot generation > 65,535 times — pathological loop) | `overflowed` flag (§5) | Counts remain lower bounds and are labelled as such in any output; presence stays exact. A run that sets the flag in a *bench* invalidates that bench's lineage claims, not its timing |
| F6 | Sheaf step with bad `alpha` / diverging energy | Construction-time alpha validation; per-step energy check in test builds | Construction error, not a clamp; in release, a monitored run that sees energy rise beyond tolerance for k consecutive steps halts the refine stage and reports — measured divergence is data, silent divergence is corruption |
| F7 | Gate empty for a long stretch (director failure) | Snapshot staleness ages grow; metrics expose max age | The system remains correct (everything is labelled stale) but a scenario-level assertion on max tolerable age fails the *scenario*, surfacing a dead director as a test failure rather than a quietly frozen picture |
| F8 | Clock misuse — wall time in deterministic path | Type-level: deterministic APIs take `LogicalClock` only | Compile-time prevention; `mono_ns` is `Option` and `None` in logical mode, and INV-D1's bit-identity test would catch a leak |
| F9 | Ring capacity not a power of two / zero | Construction asserts | `Err` at construction; mask arithmetic is only sound under this precondition, so it is checked where the mask is born |
| F10 | Integer wrap of per-lane `Seq` (u64) | — | Accepted and documented: at 1M msgs/s a lane needs ~585,000 years to wrap. (The PIR scheme's wrap problem was at *40 multiplications*; ours is at 2^64 messages. The difference is the design.) |
| F11 | False sharing / layout regression after a struct edit | `size_of` const asserts (§3.1); ring bench in CI compares against committed baseline with a wide tolerance | Layout break fails the build; perf regression beyond tolerance fails CI *visibly* (not a silent slow-down) |
| F12 | Replay trace version drift | Trace files carry a format version + the git SHA of the writer | Replay refuses a mismatched major version with a named error |

Concurrency-specific: the only shared-mutable structures in v0.1 are the rings
(one atomic word of protocol each, §3.2) and the metrics counters (`Relaxed`,
never load-bearing). Shared sections are mutated only by the single scheduler
thread in v0.1 — producers write only their own lane's ring payloads. That
restriction is a *feature of the scope*, stated here so nobody "optimises" it
away without redoing the concurrency argument: the day two threads mutate
sections, §3.2's proof sketch no longer covers the system and a new one is
required before code.

---

## 9. The v0.2 seam (and nothing more)

- `node.rs` defines the stage boundary in data terms (section in, section out,
  gate, op count), so a future `Executor` can run the *perceive* stage's math
  on the GPU while the trait, schedulers, lineage, and metrics stay unchanged.
  v0.1 implements exactly one executor: `CpuExecutor` (i.e. the nodes
  themselves). The trait for a second executor is **not** created in v0.1 —
  designing it now would be guessing at CUDA's shape; the seam is the *data
  boundary*, which is already real, not a speculative trait hierarchy.
- What v0.2 will need that v0.1 must not preclude: sections whose payload
  allocation could be replaced by a device-mapped allocation behind the same
  `Section` handle (so §3.1 keeps payload behind an owned buffer type, not a
  bare `Vec` leaked through the API), and op counting that a GPU executor can
  report analytically (ops launched) alongside CPU counts — with the two
  labelled differently in results, since counted-by-instrumentation and
  counted-by-construction are not the same evidence.
- What v0.2 must inherit unchanged: the reference implementations and the
  correctness suites. A GPU executor is accepted by running PLAN §5's tests
  *against it*, not by a new, weaker GPU-only suite.

---

## 10. Decisions index (one line each; reasoning at the section named)

| Decision | Where | Beat which alternative |
|---|---|---|
| SPSC per-lane rings | §0.2, §3.2 | Vyukov MPMC; the email's protocol (§3.3) |
| Drop-oldest as a policy over a real queue | §0.3 | Pure latest-value seqlock buffer |
| Counted lineage, 144 B/slot, priced by bench | §0.4, §5 | PIR at u64 / u128 / bignum widths |
| Sheaf = graph consensus, energy in f64, no alloc in step | §4 | General sheaf machinery; the email's clamp |
| Tile gate, bitset, deadband (band + yaw) | §6 | Per-element branchless masks |
| Logical clock is the primary clock | §7.3 | Wall-clock-first with "deterministic-ish" tests |
| One crate, no speculative Executor trait | §1, §9 | Workspace split; trait hierarchy designed pre-CUDA |
| Publish-only-after-full-chain (no partial slots) | §8 F3 | Publish-per-stage into the same slot |

## 11. Process log (this design)

- **2026-11-01 — Lane PLAN.** Derived from the seed email (re-read as code,
  §0.1) and `PLAN.md`. The three analysis artefacts produced en route — the
  email-protocol defect list (§3.3), the PIR failure enumeration (PLAN §5.4),
  and the sheaf formula correction (PLAN §3 row 5) — are embedded in the
  documents rather than kept as side notes, per the documentation doctrine.
  No repo created, nothing pushed, Thor untouched.
- **Open design questions handed back with this document:** (a) tile size
  default (32×32 chosen as a starting parameter, to be benched at 16/32/64 —
  not a conviction); (b) whether `decide`'s hysteresis belongs in the node or
  the director (placed in `decide` for v0.1 so the director stays a pure
  function of responses — flagged as revisitable after the first churn data);
  (c) loom model scope (capacity-2/3-message model specified; if CI time
  bites, the stress test is the last thing cut, the loom model is not).
