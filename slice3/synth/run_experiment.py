"""Reader-lag measurement: SAMPLER vs ENGINE vs ORACLE.

A reader whose view of the stream is delayed by lag L gets, at query
time t_q, only the reads that arrived by t_q - L.
  SAMPLER: the last raw read in that window, held as-is.
  ENGINE:  the synthesiser's state from that window, extrapolated
           to t_q, with basis label + stated tolerance.
  ORACLE:  ground truth (error 0 by construction; the framing row).

Plus: a manoeuvre event study (speeder acceleration change at 30 s,
reverser direction reversal at 45 s), the exceedance self-test, and
the wave-3 sequence C discrete echo (tile scene-label prediction).

Deterministic: seed fixed. Run: python3 run_experiment.py
Writes results.json next to this file and prints the tables.
"""

from __future__ import annotations

import bisect
import json
import math
import os
import random
import statistics

from engine import EngineObject, Lens, Sensor, World

SEED = 20261101
LAGS = [0.0, 0.5, 1.0, 2.0, 5.0, 10.0]
QUERY_T0, QUERY_T1, QUERY_DT = 12.0, 88.0, 0.25
HERE = os.path.dirname(os.path.abspath(__file__))


def p95(xs):
    s = sorted(xs)
    return s[max(0, math.ceil(0.95 * len(s)) - 1)]


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


# ---------------------------------------------------------------- replay

def replay(world, reads):
    """Feed arrivals (non-dropped reads) to lens+engines; snapshot
    the full state after every arrival."""
    lens = Lens(nominal_period=0.5)
    engines = {n: EngineObject(n) for n in world.NAMES}
    snaps = []  # (t_arrival, lens_tuple, {name: engine snapshot}, {name: raw z})
    for rd in reads:
        if rd.dropped:
            continue
        lens.observe(rd.t)
        for n in world.NAMES:
            engines[n].correct(rd.t, rd.z[n][0], rd.z[n][1], lens)
        snaps.append((rd.t,
                      (lens.est_period, lens.jitter_var),
                      {n: engines[n].snapshot() for n in world.NAMES},
                      dict(rd.z)))
    return snaps, engines, lens


def lens_from(period, var):
    l = Lens(nominal_period=period)
    l.est_period = period
    l.jitter_var = var
    return l


# ---------------------------------------------------------------- main run

