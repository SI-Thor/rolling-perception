# STUDY — NVIDIA Nemotron-Labs Dory1.0-4B as a candidate component, and an experiment charter for cascading loop allocation

**Status (2026-11-06):** the taps experiment chartered here has run; the full result is [DORY-TAPS.md](DORY-TAPS.md) — per-pass deltas contract strongly but uniformly and do not separate delivered from undelivered runs, so the internal settle signal is outcome-blind and loop allocation goes to an external/learned governor.

Lane DORY STUDY, 2026-11-05. Study only: nothing was downloaded,
nothing on the Thor was touched. Facts below come from primary
sources — the Hugging Face model card and `config.json` for
`nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-BF16` (read in full,
2026-11-05), the HF API file listings for the BF16 / MXFP8 /
NVFP4 / GGUF repos, and the GitHub API records for the two
serving PRs — and are labelled as such. Every benchmark number
attributed to Dory is **NVIDIA's own** (NeMo Gym / NeMo Evaluator
harness, BF16 checkpoint) unless a sentence says otherwise. The
only independent measurements found are two single-operator
runs (an RTX 3060 YouTube test and an M4 blog post); both are
cited as **anecdote-grade** wherever used. Anything not
confirmable from a primary source is marked **UNVERIFIED**.

## Deficits first

- **There is no merged serving path today.** Dory support is an
  **open** PR in llama.cpp (ggml-org/llama.cpp#30306, state
  `open`, `merged_at: null` per the GitHub API, last updated
  2026-11-02) and an **open** PR in vLLM
  (vllm-project/vllm#60149, still in review; auto-merge was
  disabled on it 2026-10-24). The card's llama.cpp recipe builds
  a **fork** (brianchmielNV/llama.cpp, branch `dory-support`)
  pinned to revision `98a74c97ea09ac72f6ceda1559808fc0a2f447ce`,
  and its build instructions are written for macOS/Metal. The
  card's vLLM recipe is `pip install` from the PR ref. Stock
  llama.cpp will not load this model.
- **The loop dial exists, but it is a launch-time constant.**
  This is the sharpest contrast with SenseNova Loop-9B
  (STUDY-SENSENOVA-LOOP-9B), whose pass count is fused into the
  checkpoint: Dory exposes loop count as configuration
  (`n_recurrent_loops`, 1–4) in both serving stacks. But in
  every documented recipe it is set **once, when the server
  starts** — vLLM `--hf-overrides`, llama-server
  `--override-kv`. No per-request, per-token, or per-frame loop
  control is documented in the card or either PR as read.
  NVIDIA's "elastic inference compute" is elasticity *across
  deployments*, not within a stream. Our programme's thesis —
  depth allocated per frame/tile by a settle signal — is
  therefore a build project on top of this artefact, not a
  flag. §3 is written with that gap stated, not elided.
- **Every performance number is the vendor's, and for BF16.**
  The benchmark table was measured by NVIDIA under NVIDIA's
  harness on the BF16 checkpoint. The artefact this house would
  actually run is the Q5_K_M GGUF; no vendor number exists for
  it. The two independent runs that exist are single-operator
  anecdotes (below).
- **Dory is text-only.** Input type on the card: Text. There is
  no vision tower, no image input, no embedding endpoint. It
  cannot sit in the perceptual path where I-JEPA sits, and any
  "Dory perceives the harbour" framing would be false. Its
  candidacy in this programme is one tier up: a *refiner over
  text* — digests, event descriptions, claims — where the loop
  dial could meter reflective compute the way embed-seconds
  meter perceptual compute.
- **`last_loop` KV mode is not a free lunch and not numerically
  neutral.** The llama.cpp PR body states it plainly:
  last-loop caching "changes predictions compared with separate
  caches, and prefill chunk size matters." Any experiment that
  compares loop counts under `last_loop` must pin prefill chunk
  size or the comparison is confounded; any deployment that
  flips the mode changes the model's answers, not just its
  memory bill.
