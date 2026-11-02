# Slice 3 (experiment) — the engine is the synthesizer, measured

Casey's thesis: reading sensor positions faster never gives you the
song; the song exists when the samples are laid out into a waveform.
A game engine is a *synthesizer*, not a sampler: it holds a model of
the world, samples correct it, and a reader who arrives late gets
the rendered present — not the stale sample. This experiment prices
that claim, and prices where it breaks.

Everything here is synthetic ground truth plus one real-data echo.
Nothing touched the live soak feed. Code: `engine.py` (world,
sensor, lens, engine), `run_experiment.py` (the measurement),
`test_engine.py` (the labelling rules, 10/10 passing), numbers in
`results.json` (seed 20261101, deterministic).

## Method

**World** (analytic truth, 90 s): four objects — `cruiser` and
`glider` at constant velocity (controls), `speeder` under sustained
acceleration 0.35 u/s² from t=30 s to t=60 s (velocity 1.0 → 11.5
u/s), `reverser` flipping velocity +3 → −3 u/s instantly at t=45 s.

**Sensor (the sampler side)**: reads at nominal 0.5 s cadence,
arrival jitter σ=0.08 s, 8% of reads dropped, position noise
σ=0.05/axis. 178 reads generated, 7 dropped, 171 arrivals.

**Engine (the synthesizer side)**: per object, the corrected state
is the raw read (no filtering — deliberately; filtering is a
different converter and would confound the comparison), velocity is
an EMA (α=0.35) of per-read delta velocities, and the error model is
an EMA of squared one-step extrapolation residuals (final σ_r ≈
0.10–0.13 for all four objects). The stream's rhythm lens mirrors
the substrate's LensFile (EMA period + jitter variance, α=0.10).

**Serving** follows Panel 2 Q3's evidence kit from the first
commit: every serve carries `basis`, `extrapolation_age`, stated
`tolerance`, and the lens's `stale_threshold`. Basis rules (unit
tested): age = 0 → `corrected`; 0 < age ≤ period + 3σ jitter →
`extrapolated`; age above → `stale`, never "now". The stated band is
band(a) = σ_r · max(1, a/period), whose design-point exceedance
under an isotropic-Gaussian, linear-growth error model is
e⁻¹ ≈ 0.368 — the calibration target the exceedance rate is graded
against. Exceedance at corrections is graded against the band
stated *before* the read arrived.

**Measurement**: 305 query times (12–88 s, 0.25 s step) × reader
lags L ∈ {0, 0.5, 1, 2, 5, 10} s. A lag-L reader sees only reads
arrived by t_q − L. SAMPLER holds the newest such read; ENGINE
extrapolates the synthesiser state built from the same window to
t_q; ORACLE is truth (error 0, the framing row). Identical read
streams for both strategies.

## The lag table (radial position error, world units)

| lag s | mean age s | sampler mean | sampler p95 | engine mean | engine p95 | exceed | basis c/e/s |
|---|---|---|---|---|---|---|---|
| 0 | 0.27 | 0.935 | 3.443 | **0.087** | 0.185 | 0.121 | 0/302/3 |
| 0.5 | 0.77 | 2.641 | 8.831 | **0.154** | 0.456 | 0.142 | 0/219/86 |
| 1 | 1.27 | 4.347 | 14.465 | **0.236** | 0.857 | 0.097 | 0/16/289 |
| 2 | 2.27 | 7.717 | 25.814 | **0.442** | 1.925 | 0.109 | 0/0/305 |
| 5 | 5.26 | 17.545 | 59.729 | **1.380** | 7.220 | 0.128 | 0/0/305 |
| 10 | 10.26 | 33.083 | 116.828 | **4.065** | 22.996 | 0.155 | 0/0/305 |

The engine wins at every lag: 11× on mean error at lag 0, 17–18×
through lag 2, still 8× at lag 10 (5× on p95). Two honest
qualifications:

