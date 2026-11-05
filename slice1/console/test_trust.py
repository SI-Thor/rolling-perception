#!/usr/bin/env python3
"""Trust-loop tests — trust.py against the paper test's own fixtures.

The §4 SYNTHETIC histories of docs/TRUST-LOOP-PAPER-TEST.md are
re-derived here as fixtures, with the note's quoted per-day outputs as
expectations, compared line by line. Everything else covers the brief's
list: sparsity, dedup, window edge, hysteresis, feed-fault routing, era
fence, idempotent re-run, and the evaluation pass's receipts.
Run: python3 test_trust.py (stdlib only; exits non-zero on failure).
"""
import json, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trust  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  {extra}" if extra and not cond else ""))
    if not cond:
        fails.append(name)


DAY = 86400
B0 = 1_700_000_000          # abstract epoch base; all times consistent seconds


def tap(eid, pub_day, tap_day, correction):
    return {"ts": B0 + tap_day * DAY + 3600, "stream": "cam", "event_id": eid,
            "correction": correction, "frame": None, "tiles": None}


def run_days(history_rows, days, frozen=(), markers=()):
    """Drive rollup once per day, threading prior state; return per-day
    results — the note's columns."""
    pub = {}
    for c in history_rows:
        pub[c["event_id"]] = B0 + c["pub_day"] * DAY
    out, prior = [], None
    for day in range(1, days + 1):
        now = B0 + day * DAY + 43200
        r = trust.rollup(history_rows, pub, list(frozen), list(markers), now, prior)
        out.append(r)
        prior = {"mode": r["mode"], "below_run": r["below_run"], "ok_run": r["ok_run"]}
    return out


def rows_with_pub(day_pairs, eid_base=0):
    """[(pub_day, mattered, dismissed)] -> correction rows (pub==tap day)."""
    out = []
    n = [eid_base]
    for pub_day, m, d in day_pairs:
        for _ in range(m):
            n[0] += 1
            out.append(dict(tap(f"cam:{n[0]}", pub_day, pub_day, trust.MATTERED), pub_day=pub_day))
        for _ in range(d):
            n[0] += 1
            out.append(dict(tap(f"cam:{n[0]}", pub_day, pub_day, trust.DISMISSED), pub_day=pub_day))
    return out


