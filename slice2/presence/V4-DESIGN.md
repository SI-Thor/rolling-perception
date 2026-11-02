# Presence v4 — real-time, interruptible voice (DESIGN ONLY)

Status: design, 2026-11-02. No code, no downloads, no Thor changes —
the Slice-1 soak and the live v3 presence stack are running and this
lane touched neither. Casey direction (2026-11-02): presence becomes
a real-time voice system, tappable on the fly — the user can
interrupt (barge-in) while the system is speaking. Enabler: llama.cpp
v0.8.0 (ggml-org) ships a realtime voice stack. This document designs
v4 on top of it, under the standing rule that **the v3 fences are
non-negotiable**: verdict-only grounding, per-sentence claim checking
BEFORE speech, health numbers quote-only. A design that cannot hold
the fences is not a candidate, however good it sounds.

## 0. What v0.8.0 actually ships — verified vs unverified

Verified from the v0.8.0 release notes (ggml-org/llama.cpp, release
page read 2026-11-02):

- **`/v1/realtime`** — server endpoint implementing the OpenAI
  Realtime protocol for conversation and transcription
  (PRs #31269, #30636). **Tool calls in /v1/realtime** are supported
  (#31287). **`response.done` is sent after the committed audio
  drains** (#30994) — the server's notion of "done" is drain-based,
  which §3 leans on and fences against.
- **`POST /tts`** — endpoint for text-to-speech models (#26603).
- **`mtmd_audio_stream`** — experimental streaming-audio API in
  mtmd: PCM fed as it arrives becomes decoder-ready embedding rows
  (#30629; first consumer was voxtral-realtime). Audio generation
  is stateful via `mtmd_gen_state` (#30902).
- **LFM3-Audio-2B and LFM3-Omni-2B** — single models doing ASR, TTS
  and voice chat, with streaming audio input and output (#31257).
  New TTS types `SOPRANO` and `LFM3A` in mtmd.
- **Router propagates client disconnects to the child task**
  (#29707) — cancel/disconnect is intended to reach the worker, not
  just close the socket.

UNVERIFIED (not stated in the release notes; the bench plan's spike
B0 exists to resolve each of these before any build):

- U1. Whether llama.cpp's /v1/realtime implements **server-side VAD
  / turn_detection** with `input_audio_buffer.speech_started`
  events, and whether speech onset auto-cancels an in-flight
  response (OpenAI-protocol behaviour) or the client must send
  `response.cancel` itself.
- U2. What `response.cancel` does to in-flight generation on
  llama.cpp: how promptly generation stops, how much already
  committed audio continues to be emitted before `response.done`.
- U3. Audio wire format and sample rates on /v1/realtime and /tts
  (the OpenAI protocol's PCM16/24 kHz convention is assumed, not
  confirmed for this server).
- U4. Whether streamed **transcript text deltas lead the audio
  deltas** for the same response (load-bearing for Shape A's fence
  variant, §2.3).
- U5. Whether LFM3-Audio can be driven in **split modes** — ASR-only
  (transcription session) and TTS-only (via /tts) — or only as an
  end-to-end voice-chat model; and whether externally authored
  assistant text (a `conversation.item.create` assistant message)
  is spoken **verbatim** by a following response.
- U6. LFM3-Audio/Omni quality and latency on the Thor (sm_110):
  no numbers exist yet. All LFM3 performance expectations in this
  document are unmeasured.

## 1. Target experience

### 1.1 The session

- A session is **opened deliberately** — the user opens the page and
  starts the session; the LIVE indicator is lit for exactly the
  session's lifetime and dies with it (Amendment 2 discipline,
  unchanged). The v3 secure-context product requirement carries
  over unchanged: presence ships a certificate story; the page
  detects an insecure context and says so instead of failing
  silently.
- **Default mode is open-mic conversation inside the session.** No
  button is held. The user speaks; the system answers in streaming
  audio; the user may interrupt at any moment (§1.2). Listening
  exists **only inside an open session** — barge-in is not ambient
  listening (§5).
- **Fallback mode is v3's**: tap-to-toggle / hold-to-talk,
  half-duplex, one tap away in the page, for noisy rooms, shared
  spaces, and anyone who prefers a floor they control by hand. The
  fallback is a mode of the same session, not a separate app.
- The session ends on explicit close or an idle timeout
  (design default 10 min without a completed turn; configurable).
  Session open/close are receipted.

### 1.2 Interruption semantics (the "tappable" contract)

An interruption is any of: the user **starts speaking** (voice
barge-in, detected by VAD onset), or the user **taps** the talk
control / presses the key. On interrupt:

1. **Silence, fast.** Heard audio stops within the budget of §1.3.
   The client discards its playback buffer immediately; it does
   **not** wait for the server's drain-based `response.done`.
2. **The unspoken remainder is discarded, never resumed.** Whatever
   the reply still had to say is dropped — released-but-unplayed
   audio, synthesized-but-unreleased sentences, and ungenerated
   text alike. The next system utterance is a fresh response to the
   user's new turn. In the spoken history the interrupted reply is
   recorded as `[interrupted after sentence k]` so the brain never
   "continues" a thought the user cut off.
3. **The floor passes to the user.** The system is listening from
   the moment of the interrupt; the user's interrupting speech is
   the new turn's audio, not noise to be waited out. (Barge-in
   speech that turns out to be a cough or a "mm-hm" shorter than
   the VAD minimum simply becomes a very short turn; the system
   answers it as it would any turn — likely by asking, briefly.
   No special backchannel machinery in v4.)
4. **The interruption is receipted** (§2.4): source (vad|tap),
   signal→silence milliseconds, samples received / played /
   discarded for the killed response, sentences released vs
   discarded, and the server's cancel→`response.done` drain time
   (bookkeeping; a long drain is a cost leak and is reported, not
   waited on).
5. **The system never barges in on itself.** Its own TTS output
   must not trip the VAD: the page requests `echoCancellation`
   on the mic stream, and the bench (B1) measures the false-
   interrupt rate with AEC on and off. A self-interrupt is a
   defect, counted like any other false event.

### 1.3 Latency budgets (design targets, to be benched in §4)

| Quantity | Budget | Notes |
|---|---|---|
| Interrupt signal → silence, tap | **p50 ≤ 150 ms, p95 ≤ 300 ms** | signal = pointerdown timestamp |
| Interrupt signal → silence, voice | **p50 ≤ 200 ms, p95 ≤ 300 ms** | signal = VAD onset (see below) |
| End of user speech → first heard audio | **p50 ≤ 900 ms, p95 ≤ 1,800 ms** | v3 full loop was 1.3–4.3 s per turn |
| Claim-check cost per sentence | **≤ 10 ms** | claims.py is deterministic regex; measured class is sub-ms–ms |
| Fence cost to first audio | **≤ 400 ms** vs an unfenced streamer | §3.2; steady-state cost after sentence 1 ≈ 0 |

The 300 ms interrupt ceiling is the "tappable" number: below ~300 ms
from signal to silence, an interruption feels like touching the
system; above it, it feels like filing a request. The budget is
dominated by terms we control, in order: (a) **client playback
buffer depth** — the page must never hold more than ~120 ms of
unplayed audio; (b) VAD onset detection — a low-threshold energy
pre-trigger on the client (30–60 ms class) for the tap-fast path,
with the server's VAD (if U1 holds) as confirmation, not as the
first signal; (c) cancel propagation — LAN RTT is 5–15 ms class on
this network; the rest is server handling, measured in B0/B1.
"Signal" is defined honestly: for voice, it is the acoustic onset
as timestamped by the client VAD, not the moment the server agrees
speech started — the bench reports both.

## 2. Architecture on v0.8.0 — two shapes

Both shapes keep: the ledger and its digest exactly as v3
(`ledger_digest` produces digest text + grounding meta: verdict ids,
per-stream computed states, quote-only health figures); the brain
exactly where the bench put it (**Qwen3-Coder-30B-A3B Q4_K_M** under
a thor-admit lease; LFM2-1.2B the named fenced fallback); claims.py
and the v2 grounding check as the only path from brain words to
speakers. They differ in who owns the audio path and the words.

### 2.1 Shape A — LFM3 voice cell, brain as a tool

llama-server runs **LFM3-Audio-2B (or Omni-2B)** behind
`/v1/realtime`. The browser is the realtime client. The model does
ASR + conversation + TTS in one pass, streaming both ways. Our
presence service is demoted to a **tool/ledger service**: it exposes
the digest to the model as realtime tool calls (tool support
verified, #31287) — the model asks for verdicts/health, gets the
digest payload, and answers in its own words, in its own voice.

- *Digest*: built by our service per tool call, identical content
  to v3's. But the model decides **whether and when** to call, and
  what to do with what returns. Grounding degrades from a hard
  pipeline property to a prompt-and-tool discipline.
- *claims.py*: **has no natural seat**. The model authors and
  speaks in one atomic pass; there is no text bottleneck where a
  checker can sit before speech. The only fence-compatible variant
  is the *playback gate* (§2.3), which depends on U4.
- *Latency*: potentially the best first-audio of any shape (one
  model, no seams) — unmeasured (U6).
- *Brain-bench problem*: a 2B model takes the conversational chair
  that a 30B bench winner currently holds. The brain bench's
  recorded lesson is that small models fabricate (LFM2-1.2B
  invented a health figure; it serves only fenced, as fallback).
  In Shape A the fabrication would be **spoken with no checker in
  front of it** — precisely Finding 1's fluency trap at the
  presence layer (docs/FINDINGS-CFC-JEPA-V2.md: the judge scored
  the polished dangerous answer 0.961 "settled +").

### 2.2 Shape B — cascaded cells, realtime as transport (RECOMMENDED)

The v3 pipeline, streamed. llama.cpp v0.8.0 supplies the audio
plumbing; every cognitive stage stays a separate cell with the
text bottleneck intact:

```
browser ⇄ (WebSocket, our page) ⇄ presence service
   user audio up ──► /v1/realtime transcription session ──► transcript events
   transcript ──► ledger_digest (unchanged) ──► brain (Qwen3-Coder, streaming)
   brain tokens ──► sentence segmenter ──► RELEASE GATE (§3)
        per sentence: trim → claims.py → grounding check → release queue
   released sentences ──► TTS cell ──► audio chunks ──► browser playback buffer
   TTS cell: resident Piper (incumbent) or LFM3 TTS via POST /tts (candidate)
```

- *Inbound leg*: the presence service holds a `/v1/realtime`
  session to llama-server in transcription configuration and
  streams the user's PCM up as it arrives (the `mtmd_audio_stream`
  pattern server-side); transcript deltas/finals and (if U1 holds)
  VAD turn events come back as protocol events. Whisper-tiny
  (faster-whisper, in-process) remains the fallback ASR and the
  battery reference. If llama.cpp's realtime turns out to be
  conversation-only, the inbound leg falls back to v3's decode →
  faster-whisper path with client VAD — the shape survives U1
  failing; only the streaming-ASR latency win is lost.
- *Digest*: built by the presence service at turn start, exactly
  as v3 — before the brain sees anything, from files, tolerantly.
  A snapshot: checks later in the turn run against this snapshot
  (§3.3).
- *claims.py*: sits in the release gate, on complete sentences,
  before any audio for that sentence exists (§3). Same module,
  same rules, same replacements.
- *Outbound leg*: released sentences go to the TTS cell one at a
  time. Incumbent: the resident Piper worker (252–287 ms class
  warm; short sentences 120–225 ms). Candidate: LFM3 TTS via
  `POST /tts` — it replaces Piper only if B4 says it wins, and it
  changes nothing upstream of itself: it renders fence-passed text,
  like Piper does. Audio streams back to the browser, which keeps
  its playback buffer ≤ ~120 ms deep (§1.3).
- *Interruption*: browser VAD pre-trigger or tap → presence
  service cancels the turn: brain stream aborted, gate queue
  purged, TTS queue purged, browser told to flush; any realtime
  response in flight gets `response.cancel`. §3.4 details the
  fencing that makes "cancelled" mean silent.
- *Latency budget per stage* (targets, B-series benches verify):
  streaming ASR final ≤ 250 ms after end-of-speech; digest
  ≤ 50 ms (file reads, v3 class); brain to first sentence
  ≤ 450 ms (65 tok/s class brain, ~20-token first sentence);
  gate ≤ 10 ms/sentence; TTS first sentence ≤ 250 ms; network +
  buffer ≤ 150 ms. Sum ≈ the §1.3 first-audio budget.

### 2.3 Shape A′ — the playback-gate variant (spike-gated, not recommended now)

If B0 proves U4 (transcript deltas lead audio deltas by at least a
sentence), Shape A gains a fence: a gate proxy between server and
speaker withholds each sentence's audio until that sentence's
transcript completes and passes claims.py + the grounding check —
fence-before-*heard*, though not fence-before-*generated*. This is
weaker than B's gate in three ways: the digest/tool discipline
problem of §2.1 is untouched (the model may never call the tool,
or may speak around what it returns); a failed sentence's audio
already exists and must be *replaced mid-buffer*, so the spoken
stream splices the model's voice against template text rendered
by a different voice; and the whole variant rests on an unverified
ordering property of one server version. **Verdict: record the
variant, let B0's U4 measurement decide whether it is even
possible, do not design the product on it.** If U4 fails, Shape A
is not fence-compatible at all and is closed, not merely deferred.

### 2.4 Receipts (both shapes; B's are complete, A's are partial)

Receipts stay one JSONL line per turn in `receipts.jsonl`, v3
fields preserved (`reply` = **exactly what was spoken** — in v4,
the concatenation of *released* sentences only), extended with:

- `turn_id`, `response_ids` (protocol ids where they exist);
- `mode`: `open` | `fallback-ptt`; `session_id`;
- per-sentence gate records: `sentences[]` with `text`, `check_ms`,
  `violations`, `released: bool`, `synth_ms`;
- `reply_unreleased`: text generated but never released
  (interrupted or gate-held) — present for audit, never spoken,
  never conflated with `reply`;
- `interrupt`: null or `{source: vad|tap, signal_to_silence_ms,
  samples_received, samples_played, samples_discarded,
  sentences_released, sentences_discarded, server_drain_ms}`
  (drain = cancel→`response.done`, bookkeeping only);
- stage timings as v3 (decode/stt/digest/brain/tts) plus
  `first_audio_ms` (end-of-user-speech → first sample handed to
  the playback buffer).

In Shape A, per-sentence gate records and `reply_unreleased`
cannot be produced (no gate, no bottleneck) — the receipt itself
documents the downgrade, which is part of why A is not recommended.

### 2.5 Recommendation

**Build Shape B.** Adopt v0.8.0 for what it verifiably provides —
streaming audio transport (`/v1/realtime`, `mtmd_audio_stream`),
a `/tts` endpoint, drain-based completion bookkeeping — and keep
the cascaded cells, the digest, the bench-winning brain, and the
gate. Treat LFM3-Audio/Omni as **bench candidates for the ASR and
TTS cells individually** (split modes, U5), never as the author of
spoken words, unless and until B4's trap battery says otherwise.

Deciding evidence (benches, §4 — not taste): B0's resolution of
U1/U2/U4/U5; B4's rerun of the v3 battery (7 questions, 8 stub
traps, 2 controls) against LFM3 in each seat; B1's interrupt
distribution. If LFM3 end-to-end passes the full trap battery
unfenced — no invented numbers, no false calm, no loose ids —
Shape A may be re-proposed with that battery as its evidence.
Nothing in its class's record (brain bench, Finding 1) predicts
that outcome.

## 3. The hard problem — fences in a streaming world

v3's safety is an accident of its shape: the whole reply (≤ 2
sentences, ≤ 45 words, 64-token cap) exists as text before Piper
sees a word of it. Streaming removes the accident. v4 must make
the property deliberate.

### 3.1 The release gate

**Rule: audio for sentence n is released only after sentence n
has passed, in order — trim, claims.py, the v2 grounding check.**
Mechanically:

1. The brain streams tokens into a sentence segmenter (the same
   sentence splitting claims.py uses, so "a sentence" means one
   thing everywhere in the system).
2. Each completed sentence runs the v3 trim rules, then
   `check_claims` against the turn's digest meta, then
   `grounding_check` (citations ∈ digest ids; every number
   verbatim in digest or question).
3. A passed sentence enters the release queue and is synthesized
   and streamed. While sentence n plays, sentence n+1 is being
   generated, checked, and synthesized — the pipeline overlaps,
   so the gate's cost is paid once, at the first sentence.
4. The 2-sentence / 45-word brevity discipline is unchanged; it
   is what makes the gate cheap. v4 does not lengthen replies to
   show off streaming.

### 3.2 What the gate costs (design targets)

- Per-sentence check: claims.py + grounding check are
  deterministic string work — **≤ 10 ms per sentence** budget,
  expected sub-ms–ms (B3 measures the real distribution).
- First audio: an unfenced streamer could start speaking after
  ~3–5 words; the gate waits for sentence 1 to complete
  (~20 tokens at the brain's measured 65 tok/s ≈ 300 ms) plus
  check plus first-sentence synthesis (~120–250 ms). **Fence cost
  to first audio: ≤ 400 ms** against the unfenced figure, inside
  the §1.3 budget. Steady state: zero added latency — sentence
  n+1's check hides entirely under sentence n's playback.
- What we refuse to buy back: token-level TTS (speaking partial
  sentences) would return ~300 ms of first-audio latency at the
  price of the entire fence. Not a trade on offer.

### 3.3 A failing sentence mid-stream

- The sentence is **never synthesized**. claims.py's replacement
  (template truth for state failures, the safe template for
  entity failures) takes its place in the release queue, in the
  same position, and is receipted with the original quoted —
  exactly v3's semantics, moved one boundary earlier.
- If the failure is in sentence 1, the user hears the template
  truth as the whole opening — same as v3 today.
- Generation continues for later sentences (the reply cap is 2;
  a replaced sentence 1 does not poison sentence 2, which is
  checked on its own text). If the brain's stream itself is
  garbage (empty, runaway), the turn ends with the safe template
  and a receipt saying so.
- **Snapshot rule**: checks run against the digest snapshot taken
  at turn start. If a stream's real state changes mid-reply (a
  heartbeat crosses its tolerance while sentence 1 plays),
  sentence 2 is still checked against the snapshot — the reply is
  a statement about the turn's evidence, and the new state is
  next turn's news. The snapshot's age is receipted. (The
  alternative — re-checking against live state mid-reply — can
  make two sentences of one reply contradict each other; worse,
  and unreceiptable.)

### 3.4 Interruption, drain, and zombie audio

The release notes say `response.done` arrives **after the
committed audio drains** — the server's completion is defined by
its buffer emptying, not by our intent. Two consequences, both
designed for:

1. **We never wait for drain.** On interrupt, the client flushes
   its playback buffer and the turn is over from the user's side
   within the §1.3 budget. Server-side, `response.cancel` is sent
   (and the presence service aborts brain/TTS work), but
   cancel→`response.done` is measured and receipted as
   `server_drain_ms` — a server that keeps generating after
   cancel is burning Thor GPU on a dead turn, and the receipt is
   how we'd know.
2. **Late audio is fenced by response id, and supervised by
   counters — never by process existence.** The fleet has
   already paid for this lesson once (ffmpeg `-stream_loop` +
   cuvid zombies at the loop seam: processes alive, frames
   stopped — supervise counters, not processes; slice2 player
   record). The v4 form of the rule: every audio chunk carries
   its response id; after a cancel, chunks for that id are
   **dropped on arrival** and counted. Per response, the client
   reconciles `samples_received` vs `samples_played` vs
   `samples_discarded` at `response.done` (or at session close);
   a response whose counters don't reconcile, or that emits audio
   more than 500 ms after its cancel was acknowledged, raises a
   `zombie_delta` receipt. Silence after interrupt is a measured
   property of counters, not a hope about processes.

The unspoken remainder is discarded at **every** layer on
interrupt, and each layer's discard is counted in the receipt:
ungenerated text (brain stream aborted), generated-unreleased
sentences (gate queue purged), synthesized-unplayed audio (TTS
queue purged), buffered-unplayed samples (client flush, counted
as `samples_discarded`).

## 4. Bench plan (design only — Thor time is soak-occupied)

All benches run later, on scratch ports, brain under thor-admit
lease, soak untouched — the v2/v3 lanes' tenancy discipline.

- **B0 — protocol spike** (resolves §0's unverified list). Against
  a scratch llama-server v0.8.0: does /v1/realtime emit VAD
  speech_started/stopped events, and does onset auto-cancel (U1)?
  On `response.cancel`: time to last audio delta, time to
  `response.done`, tokens generated after cancel (U2). Wire
  format/rates (U3). Do transcript deltas lead audio deltas, and
  by how much (U4)? LFM3-Audio split modes: transcription-only
  session; /tts rendering; verbatim-speak test of injected
  assistant text (U5). Deliverable: each U answered with a
  capture, or marked still-unverified with the reason.
- **B1 — interrupt latency.** A long staged reply (the 2-sentence
  cap lifted *for the bench only*, via bench config, so there is
  something to interrupt) plays; interrupts fire at randomized
  offsets, n ≥ 50 per mode: (a) tap; (b) spoken barge-in at
  controlled level (a recorded phrase played at measured SPL at
  the mic position). Measure signal→silence (client sample
  counters give the ground truth of when sound stopped), report
  p50/p95/max against the §1.3 budgets. Plus the **false-
  interrupt rate**: 50 uninterrupted replies with AEC on and off;
  any self-triggered cancel is a failure counted by name.
- **B2 — first-audio latency.** End-of-user-speech → first heard
  sample, across the v3 battery's seven questions, p50/p95,
  compared against v3's recorded 1.3–4.3 s loop totals and the
  from-the-chair turn (STT 436 ms + brain 2,620 ms + TTS 252 ms).
- **B3 — fence overhead.** Gate ms per sentence (distribution over
  the battery + the 8 stub traps); first-audio delta between the
  gated build and a deliberately unfenced bench build on identical
  turns. The unfenced build is a measuring instrument, never a
  deployment candidate.
- **B4 — voice-cell quality, seat by seat.** (i) ASR: LFM3-Audio
  transcription vs faster-whisper-tiny on the battery's spoken
  questions — word-error on the transcripts, with the recorded
  dock→dark/dot garble class scored separately (it is v3's noise
  floor and the first thing a better ASR must fix). (ii) TTS:
  LFM3 (via /tts) vs resident Piper on identical fence-passed
  texts — synthesis latency by length, intelligibility by
  ASR-round-trip, and Casey's ear at acceptance. (iii) End-to-end:
  LFM3 voice chat (Shape A) run **unfenced** through the v3 trap
  battery — the 8 stub traps become spoken prompts/situations;
  invented numbers, false calm, loose ids are counted. This is
  the evidence §2.5 says could reopen Shape A; it is also the
  evidence expected to close it.
- **B5 — acceptance, from the chair again.** Live ledger (the
  soak's, read-only view, as performed 2026-11-02), the seven
  battery questions, plus **three deliberate mid-sentence
  interruptions**: one tap, one voice barge-in, one during a
  template-truth replacement sentence. Pass requires: all three
  interrupts inside the §1.3 budget by the receipts' own counters;
  no reply ever resumes after interruption; zero grounding/claim
  violations in released text; the interrupted turns' receipts
  reconcile (received = played + discarded); and the human at
  the chair reports it felt tappable — the receipts alone don't
  get to call that one.

## 5. What does not change

- **Presence is a platform interface, not part of telltape.** The
  anti-bloat line from the extraction stands: telltape's ledger
  is an input to presence; presence's voice machinery never
  enters the tool.
- **Amendment 2's refusal of always-on ambient mic perception
  stands.** v4 listens inside a deliberately opened, visibly live
  session, and nowhere else. Barge-in widens the duplexity of a
  session; it does not widen when the system has ears.
- **The fences stand**, verbatim: verdict-only grounding (events
  enter as published verdict records with ids; health from
  computed state lines only), health numbers quote-only and
  template-rendered, per-sentence claim checking before speech —
  in v4, before *release* — with template-truth replacement and
  receipted violations.
- **Jev stays advisor-only.** Nothing in the realtime stack gives
  a judge a gate; the constitution is unchanged.
- **The brain is earned, not assumed.** Qwen3-Coder-30B-A3B holds
  the chair on its bench record; any challenger — LFM3-Omni
  included — takes it by beating the battery, behind the fences,
  or not at all. Small models serve fenced or not at all
  (LFM2-1.2B fallback precedent).
- **Tenancy stands.** Brains run under thor-admit leases; test
  deployments use scratch ports and play-area directories, are
  stopped and verified free afterwards, and the soak is never
  touched. Casey's decision-model tenants (:8295/:8296) are not
  ours to start, stop, or borrow.

---

*Sources: llama.cpp v0.8.0 release notes (ggml-org/llama.cpp,
read 2026-11-02) for §0's verified list — PR numbers are the
release's own. Protocol behaviours listed as U1–U6 are explicitly
unverified against this server; third-party descriptions of the
OpenAI Realtime protocol were used only to phrase the questions
B0 must answer, never as evidence about llama.cpp's
implementation. Presence facts, numbers, and battery records are
from this directory's README (v1–v3 + from-the-chair acceptance)
and claims.py.*
