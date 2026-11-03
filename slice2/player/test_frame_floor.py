#!/usr/bin/env python3
"""Frame-floor tests for player.py (POLISH-BACKLOG blocker 3).

Blocker 3 was two coupled defects, both reproduced against the
pre-fix code before the fix landed:

  A. exit-0 + any segment = ready: an instantly-EOSing source with
     an EMPTY segment finished "ready" with 0 frames (first
     recorded as the VP9 wart in RESULTS.md).
  B. the stall watchdog was transcode-only: a hung remux/fMP4
     worker (alive, no output) stayed "running" forever, and
     start_session's reuse rule handed that zombie to every later
     request for the item.

The floor, as tested here: ready requires >= 1 counted frame
(exit case -> failed/no_frames); a live worker with zero frames
past FIRST_FRAME_S is killed (live case -> failed/no_first_frame);
a failed session releases its item (a later request starts fresh)
and releases /play waiters with the failure.

Workers are fake: small python scripts standing in for the
GStreamer pipelines, writing (or not writing) playlist/segment
files into the session dir — the same files supervise() counts.
The "real" segment is a genuine ffmpeg-made H.264 TS, so frame
counts come from player.count_frames (ffprobe packet counting),
not from a stub.

Run:  python3 test_frame_floor.py        (needs fastapi + ffmpeg)
The window is shrunk to 3 s via PLAYER_FIRST_FRAME_S (the player's
own env config); production default is 10 s.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(tempfile.mkdtemp(prefix="player-frame-floor-"))
os.environ["PLAYER_MEDIA_DIR"] = str(ROOT / "media")
os.environ["PLAYER_WORK_DIR"] = str(ROOT / "work")
os.environ["PLAYER_LEDGER_DIR"] = str(ROOT / "ledger")
os.environ["PLAYER_FIRST_FRAME_S"] = "3.0"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import player  # noqa: E402  (import starts the supervise thread)

WINDOW = 3.0

# A real H.264 TS segment: 1 s of testsrc at 10 fps (~10 packets).
REAL_SEG = ROOT / "real-seg.ts"
subprocess.run(
    ["ffmpeg", "-v", "error", "-f", "lavfi",
     "-i", "testsrc=duration=1:size=320x240:rate=10",
     "-c:v", "libx264", "-pix_fmt", "yuv420p", "-f", "mpegts",
     str(REAL_SEG)], check=True)
REAL_FRAMES = player.count_frames(REAL_SEG)
assert REAL_FRAMES and REAL_FRAMES >= 1, "fixture segment must have frames"

EMPTY_SETUP = (
    "import sys,pathlib; d=pathlib.Path(sys.argv[1]);"
    " (d/'playlist.m3u8').write_text('#EXTM3U\\nseg00000.ts\\n');"
    " (d/'seg00000.ts').write_bytes(b'');"
)
COPY_REAL = (
    " import shutil; shutil.copy(sys.argv[2],"
    " str(pathlib.Path(sys.argv[1])/'seg00000.ts'));"
)
WORKERS = {
    # playlist + empty segment, exit 0 (defect A's shape)
    "empty_eos": EMPTY_SETUP,
    # playlist + empty segment, then hang forever (defect B's shape)
    "hung": EMPTY_SETUP + " import time; time.sleep(3600);",
    # playlist + real segment, exit 0 (healthy)
    "healthy": EMPTY_SETUP + COPY_REAL,
    # empty segment, real segment lands at 2 s — inside the 3 s
    # window, near its edge — then exit 0 (slow but alive)
    "slow": EMPTY_SETUP + " import time; time.sleep(2.0);" + COPY_REAL,
    # hangs writing nothing at all (fMP4 zombie shape)
    "hung_silent": "import time; time.sleep(3600);",
}


def make_item(iid, mode):
    return {"id": iid, "src": iid + ".mp4", "mode": mode,
            "probe": {"codec": "h264", "width": 1280, "height": 720,
                      "fps": 30.0, "duration": 1.0}}


def use_worker(name):
    body = WORKERS[name]
    player.build_cmd = lambda it, sdir: [sys.executable, "-c", body,
                                         str(sdir), str(REAL_SEG)]


def wait_status(s, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        if s.status not in ("starting", "running"):
            return s.status
        time.sleep(0.1)
    return s.status


def registry_rows(sid):
    return [r for r in player.read_registry() if r.get("session") == sid]


class FrameFloor(unittest.TestCase):
    def tearDown(self):
        player._shutdown()
        with player.SES_LOCK:
            player.SESSIONS.clear()

    # -- defect A: exit 0, playlist, zero frames --------------------

    def test_empty_eos_transcode_fails_no_frames(self):
        """The recorded VP9 wart, in its original transcode shape."""
        use_worker("empty_eos")
        s, _ = player.start_session(make_item("t-eos-transcode", "transcode"))
        self.assertEqual(wait_status(s), "failed")
        self.assertEqual(s.reason, "no_frames")
        self.assertEqual(s.frames, 0)
        rows = registry_rows(s.id)
        self.assertTrue(any(r["event"] == "failed" and r.get("reason") == "no_frames"
                            for r in rows), rows)

    def test_empty_eos_remux_fails_no_frames(self):
        use_worker("empty_eos")
        s, _ = player.start_session(make_item("t-eos-remux", "remux"))
        self.assertEqual(wait_status(s), "failed")
        self.assertEqual(s.reason, "no_frames")
        self.assertEqual(s.frames, 0)

    # -- defect B: hung worker, zero frames, past the window --------

    def test_hung_remux_fails_no_first_frame_and_releases_item(self):
        use_worker("hung")
        s, _ = player.start_session(make_item("t-hung-remux", "remux"))
        t0 = time.time()
        self.assertEqual(wait_status(s, timeout=WINDOW + 10), "failed")
        elapsed = time.time() - t0
        self.assertEqual(s.reason, "no_first_frame")
        self.assertLess(elapsed, WINDOW + 5,
                        "failure must land in bounded time, near the window")
        self.assertIsNotNone(s.proc.poll(), "zombie worker must be killed")
        rows = registry_rows(s.id)
        self.assertTrue(any(r["event"] == "failed"
                            and r.get("reason") == "no_first_frame"
                            for r in rows), rows)
        # the reuse rule no longer traps the item: a later request
        # starts a FRESH session instead of inheriting the zombie
        s2, created = player.start_session(make_item("t-hung-remux", "remux"))
        self.assertTrue(created)
        self.assertNotEqual(s2.id, s.id)

    def test_hung_fmp4_fails_no_first_frame(self):
        use_worker("hung_silent")
        s, _ = player.start_session(make_item("t-hung-fmp4", "fmp4"))
        self.assertEqual(wait_status(s, timeout=WINDOW + 10), "failed")
        self.assertEqual(s.reason, "no_first_frame")
        self.assertIsNotNone(s.proc.poll(), "zombie worker must be killed")

    # -- the healthy paths are unchanged ----------------------------

    def test_healthy_remux_ready_with_frames(self):
        use_worker("healthy")
        s, _ = player.start_session(make_item("t-healthy", "remux"))
        self.assertEqual(wait_status(s), "ready")
        self.assertEqual(s.frames, REAL_FRAMES)
        rows = registry_rows(s.id)
        self.assertTrue(any(r["event"] == "stop" and r.get("frames") == REAL_FRAMES
                            for r in rows), rows)

    def test_slow_but_alive_within_window_succeeds(self):
        """First frame at 2.0 s of a 3.0 s window: slow, not zombie."""
        use_worker("slow")
        s, _ = player.start_session(make_item("t-slow", "remux"))
        self.assertEqual(wait_status(s), "ready")
        self.assertEqual(s.frames, REAL_FRAMES)

    # -- the waiting consumer is released with the failure ----------

    def test_play_consumer_released_on_zombie(self):
        use_worker("hung")
        it = make_item("t-play-zombie", "remux")
        orig = player.find_item
        player.find_item = lambda iid: it if iid == it["id"] else None
        try:
            t0 = time.time()
            resp = player.play(it["id"])
            elapsed = time.time() - t0
        finally:
            player.find_item = orig
        self.assertEqual(resp.status_code, 502)
        self.assertIn("no_first_frame", resp.body.decode())
        self.assertLess(elapsed, 30,
                        "/play must be released by the failure, not its 90 s deadline")


if __name__ == "__main__":
    unittest.main(verbosity=2)
