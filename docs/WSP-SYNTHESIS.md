# WSP-SYNTHESIS — The composed system: looped refiner, liquid shadow, governed weight authoring, FP4 serving — on the rolling-perception cascade

*Internal design record, 2026-11-05/06. Synthesis of the weight-space
programming (WSP) thinking team: the architect take (ZCode seat, Orin,
`zcode-take.md`, 4,820 words) and the empiricist/auditor take (MCode seat,
ProArt, `mcode-take.md`), reconciled against this repo's measured ground
truth (STUDY-DORY, DORY-SMOKE-1, RESEARCH-SWEEP-2026-11-05) and the team's
shared brief, which carries the fleet's Phase 15/16 patch-programme results
as ground truth. Where a take and a measured document conflict, the measured
document wins and the conflict is recorded, not smoothed. Claim tags are
used throughout and collected in the register in §7: **[measured: DOC]** =
our own measurement in a named doc; **[brief]** = fleet prior results
carried in the team brief; **[take: architect]** / **[take: empiricist]** =
that seat's position; **[unverified]** = author- or vendor-reported,
unreplicated by us.*

## 0. The composed system in one picture

Casey's sentence under test: liquid models, Dory, and weight-space
programming, quantised into FP4, extremely effective in a rolling system on
a Thor. The synthesis verdict is that the sentence describes a real
architecture, but a narrower one than its most exciting reading — and the
narrowing is the design. Three of its four ingredients survive audit in
constrained roles; the fourth (FP4) survives as a *serving question*, not
an assumption (§1.4, §6-Q1).

```
PERCEPTION (unchanged cascade)                REFLECTION (new seat)
frames → diff gate → embedder → events ──→ text digest ──→ LOOPED REFINER
             │ embed-seconds        ▲            │              │  ▲
             ▼                      │            ▼              │  │ k per window
        sheaf/refine ── residual ───┴──→ ALLOCATOR ─────────────┘  │
             │                              ▲   loop-seconds receipt│
             ▼                              │ surprise              ▼
        CfC LIQUID SHADOW ──────────────────┘              verdict prose
        (expectation over wall time)                            │
                                                                ▼
EVERYTHING ── receipts ──→ LEDGER (append-only) ── digests ──→ WEIGHT AUTHOR
(author off-box, System Three) ── sealed patch proposals ──→ GOVERNANCE
(propose → verify on-box at deployment precision, equal budget →
adopt/deny → rollback bit-for-bit) ──→ PATCH PLANE (frozen spine +
overlay / scale dials at declared surface)
```

**Where each component sits, and the contract at each interface:**

| Interface | Producer → consumer | Payload | Unit of account |
|---|---|---|---|
| Gate → embedder | fingerprint-moved tiles only | tile images | **embed-seconds**, receipted (existing) [brief] |
| Embedder/sheaf → digest | settled events | text digest (events, claims, scores) | per-window |
| CfC → allocator | expectation state | surprise scalar (observed vs expected), silent-drift receipt | per window |
| Sheaf → allocator | refine step | residual disagreement of the window's events | per window |
| Allocator → refiner | loop allocator | k ∈ {1,2,3,4} for this window + budget admission decision | **loop-seconds** (one recurrent-block pass over the working context) [measured: STUDY-DORY §3] |
| Refiner → ledger | Dory-seat | verdict prose + receipt: k spent, KV mode, patch-ids in force, content-non-empty check | loop-seconds |
| Ledger → author | ledger digests, probe results, held-out curves | the price history of certainty: where loops burned without verdict change, where patches transferred or measured zero | governance-minutes |
| Author → governance | sealed patch proposal | declared target surface (overlay / scale-space / native), declared mechanism class (readout / completion harvest / writer-direction) | ~25 min governed path at our patch scale [brief] |
| Governance → patch plane | verified patch or denial | adopt = hot-swap at window boundary; deny = recorded negative result; rollback = bit-for-bit restore | per proposal |
| Patch plane → allocator/refiner | patched weights | every downstream verdict carries the patch-ids in force, so a price or quality change is attributable | — |

Two placements are load-bearing and not negotiable within this design:

- **The refiner is a text tier, never a perceptual tier.** Dory is
  text-only; it refines digests, event descriptions, and claims — the
  System-Two "deep end" of ARCH-AGENT-COMMUNITY §5. It never touches
  pixels [measured: STUDY-DORY §0].
- **Verify lives on the Thor at deployment precision; the author lives
  off-box.** Replay and bit-for-bit rollback are only meaningful on the
  silicon and artefact that will run the patch [take: architect, on brief
  governance]. The author is a System Three actor in the community
  architecture's sense: called on, asynchronous, expensive, receipted.

## 1. What the two takes agree on (settled, unless a queue item kills it)