- **Lag 0 is not freshness.** Even an undelayed reader holds a read
  averaging 0.27 s old — that alone costs the sampler 0.94 units of
  mean error on moving objects. "Latest sample" is already a stale
  serve; extrapolation is what makes it a *now*.
- **Almost everything past ~1 s is labelled `stale`, and the label
  is right.** The lens learned period 0.563 s and jitter σ 0.139 s
  from arrivals — wider than the sensor's nominal 0.5/0.08 because
  drop gaps are part of the arrival rhythm — giving a stale
  threshold of 0.98 s. At lag ≥ 2 every serve is stale-labelled.
  The stale-labelled extrapolation still beats the held sample 8×,
  but the label governs how a consumer may *act* on it (Panel 2's
  compensation machinery), not whether it is the best estimate.

## Where the synthesizer lies

**1. The reversal: for ~2 s the engine is worse than the sampler.**
Reverser, lag-1 engine mean error by time relative to the flip
(baseline 0.115):

| rel window s | engine | sampler | engine lag-2 |
|---|---|---|---|
| [−5, 0) | 0.111 | 3.740 | 0.270 |
| [0, 1) | 2.303 | **2.012** | 2.402 |
| [1, 2) | 6.919 | **3.212** | 8.287 |
| [2, 4) | 2.452 | 3.698 | 9.399 |
| [4, 8) | 0.438 | 3.799 | 1.319 |
| [8, 16) | 0.101 | 3.761 | 0.152 |

Extrapolating confidently in the old direction is worse than
holding a stale sample near the turn — the sampler wins the first
two seconds outright, and the engine's error *peaks* at [1, 2)
(60× baseline) after the flip is already in the past. Recovery:
the velocity estimate is within 0.3 u/s of truth after 8
corrections (~4.4 s); lag-1 serve error is back at baseline
(0.101 vs 0.115) in the [8, 16) window. Lag-2 readers recover
later (peak 9.40 in [2, 4)) because their information window
straddles the flip longer.

**2. Sustained acceleration: no spike, a bleed.** Speeder lag-1
engine error: 0.111 pre-event → 0.139 → 0.323 → 0.589 → 0.838 →
0.786 across the same windows — a plateau at ~6–7× baseline
(0.126) for the *entire* 30 s acceleration. A constant-velocity
synthesiser structurally cannot represent it: every correction
re-anchors position, but the velocity EMA chases a moving target.
There is no alarm moment; the error just stays wrong. The sampler
bleeds worse (1.25 → 6.12), so the engine still wins the
comparison — and the moment acceleration ends, the engine is back
at baseline (post-accel cruise 0.120 vs baseline 0.126).

**3. Calibration: one pooled band is honest nowhere.** Serve-level
exceedance vs the 0.368 design point, by class:

| class | L0 | L0.5 | L1 | L2 | L5 | L10 |
|---|---|---|---|---|---|---|
| controls | 0.14 | 0.12 | 0.02 | 0.00 | 0.00 | 0.00 |
| speeder | 0.11 | 0.24 | 0.30 | 0.39 | 0.43 | 0.48 |
| reverser | 0.09 | 0.08 | 0.04 | 0.04 | 0.08 | 0.14 |

(At corrections themselves, trailing-100 exceedance is 0.25–0.32 —
near the design point.) In cruise the band is ~3× too wide: the
σ_r that prices it is pooled over manoeuvre transients, so the
engine understates its own precision exactly when it is most
trustworthy. For the speeder at long lags it flips: exceedance
0.39–0.48 > 0.368 — error under sustained acceleration grows
quadratically with horizon while the band model is linear in age,
so long-horizon bands under-cover precisely in the regime where a
reader most needs the warning. The pooled number (0.10–0.16)
looks "conservative" and conceals both failures — Hy's
regime-mislearning failure, measured.

## Real-data echo: wave-3 sequence C

