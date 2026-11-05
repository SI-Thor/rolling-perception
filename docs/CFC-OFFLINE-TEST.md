# CFC-OFFLINE-TEST — CfC expectation layer vs the soak's real verdict series

The sibling lane's findings note (FINDINGS-CFC-JEPA-V2.md) proposed a
CfC-style expectation layer as a post-verdict candidate for the lens;
Casey's position is candidate-only, tested offline against real data
before any build change. This note is that test, run against the
complete verdict series of the 48 h Slice-1 soak (1,675 rows,
`soak-series.csv`). §1 below was written and fixed BEFORE any run of
the candidate against the data — the L5 discipline: a test that
cannot say no is not a test. What was known when §1 was written: the
findings note, the scorer code, the soak verdict's published numbers,
and exactly one structural fact about the series (checked as
implementation sanity, not outcome peeking): **all 1,675 rows carry
`n_changed_tiles > 0`** — slice 1's ledger writes a verdict row only
per changed frame, so every row is an incumbent fire and every row's
`max_smoothed ≥ 0.25` by the publish rule. No score distribution,
cluster tally, or integration state was computed before §1 was fixed.

## §1 — Pre-registration (fixed before any run)

### The data's shape, and what it makes gradeable

Rows exist only for frames the pipeline verdicted. Quiet frames leave
no row; the inter-row wall gaps carry the quiet. The series is
event-biased and, stronger: **fire-only** (the structural fact
above). Two consequences, stated now because they shape the clauses:

- A row-driven integrator can never trip strictly before a cluster's
  *onset* — there are no rows before onset to integrate. Anticipation
  of onset on this series is structurally ungradeable; the gradeable
  form is anticipation of **continuation** (defined below). This
  limitation is the test's, not the candidate's — the note's verdict
  section names the data that would reopen onset anticipation.
- "Steady stretches" contain no rows at all. A false alarm therefore
  cannot be *in* a steady stretch (nothing arrives there to trip on);
  the gradeable form of the false-alarm clause is a **trip whose
  forward window contains no incumbent fire** (defined below).

