#!/usr/bin/env python3
"""Presence v3 acceptance — the claim checker, proven three ways.

  Part 0  unit tests: test_claims.py (adversarial sentences against
          the checker alone; stdlib, deterministic).
  Part 1  v1 rerun against the v3 code (acceptance_v1_rerun.main
          with APP_DIR patched to app-v3): the original no-throat
          test must stay green.
  Part 2  the v2 seven-question battery through the FULL voice loop
          with the winner brain (thor-admit lease via brain-server.sh,
          released after): must stay 7/7 with the claim checker live.
  Part 3  prose traps: a second backend runs with the stub-brain
          hook (PRESENCE_BRAIN_STUB_FILE) so each adversarial brain
          output from test_claims.py is FORCED through /hear. For
          every trap we assert: the response text is the corrected
          template truth, the violation is logged with the original
          sentence quoted, and the receipts line — whose "reply" is
          exactly what the TTS stage speaks — carries the corrected
          text, never the trap. Two correct claims must pass
          byte-identical with zero claim violations.

Fixture discipline: the bench fixture is REBUILT immediately before
Part 3 and that backend runs with STALE_TOLERANCE_S=3600, so stream
freshness cannot drift mid-part (dock-cam at 7200 s stays stale;
phone/porch stay fresh). Casey's tenants and the Slice-1 soak are
never touched. Run on the Thor from ~/confluence-play/slice2/ with
the ml venv python; deploy = this directory (app-v3).
"""
import contextlib
import io
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import acceptance_v1_rerun as v1  # noqa: E402
import acceptance_v2 as v2  # noqa: E402

HOME = Path.home()
PLAY = HOME / "confluence-play/slice2"
APP_DIR = PLAY / "app-v3"
QDIR = PLAY / "q3"
PIPER = HOME / "radio-room-thor/.venv/bin/piper"
VOICE = HOME / "radio-room-thor/voices/en_US-lessac-medium.onnx"
BRAIN_PORT = 8321
BATTERY_PORT = 8331
TRAP_PORT = 8333
SAFE = "I don't have a record of that."

# (stubbed brain output, expected reply, expected violation type,
#  exact?) — the two dock-truth traps assert a PREFIX because the
# digest humanises the 7200 s heartbeat as "2 hours ago" only at
# exactly 7200 s (later: "2.0 hours ago"); the unit tests pin the
# exact template strings against fixed meta. DOCK_PREFIX must also
# be followed by "hours ago." in the reply.
DOCK_PREFIX = "The dock-cam is not reporting — last heartbeat "
TRAPS = [
    ("The porch-cam is not reporting.",
     "The porch-cam is reporting normally.", "false_stale_claim",
     True),
    ("Dock-cam-41 is not reporting.", SAFE, "event_id_as_stream",
     True),
    ("The phone-cam is not reporting.",
     "The phone-cam is reporting normally.", "false_stale_claim",
     True),
    ("The dock-cam is reporting normally.", DOCK_PREFIX,
     "false_healthy_claim", False),
    ("The phone-cam-12 camera is down.", SAFE, "event_id_as_stream",
     True),
    ("[porch-cam] shows no changes reported.", SAFE,
     "stream_name_as_event", True),
    ("The garage-cam is not reporting.", SAFE, "unknown_stream",
     True),
    ("Everything is calm and normal right now.", DOCK_PREFIX,
     "false_calm", False),
]
CONTROLS = [
    "The dock-cam is not reporting.",
    "A red toolbox appeared beside the dock door [dock-cam-41].",
]


def wait_health(url, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status == 200:
                    return round(time.time() - t0, 1)
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"no health at {url}")


def start_backend(port, env_extra, logname):
    env = dict(os.environ, PRESENCE_PORT=str(port), **env_extra)
    proc = subprocess.Popen(
        [str(HOME / "ml/.venv/bin/python"), str(APP_DIR / "presence.py")],
        env=env, stdout=open(PLAY / logname, "w"),
        stderr=subprocess.STDOUT)
    wait_health(f"http://127.0.0.1:{port}/health", timeout=180)
    return proc


def stop(proc):
    if proc is None:
        return
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=20)
    except Exception:
        proc.kill()


