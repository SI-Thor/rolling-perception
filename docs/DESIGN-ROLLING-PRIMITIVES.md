# DESIGN — Rolling Primitives: Perception and Plans Drafted as Deltas

*Top-level design document, 2026-11-07. This document develops one
synthesis — rolling perception (this programme) and Flash Primitive
Decoding (NVIDIA VFlash, arXiv:2611.08449, studied in STUDY-VFLASH)
are the same move in two substrates — states it precisely enough to
be wrong, tests where it breaks, and derives three applications,
each with the measurement that would prove or kill it. Nothing in
this document is built. What exists today is named as such; what is
proposed is named as such; every load-bearing unknown is collected
in §6 rather than smoothed over.*

---

## 0. The thesis, stated as a claim that can fail

**Rolling perception exploits persistence over time.** The world at
tick *t* is the world at tick *t−1* plus changes. A system that
re-perceives everything every tick pays for the world; a system
that carries verified state forward and pays only for the delta
pays for the *rate of change*. Measured in this programme: on
identical work, rolling time-to-first-output was 243.5 µs against
2,528.6 µs batched (10.39×, checksums bit-identical); diff-gating
cut I-JEPA embeds from 576 to 312 (−54%) on real scenes and by 88%
on gradual material, with frame verdicts agreeing 1.0000 with the
ungated run.

**Flash Primitive Decoding exploits structure over the output.** A
trajectory is one coherent object, not forty independent numbers.
Autoregressive decoding pays per token and can be wrong
token-by-token in ways the object never is; a drafter that knows
the object's schema predicts it jointly, in one pass, and the
system pays only to verify. Measured by the paper's authors, on
their own runtime: robot-planning latency on Jetson Thor fell
3,552.7 ms → 703.3 ms, decoding alone 12×, with trajectory accuracy
*improving* against the autoregressive target.

**The synthesis — rolling primitives.** Put the two moves on the
same stream:

> Each tick, the system's structured output — a world digest, a
> citizen's plan, a stream's change record — is **drafted as a
> delta against the last verified state**, by a drafter whose
> memory is the change ledger itself, and **committed only through
> a verifier**. Cost then scales with the rate of change and the
> rate of surprise — not with world size × tick rate.

Three roles, named once and used throughout:

- **The ledger is the drafter's memory.** The last *verified*
  primitives, plus the receipts of how they were verified, are the
  base every new draft is a delta against. A draft is never
  generated from nothing; it is generated from the ledger.
