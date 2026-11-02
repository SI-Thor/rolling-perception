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
or touched. **v2 changes the default brain and its port — see
"Presence v2" below.**

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

## Presence v2 — the bench winner, verdict-only grounding (2026-11-01)

Three findings composed into one upgrade: the brain bench's winner,
its two digest disciplines, and Panel 2 Q1's verdict-only grounding.

**The brain.** Default is now the bench winner,
**Qwen3-Coder-30B-A3B-Instruct Q4_K_M**, at `BRAIN_URL`
default `http://127.0.0.1:8310`. **LFM2-1.2B Q8_0 is the named
fallback** (`brain-server.sh start fallback`) — it serves only
behind the disciplines below. On this box the brain MUST be
started under a thor-admit lease: the Thor's admission daemon
SIGTERMs unleased multi-GB loads as runaways. Three launches of
the winner died that way during this lane (a script's setsid
child, a setsid+nohup shell launch, and a systemd user service
running llama-server directly; the daemon's log records
`guard.terminated, trigger=runaway, 18.5 GB`). `brain-server.sh`
wraps the working route:

    brain-server.sh start [winner|fallback] [port]   # default winner, 8310
    brain-server.sh status [port]
    brain-server.sh stop [port]                      # releases the lease

It runs `thor-admit serve <Model> --port <n> --peak 24G|4G --
llama-server …` as a transient systemd user unit (linger on, so
it survives SSH logout). The first serve of a model needs the
explicit --peak; the daemon learns the label afterwards. Full
start→healthy→stop cycle verified with the fallback (healthy in
~6 s); the winner reached health 200 within ~2 min of its serve
launch (registry hashing + grant + 18.6 GB load).

**Digest v2** (`ledger_digest` now returns text + grounding meta):
- *Staleness in words.* A stream whose heartbeat exceeds its lens
  tolerance (`lens.txt heartbeat_tolerance_s`, else 90 s) renders
  as a literal line — `NOT REPORTING — dock-cam, last heartbeat
  2 hours ago` — and health claims may come only from these lines.
  Ages are humanised by the digest; brains are never handed a raw
  second count and asked to judge calm.
- *Numbers are quote-only.* Health figures are template-rendered
  verbatim from `health.txt`; a NOT REPORTING stream's figure is
  annotated "(last measured before it stopped reporting)".
- *Verdict-only grounding.* Events enter only as published
  verdict records with ids (`[dock-cam-41] …`). The brain refers
  to an event by selecting its id; a backend self-check (string
  matching, not a judge) then verifies the reply: every bracketed
  citation must be a digest id, and every spoken number must
  appear verbatim in the digest (or in the question itself). On
  violation the reply is replaced with "I don't have a record of
  that." and the violation is logged in the receipts. Citations
  stay in the written reply; the spoken text drops the brackets.
- *Brevity outside the model.* `max_tokens` 64, plus a
  post-generation trim to 2 sentences / 45 words at a sentence
  boundary — the winner writes briefings, and TTS time is the
  scarce stage. A 4-turn spoken history rides in the prompt so
  follow-ups resolve ("What colour is it?" → the red toolbox).

**Acceptance** (`acceptance_v2.py`, bench fixture rebuilt as a
Slice-1 ledger: phone-cam fresh/173 ms, dock-cam 7200 s
stale/181 ms + the toolbox verdict, porch-cam fresh, the Sitka
shelf line). All seven turns through the FULL loop (Piper speech
in, spoken reply out), winner brain leased on a scratch port:
**7/7 PASS, zero grounding violations, zero replacements, zero
invented numbers.** (a) toolbox named, cited `[dock-cam-41]`,
NOT REPORTING led the answer; (b) trick refused in words —
"not mentioned in the records … no movement of a ladder is
recorded"; (c) embed figures quoted exactly, "173 ms" and
"181 ms"; (d) shelf named; (e) follow-up resolved to red via
history; (f) "The dock-cam is not reporting, so I can't confirm
if everything is normal" — the bench's cross-model (f) failure,
fixed by the digest, not the model. Loop totals 2.3–4.3 s per
turn (brain 0.6–1.1 s, STT 1.1–1.6 s, resident TTS 0.5–1.9 s).
The **v1 acceptance also stays green against v2 code** (run
twice; final: transcript overlap 1.0, reply cites the staged
event, wall 5.07 s) with the LFM2 fallback as its brain.

