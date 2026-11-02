"""L3 — nuisance measurement + subspace fix (memo Lever 3, part a).

Part 1 — rho-hat per tile. Paper's rho(f) = tr C_f^{1/2} / k with
C_f = cov of E[f(x)|z] needs whitening in 1280 dims from 24 samples
per tile: inestimable. We compute the trace-ratio analogue by
variance decomposition, per tile t, over its 24 steady
re-observations (12 frames of scene A + 12 of scene B, same tile):

    rho_hat_t = SS_between-scenes / SS_total        (trace form)

Nuisance share = 1 - rho_hat_t. Caveat carried into the report:
within-scene variance here includes genuine gradual change
(A = fresh generations, B = rotation), so 1 - rho_hat is an UPPER
bound on pure nuisance, and rho_hat a lower bound on the paper's
rho. A pooled version (cells = (tile, scene), all 384 steady
embeddings) is reported alongside.

Part 2 — subspace fix, held out. Nuisance subspace = top principal
components of pooled within-cell deviations (x - mean of its
(scene, tile) cell), estimated on ONE half of the tiles and
evaluated on the OTHER half (cross-fitted both ways, then pooled,
so no evaluated step contributed to its own subspace).
Change-detection task (the gate's decide step, embedding distance
only — the pixel-diff nomination stage is not part of this test):
  positive step: consecutive frames of C_cuts (every boundary is a
                 scene cut, all tiles, ground truth)
  negative step: consecutive frames of A_burst / B_turntable
                 (no cut, ground truth)
Score: cosine distance between the two frames' embeddings of the
same tile, full-space vs projected onto the orthogonal complement
of the nuisance subspace (cosine after projection, matching the
shipped metric family). Headline m: smallest m capturing >= 50%
of within-cell variance (per estimation half). Sweep shown for
transparency. Pre-registered falsifier (memo L3a): delta-AUC <= 0
on held-out C boundaries kills the subspace fix.
"""
import json

import numpy as np

from common import auc_higher_is_positive, cos_dist, load_all

rng = np.random.default_rng(20261102)
E = load_all()
A, B, C = E["A_burst"], E["B_turntable"], E["C_cuts"]
STEADY = {"A_burst": A, "B_turntable": B}

# ---------- Part 1: rho-hat ----------
rho_tiles = []
ss_b_tot, ss_t_tot = 0.0, 0.0
for t in range(16):
    obs = np.concatenate([A[:, t], B[:, t]])          # [24, 1280]
    grand = obs.mean(axis=0)
    ss_tot = float(((obs - grand) ** 2).sum())
    ss_bet = float(sum(12 * ((sc[:, t].mean(axis=0) - grand) ** 2).sum()
                       for sc in (A, B)))
    rho_tiles.append(ss_bet / ss_tot)
    ss_b_tot += ss_bet
    ss_t_tot += ss_tot
rho_tiles = np.array(rho_tiles)

# Pooled: cells = (tile, scene); SS_between over 32 cell means.
all_obs = np.concatenate([A.reshape(-1, 1280), B.reshape(-1, 1280)])
grand = all_obs.mean(axis=0)
ss_tot_p = float(((all_obs - grand) ** 2).sum())
ss_bet_p = 0.0
for sc in (A, B):
    for t in range(16):
        ss_bet_p += 12 * float(((sc[:, t].mean(axis=0) - grand) ** 2).sum())

# ---------- Part 2: subspace fix, cross-fitted by tile halves ----------
def deviations(tiles):
    """Within-cell deviation vectors for (scene, tile) cells."""
    devs = []
    for sc in (A, B):
        for t in tiles:
            cell = sc[:, t]
            devs.append(cell - cell.mean(axis=0))
    return np.concatenate(devs)


def steps(seq, tiles):
    """Consecutive-frame cosine distances, all steps for given tiles."""
    return {(f, t): cos_dist(seq[f, t], seq[f - 1, t])
            for f in range(1, 12) for t in tiles}


def projected_dist(x, y, V):
    """Cosine distance after projecting out the row space of V."""
    if V.shape[0]:
        x = x - (x @ V.T) @ V
        y = y - (y @ V.T) @ V
    nx, ny = np.linalg.norm(x), np.linalg.norm(y)
    if nx < 1e-9 or ny < 1e-9:
        return 1.0  # projection annihilated the vector; call it maximal
    return float(1.0 - (x @ y) / (nx * ny))


def precision_at_recall(pos, neg, recall=0.90):
    thr = np.quantile(pos, 1.0 - recall)
    tp = float((pos >= thr).sum())
    fp = float((neg >= thr).sum())
    return tp / (tp + fp) if tp + fp else 1.0


