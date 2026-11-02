#!/usr/bin/env python3
"""Build fixture ledger + media for the console test, in the SPEC
§A2.3 layout. Run ON the Thor (heartbeat stamps use local time).
Inputs beside this script: verdicts.jsonl (wave-3 per-tile rows),
frames/ (C*.png), shelf/ (images)."""
import json, shutil, sys, time
from pathlib import Path

src = Path(sys.argv[1]); root = Path(sys.argv[2])
led = root / "ledger"; med = root / "media"
cam = led / "streams" / "phone-cam"
(cam / "frames").mkdir(parents=True, exist_ok=True)
med.mkdir(parents=True, exist_ok=True)

shutil.copy(src / "verdicts.jsonl", cam / "events.jsonl")
with open(cam / "events.jsonl", "a") as f:  # one spec-shape frame verdict too
    f.write(json.dumps({"tick": 12, "tiles": [5, 6, 9, 10], "score": 0.71,
                        "sheaf_energy": 1.83, "jev_p": 0.12,
                        "line": "Change in the centre of the frame"}) + "\n")
for p in sorted((src / "frames").glob("C*.png")):
    shutil.copy(p, cam / "frames" / (p.name[1:] if p.name[1:].isdigit() else p.name))
    shutil.copy(p, cam / "frames" / p.name.replace("C", "").lstrip("0") or "0") if False else None
# frames named by frame number: C4.png -> 4.png
for p in sorted((src / "frames").glob("C*.png")):
    n = p.name[1:-4]
    shutil.copy(p, cam / "frames" / f"{int(n)}.png")
(cam / "lens.txt").write_text(
    "# phone camera lens\nbudget_embed_seconds = 600\nknob = spend freely\nperiod_ms = 1000\n")
(cam / "state.txt").write_text(
    "state = dock: person-scale change, centre tiles\nembeds_spent = 212\ncoverage = 0.94\n")
(cam / "health.txt").write_text(
    f"heartbeat_ts = {time.time():.0f}\nembed_p50_ms = 173\nembed_p99_ms = 402\nqueue_depth = 0\n")

dock = led / "streams" / "dock-cam"; dock.mkdir(parents=True, exist_ok=True)
(dock / "state.txt").write_text("state = harbour: quiet\nembeds_spent = 41\ncoverage = 0.88\n")
(dock / "health.txt").write_text(f"heartbeat_ts = {time.time() - 7200:.0f}\nembed_p50_ms = 181\n")

empty = led / "streams" / "porch-cam"; empty.mkdir(parents=True, exist_ok=True)
(empty / "lens.txt").write_text("budget_embed_seconds = 300\n")

for p in sorted((src / "shelf").iterdir()):
    if p.is_file():
        shutil.copy(p, med / p.name)
items = led / "items"; items.mkdir(parents=True, exist_ok=True)
(items / "A00.txt").write_text("title = Harbour at anchor\ntype = image\nperception = perceived\n")
print("fixtures built at", root)
