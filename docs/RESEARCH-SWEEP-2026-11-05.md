# RESEARCH SWEEP — 2026-11-05

Window: roughly 2026-10-15 → 2026-11-05. Five areas around the
rolling-perception programme. Every item carries a source grade:
**primary** (arXiv paper, official blog, model card, repo/PR),
**reputable-secondary** (named-author analysis or established
newsletter reporting primary material), **anecdote** (self-reported,
single-run, forum-grade). Vendor numbers are labelled vendor-claimed
and never mixed with independent results. Items just outside the
window are included only where the window's discourse turned on
them, and are dated as such.

Programme frame for the relevance lines: a rolling perception system
on one Jetson AGX Thor (aarch64, sm_110, CUDA 13.2) that meters two
currencies — **embed-seconds** and **loop-seconds** — and allocates
recurrent depth by a settle signal rather than a fixed launch-time
choice (see STUDY-DORY.md for the charter this sweep feeds).

---

## 1. Looped / recurrent-depth / latent-recurrence models

### 1.1 SenseNova-Loop-9B-Preview actually shipped (2026-10-30) — primary (model card) + reputable-secondary
SenseTime released the model our earlier study knew only as a
preview announcement: 9B stored parameters, 32 layers of which
layers 4–27 execute **twice** (56 layer passes), two residual
streams mixed by manifold-constrained hyper-connections (mHC,
Sinkhorn-normalised), text+image in, Apache-2.0, trained to 262K
tokens. Vendor-claimed: "27B-class results" on agentic benches,
beating Qwen3.5-27B on three of five reported benchmarks and losing
Terminal-Bench 2.1 (40.45 vs 47.19). Technical report still TBA;
no independent scoring yet. Third-party GGUFs already exist but
**require a patched llama.cpp** — upstream does not support the
`sensenova_loop` architecture.
*Relevance:* the second looped checkpoint in the wild confirms the
pattern is a product line, not a stunt — but its loop count is
fused at exactly 2 with no dial at all, which widens, not narrows,
the unclaimed space our charter occupies (allocation as a runtime
decision).

### 1.2 UpLoop: looped models trained by upcycling at no extra pretraining compute (2026-10-30) — primary (arXiv:2610.41720)
Train shallow, copy layers to grow depth, then spend the saved
compute running a shared middle block repeatedly. Claim: at 1.3B,
average across 22 downstream tasks rises 22.99 → 27.52 against a
dense baseline at **identical** parameter count, tokens and
training FLOPs.
*Relevance:* answers the "who trains these" question — looping no
longer needs a from-scratch run, which lowers the cost of someday
training a looped refiner on our own digest distribution.

### 1.3 Asymmetric Looped Transformers (2026-10-20) — primary (arXiv:2610.28489)
Full-stack looping conflates context construction with state
refinement. AsymLoop separates them: a single-pass encoder builds
fixed global KV once; a weight-tied recurrent decoder refines
state against it. Claim: at 1B, +1.27 points average zero-shot
accuracy over full-loop at matched effective depth and tokens.
*Relevance:* this is our cascade's shape stated inside one model —
encode once, refine repeatedly. It suggests the refiner seat should
loop against a **frozen** context representation (our digest +
frozen tile embeddings) rather than re-encoding per pass, which is
also the only arrangement under which per-loop KV stays cheap.

### 1.4 PAR: extra iterations do not extrapolate unless each iteration is trained to make progress (2026-10-21) — primary (arXiv:2610.27628)
Looped models run longer at test time need not solve longer
problems: final-answer supervision doesn't tell iteration k how far
it should advance. Progress-Aligned Recurrence supervises each
iteration's prediction against the true intermediate state and
anchors recurrent-state norms. Claim: 95.5% full-state accuracy at
16× training length on S5 state tracking, vs 0.8% for explicit CoT;
removing norm anchoring collapses extrapolation to <2.2×.
*Relevance:* a warning aimed at our settle signal — iteration count
is not a free dial on an arbitrarily-trained looped model; the
per-pass trajectory has to be *shaped* (or at least measured)
before "loop until settled" means anything. See Contradictions.