def run():
    rng = random.Random(SEED)
    world = World()
    sensor = Sensor(rng)
    reads = sensor.stream(world, World.T_END)
    snaps, engines_final, lens_final = replay(world, reads)
    arrivals = [s[0] for s in snaps]

    # per (lag, object) accumulators
    acc = {}
    basis_counts = {}
    ages = {}
    exceed_serve = {}
    for L in LAGS:
        for n in world.NAMES:
            acc[(L, n)] = {"sampler": [], "engine": []}
            exceed_serve[(L, n)] = []
        basis_counts[L] = {"corrected": 0, "extrapolated": 0, "stale": 0}
        ages[L] = []

    # manoeuvre event study: engine/sampler errors at lag 1 and 2,
    # binned by (t_q - t_event)
    events = {"speeder": World.ACCEL_T, "reverser": World.REV_T}
    bins = [(-5, 0), (0, 1), (1, 2), (2, 4), (4, 8), (8, 16)]
    man = {n: {b: {"engine1": [], "sampler1": [], "engine2": []} for b in bins}
           for n in events}
    baseline_err = {n: [] for n in world.NAMES}  # lag-1 engine err, quiet window
    post_cruise = {"speeder": [], "reverser": []}  # lag-1 engine err after events settle

    t_q = QUERY_T0
    while t_q <= QUERY_T1 + 1e-9:
        for L in LAGS:
            cutoff = t_q - L
            i = bisect.bisect_right(arrivals, cutoff) - 1
            if i < 0:
                continue
            t_arr, (per, var), esnap, z = snaps[i]
            lens_s = lens_from(per, var)
            for n in world.NAMES:
                tx, ty = world.truth(n, t_q)
                sx, sy = z[n]
                acc[(L, n)]["sampler"].append(math.hypot(tx - sx, ty - sy))
                sv = esnap[n].serve(t_q, lens_s)
                e = math.hypot(tx - sv.x, ty - sv.y)
                acc[(L, n)]["engine"].append(e)
                if sv.tolerance > 0:
                    exceed_serve[(L, n)].append(1 if e > sv.tolerance else 0)
                if n == world.NAMES[0]:
                    basis_counts[L][sv.basis] += 1
                    ages[L].append(sv.age)
                if L == 1.0 and 15.0 <= t_q <= 28.0:
                    baseline_err[n].append(e)
                if L == 1.0 and n == "speeder" and 63.0 <= t_q <= 80.0:
                    post_cruise["speeder"].append(e)
                if L == 1.0 and n == "reverser" and 58.0 <= t_q <= 80.0:
                    post_cruise["reverser"].append(e)
                if n in events and L in (1.0, 2.0):
                    rel = t_q - events[n]
                    for b in bins:
                        if b[0] <= rel < b[1]:
                            if L == 1.0:
                                man[n][b]["engine1"].append(e)
                                man[n][b]["sampler1"].append(
                                    acc[(L, n)]["sampler"][-1])
                            else:
                                man[n][b]["engine2"].append(e)
        t_q += QUERY_DT

    # ---- tables
    classes = {"all": list(world.NAMES),
               "controls": list(world.CONTROLS),
               "speeder": ["speeder"],
               "reverser": ["reverser"]}
    lag_table = []
    for L in LAGS:
        row = {"lag_s": L, "mean_age_s": mean(ages[L]),
               "basis": dict(basis_counts[L])}
        for cname, members in classes.items():
            se = [e for n in members for e in acc[(L, n)]["sampler"]]
            ee = [e for n in members for e in acc[(L, n)]["engine"]]
            ex = [x for n in members for x in exceed_serve[(L, n)]]
            row[cname] = {
                "sampler_mean": mean(se), "sampler_p95": p95(se),
                "engine_mean": mean(ee), "engine_p95": p95(ee),
                "exceedance": (sum(ex) / len(ex)) if ex else None,
                "n": len(ee),
            }
        lag_table.append(row)

    corr_exceed = {n: engines_final[n].exceedance_rate(100)
                   for n in world.NAMES}
    sigma_r = {n: engines_final[n].sigma_r() for n in world.NAMES}

    man_table = {}
    for n, te in events.items():
        base = statistics.median(baseline_err[n])
        rows = []
        recovery = None
        for b in bins:
            d = man[n][b]
            row = {"rel_window_s": list(b),
                   "engine_lag1_mean": mean(d["engine1"]) if d["engine1"] else None,
                   "sampler_lag1_mean": mean(d["sampler1"]) if d["sampler1"] else None,
                   "engine_lag2_mean": mean(d["engine2"]) if d["engine2"] else None}
            rows.append(row)
            if b[0] >= 0 and recovery is None and d["engine1"] \
                    and mean(d["engine1"]) < 1.5 * base:
                recovery = b
        man_table[n] = {"event_t": te, "baseline_lag1_median": base,
                        "recovery_window": recovery, "rows": rows}

    # post-event cruise levels + reverser velocity reconvergence,
    # read back out of the per-arrival snapshots
    rev_conv = None
    for t_arr, _lt, esnap, _z in snaps:
        if t_arr > World.REV_T and abs(esnap["reverser"].vy - (-3.0)) < 0.3:
            rev_conv = {"t": t_arr,
                        "corrections_after_event":
                            sum(1 for s in snaps
                                if World.REV_T < s[0] <= t_arr)}
            break
    post = {"speeder_post_accel_lag1_mean": mean(post_cruise["speeder"]),
            "reverser_post_recovery_lag1_mean": mean(post_cruise["reverser"]),
            "reverser_velocity_reconverged": rev_conv}

    result = {
        "seed": SEED,
        "post_event": post,
        "reads_total": len(reads),
        "reads_dropped": sum(1 for r in reads if r.dropped),
        "arrivals": len(snaps),
        "lens_final": {"period": lens_final.est_period,
                       "jitter_std": lens_final.jitter_std,
                       "stale_threshold": lens_final.stale_threshold},
        "stated_exceedance_target": EngineObject.STATED_EXCEEDANCE,
        "sigma_r_final": sigma_r,
        "correction_exceedance_trailing100": corr_exceed,
        "lag_table": lag_table,
        "manoeuvre": man_table,
        "echo_C": echo_c(),
    }
    with open(os.path.join(HERE, "results.json"), "w") as f:
        json.dump(result, f, indent=1)
    print_tables(result)
    return result


# ---------------------------------------------------------------- wave-3 echo

