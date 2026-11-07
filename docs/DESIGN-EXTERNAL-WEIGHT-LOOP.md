# DESIGN — The External Weighting Loop: Weight-Space Work as a Rolling Operation

*Top-level design document, 2026-11-07. This document develops one
claim — that the strong form of weight-space programming is not a
model reading its own weights, but an external system that iterates
in and out of a running model during operation — states it
precisely enough to be wrong, bounds it by this programme's own
measurements, and derives the first three experiments, each with
the result that would kill it. It is the sibling of
DESIGN-ROLLING-PRIMITIVES: that document drafts plans and
percepts as deltas against verified state; this one drafts
**weight deltas** against verified behaviour, one substrate down.
Cross-references to WSP-SYNTHESIS are to the composed-system
record (looped refiner, liquid shadow, governed weight authoring);
references to "Phase 15" are to the fleet's governed patch
programme, whose measurements bound everything claimed here.*

*Nothing in this document is built. What exists today is named as
such; what is proposed is named as such; every load-bearing
unknown is collected in §8 rather than smoothed over.*

---

## 0. The thesis: the weak form and the strong form

### 0.1 The weak form — a model reading weights in one response

On 2026-11-03, Simon Willison published a careful replication of
the reading half of "Sparks of Weight-Space Programming"
(Takehi/Teoh/Zhang/Khattab). A local Qwen 3.8 27B, given the raw
weights of small PPO policy networks as text and **no tools** —
no code execution, no calculator, a single response — named the
games the networks were trained on: Pac-Man after 46 minutes 12
seconds and 43,506 reasoning tokens (72% confidence), Pong after
1 hour 4 minutes 54 seconds (75%), Breakout after 52 minutes 25
seconds (88%). It failed Freeway, calling it a Pac-Man-like grid
game. A frontier hosted model (Kimi K3.1 Pro) named Breakout in
9 minutes 41 seconds and 19,493 reasoning tokens.

This is genuinely remarkable and operationally useless, and the
design begins by holding both halves of that sentence. As a
measurement of what a reader can extract from weights, it is a
result. As a *way of working on a running system*, it has every
property we design against:

- **It is a single giant response.** One uninterruptible act of
  reasoning, priced in tens of thousands of tokens and tens of
  minutes, with no intermediate checkpoint at which evidence
  could correct it.
- **Its conclusions are unverifiable in-band.** "Pac-Man, 72%"
  is a claim the same witness grades. Nothing in the act
  converts the interpretation into a prediction that could be
  tested cheaply — although a probe battery (run the policy,
  watch what it does) answers the same question in seconds.
- **It does not scale with the artefact.** The demo networks are
  thousands of weights rendered as text. The models this
  programme operates are 0.6B–30B parameters. The reading feat
  does not transfer by enthusiasm; nobody is pasting a 30B
  artefact into a context window.
- **It still failed one case in four**, on the least famous
  game — the failure arriving, as failures do, exactly where
  prior knowledge ran out and the weights had to speak alone.

The paper's editing half is stronger — a frontier model editing
0.016% of Qwen3.5-0.8B's weights took MATH-500 from 7.9% to
48.1% and tripled IFEval — but it is a *project*: an expert
effort, performed once, on a small artefact, offline. §4 takes
up the two published critiques of the paper, because the design
answers both by construction.

### 0.2 The strong form — an external system, iterating during operation

This programme already owns the pieces of a different shape,
built for other reasons:

- **ExoJ-lineage senses.** External instruments that read the
  world and return judgements to systems that never see the raw
  input — built on the Oracle in October (I-JEPA and data2vec
  CLIs returning embedding fields, not verdicts), descended
  today into the Thor's jev-rack. The constitutional rule of
  that lineage binds everything below: **a sense is an advisor,
  never the gate.** A sense proposes readings; something else —
  probes, world evidence — disposes.
- **Per-pass taps.** Our Dory fork exposes the recurrent block's
  boundary states during generation, caller-enabled only,
  bit-identical with taps off (DORY-TAPS). The inside of a
  running model is, at one seam, already legible to an external
  reader.
- **A governed patch lifecycle, measured.** Phase 15 ran
  authored weight patches end-to-end — proposal → sealed
  artefact → eval → shadow → canary → adoption, rollback
  bit-for-bit — in ~25 minutes at 0.6B scale, and measured what
  patching is *for* (§2). Governance is not a wrapper we would
  need to invent; it is a path we have already priced.
- **A ledger culture.** Every consequential act in this
  programme is receipted against the state it assumed: plan
  commits carry provenance, verdicts carry patch-ids in force,
  mind spend is metered per call. A weight delta is one more
  kind of entry — if it is written in the same discipline.

**The claim of this design:**

> The useful form of weight-space programming is a **rolling
> external loop**: senses, judges, and patch authors living
> *outside* the model, iterating in and out of it **during
> operation** — reading state (weights, activations, per-pass
> taps), interpreting it with cheap external instruments,
> proposing weight deltas as governed artefacts, verifying them
> against held-out probes, applying them at safe seams,
> observing behaviour, and committing or rolling back — at the
> cadence of the work itself, not as an offline ceremony.