### 1.5 TaH2: adaptive looped transformers — per-token iteration decider (project page/paper, surfaced in window) — primary
Post-trained looped models often show a *steeper* accuracy–compute
slope than dense baselines yet still lose at matched compute. TaH2
jointly trains the backbone and an **iteration decider** with
lookahead supervision (labels = "would another iteration improve
this token's prediction?"). Claim: +53% accuracy–compute slope on
AIME over the non-looped baseline, exceeding its peak accuracy by
~3.4 points at matched test-time compute; gain grows with depth.
*Relevance:* the closest published relative of our cascading
allocator — a *learned, per-unit* loop governor with an explicit
training signal. Their labels are exactly what our loop receipts
would generate as a by-product. Shortlist item.

### 1.6 Elastic Latent Recurrence / Koi-4B: the "one-loop tax" named and attacked (surfaced in window) — primary
Loop-trained models typically underperform a same-size dense model
at 1 loop — a tax that makes them the wrong choice whenever latency
matters. ELR's recipe (gated state update with learned step size,
loop counts mixed within each optimizer step, per-pass loop-index
conditioning, last-loop-only KV) claims to erase it: 4B model
within ±1 point of its dense baseline at 1 loop, +7.25 points by
4 loops; shipped as Koi-4B.
*Relevance:* if we ever serve two loop counts of one checkpoint —
a 1-loop reflex path and a 4-loop deliberative path — the one-loop
tax is the property to test first; a model that pays it breaks the
reflex tier.

### 1.7 LoopCoder-v2: loop-count returns are strongly non-monotonic (pre-window, load-bearing) — primary (arXiv:2606.18023)
A 7B looped coder family trained from scratch: 2 loops lift
SWE-bench Verified 43.0 → 64.4; **3 loops collapse it to 27.6**;
later-loop updates turn oscillatory with reduced representational
diversity.
*Relevance:* the strongest single evidence that loop depth must be
*allocated and receipted per workload*, never set-and-forgotten —
and that "4 loops" as a default (Dory's GGUF ships defaulting to
4) can be actively harmful on some distributions.

### 1.8 Recursive CLIP: looping works for vision encoders too (2026-10-25) — primary (arXiv:2610.34563)
CLIP backbones tolerate substantial recurrent block reuse at fixed
total depth (N blocks × M passes), under both direct training and
distillation; the effect is encoder- and task-dependent.
*Relevance:* our front end is an embedder, not an LLM. If a looped
vision encoder can spend 1 pass on calm tiles and more on contested
ones, embed-seconds themselves become allocatable depth — the
recursive-CLIP result says the architecture family survives the
transplant.

### 1.9 Tiny Autoregressive Recursive Models: a clean negative result (ICLR 2026 workshop paper, circulating in window) — primary
Controlled, compute-matched transformation of a standard
Transformer into an autoregressive TRM: **no reliable gains from
the full AR-TRM architecture**; simpler two-level refinement
baselines did show gains. Authors caution against the direction.
*Relevance:* recursion's wins are concentrated in non-autoregressive
refinement (grids, states, digests) — which is where our refiner
sits — and do not automatically transfer to token generation.
Keeps expectations for any looped *speaker* in the presence stack
at zero until measured.

### 1.10 The exchange rate, priced: φ = 0.46 (Apr 2026, pre-window; the window's discourse kept citing it) — primary (arXiv:2604.21106)
Iso-depth scaling sweep (116 pretraining runs): one recurrence is
worth r^0.46 in equivalent unique parameters. At r=4 a 410M looped
model matches a 580M dense model while paying a 1B model's
training cost. Truncated backprop lowers φ to 0.38;
hyperconnections raise it to 0.65. Framing replicated across three
groups: looping buys *reasoning/application*, not *knowledge*
(282% vs 37% of gap recovered).
*Relevance:* gives our loop-second a defensible exchange rate for
budget arithmetic — depth-by-looping is real, sublinear, and
trainable upward (mHC in SenseNova-Loop is exactly the φ-raising
lever, which may be why it exists).

**Area 1 count: 10 items.**

---

## 2. Weight-space programming — follow-ups to "Sparks" (2026-11-02)

The original post (Takehi, Teoh, Zhang, Khattab) is a **blog post
with fully published logs**, not a peer-reviewed paper — and that
turned out to be the story: the correction cycle ran in ~24 hours
*because* the logs were open.

### 2.1 Hugging Face reproduced it (2026-11-03) — reputable-secondary (reported by Latent Space; HF artefact released)
HF reran the work with its ML Intern research harness and released
the resulting model and a demo.
*Relevance:* moves the core phenomenon from "one lab's blog" to
"reproduced by a second organisation with its own harness" — the
floor of the claim (frontier models can read/write small nets'
weights usefully) is now load-bearing.

