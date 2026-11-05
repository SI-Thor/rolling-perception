# STUDY — CUA-Master (arXiv:2611.03126): recursive improvement loops for computer-use agents, and what its flywheel does and does not teach a rolling perception platform

Lane CUA STUDY, 2026-11-05. Study only: nothing was run,
downloaded, or trained. Facts in §1–§2 come from the paper
itself — the arXiv abstract page and the HTML full text of
arXiv:2611.03126v1 (Yu, Li, Zhao, Chen, Wang, Dong, Peng, Xu,
Wu, Tuo, Yang, Feng, Wu, Zhang, Wu, Shao, Wang, Yue — MMLab /
CUHK / THU / HKUST(GZ) / Explore Academy, JD), submitted
2026-11-02, read in full (method, experiments, analyses)
2026-11-05. Project page, code repository, and a 27B model
release are linked from the paper. **Every performance number
in §2 is the authors' own**, measured under their benchmark
protocol on their infrastructure; no independent replication
exists as of this writing. §3 is **our synthesis** — the
programme's reading, not the paper's claims — and is labelled
as such throughout. Anything not confirmable from the paper
text is marked **UNVERIFIED** (in practice: nothing load-bearing
below rests on sources outside the paper).

## Deficits first

- **The headline model is a training-flywheel artefact, not a
  deployable technique at our scale.** CUA-Master-27B was
  produced on 16 nodes × 8 NVIDIA H200-141GB, rolling out
  trajectories across ">100 different CUA environments" with
  ">2,000 concurrently running VMs". The framework's unit of
  improvement is a full SFT/RL iteration over ~115K tasks. A
  single AGX Thor runs none of this. What transfers is the
  *loop topology* and its instrumentation, not the loop's
  throughput (§4).
- **The flywheel's judge is a stronger model, and the paper
  says the loop degrades without one.** One annotator model
  𝒜 plays every quality role — suitability scorer, task
  generator, action rechecker, action annotator, trajectory
  verifier, primitive extractor, failure detector. The
  annotator ablation (§2.4) is the paper's most important
  negative result: using the policy itself as its own
  annotator ("self-policy strategy") "can bring about some
  improvements, but its gains are relatively limited." The
  recursive engine runs on an external, stronger judge — the
  same structural fact this house already holds about
  jev-semantic (advisor, never the gate) and about cold-agent
  playtests (a hired hand validates; a cold user falsifies).
- **"Continuous gains across recursive iterations" is shown
  for three SFT iterations plus one RL stage.** The iteration
  curve (their Figure 8 / §3.3.3) rises across the reported
  rounds, with OSWorld Verified and WeaveBench up "over 25
  points" across the full run; it is not evidence about
  iteration 10 or 30. The paper's own framing concedes the
  saturation shape: SFT saturates on simpler tasks first,
  which is *why* the final stage switches to RL.
- **The task universe is benchmark-shaped.** Tasks are
  tuples 𝒯 = (ℐ, ℰ, 𝒱) — instruction, environment, and a
  task-specific verifier that decides success. The whole
  apparatus (primitive composition, verifier composition,
  outcome-based RL reward) leans on the existence of 𝒱.
  A continuous physical stream has no per-task verifier; what
  it has is a corrections ledger and judged precision over
  windows (our trust loop). The analogy in §3(a) is drawn at
  that seam, not over it.
- **Seeding quality is asserted through pipeline stages, not
  audited independently.** Seed trajectories are reconstructed
  from videos by the same annotator family that later verifies
  rollouts; the paper notes reconstructed trajectories "may
  contain annotation noise and do not necessarily correspond
  to real executions". The defence inside the paper is
  structural (dual-path agreement + recheck, §1.3), not an
  external ground-truth audit.

## 1. The mechanism, as published

### 1.1 The nested double loop

CUA-Master is a *nested double-loop recursive improvement
framework* for computer-use agents (CUAs) — agents that
execute natural-language instructions through GUI actions
(`computer.click`, `computer.scroll`, …), CLI actions
(`shell.exec`), and tool calls in one unified atomic action
space, with observations grounded in screenshots for GUI steps
and in standardised shell output (stdout, stderr, status) for
CLI steps. Coordinates are resolution-independent, normalised
to [0, 1000].

