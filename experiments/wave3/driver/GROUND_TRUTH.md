# Ground truth — wave 3 frame material (all on the Thor)

## Sequence A_burst — gradual, no cuts
- Source: `~/image-studio/outputs/burst_1792818193_b512cd_f00.png` … `_f11.png`
- 12 frames, 512×512 RGB, one generated scene in a sequential burst
  (f00→f11 is frame order). Ground truth: **same scene throughout, gradual
  change only, zero scene cuts.** (The longest burst on the box; all other
  bursts are 5 frames.)

## Sequence B_turntable — gradual motion, no cuts
- Source: `~/sitka-distill/showcase/dock-turntable.webp` (animated, 20
  frames, 540×960). Frames 0–11 extracted with PIL, centre-cropped to
  540×540 and resized to 512×512 so tiling/diff geometry matches A.
- Ground truth: **one scene (dock model) rotating on a turntable —
  continuous gradual motion, zero scene cuts.**

## Sequence C_cuts — known scene cuts at every boundary
- Constructed by interleaving the processed frames of A and B:
  `A0, B0, A1, B1, … A5, B5` (12 frames).
- Ground truth: **every frame boundary (11 of 11) is a scene cut**;
  even-indexed frames are scene A, odd-indexed frames are scene B.
  Expected signal: diff scores should be large on (nearly) all tiles at
  every step, and CHANGED should embed almost everything — if it doesn't,
  the threshold/perceive stage is wrong, not the data.

## Tiles
Every frame is tiled into a 4×4 grid of 128×128 crops (tile = row*4+col).
Crops are saved only under the Thor play dir (`~/rolling-perception-play/wave3/crops/`).