In the rolling-primitives pattern, one substrate down: the
**ledger is the loop's memory** (the last verified behaviour of
the sealed artefact in force, plus the receipts of how it was
verified); a **weight delta is a draft** (cheap to propose,
allowed to be wrong, not allowed to commit itself); the
**verifier is external** (held-out probe batteries and live
world evidence, never the proposing sense's confidence); and
**surprise invalidates** (behaviour that contradicts an adopted
patch's battery claims recalls the patch to its last sealed
state, pending re-verification — the weight-space form of the
sibling design's rule that surprise is the one signal a rolling
system must never amortise).

Three roles, named once:

- **The senses** (ExoJ lineage): taps readers, probe batteries,
  behaviour graders, the learned loop governor of §5-E1. They
  read; they do not write.
- **The author** (System Three, off-box or off-seat): proposes
  sealed weight deltas with a declared surface and a declared
  mechanism class. It is called on, asynchronous, expensive,
  and receipted — including its search costs (WSP-SYNTHESIS
  §3.6).
- **The gate** (governance, §3): verifies at deployment
  precision on the deployment artefact, shadows, canaries,
  adopts or denies, rolls back. The gate is the only writer.
  The human stands at exactly one point of it (§3.3).

The loop's novelty is stated narrowly in §4.2, because two
critics have already done the field the favour of narrowing it.

---

## 1. Anatomy: the cycle and its seams

### 1.1 The cycle

```
        ┌──────────────────── LEDGER ────────────────────┐
        │ sealed artefact in force · patch-ids · battery  │
        │ fields (uncollapsed) · behaviour receipts       │
        └───────▲──────────────────────────┬──────────────┘
           commit / recall                 │ base + receipts
                │                          ▼
   OBSERVE ──► SENSES ──► INTERPRET ──► AUTHOR proposes
   (live        (taps,      (external    sealed delta +
    behaviour)   probes,     instruments, declared surface
                │           falsifiable  + mechanism class)
                │           predictions)      │
                │                             ▼
                │                      GATE: verify on-box at
                │                      deployment precision →
                │                      shadow → canary ──► APPLY
                └──────────────────────────────────────  at seam
```

Each pass round the cycle is priced in the currency of its
seam: loop-seconds and steering events at the fast seam,
governance-minutes and search tokens at the slow ones. A cycle
that cannot produce its receipts has not run, whatever it
changed.

### 1.2 The seams, ranked

An external system may only enter a running model where the
architecture gives it a boundary. Four candidate seams exist
on our stack; three are real. Ranked by safety and
reversibility — the two properties that decide what each seam
may carry:

| Seam | Cadence | What can change | Reversibility | Status today |
|---|---|---|---|---|
| **S2 — between league ticks** | per tick (seconds–minutes) | the whole served artefact: a patched copy swapped for the citizens' brain between calls | total: the previous sealed artefact is restored bit-for-bit; the brain is stateless across calls, so no session state is stranded | shaped: hot-swap at a window boundary is already the synthesis's adopt mechanism; the governor already meters this boundary |
| **S1 — between Dory's passes** | per pass (sub-second) | transient state only: a steering delta on the boundary tensor h_k; nothing persists past the generation | total by construction: the delta evaporates when generation ends | half-built: the **read** path exists (taps, DORY-TAPS); the **write** path does not — no hook applies a delta to the boundary state |
| **S3 — at presence session boundaries** | per session (minutes–hours) | the presence brain's artefact, between voice sessions | total, as S2; slower blast-radius discovery | shaped: sessions are natural windows; a human is nearby by design |
| **S0 — mid-generation** | per token | the weights of the live server process | — | **not a seam we have** (see §1.3) |

**The ranking, in one line each:**

- **S2 (tick boundary) is the loop's centre of gravity** — the
  safest place for anything persistent: stateless calls, a
  whole-artefact swap, bit-for-bit rollback, and a governor
  already standing at the boundary metering what crosses it.
- **S1 (between passes) is the fastest seam and the safest
  place for anything transient** — a steering delta cannot
  outlive the generation it steers, so its blast radius is one
  response; it ranks second only because its write path is
  unbuilt and its effects are the hardest to attribute.
- **S3 (session boundary) is the canary theatre** — too slow
  for iteration, ideal for first live exposure of a patch class:
  real traffic, natural windows, a human within earshot.
- **S0 does not exist** and no part of this design may pretend
  otherwise.

### 1.3 The honest non-seam

Mid-generation weight mutation of a live llama.cpp server is
**not available to us**: the server loads its artefact at start;
there is no hot weight-swap interface; the citizens' brain and
the presence brain are stock-shaped servings. Anything in this
design that required rewriting weights *while tokens flow*
would require a serving-stack fork of an entirely different
order than the taps patch (+8 lines, behaviour-invariant), and
is excluded. The loop iterates at the seams that exist — tick,
pass (state plane only), session — and its cadences are the
seams' cadences. This is a constraint, and it is also the
safety case: every application point in the design is a point
where the system was already prepared to stop, swap, or end.

### 1.4 Two planes, kept separate

The loop works two planes that must never be conflated (the
conflation is §4.1's complaint against the paper, and it would
be embarrassing to re-commit it at home):

- **The state plane** (S1): transient interventions on
  activations — steering deltas, loop allocation. Nothing is
  written to the artefact; effects end with the generation.
  Cheap, fast, reversible by physics.
- **The weight plane** (S2, S3): persistent changes to a sealed
  artefact, arriving only as governed proposals (§3). Slow,
  priced, reversible by discipline (rollback), never by
  physics.

A result on one plane is not evidence about the other. A
steering direction that works transiently is a *candidate*
writer direction for a weight proposal — no more; it enters
the weight plane at the bottom of the governance path like any
other proposal.

---

## 2. Scope: what the loop is for, and what it may not claim

The loop's scope is not a matter of taste. It is Phase 15's
measurement, and the design inherits it as a fence:

**Measured (Phase 15/16, carried in WSP-SYNTHESIS):** authored
weight patching is a **behaviour-deployment instrument**. It
harvests format, completion, and framing failures, and it
installs readouts where the representation already separates
the classes. It measures **zero** on procedure, **zero** on
facts, and **zero** on unseparated relations. One patch through
the full governed lifecycle took ~25 minutes at 0.6B scale.
Casey's soft-joints design — patch the dials at the joints of a
signal chain, spine untouched — validated: 46.7% → 84.2%
held-out. A custom decision model, proposed as a patch target,
was a measured negative: held-out behaviour item-identical to
base, adoption denied. Detector-derived interventions on
procedure: eleven trials, zero effect; the writer/detector
distinction (a direction that *writes* a behaviour vs one that
merely *detects* it) is the one sharpening admitted, and it is
gated on WSP-SYNTHESIS Q2 before it widens anything.

### 2.1 What the loop may touch

- **Dials.** Soft-joint and scale-space adjustments at declared
  surfaces — the validated centre of the patch lane.
- **Unblocking edits.** Completion-pathology repairs: the
  paper's headline edit (subtracting a reasoning-loop direction)
  is of this class, and so — pointedly — is our own measured
  Dory problem: the refiner's failure is delivery, not depth;
  prompts arrive at correct answers inside reasoning that never
  terminates (DORY-SMOKE-1, DORY-TAPS). A loop that can detect
  a deliberation trap and unblock it is working the proven lane
  on our own most concrete failure.
- **Readout installs.** Where a battery demonstrates the
  representation already separates a class the artefact fails
  to report, installing the readout is deployment of existing
  structure, not new capability.
- **Loop allocation.** The governor of §5-E1: deciding how many
  passes a window buys. Allocation touches no weights at all;
  it is the loop's cheapest organ and its first experiment.

### 2.2 What the loop may not claim

- **Procedure.** No patch, at any cadence, is described as
  teaching the model *how* to do something it could not do.
  Detector-derived procedure proposals are denied by default,
  with the eleven-trial null cited in the denial. Writer-derived
  procedure proposals are admissible as *experiments* only,
  under Q2's gate, never as normal operation.
- **Facts.** A weight delta is not a knowledge channel. Nothing
  the loop writes may be represented as the model "learning"
  a fact; facts live in ledgers, prompts, and retrieval, where
  they can be read and corrected.
- **Capability.** The loop deploys behaviour the artefact's
  representations already support. Any proposal whose stated
  benefit is a capability gain is returned for re-scoping
  before it is verified, however good its battery numbers look
  — because a battery that appears to show capability gain
  from a dial-class edit is, on our measurements, a battery
  that has been gamed or misread, and the correct response is
  suspicion of the instrument.

### 2.3 Struck from this design

Per the fence above, the following elements were considered
and are struck **in the document itself**, so that no later
reader mistakes their absence for an oversight:

- ~~The loop teaches citizens new skills at runtime by patching
  their brain between ticks~~ — **struck**: procedure measures
  zero (§2.2). Citizens learn in plan space and memory, where
  the sibling design works; the weight loop keeps their brain
  *honest* (unblocked, well-dialled), not *smarter*.
- ~~A self-improving presence brain that adopts its own patches
  overnight~~ — **struck**: adoption of a persistent patch is
  the human's gate (§3.3), and "overnight" is precisely the
  cadence at which unobserved adoption would hide.
- ~~Weight-reading as a diagnostic sense~~ (feed the brain its
  own weights and ask what it is doing) — **struck as a
  load-bearing instrument**: 43,506 tokens and 46 minutes for
  a label a probe battery settles in seconds, at a 3-in-4 hit
  rate on toy networks (§0.1). It may survive as entertainment;
  it appears nowhere in the loop's sense path.
- ~~Continuous mid-generation weight adaptation~~ — **struck**:
  the seam does not exist (§1.3).

---

## 3. Governance: the default path, at three speeds

Governance is not a review step bolted onto the loop; it is
the loop's operating system (WSP-SYNTHESIS §1.2). What the
rolling form adds is *cadence*: the same propose → verify →
adopt/deny → rollback path, run at three speeds with autonomy
matched to reversibility.

### 3.1 The three speed classes

- **Class I — per-pass steering (S1, state plane).**
  Autonomous at machine cadence. Justification: transient,
  in-memory, evaporates at generation end; blast radius one
  response. Requirements: the steering policy is itself a
  sealed artefact (a governor build, §5-E1/E3), every steering
  event is receipted (pass, delta norm, trigger features), and
  a kill switch reduces the policy to no-op without a restart
  of anything else. No weight changes. No human in this loop;
  the human reviews its receipts.
- **Class II — per-tick patch proposals (S2, weight plane, up
  to canary).** Autonomous through proposal, verification, and
  shadow. Canary — exposure of one citizen's non-critical
  traffic to a patched copy — is permitted autonomously only
  when the proposal meets the standing FIX-class shape:
  evidence-dominant on sealed held-out batteries,
  rollback-proven, blast-radius-bounded, and smoked in the
  serving shape it will run in. Canaries are **temporary and
  auto-expiring**: a canary that is not adopted through
  Class III reverts at its expiry; there is no path by which a
  canary quietly becomes the artefact. Every transition is a
  ledger entry.
- **Class III — adopted persistent patches (S2/S3).** The full
  governed lifecycle, priced by Phase 15 at ~25 minutes at
  0.6B scale — with the honest scaling note that battery
  replay cost grows with artefact size, and the league brain
  is 30B; the 25-minute figure is a floor measured on a small
  model, not a promise (§6). Adoption produces a new sealed
  artefact whose hash, parent hash, battery fields, and
  patch-ids become the base every later delta is drafted
  against.

### 3.2 Standing rules the loop inherits

- **The discrimination rule.** No instrument is trusted until
  it has demonstrated discrimination on the run's actual
  inputs. The taps are the standing cautionary tale: per-pass
  contraction is real and strong (median r3 0.23–0.31 across
  36 runs) and *outcome-blind* — delivered and undelivered
  runs interleave completely (pooled medians 0.333 vs 0.388).
  A sense that reads "settled" everywhere is not a sense.
  Every new instrument in the loop passes a discrimination
  check on live inputs before its readings may trigger even a
  Class I action.
- **Advisor, never gate.** Senses propose readings; the gate
  disposes on probe and world evidence. No confidence score
  from any sense — JEPA-lineage, taps-derived, or the author's
  own — is itself a verification.
- **Two-currency verify.** A patch (or steering policy) must
  hold its verdicts at equal-or-lower loop *and* embed budget,
  so quality cannot be silently bought with the other currency
  (WSP-SYNTHESIS §4, adopted unconditionally).
- **Search costs are receipted.** The ~25 minutes prices
  verification, not discovery: the paper's results rest on a
  search of up to 300 sandbox runs and ~200k output tokens for
  a single "one-shot" write. Every proposal carries its search
  cost (tokens, passes, wall time) beside its governance cost.
  Two accepted patches whose search cost exceeds their measured
  value end trigger-driven authoring at loop cadence; the
  author demotes to batch (WSP-SYNTHESIS §3.6, dead-end 3).
- **Patch-ids in force ride every receipt.** The loop reads a
  system it modifies; if a downstream verdict does not name
  the artefact it was produced under, attribution dies and the
  ledger becomes fiction (WSP-SYNTHESIS §1.3).
- **Surprise recalls.** Behaviour contradicting an adopted
  patch's sealed battery claims triggers automatic recall to
  the parent artefact, pending re-verification. Recall is a
  safety action — reversible, returning to the last verified
  state — and is therefore autonomous. Adoption is a
  commitment, and is therefore not (§3.3). The asymmetry is
  deliberate and mirrors the sibling design: a rolling system
  may always retreat to verified ground on its own authority;
  it may advance only through the gate.

### 3.3 Where the human gate remains

**Adoption of any persistent patch is Casey's decision.** The
loop's job is to make that decision cheap and evidence-complete:
a sealed artefact, battery fields uncollapsed in the ExoJ
manner (the full per-question readings, not the pass/fail
projection), shadow and canary receipts, search and governance
costs, and a one-line statement of which §2.1 class the patch
belongs to. What the loop may never do is convert its own
accumulated confidence into an adoption. This is the standing
classification applied to a new substrate, not a new rule:
FIX-class evidence earns a *canary*; adoption creates the new
normal, and the new normal is the owner's call.

---

## 4. The critiques, answered in design terms

### 4.1 Honnibal: the conflation charge

Matthew Honnibal's charge against the paper is that it
conflates two topics that deserve separate treatment: what a
model can do with raw weights *without* tools, and what models
armed with code can do to update other models. The charge is
correct, and this design pleads guilty on the paper's behalf
and then changes the subject on purpose: **the loop is
unapologetically the second topic.** The no-tools reading feat
is excluded from the sense path (§2.3) precisely because the
conflation flatters it — stripped of the editing results'
reflected excitement, a 46-minute, 43,506-token single-response
guess at "Pac-Man" that fails Freeway is a parlour measurement
of the reader, not an instrument for the read.

Tool-armed interpretation is the scientifically stronger
posture, for a reason the design can state as a rule: **an
interpretation is admitted only if it can be converted into a
falsifiable prediction against a probe.** "This direction
writes the reasoning loop" becomes: *subtracting it will raise
delivered completions on the held-out battery by a stated
amount, at a stated cost, without moving the regression
slices.* That prediction is cheap to test and impossible to
fake for long. The no-tools posture cannot make its
interpretations falsifiable without ceasing to be no-tools;
the loop's posture makes falsifiability the price of admission
for every reading. Conflation dissolved: we do not claim the
model *understands* its weights in any sense that matters
here; we claim an external system can form hypotheses about
weights and *settle them against evidence at operational
cadence*.

### 4.2 Goedecke: the ordinary-steps deflation

Sean Goedecke deconstructed the paper's Qwen3.5-0.8B repair as
taking the same steps a human ML researcher would use: find
the pathological direction, subtract it, measure. Granted —
entirely. The design locates its novelty where the deflation
leaves room, and nowhere else:

- **Not the steps.** Every operation in the loop — probe,
  direction-finding, subtraction, battery — is ordinary
  ML-researcher work. Any sentence in this programme's records
  implying otherwise should be corrected on sight.
- **The cadence.** The steps run *during operation*, at tick
  and pass boundaries, as routine — the difference between a
  careful person compiling by hand and a build system. Nobody
  claims the build system compiles more cleverly; the claim is
  that compilation became continuous, receipted, and boring.
- **The governance.** Each ordinary step lands as a sealed,
  verified, reversible artefact with its costs receipted —
  the difference between a heroic one-off repair and a
  maintained system is not the repair; it is that the second
  one can be audited, attributed, and undone.
- **The externality.** The instruments are not the patient.
  The model being steered is never the model grading the
  steering; the reader of the taps is not the block being
  read. Willison's Qwen graded its own homework in-band; the
  loop's entire architecture is the refusal of that arrangement.

Willison's own closing caution — that he is "not ready to
declare the age of source code is over" on the strength of
these results — is adopted as this design's posture toward its
own claims. The loop, if it works, produces something less
exciting and more valuable than self-editing machines: a
maintained artefact whose behaviour-deployment history is
fully legible.

---

## 5. First experiments, cheapest first

Each experiment names what it needs that exists, what it does
not, and the result that kills it. Ordering is by kill-power
per unit cost, per house practice.

### E1 — The taps governor: the loop's allocation organ

**What it is.** A small learned governor that allocates Dory's
loop count per window — the external/learned route the taps
verdict mandated, since raw contraction cannot discriminate
(DORY-TAPS; WSP-SYNTHESIS addendum). It is the loop's first
organ precisely because it touches no weights: it is a
Class I citizen from birth, and it proves the loop's
sense → decide → receipt cycle at the cheapest seam before
anything is allowed to write.

**How it plugs in.** The governor sits between the refiner
seat and the Dory instances. Inputs: external signals with
demonstrated discrimination (CfC surprise, sheaf residual,
class-level loop-marginal receipts from the ledger) — *not*
raw per-pass delta features, which the taps matrix convicts
of outcome-blindness; taps features may enter only as the
trained model's inputs if the training itself demonstrates
held-out separation the raw features lacked. Outputs: k ∈
{1,2,3,4} per window plus a budget-admission decision, in
loop-seconds. Every allocation is receipted with the features
that produced it, so quality can always be divided by spend
after the fact. Delivery is by multi-instance routing over
fixed-k servings (WSP-SYNTHESIS Branch B machinery), which
requires no engine change.

**Needs that exists:** the 36-run taps matrix and its labels;
the ledger's loop receipts; fixed-k routing on the stock PR
build; the conservative default policy (k=1 unless a class has
demonstrated loop-marginal value, k=2 on surprise) as the
baseline it must beat. **Needs that does not exist:** the
trained governor itself (a crew is building v0 tonight from
the taps matrix, offline, on recorded data).

**Kill criterion:** the governor fails to beat fixed-2 at
equal total loop-seconds on grounded quality (the
WSP-SYNTHESIS Q4 falsifier), or its features show no held-out
separation between windows where another pass changes the
verdict and windows where it does not — in which case
allocation stays a receipting router at fixed-2 and the loop
loses its cheapest organ, honestly.

### E2 — The tick-boundary patch loop, against a fixed battery

**What it is.** The full weight-plane cycle at S2, run as an
experiment rather than an operation: a known dial-class
failure of the league brain, measured on a **fixed** held-out
battery, carried once around the loop — propose → verify →
shadow → canary → verdict — with every price receipted.

**The target behaviour.** A format/completion failure of the
citizens' brain on held-out prompts — the class Phase 15
proved patchable. The concrete candidate is plan-shape
discipline: the deliberating citizens' calls are
schema-bound (a plan is JSON of a declared shape), and
format failures in that traffic are measurable, frequent
enough to battery, and dial-class by construction (the
representation plainly separates well-formed output; the
failure is in the readout path). The battery is fixed before
the author is called: held-out prompts scored for schema
validity and task completion, plus regression slices covering
the brain's other duties (narration, calculation, chat), so
capability-shaped forgetting has somewhere to be seen
(Phase 15's E5 warning: forgetting is invisible to generic
probes, so the slices must be task-held-out, not generic).

**The cycle.** The author (off-box, System Three) proposes a
sealed delta with declared surface and mechanism class. The
gate verifies on the Thor, on the deployed artefact, at
deployment precision — *in place*, since the deployed grid is
Q5_K_M and there is no cheap cross-precision path
(WSP-SYNTHESIS §4). Shadow: the battery and regression slices
replay against the patched copy with no live traffic. Canary:
one citizen's non-critical traffic (narration-class calls,
never deliberation) routes to the patched copy for a bounded
window, auto-expiring. Verdict: battery delta, canary delta,
cycle time, search + governance cost — reported against the
Phase 15 reference price (~25 min at 0.6B), with the 30B
scaling measured, not assumed. **Adoption is not part of E2:**
the experiment ends at a decision packet on Casey's gate
(§3.3). E2 tests the loop, not the patch.

