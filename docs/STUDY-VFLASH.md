# STUDY — NVIDIA VFlash (Flash Primitive Decoding) as a candidate component for the Thor stack

Lane ROLLING PERCEPTION, 2026-11-06. Study only: nothing was
downloaded, no code was run, nothing on the Thor was touched.
Facts below come from primary sources — the paper itself
(arXiv:2611.08449, submitted 2026-11-05, read in full including
appendices) and the NVIDIA Research project page
(research.nvidia.com/labs/lpr/vflash, including its deployment
tables) — and are labelled as such. Every performance number
attributed to VFlash is **the authors' own**, measured on their
own customized runtime; no independent replication exists at
the time of writing (the Medium and trade-press coverage of
2026-11-06/07 is reporting of the paper, not reproduction, and
says so). Anything not confirmable from a primary source is
marked **UNVERIFIED**.

## Deficits first

- **There is nothing to run.** As of 2026-11-07, no public code,
  no drafter weights, no target-VLM weights, and no licence for
  any of them could be located. The paper's front page carries a
  GitHub link, but no reachable public repository, release, or
  model artefact was found through the project page, the arXiv
  record, or the secondary coverage; third-party trackers
  describe the release posture as "watch LPR/GEAR for code and
  weight releases." The paper itself is © 2026 NVIDIA, all
  rights reserved. VFlash today is a paper and a project page,
  not a component.
- **The demonstrated target VLM is a custom, unreleased model.**
  Most experiments run on the authors' own embodied VLM —
  a Qwen3-4B language model with a MoonViT vision encoder and
  an MLP connector, progressively trained in-house — fine-tuned
  per task and then frozen. VFlash's numbers are therefore
  numbers about a (target, drafter) pair that does not exist
  outside NVIDIA's lab, not about a drafter bolted onto a stock
  model. The one released target used is MolmoMotion-AR (dense
  motion only).
- **A drafter is trained per (target, task) pair, at real
  cost.** Each primitive family gets its own drafter trained on
  annotated geometry for that target: the robot 2D+3D drafter
  trains for 30,562 updates at batch 512; the dense-motion
  drafter trains over 12.7M sampled windows on 32 H100s; the
  target itself is first fine-tuned on the task (10k–26k
  updates) before any drafter exists. "Lightweight" describes
  the drafter's inference cost, not its production cost.
- **Direct acceptance is not free: boxes need their fallback.**
  Accepting every schema-valid box without verification drops
  mean F1 by about 20 points on the crowded Dense200 set; the
  published box results use a spatial-confidence guard with
  constrained autoregressive regeneration, and even then F1 at
  IoU 0.95 is *lower* than the AR baseline. The clean
  "accept without agreement" story holds for trajectories; for
  boxes it holds only with a verification-shaped guard bolted
  back on.
- **The dense-motion result is mixed, and its headline number
  is preliminary.** The ~25× generation speedup is, in the
  paper's own words, "preliminary single-rollout measurements."
  On PointMotionBench, VFlash's ADE ranks second behind its AR
  target on two of three datasets, WorldTrack FDE is 15%
  *worse* than AR, and its PWT is 7–12% lower across all three.
- **Every latency number is model-pipeline latency on a
  customized runtime.** Measurements use "customized
  TensorRT-Edge-LLM runtimes" (a modified Edge-LLM 0.9.0 base
  on Thor, with CuTe DSL attention kernels), FP16 engines with
  FP16 KV caches and no quantization, batch size one, and a
  timing boundary that excludes model loading, engine building,
  warmup, out-of-module preprocessing, and detokenization. The
  Thor robotics figure rests on 24 records. This is a
  laboratory measurement of a bespoke stack, not a property of
  an artefact we could install.
- **No limitations section exists.** The paper's conclusion
  names one future direction (multiple complementary
  primitives per observation). Every limitation in §1.4 below
  is either stated in the paper's body/appendices or is our
  reading, labelled as such.

## 1. Verified facts (primary sources)

### 1.1 What it is

