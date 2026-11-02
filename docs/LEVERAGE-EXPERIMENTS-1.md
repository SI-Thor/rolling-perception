# LEVERAGE-EXPERIMENTS-1 — the wave-3-decidable levers, run

Lane: LEVERAGE-EXPERIMENTS, 2026-11-02. Runs the three
falsifiable applications from `PAPER-LEVERAGE-2610.39302.md`
(Balestriero & LeCun, arXiv:2610.39302) that the stored wave-3
data can decide now: L1 (same/cross-scene separation), L3(a)
(nuisance share ρ̂ + the subspace fix), L5 (baseline recipe).
Falsifiers are the memo's, quoted before each result; none was
moved. L2, L3(b), L4, L6, L7 need the soak ledger or other data
and are not run here.

Data: `experiments/wave3/driver/embeddings_ALL.jsonl` (576
I-JEPA 1280-dim tile embeddings: A_burst / B_turntable /
C_cuts, 12 frames × 16 tiles each) and `embeddings_AUDIT.jsonl`
(60 second-pass embeddings). Distance is cosine distance
(1 − cos), the shipped harbor-watch metric. Scripts:
`experiments/leverage/{common,l1_same_scene_auc,l3_nuisance,
l5_baseline_recipe}.py` (numpy, seed 20261102); every number
below is their stdout.

## Deficits first — what this data cannot decide

1. **There is no nuisance-only control in the tree.** The memo's
   L3(a) premise calls A_burst "repeated observations of
   near-identical scenes." The wave-3 RESULTS.md says otherwise:
   A's frames are fresh generations (mean tile diff 63.9/255),
   and B is continuous rotation. Within-scene variation here is
   nuisance *mixed with genuine gradual change*. Consequence,
   stated once and applied throughout: L3's "nuisance subspace"
   is estimated from that mixture, and ρ̂'s complement is an
   **upper bound** on pure nuisance. L3's falsifier still
   applies as pre-registered — but its failure cannot
   distinguish "the nuisance story is false" from "nuisance is
   not identifiable from within-scene variation in this
   material." What is missing, exactly: repeated embeddings of
   a truly unchanged scene under varying nuisance only (same
   camera, same scene, lighting/viewpoint variation), or the
   soak's steady stretches (L3(b), post-verdict).
2. **The stored embedder is deterministic; there is no
   measurement-noise term to find.** C_cuts' frames are the A/B
   source images re-embedded in a separate rack pass, and the
   AUDIT rows are a second pass over the same tiles: both
   replicate sets are at cosine distance **exactly 0.0** (max
   ~2×10⁻¹⁶) from the ALL embeddings of the same image. Every
   distance below is therefore content variation, none of it is
   re-embedding noise. (This also cross-validates the loading:
   recomputing the AUDIT file's `prev_cos_drift` from the
   stored embeddings reproduces it to max abs error 5.0×10⁻⁷.)
3. **Two scenes, total.** A and B are the only scenes in the
   tree. ρ̂'s between-scene term rests on one scene pair, and
   the AUCs are two-scene numbers. They decide the falsifiers
   as pre-registered; they assert nothing about many-scene
   streams.
4. **ρ̂ is a trace-ratio analogue, not the paper's ρ.** The
   paper's ρ = tr C_f^½/k needs whitening in 1280 dims; per
   tile we have 24 observations. We compute the variance-
   decomposition ratio SS_between-scenes / SS_total instead.
   Its values must not be quoted next to the paper's measured
   .804 / .655 / .608 as if commensurate.
5. **L5's test set is 53 tiles** (AUDIT rows for A: 13, B: 40;
   C's 7 excluded by design — see L5). A p95 over 53 points is
   a noisy order statistic; a bootstrap CI is reported with it.

## L1 — same-scene vs cross-scene separation

**Memo's falsifier:** "a re-run of that separation statistic on
the stored embeddings shows same-scene and cross-scene distance
distributions overlapping (AUC ≈ 0.5)" — then the foundation
claim fails on our own data.

**Method.** Tile-matched pairs (tile identity controlled).
Same: same tile, two frames of one sequence (A or B) —
2,112 pairs. Cross: same tile, one A frame × one B frame —
2,304 pairs. AUC = P(d_cross > d_same). Also the memo's
baseline form: each embedding's distance to its own scene's
leave-one-out mean baseline (same tile) vs the other scene's
mean baseline (same tile), 384 embeddings each side.

**Numbers.**

