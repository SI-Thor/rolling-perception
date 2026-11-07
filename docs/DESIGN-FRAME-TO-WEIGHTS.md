# DESIGN — Frame to Weights: The Compilation Path

*Top-level design document, 2026-11-07. This document develops
the third move of the weight-space programme: an external frame
— the ExoJ-lineage superstructure of senses, judges, governors
and patch authors that runs around a resident model (Casey's
"XO cortex") — **compiles down into the model it surrounds**.
A frame behaviour that has proven itself at runtime is
distilled into a weight modifier — a LoRA, another attachable
modifier, or a governed base-model edit — after which the
behaviour runs at weight speed and the loop is no longer
required to produce it. The frame is the school; the weights
are the graduate. The document names the pattern's prior art
before claiming anything, states what can and cannot graduate,
prices the promotion pipeline in this programme's governance
terms, assigns the liquid models their roles, and derives
three experiments with kill criteria.*

*Companion documents: DESIGN-EXTERNAL-WEIGHT-LOOP (the loop
this compiles from; its seam map, its §2 scope fence, and its
addendum on verifier budgets are inherited whole),
WSP-SYNTHESIS (the composed system and the Q1–Q6 queue),
DESIGN-ROLLING-PRIMITIVES (the sibling pattern in plan and
percept space). Nothing in this document is built. What exists
today is named as such; what is proposed is named as such;
every load-bearing unknown is collected in §9.*

---

## 0. The thesis: the internal/external split is a phase difference

Weight-space work currently presents as an either/or. On one
side, the internal form: a model reads raw weights in a single
response and edits them — remarkable, uninstrumented, priced
in tens of thousands of reasoning tokens per act, and graded
by the same witness that performed it (DESIGN-EXTERNAL-
WEIGHT-LOOP §0.1). On the other side, this programme's
external form: the weighting loop, where senses, judges and
authors live outside the model and iterate in and out of it at
safe seams — governed, receipted, reversible, and *slow in
the way supervision is slow*: every behaviour the frame
produces is paid for again at every call, forever.

Neither form is the finished shape. The internal form has no
verifier; the external form has no economy. The claim of this
design is that they are two phases of one lifecycle:

> **A behaviour is first produced by the frame** — externally,
> observably, at frame cadence, against live evidence. **If
> the behaviour proves stable and state-independent, it is
> compiled**: the frame's receipts become a training corpus,
> the corpus trains a weight modifier, the modifier passes a
> graduation exam on probes the frame never saw, and the
> behaviour thereafter runs inside the model at weight speed.
> **The frame then retires that behaviour to a monitor** and
> spends its cadence on the behaviours that are not yet — or
> can never be — compiled.

Compilation is not a metaphor borrowed from software; it is
the same trade, with the same terms. The frame is an
interpreter: flexible, inspectable, slow, present at every
execution. The modifier is compiled code: fixed, opaque at
runtime, fast, absent until invoked by the forward pass. And
the trade has the same price in both worlds — whatever the
interpreter was checking at runtime, the compiled artefact
no longer checks. §2 exists to say which behaviours can
survive that trade, and §3 exists because the thing most
likely to be baked in by compilation is the frame's own
overfitting.

One asymmetry governs everything below: **compilation is
adoption, not canary.** A compiled modifier is a persistent
weight artefact; by the standing classification, its adoption
is Casey's gate (DESIGN-EXTERNAL-WEIGHT-LOOP §3.3). The
pipeline below is built to make that decision cheap and
evidence-complete, exactly as the patch lifecycle does — and
to make rollback cheaper than any patch's: detach.

### 0.1 The organising image: the scratch pad

The design's framing is Casey's, and it predates the design —
it is how the ExoJ lineage has understood itself from the
start, stated by him on 2026-11-07 as the compilation path
was being directed:

> "We've always thought of the exo-J as the scratch pad — a
> scratch pad for knowing what to do internally once you've
> got it figured out on the outside on the scratch paper.
> Once you've shown your work enough times, you find your
> QED and no longer need to show your work."

The mapping onto this document's machinery is exact:

- **Scratch paper = the external frame and its ledger.**
  Slow, messy, reversible, everything shown. The frame works
  the problem in the open, at runtime, where every step can
  be seen, challenged, and erased. Scratch paper is not
  waste awaiting the real work; it is where the knowing
  happens.
- **Showing your work = the receipts and the verification.**
  A behaviour becomes eligible to graduate only by being
  shown — every instance receipted, every claim verified
  against evidence the behaviour did not produce. Work that
  cannot be shown cannot be compiled, however often it
  happens to succeed.
- **QED = the sealed compiled artefact.** The proof stands
  on its own: the behaviour runs at weight speed, inside the
  model, with no derivation re-performed and no frame in
  attendance. Finding the QED is the moment the scratch work
  for that behaviour is *finished*, not merely paused.
- **The one refinement this design adds: the scratch paper
  is kept.** A mathematician may throw the scratch paper
  away; a programme may not. The kept ledger is the audit
  trail if the proof is ever challenged (the alumni monitor
  of §3.3 reads it), and it is the place the behaviour
  *returns to* when the world changes under the compiled
  form — re-opened, re-derived against new evidence,
  re-compiled if it re-earns it. Discarding the scratch
  paper at QED would reproduce, in a new costume, the
  failure this programme keeps meeting: a standing claim
  whose evidence no longer exists anywhere.

And the image carries its own boundary, in the same terms:
**some problems never reach QED.** A behaviour that depends
on the world at decision time has no closed form to find —
its "proof" would have to be re-derived at every moment,
which is to say it lives on scratch paper permanently.
That is not a failure of the compilation path; it is the
path correctly declining work it cannot do. §2 states the
boundary as a test.

---

## 1. The pattern, named, with its prior art stated first

### 1.1 Prior art — this is expert iteration, and we say so

The loop *search improves behaviour → behaviour becomes
training data → the improved artefact re-enters the loop* is
**expert iteration** (Anthony et al., 2017), and its canonical
ancestor is AlphaGo: a Monte Carlo tree search — an external,
expensive, per-move frame — produced play stronger than the
policy network's; that play became the corpus that trained a
stronger policy; the stronger policy made the search stronger.
AlphaGo Zero closed the loop and removed the human corpus.
STaR applies the same shape to language-model reasoning:
generate rationales with the model plus hints, keep the ones
that reach verified answers, fine-tune on them, repeat.