1. **The author works a narrow lane.** Authored patches harvest
   format/completion/framing failures and install readouts where the
   representation already separates; they do not add capability. The
   paper's Qwen headline is a completion-pathology unblocking (576 of 579
   rescued answers had hit the token cap), and its Gemma failure is the
   same map's other half [take: empiricist, grading the paper against
   brief]. The architect designs to the same lane independently
   [take: architect §1, §5]. Any budget that prices WSP edits as
   capability additions is contradicted by the paper's own logs, the
   replication cluster, and our Phase 15/16 measurements alike
   [measured: RESEARCH-SWEEP §2.5; brief].
2. **Governance is the operating system, not a wrapper.** A patch is an
   effect: propose → verify → adopt/deny → rollback, sealed and
   replay-verified. Both takes treat the ~25-minute governed path as what
   makes weight-writing *normal operation* rather than an event
   [brief; take: architect §7; take: empiricist §Exp].
3. **The ledger is the composition's real product and its single point of
   failure.** Allocator feeds author; author feeds patch plane; patch
   plane changes what the allocator sees. If receipts are lossy or
   gameable, every other component reads fiction [take: architect §10].
   The empiricist's version of the same point: a loop budget whose
   instrument cannot demonstrate discrimination is "a word rather than a
   mechanism" [take: empiricist, dead-ends].
4. **Loops are a metered currency beside embed-seconds**, receipted per
   verdict so quality can always be divided by spend after the fact
   [measured: STUDY-DORY §3; both takes].
5. **The CfC stays at FP16/BF16 and earns its place between
   observations** — expectation over wall-time gaps, and as the
   allocator's feed-forward price-setter (surprise is available *before*
   any loop is spent; sheaf residual is not) [take: architect §4;
   take: empiricist is silent on CfC precision but its Exp 3 fixture
   choice — the soak verdict series — presumes the same seat;
   measured support for the narrow claim: RESEARCH-SWEEP §4.2].
6. **The discrimination rule binds every tier.** Nothing — sensor, settle
   signal, patch — is trusted until it has demonstrated discrimination on
   the run's actual inputs. The empiricist adds the control-theory edge:
   a settle signal must publish its **false-settle rate**, and its own
   cost comes out of the budget it allocates [take: empiricist, citing
   Snell et al. on difficulty-estimate costs].
7. **Dory is a credible substrate and a launch-fixed one.** The dial
   exists (k = 1–4, tooling-exposed) but no shipping stack exposes it per
   request; runtime allocation is a build on top, via multi-instance
   routing on stock code or a source patch [measured: STUDY-DORY §2–3].

## 2. Corrections the ground truth applies to the takes

The synthesis inherits four corrections. Two hit the architect (whose
verification fetches were queue-held during composition — its blog/card
claims are self-labelled "distilled brief — unverified," and the brief
itself carried one of the errors). One hits both. One hits the brief.

- **IFBench does not drop at 4 loops.** The brief's claim (57.4 at 4
  loops) is a misread cell; the vendor table is monotone: 74.29 → 77.94
  → 79.0 [measured: STUDY-DORY §1]. The over-looping risk is real but
  lives elsewhere: GPQA Diamond and HLE peak at 2 loops and fall at 4,
  and AA-Omniscience is flat — loops buy compute, not knowledge
  [measured: STUDY-DORY §1]. Every argument in the architect take that
  leans on the IFBench drop (§3, §6, §9 row 2) survives in weakened form
  on the GPQA/HLE shape, but the *mechanism* it proposed — quantisation
  error compounding across passes — is separately contradicted (§3.2).
- **k = 3 exists and is already measured on the Thor.** The architect
  caps allocation at {1,2,4} "because vendor numbers exist only for
  1/2/4." The tooling allows 1–4; the vendor simply never benchmarked 3
  [measured: STUDY-DORY §2]. On our box, decode at k=3 is 10.4 tok/s,
  between k=2 (13.0) and k=4 (7.6) [measured: DORY-SMOKE-1]. The
  allocator's action space is {1,2,3,4}.
- **The measured Dory problem is delivery, not depth.** Neither take
  could see DORY-SMOKE-1 (concurrent work), and it reorders their shared
  assumptions: in reasoning-on mode at a 1024-token budget, 4 of 6
  prompts reached the correct answer inside the reasoning and never
  emitted it, at *every* loop count; reasoning length is flat-to-growing
  with depth; delivered-correct was 1/6 at k=1 and 2/6 at k≥2. With
  reasoning off, 5/6 deliver correctly at every k and loops changed
  phrasing, never a verdict [measured: DORY-SMOKE-1]. Consequence for
  the whole queue: **the refiner seat's first engineering problem is
  termination discipline (reasoning-off operation, or a delivery
  contract with content-non-empty verification per response), and it
  precedes any allocation experiment.** An allocator metering a model
  that cannot stop talking is metering the wrong failure.