| statistic | median | p95 | AUC |
|---|---|---|---|
| same-scene pairs (n=2,112) | 0.287 | 0.544 | — |
| cross-scene pairs (n=2,304) | 0.561 | 0.741 | 0.924 vs same |
| same, adjacent frames only (n=352) | 0.193 | 0.565 | 0.927 vs cross |
| own-scene LOO baseline (n=384) | 0.158 | 0.355 | — |
| other-scene baseline (n=384) | 0.465 | 0.664 | 0.983 vs own |

**Verdict: NOT falsified — the licence holds on our data.**
AUC 0.924 (raw pairs) and 0.983 (baseline form) against a 0.5
kill line. The honest texture: 0.924 is not ~1.0 — the tails
overlap (same-scene p95 0.544 ≈ cross-scene median 0.561),
which is L2's ranker-not-separator behaviour visible in the
same table. The baseline form separates far better than raw
pairwise distance, which is the first hint of L5's result.

**Implication for telltape.** The doc change the memo already
prescribed (BYO-embedder foundation sentence, conditional
form) can now carry a measurement, not just a citation:
on wave-3 I-JEPA embeddings, embedding distance discriminates
same-scene from cross-scene at AUC 0.92 pairwise / 0.98
against a mean baseline. No code change.

## L3 — nuisance share ρ̂, and the subspace fix

**Memo's falsifier (a):** "ΔAUC ≤ 0 on held-out C boundaries —
the nuisance story does not transfer to tile embeddings and
the subspace fix is dead."

**ρ̂ method.** Per tile: 24 steady re-observations (12 A + 12 B
frames of that tile); ρ̂ = SS_between-scenes / SS_total
(trace form; deficit 4 applies). Nuisance share = 1 − ρ̂
(upper bound; deficit 1 applies).

**ρ̂ numbers.** Per-tile ρ̂ ranges 0.248–0.502 across the 16
tiles, median **0.326** (IQR 0.107); pooled per-tile ratio
0.349; pooled over (tile, scene) cells 0.434. Median
nuisance-share upper bound ≈ **0.67**: on this material, at
most a third of a tile's steady-state embedding variance is
explained by which scene it is in. Read strictly: the
within-scene remainder includes genuine change (deficit 1),
so this bounds, and likely overstates, the paper's nuisance
share. It does establish the ordering the mechanism predicts —
the scene-explained fraction is nowhere near 1 for a
crop-positive (bad-view) embedder.

**Subspace-fix method.** Nuisance subspace = top principal
components of pooled within-cell deviations (x − its
(scene, tile) mean). **Held out by construction:** estimate on
tiles 0–7, evaluate on tiles 8–15, and vice versa; pooled
results cover all 16 tiles with no step evaluated on a
subspace it contributed to. Headline m = smallest m capturing
≥ 50% of within-cell variance (m = 9 and 8 in the two halves;
rank 176). Task: consecutive-frame step distance, positives =
C_cuts steps (176; every boundary is a cut), negatives = A/B
steps (352). Score: cosine distance after projecting out the
nuisance subspace vs shipped full-space cosine distance.

**Numbers.**

| | full-space AUC | subspace AUC | ΔAUC |
|---|---|---|---|
| est. tiles 0–7 → eval 8–15 | 0.924 | 0.909 | −0.016 |
| est. tiles 8–15 → eval 0–7 | 0.929 | 0.921 | −0.008 |
| pooled held-out | 0.926 | 0.915 | **−0.012** |

Bootstrap 95% CI on pooled ΔAUC: **[−0.029, +0.008]**.
Precision at 90% recall, pooled: 0.712 full vs 0.693 subspace.
Sweep over m ∈ {8, 32, 64, 128, 256}: ΔAUC is negative in one
cross-fit direction at every m and sign-inconsistent in the
other (−0.024…+0.016) — no dose-response, i.e. no m rescues it.

**Verdict: FALSIFIED as specified.** ΔAUC ≤ 0 — negative in
both independent directions at the pre-registered m. The
subspace fix (project out top within-scene PCs, cosine in the
remainder) is dead on this data, per the memo's own terms.
Why, labelled as interpretation, not result: the top
within-scene directions of *this* material are dominated by
genuine change (deficit 1), so the projection removes signal
along with nuisance — likely including directions the A↔B cut
itself uses. The experiment does **not** decide whether
nuisance-structured creep exists (that is L3(b) on the soak's
genuinely steady stretches, plus a nuisance-only control that
does not yet exist); it decides that this construction of the
fix does not work here.

