"""L5 — baseline recipe (memo Lever 5).

Baselines for a tile built from steady material (sequences A and B;
C is excluded — its frames alternate scenes, so a cross-frame
baseline is ill-defined there), tested against the AUDIT
embeddings: independent second-pass embeddings of tiles the
CHANGED strategy skipped (low pixel-diff = no-change material).

Methods compared, per AUDIT row (seq s, frame f, tile t, embedding e):
  single : baseline = ALL embedding of (s, f-1, t) — the shipped
           incumbent (harbor-watch compares vs the previous
           published embedding). Cross-check: this distance must
           reproduce the file's stored prev_cos_drift.
  ema    : causal EMA over ALL (s, 0..f-1, t), alpha = 2/9
           (effective window ~8 frames). Secondary comparator.
  mean8  : mean of 8 temporally separated ALL embeddings of
           (s, ., t), frame f excluded (f is the audit target's own
           image — including it would leak), chosen as 8 evenly
           spaced picks from the remaining 11 frames.
  repl   : distance from e to ALL (s, f, t) — same image, second
           pass. The measurement floor: no baseline recipe can
           push steady-state distance below re-embedding noise.

Statistic: p95 of the distance set (memo's pre-registered primary),
plus median/IQR. Falsifier (memo L5): p95 reduction of mean8 vs
single < 5% kills the recipe change. Prediction was >= 20%.
Bootstrap (rows resampled, 10k) gives a 95% CI on the reduction.
"""
import json

import numpy as np

from common import cos_dist, load_all, load_audit, summarise

rng = np.random.default_rng(20261102)
E = load_all()
audit = load_audit()

# --- validation: recompute prev_cos_drift from stored embeddings ---
val_err = []
for r in audit:
    if r["frame"] >= 1:
        d = cos_dist(r["embedding"], E[r["seq"]][r["frame"] - 1, r["tile"]])
        val_err.append(abs(d - r["prev_cos_drift"]))
val_err = np.array(val_err)

rows = [r for r in audit if r["seq"] in ("A_burst", "B_turntable")
        and r["frame"] >= 1]

d_single, d_ema, d_mean8, d_repl = [], [], [], []
frames_used = []
for r in rows:
    s, f, t, e = r["seq"], r["frame"], r["tile"], r["embedding"]
    series = E[s][:, t]                                # [12, 1280]
    d_single.append(cos_dist(e, series[f - 1]))
    ema = series[0].copy()
    for fp in range(1, f):
        ema = (1 - 2 / 9) * ema + (2 / 9) * series[fp]
    d_ema.append(cos_dist(e, ema))
    cand = [fp for fp in range(12) if fp != f]
    picks = [cand[i] for i in
             np.unique(np.round(np.linspace(0, len(cand) - 1, 8)).astype(int))]
    assert len(picks) == 8
    d_mean8.append(cos_dist(e, series[picks].mean(axis=0)))
    d_repl.append(cos_dist(e, series[f]))
    frames_used.append(f)

d_single, d_ema, d_mean8, d_repl = map(np.array, (d_single, d_ema, d_mean8, d_repl))

red_p95 = (np.percentile(d_single, 95) - np.percentile(d_mean8, 95)) \
    / np.percentile(d_single, 95)
red_med = (np.median(d_single) - np.median(d_mean8)) / np.median(d_single)

boots = []
n = len(rows)
for _ in range(10000):
    idx = rng.integers(0, n, n)
    a, b = d_single[idx], d_mean8[idx]
    pa, pb = np.percentile(a, 95), np.percentile(b, 95)
    boots.append((pa - pb) / pa if pa > 0 else 0.0)
boots = np.array(boots)

print(json.dumps({
    "validation_prev_cos_drift_max_abs_err": float(val_err.max()),
    "n_audit_rows_used": n,
    "frames_used": sorted(int(x) for x in frames_used),
    "single_frame_incumbent": summarise(d_single),
    "ema_alpha_2_over_9": summarise(d_ema),
    "mean_of_8": summarise(d_mean8),
    "replicate_floor": summarise(d_repl),
    "p95_reduction_mean8_vs_single": float(red_p95),
    "median_reduction_mean8_vs_single": float(red_med),
    "p95_reduction_bootstrap_ci95": [float(np.percentile(boots, 2.5)),
                                     float(np.percentile(boots, 97.5))],
}, indent=1))
