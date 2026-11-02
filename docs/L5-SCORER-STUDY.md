# L5-SCORER-STUDY — the reference-baseline scorer, judged as a scorer

Lane: L5-SCORER-STUDY, 2026-11-02. Offline only (Python/numpy
over stored embeddings); no shipped code touched, no Thor, no
pushes. Scripts: `experiments/l5-scorer/l5_scorer_study.py`
(full results in its `results.json`) and `sensitivity.py`.

**Why this study exists.** The L5 licence
(`LEVERAGE-EXPERIMENTS-1.md`) measured a *spread*: a per-tile
reference built as the mean of ≥ 8 steady observations has a
much tighter steady-state distance distribution than a single
frame (AUDIT p95 0.344 → 0.258). But telltape's shipped scorer
is distance-to-**previous-frame**, and the licence never
measured detection. Casey ruled (2026-11-02, option 3): no core
change until a reference-baseline **scorer** is validated as a
scorer. This study is that validation attempt.

**Pre-registered decision rule** (from the ruling; not adjusted
after seeing numbers). The reference scorer earns a product
path ONLY IF:

- (i) at equal precision to the incumbent it has **higher**
  recall on labelled change, AND
- (ii) at least one maintenance policy holds the drift segments
  silent (zero false verdicts) without collapsing recall.

If either fails: L5 closes as *"spread result real, detection
value not shown on available material"* and the shipped scorer
stands.

## Verdict (stated up front, argued below)

**Both clauses fail. L5 closes under the rule.** The shipped
distance-to-previous-frame scorer stands; no product shape is
proposed. The spread result itself is confirmed again in
passing (reference-form calibration p95 0.353 vs incumbent
0.525; spotless drift tails) — it does not convert into
detection wins on any labelled change this corpus contains.
What would reopen the question is specified at the end.

## Deficits first — where the material cannot separate the scorers

1. **Every labelled change arrives before a streaming reference
   can exist.** C_cuts has no steady run at all (the scene
   alternates every frame); the harbor fixture's only change is
   at frame 4 and its changed tiles reach 8 qualifying
   observations at frame 8. So the streaming reference scorer's
   recall on labelled change is **0 by coverage** — unscored,
   not out-scored. The seeded construction in T2b (reference
   pre-built from a preceding steady watch) is a deployment
   analogue built from stored frames, not stored material.
2. **Two scenes, total.** All 176 C tile-step positives are one
   scene pair (A↔B); the only other positives are 3 harbor
   tile-steps. Every precision/recall below is that pair's
   biography, not a population estimate.
3. **Half of C's positives are returns-to-scene.** A reference
   scorer is *semantically correct* to ignore a return to the
   reference scene; the ground truth labels every boundary a
   cut and the pre-registered rule does not exempt semantics.
   The odd/even split is reported so the reader can see exactly
   how much of the recall gap is this effect: for the seeded
   form it is *all* of it — on departure steps the reference is
   the stronger tile-level detector (recall 0.448 vs the
   incumbent's 0.302), and the entire pooled deficit is the 80
   return tile-steps (incumbent 29/80, reference 0/80).
4. **Calibration shares the corpus's only drift material.**
   Thresholds are fit on A/B steps 1–8 and evaluated on
   disjoint slices (A/B steps 9–11, all of C, the harbor
   fixture) — no test material is tuned on — but with 256
   calibration tile-steps, the p99 threshold is a noisy order
   statistic: τ_inc moves 0.581 → 0.740 across q97.5–q99.9, and
   tile-level C recall is threshold-fragile *for both scorers*
   (incumbent 0.403 / 0.330 / 0.057). Frame-level detection is
   far more stable and is reported alongside throughout.
5. **"Temporally separated" = distinct frames.** The L5
   experiment's mean-8 picks were spread across a 12-frame
   window; a causal scorer cannot spread picks across a window
   it has not seen, and spacing ≥ 2 would cap accumulation at
   6 observations in any 12-frame sequence (the stopped lane's
   own re-pin arithmetic made the same choice). On a real
   30 fps stream, 8 consecutive frames are near-duplicates and
   the separation requirement would bite differently — that
   regime is untestable here.
6. **Qualification uses the incumbent's signal** (the stopped
   lane's definition: steady = the tile did not fire, fire =
   previous-frame step over the calibrated τ_inc). Measured
   consequence on C: at τ_inc = 0.614, the median cross-scene
   step (≈ 0.56) does *not* fire, so 11 of 16 C tiles accumulate
   "references" from alternating A/B frames — chimeras of
   neither scene, whose scores never reach τ_ref. The
   qualification rule is part of the design as specified; its
   interaction with a high incumbent threshold is a finding,
   not an implementation detail.