# ---- §4 fixture S1+S2: decay -> demotion -> recovery (28 days) ---------------
WEEK1 = [(1, 3, 0), (2, 2, 0), (3, 3, 0), (4, 2, 1), (5, 3, 0), (6, 2, 0), (7, 3, 0)]
DECAY = [(8, 1, 1), (9, 1, 2), (10, 0, 2), (11, 1, 2), (12, 1, 1), (13, 0, 2), (14, 1, 2)]
RECOV = [(d, 3, 0) for d in range(15, 29)]
# The note's quoted table: (day, m, d, n, precision, status, mode, feed_fault)
S12_EXPECT = [
    (1, 3, 0, 3, 1.000, "insufficient", "full", 0),
    (2, 5, 0, 5, 1.000, "insufficient", "full", 0),
    (3, 8, 0, 8, 1.000, "insufficient", "full", 0),
    (4, 10, 1, 11, 0.909, "healthy", "full", 0),
    (5, 13, 1, 14, 0.929, "healthy", "full", 0),
    (6, 15, 1, 16, 0.938, "healthy", "full", 0),
    (7, 18, 1, 19, 0.947, "healthy", "full", 0),
    (8, 16, 2, 18, 0.889, "decayed", "full", 0),
    (9, 15, 4, 19, 0.789, "decayed", "feed-only", 0),
    (10, 12, 6, 18, 0.667, "decayed", "feed-only", 0),
    (11, 11, 7, 18, 0.611, "decayed", "feed-only", 0),
    (12, 9, 8, 17, 0.529, "decayed", "feed-only", 0),
    (13, 7, 10, 17, 0.412, "decayed", "feed-only", 0),
    (14, 5, 12, 17, 0.294, "decayed", "feed-only", 0),
    (15, 7, 11, 18, 0.389, "decayed", "feed-only", 0),
    (16, 9, 9, 18, 0.500, "decayed", "feed-only", 0),
    (17, 12, 7, 19, 0.632, "decayed", "feed-only", 0),
    (18, 14, 5, 19, 0.737, "decayed", "feed-only", 0),
    (19, 16, 4, 20, 0.800, "decayed", "feed-only", 0),
    (20, 19, 2, 21, 0.905, "healthy", "feed-only", 0),
    (21, 21, 0, 21, 1.000, "healthy", "feed-only", 0),
    (22, 21, 0, 21, 1.000, "healthy", "feed-only", 0),
    (23, 21, 0, 21, 1.000, "healthy", "feed-only", 0),
    (24, 21, 0, 21, 1.000, "healthy", "feed-only", 0),
    (25, 21, 0, 21, 1.000, "healthy", "feed-only", 0),
    (26, 21, 0, 21, 1.000, "healthy", "full", 0),
    (27, 21, 0, 21, 1.000, "healthy", "full", 0),
    (28, 21, 0, 21, 1.000, "healthy", "full", 0),
]
rows12 = rows_with_pub(WEEK1 + DECAY + RECOV)
got = run_days(rows12, 28)
mismatches = []
for exp, r in zip(S12_EXPECT, got):
    day, m, d, n, p, st, mode, ff = exp
    if (r["m"], r["d"], r["n"], r["precision"], r["status"], r["mode"], r["feed_fault"]) \
            != (m, d, n, p, st, mode, ff):
        mismatches.append(f"day {day}: want {exp} got "
                          f"(m={r['m']}, d={r['d']}, n={r['n']}, p={r['precision']}, "
                          f"{r['status']}, {r['mode']}, ff={r['feed_fault']})")
check(f"S1+S2: all 28 days match the note's quoted table", not mismatches,
      "; ".join(mismatches[:3]))
check("S1+S2: demote fires on day 9 (2nd decayed evaluation)",
      got[7]["action"] == "hold" and got[8]["action"] == "demote")
check("S1+S2: restore fires on day 26 (7th healthy evaluation)",
      got[25]["action"] == "restore" and all(g["action"] == "hold" for g in got[19:25]))

# ---- §4 fixture S3: frozen-span burst + recalibration era fence ---------------
S3_DAYS = [(1, 2, 0), (2, 2, 0), (3, 2, 0), (4, 2, 0), (5, 0, 0), (6, 2, 0), (7, 2, 0),
           (8, 1, 2), (9, 1, 2), (10, 0, 0), (11, 1, 1), (12, 1, 1), (13, 1, 1), (14, 1, 1)]
S3_EXPECT = [
    (1, 2, 0, 2, 1.000, "insufficient", "full", 0),
    (2, 4, 0, 4, 1.000, "insufficient", "full", 0),
    (3, 6, 0, 6, 1.000, "insufficient", "full", 0),
    (4, 8, 0, 8, 1.000, "insufficient", "full", 0),
    (5, 8, 0, 8, 1.000, "insufficient", "full", 0),
    (6, 10, 0, 10, 1.000, "healthy", "full", 6),
    (7, 12, 0, 12, 1.000, "healthy", "full", 6),
    (8, 11, 2, 13, 0.846, "decayed", "full", 6),
    (9, 10, 4, 14, 0.714, "decayed", "feed-only", 6),
    (10, 0, 0, 0, None, "unjudged", "feed-only", 0),
    (11, 1, 1, 2, 0.500, "insufficient", "feed-only", 0),
    (12, 2, 2, 4, 0.500, "insufficient", "feed-only", 0),
    (13, 3, 3, 6, 0.500, "insufficient", "feed-only", 0),
    (14, 4, 4, 8, 0.500, "insufficient", "feed-only", 0),
]
s3 = rows_with_pub(S3_DAYS, eid_base=100)
frozen = [{"start": B0 + 5 * DAY, "end": B0 + 5 * DAY + 3600}]
era10 = [{"ts": B0 + 10 * DAY, "what": "recalibration: threshold 0.25 -> 0.18"}]
for k in range(6):  # the frozen-span burst: pub day 5, tapped day 6
    s3.append(dict(tap(f"cam:{200 + k}", 5, 6, trust.DISMISSED), pub_day=5))