The two loops:

- **Outer loop — the world-data-model flywheel (system
  level).** Open world → data construction → model training
  → weakness analysis → guided re-exploration of the open
  world. The coupling the paper insists on is the feedback
  edge conventional pipelines lack: "an in-house assessment
  of [the] model, including domain- and application-level
  hierarchical failure cases and rollout success rates
  analyses" identifies "the gaps and limitations of the
  current policy, guiding the next iteration of adaptive data
  scaling". Data construction is *steered by measured
  weakness*, not merely enlarged.
- **Inner loop — the data flywheel (data level).** Two
  "complementary driving forces": **open-world seeding**
  (§1.3) injects real-world diversity and operational
  knowledge from outside the model's own distribution, and
  **autocatalytic propagation** (§1.4) abstracts those seeds
  into reusable primitives and composes them into new
  verifiable tasks at controlled complexity, with resilient
  trajectory collection (§1.5) harvesting the rollouts. The
  cycle is self-reinforcing by design: seeding is the
  foundation, propagation "systematically amplifies its
  coverage, complexity, and scale".

### 1.2 Training inside the loop

Each outer iteration is a complete model optimisation:

- **SFT iterations.** Iteration *i* fine-tunes on the
  cumulative union of all verified seed and synthetic
  trajectories collected so far (𝒳^seed ∪ 𝒳^syn over rounds
  1..*i*). To avoid "potential optimization drift", **each
  SFT iteration is trained starting from the same base
  checkpoint** (Qwen-3.5-27B), with the expanded dataset —
  the loop accumulates *data*, not successive weight states.
  Reported per-iteration task counts added: 63K, 38K, 14K
  (≈115K tasks total at the final SFT iteration). AdamW,
  peak lr 5×10⁻⁶, cosine schedule, batch 128.
- **Final RL stage.** Once SFT gains saturate, one RL stage
  (a modified GRPO-style algorithm for CUAs, following
  ScaleCUA) runs on ~12K high-quality synthetic tasks in real
  executable environments, 8 sampled trajectories per task,
  with outcome rewards derived directly from the composed
  task verifiers — no manual reward annotation. lr 1×10⁻⁶,
  batch 64 (up to 512 trajectories per batch).

### 1.3 Open-world seeding

The seed supply is mined from instructional video (YouTube,
TikTok, Bilibili) organised by a hierarchical application
taxonomy — 8 main categories, 36 subdomains, 650+
applications — crossed with operation-oriented keywords
("tutorial", "how to", "guide") into compositional queries.
Candidates are deduplicated and filtered (duration, recency,
taxonomy-consistent attribution; a noise filter suppresses
promotional/entertainment/incidental content). Surviving
audio is transcribed with Whisper-Large-v3 (Faster-Whisper);
the annotator 𝒜 scores each video 0–5 for CUA suitability —
legible interaction, reconstructible step-by-step trajectory
— and predicts CUA presence, trajectory availability, and
visual clarity.

**Seed task mining** is formulated as multimodal temporal
episode discovery: from metadata, timestamped transcript, and
sampled overview frames, 𝒜 segments a video into independent
task episodes (start/end timestamps), retaining only
"observable computer-operation state-continuous intervals"
and excluding introductions, advertisements, talking-head
commentary, and slide-only content. One video yields multiple
independently executable seed tasks, each with a goal inferred
jointly from visual context, narration, application identity,
and the demonstrated state transition.

**Visual-semantic dual-path trajectory reconstruction** then
rebuilds an executable trajectory for each mined episode from
two independent trigger streams:

- *Semantic path:* the transcript is decomposed into atomic
  clauses at discourse connectives and temporal markers
  ("then", "next", "after that"); clauses carrying action
  expressions ("click", "press", "scroll", "drag") become
  semantic triggers, a set of candidate action times.
- *Visual path:* FFmpeg frame-level appearance-change scores
  above a threshold become visual triggers — candidate times
  of meaningful interface transition (menu opening, dialog,
  navigation, content update).