**Needs that exists:** the tick seam (stateless brain calls
under a governor that already routes them); the battery
discipline and lifecycle from Phase 15; canary-shaped traffic
classes in the league's own call mix. **Needs that does not
exist:** the fixed league-brain battery itself (new, small,
must be sealed before any authoring); a patched-copy serving
slot beside the brain's (a second llama-server instance under
thor-admit discipline — plumbing, not research); Q1's verdict
on which surface survives the deployed grid (E2 inherits Q1;
if Q1 is still open, E2's surface is the overlay/scale-dial
class that survives by construction, and says so).

**Kill criterion:** shadow and canary disagree — a patch that
passes shadow eval fails to reproduce its battery gain on
canary traffic, or regresses any sealed regression slice
beyond noise. Either result shows the tick seam's verification
is not predictive of live behaviour, and a loop whose
verification does not predict is a ceremony: stop, and fix the
battery before any further patch work at this seam.

### E3 — Per-pass steering on Dory, with taps feedback

**What it is.** The state plane's first experiment: close the
S1 loop on the refiner's measured disease. Dory's failure is
delivery — correct answers dying inside reasoning that never
terminates, at every loop count (DORY-SMOKE-1; DORY-TAPS:
p1/p2/p5-class prompts trapped in deliberation while p4-class
delivers reliably). The paper's repair for the same disease
was a weight edit: subtract the reasoning-loop direction. E3
tests the transient form: when the taps show a window entering
the deliberation trap's signature, apply a steering delta to
the boundary state between passes — subtract the loop
direction from h_k — and measure whether delivery is rescued
*within the same generation*, at fixed k.