The verdict stream from wave 3 (`verdicts_ALL_C_cuts.jsonl`, real
Thor pipeline output: 12 frames at 30 fps, 16 tiles) is an A/B
interleave — every tile flips scene at every frame. Per-tile scene
label = cumulative XOR of `changed`. Delayed readers at frame-lags
0–3 (n = 8/8/8/7 evaluated frames):

| frame lag | sampler label err | engine label err |
|---|---|---|
| 0 | 0.000 | 0.000 |
| 1 | **1.000** | 0.000 |
| 2 | 0.000 | 0.000 |
| 3 | **1.000** | 0.000 |

(The brief's literal form — predicting the changed-tile *set* —
is degenerate on C and recorded for completeness: every frame's
changed set is all 16 tiles, so both strategies score 0.000 at
every lag. The state-label form above is the faithful analogue.)

C is a metronome, so this is an echo, not a measurement — but it
shows the sampler's failure shape on real pipeline data: holding
is not "safe", it is *wrong on a schedule* (100% of tiles at every
odd lag), and a lens that learns the rhythm removes the error
entirely. A stream doesn't have to be positional for the
synthesizer argument to bite; it has to have rhythm.

## Design rules earned for Confluence's engine layer

1. **Max extrapolation horizon is a lens property, not a constant.**
   A serve may be labelled `extrapolated` only within
   period + 3σ jitter of the stream's *arrival* rhythm — drops
   included (here: 0.98 s earned by a nominal-0.5 s stream).
   Faster, cleaner streams earn longer horizons; the number is
   read off the lens, never set by policy.
2. **Stale is a serving class, not a failure.** At 10 s lag the
   stale-labelled extrapolation beat the held sample 8×. Serve it,
   label it, and route *action* on stale state through the
   compensation/false-action machinery (Panel 2 Q3) — never let it
   masquerade as "now", never throw it away either.
3. **Tolerance must be regime-conditional.** One pooled σ_r
   over-covers cruise (exceedance 0.00–0.14 vs 0.368 stated) and
   under-covers manoeuvre at long horizon (0.48). Minimum viable
   fix: split the error model by a regime signal the engine
   already has (velocity-estimate stability), and make the band
   superlinear in age wherever acceleration is physically
   possible. Exceedance rate per regime is the self-test that
   grades the fix — this is Hy's `regime_tag` requirement with
   numbers behind it.
4. **Manoeuvre response is a designed mechanism, not an EMA
   setting.** A reversal made the engine worse than a sampler for
   ~2 s and took 8 corrections to re-converge velocity. The
   exceedance counter already detects the event (a correction
   residual ≫ band); the earned next step is a snap rule —
   residual > 3× band resets the velocity EMA to the measured
   delta — graded by recovery time, the metric this experiment
   defines. **Built and measured in the SNAP section below: the
   rule is right and 3× is the right threshold, but graded
   against the live σ_r it is toothless — the triggering residual
   inflates the very band the next correction is judged by. The
   updated rule: a residual that beats the snap threshold is a
   regime change and must be excluded from the error-model EMA
   (or σ_r frozen while a snap transient is open), so follow-on
   contradictions grade against the pre-event band.**
5. **Rhythm learning belongs in the lens for every stream class,**
   including discrete ones. The C echo's sampler was wrong 100%
   at odd lags on rhythm alone.

## SNAP: the follow-up experiment, measured

Design rule 4's named follow-up, built as a strategy flag on the
same engine (`EngineObject.snap_k`; `python3 run_experiment.py
--snap`, full numbers in `snap_results.json`). Identical streams
(seed 20261101) — a comparability audit first: the snap-off
variant reproduces every v1 engine mean exactly, so the sweep
compares policies, not streams.