- **Over-looping already regresses inside the vendor's own
  table.** GPQA Diamond: 69.19 → **72.41** → 72.16 (peaks at 2
  loops, falls at 4). HLE: 8.25 → **10.89** → 10.43 (same
  shape). AA-Omniscience is flat (10.03 / 10.08 / 10.03) —
  loops add compute, not knowledge. "More loops" is not
  monotone even on NVIDIA's home ground; §3 names this the
  charter's standing risk and designs a hunt for it.

## 1. Verified facts (primary sources)

Source for everything in this section unless noted: the model
card, `config.json`, and HF API metadata for
`nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-BF16` and its sibling
repos, accessed 2026-11-05.

### What it is

| Property | Value (per card / config) |
|---|---|
| Architecture | Looped (latent-recurrent) normalised-GPT (nGPT), `DoryForCausalLM` |
| Input / output | Text in / text out. English only (per card) |
| Stored parameters | 3,975,229,440 (≈4B) |
| Hidden size / vocab | 2,560 / 131,072 (embeddings untied) |
| Attention | Interleaved sliding-window (window 1,024) and full attention; 16 Q heads, 4 KV heads, head_dim 256 |
| Context | Up to 262,144 tokens (card: validated 256K) |
| Release | 2026-10-16, version GA (10/16/2026) |
| Licence | **OpenMDW License Agreement v1.1**; card states "ready for commercial or non-commercial use"; repos are ungated |
| Training | 6T tokens pre-training — **NVFP4 for the first ~4.5T, BF16 for the remainder** — plus 300B context-extension; SFT; GRPO RL (Megatron-LM / NeMo RL) |
| Reasoning | Always on in vLLM; `--reasoning on` in llama.cpp; vendor-recommended sampling temp 1.0, top_p 0.95 |

The NVFP4 point deserves one careful sentence: "native NVFP4
pre-training" is the vendor's claim about its own recipe —
the first ~4.5T of 6T tokens were trained with weights in
NVIDIA's 4-bit float format before continuing in BF16. It is
a training-provenance fact from the card, not a performance
claim, and nothing in this study depends on it beyond noting
that the NVFP4 *checkpoint* (below) descends from a model that
was born at 4-bit rather than quantised down to it.

### Weights, formats, sizes (HF API file listings, 2026-11-05)

| Repo | Weight file | Bytes |
|---|---|---|
| `…-Dory1.0-4B-BF16` | `model.safetensors` | 7,950,515,472 |
| `…-Dory1.0-4B-MXFP8` | `model.safetensors` (W8A16) | 4,750,755,304 |
| `…-Dory1.0-4B-NVFP4` | `model.safetensors` (W4A16) | 3,202,498,032 |
| `…-Dory1.0-4B-GGUF` | `NVIDIA-Nemotron-Labs-Dory1.0-4B-Q5_K_M.gguf` | **3,673,288,864** |

The official GGUF repo contains exactly **one** quant —
Q5_K_M — and nothing else. The card publishes its SHA-256
(`96080be4…a660e0`) and expected byte size; the file in the
repo matches the stated size exactly. No official Q4_K_M file
exists (the llama.cpp PR reports testing q4_k_m conversions,
so one can be produced with the PR's converter — a conversion
we would have to run and verify ourselves).

### Benchmarks — all vendor-claimed

NVIDIA-measured, BF16 checkpoint, NeMo Gym / NeMo Evaluator
SDK harness, from the card's table. Reproduced in full because
the *shape across loop counts* is the datum this programme
cares about:

| Task | 1 loop | 2 loops | 4 loops | Qwen3.5-4B | Qwen3.5-9B |
|---|---|---|---|---|---|
| SciCode | 27.3 | 34.94 | 35.11 | 25.82 | 28.21 |
| SWE-bench Verified | 50.3 | 59.5 | 61.8 | 54.7 | 61 |
| Terminal-Bench 2.1 | 12.5 | 18.1 | 22.2 | 15 | 24 |
| τ³-bench (Banking) | 11.6 | 12.89 | 14.69 | 5.03 | 7.22 |
| GDPval-AA-V2 (Elo) | 815 | 946 | 967 | 424 | 546 |
| GPQA Diamond | 69.19 | **72.41** | 72.16 | 77.71 | 80.93 |
| HLE (text-only) | 8.25 | **10.89** | 10.43 | 11.31 | 15.43 |
| IFBench | 74.29 | 77.94 | 79.0 | 53.83 | 59 |
| AA-LCR | 63 | 71 | 73 | 64.7 | 68.4 |
| AA-Omniscience (acc.) | 10.03 | 10.08 | 10.03 | 15.02 | 18.05 |