VFlash is a decoding framework for vision-language models whose
outputs mix ordinary text with **visual primitives**: bounding
boxes, points, 2D/3D trajectories, and dense point motion. Its
central claim is that a primitive's type, dimensionality, and
length are known *before* any coordinate is decoded, so the
entire primitive can be predicted jointly, in one parallel
pass, by a small drafter — and that spatial accuracy does not
require reproducing the autoregressive target's exact token
sequence. Primitives are therefore **accepted on structural
validity, not token agreement**; text keeps classical verified
speculative decoding. The paper frames this as enabling a
"System-1 mode" of visual planning in VLMs, and cites Jev and
Visual Jev in that context — a framing kinship with this
house's JEV rack, not an integration with it.

### 1.2 The mechanism, precisely

- **Routing.** Generation proceeds in DFlash blocks of 16
  positions for ordinary text (one accepted anchor plus up to
  15 proposals). A structured tool call in the text declares
  the size of the next variable-length primitive; when an
  accepted prefix reaches a primitive-start token, speculative
  text tokens after it are discarded and the primitive schema
  takes over.
- **Flash Primitive Decoding.** A block is allocated for the
  *complete* primitive: an observed start token followed by
  B(s)−1 masked positions, where the schema s (type + extent
  from the tool call) fixes every position's role — waypoint,
  axis, delimiter. The drafter predicts all positions
  conditionally independently, in one bidirectional pass,
  conditioned on fused hidden features from the frozen target.
  Per-position constraints restrict each slot to its legal
  vocabulary (coordinate tokens or delimiters) at zero extra
  network cost. Block lengths in the paper: 6 for a box, 54
  for a 10-point 2D+3D trajectory, 155 for one dense-motion
  frame, 16 for text.
- **Coordinate representations.** Two are supported: dedicated
  coordinate tokens (the authors' base model uses 1,001 special
  tokens for coordinates normalized to 0–1,000), and, for
  text-tokenized targets, a fixed-width layout of one sign plus
  five digit positions per coordinate, rendered back into the
  target's text format afterwards.
- **Acceptance (the part that is not speculative decoding).**
  A schema-valid primitive is committed in full, with no
  token-level agreement check. One target pass over the
  accepted primitive then updates the KV cache and produces
  the hidden features that downstream action heads cross-attend
  to. If validation fails, the cache rolls back to the anchor
  and the block is regenerated by constrained target AR from
  the first invalid position (for trajectories, nothing is
  retained). For boxes, acceptance additionally requires the
  spatial-confidence guard inherited from LocateAnything:
  boxes whose coordinate distributions look uncertain are
  regenerated autoregressively.
- **Text path ("verified speculative decoding", concretely).**
  The same drafter drafts 16-position text blocks; the target
  verifies in one pass and keeps the longest prefix that
  matches its own greedy continuation, plus the target's next
  token. This is distribution-preserving speculative decoding
  in the standard sense — the text the system emits is exactly
  the target's text, only faster. The measured benefit is
  modest inside primitives (DFlash commits 5.5 tokens per
  iteration on sub-task text but only 2.2 within trajectory
  blocks, because a coordinate one bin off fails verification)
  — which is precisely the gap the unverified primitive path
  exists to bypass.

### 1.3 The drafter

Per Appendix B of the paper: five full-width Qwen3 transformer
layers, 32 query heads, 8 key/value heads, 128-dimensional
heads, 9,728-dimensional feedforward — **537M trainable
parameters**, sharing the frozen target's input embedding and
output projection. It consumes the target's hidden states from
layers 1, 9, 17, 25, and 33 (zero-based), concatenated
(12,800 dimensions) and projected to 2,560. Training is
weighted cross-entropy against **annotated coordinates**, not
against the target's outputs — no distillation, no
hidden-state regression. Primitive positions carry unit
weight; ordinary-text positions decay with distance from the
anchor (so one drafter serves both paths). The target VLM is
fine-tuned on the task's spatial format first, frozen, and
only then is its drafter trained, on the same data.

### 1.4 Targets and results (all author-reported)