- **"FP4 serving" is two different claims, and only one is currently
  true.** The deployable Dory artefact today is the Q5_K_M GGUF under
  the PR-branch llama.cpp [measured: DORY-SMOKE-1]. The NVFP4 checkpoint
  is a W4A16 safetensors artefact for vLLM/TensorRT-class stacks whose
  Dory support is unmerged [measured: STUDY-DORY §4]; and weight-only
  NVFP4 is the one configuration NVIDIA itself measured as *slower than
  BF16* — only W4A4 reaches the FP4 tensor cores [measured:
  RESEARCH-SWEEP §3.1]. The architect's design assumes NVFP4 serving
  throughout; the synthesis re-scopes it: **near-term deployment
  precision is Q5_K_M; NVFP4 is a bench question (queue Q1/Q6), not a
  premise.** The empiricist's grid analysis (§3.1) stands regardless —
  it prices what happens *if and when* patches must live on the NVFP4
  grid, and its method applies to any coarse grid.

## 3. Where the takes disagree

### 3.1 Which patch geometry survives quantisation — the sharpest disagreement

- **Architect:** the design should standardise on surfaces that survive
  by construction — per-block **scale-space dials** (move the FP8 block
  scales, leave E2M1 values alone) and an **FP16 overlay plane** (dials,
  joints, readouts beside the spine). E2M1-native editing is "almost
  never right" [take: architect §6].
- **Empiricist:** the grid does not tax all edits equally — it appears to
  tax *ours*. The paper's edit is a large perturbation (direction
  component reversed and amplified ×5, α = 6); our soft-joint patches
  are small and near-norm-preserving — plausibly exactly the regime a
  ~25%-finest-step grid erases (naive requantisation of a ~3%
  perturbation leaks the edit back at 67% on FP4 tensors in the
  quantised-ablation literature). "The 4-bit constraint… appears to
  select against our current patch style and possibly for the paper's"
  [take: empiricist].
- **Settlement:** pure measurement, and it is queue Q1. Per-block
  survival cosines for both geometries (α≈1 ablation, α=6 reversal) plus
  all three surfaces, on the published edit and on our Phase 15/16
  batteries. Not decidable from either take's armchair; both seats agree
  it is computable in hours-to-a-day, which is why it gates the queue.

### 3.2 Does quantisation error compound across loops?

- **Architect:** yes, plausibly — the same quantised weights are
  re-traversed k times, so error is systematic and repeated, "a
  candidate mechanism" for non-monotone loop behaviour
  [take: architect §6].
- **Empiricist:** measured otherwise by a third party — KL divergence
  at 4 loops ÷ at 1 loop is 0.98–1.17 for everything at Q5 and below;
  error does not compound with depth. Held-out perplexity is minimised
  at 2 loops (2.284 vs 2.340 at 1, 2.291 at 4) — the loop-2 peak is a
  loss-curve fact, not a quantisation artefact [take: empiricist].
- **Settlement:** the third-party KL figure is [unverified] for our
  artefact and box. Q3 phase 0 measures per-loop-count grounded quality
  *and* a divergence proxy on house fixtures at the deployment
  artefact. If error does not compound on our box either, the
  architect's drift-detector use of settle traces loses its mechanism
  and the oscillation guard must key on verdict flips, not latent drift.

### 3.3 What allocation is actually worth: continuous metering vs the 1↔2 boundary

- **Architect:** per-window allocation over the full dial, driven by
  settle traces — the allocator is the architecture's centre
  [take: architect §3].
- **Empiricist:** the vendor's marginal returns collapse after loop 2
  (SciCode +7.64 for 1→2, +0.17 for 2→4) while cost scales with passes;
  the control problem is really "a small integer allocation on the
  one-to-two boundary, with three and four reserved for the rare
  genuinely hard item" [take: empiricist]. Our Thor numbers sharpen
  this: k=2 costs 0.66× the k=1 rate, k=4 costs 0.39×
  [measured: DORY-SMOKE-1] — and the exchange-rate literature prices one
  recurrence at r^0.46 equivalent parameters: real, sublinear
  [measured: RESEARCH-SWEEP §1.10].
- **Synthesis position (adopted):** the architect's machinery with the
  empiricist's economics. The allocator exists, receipts everything, and
  its *default policy* is conservative: k=1 unless demonstrated
  loop-marginal-value for the window's class, k=2 on surprise, k∈{3,4}
  only under a class-level receipt history. Q4 tests whether even that
  beats fixed-2 at equal spend; if it does not, we ship fixed-2 and the
  allocator retires to a receipting router.

### 3.4 Procedure: closed surface, or reopened by the writer/detector distinction?

