"""L5-SCORER-STUDY — is a mean-of->=8 reference a better SCORER than
distance-to-previous-frame? (Casey's ruling 2026-11-02, option 3:
L5 is studied as the reference-baseline scorer it actually is;
no core change until a reference scorer is validated as a scorer.)

Pre-registered decision rule (from the ruling, not adjusted here):
the reference scorer earns a product path ONLY IF
  (i)  at equal precision to the incumbent it has HIGHER recall
       on labelled change, AND
  (ii) at least one maintenance policy holds the drift segments
       silent (zero false verdicts) without collapsing recall.
Otherwise L5 closes as "spread result real, detection value not
shown on available material" and the shipped scorer stands.

Material (all read-only, stored embeddings; the embedder is
deterministic, so C_cuts frames are the A/B images re-embedded at
distance exactly 0.0 from embeddings_ALL):
  A_burst      12x16 I-JEPA tile embeddings; gradual, zero cuts.
  B_turntable  12x16; continuous rotation, zero cuts.
  C_cuts       12x16 interleave A0,B0,A1,B1,...; all 11 steps are
               labelled scene cuts (176 tile-steps, positive).
  harbor       12x16 (wave3/jev/fixture.jsonl); steady synthetic
               harbour, 3 labelled changed tile-steps (frame 4,
               tiles 3,7,11), 173 labelled no-change steps.
  A++B, B++A   constructed 24-frame streams (real embeddings, real
               order, concatenated): one seam cut at step 12.

Scorers:
  INC   incumbent: score(f,t) = cos_dist(E[f,t], E[f-1,t]).
        (The shipped pipeline thresholds this raw score too —
        `changed_raw` — alongside its smoothed verdict; the study
        compares the decide metric itself.)
  REF   reference: per-tile reference = mean of the first >=8
        qualifying steady observations; score = cos_dist(E[f,t],
        reference). An observation at frame f qualifies iff the
        tile did not fire on arrival under the INCUMBENT signal
        (step distance <= tau_inc; frame 0 always qualifies) —
        the stopped lane's definition ("steady = the frame did
        not itself fire a change for that tile"). Temporally
        separated = distinct frames (see study doc, deficit 4).
  Policies for REF once a reference exists:
    frozen    reference never moves.
    adapt05   on a non-fired frame: ref <- .95 ref + .05 E[f].
    adapt20   on a non-fired frame: ref <- .80 ref + .20 E[f].
    reset     a fired frame discards the reference; the tile is
              unscored until 8 new qualifying observations exist.

Threshold discipline (identical for both scorers; nothing is fit
to test material): calibration slice = A and B steps 1..8.
  tau_inc = p99 of INC scores on the slice (256 tile-steps).
  tau_ref = p99 of REF-form scores on the slice: for target frame
            f in 1..8, reference = mean of the other 8 frames of
            frames 0..8 (leave-one-out, so every calibration
            reference is a genuine mean-of-8), same tile/scene.
Unscored tile-steps count as misses for recall and cannot fire
(they add nothing to precision's denominator).

Output: results.json next to this script + a stdout summary.
Seed: none needed — every statistic is an exact enumeration.
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, "..", "leverage"))
from common import cos_dist, load_all  # noqa: E402

TILES = 16
NEED = 8
POLICIES = ("frozen", "adapt05", "adapt20", "reset")
ADAPT_ALPHA = {"adapt05": 0.05, "adapt20": 0.20}


# ---------------------------------------------------------------- data
def load_harbor():
    """Return (E[12][16][1280], truth {(frame,tile): bool})."""
    path = os.path.join(HERE, "..", "wave3", "jev", "fixture.jsonl")
    E = np.zeros((12, TILES, 1280))
    with open(path) as fh:
        for line in fh:
            r = json.loads(line)
            E[r["frame"], r["tile"]] = r["embedding"]
    truth = {}
    with open(path + ".truth.jsonl") as fh:
        for line in fh:
            r = json.loads(line)
            truth[(r["frame"], r["tile"])] = bool(r["changed"])
    return E, truth


def step_distances(E):
    """D[f][t] = cos_dist(E[f][t], E[f-1][t]) for f>=1; D[0] unused."""
    F = E.shape[0]
    D = np.zeros((F, TILES))
    for f in range(1, F):
        for t in range(TILES):
            D[f, t] = cos_dist(E[f, t], E[f - 1, t])
    return D


def pct(x, q):
    return float(np.percentile(np.asarray(x, dtype=np.float64), q))


# ---------------------------------------------------------------- runners
def run_incumbent(E, tau):
    """Return per-(f,t) for f>=1: score, fired. Always scored."""
    D = step_distances(E)
    return D, D >= tau


def run_reference(E, tau_inc, tau_ref, policy, seed_ref=None):
    """Causal streaming reference scorer.

    Returns (scores, scored, fired): float/bool arrays [F][16];
    frame 0 is never scored (no step exists). If seed_ref (array
    [16][1280]) is given, every tile starts in scoring mode with
    that reference (the deployment analogue: the 8 qualifying
    observations were accumulated during a preceding steady watch).
    Qualification for (re)accumulation uses the incumbent signal.
    """
    F = E.shape[0]
    D = step_distances(E)
    scores = np.zeros((F, TILES))
    scored = np.zeros((F, TILES), dtype=bool)
    fired = np.zeros((F, TILES), dtype=bool)
    for t in range(TILES):
        if seed_ref is not None:
            ref = seed_ref[t].astype(np.float64).copy()
            acc = None
        else:
            ref = None
            acc = [E[0, t].copy()]  # frame 0 always qualifies
        for f in range(1, F):
            if ref is None:
                if D[f, t] <= tau_inc:
                    acc.append(E[f, t].copy())
                    if len(acc) >= NEED:
                        ref = np.mean(acc, axis=0)
                        acc = None
                continue
            s = cos_dist(E[f, t], ref)
            scores[f, t] = s
            scored[f, t] = True
            if s >= tau_ref:
                fired[f, t] = True
                if policy == "reset":
                    ref = None
                    acc = []
            elif policy in ADAPT_ALPHA:
                a = ADAPT_ALPHA[policy]
                ref = (1.0 - a) * ref + a * E[f, t]
    return scores, scored, fired


def build_reference(E, tau_inc):
    """Mean of the first NEED qualifying observations per tile
    (causal, incumbent-signal qualification). Returns (ref, ready)
    where ready[t] = frame index at which the reference completed
    (None if it never did within the sequence)."""
    F = E.shape[0]
    D = step_distances(E)
    ref = np.zeros((TILES, E.shape[2]))
    ready = {}
    for t in range(TILES):
        acc = [E[0, t].copy()]
        r = None
        if len(acc) >= NEED:
            r = 0
        for f in range(1, F):
            if len(acc) >= NEED:
                break
            if D[f, t] <= tau_inc:
                acc.append(E[f, t].copy())
                if len(acc) >= NEED:
                    r = f
        if len(acc) >= NEED:
            ref[t] = np.mean(acc, axis=0)
            ready[t] = r
    return ref, ready


# ---------------------------------------------------------------- metrics
def pr_counts(fired, pos_mask, neg_mask):
    tp = int((fired & pos_mask).sum())
    fp = int((fired & neg_mask).sum())
    fn = int((~fired & pos_mask).sum())
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": (tp / (tp + fp)) if (tp + fp) else None,
        "recall": (tp / (tp + fn)) if (tp + fn) else None,
    }


def recall_at_precision(pos_scores, neg_scores, target_precision):
    """Sweep thresholds over the pooled scores; return the best
    recall among thresholds whose precision >= target_precision
    (None if no threshold reaches it). Exact enumeration."""
    pos = np.sort(np.asarray(pos_scores))[::-1]
    neg = np.sort(np.asarray(neg_scores))[::-1]
    if pos.size == 0 or target_precision is None:
        return None
    best = None
    # candidate thresholds: every distinct positive score
    for th in np.unique(pos)[::-1]:
        tp = int((pos >= th).sum())
        fp = int((neg >= th).sum())
        if tp + fp == 0:
            continue
        if tp / (tp + fp) >= target_precision:
            rec = tp / pos.size
            if best is None or rec > best:
                best = rec
    return best


def frame_verdicts(fired):
    """Frame-level event = >=1 tile fired. Returns bool [F]."""
    return fired.any(axis=1)


# ---------------------------------------------------------------- main
def main():
    E_all = load_all()
    A, B, C = E_all["A_burst"], E_all["B_turntable"], E_all["C_cuts"]
    H, h_truth = load_harbor()
    out = {}

    # ---- sanity: offline incumbent reproduces the recorded
    # raw_score in wave3/jev/candidates.jsonl (frame 1, tile 0).
    cand_path = os.path.join(HERE, "..", "wave3", "jev", "candidates.jsonl")
    with open(cand_path) as fh:
        cand0 = json.loads(fh.readline())
    d_h10 = cos_dist(H[1, 0], H[0, 0])
    out["sanity"] = {
        "harbor_frame1_tile0_offline": d_h10,
        "harbor_frame1_tile0_recorded_raw_score": cand0["raw_score"],
        "abs_err": abs(d_h10 - cand0["raw_score"]),
        "harbor_cut_shipped_tau_0.25_raw_fired_tiles_frame4":
            sorted(int(t) for t in range(TILES)
                   if cos_dist(H[4, t], H[3, t]) >= 0.25),
    }

    # ---- calibration (A/B steps 1..8 only; identical discipline)
    inc_cal, ref_cal = [], []
    for E in (A, B):
        D = step_distances(E)
        inc_cal.extend(D[1:9].ravel().tolist())
        for t in range(TILES):
            for f in range(1, 9):
                others = [fp for fp in range(9) if fp != f]
                ref = E[others, t].mean(axis=0)
                ref_cal.append(cos_dist(E[f, t], ref))
    tau_inc = pct(inc_cal, 99)
    tau_ref = pct(ref_cal, 99)
    out["calibration"] = {
        "slice": "A_burst + B_turntable steps 1..8 (256 tile-steps)",
        "tau_inc_p99": tau_inc, "tau_ref_p99": tau_ref,
        "inc_cal_median": pct(inc_cal, 50), "inc_cal_p95": pct(inc_cal, 95),
        "ref_cal_median": pct(ref_cal, 50), "ref_cal_p95": pct(ref_cal, 95),
        "tau_sensitivity": {
            f"q{q}": {"tau_inc": pct(inc_cal, q), "tau_ref": pct(ref_cal, q)}
            for q in (97.5, 99.5, 99.9)
        },
    }

    # masks shared across evaluations
    F12 = 12
    posC = np.ones((F12, TILES), dtype=bool); posC[0] = False   # C steps
    test_frames = [9, 10, 11]

    # ================= T1: drift tails A/B steps 9..11, streaming
    t1 = {}
    for name, E in (("A_burst", A), ("B_turntable", B)):
        D, inc_fired = run_incumbent(E, tau_inc)
        neg = np.zeros((F12, TILES), dtype=bool); neg[test_frames] = True
        row = {"incumbent": pr_counts(inc_fired, np.zeros_like(neg), neg)}
        row["incumbent"]["frame_verdicts"] = \
            [int(f) for f in test_frames if frame_verdicts(inc_fired)[f]]
        refA, readyA = build_reference(E, tau_inc)
        row["readiness"] = {str(t): readyA.get(t) for t in range(TILES)}
        for pol in POLICIES:
            s, sc, fi = run_reference(E, tau_inc, tau_ref, pol)
            r = pr_counts(fi, np.zeros_like(neg), neg)
            r["frame_verdicts"] = \
                [int(f) for f in test_frames if frame_verdicts(fi)[f]]
            r["tile_steps_scored_in_window"] = int(sc[test_frames].sum())
            r["tile_steps_unscored_total"] = int((~sc[1:]).sum())
            row[pol] = r
        t1[name] = row
    out["T1_drift_tails"] = t1

    # ================= T2a: C cuts, streaming (as stored)
    D_C, inc_fired_C = run_incumbent(C, tau_inc)
    t2a = {"incumbent": pr_counts(inc_fired_C, posC, np.zeros_like(posC))}
    t2a["incumbent"]["frame_verdicts"] = \
        [int(f) for f in range(1, F12) if frame_verdicts(inc_fired_C)[f]]
    refC, readyC = build_reference(C, tau_inc)
    t2a["reference_readiness_on_C"] = \
        {str(t): readyC.get(t) for t in range(TILES)}
    for pol in POLICIES:
        s, sc, fi = run_reference(C, tau_inc, tau_ref, pol)
        r = pr_counts(fi, posC, np.zeros_like(posC))
        r["tile_steps_scored"] = int(sc[1:].sum())
        r["tile_steps_unscored"] = int((~sc[1:]).sum())
        r["frame_verdicts"] = \
            [int(f) for f in range(1, F12) if frame_verdicts(fi)[f]]
        t2a[pol] = r
    out["T2a_C_streaming"] = t2a

    # ================= T2b: C cuts, seeded reference (deployment
    # analogue: reference accumulated while watching scene A —
    # C's even frames ARE A's frames 0..5, re-embedded identically)
    seed_ref, seed_ready = build_reference(A, tau_inc)
    out["seed_from_A"] = {
        "ready_frame_per_tile": {str(t): seed_ready.get(t) for t in range(TILES)},
        "note": "seed frames are A-sequence frames; C even frames "
                "(A images) contributed to the seed -> their scores "
                "are leakage-optimistic; odd steps (A->B departures) "
                "are clean.",
    }
    odd = np.zeros((F12, TILES), dtype=bool); odd[[1, 3, 5, 7, 9, 11]] = True
    even = np.zeros((F12, TILES), dtype=bool); even[[2, 4, 6, 8, 10]] = True
    # seeded negatives: A steps 9..11 scored from the same seed
    negA = np.zeros((F12, TILES), dtype=bool); negA[test_frames] = True
    t2b = {}
    for pol in POLICIES:
        sC, scC, fiC = run_reference(C, tau_inc, tau_ref, pol, seed_ref=seed_ref)
        sA, scA, fiA = run_reference(A, tau_inc, tau_ref, pol,
                                     seed_ref=seed_ref)
        # NOTE: run_reference with a seed scores A from frame 1;
        # restrict negatives to the 9..11 window via mask.
        entry = {}
        tp = int((fiC & posC).sum())
        fp = int((fiA & negA).sum())
        fn = int((~fiC & posC).sum())
        entry["pooled"] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "neg_pool": "A steps 9..11 (48 tile-steps)",
            "pos_pool": "C steps 1..11 (176 tile-steps)",
        }
        entry["odd_departures_only"] = pr_counts(fiC, odd, np.zeros_like(odd))
        entry["even_returns_only"] = pr_counts(fiC, even, np.zeros_like(even))
        entry["frame_verdicts_C"] = \
            [int(f) for f in range(1, F12) if frame_verdicts(fiC)[f]]
        entry["tile_steps_unscored_C"] = int((~scC[1:]).sum())
        entry["scores_for_curves"] = {
            "pos": sC[posC].tolist(),
            "neg": sA[negA].tolist(),
            "pos_scored_mask": scC[posC].tolist(),
        }
        t2b[pol] = entry
    out["T2b_C_seeded"] = t2b

    # incumbent scores for curves (positives C steps; negatives
    # A/B steps 9..11)
    negAB = np.zeros((F12, TILES), dtype=bool); negAB[test_frames] = True
    _, inc_fired_A = run_incumbent(A, tau_inc)
    _, inc_fired_B = run_incumbent(B, tau_inc)
    inc_neg_fired = inc_fired_A | inc_fired_B
    inc_pool = pr_counts(inc_fired_C, posC, np.zeros_like(posC))
    fp_inc = int((inc_neg_fired & negAB).sum())
    inc_pool["fp"] = fp_inc
    inc_pool["precision"] = inc_pool["tp"] / (inc_pool["tp"] + fp_inc)
    inc_pool["neg_pool"] = "A+B steps 9..11 (96 tile-steps)"
    out["incumbent_pooled"] = inc_pool
    inc_pos_scores = step_distances(C)[posC]
    inc_neg_scores = np.concatenate([step_distances(A)[negAB],
                                     step_distances(B)[negAB]])
    out["curves"] = {
        "incumbent": {
            "recall_at_own_precision": float(
                (inc_pos_scores >= tau_inc).mean()),
            "precision_at_tau": inc_pool["precision"],
        },
    }
    for pol in POLICIES:
        e = t2b[pol]
        pos_s = np.array(e["scores_for_curves"]["pos"])
        neg_s = np.array(e["scores_for_curves"]["neg"])
        scored = np.array(e["scores_for_curves"]["pos_scored_mask"])
        # unscored positives can never fire at any threshold:
        # they enter recall's denominator via pos.size total.
        best = None
        for th in np.unique(pos_s[scored])[::-1] if scored.any() else []:
            tp = int((pos_s[scored] >= th).sum())
            fp = int((neg_s >= th).sum())
            if tp + fp and tp / (tp + fp) >= inc_pool["precision"]:
                rec = tp / pos_s.size
                if best is None or rec > best:
                    best = rec
        out["curves"][pol] = {
            "recall_at_incumbent_precision": best,
            "incumbent_precision_target": inc_pool["precision"],
        }

    # ================= T3: constructed streams A++B, B++A
    t3 = {}
    for name, E in (("A_then_B", np.concatenate([A, B], axis=0)),
                    ("B_then_A", np.concatenate([B, A], axis=0))):
        F = E.shape[0]
        seam = 12
        D, inc_f = run_incumbent(E, tau_inc)
        ent = {}
        ent["incumbent"] = {
            "seam_tiles_fired": int(inc_f[seam].sum()),
            "seam_frame_verdict": bool(inc_f[seam].any()),
            "pre_seam_false_verdict_frames":
                [int(f) for f in range(1, seam) if inc_f[f].any()],
            "post_seam_fired_frames":
                [int(f) for f in range(seam + 1, F) if inc_f[f].any()],
            "post_seam_fired_tile_steps": int(inc_f[seam + 1:].sum()),
        }
        for pol in POLICIES:
            s, sc, fi = run_reference(E, tau_inc, tau_ref, pol)
            post = fi[seam + 1:]
            silent = [int(f) for f in range(seam + 1, F) if not fi[f].any()]
            ent[pol] = {
                "seam_tiles_fired": int(fi[seam].sum()),
                "seam_frame_verdict": bool(fi[seam].any()),
                "pre_seam_false_verdict_frames":
                    [int(f) for f in range(1, seam) if fi[f].any()],
                "post_seam_fired_frames":
                    [int(f) for f in range(seam + 1, F) if fi[f].any()],
                "post_seam_fired_tile_steps": int(post.sum()),
                "first_post_seam_silent_frame": silent[0] if silent else None,
                "tile_steps_unscored_total": int((~sc[1:]).sum()),
                "tile_steps_unscored_post_seam":
                    int((~sc[seam + 1:]).sum()),
            }
        t3[name] = ent
    out["T3_constructed_streams"] = t3

    # ================= T4: harbor fixture (test role)
    posH = np.zeros((F12, TILES), dtype=bool)
    negH = np.zeros((F12, TILES), dtype=bool)
    for (f, t), ch in h_truth.items():
        (posH if ch else negH)[f, t] = True
    D_H, inc_fired_H = run_incumbent(H, tau_inc)
    t4 = {"incumbent": pr_counts(inc_fired_H, posH, negH)}
    t4["incumbent"]["frame4_fired_tiles"] = \
        sorted(int(t) for t in range(TILES) if inc_fired_H[4, t])
    refH, readyH = build_reference(H, tau_inc)
    t4["reference_readiness"] = {str(t): readyH.get(t) for t in range(TILES)}
    t4["changed_tiles_ready_by_frame4"] = \
        {str(t): readyH.get(t) for t in (3, 7, 11)}
    for pol in POLICIES:
        s, sc, fi = run_reference(H, tau_inc, tau_ref, pol)
        r = pr_counts(fi, posH, negH)
        r["tile_steps_scored"] = int(sc[1:].sum())
        r["tile_steps_unscored"] = int((~sc[1:]).sum())
        r["false_verdict_frames"] = \
            [int(f) for f in range(1, F12) if fi[f].any() and f != 4]
        t4[pol] = r
    out["T4_harbor"] = t4

    with open(os.path.join(HERE, "results.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
