# Panel 3 — outside critique, round 3 (refereed)

*2026-11-01 (AKST). Four hosted models on DeepInfra. Round 3's
design fix, per round 2's honest negative: **two questions per
model**, so each model's second call rides its own cached prefix.
The prefix — byte-identical across all 8 calls, question appended
last — was the design AND its audit together: SPEC-STREAM-PLATFORM
+ ARCHITECTURE.md (claim→proof tracing) + RESULTS.md, 118,271 bytes
≈ 30k tokens per call. Pair A (DeepSeek, Hy): Q1 the ring fork,
Q2 the chatty gate. Pair B (MiMo, Seed): Q3 allocation policy,
Q4 the graduation bar. Raw answers: `docs/panel-3/`. Panel output
is testimony, not measurement — this file is the referee's record.*

## Cache accounting — the design goal, graded

| Call | Model | Q | Prompt tok | Cached | Completion (reasoning) | Cost |
|---|---|---|---|---|---|---|
| 1 | DeepSeek-V4.1-Flash-1017 | Q1 | 30,890 | 0 | 1,752 (0) | $0.0035 |
| 2 | DeepSeek-V4.1-Flash-1017 | Q2 | 30,992 | **30,464** | 1,671 (0) | $0.0006 |
| 3 | Hy4-preview | Q1 | 30,727 | 0 | 7,522 (6,000) | $0.0444 |
| 4 | Hy4-preview | Q2 | 30,838 | **30,208** | 7,394 (6,000) | $0.0203 |
| 5 | MiMo-V2.6-Pro | Q3 | 31,104 | 0 | 5,276 (3,600) | $0.0162 |
| 6 | MiMo-V2.6-Pro | Q4 | 31,044 | **0** | 5,306 (3,600) | $0.0162 |
| 7 | Seed-2.0-mini | Q3 | 32,339 | 0 | 4,385 (3,591) | $0.0050 |
| 8 | Seed-2.0-mini | Q4 | 32,279 | **31,800** | 3,911 (3,213) | $0.0022 |

**Total spend: $0.1085.**

