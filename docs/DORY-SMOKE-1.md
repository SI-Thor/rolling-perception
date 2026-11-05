# DORY-SMOKE-1 — Dory1.0-4B (Q5_K_M GGUF) running on the Jetson AGX Thor: build, hash, first measurements

Date: 2026-11-05. Lane: DORY SMOKE 1 (hands-on follow-up to docs/STUDY-DORY.md).
Artefact: NVIDIA-Nemotron-Labs-Dory1.0-4B-Q5_K_M.gguf, 3,673,288,864 bytes.
Engine: llama.cpp fork brianchmielNV/llama.cpp, branch dory-support, pinned
revision 98a74c97ea09ac72f6ceda1559808fc0a2f447ce (the model card pin),
built with GGML_CUDA=ON, CMAKE_CUDA_ARCHITECTURES=110, CUDA 13.2, Release.
Binary reports: version 0.6.0-dev (build 11551, commit 98a74c97e), aarch64.
Workdir on the Thor: /home/caseydigennaro/dory-lab (source, prompts, raw
run JSON, server logs and summaries are all kept there).

## Verdict up front

- The build works on sm_110. The pinned PR-branch llama.cpp compiled
  clean for CUDA and runs the model on the Thor GPU (device enumerated
  as "CUDA0: NVIDIA Thor"; see Evidence of GPU execution).
- The GGUF hash-verifies exactly against the card-published SHA-256.
- The loop dial works and is priced honestly: decode speed falls
  monotonically with loop count at ratios close to the step-count
  arithmetic in STUDY-DORY.md section 2.
- In vendor mode (reasoning on), the artefact has a delivery problem,
  not a knowledge problem: on 4 of 6 prompts the reasoning reaches the
  correct answer and then never emits it, exhausting a 1024-token
  budget at every loop count. Delivered-correct: 1/6 prompts at
  1 loop, 2/6 at 2, 3 and 4 loops.
- With reasoning off, the same prompts are answered directly: 5/6
  correct at every loop count, and the single error (a logic trap) is
  wrong at every loop count. Loop count changed phrasing, never a
  verdict, in this arm.
- No per-pass settle signal is observable in this build (see the
  dedicated section). D2 from the charter needs source-level
  instrumentation; it is a patch, not a flag.

## Hash verification (before first run)

Published on the model card (and identical to the HF LFS oid served
for the file): 96080be49ffd67b916018b7bdef8c484762576fb52780e10ab98ac4978a660e0
Measured on the downloaded file:    96080be49ffd67b916018b7bdef8c484762576fb52780e10ab98ac4978a660e0
Byte size: 3,673,288,864 — exact match on both. PASS.

## Method

- Serving: llama-server from the pinned build, one server per loop
  count, started fresh per count. All GPU runs under thor-admit
  leases (run --peak 8G), except one brief debug run noted under
  Incidents.
- Configuration recorded on every run: --override-kv
  dory.num_loops=int:K and dory.recurrent_kv_cache_mode=str:last_loop,
  context 4096, reasoning on (main arm) / off (supplementary arm),
  temperature 0.0, seed 42, cache_prompt false, max_tokens 1024
  (reasoning on) / 256 (reasoning off). Prompts: the fixed six in
  prompts/p1.txt .. p6.txt, kept on disk. Raw responses:
  runs/kK-pP.json and runs/nr-kK-pP.json; per-run server timings are
  inside those JSON files.
- Deviations from the charter, stated: (a) KV mode is last_loop per
  this smoke tasking; D1 in the charter specifies per_loop with a
  pinned prefill chunk. All prompts here are 42-105 tokens, so
  prefill is a single chunk at any plausible chunk size and the
  chunk-sensitivity caveat does not arise. (b) Temperature 0.0
  instead of the vendor-recommended 1.0 / top_p 0.95, chosen so any
  output change across loop counts is attributable to the loop count
  alone. The reasoning-on behaviour below is therefore greedy-mode
  behaviour; vendor sampling may differ. (c) The box was shared
  throughout: the owner's three llama-servers and presence stack
  were resident (about 81-84 GB free of 122.8 GB; my lease 8 GB).
  Absolute speeds are same-conditions measurements on a contended
  box; the cross-loop ratios are the robust figure.

## Evidence of GPU execution

This build's server log at default verbosity prints no offload or
device line. GPU execution rests on: llama-cli --list-devices on the
built binary enumerates "CUDA0: NVIDIA Thor (125748 MiB, 82510 MiB
free)"; prompt-eval rates up to 345 tokens/s were recorded, which
the 14 ARM cores do not reach on this model; nvidia-smi sampled
during a k=2 decode read GPU utilisation 13/13/11/8 percent (memory
utilisation 0 percent) — the GPU is engaged but lightly loaded,
while a CLI probe showed 939 percent CPU (413 s user time in a
44.9 s wall run). Reading: the unrolled nGPT graph is host /
kernel-launch bound in this build, far below the roughly 74
tokens/s bandwidth ceiling implied by 3.67 GB of weights. KV cache
size was not separately observable in the logs; the lease
accounting is CPU-RSS based (matrix peak RSS 2.0 GB) and does not
isolate KV.

