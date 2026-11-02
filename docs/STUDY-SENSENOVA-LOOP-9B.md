# STUDY — SenseNova-Loop-9B-Preview as a candidate component

Lane LOOP-9B STUDY, 2026-11-02. Study only: nothing was downloaded,
nothing on the Thor was touched. Facts below come from primary
sources — the Hugging Face model card / repo metadata for
`sensenova/SenseNova-Loop-9B-Preview` (read in full, 2026-11-02) —
and are labelled as such. Press coverage (TechNode, and the
secondary write-ups that quote the same vendor chart) is used only
where marked. Anything not confirmable from a primary source is
marked **UNVERIFIED** rather than repeated.

## Deficits first

- **There is no serving path this house can use today.** The
  incumbent brain runs as a GGUF under llama-server. Loop-9B ships
  as BF16 safetensors behind `trust_remote_code` custom code;
  vLLM and SGLang support exist only as **unmerged PR branches**
  (vLLM #64832, SGLang #47281, both named in the card itself), and
  the card's LightLLM example is a 4-GPU tensor-parallel setup.
  The only GGUF in existence is an unofficial third-party
  conversion that requires **three patches on a pinned llama.cpp
  commit** — stock llama.cpp will not load this model.
- **The loop count is not a knob.** The card states the loop range,
  pass count and mHC routing parameters are part of the checkpoint's
  *execution configuration*, which a compatible implementation
  "must load … and reproduce the same execution order." No
  inference-time loop control is documented anywhere in the card.
  The fine-tune script is literally named `mhc2_loop2_titan.sh` —
  2 passes is a training-time decision, not a runtime dial. This
  kills the most interesting idea (loops as budget currency) for
  this artefact; see seat (c).
- **Every performance number is the vendor's.** The benchmark
  results live in a chart image on the card (not machine-readable
  text); the technical report is listed as **TBD**; at least one
  charted benchmark (RaccoonPPTBench) is named for SenseTime's own
  Raccoon product line. No third-party reproduction existed at
  study time.
- **"9B" is the flattering number.** The card's own accounting is
  ~9B stored parameters but **~14.6B "inference parameters"** —
  i.e. per-token compute comparable to a dense ~14.6B model, from
  56 layer executions per forward pass. Against the presence
  incumbent (a 3B-active MoE measured at 65 tok/s on the Thor),
  expect materially fewer tokens/s at similar resident size.
  No Thor-class throughput figure exists anywhere (UNVERIFIED
  either way — but the arithmetic direction is not in doubt).

## 1. Verified facts (primary sources)

Source for everything in this section unless noted: the model card
and repo metadata at `sensenova/SenseNova-Loop-9B-Preview`,
accessed 2026-11-02.

### Architecture — how the loop is wired

| Property | Value (per card) |
|---|---|
| Architecture | Autoregressive multimodal decoder; looped block with two-stream mHC |
| Input / output | Text + images in / text out |
| Distinct decoder layers | 32 |
| Looped block | Layers **[4, 28)** — 24 layers — executed **2 passes**, shared weights |
| Layer executions per forward pass | **56** (= 4 head + 24×2 loop + 4 tail) |
| mHC | 2 residual streams; learned read/mix/write mappings; Sinkhorn normalisation, 20 iterations |
| Attention | Hybrid: each 4-layer group = 3 linear-attention + 1 full-attention; loop boundaries align to whole groups, so the pattern is identical on both passes |
| Hidden / FFN | 4,096 / 12,288 |
| Full-attention heads / KV heads | 16 / 4 (GQA) |
| Vocabulary | 248,320 |
| Scale | ~9B total parameters; ~14.6B "inference parameters" (vendor's compute-equivalence figure) |
| Export precision | BF16 backbone; **FP32 mHC routing parameters** |
| Training context | Up to **262,144** tokens |
| Acceleration | MTP available; DSpark and DFlash2 "training in progress" |

The computation is written on the card as **B(B(h))**: layers 0–3
process the input, the block B (layers 4–27) is applied twice in
sequence — the second pass consumes the first pass's output — then
layers 28–31 and the output head finish. The TechNode framing
("24 layers run twice") is correct about the block but the honest
total is 56 executions from 32 stored layer weight sets.

**Fixed or variable?** Fixed. Two passes, baked into the
checkpoint's execution configuration (see Deficits). No
generation parameter, config field, or serving flag for loop count
is documented in the card, the Transformers example, or any of the
three deployment recipes. Whether the custom code would tolerate a
patched pass count is UNVERIFIED — and the model was trained at
exactly 2 passes (the mHC routing included), so off-count runs
would be off-distribution by construction.

**Thinking mode:** the card's chat-template example exposes
`enable_thinking=True/False`. Noted because this house has a
measured failure mode here: Qwen3-0.6B spent its whole budget in
`reasoning_content` and returned empty content at presence
settings (BRAIN-BENCH). Any future battery must pin thinking off
and verify content actually returns.

### Training recipe (what is actually published)

- Documented recipes combine text, images, code and **tool-use
  trajectories** as supervised data, at sequence lengths up to
  262,144 tokens. No mixture proportions, token counts, or
  loop-specific training procedure are published — the technical
  report is TBD, so *how the loop itself was trained* (from
  scratch at loop-2? curriculum over counts?) is **UNVERIFIED**.
- Fine-tuning guidance is real and public: an OpenSenseNova
  torchtitan fork with a single-node 8-GPU script
  (`mhc2_loop2_titan.sh`); the card links a training guide covering
  configuration, DPO and MTP training, and a separate SenseSpec
  repo for training DSpark/DFlash2 draft models.
- Checked inference environment: **Transformers 5.18.0, PyTorch
  2.11.0, CUDA 13.0**, `trust_remote_code=True`.

### Benchmarks — all vendor-claimed

The card charts eight benchmarks: BIRD-Dev, WorkBuddy Bench,
AIDABench, TeamBench, Terminal Bench 2.1, T³-Banking,
AutomationBench, RaccoonPPTBench. The figures exist only as a
chart image; the following numbers come from press reporting of
that chart (TechNode / TechCityAuthority, 2026-10-30→11-02) and
are **vendor-claimed, not third-party measured**:

| Benchmark | Loop-9B | Qwen3.5-27B (per vendor chart) |
|---|---|---|
| WorkBuddy Bench | 66.89 | 60.53 |
| RaccoonPPTBench | 70.70 | 59.08 |
| AutomationBench | 13.72 | 10.17 |

Vendor summary claim: "27B-class results on complex tasks."
Numeric values for the other five charted benchmarks are
UNVERIFIED (locked in the chart image). Note also that several
charted benchmarks are agentic/office suites aligned with
SenseTime's own product line — the comparison set is the vendor's
choice, on the vendor's home ground, with no independent run.

### Weights, formats, licence

- **Licence: Apache License 2.0 — confirmed from the repo
  itself**: the HF metadata header declares `license: apache-2.0`
  and the card's License section links the Apache 2.0 text. This
  matters here: it is a clean contrast with I-JEPA, which the
  fleet uses for research evaluation only (its licence is not
  commercial — FINDINGS-CFC-JEPA-V2).
- Official format: BF16 safetensors + FP32 mHC parameters, custom
  code in-repo. No official GGUF, AWQ, or NVFP4 export exists.
- Repo size: the card states no byte size. Arithmetic floor for
  ~9B params at BF16 is ≈18 GB before the vision tower and FP32
  routing parameters. A secondary write-up reports a ~38.2 GB
  total repository; **UNVERIFIED** against the HF file listing.
- The vision tower's identity is not named in the card. A
  third-party GGUF conversion describes it as a Qwen3.5 vision
  tower + merger — **UNVERIFIED** from SenseTime sources.
- An unofficial GGUF (Q4_K_M text + F16 projector) exists
  (third-party, requantised from a Q8_0 conversion, mHC/routing
  tensors kept F32) but requires the patched llama.cpp described
  in Deficits. It is not a serving path, it is a research project.

## 2. Seat-by-seat fit

### (a) Presence / platform BRAIN — verdict: **study-only**

Incumbent: Qwen3-Coder-30B-A3B Q4_K_M, 18.6 GB GGUF, measured
65 tok/s on the Thor, and — the actual bar — the only benched
model that grounded every content question on the BRAIN-BENCH
battery, refused the trick question with its reasoning shown,
quoted health figures exactly, and tracked a pronoun across
turns. Presence v2 then passed 7/7 through the full voice loop
behind digest-v2 discipline.

Loop-9B brings no evidence against that bar, and three strikes
before evidence is even the question:

1. **Serving.** It cannot be served by the house's stack at all
   (Deficits). A brain appointment would start with adopting a
   PR-branch inference server or a patched llama.cpp fork —
   integration debt the incumbent does not carry.
2. **Cost per token.** 56 layer executions ≈ dense-14.6B compute
   per token vs the incumbent's 3B active. The brain is not the
   presence loop's bottleneck today (TTS is), but a standing
   tenant that costs ~5× the incumbent's per-token compute to
   answer digest questions needs a quality reason, and none is
   measured.
3. **Its headline strengths are aimed elsewhere.** 262K context
   and document understanding serve a digest that is ~1–2K
   tokens of structured text. The context window is 100×
   oversized for the seat.

**Does multimodal input change anything? No — and the reason is
architectural, not preferential.** Presence is ledger-first by
design: the brain reads a text digest of published verdicts, and
since v3 its factual sentences are checked clause-by-clause
against that digest before TTS (verdict-only grounding,
SPEC-PANEL lineage; claim checker 23/23 unit traps). Feeding the
brain raw frames would route around the claim checker, put a
generative model upstream of the ledger's account of the world,
and break the platform's constitution that perception is
diff-gated JEPA work and the brain is a gauge consulted over
text (SPEC §1.1, §B). The one place image+text could earn a
look is a *different* seat — an on-demand "show me / what is
this" consult in the console/serve plane, over a frame the user
explicitly asks about. That is a reflective-tier consult, not
the presence brain, and it is study-only speculation until a
use case asks for it.

**The battery it would have to pass to earn a trial** (all of
it, no partial credit — this is the earn-the-seat rule that
already deposed one judge in this project):

1. BRAIN-BENCH verbatim: the same 6 questions, same fixture
   digest, presence production conditions (persona, temp 0.3,
   thinking pinned OFF, content verified non-empty). Pass =
   G on (a) dock event, (c) embed figures quoted exactly,
   (d) shelf, (e) pronoun follow-up; refusal-with-reason on
   (b) the ladder trick; and on (f) — under digest v2, where
   staleness is pre-computed into words — surfacing
   NOT REPORTING, never concluding calm.
2. Zero invented numbers across the battery (the LFM2 failure:
   a plausible fabricated "50 milliseconds" with the true
   figures in its prompt).
3. Brevity under the house fence: answers that survive the
   ≤60-token cap + 2-sentence pre-TTS trim without losing the
   grounded content (the incumbent's known weakness is
   briefing-tone; a challenger that is *more* verbose loses
   even if it grounds).
4. Then the presence v2/v3 batteries through the real loop:
   7/7-class voice-loop run and the claim-checker trap set,
   with violations counted, not vibes.
5. Serving conditions measured on the Thor, not quoted:
   tok/s and 40-token wall under the production prompt, resident
   footprint, detached-service operation with its own port and
   a ledger heartbeat — silence from the brain must not look
   like calm either (BRAIN-BENCH condition 4).

Until a download is authorised and that battery is run, there
is nothing to decide: the incumbent holds the seat on measured
evidence, and Loop-9B holds a press chart.

### (b) EMBEDDER behind telltape's seam — verdict: **no**

The seam's contract is a JEPA-shaped thing: a fixed-dimension
embedding per tile crop, stable enough geometry that distance
against a per-tile baseline is a calibrated change signal,
cheap enough to spend by the thousand. Measured incumbent:
I-JEPA, 1,280-dim, p50 173 ms per tile via the JEV rack;
diff-gating cut spend 54% (312 vs 576 embeds) *at that price*.
The platform meters perception in embed-seconds (SPEC §B)
precisely because embeds are the scarce currency.

Loop-9B fails the contract on every axis:

- **No embedding story exists in the primary sources.** No
  embedding endpoint, no pooling head, no retrieval/similarity
  benchmark, no documented hidden-state extraction recipe. It
  is an autoregressive text generator; "take a hidden state and
  hope" is not an embedding story.
- **The theory points the other way.** Per arXiv:2610.39302
  (Balestriero & LeCun), next-token prediction is a JEPA with
  *bad views* — decoder-LM representations are the inefficient,
  poorly-aligned route to the representation geometry a change
  gate needs, next to an encoder trained on joint-embedding
  prediction. Our own record agrees from the measurement side:
  the sheaf-refined JEPA pipeline hit precision 1.00 at recall
  1.00 on the wave-3 battery; nothing decoder-shaped has ever
  been measured in that seat.
- **Cost is disqualifying on its own.** Even at an optimistic
  ~1 s per tile forward (56-layer multimodal decoder, image
  tokens included), embedding everything is ~6× the I-JEPA
  price per tile before accuracy is discussed — spent against
  a budget whose whole point is that the reflex tier exists
  to avoid exactly this.
- The one honest point in its favour is licence: Apache 2.0
  vs I-JEPA's research-only terms. A clean licence for a tool
  that cannot do the job is not a candidacy. If a future
  pooled-representation proposal wants this seat reopened, the
  bar is the wave-3 battery — precision/recall against the
  refined pipeline's 1.000/1.000 at competitive embed-seconds —
  and the prior from the bad-views result is that it will not
  clear it.

### (c) The CONCEPT seat — verdict: **study-only** (real kinship, no usable control)

The kinship is genuine and worth stating precisely, because it
is the reason this model is interesting to this project at all.
Our substrate's thesis is that **iteration of a shared operator
beats width**: the rolling cascade re-applies perceive→refine
over arriving time instead of batching (10.39× TTFO at identical
work); the sheaf refine applies the *same* Laplacian operator
repeatedly to a tile field and watches energy settle
(132.75 → 95.97 in the cascade measurement; precision
0.60 → 1.00 in the ablation); the CfC finding adds a small
learned iterator over JEPA latents at 1.1 ms/gap whose surprise
leads frame diffs. Loop-9B is the same bet inside a transformer:
one block of weights, applied twice, depth bought with
repetition instead of parameters — with mHC as the learned
analogue of our refine step's mixing (two residual streams,
learned read/mix/write, constrained by Sinkhorn normalisation,
where our refine mixes neighbour tiles under a fixed operator
with a measured energy).

The differences are as instructive as the kinship:

- **Our iterations are adaptive and metered; theirs are fixed
  and fused.** Sheaf refine runs against an energy reading —
  settle is observable, so iteration count can in principle
  follow the signal. Loop-9B's count is 2, chosen at training
  time, invisible at inference. There is no settle signal to
  read and no dial to turn.
- **Ours iterate over a spatial/temporal field; theirs over a
  representation.** Same algebra of reuse, different operand.

**What we would measure if loop count became a budget
currency** (specified now, executable only on an artefact that
exposes the count — this one does not):

- Battery: the BRAIN-BENCH 6-question set + the presence
  claim-trap set, frozen, at loop counts 1 / 2 / 3 (3 being
  off-training-distribution for this checkpoint — itself a
  datum).
- Axes: grounding score (G/P/H per question), claim violations,
  wall time and a *loop-second* unit (one full block pass over
  the production prompt) as the spend currency, mirroring
  embed-seconds.
- The settle test, imported from sheaf refine: measure the
  representational delta between successive passes
  (‖h₂−h₁‖ vs ‖h₃−h₂‖). If pass-3 delta ≈ 0 while pass-2 delta
  is large, a convergence signal exists and an adaptive-depth
  rule ("spend loops until settled") becomes a real design —
  the learned counterpart of our energy threshold. If deltas
  do not contract, depth-as-currency is a fixed tax, not a
  dial, and the concept seat closes.
- Decision rule: loops earn budget-currency status only if
  quality-vs-loops is monotone *and* the settle signal
  predicts the quality gain; a flat quality curve at 2× cost
  is the expected outcome for a checkpoint trained at exactly
  2 passes, and would confirm the fixed design.

Verdict: the concept is a validated relative — SenseTime
independently bet a flagship release on iteration-over-width,
which is evidence for the substrate's founding intuition. But
as a component it offers no control surface, and the
nearer-term learned-iterator work in this house remains the
CfC-over-JEPA-latents line (post-soak-verdict, on Casey's
word — FINDINGS Finding 3), not a 9B decoder.

## 3. Cost reality (no download taken or proposed)

- **Download size:** ≈18 GB arithmetic floor (BF16); ~38.2 GB
  as reported secondarily for the full repo (UNVERIFIED). Either
  figure is 20–43% of the Thor's ~89 GB free disk — for a
  study-only artefact with no seat. Under the house's standing
  rule (and the cancelled-27B precedent: disk headroom is spent
  on things with a measured job), this study recommends **no
  download** unless Casey names the battery in §2(a) as worth
  running.
- **Memory fit:** BF16 resident ≈19–20 GB plus KV cache —
  inside the Thor's 122 GiB unified memory (~88 GB available at
  brain-bench time) and comparable to the incumbent's 18.1 GB
  resident. Memory is not the blocker; at production-length
  contexts the KV bill is modest. (At its 262K training
  context the KV cache would be a different story — irrelevant
  to any seat here.)
