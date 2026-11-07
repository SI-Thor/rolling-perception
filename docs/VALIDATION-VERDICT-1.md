# VALIDATION-VERDICT-1 — The fixed telltape build, watched for a day

*Internal record. Verdict on the first full validation run of telltape
v0.3.2 (the build carrying G1 freshness-by-novelty and the B1
demonstrated-discrimination rule) against a live camera feed. Computed
2026-11-06 from the run's own receipts on the Thor:
`~/confluence-play/validation-1/ledger/` (`events.jsonl` 2,292 rows,
`state.txt`, `health.txt`, `lens.txt`) and the parent agent's mid-run
anchor reads. Every number below names the file it came from. Where the
receipts cannot establish a claim, this document says so instead of
rounding it off.*

## The verdict, per axis

- **Feed liveness: PASS.** The feed stayed live for the full 24 h
  window, and — the point of the exercise — the fixed build can *prove*
  the negative space: across the whole 37.7 h the watch ran, it
  receipted 24 frozen stretches totalling **17.9 seconds**, the longest
  1.65 s. The Slice-1 soak's feed died for 21.6 hours unnoticed; this
  build notices a one-second repeat and writes it down.
- **Spend: PASS.** Final `spend_ratio = 0.0466` against the ≤ 0.60
  ceiling (`state.txt`: 16,934.877 embed-seconds spent against a
  363,214.899 embed-everything estimate).
- **Receipt trustworthiness: PASS, with named limits.** Freshness on
  this build is derived from frame novelty, not poll success (G1), and
  `silence_meaningful = true` appears in `health.txt` — a stamp v0.3.2
  only issues when the embedder has demonstrated discrimination on the
  run's actual inputs (B1). The limits are in §3.
- **Precision: UNJUDGED.** No corrections were recorded against this
  run's events, so no judged precision exists. Same status as the soak;
  the difference is that the machinery to judge now exists (§5).

## 1. The run

| | |
|---|---|
| Stream | `proart-cam-validation` (`validation.conf`, `state.txt`) |
| Source | ProArt webcam via the pusher/receiver (`ingest.py --source shot`, gate 3.0, cadence 500 ms) |
| Embedder | `ijepa@1` (JEV rack, HTTP, dim 1280), identity constant all run |
| Start | **2026-11-05 01:17:37 AKST** — first row of `events.jsonl` (`service/start`, wall_us 1793873857319539) |
| Planned window | 24 h → ends **2026-11-06 01:17:37 AKST** |
| Actual stop | Parent-stopped 2026-11-06 14:59 AKST; final `state.txt` update 15:00:09 AKST. The watch had no self-stop; the surplus past the window is separated by timestamp in §2, not silently included. |
| Totals at stop | frames_seen 254,149 · frames_novel 240,068 · frames_repeated 14,081 · events_published 2,243 · tiles nominated = embedded 182,264 · coverage 1.0000 · freshness live (`state.txt`) |

(The failed first attempt of 2026-11-04 — zero frames, ingest probe
timeout — is preserved separately in `ledger-attempt-1-failed-probe/`
and is no part of this run.)

## 2. Window accounting

Measured directly from `events.jsonl` timestamps (verdict rows with
`wall_us` ≤ start + 24 h):

- **Verdicts inside the 24 h window: 2,000.** Verdicts in the surplus
  (01:17:37 → 15:00:09 AKST on 2026-11-06): **243.** Total 2,243,
  matching `events_published` in `state.txt` exactly. The ledger's
  2,292 lines are the 2,243 verdict rows plus 49 service rows
  (1 start, 24 `source_frozen`, 24 `source_recovered`).
- **Frames inside the window: ≈ 159,000–162,000 — interpolated, not
  measured.** `state.txt` is cumulative-only; no per-window frame
  counter exists. Two interpolations from the parent's anchors
  (frames_seen 43,777 at 2026-11-05 07:33 AKST; 137,832 at ~22:15 AKST;
  254,149 at stop): extending the final segment's rate (6,944
  frames/h) from the 22:15 anchor to the window end gives ≈ 158,900;
  the whole-run mean rate (6,740 frames/h × 24 h) gives ≈ 161,800.
  The surplus therefore holds ≈ 92,000–95,000 frames. Anyone quoting a
  single window frame count is quoting a model, not a receipt.
- Cross-check on the anchors: the ledger's per-hour verdict counts
  (29 in run-hour 5, the morning burst beginning with the first verdict
  at 07:05:38) are consistent with the 07:33 live read of 46 events —
  the mid-run numbers and the final ledger describe the same run.

