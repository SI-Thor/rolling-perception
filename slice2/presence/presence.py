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
BRAIN_URL = os.environ.get("BRAIN_URL", "http://127.0.0.1:8310")
BRAIN_MAX_TOKENS = int(os.environ.get("BRAIN_MAX_TOKENS", "64"))
STALE_TOLERANCE_S = int(os.environ.get("STALE_TOLERANCE_S", "90"))
HISTORY_TURNS = int(os.environ.get("PRESENCE_HISTORY_TURNS", "4"))
SAFE_REPLY = "I don't have a record of that."
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
    "Answer in plain spoken words, at most two short sentences, no "
    "lists, no markdown. You are the voice of records the system has "
    "already published; you never search and never invent. "
    "Grounding rules: (1) Refer to a camera event only by choosing "
    "its record id, written in brackets like [dock-cam-41], from the "
    "records below. (2) State a number only if it appears exactly in "
    "the records below; never invent, estimate, or round a number. "
    "(3) A record line that says NOT REPORTING means that camera is "
    "not watching: say so plainly, and never call the house calm or "
    "normal while any camera is not reporting. (4) If no record "
    "covers the question, say exactly: I don't have a record of that. "
    "Health claims come only from the record lines below."
)

_whisper = None
_whisper_load_s = None
_brain_model = None
_history = deque(maxlen=max(HISTORY_TURNS, 0)) if HISTORY_TURNS > 0 \
    else deque(maxlen=1)


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


_NUM_RE = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w])")


def _human_age(age_s):
    """Seconds -> spoken words ('14 seconds ago', '2 hours ago').
    The bench's core lesson: models do not do seconds->hours
    arithmetic as a side effect of reading; the digest does it."""
    if age_s < 90:
        return f"{age_s} second{'s' if age_s != 1 else ''} ago"
    if age_s < 5400:
        m = max(1, round(age_s / 60))
        return f"{m} minute{'s' if m != 1 else ''} ago"
    h = age_s / 3600.0
    hs = str(int(h)) if h == int(h) else str(round(h, 1))
    return f"{hs} hour{'s' if hs != '1' else ''} ago"


def ledger_digest():
    """Digest v2 — verdict-only grounding (Panel 2 Q1) plus the brain
    bench's two digest disciplines:

    * Staleness is pre-computed into words: a stream whose heartbeat
      exceeds its lens tolerance (lens.txt heartbeat_tolerance_s, else
      STALE_TOLERANCE_S) renders as a literal NOT REPORTING line; the
      brain is never handed a raw age and asked to judge calm.
    * Events enter ONLY as published verdict records carrying ids;
      the brain references an event by selecting its id (the backend
      self-check enforces this — see grounding_check).
    * Health numbers are template-rendered verbatim from health.txt
      (quote-only; enforced by grounding_check).

    Returns (text, meta) where meta = {"ids": [...], "numbers": set
    of float values present in the digest, "not_reporting": [...]}.
    """
    lines = []
    ids = []
    not_reporting = []
    streams_dir = LEDGER_DIR / "streams"
    stream_names = []
    if streams_dir.is_dir():
        stream_names = sorted(p.name for p in streams_dir.iterdir() if p.is_dir())
    for name in stream_names:
        sdir = streams_dir / name
        lens = _read_kv(sdir / "lens.txt")
        try:
            tol = int(float(lens.get("heartbeat_tolerance_s",
                                     STALE_TOLERANCE_S)))
        except (TypeError, ValueError):
            tol = STALE_TOLERANCE_S
        health = _read_kv(sdir / "health.txt")
        age = None
        hb = health.get("heartbeat_ts")
        if hb:
            try:
                age = max(0, int(time.time() - float(hb)))
            except ValueError:
                age = None
        if age is None or age > tol:
            age_words = "never" if age is None else _human_age(age)
            lines.append(f"NOT REPORTING — {name}, last heartbeat "
                         f"{age_words}")
            not_reporting.append(name)
        else:
            lines.append(f"{name}: heartbeat {_human_age(age)}")
        if "embed_p50_ms" in health:
            hline = f"{name} health: embed p50 {health['embed_p50_ms']} ms"
            if "queue_depth" in health:
                hline += f", queue depth {health['queue_depth']}"
            if name in not_reporting:
                hline += " (last measured before it stopped reporting)"
            lines.append(hline)
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
        for i, v in enumerate(verdicts[-3:]):
            eid = str(v.get("id") or
                      f"{name}-{v.get('tick', v.get('frame', i))}")
            ids.append(eid)
            lines.append(f"[{eid}] {name} event: {v['line']} "
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
    text = "\n".join(lines) if lines else "The ledger is empty."
    numbers = set()
    for tok in _NUM_RE.findall(text):
        try:
            numbers.add(float(tok))
        except ValueError:
            pass
    return text, {"ids": ids, "numbers": numbers,
                  "not_reporting": not_reporting}


# ---------- grounding: brevity + the cheap self-check --------------------
# Panel 2 Q1's self-check is string matching, not a judge: a cited id
# not in the digest, or a spoken number in no record, means the reply
# is not spoken — it is replaced with the safe template and the
# violation is logged in the receipts. Brevity is enforced here too,
# outside the model (the winner writes briefings; TTS time is scarce).

def trim_reply(text, max_sentences=2, max_words=45):
    """Cap a reply at ~2 sentences / 45 words, cutting at a sentence
    boundary whenever one exists inside the budget."""
    text = " ".join(text.split())
    if not text:
        return text, False
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if s]
    kept, words = [], 0
    for s in sentences:
        w = len(s.split())
        if kept and (len(kept) >= max_sentences or words + w > max_words):
            break
        kept.append(s)
        words += w
        if len(kept) >= max_sentences or words >= max_words:
            break
    out = " ".join(kept) if kept else text
    if len(out.split()) > max_words:  # one long sentence: hard cut
        out = " ".join(out.split()[:max_words]).rstrip(",;:") + "."
    return out, out != text


