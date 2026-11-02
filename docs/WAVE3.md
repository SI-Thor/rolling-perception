# Wave 3 — the first real workload: harbor-watch

v0.1 proved the scheduling arithmetic on synthetic lanes. v0.2 proved
the GPU mechanisms on the real Thor. Wave 3 puts a **real workload**
through the machinery: rolling visual change detection over real
frames, perceived by the Thor's own **I-JEPA** (the JEV rack, :8077),
decided in Rust on the substrate rings, with an optional reflective
judge (TypeSafe Jev) evaluated separately.

The workload in one sentence: *a camera watches a scene; spend the
expensive perception (a 173 ms I-JEPA embed) only where the scene
actually changed, and publish a verdict per tile as it lands — not a
verdict per frame after everything finishes.*

## Material (real, on the Thor, ground truth known)

| seq | source | truth |
|---|---|---|
| A_burst | 12 sequential burst frames, one generated scene (image-studio outputs) | same scene, no cuts — but see the A finding below |
| B_turntable | 12 frames of the dock turntable (sitka-distill showcase) | one scene rotating gradually, no cuts |
| C_cuts | A and B interleaved frame-by-frame | **a scene cut at every one of the 11 boundaries** |

Frames are tiled 4×4 (128×128 crops). Cheap perceive = per-tile
mean-abs frame diff (numpy, µs). Expensive perceive = I-JEPA embed of
the tile crop (1280-dim), via the rack. Full method, schema and
ground truth: `experiments/wave3/driver/` (RESULTS.md, SCHEMA.md,
GROUND_TRUTH.md, driver.py).

## Measured on the Thor (2026-11-01)

- Rack embed latency per tile crop: **p50 173 ms, p95 200 ms**
  (n=887, excluding the 11.9 s one-time lazy model load).
- **ALL** (embed every tile): 576 embeds, 119.6 s of rack time.
  **CHANGED** (embed only tiles whose diff ≥ the pooled median,
  a threshold rule fixed before the run): **312 embeds, 55.0 s —
  46% fewer calls, 54% less time.**
- The gate follows the ground truth per sequence: B (gradual
  turntable) kept only **23/192** embeds (−88%); C (a cut every frame)
  kept 157/192; A kept 132/192.
- **Audit** (skipped tiles embedded anyway, kept separate): skipped
  tiles' embedding drift vs previous frame mean **0.202** vs
  embedded-band **0.484** — the µs diff ranks true embedding drift
  ~2.4×. It is a ranker with a budget knob, **not** a clean separator:
  on this material no pixel threshold splits "changed" from
  "unchanged" sharply (the generated burst frames genuinely differ;
  seq A mean tile diff 63.9/255).

## Verdicts through the Rust cascade (crates/harbor-watch)

Full 1280-dim embeddings ride the substrate rings untruncated
(ingest ring dim 1280, decide ring dim 1281). Stages: perceive →
decide (cosine vs the tile's previous *published* embedding) →
direct (top-4 focus; published, does not gate compute in this
version) → refine (one Laplacian step over the tile grid) → publish.

- **C_cuts, ALL strategy: perfect.** Frame 0 flags 0 tiles; **every
  cut frame flags 16/16 tiles.** Frame-level agreement between ALL
  and CHANGED on C is **1.0000** (tile-level 0.807 — where change is
  dense, skipping costs tile fidelity but not the frame verdict).
- **B_turntable: 2/192 tiles flagged** under ALL — gradual rotation
  is correctly near-silent, and CHANGED's verdicts agree with ALL
  at **0.979** while spending 23 embeds instead of 192.
- **A_burst is a finding, not a failure:** 148/192 tiles flagged.
  Its ground truth was scene *continuity*, but the burst frames are
  regenerated variations, not near-duplicates — the embeddings say
  the tiles genuinely move (drift ≈0.48 against a 0.25 threshold),
  and the detector believes the embeddings. A camera burst this is
  not; the sequence is kept in the record as the high-change case.
- The fixture ablation (controlled ground truth) says the sheaf
  refine step earns its place: raw precision 0.60 → **1.00** after
  one smoothing step, recall 1.00 both ways — an isolated noise
  spike fires alone and dies; a real cut's tiles hold each other up.
- A real bug class was caught by tests during the build: **stale
  scores re-firing** — in a sparse (CHANGED) stream, a tile's last
  known cut-score was republished as a fresh change two frames
  later. The publish rule now: *a verdict is a claim about this
  frame*; stale tiles publish stable, score reported and labelled.

A human artifact exists: `experiments/wave3/report/` builds one
self-contained HTML page (frames with changed tiles overlaid,
scoreboard vs ground truth) — generated for sequence C from the real
verdicts.

## The reflective layer: Jev (TypeSafe) — measured 2026-11-01

Casey noted the pi agent on the Oracle also carries Jev (TypeSafe
AI). A judge lane was built: 15 text-state candidates (including the
fixture's two raw false positives — the exact reflective case), a
typed yes/no with explicit corroboration criteria, a borderline band
of [0.15, 0.60] (`experiments/wave3/jev/`).

First attempt failed at the credential wall (pi's TypeSafe provider
unconfigured; the stored connector key returned 401). After Casey
reconnected the credential, the direct route ran clean: **15/15
calls, latency p50 0.47 s** — reflective-tier speed, not reflex.

The scorecard (fixture ground truth): raw system P=0.600; **sheaf
refine alone P=1.000, R=1.000**; Jev alone P=0.750, R=1.000; Jev as
tie-breaker **made it worse (0.750)**; Jev as a hard gate changed
nothing (1.000). Jev never doubted a true change (p 0.88–0.92) and
killed one spike FP, but believed the spike's return edge at 0.61
where the sheaf step had already said no. **Verdict by the
project's rule — the seat is earned by the delta: Jev does not earn
the gate. It earns the recorded-advisor seat**: its probability
rides in the verdict as a second opinion, surfaced, not
thresholded. What fixed the false positives was the sheaf refine,
not the judge. n=15 and curated hard; the honest next measurement
is a bigger, duller candidate stream. Full run: 
`experiments/wave3/jev/RESULTS.md` + `jev_verdicts.jsonl`.

## Service footprint

The JEV rack was **inactive** when wave 3 began (the Thor's current
tenancy). It was started for the run (health in ~2 s, I-JEPA lazy
load 11.9 s), and **stopped afterwards — verified inactive, GPU back
to idle.** Nothing in wave 3 is resident or auto-started.

## What wave 3 establishes for the graduation gate

"Working" was v0.2. "Useful on our Thor" now has a concrete shape:
a watch that spends 173 ms embeds only where a µs diff says the
scene moved, catches every real cut the frame it lands, stays
silent on gradual motion, and produces a page a human can open.
The honest limits are in this document: the gate is a ranker, the
director's focus does not yet gate compute, and the reflective
judge — measured at last — earns an advisory seat, not the gate.

## Verification of this wave's tree

The assembled wave-3 tree (commit `fe7a9e4`) passes **52/52 tests
natively on the Thor** (aarch64) and 52/52 on x86_64 — the 44 of
waves 1–2 plus harbor-watch's 8. After the run the JEV rack was
re-checked: `inactive`, as found.
