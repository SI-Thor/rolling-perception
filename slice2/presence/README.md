# Slice 2 — Presence (Spec Amendment 2)

Any browser is a terminal; the Thor is the only mind. Open the page,
hold the button, speak — the system answers out loud, from the live
ledger. Presence is a deliberately opened, visibly live session:
nothing listens until the button is held, and the indicator says
LIVE while it does. This is the Radio Room generalised from a radio
to a chair at the table — same stage discipline (STT → brain → TTS,
receipts per stage), minus the radio dressing: the voice here is a
person in the room, not a transmission.

## Stack — found vs built

Found on the Thor and reused:
- **Piper TTS** — radio-room-thor's venv binary + the voices on disk
  (`en_US-lessac-medium.onnx`), invoked exactly as
  `radioroom/tts_local.py` does it (temp file; Piper seeks).
- **Whisper model** — `Systran/faster-whisper-tiny.en` already in the
  HF cache. The `faster-whisper` package itself was NOT installed;
  it was added to `~/ml/.venv` with uv (faster-whisper 1.2.1 +
  ctranslate2 4.8.4, two small wheels — no model download).
- **Ledger** — the Slice-1 text ledger, read tolerantly from files.
- **Radio Room lessons** — STT decode via soundfile/stdlib, never
  PyAV (the ml venv's PyAV is incompatible with faster-whisper's
  file path; audio is ffmpeg-normalised to 16 kHz mono WAV and
  decoded with the stdlib `wave` module instead).

Built here:
- `presence.py` — FastAPI backend (ml venv): POST /hear runs
  decode → STT (CPU int8) → ledger digest → brain → Piper, returns
  transcript + reply text + reply audio (base64 WAV) + per-stage
  timings; every call appends a receipts line.
- `piper_worker.py` — resident Piper synthesis worker (see TTS
  below): loads the voice once, serves text → WAV over a unix
  socket (request = one line of text; reply = `OK <nbytes>` +
  WAV bytes).
- `tts_bench.py` — spawn-vs-resident TTS bench (stdlib only).
- `index.html` — one static page: hold-to-talk (or tap-to-toggle),
  a live state indicator (idle / ● LIVE listening / thinking /
  speaking), transcript and reply shown, reply played on the
  device's own speaker.
- `acceptance.py` — the no-human-throat test (below).

## The brain endpoint — read this

The spec pointed at llama-server :8001. At build time **:8001 was
down**, and the Thor's two live llama-servers (:8295 d1-3B, :8296
d1-2B) are Casey's *decision models* — they refuse chat completions
("decision model without text generation, use /v1/systemone"). A
decision model cannot hold a conversation, so `BRAIN_URL` is config:
default `http://127.0.0.1:8001`; point it at any OpenAI-shaped
llama.cpp chat endpoint. Acceptance ran against a temporary
llama-server serving the on-disk LFM2-1.2B GGUF on :8301, started
for the test and killed after. Casey's tenants were never stopped
or touched.

## Run it (on the Thor)

    mkdir -p ~/confluence-play/slice2/app   # deploy presence.py + index.html here
    cd ~/confluence-play/slice2/app
    BRAIN_URL=http://127.0.0.1:8001 \
    LEDGER_DIR=~/confluence-play/slice1/run/ledger \
      ~/ml/.venv/bin/python presence.py     # serves 0.0.0.0:8330

Then open `http://thor.local:8330` (or the Thor's LAN IP) in any
browser on the LAN and hold the button. Stop with Ctrl-C — nothing
is installed, nothing is resident.

## TTS — the resident Piper worker

Spawn-per-call Piper was the loop's biggest stage: process start +
ONNX model load on *every* reply. Measured on the Thor
(`tts_bench.py`, plus paired acceptance runs, same fixture):

| TTS path | TTS stage | total /hear loop |
|---|---|---|
| spawn-per-call (before) | 1,974 ms | 2,891 ms |
| resident worker (after) | **287 ms** | **1,284 ms** |

(The original presence build measured 2,788 ms / 4,860 ms on a
colder box; the table above is the controlled same-session pair.
A confirmation acceptance run on the final shipped code: TTS
499 ms, PASS.)

Bench detail (`tts_bench.py`, same texts both paths):
- spawn-per-call: p50 2,664 ms, p99 3,465 ms (n=6)
- worker start-to-ready: 2,011 ms — the spawn tax, paid **once**
- first request after ready: 852 ms
- warm requests (n=12, mixed lengths): p50 852 ms, p99 1,509 ms;
  per length — short ~120–225 ms, medium ~550–970 ms,
  long ~1,165–1,509 ms. Synthesis time is length-bound; the
  process tax is what's gone.
- worker RAM: 137 MB RSS at ready, ~273 MB after a warm set
  (ONNX arena growth) — the honest rent for the speed.
- cold /hear where the backend must start the worker itself:
  ~2.0–2.6 s once per backend run, then warm.

How it runs: `presence.py` uses the resident path when available
(`TTS_RESIDENT=0` disables it) and falls back to spawn-per-call on
any worker failure. The backend starts the worker **on demand** on
the first /hear that needs it and stops it at shutdown; a worker
started explicitly is used as-is and left running. Never a
systemd resident. Manual control:

    # start (radio-room venv python — that's where piper lives)
    ~/radio-room-thor/.venv/bin/python piper_worker.py \
        --sock ~/confluence-play/slice2/piper.sock \
        --model ~/radio-room-thor/voices/en_US-lessac-medium.onnx
    # stop: SIGTERM/SIGINT to that PID, or kill it; the socket
    # file is removed on the next start.

Build lesson, recorded because it cost a debug cycle: uvicorn
re-raises the captured SIGTERM after lifespan shutdown, so a
`finally`/`atexit` around `uvicorn.run` never executes on a
service stop — the owned worker is stopped from FastAPI's
shutdown event instead (both hooks are in place; the lifespan
one is the one that fires under uvicorn).

## Acceptance

`acceptance.py` (ml venv python, from ~/confluence-play/slice2/):
builds a fixture ledger with one staged event ("A red toolbox
appeared beside the dock door"), synthesises the spoken question
"What changed at the camera today?" with Piper, POSTs it through
/hear, and verifies transcript overlap, that the reply names the
staged event, and that the reply audio is non-silent plausible
speech; plus GET / = 200 with the live-indicator marker. Measured
numbers live in the run output, not in this file.