- **The drafter is cheap and temporal.** It extrapolates the
  verified state forward using the observed delta (motion,
  momentum, an unfinished plan's next steps) and proposes the new
  primitive set. It is allowed to be wrong; it is not allowed to
  commit.
- **The verifier is what makes a draft a fact.** Verification is
  against something that is not the drafter: fresh sensor evidence,
  server truth, a satisfiability check, world evidence after
  execution. Only verified output enters the ledger and becomes
  the base for the next delta.

The cost model follows directly. Let a full decode of one tick's
primitives cost *C_full*, a draft cost *C_draft ≪ C_full*, and a
verification cost *C_verify*. With draft acceptance rate *p*:

```
C_tick = C_draft + C_verify + (1 − p) · C_full
```

The synthesis wins exactly when the world is persistent enough
that *p* is high and verification is genuinely cheaper than
generation. Both conditions are empirical, per application, and
each application below carries the measurement that decides them.

---

## 1. Testing the thesis against itself — where it holds, where it breaks

The thesis is a composition, and compositions fail at the joints.
Four findings, stated before the applications because the
applications inherit them.

### 1.1 The two moves are orthogonal, and that is the good news

VFlash's gain is **within-object**: joint prediction of one
primitive's positions, in one tick, with no reference to the
previous tick. Rolling perception's gain is **across-time**:
re-use of verified state between ticks, with no claim about how
any single tick's output is produced. Neither paper nor programme
measures the other's axis — VFlash's benchmarks are single-shot
(open-loop prediction from one observation); rolling perception
has never drafted an output, only gated its inputs.

Orthogonality means the gains are not the same gain counted twice:
a system could in principle draft jointly *and* roll temporally,
and the savings multiply where both redundancies exist. It also
means neither result is evidence for the other. The NVIDIA paper
never separates a temporal component because its tasks have none;
our measurements never separate a joint-decoding component because
our outputs are written by code, not decoded. **Stage 0.5 in §2
exists precisely to measure the rolling axis in isolation on a
decoding workload** — the separation neither source provides.

### 1.2 Break one: verification is not free, and not always possible

Speculative decoding's text path is lossless because the target
model *is* the verifier: it checks the draft against its own
distribution in one pass. VFlash's primitive path gives that up —
primitives are accepted on structural validity, not agreement —
and the paper's own results show the cost: boxes accepted without
a verification-shaped guard lose ~20 F1 points on crowded scenes,
and the published box numbers reinstate a spatial-confidence guard
with autoregressive fallback.

The synthesis inherits this in a stronger form. A rolling
primitive system whose verifier is the same model that drafted
has no verifier; it has a second opinion from the same witness.
The design therefore requires the verifier to be **external** —
ground truth from the server, a calculator that checks arithmetic
and satisfiability, world evidence after execution — and external
verification has a price and a coverage limit. Where no cheap
external check exists for a primitive field, that field cannot be
rolled; it must be fully decoded or not emitted. Each application
below names its verifier explicitly, and "the verifier is not
actually cheaper than the decode" is a standing kill condition.

### 1.3 Break two: rolling state is self-referential, so errors compound

An autoregressive decoder that errs produces one wrong output.
A rolling system that *commits* a wrong primitive has poisoned
the base from which the next delta is drafted — the error becomes
premise. The programme has already met this failure in citizens'
clothing: Geist rode a stale fact (a pond recorded as his anchor)
through nineteen deaths because nothing in his loop invalidated a
believed state against the world; the fix was an external
correction and a re-survey, not better reasoning from the same
premise.

Two counterweights are therefore part of the design, not
hardening to be added later:

- **Periodic full re-derivation.** Every *N* ticks (or every *T*
  seconds), the primitive set is regenerated from scratch and the
  ledger is reconciled against it. The interval is a priced
  parameter: it bounds how long a poisoned base can persist, and
  its cost is charged to the design in every measurement.
- **Surprise-triggered invalidation.** Any verifier failure, any
  world-evidence contradiction, any observation the carried state
  cannot explain invalidates the affected entries immediately —
  not at the next reconciliation. Surprise is the one signal the
  system must never amortise.

### 1.4 Break three: persistence is a property of scenes, not of systems

The rolling gain exists only where the world actually persists.
This programme's own measurements mark both ends: gradual material
saved 88% of embeds; a scene cut flags 16/16 tiles on the landing
frame and saves nothing — correctly. A digest of a quiet world is
nearly free under rolling primitives; a digest of a world in
regime change costs *more* than plain decoding (draft + verify +
full decode, per the cost model, with *p → 0*).

Consequence: **no application below is allowed to report a single
average saving.** Every measurement reports cost against measured
change rate, and the interesting number is the crossover — the
change rate at which rolling stops paying. A design that wins on
quiet scenes and loses silently on busy ones has the failure shape
of every amortisation scheme; the crossover is the deliverable.

### 1.5 Verdict on the thesis

**Holds with qualifications.** The two moves compose, the cost
model is honest, and each of the three breaks has a designed
counterweight. The qualifications are the design: the verifier
must be external and priced (§1.2), the ledger must be defended
against its own commits (§1.3), and every claim must be stated
against change rate (§1.4). Where any of the three cannot be
satisfied, the synthesis does not apply and the application says
so.

---

## 2. Application A — The world digest as rolling primitives

### 2.1 Mechanism

The world digest (ARCH-AGENT-COMMUNITY §3) is the continuously
updated structured state of the world — who is where, what moved,
what changed — from which every citizen drinks at its earned
cadence. In its frame-based form (§2 of STUDY-VFLASH), a VLM
emits the digest as primitives: one box per visible entity, one
short track per mover, one point per changed structure.

Under rolling primitives, the digest service holds the last
**verified** primitive set as its ledger state. Each cycle:

1. **Draft.** A temporal drafter extrapolates the verified set:
   entities carried at their extrapolated positions (last position
   + observed velocity), tracks extended by their last segment,
   static structure carried unchanged. The draft costs no model
   call in its trivial form — it is arithmetic over the ledger.
2. **Verify.** Fresh evidence is checked against the draft, field
   by field: server state feeds (exact positions, free) where the
   digest is state-fed; targeted frame crops where it is
   frame-based. Fields that verify are committed at verification
   cost. Fields that fail are marked *moved / appeared /
   vanished*.
3. **Decode the delta only.** Full VLM decoding is spent only on
   failed fields: a re-box for a moved entity, a fresh track for a
   new mover, a first description for an appeared one.
4. **Publish the ledger delta.** What enters the digest's record
   is the change set with its receipts — which entries were
   carried, which verified, which re-decoded, at what cost. This
   is the change feed's native shape; the digest stops being a
   periodic re-description of the world and becomes what the
   platform's attention plane already assumes: a stream of
   departures from a known state.

### 2.2 What exists today that it builds on

- The digest is designed (ARCH-AGENT-COMMUNITY §3) with tiered
  subscriptions and a novelty check per citizen slot — the
  consumer-side half of this design already exists on paper.
- Server state feeds are live and exact: every citizen's position,
  health, inventory, and deaths, published at 10 s cadence by the
  league's residents. As a verifier for a Minecraft digest they
  are perfect — free, authoritative, and independent of any model.
- Frames exist: the headed client on the Orin renders the world
  continuously, and the cameraman's event tail already consumes
  world events as a stream.
- The platform's ledger discipline (per-stream state as structured
  text, per-stage receipts, silence semantics) is built and
  soak-tested in telltape's lineage.

