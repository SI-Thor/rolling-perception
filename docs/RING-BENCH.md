# RING-BENCH — §3.2's SPSC ring vs the shipped Disruptor ring

**Question.** `docs/ARCHITECTURE.md` recorded the repo's headline
divergence: DESIGN.md §3.2 specifies a single-producer/single-consumer
ring with consumer acquire/release, and §0.2 records SPSC as a
*deliberate choice over* the Disruptor/Vyukov family — yet what shipped
in `crates/rolling-substrate-core/src/substrate.rs` is a multi-producer
Disruptor claim/finalize ring, and §3.2's ring was never built. Casey
ruled the fork be settled by numbers. This document is the settlement:
the §3.2 ring implemented as written (`src/spsc.rs`), property-tested
(`tests/spsc_properties.rs`), and benched head-to-head against the
shipped ring on the pipeline's actual message pattern.

**Process, in the body.** The implementation came first and the bench
second, and building the implementation is what produced the sharpest
finding: §3.4's drop policies cannot be bolted onto §3.2's protocol
without two repairs the design never states (ambiguity log, A1/A2
below) — one of them a permanent wedge, not a corner case. The bench
then produced the second finding: the shipped ring, used the way a
queue is used, silently overwrote **5–27% of a polling consumer's
reads** across four runs. Neither finding is visible from either
document or either codebase alone; both are recorded here with their
evidence.

---

## 1. Semantic diff — design (§3.2) vs shipped (substrate.rs)

