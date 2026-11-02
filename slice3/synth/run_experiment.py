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

def replay(world, reads, snap_k=None, decontam=None):
    """Feed arrivals (non-dropped reads) to lens+engines; snapshot
    the full state after every arrival. snap_k=None is the v1
    engine; a float arms the snap rule at that band multiple.
    decontam ("A"/"B") arms a SNAP2 band-decontamination variant;
    it is inert when snap_k is None."""
    lens = Lens(nominal_period=0.5)
    engines = {n: EngineObject(n) for n in world.NAMES}
    for e in engines.values():
        e.snap_k = snap_k
        e.decontam = decontam
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


# ---------------------------------------------------------------- snap sweep

SNAP_KS = (2.0, 3.0, 5.0)
# An on-rhythm correction age is ~0.5 +- 0.1 s in this stream; a
# post-drop one is ~1.0 +- 0.15 s. 0.8 s splits the two clusters and
# is used only to AUDIT where fired snaps landed (the guard itself
# is the lens stale_threshold, judged inside EngineObject.correct).
GAP_AGE_SPLIT = 0.8


def measure_variant(world, snaps):
    """The v1 query loop, trimmed to what the snap comparison
    grades: per-(lag, object) engine/sampler errors + serve
    exceedance, manoeuvre bins, per-query reverser lag-1 series,
    and reverser velocity re-convergence."""
    arrivals = [s[0] for s in snaps]
    acc = {(L, n): {"sampler": [], "engine": []}
           for L in LAGS for n in world.NAMES}
    exceed_serve = {(L, n): [] for L in LAGS for n in world.NAMES}
    events = {"speeder": World.ACCEL_T, "reverser": World.REV_T}
    bins = [(-5, 0), (0, 1), (1, 2), (2, 4), (4, 8), (8, 16)]
    man = {n: {b: {"engine1": [], "sampler1": [], "engine2": []}
               for b in bins} for n in events}
    baseline_err = {n: [] for n in world.NAMES}
    rev_series = []          # (t_q, engine lag-1 err, sampler lag-1 err)

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
                serr = math.hypot(tx - sx, ty - sy)
                acc[(L, n)]["sampler"].append(serr)
                sv = esnap[n].serve(t_q, lens_s)
                e = math.hypot(tx - sv.x, ty - sv.y)
                acc[(L, n)]["engine"].append(e)
                if sv.tolerance > 0:
                    exceed_serve[(L, n)].append(
                        1 if e > sv.tolerance else 0)
                if L == 1.0 and 15.0 <= t_q <= 28.0:
                    baseline_err[n].append(e)
                if L == 1.0 and n == "reverser":
                    rev_series.append((t_q, e, serr))
                if n in events and L in (1.0, 2.0):
                    rel = t_q - events[n]
                    for b in bins:
                        if b[0] <= rel < b[1]:
                            if L == 1.0:
                                man[n][b]["engine1"].append(e)
                                man[n][b]["sampler1"].append(serr)
                            else:
                                man[n][b]["engine2"].append(e)
        t_q += QUERY_DT

    classes = {"all": list(world.NAMES),
               "controls": list(world.CONTROLS),
               "speeder": ["speeder"],
               "reverser": ["reverser"]}
    lag_table = []
    for L in LAGS:
        row = {"lag_s": L}
        for cname, members in classes.items():
            ee = [e for n in members for e in acc[(L, n)]["engine"]]
            ex = [x for n in members for x in exceed_serve[(L, n)]]
            row[cname] = {
                "engine_mean": mean(ee), "engine_p95": p95(ee),
                "exceedance": (sum(ex) / len(ex)) if ex else None,
                "n": len(ee)}
        lag_table.append(row)

    man_out = {}
    for n, te in events.items():
        base = statistics.median(baseline_err[n])
        rows, recovery = [], None
        for b in bins:
            d = man[n][b]
            row = {"rel_window_s": list(b),
                   "engine_lag1_mean":
                       mean(d["engine1"]) if d["engine1"] else None,
                   "sampler_lag1_mean":
                       mean(d["sampler1"]) if d["sampler1"] else None,
                   "engine_lag2_mean":
                       mean(d["engine2"]) if d["engine2"] else None}
            rows.append(row)
            if b[0] >= 0 and recovery is None and d["engine1"] \
                    and mean(d["engine1"]) < 1.5 * base:
                recovery = list(b)
        man_out[n] = {"event_t": te, "baseline_lag1_median": base,
                      "recovery_window": recovery, "rows": rows}

    # fine recovery metric: first post-flip query time whose next
    # 2 s AND following 2 s of lag-1 errors both average below
    # 1.5x the variant's own pre-flip baseline median.
    base_rev = man_out["reverser"]["baseline_lag1_median"]
    thr = 1.5 * base_rev
    post = [(t, e) for (t, e, _s) in rev_series if t >= World.REV_T]
    ttb = None
    for idx, (t0, _e) in enumerate(post):
        w1 = [e for (t, e) in post if t0 <= t < t0 + 2.0]
        w2 = [e for (t, e) in post if t0 + 2.0 <= t < t0 + 4.0]
        if w1 and w2 and mean(w1) < thr and mean(w2) < thr:
            ttb = t0 - World.REV_T
            break

    rev_conv = None
    for t_arr, _lt, esnap, _z in snaps:
        if t_arr > World.REV_T and abs(esnap["reverser"].vy - (-3.0)) < 0.3:
            rev_conv = {"t": t_arr,
                        "corrections_after_event":
                            sum(1 for s in snaps
                                if World.REV_T < s[0] <= t_arr)}
            break

    return {"lag_table": lag_table, "manoeuvre": man_out,
            "time_to_baseline_s": ttb,
            "reverser_velocity_reconverged": rev_conv}