**Implication for telltape.** Nothing: do not build subspace
distance, do not change the metric. The shipped full-space
cosine distance survives its challenger. ρ̂ remains worth
computing on soak data as a *diagnostic* (L3(b): does
per-tile surprise growth track low ρ̂?) — that tests the
diagnosis, not this fix, and is already inside the verdict
job's calibration-ageing frame.

## L5 — baseline recipe: mean-of-8 vs single frame

**Memo's falsifier:** p95 spread reduction < 5% kills the
recipe change. **Memo's prediction:** ≥ 20% at the 95th
percentile.

**Method.** Test set: the 53 AUDIT embeddings from steady
sequences (A: 13, B: 40; C's 7 rows excluded — a cross-frame
baseline over alternating scenes is ill-defined). Per row
(seq s, frame f, tile t, audit embedding e), baselines built
from ALL embeddings of (s, ·, t):
- **single** (the shipped incumbent — harbor-watch compares
  against the previous published embedding): frame f−1.
- **ema**: causal EMA over frames 0…f−1, α = 2/9 (effective
  window ≈ 8). Secondary comparator, not shipped.
- **mean8**: mean of 8 temporally separated frames, f excluded
  (f is e's own image — including it would leak), picked
  evenly from the remaining 11.
Statistic: p95 of the distance set (pre-registered primary),
median/IQR alongside; bootstrap (10k row resamples) CI on the
p95 reduction.

**Numbers.**

| baseline | median | p95 | IQR |
|---|---|---|---|
| single frame (incumbent) | 0.138 | 0.344 | 0.136 |
| EMA α=2/9 | 0.165 | 0.368 | 0.091 |
| **mean of 8** | 0.141 | **0.258** | 0.074 |
| replicate floor (same image, 2nd pass) | 0.000 | 0.000 | — |

p95 reduction, mean8 vs single: **25.1%**, bootstrap 95% CI
**[15.9%, 50.9%]**. Median reduction: −2.0% (mean8's median is
a hair *worse*). EMA is worse than even single-frame at both
median and p95 on this material.

**Verdict: NOT falsified — the recipe change is licensed.**
The reduction clears the 5% kill line by a wide margin (CI
entirely above it) and meets the memo's 20% prediction at the
point estimate (CI straddles 20%). The honest shape of the
win: mean-of-8 does not move the centre — it **tightens the
tail** (p95 −25%, IQR −45%). For a gate, the tail is the
operative region: thresholds sit there, so a tighter
steady-state tail means fewer no-change excursions nominated
past a fixed gate, at the same centre behaviour.

**Implication for telltape.** A default/doc change, of the
bounded kind: baseline *construction* should be the mean of
≥ 8 temporally separated steady observations per tile (the
memo's L5 rule), replacing single-frame baselines wherever a
baseline is built or re-admitted — admission/recalibration is
where this lands first; a streaming decide step can keep a
small reservoir of separated steady frames per tile (cost:
8 × 1280 floats per tile, nothing). Two fences on the claim:
(1) EMA is **not** an equivalent shortcut — it underperformed
single-frame here, so "just EMA the baseline" should not be
substituted for the mean-of-separated-observations recipe;
(2) the evidence is 53 tiles from generated/turntable
material with 12-frame sequences — the memo's soak version
(post-verdict offline replay over ledger windows) is the
longer-horizon confirmation, and the recipe should be
documented as wave-3-proven, soak-pending.

## Summary

| lever | pre-registered test | result | verdict | telltape consequence |
|---|---|---|---|---|
| L1 | same/cross AUC ≈ 0.5 kills | 0.924 pairs / 0.983 baseline form | licence holds | doc: foundation sentence gains a measurement |
| L3(a) | ΔAUC ≤ 0 kills the fix | ΔAUC −0.012 (both directions < 0) | **fix dead** | none — full-space distance stands; ρ̂ = diagnostic only |
| L5 | p95 reduction < 5% kills | 25.1% [15.9, 50.9] | recipe licensed | default change: baselines = mean of ≥ 8 separated steady observations; EMA explicitly not a substitute |

## Appendix — reproduction

```
cd experiments/leverage
python3 l1_same_scene_auc.py   # L1 (+ replicate floor)
python3 l3_nuisance.py         # rho-hat, cross-fitted subspace test
python3 l5_baseline_recipe.py  # AUDIT validation + recipe comparison
```

Inputs are read-only (`experiments/wave3/driver/*.jsonl`).
Nothing in the shipped crates was modified.