def echo_c():
    """Discrete analogue on the REAL wave-3 sequence C verdict stream
    (repo wave3/verdicts_ALL_C_cuts.jsonl): each tile carries a scene
    label (which side of the A/B interleave it shows), reconstructed
    as the cumulative XOR of its `changed` flags. A delayed reader
    (frame-lag k) gets labels as of frame t-k:
      SAMPLER holds them; ENGINE learns each tile's flip rhythm
      (flip-rate > 0.5 => flips every step) and predicts frame t.
    Metric: fraction of 16 tiles labelled wrong. Also the literal
    changed-set symmetric difference, for the record."""
    path = os.path.join(HERE, "..", "..", "wave3",
                        "verdicts_ALL_C_cuts.jsonl")
    frames = {}
    arrivals = {}
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            frames.setdefault(r["frame"], {})[r["tile"]] = bool(r["changed"])
            arrivals[r["frame"]] = r["t_arrival_us"] / 1e6
    fids = sorted(frames)
    tiles = sorted(frames[fids[0]])
    labels, changed = {}, {}
    run = {t: 0 for t in tiles}
    for fr in fids:
        changed[fr] = {t for t in tiles if frames[fr][t]}
        for t in tiles:
            run[t] ^= 1 if frames[fr][t] else 0
        labels[fr] = dict(run)

    out = {}
    for k in (0, 1, 2, 3):
        s_err, e_err, s_set, e_set = [], [], [], []
        for t in fids:
            m = t - k
            if m < 2 or t < 4:   # engine needs >=2 observed transitions
                continue
            # per-tile flip rate over the frames observed up to m:
            # a tile's label flips at frame fr exactly when its
            # `changed` flag is set there.
            flips, steps = {}, {}
            for tt in tiles:
                flips[tt] = sum(1 for fr in fids[1:m + 1] if frames[fr][tt])
                steps[tt] = m
            s_wrong = e_wrong = 0
            pred_changed = set()
            for tt in tiles:
                p_flip = flips[tt] / steps[tt] if steps[tt] else 0.0
                lab_s = labels[m][tt]
                lab_e = lab_s ^ ((t - m) % 2) if p_flip > 0.5 else lab_s
                if lab_s != labels[t][tt]:
                    s_wrong += 1
                if lab_e != labels[t][tt]:
                    e_wrong += 1
                if p_flip > 0.5:
                    pred_changed.add(tt)
            s_err.append(s_wrong / len(tiles))
            e_err.append(e_wrong / len(tiles))
            s_set.append(len(changed[m] ^ changed[t]) / len(tiles))
            e_set.append(len(pred_changed ^ changed[t]) / len(tiles))
        out[f"frame_lag_{k}"] = {
            "sampler_label_err": mean(s_err), "engine_label_err": mean(e_err),
            "sampler_changedset_err": mean(s_set),
            "engine_changedset_err": mean(e_set),
            "frames_evaluated": len(s_err),
            "frame_period_s": 1 / 30.0}
    return out


# ---------------------------------------------------------------- printing

def print_tables(r):
    print(f"reads {r['reads_total']} (dropped {r['reads_dropped']}), "
          f"arrivals {r['arrivals']}; lens period "
          f"{r['lens_final']['period']:.3f}s jitter "
          f"{r['lens_final']['jitter_std']:.3f}s stale-threshold "
          f"{r['lens_final']['stale_threshold']:.3f}s")
    print(f"stated exceedance target {r['stated_exceedance_target']:.3f}; "
          f"correction exceedance (trailing 100): " +
          ", ".join(f"{k} {v:.3f}" for k, v in
                    r["correction_exceedance_trailing100"].items()))
    print("\nLAG TABLE (radial position error, world units)")
    print(f"{'lag':>5} {'age':>5} | {'samp mean':>9} {'samp p95':>9} | "
          f"{'eng mean':>9} {'eng p95':>9} | {'exceed':>6} | basis (c/e/s)")
    for row in r["lag_table"]:
        a = row["all"]
        b = row["basis"]
        print(f"{row['lag_s']:>5} {row['mean_age_s']:>5.2f} | "
              f"{a['sampler_mean']:>9.3f} {a['sampler_p95']:>9.3f} | "
              f"{a['engine_mean']:>9.3f} {a['engine_p95']:>9.3f} | "
              f"{a['exceedance']:.3f} | {b['corrected']}/{b['extrapolated']}/{b['stale']}")
    print("\nPER-CLASS ENGINE vs SAMPLER (mean error)")
    for cname in ("controls", "speeder", "reverser"):
        print(f" {cname}: " + "  ".join(
            f"L{row['lag_s']:g}: {row[cname]['engine_mean']:.2f}/"
            f"{row[cname]['sampler_mean']:.2f} ex={row[cname]['exceedance']:.2f}"
            for row in r["lag_table"]))
    print("\nMANOEUVRE EVENT STUDY")
    for n, mt in r["manoeuvre"].items():
        print(f" {n} event@{mt['event_t']}s baseline(lag1 median) "
              f"{mt['baseline_lag1_median']:.3f} recovery window "
              f"{mt['recovery_window']}")
        for row in mt["rows"]:
            print(f"   rel {row['rel_window_s']}: engine1 "
                  f"{row['engine_lag1_mean']}, sampler1 "
                  f"{row['sampler_lag1_mean']}, engine2 "
                  f"{row['engine_lag2_mean']}")
    pe = r["post_event"]
    print(f"\nPOST-EVENT CRUISE (lag-1 engine mean): speeder post-accel "
          f"{pe['speeder_post_accel_lag1_mean']:.3f}; reverser recovered "
          f"{pe['reverser_post_recovery_lag1_mean']:.3f}; reverser velocity "
          f"reconverged {pe['reverser_velocity_reconverged']}")
    print("\nWAVE-3 C ECHO (fraction of tiles wrong)")
    for k, v in r["echo_C"].items():
        print(f" {k}: sampler label {v['sampler_label_err']:.3f} "
              f"engine label {v['engine_label_err']:.3f} | sampler set "
              f"{v['sampler_changedset_err']:.3f} engine set "
              f"{v['engine_changedset_err']:.3f} (n={v['frames_evaluated']})")


if __name__ == "__main__":
    run()
