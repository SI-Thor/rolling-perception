"""Sensitivity pass for the L5 scorer study: rerun the headline
operating-point comparisons at the two alternate calibration
quantiles (q97.5 and q99.9) flanking the primary q99 discipline.
Same slices, same masks, same runners — only tau changes.
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(HERE)
sys.path.append(os.path.join(HERE, "..", "leverage"))
from common import load_all  # noqa: E402
from l5_scorer_study import (build_reference, load_harbor, pct,  # noqa: E402
                             pr_counts, run_incumbent, run_reference,
                             step_distances)

E_all = load_all()
A, B, C = E_all["A_burst"], E_all["B_turntable"], E_all["C_cuts"]
H, h_truth = load_harbor()
TILES, F12 = 16, 12
posC = np.ones((F12, TILES), dtype=bool); posC[0] = False
negAB = np.zeros((F12, TILES), dtype=bool); negAB[[9, 10, 11]] = True
negA = negAB.copy()
posH = np.zeros((F12, TILES), dtype=bool)
negH = np.zeros((F12, TILES), dtype=bool)
for (f, t), ch in h_truth.items():
    (posH if ch else negH)[f, t] = True

out = {}
for q in (97.5, 99.9):
    inc_cal, ref_cal = [], []
    for E in (A, B):
        D = step_distances(E)
        inc_cal.extend(D[1:9].ravel().tolist())
        for t in range(TILES):
            for f in range(1, 9):
                others = [fp for fp in range(9) if fp != f]
                ref_cal.append(float(1 - np.dot(E[f, t], E[others, t].mean(axis=0)) /
                                     (np.linalg.norm(E[f, t]) *
                                      np.linalg.norm(E[others, t].mean(axis=0)))))
    tau_inc, tau_ref = pct(inc_cal, q), pct(ref_cal, q)
    row = {"tau_inc": tau_inc, "tau_ref": tau_ref}
    _, fiC = run_incumbent(C, tau_inc)
    _, fiA = run_incumbent(A, tau_inc)
    _, fiB = run_incumbent(B, tau_inc)
    inc = pr_counts(fiC, posC, np.zeros_like(posC))
    fp = int(((fiA | fiB) & negAB).sum())
    inc["fp_negAB"] = fp
    inc["precision_pooled"] = inc["tp"] / (inc["tp"] + fp)
    row["incumbent_C_and_drift"] = inc
    seed, _ = build_reference(A, tau_inc)
    for pol in ("frozen", "reset"):
        _, _, fC = run_reference(C, tau_inc, tau_ref, pol, seed_ref=seed)
        _, _, fA = run_reference(A, tau_inc, tau_ref, pol, seed_ref=seed)
        r = pr_counts(fC, posC, np.zeros_like(posC))
        r["fp_negA"] = int((fA & negA).sum())
        r["precision_pooled"] = (r["tp"] / (r["tp"] + r["fp_negA"])
                                 if r["tp"] + r["fp_negA"] else None)
        row[f"seeded_{pol}"] = r
        _, scS, fS = run_reference(C, tau_inc, tau_ref, pol)
        rs = pr_counts(fS, posC, np.zeros_like(posC))
        rs["scored"] = int(scS[1:].sum())
        row[f"streaming_{pol}_C"] = rs
    _, fiH = run_incumbent(H, tau_inc)
    row["incumbent_harbor"] = pr_counts(fiH, posH, negH)
    out[f"q{q}"] = row

print(json.dumps(out, indent=1))
with open(os.path.join(HERE, "sensitivity.json"), "w") as fh:
    json.dump(out, fh, indent=1)
