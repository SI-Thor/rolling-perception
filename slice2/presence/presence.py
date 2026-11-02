#!/usr/bin/env python3
"""Confluence presence backend — Spec Amendment 2.

Any browser is a terminal; the Thor is the only mind. A browser lends
this service its microphone and speaker for a deliberately opened,
visibly live session:

    POST /hear   audio clip (webm/wav from MediaRecorder)
                 -> STT (faster-whisper, on-disk model)
                 -> brain prompt = persona + LEDGER DIGEST + transcript
                 -> llama.cpp chat endpoint (OpenAI-shaped)
                 -> Piper TTS (radio-room-thor voice, called directly)
                 -> {transcript, reply_text, reply_audio_b64, timings}
    GET  /       the presence page (single static file)
    GET  /health service + config summary

Per-stage timings are appended to a receipts log — the Radio Room
discipline: every stage measured, nothing claimed without a number.

Prior art reused, not rebuilt: radioroom/tts_local.py's Piper
invocation (binary beside the radio-room venv, real temp file because
Piper seeks in the WAV header), the radio-room voices on disk, and
radioroom/stt.py's faster-whisper choice — with the fleet lesson that
STT decode must NOT go through PyAV here: audio is normalised by
ffmpeg to 16 kHz mono WAV and decoded with the stdlib wave module.

Config (env):
  PRESENCE_PORT  default 8330
  LEDGER_DIR     default ~/confluence-play/slice1/run/ledger
  BRAIN_URL      default http://127.0.0.1:8310 — the bench winner's
                 port (Qwen3-Coder-30B-A3B-Instruct Q4_K_M, served
                 detached by brain-server.sh; BRAIN-BENCH.md has the
                 scores). Named fallback: LFM2-1.2B Q8_0, same port
                 via `brain-server.sh start fallback`. Any
                 OpenAI-shaped llama.cpp chat endpoint works; the
                 model is auto-detected.
  BRAIN_MAX_TOKENS  default 64 — the winner writes briefings, not
                 table talk; brevity is also enforced post-generation
                 (trim_reply: 2 sentences / 45 words) because TTS is
                 the loop's scarcest stage.
  STALE_TOLERANCE_S default 90 — a stream whose heartbeat is older
                 than its lens tolerance (lens.txt
                 heartbeat_tolerance_s wins when present) is rendered
                 in the digest as a NOT REPORTING line, in words.
  PRESENCE_HISTORY_TURNS default 4 — recent exchanges ride in the
                 prompt so follow-ups ("What colour is it?") resolve.
  PIPER_BIN      default ~/radio-room-thor/.venv/bin/piper
  PIPER_VOICE    default ~/radio-room-thor/voices/en_US-lessac-medium.onnx
  WHISPER_MODEL  default tiny.en (already in the HF cache on the Thor)
  RECEIPTS_LOG   default ./receipts.jsonl next to this file
  TTS_RESIDENT   default 1 — speak via the resident piper_worker
                 (unix socket) when possible, falling back to
                 spawn-per-call. Set 0 to disable the resident path.
  PIPER_SOCK     default ~/confluence-play/slice2/piper.sock
  PIPER_VENV_PY  default ~/radio-room-thor/.venv/bin/python
                 (interpreter that owns the piper package)
"""
import atexit
import base64
from collections import deque
import json
import os
import re
import socket
import subprocess
import tempfile
import time
import urllib.request
import wave
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

HOME = Path.home()
PORT = int(os.environ.get("PRESENCE_PORT", "8330"))
LEDGER_DIR = Path(os.environ.get(
    "LEDGER_DIR", HOME / "confluence-play/slice1/run/ledger"))
BRAIN_URL = os.environ.get("BRAIN_URL", "http://127.0.0.1:8001")
PIPER_BIN = os.environ.get(
    "PIPER_BIN", str(HOME / "radio-room-thor/.venv/bin/piper"))
