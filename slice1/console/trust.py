#!/usr/bin/env python3
"""Confluence Slice 1 console — the trust loop (SPEC §2.2 demotion rule).

Implements docs/TRUST-LOOP-PAPER-TEST.md's §2 mapping and §6 smallest
mechanism: the single roll-up definition over corrections.jsonl, the
evaluation pass that receipts transitions, and nothing else. The
arithmetic's authority is the note; every constant below cites it.

What runs here (README's trust-loop section says the same in prose):

  rollup()            pure: taps + event times + spans + eras -> the
                      per-stream figures and the demote/hold/restore
                      decision. No I/O, deterministic, `now` is an
                      argument.
  evaluate_stream()   the pass: reads a stream's corrections,
                      events, spans, era markers; runs rollup();
                      appends a trust_status service row to
                      events.jsonl ONLY on transitions; writes
                      ledger/attention/trust-state.json. Idempotent.
  __main__            CLI: python3 trust.py <ledger_dir> [stream ...]

v0 input honesty (the note's build list, item 3): slice 1's watcher
emits no frozen-span receipts and no recalibration stamps yet, so in
production today the span list is empty and the era marker is the
stream's start row. The routing code is live and fixture-tested; its
inputs are simply empty until the watcher ships them. Not wired here.
"""
import json, sys, time
from pathlib import Path

# ---- config: every number cites the paper test ------------------------------
WINDOW_S = 7 * 86400   # §2 closed form W(t): trailing 7 d (SPEC §3.3's figure)
BAR = 0.9              # SPEC §2.2: precision below 0.9 demotes to feed-only
N_MIN = 10             # §2: minimum judged events before any decision (a design
                       #   choice the note names as config — the sparsity fence)
SUSTAIN_DEMOTE = 2     # §2 closed form: decayed on 2 consecutive evaluations
SUSTAIN_RESTORE = 7    # §2 closed form: healthy on 7 consecutive evaluations
MATTERED = "mattered"
DISMISSED = "not-a-change"
TAPS = (MATTERED, DISMISSED)   # the two symmetric citizens of corrections.jsonl


def _event_times(events):
    """events -> {event_id: publish epoch s}. Accepts the console's
    normalised event dicts ({"id","ts",...}) or such a dict directly."""
    if isinstance(events, dict):
        return dict(events)
    return {e["id"]: e["ts"] for e in events if e.get("id") and e.get("ts") is not None}


def _spans(frozen_spans):
    """Normalise span inputs ({"start","end"} dicts or (start,end)
    pairs) to a list of (start_s, end_s), end-inclusive."""
    out = []
    for s in frozen_spans or ():
        if isinstance(s, dict):
            a, b = s["start"], s["end"]
        else:
            a, b = s
        out.append((float(a), float(b)))
    return out