def port_free(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def last_receipt(path):
    lines = Path(path).read_text().splitlines()
    return json.loads(lines[-1]) if lines else {}


def main():
    results = {}
    QDIR.mkdir(parents=True, exist_ok=True)

    # ---- Part 0: unit tests --------------------------------------
    r = subprocess.run([sys.executable,
                        str(APP_DIR / "test_claims.py")],
                       capture_output=True, text=True)
    results["unit_tests"] = r.stdout.strip().splitlines()[-1]
    results["unit_pass"] = r.returncode == 0

    # ---- Part 1: v1 rerun against v3 code ------------------------
    v1.APP_DIR = APP_DIR
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            v1.main()
        v1_out = json.loads(buf.getvalue())
        results["v1_rerun"] = {
            "PASS": v1_out["PASS"],
            "reply_text": v1_out["reply_text"],
            "transcript_overlap": v1_out["transcript_word_overlap"]}
    finally:
        for p in v1.procs:
            try:
                p.send_signal(signal.SIGTERM)
                p.wait(timeout=10)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass

    # ---- Part 2: v2 battery, winner brain under lease ------------
    v2.build_fixture()
    brain = subprocess.run(
        ["bash", str(APP_DIR / "brain-server.sh"), "start", "winner",
         str(BRAIN_PORT)], capture_output=True, text=True)
    results["brain_start"] = brain.stdout.strip()
    backend = None
    try:
        results["brain_health_s"] = wait_health(
            f"http://127.0.0.1:{BRAIN_PORT}/health", timeout=420)
        backend = start_backend(BATTERY_PORT, {
            "LEDGER_DIR": str(v2.FIXTURE),
            "BRAIN_URL": f"http://127.0.0.1:{BRAIN_PORT}",
            "RECEIPTS_LOG": str(PLAY / "receipts-v3.jsonl"),
        }, "backend-v3.log")
        qs = []
        for key, question in v2.QUESTIONS:
            wav_path = QDIR / f"{key}.wav"
            subprocess.run([str(PIPER), "--model", str(VOICE),
                            "--output_file", str(wav_path)],
                           input=question.encode(), check=True,
                           capture_output=True)
            out = v2.ask(BATTERY_PORT, wav_path)
            ok, why = v2.score(key, out, qs)
            qs.append({"key": key, "reply_text": out["reply_text"],
                       "pass": ok, "why": why,
                       "claim_violations":
                           out["grounding"].get("claim_violations"),
                       "violation": out["grounding"].get("violation"),
                       "wall_s": out["_wall_s"]})
        results["battery"] = qs
        results["battery_pass"] = all(q["pass"] for q in qs)
        results["battery_claim_replacements"] = sum(
            1 for q in qs if q["claim_violations"])
    finally:
        stop(backend)
        subprocess.run(["bash", str(APP_DIR / "brain-server.sh"),
                        "stop", str(BRAIN_PORT)],
                       capture_output=True, text=True)

    # ---- Part 3: forced prose traps via the stub hook ------------
    v2.build_fixture()  # fresh heartbeats for deterministic states
    stub = PLAY / "stub-brain.txt"
    receipts = PLAY / "receipts-v3-traps.jsonl"
    if receipts.exists():
        receipts.unlink()
    backend = start_backend(TRAP_PORT, {
        "LEDGER_DIR": str(v2.FIXTURE),
        "BRAIN_URL": "http://127.0.0.1:9",  # dead on purpose: stubbed
        "PRESENCE_BRAIN_STUB_FILE": str(stub),
        "STALE_TOLERANCE_S": "3600",
        "RECEIPTS_LOG": str(receipts),
    }, "backend-v3-traps.log")
    q_wav = QDIR / "trap.wav"
    subprocess.run([str(PIPER), "--model", str(VOICE),
                    "--output_file", str(q_wav)],
                   input=b"What is happening at the house?",
                   check=True, capture_output=True)
    traps = []
    try:
        for forced, want_reply, want_type, exact in TRAPS:
            stub.write_text(forced)
            out = v2.ask(TRAP_PORT, q_wav)
            rec = last_receipt(receipts)
            types = [c["type"] for c in
                     out["grounding"].get("claim_violations") or []]
            quoted = any(c.get("sentence") == forced for c in
                         out["grounding"].get("claim_violations") or [])
            reply = out["reply_text"]
            text_ok = (reply == want_reply if exact else
                       reply.startswith(want_reply)
                       and "hours ago." in reply)
            traps.append({
                "forced": forced, "want_type": want_type,
                "reply_text": reply,
                "types": types, "quoted_in_violation": quoted,
                "receipt_reply": rec.get("reply"),
                "receipt_reply_raw": rec.get("reply_raw"),
                "audio_rms": out["reply_audio_stats"]["rms"],
                "pass": bool(
                    text_ok
                    and want_type in types and quoted
                    and rec.get("reply") == reply
                    and rec.get("reply_raw") == forced
                    and out["reply_audio_stats"]["rms"] >= 0.01)})
        controls = []
        for forced in CONTROLS:
            stub.write_text(forced)
            out = v2.ask(TRAP_PORT, q_wav)
            controls.append({
                "forced": forced, "reply_text": out["reply_text"],
                "claim_violations":
                    out["grounding"].get("claim_violations"),
                "pass": bool(out["reply_text"] == forced
                             and not out["grounding"].get(
                                 "claim_violations"))})
        results["traps"] = traps
        results["traps_pass"] = all(t["pass"] for t in traps)
        results["controls"] = controls
        results["controls_pass"] = all(c["pass"] for c in controls)
    finally:
        stop(backend)
        stub.unlink(missing_ok=True)

    # ---- cleanup verification ------------------------------------
    time.sleep(2)
    results["cleanup"] = {
        "ports_free": {p: port_free(p) for p in
                       (8312, BRAIN_PORT, BATTERY_PORT, 8332,
                        TRAP_PORT)},
        "brain_unit": subprocess.run(
            ["systemctl", "--user", "is-active",
             f"presence-brain-{BRAIN_PORT}"],
            capture_output=True, text=True).stdout.strip(),
        "soak_alive": subprocess.run(
            ["pgrep", "-f", "confluence-watch"],
            capture_output=True, text=True).returncode == 0}
    results["PASS"] = bool(
        results["unit_pass"] and results["v1_rerun"]["PASS"]
        and results["battery_pass"] and results["traps_pass"]
        and results["controls_pass"])
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