### 2.2 Cross-generation replication: the capability is new and generation-bound (Alex Krentsel, 2026-11-03) — reputable-secondary / anecdote
Independent reproduction of the MIT experiments; across model
generations the effect is a **step change in the latest models
only**; latest models' hand-written Breakout networks scored up to
22× the RL-trained baseline.
*Relevance:* if the reader/writer of weights must be a frontier
model of the newest generation, the authoring seat in our governed
patch pipeline is a *cloud* seat for the foreseeable future — the
Thor hosts the patched, not the patcher. Design accordingly.

### 2.3 The same feat on a laptop with open weights (Simon Willison, 2026-11-03) — anecdote (self-reported, detailed log)
Qwen 3.8 27B running locally identified 3 of 4 game networks from
raw weights in ~45 minutes (failed on Freeway).
*Relevance:* a 27B local reader at 3/4 is the first hint the
authoring seat could come on-premise at reduced reliability — the
gap between 3/4 (local) and 4/4 (frontier) is precisely what a
governed propose→verify→deny pipeline exists to absorb.

### 2.4 A cheaper, smaller replication of the headline edit (Zeng Jiajun, reported 2026-11-03) — anecdote
Opus-class model edited **2 neuron output columns** in layer 29 of
Qwen3.5-4B (0.00012% of weights), cutting repetition loops from
22–25 to 0 and lifting held-out correct answers 59 → 92–94, for
about $1 and 27 minutes.
*Relevance:* the effect survives at *two columns*. For our patch
programme this is the shape to copy: minimum-surface edits against
a diagnosed failure mode, verified on held-out items — our Phase
15/16 discipline with an existence proof from outside.

### 2.5 The narrowing: the MATH-500 gain is an unblocking, not an upgrade (Zhihu reconstruction from the published logs, 2026-11-03) — reputable-secondary
Reconstruction shows 576 of 579 "repaired" answers had originally
hit the 32K-token limit *because of looping*; held-out accuracy
rose 10.6% → 60.4% mostly by letting existing reasoning finish.
Convergent critiques (Honnibal, Goedecke, others): early
experiments may ride on spatially-structured first/last layers;
the transformer analysis follows known QK/OV circuit methods; the
abstract composites eight different setups; fitting weights
directly against a benchmark is Goodhart bait.
*Relevance:* matches our own measured map almost line for line —
authored patches harvest completion/format failures and install
readouts; they measure zero on facts and procedure. Any plan that
budgets WSP edits as *capability additions* is now contradicted by
two independent sources plus our own data. See Contradictions.

### 2.6 Hand-written weights for a DOOM route planner (Muninn/Austegard, 2026-11-03) — reputable-secondary (working artefact, blog)
An agent replaced **all** weights of a Tiny Recursive Model route
planner with hand-written numbers (a C. Y. Lee 1961 wavefront
router compiled into the net: 69 of 1,024 hidden units used, the
rest zero) — no data, no gradients; same week, the MIT Qwen edit
was re-staged against an LFM2.5-350M.
*Relevance:* the TRM connection Casey suspected is real and
already being worked in public: small recursive nets are the most
legible weight surface there is, because the same weights are
re-applied every pass — an edit compounds across loops. A looped
refiner is therefore the *most* WSP-addressable component we own.

### 2.7 The benchmark: still missing (as of 2026-11-05) — primary (absence, checked)
The authors floated a benchmark; none has appeared. Claims remain
demo-grade with released logs — unusually auditable demos, but
demos. GDPx (SemiAnalysis) is sometimes mentioned in the same
breath; it is an agent benchmark, not a weight-space one.
*Relevance:* there is no external scoreboard to adopt yet; our
own patch batteries remain the measuring instrument, which is
where the programme already lives.

**Area 2 count: 7 items.**

---

## 3. NVFP4 / FP4 — tooling and evidence

