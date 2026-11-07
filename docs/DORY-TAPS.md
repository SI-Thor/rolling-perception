# DORY-TAPS — per-pass hidden-state taps on the Dory fork (D2's instrument)

Date: 2026-11-06. Lane: DORY TAPS (charter experiment D2: instrument + first
measurement). Engine: llama.cpp fork brianchmielNV/llama.cpp, branch
dory-support, pinned rev 98a74c97e, patched on local branch `dory-taps`
(~/dory-lab/llama.cpp), built Release / CMAKE_CUDA_ARCHITECTURES=110 / CUDA in
build-dory. Model: NVIDIA-Nemotron-Labs-Dory1.0-4B-Q5_K_M.gguf (hash verified in
DORY-SMOKE-1). Every GPU run in this file sat under a thor-admit lease
(~/lm-tools/thor-admit run --peak 8G --label ...): dory-taps-invariant (x3),
dory-taps-matrix. Raw data: taps/runs/*.jsonl (taps), *.txt (generated text),
*.err, manifest.json, analysis.json.

## Files touched (pristine recoverable: .orig copies + branch off the pinned rev)

- src/models/dory.cpp (+3 lines): at the top of the graph's virtual-layer loop,
  `res->t_layer_inp[il] = cur;` records each layer's input tensor — the same
  recording src/models/llama.cpp:127 already does for the llama arch. Inert
  pointer stores; no new graph nodes, no new allocations.
- include/llama.h (+4 lines): public declarations for
  llama_set_embeddings_layer_inp / llama_get_embeddings_layer_inp. The fork
  already contained the definitions (src/llama-context.cpp:4137/4165) plus the
  whole capture pipeline (cparams.embeddings_layer_inp -> set_outputs marks the
  tensor -> ggml_backend copy into embd_layer_inp in
  llama_context::extract_layer_inputs) — it was simply never exposed in the
  public header. Nothing else in the engine changed: git diff is 3 files, +8
  lines, plus the new tool.
- tools/CMakeLists.txt (+1 line): add_subdirectory(dory-taps).
- tools/dory-taps/{dory-taps.cpp (~250 lines), CMakeLists.txt} (new): the tool.

## Exact mechanism

dory.cpp unrolls the recurrent block over shared weights into virtual layers:
pass k occupies layers [n_input + k*n_recurrent, n_input + (k+1)*n_recurrent).
At each end-of-pass layer the state is unit-L2 normalised (build_gdn_l2_norm);
that normalised tensor is the block's pass-k output h_k. In the graph, h_k is
exactly the untransformed input of the first virtual layer of pass k+1, i.e.
virtual layer n_input + k*n_recurrent — which is what the recording line now
stores in res->t_layer_inp. For this GGUF n_input=16, n_recurrent=40, so the
boundary layer ids are 56/96/136/176 for h_1..h_4; at loops L the tool enables
capture at exactly those L ids (no others) and, after each single-token decode,
reads the L boundary vectors host-side and emits
delta_norm(k) = ||h_k - h_{k-1}||_2 for k>=2 (computed in double precision in
the tool) and final_norm(k) = ||h_k||_2.

Per-token granularity is exact: every generation decode is a 1-token ubatch,
and taps are read after decode of generated token t, so token_index t is the
forward pass that consumed token t. Prompt-phase decodes are not recorded
(multi-token ubatches; not needed for D2).

## How to enable

There is no engine-wide runtime flag by design: taps exist only when a caller
enables layer capture explicitly. The dory-taps tool does so only when --taps
is given:

  llama.cpp/build-dory/bin/dory-taps --model <gguf> --prompt-file prompts/p1.txt \
      --loops 3 --reasoning on --n-predict 1024 \
      --taps taps/runs/k3-p1.jsonl --gen-out taps/runs/k3-p1.txt

(other args: --ctx 4096, --temp 0.0, --seed 42; defaults match the smoke).
Without --taps: no layer ids enabled, no capture, no extraction — and
llama-server / llama-cli never enable capture at all. When off, the patched
engine is bit-behaviourally identical to the pinned rev (verified below).

## JSONL schema

Line 1 header: {"header": true, "n_input": 16, "n_recurrent": 40, "n_loops": L,
"reasoning": "on"|"off", "enable_thinking": bool, "temp": 0, "seed": 42,
"n_predict": N, "prompt_file": ..., "think_start": "<think>", "think_end": ...}.
Then one object per generated token t and pass k (1-based):
  {"token_index": t, "pass": k, "delta_norm": null | float, "final_norm": float}
delta_norm is null at pass 1 (no previous boundary). final_norm measured
1.000000 on every pass of every run (unit-L2 by construction — the end-of-pass
normalisation), so delta_norm carries all information.

## Verification (brief step 2)

- Engine OFF-invariant, exact: the patched llama-server replayed the smoke's
  k=2 p1 request through the original client.py flow — finish length=length,
  predicted_n 1024=1024, reasoning_content identical (3501 chars), content
  identical. Byte-exact reproduction of DORY-SMOKE-1 output.
- Taps non-perturbation: dory-taps (k=2 p1, taps OFF) vs (taps ON) produced
  byte-identical text (cmp clean).
- Geometry sanity: header n_input=16 n_recurrent=40; lids 56 96 (loops=2);
  2049 lines = header + 1024 tokens x 2 passes.

## Measurement (36 runs, one dory-taps-matrix lease, 17:08–17:28)

Fixed 6-prompt set; loops 2/3/4; reasoning on (n_predict 1024) and off (256);
temp 0.0, seed 42, ctx 4096, override dory.num_loops=int:L and
dory.recurrent_kv_cache_mode=str:last_loop — the smoke's configuration.
"del/cor" = delivered/correct graded in this harness (delivered: generation
stopped before the cap with non-empty content after </think>).

Reasoning-ON arm — median per-token delta norms d_k = ||h_k - h_{k-1}||:

| run k | p1 | p2 | p3 | p4 | p5 | p6 |
|---|---|---|---|---|---|---|
| 2 | 0.0117 | 0.0131 | 0.0107 | 0.0114 | 0.0130 | 0.0104 |
| 3 | 0.0111 | 0.0135 | 0.0102 | 0.0120 | 0.0121 | 0.0101 |
| 4 | 0.0110 | 0.0137 | 0.0103 | 0.0116 | 0.0125 | 0.0103 |

(median d_2; loops=2 rows have only d_2) — d_3 medians (k=3): 0.0026–0.0033;
d_4 medians (k=4): 0.0024–0.0028.

Median per-token ratios r_k = d_k/d_{k-1}, reasoning ON:

| | p1 | p2 | p3 | p4 | p5 | p6 |
|---|---|---|---|---|---|---|
| r3 (k=3) | 0.305 | 0.266 | 0.280 | 0.283 | 0.282 | 0.307 |
| r3 (k=4) | 0.302 | 0.271 | 0.277 | 0.299 | 0.284 | 0.305 |
| r4 (k=4) | 0.914 | 0.842 | 0.889 | 0.912 | 0.888 | 0.920 |

Fraction of tokens with r<1 (k=3): 98.4–99.4%. (k=4): 89.1–94.5%; strictly
monotone d_2>d_3>d_4 fraction (k=4): 78.8–89.6%.

Reasoning-OFF arm: median d_2 0.0112–0.0300 (short answers run fewer tokens);
r3 (k=3) 0.228–0.265; r3 (k=4) 0.229–0.258; r4 (k=4) 0.552–0.829; fraction
r<1 (k=3) 96.6–100%, (k=4) 92.9–100%; monotone (k=4) 85.7–100%.
(Per-run values in taps/runs/manifest.json + taps/analysis.json.)

Delivery/correctness in this harness, reasoning ON: p4 delivered+correct at
k=2/3/4 (516/482/557 tok); p6 delivered+correct at k=2 and k=4 (535/576);
p3 delivered+correct at k=3 (990); all other cells hit the 1024 cap
undelivered. Reasoning OFF: all 18 delivered; correct except p2 at every k.

## Grading the settle hypothesis (D2, plainly)

1. Do per-pass deltas contract? YES — strongly from pass 2 to 3, in every run
   of both arms: median r3 = 0.27–0.31 (on) and 0.23–0.27 (off); 97–100% of
   tokens contract at k=3. The contraction then nearly exhausts: pass 3 to 4
   ratios sit at 0.55–0.92 (deltas already ~0.003 vs the unit-norm sphere).
   Absolute d_2 medians are 0.010–0.030 — the second pass already moves the
   state by only ~1–3% of the sphere radius, and the third pass by ~0.3%.
2. Does contraction separate delivered from undelivered, or correct from
   wrong? NO. Like-for-like at k=3 (on-arm): delivered runs r3 = 0.280, 0.283
   vs undelivered r3 = 0.266/0.282/0.305/0.307 — the ranges interleave
   completely (an undelivered cell, k3-p6 at 0.307, is indistinguishable from
   the delivered k2-p6 at 0.307). Pooled medians: delivered 0.333 vs
   undelivered 0.388; correct 0.333 vs wrong 0.369 — no usable separation at
   n=6. The settle signal is uniform: everything looks settled by pass 3,
   including the four prompts that still burn 1024 tokens in deliberation.
3. Pre-registered falsifier (charter): "if per-pass deltas do not measurably
   contract, the internal settle signal is dead and cascading allocation must
   use an external signal." NOT triggered: deltas do measurably contract. The
   complementary finding matters just as much for D2's second question —
   contraction carries no per-prompt information at this scale (uniform
   presence, no outcome correlation), and it is largely complete by pass 3,
   which is consistent with the smoke's observation that loop count never
   changed a verdict beyond k=2. A cascade allocator reading these taps would
   see "settled" everywhere and learn nothing about delivery risk.

## Honesty notes

- The taps tool's token streams are not byte-equivalent to the smoke server's
  streams beyond an early point: raw-text prefix-match fractions against the
  smoke's reasoning_content/content are 1.000 for the short off-arm answers
  (p2/p4/p6 at every k) but 0.00–0.86 elsewhere (divergence mid-stream at
  temp 0). The engine itself is exact (server replay invariant above) and
  taps-off==taps-on is exact, so this is tool-harness sensitivity (direct
  tool vs server request path), not the patch. Consequence: two verdict-grid
  cells differ from the smoke in this harness (k3-p3 delivered here vs
  truncated there; k3-p6 truncated here vs delivered there) — delivery near
  the termination margin is harness-sensitive; the p1/p2/p5 deliberation trap
  and p4's reliable delivery reproduce at every k.
- The settle-signal statistics are internally consistent (one harness for all
  36 cells); cross-harness text divergence does not affect delta norms, which
  are a property of each run's own forward passes.
- n=6 prompts, greedy decoding, one artefact: descriptive statistics only,
  no significance claims.

## Addendum 2026-11-07 — The learned governor: a clean negative

The measurement above closed with a conditional: contraction is real but
carries no per-prompt outcome information, so cascading loop allocation would
have to use an external or learned signal. That allocator has now been built
and honestly evaluated against the recorded matrix (workspace
`dory-taps-governor/`: REPORT.md, code/governor.py, results/results.json;
labels re-derived from the raw outputs with 0 mismatches against
manifest.json). Verdict: **clean negative.** Nothing was tuned until it won;
all numbers are leave-one-prompt-out over the six reasoning-on prompts, scored
as delivered answers per 100 decode-cost-seconds under the smoke's measured
rates (19.7 / 13.0 / 10.4 / 7.6 tok/s at k = 1–4).

| policy | delivered | cost (s) | deliv / 100 cost-s |
|---|---|---|---|
| fixed k=2 | 2 | 395.9 | **0.505** |
| tree governor | 2 | 401.3 | 0.498 |
| contraction-threshold rule | 2 | 414.4 | 0.483 |
| LR governor | 1 | 452.0 | 0.221 |
| oracle cascade (bound, not a policy) | 3 | 411.1 | 0.730 |

- **Fixed k=2 wins.** The tree and the threshold rule tie it on deliveries
  and lose slightly on cost — their skill is having learned to almost never
  deviate. The LR governor does strictly worse than every fixed-k baseline:
  its single deviation (p6 to k=3) lands exactly on a harness-noise cell and
  costs one delivery and 56 s.
- **The scorer is anti-predictive.** Refitting the identical LR pipeline on
  label-shuffled data scored at or above the true model in **300 of 300**
  permutations (null mean 0.335, null p95 0.505, true 0.221). Even fit
  in-sample on all 18 rows, the LR's coefficients on the loop-count terms are
  exactly 0.0 — there is no systematic k effect for it to find.
- **The anatomy explains why.** Every fixed k delivers exactly 2 of 6 in the
  reasoning-on arm. Empirical marginal gains of an extra pass are zero for
  p1, p2, p4, p5; the only k-dependent variation in all 18 runs sits in two
  cells — p3 gains at k=3 then loses it at k=4, p6 loses at k=3 then regains
  it at k=4 — and those are precisely the two cells (k3-p3, k3-p6) where this
  harness and the smoke harness graded opposite outcomes, as the honesty
  notes above already record. All allocator-exploitable variation on present
  evidence is termination-margin harness noise, not signal. Even the
  oracle's +45% headroom rests entirely on one of those cells.
- **The decision-time constraint was honoured, and it matters.** A real
  cascade must decide before paying for pass 3, so the only taps observable
  at decision time are features of the pass-2 delta series d2 (level, spread,
  trend, slope, near-settled fraction, over probe windows of 32/64/128
  tokens). The headline r3 of the study above is a pass-3 quantity and is
  **not available to any real allocator**. The negative is therefore stronger
  than the study's: not only does r3 fail to separate outcomes, the full d2
  family a real allocator could actually use fails too, at every window and
  every regularisation tried (λ ≥ 3 collapses the LR to fixed k=2; gifting
  the probe for free moves every cascade metric by ≤0.002 — not a probe-cost
  artefact). The reasoning-off arm is degenerate for allocation: 18/18
  delivered at k=2/3/4, correctness perfectly k-invariant — minimum k is
  trivially optimal there.

Standing recommendation: **do not implement the cascade behind the taps
flag.** The policy taken to the fight is specified precisely enough to build
(probe W=64 tokens at k=2, score k ∈ {2,3,4} by predicted delivery per
expected cost, switch for the remainder), and the evidence says its learned
step is machinery around "always choose 2". If loop count ever becomes a
runtime knob for this model, the evidence supports a constant: **k=2 for
reasoning-on** (k=1 under-delivers at 1/6 despite the lowest cost; k≥3 buys
nothing measurable), **minimum k for reasoning-off**.

Cross-references: this closes the WSP synthesis §5 fork in favour of
**Branch B** for allocation — no learned or threshold allocator is carried
forward from this dataset. It also fires the DESIGN-EXTERNAL-WEIGHT-LOOP E1
kill criterion **as written**: the recorded taps matrix cannot support a
learned per-prompt allocation decision, so E1's learned-allocation leg does
not proceed on this data.

What would change the verdict — the negative is about this dataset, whose
limits are precise:

- **Replicated labels.** Multiple seeds/runs per (prompt, k) cell, graded
  identically, so per-cell delivery *rates* replace single Bernoulli draws;
  the two disagreeing cells suggest run-to-run variance is the dominant term.
- **Prompt count.** On the order of 50–100 prompts with replicated cells
  before an effect of the oracle-hinted size (~+1 delivery per 6 prompts)
  could be fit and honestly held out with a 2–3-feature model.
- **Richer pre-pass-3 signals.** Everything currently observable before
  pass 3 is a norm of a hidden-state difference. Token logits / entropy over
  the probe window, or pass-1 state geometry, are untested signal classes —
  ruling them in or out requires extending the taps; what is ruled out is
  only the d2-norm family and r-style ratios.
- **A graded outcome.** Binary delivery is a termination-margin phenomenon
  here, and it saturates with reasoning off. Answer quality that actually
  varies with loop count is a different — possibly learnable — problem, not
  measurable in this dataset.

Reproduce: `python3 code/build_dataset.py && python3 code/governor.py` in
`dory-taps-governor/` (~2.5 min; the permutation null dominates). Thor
originals untouched throughout; all work ran on copies.
