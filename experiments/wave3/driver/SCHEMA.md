# Embedding JSONL schema — wave 3 driver output

One JSON object per line, one line per tile-embedding actually produced by
a rack call. Files: `embeddings_ALL.jsonl`, `embeddings_CHANGED.jsonl`,
`embeddings_AUDIT.jsonl` (audit lines are a separate measurement pass and
are never counted in strategy totals).

| Field | Type | Meaning |
|---|---|---|
| `seq` | string | Sequence id: `A_burst`, `B_turntable`, `C_cuts` (see GROUND_TRUTH.md). |
| `frame` | int | Frame index within the sequence, 0-based. |
| `tile` | int | Tile index in a 4×4 grid, row-major: `tile = row*4 + col`, 0–15. |
| `t_arrival_us` | int | **Modelled** camera arrival time: `frame * 33333` µs (a nominal 30 fps cadence). This is a label for downstream scheduling experiments — it is NOT a measured capture time; the source frames are files, not a live camera. |
| `diff_score` | float | Cheap-perceive score for this tile: mean absolute pixel difference (0–255 scale, computed in float32 on the 128×128 tile) between this frame's tile and the previous frame's same tile. Frame 0 of each sequence is defined as `diff_score = 255.0` (no predecessor — always embedded). |
| `embedding` | float[1280] | I-JEPA ViT-H/14 embedding from the Thor's jev-rack (`POST /embed/image`), mean over patch tokens, as returned by the rack (6-decimal rounding). |

Strategy definitions (both run for real against the rack):

- **ALL** — every tile of every frame is embedded (16 × frames calls).
- **CHANGED** — frame 0 fully embedded; for later frames, a tile is
  embedded only if `diff_score > THRESHOLD` (threshold calibrated from the
  pooled diff distribution of all sequences before any embedding; the
  value and rule are recorded in the run log and RESULTS).

AUDIT lines carry one extra field, `prev_cos_drift`: `1 − cosine` between
this tile's audit embedding and strategy ALL's embedding of the same tile
in the previous frame — i.e. how much the embedding actually moved on
tiles CHANGED chose to skip.