Fences (excluded from all scoring; rows inside them: none by
construction — a frozen feed produces no verdicts):
gap 1: 2026-11-01 21:08:17 → 2026-11-02 09:35:26 AKST; gap 2:
2026-11-03 09:06:37 → 18:18:00 AKST (epoch µs, AKST = UTC−9; the
CSV's `wall_us` is epoch µs). **Re-entry transient class**: the first
10 wall-minutes of rows after each fence end — their own class, not
steady, not change.

### The incumbent baseline

The shipped gate: per fresh tile, cosine distance to the tile's
previous embedding (`live.rs`, decide), one Laplacian smooth step
over the 4×4 grid (refine, α = 0.1), and a fire when a fresh tile's
smoothed score ≥ threshold 0.25 (`live.rs`, publish: `changed =
fresh[t] && smoothed >= threshold`). On this series the incumbent's
fires are **all 1,675 rows** (`n_changed_tiles > 0`), and
`max_smoothed` is the frame's largest per-tile smoothed score.
Anticipation is measured against these fires.

### The candidate ("CfC-E", the findings note's shape on this input)

A closed-form continuous-time leaky integrator over the surprise
stream, evaluated at row arrivals, integrating over **wall time**
(no resampling onto a uniform grid — gaps enter through the leak
term exactly as long as they are):

```
per row i (in wall_us order), Δtᵢ = wall_us[i] − wall_us[i−1]:

  sᵢ = max_smoothed[i]                      # the row's surprise
  rᵢ = sᵢ − Bᵢ₋₁                            # residual over expectation
  Bᵢ = Bᵢ₋₁ + β·(sᵢ − Bᵢ₋₁)                 # slow background EMA
  aᵢ = max(rᵢ, 0)                           # only above-expectation surprise accumulates
  Eᵢ = Eᵢ₋₁·exp(−Δtᵢ/τ) + aᵢ                # leaky integral over wall time
```

Fixed parameters (chosen a priori, from the findings note's
continuous-time shape and the series' scale — not tuned to outcomes):
`τ = 120 s` (leak time constant: a burst of rows seconds apart
accumulates; a 10-minute quiet gap decays the state by e⁻⁵ ≈ 0.007,
effectively resetting), `β = 0.005` per row (background adapts on a
~3-hour scale at the series' ~63 rows/live-hour), `B₀ = 0.25` (the
series' own structural floor), `E₀ = 0`.

**Bound (split-conformal in the findings note's spirit, from a
designated calibration segment):** `Θ =` the 99th percentile of `E`
over the rows of the **first 12 live hours** (fences excluded; purely
mechanical — no labels, no outcomes beyond that segment are touched).
Stated consequence of this choice: the first evening's intensity sets
the bar; later bursts must exceed it to trip.

**Trip rule (the findings note's escalation discipline):** a trip
fires at row i when `Eᵢ > Θ` and `Eᵢ₋₁ > Θ` (two consecutive rows
over bound). **Reset:** at a trip, `E ← 0` (background `B` is
untouched — it is slow by construction); a **refractory of 10
wall-minutes** follows each trip, during which the state keeps
integrating but no new trip is counted.

### PASS requires ALL of

- **(i) Anticipation (continuation form).** A *cluster* is incumbent
  fires grouped when consecutive rows are ≤ 10 wall-minutes apart
  (the soak verdict's own split); a *multi-row cluster* has ≥ 2 rows.
  A *qualifying resumption pair* is two consecutive rows of one
  cluster separated by ≥ 60 wall-seconds (a lull then resumption).
  The candidate anticipates a qualifying pair iff a trip lands on the
  pair's earlier row (state alive through the lull), which strictly
  precedes the incumbent's resumption fire (the later row) by the
  lull's length. **PASS: anticipation on ≥ 30% of qualifying
  resumption pairs.** (30% because below that the layer adds trips
  without reliably buying lead time; onset anticipation is
  ungradeable on a fire-only series, as stated above.)
- **(ii) False-alarm budget.** A trip is a *false alarm* iff no
  incumbent fire occurs in `(trip_time, trip_time + 30 wall-minutes]`
  (the steady-stretch condition in its gradeable form: a trip on a
  row whose ±30-min neighbourhood — fences excluded — contains no
  other fire is necessarily false). **PASS: ≤ 0.10 false trips per
  live hour (26.36 live hours ⇒ at most 2 in total, compared as
  integers).**
- **(iii) Re-entry transients.** Trips landing inside the re-entry
  transient class (first 10 wall-minutes after each fence end).
  **PASS: ≤ 1 in total across both re-entries.**

### FAIL / REJECT / REOPEN-WITH

Failing any clause ⇒ the candidate is **REJECTED as a shadow-mode
candidate on this evidence** (not merely "not adopted": the clauses
were fixed, the data is real, and a miss is a result). Legitimate
alternative verdict: **REOPEN-WITH** — the named missing data that
would reopen the question, stated now: (a) a **per-frame score series
including quiet frames** (sub-threshold run-ins are the CfC's whole
anticipation case, and this series structurally cannot contain them;
only a future run with fuller logging — telltape's
`max_smoothed`/`near_miss_frames` health counters are the existing
pattern — can produce it); (b) **per-tile score streams** (the creep
analysis the soak verdict ran operates at tile level inside fired
frames; a row-level max cannot see it); (c) the findings note's
actual input — **latent-gap prediction residuals** from the rack,
absent here entirely.

---

Everything below §1 was written after the pre-registration was fixed
on disk and after the runs reported here. The grading script is
`~/lane-cfc-test/cfc_offline.py`; its output is quoted verbatim.

## §2 — Method

The script loads `soak-series.csv` (1,675 rows), drops rows inside
the frozen fences, asserts the fire-only property (all rows
`n_changed_tiles > 0`), and runs §1's state equation exactly as
written — wall-clock gaps through the leak term, no resampling. Two
boundary decisions made during implementation, both structural, both
stated here because §1's fence sentence left the endpoints' convention
unpinned:

- **Fence endpoints are whole-second roundings of the boundary rows'
  own timestamps.** Gap 1's start label (21:08:17) names frame 17407,
  whose actual wall time is 21:08:17.081 AKST — the last *live*
  verdict, the row the soak verdict itself uses to define the gap. A
  closed-interval exclusion would wrongly eat it (my first run did,
  and graded 1,674 rows); the frozen interval lies strictly *between*
  boundary rows, so exclusion applies one second past the label. With
  the faithful convention, all 1,675 rows are live and frame 17407
  rejoins the Nov 1 evening cluster. No other row sits near any
  boundary.
- **Θ's pass discipline.** Θ is computed from a reset-free
  integration of §1's state equation over the calibration segment
  (393 rows — the Nov 1 evening cluster); the trip pass then
  re-integrates the same equation with §1's reset-at-trip behaviour.
  No trip occurs inside the calibration segment, so the two passes
  agree where Θ was measured.

The re-entry transient class (first 10 wall-minutes after each fence
end) contains 14 rows. Grading definitions are §1's verbatim:
clusters split at >10 min silence (the soak verdict's own
convention); qualifying resumption pairs = consecutive same-cluster
rows ≥60 s apart; false alarm = counted trip with no fire in
(trip_time, trip_time + 30 min]; live denominator 26.36 h (the soak
verdict's measured live time).

## §3 — Results, against the clauses exactly as written

```
[setup]
rows (fences excluded): 1675; all are incumbent fires (asserted)
calibration segment rows (first 12 h of rows): 393
re-entry transient rows: 14

[integrator]
Theta (99th pct of E, reset-free, calibration segment): 2.2177
trip occurrences: 3; counted trips (10-min refractory): 3
  trip frame 15224  wall 1793598104189300  s=0.4220  E_noreset=2.4099
  trip frame 162714  wall 1793680359136689  s=0.5472  E_noreset=2.4750
  trip frame 168111  wall 1793683514847589  s=0.7728  E_noreset=2.8522

[clause-i] anticipation (continuation form)
clusters: 19 (multi-row: 19)
qualifying resumption pairs (>=60 s lull inside a cluster): 133
anticipated: 0  fraction: 0.000  (bar >= 0.300): FAIL

[clause-ii] false alarms
false trips (no fire within +30 min): 0 over 26.36 live h = 0.000/h
(bar <= 0.100/h and <= 2 total): PASS

[clause-iii] re-entry transients
trips inside transient class: 0 (bar <= 1): PASS
```

- **Clause (i): FAIL, decisively — 0 of 133 qualifying resumption
  pairs anticipated (bar ≥ 30%).** The integrator tripped exactly
  three times, all mid-burst on the two great evening clusters
  (2026-11-01 20:41:44, 2026-11-02 19:32:39 and 20:25:14 AKST; the
  tripping rows' own surprise was s = 0.42–0.77, the strongest of the
  run), and never on the earlier row of a lull. The mechanism is
  visible in the state equation: τ = 120 s means a ≥60 s lull decays
  E by ≥37% before any resumption, and a trip needs two consecutive
  rows over Θ — the state that would have to survive the lull is
  exactly what the lull erodes. On this series the candidate is a
  burst-intensity detector, not an anticipator.
- **Clause (ii): PASS — 0 false trips.** All three trips landed
  mid-cluster with fires continuing around them; nothing tripped that
  was followed by 30 minutes of quiet.
- **Clause (iii): PASS — 0 trips in the re-entry transient class.**
  The 14 transient rows never accumulated state near Θ.

**PASS required ALL three; clause (i) failed; the candidate FAILS the
pre-registered test on this series.**

## §4 — Calibration lens

What the integrator's internal state says about calibration health,
row-level only — and this is the lens's own limit: the soak verdict's
creep analysis (median background surprise 0.0817 early → 0.0671
late, threshold 0.2500 throughout, no creep) operates at TILE level
inside fired frames; `max_smoothed` is a row-level maximum over tiles
and cannot see the same quantity. The two are kept apart.

```
max_smoothed median: early 0.3222 vs late 0.3861
background B: start 0.25 -> early-end 0.3445 -> late-end 0.3863 (run median 0.3602)
E (post-reset) median: early 0.5469 vs late 0.2752
E (reset-free) median: early 0.5472 vs late 0.2752
live midpoint (13.18 live h): frame 165209, B=0.3779, E=0.4173, s=0.3441
```

Read honestly: the background B rose steadily across the soak
(0.25 → 0.3863), because the fires themselves intensified — the
late-evening clusters of Nov 2 published stronger maxima than Nov 1's
(row medians 0.3222 → 0.3861), and B, an EMA of the surprise input,
absorbed that level. At the soak's live midpoint the integrator held
B = 0.3779 and would have reported "surprise level drifting upward —
possible calibration ageing," exactly the finding-2 signal the
findings note told us to watch. **That conclusion would have been
wrong.** The verdict's tile-level measurement found the opposite
(background medians fell, 0.0817 → 0.0671; threshold never moved; no
calibration creep) — the run's later events were simply stronger.
The lesson for any future expectation layer: an integrator fed
event-level maxima conflates event intensity with calibration drift,
and cries creep where there was none. Creep detection needs the
quiet-frame/tile-level series this CSV does not contain — the same
missing data as the anticipation clause.

## §5 — Cost

```
reset-free integration, 1675 rows: 0.78 us/row (total 1.31 ms)
trip pass: 0.79 us/row (total 1.33 ms)
whole script wall: 0.010 s
```

Measured on this machine (Orin, Python 3.12, one pass over 1,675
rows): **0.78 µs per row** for the pure integration, 0.79 with the
trip machinery — against the findings note's 1.1 ms per latent-gap
prediction. Three orders of magnitude cheaper, and honestly so: this
candidate integrates one scalar per verdict row; the findings note's
CfC predicts a 96-dim latent through trained dynamics. Cost is not
this candidate's problem.

## §6 — Verdict

**REJECTED as a shadow-mode candidate on this evidence — REOPEN-WITH
the data named in §1.** The clauses were fixed before the run; the
data is the soak's real series; on it the candidate bought zero
anticipation (0/133, clause (i)) at zero false-alarm cost (clauses
(ii)/(iii) passed). A layer that cannot anticipate anything the
incumbent does not already say, on the only real data that exists,
does not earn a shadow slot — no matter how cheap it is.

The rejection is about the evidence, and the reopening conditions are
§1's, restated with what this run added:

1. **A per-frame score series including quiet frames** — the CfC's
   whole anticipation case lives in the sub-threshold run-in before
   scores reach 0.25, and a fire-only series structurally cannot
   contain it. The soak verdict's deficit 4 named this exact gap
   ("no per-frame gate statistics for no-event windows"); telltape's
   `max_smoothed`/`near_miss_frames` health counters are the built
   pattern a future soak can copy.
2. **Per-tile score streams** — required before the calibration lens
   of any expectation layer can be trusted (§4: event-maxima conflate
   intensity with drift).
3. **Latent-gap prediction residuals from the rack** — the findings
   note's actual input; a scalar integrator over published maxima is
   a distant proxy for it.

If the reopening data ever lands, the smallest honest re-test is this
note's §1 verbatim with one substitution: the anticipation clause
reverts to its strong form (trip strictly before a cluster's first
fire, on the run-in rows that now exist), everything else unchanged.
No build change is recommended now; the running perception mechanism
is untouched, as the findings note's handling already required.