**The honest anatomy.** The trap's signature cannot be raw
contraction (outcome-blind, §3.2). The trigger must be a
learned or behavioural feature — reasoning-length trajectory,
repetition statistics of the emitted stream, the E1
governor's trap classifier if E1 produces one — and it must
pass the discrimination rule on the battery before it may
trigger anything. The steering direction is derived offline
from contrasted runs (delivering vs trapped continuations),
exactly the writer-direction method; applied transiently, it
is a Class I action; if it works, it becomes a *candidate*
for a weight-plane proposal through E2's path — the two
planes' hand-off, exercised once, in the right direction.

**Needs that exists:** the taps read path (boundary states at
layers 56/96/136/176 for passes 1–4, caller-enabled,
behaviour-invariant when off); the 36-run battery with
delivery labels; the contrasted-run corpus (trapped and
delivering runs at matched k). **Needs that does not exist:**
the steering **write** path — a hook in the fork applying a
delta to the boundary tensor between passes, held to the
taps patch's own discipline (default-off, off == stock
bit-for-bit, verified by replay). This is the experiment's
real engineering cost and is stated as such; it is a fork
change of the same character as taps, not a serving change.

**Kill criterion:** steering does not raise delivered-correct
on the trap-class prompts at fixed k versus the unsteered
arm — or it rescues traps by degrading the reliably-delivering
class beyond noise. Either way the state plane's first
hypothesis dies cleanly: delivery is then a termination-
contract problem (reasoning-off operation, output contracts),
not a steering problem, and E3's negative result is what
proves it.