Triggers from the two paths that fall within a temporal
window *T* of each other form a **boundary lattice** of
candidate actions. 𝒜 then acts as *action rechecker* over
paired pre/post-action frames and local transcript context —
rejecting non-operational changes and adding, removing,
splitting, or merging candidates — then as *action annotator*
(emitting coordinates, typed content, keys), and finally as
*trajectory verifier* (deduplicating actions, splitting at
substantial temporal/semantic discontinuities, retaining
qualified trajectories). The design intent is explicit:
neither narration nor pixels are trusted alone; an action is
believed where the two independent paths agree, and a
stronger model adjudicates the agreement.

### 1.4 Autocatalytic propagation: primitives and composition

Seeds alone cover little of the combinatorial space, so each
(seed task, trajectory) pair is **primitivized** by 𝒜 into a
sequence of reusable, application-level ability primitives.
A primitive is a five-tuple

  p = (u, a, 𝒫, ℰ, 𝒱)

— the application *u*, the reusable ability *a*, execution
preconditions 𝒫, environment requirements ℰ, and a verifier
specification 𝒱. Primitives are aggregated into an
application-indexed **primitive library ℬ**; semantically
equivalent primitives are canonicalised and deduplicated,
while variants differing in preconditions, environment
requirements, or verification logic are retained. The
representation "abstracts away task-specific entities while
preserving the operational dependencies necessary for
reliable execution", so one primitive can be instantiated
with different files, content, interface states, and
application configurations.