def run_snap():
    """Identical streams to run() (same seed, same consumption
    order); only the engine's correction policy varies."""
    rng = random.Random(SEED)
    world = World()
    sensor = Sensor(rng)
    reads = sensor.stream(world, World.T_END)
    with open(os.path.join(HERE, "results.json")) as f:
        v1 = json.load(f)

    variants = {}
    for k in (None,) + SNAP_KS:
        snaps, engines_final, _lens = replay(world, reads, snap_k=k)
        m = measure_variant(world, snaps)
        m["correction_exceedance_trailing100"] = {
            n: engines_final[n].exceedance_rate(100) for n in world.NAMES}
        m["snap_stats"] = {}
        for n in world.NAMES:
            ev = engines_final[n].snap_events
            m["snap_stats"][n] = {
                "n_snaps": engines_final[n].n_snaps,
                "n_suppressed": engines_final[n].n_snap_suppressed,
                "snaps_on_rhythm":
                    sum(1 for e in ev if e[1] <= GAP_AGE_SPLIT),
                "snaps_post_gap_age":
                    sum(1 for e in ev if e[1] > GAP_AGE_SPLIT),
                "events": [[round(x, 3) for x in e] for e in ev]}
        variants["off" if k is None else f"k{k:g}"] = m

    # comparability audit: the snap-off variant must reproduce the
    # v1 lag table's engine means, or the sweep compares nothing.
    audit = []
    for row_v, row_1 in zip(variants["off"]["lag_table"], v1["lag_table"]):
        for cname in ("all", "controls", "speeder", "reverser"):
            audit.append(abs(row_v[cname]["engine_mean"]
                             - row_1[cname]["engine_mean"]) < 1e-9)
    result = {"seed": SEED, "snap_ks": list(SNAP_KS),
              "gap_age_split_s": GAP_AGE_SPLIT,
              "comparability_audit_passed": all(audit),
              "variants": variants}
    with open(os.path.join(HERE, "snap_results.json"), "w") as f:
        json.dump(result, f, indent=1)
    print_snap_tables(result, v1)
    return result


