#!/usr/bin/env python3
"""TTS bench: spawn-per-call Piper vs the resident piper_worker.

Same texts through both paths; the resident path also reports its
honest costs — worker start-to-ready (the model load the spawn path
pays on EVERY call), first request, and resident RAM. Stdlib only;
run on the Thor with any python3. Leaves nothing running: the worker
it starts is terminated and its socket removed.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOME = Path.home()
SOCK = str(HOME / "confluence-play/slice2/piper-bench.sock")
VENV_PY = str(HOME / "radio-room-thor/.venv/bin/python")
PIPER_BIN = str(HOME / "radio-room-thor/.venv/bin/piper")
VOICE = str(HOME / "radio-room-thor/voices/en_US-lessac-medium.onnx")
WORKER = Path(__file__).with_name("piper_worker.py")

TEXTS = [
    "Yes.",
    "The dock camera is quiet, and nothing has changed since this "
    "morning.",
    "A red toolbox appeared beside the dock door a little while ago. "
    "Everything else on the shelf and at the dock looks the same as "
    "it did yesterday, and the harbour is calm.",
]


def pct(sorted_vals, q):
    if not sorted_vals:
        return None
    i = min(len(sorted_vals) - 1, max(0, int(q * len(sorted_vals))))
    return round(sorted_vals[i])


def rss_kb(pid):
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return None


def spawn_tts(text):
    fd, tmp = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        t0 = time.perf_counter()
        p = subprocess.run([PIPER_BIN, "--model", VOICE,
                            "--output_file", tmp],
                           input=text.encode(), capture_output=True,
                           timeout=180)
        ms = (time.perf_counter() - t0) * 1000
        if p.returncode != 0:
            raise RuntimeError(p.stderr.decode()[-200:])
        return ms, Path(tmp).stat().st_size
    finally:
        os.unlink(tmp)


def resident_tts(text):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(180)
        s.connect(SOCK)
        t0 = time.perf_counter()
        s.sendall(text.encode() + b"\n")
        buf = b""
        while b"\n" not in buf:
            buf += s.recv(65536)
        header, _, data = buf.partition(b"\n")
        kind, n = header.decode().split(" ", 1)
        assert kind == "OK", header
        n = int(n)
        while len(data) < n:
            data += s.recv(min(65536, n - len(data)))
        ms = (time.perf_counter() - t0) * 1000
    assert data.startswith(b"RIFF")
    return ms, len(data)


def main():
    out = {}
    # spawn path, same texts, 2 reps each
    spawn_ms = []
    for text in TEXTS:
        for _ in range(2):
            ms, size = spawn_tts(text)
            spawn_ms.append(ms)
    s = sorted(spawn_ms)
    out["spawn"] = {"n": len(s), "p50_ms": pct(s, 0.5),
                    "p99_ms": pct(s, 0.99), "all_ms": [round(x) for x in s]}

    # resident path
    proc = subprocess.Popen(
        [VENV_PY, str(WORKER), "--sock", SOCK, "--model", VOICE],
        stdout=open("/tmp/piper-bench-worker.log", "wb"),
        stderr=subprocess.STDOUT)
    try:
        t0 = time.perf_counter()
        while True:
            try:
                with socket.socket(socket.AF_UNIX,
                                   socket.SOCK_STREAM) as sk:
                    sk.settimeout(2)
                    sk.connect(SOCK)
                break
            except OSError:
                if proc.poll() is not None:
                    raise RuntimeError("worker died at start")
                if time.perf_counter() - t0 > 90:
                    raise RuntimeError("worker start timeout")
                time.sleep(0.1)
        out["worker_start_to_ready_ms"] = round(
            (time.perf_counter() - t0) * 1000)
        out["worker_rss_mb"] = round(rss_kb(proc.pid) / 1024, 1)

        first_ms, _ = resident_tts(TEXTS[1])
        out["resident_first_call_ms"] = round(first_ms)

        warm = []
        for i in range(12):  # >=10 warm calls, varying length
            ms, _ = resident_tts(TEXTS[i % len(TEXTS)])
            warm.append(ms)
        w = sorted(warm)
        out["resident_warm"] = {
            "n": len(w), "p50_ms": pct(w, 0.5), "p99_ms": pct(w, 0.99),
            "min_ms": round(w[0]), "max_ms": round(w[-1]),
            "all_ms": [round(x) for x in warm]}
        out["worker_rss_mb_after"] = round(rss_kb(proc.pid) / 1024, 1)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        try:
            Path(SOCK).unlink()
        except OSError:
            pass
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