Reading, carefully:

- **The 1→2 step is where the money is** — the card says so
  itself and the table agrees (SWE-bench +9.2, SciCode +7.6,
  GDPval +131 Elo). 2→4 buys a little more on agentic/coding
  suites (Terminal-Bench +4.1, SWE-bench +2.3) and *loses* a
  little on GPQA and HLE.
- **Instruction following (IFBench) is monotone here** — 74.29
  → 77.94 → 79.0. The over-looping regression named in §3 is
  therefore not "IFBench falls at 4 loops" (it does not, in
  the vendor's numbers); it is the GPQA/HLE shape — a peak at
  intermediate depth — plus the house-specific version of it:
  whether extra loops increase *confident, well-formed,
  wrong* output on grounded tasks. That is an empirical
  question the vendor table cannot answer for our fixtures.
- **Token efficiency** (fewer generated tokens at higher loop
  counts on the same tasks) is claimed via a chart image on
  the card; the underlying numbers are not machine-readable,
  so the size of the effect is **UNVERIFIED**.
- The AA v4.3.2 comparison chart is labelled by NVIDIA itself
  as *internal estimates* that "may deviate from official
  Artificial Analysis scores."
- Vendor-measured on DGX Spark (the only edge-class hardware
  in the card): quantised-checkpoint speedups vs BF16 of
  1.69–1.84× (MXFP8) and 2.17–2.44× (NVFP4) at batch 1. No
  absolute tok/s for any edge device appears in the card.

### Independent data points (anecdote-grade, labelled)

Two, and only two, independent runs were found:

1. **YouTube, "Looped Transformers on One RTX 3060: Smarter or
   Just Slower?"** (https://www.youtube.com/watch?v=h7hILgt_2SQ)
   — the Q5_K_M GGUF under the PR-branch llama.cpp, RTX 3060
   12 GB, 8K context: **52 / 35 / 21 tok/s at 1 / 2 / 4 loops**;
   VRAM 3.8 GB at 1 loop rising to 4.1 GB at 2 loops
   (per-loop KV). The same tester's knowledge score stayed
   flat (~10) across loop counts, consistent with the vendor's
   flat Omniscience row; and their control experiment —
   naively looping an *untrained* model's middle block —
   **degraded** it (MMLU-Pro −8.35 points), which is the
   expected evidence that Dory's gains come from being trained
   to loop, not from looping per se. Single creator, own
   harness, quantised checkpoint: colour, not measurement.
2. **Hack-Log (note.com), 16 GB M4 Mac**
   (https://note.com/hacklog_stealth/n/nd271a336a7f4) — KV
   cache at 32K context, f16: 1,314 MiB at 1 loop → 3,504 MiB
   at 4 loops under `per_loop`; flat 1,314 MiB under
   `last_loop`. Generation 6.98 / 4.36 / 2.66 tok/s at 1/2/4
   loops (the author flags the three runs were not under
   identical conditions). The KV figures matter beyond
   anecdote for one reason: they match the arithmetic derived
   from `config.json` in §2 to within ~1%, which cross-checks
   both.

No third-party benchmark replication of the card's table
exists as of this study.

## 2. The loop mechanism, precisely

### Block structure

The stack is three groups of layers with shared weights in the
middle group (card architecture figure; `config.json` counts
each attention and MLP sub-layer as a separate step, so both
accountings are given):

| Group | Attention layers (card) | Steps in config | Repeats |
|---|---|---|---|
| Input (I) | 8 | `n_input_layers` = 16 | ×1 |
| Recurrent (R) | 20 | `n_recurrent_layers` = 40 | ×k (the loops) |
| Output (O) | 8 | `n_output_layers` = 16 | ×1 |

36 stored attention layers in total (`num_hidden_layers` = 72
steps). Per token, the number of attention layers actually
executed is **16 + 20k**: 36 at k=1, 56 at k=2, 96 at k=4 —
i.e. step counts 72 / 112 / 192, or 1.00× / 1.56× / 2.67× the
k=1 compute. That is the honest version of "4B": the stored
artefact is 4B parameters; a 4-loop token costs roughly the
layer-work of a ~96-attention-layer network built from those
weights. (The RTX 3060 anecdote's tok/s ratios — 1 : 0.67 :
0.40 — sit close to the inverse of these compute ratios,
1 : 0.64 : 0.375, which is what bandwidth-bound decode would
predict. Anecdote-grade, but consistent.)

Attention composition: every group of 4 attention layers is
3 sliding-window (window 1,024 tokens, rope θ=10⁴) + 1 full
attention (rope θ=10⁷). Across the 36 stored layers: 27
sliding, 9 full. The recurrent block contains 15 sliding + 5
full; the fixed I/O blocks together contain 12 sliding + 4
full. This composition matters for the KV arithmetic below:
sliding layers' caches stop growing at 1,024 tokens.

### Input re-injection

Per the card's architecture figure caption: the shared
Recurrent block "is applied multiple times between the Input
and Output blocks, and **the input is reinjected into every
loop**." Each pass of R therefore sees not only the previous
pass's output but a fresh copy of the Input block's output —
the loop refines a representation that is continuously
re-anchored to the encoded input, rather than a free-running
recurrence that can drift from it. The exact combination
operator (addition vs gated mix) is **not specified in the
card**; the config carries nGPT machinery
(`ngpt_alpha_init: 0.05`, an attention output gate), consistent
with learned, normalised mixing, but the operator itself is
UNVERIFIED from primary sources and should be read out of the
PR source before any experiment depends on it.

### Loop counts allowed, and how the count is selected

- **Allowed: 1, 2, 3, 4.** The llama.cpp PR states support for
  recurrent loops k=1–4 and lists **K>4 as unsupported**; the
  card's recipes document 1/2/4 and its benchmarks report
  1/2/4. 3 loops is exposed by the tooling but has **no vendor
  benchmark row** — an unmeasured point on the curve, which §3
  uses.
- **Default: 2** (`config.json`: `n_recurrent_loops: 2`;
  the card recommends 2 as the starting point).
- **Selection is launch-time configuration, in both stacks:**
  - vLLM: `--hf-overrides '{"n_recurrent_loops": 2,
    "recurrent_kv_cache_mode": "per_loop"}'` on the serve
    command.
  - llama.cpp: GGUF metadata override at server launch,
    `--override-kv "dory.num_loops=int:2,dory.recurrent_kv_cache_mode=str:per_loop"`.
  - Neither the card nor either PR documents a per-request
    override. Whether the vLLM PR's model class could accept
    one is UNVERIFIED; in llama.cpp the compute graph is built
    per batch, so a per-request `num_loops` is *plausibly* a
    small patch to the PR branch — a source-reading question,
    marked as such in §3, not an assumption.

### KV-cache modes and their memory arithmetic

Two modes, config key `recurrent_kv_cache_mode`, default
`per_loop`:

- **`per_loop`** — every loop keeps its own KV cache for each
  recurrent attention layer (the standard looped-model
  behaviour). Recurrent-layer cache instances scale with k.
- **`last_loop`** — one cache per recurrent attention layer;
  each loop overwrites the previous loop's entries, so the
  retained cache is the final loop's. Cache size is the k=1
  size at any loop count (card claim; independently matched by
  the M4 anecdote). Costs: predictions change vs `per_loop`,
  and prefill chunk size affects results (llama.cpp PR body).

Arithmetic, derived from `config.json` (4 KV heads × 256
head_dim × 2 tensors × 2 bytes at f16 = **4 KiB per token per
attention layer**; sliding layers capped at 1,024 tokens):

| Context | Mode | k=1 | k=2 | k=4 |
|---|---|---|---|---|
| 4,096 tokens | per_loop | ~0.61 GB | ~0.79 GB | ~1.15 GB |
| 4,096 tokens | last_loop | ~0.61 GB | ~0.61 GB | ~0.61 GB |
| 32,768 tokens | per_loop | ~1.32 GB | ~2.11 GB | ~3.52 GB |
| 32,768 tokens | last_loop | ~1.32 GB | ~1.32 GB | ~1.32 GB |
| 262,144 tokens | per_loop | ~9.8 GB | ~15.2 GB | ~26.1 GB |
| 262,144 tokens | last_loop | ~9.8 GB | ~9.8 GB | ~9.8 GB |

(Full-attention instances are 4 + 5k and grow with context;
sliding instances are 12 + 15k and saturate at the 1,024-token
window. At 262K the full-attention term dominates, which is
why the ratio compresses from the naive (16+20k)/36.) The
32,768 row reproduces the M4 anecdote's measured 1,314 MiB /
3,504 MiB within ~1% — the one place in this study where an
independent measurement and a primary-source derivation meet.
Halve every figure for an 8-bit KV cache, quarter for 4-bit,
if the deployment quantises KV; the card's reference recipe
uses f16.

### Tooling status (2026-11-05)

| Path | Status |
|---|---|
| llama.cpp | PR #30306 **OPEN, unmerged** (GitHub API: `state: open`, `merged_at: null`, updated 2026-11-02). Head `brianchmielNV:dory-support` @ `1c3cdd2…`; card pins the earlier rev `98a74c9…`. PR reports: HF→GGUF converter, k=1–4, both KV modes, tested bf16/q4_k_m/q5_k_m, 96/96 numerical comparisons (CPU and CUDA), 36/36 serving smoke tests. Stated limitations: Metal untested, long-context qualification incomplete, **context shifting and runtime re-save unsupported, K>4 unsupported**. |
| vLLM | PR #60149 **OPEN, unmerged**, in review since 2026-10-06; card's install line pulls the PR ref with precompiled wheels. |
| Transformers | `DoryForCausalLM` is the config's architecture and HF lists `AutoModelForCausalLM` support; the card documents no Transformers quick-start (its recipes are vLLM and llama.cpp). Treat a pure-Transformers route as UNVERIFIED. |

## 3. The rolling-perception connection — and the charter

### What NVIDIA ships vs what this programme claims

State the difference without blur. NVIDIA ships a checkpoint
whose depth is chosen **once per deployment**: an operator
reads a benchmark table, picks 1, 2 or 4, and every token of
every request pays that depth forever, whether the token is a
routine harbour frame or the one ambiguous event of the day.
The dial is real — that alone separates Dory from Loop-9B —
but it is a *fixed point*, set by a human, at launch.

This programme's thesis since the seed email is the opposite
allocation: **compute follows the signal, inside the stream.**
The rolling cascade spends its iterations where surprise is —
diff-gating cut embed spend 54% (312 vs 576) in wave 3; sheaf
refine iterates a shared operator until energy settles
(precision 0.60 → 1.00 in the ablation); the platform meters
perception in **embed-seconds** precisely so spend is a
budgeted, receipted quantity rather than a constant. Dory's
loop is the same algebraic object one tier up — a shared block,
re-applied — with one property none of our iterators have: it
was *trained* to be iterated elastically, at counts 1–4, with
vendor-measured quality at each count. The naive-looping
control in the RTX 3060 anecdote (an untrained model made
*worse* by looping) is the negative control that gives this
point its weight: iteration-as-dial only works when the
artefact was built for it, and this one was.

So the charter's unit of account is the **loop-second** (one
recurrent-block pass over the working context, mirroring the
embed-second), and its non-negotiable discipline is the one
the ledger already enforces downstairs: **every verdict
carries a receipt of loops spent**, so quality can always be
divided by spend after the fact. An allocation scheme that
cannot show its receipts is not cascading; it is just a
different fixed point with better marketing.

And the honest obstacle, once more: **no current tool exposes
the dial per request.** The experiments below are ordered so
that the cheapest ones run on the stock PR build, and the one
that needs per-request control says exactly what has to be
built (or patched) first.

### Experiment D1 — over-looping regression hunt (runs first; stock build)

*Question.* On this house's grounded fixtures, where does the
quality-vs-loops curve peak, and does depth past the peak buy
*confident wrongness*?

*Design.* The PR-branch llama-server, Q5_K_M, `per_loop`,
prefill chunk pinned. Fixtures: the BRAIN-BENCH battery and
the presence claim-trap set (frozen texts, digest-in /
sentences-out, claim-checker scored), plus an IFBench-style
instruction set with verifiable constraints. Arms: loops
**1 / 2 / 3 / 4** — 3 included precisely because the vendor
never measured it. Metrics per arm: grounding score, claim
violations (counted, per house rule), constraint-satisfaction
rate, output tokens, wall time, loop-seconds.

*Named risk.* The GPQA/HLE shape (peak at 2, regression at 4)
appearing on grounded tasks, with the regression taking the
specific form of *more* claim violations at 4 loops — fluent,
well-formed, ungrounded sentences that the 2-loop arm did not
produce. That failure mode, not a benchmark dip, is what
would bar high-loop allocation in the cascade.

*Falsifiers.* The risk retires for this artefact if quality
is monotone 1→4 on every fixture **and** claim violations do
not increase at any step. Conversely, if quality is *flat*
1→4 everywhere at 2.67× the k=1 spend, the loop dial itself —
not merely its over-use — is dead on our workloads, and D2/D3
do not run.

### Experiment D2 — settle-signal probe (needs instrumentation)

*Question.* Does a *settle signal* exist inside Dory — a
measurable quantity, readable during the forward pass, that
says "another loop will not change this token's answer"? This
is the sheaf-energy question transplanted: our refine loop is
allocatable because its energy is observable.

*Design.* Instrument the PR branch (or run the BF16 checkpoint
under a research harness) to record the representational
delta between successive recurrent passes, ‖hₖ₊₁ − hₖ‖, per
token, over the D1 fixtures. Test two things: (a) contraction —
do deltas shrink geometrically with k, as sheaf energy does
(132.75 → 95.97 in the cascade measurement)? (b) prediction —
does a small delta at loop 2 predict that loops 3–4 leave the
output unchanged, well enough to stop on?

*Falsifiers.* If deltas do not contract (oscillation or growth
across passes), there is no internal settle signal and
allocation must be driven entirely from outside (D3's
surprise signal) — the "rolling" version of Dory is then a
router, not a settler, and the charter says so. If deltas
contract but do not predict output stability, the signal is
decoration: same conclusion.

### Experiment D3 — cascading allocation at equal compute (the charter's centre)

*Question.* Driven by the stream's own signals, can per-item
loop allocation beat every fixed loop count **at equal total
loop-seconds**?

*Design.* Seat: Dory as the cascade's **reflective refiner** —
the tier that turns published events into checked prose.
Pipeline unchanged up to the digest: frames → diff gate →
I-JEPA events → text digest (this is the platform's existing
shape; Dory never touches pixels). Each digest window is
assigned a loop count by the allocator; arms:

1. Fixed 1 / fixed 2 / fixed 4 (baselines, from D1).
2. **Surprise-allocated:** the window's surprise (max smoothed
   tile score / sheaf energy of its events, quantities the
   platform already computes) maps to loops — calm windows 1,
   unsettled windows 4, budget-normalised so the arm's total
   loop-seconds equal the fixed-2 arm's.
