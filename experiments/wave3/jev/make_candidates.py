#!/usr/bin/env python3
"""Build the Jev candidate set from harbor-watch fixture verdicts.

Candidate selection (stated, reproducible):
- every tile with raw embedding-change score >= 0.02 (above the ~0.006
  background; captures all flagged, both false positives, and the
  persistent low-level drift tiles), PLUS
- a deterministic sample of 6 clear background tiles (score < 0.01,
  spread across frames) as negative controls for agreement measurement.
Each candidate becomes a compact TEXT state (Jev judges text, not
pixels) in the Syzygy digest style: only numbers a stranger could
recompute from the verdicts + fixture records.
"""
import json, sys

BASE = "~/workspace/rolling-perception-work/wave3/jev"
rows = [json.loads(l) for l in open(f"{BASE}/verdicts.jsonl")]
truth = {}
for l in open(f"{BASE}/fixture.jsonl.truth.jsonl"):
    d = json.loads(l); truth[(d["frame"], d["tile"])] = d["changed"]
fx = {}
for l in open(f"{BASE}/fixture.jsonl"):
    d = json.loads(l); fx[(d["seq"], d["frame"], d["tile"])] = d

# neighbours flagged (raw verdict) per (frame, tile)
def neigh_flagged(frame, tile):
    r, c = divmod(tile, 4)
    n = 0
    for rr in (r-1, r, r+1):
        for cc in (c-1, c, c+1):
            if (rr, cc) == (r, c) or not (0 <= rr < 4 and 0 <= cc < 4):
                continue
            t2 = rr*4+cc
            v = next((x for x in rows if x["frame"] == frame and x["tile"] == t2), None)
            if v and v["changed_raw"]:
                n += 1
    return n

cands = []
for r in rows:
    if r["raw_score"] is not None and r["raw_score"] >= 0.02:
        cands.append(r)
negs = [r for r in rows if r["raw_score"] is not None and r["raw_score"] < 0.01]
negs.sort(key=lambda r: (r["frame"], r["tile"]))
neg_sample = [negs[i] for i in range(0, len(negs), max(1, len(negs)//6))][:6]
cands += neg_sample
cands.sort(key=lambda r: (r["frame"], r["tile"]))

out = []
for r in cands:
    f, t = r["frame"], r["tile"]
    rec = fx.get(("fixture", f, t)) or fx.get((list(fx)[0][0], f, t)) or {}
    diff = r.get("driver_diff")
    if diff is None:
        diff = rec.get("diff_score")
    row, col = divmod(t, 4)
    state = (
        "HARBOR-WATCH TILE-CHANGE CANDIDATE. A fixed camera scene (512x512) is watched as a 4x4 grid of tiles. "
        "Each tile's image embedding (I-JEPA) is compared with the same tile in the previous frame.\n"
        f"tile: row {row}, col {col} (tile {t} of 16)\n"
        f"frame: {f} (compared against frame {f-1})\n"
        f"pixel_diff_score: {diff if diff is not None else 'n/a'} (mean absolute pixel change for this tile, 0..1 scale; a typical unchanged tile is below 0.01)\n"
        f"embedding_change_score: {r['raw_score']:.3f} (cosine distance between this tile's embedding now and last frame; a typical unchanged tile is about 0.006)\n"
        f"neighbour_tiles_flagged: {neigh_flagged(f,t)} of 8 neighbouring tiles were also flagged as changed this frame\n"
        f"smoothed_change_score: {r['smoothed_score']:.3f} (embedding change after spatial smoothing across neighbouring tiles)\n"
        f"system_flag: {'CHANGED' if r['changed_raw'] else 'unchanged'} (flag threshold is 0.25 on embedding change)"
    )
    out.append({
        "frame": f, "tile": t, "state": state,
        "raw_score": r["raw_score"], "smoothed_score": r["smoothed_score"],
        "driver_diff": diff, "system_changed": r["changed_raw"],
        "refined_changed": r["changed"], "truth": truth.get((f, t)),
    })

with open(f"{BASE}/candidates.jsonl", "w") as fh:
    for c in out:
        fh.write(json.dumps(c) + "\n")
print(f"{len(out)} candidates: {sum(1 for c in out if c['truth'])} true changes, "
      f"{sum(1 for c in out if c['system_changed'])} system-flagged")
for c in out:
    print(c["frame"], c["tile"], round(c["raw_score"], 3), "truth=", c["truth"], "sys=", c["system_changed"])