### 2.3 The experiments

**Stage 0 — the baseline (from STUDY-VFLASH §3, restated as this
design's experiment 1).** A stock Qwen3-VL-4B on the Thor, FP16,
emits the fixed-schema digest primitive set from live world frames
(spectator and citizen POV), autoregressively, at batch one.
Ground truth is free and exact from the server state feeds.
Measure over ≥50 digests, including night and occluded frames:
AR decode latency per digest, token counts, spatial error (box
IoU, track displacement) against server truth. Stage 0 decides
whether the frame-based digest has a decode cost worth attacking
at all, and produces the annotated corpus (frames paired with true
primitives) every later stage trains or evaluates on.

**Stage 0.5 — the rolling contribution, isolated.** The same
digest task, three arms, same frames, same ground truth:

- **Arm 1 — plain AR.** Stage 0's decode, every cycle, from
  scratch.
- **Arm 2 — rolling with a trivial temporal drafter.** The drafter
  is extrapolation only (step 1 above, no learned component, no
  NVIDIA artefact of any kind). Verification is against the state
  feeds. Failed fields are re-decoded by the same stock AR model.
  Periodic full re-derivation every *N* cycles, with *N* swept
  (e.g. 5, 20, ∞) so the price of §1.3's counterweight is measured,
  not asserted.
- **Arm 3 — rolling with the drafter replaced by an oracle.**
  Drafts are generated from ground truth with the *measured*
  change applied — the ceiling arm. It separates "rolling doesn't
  pay on this workload" from "our trivial drafter is too weak":
  if the oracle arm doesn't beat Arm 1, no drafter will.

Report, per arm: per-digest latency (draft, verify, decode,
total), accuracy against server truth, and **cost plotted against
measured per-cycle change rate** (fraction of entities whose true
state moved beyond the verification tolerance), with the Arm 1 /
Arm 2 crossover marked. Stage 0.5 is the experiment the NVIDIA
paper never runs: its tasks are single-shot, so the temporal axis
is invisible to it; here the temporal axis is the whole question.

**What Stage 0.5 needs that exists:** state feeds as ground truth
and verifier; frames from the headed client; a stock VLM serving
path on the Thor for the decode arm. **What it does not need:** any
NVIDIA artefact, any trained drafter, any code release. If Stage
0.5's Arm 2 wins, a learned drafter (STUDY-VFLASH Stage 1) becomes
a priced upgrade to a proven shape, evaluated against Arm 2's
numbers rather than against hope.

### 2.4 Kill criteria

- Stage 0 shows AR decode is **<60%** of per-digest latency —
  the digest's bottleneck is elsewhere; rolling primitives attack
  the wrong term. (Inherited from STUDY-VFLASH §3.)
- Arm 2 fails to beat Arm 1 on total latency at matched accuracy
  at the *median observed change rate* of the live world — the
  workload isn't persistent enough, and the crossover sits below
  the world's normal operating point.
- Verification cost per carried field exceeds ~⅓ of that field's
  full decode cost — §1.2's condition fails; the verifier is not
  actually cheaper than the decode.
- Accuracy of the committed digest (Arm 2) falls measurably below
  Arm 1 against server truth beyond the pre-registered tolerance —
  carried state is committing errors faster than reconciliation
  clears them.

### 2.5 Honest obstacles

- The frame-based digest is itself an open design choice; the
  state-feed digest is exact and free, and for the current world
  (three citizens, one server) it is sufficient. Rolling
  primitives earn their place only where frames carry what state
  feeds cannot — uninstrumented entities, structure, the visual
  world beyond the server's model. Stage 0 must report against
  that bar, not against a straw digest.
- Serving a stock VLM on the Thor inside the house's serving
  culture (llama.cpp, JEV rack) is new plumbing; it is Stage 0's
  real cost and should be reported as such.
- Occlusion and night frames will produce the worst drafts and
  the most verifier failures in exactly the conditions where the
  digest matters most. The change-rate plots must be split by
  condition, or the average will lie in the dangerous direction.

---

## 3. Application B — Rolling plans for the citizens

### 3.1 The measured problem

A citizen's plan is a primitive: fixed schema, known structure —
an ordered list of actions from a closed vocabulary, with counts,
targets, and preconditions. Lineage C's planner (GITM pattern:
planner → calculator → execution → reflection) currently
regenerates that primitive **from scratch at every tick**, paying
full deliberation for a plan that usually differs from the last
one in one or two steps.