**The rule.** A correction whose residual beats k × the band
stated *before* the read is a contradiction, not noise: velocity
resets to the measured read-to-read delta instead of EMA-blending
toward it. **Guard:** a contradiction may not be judged from a
blind interval — if the correction's extrapolation age exceeds
the lens freshness window (the dropped-read gap case), the snap
is suppressed and the engine blends as usual; a real
contradiction persists and fires on the next on-rhythm
correction. The guard is unit-tested (gap suppresses, next
on-rhythm read fires). In this stream it was never exercised:
0 suppressions at every k, and an age audit of every fired snap
shows all landed on-rhythm (none post-gap) — the reversal did
not hide in a drop, and the guard's in-stream cost was zero.

**Reverser recovery** (lag-1 engine error by window after the
flip; baseline median 0.115 for every variant; sampler never
returns below the engine baseline — its post-flip error *is* its
cruise level):

| variant | [0,1) | [1,2) | [2,4) | [4,8) | recovery window | time-to-baseline | velocity re-converged |
|---|---|---|---|---|---|---|---|
| snap off | 2.303 | 6.919 | 2.452 | 0.438 | [8, 16) | 6.00 s | 8 corrections |
| snap 2× | 2.320 | 5.778 | **0.157** | **0.122** | **[2, 4)** | **2.00 s** | **2 corrections** |
| snap 3× | 2.303 | 5.780 | 1.674 | 0.309 | [8, 16) | 6.00 s | 7 corrections |
| snap 5× | identical to 3× in every measure | | | | | | |

**Snap accounting** (fired / objects):

| variant | cruiser | glider | speeder | reverser |
|---|---|---|---|---|
| 2× | 8 | 4 | 4 | 5 |
| 3× | 0 | 0 | 0 | 1 |
| 5× | 0 | 0 | 0 | 1 |

**Why 3× is toothless as implemented.** At 3× (and 5×) exactly
one snap fires: the straddle read at t=45.251, residual ratio
8.97×. It resets velocity to the straddle-interval average —
then nothing. The next correction's residual is 1.99, but the
straddle read's own residual (1.56) has already been absorbed
into the resid_ms EMA, inflating σ_r ~5×, so the follow-on
contradiction grades at only ~2× the widened band and the
engine falls back to EMA for the remaining convergence
(7 corrections, time-to-baseline unmoved). The band is
contaminated by the event it exists to detect. At 2× the second
snap *does* fire (t=45.846, ratio 2.79 against the inflated
band; ~10×+ against the pre-event band) and recovery collapses
to 2 corrections / 2.00 s — but 2× sits inside the error model's
noise tail: every false snap at 2× has ratio 2.00–2.67, and
there are 16 of them (12 on the controls; 4 on the speeder,
whose silence is required — two land just before acceleration
onset and worsen its [0, 1) bin 0.139 → 0.291). The price shows
in control error: +4.2% at lag 0 growing to +14.0% at lag 1 and
+22.6% at lag 5. At 3×/5× the cost side is exactly zero: no
false snaps anywhere, speeder bins bit-identical to snap-off,
control error +0.0% at every lag.

**Calibration re-grade.** At 3×/5×, serve exceedance per regime
is v1's within noise (controls and speeder identical; reverser
0.09/0.08 → 0.10/0.10 at lag 0/0.5) and correction exceedance is
unchanged (0.25–0.32 across objects and variants). Snap does not
disturb the calibration story — because, at 3×, it barely fires.
At 2× the false snaps tax calibration where they tax error:
control exceedance at long lags rises 0.00 → 0.02–0.04, speeder
lag-0.5 0.24 → 0.29.

**Verdict.** No bare constant earns the seat. 2× buys the
recovery and pays for it in false snaps; 3× and 5× are free and
nearly useless. The threshold is not the problem — the band is.
3× is the right multiple of an *honest* band, and the honest
band is the pre-event one: per updated design rule 4, a
snap-grade residual is a regime change, not a sample of the
error distribution, and must not enter the resid_ms EMA (or σ_r
freezes while a snap transient is open). That decontamination —
graded by this same recovery metric — is the next experiment.
Until it lands, the engine ships snap-off, with 3× armed only
where a false snap is cheaper than a slow recovery.