---

## 6. Where this design is weakest

Stated in the body, per house doctrine, before §8 collects
the unknowns:

- **The verification surface is the safety surface.** The loop
  is exactly as safe as its batteries are honest. Phase 15's
  sharpest warning is that capability-shaped forgetting is
  invisible to generic probes — a loop cycling patches at
  operational cadence against a shallow battery will
  confidently deploy slow damage. Battery design, not patch
  design, is where this programme's care belongs.
- **The price was measured at 0.6B; the brain is 30B.** Every
  cost in this document inherits that gap. The loop may prove
  to be a small-model instrument (Dory at 4B, the citizens'
  refiner) long before it is a big-brain instrument, and the
  design should be read with that demotion pre-accepted.
- **Cadence multiplies the author's search problem.** A
  ceremony can afford a 300-run search; a loop cannot.
  §3.6's dead-end — governed only in the verification half —
  applies to this design with interest, and E2's cost receipts
  are the first place it will show.
- **Precision is an open gate.** Q1 (edit survival on the
  deployed grid) is unresolved at the time of writing. If no
  surface survives, the weight plane shrinks to the overlay
  and scale-dial class — the loop survives, smaller, and this
  document's §2.1 dial clause becomes most of its territory.
- **The loop observes a system it is changing.** Patch-ids in
  force (§3.2) are the mitigation, but the deeper problem is
  real: the behaviour distribution the batteries were sealed
  against drifts under the loop's own patches and under the
  citizens' growth. Adopted patches therefore have a
  half-life, and re-verification cadence for the *standing*
  artefact — not just new proposals — is a cost this design
  names but does not yet price.

