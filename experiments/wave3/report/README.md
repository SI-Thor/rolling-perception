# Harbor Watch — human report (wave 3, W3-REPORT lane)

`make_report.py` turns the harbor-watch crate's machine output into the one
artifact a person actually opens: a single HTML file with every frame, its
changed tiles painted red on the image itself, the frame verdict, and a
header scoreboard scored against ground truth. It is pure Python 3 stdlib —
no pip installs, no JavaScript, no canvas, no external assets — so the file
renders identically offline, on a phone, or attached to a message.

```
[Thor] driver            [Thor] harbor-watch crate        [anywhere] this folder
frame capture     ──►    tile verdicts (+ strategy    ──►   make_report.py
(frames + manifest)      compare summary)                     │
ground truth JSON ────────────────────────────────────────►  └─► report.html  ◄── a human
```

## Run it end-to-end (once the real data lands)

Steps marked **[Thor]** must run on the Thor (its GPU, its JEV rack, its
cameras). Everything else runs anywhere with `python3`.

### 0. Get the code onto the Thor **[Thor]**

```bash
ssh -F ~/workspace/ssh/thor.config thor
cd ~/rolling-perception-play && git clone https://github.com/SI-Thor/rolling-perception
cd rolling-perception
export PATH=$HOME/.cargo/bin:/usr/local/cuda/bin:$PATH   # Thor quirk: neither is on the non-login PATH
```

### 1. Capture frames — the driver **[Thor]**

Run the wave-3 capture driver per its own README. Its contract with this
report is only the output folder:

```
capture/
  frame0000.png  frame0001.png  ...
  manifest.json        {"grid": [4, 4],
                        "frames": [{"frame": 0, "image": "frame0000.png"}, ...]}
```

One frame = one still, tiled 4×4 by the crate. Keep the capture timestamps:
ground truth is keyed by the same frame ids the driver emits.

### 2. Run the crate **[Thor]**

```bash
# ADAPT flags to the crate's CLI as it lands; the file contracts below are fixed.
cargo run -p harbor-watch --release -- \
  --manifest capture/manifest.json \
  --out verdicts.jsonl \
  --compare-out compare.json
```

Outputs:
- `verdicts.jsonl` — one line per tile decision:
  `{"frame": 0, "tile": 5, "changed": true, "score": 0.97}`
  (`tile` is row-major 0–15 on the 4×4 grid; `[row, col]` and `"row,col"`
  are also accepted by the report.)
- `compare.json` (optional, from the rolling-vs-batched run) —
  `{"strategies": {"rolling": {"embeds_spent": 40, "ttfv_ms": 812.0},
                   "batched": {"embeds_spent": 160, "ttfv_ms": 2910.0}}}`

### 3. Write the ground truth (anywhere)

By hand, from watching the same frames — this is the scoreboard's referee,
so it stays a human artifact:

```json
{"changed": {"0": [5, 6], "1": [], "2": [0, 1, 2, 3]},
 "scene_cuts": [2]}
```

`changed` maps each frame to the tiles that *truly* changed; `scene_cuts`
lists frames that start a new scene. Frames with no ground truth are
reported as **unscored**, never silently counted as correct.

### 4. Build and open the report (anywhere)

```bash
cd crates-or-workdir/wave3/report        # this folder
python3 make_report.py \
  --verdicts verdicts.jsonl \
  --manifest capture/manifest.json \
  --ground-truth ground_truth.json \
  --compare compare.json \
  --out report.html --title "Harbor Watch — Sitka, <date>"
# --compare is optional; omit it and the scoreboard simply has no strategy table.
open report.html        # or copy it anywhere: it is one self-contained file
```

The tool prints the headline numbers as it writes
(`precision=… recall=… tp=… fp=… fn=…`) — if those disagree with the page
you opened, you opened a stale file.

## Check the tool itself (fixtures, works anywhere)

```bash
python3 test_fixtures.py
```

It generates 3 small PNGs (needs Pillow, present on the fleet VM; the
*report tool itself* needs only stdlib), a verdict set whose confusion
counts are known by construction (TP 5 / FP 2 / FN 1), and asserts the
HTML's scoreboard equals the hand computation — precision 0.714, recall
0.833, F1 0.769 — plus 7 overlays, 3 embedded images, named missed /
false-alarm tiles, and zero external references. Open
`fixtures/report.html` to see exactly what a real report looks like.

## Schema assumptions (recorded, since the crate landed in parallel)

Verdicts are per-tile JSONL as in step 2; if the crate emits per-frame
records with a `tiles` array instead, split them into per-tile lines
before this tool — the metrics and overlays are defined per tile, and
row-major tile order over the manifest's `grid` is the shared convention
between crate, ground truth, and report.
