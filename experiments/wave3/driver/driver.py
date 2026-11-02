#!/usr/bin/env python3
"""Wave-3 driver: real frames -> tiles -> cheap diff perceive -> I-JEPA embeds
via the Thor's jev-rack, under two strategies (ALL vs CHANGED), plus an audit
pass over tiles CHANGED skipped. Run on the Thor with ~/ml/.venv/bin/python.
All outputs land in the play dir given as argv[1]."""
import io, json, math, os, sys, time
import numpy as np
import requests
from PIL import Image

PLAY = sys.argv[1]
RACK = "http://127.0.0.1:8077/embed/image"
CADENCE_US = 33333  # MODELLED 30 fps arrival label — see SCHEMA.md
log_lines = []
def log(msg):
    s = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(s, flush=True); log_lines.append(s)

# ---------- build sequences ----------
def load_pngs(pattern_dir, prefix):
    import glob
    paths = sorted(glob.glob(os.path.join(pattern_dir, prefix)))
    return [np.asarray(Image.open(p).convert("RGB"), dtype=np.float32) for p in paths], paths

A, A_paths = load_pngs(os.path.expanduser("~/image-studio/outputs"), "burst_1792818193_b512cd_f*.png")
log(f"seq A: {len(A)} frames from {A_paths[0]} .. {A_paths[-1]}, shape {A[0].shape}")