3. **Settle-allocated** (only if D2 finds a signal): loops
   spent per window until the delta criterion stops them,
   hard-capped at 4, same total budget enforced by the
   allocator.

Delivery mechanism, stated as a build item: per-request loop
counts are **not exposed** by either server today. Two honest
routes: (a) run two/three llama-server instances at fixed
counts and route windows between them (works with the stock
PR build; costs resident memory per instance — ~4 GB each at
Q5_K_M, affordable on the Thor, and routing is a receipted
ledger decision); or (b) patch the PR branch for a per-request
`dory.num_loops` override (graph is per-batch in llama.cpp;
effort UNVERIFIED until the source is read). Route (a) is the
charter's default — it keeps the experiment on unmodified
upstream code.

Metrics: grounded-claim rate and correction rate on the
windows' prose, divided by loop-seconds; per-window gain vs
the window's surprise (does the allocator spend where the
gain is?); freshness/TTFO impact on the stream (the refiner
must not stall the reflex tier — the tenancy ladder applies).

*Falsifiers.* If no adaptive arm beats fixed-2 at equal spend
on grounded quality, cascading allocation is falsified for
this seat and the programme keeps Dory (if at all) as a fixed
2-loop component — a fine outcome, honestly reported. If the
surprise signal does not predict which windows gain from
depth (gain-vs-surprise correlation ≈ 0), the allocator's
input is wrong even if allocation in principle works; that
points back at the perception tier, not at Dory.