Targets demonstrated: (i) the authors' custom 4B embodied VLM
(§Deficits), in three training variants — 3D-only, 2D+3D, and
2D+3D with wrist-camera training — evaluated for trajectory
prediction on InternA1, AgiBot, and MolmoBot data; (ii) the
released MolmoMotion-AR 4B, frozen, for dense 3D point motion;
(iii) the same custom VLM as planner for downstream action
heads — a Cosmos-Predict2.5 world action model on MolmoSpaces,
a PIv3 flow-matching head on the LIBERO family, and a
ReCogDrive-derived diffusion head on NAVSIM / Waymo /
Alpamayo-format driving trajectories. (A stock Qwen3-VL-4B
appears in the LIBERO experiments as the *baseline* encoder,
not as a VFlash target.)

Headline results, as published:

- Robot trajectory prediction (open loop): VFlash reduces all
  six 2D error metrics on ShareRobot-Bench and VABench-V
  (3–7%); 3D ADE falls 18–49% (3D-only target) and 28–61%
  (2D+3D target) against the same targets decoded
  autoregressively; mean 3D ADE −42.6% across settings.
- Boxes: with the AR fallback, mean F1 matches AR on COCO and
  Dense200 at 2.6–2.8× the boxes-per-second; without the
  fallback it does not (see Deficits).
- MolmoSpaces manipulation (simulator; the simulator pauses
  during inference): the plan-conditioned WAM reaches 70.2%
  average success vs 62.6% for the WAM baseline and 61.0% for
  the same WAM conditioned on autoregressively generated
  plans. On the LIBERO family, gains over the no-primitive
  baseline grow under perturbation (LIBERO-PRO: +6.8 points).
- Driving: VFlash-SFT reaches 87.1 PDMS on NAVSIM (best listed
  SFT-only competitor: 90.7 after RL; VFlash's own RL-tuned
  action head also reaches 90.7 — the RL is on the action
  head, the plans are unchanged).
- Latency (Jetson Thor, batch 1, model-pipeline boundary):
  MolmoSpaces per-step latency 3,552.7 ms (AR) → 1,828.4 ms
  (DFlash) → **703.3 ms (VFlash)**, a 5.1× pipeline speedup;
  the decoding stage alone falls 3,107.6 → 258.2 ms (12×).
  AR decoding of the 4B FP16 target costs 35–39 ms per token
  on Thor; one drafter pass over a 36–84-token primitive costs
  13–23 ms. Driving decoding falls 19–42×.

Limitations stated or demonstrated in the paper: the box
fallback dependency and IoU-0.95 regression (above); the mixed
dense-motion metrics (above); the preliminary status of the
25× figure (above); per-(target, task) drafter training with
a prior per-task target fine-tune (§1.3); and, in the driving
setup, SFT plans that need an RL-tuned head to reach the top
of the table. Limitations by our reading: evaluation is
open-loop for all primitive prediction; the one closed-loop
downstream benchmark is a simulator that pauses during
inference; and no evidence is offered for primitives outside
the four families studied (boxes, points, trajectories, dense
motion), for targets larger than 4B, or for quantized
deployment — the entire study runs FP16 without quantization.

### 1.5 The runtime, vs our Thor

The paper's Thor measurements run on: Jetson AGX Thor (SM110),
CUDA 13.0, TensorRT 10.15.2.7, a **customized** TensorRT-Edge-LLM
0.9.0 base, FP16 VLM engines with FP16 KV caches, CuTe DSL
FMHA (vision/prefill) and XQA (decode/verification) kernels,
and a custom head-dimension-128 CuTe attention kernel in the
robot action model. The paper's JetPack version is not stated
(**UNVERIFIED**).

Our Thor (fleet record; not re-verified for this study):
JetPack 7.2.1-b49, CUDA 13.2, TensorRT 10.16.2.10, PyTorch
2.11 (cu130), and a serving culture built on llama.cpp GGUF
(the presence brain) and the JEV rack (I-JEPA / V-JEPA
embeddings and the semantic judge). Version drift is not the
obstacle — our CUDA and TensorRT are *newer* than the paper's
bench. The obstacle is that VFlash's runtime is a modified
Edge-LLM with custom kernels that is not published, and our
stack contains no TensorRT-Edge-LLM deployment, no FP16 VLM
engine, and no VLM in the serving path at all.

## 2. Fit assessment, surface by surface

### (a) The league citizens' minds — NO FIT