got3 = run_days(s3, 14, frozen=frozen, markers=era10)
mm3 = []
for exp, r in zip(S3_EXPECT, got3):
    day, m, d, n, p, st, mode, ff = exp
    if (r["m"], r["d"], r["n"], r["precision"], r["status"], r["mode"], r["feed_fault"]) \
            != (m, d, n, p, st, mode, ff):
        mm3.append(f"day {day}: want {exp} got "
                   f"(m={r['m']}, d={r['d']}, n={r['n']}, p={r['precision']}, "
                   f"{r['status']}, {r['mode']}, ff={r['feed_fault']})")
check("S3: all 14 days match the note's quoted table (frozen burst + era fence)",
      not mm3, "; ".join(mm3[:3]))

# ---- sparsity: a stream nobody corrects is UNJUDGED, forever ------------------
now = B0 + 400 * DAY
r = trust.rollup([], {f"cam:{i}": B0 + i for i in range(5000)}, [], [], now, None)
check("sparsity: 0 corrections -> n=0, UNJUDGED, no decision",
      r["n"] == 0 and r["status"] == "unjudged" and r["action"] == "hold" and r["mode"] == "full",
      f"got {r}")
r = trust.rollup([], {f"cam:{i}": B0 + i for i in range(5)}, [], [], now,
                 {"mode": "feed-only", "below_run": 0, "ok_run": 0})
check("sparsity: an unjudged window never restores either (evidence, not time, restores)",
      r["action"] == "hold" and r["mode"] == "feed-only")

# ---- dedup: one flag per event, last tap wins ---------------------------------
base = {f"cam:{i}": B0 + DAY for i in (1, 2)}
rows = [tap("cam:1", 1, 1, trust.DISMISSED), tap("cam:1", 1, 2, trust.MATTERED)]
r = trust.rollup(rows, base, [], [], B0 + 2 * DAY + 43200, None)
check("dedup: dismissed then mattered -> mattered once",
      (r["m"], r["d"], r["n"]) == (1, 0, 1), f"got {(r['m'], r['d'], r['n'])}")
rows = [tap("cam:1", 1, 1, trust.MATTERED), tap("cam:1", 1, 2, trust.DISMISSED)]
r = trust.rollup(rows, base, [], [], B0 + 2 * DAY + 43200, None)
check("dedup: mattered then dismissed -> dismissed once",
      (r["m"], r["d"], r["n"]) == (0, 1, 1), f"got {(r['m'], r['d'], r['n'])}")

# ---- window edge: (now - 7d, now] ---------------------------------------------
now = B0 + 100 * DAY
base = {"a": now - 8 * DAY, "b": now - 7 * DAY, "c": now - 7 * DAY - 1,
        "d": now - 7 * DAY + 1, "e": now}
rows = [tap(x, 1, 1, trust.MATTERED) for x in "abcde"]
for row, t in zip(rows, [now - 8 * DAY + 60, now - 60, now - 7 * DAY - 1,
                         now - 7 * DAY + 1, now]):
    row["ts"] = t
r = trust.rollup(rows, base, [], [], now, None)
check("window edge: (now-7d, now] — a (8d old) and c (7d+1s old) fall out; b, d, e stay",
      r["n"] == 3, f"n={r['n']}")

# ---- hysteresis in isolation ---------------------------------------------------
# Each evaluation gets fresh taps on its own day, so the window never
# starves (the point is the state machine, not the window).
def fresh(kind, day, k=12):
    rs = [tap(f"cam:{i}", day, day, kind) for i in range(k)]
    pb = {f"cam:{i}": B0 + day * DAY for i in range(k)}
    return rs, pb