Two honest residuals, recorded not smoothed: in one (c) answer
the brain appended "The porch-cam is not reporting" when porch
was fresh — prose-level staleness claims are NOT fenced by the
id/number self-check (a v3 could check not-reporting claims
against digest meta too) — and it once used an event id loosely
as a stream reference, which passes the check because the id
exists. Also, whisper-tiny.en hears "dock" as "dark"; the brain
coped both runs.

Tenancy note: :8295/:8296 were already down when this lane first
probed (18:04) and are down at its finish — never signalled,
never touched; every SIGTERM in this story was thor-admit's
guard acting on this lane's own unleased launches. Test
deployments used `~/confluence-play/slice2/app-v2/` and scratch
ports 8310–8332, all stopped and verified free at the end.

## Presence v3 — the claim checker (2026-11-01)

v2 fenced ids and numbers; its two residuals were prose-shaped:
a false staleness claim in plain words ("The porch-cam is not
reporting", said of a fresh stream) and an event id used loosely
as a stream reference. v3 fences both mechanically, the same
way: `claims.py` (stdlib-only, deterministic) runs in /hear
between trim and the v2 id/number check, verifying every
CHECKABLE claim in the reply against the digest's computed
stream states (which `ledger_digest` now exports as meta:
`streams` + `stream_states`). Nothing is judged by a model.

**Checker rules.**
- *Stream-state claims.* A sentence asserting a stream is/isn't
  reporting, healthy, down, silent… is checked against that
  stream's computed state. Attribution is **clause-local**: the
  sentence is split on commas/semicolons and contrastive
  conjunctions (but/while/whereas/yet); a mention takes the
  nearest state predicate in its own clause, and a clause with
  no state predicate makes no state claim.
- *Entity references.* A bracketed citation naming a stream
  (stream-name-as-event), a bare event id carrying a stream
  predicate with no stream in its clause (event-id-as-stream),
  and a state claim about a "-cam" name the digest doesn't
  carry (unknown stream).
- *False calm.* "Everything is normal / all cameras are fine"
  while any stream is NOT REPORTING (sentence not itself
  negated).
- *Replacement.* A failed sentence is replaced, before TTS,
  with the template truth — "The porch-cam is reporting
  normally." / "The dock-cam is not reporting — last heartbeat
  2 hours ago." (truths for every stream the sentence claimed
  about) — or the safe template for referentially broken
  sentences. Each violation lands in the receipts with the
  original sentence quoted; the receipt's `reply` field is
  exactly what the TTS stage speaks, so a corrected receipt is
  proof the corrected text is what was said. Correct claims
  pass byte-identical.

**Unit tests** (`test_claims.py`, runs anywhere): **23/23** —
the two v2 residuals, invented traps for every class, correct
claims (incl. a true mixed sentence and the battery's own (f)
answer) passing untouched.

**Stub-fed traps** (`acceptance_v3.py`, Part 3): a test hook
(`PRESENCE_BRAIN_STUB_FILE`, re-read per call) forces adversarial
brain outputs through the full /hear loop. **8/8 caught and
replaced before TTS** (receipt `reply` = corrected text,
`reply_raw` = the trap, audio non-silent); **2/2 correct
controls passed byte-identical** with zero claim violations:

