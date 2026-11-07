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