The citizens' deliberation loop is text in, text out: a state
feed and facts files go to a local text LLM (the llama.cpp
presence brain); JSON plans, authored JavaScript skills, and
chat lines come back; a protocol client (mineflayer) executes
symbolic actions — goto, collect, craft. There is no vision
model in the loop, no image input to any decision, and no
coordinate sequence is ever decoded: positions enter as text
and leave as action names. The only VFlash machinery that
touches text at all is its DFlash path, which is ordinary
verified speculative decoding — it would require a drafter
trained against our exact target, exists in this work only
inside the unpublished runtime, and addresses a cost we do not
have: the brain already decodes at ~65 tok/s against
ten-minute deliberation ticks, and the league's measured
bottlenecks tonight are budget accounting, planner arithmetic,
and locomotion physics — never decode latency. There is no
visual-primitive decoding anywhere in this loop for VFlash to
accelerate, and bolting a VLM into it to create one would be
inventing a workload to justify a component.

### (b) telltape / rolling perception — NO FIT

telltape's perceptual path contains no autoregressive decoding
of anything. Frames are embedded (I-JEPA / V-JEPA on the JEV
rack), per-tile cosine differences gate which tiles earn
further compute, and change events are written to the ledger
by code. The v0.4.0 score-series sidecar widened what gets
recorded; it did not add a generator. A VLM narrating ledger
events would emit prose, not primitives, and narration is not
on the critical path. The honest connection is conceptual and
worth one sentence: VFlash's premise — when the structure of
an output is known in advance, predict it jointly instead of
spelling it out — is the same shape as this programme's
premise that a rolling percept should not re-pay full price
for what did not change. A premise rhyme is not an integration
surface. No fit.

### (c) The world digest / Orin game-master — CONDITIONAL FIT (the strongest candidate)

The game-master design calls for a resident slow mind on the
Orin, fed by a **world digest**: structured spatial state —
who is where, what moved, what changed — on a minutes cadence,
issuing receipted, reversible nudges. Everything depends on
how the digest is produced, and there are two designs:

- *Digest from server state* (the current design centre): the
  digest is assembled from state feeds, the server log, and
  the ledger — data that already exists in exact, structured
  form. No VLM emits anything; VFlash has nothing to attach
  to, exactly as in (a) and (b).
- *Digest from frames*: a VLM watches the world (spectator
  frames, citizen POVs) and emits the digest as structured
  spatial state — a box per citizen, a short trajectory per
  mover, a point per changed structure. That emission *is*
  visual-primitive decoding with a fixed schema, in exactly
  the families VFlash demonstrates (box = 6-token block,
  short trajectory = tens of tokens), and it is the one place
  in the programme where autoregressive coordinate decoding
  would be a real, measured cost: at the paper's own Thor
  figure of 35–39 ms per AR token for a 4B target, a
  16-entity digest of boxes plus 8-point tracks runs to
  several hundred coordinate tokens — order ten seconds of
  pure decode per digest, at batch one, before the GM has
  thought at all. One-pass drafting is the difference between
  a digest cadence of minutes and one of seconds.

The fit is real but doubly gated: the frame-based digest is a
design option, not the current design; and VFlash itself is
unobtainable (§Deficits), so any spike today tests a
reimplementation of the published scheme against a stock
target, not NVIDIA's artefact. Verdict: **the only designed
surface where the shoe fits — carry the spike in §3, gated as
stated there.**

### (d) Lineage F, the pixel body — REAL FIT IN PRINCIPLE, DEFERRED WITH F

Lineage F (VPT/STEVE-1 class) is deferred on its own merits:
its only seat is the headed client, which is the camera's
seat. It is also, architecturally, the truest fit of the five
surfaces. A pixel body that plans — a VLM consuming frames and
emitting camera/movement trajectories or waypoint primitives
in world coordinates, replanning at System-1 cadence — is
MolmoSpaces with blocks instead of grippers: the plan is a
trajectory primitive, the action head is the movement stack,
and AR coordinate decoding would tax every replan exactly as
the paper measures. If F is ever fielded in that shape (a
planning VLM over a scripted body, rather than a pure
end-to-end pixel policy, which emits action tokens, not
spatial primitives, and would fit VFlash correspondingly
less), Flash Primitive Decoding is the correct decoding layer
for it, and a Minecraft-trajectory drafter could be trained on
annotation this world provides for free — the server knows
every citizen's true position at every tick. That is a
programme of work behind a deferred lineage, not a spike.
Verdict: fit recorded; no action while F is deferred.