def print_snap_tables(r, v1):
    print(f"comparability audit (snap-off == v1 engine means): "
          f"{r['comparability_audit_passed']}")
    vs = r["variants"]
    print("\nREVERSER RECOVERY (the headline)")
    print(f"{'variant':>8} {'base':>6} {'[0,1)':>7} {'[1,2)':>7} "
          f"{'[2,4)':>7} {'[4,8)':>7} {'rec win':>9} {'t->base':>8} "
          f"{'vel conv':>9}")
    samp_rows = v1["manoeuvre"]["reverser"]["rows"]
    print(f"{'sampler':>8} {v1['manoeuvre']['reverser']['baseline_lag1_median']:>6.3f} "
          + " ".join(f"{row['sampler_lag1_mean']:>7.3f}"
                     for row in samp_rows[1:5])
          + f" {'--':>9} {'never':>8} {'--':>9}")
    for name, m in vs.items():
        mt = m["manoeuvre"]["reverser"]
        rows = mt["rows"]
        vc = m["reverser_velocity_reconverged"]
        print(f"{name:>8} {mt['baseline_lag1_median']:>6.3f} "
              + " ".join(f"{row['engine_lag1_mean']:>7.3f}"
                         for row in rows[1:5])
              + f" {str(mt['recovery_window']):>9} "
              + (f"{m['time_to_baseline_s']:>8.2f}"
                 if m["time_to_baseline_s"] is not None else f"{'never':>8}")
              + (f"{vc['corrections_after_event']:>7}c" if vc else f"{'--':>9}"))
    print("\nSNAP ACCOUNTING (fired / guard-suppressed; fired split "
          "by correction age)")
    for name, m in vs.items():
        if name == "off":
            continue
        parts = []
        for n in World.NAMES:
            s = m["snap_stats"][n]
            parts.append(f"{n}: {s['n_snaps']} fired "
                         f"({s['snaps_on_rhythm']} rhythm / "
                         f"{s['snaps_post_gap_age']} post-gap), "
                         f"{s['n_suppressed']} suppressed")
        print(f" {name}: " + "; ".join(parts))
    print("\nCONTROL COST (engine mean error, snap vs off, by lag)")
    off = {row["lag_s"]: row["controls"]["engine_mean"]
           for row in vs["off"]["lag_table"]}
    for name, m in vs.items():
        if name == "off":
            continue
        print(f" {name}: " + "  ".join(
            f"L{row['lag_s']:g}: {row['controls']['engine_mean']:.3f} "
            f"({(row['controls']['engine_mean'] / off[row['lag_s']] - 1) * 100:+.1f}%)"
            for row in m["lag_table"]))
    print("\nSPEEDER (snap should stay silent — the bleed is honest "
          "model error)")
    for name, m in vs.items():
        mt = m["manoeuvre"]["speeder"]
        print(f" {name}: lag1 bins " + " ".join(
            f"{row['engine_lag1_mean']:.3f}" for row in mt["rows"])
            + f" | snaps fired: "
              f"{m['snap_stats']['speeder']['n_snaps'] if name != 'off' else 0}")
    print("\nEXCEEDANCE PER REGIME (serve level, design point "
          f"{EngineObject.STATED_EXCEEDANCE:.3f})")
    for cname in ("controls", "speeder", "reverser"):
        for name, m in vs.items():
            print(f" {cname:>9} {name:>4}: " + " ".join(
                f"L{row['lag_s']:g}={row[cname]['exceedance']:.2f}"
                for row in m["lag_table"]))
    print("\nCORRECTION EXCEEDANCE (trailing 100, per object)")
    for name, m in vs.items():
        print(f" {name}: " + ", ".join(
            f"{n} {v:.3f}" for n, v in
            m["correction_exceedance_trailing100"].items()))


# ---------------------------------------------------------------- snap2 sweep

SNAP2_VARIANTS = [("off", None, None),
                  ("k2", 2.0, None), ("k3", 3.0, None),
                  ("k2A", 2.0, "A"), ("k2B", 2.0, "B"),
                  ("k3A", 3.0, "A"), ("k3B", 3.0, "B")]