### 3.1 NVIDIA's own measurement: weight-only NVFP4 is SLOWER than BF16 (Model Optimizer QAD post, updated 2026-10-21) — primary (NVIDIA engineering blog with measurements)
On Blackwell + vLLM, W4A16 NVFP4 falls back to dequant-to-BF16
(Marlin) and **loses to BF16 in 10 of 12 shapes**; only W4A4
(activations also FP4) reaches the FP4 tensor cores, beating BF16
in 9 of 12 shapes and shrinking a 35B checkpoint 67 → 22 GiB.
W4A4 PTQ accuracy cost is small and uneven (2 of 6 benchmarks);
500 iterations of Quantization-Aware Distillation recover most of
it (IFBench fully), while changing behaviour shape — SciCode
completions lengthen ~91% at unchanged score and abstention drops.
*Relevance:* **the single most consequential item in this area
for us.** "FP4" is not a speed property; W4A4 is. Any Thor serving
plan that assumes a weight-only FP4 checkpoint buys throughput is
building on the one configuration NVIDIA measured as a regression.
See Contradictions.

### 3.2 TRACE: FP4 RL rollouts matched to BF16 by aligning train and rollout quantisation (2026-10-07, edge of window) — primary (arXiv:2610.07767)
Rollout-guided QAT for MoE RL: FP4 weights/activations/KV rollouts
at BF16-comparable RL outcomes, up to 5.4× rollout speedup claimed
on large MoEs.
*Relevance:* datacenter-scale, but the principle ports: the
quantiser must be inside the training/eval loop that consumes it —
for us, quantise the refiner *with its settle-signal fixtures in
the loop*, not as a post-hoc export step.

### 3.3 Microscaling FP4, measured cold: MR-GPTQ (ICLR 2026, circulating) — primary (arXiv:2509.23202)
First comprehensive PTQ study of MXFP4/NVFP4: NVFP4's 16-element
groups provably neutralise classic outlier mitigation; MXFP4's
power-of-two scales cost accuracy; rotations help MXFP4 and *hurt*
NVFP4 under RTN. Their MR-GPTQ matches or beats SOTA PTQ accuracy.
*Relevance:* the recipe book for producing our own FP4 checkpoints
of small refiners — and a warning that techniques imported from
INT4 practice (rotations, outlier tricks) do not transfer by
default.

### 3.4 llama.cpp FP4 kernels: landed for Blackwell — in April (surfaced via a DGX Spark ops ADR, Aug–Oct) — primary (PR record) + anecdote (ADR)
PR #22196 (merged 2026-04-28) added an NVFP4 MMQ kernel benchmarked
on GB10; a production operator nonetheless reverted a DGX Spark
deployment from vLLM-NVFP4 back to llama.cpp K-quants because no
published NVFP4 GGUF existed for their models. Separately, forum
reports (Mar 2026) describe NVFP4 checkpoints blocked "at the
kernel level" on Spark under vLLM.
*Relevance:* kernels existing ≠ checkpoints existing ≠ our
architecture supported. For sm_110 the honest status is: GGUF
K-quants are the proven path today (our Dory study's conclusion
stands); NVFP4-native serving is a watch item, not a plan.

### 3.5 Dory's own serving support: still unmerged (checked 2026-11-05) — primary (GitHub PRs)
llama.cpp PR #30306 remains open (draft-review friction in
October over unrelated CUDA-backend changes; the diff circulates
as an apply-it-yourself patch — 17 files, +507/−9 — and at least
one downstream project ships it that way). vLLM PR #60149 open, no
approvals; a maintainer asked for Transformers support first and
the author declined. A community MLX port exists (Apple-only).
*Relevance:* unchanged from STUDY-DORY: the smoke build from the
PR branch (or the extracted patch on stock llama.cpp, which is
new and slightly cleaner) is still the gateway task; nothing in
the window removes it.

### 3.6 FP4 becomes a default release format at the top end (2026-10-15 → 10-29) — primary (model cards)
Meta's Muse Spark Open (10-15) and Mistral Large 4 (10-29) both
ship official NVFP4 variants alongside BF16; Kimi K3.1 Pro
(2026-11-04) ships MXFP4. vLLM v0.22.0 lists NVFP4 fused-MoE work.
*Relevance:* the format war is over at the checkpoint level —
future looped checkpoints (a Dory successor, an LFM) will arrive
FP4-native. The bottleneck is edge runtimes, i.e. precisely the
layer we control on the Thor.

**Area 3 count: 6 items.**

---

## 4. Liquid networks / CfC / continuous-time models

The honest headline: **no major CfC result landed inside the
window.** The area moved at its product edge instead.