dec_rows, dec_pub = fresh(trust.DISMISSED, 1)
r1 = trust.rollup(dec_rows, dec_pub, [], [], B0 + 1 * DAY + 43200,
                  {"mode": "full", "below_run": 0, "ok_run": 0})
check("hysteresis: one decayed evaluation does not demote",
      r1["status"] == "decayed" and r1["action"] == "hold" and r1["mode"] == "full")
dec_rows, dec_pub = fresh(trust.DISMISSED, 2)
r2 = trust.rollup(dec_rows, dec_pub, [], [], B0 + 2 * DAY + 43200,
                  {"mode": "full", "below_run": 1, "ok_run": 0})
check("hysteresis: the second consecutive decayed evaluation demotes",
      r2["action"] == "demote" and r2["mode"] == "feed-only")
for k in range(0, 6):
    g_rows, g_pub = fresh(trust.MATTERED, 2 + k)
    rk = trust.rollup(g_rows, g_pub, [], [], B0 + (2 + k) * DAY + 43200,
                      {"mode": "feed-only", "below_run": 0, "ok_run": k})
    check(f"hysteresis: healthy evaluation {k + 1}/7 holds", rk["action"] == "hold")
g_rows, g_pub = fresh(trust.MATTERED, 9)
r7 = trust.rollup(g_rows, g_pub, [], [], B0 + 9 * DAY + 43200,
                  {"mode": "feed-only", "below_run": 0, "ok_run": 6})
check("hysteresis: the seventh healthy evaluation restores", r7["action"] == "restore")

# ---- feed-fault routing ----------------------------------------------------------
fr = [tap(f"cam:{i}", 5, 6, trust.DISMISSED) for i in range(1, 7)]
fr += [tap(f"cam:{i}", 6, 6, trust.MATTERED) for i in range(10, 15)]
fpub = {**{f"cam:{i}": B0 + 5 * DAY for i in range(1, 7)},
        **{f"cam:{i}": B0 + 6 * DAY for i in range(10, 15)}}
fz = [{"start": B0 + 5 * DAY, "end": B0 + 5 * DAY + 3600}]
with_fz = trust.rollup(fr, fpub, fz, [], B0 + 7 * DAY, None)
without_fz = trust.rollup(fr, fpub, [], [], B0 + 7 * DAY, None)
check("feed-fault: frozen-span taps counted as feed_fault, never in phi",
      with_fz["feed_fault"] == 6 and with_fz["n"] == 5
      and with_fz["precision"] == 1.0 and without_fz["precision"] == 0.455,
      f"with={with_fz['feed_fault']}/{with_fz['n']}/{with_fz['precision']} "
      f"without={without_fz['n']}/{without_fz['precision']}")

# ---- era fence ---------------------------------------------------------------------
er = [tap(f"cam:{i}", 2, 2, trust.MATTERED) for i in range(12)]
er += [tap(f"cam:{i}", 9, 9, trust.DISMISSED) for i in range(20, 24)]
epub = {**{f"cam:{i}": B0 + 2 * DAY for i in range(12)},
        **{f"cam:{i}": B0 + 9 * DAY for i in range(20, 24)}}
marker = [{"ts": B0 + 5 * DAY, "what": "recalibration"}]
before = trust.rollup(er, epub, [], marker, B0 + 4 * DAY, None)
after = trust.rollup(er, epub, [], marker, B0 + 9 * DAY + 43200, None)
check("era fence: pre-marker taps stop counting once the marker is past",
      before["n"] == 12 and after["n"] == 4 and after["m"] == 0,
      f"before n={before['n']} after n={after['n']}")

# ---- evaluation pass: receipts, idempotency, start-row era, CLI -------------------
ROOT = Path(tempfile.mkdtemp(prefix="trust-test-"))
LED = ROOT / "ledger"
CAM = LED / "streams" / "cam"
CAM.mkdir(parents=True)
ATT = LED / "attention"
ATT.mkdir()
evrows = [{"kind": "service", "event": "start", "msg": "watcher up",
           "wall_us": (B0 + 0) * 10**6}]
