# 2026-11-01 — Thor feasibility probe (summary entry)

Canonical full text: `docs/FEASIBILITY.md` — read it there; this file
is the results-index pointer, not a copy.

- **Machine:** thor (AGX Thor, aarch64), GPU capability 11.0 (sm_110),
  20 SMs, driver 595.78, CUDA 13.2 (nvcc V13.2.86), Rust 1.99.1.
- **Headline results:** sm_110 nvcc compile+run PASS (managed vadd
  c[42]=126 ✓); NVRTC `compute_110` runtime compile PASS (PTX 562 B);
  CUPTI library+headers present (its stall metrics are ncu replay
  metrics — not a live feed); cooperativeLaunch=1,
  directManagedMemAccessFromHost=0 (→ control slots in pinned mapped
  memory, bulk tensors in managed memory).
- **Verdicts carried into the design:** persistent kernel feasible
  (soak untested); hot-swap real only at launch / per-iteration-flag
  granularity; seed's sm_100/sm_101 targets wrong for this box.