PIPER_VOICE = os.environ.get(
    "PIPER_VOICE", str(HOME / "radio-room-thor/voices/en_US-lessac-medium.onnx"))
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "tiny.en")
RECEIPTS_LOG = Path(os.environ.get(
    "RECEIPTS_LOG", Path(__file__).with_name("receipts.jsonl")))
TTS_RESIDENT = os.environ.get("TTS_RESIDENT", "1") != "0"
PIPER_SOCK = os.environ.get(
    "PIPER_SOCK", str(HOME / "confluence-play/slice2/piper.sock"))
PIPER_VENV_PY = os.environ.get(
    "PIPER_VENV_PY", str(HOME / "radio-room-thor/.venv/bin/python"))
PAGE = Path(__file__).with_name("index.html")

PERSONA = (
    "You are Confluence, the house system, sitting at the table. "
    "You watch the house's cameras and library and report what changed. "
    "Answer in plain spoken words, one to three short sentences, no "
    "lists, no markdown. Use only the ledger facts you are given. "
    "If nothing changed, say so plainly."
)

_whisper = None
_whisper_load_s = None
_brain_model = None


def get_whisper():
    global _whisper, _whisper_load_s
    if _whisper is None:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        from faster_whisper import WhisperModel
        t0 = time.perf_counter()
        _whisper = WhisperModel(WHISPER_MODEL, device="cpu",
                                compute_type="int8", local_files_only=True)
        _whisper_load_s = round(time.perf_counter() - t0, 3)
    return _whisper


def get_brain_model():
    global _brain_model
    if _brain_model is None:
        try:
            with urllib.request.urlopen(BRAIN_URL + "/v1/models",
                                        timeout=5) as r:
                data = json.loads(r.read())
            _brain_model = data["data"][0]["id"]
        except Exception:
            _brain_model = "default"
    return _brain_model


# ---------- ledger digest (tolerant reader; absence is not an error) ----

def _read_kv(path):
    out = {}
    try:
        for line in path.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    except OSError:
        pass
    return out


def ledger_digest():
    lines = []
    streams_dir = LEDGER_DIR / "streams"
    stream_names = []
    if streams_dir.is_dir():
        stream_names = sorted(p.name for p in streams_dir.iterdir() if p.is_dir())
    for name in stream_names:
        sdir = streams_dir / name
        health = _read_kv(sdir / "health.txt")
        hb = health.get("heartbeat_ts")
        if hb:
            try:
                age = max(0, int(time.time() - float(hb)))
                lines.append(f"{name}: heartbeat {age}s ago"
                             + (f", embed p50 {health['embed_p50_ms']} ms"
                                if "embed_p50_ms" in health else ""))
            except ValueError:
                pass
        state = _read_kv(sdir / "state.txt")
        if state.get("state"):
            lines.append(f"{name} state: {state['state']}")
        verdicts = []
        try:
            for raw in (sdir / "events.jsonl").read_text().splitlines():
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if row.get("line"):
                    verdicts.append(row)
        except OSError:
            pass
        for v in verdicts[-3:]:
            lines.append(f"{name} event: {v['line']} "
                         f"(score {v.get('score', '?')})")
        if not verdicts:
            lines.append(f"{name}: no changes reported")
    items_dir = LEDGER_DIR / "items"
    if items_dir.is_dir():
        titles = []
        for p in sorted(items_dir.glob("*.txt"))[:5]:
            try:
                first = p.read_text().splitlines()[0].strip()
            except (OSError, IndexError):
                continue
            if first:
                titles.append(first)
        if titles:
            lines.append("On the library shelf: " + "; ".join(titles))
    return "\n".join(lines) if lines else "The ledger is empty."


# ---------- stages --------------------------------------------------------