### (e) Marine / robotics futures — NOT NOW

SI-Marine's named projects (CoCapn, sonar-vision, the vessel
room navigator) are the genre VFlash was built for — a VLM on
a vessel emitting berthing trajectories, contact boxes, and
track forecasts at System-1 cadence is a direct analogue of
the paper's driving setup, and the Thor-class deployment
story transfers unchanged. But the org is, by Casey's own
charter, in process of development: its perception problems
are sonar-first, no marine VLM planner exists to be
accelerated, and nothing in that programme is currently
latency-bound on coordinate decoding. File VFlash in the
marine programme's reading list, next to the navigator; it
earns a second look the day a marine VLM emits its first
trajectory.

## 3. The spike (surface (c) only)

**Name:** digest-primitive spike. **Question:** on our Thor,
does one-pass primitive drafting beat autoregressive decoding
for a VLM emitting structured spatial state, at spatial
accuracy that does not embarrass the AR target — using only
artefacts we can actually obtain?

**Stage 0 — the baseline (runnable today, no NVIDIA
artefacts).** Serve a stock Qwen3-VL-4B (the same target class
the paper uses as its LIBERO baseline encoder; weights
publicly available under the Qwen licence) on the Thor in
FP16, and prompt it with frames from the live Orin world —
spectator and citizen-POV screenshots — to emit a fixed-schema
digest primitive set: one box per visible citizen, one
8-point trajectory per mover, in the paper's layout style.
Ground truth is free and exact: the server state feeds know
every citizen's position. Measure, at batch one: AR decode
latency per digest, token counts, and spatial error (box IoU,
track displacement) against server truth, across ≥50 digests
including night and canopy-occluded frames. This stage alone
decides whether the frame-based digest design has a latency
problem worth solving, and produces the annotated corpus
(frames paired with true boxes/tracks) that Stage 1 trains on.

**Stage 1 — the drafter (gated).** Enter only if Stage 0 shows
both (i) AR decode dominating digest latency (≥60% of
per-digest time) and (ii) the schema holding up as the right
digest shape. Then: fine-tune the target lightly into the
spatial format (the paper's recipe does this first; budget
~10k updates at 4B), freeze it, and train the published
drafter architecture (five Qwen3 layers, 537M parameters,
features from target layers 1/9/17/25/33) on the Stage 0
corpus — **boxes only** (the 6-token block, the cheapest
primitive the paper demonstrates) for the spike's first
verdict. If NVIDIA has by then released code or drafters, this
stage collapses into an evaluation of their artefact instead;
the spike is written to survive either world.

**Kill criterion.** Stop, and leave the digest autoregressive
(or state-feed-based), if any of: the box drafter's mean F1
against server ground truth falls more than 5 points below
the AR target's on the same frames (the paper's own
direct-acceptance box failure was ~20 points on Dense200 —
if we reproduce that failure shape at any scale, the guard
machinery it forces is worth more than the latency it saves);
or one-pass drafting cuts per-digest decode latency by less
than 3× at batch one (below that, the pipeline's other stages
eat the win, as they did between the paper's 12× decoding and
5.1× pipeline figures); or Stage 0 shows decode is not the
digest's bottleneck in the first place.

**Train vs download.** Download: the stock target's weights,
nothing else — nothing of VFlash's is downloadable. Train:
the target's spatial-format fine-tune and the box drafter,
both on the Thor, both sized by Stage 0's corpus (hundreds to
low thousands of annotated frames, which this world generates
as a by-product of being watched). No H100 fleet is assumed;
if Stage 1's training cost on one Thor exceeds a long weekend
of GPU time, that is itself a reportable result against
adoption.

## 4. What would have to change for VFlash to matter more

1. **A release.** Code, the customized Edge-LLM runtime (or
   the scheme's arrival in stock TensorRT-Edge-LLM / a
   maintained serving stack), and ideally pre-trained drafters
   for stock targets. Until then every adoption is a
   reimplementation of a paper whose reference implementation
   is a customized C++ runtime with bespoke kernels.