The cost is not hypothetical; it is the league's own ledger.
Across the governor's 324 receipts to date, the two deliberating
citizens dominate mind spend, and the failure mode is recorded in
full: on the morning of 2026-11-07, Geist's planner re-proposed
near-identical S1 plans tick after tick — including three
calculator bounces on the same stick arithmetic — burning his
entire rolling-hour budget on re-derivation. When dusk came, the
one event his written facts existed to handle, **he had no mind
awake to deliberate with**, and the night killed him nine times in
three minutes through a substrate loop no fact could reach. The
facts channel worked; the economics of from-scratch planning ate
the mind before the moment arrived. Failure class, in the house's
own taxonomy: infrastructure (budget) compounding an agent-layer
flaw (no carry-over between plans).

### 3.2 Mechanism — plan-delta drafting

- **The drafter** is the last *verified* plan plus the state
  delta: what changed since the plan was committed (position,
  inventory, deaths, stage evidence, new messages). In its first
  form the drafter is not a model at all — it is a continuation
  rule over the committed plan: drop completed steps, drop steps
  whose preconditions the state delta falsifies, keep the rest,
  and ask the planner model only for the *suffix* — the steps
  after the first invalidated one, or a repair for a single failed
  step. Full-plan generation becomes the fallback, not the
  default.
- **The verifier already exists.** The calculator checks counts
  and satisfiability (it caught the stick arithmetic three times —
  verification works; it was simply being paid for whole plans).
  World-evidence checks verify the delta itself: the state feed
  confirms the inventory and position the continuation assumes.
  A drafted continuation that fails the calculator, or whose
  assumed state contradicts the feed, is rejected and escalates
  to a full derivation — the plan-level form of §1.2.
- **Commit** writes the continued plan to the same text memory
  the architecture already keeps, with its provenance marked:
  *continued* (and from which committed plan), *repaired* (which
  step, why), or *fresh*. Reflection continues to record outcomes
  against plans; it now also records them against continuation
  depth, so a plan that has been continued eleven times and keeps
  failing is visible as such.
- **The counterweights (§1.3), instantiated.** (i) *Periodic full
  re-derivation:* every *K* ticks — and always at a stage
  boundary — the planner derives from scratch, ignoring the
  committed plan, and the result reconciles memory: agreements
  confirm, disagreements replace, and the disagreement itself is
  receipted. (ii) *Surprise-triggered invalidation:* any executor
  failure whose cause the plan did not predict, any death, any
  state-feed contradiction of a plan assumption, invalidates the
  plan immediately. A citizen may ride a continued plan through
  routine; he may not ride it through a surprise.

### 3.3 The A/B protocol — runnable on Lineage C, with instruments that exist

No new models, no downloads. The governor ledger
(`ledger/mind-calls.jsonl`) already receipts every mind call with
agent, status, and mind-seconds; the lineage's tick logs record
attempts, calculator verdicts, and outcomes; the scoreboard
records stage attempts and passes from world evidence.