def rollup(corrections, events, frozen_spans, era_markers, now, prior=None):
    """The single definition of the trust roll-up (paper test §2).

    corrections   rows from corrections.jsonl (ts epoch s, event_id,
                  correction) — this stream's only; no I/O here.
    events        {event_id: publish epoch s} (or normalised event dicts)
    frozen_spans  receipted frozen spans, epoch s (empty in v0 production)
    era_markers   [{"ts": epoch s, "what": str}, ...] — latest ≤ now fences
    now           the evaluation instant, epoch s (the note's daily t)
    prior         {"mode","below_run","ok_run"} from trust-state.json;
                  a fresh stream starts {"full", 0, 0}.

    Returns {m, d, n, precision, status, action, mode, feed_fault,
    unknown_event, below_run, ok_run}. Pure: same inputs, same output.

    Window W(t) = taps with ts in (now − 7 d, now], deduped by event_id
    (last tap wins). Era fence: only taps whose event was PUBLISHED at
    or after the latest era marker ≤ now. Frozen: taps on events
    published inside a receipted frozen span are routed out of φ and
    counted as feed_fault — a feed freeze is the feed's crime, not the
    gate's. Judged set G: mattered/dismissed only; other correction
    values are neither (and are visible in the file). Events a tap
    names that the events index cannot time are dropped and counted as
    unknown_event — never silently either side.
    """
    st = dict(prior or {"mode": "full", "below_run": 0, "ok_run": 0})
    pub = _event_times(events)
    spans = _spans(frozen_spans)

    # W(t): the trailing window, deduped by event_id, last tap wins.
    in_window = [c for c in corrections
                 if c.get("ts") is not None and now - WINDOW_S < c["ts"] <= now]
    dedup = {}
    for c in sorted(in_window, key=lambda c: (c["ts"],)):
        dedup[c["event_id"]] = c          # later ts (file order on ties) wins

    # E(t): the era fence — the latest marker at or before now.
    era_start = max((m["ts"] for m in era_markers or () if m["ts"] <= now),
                    default=None)
    era_ok, feed_fault, unknown_event = [], 0, 0
    for eid, c in dedup.items():
        t = pub.get(eid)
        if t is None:
            unknown_event += 1
            continue
        if era_start is not None and t < era_start:
            continue                      # pre-era taps do not convict this era
        if any(a <= t <= b for a, b in spans):
            feed_fault += 1               # frozen-span tap: about the feed
            continue
        era_ok.append(c)

    m = sum(1 for c in era_ok if c.get("correction") == MATTERED)
    d = sum(1 for c in era_ok if c.get("correction") == DISMISSED)
    n = m + d
    precision = (m / n) if n else None

    if n == 0:
        status = "unjudged"               # the sparsity fence: never certified
    elif n < N_MIN:
        status = "insufficient"           # evidence exists, cannot decide
    elif precision >= BAR:
        status = "healthy"
    else:
        status = "decayed"

    # Hysteresis: the note's asymmetric sustains (demote fast, restore slow).
    st["below_run"] = st["below_run"] + 1 if status == "decayed" else 0
    st["ok_run"] = st["ok_run"] + 1 if status == "healthy" else 0
    action = "hold"
    if st["mode"] == "full" and st["below_run"] >= SUSTAIN_DEMOTE:
        st["mode"] = "feed-only"
        st["ok_run"] = 0
        action = "demote"
    elif st["mode"] == "feed-only" and st["ok_run"] >= SUSTAIN_RESTORE:
        st["mode"] = "full"
        st["below_run"] = 0
        action = "restore"
    return {"m": m, "d": d, "n": n,
            "precision": None if precision is None else round(precision, 3),
            "status": status, "action": action, "mode": st["mode"],
            "feed_fault": feed_fault, "unknown_event": unknown_event,
            "below_run": st["below_run"], "ok_run": st["ok_run"],
            "era_ts": era_start}


# ---- the evaluation pass -----------------------------------------------------

def _read_jsonl(path):
    rows = []
    try:
        for line in path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        pass
    return rows


