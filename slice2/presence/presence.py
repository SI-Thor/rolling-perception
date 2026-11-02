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
  BRAIN_URL      default http://127.0.0.1:8001  (any OpenAI-shaped
                 llama.cpp chat endpoint; model auto-detected)
  PIPER_BIN      default ~/radio-room-thor/.venv/bin/piper
  PIPER_VOICE    default ~/radio-room-thor/voices/en_US-lessac-medium.onnx
  WHISPER_MODEL  default tiny.en (already in the HF cache on the Thor)
  RECEIPTS_LOG   default ./receipts.jsonl next to this file
"""
import base64
import json
import os
import re
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


def speak(text):
    """Piper via the radio-room venv binary; temp file (Piper seeks)."""
    clean = re.sub(r"[*#`_>]", "", text).strip()
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
            "voice": Path(PIPER_VOICE).name}


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
    uvicorn.run(app, host="0.0.0.0", port=PORT)