Per-hour verdict counts inside the window (run-hours from 01:17 AKST):
0, 0, 0, 0, 0, 29, 17, 74, 127, 63, 160, 108, 445, 315, 76, 56, 178,
124, 134, 78, 16, 0, 0, 0. A household day: dead quiet overnight,
a working day's activity, quiet again by 22:12 (the last in-window
verdict), 185 minutes of trailing silence to the window's end.

## 3. Liveness — what the receipts can and cannot establish

**Can establish:**

- `freshness = live` at every recorded anchor (start verification,
  07:33 and ~22:15 live reads, final `state.txt`/`health.txt`), and
  `consecutive_repeats = 0` in both health reads taken (~22:15 and
  final, `health.txt`).
- The frozen detector was awake at one-second granularity for the
  entire run: 24 `source_frozen`/`source_recovered` pairs in
  `events.jsonl`, total frozen time **17.9 s**, longest stretch
  **1.65 s**, none over 60 s. Inside the window: 19 stretches,
  12.0 s. Twelve of the marks fall in run-hour 0 (the 01:40 AKST
  cluster, shortly after start — the pusher settling); the rest are
  singles scattered across the run, five in the final partial hour.
- Frame-level novelty accumulated monotonically: 240,068 novel frames
  of 254,149 (94.5%). The 14,081 repeated frames (5.5%) are what a
  ~2 fps pusher polled at a similar cadence produces against a static
  room — repeats happened constantly and never chained past 1.65 s.
- The overnight event silences (no verdict before 07:05:38; none after
  22:12 in-window; largest between-verdict gap during the active day
  48.7 min, from 07:32) coincide with live freshness, continuing frame
  flow, and an awake frozen detector. On the soak's failure pattern —
  a dead pusher — this build would have receipted a frozen stretch
  measured in hours. It receipted 17.9 seconds of sub-2-second repeats
  instead. That contrast is the liveness evidence; event-gap analysis
  alone would prove nothing, since a quiet room and a dead feed are
  indistinguishable in an event list.

**Cannot establish:**

- That every quiet stretch was a quiet room. Novelty on G1 is
  byte-level frame change: a pathological feed that kept delivering
  *slightly different* frames of a frozen scene (sensor noise over a
  stuck image) would pass novelty. The B1 stamp covers embedder
  collapse, not that case. Nothing in this run suggests it happened —
  the verdict rows show real, varied, tile-level change structure —
  but the receipts do not formally exclude it.
- Anything about event *correctness*. Liveness and spend are receipted;
  whether the 2,243 verdicts were *right* is §5's open question.

## 4. Spend