- **Design:** alternate by attempt block within Lineage C. Arm A
  (control): current behaviour — full derivation every tick. Arm
  B: plan-delta drafting as above, with *K* fixed in advance
  (suggested *K* = 4 ticks) and invalidation rules as specified.
  Blocks alternate A/B/A/B across comparable stage work (S1
  attempts and beyond), with the arm recorded in the tick log so
  the ledger joins cleanly.
- **Primary metrics, all from existing records:**
  - mind-seconds per stage attempt (governor ledger ÷ tick log);
  - mind-seconds per stage *pass* — the number the league
    actually buys;
  - replans per stage (full derivations per attempt);
  - budget-exhaustion events (governor 429s and context-refusal
    400s attributable to plan volume) per rolling hour;
  - continuation depth distribution and invalidation causes
    (Arm B only) — the lock-in instrumentation.
- **Secondary:** stage pass rate per arm (world evidence only,
  per house rule); time-to-pass; deaths per attempt.

### 3.4 Kill criteria

- Arm B's mind-seconds per pass are not lower than Arm A's at
  comparable pass rates — the continuation machinery costs what
  it saves.
- Arm B's pass rate falls below Arm A's beyond noise — carried
  plans are worse plans, full stop.
- Invalidations fire so often that Arm B's effective full-
  derivation rate approaches Arm A's — the workload's plans do
  not persist, and rolling them is ceremony.
- Any single incident of stale-plan lock-in causing harm the
  control arm would have avoided (a death sequence, a lost
  inventory) *without* an invalidation having fired — the
  counterweight design is wrong, not just mistuned; stop and
  redesign rather than lengthen *K*.

### 3.5 The named risk, honestly

**Stale-plan lock-in is this design's pond anchor.** A delta
drafter that never re-derives can ride a wrong plan exactly the
way a citizen rode a wrong fact: the plan's premise (a location,
a resource, a route) is false, every continuation is locally
sensible, and the system efficiently executes its way nowhere.
The pond loop killed Geist nine times in three minutes through a
*substrate* path; a locked-in plan would do it through the
*deliberative* path, with better paperwork. The counterweights in
§3.2 are therefore not tuning knobs but the design's centre:
periodic re-derivation bounds the ride, surprise invalidation
ends it early, and continuation-depth receipts make the ride
visible in the record before it becomes a result. If the A/B
cannot demonstrate those mechanisms firing in practice — not in
principle — Arm B does not ship regardless of its mind-second
savings.

A second, quieter risk: continuation makes plans *legible as
savings* before they are legible as behaviour. The governor
ledger will show Arm B cheaper within a day; whether it is
*better* takes stage passes, which are slower evidence. The
protocol's ordering (pass rate is a kill criterion, not a
secondary observation) exists to keep the cheap number from
outrunning the true one.

---

## 4. Application C — Prediction-error perception for telltape

### 4.1 Today's mechanism, and the proposed variant

telltape perceives by **diff-gating**: cheap per-tile differences
and embedding drift decide which tiles earn embedding computation;
published change events ("tells") are written where measured drift
clears the gate. The gate is a ranker with a budget knob, and its
known honesty limits are measured: skipped tiles still drift (0.20
vs the embedded band's 0.48), so the gate ranks change, it does
not separate change from noise.

The VFlash-shaped variant is **prediction-error perception**: a
predictor extrapolates the stream's next interval — the next
primitives, in the digest sense: expected tile states, expected
drift band, expected scene continuation — and the system computes
embeddings and writes tells **only where prediction fails**. The
ledger becomes, explicitly, a record of surprises: silence means
"the world did what the model of it expected," and every tell is
a place the model was wrong.

### 4.2 What it would buy — and what it costs

**The buy is semantic, if it is real.** Diff-gating fires on raw
change: a cloud shadow, a lighting ramp, a camera's auto-exposure
are all large diffs and no news. Prediction error, from a
predictor that has absorbed the stream's regularities, fires on
*unexpected* change — the same raw change discounted by its
predictability. If the discounting works, the same budget buys
attention concentrated on the semantically surprising fraction,
and the LensFile's learned normal (period, jitter, phase — the
substrate already carries a per-stream self-model) becomes a
predictive model rather than a scheduling aid. That is a genuine
upgrade in kind, not degree: from "what moved" to "what moved
that shouldn't have."

**The costs are equally concrete.** A predictor sits in the
perception loop: it must be run per interval (its cost charged
against the very spend it saves), trained or fitted per stream,
and maintained as streams drift. Its failures are correlated
with its subject: the predictor is worst exactly where the
stream is least regular, which is where perception matters most.
And the diff gate it replaces is µs-class CPU arithmetic with a
decade of receipts in this programme; the predictor must beat
that baseline at equal total spend, not merely be interesting.

