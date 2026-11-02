# 2026-11-01 — Thor CUDA play session (summary entry)

Canonical full text: `experiments/thor-cuda/PLAYLOG.md` — read it
there; this file is the results-index pointer, not a copy.

- **Machine:** thor (AGX Thor, sm_110), CUDA 13.2, driver 595.78.
  GPU idle at start (0%, 37 °C); all experiments single-shot, stopped.
- **Headline results:**
  - exp1 rolling vs batched: first output **5.74 vs 21.41 ms (3.7×)**,
    outputs as a staircase at max(stagger, kernel-time); total
    completion unchanged.
  - exp2 NVRTC swap: compile 54.4 / 29.6 ms off-path, launch-time swap,
    outputs verified (6.0 → 12.0).
  - exp3 persistent kernel: 300 requests / one launch via pinned
    mapped memory, **mean request→ack 4.8 µs, p95 5.5 µs**, mid-run
    behaviour swap exact, clean flag stop.
  - exp4 gating: early-exit blocks 1.3×; launch-shaped ROI grid
    **192×** (0.006 vs 1.08 ms), sentinel-verified zero outside touches.
- **Rig bug recorded in PLAYLOG:** first bench timestamped host
  observation time, bunching all outputs at ~20 ms; caught because two
  work sizes gave identical numbers; fixed with CUDA event timestamps.