| forced brain output | spoken instead | violation |
|---|---|---|
| The porch-cam is not reporting. | The porch-cam is reporting normally. | false_stale_claim |
| Dock-cam-41 is not reporting. | I don't have a record of that. | event_id_as_stream |
| The phone-cam is not reporting. | The phone-cam is reporting normally. | false_stale_claim |
| The dock-cam is reporting normally. | The dock-cam is not reporting — last heartbeat 2.0 hours ago. | false_healthy_claim |
| The phone-cam-12 camera is down. | I don't have a record of that. | event_id_as_stream |
| [porch-cam] shows no changes reported. | I don't have a record of that. | stream_name_as_event |
| The garage-cam is not reporting. | I don't have a record of that. | unknown_stream |
| Everything is calm and normal right now. | The dock-cam is not reporting — last heartbeat 2.0 hours ago. | false_calm |

**Battery, reported as run — twice.** The v2 seven questions
were run through the full loop with the winner brain leased
(and released) in both runs; the v1 rerun stayed green both
times (overlap 1.0). Neither run reached v2's 7/7, and both
failures sit at the STT→brain seam, not in the checker:

- *Run 1: 6/7.* (c) failed because whisper-tiny transcribed
  the embed question as "Hello, I'm Mar the camera in Bed's
  taking right now" — no figures were ever produced. The brain
  then fabricated a stream from the garble ("The bed-cam is
  not reporting") and **the checker caught it live**
  (unknown_stream → safe template) — the fence's first wild
  catch. (f) exposed a checker bug: nearest-predicate-in-
  sentence attribution fenced the brain's TRUE sentence "The
  porch-cam shows no changes, but the dock-cam is not
  reporting…" as a false porch claim. Fixed by clause-local
  attribution (above), with the sentence added to the unit
  tests verbatim.
- *Run 2 (fixed checker): 6/7.* Zero claim violations across
  all seven answers — the checker touched nothing. (c) passed,
  quoting 173 and 181 exactly; (f) passed unfenced. (a)
  failed: whisper heard "the dark camera", the brain echoed
  the mangled name and never reached for the toolbox event —
  the failure is present verbatim in `reply_raw`, upstream of
  every fence. Rotating (c)-then-(a) failures across runs,
  both from whisper-tiny's known "dock"→dot/dark garbling
  (recorded in v2), are the battery's current noise floor;
  v3 claims no battery improvement and no battery regression.

Deployments used `~/confluence-play/slice2/app-v3/`, scratch
ports 8312–8333, winner leased on 8321 via brain-server.sh and
released after each run (unit verified inactive). At finish:
no app-v3 processes, no piper workers, stub file removed, the
Slice-1 soak untouched and alive. (Port 8321 was re-taken after
run 2 by the Slice-1 console's app.py — not this lane's
process; identified read-only and left alone.)

## From-the-chair acceptance — PERFORMED (2026-11-02)

The Amendment-2 headline test, open since Slice 2 shipped, was
performed by Casey in person: ProArt browser (Chrome) → the
presence page served from the Thor → hold-to-talk conversation
against the LIVE Slice-1 soak ledger (via the read-only rendered
ledger view; the soak's files were never written).

- Question (spoken): "What has changed in the last hour?"
  Transcript exact. STT 436 ms, brain 2,620 ms, TTS 252 ms.
- Reply grounded in real verdicts from that morning
  ([proart-cam-114023] tiles 12 at 11:43 AM, plus two more
  11:4x events — the homeowner's own activity at the desk);
  grounding violation null, claim_violations [], reply_raw ==
  reply (every fence passed it untouched). Audio returned to
  the page. Receipt in the Thor play area (app-v3/receipts.jsonl,
  ts 1793652288.8).
- The road here is part of the record: the first attempt failed
  silently because browsers deny getUserMedia on plain-http LAN
  origins (secure-context rule). It worked only after the
  insecure-origin flag was set in Casey's Chrome. PRODUCT
  REQUIREMENT, now named: presence must ship a certificate
  story (installer-issued local cert or equivalent) — a
  household member cannot be asked to flip browser flags — and
  the page must detect the insecure context and SAY so instead
  of failing silently. Both are polish-backlog items.
- Known wart visible in the performed reply: the 64-token cap
  clipped the final sentence mid-phrase ("at 11:"). Brevity
  enforcement stays, the cap/trim interplay needs a cleaner cut.