def evaluate_stream(ledger_dir, stream_id, now=None):
    """Run the pass for one stream. Reads corrections + the stream's
    events + span/era inputs, runs rollup, appends a trust_status
    service row to events.jsonl only on a transition, and writes
    ledger/attention/trust-state.json (only when its content changes).
    Idempotent: no new taps, no new row, no rewritten state. Returns
    the rollup dict (with "changed": whether anything was written).
    """
    ledger = Path(ledger_dir)
    sdir = ledger / "streams" / stream_id
    now = time.time() if now is None else now

    events = _read_jsonl(sdir / "events.jsonl")
    pub = {}
    start_ts = None
    for r in events:
        if r.get("kind") == "service" and r.get("event") == "start" \
                and r.get("wall_us") and start_ts is None:
            start_ts = r["wall_us"] / 1e6          # v0 era marker: the start row
        eid = r.get("id") or (f"{stream_id}:{r['frame']}"
                              if r.get("frame") is not None and r.get("kind") != "service"
                              else None)
        ts = r.get("ts") or (r.get("t_capture_us", r.get("wall_us")) or 0) / 1e6
        if eid and ts:
            pub[eid] = ts

    era_markers = ([{"ts": start_ts, "what": "stream start"}] if start_ts else []) \
        + [{"ts": m["ts"], "what": m.get("what", "")}
           for m in _read_jsonl(ledger / "attention" / "era-markers.jsonl")]
    frozen = _read_jsonl(ledger / "attention" / "frozen-spans.jsonl")

    corrections = [c for c in _read_jsonl(ledger / "attention" / "corrections.jsonl")
                   if c.get("stream") == stream_id]

    state_path = ledger / "attention" / "trust-state.json"
    prior = None
    if state_path.exists():
        try:
            s = json.loads(state_path.read_text()).get(stream_id)
            if s:
                prior = {"mode": s.get("mode", "full"),
                         "below_run": s.get("below_run", 0),
                         "ok_run": s.get("ok_run", 0),
                         "era_ts": s.get("era_ts")}
        except (OSError, ValueError):
            prior = None

    r = rollup(corrections, pub, frozen, era_markers, now, prior)

    changed = False
    rows_to_append = []
    if r["action"] == "demote":
        p = f"{r['precision']:.3f}"
        rows_to_append.append({"kind": "service", "event": "trust_status",
                               "action": "demote",
                               "msg": (f"demoted to feed-only: precision {p} < {BAR} "
                                       f"over {r['n']} judged events "
                                       f"(window {WINDOW_S // 86400}d), "
                                       f"sustained {r['below_run']} evaluations"),
                               "wall_us": int(now * 1e6)})
    elif r["action"] == "restore":
        p = f"{r['precision']:.3f}"
        rows_to_append.append({"kind": "service", "event": "trust_status",
                               "action": "restore",
                               "msg": (f"restored to full: precision {p} >= {BAR} "
                                       f"sustained {r['ok_run']} evaluations"),
                               "wall_us": int(now * 1e6)})
    # The note's §5: an era change receipts era_reset — the window's
    # discontinuity is in the record, not smoothed over.
    if prior is not None and r["era_ts"] != prior.get("era_ts"):
        rows_to_append.append({"kind": "service", "event": "trust_status",
                               "action": "era_reset",
                               "msg": ("instrument era change; window re-derived; "
                                       "pre-era corrections no longer convict"),
                               "wall_us": int(now * 1e6)})
    if rows_to_append:
        with open(sdir / "events.jsonl", "a") as f:
            for row in rows_to_append:
                f.write(json.dumps(row) + "\n")
        changed = True

    state = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
        except (OSError, ValueError):
            state = {}
    entry = {"stream": stream_id, "m": r["m"], "d": r["d"], "n": r["n"],
             "precision": r["precision"], "status": r["status"],
             "mode": r["mode"], "feed_fault": r["feed_fault"],
             "unknown_event": r["unknown_event"],
             "below_run": r["below_run"], "ok_run": r["ok_run"],
             "era_ts": r["era_ts"], "evaluated_ts": now}
    # Idempotent: evaluated_ts is bookkeeping, not state — a re-run with
    # no new taps and no transition writes nothing.
    comparable = {k: v for k, v in entry.items() if k != "evaluated_ts"}
    old = state.get(stream_id)
    old_cmp = {k: v for k, v in (old or {}).items() if k != "evaluated_ts"} \
        if old else None
    if old_cmp != comparable:
        state[stream_id] = entry
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=1, sort_keys=True))
        changed = True
    r["changed"] = changed
    return r


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print("usage: python3 trust.py <ledger_dir> [stream_id ...] [--now EPOCH_S]")
        return 2
    ledger = Path(argv[1])
    rest = argv[2:]
    now = None
    if "--now" in rest:
        i = rest.index("--now")
        now = float(rest[i + 1])
        del rest[i:i + 2]
    if rest:
        streams = rest
    elif (ledger / "streams").is_dir():
        streams = sorted(d.name for d in (ledger / "streams").iterdir() if d.is_dir())
    else:
        streams = []
    if not streams:
        print(f"trust: no streams under {ledger}/streams")
        return 1
    for sid in streams:
        r = evaluate_stream(ledger, sid, now=now)
        p = "-" if r["precision"] is None else f"{r['precision']:.3f}"
        print(f"{sid}: n={r['n']} precision={p} status={r['status']} "
              f"mode={r['mode']} feed_fault={r['feed_fault']} "
              f"action={r['action']}{'+receipted' if r['changed'] else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