2. **A workload that decodes coordinates.** Today, no running
   system in the house asks a VLM for a box, a point, or a
   trajectory. VFlash accelerates exactly one thing; the
   programme currently does that thing zero times per day.
   The frame-based digest (c) or a fielded Lineage F (d) would
   change the count from zero; nothing else on the roadmap
   does.
3. **Cheaper drafter production.** A per-(target, task)
   training pipeline whose reference budgets run to tens of
   thousands of updates — and 32 H100s for the dense-motion
   drafter — is a lab workflow. A published recipe that trains
   a useful drafter on a single Thor-class device in hours
   would move VFlash from "watch" to "try" for every surface
   above.

## 5. Risks

- **Vendor-number risk.** All results are self-reported, on a
  custom runtime, with a custom target, days after
  publication, with zero independent replication — the same
  evidence posture this house recorded for Dory at study time,
  and the reason every figure in §1.4 is labelled
  author-reported.
- **Reimplementation risk.** The scheme's load-bearing details
  (feature fusion, constraint machinery, cache handling) live
  in appendices and an unpublished runtime; a from-paper
  rebuild may spend its budget rediscovering them. The §3
  spike is scoped (boxes only, one target class) to keep that
  risk priced.
- **Premise risk (ours).** Adopting VFlash thinking too early
  would push the digest design toward frames-and-VLM because
  a fast decoder exists for it, when the state-feed digest is
  exact, free, and already designed. The spike's Stage 0 is
  ordered to measure the frame design on its merits before
  any drafter is trained.

## Bottom line

VFlash is a well-evidenced *idea* and an unavailable
*artefact*: a 537M block-diffusion drafter that predicts whole
visual primitives in one pass off a frozen VLM's features,
accepts them on structural validity rather than token
agreement, and — on the authors' own customized Thor runtime —
cuts robot-planning latency 5.1× end to end and 12× at the
decoding stage, while *improving* trajectory accuracy against
its target. None of the house's running workloads decode
visual primitives: the league's minds are text-only (a), and
telltape's perception is embedding arithmetic (b). The two
surfaces where the shoe genuinely fits are both unbuilt — the
frame-based world digest for the Orin game-master (c), for
which §3 names a staged, kill-criterion spike, and the
deferred pixel-body Lineage F (d), whose fit is recorded for
the day it is fielded. Marine (e) is a reading-list entry.
Recommendation: **watch, with the Stage 0 baseline runnable
whenever the game-master's digest design is next opened** —
and revisit the whole study on the day NVIDIA ships code.

## Sources

- Chou, Wang, Huang et al., *VFlash: Fast, Accurate Visual
  Planning via Flash Primitive Decoding*, arXiv:2611.08449
  (submitted 2026-11-05) — paper and appendices, read in full
  2026-11-06: mechanism (§§2, 2.4–2.5, App. C), drafter
  architecture and training budgets (App. B), results (§3,
  Tables 2–8), latency methodology (§3.3, App. E–F).
- NVIDIA Research project page, *VFlash: Enabling System-1
  VLMs for Physical AI*, research.nvidia.com/labs/lpr/vflash —
  deployment tables (Thor: CUDA 13.0, TensorRT 10.15.2.7,
  customized Edge-LLM 0.9.0, FP16, timing boundary), read
  2026-11-06.
- Secondary coverage consulted for evidence-quality and
  release posture only (all reporting, no replication):
  Medium technical review (2026-11-06); FastToolHub VFlash
  entry ("watch LPR/GEAR for code and weight releases");
  AI Weekly alert (drafter parameter count, corroborating
  App. B). No public repository, weights, or licence located
  as of 2026-11-07.
- House records for stack facts (§1.5) and workload shapes
  (§2): TOOLS.md (Thor JetPack/CUDA/TensorRT, JEV rack,
  presence brain); MEMORY.md and this lane's records (league
  architecture and governor economics; telltape v0.4.0
  score-series sidecar; the Orin game-master design and its
  1.5–2 GiB headroom; Lineage F's deferral and its reason).