### 4.
...[truncated 9113 chars]
---

## Addendum 2026-11-07 — Seat harvest (ZCode Orin, ZCode ProArt, MCode ProArt)

*Three prepaid fleet seats were given the identical brief behind
this design and asked for independent takes: ZCode (GLM) on the
Orin, ZCode (GLM) on the ProArt, and MCode (MiniMax) on the
ProArt. The takes and a comparison are held in the lane's
records. What follows is what the harvest changes, confirms, or
challenges in the design above — including where a seat was
wrong.*

**Convergence.** All three seats independently rebuilt the
synthesis as a transactional system rather than a faster
pipeline: the change ledger is the source of truth, canonical
state is the replay of committed deltas, and agents at different
temporal resolutions are readers at different snapshot levels of
one log. All three put the design's weight where §1.2 does:
verification is the load-bearing cost, and it must be scoped to
the delta — the verifier sees the old primitive, the proposed
delta, and the evidence window, never the whole world. All three
rejected the cost slogan of §0 as median-true and tail-false: at
regime change, acceptance collapses and the system pays drafting
on top of full re-perception, strictly worse than batch at the
moment of maximum danger — so batch mode survives permanently,
as fallback, garbage collector, and audit mechanism. All three
treated cumulative error as a permanent audit tax: periodic full
re-derivation diffed against committed state, a cost that is
never finished being paid (§1.3). And all three sequenced the
first experiment the way §2.3 does — a deliberately dumb
drafter, constant-velocity extrapolation or raw region diffs —
to test the economics and the load-bearing assumption before any
learned drafter is built. Stage 0.5's trivial arm is that
experiment.

**The rejection channel.** Both GLM takes named the same missed
component, in the same words: the rejection channel. A rejected
draft is currently waste; in a rolling system it is perception
data — the record of where the system's model of the world was
wrong, in what direction, at what rate — and it can be routed:
rejection is a surprise signal, able to wake slower-tapping
agents and to feed the audit schedule, and the abort path earns
its engineering budget on that basis. The agreement is recorded
with its limit stated plainly: the two takes come from one model
family, so this is a single strong sample developed twice —
partial independence, not two independent witnesses.

**The epistemic third state.** The MCode take diverged, and its
missed component is the one this design lacked entirely: a delta
is three-valued, not two — confirmed-changed,
confirmed-unchanged, and *unobservable-at-this-tick*. Occlusion
means "no delta" does not mean "no change"; a two-valued
protocol silently launders the unobserved into the unchanged,
and every downstream derivation inherits the error, so the
verifier must be allowed to answer "insufficient observation."
The league's world digest v0 already implements a citizen-level
form of this rule — a stale feed reads as unknown, never as
calm — and the design above is amended in kind: any primitive
carried forward on unobservable evidence carries the third state
with it.

**The ledger as invalidation index.** The harvest's sharpest
single mechanism: the ledger's second job is indexing
invalidation. Every derived artefact — a plan, a prediction, a
digest entry — anchors to a ledger position and a region set,
so a committed delta invalidates exactly the derivations that
depended on what changed, in time proportional to the
invalidated set rather than to the number of agents. That, more
than the drafting itself, is what makes the multi-agent
economics of §3 close.

**A challenge to the governor, recorded, not adopted.** The
seats were unanimous that the league governor's unit —
mind-seconds per call — is the wrong thing to meter: per-call
pricing invites conservative drafting and hidden change. Their
candidates differed (reader demand; commit bandwidth per
accepted delta; derivations invalidated), and the harvest's own
synthesis is to price verification, the load-bearing cost. The
challenge stands open: the governor's unit is unchanged, and
the §3.3 A/B protocol still measures in mind-seconds — its
results should be read knowing the unit itself is contested.

**One flag, adjudicated.** The MCode take asserted that
VFlash's code is openly available and its runtime could be
pointed at this design's delta schema. That was checked against
the NVIDIA project page and the release trackers on 2026-11-07:
a GitHub link exists, but no public code, weights, or licence
could be reached. STUDY-VFLASH's finding stands — as of this
writing there is nothing to install — and the claim is filed as
announcement-vs-artefact confusion: a paper's availability
mistaken for a release.
