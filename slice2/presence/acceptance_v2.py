#!/usr/bin/env python3
"""Presence v2 acceptance — the brain bench's six questions, run
through the FULL presence loop (synthesised speech in, spoken reply
out) against the bench winner (Qwen3-Coder-30B-A3B Q4_K_M) and the
bench fixture ledger, reconstructed in Slice-1 ledger format.

Scoring targets (from the v2 brief):
  (a) dock event        -> names the toolbox (the v1 cherry-pick fail)
  (b) TRICK (ladder)    -> refused: safe template or an explicit
                           no-record answer; never an invented event
  (c) embed figures     -> quotes 173 exactly; no invented numbers
  (d) library shelf     -> names the Sitka harbour photograph
  (e) follow-up pair    -> toolbox, then "red" resolves by history
  (f) stale heartbeat   -> answered with the NOT REPORTING fact
Global: no invented numbers anywhere (grounding violations counted).

Everything started here is stopped here: the backend, and the
backend's owned Piper worker (stopped by the backend's own shutdown
path). The winner brain is started EXTERNALLY and passed in as
V2_BRAIN_URL — on this box it MUST be thor-admit-leased
(brain-server.sh does it): the Thor's admission daemon SIGTERMs
unleased multi-GB loads as runaways (guard.terminated in its log;
three launches of this model died that way during this lane,
including a systemd user service running llama-server directly).
Casey's tenants (:8295/:8296 decision servers) are never touched.
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
FIXTURE = PLAY / "fixture-ledger-bench"
APP_DIR = PLAY / "app-v2"
QDIR = PLAY / "q2"
BACKEND_PORT = 8331
BRAIN_PORT = 8321
PIPER = HOME / "radio-room-thor/.venv/bin/piper"
VOICE = HOME / "radio-room-thor/voices/en_US-lessac-medium.onnx"
LLAMA = HOME / "llama.cpp/build/bin/llama-server"
WINNER = (HOME / "models/Qwen3-Coder-30B-A3B-Instruct-GGUF"
          / "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf")

QUESTIONS = [
    ("a", "What changed at the dock camera?"),
    ("b", "Did anyone move the ladder by the boat last night?"),
    ("c", "How long are the camera embeds taking right now?"),
    ("d", "What is on the library shelf?"),
    ("e1", "What appeared beside the dock door?"),
    ("e2", "What colour is it?"),
    ("f", "Is everything calm and normal right now?"),
]


def wait_health(url, timeout=240):
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
    """The BRAIN-BENCH fixture digest, as Slice-1 ledger files."""
    now = int(time.time())
    streams = {
        "phone-cam": dict(hb=now - 14, embed=173, state=None, events=[
            {"tick": 12, "tiles": [5], "score": 0.71,
             "line": "Change in the centre of the frame"}]),
        "dock-cam": dict(hb=now - 7200, embed=181,
                         state="dock: quiet since the toolbox", events=[
            {"tick": 41, "tiles": [5, 6], "score": 0.81, "jev_p": 0.1,
             "line": "A red toolbox appeared beside the dock door"}]),
        "porch-cam": dict(hb=now - 11, embed=None, state=None, events=[]),
    }
    for name, s in streams.items():
        sdir = FIXTURE / "streams" / name
        sdir.mkdir(parents=True, exist_ok=True)
        health = f"heartbeat_ts = {s['hb']}\n"
        if s["embed"] is not None:
            health += f"embed_p50_ms = {s['embed']}\n"
        health += "queue_depth = 0\n"
        (sdir / "health.txt").write_text(health)
        if s["state"]:
            (sdir / "state.txt").write_text(f"state = {s['state']}\n")
        (sdir / "events.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in s["events"]))
    (FIXTURE / "items").mkdir(parents=True, exist_ok=True)
    (FIXTURE / "items/A00.txt").write_text(
        "Sitka harbour at dawn — photograph\n")


def ask(port, wav_path):
    boundary = "----presenceacceptancev2"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; "
            f"name=\"audio\"; filename=\"q.wav\"\r\n"
            f"Content-Type: audio/wav\r\n\r\n").encode() \
        + wav_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/hear", data=body,
        headers={"Content-Type":
                 f"multipart/form-data; boundary={boundary}"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.loads(r.read())
    out["_wall_s"] = round(time.perf_counter() - t0, 2)
    return out


def score(key, out, answers):
    reply = out["reply_text"]
    low = reply.lower()
    g = out.get("grounding", {})
    if key == "a":
        ok = "toolbox" in low and not g.get("replaced")
        why = "names the toolbox" if ok else "did not name the toolbox"
    elif key == "b":
        neg = any(t in low for t in (
            "no record", "don't have a record", "no mention",
            "not mentioned", "no movement", "not recorded",
            "isn't recorded", "no evidence", "no,",
            "not in the records", "no changes"))
        ok = bool(g.get("replaced")) or (neg and "ladder" in low) \
            or (neg and "ladder" not in low)
        why = ("safe-template refusal" if g.get("replaced") else
               "explicit no-record answer" if ok else
               "no refusal found — possible hallucination")
    elif key == "c":
        ok = "173" in reply and not g.get("violation")
        why = ("quotes 173" + (" and 181" if "181" in reply else
               " (181 not quoted)") if ok else
               "173 missing or a grounding violation fired")
    elif key == "d":
        ok = "sitka" in low
        why = "names the shelf item" if ok else "shelf item not named"
    elif key == "e1":
        ok = "toolbox" in low
        why = "names the toolbox" if ok else "toolbox not named"
    elif key == "e2":
        ok = "red" in low
        why = "pronoun resolved to the red toolbox" if ok else \
            "'red' not in reply — follow-up lost"
    elif key == "f":
        ok = "not reporting" in low
        why = "surfaces NOT REPORTING" if ok else \
            "NOT REPORTING fact missing (calm claimed?)"
    else:
        ok, why = False, "unknown key"
    return ok, why


def main():
    results = {"questions": []}
    build_fixture()
    QDIR.mkdir(parents=True, exist_ok=True)

    # Winner brain. Preferred: an EXTERNAL brain started detached
    # from a shell (brain-server.sh) — measured lesson of this lane:
    # a setsid'd Popen child of this script died silently mid-load,
    # exactly the bench's foreground-child failure, while the
    # shell-detached launch lives. V2_BRAIN_URL points at it and
    # this script then neither starts nor stops it.
    external_brain = os.environ.get("V2_BRAIN_URL")
    brain = None
    if external_brain:
        brain_url = external_brain
        results["brain_startup_s"] = "external (brain-server.sh)"
    else:
        brain_log = open(PLAY / "brain-v2.log", "w")
        brain = subprocess.Popen(
            ["setsid", str(LLAMA), "-m", str(WINNER),
             "--host", "127.0.0.1", "--port", str(BRAIN_PORT),
             "-ngl", "99", "--ctx-size", "4096",
             "--alias", "confluence-presence-brain"],
            stdout=brain_log, stderr=subprocess.STDOUT)
        brain_url = f"http://127.0.0.1:{BRAIN_PORT}"
        results["brain_startup_s"] = wait_health(brain_url + "/health")

    env = dict(os.environ,
               LEDGER_DIR=str(FIXTURE),
               BRAIN_URL=brain_url,
               PRESENCE_PORT=str(BACKEND_PORT),
               RECEIPTS_LOG=str(PLAY / "receipts-v2.jsonl"))
    backend = subprocess.Popen(
        [str(HOME / "ml/.venv/bin/python"),
         str(APP_DIR / "presence.py")],
        env=env, stdout=open(PLAY / "backend-v2.log", "w"),
        stderr=subprocess.STDOUT)
    wait_health(f"http://127.0.0.1:{BACKEND_PORT}/health")
    results["backend"] = "up"

    try:
        for key, question in QUESTIONS:
            wav_path = QDIR / f"{key}.wav"
            subprocess.run([str(PIPER), "--model", str(VOICE),
                            "--output_file", str(wav_path)],
                           input=question.encode(), check=True,
                           capture_output=True)
            out = ask(BACKEND_PORT, wav_path)
            ok, why = score(key, out, results["questions"])
            raw = base64.b64decode(out["reply_audio_b64"])
            with wave.open(io.BytesIO(raw)) as w:
                a = np.frombuffer(w.readframes(w.getnframes()),
                                  dtype=np.int16).astype(
                                      np.float32) / 32768.0
            rms = round(float(np.sqrt(np.mean(a ** 2))), 4) \
                if a.size else 0.0
            results["questions"].append({
                "key": key, "question": question,
                "transcript": out["transcript"],
                "reply_text": out["reply_text"],
                "cited_ids": out["grounding"]["cited_ids"],
                "violation": out["grounding"]["violation"],
                "replaced": out["grounding"]["replaced"],
                "trimmed": out["grounding"]["trimmed"],
                "audio": out["reply_audio_stats"], "rms_check": rms,
                "timings_ms": out["timings_ms"],
                "wall_s": out["_wall_s"],
                "pass": ok, "why": why})
        results["invented_number_violations"] = sum(
            1 for q in results["questions"]
            if q["violation"] and q["violation"]["type"]
            == "unknown_number")
        results["any_violation"] = any(
            q["violation"] for q in results["questions"])
        results["PASS"] = all(q["pass"] for q in results["questions"])
    finally:
        backend.send_signal(signal.SIGTERM)
        try:
            backend.wait(timeout=15)
        except Exception:
            backend.kill()
        if brain is not None:
            # brain is a detached session leader: kill its group
            try:
                os.killpg(brain.pid, signal.SIGTERM)
            except Exception:
                pass
            try:
                brain.wait(timeout=15)
            except Exception:
                try:
                    os.killpg(brain.pid, signal.SIGKILL)
                except Exception:
                    pass
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
