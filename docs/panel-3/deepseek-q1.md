# The ring fork: keep the Disruptor, amend the design

## 1. Which protocol deserves the centre

**The shipped multi-producer Disruptor, kept — with the design amended, and with the missing pieces of the *contract* (not the protocol) built on top.**

The argument is junction-shaped, not taste-shaped. Walk the cascade's five edges:

- **ingest → reflex**: one producer per stream, but N streams. Multi-producer at the ring, single-producer per logical lane.
- **reflex → embed**: the gate emits nominated tiles from several tile workers. Genuinely multi-producer.
- **embed → refine**: several tile workers, one refine stage. Genuinely multi-producer — this is the junction the question names, and it is the *hot* one (173 ms embeds, the stage the budget system meters).
- **refine → verdict**: one refine, one publisher. SPSC.
- **verdict → ledger writer**: several streams, one writer. Genuinely multi-producer.

So three of five junctions are multi-producer in the real topology, and one of those three (embed → refine) is the stage the whole budget/perception design is built around. A protocol that is SPSC at the centre and "handles multi-producer at the edges" means every edge that matters wraps the SPSC ring in a shim: either an external claim counter (which *is* the Disruptor's `fetch_add`, just relocated and now un-audited), or a per-producer SPSC ring plus a merge stage (which adds a hop, a queue, and a second place for lineage to be lost — and lineage loss is the failure the substrate's whole bitmask design exists to prevent). The SPSC-at-centre design pays its cost exactly where the cascade is busiest and pays it in the currency (lineage continuity across edges, `TickMeta` relay) the engine is least able to afford.

The Disruptor's real cost is the one the audit already named: **polling consumers and no conservation accounting.** Those are not protocol properties — they are *contract* properties the design specified and the build skipped. They can be added to the shipped ring without changing its claim/finalize core:

- **Conservation** (`produced == consumed + dropped + in_flight`) is a counter set on the existing claim and publish paths plus a consumer-side read counter. It is orthogonal to whether producers are one or many.
- **Drop policies** (Block / DropNewest / DropOldest) are admission decisions at `lease()`. The shipped ring is Block-by-spin; the other two are a `try_lease()` returning `None` and a caller-side policy enum. Again orthogonal to producer count.
- **Consumer-side in-order exactly-once delivery** is a consumer protocol object over `is_published` — the thing DESIGN §3.2 specified and the build never wrote. It is needed *more* under multi-producer (claim order ≠ per-producer order), so building it is required either way.

In other words: the shipped ring is the right *core*; the design's §3.2 is the right *contract*; the debt is that the contract was never layered onto the core. Rebuilding the core as SPSC to match the document would be motion toward the document, not toward the workload.

The one honest counter-argument: if the cascade were reshaped so every stage had a single logical producer (one dispatcher fanning out, one collector fanning in), SPSC would be defensible and cheaper (no `fetch_add` contention, no lap-spin). But that reshaping is a *different engine* — it moves the multi-producer cost into the dispatcher/collector, which is now a new single point of failure and a new place lineage must be relayed. The design chose a cascade of independent lane families (§2.2, §2.8 of the spec: "lanes are independent, so death is local"); the Disruptor is the ring shape that matches that choice.

**Verdict: keep the Disruptor. Amend DESIGN.md §3.2 to describe it (the audit's D1 debt), and open three build items — conservation counters, drop policies, consumer protocol — as contract work on the existing ring.** The audit's "worst divergence is D1" is correct as a *documentation* finding; it is not a finding that the wrong ring was built.

## 2. The measurement that would settle it

The question asks for one experiment, one metric, one threshold. Here it is.

**Experiment.** Take the real cascade topology — five stages, the actual junction shapes above, the actual payload sizes (1280-dim embeddings on the embed→refine edge, tile-verdict units elsewhere) — and run it two ways on the Thor, identical work and identical checksums (the engine's existing `both_schedulers_do_the_same_work` discipline, extended to this comparison):

- **A**: shipped Disruptor, with the three contract pieces built (conservation, drop policies, consumer protocol).
- **B**: SPSC core per DESIGN §3.2, with multi-producer handled at the three multi-producer edges by the cheapest correct shim (external claim counter feeding per-producer SPSC rings, merged at the consumer).

Drive both with the same trace: a synthetic load shaped like the 48 h soak (mostly quiet, bursty on cuts, one gradual-drift stretch), plus a stress tail at 10× the soak's peak embed rate to expose the edges.

**Metric.** *End-to-end p99 verdict latency at the embed→refine junction, plus lineage-completeness rate* — the fraction of published verdicts whose `lineage_mask` equals the full five-stage mask. Latency is the throughput story; lineage completeness is the correctness story the SPSC shim is most likely to break (the merge stage is exactly where a `LineageSnapshot` gets dropped).

**Threshold and decision rule.** Switch the answer (i.e. adopt SPSC-at-centre) if and only if, on the same trace and with identical checksums:

- **B's p99 embed→refine latency is ≥ 20% lower than A's**, *and*
- **B's lineage-completeness rate is ≥ A's** (no correctness regression to buy the speed), *and*
- **B's conservation accounting closes** (`produced == consumed + dropped + in_flight` at shutdown) — the shim must not leak slots.

If B wins latency but loses lineage completeness, the answer stays Disruptor: the engine's publish rule ("verdicts without lineage are not published," spec §2.3) makes lineage non-negotiable, and a faster ring that drops lineage is a slower product.

If A wins or ties on latency (which I expect: the `fetch_add` cost at these rates is nanoseconds against 173 ms embeds, and the shim's merge hop is a real added cost), the answer is Disruptor and the measurement's job is done — it converts the audit's "the design doesn't describe the code" from a documentation embarrassment into a measured, recorded justification for amending the design.

**Why this threshold and not another.** 20% is the smallest latency win that would justify the added merge-stage complexity and its lineage risk; below that, the SPSC rebuild is motion, not progress. The lineage-completeness clause is the correctness fence the engine's own doctrine demands. The conservation clause is the audit's D3 debt made a gate — whichever ring wins, it must close its accounts.

**What this measurement deliberately does not test.** Absolute throughput of either ring in isolation (a microbenchmark of `fetch_add` vs SPSC would answer a question nobody asked); the persistent-kernel arrangement (already refuted for slice work, P18); and multi-*household* fan-in (out of scope, spec §1.6). The experiment is scoped to the cascade's real junctions because that is where the protocol choice is load-bearing.

**Record the result either way**, in RESULTS.md, with the trace and the checksums — the house rule. If the answer flips later (a topology change makes a junction single-producer that is currently multi), the measurement is re-run, not re-argued.
