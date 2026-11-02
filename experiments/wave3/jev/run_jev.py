#!/usr/bin/env python3
"""Ask TypeSafe hosted Jev (jev-latest) to judge harbor-watch tile-change
candidates as TEXT states. One noul question per candidate, timed per call.

Usage: run_jev.py <jev_py_path> [limit]
Writes jev_verdicts.jsonl: candidate fields + {jev_p, jev_changed (p>=0.5),
latency_s, route}.
"""
import json, sys, time
sys.path.insert(0, "/tmp")  # placeholder, real import below

jev_path = sys.argv[1]
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 999
import importlib.util
spec = importlib.util.spec_from_file_location("jev", jev_path)
jev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jev)

BASE = "~/workspace/rolling-perception-work/wave3/jev"
QUESTION = {
    "instructions": "Is this a real scene change in this tile, rather than noise, a lighting shift, or sensor jitter?",
    "type": "noul",
    "criteria": {
        "true": "the tile's content genuinely changed: the embedding change is large AND corroborated — a substantial pixel difference, or neighbouring tiles changing together in the same frame",
        "false": "no genuine content change: the embedding moved while pixels barely changed (noise, lighting shift, or jitter), or the signal is small, isolated, and uncorroborated",
    },
}

cands = [json.loads(l) for l in open(f"{BASE}/candidates.jsonl")][:limit]
out = open(f"{BASE}/jev_verdicts.jsonl", "w")
for c in cands:
    t0 = time.time()
    try:
        data = jev.system_one(c["state"], {"q": QUESTION})
        ans = data.get("answers", {}).get("q", {})
        p = ans.get("noul")
        err = None if p is not None else f"no noul in answer: {ans}"
    except Exception as e:
        p, err = None, f"{type(e).__name__}: {e}"
    dt = time.time() - t0
    rec = dict(c)
    rec.pop("state")
    rec.update({"jev_p": p, "jev_changed": (p >= 0.5) if p is not None else None,
                "latency_s": round(dt, 3), "error": err, "route": "B-direct (jev.py, custom.typesafe)"})
    out.write(json.dumps(rec) + "\n"); out.flush()
    print(f"frame {c['frame']} tile {c['tile']}: p={p} latency={dt:.2f}s err={err}", flush=True)
out.close()
print("done")
