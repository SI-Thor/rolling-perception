# W3-DRIVER results — real frames, real I-JEPA, ALL vs CHANGED

Run: 2026-11-01 on the Thor. Service lifecycle (this lane only):
jev-rack was **inactive** at start (GPU 8% ambient, 43 °C, 68 GB RAM free);
started 15:18:24 AKST (`sudo -n systemctl start jev-rack`), /health OK in
~2 s; first /embed/image call triggered the I-JEPA lazy load and took
**11.9 s**; rack stopped 15:24:35, verified `is-active = inactive`,
GPU util 1%, health endpoint down. Nothing else on the box was touched.

## Material (ground truth in GROUND_TRUTH.md)
- A_burst: burst_1792818193_b512cd f00–f11, 12× 512×512, one scene, no cuts by construction.
- B_turntable: dock-turntable.webp frames 0–11, centre-cropped/resized to 512×512, rotating dock, no cuts.
- C_cuts: A/B interleaved, 12 frames, all 11 boundaries are known scene cuts.
Each frame tiled 4×4 (128×128 crops, saved only in the Thor play dir).

## Measured
- Rack embed latency (887 strategy calls, excl. first load): **p50 173 ms, p95 200 ms, mean 182 ms** per 128×128 crop.
- Diff distribution (528 tile-steps, 0–255 mean-abs): min 3.4, p50 50.1, p95 101.8, max 147.9.
  Threshold (pre-stated rule: pooled median) = **50.06**.
- Strategy ALL: **576 embeds, 119.6 s wall.** Strategy CHANGED: **312 embeds, 55.0 s wall** (−45.8% calls, −54% time).
- Per sequence under CHANGED: A 132/192 embedded, B **23/192**, C **157/192** — the gate behaves
  as ground truth says it should: turntable (mean diff 25.9) is mostly skipped, cuts (mean diff 66.4)
  are mostly embedded.

## Audit — were skipped tiles truly low-change?
60 skipped tiles (seeded sample) embedded anyway, drift vs ALL's previous-frame
embedding of the same tile: **mean 0.202, p50 0.145, p95 0.535** (1−cosine).
Cross-check from ALL data directly: skipped-band drift mean 0.203 vs
embedded-band drift mean **0.484** — the audit sample and the full-data
computation agree, and pixel-diff does rank tiles by embedding drift (~2.4×).

**Honest caveat (the finding, not a footnote):** the separation is weak.
Skipped tiles still drift 0.20 on average — they are *less* changed, not
*unchanged*. Root cause is in the material: these generated "burst" frames
are not near-duplicates — sequence A's mean tile diff is 63.9/255 (each
burst frame is a fresh generation with large global variation), so no
pixel threshold yields a clean changed/unchanged split here. On genuinely
gradual material (B), the gate saves 88% of embeds; on cut-heavy material
(C) it correctly spends 82%. CHANGED is a ranker with a budget knob, not
a change detector — downstream work should treat it that way.

## Files (this folder)
`embeddings_ALL.jsonl` (576), `embeddings_CHANGED.jsonl` (312),
`embeddings_AUDIT.jsonl` (60), `driver_summary.json`, `driver.log`,
`driver.py`, `SCHEMA.md`, `GROUND_TRUTH.md`. Schema per SCHEMA.md;
`t_arrival_us` is a modelled 30 fps label, not a measured capture time.