### What would have to be true for any of this to matter

D1–D3 are cheap because the artefact is small (§4). But the
charter's bar is the house bar: Dory earns a *seat* only
against the incumbent brain's measured record (BRAIN-BENCH,
claim-trap set, presence loop), and it earns the *concept*
only if allocation beats the fixed point at equal spend with
receipts. A tie goes to the incumbent — it is already
integrated, and its failure modes are known.

## 4. Running it on the Jetson AGX Thor — what it takes today

Target: aarch64, sm_110, CUDA 13.2, 122 GiB unified memory,
~89 GB free disk at last measure. Nothing in this section was
run; it is a requirements statement, with unknowns flagged.

- **Build.** llama.cpp from the PR branch — clone
  brianchmielNV/llama.cpp (`dory-support`) or check out the
  card's pinned revision `98a74c97ea09ac72f6ceda1559808fc0a2f447ce`,
  and build with the house's usual CUDA configuration
  (GGML_CUDA on, the Thor's sm_110 target) instead of the
  card's macOS/Metal recipe. The PR body reports CUDA among
  its numerically tested backends (96/96 comparisons) — on
  unspecified hardware; **sm_110 specifically is UNVERIFIED**,
  and the house has been bitten before by assuming a backend
  covers this GPU (the Cycles sm_110 patch in TOOLS.md). The
  first Thor task is therefore a smoke build + the PR's own
  numerical tests, before any fixture runs. Expect the usual
  aarch64 build time in the tens of minutes, not a package
  install.
- **Weights.** One file: the official Q5_K_M GGUF,
  3,673,288,864 bytes, SHA-256 published on the card — hash-
  gate it on arrival per house rule. At ~3.7 GB it is ~4% of
  free disk; the download is a non-event (contrast Loop-9B's
  ~38 GB for a study-only artefact). Download doctrine still
  applies: single stream, through the governor if the Thor's
  pipe is contended.
- **Expected memory.** Weights 3.67 GB resident; KV from the
  §2 table at working contexts — presence/digest workloads
  live at ~4K context, so ≈0.6–1.2 GB depending on mode and
  loops; even a 32K-context experiment at 4 loops `per_loop`
  is ~3.5 GB of KV. Total resident ≈ **4–8 GB** — small next
  to the incumbent brain's 18.6 GB GGUF. As a standing tenant
  it still takes a thor-admit lease like every other multi-GB
  resident; D3's multi-instance routing multiplies the weight
  term per instance (plan: ≤3 instances ≈ 11 GB weights).
- **Expected speed: no Thor number exists — UNVERIFIED.**
  Brackets only: the RTX 3060 anecdote (35 tok/s at 2 loops,
  Q5_K_M, 8K ctx) is a weaker, discrete GPU on the same code
  path; the card's only edge-class figures are DGX Spark
  *relative* quant speedups with no absolute rates. Anyone
  quoting a Thor tok/s for Dory before a bench is inventing
  it. The D1 fixture run produces this number as a by-product.
- **vLLM route: not recommended today.** The PR is unmerged,
  and its install line assumes precompiled wheels matching the
  platform; on Jetson/aarch64 those typically do not exist and
  the fallback is a full source build of vLLM — UNVERIFIED
  and disproportionate next to the llama.cpp route this house
  already operates.
- **NVFP4 route: noted, not planned.** The NVFP4 checkpoint
  (3.20 GB) is a safetensors artefact for the vLLM /
  TensorRT-LLM class of stacks; llama.cpp does not consume it
  (its artefact is the GGUF). The Thor's Blackwell-class GPU
  has FP4 tensor cores, so a future NVFP4 serving path is
  physically plausible — and entirely UNVERIFIED today.
- **Operational caveats from the PR itself:** no context
  shifting and no runtime state re-save — long streaming
  sessions must manage context explicitly rather than rely on
  the server's shift machinery the house's current brain
  deployment uses; long-context qualification is incomplete,
  so the 256K headline is not a planning number (nothing in
  the charter needs it: digests are ~1–4K tokens).

## 5. Risks

- **Two unmerged PRs are the whole serving story.** Either
  could stall, be rewritten, or land with changed metadata
  keys (`dory.num_loops` is a PR-branch key name; a merged
  version could rename it). Pin everything to the card's
  revision and record the pin in the run receipts.
- **Benchmark shape risk (the D1 hunt):** quality peaks at
  intermediate depth on two of the vendor's own suites. If
  that shape holds on grounded prose, a naive "spend 4 loops
  on anything important" policy would be *worse* than 2 on
  exactly the windows that matter — the charter's allocator
  must treat loops as capable of harm, not merely of cost.
- **Reasoning is always on** in the vLLM recipe and the
  chat template defaults `enable_thinking` true. This house
  has a measured failure mode here (a reasoning model spending
  its whole budget in `reasoning_content` and returning empty
  content at presence settings — BRAIN-BENCH). The vendor's
  own coding-agent note (pass `force_nonempty_content`) shows
  the empty-content edge is real on this artefact too. Every
  battery must verify content non-empty, per response.
- **Mode-flip risk:** `per_loop` ↔ `last_loop` changes
  predictions (PR body). A/B comparisons, soak baselines, and
  any "same model" claim must record the mode in the receipt
  alongside the loop count; an unrecorded flip silently
  invalidates a comparison.
- **Licence is OpenMDW-1.1, not Apache.** The card states
  commercial and non-commercial use is permitted and the
  repos are ungated, so research use here is unblocked; but
  it is a distinct licence from the Apache 2.0 of Loop-9B and
  should be read in full before any product-facing use —
  flagged, not adjudicated, by this study.
- **Single-source evidence, again.** Architecture, training
  recipe, and all benchmarks trace to one vendor card plus
  two anecdotes. The KV arithmetic is the only claim in this
  study cross-checked two independent ways.
- **Text-only scope creep.** The standing temptation will be
  to describe D1–D3 as "looped perception." It is looped
  *reflection over perception's receipts*. The perceptual tier
  remains JEPA-shaped for the reasons recorded in
  STUDY-SENSENOVA-LOOP-9B §2(b) (arXiv:2610.39302's bad-views
  result; the wave-3 battery's 1.000/1.000). Keep the words
  honest and the tiers separate.

## Bottom line

Dory is the first looped artefact this programme can actually
*pick up*: small (3.7 GB), permissively licensed for research
use, trained to be iterated, and — unlike Loop-9B — possessed
of a real loop dial. The dial is nevertheless a **launch-time
fixed point in all current tooling**, every quality number is
the vendor's, and the only serving paths are two unmerged
PRs. Filed as: **charter-ready, seat-unproven.** D1 (the
over-looping hunt) runs on the stock PR build and costs an
afternoon; D2 decides whether a settle signal exists; D3 —
cascading allocation at equal compute, with loop receipts in
the ledger — is the experiment that would make "rolling
perception" a claim about language-model depth as well as
about frames. Nothing about Dory displaces any incumbent
before those numbers exist.

*Sources: HF model card, config.json and API file listings
for `nvidia/NVIDIA-Nemotron-Labs-Dory1.0-4B-BF16` / `-MXFP8` /
`-NVFP4` / `-GGUF` (accessed 2026-11-05);
https://github.com/ggml-org/llama.cpp/pull/30306 and its
GitHub API record (state/head/limitations);
https://github.com/vllm-project/vllm/pull/60149 (status);
"YouTube — Looped Transformers on One RTX 3060: Smarter or
Just Slower?", https://www.youtube.com/watch?v=h7hILgt_2SQ
(anecdote-grade); Hack-Log, note.com,
https://note.com/hacklog_stealth/n/nd271a336a7f4
(anecdote-grade, KV figures used as an arithmetic
cross-check). Local records: docs/STUDY-SENSENOVA-LOOP-9B.md,
docs/FINDINGS-CFC-JEPA-V2.md, docs/SPEC-STREAM-PLATFORM.md,
slice2/BRAIN-BENCH.md.*
