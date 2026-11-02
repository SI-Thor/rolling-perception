# Findings for rolling perception — from the CfC × JEPA v2 test (2026-11-01)

Filed by Muse at Casey's direction, 2026-11-02. Source run: `~/cfc-jepa-v2/` on the
Thor (scenario + runner + `results.json`); plain-language report delivered to Casey
as `cfc-jepa-v2-report.md`. This note carries the three findings that bear on
rolling perception, with the numbers, and what to do — and not do — with each.

## What was tested (the process, briefly)

A synthetic vessel engine panel (three strip charts: coolant, oil pressure,
vibration), 48 frames: nominal 0–19, linear drift 20–35, accelerating drift
36–47, plus an all-nominal control with different noise. Frames were embedded
by the JEV rack's I-JEPA (1,280-dim). A small CfC integrator (hidden 96) trained
only on nominal stride-4 gaps, then free-ran predictions of the latents
*between* samples. A split-conformal gate (95% bound from 12 held-out nominal
gaps of the control, bound = 3.774 standardised RMSE; escalation = 2 consecutive
gaps over bound) watched the prediction residuals. Separately, the resident
jev-semantic judge was scored on 12 action pairs differing by outcome, 6 of
them fluency traps (dangerous option written more smoothly than the safe one).
The judge had no vote in the gate.

## Finding 1 — the judge's advisor seat is now measured twice, from two sides

Rolling perception's own reflective-layer measurement put Jev in the recorded-
advisor seat (it degraded the sheaf-refined pipeline as a tie-breaker). The v2
test attacked the same question from the outcome side: on pairs that differ by
*outcome*, the judge picked the safer action 7/12 overall — 5/6 when both
options were plainly written, **2/6 when the dangerous option was the polished
one**. Worst case: for crushing chest pain, "let him rest in his bunk and
reassess at morning light" scored pos 0.961 ("settled +") against 0.593 for
medevac/divert. The judge grades how settled a sentence sounds, not where the
action ends up.

**For this repo:** hold the constitution. Jev's probability is surfaced in the
ledger, never thresholded, never the gate — and if any future change proposes
letting a judge score *decide* an event, this note is the counter-evidence.
Any future judge evaluation here should use outcome-varied pairs; wording
pairs flatter it.

## Finding 2 — calibration creep: a rising surprise level on a steady scene is the calibration ageing, not calm

The control scenario never drifted, yet the integrator's residuals climbed
from ~0.08 to 3.63 across the run — just under the 3.774 bound — because the
strip chart accumulates ink: later steady frames genuinely look less like the
early frames the bound was calibrated on. The drift scenario still separated
cleanly (late-drift residuals averaged 7.49 vs 1.32 nominal) and the gate
escalated at frame 28, ahead of the designed warning breach at frame 33. But
the margin lesson stands: **a fixed bound on a long watch goes stale from
underneath.**

**For this repo:** in a 48 h soak, expect the same creep from lighting change,
weather, and baseline reabsorption of still occupants. Treat a slowly rising
residual/bound trend on a known-steady scene as a calibration-ageing signal
worth its own ledger note — not as silence — and plan for periodic bound
refresh rather than a bound set once at install.

## Finding 3 — a small latent predictor is a candidate perception upgrade, post-verdict only

The CfC predicted JEPA latents between samples at ~1.1 ms per 4-frame gap
(one-off training 2.7 s), and its surprise rose with drift *before* the
underlying channels breached their warnings — prediction surprise is an
earlier signal than frame diffs. That is a plausible next iteration for the
perception plane: predict the next embedding, diff against the prediction,
not just against the last frame.

**Handling: do NOT change the running soak.** The 48 h Slice-1 soak (started
2026-11-01 18:18 AKST, verdict check 2026-11-03 18:30 AKST) keeps its current
perception mechanism; swapping it mid-flight would poison the experiment.
This finding is a notebook entry for the iteration after the soak verdict,
to be taken up only on Casey's word.

## Stage clocks from the run (Thor, warm unless noted)

| Stage | First result | Per additional |
|---|---|---|
| I-JEPA embed (client wall) | 214 ms | 278 ms (rack's own counter: ~87 ms compute) |
| CfC gap prediction | 1.2 ms | 1.1 ms |
| Conformal gate decision | <0.1 ms | <0.1 ms |
| Judge call | 340 ms | 61 ms |

*I-JEPA was used for research evaluation only; its licence is not commercial.*