- **Architect:** procedure/facts/unseparated relations are MAY NOT —
  write surface excludes them; lever-style writes are denied by default
  with the 11-trial null cited in the denial template
  [take: architect §5, §7].
- **Empiricist:** our map conflated two things. A *detector* direction
  is a readout — intervening moves nothing, exactly as our 11 trials
  showed. A *writer* direction is causal — the paper's Kinetix repair
  (the one result our map does not predict, independently replicated at
  1,024/1,024 with 1.70% of weights changed) found a writer and *added*
  a policy fragment. The sharpened map: "patches do not work on
  procedure we can only detect" [take: empiricist].
- **Synthesis position (adopted):** the architect's denial template
  stays for detector-derived proposals. Writer-derived proposals aimed
  at procedure are admissible **as experiments, not as normal
  operation**, gated on Q2. If Q2's writer arm ties its detector arm,
  the surface closes again permanently and the Kinetix result is filed
  as a curiosity with no programme attached [take: empiricist,
  dead-ends].

### 3.5 How novel is runtime allocation?

- **Architect (and the brief):** NVIDIA fixes depth at launch; "ours
  would not be" [take: architect §1; brief].
- **Empiricist:** half right. Serving is launch-time in both stacks —
  but Dory was *trained* with a difficulty-aware loop curriculum; its
  largest curriculum gains are at 4 loops. Allocation-by-difficulty is
  NVIDIA's idea, baked into the weights [take: empiricist, corrections].