halves = [list(range(8)), list(range(8, 16))]
pooled = []          # (label, d_full, d_sub_m50) for every held-out step
per_direction = []
sweep_ms = [8, 32, 64, 128, 256]
sweep = {m: [] for m in sweep_ms}   # delta-AUC per direction

for est_tiles, eval_tiles in ((halves[0], halves[1]), (halves[1], halves[0])):
    D = deviations(est_tiles)
    _, S, Vt = np.linalg.svd(D, full_matrices=False)
    var = S ** 2
    cum = np.cumsum(var) / var.sum()
    m50 = int(np.searchsorted(cum, 0.50) + 1)
    rank = int((S > 1e-10).sum())

    pos_full, pos_sub = [], []
    neg_full, neg_sub = [], []
    V50 = Vt[:m50]
    for f in range(1, 12):
        for t in eval_tiles:
            pos_full.append(cos_dist(C[f, t], C[f - 1, t]))
            pos_sub.append(projected_dist(C[f, t], C[f - 1, t], V50))
            pooled.append((1, pos_full[-1], pos_sub[-1]))
    for sc in (A, B):
        for f in range(1, 12):
            for t in eval_tiles:
                neg_full.append(cos_dist(sc[f, t], sc[f - 1, t]))
                neg_sub.append(projected_dist(sc[f, t], sc[f - 1, t], V50))
                pooled.append((0, neg_full[-1], neg_sub[-1]))
    auc_f = auc_higher_is_positive(pos_full, neg_full)
    auc_s = auc_higher_is_positive(pos_sub, neg_sub)
    per_direction.append({
        "est_tiles": est_tiles, "eval_tiles": eval_tiles,
        "m50": m50, "rank": rank,
        "auc_full": auc_f, "auc_sub_m50": auc_s, "delta_auc": auc_s - auc_f,
        "prec_at_recall90_full": precision_at_recall(np.array(pos_full), np.array(neg_full)),
        "prec_at_recall90_sub": precision_at_recall(np.array(pos_sub), np.array(neg_sub)),
    })
    for m in sweep_ms:
        Vm = Vt[:min(m, rank)]
        ps = [projected_dist(C[f, t], C[f - 1, t], Vm)
              for f in range(1, 12) for t in eval_tiles]
        ns = [projected_dist(sc[f, t], sc[f - 1, t], Vm)
              for sc in (A, B) for f in range(1, 12) for t in eval_tiles]
        sweep[m].append(auc_higher_is_positive(ps, ns) - auc_f)

pooled = np.array([(l, a, b) for (l, a, b) in pooled], dtype=np.float64)
lab, dfull, dsub = pooled[:, 0], pooled[:, 1], pooled[:, 2]
auc_full_pooled = auc_higher_is_positive(dfull[lab == 1], dfull[lab == 0])
auc_sub_pooled = auc_higher_is_positive(dsub[lab == 1], dsub[lab == 0])

# Bootstrap CI for pooled delta-AUC (resample steps within class).
boots = []
pos_i = np.where(lab == 1)[0]
neg_i = np.where(lab == 0)[0]
for _ in range(2000):
    pi = rng.choice(pos_i, size=pos_i.size, replace=True)
    ni = rng.choice(neg_i, size=neg_i.size, replace=True)
    boots.append(auc_higher_is_positive(dsub[pi], dsub[ni])
                 - auc_higher_is_positive(dfull[pi], dfull[ni]))
boots = np.array(boots)

print(json.dumps({
    "rho_hat_per_tile": {
        "values": [round(float(v), 4) for v in rho_tiles],
        "median": float(np.median(rho_tiles)),
        "iqr": float(np.percentile(rho_tiles, 75) - np.percentile(rho_tiles, 25)),
        "min": float(rho_tiles.min()), "max": float(rho_tiles.max()),
        "pooled_per_tile_ss_ratio": ss_b_tot / ss_t_tot,
        "pooled_cells_ratio": ss_bet_p / ss_tot_p,
        "median_nuisance_share_upper_bound": float(1.0 - np.median(rho_tiles)),
    },
    "per_direction": per_direction,
    "pooled_auc_full": auc_full_pooled,
    "pooled_auc_sub_m50": auc_sub_pooled,
    "pooled_delta_auc": auc_sub_pooled - auc_full_pooled,
    "pooled_prec_at_recall90_full": precision_at_recall(dfull[lab == 1], dfull[lab == 0]),
    "pooled_prec_at_recall90_sub": precision_at_recall(dsub[lab == 1], dsub[lab == 0]),
    "delta_auc_bootstrap_ci95": [float(np.percentile(boots, 2.5)),
                                 float(np.percentile(boots, 97.5))],
    "sweep_delta_auc_by_m": {str(m): [float(v) for v in sweep[m]] for m in sweep_ms},
}, indent=1))