# Selection rule — committed in the README before the results:
# disqualify any variant with a false snap on the controls, or a
# speeder regression (any lag-1 manoeuvre bin worse than snap-off
# by more than max(10% relative, 0.02 absolute)). Among survivors,
# fastest reverser time-to-baseline wins; ties break on fewer
# corrections-to-reconverge, then smaller max control-error delta.
SPEEDER_TOL_REL, SPEEDER_TOL_ABS = 0.10, 0.02


def apply_selection(variants):
    off = variants["off"]
    off_bins = [r["engine_lag1_mean"]
                for r in off["manoeuvre"]["speeder"]["rows"]]
    off_ctrl = {row["lag_s"]: row["controls"]["engine_mean"]
                for row in off["lag_table"]}
    scored = {}
    for name, m in variants.items():
        false_snaps = sum(m["snap_stats"][n]["n_snaps"]
                          for n in World.CONTROLS)
        bins = [r["engine_lag1_mean"]
                for r in m["manoeuvre"]["speeder"]["rows"]]
        worst_excess = max(
            (b - o) - max(SPEEDER_TOL_REL * o, SPEEDER_TOL_ABS)
            for b, o in zip(bins, off_bins))
        ctrl_delta = max(
            row["controls"]["engine_mean"] / off_ctrl[row["lag_s"]] - 1.0
            for row in m["lag_table"])
        vc = m["reverser_velocity_reconverged"]
        scored[name] = {
            "false_snaps_controls": false_snaps,
            "speeder_worst_bin_excess": worst_excess,
            "speeder_regression": worst_excess > 0.0,
            "max_control_error_delta": ctrl_delta,
            "time_to_baseline_s": m["time_to_baseline_s"],
            "corrections_to_reconverge":
                vc["corrections_after_event"] if vc else None,
            "disqualified": false_snaps > 0 or worst_excess > 0.0,
        }
    survivors = {n: s for n, s in scored.items() if not s["disqualified"]}
    winner = None
    if survivors:
        winner = min(survivors, key=lambda n: (
            survivors[n]["time_to_baseline_s"]
            if survivors[n]["time_to_baseline_s"] is not None
            else float("inf"),
            survivors[n]["corrections_to_reconverge"] or 10 ** 9,
            survivors[n]["max_control_error_delta"]))
    return scored, winner


def run_snap2():
    """SNAP2: bare snap vs the two decontamination variants, at
    k in {2, 3}. Identical streams to run()/run_snap(); snap-off
    (with and without a decontam flag) must reproduce v1 exactly."""
    rng = random.Random(SEED)
    world = World()
    sensor = Sensor(rng)
    reads = sensor.stream(world, World.T_END)
    with open(os.path.join(HERE, "results.json")) as f:
        v1 = json.load(f)

    variants = {}
    for name, k, dc in SNAP2_VARIANTS:
        snaps, engines_final, _lens = replay(world, reads,
                                             snap_k=k, decontam=dc)
        m = measure_variant(world, snaps)
        m["correction_exceedance_trailing100"] = {
            n: engines_final[n].exceedance_rate(100) for n in world.NAMES}
        m["snap_stats"] = {}
        for n in world.NAMES:
            ev = engines_final[n].snap_events
            m["snap_stats"][n] = {
                "n_snaps": engines_final[n].n_snaps,
                "n_suppressed": engines_final[n].n_snap_suppressed,
                "n_decontam_excluded":
                    engines_final[n].n_decontam_excluded,
                "sigma_r_final": engines_final[n].sigma_r(),
                "snaps_on_rhythm":
                    sum(1 for e in ev if e[1] <= GAP_AGE_SPLIT),
                "snaps_post_gap_age":
                    sum(1 for e in ev if e[1] > GAP_AGE_SPLIT),
                "events": [[round(x, 3) for x in e] for e in ev]}
        variants[name] = m

    scored, winner = apply_selection(variants)

    # comparability audits: snap-off reproduces v1; a decontam flag
    # with snap disarmed is inert and also reproduces v1.
    def matches_v1(snaps_list):
        mm = measure_variant(world, snaps_list)
        return all(
            abs(row_v[c]["engine_mean"] - row_1[c]["engine_mean"]) < 1e-9
            for row_v, row_1 in zip(mm["lag_table"], v1["lag_table"])
            for c in ("all", "controls", "speeder", "reverser"))

    snaps_off, _e, _l = replay(world, reads)
    audit_off = matches_v1(snaps_off)
    snaps_off_dc, _e2, _l2 = replay(world, reads, snap_k=None,
                                    decontam="B")
    audit_off_dc = matches_v1(snaps_off_dc)

    result = {"seed": SEED,
              "variants_spec": {n: {"snap_k": k, "decontam": dc}
                                for n, k, dc in SNAP2_VARIANTS},
              "comparability_audit_passed": audit_off,
              "decontam_inert_audit_passed": audit_off_dc,
              "selection": scored, "winner": winner,
              "variants": variants}
    with open(os.path.join(HERE, "snap2_results.json"), "w") as f:
        json.dump(result, f, indent=1)
    print_snap2_tables(result)
    return result


