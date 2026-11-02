"""L1 — weaker-claim check (PAPER-LEVERAGE-2610.39302, Lever 1).

Claim under test: within one embedder's space, same-scene
re-observations sit systematically closer than cross-scene pairs —
AUC of embedding (cosine) distance as a same/cross discriminator
must be well above chance (0.5). Pre-registered falsifier
(memo L1): AUC ~ 0.5 kills the foundation claim on our own data.

Pairs (tile-matched throughout, so tile identity is controlled):
  same  : same tile, two frames of the same sequence (A or B)
  cross : same tile, one frame from A and one from B
Also: the baseline form the memo phrases (distance to own-scene
leave-one-out mean baseline vs the other scene's baseline), and a
replicate noise floor (C_cuts frames are the A/B source images
re-embedded in a separate rack pass: C[2i] is A frame i's image,
C[2i+1] is B frame i's image).
"""
import itertools
import json

import numpy as np

from common import auc_higher_is_positive, cos_dist, load_all, summarise

E = load_all()
A, B, C = E["A_burst"], E["B_turntable"], E["C_cuts"]

same, cross = [], []
same_adjacent = []
for t in range(16):
    for f1, f2 in itertools.combinations(range(12), 2):
        same.append(cos_dist(A[f1, t], A[f2, t]))
        same.append(cos_dist(B[f1, t], B[f2, t]))
    for f in range(11):
        same_adjacent.append(cos_dist(A[f, t], A[f + 1, t]))
        same_adjacent.append(cos_dist(B[f, t], B[f + 1, t]))
    for f1 in range(12):
        for f2 in range(12):
            cross.append(cos_dist(A[f1, t], B[f2, t]))

same = np.array(same)
cross = np.array(cross)
# AUC of distance as a same/cross discriminator: a random cross pair
# should be FARTHER than a random same pair.
auc_pairs = auc_higher_is_positive(cross, same)
auc_pairs_adj = auc_higher_is_positive(cross, np.array(same_adjacent))

# Baseline form: for every embedding, distance to its own scene's
# leave-one-out mean baseline (same tile) vs the other scene's mean
# baseline (same tile).
own_d, other_d = [], []
for seq, other in ((A, B), (B, A)):
    for t in range(16):
        other_base = other[:, t].mean(axis=0)
        for f in range(12):
            loo = np.delete(seq[:, t], f, axis=0).mean(axis=0)
            own_d.append(cos_dist(seq[f, t], loo))
            other_d.append(cos_dist(seq[f, t], other_base))
auc_base = auc_higher_is_positive(np.array(other_d), np.array(own_d))

# Replicate noise floor: identical image, two separate rack passes.
repl = []
for i in range(6):
    for t in range(16):
        repl.append(cos_dist(A[i, t], C[2 * i, t]))
        repl.append(cos_dist(B[i, t], C[2 * i + 1, t]))

print(json.dumps({
    "same_pairs": summarise(same),
    "same_pairs_adjacent_only": summarise(same_adjacent),
    "cross_pairs": summarise(cross),
    "AUC_pairs_cross_vs_same": auc_pairs,
    "AUC_pairs_cross_vs_same_adjacent": auc_pairs_adj,
    "baseline_form": {
        "own_scene_LOO_baseline_dist": summarise(own_d),
        "other_scene_baseline_dist": summarise(other_d),
        "AUC": auc_base,
    },
    "replicate_noise_floor": summarise(repl),
}, indent=1))