- **Synthesis position:** our defensible novelty is exactly two things:
  allocation decided **at runtime, per request**, which no shipping
  stack exposes; and allocation on a **perception-settling axis**
  (surprise, residual, demonstrated discrimination on this run's inputs)
  rather than a task-difficulty axis. Claims beyond that are retired.

### 3.6 The author's economics: cheap governance, expensive search

- **Architect:** the governed path is ~25 minutes end-to-end, so
  trigger-driven authoring is the default; proposals are small artefacts
  shipped over any link [take: architect §5].
- **Empiricist:** the 25 minutes prices *verification*. The paper's
  results are a *search* — up to 300 sandbox runs, up to 50 forward
  passes on practice problems, max reasoning effort, ~200k output tokens
  for a single "one-shot" policy write. If our envelope cannot reproduce
  the search, "our governed path is governed only in the verification
  half" and the programme is a wrapper around someone else's inference
  budget [take: empiricist, tertiary dead-end]. The counterweight from
  the sweep: a local 27B reader reproduced 3 of 4 weight-reading tasks
  on a laptop — the author seat may come on-premise at reduced
  reliability, which a propose→verify→deny pipeline is built to absorb
  [measured: RESEARCH-SWEEP §2.3].
- **Settlement:** every queue item that invokes the author must receipt
  **search cost per accepted patch** (tokens, passes, wall time)
  alongside governance-minutes. Two accepted patches whose search cost
  exceeds their measured value end trigger-driven authoring; the author
  demotes to nightly-batch, and if it fails there too, to off.

## 4. What each take has that the other lacks

**Architect only:** the **oscillation guard with rollback to the pass-2
latent state** (converts non-monotone loop failure from a launch hazard
into a metered early-stop; synthesis: retained, but keyed per §3.2's
settlement); **scale-space dials** as a named surface (in Q1);
**two-currency verify** — a patch must hold verdicts at equal-or-lower
loop *and* embed budget, so a patch cannot silently buy quality with the
other currency (adopted into governance unconditionally — it is cheap
and closes a Goodhart channel neither the brief nor the empiricist
named); **pass-dynamics dials** (authoring the re-injection mix / per-pass
gating of the shared block — highest leverage, highest blast radius;
admissibility decided by Q5); the framing of the ledger as a **price
history of certainty** and of the whole composition as *perception as a
priced market in certainty, purchased three ways — embed more, loop
more, propose a patch — all priced, receipted, reversible through one
governance path* (adopted as this note's §0 framing).

**Empiricist only:** the **writer/detector sharpening** (§3.4 — the
single most useful thing the paper hands us); the **constrained
requantisation recipe** held in reserve (per-column over-projection by
bisection + per-block scale co-optimisation = a fixed point of the
runtime's own quantise kernel; and the warning that **the verification
probe must read the same code space the deployed kernel reads**, or we
manufacture clean-looking nulls); the fact that the released NVFP4
checkpoint is a **QAD product** (all parameters unfrozen, scales
recomputed per forward, 128 GB300 × 12 h per candidate) — there is no
cheap BF16-edit → NVFP4-checkpoint path, so patching happens **in place
on the deployed artefact** or not at all; the **false-settle ≤ 5%**
pre-registration for any settle detector; the **search-cost dead-end**
(§3.6); and the honest price of "one-shot" (~20k output tokens of policy
inside ~200k tokens of run).

## 5. The Dory taps dependency — both branches designed

The taps job (ProArt seat: patch the fork to expose per-pass hidden-state
delta norms behind a default-off flag; verify flag-off parity against
DORY-SMOKE-1; grade contraction on the fixed prompt set) is **still
running**. Its question is STUDY-DORY's D2: does ‖hₖ₊₁ − hₖ‖ contract
across passes, and does a small delta at loop 2 predict that loops 3–4
leave the output unchanged? The stock build cannot answer it — the
recurrent block is unrolled into one graph, the head runs once after the
final pass, no per-pass tensors are exposed [measured: DORY-SMOKE-1].
The programme must not stall on it; both branches are designed now.

**Branch A — the signal verifies** (deltas contract geometrically *and*
predict output stability at a demonstrated false-settle rate ≤ 5%):
- The internal settle signal becomes the allocator's primary stop rule;
  the architect's §3(b) lives as designed, with the oscillation guard
  keyed on the delta trace.
- Q4 gains its third arm (settle-allocated, hard-capped at k=4,
  budget-normalised to the fixed-2 arm).
- Per-pass receipts enter the ledger; loop-marginal-value becomes a
  measured per-window quantity rather than an after-the-fact division.
- Pass-dynamics dials (Q5) gain an observability basis: a dial's effect
  on the trajectory is directly readable, so Q5's verify can include
  trajectory-shape constraints, not just endpoint verdicts.
- Follow-on named by the sweep: the receipts become training labels for
  a **learned loop governor** in the TaH2 shape (lookahead labels =
  "would another pass have changed this verdict?") — the allocator
  graduates from thresholds to a small trained decider
  [measured: RESEARCH-SWEEP §1.5].

**Branch B — the signal dies** (deltas do not contract, or contract
without predicting stability; note the standing threat: progress-aligned
training work shows unshaped iterations need not track progress at all
[measured: RESEARCH-SWEEP §1.4]):
- The internal settle signal is recorded as **dead for this artefact**,
  in the same register as the L5 scorer closure: a clean negative, not
  a programme failure.
- Allocation becomes **external only**: the allocator is a router, not
  a settler. Windows are routed across fixed-k llama-server instances
  (stock PR build, route (a) of STUDY-DORY D3) by CfC surprise + sheaf
  residual + class-level loop-marginal receipts. The loop currency,
  budgets, and receipts survive intact — only the stop rule's source
  changes.
- The oscillation guard re-keys to verdict-level observables (verdict
  flip between k and k+1 on sampled windows; claim-violation deltas),
  sampled at a receipted audit rate rather than read from inside.
- Q4 runs with two arms fewer (no settle-allocated arm); its falsifier
  is unchanged. If external allocation also fails to beat fixed-2 at
  equal spend, Dory ships (if at all) as a fixed 2-loop refiner and the
  synthesis's middle clause — depth as a runtime budget — is struck
  from the architecture, honestly, in this document's successor.
- The TaH2 follow-on becomes *more* important, not less: if no
  hand-read signal exists, a learned governor trained on loop receipts
  is the remaining route to per-request allocation.

## 6. The merged experiment queue

One queue, ordered by kill-power per unit cost. The empiricist's three
experiments (E1–E3) and the architect's three decisions (A1–A3) dedupe
as: E1+A2 → Q1 (same question at two altitudes: does an edit survive,
and on which surface); A1 → Q3 (trace validity, with STUDY-DORY's D1
grounded-curve run folded in as phase 0); E3 → Q4 (allocation at equal
spend, consuming Q3's signal or Branch B's router); E2 → Q2 (independent
of the loop line, runs second because it is the only item testing
something genuinely unknown); A3 → Q5 (last, contingent on Q1). A
standing precondition from §2 applies to Q3–Q5: **the refiner harness
runs reasoning-off (or under a verified delivery contract) before any
loop measurement is taken.**

### Q1 — Edit survival and authoring surface at deployment precision
*(merges empiricist E1 + architect A2)*
- **Question:** Does an authored direction edit survive requantisation
  to the deployment grid with its behavioural effect intact — and does
  survival differ by geometry (α≈1 norm-preserving ablation vs α=6
  amplified reversal) and by surface (native / scale-space / overlay)?
- **Method:** Arithmetic arm (no GPU): per-block survival cosine
  (intended vs surviving delta) for the paper's published Qwen edit and
  for our Phase 15/16 soft-joint patches, across grids (NVFP4 primary;
  Q5_K_M as the actually-deployed grid). Behavioural arm: five
  artefacts (BF16 base/edited, NVFP4 base/edited, NVFP4 edited with
  constrained requantisation) on the published protocol (500 problems ×
  4 samples), tracking accuracy *and* hit-limit share; surface arm:
  re-author a Phase 15/16 battery slice on all three surfaces, deploy,
  measure post-quant held-out separation. Probe reads the runtime's own
  code space throughout.
- **Cost:** hours of arithmetic; ~1 GPU-day behavioural. Seat-hours: low.
- **Falsifier:** amplified edit's aggregate survival cosine < 0.9, or
  NVFP4-edited accuracy gain < half the BF16 gap → the paper's method
  does not transfer to our deployment target; the plastic tier's
  paper-derived charter is dead. Sub-falsifier: α≈1 arm erased (cosine
  < 0.5) while α=6 survives → our patch *style* must change before any
  Dory work. Total falsifier: no surface survives → plasticity freezes
  at coarse precision; the spine/overlay split is moot.
- **Unblocks:** the patch plane's surface standard; Q2's deployment
  arm; Q5's admissibility; the NVFP4-vs-Q5 serving decision's patch
  half.

### Q2 — Writer-versus-detector discrimination on our own batteries
*(empiricist E2, unmerged — nothing else in either take tests this)*
- **Question:** Does a patch succeed when the direction it removes is a
  *writer* of the behaviour rather than a *detector* of it?
- **Method:** Phase 15/16 batteries (Qwen3-0.6B, LFM2-1.2B) plus the
  harbour-watch fixture. Re-derive each known patchable failure two
  ways at matched edit size: detector-derived (our current method; the
  11-trial null is its baseline) vs writer-derived (difference
  failing/passing continuations in the residual stream; subtract from
  the columns that write it). Held-out behaviour delta per arm;
  rollouts-to-result per arm; search cost receipted per §3.6.
- **Cost:** 2–3 seat-days. GPU-minutes: moderate (battery replays).
- **Falsifier:** writer and detector arms indistinguishable, both
  within 1 SE of zero → the sharpening collapses; procedure stays
  closed (§3.4); the paper's one surprising result has no mechanism we
  can generalise.
- **Unblocks:** the write surface's procedure clause; the author's
  search strategy (writer-finding becomes its primary instrument); the
  denial templates get rewritten either way — with evidence.

### Q3 — Settle-signal validity, external and internal
*(architect A1 + STUDY-DORY D1/D2; taps-dependent for the internal arm)*
- **Question:** Is there a signal — external (CfC surprise, sheaf
  residual) or internal (per-pass delta, if taps lands) — that
  discriminates windows where another loop changes the verdict from
  windows where it does not, on this run's actual inputs?
- **Method:** Phase 0 (D1 folded in): fixed k ∈ {1,2,3,4} over the
  house grounded fixtures (BRAIN-Bench battery, presence claim-trap
  set, harbour digest windows), reasoning-off harness; per-k grounded
  quality, claim violations, tokens, loop-seconds — the grounded
  quality-vs-loops curve neither vendor table nor smoke (n=6) can give
  us, plus a per-pass divergence proxy for the §3.2 settlement. Phase
  1: score each candidate signal against measured loop-marginal-value
  per window; a signal passes only with demonstrated discrimination
  and a false-settle rate ≤ 5% on inputs where looping would not have
  helped, its own cost charged.
- **Cost:** ~1 seat-day phase 0 on the stock build; phase 1 analysis
  cheap; internal arm waits on taps (no additional cost, a dependency).
- **Falsifier:** no signal correlates with loop-marginal-value, or the
  best signal's false-settle rate > 5% → metered allocation has no
  instrument; Branch B routing becomes the design, and if phase 0 shows
  quality flat 1→4 everywhere at 2.67× spend, the loop dial itself is
  dead on our workloads and Q4/Q5 do not run.
- **Unblocks:** Q4's allocator arms; the loop currency's credibility;
  the §3.2 compounding question.

### Q4 — Cascading allocation at equal compute
*(empiricist E3 = STUDY-DORY D3, consuming Q3)*
- **Question:** Does per-window loop allocation beat every fixed loop
  count at **equal total loop-seconds** on grounded quality?
- **Method:** Refiner seat over the live cascade shape (frames → gate →
  I-JEPA events → digest → refiner). Arms: fixed 1 / 2 / 4;
  surprise-allocated (external signals, budget-normalised to fixed-2);
  settle-allocated (Branch A only). Delivery by multi-instance routing
  on the stock PR build. Metrics: grounded-claim rate and correction
  rate per loop-second; gain-vs-surprise correlation per window;
  TTFO/freshness impact on the reflex tier (the tenancy ladder
  applies); detector cost subtracted from the arm it serves.
- **Cost:** ~1 seat-week (empiricist's E3 estimate). GPU-minutes: the
  largest in the queue — this is the first item that runs the full
  cascade as a system.
- **Falsifier:** no adaptive arm beats fixed-2 at equal spend → 
  cascading allocation is falsified for this seat; Dory ships (if at
  all) as a fixed 2-loop component. Gain-vs-surprise correlation ≈ 0
  with allocation otherwise working → the allocator's *input* is wrong;
  the fault is in the perception tier's signals, not in Dory.
- **Unblocks:** the architecture's middle clause (depth as a runtime
  budget) — or its honest removal; the production refiner seat decision
  against the incumbent brain's measured record (a tie goes to the
  incumbent).

### Q5 — Recurrent-block dial transfer across loop counts
*(architect A3, contingent on Q1)*
- **Question:** Do dials authored on the shared recurrent block at k=2
  hold at k=1 and k=4 — or does per-pass compounding make the block
  effectively read-only under a variable-k allocator?
- **Method:** Author dials (surface per Q1's winner) on the shared
  block tuned at k=2; replay the batteries at k ∈ {1,2,4} at equal
  budget under two-currency verify; in Branch A, add trajectory-shape
  constraints from the taps signal.
- **Cost:** 1–2 seat-days plus battery replays, after Q1.
- **Falsifier:** k=2-tuned dials fail at k=1/k=4 → the shared block is
  read-only by default; the writable surface shrinks to input/output
  layers, joints, and readouts, and the author's leverage drops by the
  block's share of the network — recorded as a smaller, still-viable
  plastic tier.
- **Unblocks:** pass-dynamics dials (the architect's highest-leverage
  write surface) or their permanent exclusion; the final shape of the
  patch plane.

### Q6 — (standing bench, not a gate) W4A4-or-nothing at our scale
- **Question:** At Thor scale, do W4A16 / W4A4 / K-quant servings of one
  resident model reproduce the shape of NVIDIA's NVFP4 result —
  including behaviour-shape changes (completion length, abstention),
  not just scores? [measured: RESEARCH-SWEEP shortlist 3]
- **Method/cost:** a bench-week, schedulable in parallel with Q2–Q3;
  it gates no other item but decides the refiner's eventual serving
  format and whether "NVFP4-native" ever becomes a premise rather than
  a question. TensorRT Edge-LLM's audited 6.4× over the llama.cpp
  reference for *dense* models [measured: RESEARCH-SWEEP §5.1] means
  the serving stack decision is split by architecture: Edge-LLM class
  for dense residents, PR-build llama.cpp for the looped refiner,
  unless Q6 says otherwise.

### Programme dead-ends (pre-registered, from the empiricist, adopted)

1. **Precision dead-end:** Q1 fails on both geometries and the
   constrained-requantisation remedy costs more engineering than the
   problem justifies at our scale → the weight-patching leg is a
   research project, not a programme; drop it, keep the governed path
   for BF16/Q5-scale patches only.
2. **Accounting dead-end:** no settle/surprise signal demonstrates
   discrimination, or the detector's cost eats the budget it allocates
   → "metered" is vocabulary, not mechanism; ship fixed-2 (Q4's
   falsifier is this dead-end's operational form).
3. **Search dead-end:** the governed path cannot reproduce the author's
   *search* inside our cost envelope (§3.6) → the programme is a
   wrapper around a frontier inference budget; name it as such or stop.
4. **Procedure dead-end:** Q2 ties → the ambition to extend patching to
   procedure is dropped; the existing programme continues unchanged.

## 7. Claims register

Load-bearing claims only. "Measured" means our instruments, this repo.

| # | Claim | Tag |
|---|---|---|
| 1 | Rolling vs batched time-to-first-output 243.5 µs vs 2,528.6 µs (10.39×) | [measured: parent repo RESULTS] |
| 2 | Diff-gating cut embeds 576 → 312 (−54%); sheaf refine ablation precision 0.60 → 1.00 | [brief] |
| 3 | Authored patches harvest format/completion/framing + readouts on separated representations; zero on procedure/facts/unseparated relations | [brief] (Phase 15/16) |
| 4 | Soft-joint dial patches: held-out 46.7% → 84.2% where full-model patching did not transfer | [brief] |
| 5 | Detector-neuron interventions: 11 trials, zero effect | [brief] |
| 6 | Governed patch path ≈ 25 min end-to-end; rollback bit-for-bit | [brief] |
| 7 | Dory: 8 in / shared 20 recurrent / 8 out; input re-injected per pass; k ∈ {1,2,3,4}, launch-time in all current tooling; default 2 | [measured: STUDY-DORY §1–2] |
| 8 | Vendor quality shape: SWE-bench 50.3/59.5/61.8; GPQA peaks at 2 (72.41) falls at 4 (72.16); IFBench monotone 74.29/77.94/79.0 | [measured: STUDY-DORY §1] (vendor-claimed numbers, our reading) |
| 9 | Thor decode, Q5_K_M, last_loop: 19.7 / 13.0 / 10.4 / 7.6 tok/s at k=1/2/3/4, contended box | [measured: DORY-SMOKE-1] |
| 10 | Reasoning-on delivery failure: 4/6 prompts correct-in-reasoning, never delivered, all k; reasoning-off 5/6 correct, loops change phrasing not verdicts | [measured: DORY-SMOKE-1] |
| 11 | Per-pass settle signal NOT observable in the stock fork build; needs a source patch | [measured: DORY-SMOKE-1] |
| 12 | last_loop KV mode changes predictions and is prefill-chunk-sensitive; mode must be receipted | [measured: STUDY-DORY §2] |
| 13 | W4A16 NVFP4 slower than BF16 (10/12 shapes); only W4A4 reaches FP4 tensor cores; QAD changes output shape | [measured: RESEARCH-SWEEP §3.1] (NVIDIA's own measurements) |
| 14 | One recurrence ≈ r^0.46 equivalent parameters; looping buys reasoning/application, not knowledge | [measured: RESEARCH-SWEEP §1.10] |
| 15 | Unshaped iterations need not track progress (PAR); settle-by-default is not safe | [measured: RESEARCH-SWEEP §1.4] |
| 16 | TaH2: learned per-token loop governor with lookahead labels exists and beats fixed allocation slopes | [measured: RESEARCH-SWEEP §1.5] |
| 17 | TensorRT Edge-LLM 6.4× over llama.cpp reference on AGX Thor (dense models, MLPerf-audited, vendor submission) | [measured: RESEARCH-SWEEP §5.1] |
| 18 | Qwen headline edit = completion-pathology unblocking; 576/579 rescued answers had hit the token cap | [take: empiricist] (from published logs) |
| 19 | Kinetix repair adds a policy fragment; replicated 1,024/1,024 at 1.70% weights changed | [take: empiricist] (replication-grade) |
| 20 | Writer-vs-detector is the correct sharpening of the Phase 15/16 procedure null | [take: empiricist] — inference, tested by Q2 |
| 21 | Naive requantisation leaks a ~3% direction edit at 67% on FP4 tensors; constrained per-column requantisation is a documented remedy | [take: empiricist] (prior literature, not our measurement) |
| 22 | NVFP4 checkpoint is a QAD product; no cheap BF16-edit → NVFP4 path; patch in place | [take: empiricist] |
| 23 | Quantisation error does not compound with loop depth (KL ratio 0.98–1.17, Q5 and below) | [take: empiricist] (third-party) — [unverified] for our artefact; settled by Q3 phase 0 |
| 24 | Dory trained with a difficulty-aware loop curriculum; allocation-by-difficulty is NVIDIA's, in the weights | [take: empiricist] |
| 25 | Settle signal primary source = per-pass latent delta + sheaf residual; oscillation guard with pass-2 rollback | [take: architect] — internal arm unverified pending taps (§5) |
| 26 | Scale-space dials are a viable authoring surface on NVFP4 | [take: architect] — [unverified]; tested by Q1 |
| 27 | Two-currency verify closes a silent budget-conversion channel | [take: architect] — adopted as governance, no experiment required |
| 28 | WSP headline numbers (MATH-500 7.9% → 48.1%; Breakout one-shot > PPO-100M) | [unverified] — author-reported; effect direction not in doubt, magnitude has a published spread (third-party replays 0.11–0.33 to 51.0%) [take: empiricist] |
| 29 | NVFP4 format mechanics (E2M1, 16-element blocks, FP8 block scales, ~25% finest step) | [take: empiricist] (NVIDIA TE docs) + [take: architect] [BG] — consistent across both takes |
| 30 | Local 27B weight-reading at 3/4 tasks — author seat could come on-premise at reduced reliability | [measured: RESEARCH-SWEEP §2.3] (anecdote-grade) |

## 8. Bottom line

The composition holds, with its ambitions correctly sized. The cascade
gains a **looped refiner seat** whose depth is a receipted currency; a
**liquid shadow** that prices that depth before it is spent; and a
**plastic tier** confined — by our own measurements, the paper's logs,
and the replication cluster alike — to unblocking, readouts, and dials,
arriving only as governed proposals verified on the deployment artefact.
The architecture's centre of gravity is not any of the three models. It
is the ledger and the rule that binds every tier: *nothing is trusted —
sensor, settle signal, or patch — until it has demonstrated
discrimination on the run's actual inputs* [take: architect §11, on
brief]. The queue in §6 is ordered so that the cheapest questions kill
the most architecture: precision first (hours), the writer question
second (days), the settle instrument third, allocation fourth — and the
programme degrades safely at every gate, each failure leaving a smaller,
honest system standing rather than a larger, fictional one.