### 4.1 LFM3: Liquid AI's third generation (late Oct 2026) — reputable-secondary (release roundups of Liquid's blog/cards)
Six models from one 1.73B base (text, VL, audio, omni + two
decision models), tri-hybrid architecture (gated short
convolutions + sliding-window + global attention), 22T tokens,
256K context; vendor-claimed to beat Qwen3.5-9B on agentic tasks at
~1 GB in 4-bit; **zero-day llama.cpp support**, licence is
revenue-capped (not open source). Note: LFM3 is a hybrid
architecture, not a CfC network — the "liquid" lineage is now a
brand over conventional-ish sequence modelling.
*Relevance:* our candidate resident models get cheaper and better,
but anyone citing LFM3 as evidence about *continuous-time*
dynamics is trading on the name. The CfC integrator in our cascade
stands or falls on event-stream evidence, not on Liquid's release
cadence.

### 4.2 CfC vs LSTM across event/clinical streams (preprint, pre-window, still the freshest direct comparison) — primary (arXiv:2605.27467)
Benchmarks CfC against LSTM on N-MNIST (event data), QuickDraw,
IAM handwriting and PhysioNet sepsis: CfC's edge concentrates in
**parameter efficiency and robustness under sparsity/temporal
dropout** — i.e. exactly the gappy, irregular regime — not in
headline accuracy on dense sequences.
*Relevance:* independent support for the narrow claim our design
actually makes: the liquid layer earns its seat *between*
observations, over wall-clock gaps — not as a general sequence
model.