webp = Image.open(os.path.expanduser("~/sitka-distill/showcase/dock-turntable.webp"))
B = []
for i in range(12):
    webp.seek(i)
    fr = webp.convert("RGB")
    w, h = fr.size                      # 540x960
    fr = fr.crop((0, (h - w)//2, w, (h - w)//2 + w)).resize((512, 512))
    B.append(np.asarray(fr, dtype=np.float32))
log(f"seq B: {len(B)} frames extracted from dock-turntable.webp (centre-crop 540x540 -> 512x512)")

C = []
for i in range(6):
    C.append(A[i]); C.append(B[i])
SEQS = {"A_burst": A, "B_turntable": B, "C_cuts": C}
log(f"seq C: interleaved A/B, {len(C)} frames, every boundary a known cut")

# ---------- tile + save crops + diffs ----------
os.makedirs(os.path.join(PLAY, "crops"), exist_ok=True)
def tiles_of(frame):
    return [frame[r*128:(r+1)*128, c*128:(c+1)*128] for r in range(4) for c in range(4)]

diffs = {}   # (seq, frame, tile) -> float
crop_path = {}
pooled = []
for name, frames in SEQS.items():
    prev = None
    for fi, fr in enumerate(frames):
        tls = tiles_of(fr)
        for ti, t in enumerate(tls):
            p = os.path.join(PLAY, "crops", f"{name}_f{fi:02d}_t{ti:02d}.png")
            Image.fromarray(t.astype(np.uint8)).save(p)
            crop_path[(name, fi, ti)] = p
            if prev is None:
                d = 255.0
            else:
                d = float(np.mean(np.abs(t - prev[ti])))
                pooled.append(d)
            diffs[(name, fi, ti)] = d
        prev = tls
pooled = np.array(pooled)
THRESHOLD = float(np.median(pooled))
log(f"diff distribution over {len(pooled)} tile-steps: min={pooled.min():.3f} "
    f"p25={np.percentile(pooled,25):.3f} median={np.median(pooled):.3f} "
    f"p75={np.percentile(pooled,75):.3f} p95={np.percentile(pooled,95):.3f} max={pooled.max():.3f}")
log(f"THRESHOLD (calibration rule: pooled median of all tile diffs) = {THRESHOLD:.3f}")

# ---------- rack embedding ----------
session = requests.Session()
latencies = []
first_call = [True]
def embed(name, fi, ti, count=True):
    p = crop_path[(name, fi, ti)]
    with open(p, "rb") as fh:
        data = fh.read()
    t0 = time.perf_counter()
    r = session.post(RACK, files={"file": (os.path.basename(p), data, "image/png")}, timeout=600)
    dt = time.perf_counter() - t0
    r.raise_for_status()
    emb = r.json()["embedding"]
    assert len(emb) == 1280, f"embedding dim {len(emb)}"
    if first_call[0]:
        log(f"first embed call (includes I-JEPA lazy load): {dt:.1f}s")
        first_call[0] = False
    elif count:
        latencies.append(dt)
    return emb, dt

def record_line(fout, name, fi, ti, emb, extra=None):
    line = {"seq": name, "frame": fi, "tile": ti,
            "t_arrival_us": fi * CADENCE_US,
            "diff_score": round(diffs[(name, fi, ti)], 4),
            "embedding": emb}
    if extra: line.update(extra)
    fout.write(json.dumps(line) + "\n")

def run_strategy(strategy):
    path = os.path.join(PLAY, f"embeddings_{strategy}.jsonl")
    n = 0; t_start = time.perf_counter()
    with open(path, "w") as fout:
        for name, frames in SEQS.items():
            for fi in range(len(frames)):
                for ti in range(16):
                    if strategy == "CHANGED" and fi > 0 and diffs[(name, fi, ti)] <= THRESHOLD:
                        continue
                    emb, _ = embed(name, fi, ti)
                    record_line(fout, name, fi, ti, emb)
                    n += 1
    wall = time.perf_counter() - t_start
    log(f"strategy {strategy}: {n} embeds, wall {wall:.1f}s -> {path}")
    return n, wall

n_all, wall_all = run_strategy("ALL")
n_chg, wall_chg = run_strategy("CHANGED")

# ---------- audit: embed a sample of CHANGED-skipped tiles anyway ----------
# Reference: strategy ALL's embedding of the same tile in the previous frame.
all_prev = {}
with open(os.path.join(PLAY, "embeddings_ALL.jsonl")) as fh:
    for ln in fh:
        d = json.loads(ln)
        all_prev[(d["seq"], d["frame"], d["tile"])] = np.array(d["embedding"], dtype=np.float64)

skipped = [(name, fi, ti) for name, frames in SEQS.items()
           for fi in range(1, len(frames)) for ti in range(16)
           if diffs[(name, fi, ti)] <= THRESHOLD]
rng = np.random.default_rng(20261101)
idx = rng.choice(len(skipped), size=min(60, len(skipped)), replace=False)
sample = [skipped[i] for i in sorted(idx)]
drifts = []
t0 = time.perf_counter()
with open(os.path.join(PLAY, "embeddings_AUDIT.jsonl"), "w") as fout:
    for (name, fi, ti) in sample:
        emb, _ = embed(name, fi, ti, count=False)
        cur = np.array(emb, dtype=np.float64)
        prev = all_prev[(name, fi - 1, ti)]
        cos = float(cur @ prev / (np.linalg.norm(cur) * np.linalg.norm(prev)))
        drift = 1.0 - cos
        drifts.append(drift)
        record_line(fout, name, fi, ti, emb, {"prev_cos_drift": round(drift, 6)})
log(f"audit: {len(sample)} skipped tiles embedded anyway in {time.perf_counter()-t0:.1f}s; "
    f"prev-frame cosine drift: mean={np.mean(drifts):.4f} p50={np.percentile(drifts,50):.4f} "
    f"p95={np.percentile(drifts,95):.4f} max={np.max(drifts):.4f}")
skipped_diff = np.array([diffs[k] for k in skipped]) if skipped else np.array([0.0])
log(f"skipped tiles: {len(skipped)} total; their diff scores: mean={skipped_diff.mean():.3f} max={skipped_diff.max():.3f}")

lat = np.array(latencies) if latencies else np.array([0.0])
summary = {
    "threshold_rule": "pooled median of all tile diffs",
    "threshold": THRESHOLD,
    "rack_embed_latency_s_excl_first_load": {
        "n": int(len(lat)), "p50": float(np.percentile(lat, 50)),
        "p95": float(np.percentile(lat, 95)), "mean": float(lat.mean())},
    "strategy_ALL": {"embeds": n_all, "wall_s": wall_all},
    "strategy_CHANGED": {"embeds": n_chg, "wall_s": wall_chg},
    "audit": {"n": len(sample),
              "drift_mean": float(np.mean(drifts)), "drift_p50": float(np.percentile(drifts, 50)),
              "drift_p95": float(np.percentile(drifts, 95)), "drift_max": float(np.max(drifts))},
    "skipped_total": len(skipped),
}
with open(os.path.join(PLAY, "driver_summary.json"), "w") as fh:
    json.dump(summary, fh, indent=2)
log("summary written: " + json.dumps(summary))
with open(os.path.join(PLAY, "driver.log"), "w") as fh:
    fh.write("\n".join(log_lines) + "\n")