---

## 7. Claims register

Load-bearing claims only. "Measured" means our instruments,
this programme.

| # | Claim | Source |
|---|---|---|
| 1 | Local 27B weight-reading: Pac-Man in 46m12s / 43,506 reasoning tokens (72%); Pong 1h04m54s (75%); Breakout 52m25s (88%); Freeway failed | Willison 2026-11-03, author's runs |
| 2 | Paper's edit: 0.016% of Qwen3.5-0.8B weights; MATH-500 7.9% → 48.1%; IFEval ×3 — author-reported | Sparks of WSP, abstract |
| 3 | Authored patching: zero on procedure, facts, unseparated relations; harvest = format/completion/framing + readouts on separated representations | Phase 15/16 [measured] |
| 4 | Full governed patch lifecycle ≈ 25 min at 0.6B; rollback bit-for-bit | Phase 15 [measured] |
| 5 | Soft-joint dial: 46.7% → 84.2% held-out, spine untouched; custom decision model patch = measured negative | Phase 15 [measured] |
| 6 | Detector interventions on procedure: 11 trials, zero effect; writer/detector distinction gated on Q2 | Phase 15/16; WSP-SYNTHESIS §3.4 |
| 7 | Taps: per-pass deltas contract (median r3 0.23–0.31, 36 runs) and are outcome-blind (pooled delivered 0.333 vs undelivered 0.388) | DORY-TAPS [measured] |
| 8 | Dory's measured failure is delivery: 4/6 prompts correct-in-reasoning, never delivered, at every k (reasoning on); decode 19.7/13.0/10.4/7.6 tok/s at k=1–4 | DORY-SMOKE-1 [measured] |
| 9 | Taps patch: +8 lines on the fork; caller-enabled only; off == stock bit-for-bit; the server never enables capture | DORY-TAPS [measured] |
| 10 | Author search behind the paper's results: up to 300 sandbox runs, ~200k output tokens per "one-shot" write; the 25 min prices verification, not search | WSP-SYNTHESIS §3.6 |
| 11 | The deployed grid is Q5_K_M; the NVFP4 checkpoint is a QAD product — patch in place on the deployed artefact or not at all | WSP-SYNTHESIS §2, §4 |
| 12 | Senses are advisors, never the gate (ExoJ lineage; jev-rack constitution) | Programme standing rule |