`spend_ratio` at the ~22:15 anchor was 0.0745 (15,162.344 /
203,625.127, per the parent's health read); at stop it is **0.0466**.
The fall is accounting doing its job, not a change of method: the
embed-everything estimate accrues at a fixed ~1.43 embed-seconds for
*every* frame regardless of scene, while gated spend accrues only on
nominated tiles. In the final segment (22:15 → stop) the estimate grew
159,589.8 s while spend grew only 1,772.5 s (marginal ratio 0.011);
tiles embedded per frame fell from 1.18 (run start → 22:15) to 0.168
(22:15 → stop), because the tail period — overnight and a quiet
morning — nominated far fewer tiles. A quieter scene spends less and
the denominator doesn't care: the ratio falls. Embedder identity never
changed (`ijepa@1`), coverage stayed 1.0000 (every nominated tile was
embedded), so no recalibration or partial-embedding caveat applies.
**PASS, at 7.8% of the ceiling.**

## 5. Corrections and the trust loop — readiness, and the deploy gap

These 2,243 verdicts are the first corpus produced since the trust
loop shipped (parent repo commit 1b21b23: `slice1/console/trust.py`,
per-stream trailing judged precision φ, the demotion/restore rule of
the paper test made real). Nothing has judged them yet:

- **No corrections exist for this run.** No taps file was created; the
  events stand uncorrected, so φ for `proart-cam-validation` is
  UNJUDGED — not low, not high, unjudged, exactly as the paper test's
  vocabulary insists.
- **Named residual — the deploy gap (recorded, not fixed here):** the
  console deployed on the Thor still runs the pre-trust-loop build
  (the 2026-11-04 verdict-drop fix). The shipped trust loop's two-tap
  UI (`not-a-change | mattered`) is therefore not live against this
  ledger, and the console reads its prepared `streams/` layout, so the
  telltape ledger needs its bridge into that layout as part of the
  same deploy.
- What a corrections pass needs, scoped: the deployed console updated
  to the shipped build; the run's events presented in it; taps over a
  defensible sample (all 445 of run-hour 12 is a bad sample — peak
  activity only; a spread across the per-hour distribution, weighted
  to include the quiet hours' rare events, is the honest one); then
  `trust.py` rolls the taps into φ with its N_MIN / hysteresis rules.
  Until that pass happens, any precision claim for this run — in
  either direction — is invention.

## 6. The CfC question — is anticipation gradeable now?

Short answer: **no — the REOPEN-WITH condition is only partly met, and
the unmet part is the one that matters.**

What `events.jsonl` actually holds, per verdict row (all 2,243 rows,
verified): `frame`, `wall_us`, `t_capture_us`, `changed_tiles`
(mean 2.89, max 14), `embeds_this_frame`, `energy_before/after`, and
all 16 tiles with `raw` and `smoothed` scores. Richer than the soak's
extraction in one respect — full per-tile state at every fired frame.

What it does not hold: **a per-frame score series.** Rows exist only
for frames that fired. The run's sub-threshold life — 117,292
near-miss frames (`state.txt`) — survives only as a counter. No row
stamps a frame-level max score (a per-event maximum can be *derived*
as max over tiles of `smoothed`, and the cumulative
`max_smoothed_score = 0.7181` in `state.txt` is consistent with that
derivation, but derived is derived and a grade must label it so).

This is the same structural position as CFC-OFFLINE-TEST documented
for the soak: a fire-only series cannot grade anticipation, because
the run-in to an event — the score climbing through sub-threshold
values in the frames *before* it fired — is precisely the data that
isn't recorded. Clause (i) stays ungradeable. Clauses (ii)/(iii)
could be re-run on the fired rows, but the offline test already showed
what that measures on a fire-only series (a burst-intensity detector,
not an anticipator); re-running it here would reproduce the artefact
with better scenery.

Scoped precisely, if the grading is wanted:

1. *Extraction (minutes, no new evidence):* build
   `validation-series.csv` in the soak format — frame, wall_us,
   t_capture_us, |changed_tiles|, derived max_smoothed,
   embeds_this_frame — for continuity with the soak analysis.
2. *The real unblock is an instrument change, not an analysis:* a
   score-series sidecar in `telltape watch` (per-frame max smoothed
   score plus the 16 tile EMAs, dumped at a fixed cadence whether or
   not the frame fires). One short build; it converts every future
   run into CfC-gradeable evidence and costs no embed spend — the
   scores already exist inside the gate; they are simply not written
   down for quiet frames.
3. Until (2) exists, the CfC verdict stands as written in
   CFC-OFFLINE-TEST: REJECTED as a shadow-mode candidate on
   fire-only evidence, anticipation untested rather than failed.

## 7. Against the soak — the comparison that was the point

| Axis | Slice-1 soak (2026-11-01 → 03) | This run (fixed build) |
|---|---|---|
| Feed | **FAIL** — frozen 21.64 h of 48, found after the fact | **PASS** — 17.9 s of receipted micro-freeze in 37.7 h, longest 1.65 s |
| Freshness basis | Poll success | Frame novelty (G1), in the receipt |
| Silence semantics | Assumed | Earned: `silence_meaningful = true` only under demonstrated discrimination (B1) |
| Spend ratio | 0.0443 (PASS) | 0.0466 (PASS) |
| Events | 1,675 over 26.36 live hours | 2,243 over 37.7 h (2,000 in the 24 h window) |
| Precision | UNJUDGED (no corrections file) | UNJUDGED (no corrections yet; judging machinery now shipped, console deploy pending) |
| Watcher | PASS (heartbeat) | PASS (anchors at 07:33, ~22:15, stop all consistent with the final ledger) |

The soak's failure was never that a pusher died — pushers die. It was
that the system *could not tell*. This run's pusher hiccupped at least
24 times, in writing, for a total of 17.9 seconds, and the ledger can
show its work. That is the difference the fixed build was built to
make, and on this evidence it made it.

## 8. Process notes and residuals

- The watch overran its window by 13.7 h for want of a self-stop. The
  verdict is computed on the window with the surplus reported
  separately (§2) — but a validation harness should stop itself; a
  `--until` on the run config is a noted, unbuilt nicety.
- The window frame count is interpolated (§2). A per-window snapshot
  of `state.txt` at window end would have made it a receipt; the
  sidecar proposed in §6(2) would make such snapshots routine.
- Deployed Thor console still pre-dates the trust loop (§5). Deploy
  is a separate, scheduled job — deliberately not folded into this
  verdict.
- Remaining open from the run's own terms: a corrections pass (§5)
  and the score-series sidecar (§6) are the only two actions standing
  between this run and a fully judged verdict. Both are scoped above;
  neither is started by this document.