n = [0]
for day, m, d in S3_DAYS:
    for _ in range(m + d):
        n[0] += 1
        evrows.append({"kind": "verdict", "stream": "cam", "frame": n[0],
                       "wall_us": (B0 + day * DAY + 60) * 10**6,
                       "t_capture_us": (B0 + day * DAY + 60) * 10**6,
                       "changed_tiles": [1]})
# corrections reference those frames, same order
corr_rows, k = [], [0]
for day, m, d in S3_DAYS:
    for _ in range(m):
        k[0] += 1
        corr_rows.append(tap(f"cam:{k[0]}", day, day, trust.MATTERED))
    for _ in range(d):
        k[0] += 1
        corr_rows.append(tap(f"cam:{k[0]}", day, day, trust.DISMISSED))
(ATT / "corrections.jsonl").write_text("".join(json.dumps(c) + "\n" for c in corr_rows))
(CAM / "events.jsonl").write_text("".join(json.dumps(r) + "\n" for r in evrows))

r = trust.evaluate_stream(LED, "cam", now=B0 + 8 * DAY + 43200)
check("pass: day-8 evaluation (first decayed) holds — no receipt yet",
      r["status"] == "decayed" and r["action"] == "hold"
      and "trust_status" not in (CAM / "events.jsonl").read_text())
r = trust.evaluate_stream(LED, "cam", now=B0 + 9 * DAY + 43200)
lines = (CAM / "events.jsonl").read_text().splitlines()
trust_rows = [json.loads(l) for l in lines if "trust_status" in l]
check("pass: demote receipt appended at day 9",
      r["action"] == "demote" and len(trust_rows) == 1
      and trust_rows[0]["action"] == "demote"
      and "precision 0.714 < 0.9 over 14 judged events" in trust_rows[0]["msg"],
      f"rows={trust_rows}")
check("pass: trust-state.json written with the figures",
      json.loads((ATT / "trust-state.json").read_text())["cam"]["mode"] == "feed-only")

(ATT / "era-markers.jsonl").write_text(json.dumps(
    {"ts": B0 + 10 * DAY, "what": "recalibration: threshold 0.25 -> 0.18"}) + "\n")
r = trust.evaluate_stream(LED, "cam", now=B0 + 10 * DAY + 43200)
trust_rows = [json.loads(l) for l in (CAM / "events.jsonl").read_text().splitlines()
              if "trust_status" in l]
check("pass: era change receipts era_reset and re-derives the window (n=0, unjudged)",
      r["n"] == 0 and r["status"] == "unjudged"
      and any(t["action"] == "era_reset" for t in trust_rows))

before_state = (ATT / "trust-state.json").read_text()
before_rows = (CAM / "events.jsonl").read_text()
r = trust.evaluate_stream(LED, "cam", now=B0 + 10 * DAY + 43200)
check("pass: idempotent re-run appends nothing and rewrites nothing",
      not r["changed"]
      and (CAM / "events.jsonl").read_text() == before_rows
      and (ATT / "trust-state.json").read_text() == before_state)

# unknown event_id: visible, never silently either side
(ATT / "corrections.jsonl").write_text(
    (ATT / "corrections.jsonl").read_text()
    + json.dumps(tap("cam:9999", 10, 10, trust.DISMISSED)) + "\n")
r = trust.evaluate_stream(LED, "cam", now=B0 + 10 * DAY + 43200)
check("pass: a tap naming an unknown event counts as unknown_event, not phi",
      r["unknown_event"] == 1 and r["n"] == 0)

rc = trust.main(["trust.py", str(LED), "cam", "--now", str(B0 + 11 * DAY + 43200)])
check("CLI: exits 0 and prints the stream line", rc == 0)

print(f"\n{len(fails)} failure(s)" if fails else "\nALL PASS")
sys.exit(1 if fails else 0)