7. **The shipped pipeline is more than the raw metric.** Its
   published verdict thresholds an EMA/sheaf-smoothed score
   with a stale-carry; the study compares the decide metric
   itself, which the pipeline also thresholds directly
   (`changed_raw`). Smoothing is scorer-agnostic post-processing
   — a reference scorer dropped into the pipeline would receive
   the same smoothing — but the numbers below are raw-metric
   numbers.
8. **The AUDIT set cannot help detection.** Its rows are
   second-pass embeddings of the same images (replicate distance
   exactly 0.0): new measurements of old frames, no new frames.
   It decided the spread question (L5) and has nothing further
   to say here.

## Method

**Material** (stored I-JEPA 1280-dim tile embeddings, 4×4 grid;
`experiments/wave3/driver/embeddings_ALL.jsonl` and
`experiments/wave3/jev/fixture.jsonl`):

| material | shape | ground truth |
|---|---|---|
| A_burst | 12 frames × 16 tiles | one scene, gradual change, zero cuts |
| B_turntable | 12 × 16 | one scene rotating, zero cuts |
| C_cuts | 12 × 16, interleave A0,B0,A1,B1,… | all 11 steps are scene cuts (176 positive tile-steps) |
| harbor fixture | 12 × 16, steady synthetic harbour | 3 changed tile-steps (frame 4, tiles {3,7,11}); 173 no-change steps |
| A++B, B++A (constructed) | 24 × 16, real embeddings concatenated | one seam cut at step 12; lifecycle behaviour only |

**Scorers.** INC (incumbent): score(f,t) = cosine distance
(E[f,t], E[f−1,t]) — cosine distance as in the shipped code
(embeddings not assumed unit-norm). REF: per-tile reference =
mean of the first ≥ 8 qualifying steady observations (frame 0
always qualifies; frame f qualifies iff the tile's incumbent
step at f is ≤ τ_inc); score = cosine distance to the
reference. A tile is unscored until its reference completes;
unscored tile-steps count as misses for recall and cannot fire.

**Maintenance policies** (once a reference exists):
**frozen** — never moves. **adapt05 / adapt20** — on a
non-fired frame, ref ← (1−α)·ref + α·E[f], α = 0.05 / 0.20.
**reset** — a fired frame discards the reference; the tile is
unscored until 8 new qualifying observations accumulate
(frames-unscored counted).

**Threshold discipline** (identical for both scorers):
calibration slice = A + B steps 1–8 (256 tile-steps, all
no-change). τ_inc = p99 of incumbent scores on the slice =
**0.614**. τ_ref = p99 of reference-form scores on the slice,
each computed against a leave-one-out mean-of-8 reference from
frames 0–8 = **0.466**. (Calibration medians: incumbent 0.189,
reference-form 0.154; p95: 0.525 vs 0.353 — the L5 tightening
visible in calibration form.) Sensitivity at q97.5 / q99.9 in
the appendix. Evaluation slices are disjoint from calibration.