| Aspect | DESIGN §3.2 `SpscRing` (now built) | Shipped `FluidSubstrateBuffer` |
|---|---|---|
| Producers / consumers | Exactly 1 / exactly 1, per lane; ends minted once, second mint panics | Many producers (`fetch_add` claim), any number of polling readers |
| Slot state word | Distinct states: free-for-`n` (`seq == n`), ready-`n` (`seq == n+1`), freed by consumer (`seq = m + capacity`) | One transition: `finalize` stores `claim + capacity`, which means both "published" and "reusable" at once |
| Consumer's role | Protocol party: Acquire load pairs with publish; Release store *creates* the producer's next claim right — real backpressure | Not a protocol party: `is_published` poll + `unsafe read_published`; no release, no backpressure, producer never waits for any reader |
| Ordering | Publish `Release` ↔ acquire `Acquire`; free-transition likewise; only the sequence word synchronises; counters `Relaxed`, never load-bearing | `lease` spins `Acquire`; `finalize` stores `Release`; `is_published` is a `>` comparison on the slot word |
| Drop policy | Chosen at construction (§3.4): Block / DropNewest / DropOldest, each with exact accounting | None exists. A slow reader's slot is silently overwritten by a later lap; the protocol has no name for the loss |
| Conservation (INV-R4) | `produced == consumed + dropped_newest + dropped_oldest + in_flight`, exposed via `RingStats`, asserted at drain in tests for all three policies | No counters at all. `is_published` is era-local across the 2⁶⁴ wrap (pinned in its own tests); loss to a lapped reader is unobservable from the API |
| Payload | Generic `T: Send`, one value per slot, moved through | Fixed `Box<[f32]>` section per slot + a lineage header cleared on lease |
| Claim cost (1-producer case) | Plain counter increment (the counter is a field, not an atomic) | One `fetch_add(AcqRel)` per message, plus a spin on the slot word |
| Full-ring semantics | Full capacity usable: all `capacity` slots can be in flight (§3.2's arithmetic sacrifices no slot; tested) | Producer is paced by other producers' finalize, never by readers; "full" from a reader's perspective is undefined |

## 2. Ambiguity log — where §3.2/§3.4 under-specify, and the reading taken

Interpreting silently is the failure this lane exists to prevent, so
every judgement call is here, numbered, with its reasoning.

- **A1 — DropNewest has no consumer-side mechanics in the design.**
  §3.4 says the consumer "sees a sequence gap of known size", but
  §3.2's consumer signal is only the slot sequence: a dropped
  generation is never published, so a consumer waiting on it waits
  forever — and worse, **the dropped generation is never released
  either**, so when the producer later reaches generation
  `m + capacity`, the slot's free-value is a number no one will ever
  store. Unrepaired, one drop wedges the ring permanently.
  *Reading (two minimal additions, both recorded in the code):*
  (a) the producer publishes its next counter in a ring-level
  `producer_head` atomic, stored (`Release`) *after* the publish or
  drop it describes and read (`Acquire`) only for gap detection —
  never for payload synchronisation, which remains exclusively the
  slot sequence's job, as §3.2 demands;
  (b) a consumer skipping a dropped generation performs that
  generation's release store (`m + capacity`) — there is nothing to
  read, and freeing the slot is the only act that keeps §3.2's
  arithmetic coherent.
  *Proof the repair is right:* the DropNewest random-schedule test
  runs 400 messages against a naive queue model and the counters meet
  exactly at drain; the gap test then sends successfully *after* a
  gap, which is the wedge case.
- **A2 — DropOldest contradicts §3.2's claim precondition, and is
  silent on the mid-read race.** §3.2 permits a write iff
  `sequence[i] == n`; DropOldest exists precisely to write when the
  previous generation is unread. *Reading:* the §3.4 policy is an
  override of the precondition — the producer reclaims when
  `sequence[i] == n − capacity + 1` (published, unread), destroying
  the stale payload in place. For a consumer caught mid-copy by a
  reclaim — a case the design never mentions — the consumer
  revalidates the slot sequence after copying and discards a torn
  copy (counted as `dropped_oldest`); a formally race-free treatment
  would need a consumer-progress signal §3.2 does not provide, and
  that gap is stated, not papered over. The threaded property tests
  therefore exercise Block (the policy INV-R2/R3 are stated under);
  DropOldest is verified against the naive model single-threaded and
  under random schedules.
- **A3 — Block's "park" names no primitive.** §3.4: "spin-with-
  backoff, then park (bench mode: spin only, and say so)". A
  `Mutex`/`Condvar` park would step outside the stated protocol.
  *Reading:* spin (`spin_loop`) escalating to `yield_now`; no park.
  The `blocked_ns` accounting §3.4 requires is implemented.
- **A4 — Capacity.** §3.2's arithmetic makes all `capacity` slots
  usable (no sacrificed slot to distinguish full from empty, unlike
  some textbook SPSC rings). *Reading:* literal — implemented and
  pinned by a test that fills a capacity-8 ring with 8 unread
  messages.
- **A5 — Payload shape.** §3.1/§3.2 are written around `f32` sections
  with stamp/lineage headers in the slot. §1's module table assigns
  `ring.rs` "no knowledge of nodes, lanes, or payload meaning".
  *Reading:* the ring is generic over `T: Send`; stamps/lineage ride
  inside the payload if a caller wants them. The 64-byte slot
  alignment (§3.1's rationale) is kept.

## 3. Bench — methodology

Hand-rolled, `std::time`, std-only, in
`tests/spsc_properties.rs::bench_rings_head_to_head`
(`cargo test --release --test spsc_properties -- --ignored --nocapture`).

- **Payload:** `[f32; 8]` for SPSC; the shipped ring at `dimension 8`
  — the pipeline's small section shape, byte-identical sizes.
- **Throughput:** two threads, producer → consumer, 1,000,000
  messages, capacities 256 and 4096. The SPSC run *asserts* the exact
  checksum of all 1M values (loss or reordering fails the bench). The
  shipped-ring run consumes the only way its API allows — poll
  `is_published(c)`, then `read_published(c)` — and counts **torn
  reads**: slots whose 8 words are not uniformly the claim value
  (i.e. the slot was overwritten by a later lap before or during the
  read; there is no safer consumer the shipped API offers).
- **Latency proxy:** ping-pong round trip over a pair of rings, one
  message in flight, 20,000 round trips × 5 runs, median reported.
  (For the shipped ring, one-in-flight is also what makes its
  consumer contract safe by pacing.)
- **Machine:** this dev VM — AMD EPYC 9D25, 4 vCPUs available to the
  process, shared host (run-to-run variance is large and is reported,
  not averaged away). **Thor numbers are future work** — the Thor was
  serving another lane during this run and was not touched; the same
  command runs there unchanged.

## 4. Bench — results (two full runs, both reported)

Throughput, M msgs/s (1M messages, 2 threads):

| Run | Cap | SPSC (§3.2) | Disruptor (shipped) | Shipped-ring torn reads |
|---|---|---|---|---|
| 1 | 256 | 11.37 | 2.59 | 140,436 / 1M (14.0%) |
| 1 | 4096 | 6.81 | 5.55 | 273,980 / 1M (27.4%) |
| 2 | 256 | 6.65 | 5.26 | 52,231 / 1M (5.2%) |
| 2 | 4096 | 9.14 | 2.61 | 201,214 / 1M (20.1%) |

Ping-pong round trip, µs, median of 5 runs × 20k:

| Run | SPSC (§3.2) | Disruptor (shipped) |
|---|---|---|
| 1 | 0.35 | 1.47 |
| 2 | 0.82 | 1.58 |

Reading the tables honestly: absolute throughput swings widely
between runs on this shared VM (the cap that wins flips between
runs), so no single M msgs/s figure should be quoted. Three results
are stable across every pairing: **(1)** SPSC throughput ≥ shipped in
all four pairings (1.3×–4.4×); **(2)** ping-pong median favours SPSC
in both runs (≈1.9×–4.2×); **(3)** the shipped ring tore **every**
run — 5–27% of reads — while the SPSC checksum asserted exactly, by
construction cannot tear under Block. The torn-read figure deserves
its context: the shipped cascade's real consumers are same-thread or
paced, where the lap cannot happen; the bench's free-running polling
consumer is the queue-shaped use, and it is precisely the use §3.2
was designed for.

Correctness evidence behind the numbers: 8 property tests
(randomised-schedule FIFO/no-loss across >5 laps; two-thread 100k
in-order run; full-capacity fill; both drop policies against naive
queue models under random schedules, 400 messages each; INV-R4 at
drain for every policy) + 3 unit tests in `spsc.rs` — this lane adds
11 tests, all passing, with the crate clippy-clean at
`--all-targets` and the full workspace green at assembly time.

## 5. Verdict — both, placed differently

The numbers and the semantics point the same way, and they point to
*placement*, not replacement:

- **Per-lane stage links — the perception cascade's actual topology —
  belong to `SpscRing`.** §0.2's premise still holds: each lane has
  exactly one producer by construction. On those links the §3.2 ring
  is faster on every pairing measured, its latency is ~2–4× lower,
  and — the deciding property, worth more than the speed — it is the
  only one of the two that can promise a slow stage *backpressure
  instead of silent data loss*, with INV-R4 accounting to prove the
  promise at shutdown. A cascade whose benches must account for every
  produced slice (§0.3's reason for rejecting a pure latest-value
  buffer) cannot be built on a ring whose losses are unobservable.
- **The shipped Disruptor ring keeps the jobs its semantics actually
  fit:** genuine multi-producer junctions (several lanes finalizing
  into one buffer is the one thing SPSC cannot do at all), and
  latest-data publish points where readers sample the newest state
  and an overwritten sample is the *intended* behaviour, not a loss.
  In those seats its costs — the `fetch_add` claim, no consumer
  accounting — buy the one capability the other ring refuses.
- **What must not survive:** the shipped ring used as a queue for a
  consumer it cannot pace. That use is now measured, not suspected:
  5–27% silent corruption under load. Any future call site that polls
  `is_published` from another thread should be treated the way this
  repo treats a failed test.

Net: DESIGN.md §3.2 was right about the centre and wrong about
nothing it stated — its gaps were omissions (A1/A2), now recorded.
The centre moves to `SpscRing`; the Disruptor moves to the junctions;
`docs/ARCHITECTURE.md`'s divergence entry can close with this
document as its evidence.
