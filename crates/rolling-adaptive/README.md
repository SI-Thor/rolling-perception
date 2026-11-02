# rolling-adaptive — lens-calibrated adaptive staggering

Wave-2 prototype for SI-Thor/rolling-perception. Std-only, deterministic
(logical clock in µs, no wall-clock sleeps), no dependency on the sibling
crate.

**The doctrine under test** (Casey's perception notes): every sensor
carries a *lens file* — a living self-model of its delays, jitter and
drift. Perception improves by knowing the lens, not by adding channels.
The sibling `rolling-perception` crate uses a **fixed** stagger that
assumes each lane's period is known and exact. This crate asks what
happens when that assumption is graded against sensors that jitter and
drift, and the scheduler is allowed to read the lens.

## Pieces

- `LensFile` — per lane: period estimate (EMA, α = 0.10), jitter
  (EMA variance), last signed phase error, observation count. Updated
  causally on every observed arrival. Serialises to a small
  `key = value` text format (`to_text` / `from_text`, roundtrip-tested)
  — the lens as text, inspectable and diffable.
- `gen_trace` — synthetic lanes with known ground truth (period,
  jitter σ, linear drift, phase), SplitMix64 + Box–Muller, fixed seeds.
- Predictors on **identical traces**: `predict_fixed` (origin +
  k·nominal — the fixed stagger's assumption) vs `predict_adaptive`
  (lens `last + est_period`, one-step ahead).
- `simulate` — consequences: a per-lane stager pre-stages each item to
  be ready at its predicted arrival (prep 600 µs, staged prep expires
  if the arrival is >2000 µs later than predicted and is redone), then
  one shared executor runs items in ready order (900 µs each).
  Freshness deadline: output within 1600 µs of arrival.

## Measured results (`cargo run --release`, 4 lanes × 400 cycles)

| Scenario | Pred. error p95, fixed | Pred. error p95, adaptive | Fresh ≤1600 µs, fixed → adaptive | Mean latency, fixed → adaptive |
|---|---|---|---|---|
| A. jitter σ=800 µs + drift +12 µs/cycle | 854,285 µs | **1,669 µs** (512×) | 66.8% → **70.4%** | 1694 → **1368 µs** |
| B. jitter σ=800 µs, no drift | 18,492 µs | **1,629 µs** (11.4×) | 32.1% → **57.1%** | 5499 → **1581 µs** |
| C. zero jitter, zero drift | 0 µs | 0 µs | 100% → 100% | 900 → 900 µs (tie) |

Why fixed's prediction error explodes: anchored at the origin, jitter
makes its phase a random walk (∝ √k·σ — scenario B) and drift makes it
quadratic in k (scenario A: the true period grows 5000 → 9788 µs; the
fixed scheduler is predicting arrivals ~0.85 s early by the end).
Adaptive only ever predicts one interval ahead from a tracked period,
so its error stays ~1–2× the per-interval jitter forever.

**Where adaptive does NOT win — stated plainly:**
- **Zero jitter/drift (C): exact tie.** Fixed is exact, and the lens
  converges to the same exact period. There is nothing to learn, so
  learning gains nothing. (With a worse-tuned lens it would lose; α
  and tolerances were not tuned per-scenario — one α for all three.)
- **TTFO: ties in every scenario (900 µs).** The first sample has no
  history; no lens can predict it better. The adaptive win is in the
  *sustained stream* — freshness and latency after warmup — not in
  time-to-first-output.
- **Scenario A's freshness gap is small (3.6 pts)** despite the huge
  prediction gap: predicting *early* is cheap in this executor (a
  600 µs redo), while predicting *late* (scenario B's random walk,
  both signs) stalls the executor. Asymmetry worth knowing before
  designing a real stager.

Lens calibration quality (test-graded against ground truth): period
within 100 µs of 5000 µs after 300 samples at σ=300 µs (nominal started
deliberately wrong at 4000 µs); under drift it tracks the *current*
period within 5% (est. 9906 µs vs true 9788 µs at trace end, jitter
est. 722 vs true σ 800).

## Process / dead ends (in the body, per doctrine)

1. **α = 0.25 failed first.** Its endpoint period-estimate noise
   (~0.38·σ) failed the convergence tolerances on both lens tests.
   The generator was verified innocent first (trace mean interval
   5017.8 µs on a 5000 µs truth). α = 0.10 (endpoint noise ~0.23·σ,
   drift lag 9 steps) passes with margin. Recorded in `LensFile::new`.
2. **Executor v1 measured nothing.** Putting staging on the shared
   executor gave 4 lanes × 1500 µs of work per 1250 µs mean
   inter-arrival: the queue saturated, both schedulers posted
   ~200 ms mean latencies and identical freshness (0.2%), and the
   only thing measured was the overload. v2 stages per-lane
   (parallel front-ends) and shares only the run; latencies dropped
   to the 1–5 ms range and the schedulers separated. Recorded in
   `simulate`'s doc comment.
3. **Phase-error feed-forward was dropped.** Predicting
   `last + period + last_phase_error` mostly chases the previous
   sample's jitter. The phase error is still recorded in the lens —
   it is the health signal — but the predictor is period-only.

## Tests

`cargo test` — 6/6: lens convergence (no drift), lens drift tracking,
adaptive p95 < fixed p95 on jitter+drift (asserted, and < 0.5×),
fixed-is-exact on a perfect sensor, lens text roundtrip, trace
determinism + drift direction.