---

## 8. What would have to be true

The design stands on the following. Each is stated so that its
failure is recognisable when it arrives.

1. **Q1 resolves with at least one surviving surface** at
   deployment precision — an edit geometry whose behavioural
   effect survives the deployed grid. If none survives, the
   weight plane is the overlay/dial class only, and §2.1
   shrinks accordingly.
2. **Shadow evaluation predicts canary behaviour** (E2's
   premise). If the tick seam's offline verification does not
   forecast live behaviour, no cadence of governance repairs
   it; the loop's weight plane closes until the battery
   problem is solved.
3. **A steering write path can be added to the fork** under
   the taps discipline — default-off, off bit-identical to
   stock, replay-verified. If the write hook cannot be made
   behaviour-invariant when disabled, the state plane stays
   read-only and E3 does not run.
4. **The governor demonstrates the discrimination the raw
   taps lacked** (E1's premise): some feature set separates
   windows where another pass changes the verdict from windows
   where it does not, on held-out inputs, at a false-settle
   rate the budget can afford. If nothing separates, allocation
   is fixed-2 with receipts, permanently.
5. **Batteries can be built that see the damage that
   matters** — task-held-out slices that catch
   capability-shaped forgetting at the cadence the loop runs.
   This is an instrument-design claim, and it is the one the
   whole safety case rests on.
6. **Author search fits the envelope at loop cadence** — the
   cost per accepted patch (§3.2) stays below the measured
   value of the patches it buys, at tick cadence, not just at
   ceremony cadence.
7. **The citizens' brain remains stateless across calls** in
   the serving stack. S2's safety argument is that no session
   state is stranded by an artefact swap; any future move to
   persistent KV or session state in that serving re-opens
   the seam's analysis from the beginning.
8. **Adopted patches have a measurable half-life** — their
   battery claims either persist under drift or decay
   observably enough that the re-verification cadence (§6)
   can be priced. A patch whose validity decays silently is
   a poisoned base in the sibling design's sense, one
   substrate down.
9. **The two planes stay separate in practice** — that
   transient steering results are not silently read as weight
   evidence, nor battery results as steering evidence, as the
   loop's records accumulate. This is a discipline claim about
   us, not about the models, and it is listed here because
   the paper we started from failed exactly it.

---

*End of design. Companion documents: DESIGN-ROLLING-PRIMITIVES
(the same pattern in plan and percept space), WSP-SYNTHESIS
(the composed system and the Q1–Q6 queue this design's
experiments inherit), STUDY-VFLASH (the within-object decoding
result), DORY-TAPS (the seam instrumentation and the verdict
that allocation goes external).*

---

## Addendum 2026-11-07 — Seat take: ProArt Claude Code

*This addendum records the contribution of a seat the main
design did not use: Claude Code on the ProArt, run as a pure
thinking tier (headless, no tools, the brief embedded whole;
the full take is held in the lane's seat record as
weightloop-claude-code-proart). The take was asked one
question — whether the external loop is a real advantage over
one-shot introspective authoring, or ceremony around the same
limits. Its answer amends this design in one place, sharpens
it in a second, strengthens the experiment discipline in a
third, and lodges one challenge as a hypothesis. Nothing
above is overwritten: each item below names the section it
touches and whether it amends, sharpens, or merely records.*

### A.1 The verifier is a consumable — §3 gains a verifier budget

The design treats held-out probe batteries as the gate's
ground (§3, §5-E2) and names battery honesty as the safety
surface (§6). The take's correction: **even an honest battery
is depleted by use.** Every verification call leaks
information about the probes into the loop's choices. A
propose-and-select loop running hundreds of commits is an
adaptive optimizer aimed at its own probe set, and it will
fit the held-out set the way public leaderboards get fitted —
no gradients needed. Each delta passes its check; the total
drifts. This sharpens §6 rather than contradicting it: the
verification surface is the safety surface, and it is also a
*consumable* — spent a little by every commit it certifies.

§3 therefore gains a **verifier budget**, with three tiers of
probes:

- **Dev probes** — visible to the proposer; spend freely.
- **Gate probes** — the probes that decide commits, accessed
  only through a limited-information mechanism
  (Thresholdout-style noisy answers, or a small bit budget
  per query), so that a commit decision cannot transmit the
  gate set back into the proposer's search.
- **A sealed audit set** — touched only on a fixed schedule,
  never used to decide a commit; its sole job is to measure
  the gate set's own drift.

Gate probes are **retired and regenerated on a schedule**, by
a generator that does not share weights with the proposer. A
widening gap between gate-set and audit-set performance is a
**divergence alarm**: the loop is fitting its judge, and
commits freeze until the budget is repaired. This also
corrects one premise of §5-E2 as written: a *fixed* battery
is right for a single pass around the loop, and wrong as a
standing design, because a battery that stays fixed while the
loop iterates becomes the loop's true objective.

The failure mode has a name, and it is visible at ledger
level, not at commit level: **verifier capture**, in two
channels that compound.

1. **Adaptive overfitting** (above): the loop slowly optimizes
   its judge in place of the behaviour the judge stands for.
2. **Operational steering — the input-shaping attack.** The
   loop takes its failure signals from live operation.
   Whoever can shape the input stream shapes which failures
   get flagged, and thereby shapes which deltas get proposed
   and verified — a *verified* write path into the weights,
   since each steered delta genuinely passes the checks its
   steering arranged to have run. Real-time data poisoning,
   with a governance stamp on every step.

Neither channel is catchable locally, because each delta
really does pass. The damage shows only in the distribution
of committed deltas and in the gate/audit gap — which is why
both are monitored at ledger level, and why the take's
mitigations bind at the trigger rather than at the commit:
failure signals that can trigger authoring must come from
sources the operating inputs cannot produce (curated
batteries, or flags confirmed by a human or a separate
judge); commits are rate-limited per input source; and every
behaviour delta must carry a mechanism that survives
ablation, because steered edits tend to have mechanisms that
do not hold up. The take's expectation is recorded without
endorsement or rebuttal: even with these mitigations,
verifier capture is what limits deployment of the loop in
open-input settings.

### A.2 Staging — a hypothesis against §2's fence, recorded as a hypothesis

§2 holds the fence: authored patching is behaviour
deployment; it measures zero on procedure, per edit, and the
design builds on that measurement. The take accepts the
per-edit measurement and challenges the inference from one
edit to many: **staging**. Edit *k* installs a readout that
makes a latent distinction linearly available at a seam — a
§2.1-permitted act, deployment of existing structure. Edit
*k+1* routes behaviour on that readout — again a §2.1 act.
Each step compounds *inside* the permitted lane rather than
escaping it; the claim is that a chain of such steps can
assemble small amounts of procedure out of steps that each
look like routing, reaching what a single edit measurably
cannot. One-shot introspection cannot do this at all, because
it cannot check its intermediate states. Of everything the
take offers, staging is the only capability-shaped claim —
and it is untested.

It is therefore recorded as **a hypothesis with its test, not
a design premise**. §2 is not amended: procedure remains
denied as normal operation (§2.2), and staging joins the
writer-derived procedure proposals already gated there —
admissible only as an experiment. If the hypothesis is ever
promoted, it enters through §8 as a new load-bearing unknown;
it does not enter by quietly widening §2.1.

Its test is the two-family experiment of A.3: family **S**
(separable — format and behaviour failures where triage
separates at AUC above 0.9, the known-good regime) and family
**P** (procedure — a novel deterministic transform or a short
arithmetic procedure, triage AUC near 0.5, where one-shot
authoring measures zero). Staging runs to depth K ≤ 4
(instrument, route, route). The hypothesis lives only if
gains on P grow with K; a flat curve is the fence reasserting
itself through the experiment, which is also a result worth
having.

### A.3 Baseline discipline for E2-class tests — §5's kill criteria strengthened

§5-E2 as designed tests the seam: its kill criterion is that
shadow and canary agree. The take's point, adopted here: that
criterion never tests the *author*. A loop can pass E2 with
the authoring model contributing nothing the verifier did not
supply — in which case the author component is ceremony,
however good the governance around it. For E2-class tests —
any test whose result will be cited as evidence about the
loop — four conditions are run, **matched on total compute
and on verifier calls**, scored **only on the sealed audit
set** (A.1), with off-target drift measured as KL divergence
of next-token distributions on a fixed, broad, generic
corpus: batteries measure only what someone thought to test,
and the KL term is the collateral instrument for the damage
nobody thought to test for.

- **A. One-shot introspective authoring** — best of N at the
  same total token budget.
- **B. The external loop** — staging to depth K, readouts
  permitted.
- **C. Verifier-matched random search** — sparse random or
  evolutionary search over the same parameter mask, with the
  same verifier and the same number of verifier calls.
- **D. Rank-1 LoRA** — trained on the same number of labelled
  probes.

Kill criteria, decided in advance:

1. **Staging does not exceed the ceiling.** On P, B beats A
   by less than 5 points absolute at any K ≤ 4, or B's gain
   does not increase with K → composition does not escape
   the ceiling; the capability claim is dropped and only the
   governance pipeline is kept.
2. **The author is not the power source.** On S, C reaches at
   least 80% of B's gain at equal verifier calls → the
   verifier is doing the work; the author is replaced by
   cheap search, and weight-reading is recorded as a
   diagnostic tool, not a writing instrument.
3. **Not worth the complexity.** On either family, D matches
   B within 2 points at equal or lower off-target KL → use
   LoRA with a ledger and rollback; skip authoring.
4. **The loop is fitting its judge.** B's gate-to-audit gap
   exceeds twice A's → fix the verifier budget (A.1) before
   anything else runs.

Survival is all four at once: B beats A on P with gains
growing in K, beats C by a clear margin on S, and stays
inside its KL bound.

The seat's prior is recorded **as a prior, not a result**:
kill criterion 2 fires first — verifier-matched random search
matches the loop on the separable family — and criterion 1
fires for the procedure family beyond K = 2. The design
holds no position on either. They are written here so that
when the experiment runs, the prediction it is testing
against is on the record before the numbers are.

*The take proposes more than this addendum adopts — a cheap
triage gate that routes failures by measured separability
before any authoring spend, instrumentation-first edits as
their own ledger class, and the ledger rebuilt as a
dependency graph with cascading rollback. Those stand in the
seat record, unadopted. If any is taken up, it will be taken
up the way these were: named, sectioned, and argued against
the measurements.*
