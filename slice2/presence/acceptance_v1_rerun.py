#!/usr/bin/env python3
"""Slice-2 presence acceptance — no human throat required.

A spoken question is synthesised with Piper ("What changed at the
camera today?"), POSTed through /hear against a fixture ledger with
one known staged event, and three things are verified with numbers:
  1. transcript ~= the question (word overlap)
  2. the reply references the staged event's content ("toolbox")
  3. the reply audio is a non-silent WAV of plausible duration
Plus: GET / = 200 carrying the live-indicator marker.

The Thor's live llama-servers (:8295/:8296) are decision models with
no text generation, and :8001 is down — so this script starts a
TEMPORARY text brain (llama-server + the on-disk LFM2-1.2B GGUF) on
:8301, and kills it afterwards. Casey's tenants are never touched.
Run on the Thor from ~/confluence-play/slice2/ with the ml venv python.
"""
import base64
import io
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
import wave
from pathlib import Path

import numpy as np

HOME = Path.home()
PLAY = HOME / "confluence-play/slice2"
FIXTURE = PLAY / "fixture-ledger-v1rerun"
APP_DIR = PLAY / "app-v2"
PORT = 8332
BRAIN_PORT = 8312
QUESTION = "What changed at the camera today?"
STAGED_LINE = "A red toolbox appeared beside the dock door"
PIPER = HOME / "radio-room-thor/.venv/bin/piper"
VOICE = HOME / "radio-room-thor/voices/en_US-lessac-medium.onnx"
LLAMA = HOME / "llama.cpp-upstream/build-up/bin/llama-server"
MODEL = HOME / "models/LFM2-1.2B/LFM2-1.2B-Q8_0.gguf"

procs = []


def wait_health(url, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status == 200:
                    return round(time.time() - t0, 1)
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"no health at {url}")


def build_fixture():
    sdir = FIXTURE / "streams/dock-cam"
    sdir.mkdir(parents=True, exist_ok=True)
    (FIXTURE / "items").mkdir(parents=True, exist_ok=True)
    rows = [
        {"frame": 40, "tile": 5, "raw_score": 0.42, "changed": True,
         "lineage_mask": 31},
        {"tick": 41, "tiles": [5, 6], "score": 0.81, "jev_p": 0.1,
         "line": STAGED_LINE},
    ]
    (sdir / "events.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")
    (sdir / "state.txt").write_text(
        "state = dock: quiet since the toolbox\nembeds_spent = 41\n"
        "coverage = 0.88\n")
    (sdir / "health.txt").write_text(
        f"heartbeat_ts = {int(time.time())}\nembed_p50_ms = 181\n"
        "queue_depth = 0\n")
    (FIXTURE / "items/A00.txt").write_text(
        "Sitka harbour at dawn — photograph\n")


def main():
    results = {}
    build_fixture()

    # temporary text brain (Casey's decision-model tenants untouched)
    brain = subprocess.Popen(
        [str(LLAMA), "-m", str(MODEL), "--host", "127.0.0.1",
         "--port", str(BRAIN_PORT), "-ngl", "99", "--ctx-size", "4096",
         "--alias", "presence-test-brain"],
        stdout=open(PLAY / "brain.log", "w"),
        stderr=subprocess.STDOUT)
    procs.append(brain)
    results["brain_startup_s"] = wait_health(
        f"http://127.0.0.1:{BRAIN_PORT}/health")

    # synthesise the question with Piper (the acceptance throat)
    q_wav = PLAY / "question.wav"
    subprocess.run([str(PIPER), "--model", str(VOICE),
                    "--output_file", str(q_wav)],
                   input=QUESTION.encode(), check=True,
                   capture_output=True)

    env = dict(os.environ,
               LEDGER_DIR=str(FIXTURE),
               BRAIN_URL=f"http://127.0.0.1:{BRAIN_PORT}",
               PRESENCE_PORT=str(PORT),
               RECEIPTS_LOG=str(PLAY / "receipts-v1rerun.jsonl"))
    backend = subprocess.Popen(
        [str(HOME / "ml/.venv/bin/python"), str(APP_DIR / "presence.py")],
        env=env, stdout=open(PLAY / "backend.log", "w"),
        stderr=subprocess.STDOUT)
    procs.append(backend)
    wait_health(f"http://127.0.0.1:{PORT}/health")

    # 0. page: 200 + live indicator marker
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/") as r:
        page = r.read().decode()
        results["page_status"] = r.status
    results["page_has_live_indicator"] = "presence-live-indicator" in page

    # the voice loop
    boundary = "----presenceacceptance"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; "
            f"name=\"audio\"; filename=\"question.wav\"\r\n"
            f"Content-Type: audio/wav\r\n\r\n").encode() \
        + q_wav.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/hear", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.loads(r.read())
    results["hear_wall_s"] = round(time.perf_counter() - t0, 2)
    results["transcript"] = out["transcript"]
    results["reply_text"] = out["reply_text"]
    results["timings_ms"] = out["timings_ms"]
    results["audio_stats"] = out["reply_audio_stats"]

    q_words = set(QUESTION.lower().strip("?").split())
    t_words = set(out["transcript"].lower().strip("?").split())
    results["transcript_word_overlap"] = round(
        len(q_words & t_words) / len(q_words), 2)
    results["reply_mentions_staged_event"] = \
        "toolbox" in out["reply_text"].lower()

    raw = base64.b64decode(out["reply_audio_b64"])
    with wave.open(io.BytesIO(raw)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()),
                          dtype=np.int16).astype(np.float32) / 32768.0
    results["audio_rms_check"] = round(
        float(np.sqrt(np.mean(a ** 2))), 4) if a.size else 0.0

    results["PASS"] = bool(
        results["page_status"] == 200
        and results["page_has_live_indicator"]
        and results["transcript_word_overlap"] >= 0.75
        and results["reply_mentions_staged_event"]
        and 0.8 <= out["reply_audio_stats"]["duration_s"] <= 20
        and results["audio_rms_check"] >= 0.01)
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    try:
        main()
    finally:
        for p in procs:
            try:
                p.send_signal(signal.SIGTERM)
                p.wait(timeout=10)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        print("cleanup: backend + temp brain stopped", file=sys.stderr)
