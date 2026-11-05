#!/usr/bin/env python3
"""Console regression tests — the watcher's verdict rows must surface.

Builds a fixture ledger holding the REAL verdict row shape the
watcher writes (slice1/core/src/ledger.rs: kind "verdict",
changed_tiles, per-tile objects in `tiles`, microsecond
wall_us/t_capture_us), the spec frame-verdict shape, and wave-3
per-tile rows, then asserts /api/state surfaces all of them and
/api/correct validates. Run: python3 test_console.py (needs
fastapi + httpx for TestClient; exits non-zero on failure).
"""
import json, os, sys, tempfile, time
from pathlib import Path

ROOT = Path(tempfile.mkdtemp(prefix="console-test-"))
LED = ROOT / "ledger"; MED = ROOT / "media"
CAM = LED / "streams" / "cam1"; CAM.mkdir(parents=True); MED.mkdir(parents=True)
os.environ["CONSOLE_LEDGER_DIR"] = str(LED)
os.environ["CONSOLE_MEDIA_DIR"] = str(MED)
sys.path.insert(0, str(Path(__file__).resolve().parent))

WALL = 1793599681553389        # a real-shaped microsecond epoch
CAP = WALL - 1540476


def tile_objs(changed):
    return [{"tile": t, "raw": 0.5, "smoothed": 0.5,
             "changed": t in changed, "stale": False, "lineage_mask": 31}
            for t in range(16)]


def verdict(frame, changed, wall, cap):
    return {"kind": "verdict", "stream": "cam1", "frame": frame,
            "wall_us": wall, "t_capture_us": cap, "verdict_latency_ms": 1540.476,
            "changed_tiles": changed, "focus": changed[:4], "lineage_mask": 31,
            "stage_ms": {"perceive_decide": 900.0, "direct": 1.0,
                         "refine": 2.0, "publish": 0.5},
            "embeds_this_frame": len(changed), "energy_before": 12.0,
            "energy_after": 3.0, "tiles": tile_objs(changed)}


rows = [
    {"kind": "service", "event": "start", "msg": "watcher up", "wall_us": WALL - 10**7},
    verdict(4, list(range(16)), WALL, CAP),                    # the cut
    verdict(7, [5, 6], WALL + 5_000_000, CAP + 5_000_000),     # the object
    {"frame": 10, "tile": 1, "changed": True, "smoothed_score": 0.42},
    {"frame": 10, "tile": 2, "changed": True, "smoothed_score": 0.51},
    {"frame": 10, "tile": 3, "changed": False, "smoothed_score": 0.01},
    {"tick": 12, "tiles": [5, 6, 9, 10], "score": 0.71, "sheaf_energy": 1.83,
     "jev_p": 0.12, "line": "Change in the centre of the frame"},
]
(CAM / "events.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
(CAM / "lens.txt").write_text("budget_embed_seconds = 600\n")
(CAM / "state.txt").write_text("state = test\ncoverage = 1.0000\n")
(CAM / "health.txt").write_text(f"heartbeat_ts = {time.time():.0f}\n")

from fastapi.testclient import TestClient  # noqa: E402
import app as console_app  # noqa: E402

client = TestClient(console_app.app)
fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  {extra}" if extra and not cond else ""))
    if not cond:
        fails.append(name)


st = client.get("/api/state")
check("GET /api/state 200", st.status_code == 200)
body = st.json()
streams = {s["id"]: s for s in body["streams"]}
check("cam1 reports 4 events", streams.get("cam1", {}).get("events") == 4,
      f"got {streams.get('cam1')}")
feed = {(e["stream"], e["frame"]): e for e in body["feed"]}

cut = feed.get(("cam1", 4), {})
check("cut verdict surfaces", bool(cut))
check("cut tiles = all 16", cut.get("tiles") == list(range(16)), f"got {cut.get('tiles')}")
check("cut line synthesised", cut.get("line") == "Whole scene changed", f"got {cut.get('line')}")
check("cut ts from t_capture_us", abs((cut.get("ts") or 0) - CAP / 1e6) < 1e-3,
      f"got {cut.get('ts')} want {CAP / 1e6}")
check("cut kind = verdict", cut.get("kind") == "verdict")

obj = feed.get(("cam1", 7), {})
check("object verdict surfaces with tiles {5,6}", obj.get("tiles") == [5, 6],
      f"got {obj.get('tiles')}")
check("object line names the centre", obj.get("line") == "Change in the centre of the frame",
      f"got {obj.get('line')}")

w3 = feed.get(("cam1", 10), {})
check("wave-3 rows still group per frame", w3.get("tiles") == [1, 2], f"got {w3.get('tiles')}")
spec = feed.get(("cam1", 12), {})
check("spec frame verdict still surfaces", spec.get("tiles") == [5, 6, 9, 10],
      f"got {spec.get('tiles')}")
check("service rows do not surface", all(e["kind"] != "service" for e in body["feed"]))

bad = client.post("/api/correct", json={"stream": "cam1", "event_id": "cam1:999"})
check("unknown event_id -> 400", bad.status_code == 400, f"got {bad.status_code}")
ghost = client.post("/api/correct", json={"stream": "nope", "event_id": "nope:1"})
check("unknown stream -> 400", ghost.status_code == 400, f"got {ghost.status_code}")
malformed = client.post("/api/correct", content="{not json",
                        headers={"content-type": "application/json"})
check("malformed JSON -> 400 (not 500)", malformed.status_code == 400,
      f"got {malformed.status_code}")
ok = client.post("/api/correct", json={"stream": "cam1", "event_id": "cam1:4"})
check("known event_id -> 200", ok.status_code == 200, f"got {ok.status_code}")
corr = LED / "attention" / "corrections.jsonl"
check("correction appended", corr.exists() and "cam1:4" in corr.read_text())

# The mattered tap: the confirmation side of the ground-truth labels
# (SPEC §C; the trust roll-up's other citizen).
mat = client.post("/api/correct", json={"stream": "cam1", "event_id": "cam1:7",
                                        "correction": "mattered"})
check("mattered tap -> 200", mat.status_code == 200, f"got {mat.status_code}")
check("mattered recorded with its value",
      '"correction": "mattered"' in corr.read_text() and "cam1:7" in corr.read_text())
bad_val = client.post("/api/correct", json={"stream": "cam1", "event_id": "cam1:4",
                                            "correction": "bogus"})
check("correction value outside the two labels -> 400", bad_val.status_code == 400,
      f"got {bad_val.status_code}")

# The trust pass over the console's own fixture ledger.
import trust  # noqa: E402
t = trust.evaluate_stream(LED, "cam1")
check("trust pass runs on this ledger (2 taps, 1 of each -> n=2)",
      t["n"] == 2 and t["m"] == 1 and t["d"] == 1 and t["status"] == "insufficient",
      f"got {t}")
check("trust pass wrote trust-state.json",
      (LED / "attention" / "trust-state.json").exists())

print(f"\n{len(fails)} failure(s)" if fails else "\nALL PASS")
sys.exit(1 if fails else 0)