**Task synthesis is constrained primitive composition**, not
instruction rewriting. Given a complexity budget *K* (number
of composed primitives) and an application set of size *N*,
complexity is controlled along exactly those two axes: *N* = 1
gives single-application tasks, *N* > 1 cross-application
tasks. Composition first checks pairwise compatibility of
preconditions and environment requirements — conflicting
primitives cannot compose — and the synthetic task's
precondition is the conjunction of the composed primitives'
preconditions. 𝒜 instantiates the coherent instruction, the
composed environment specification, and the composed
task-level verifier from the primitive-level verifier specs.
High-quality synthetic tasks are selected into training sets
per stage. Because difficulty is a construction parameter
(the *K*/*N* pair), the same machinery yields difficulty-
graded task collections — which is what makes the RL stage's
curriculum and the §2.3 difficulty analysis possible.

### 1.5 Feedback-guided snapshot-rollback retry

Trajectory collection is where the inner loop meets real
environments, and where naive pipelines bleed yield: "a
failure is often caused by a localized misoperation while
most of the preceding trajectory remains valid". Discarding
a failed rollout and restarting wastes the valid prefix;
keeping failed or bloated trajectories poisons supervision.

The mechanism:

1. Roll out in an environment materialised from the VM pool
   (versioned image catalog; immutable base image plus a
   disposable writable overlay; standardised lifecycle hooks
   for acquisition, readiness, reset, cleanup; a global
   resource-aware scheduler bounding concurrency by VM
   slots).
2. On verification failure **or detected inefficiency**,
   𝒜 as *detector* jointly examines the verifier residuals,
   the collected trajectory, and the environment, and
   outputs (ŝ, ℱ): an estimate ŝ of the **earliest
   state-divergence step**, and execution-grounded feedback
   ℱ describing the observed failure or inefficiency —
   deliberately *without* exposing a privileged action
   solution, "alleviating potential distribution mismatch".
3. The environment is restored to the **latest valid
   snapshot preceding ŝ**. Snapshots are incremental, taken
   at stable boundaries, each storing VM state plus a
   lightweight **state signature** — active applications,
   window layout, relevant files, controller metadata —
   rather than replaying history from the initial snapshot.
4. The policy keeps the stable prefix, discards the suffix,
   and resumes **conditioned on ℱ as hints**.
5. Repeat until the verifier passes or a retry budget is
   exhausted. **Only the successful and most efficient
   branch is retained** as the final trajectory; failed or
   inefficient suffixes are excluded from supervision.

Retries thereby form "a lightweight branching search that
reuses successful prefixes". Rollout infrastructure is
backend-agnostic and profile-driven across Linux, Windows,
and macOS; base images are programmatically perturbed
(applications removed, desktop layouts reorganised) to expand
environment coverage "at low marginal cost".

## 2. Reported results (all author-reported)

### 2.1 Headline benchmarks

CUA-Master-27B (initialised from Qwen-3.5-27B), against
generalist and specialist baselines re-evaluated under one
protocol (same environments, action interfaces, criteria).
Scores are per-task averages except Agents' Last Exam, which
is a full-pass rate:

| Benchmark | Mode | CUA-Master-27B | Selected context (authors' table) |
|---|---|---|---|
| OSWorld Verified | GUI | **80.2** | Claude-Opus-5 86.3, GPT-5.6-Sol 83.6, Qwen-3.8-27B 81.2, base Qwen-3.5-27B 54.6 |
| OSWorld 2.0 | GUI | **36.9** | Claude-Opus-5 64.2, GPT-5.6-Sol 59.0, Qwen-3.8-27B 36.5 |
| WeaveBench | GUI+CLI | **43.9** | Claude-Opus-5 55.7, GPT-5.6-Sol 50.6, GPT-5.6-Luna 44.0 |
| Agents' Last Exam | GUI+CLI | **25.0** | Claude-Opus-5 28.3, GPT-5.6-Sol 26.3, Kimi-K3 25.0 |

Per the authors: +2.6 / +12.9 / +25.6 / +11.8 over the
strongest similarly-sized specialist (UI-Mate-27B) across the
four benchmarks; competitive with the 397B Qwen-CUA on
GUI-only and ahead of it on the hybrid benchmarks. Cross-
platform: 56.2 WindowsAgentArena, 43.0 MacOSWorld, 59.9
MacAgentBench. Efficiency is a first-class reported axis:
80.2 on OSWorld Verified at a mean of 19.0 steps / 247K
tokens / **8 minutes** per task; the authors claim 24–36%
runtime reductions versus score-matched frontier models on
the harder benchmarks.

### 2.2 The hybrid action space is doing heavy lifting

An ablation the synthesis in §3 should not skip: on
WeaveBench, hybrid GUI+CLI scores 43.9 against **6.6 GUI-only
and 11.5 CLI-only**; on Agents' Last Exam, hybrid lifts
5.9 → 25.0 over GUI-only with 26.7% fewer steps; on OSWorld
2.0, steps drop 43.8% at competitive score. The unified
interface — choosing per state whether to click or to shell —
is, on the authors' own numbers, worth more than most of the
flywheel's benchmark margin over same-size specialists.

### 2.3 Snapshot-rollback yield (rollout success, %)

Rollout success rate by composed difficulty (*K* primitives /
*N* applications), CUA-Master's resilient collection versus a
same-retry-budget baseline that re-rolls out from the start:

| K / N | Restart baseline | Snapshot-rollback |
|---|---|---|
| 5 / 1 | 74.0 | 95.4 |
| 10 / 1 | 53.0 | 89.1 |
| 20 / 1 | 31.5 | 83.7 |
| 10 / 3 | 29.2 | 62.3 |
| 20 / 3 | 19.3 | 56.9 |
| 40 / 3 | 14.6 | 49.8 |
| 20 / 5 | 1.9 | 32.8 |
| 40 / 5 | 0.4 | 24.4 |
| 50 / 8 | 0.0 | 18.7 |

The gap *widens* with difficulty — at the difficulty the
authors equate with Agents' Last Exam (K=40, N=3) the yield
is ~3.4× the restart baseline, and at K=50/N=8 the baseline
collects nothing at all. Task-distribution coverage (t-SNE
over task embeddings) is reported to span the distributions
of six existing CUA datasets and extend into sparse regions.

### 2.4 Iteration and annotator analyses

- **Across iterations**, performance rises on all four
  benchmarks over the SFT iterations (OSWorld Verified and
  WeaveBench up over 25 points across the run); when SFT
  saturates on simpler tasks, the RL stage adds ~15 points
  on OSWorld 2.0 and Agents' Last Exam.
- **Annotator strength**: stronger annotator models yield
  consistently greater gains throughout the process. The
  self-policy variant — each iteration's policy annotating
  the next iteration's data — improves somewhat but with
  "relatively limited" gains. This is the paper's internal
  evidence for its opening claim (next section).

### 2.5 The closed-world warning, in the paper's own terms

The framework is motivated by an explicit rejection of
closed-loop self-improvement: existing recursive approaches
"often rely on self-generated experiences, limiting ability
expansion and yielding diminishing returns"; closed-world
cycles are "bounded by existing capabilities, potentially
reinforcing distributional biases, and yielding diminishing
marginal returns" — with model collapse on recursively
generated data (Shumailov et al., *Nature* 2024) among the
cited grounds. The flywheel's answer is architectural, not
rhetorical: an **external knowledge inlet** (open-world
seeding from human instructional video) and an **external
judge whose strength is not the policy's own** (the annotator
ablation). Both are load-bearing; remove either and, on the
paper's own evidence, the loop still turns but buys less
each time it turns.

## 3. Connections to this programme (OUR synthesis — not the paper's claims)

Everything in this section is the rolling-perception lane's
reading. The paper is about training computer-use agents; it
says nothing about perception platforms, edge boxes, or our
fleet. The connections are drawn because the *loop shapes*
rhyme, and where they rhyme they are worth stealing precisely.

### 3(a) Three scales of loop, and the missing outer one

This programme now handles loops at three distinct scales:

1. **Intra-model loops (milliseconds–seconds).** Dory's
   shared recurrent block applied 1–4 times per token
   (STUDY-DORY): depth as a dial inside one forward pass,
   with our charter's question being whether the dial can be
   driven per frame by a settle signal instead of fixed at
   launch.
2. **Stream-time loops (seconds–days).** The rolling
   cascade itself: perceive → decide → direct → refine →
   publish over SPSC rings, budgets in embed-seconds, the
   gate deciding *where the next unit of compute goes* based
   on what the stream just did. Plus, inside it, the trust
   loop: corrections.jsonl taps fold into a per-stream
   trailing judged precision φ; φ crossing 0.9 with
   hysteresis demotes a stream, and feed faults are routed
   away from model faults (TRUST-LOOP-PAPER-TEST).
3. **Extra-model loops (days–weeks).** CUA-Master's
   flywheel: the model's measured weaknesses steer the next
   round of data construction; the system improves *between*
   deployments, not within them.

The flywheel is the scale this programme does not yet run as
a designed loop, and it maps onto assets we already hold.
The trust loop's ledger *is* a weakness record at stream
granularity: per-stream judged precision, correction taps,
near-miss frames, frozen-span receipts. What a CUA-Master-
style outer loop means here is concrete: instead of the
ledger only *demoting* (a throttle), its weakness profile —
which streams demote, which tiles chronically near-miss,
which event classes collect corrections — becomes the
steering signal for the next round of *instrument
construction*: which fixtures get built, which calibrations
get re-run, which candidate patches (Jacquard W-series) get
authored and proposed. That is the difference between a
platform that defends its precision and a platform that
spends its improvement budget where its own record says it
is weakest. Two discipline notes, both already house rules
and both confirmed by the paper's shape: the loop must be
fed from outside (§3(b)), and its products must arrive as
governed proposals, never silent mutations (§3(c)).

One asymmetry to keep visible: CUA-Master's outer loop
retrains from the *same base checkpoint* each iteration,
accumulating data rather than weight lineage, specifically
to avoid optimization drift. The governed-patch programme
accumulates the opposite way — sealed, reversible deltas
over a frozen spine, each individually adoptable and
rollback-able. These are two answers to the same fear
(uncontrolled drift of the thing being improved), tuned to
different substrates: full retraining is affordable at
H200-farm scale and gives a clean lineage of datasets; at
edge scale the patch ledger is the affordable lineage.

### 3(b) Their warning is our rule, stated from the other side

The paper's founding claim — self-generated experience
yields diminishing returns and reinforces distributional
bias — is the training-side statement of two rules this
fleet already runs on the evaluation side:

- **Shadow validation uses real traffic only.** Dressing
  battery traffic as live is falsification; a shadow
  candidate earns promotion against the stream as it
  actually is. CUA-Master's version: the flywheel's diet
  starts from *authentic human workflows* mined from the
  open world, and its synthetic expansion is anchored to
  those seeds and executed in real environments against real
  verifiers. Synthesis is the amplifier; reality is the
  source.
- **Cold agents falsify; hired hands validate.** The
  playtesting doctrine (a zero-shot agent with its own
  expertise tells you no; a seat briefed to help drifts
  toward yes) is the annotator ablation wearing work
  clothes: the paper measured that a policy annotating its
  own next round buys "relatively limited" gains, and that
  annotator *strength* — an outside judge — is what the
  loop's gains scale with. A flywheel whose judge is itself
  is a mirror, not a flywheel.

If this programme ever builds the §3(a) outer loop, these
become its two hard constraints: weakness data must
originate in real streams and real corrections (not in
self-generated rehearsals of them), and the assessment that
steers construction must be made by something that is not
the thing being improved — a stronger model, a cold agent,
or a human tap on the console. The console's "that mattered"
/ "not-a-change" taps are, in this light, not UI garnish:
they are the platform's external-judge inlet, and the
two-sided tap design (without the "mattered" tap, φ is
downward-biased by construction) is exactly the kind of
asymmetry the flywheel literature keeps rediscovering.

### 3(c) Snapshot-rollback retry is our patch discipline, applied to trajectories

The snapshot-rollback mechanism and this house's weight-
patch governance are the same invention in two substrates:

| | CUA-Master trajectory collection | Governed weight patches (Jacquard W-series) |
|---|---|---|
| Unit of work | a rollout in a live environment | a patch against a frozen spine |
| Failure handling | locate earliest divergence step ŝ; restore latest valid snapshot before it | patch is sealed and reversible; rollback is bit-for-bit |
| What is kept | the valid prefix; only the successful, most efficient branch enters supervision | only adopted patches enter the serving model; denied ones stay in the log |
| What is discarded | failed/inefficient suffixes, explicitly excluded to avoid "state-inconsistent supervision" | unadopted proposals, excluded from the spine |
| Diagnosis | verifier residuals + trajectory + environment → feedback hints, no privileged solution leaked | battery + held-out curves → adoption verdict, no claim beyond the measured battery |
| Checkpointing | incremental snapshots at stable boundaries, with lightweight state signatures | sealed patch artefacts with the governance log as signature |

The transfer worth taking is the *detector's* job shape.
Our patch lifecycle verifies after the fact (battery, then
adopt/deny). The flywheel's detector does something subtler
mid-flight: from verifier residuals it estimates *where* a
trajectory first diverged, and the retry resumes from the
last known-good state with the diagnosis as a hint rather
than an answer. The analogue for a live perception stream
writes itself — when a stream's verdicts start collecting
corrections, the interesting question is not "demote or not"
but "at which change of scene, light, or instrument did this
stream's behaviour diverge, and what is the last calibration
under which it was judged precise?" That is a
divergence-localisation receipt, and it would make the trust
loop's demotions explainable instead of merely thresholded.
It is also, read in the other direction, a validation of the
fleet's seat discipline: a delegated build that goes wrong
is rolled back to the last verified state and resumed with a
diagnosis, not restarted from a blank brief — the seats
already work this way because the alternative wastes the
valid prefix of their work exactly as restart-from-scratch
rollouts waste trajectories.

### 3(d) Autocatalytic primitives vs the compounding doctrine

Casey's compounding doctrine: every asset success must
generalise into reusable machinery before the fleet
multiplies instances, and the evidence standard is the
marginal cost of subject N+1 against subject N. The
primitive library ℬ is that doctrine, formalised by someone
else, with two refinements worth importing:

1. **A primitive carries its own verification.** The
   five-tuple (u, a, 𝒫, ℰ, 𝒱) refuses to separate an ability
   from its preconditions, its environment requirements, and
   its verifier. Our archetypes (Foundry: seed + params ARE
   the asset, geometry is a cache) carry the recipe but not
   always the *test*. A primitive in CUA-Master's sense is
   not reusable until the conditions under which it is known
   to work — and the check that would tell you — travel with
   it. That is the difference between a library and a pile of
   parts that once worked.
2. **Complexity is a budget with named axes.** Composition
   cost is (K, N): how many primitives, across how many
   applications. Marginal cost of N+1 is therefore not a
   vibe but a coordinate — you can point at the cell in the
   rollout table where yield collapses (K=50, N=8: 18.7%
   even *with* rollback) and say what the next subject will
   cost before attempting it. Our fixtures and archetype
   families would benefit from the same explicitness: name
   the composition axes of a harbour-watch scene or a
   Foundry build, and the "does it generalise" question
   becomes a table instead of an argument.

The autocatalytic property itself — primitives extracted
from seeds make new tasks whose solutions become new
primitives — is the flywheel's compounding engine, and it
is also where the doctrine's guard-rail bites hardest: in
this house, a generalised asset is only counted when a
*second subject* was actually produced from it at the quoted
marginal cost. A primitive library that grows by extraction
but is never composed is inventory, not machinery; the
paper's library earns its keep because composition and
rollout are in the same loop.

### 3(e) Direct applicability: improving our own computer-use seats

This is the least speculative connection, because the
paper's subject is literally our workforce. The fleet's
ZCode and MCode seats are computer-use/coding operators
working real tasks on the Orin, ProArt, and Thor surfaces
under briefs; their failure modes are already observed and
named in this lane (empty-brief stalls, headless modes that
cannot write, auth-dead seats, launch-path traps — each
recorded in the fleet's lessons). A weakness-guided outer
loop for the seats, in CUA-Master's shape but at bench
scale, is buildable from parts that exist:

- **Weakness record.** Seat task outcomes already produce
  receipts (verified pushes, referee passes, named flakes).
  Aggregated by failure class — brief-misreading, tool-path
  traps, environment/auth state, genuine capability gaps —
  that is the "hierarchical failure cases" assessment the
  flywheel steers by, at application granularity replaced by
  surface/seat granularity.
- **Seed mining from real workflows.** The seeding move —
  mine authentic workflows rather than inventing exercises —
  translates to: derive seat exercises from the fleet's own
  completed real work (a push that worked, a build that
  verified), reconstructed as re-runnable tasks with the
  original receipts as verifier. The seats then practise on
  the distribution they actually serve.
- **Composition with difficulty axes.** Exercises compose
  from primitives of fleet work (clone-and-verify,
  brief-to-build, referee-a-diff) with explicit (K, N) —
  steps composed, surfaces crossed — so a seat's measured
  frontier is a table, and the next brief can be aimed at
  the cell just past it, which is what "adaptive data
  scaling guided by weaknesses" means at this scale.
- **Snapshot-rollback as seat hygiene.** Trial work happens
  in disposable overlays (worktrees, scratch clones) with
  the last-verified state as the snapshot; a failed attempt
  resumes from there with a diagnosis instead of
  contaminating the tree — already the de facto discipline
  (§3(c)); the paper gives it a name and a yield table.
- **The external-judge constraint binds here too.** Seat
  self-assessment cannot steer the loop (the annotator
  ablation, §2.4); the steering signal must be referee
  verdicts, cold playtests, and Casey's taps — the same
  judges the fleet already trusts, now with a loop drawn
  around them.

What this buys, stated modestly: the seats' improvement
stops being anecdotal ("GLM handled that brief well") and
becomes a measured frontier per seat per failure class,
with exercises aimed at the frontier instead of at whatever
task happened to arrive. What it does not buy: new
capability in the underlying models — the flywheel improves
the *operator system's* yield and aim, exactly as the
paper's framework improves a fixed base model's realised
performance (their base Qwen-3.5-27B scores 54.6 where the
flywheel's product scores 80.2 — the weights changed there,
but the *system* is what the paper is actually selling).

## 4. What does NOT transfer, and the named risks

**Scale and substrate mismatches.**

- **Datacentre flywheel vs one edge box.** The paper's loop
  assumes 128 H200s, thousands of concurrent VMs, and full
  SFT/RL iterations as the unit of improvement. The Thor
  has none of these; its improvement units are calibration,
  fixtures, governed patches, and briefs. Any import that
  smuggles in "just retrain it" as a step is not an import,
  it is a fantasy. The loop *topology* (weakness → guided
  construction → verified adoption) is scale-free; every
  mechanism implementing it here must be re-derived at edge
  scale.
- **Verifiable benchmark tasks vs a continuous physical
  stream.** CUA tasks come with 𝒱; a harbour does not. Our
  nearest equivalents — judged precision over trailing
  windows, correction taps, fixture batteries with known
  ground truth — are statistical and delayed where 𝒱 is
  exact and immediate. An outer loop steered by φ is
  steered by a noisier, slower signal than anything in the
  paper, and its iteration cadence and hysteresis must be
  set accordingly (the trust loop's 2-eval demote / 7-eval
  restore asymmetry is a start, not a coincidence).
- **Disposable environments vs the one real room.** Rollback
  works because VMs are restorable and overlays disposable.
  The physical scene in front of a camera cannot be rolled
  back; only the instrument's state (calibration, threshold,
  patch set) can. §3(c)'s mapping holds for instrument state
  and for seat work products; it does not hold for the
  world, and a design that forgets which side of the lens it
  is on will talk nonsense about "retrying" reality.
- **Video-mined diversity vs a fixed sensorium.** Seeding
  buys diversity because the open world of instructional
  video is vast and varied. A deployed platform watches the
  rooms it is installed in; its "open world" is smaller and
  stranger, and its weakness-guided exploration is mostly
  *temporal* (seasons, light, occupancy patterns) rather
  than taxonomic. The flywheel's steering still applies;
  its seeding economics do not.

**Named risks.**

- **Flywheel drift.** A loop that steers construction by
  measured weakness optimises for the weaknesses it can
  measure. Unmeasured failure classes get no data, get
  worse relatively, and stay unmeasured — the flywheel's
  version of the streetlight effect. The paper mitigates by
  re-deriving each SFT round from the base checkpoint and by
  the open-world inlet; our mitigations are the same shapes
  (frozen spine, external inlet, cold playtests that are
  deliberately *not* aimed by the weakness record).
- **Synthetic-task capture.** Composed tasks are verifiable
  by construction — which means the loop can get very good
  at the *composable* slice of the world while the
  incompressible remainder (the part of computer use, or of
  a harbour scene, that does not decompose into primitives
  with clean verifiers) silently exits the curriculum. The
  paper's own difficulty table is the warning label: even
  with rollback, yield at K=50/N=8 is 18.7% — the frontier
  of composition is also where the method's grip weakens.
  A perception analogue: scenes that decompose into tiles
  and gates get fixtures; scenes that don't, don't — and
  the ledger will not notice their absence unless someone
  looks at what never became a task.
- **Judge capture.** Every quality role in the pipeline is
  one annotator. If 𝒜's blind spots align with the policy's,
  the loop certifies its own biases as ground truth — the
  paper's stronger-annotator result cuts both ways: the
  loop's ceiling is the judge's discrimination, a sentence
  this house already has on file about silence and
  embedders (a verdict is only meaningful when the
  instrument has demonstrated discrimination on this run's
  actual inputs). Any outer loop built here inherits the
  obligation: the judge's discrimination must itself be
  probed, on the loop's actual material, every round.
- **Prefix worship.** Snapshot-rollback retains the
  "successful and most efficient" branch and discards the
  rest. In trajectory collection that is hygiene; imported
  carelessly into evaluation it becomes survivorship —
  keeping only the attempts that passed and losing the
  distribution of failures the weakness record needs. The
  discard rule is safe only because the *failure metadata*
  (divergence step, residuals, feedback) is retained even
  when the failed suffix is not. Keep the receipts, discard
  the trajectory — the ledger discipline this platform
  already runs.

## 5. Bottom line

The paper's artefact (a 27B CUA) is not usable here; its
loop is. Read as a design document, CUA-Master contributes
three things to this programme: a worked proof that
**weakness-guided construction beats volume** (steer by the
failure record, not by appetite); a worked proof that
**reversibility plus divergence localisation beats restart**
(snapshot-rollback's yield table is the strongest single
result in the paper, and it is our patch discipline
recognised in a foreign substrate); and a measured warning,
from inside a recursive-improvement paper, that **the loop
is only as good as its external inlet and its external
judge** — which this fleet already believed, and can now
cite. The flywheel's natural home here is not the
perception cascade (which already has its loops, at stream
scale) but the layer above it: the trust loop's ledger,
read as a weakness record, steering what the platform
builds, calibrates, and practises next — under governance,
with the receipts kept.