- **Serving stack required:** one of — Transformers 5.18.0 +
  PyTorch 2.11.0/CUDA 13.0 with `trust_remote_code` (the card's
  single-GPU example is the only recipe that maps onto a
  one-GPU Thor; whether the pinned torch build exists for this
  aarch64/sm_110 box is UNVERIFIED); LightLLM (card example is
  tp 4 — single-GPU operation UNVERIFIED); PR-branch builds of
  vLLM or SGLang; or the unofficial patched-llama.cpp GGUF.
  Every route is new infrastructure next to the house's
  llama-server pattern, and a resident deployment would
  additionally need a thor-admit lease like every other
  multi-GB tenant.

## 4. Risks

- **Preview maturity is in the name and in the artefacts:**
  technical report TBD; the card itself was still being edited
  hours before this study ("docs: consolidate speculative
  decoding training instructions"); two of three serving paths
  are unmerged PRs; DSpark/DFlash2 unfinished; the card
  simultaneously ships a Transformers example and lists the
  "Transformers inference implementation" as *publication
  details to be announced* — the documentation has not settled.
- **Vendor-claim inflation, structurally:** the only primary
  source is the vendor; the benchmark evidence is a chart
  image of vendor-run suites, several aligned with the
  vendor's own products; the "~14.6B inference parameters"
  framing cuts both ways (it inflates the capability story
  *and* understates the 9B headline's compute cost). Nothing
  here has survived contact with a third party yet.
- **Single-source everything:** architecture, training, and
  scores trace to one model card. The loop's training
  procedure — the part a study would most want — is the part
  not yet published.
- **Off-distribution traps if ever trialled:** the thinking
  toggle (empty-content failure mode is measured in this
  house), FP32 mHC tensors that quantisation must not touch
  (the third-party GGUF keeps them F32 for a reason), and a
  pass count that must not be "adjusted" in config and assumed
  equivalent.

## Bottom line

Loop-9B is a well-licensed, genuinely interesting proof that
iteration-over-width scales — filed as **study-only** for the
brain and concept seats and **no** for the embedder seat. It
earns a trial only through the door every other model in this
project used: a named battery, run on the Thor, against the
incumbent's measured record. Nothing about it changes any
current appointment.

*Sources: HF model card + repo metadata for
`sensenova/SenseNova-Loop-9B-Preview` (accessed 2026-11-02);
TechNode 2026-11-02 and TechCityAuthority 2026-10-30 (press,
vendor-chart figures labelled above); the unofficial GGUF repo
`annelo/SenseNova-Loop-9B-Preview-Q4_K_M-Vision-GGUF`
(third-party, for serving-path facts only). Local records:
slice2/BRAIN-BENCH.md, docs/RESULTS.md, docs/FINDINGS-CFC-JEPA-V2.md,
docs/SPEC-STREAM-PLATFORM.md.*