**Verdict: the fix works on three of four models — and fails
plainly on MiMo.** DeepSeek, Hy, and Seed each rode ~98% of the
prefix on their second call (30,464 / 30,208 / 31,800 cached
tokens; second-call costs fell accordingly — DeepSeek's by 5.6×).
**MiMo's second call reported cached_tokens = 0** despite a
byte-identical prefix minutes after its first call. By the
round's own pre-committed rule, that is a design-goal failure for
that model: either MiMo does not cache this prefix shape or does
not report it, and the practical consequence is the same — MiMo
calls are priced at full rate until proven otherwise. Round 4's
rule: ≥2 questions per model stays (it is also just a better
panel shape), but MiMo's prefix is budgeted uncached.

Referee notes on form: no truncations this round (round 2's MiMo
failure mode did not recur at the higher cap). Hy remains the
expensive seat — $0.0647 of the $0.1085 total, 6,000 reasoning
tokens spent before visible text on both calls — but both answers
arrived complete. Seed's known failure mode (invented facts)
appears once, flagged at Q4 below.

## Q1 — The ring fork (DeepSeek + Hy)

**Convergence — total, and arrived at independently.** Both
models: **keep the shipped multi-producer Disruptor at the centre,
amend DESIGN.md §3.2 to describe what shipped, and build the
design's missing *contract* pieces on the existing ring** —
conservation counters (`produced == consumed + dropped +
in_flight`), per-ring drop policies, and a consumer-side delivery
object (cursor with acquire/release semantics). Both argue the
fork is miscast: the shipped ring's deficits are contract
properties, orthogonal to producer count, while the SPSC design's
cost lands exactly on the genuinely multi-producer junctions
(tile workers → refine; streams → ledger writer), where it would
need claim-counter shims or merger stages — the Disruptor's
mechanism relocated, plus a new place for lineage to be dropped.

Both also converge on the settling measurement's shape: an A/B
on the real cascade topology, metric = p99 latency at the
embed→refine join, decision threshold = the SPSC arm must be
**≥20% faster** (Hy: ≤0.8×) *and* no worse on correctness
(DeepSeek: lineage completeness ≥ and conservation closes; Hy:
zero delivery violations / shed-accounting errors) before the
answer flips.

**Accepted.**
- **The verdict itself**, because the junction census is an
  argument from the workload, not from taste, and because it
  matches the house rule (inventory before building): the
  Disruptor is soak-proven inventory; the SPSC ring is a document.
- **The contract/contract split** as the correct framing of the
  ARCHITECTURE D1/D3/D4 debts: they are build items on the shipped
  ring (conservation, drop policies, consumer cursor), not
  evidence the wrong ring was built. The audit's "worst
  divergence" stands as a *documentation* finding.
- **The measurement as a standing decision rule**, pre-committed:
  if the fork is ever forced, this experiment — not another
  argument — settles it, and its result goes in RESULTS.md either
  way.

**Refinements the referee adds.**
- Hy's census correction: the *spine* junctions are SPSC in
  practice today (rolling-pipeline drives its rings sequentially);
  the multi-producer junctions are the two edges. Accepted — it
  strengthens the verdict (the Disruptor's generality is spent
  where it is needed) and it carries Hy's own honest caveat: if
  the tile workers are never actually concurrent in the real
  workload, the MP junction is theoretical and the question
  re-opens as a workload measurement, not a protocol one.
- DeepSeek's lineage-completeness metric joins the decision rule
  as a first-class term: a faster ring that drops lineage is a
  slower product, per the publish rule (verdicts without lineage
  are not published).

**Refused.** Nothing in either answer is refused. One emphasis
correction, the mirror of round 2's Hy correction: both models
write the three contract pieces as small work. They are small
*relative to a ring rebuild*; conservation accounting on a live
soak-carrying ring is still surgery on a running system and gets
scheduled like it.

## Q2 — The chatty gate (DeepSeek + Hy)

**Convergence — strong, and largely derived from the spec's own
machinery rather than invented.** Both models, independently:
- **Demote on measured precision, never on event count.** A busy
  evening is not a false evening. Unscored events are not votes
  (DeepSeek); the estimate runs over a judged window (Hy: last 30
  judged events or 7 days).
- **Demotion is per-region as well as per-stream, is always
  visible** (a feed entry naming the trigger and the numbers; a
  demoted region still records, badged quiet), **and cannot decay
  into invisible permanent silence** — probation and promotion are
  scheduled, logged events, and a region producing zero verdicts
  for 24 h is itself a feed entry.
- **Recalibration is scheduled (weekly) + triggered, never
  continuous**, and the anti-contamination rule is the spec's own
  baseline-admission rule, which both models found and cited
  (§B 3.2): a sample enters the baseline only if it published as
  no-change *and* sits below the current change threshold — so a
  person in the room is held out as pending drift, and a second
  person is still measured against the empty room. Absorption of
  a still person happens only through the pending-drift
  accumulator and publishes a labelled `slow-change` verdict when
  it does.
- **The homeowner's surface is a digest, not a stream of pushes**:
  one card per hour / per absence, top-ranked thumbnails only;
  pushes are rationed separately from recording.
- **A correction buys four mechanical things and no silent
  retraining**: an exception exemplar in the lens, a scored label
  in the precision denominator, a scheduled (batched) ranker
  refit, and a ledger record. Both models state the discipline
  explicitly: labels schedule visible refits; they never
  self-modify thresholds on the spot.

**Accepted.**
- The whole shape above. It extends Panel 1's precision-with-n
  and auto-demotion (spec §C 2.2's 0.9 rule) with the missing
  operational detail — window, unit, probation — without new
  machinery, and it satisfies the cross-round convergence that
  silence must carry its basis: here, *suppression* must carry
  its basis too.
- Hy's **rate trigger** as a second, label-independent demotion
  path (>2 pushes/hour with unmeasured or imperfect precision →
  feed-only): the livability cap that catches a blow-up before
  enough corrections exist to score it. DeepSeek's precision-only
  scheme has a cold-start hole here — 393 events can arrive before
  20 are judged — and Hy's trigger is the plug.
- DeepSeek's **"Busy tonight"** knob: a one-tap, auto-expiring,
  whole-stream feed-only demotion. It is the homeowner-side
  pressure valve the spec's three-position knob lacks, and it
  converts the worst evening from a trust-destroying event into
  one tap.

**Refused / held.**
- Every numeric threshold in both answers (0.70 region demotion,
  7-day probation, 2 pushes/hour, ≥0.95 promotion, 5 recurrences)
  is a labelled guess, as both models honestly mark them. They
  are adopted as *starting values to be measured against the
  soak's corrections ledger*, not as findings. The first real
  input is the 393-event evening's per-region precision — which,
  per RESULTS.md, does not exist until a human scores it.
- Hy's spend line quotes the budget unit as "embed-minutes"; the
  platform's unit is the **embed-second** (spec §B 2.2). Wording
  corrected, mechanism accepted.

## Q3 — Allocation policy (MiMo + Seed)

**Convergence — on the one mechanism that matters.** Both models
independently land on the same load-bearing gate: **a std-only
counting global allocator in tests** (`std::alloc::GlobalAlloc`
wrapper over `System`, atomic counters), with a zero-allocation
(or budgeted) assertion per hot function — plus a grep gate as a
coarse backup, scratch-buffer signatures (`&mut [T]` in, nothing
owned out) as the coding convention, and an exemption path with
a named reason. Both are honest that the compiler forbids
nothing here.

**Accepted — MiMo's draft is adopted as the policy's skeleton.**
- **The manifest form**: hot files are listed in one manifest
  (`docs/HOTPATH.md`); file membership is grep-checkable, function
  membership is not — the boundary rule ("does this line execute
  once per item/frame/tile?") a reviewer can apply without
  judgement calls.
- **The budget unit**: allocations *and* bytes per call, declared
  per function; a budget > 0 is an expiring exception with an
  owner and the rejected alternative recorded, reported as debt
  in RESULTS.md until renewed or removed.
- **The honesty table**: counting-allocator test catches this bug
  deterministically *if the test is written in the same commit*
  (hence MiMo's closure rule — no manifest file without its
  budget test); grep catches the literal `vec!` form only; the
  debug-assertion variant catches transitive allocations in debug
  runs; clippy has no allocation lint and is relied on for
  nothing. The policy is only as strong as the closure rule, and
  MiMo says so.

**Refused.**
- **Seed's clippy mechanism, as written, does not work.**
  `clippy::disallowed_methods` is configured in `clippy.toml` by
  path, not via a `[workspace.lints]` table in the form shown,
  and `format!` is a macro, not a method — it cannot be banned
  through that lint. A policy whose enforcement example cannot
  compile teaches reviewers to stop trusting the policy. (The
  lint itself, correctly configured, remains a usable backup to
  the grep gate.)
- **Seed's exemption quota** ("limited to 10% of hot path
  functions") — an invented number with no mechanism behind it;
  the budget is per-function or it is nothing. And its closing
  rule ("all allocations must be freed before the function
  returns") is refused as meaningless in Rust: values free on
  drop; the policy governs *allocating*, not freeing.
- Seed's scope heuristic (">10k calls per hour in production
  soaks") is held, not adopted: call-count is a symptom, the
  per-item boundary rule is the definition. Its one solid
  contribution — setup-time pre-allocation sized to fixed
  hardware maxima — is already implied by the scratch convention.

## Q4 — The graduation bar (MiMo + Seed)

**Convergence.** Both reviewers independently put the same three
things at the top of the bar in some order: (1) a validated
end-to-end pipeline whose precision is *judged*, not pending;
(2) honest, findable deficits; (3) architecture docs that match
the shipped code. And both grade this project **proven on the
deficit ledger** and **partial on the validated pipeline** (the
soak's precision number does not exist yet — RESULTS.md says so
itself). Both also independently flag the same public-facing
hazard: **DESIGN.md still presents the unbuilt SPSC protocol** —
a cold reader meets the stale design before the audit that
corrects it. That is Q1's amend-DESIGN action arriving again
from outside, and it raises that amendment from housekeeping to
a graduation blocker.

**Accepted.**
- **MiMo's bar and most of its grading** — the sharper of the
  two reviews. Demands 1 (buildable cold in under an hour),
  5 (a cold demo on bundled fixtures), and 6 (honest scope) are
  the findings that matter:
  - Demand 5 graded **MISSING from the prefix** — and the referee
    records the distinction MiMo itself draws: the *repo* has
    cold fixtures (confluence-watch's staged and wave-3-replay
    sources, the harbor-watch fixture), so the repo-grade is
    partial; but the three front-door documents a stranger reads
    first never surface them. A demo nobody is pointed at is, to
    a stranger, missing. Accepted as a docs defect, fixable in
    the front door.
  - Demand 1 graded **PARTIAL from the prefix** — same shape:
    the root README carries a quickstart (75 tests, verified);
    the spec/audit/results trio doesn't route a cold reader to
    it. Accepted as a cross-linking defect.
  - Demand 6's bottom line is accepted as the round's most
    quotable verdict: as evidenced, the project **graduates as a
    reference implementation and design record; it does not yet
    graduate as a tool a stranger picks up** — because it is, by
    design and admission, a personal platform. Whether "useful"
    must mean "useful to a stranger" is the owner's call at flip
    time; the panel's job was to name the gap, and it did.
  - MiMo's demand 4 (CI actually on, not prepared): PARTIAL,
    accepted — the audit's P14 gaps (no grep gate, no loom job,
    ring happens-before argued only in comments) are the
    substance behind it.
- **Seed's demand ordering in one respect**: its #1 (a judged
  pipeline, no unjudged soaks) is the single most fatal absence
  and both reviewers agree it is currently partial. The soak
  verdict (due 2026-11-03) is the project's own scheduled answer
  to it.

**Refused — Seed's grades where they contradict the evidence.**
Seed was instructed to grade from the prefix; three of its
grades fail even against the prefix, and one inverts a measured
fact (its standing failure mode — referee everything):
- "Public client: **Missing** — no evidence of a web UI." The
  spec in the prefix describes the console and feed; the repo
  carries the built Slice-1 console (change feed, shelf, working
  corrections button, all test-verified). Corrected grade:
  **partial** — it exists and is LAN-shaped; no stranger has
  ever used it.
- "Setup docs: **Missing**." The repo carries a technician
  install pack (INSTALL.md + dry-run-first installer, dry-run
  verified live on the Thor; never applied on a clean box).
  Corrected grade: **partial** — written and rehearsed, never
  run end-to-end by anyone but its author.
- "User controls: **Missing** — only planned." The corrections
  control is built and ledger-verified (a "That wasn't a change"
  tap lands in `corrections.jsonl`); budget knobs remain spec.
  Corrected grade: **partial**.
- "Benchmarks: Proven — H.264 transcode throughput 530–740 fps."
  **The number is inverted**: 530–740 fps is the GStreamer V4L2
  **H.265** figure; H.264 transcodes measured ~208 fps (ffmpeg)
  within a ~580–640 fps aggregate. The demand itself is still
  graded proven on the remaining rows (embed latency, gating
  savings, concurrency caps) — but the citation is refused, and
  it is why Seed's grades are never adopted unrefereed.

## What round 3 changes

1. **DESIGN.md §3.2 gets amended** to describe the shipped
   Disruptor, with the three contract pieces (conservation,
   drop policies, consumer cursor) opened as build items on the
   shipped ring. Two panel rounds now point at the same stale
   document; Q4 makes it a graduation blocker, not housekeeping.
2. **The chatty-gate trust economics enter the spec's backlog**
   in the converged shape: judged-window precision per region,
   a label-independent rate trigger, scheduled + triggered
   recalibration under the §B 3.2 admission rule, digest-first
   surface, and the "Busy tonight" knob. Thresholds are starting
   guesses; the soak's corrections ledger is their first test.
3. **The allocation policy is adopted in MiMo's form**: hot-path
   manifest, counting-allocator budget tests as the closure
   rule, budgets as expiring owned exceptions. Its first
   application is the sheaf fix itself.
4. **The graduation gap list is now explicit** (MiMo Q4): route
   the front door at the quickstart and the cold fixtures, close
   the CI gaps (P14), and let the owner decide whether
   "useful" means useful-to-a-stranger at flip time.
5. **Panel economics**: round 4 keeps ≥2 questions per model;
   MiMo is budgeted uncached; Hy's reasoning appetite is priced
   in advance, not discovered in the usage line.

## Referee addendum (same night, after the ring bench landed)

Q1's convergence — *keep the shipped Disruptor, amend §3.2* — was
argued from this book's first edition, which predated the
measurement. The panel itself pre-committed a settling test
(A/B, SPSC must win with no conservation regression). That test
effectively ran in parallel (docs/RING-BENCH.md): SPSC won on
speed (6.7–11.4 vs 2.6–5.6 M msgs/s) — and, decisively, the
shipped ring **consumed as a queue tore 5–27% of reads silently
in every run**, because it has no consumer release, no drop
policy, no counters. Per this repo's rules, measurement outranks
convergence: the Q1 verdict stands only for multi-producer
junctions and latest-value publish points. For per-lane cascade
queues the bench verdict governs — SPSC takes the centre, and
the shipped ring used as a paced queue is refuted. The panel's
contract pieces (conservation, drop policies, consumer cursor)
remain accepted — they are, in substance, what the SPSC build
implements.