## MEASURED — decode speed by loop count (reasoning on)

Server-reported predicted tokens/second on the full 1024-token
generations (the clean long runs; per-prompt values in
runs/summary.tsv):

| Loops | Decode t/s (range over 1024-token runs) | Mean | Ratio to k=1 | Wall time per 1024-token generation |
|---|---|---|---|---|
| 1 | 18.4 - 21.1 | 19.7 | 1.00 | 49 - 56 s |
| 2 | 12.0 - 13.9 | 13.0 | 0.66 | 74 - 86 s |
| 3 | 10.0 - 10.7 | 10.4 | 0.53 | 96 - 103 s |
| 4 | 7.1 - 8.0 | 7.6 | 0.39 | 129 - 144 s |

Step-count prediction from STUDY-DORY.md section 2 (executed steps
72 / 112 / 152 / 192): ratios 1 : 0.64 : 0.47 : 0.375. Measured
ratios track the prediction closely (k=3 slightly better than the
naive figure, as the fixed input/output blocks amortise).
Prompt-eval rates ranged 69 - 346 t/s and were noisier under
contention; they are recorded per run in the summary but are not a
headline figure.

## MEASURED — reasoning-on arm: what each prompt did at each loop count

Prompts: p1 tank arithmetic (correct: 30); p2 syllogism trap
(correct: No, the conclusion does not follow); p3 constrained
writing (exactly 3 sentences, gull in sentence 2, no "sea");
p4 digest trap (correct: NOT IN DIGEST, verbatim); p5 ferry time
(correct: 5h 30m); p6 primes 20-40 (correct: 23, 29, 31, 37).

| Prompt | k=1 | k=2 | k=3 | k=4 |
|---|---|---|---|---|
| p1 | truncated 1024 tok, no content (reasoning reached 30) | same | same | same |
| p2 | truncated, no content, reasoning unfinished | same | same | same |
| p3 | truncated, no content, still re-drafting at cap | same | same | same |
| p4 | STOP 594 tok, content NOT IN DIGEST (correct) | STOP 531 tok, correct | STOP 532 tok, correct | STOP 484 tok, correct |
| p5 | truncated, no content (reasoning reached 5h 30m) | same | same | same |
| p6 | truncated, no content | STOP 503 tok, content 23,29,31,37 (correct) | STOP 719 tok, correct | STOP 653 tok, correct |

Findings, in order of weight:

1. The deliberation trap is loop-invariant at this budget. p1, p2,
   p3 and p5 consumed the entire 1024 tokens in reasoning_content
   and delivered an empty content string at every loop count —
   the empty-content failure mode STUDY-DORY.md flagged from
   BRAIN-BENCH, reproduced on the vendor's own recommended
   operating mode. On p1 and p5 the reasoning demonstrably
   converges on the correct answer early and then keeps
   deliberating about formatting until the cap; the failure is
   termination, not capability.
2. Reasoning does not shorten with depth. Reasoning character
   counts per prompt are roughly flat across k (p1: 3723, 3501,
   3471, 3452; p5: 3261, 3202, 3250, 3075) and grow on p3
   (3862, 3995, 4124, 4034). More loops did not buy briefer or
   better-terminating thought on any prompt that failed to
   terminate.
3. The one clean flip: p6 goes from undelivered at k=1 to
   delivered-and-correct at k=2, and stays correct at k=3, k=4.
   Whatever the second pass settles, this prompt needed it.
4. The one prompt that always completes gets mildly cheaper with
   depth: p4 completion tokens 594, 531, 532, 484 across k.
   Its answer was exactly correct, verbatim, at all four counts —
   no hallucinated forklift at any depth. No confident-wrong
   content was produced anywhere in this arm (the D1 named risk
   did not appear at n=6; that is a smoke sample, not a verdict).

## MEASURED — reasoning-off arm (supplementary; direct answers)

Same prompts, same loop counts and KV mode, reasoning off,
max_tokens 256. All 24 runs finished with stop. Short generations
make the per-run decode rates noisy (4.2 - 20.7 t/s); they are in
runs/summary-noreason.tsv and are not the headline speed table.

| Prompt | k=1 | k=2 | k=3 | k=4 |
|---|---|---|---|---|
| p1 | 30, correct | correct | correct | correct |
| p2 | "Yes" + invalid justification (wrong) | "Yes", garbled justification (wrong) | "Yes", fallacious justification (wrong) | same as k=3 (wrong) |
| p3 | all constraints met | met | met (text identical to k=2) | met |
| p4 | NOT IN DIGEST | NOT IN DIGEST | NOT IN DIGEST | NOT IN DIGEST |
| p5 | 5h 30m, correct | correct | correct | correct |
| p6 | 23, 29, 31, 37 | correct | correct | correct |