### 4.3 Stochastic CfC: the closed form is the deterministic limit (Aug 2026, pre-window) — primary (arXiv:2608.28702)
Reinstating a noise term on the CfC time gate (SDE generalisation)
recovers robustness properties the closed form drops, in dynamic
3D reconstruction.
*Relevance:* if our integrator ever shows brittle behaviour at
feed-gap re-entry (the soak's gap transients are the test case),
the stochastic gate is the named candidate fix — filed, not
scheduled.

**Area 4 count: 3 items (and one explicit gap).**

---

## 5. Streaming/rolling perception and edge inference on Jetson-class hardware

### 5.1 TensorRT Edge-LLM matures into the Thor's production runtime (tutorial 2026-10-30; MLPerf result Sept, in window discourse) — primary (NVIDIA blog)
Edge-LLM 0.11.1: one runtime spanning DGX Spark development →
Jetson/DRIVE/IGX Thor deployment, OpenAI-compatible local API,
DSpark speculative decoding lifting HumanEval generation
73.4 → 126.9 tok/s (vendor-measured, Spark). In MLPerf Inference
v6.1 Edge Agentic, Edge-LLM on **one AGX Thor** ran Qwen3.6-27B at
52.33 tok/s, finishing the 1,007-turn workload in 24m36s vs
2h37m for the llama.cpp reference — **6.4×** (vendor submission,
MLPerf-audited process).
*Relevance:* threatens our llama.cpp-first serving habit, not our
architecture: for any *dense* resident model on the Thor, NVIDIA's
runtime is now the measured front-runner. It does not run looped
architectures (Dory) — so the likely end-state is split serving:
Edge-LLM for dense residents, PR-build llama.cpp for the looped
refiner. Budget both.

### 5.2 JetPack 7.2.1 / DeepStream 9.1: the platform consolidated (JetPack 7.2.1 dated 2026-08-11; pairing current in window) — primary (NVIDIA)
Current stack: Jetson Linux 39.2.1, CUDA 13.2.2, TensorRT 10.16.2,
DeepStream 9.1 (first 9.x to restore Orin support; unified GitHub
monorepo; multi-view 3D tracking + auto-calibration as "agentic
skills"). Forum reports in the window include a confirmed fix for
live-RTSP frame corruption on AGX Thor under 9.1 (explicit rtspsrc
chain over uridecodebin).
*Relevance:* our hand-rolled ingest (the soak's pusher/receiver)
now has a vendor-maintained counterpart at the same JetPack level
we already run; the RTSP corruption note is the kind of defect
that would present as *our* freshness bug — worth one comparison
run before the next soak, not a migration.

### 5.3 OneStreamer: memory as captions written during capture (Oct 2026) — primary (arXiv:2610.01762, via authors' repo)
A 4B streaming video model writes timestamped captions as video
plays and answers later **from the text only**: on a 6-minute clip,
62,094 context tokens → 4,308, 25 GB → 10 GB, time-to-first-token
4.56 s → 0.12 s (H200-measured — datacentre, not edge).
*Relevance:* independent convergence on our ledger doctrine from
the streaming-VLM side: the durable artefact of perception is a
text record written *as it happens*, queried as text. Their
captioner cost at the edge is unmeasured (their own gap) — which
is the half we have already paid for and measured on the Thor.

### 5.4 Event-SAMA: language-grounded segmentation on event streams (2026-10-29) — primary (arXiv:2610.39676)
First event-native referring-segmentation baseline (24.37 vs RGB
55.4 on MeViS — event side is well behind) plus a 239K synthetic
event corpus converted from RGB data.
*Relevance:* the change-only sensor remains academically alive
but practically behind; our diff-gating over ordinary frames keeps
its cost advantage without the sensor swap. Filed as a watch item
for the day an event camera is ever on the bench.

### 5.5 Calibration data point: Thor vs DGX Spark, same llama.cpp build (Oct 2026 comparison) — reputable-secondary
Spark leads Thor ~1.9× on prompt processing and 1.1–1.4× on
generation in the only public same-build runs; NVIDIA's own Thor
figures use vLLM at 8 concurrent requests. Thor's 2,070 FP4
TFLOPS is a *sparse* (2:4) peak production checkpoints don't meet.
*Relevance:* keeps our loop-second arithmetic honest — plan
budgets from single-stream measured rates on our box, never from
peak-TFLOPS marketing, ours included.

**Area 5 count: 5 items.**

---

## Shortlist — the three deepest studies worth commissioning

1. **TaH2 and the learned loop governor (1.5, with 1.4 and 1.7).**
   Our cascading-allocation thesis now has a published neighbour
   with a training recipe (lookahead labels) and a failure taxonomy
   (PAR's unshaped iterations; LoopCoder's loop-3 collapse). A
   study that maps their decider onto our loop receipts — what our
   ledger already records that could serve as labels — is the
   highest-leverage paper work available.
2. **The WSP replication cluster, read as one experiment (2.1–2.5).**
   HF's reproduction, Krentsel's generation-boundary, Willison's
   local 3/4, Zeng's two-column edit, and the Zhihu narrowing
   together draw the capability's real outline — and it matches our
   Phase 15/16 map. A single study reconciling all five against
   our patch batteries would settle what the governed authoring
   seat may and may not be asked to do.
3. **W4A4-or-nothing: NVIDIA's NVFP4 measurements (3.1, with 3.3).**
   Before any FP4 serving decision on the Thor, reproduce the
   shape of NVIDIA's result at our scale: W4A16 vs W4A4 vs K-quant
   on one resident model, accuracy *and* behaviour-shape (length,
   abstention) scored. It decides the refiner's serving format and
   it is a bench-week, not a paper-quarter.

## Contradictions — assumptions this window's evidence threatens

- **"FP4 quantisation buys speed."** Threatened by 3.1 (NVIDIA's
  own numbers): weight-only NVFP4 is *slower than BF16*; only W4A4
  reaches the tensor cores, and QAD recovery measurably changes
  output shape (length, abstention) even where scores recover.
  Any budget that prices an FP4 checkpoint at BF16 accuracy and
  >BF16 speed, unmeasured, is now against the vendor's evidence.
- **"More loops, more accuracy — set the dial high."** Threatened
  by 1.7 (loop-3 collapse), the Dory card's own peak-and-fall rows,
  and priced by 1.10 (φ = 0.46, sublinear). The surviving form of
  the assumption is the charter's: loops are a *metered, allocated*
  resource with per-workload receipts — fixed-high is falsified.
- **"A settle signal will emerge from loop dynamics on its own."**
  Threatened by 1.4: without progress-aligned training, extra
  iterations don't track progress at all. Our D2 experiment (do
  per-pass deltas contract measurably?) is now the load-bearing
  test of the whole cascading idea, not a formality.
- **"Weight edits can add capability."** Threatened by 2.5 and
  convergent with our own Phase 15/16 measurements: every verified
  WSP gain so far is an *unblocking* (completion pathology removed)
  or a *readout installed where separation already existed*. The
  authoring seat's charter should be written in those verbs only.
- **"llama.cpp is the Thor serving default."** Threatened by 5.1:
  for dense models, TensorRT Edge-LLM's audited 6.4× over the
  llama.cpp reference on our exact hardware ends the default.
  Looped architectures remain llama.cpp-PR territory — plan a
  split serving stack, not a single runtime.