**Sanity.** The offline incumbent reproduces the recorded
`raw_score` in `wave3/jev/candidates.jsonl` (frame 1, tile 0:
0.0058314 vs 0.005831 recorded), and at the shipped raw
threshold 0.25 it fires on the harbor frame-4 cut on exactly
tiles {3,7,11} — the loading and metric are the pipeline's.

## Results

### T1 — drift tails (A/B steps 9–11; 48 tile-steps each; all no-change)

| scorer | A false tile-fires | A false frames | B false tile-fires | B false frames | tile-steps scored (A+B) |
|---|---|---|---|---|---|
| incumbent | 3 | {9} | 0 | — | 96 / 96 |
| REF frozen | 0 | — | 0 | — | 95 |
| REF adapt05 | 0 | — | 0 | — | 95 |
| REF adapt20 | 0 | — | 0 | — | 95 |
| REF reset | 0 | — | 0 | — | 89 |

The reference scorer's drift behaviour is genuinely spotless —
this is the spread result expressing itself as silence. The
incumbent, at the same calibration discipline, spends 3 false
tile-fires and one false frame verdict on A's generation jumps.

### T2a — C_cuts, streaming (as stored)

| scorer | TP | FP | precision | tile recall | C frames detected | tile-steps scored |
|---|---|---|---|---|---|---|
| incumbent | 58 | 0 | 1.000 | 0.330 | 11 / 11 | 176 / 176 |
| REF, all policies | 0 | 0 | — | 0.000 | 0 / 11 | 29 / 176 |

11 of 16 tiles do build references on C — from alternating
scenes (deficit 6) — and none of their 29 scored tile-steps
reaches τ_ref. Detection latency: incumbent 0 frames on all
11 boundaries; streaming REF never detects.

### T2b — C_cuts, seeded reference (deployment analogue)

Reference pre-built per tile from A's first 8 qualifying
frames (a preceding steady watch of scene A — C's even frames
are those very images, so even-step scores are
leakage-optimistic; claims rest on the odd steps and the pooled
operating points). Negatives: A steps 9–11 (48 tile-steps) from
the same continuing runs.

| scorer | TP | FP | precision | tile recall | recall, odd steps (departures) | recall, even steps (returns) | C frames |
|---|---|---|---|---|---|---|---|
| incumbent (pooled vs A+B negs) | 58 | 3 | 0.951 | 0.330 | — | — | 11 / 11 |
| REF frozen | 43 | 0 | 1.000 | 0.244 | 0.448 | 0.000 | 6 / 11 |
| REF adapt05 | 37 | 0 | 1.000 | 0.210 | 0.385 | 0.000 | 6 / 11 |
| REF adapt20 | 35 | 0 | 1.000 | 0.199 | 0.365 | 0.000 | 6 / 11 |
| REF reset | 12 | 0 | 1.000 | 0.068 | 0.125 | 0.000 | 4 / 11 |

Every fired tile-step is a departure step; returns are never
fired (deficit 3). For scale: the incumbent's own split is
29/96 on departures and 29/80 on returns — the seeded frozen
scorer out-detects it on departures (43/96) and scores zero on
returns. Reset additionally leaves 103 of 176 C tile-steps
unscored. Latency where detected: 0 frames, all scorers.

**Matched-precision sweep (characterisation, not the
operating point).** Sweeping the reference threshold over the
test pool to match the incumbent's pooled precision (0.951):
frozen reaches recall 0.364, adapt05 0.267, adapt20 0.233,
reset 0.114 — vs the incumbent's 0.330 at its own calibrated
threshold. Frozen's +0.034 edge (6 tile-steps of 176) is real
arithmetic and is **not** counted toward clause (i), for three
stated reasons: the sweep selects a threshold on the test pool,
which the study's discipline forbids for a decision; the
negative pools differ (48 vs 96 tile-steps — B negatives are
meaningless against an A reference); and the comparison
collapses at q99.9 (appendix). At the calibrated operating
points — the comparison the discipline licenses — the best
reference configuration trades *lower* recall for higher
precision, whic
...[truncated 6981 chars]