In this arm, loop count never changed a verdict. The p2 logic
error is loop-invariant (its justification mutates between k=1
and k=3, then stabilises — the dial rearranges the rationale, not
the answer). Everything the reasoning-on arm failed to deliver,
this arm delivers at k=1 already — i.e. at this prompt scale the
reasoning layer, not the loop count, is what stands between the
model and its own answers. That is a property of this artefact
plus this harness (chat template, greedy decoding), and it is
exactly what D1 exists to measure properly on house fixtures.

## CLAIMED — vendor and anecdote figures (not measured here)

Kept separate from the measured tables, per house rule. Source:
STUDY-DORY.md sections 1-2, from the model card and two
single-operator runs.

| Figure | Value | Source / grade |
|---|---|---|
| SWE-bench Verified at 1/2/4 loops | 50.3 / 59.5 / 61.8 | NVIDIA card, BF16, vendor harness |
| GPQA Diamond at 1/2/4 loops | 69.19 / 72.41 / 72.16 (peaks at 2) | NVIDIA card, BF16 |
| Decode, Q5_K_M, RTX 3060, 8K ctx, 1/2/4 loops | 52 / 35 / 21 t/s | YouTube single-operator, anecdote-grade |
| Decode, Q5_K_M, M4 Mac, 1/2/4 loops | 6.98 / 4.36 / 2.66 t/s | Blog single-operator, anecdote-grade |
| KV at 32K ctx, f16, per_loop, k=1 to k=4 | 1.32 GB to 3.52 GB (last_loop flat) | Derived from config; cross-checked by M4 anecdote |

Context note (prose, labelled): the Thor measured means
(19.7 / 13.0 / 10.4 / 7.6 t/s) sit below the RTX 3060 anecdote at
every loop count, on a contended box with a launch-bound graph;
they are a first Thor datapoint, not a refutation of the anecdote.

## Per-pass settle signal: NOT observable in this build

Checked in source and in the running binaries. The recurrent
block is unrolled into a single compute graph at graph-build
time (src/models/dory.cpp: n_loops read from GGUF metadata,
validated 1-4, block repeated k times over shared weights); the
output head runs once, after the final pass. The graph builder
registers debug callbacks only for the final norm and output
tensors — there are no per-loop tensor callbacks, no per-pass
logits, and neither llama-cli nor llama-server exposes hidden
states or activation deltas (checked --help and the chat
completions surface used above). Consequence for the charter:
D2's question — whether a per-pass representational delta
contracts and predicts stability — cannot be answered with this
build as shipped. It needs a source-level patch to the fork
(record the recurrent block's output tensor after each pass),
which is a small, well-localised change to dory.cpp and the
context, but it is a change. Until it exists, allocation signals
can only come from outside the model (D3 route a/b), exactly as
the charter's fallback describes.

## Incidents and honesty notes

- First matrix attempt produced no data: llama-server /health
  returns HTTP 503 while the model loads, and curl exits 0 on a
  503, so the driver's health gate passed instantly and all 24
  requests were refused inside the load window. Fixed by polling
  for HTTP 200 specifically; the rerun is the data above.
- A shell backgrounding error early on sent one cmake configure
  into the owner's own ~/llama.cpp/build directory (CMake cache
  regenerated with GGML_CUDA=ON, arch 110, Release). No binary in
  that tree was rebuilt or replaced (timestamps verified, Oct 23),
  and none of the owner's processes were restarted or touched.
- One debug llama-server ran about a minute without a thor-admit
  lease while the 503 issue was being diagnosed (one model, about
  4 GB). All matrix and listed runs were leased.
- Two GPU-check servers were orphaned when their SSH channels
  broke, were found wedged (not answering health), and were
  killed by PID. Final state verified: zero build-dory processes,
  zero dory leases, owner's three leases and presence stack
  intact, ports 8901-8904 free.

## Files

- prompts/p1.txt .. p6.txt — the fixed prompt set.
- runs/summary.tsv, runs/summary-noreason.tsv — per-run timings.
- runs/kK-pP.json, runs/nr-kK-pP.json — full raw responses
  (reasoning_content, content, timings) for all 48 runs.
- runs/server-kK.log, runs/server-noreason-kK.log — server logs.
- runs/smoke-k2-p1.out/.err — the initial llama-cli probe
  (k=2, prompt 1; correct reasoning, truncated delivery).
- client.py / client-noreason.py, run_matrix.sh,
  run_matrix_noreason.sh — the harness.
- clone.log, download.log, build.log, matrix.log,
  matrix-noreason.log — process receipts.