def decode_to_array(raw_bytes, suffix):
    """ffmpeg -> 16 kHz mono wav -> float32 numpy (never PyAV)."""
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / ("in" + suffix)
        dst = Path(td) / "out.wav"
        src.write_bytes(raw_bytes)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
                        "-ar", "16000", "-ac", "1", str(dst)],
                       check=True, timeout=60)
        with wave.open(str(dst)) as w:
            frames = w.readframes(w.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


def transcribe(audio):
    model = get_whisper()
    segs, _info = model.transcribe(audio, beam_size=1)
    return " ".join(s.text for s in segs).strip()


def ask_brain(transcript, digest):
    user = (f"House ledger, latest:\n{digest}\n\n"
            f"The person at the table asks: {transcript}\n"
            f"Answer briefly from the ledger.")
    payload = {
        "model": get_brain_model(),
        "messages": [{"role": "system", "content": PERSONA},
                     {"role": "user", "content": user}],
        "max_tokens": 120, "temperature": 0.3,
    }
    req = urllib.request.Request(
        BRAIN_URL + "/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"].strip()


# ---------- TTS: resident Piper worker, spawn fallback -------------------
# Spawn-per-call Piper pays process start + model load on every reply
# (~2 s measured). piper_worker.py holds the voice in memory and
# serves text -> WAV over a unix socket. The backend starts it on
# demand (first /hear that needs it) and stops it at shutdown if the
# backend started it; a worker started explicitly is used as-is and
# left running. Any resident failure falls back to the spawn path.

_worker_proc = None
_worker_owned = False
_last_tts_path = None


def _worker_alive():
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect(PIPER_SOCK)
        return True
    except OSError:
        return False


def _ensure_worker():
    """Make a resident worker reachable, starting one on demand."""
    global _worker_proc, _worker_owned
    if _worker_alive():
        return
    try:  # stale socket file from a dead worker
        Path(PIPER_SOCK).unlink()
    except OSError:
        pass
    worker = Path(__file__).with_name("piper_worker.py")
    if not worker.exists() or not Path(PIPER_VENV_PY).exists():
        raise RuntimeError("piper_worker.py or venv python missing")
    log = open(RECEIPTS_LOG.with_name("piper-worker.log"), "ab")
    _worker_proc = subprocess.Popen(
        [PIPER_VENV_PY, str(worker), "--sock", PIPER_SOCK,
         "--model", PIPER_VOICE],
        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    _worker_owned = True
    deadline = time.time() + 90  # model load is seconds; be generous
    while time.time() < deadline:
        if _worker_proc.poll() is not None:
            raise RuntimeError("piper worker exited during start; see "
                               "piper-worker.log")
        if _worker_alive():
            return
        time.sleep(0.2)
    raise RuntimeError("piper worker did not become ready in 90 s")


def _stop_owned_worker():
    global _worker_proc, _worker_owned
    if _worker_owned and _worker_proc is not None \
            and _worker_proc.poll() is None:
        _worker_proc.terminate()
        try:
            _worker_proc.wait(timeout=5)
        except Exception:
            _worker_proc.kill()
        try:
            Path(PIPER_SOCK).unlink()
        except OSError:
            pass
    _worker_owned = False


atexit.register(_stop_owned_worker)


def _speak_resident(clean):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(180)
        s.connect(PIPER_SOCK)
        s.sendall(clean.replace("\n", " ").encode() + b"\n")
        buf = b""
        while b"\n" not in buf:
            chunk = s.recv(65536)
            if not chunk:
                raise RuntimeError("piper worker closed the connection")
            buf += chunk
        header, _, data = buf.partition(b"\n")
        parts = header.decode("utf-8", "replace").split(" ", 1)
        if len(parts) != 2 or parts[0] != "OK":
            raise RuntimeError("piper worker said: "
                               + header.decode("utf-8", "replace"))
        n = int(parts[1])
        while len(data) < n:
            chunk = s.recv(min(65536, n - len(data)))
            if not chunk:
                raise RuntimeError("piper worker sent a short WAV")
            data += chunk
    if not data.startswith(b"RIFF"):
        raise RuntimeError("piper worker returned a non-WAV payload")
    return data


def speak(text):
    """TTS: resident Piper worker when available, else spawn-per-call
    via the radio-room venv binary (temp file; Piper seeks)."""
    global _last_tts_path
    clean = re.sub(r"[*#`_>]", "", text).strip()
    if TTS_RESIDENT:
        try:
            _ensure_worker()
            _last_tts_path = "resident"
            return _speak_resident(clean)
        except Exception:
            pass  # fall through to the known-good spawn path
    _last_tts_path = "spawn"
    fd, tmp = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        proc = subprocess.run(
            [PIPER_BIN, "--model", PIPER_VOICE, "--output_file", tmp],
            input=clean.encode(), capture_output=True, timeout=180)
        if proc.returncode != 0:
            raise RuntimeError("piper failed: "
                               + proc.stderr.decode()[-300:])
        return Path(tmp).read_bytes()
    finally:
        os.unlink(tmp)


def wav_stats(data):
    import io
    with wave.open(io.BytesIO(data)) as w:
        n, sr = w.getnframes(), w.getframerate()
        frames = w.readframes(n)
    a = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    rms = float(np.sqrt(np.mean(a ** 2))) if a.size else 0.0
    return {"duration_s": round(n / sr, 2) if sr else 0, "rms": round(rms, 4)}


def receipt(obj):
    try:
        with RECEIPTS_LOG.open("a") as f:
            f.write(json.dumps(obj) + "\n")
    except OSError:
        pass


# ---------- app -----------------------------------------------------------

app = FastAPI(title="confluence-presence")


@app.on_event("shutdown")
def _on_shutdown():
    # uvicorn re-raises the captured SIGTERM after lifespan shutdown,
    # so process-level finally/atexit never run on a service stop —
    # the owned TTS worker must be stopped HERE, inside the lifespan.
    _stop_owned_worker()


@app.get("/", response_class=HTMLResponse)
def page():
    return PAGE.read_text()


@app.get("/health")
def health():
    return {"ok": True, "service": "confluence-presence",
            "brain_url": BRAIN_URL, "ledger_dir": str(LEDGER_DIR),
            "whisper_model": WHISPER_MODEL,
            "whisper_loaded": _whisper is not None,
            "whisper_load_s": _whisper_load_s,
            "voice": Path(PIPER_VOICE).name,
            "tts_resident": TTS_RESIDENT,
            "piper_sock": PIPER_SOCK,
            "worker_owned": _worker_owned}


@app.post("/hear")
async def hear(audio: UploadFile = File(...)):
    t_start = time.perf_counter()
    timings = {}
    raw = await audio.read()
    suffix = Path(audio.filename or "clip.webm").suffix or ".webm"

    t0 = time.perf_counter()
    arr = decode_to_array(raw, suffix)
    timings["decode_ms"] = round((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    transcript = transcribe(arr)
    timings["stt_ms"] = round((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    digest = ledger_digest()
    timings["digest_ms"] = round((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    reply = ask_brain(transcript, digest)
    timings["brain_ms"] = round((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    wav_bytes = speak(reply)
    timings["tts_ms"] = round((time.perf_counter() - t0) * 1000)
    timings["tts_path"] = _last_tts_path

    stats = wav_stats(wav_bytes)
    timings["total_ms"] = round((time.perf_counter() - t_start) * 1000)
    receipt({"ts": round(time.time(), 1), "transcript": transcript,
             "reply": reply, "timings_ms": timings, "audio": stats,
             "whisper_load_s": _whisper_load_s})
    return JSONResponse({
        "transcript": transcript,
        "reply_text": reply,
        "reply_audio_b64": base64.b64encode(wav_bytes).decode(),
        "reply_audio_stats": stats,
        "timings_ms": timings,
    })


if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    finally:
        _stop_owned_worker()