Our own programme already operates the pattern one substrate
up, in text space. **Voyager's skill crystallisation** — an
agent writes a skill to solve a problem, the skill is stored,
verified skills become the library the agent retrieves from —
is frame behaviour compiled into reusable form. The league's
commons pond *is* this: citizens' verified solutions become
pond entries, and the pond's confirmation-and-decay machinery
(COMMONS v2: a transfer counts only on the receiver's
citation; unretrieved entries decay) is the text-tier
graduation-and-alumni apparatus, already running. This design
is the pond's pattern applied one substrate down, to weights —
which is precisely the rolling programme's recurring move
(plans as deltas, weight deltas as drafts, now behaviours as
candidates for compilation).

Stating the ancestry is not modesty; it is calibration.
Expert iteration's known failure modes are inherited with
it: the student converges to the teacher's ceiling unless the
frame keeps improving; self-generated corpora narrow toward
what the frame already rewards; and the whole scheme leans on
the verifier — AlphaGo's frame had a perfect one (the game
rules), STaR's had answer-checking, and **ours does not**,
which is why §3 gates graduation on the sealed-audit tier
rather than on the gate probes the frame worked against.

### 1.2 What is genuinely ours in the composition

Three elements of the composition are this programme's, and
the claim of novelty is confined to them:

1. **The receipts are simultaneously the corpus and the
   adoption evidence.** In expert iteration, the search's
   traces are training data and are then discarded; the case
   for adopting the student is a fresh evaluation. Here, the
   frame's ledger already records every behaviour instance
   with its inputs, conditions, patch-ids in force,
   verification fields uncollapsed, and outcome — because the
   ledger exists for governance (WSP-SYNTHESIS §1.3: the
   ledger is the composition's real product). Distillation
   reads the same record the adoption decision reads. A
   behaviour's corpus and its dossier are one artefact, so a
   graduation claim can be audited against exactly the data
   the modifier was trained on — no reconstruction, no gap
   between "what it learned from" and "what we were shown."
2. **The modifier form factor: sealed, attachable, detachable
   — rollback by construction.** A LoRA-class modifier is not
   a new base artefact; it is an overlay with a parent hash,
   applied or removed at load time. The patch lifecycle's
   hardest property — rollback bit-for-bit — is, for a
   modifier, a property of the file format rather than a
   procedure: detach, and the base is bit-identical to what
   it was before adoption, provably, without a restore step
   that could itself fail. Graduation therefore produces the
   most reversible persistent artefact this programme has
   ever adopted.
3. **Graduation is gated by the sealed-audit tier** — the
   third tier of the verifier budget (DESIGN-EXTERNAL-
   WEIGHT-LOOP, Addendum A.1): probes that decide nothing
   during the frame's operation, touched only on a fixed
   schedule to measure the gate set's drift. Compilation is
   where that tier earns its existence. A frame behaviour is
   certified against gate probes it was selected under; a
   *graduate* must be certified against audit probes it has
   never influenced, because compilation freezes whatever the
   selection produced. **Verifier capture, compiled, is this
   design's central hazard** (§3.2): adaptive overfitting that
   in the loop is a slow drift becomes, in a modifier, a
   permanent fixture — and the alumni monitor of §3.3 exists
   because a frozen artefact cannot be argued with, only
   watched.

Nothing else is claimed. The training is ordinary
fine-tuning; the modifier format is Hu et al.'s; the loop is
expert iteration's. The composition's novelty is the same
modest trio the weighting loop claimed: cadence, governance,
externality — now extended by one more: **the frame knows
when to stop being the frame for a behaviour, and can prove
the behaviour survived the transition.**

---

## 2. What can and cannot graduate

### 2.1 The sorting property: state-independence

A frame behaviour is a function of two arguments: the model's
input, and **live external state** — the ledger, the world,
the citizens' positions, the calendar, the probe results of
the last hour. Compilation into weights can only preserve the
first argument. A modifier sees what the model sees, at the
moment the model sees it, and nothing else — no ledger read,
no world query, no wall clock beyond what the input carries.

Hence the rule:

> A behaviour is **graduable** iff it is (approximately) a
> function of the model's inputs alone. A behaviour that
> reads live external state at decision time is
> **frame-resident forever** — not because compilation is
> weak, but because the state's content is not in the weights'
> reach, and any modifier trained on its receipts would learn
> to *imitate the behaviour's outputs on yesterday's states*,
> which is a different and worse behaviour.

"Approximately" is load-bearing and priced in §2.3: some
behaviours depend on state so slowly (a seasonal prior, a
house style) that compiling a dated snapshot and re-compiling
on a schedule is honest engineering. The test below decides
which side of the line a behaviour sits on; the schedule
decides how stale a compiled snapshot may grow before the
alumni monitor objects. In §0.1's terms: a state-dependent
behaviour is a problem whose working must be re-shown at
every use — it never reaches QED, and it is not meant to.

### 2.2 The test: state ablation on the receipts

The corpus makes the test cheap, because the receipts carry
the state the frame actually read. **Replay the behaviour's
decision window with the frame's live inputs replaced:**
first by the logged state with timestamps shuffled across
windows (right distribution, wrong moment), then by state
frozen at the window's start (stale by construction). Score
the behaviour's value — the same metric its receipts carry —
under live, shuffled, and frozen state.

- Value statistically unchanged under shuffle and freeze →
  the behaviour was never reading the moment; it is a
  function of the input. **Graduable.**
- Value collapses under shuffle but survives freeze (or the
  reverse pattern, read carefully) → the behaviour reads
  state at some timescale; the pattern of collapse names
  the timescale, and the behaviour is a candidate for
  *scheduled* compilation at that timescale, or none.
- Value collapses under both → the behaviour is the frame's
  live judgement. **It stays in the frame.** Compiling it
  would be training a model to guess what the frame would
  have said — the precise shape of the pond-anchor failure,
  one substrate down: confident continuation from a premise
  nobody re-checked.

The test runs on receipts before any training is priced.
It is the compilation path's version of the discrimination
rule: no behaviour is trusted to be state-independent until
it has demonstrated state-independence on its own recorded
inputs.

### 2.3 The two classes, populated

**Graduable (input-functions):**

- **Dial-keeping.** The soft-joint and scale-space settings
  the patch programme installs (Phase 15: the signal-chain
  dial, 46.7% → 84.2% held-out, spine untouched) are, once
  their values are known, pure functions of the forward pass.
  Compilation here competes with authored patching itself —
  §5-E1's arms make that comparison explicit rather than
  assuming either winner.
- **Readout use.** Where a representation separates a class
  and the behaviour is "report what the representation
  already knows," the readout is an input-function by
  construction; it is §2.1-of-the-parent-design's most
  proven lane.
- **Format and completion discipline.** Delivering a finished,
  well-formed answer; holding a schema; terminating instead
  of deliberating forever. The input determines the
  obligation entirely. (Dory's measured disease — correct
  answers dying inside unterminated reasoning — is this
  class's type specimen, and the frame-side delivery
  contract that treats it at runtime is E1's teacher.)
- **Allocation heuristics over observable features.** A
  governor policy that maps *features present in or
  computable from the request itself* — length, class,
  measured surprise at intake — to a loop count is an
  input-function and can graduate into the serving shape
  (as a modifier on a router-adjacent model, or as compiled
  policy). The instant the heuristic reads *ledger history
  or world state* to decide, it crosses the line and stays.

**Frame-resident (state-functions), permanently:**

- **Anything that reads the world at decision time:** the
  digest's current truth, a citizen's present position, the
  pond's current contents, whether a patch is in force.
- **Anything that reads the ledger:** surprise computed
  against accumulated receipts, price history, the audit
  schedule itself. A compiled "surprise detector" trained on
  receipts would detect yesterday's surprises.
- **The verifier, in every form.** Struck explicitly in §2.4.
- **Procedure and facts** — the parent design's fence
  (DESIGN-EXTERNAL-WEIGHT-LOOP §2.2) is inherited unchanged:
  compilation does not widen the write surface. A behaviour
  that is unclaimable as a patch is unclaimable as a
  graduate; the LoRA form factor changes the reversibility
  of an artefact, not the scope of what may be written.

### 2.4 Struck from this design

- ~~Compile the citizens' planning into their brain, so
  deliberation becomes reflex~~ — **struck**: procedure
  measures zero under authored patching (Phase 15), and a
  trained modifier is not a loophole in that measurement.
  Citizens keep learning in plan space and memory, where the
  evidence says learning happens.
- ~~Compile the verifier into the model and switch the frame
  off~~ — **struck**: the audit asymmetry is the safety case.
  A graduate whose judge lives inside it has no external
  examiner; the alumni office (§3.3) must remain external or
  it is a reunion, not a monitor.
- ~~Auto-graduation: a behaviour that clears its stability
  window promotes itself~~ — **struck**: adoption of a
  persistent weight artefact is Casey's gate (§0). The
  pipeline may assemble the entire decision packet
  autonomously; it may not sign it.
- ~~Compile the frame's world-model — the digest, the
  expectations, the current map~~ — **struck by §2.1
  itself**: these are state-functions by definition. What
  graduates is how to *read*, never what is *currently
  true*.

### 2.5 The silently-uncompilable class

*This section is the Orin ZCode seat's adversarial
contribution, adopted. It sharpens §2.2: the ablation test
is necessary, and it is not sufficient.*

§2.2 ablates the state the receipts record. The dangerous
class hides one level deeper: **behaviour conditional on
frame-side state that is correlated with the resident
model's inputs but not derivable from them.** The frame
acts on ledger history, cross-episode statistics, a judge's
deliberation, and the existence of an un-executed
counterfactual — none of which exists in the model's
activation stream at inference time. Distillation then
trains a function from resident-visible inputs to reproduce
the outputs of a composed system whose other component has
been amputated. On-distribution, the correlation between
frame state and input carries the behaviour — the input is
a working proxy for the state — and ablating the recorded
state barely moves measured value, because the proxy was
doing the work all along. The LoRA learns the proxy. Sealed
probes, drawn from the same episode distribution, confirm
the proxy. The failure is deferred to exactly the moment
that made the behaviour worth having: **the world breaks
the correlation** — drift, regime change, a new population
of inputs — and the compiled behaviour fires wrongly, or
not at all, with its exam results still on file. Hence the
seat's correction to §3.1, adopted there: **sealed ≠
shifted.** Sealing protects a probe set against training
contamination; it does nothing against correlation break.
Graduation requires a shifted slice as well as a sealed
one.

Two adjacent classes, named so they are recognised on
sight:

- **Stateful control behaviour.** Much of what a governor
  does is integral or derivative in character — damp,
  wait, accumulate evidence across operations before
  acting. A LoRA is a stateless map. Compiling a controller
  into one yields a proportional-only approximation of a
  PID loop: adequate near equilibrium, wrong exactly
  during drift, which is when control behaviour earns its
  keep.
- **Abstention-rate behaviour.** Frame interventions are
  usually *rates*, not rules — veto a small fraction of
  cases under a specific uncertainty, where the value lives
  in the operating characteristic, not the argmax.
  Distillation on imbalanced receipts collapses rates to
  modes: the graduate learns "never veto," posts *better*
  accuracy, and has lost the calibration that was the
  entire point. Accuracy rises while the behaviour
  vanishes — the most silent failure available. The
  ledger's own structure compounds it: receipts record
  *applied* deltas, not the rejected counterfactual tree,
  so the corpus over-represents the frame's confidence and
  under-represents its restraint (§3.1 stage 3's
  declined-instance floor is the partial counterweight,
  and only partial).

**Pre-run detection** — run before any training is priced;
replay is pure compute and the ledger makes all three
cheap:

1. **Knockout replay.** For each receipted intervention,
   replay with the frame-side state zeroed or permuted,
   everything model-side held fixed. The fraction of
   decision variance explained by frame-only state is a
   direct estimate of the non-compilable mass — including
   mass that §2.2's freeze/shuffle cannot see, because
   zeroing removes the proxy's referent rather than
   scrambling it.
2. **The prober ceiling.** Train a small model — a natural
   liquid job, §4 — on resident-visible state alone to
   predict the frame's decision across held-out receipts.
   Its held-out accuracy *is* the compilability ceiling:
   the prober and the LoRA are being asked for the same
   function, and if the cheap version cannot reach it, the
   expensive one is memorising, not learning. The seat's
   pre-registered gate, adopted as a candidacy requirement
   in §3.1: **prober held-out decision accuracy below ~95%
   → the family is not compile-eligible** — the missing
   mass concentrates at the decision boundary, which is
   where the value is.
3. **Calibration audit.** For rate-class behaviours, check
   that the corpus can even *express* the rate — enough
   intervention events per context family to teach an
   operating characteristic rather than a mode. If it
   cannot, do not train; the run would distil the mode and
   report it as success.

---

---

## 3. The promotion pipeline

Five stages, each a ledger event, each priced. The pipeline
is deliberately the patch lifecycle's shape — candidacy for
proposal, exam for verification, adoption at the human gate —
because that shape is already measured, and because a
behaviour that graduates should carry a dossier in the same
format as a patch that was adopted, so the two histories can
be read side by side.

### 3.1 The stages

1. **Accumulation.** The frame produces the behaviour at
   runtime, at frame cadence, and every instance is receipted
   in the ExoJ manner: inputs, the state the frame read,
   conditions, patch-ids in force, the behaviour's output,
   and the outcome graded against evidence. Nothing about
   this stage is new — it is the weighting loop operating as
   designed. Compilation adds only a standing question over
   the accumulating record: *has this behaviour stopped
   being a judgement and become a function?*
2. **Candidacy.** A behaviour becomes a candidate when two
   declared conditions hold: its value has been demonstrated
   consistently across a **declared stability window** — a
   count of independent windows (days, sessions, world
   regimes) fixed in advance, with failures inside the
   windows visible in the record rather than averaged away —
   and it passes the **state-ablation test** of §2.2 on its
   own receipts. Candidacy is a receipt like any other: it
   names the behaviour, the windows, the ablation numbers.
   A behaviour that fails ablation is not rejected; it is
   classified frame-resident, which is a permanent and
   respectable classification (§2.3). The candidacy record
   also carries §2.5's pre-run detectors: the knockout
   replay's non-compilable mass estimate, and the prober
   ceiling — which must clear the declared gate (~95%
   held-out decision predictability from resident-visible
   state) or the behaviour is classified frame-resident at
   this stage, at probe cost rather than training cost.
3. **Corpus assembly.** The distillation corpus is built
   from the receipts of the candidacy windows: input →
   frame-produced behaviour pairs. **The failures are in the
   corpus, by design and at a declared ratio.** A corpus of
   only successes teaches the wins and hides the boundaries —
   the student learns what the frame did when things went
   well and nothing about where the behaviour stops applying,
   which is exactly where a compiled artefact, running
   unsupervised, will spend its worst moments. Three failure
   classes are included: *corrected pairs* (the base's raw
   output beside the frame's correction — the highest-value
   examples in the corpus, because they mark the delta the
   behaviour actually is); *declined instances* (inputs the
   frame flagged, refused, or escalated — the behaviour's
   boundary, taught as boundary); and *frame errors* (the
   instances the frame itself got wrong, labelled as such,
   so the student does not inherit them as ground truth).
   The declared floor: failure-class examples constitute no
   less than their natural rate in the candidacy windows,
   and in no case are they down-sampled below one in five
   examples where the class exists — a corpus that
   under-represents failure below its observed rate has
   survivorship baked in before training starts. Near-
   duplicate successes are capped per cluster: a ledger is
   repetitive, and ten thousand copies of the same easy win
   teach the mode, not the behaviour.
4. **Training and the graduation exam.** A LoRA is trained
   on the corpus at a rank declared in advance — small, and
   held fixed across arms in any comparative experiment,
   because the low-rank hypothesis is part of what is being
   tested: a dial-class behaviour should live in a small
   modifier, and a behaviour that needs a large rank to
   compile was misclassified at §2. Compute, priced honestly
   at our scales [estimate]: at 0.6B–4B residents on
   Thor-class hardware, a corpus of a few thousand examples
   trains in tens of minutes (0.6B) to single-digit GPU-hours
   (4B) — cheap enough to re-run on schedule. The 30B league
   brain is priced out of casual compile cycles on both
   training and exam replay; compilation, like the parent
   design's loop, is a small-resident instrument first, and
   that demotion is pre-accepted here too. The **graduation
   exam** has four parts, all pre-registered: the *sealed-
   audit set* (probes the frame never saw and the corpus
   never touched — the decisive measure); a *shifted slice*
   (probes drawn from outside the candidacy windows'
   distribution — sealing protects against contamination,
   not against correlation break, §2.5); the *gate set*
   (the probes the frame worked against — reported so the
   gate/audit gap, §3.2, is measured, not wondered about);
   *regression slices* covering the resident's other duties,
   task-held-out rather than generic (Phase 15's warning:
   capability-shaped forgetting is invisible to generic
   probes); and an *off-target KL* term — next-token
   divergence from base on a fixed broad corpus, the
   collateral instrument for damage nobody thought to test
   for (Addendum A.3's discipline, inherited).
5. **Adoption and retirement.** Adoption is Casey's (§0):
   the decision packet is the sealed artefact (hash, parent
   hash, corpus hash), the candidacy record, the exam fields
   uncollapsed, training and exam costs, and the one-line
   statement of which §2.3 class the behaviour belongs to.
   On adoption, two things happen in the same ledger event:
   the modifier enters force, and **the frame retires the
   behaviour** — it stops producing it at runtime and keeps
   only the alumni monitor (§3.3). Rollback, if it is ever
   needed, is detach: the base returns bit-for-bit, and the
   behaviour returns to the frame, which still has its
   scratch paper.

### 3.2 The central hazard: verifier capture, compiled

The frame's behaviour was *selected* — by governance, by
canary, by survival — under the gate probes. Its receipts
therefore over-represent what the gate probes reward, in the
way Addendum A.1 describes: the verifier is a consumable, and
a long-running frame has spent some of it. Training on those
receipts inherits the selection twice: once in which
behaviours the frame converged to, once in which instances
the corpus keeps. In the loop, this drift is slow and in
principle correctable — tomorrow's audit can catch it and
the frame can change. **Compiled, it is permanent**: the
modifier cannot be argued with, re-audited into changing, or
surprised into invalidating itself. Whatever the frame
overfit, the graduate *is*.

The pipeline's countermeasures are aimed at exactly this:
graduation is decided on the sealed-audit tier, which the
frame's selection never touched (A.1); the gate/audit gap is
a reported exam field, so a graduate whose gate score
flatters its audit score is *seen* being exactly that; the
corpus carries the frame's errors labelled, so selection's
blind spots are at least present in the training record; and
the graduate is re-audited on the audit tier's fixed schedule
for as long as it is in force — an audit failure reopens the
frame for that behaviour (detach, return to scratch paper,
re-derive). Compilation is not the end of verification. It
is the point where verification changes from *deciding* to
*watching* — which is why the monitor is a pipeline stage
and not an operational afterthought.

### 3.3 The alumni office: the frame's retirement plan

On adoption the frame keeps three things, and only three:

- **The receipts of the compiled behaviour.** The serving
  path already receipts its outputs; the modifier's
  patch-id rides them (parent design §3.2), so the
  graduate's live behaviour stays attributable and priced.
- **A checker, not the mechanism.** The frame's cheapest
  discriminating instrument for the behaviour — the delivery
  contract's *detector* without its corrector, the
  expectation without the intervention — samples the
  graduate's outputs at a declared audit rate. The office is
  deliberately a skeleton of the school: it can recognise
  the behaviour going wrong; it cannot reproduce the
  behaviour, and is not staffed to.
- **The scratch paper.** The candidacy corpus and windows,
  kept intact — the re-entry point if the behaviour must be
  re-derived. (§0.1: the paper is kept precisely for this.)

**Divergence reopens the school.** When the checker's
readings diverge from the graduate's exam distribution
beyond a declared threshold — drift in the world, drift in
the traffic, slow decay of a compiled snapshot of slow state
(§2.1) — the behaviour reopens: modifier detached or left in
force under a reopened frame, per the harm class, and the
pipeline re-enters at accumulation with new receipts.
Graduation, in this design, is a status a behaviour holds
while the world holds still enough to deserve it.

### 3.4 The independence problem — the adversarial case, answered

*The strongest argument against this entire design, from
the Orin ZCode seat's adversarial take, stated at full
strength before it is answered — because a design that
cannot state its best counterargument has not heard it.*

The frame's value was never only its behaviours. It was
that the frame is an **independent measurement instrument**:
different substrate, different data path, different failure
modes, and a price tag that forced deliberation. Compilation
corrodes that independence in the very act of succeeding,
in four compounding ways:

1. **The monitor's lineage.** The alumni checker judges the
   graduate's divergence from receipted behaviour — but the
   graduate was *trained on those receipts*. Conformance
   on-corpus is guaranteed by construction; the monitor's
   effective test reduces to novel episodes, where the only
   ground truth is the frame itself. Worse: reference and
   artefact now share a training lineage, and a judge
   correlated with the judged is blind precisely to errors
   common to both. Distillation *maximises* corpus
   agreement — so **the blind spot grows monotonically with
   compilation success.**
2. **The ledger flips role.** Before compilation, receipts
   are adoption evidence supporting a reversible action.
   After it, the same receipts become the argument against
   ever retracting the artefact: every future proposal to
   roll back a compiled behaviour must outvote its own
   proof-of-work, now weeks deep and entangled with
   everything the graduate has since done.
3. **Downstream contamination is not recalled by detach.**
   Rollback-freedom was a property of the frame. A graduate
   that has run for weeks has written into downstream state
   — citizens' memories, pond entries, later receipts
   attesting to a hybrid causal system whose decomposition
   nobody can state. Detaching the modifier restores the
   weights bit-for-bit (§1.2) and recalls none of that.
4. **Verification coverage collapses by the frequency
   factor.** The frame's behaviours were economical
   *because* they were rare and expensive — verified for
   one-in-a-thousand contexts. Compiled, the behaviour
   fires everywhere it pattern-matches, at weight speed.
   The same verification, spread over a thousandfold more
   applications, is a thousandfold thinner per act. A
   governor that governs constantly and was checked
   occasionally is not the instrument that was verified.

The seat's honest restatement of §0 follows, and is
adopted as a correction to this design's framing: the
claim is not *"the behaviour runs with no frame in the
loop."* It is **"the frame moves from before the action to
after the anomaly."** A real saving — smaller than §0's
framing implies, and worth taking only for behaviour
families that pass §2.5's gates with headroom.

**The counterweights** — design answers, normative, each
aimed at a numbered clause above:

- **(→1) Lineage independence of the monitor, as a build
  rule.** The alumni checker is trained and derived *only*
  from residuals — live behaviour minus receipted behaviour
  on new episodes — and from probe lineages the graduate's
  corpus never touched. It is never trained on the LoRA's
  own corpus. §3.3's "checker, not the mechanism" is
  amended accordingly: the checker must not merely be
  *smaller* than the school; it must be *unrelated* to the
  student. A monitor that shares the graduate's training
  set is not a monitor; it is a second copy of the examined
  answer.
- **(→1) Fresh-paper reconciliation.** The kept scratch
  paper (§0.1) is the *method*, not the evidence. On a
  declared schedule, the frame re-derives the graduated
  behaviour from **new** windows — new evidence, probes
  regenerated by a generator that shares no lineage with
  the original corpus — and reconciles the re-derivation
  against the graduate. Divergence beyond threshold
  reopens the behaviour (§3.3). A reconciliation run
  against the original receipts is the lineage grading
  itself and does not count.
- **(→2) Pre-registered retraction criteria.** The adoption
  packet (§3.1 stage 5) states, in advance and in numbers,
  the audit and divergence readings that will trigger
  detach — decided before the receipts accumulate their
  rhetorical weight. Retraction, when it comes, is
  executed against those numbers, not re-argued from the
  ledger. The proof-of-work may not vote.
- **(→3) Downstream-exposure declaration.** The adoption
  packet enumerates the downstream state the graduate's
  outputs may enter — which memories, which pond, which
  other artefacts read them — so the limits of recall are
  known *before* they are needed. Contamination that cannot
  be undone is named in the packet, priced into the
  adoption decision, and never discovered afterwards as a
  surprise. Behaviour classes whose downstream exposure is
  unbounded do not graduate.
- **(→4) Audit rate priced per application, not per
  clock.** Because coverage collapses with frequency, the
  alumni sampling rate is set against how often the
  graduate *fires*, not against wall time: a behaviour
  that compiles its way from one-in-a-thousand contexts to
  always-on is audited at the always-on rate, and that cost
  is charged to the compilation's savings in the packet.
  The frequency factor is paid, not ignored.

**The residue, stated plainly.** These counterweights
reduce correlated blindness; they do not eliminate it. A
monitor of independent lineage still examines a world the
graduate has been shaping, and no reconciliation schedule
fully retires the fact that the programme's evidence about
a graduated behaviour is thinner per act than its evidence
about a framed one. The blind spot's growth with success is
therefore carried as a **permanent audit tax** (§7): the
more a behaviour graduates, the more independent evidence
must be bought to keep watching it. Any behaviour class
whose correlated errors are intolerable at any tax does not
graduate, whatever its exam scores say.

---

## 4. Liquid synergy: several liquid models, assigned roles

Casey's direction names the composition explicitly: the
compilation path working *in synergy with several liquid
models*. The liquid residents (CfC-class continuous-time
networks, LFM2-class small liquid/dense hybrids, and Dory's
recurrent block as the exotic member) are not decoration on
the frame; each takes a role the other components cannot
take, and the last subsection states where they take none.

- **The CfC liquid shadow — the frame's expectation organ,
  and the candidacy instrument.** As designed in
  WSP-SYNTHESIS §0, the shadow holds an expectation over
  wall-time gaps and prices surprise *before* compute is
  spent. In the compilation path it gains the decisive job:
  **surprise is the frame's own measure of "not yet figured
  out."** A behaviour the shadow prices as expected, window
  after window, is exhibiting exactly the stability §3.1's
  candidacy stage must demonstrate — the shadow's surprise
  trace over the behaviour's windows is candidacy evidence
  that costs nothing extra to collect. In §0.1's terms: the
  QED is in sight when the liquid shadow stops being
  surprised by the working.
- **LFM2-class small residents — the first compile targets.**
  Cheap LoRA cycles, fast exam replay, and the Phase 15/16
  batteries already live at this scale (LFM2-1.2B beside
  Qwen3-0.6B). Compilation is an iteration-speed game at
  this stage of the programme, and small liquid residents
  are where the iterations are affordable — E3 (§6) is
  theirs.
- **A liquid model as the frame's continuous component.**
  Parts of the frame cannot run at call cadence: the
  expectation between ticks, the monitor between sessions,
  any judgement that must be maintained across wall-clock
  gaps rather than recomputed per request. A continuous-time
  resident holds those — it is the one component of the
  frame that is *awake between events*, and the alumni
  office's checker (§3.3) is its natural duty: always on,
  cheap, watching compiled behaviour the way the shadow
  watches live behaviour.
- **Dory's shared recurrent block — the exotic compile
  surface.** A modifier on the shared block is not traversed
  once per generation but once *per pass*: its effect
  interacts with loop count, so a LoRA validated at k=2 may
  strengthen, cancel, or distort at k=1 and k=4. This is
  WSP-SYNTHESIS Q5's question (do dials authored at k=2 hold
  at other loop counts) inherited by trained modifiers, with
  one sharpening: a *trained* modifier's cross-k behaviour is
  less legible than an authored dial's, so a Dory-targeted
  graduate's exam must run at **every loop count the
  allocator may select** — or adoption pins k for that
  artefact, declared in the packet. A compile that silently
  assumes its training loop count is a poisoned base at
  variable k.
- **Where liquid models do not help.** The audit tier: a
  liquid sense is a sense — advisor, never the gate — and
  putting the graduation exam's probes through one changes
  its seat not at all. The §2 boundary: liquidity is a
  property of a model's time, not of a behaviour's
  state-dependence, and no liquid component moves a
  state-function across the graduation line. The 30B brain's
  economics: there is no liquid resident at that scale in
  our stack, and compile-cycle pricing there is unchanged
  by anything in this section. And the fence: procedure and
  facts are as ungraduable into a liquid resident as into a
  dense one — the scope limit is substrate-independent, and
  any sentence implying the liquid synergy widens it should
  be corrected on sight.

### Placement discipline — the adversarial amendment

*The Orin ZCode seat's placement rule, adopted with one
tension recorded.*

**Liquid models render no verdicts.** Their seat is
frame-side in every role this design assigns — expectation,
triage, continuous monitoring — and in no role do they gate,
grade, or adopt. The inherited rule (advisor, never gate) is
hereby sharpened from a property of one lineage into a
placement law for the substrate: liquidity earns a component
the always-on jobs; it does not earn it authority.

**The good compilation is the triage.** The seat's
counter-proposal, adopted as a first-class candidate family:
compile the frame's *routing* — a liquid predictor of "does
this decision need the expensive external call?" — rather
than verdict-adjacent behaviour. Triage is a §2.3-graduable
input-function; its errors are priced and recoverable (a
false alarm costs one frame call, a miss defers one
decision, neither manufactures a judgement); and authority
— apply, verify, roll back — stays outside. In the seat's
closing words, which this design adopts as its placement
motto: **"Compile the triage; keep the verdicts expensive,
slow, and outside."**

**The monitor trains on residuals, never on the corpus**
(§3.4, counterweight 1) — restated here because it is a
liquid placement: the always-on divergence detector is the
liquid component most tempted by the corpus, being built
from the same shop, and it is the one component that must
never touch it.

**The tension, recorded, not resolved silently.** This
placement argues against §4's compile-target role for
LFM2-class residents and against E3: if liquid models
belong entirely frame-side, a liquid resident should no
more be a *student* than a judge. The design's reading:
the seat's prohibition is aimed at liquid *judgement* —
verdicts, grading, gating — and E3's resident renders none;
it *receives* a behaviour. But the seat's deeper point
stands against E3 at full strength: liquid statefulness
makes a compiled artefact's behaviour less legible, its
cross-session interactions harder to receipt, and its
monitor's lineage harder to keep clean — and that point is
now E3's heaviest prior against itself, recorded in §6.
E3 runs, if it runs, against its own take's objection.

- ~~A liquid layer inside the resident, smoothing or
  interpolating between modifier versions~~ — **struck**
  (the seat's trap, named): a continuously blended modifier
  is a continuously drifting behaviour with no receipted
  identity — the exact object the ledger exists to prevent.

---

## 5. Harmony, formalised

The internal form — a model that reads and writes weights in
its own response — is not this frame's rival; it is a
candidate organ inside it, and the frame is what makes it
admissible: the weighting loop's author seat is precisely
where an internal editor belongs, and WSP-SYNTHESIS already
records that the seat may come on-premise (a local 27B reader
reproduced three of four weight-reading tasks on a laptop)
inside a propose-verify-deny pipeline that absorbs its
reduced reliability — because an internal editor with no
external frame is Willison's demonstration exactly: 43,506
reasoning tokens spent in one uninterruptible response, its
interpretation graded by itself, its edit irreversible in
the moment it lands, impressive and inadmissible in equal
measure; while the same editor, seated inside the frame,
becomes a fallible, receipted proposer whose every reading
must be converted into a falsifiable prediction and settled
against probes it cannot see the answers to, whose edits
arrive as sealed artefacts it cannot self-adopt, and whose
failures cost a denied proposal instead of a corrupted
resident — and the debt runs both ways, which is what makes
it a harmony rather than a hierarchy: the internal capability
is what makes the frame *cheap* (authoring and search move
on-premise, at the loop's cadence, without a frontier bill),
and the frame is what makes the internal capability *safe to
use at all* — each supplies the property the other
structurally lacks, and the compilation path is where they
meet, since what an internal author drafts as a weight delta
today, a proven frame behaviour may tomorrow make
unnecessary by arriving already compiled.

---

## 6. First experiments, cheapest first

Each experiment names what it needs that exists, what it does
not, and the result that kills it. Ordering is by kill-power
per unit cost. All three inherit the parent design's
discipline: matched budgets across arms, scoring on the
sealed-audit set, off-target KL reported, priors statable in
advance.

### E1 — Compile completion discipline on Qwen3-0.6B

**The behaviour.** Completion discipline: the model delivers
a finished, well-formed answer and terminates, instead of
trailing off, truncating, or deliberating past its own
conclusion. Chosen because it is the most receipted
behaviour class in the Phase 15/16 record on this exact
artefact family, it is §2.3-graduable by construction (the
obligation is entirely in the input), and — decisively — an
existence proof already stands: Phase 15's authored patch on
Qwen3-0.6B took held-out behaviour from 80.5 to 85.0 with
forgetting item-identical, i.e. *this behaviour demonstrably
lives in this model's weights when installed by authoring.*
E1 asks the compilation question in its sharpest form: **can
training on receipts find what authoring found?**

**The arms** (one fixed prompt battery, sealed-audit +
held-out splits sealed before any arm runs):

- **Base.** Qwen3-0.6B BF16 (the checkpoint landing tonight
  for WSP Q1's behavioural arm), untouched.
- **Frame-at-runtime.** The same base, wrapped in the frame's
  delivery contract: an external checker detects
  non-delivery (truncation, non-termination, malformed
  completion) and re-prompts or steers under a declared
  policy; every intervention receipted. This arm *is* the
  teacher — its receipts are the corpus — and its runtime
  cost (added calls, added tokens per delivered item) is the
  price compilation must undercut.
- **Compiled.** A LoRA at rank declared in advance (r = 8)
  trained on the frame arm's receipts per §3.1 stage 3 —
  corrected pairs, declined instances, frame errors labelled
  — and then run with the frame **off**.

**Pre-gate (the seat's gate 1, adopted from §2.5).** Before
the training run is spent, the family's receipts pass the
knockout replay and the prober ceiling: frame decisions
must be predictable from resident-visible state alone at
≥95% held-out, or completion discipline *on this artefact*
is not compile-eligible and E1 stops at the probe — the
kill costs a probe run, not a distillation run. E1 also
carries the seat's **trigger parity** as a scored metric,
not a kill criterion of its own: the frame arm's
interventions are triggers (re-prompt on non-delivery), and
the compiled arm is scored on whether the behaviour fires
at the frame's historical rate in the frame's historical
contexts — correctness-given-trigger alone is exactly the
number the silent failure leaves standing.

**Declared bars.** The compiled arm must retain **≥80% of
the frame arm's gain** (delivered-correct over base) on the
**sealed-audit** split; its runtime cost per delivered item
must be **≤10% of the frame arm's added cost**; off-target
KL from base must stay within the frame arm's own noise
band on the generic corpus.

**Needs that exists:** the BF16 checkpoint (landing tonight,
hash-gated); the Phase 15 battery discipline and the
authored-patch reference numbers; the Thor's training stack
(torch in ~/ml/.venv) at a scale where a rank-8 LoRA over a
few thousand examples is a sub-hour job [estimate].
**Needs that does not exist:** the delivery contract as a
receipted corpus generator (a small wrapper, built for this
experiment, and afterwards the frame's standing completion
organ); the sealed-audit set for this behaviour (generated
and sealed before the frame arm runs — an audit set created
after seeing frame receipts is not an audit set).

**Kill criteria.** (i) Sealed-audit retention <80% of the
frame gain → compilation is a lossy photocopy for this
behaviour class, and the path closes for it. (ii) The gain
holds on gate probes but collapses on the sealed audit →
*compiled verifier capture, observed* — the design's central
hazard made empirical; the path closes until corpus and exam
design change, and the result is published either way.
(iii) The retention bar is reachable only at rank ≫ 8 → the
behaviour was not dial-class on this substrate; §2's
classification, not the training, is what failed, and it is
revised before any retry. (iv) Shifted-slice trigger
recall falls below 70% of on-distribution recall while
every sealed probe passes → the silently-uncompilable
failure (§2.5), observed in the programme's flagship
family: the behaviour compiled was the correlation, not
the discipline, and the class closes until the corpus can
be drawn from more than one regime.

### E2 — The alumni monitor, under drift

**What it is.** E1's graduate (this experiment is void if E1
dies — the dependency is stated, not smoothed) is run under
a **shifted battery**: a prompt family and format regime
outside its candidacy windows, introduced without
announcement to the monitor. The alumni checker (§3.3)
samples the graduate's outputs at its declared audit rate.
Measured: **detection lag** (divergent outputs emitted
before the alarm fires), **false-alarm rate** on matched
unshifted traffic, and **recovery** — whether reopening the
frame restores the behaviour (the full cycle run once, end
to end: graduate → drift → alarm → scratch paper → verdict).

**Kill criteria.** Detection lag exceeds the behaviour
class's declared harm window (for completion discipline: a
declared count of silently undelivered items — a monitor
that notices after the harm is a historian); **or**
false alarms fire at a rate that would train an operator to
ignore them — alarm fatigue is a kill, stated plainly,
because a muted monitor is worse than none: it converts a
known blindness into a believed surveillance.

### E3 — The liquid-target compile (LFM2-class)

**What it is.** E1's shape repeated on an LFM2-class liquid
resident (LFM2-1.2B, the other Phase 15/16 battery model),
once E1's result is known. The additional question is
substrate: a liquid resident carries recurrent state across
a session, so the compiled modifier interacts with *carried
state* as well as per-call inputs — §2.2's ablation test is
therefore run with **session state as one of the ablated
arguments** (windows replayed with state reset, shuffled,
and carried). The synergy claim of §4 stands or shrinks
here. E3 also carries the adversarial take's standing
objection (§4, placement discipline) as its heaviest prior
against itself: a liquid resident's statefulness makes a
compiled artefact's behaviour less legible and its monitor's
lineage harder to keep clean — the experiment runs against
its own take's argument, and knows it.

**Needs that does not exist (stated plainly):** the LFM2
BF16 artefact on the Thor — its model directory is presently
empty (a wall recorded by the WSP Q1 crew); E3 waits on an
artefact route of the same class as E1's download, and no
part of E3 is scheduled before that route lands.

**Kill criterion.** The retention bar met on the dense
target (E1) is missed on the liquid target at matched rank
and budget → compilation is substrate-sensitive; the path
narrows to dense residents, §4's liquid roles shrink to the
frame side (shadow, continuous monitor), and the narrowing
is recorded in this document's successor rather than argued
away.

---

## 7. Where this design is weakest

- **The corpus is exactly as honest as the ledger.** The
  composition's known single point of failure (WSP-SYNTHESIS
  §1.3) is inherited with interest: a lossy or gameable
  receipt stream no longer merely misinforms a decision — it
  gets *trained in*, and the resulting artefact then produces
  behaviour that generates more receipts in its own image.
  Compilation raises the stakes of receipt discipline more
  than any prior stage of the programme.
- **Graduation can entrench the mediocre.** Expert
  iteration's ceiling problem in operational dress: a
  compiled behaviour stops paying frame costs, and therefore
  stops generating the pressure and the receipts that would
  have improved it. The frame's competence for that behaviour
  freezes at its first graduating class. The alumni monitor
  watches for *failure*; nothing in the pipeline watches for
  *foregone improvement*, and this design does not pretend
  otherwise.
- **Every battery we own is small.** Graduation exams inherit
  the power problem of the whole programme: a modifier can
  pass a small sealed audit by luck, and the audit set is
  itself a consumable (A.1) that repeated graduations spend.
  Early graduations should be read as provisional at exactly
  the confidence the exam sizes support.
- **The state-ablation test has a blind spot.** It detects
  dependence on the state the receipts *record*. A behaviour
  that reads state the frame failed to log — an unlogged
  sense, a side channel in the harness — passes ablation and
  compiles into a student that imitates a reader whose book
  it cannot see. Receipt completeness is, once again, the
  load-bearing assumption.
- **Success compounds the blind spot.** (§3.4) The better a
  graduate matches its corpus, the less its monitor can see
  of it. The counterweights tax this; nothing repeals it,
  and the tax is easy to quietly stop paying — which is why
  the retraction criteria are pre-registered rather than
  left to a future meeting's appetite.

---

## 8. Claims register

Load-bearing claims only. "Measured" means our instruments,
this programme.

| # | Claim | Source |
|---|---|---|
| 1 | The compilation pattern is expert iteration; canonical ancestor AlphaGo's search→policy distillation; text-tier analogue (Voyager skill crystallisation, our commons pond with confirmation + decay) already operated by this programme | Prior art; COMMONS v2 [measured, live] |
| 2 | Phase 15 authored patch on Qwen3-0.6B: held-out 80.5 → 85.0, forgetting item-identical; soft-joint dial 46.7% → 84.2% held-out, spine untouched | Phase 15 [measured] |
| 3 | Authored patching measures zero on procedure, facts, unseparated relations; the fence binds compilation unchanged | Phase 15/16 [measured] |
| 4 | The verifier is a consumable; verifier capture is the weighting loop's named failure mode; sealed-audit tier exists to measure gate drift | DESIGN-EXTERNAL-WEIGHT-LOOP Addendum A.1 |
| 5 | A LoRA modifier's rollback is detach: base returns bit-for-bit by construction of the form factor | Artefact property [by construction] |
| 6 | Compilation compute at 0.6B–4B on Thor-class hardware: tens of minutes to single-digit GPU-hours per LoRA at corpus scales of a few thousand | [estimate] — priced by E1's receipts when it runs |
| 7 | A modifier on Dory's shared recurrent block is traversed once per pass; cross-k transfer of recurrent-block dials is open (WSP Q5) and inherited by trained modifiers | WSP-SYNTHESIS §3/Q5 |
| 8 | Internal weight-editing models are absorbable as the author seat at reduced reliability inside propose-verify-deny; local 27B reader reproduced 3 of 4 weight-reading tasks | WSP-SYNTHESIS §3.6 settlement [measured: RESEARCH-SWEEP §2.3] |
| 9 | The citizens' pond implements confirmation-on-citation and 48 h retrieval decay, live 2026-11-07 | COMMONS v2 completion report [measured] |
| 10 | Qwen3-0.6B BF16 artefact: download dispatched 2026-11-07 (hash-gated); LFM2 model directory on the Thor is empty | WSP Q1 night report [measured] |
| 11 | A silently-uncompilable class exists: behaviour conditional on frame state correlated with, not derivable from, resident-visible inputs; sealed probes from the same distribution confirm the memorised correlation; stateful-control and abstention-rate behaviours are adjacent classes | [take: Orin ZCode seat, adversarial] — adopted as §2.5; tested by §2.5's pre-run detectors |
| 12 | Post-compilation, monitor and artefact share a training lineage; the monitor's blind spot grows monotonically with compilation success; the ledger flips from adoption evidence to anti-retraction argument; detach does not recall downstream contamination | [take: Orin ZCode seat, adversarial] — answered, not refuted, in §3.4; residue carried as a permanent audit tax |
| 13 | A prober trained on resident-visible state has a held-out ceiling equal to the compilability ceiling; sealed ≠ shifted — sealing protects against contamination, not correlation break | [take: Orin ZCode seat] — adopted as the §3.1 pre-gate and the §3.1 shifted-slice exam field |

---

## 9. What would have to be true

The design stands on the following. Each is stated so that
its failure is recognisable when it arrives.

1. **At least one frame behaviour passes state ablation with
   margin.** If every behaviour the frame produces turns out
   to read live state, the compilation path has no inputs
   and this document is a design for an empty pipeline —
   §2's test exists to find out before any training is
   priced.
2. **Receipts are a sufficient corpus.** Behaviour cloning
   from (input → frame behaviour, failures included) pairs
   reproduces the frame's gain at the declared retention
   bar. This is E1's premise, and it is an empirical claim
   about our ledger, not about distillation in general.
3. **A genuinely untouched sealed-audit set can be
   maintained.** Graduation's meaning depends on probe
   provenance discipline holding under our actual tooling —
   that no frame run, corpus build, or helpful seat ever
   reads the audit set into a context the selection can
   feel. If provenance cannot be enforced, every graduation
   is a gate-probe result wearing audit clothing.
4. **The alumni monitor detects drift inside the harm
   window, at an audit rate the budget affords** (E2's
   premise). A graduate whose decay is invisible until it
   is expensive is worse than the frame behaviour it
   replaced, which at least paid its costs in the open.
5. **Dial-class behaviours fit small modifiers.** If the
   behaviours that pass §2 routinely need high-rank or
   full fine-tuning to retain their gains, compilation is
   ordinary fine-tuning with extra ceremony, and its
   economics — cheap, frequent, scheduled re-compilation —
   collapse.
6. **Re-compilation stays cheaper than defending a stale
   graduate.** The pipeline's answer to drift is return to
   scratch paper and re-derive; if a compile cycle costs
   more than the behaviour's remaining value, behaviours
   will be defended past their evidence, and the alumni
   office becomes a tenure committee.
7. **The frame keeps learning after its first graduations.**
   Retirement must free cadence for new behaviours, not cap
   the frame's total competence at its first graduating
   class (§7). This is a claim about how the programme runs
   the pipeline, listed here because the design cannot
   enforce it — only the ledger can show it, afterwards.

---

*End of design. Companion documents: DESIGN-EXTERNAL-WEIGHT-LOOP
(the loop whose behaviours graduate), DESIGN-ROLLING-PRIMITIVES
(the same draft-verify-commit pattern in plan and percept
space), WSP-SYNTHESIS (the composed system; Q1's precision
verdict gates the surfaces any modifier must survive, and Q5
gates the recurrent-block case).*
