# PAPER-LEVERAGE — arXiv:2610.39302v1 for telltape / Confluence

Lane: PAPER-LEVERAGE, 2026-11-02. Source read in full LaTeX:
Balestriero & LeCun, "Proving and Improving the Platonic
Representation Hypothesis with JEPAs" (submitted 29 Oct 2026).
Section references are to the paper; tex line numbers are to
`main.tex` as extracted. No code changed, nothing pushed.

## Deficits first — where the paper exposes our record

Four findings, in severity order. None is fatal; two need doc
changes in the extracted tool, one reframes a soak finding, one
sharpens a spec mechanism.

**D1 — The embedder seam is interface-compatible but NOT
data-compatible, and our plan only guards the interface.**
EXTRACTION-PLAN §2.1 makes an embedder swap fail loudly on a
*width* mismatch ("a different embedder with a different width
fails once, loudly"). The paper proves the harder problem is
invisible: two embedders are two different positive-pair kernels,
their misalignment is bounded by kernel mismatch
(Thm. `thm:robust`, §2.2), and the rotation relating their spaces
is *not identifiable from unpaired data at all* (Prop.
`prop:ident`(i), §2.2). A same-width swap (1280-dim model A →
1280-dim model B) passes every guard in the plan while silently
invalidating the baselines, the gate calibration, and the
comparability of ledger rows across the swap. **Doc change
required:** the ledger must record embedder identity + version
per row (or per ledger segment), and an embedder change must
force recalibration, exactly as a lens change would. The plan
never claims distances transfer — but it never forbids the
silent case either. The paper closes that ambiguity: treat
embedder identity as part of the lens.

**D2 — FINDINGS Finding 2 ("calibration creep") is framed as a
calibration problem; the paper says it is partly an ENCODER
problem, and bound refresh alone will decay in effectiveness.**
Finding 2 recommends periodic bound refresh. The paper's
nuisance theorem (Thm. `thm:nuisance`, §2.3) locates a structural
cause: our embedder is, in the paper's own words about its
class, a *bad-view* JEPA — "our image encoders, and DINOv2, are
bad-view JEPAs: their positives are crops of one photograph"
(§2.3, after Prop. `prop:goodbad`). A bad-view encoder provably
spends embedding directions on nuisance (viewpoint, lighting,
rendering) whenever corruptions preserve nuisance more than the
world's k-th direction. Steady-scene surprise creep is then what
nuisance accumulation *looks like* in full-space distance: each
refresh re-baselines into the accumulated nuisance (Finding 2's
own ink-accumulation mechanism is a nuisance story told without
the word). Refresh still helps; the prediction is that it helps
*less each time*. The structural countermeasure — measure the
nuisance share and compute distance in the scene-explained
subspace — is Lever 3, with a falsifier.

**D3 — SPEC §3.2's drift/change distinction is under-specified
in full embedding space.**
The spec separates drift (updates baseline, never publishes)
from change (exceeds the 99th percentile, survives refine) by
distance size, with a pending-drift accumulator for slow state
movement. In the paper's terms, full-space distance mixes state
displacement and nuisance displacement, and no threshold on the
mixture separates them: a creeping shadow line (the spec's own
example) is nuisance drift that will either poison the baseline
or fire as `slow-change`, decided by magnitude alone. The
distinction the spec wants is state-vs-nuisance, which is a
*subspace* distinction (Lever 3), not a threshold distinction.
Flagged, not fatal: the mechanism works as a ranker today; the
paper names what it cannot express.

**D4 — Nothing in our docs may cite the headline theorem
without its conditions.**
The Platonic Representation Theorem is a population statement
over a finite world with injective renderings, a *shared*
positive-pair distribution, and minimizers unique up to
rotation, proved for whitened/spectral JEPAs with an identity
predictor; the authors state plainly that learned-predictor
world-model JEPAs are "not covered" (§2.1) and that "no
experiment meets the hypotheses of thm:exact exactly"
(Limitations, §6). Production I-JEPA departs on at least two
counts (learned predictor; crop positives). Any sentence in our
docs of the form "embeddings of the same scene coincide" is an
overstatement; the defensible form is Lever 1's.

---

## The levers

### L1 — The theorem as the *conditional* licence for embedding-distance change detection

**Result.** Thm. `thm:exact` (§2.1, tex L117): if M ≥ 2
modalities share one positive-pair distribution π and the
minimizers of the JEPA objective are unique up to rotation,
every modality's optimal encoder satisfies f_m∘g_m = Q_m·h* —
one world embedding, up to one rotation each. Prop.
`prop:spectral` (L127) discharges the uniqueness for the
whitened/spectral case: ℓ = squared distance, Ω whitening
(E h = 0, E hhᵀ = I_k), minimizers = the top-k eigenvectors of
the normalized positive-pair kernel K_π, unique iff the
eigengap μ_k > μ_{k+1} holds.

**What it licenses for us.** Our gate uses distance *within one
embedder's space*, where the rotation cancels identically — so
we need only the weaker, defensible claim: an embedder trained
so that two observations of one scene are positives defines a
geometry in which same-scene points are near *by construction
of the training objective*, not by hope. That is the foundation
sentence telltape's docs currently assert informally. The paper
turns it into a citable, *conditional* claim — and the
conditions are the content: the licence holds to the extent the
embedder's positives are scene-pairs, and degrades exactly as
Lever 2 quantifies when they are not.

**Falsifiable application.** Doc change (BYO-embedder doc +
GRID.md rationale): replace the informal foundation with the
conditional form, naming the two production departures
(predictor, crop positives). The empirical premise is checkable
on data already in this tree: in
`experiments/wave3/driver/embeddings_ALL.jsonl` (576 rows of
1280-dim tile embeddings with seq/frame/tile), same-scene
re-observations (A_burst repeats, control material) must sit
systematically closer to their scene's baseline than cross-scene
pairs do. They did — wave 3's gate scored precision/recall
1.000/1.000 on sequence C. **Proves it wrong if:** a re-run of
that separation statistic on the stored embeddings shows
same-scene and cross-scene distance distributions overlapping
(AUC ≈ 0.5); then the foundation claim fails on our own data
regardless of the theorem.

### L2 — The kernel-mismatch bound is the formal shape of "ranker, not separator"

**Result.** Thm. `thm:robust` (§2.2, tex L137): for two
positive-pair kernels with the same marginal, the RMS distance
between their spectral embeddings after the *best* rotation is
≤ (2√2/δ)·min(√k·‖K₁−K₂‖₂, ‖K₁−K₂‖_F), where δ = μ_k − μ_{k+1}
is the eigengap of the second kernel. Validated on 300 random
finite worlds: observed error ≤ 18% of the bound, always below
it (fig. `fig:dk`). Block form (cited in text): directions
separated by large spectral gaps are protected; directions near
the end of the spectrum "need not align at all."

**What it predicts for us.** (a) Our headline audit caveat —
the gate is a ranker, not a separator — is not an implementation
shortcoming; it is the expected behaviour whenever the kernel
that produced the embeddings differs from the kernel the scene
is currently inducing (different embedder, different regime,
different coverage). No threshold turns a bounded-misalignment
geometry into a separator; precision/recall trade along the
bound. Docs should say this once, with the citation, instead of
apologising per-experiment. (b) Regime shift is kernel shift:
day/night, weekday/weekend are different induced kernels
(Lever 7), so gate *calibration* is per-kernel while gate
*ranking* is what survives across kernels.

**Falsifiable application.** On the soak ledger after the
2026-11-03 verdict: compute per-tile surprise ranks in each 6 h
window and the Spearman rank correlation of tile surprise
across windows of different regimes (day vs night), on
no-event stretches. Prediction: absolute surprise levels shift
across regimes (calibration moves) while cross-regime rank
correlation stays materially positive (the ranking is the
kernel-robust part). **Proves it wrong if:** cross-regime rank
correlation ≈ 0 — then ranking does not survive kernel shift
either, the bound's picture does not describe our geometry,
and per-regime recalibration must be from scratch, not a
re-centring.

### L3 — Nuisance: the measurable reason the gate creeps, and the subspace fix

**Result.** Thm. `thm:nuisance` (§2.3, tex L169): for centered,
whitened encoders, min over rotations of E‖Qf₁(x₁) − f₂(x₂)‖² ≥
2k(1 − min_m ρ(f_m)), where ρ(f) = tr C_f^{1/2}/k ∈ [0,1] is
the scene-explained fraction (C_f = covariance of E[f(x)|z]);
ρ = 1 iff the embedding is a function of world state alone.
Prop. `prop:goodbad` (L179): a good-view JEPA (positives = two
observations, independent nuisances) achieves ρ = 1; a bad-view
JEPA (positives = corruptions of one observation) spends r ≥ 1
of its k directions on nuisance iff the corruptions keep more
nuisance correlation (β₁) than the state's k-th-direction
correlation (α_k), and its cross-modal alignment error is then
≥ 2r. Measured on Flickr at k = 32 (§3.1, tex L274): ρ = .804
good-view / .655 bad-view / .608 next-token; the theorem's
lower bounds (12.6 / 22.1 / 25.1) and the measured errors
(33.5 / 39.4 / 40.3) agree in order.

**What it licenses for us.** Our tile embedder is a bad-view
JEPA by construction (crop positives), so some of its 1280
directions encode viewpoint/lighting/rendering nuisance *as a
theorem*, not as a suspicion. Three consequences. (1) It
predicts Finding 2's creep and D2's refresh-decay. (2) It gives
the creep a *measurable per-tile quantity*: ρ̂ estimated from
repeated steady observations (within-scene variance vs total
variance, exactly the paper's C_f construction). (3) It
licenses the fix the spec's §3.2 lacks (D3): compute change
distance in the scene-explained subspace — project out the
directions that steady-state re-observation says are nuisance —
so relighting stops competing with arrivals in the same metric.

**Falsifiable applications (two, both on existing data).**
(a) *Wave-3:* A_burst/control embeddings are repeated
observations of near-identical scenes = nuisance-only variation.
Estimate the nuisance subspace from within-scene differences,
recompute sequence C's change ranking with distance restricted
to the scene subspace, compare AUC / precision-at-fixed-recall
against the shipped full-space distance. Prediction: separation
improves. **Proves it wrong if:** ΔAUC ≤ 0 on held-out C
boundaries — the nuisance story does not transfer to tile
embeddings and the subspace fix is dead.
(b) *Soak, post-verdict:* estimate per-tile ρ̂ from steady
stretches; prediction: per-tile steady-state surprise growth
(the verdict job's calibration-ageing statistic) is largest on
low-ρ̂ tiles. **Proves it wrong if:** the correlation between
ρ̂ and surprise growth is ≈ 0 — creep is then not
nuisance-structured and Finding 2's plain refresh is the whole
remedy after all.

### L4 — Cross-embedder migration: k pairs or geometry, never moments

**Result.** Prop. `prop:ident` (§2.2, tex L160): (i) every
rotation of a whitened embedding is whitened, so *no statistic
of the first two moments of unpaired samples identifies the
rotation* between two embedding spaces; (ii) n ≥ k paired world
states whose embeddings span R^k identify the rotation uniquely
as the orthogonal-Procrustes minimizer; when positives differ,
more pairs average out the residual misalignment of
`thm:robust`. The pair-free alternative (§5.2, `sec:pairfree`)
recovers the map from shared geometry alone (cluster matching +
optimal transport, Schnaus et al.'s method unchanged) — but on
Flickr's smaller unpaired pools *only good-view JEPAs left
chance* (R@1 16.4% ± 10.4%); bad-view and next-token encoders
scored ≤ 0.3%.

**What it licenses for us.** A concrete protocol for D1, to be
written into the seam spec (EXTRACTION-PLAN §2.1): carrying a
baseline across an embedder swap requires ≥ k anchor scenes
embedded by both embedders and a fitted Procrustes rotation —
budget more anchors when the two embedders' positives differ
more. And a prohibition, stated once so nobody builds it:
moment-matching "self-alignment" (match means/covariances,
whiten both sides) provably cannot find the rotation. The
pair-free route is *predicted to fail with our embedder class*
(bad-view), which is itself a useful negative: do not schedule
it; if it is ever tried, its failure is the expected outcome,
not a bug report.

**Falsifiable application.** Runnable entirely on wave-3 files:
construct a synthetic second embedder from `embeddings_ALL.jsonl`
(a fixed random rotation composed with projection onto the
top-768 principal components — a different space, same scenes).
Fit Procrustes on n anchor (frame, tile) pairs, rotate, and
re-score sequence C's change ranking. Prediction: AUC recovers
to within noise of the un-rotated ranking once n ≥ k = 768
anchors span the space, and degrades smoothly below it.
**Proves it wrong if:** recovery fails at n ≥ k — the migration
protocol is unsound at our scale and the seam spec must instead
mandate full recalibration with no carry-over, full stop.

### L5 — Good-view construction as the baseline recipe: average observations, trim to the shared part

**Result.** Three convergent pieces. (a) Trimming is the one
knob that matters (§3.2, tex L283–284): views drawn from
*different observations of the same state, each trimmed* — whole
captions as views lose a quarter of the alignment (.185 vs
.246 R@1); masking, view count, batch, width, schedule each
move the mean by ≤ .016. Their recommendation, verbatim in
substance: views from different observations of the same world
state, each trimmed (cropped, for images) and lightly masked.
(b) Frame averaging (§5.1, video): the mean of 8 frames of a
clip raises fit-free mutual 10-NN from .148 (middle frame) to
.167, "as thm:nuisance suggests: the frames of a clip are
several observations of one scene, and their mean averages out
what is particular to each frame." (c) Data kind (§2.3, tex
L205; `tab:sources`): under identical bad views, literal
descriptions of what is visible (LLaVA recaptions) align better
than alt-text — chains of shared positives stay within a scene
for literal text and cross scenes through shared nuisance
(brand names) for alt-text.

**What it licenses for us.** A baseline-construction rule with
a citation behind it: a tile's baseline should be the **mean of
embeddings over N ≥ 8 temporally separated steady observations**
— distinct observations whose nuisances differ — not a single
frame and not an EMA dominated by near-duplicate frames
(near-duplicates share nuisance, so averaging them averages
nothing out). This is a change to how baselines are *built*,
independent of Lever 3's subspace projection, and the two
compose. It also retro-licenses the spec's conservative
baseline admission (§3.2): admission is exactly the act of
choosing which observations get to be "views" of the baseline
state, and the paper says that choice *is* the kernel choice
(Lever 7).

**Falsifiable application.** On wave-3 data: build the tile
baseline two ways — single frame vs mean-of-8 separated frames
from A/control material — and compare the no-change distance
distribution (spread, 95th percentile) on the AUDIT embeddings.
Prediction: the mean-of-8 baseline cuts the steady-state
distance spread materially (≥ 20% at the 95th percentile).
**Proves it wrong if:** the reduction is < 5% — plausible,
because the paper's averaging gains are demonstrated
cross-modally and ours is within-embedder; if so, baseline
construction stays as-is and L5 is recorded as tested-and-dead
at our scale. Soak version (post-verdict, offline replay):
same comparison on ledger windows.

### L6 — Next-token prediction is a bad-view JEPA: the presence layer's wording sensitivity is structural

**Result.** Prop. `prop:ntp` (§2.4, tex L218): the next-token
loss decomposes into a JEPA prediction term plus the softmax
log-partition as anti-collapse; its positives are a prefix and
its continuation *within one document*; at the optimum its
representations are identified only up to GL(k), not a
rotation, and its induced kernel relates texts through shared
wording. The authors flag the next step as heuristic, then test
it: NTP should spend directions on document nuisance (author
wording, style) — and measured ρ agrees (.608, the lowest of
the three, §3.1). A second implicit positive exists (contexts
sharing a continuation gather), but one token rarely spans a
scene, so scene-joining needs long chains — "why language
models align with vision mostly through scale."

**What it licenses for us — two systems.**
(a) *Presence.* The brain reads a TEXT digest of verdicts. By
this result, a language model's take on the digest is provably
a wording-sensitive view of the scene, not a neutral read:
same verdicts, different phrasing → representations that differ
in nuisance directions the facts never touched. This is the
theorem-shaped justification for the discipline presence v2
already adopted (verdict-only grounding, citation ids, digest
pre-computing staleness into words) and it extends it: **digest
phrasing is part of the instrument** — fixed templates, literal
descriptions of what was seen (Lever 5c: literal beats
alt-text-style), numbers carried as numbers, no free paraphrase
between the ledger and the brain. Any future "let the model
summarise the ledger in its own words first" step inserts a
bad-view re-encoding into the chain and should be refused on
this citation.
(b) *The judge constitution.* FINDINGS Finding 1 measured the
jev-semantic judge picking the polished dangerous option 2/6 —
"the judge grades how settled a sentence sounds." Prop.
`prop:goodbad` applied to text encoders is that measurement
with the mechanism named: text embeddings spend directions on
wording, so a similarity/coherence judge built on them is
structurally wording-sensitive, not merely undertuned. The
advisor-only constitution now has a theory citation, and any
future proposal to give a text judge a gate must answer it.

**Falsifiable application.** On data in this tree
(`experiments/wave3/jev/fixture.jsonl` + truth): score the
judge on meaning-preserving rewrites of its fixture items vs
minimal meaning-changing edits. Prediction: score variance
across rewrites is a substantial fraction (≥ 25%) of variance
across meaning-changing edits. **Proves it wrong if:** the
ratio is < 10% — the judge is wording-robust at our scale and
Finding 1's fluency result needs a different explanation.
Presence version (post-soak): render 20 ledger verdict sets in
two faithful phrasings, ask the brain identical questions,
count answers that change a cited fact; template-only rendering
is ~0 by construction, paraphrase is predicted ≥ 15%.

### L7 — Coverage: views × data set the kernel — the principled form of recalibration

**Result.** Thm. `thm:coverage` (§2.3, tex L195): a spectral
JEPA learns, within τ_m, the spectral embedding of the world
kernel π_{W_m} its positives *and its data* induce; τ_m grows
with how much the positives mix state with nuisance and
vanishes for good views; two modalities agree exactly as well
as their induced kernels' top eigenvectors do, ± τ₁ + τ₂.
Finite-sample companion (tex L205): weak views need density —
the reach bad views need falls as Δ ∝ log N / N in samples per
state — while reach large enough to cross scenes caps alignment
at any sample size. Good views "fix the world kernel by
design," bad views "get it from the data" (fig. `fig:positives`).

**What it licenses for us.** Recalibration stops being hygiene
and becomes a named act: the gate reads the kernel the
*calibration data induced*, and a soak's data coverage changes
across 48 h (light, occupancy rhythms, weather), so the induced
kernel — hence the geometry the gate's numbers live in — is a
function of the window you calibrated on. This is the theory
form of Finding 2 and of the spec's diurnal re-fit (§3.2), and
it predicts *when* recalibration pays: in proportion to
coverage shift between windows, not to elapsed time.

**Falsifiable application.** Soak ledger, post-verdict:
compute steady-stretch surprise distributions per 6 h window;
regress window-to-window distribution shift on (a) elapsed time
and (b) coverage covariates (hour-of-day / light proxy from
mean tile brightness in the ingest record). Prediction: (b)
dominates (a). **Proves it wrong if:** shift is monotone in
elapsed time and covariate-independent — pure ageing, the
coverage account is wrong for our stream, and refresh scheduling
should be a plain clock.

---

## NOT USABLE — recorded so nobody imports them later

- **The 42× sample-efficiency headline and the "beats 72B
  language models" benchmarks.** Statements about training text
  encoders for cross-modal retrieval alignment. We train no
  encoder and align to no LLM. Importing the number into our
  docs would be decoration; the mechanism (views set the
  kernel) is already Lever 7 without it.
- **The scaling law's fitted form and exponents** —
  R@1 = a + d·log M + b·log(1 + q^α M^β N^γ / c) (§4.3):
  exponents "poorly identified," fitted on one recipe, and it
  *fails inside the paper* at 4× its fitted range for good
  views (predicted .455 vs actual .418 at q = 1, 320M samples).
  The authors fence it themselves: "an empirical summary of one
  recipe, not a consequence of thm:coverage." No exponent, and
  not even the log-form, transfers to gate calibration, soak
  length, or capacity planning. The qualitative moral (more
  samples substitute sub-linearly for better views) is noted
  under Lever 7 and carries no numbers.
- **The captioner as a description layer for presence**
  (§5.1). One rotation fitted on pairs + a text-only decoder
  does produce scene descriptions from embeddings (CIDEr .838
  on COCO), and the noise-matching recipe σ = (c⁻² − 1)^½ tied
  to the residual cosine is genuinely elegant. But presence
  reads a text ledger today; no fitted-rotation description
  layer exists, and building one is a new feature, not a
  leverage of an existing surface. Recorded with its recipe
  (including Prop. `prop:ident`'s ≥ k pairs requirement) in
  case a description layer is ever chartered — and no sooner.
- **Pair-free alignment as a roadmap item.** Covered in Lever
  4 as a *negative* prediction for our embedder class; listed
  here so it is not re-proposed as an opportunity.
- **All benchmark numbers as performance evidence for us**
  (Flickr/WIT/MSR-VTT retrieval, mutual 10-NN, CKA): different
  task (retrieval/alignment), different data. Only mechanisms
  transfer; Lever 3's ρ ordering is used as a mechanism check,
  not as a prediction of our ρ values.
- **Training-side results** (LeJEPA/SIGReg behaviour, collapse
  without gradient clipping, hyperparameter sensitivities,
  §3.2's stability findings): we train nothing; the seam
  consumes frozen embedders. If a future lane fine-tunes an
  embedder, the gradient-clipping finding is the first thing to
  re-read — until then, no bearing.
- **Thm. `thm:exact` quoted without conditions** (see D4): the
  exactness itself is the one "result" most likely to be
  smuggled into our docs and the least available to us —
  population optima, injective renderings, shared positives,
  identity predictor. The usable content is L1's conditional
  form and L2's bound, not the equality.

## Appendix — condition cheat-sheet (for doc citations)

| Claim we may cite | Where | Conditions that must travel with it |
|---|---|---|
| Same-scene embeddings share one geometry up to rotation | Thm. `thm:exact`, §2.1 | shared positives; population optima; uniqueness up to rotation; identity predictor |
| Misalignment ≤ (2√2/δ)·kernel mismatch | Thm. `thm:robust`, §2.2 | spectral/whitened solutions; eigengap δ > 0; validated ≤ 18% of bound (300 synthetic worlds) |
| Nuisance costs ≥ 2k(1 − ρ); bad views spend ≥ 1 direction on nuisance iff β₁ > α_k | Thm. `thm:nuisance`, Prop. `prop:goodbad`, §2.3 | centered whitened encoders; corruption model acts on state/nuisance separately |
| Rotation needs ≥ k pairs; moments can never find it | Prop. `prop:ident`, §2.2 | embeddings of the n states must span R^k |
| Views × data induce the kernel actually learned | Thm. `thm:coverage`, §2.3 | spectral objective; τ grows with state/nuisance mixing in positives |
| NTP positives are within-document; identified up to GL(k) only | Prop. `prop:ntp`, §2.4 | linear softmax head; the nuisance consequence is the authors' tested heuristic, not a corollary |
