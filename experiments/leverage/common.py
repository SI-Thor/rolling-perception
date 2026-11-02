"""Shared loading + metric helpers for the leverage experiments.

Data: experiments/wave3/driver/embeddings_*.jsonl (I-JEPA 1280-dim tile
embeddings from the Thor jev-rack, wave-3 run 2026-11-01).
Distance: cosine distance 1 - cos(a, b), the exact metric the shipped
harbor-watch pipeline uses (crates/harbor-watch/src/rng.rs
`cosine_distance`: embeddings are NOT assumed unit-norm).
"""
import json
import os

import numpy as np

DRIVER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "..", "wave3", "driver")
SEQS = ("A_burst", "B_turntable", "C_cuts")
FRAMES = 12
TILES = 16
DIM = 1280


def load_all():
    """Return dict seq -> float64 array [frame][tile][1280]."""
    out = {s: np.zeros((FRAMES, TILES, DIM)) for s in SEQS}
    seen = {s: 0 for s in SEQS}
    with open(os.path.join(DRIVER, "embeddings_ALL.jsonl")) as fh:
        for line in fh:
            r = json.loads(line)
            out[r["seq"]][r["frame"], r["tile"]] = r["embedding"]
            seen[r["seq"]] += 1
    assert all(v == FRAMES * TILES for v in seen.values()), seen
    return out


def load_audit():
    """Return list of AUDIT row dicts (embedding as np.array)."""
    rows = []
    with open(os.path.join(DRIVER, "embeddings_AUDIT.jsonl")) as fh:
        for line in fh:
            r = json.loads(line)
            r["embedding"] = np.asarray(r["embedding"], dtype=np.float64)
            rows.append(r)
    return rows


def cos_dist(a, b):
    """1 - cos(a, b) in float64, matching harbor-watch's cosine_distance."""
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0.0 or nb == 0.0:
        return 1.0
    return float(1.0 - np.dot(a, b) / (na * nb))


def cos_dist_many(a, B):
    """cos_dist from vector a to each row of B."""
    na = np.linalg.norm(a)
    nb = np.linalg.norm(B, axis=1)
    dots = B @ a
    with np.errstate(divide="ignore", invalid="ignore"):
        d = 1.0 - dots / (na * nb)
    d[nb == 0.0] = 1.0
    return d


def auc_higher_is_positive(pos, neg):
    """AUC when larger score = more likely positive class.

    AUC = P(pos > neg) + 0.5 * P(pos == neg), computed exactly by
    pairwise comparison (sample sizes here are small).
    """
    pos = np.asarray(pos, dtype=np.float64)
    neg = np.asarray(neg, dtype=np.float64)
    gt = (pos[:, None] > neg[None, :]).sum()
    eq = (pos[:, None] == neg[None, :]).sum()
    return float((gt + 0.5 * eq) / (pos.size * neg.size))


def summarise(x):
    x = np.asarray(x, dtype=np.float64)
    return {
        "n": int(x.size),
        "median": float(np.median(x)),
        "p95": float(np.percentile(x, 95)),
        "mean": float(np.mean(x)),
        "iqr": float(np.percentile(x, 75) - np.percentile(x, 25)),
    }