def grounding_check(reply, meta, transcript):
    """Return a violation dict, or None if the reply is grounded.
    Allowed numbers: any number rendered in the digest, plus any
    number the person themselves just said. Allowed ids: exactly the
    verdict ids the digest carried."""
    cited = [c.strip() for c in re.findall(r"\[([^\]]+)\]", reply)]
    cited += [t for t in re.findall(
        r"\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+-\d+\b", reply)
        if t not in cited]
    for cid in cited:
        if cid not in meta["ids"]:
            return {"type": "unknown_id", "value": cid, "cited": cited}
    allowed = set(meta["numbers"])
    for tok in _NUM_RE.findall(transcript or ""):
        try:
            allowed.add(float(tok))
        except ValueError:
            pass
    for tok in _NUM_RE.findall(reply):
        try:
            val = float(tok)
        except ValueError:
            continue
        if val not in allowed:
            return {"type": "unknown_number", "value": tok,
                    "cited": cited}
    return None


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
    hist = ""
    if HISTORY_TURNS > 0 and _history:
        turns = "\n".join(f"Person: {q}\nConfluence: {a}"
                          for q, a in _history)
        hist = f"Earlier at the table:\n{turns}\n\n"
    user = (f"House records, latest:\n{digest}\n\n"
            f"{hist}"
            f"The person at the table asks: {transcript}\n"
            f"Answer briefly from the records, citing the record id "
            f"in brackets when you mention an event.")
    payload = {
        "model": get_brain_model(),
        "messages": [{"role": "system", "content": PERSONA},
                     {"role": "user", "content": user}],
        "max_tokens": BRAIN_MAX_TOKENS, "temperature": 0.3,
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
            "brain_url": BRAIN_URL,
            "brain_default": "Qwen3-Coder-30B-A3B-Instruct Q4_K_M "
                             "(brain-server.sh); fallback LFM2-1.2B",
            "brain_max_tokens": BRAIN_MAX_TOKENS,
            "digest": "v2 (verdict-only, NOT REPORTING in words, "
                      "quote-only numbers)",
            "stale_tolerance_s": STALE_TOLERANCE_S,
            "history_turns_kept": len(_history),
            "ledger_dir": str(LEDGER_DIR),
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
    digest, meta = ledger_digest()
    timings["digest_ms"] = round((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    reply_raw = ask_brain(transcript, digest)
    timings["brain_ms"] = round((time.perf_counter() - t0) * 1000)

    # Grounding pipeline, all outside the model: trim to spoken size,
    # self-check ids + numbers against the digest, replace on
    # violation. Citations stay in the written reply (and the page);
    # the spoken text drops the brackets — nobody talks in [ids].
    reply, trimmed = trim_reply(reply_raw)
    violation = grounding_check(reply, meta, transcript)
    replaced = violation is not None
    if replaced:
        reply = SAFE_REPLY
    cited = [c.strip() for c in re.findall(r"\[([^\]]+)\]", reply)]
    spoken = re.sub(r"\[[^\]]+\]\s*", "", reply).strip() or reply

    t0 = time.perf_counter()
    wav_bytes = speak(spoken)
    timings["tts_ms"] = round((time.perf_counter() - t0) * 1000)
    timings["tts_path"] = _last_tts_path

    if HISTORY_TURNS > 0:
        _history.append((transcript, reply))

    stats = wav_stats(wav_bytes)
    timings["total_ms"] = round((time.perf_counter() - t_start) * 1000)
    grounding = {"violation": violation, "replaced": replaced,
                 "trimmed": trimmed, "cited_ids": cited,
                 "digest_ids": meta["ids"],
                 "not_reporting": meta["not_reporting"]}
    receipt({"ts": round(time.time(), 1), "transcript": transcript,
             "reply": reply, "reply_raw": reply_raw,
             "grounding": grounding,
             "timings_ms": timings, "audio": stats,
             "whisper_load_s": _whisper_load_s})
    return JSONResponse({
        "transcript": transcript,
        "reply_text": reply,
        "reply_audio_b64": base64.b64encode(wav_bytes).decode(),
        "reply_audio_stats": stats,
        "timings_ms": timings,
        "grounding": grounding,
    })


if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    finally:
        _stop_owned_worker()