def print_snap2_tables(r):
    vs = r["variants"]
    print(f"comparability audit (snap-off == v1): "
          f"{r['comparability_audit_passed']}; decontam-flag-inert "
          f"audit: {r['decontam_inert_audit_passed']}")
    print("\nREVERSER RECOVERY")
    print(f"{'variant':>8} {'base':>6} {'[0,1)':>7} {'[1,2)':>7} "
          f"{'[2,4)':>7} {'[4,8)':>7} {'rec win':>9} {'t->base':>8} "
          f"{'vel conv':>9}")
    for name, m in vs.items():
        mt = m["manoeuvre"]["reverser"]
        rows = mt["rows"]
        vc = m["reverser_velocity_reconverged"]
        print(f"{name:>8} {mt['baseline_lag1_median']:>6.3f} "
              + " ".join(f"{row['engine_lag1_mean']:>7.3f}"
                         for row in rows[1:5])
              + f" {str(mt['recovery_window']):>9} "
              + (f"{m['time_to_baseline_s']:>8.2f}"
                 if m["time_to_baseline_s"] is not None
                 else f"{'never':>8}")
              + (f"{vc['corrections_after_event']:>7}c" if vc
                 else f"{'--':>9}"))
    print("\nSNAP ACCOUNTING (fired per object; excluded residuals; "
          "final sigma_r)")
    for name, m in vs.items():
        if name == "off":
            continue
        parts = []
        for n in World.NAMES:
            s = m["snap_stats"][n]
            parts.append(f"{n}: {s['n_snaps']}f/"
                         f"{s['n_decontam_excluded']}x "
                         f"sr={s['sigma_r_final']:.3f}")
        print(f" {name}: " + "; ".join(parts))
    print("\nSPEEDER BINS (lag-1 engine mean; snap must not help "
          "or hurt)")
    for name, m in vs.items():
        mt = m["manoeuvre"]["speeder"]
        print(f" {name:>4}: " + " ".join(
            f"{row['engine_lag1_mean']:.3f}" for row in mt["rows"])
            + f" | snaps: {m['snap_stats']['speeder']['n_snaps']}")
    print("\nSELECTION (rule committed before the run)")
    for name, s in r["selection"].items():
        print(f" {name:>4}: false={s['false_snaps_controls']} "
              f"speeder_excess={s['speeder_worst_bin_excess']:+.3f} "
              f"ctrl_delta={s['max_control_error_delta']:+.1%} "
              f"ttb={s['time_to_baseline_s']} "
              f"disq={s['disqualified']}")
    print(f" WINNER: {r['winner']}")


if __name__ == "__main__":
    import sys
    if "--snap2" in sys.argv:
        run_snap2()
    elif "--snap" in sys.argv:
        run_snap()
    else:
        run()
