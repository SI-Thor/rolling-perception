# Presence v4 — B1 Spike Result

**Date:** 2026-11-07 (America/Anchorage; work spanned the night of 2026-11-06→07) · **Boxes:** Thor (Jetson AGX, sm_110) + Orin (Jetson Orin Nano Super) · **Spike dirs:** Thor `~/confluence-play/presence-v4/` (server, harness, results), Orin `~/b1-spike/` (page, host, clips)
**Production presence was not modified or restarted.** The presence backend (:8330, PID 141299) and brain (:8310) were only ever called through their APIs; the spike's own server, Piper worker, browser and audio nodes ran on spike ports/devices and have been torn down (§7).

## 1. The design under test (restated)

B0 proved the streamed Shape B cascade — ledger digest → brain → per-sentence claims gate → Piper — over loopback with a simulated player and ASR bypassed, and named B1 as its next step: the same cascade on the transport that measured PASS (streaming chat completions + connection abort), through a **real browser/audio-device path**, adding the two things loopback could not measure — output-buffer behaviour after a flush, and the false-interrupt behaviour of a client-side VAD with echo cancellation on/off. Acceptance budgets (design §1.3, as applied in B0): **interrupt signal→silence p95 ≤ 300 ms** with zero post-signal audio; **first-audio p50 ≤ 900 ms / p95 ≤ 1,800 ms** on the transcript-ready leg B0 measured.

B1's path, end to end: a web page on the Orin (Firefox 158, headless, served from `http://127.0.0.1:18711` — localhost is a secure context) captures a microphone with `getUserMedia`, endpoints it with a client energy VAD (700 ms hangover), streams 16 kHz PCM over a WebSocket across the LAN (Wi-Fi) to a spike server on the Thor (`harness/b1_server.py`), which runs the B0 cascade with two changes: the brain is the **production resident on :8310** (B0 used a dedicated spike brain), and the ASR leg is **in the path** — `v3.transcribe()`, faster-whisper tiny.en on CPU, its cache having been restored on 2026-11-06 (B0 wall 4 is closed). Per-sentence PCM chunks (22050 Hz) stream back over the same socket to a Web Audio player in the page; an analyser tap on the page's own output graph is the authority for "audible". The interrupt button (and, in the barge-in set, the VAD) fires the B0 abort: close the brain connection, clear the TTS queue, zero the player's gain and stop its sources in the same JS tick.

## 2. Deficits first — what this rig is not

- **The microphone is an electrical mix, not a room.** The Orin has no usable room mic for a spike at 00:30, so the "mic" is a PipeWire loopback source (`pw-loopback`: apps play into a virtual sink `b1feed`; a virtual source `b1mic` carries the mix; question clips are played into it with `pw-cat`, and Firefox is device-selected onto `b1mic` by `deviceId` and sink-routed onto `b1feed` via `PULSE_SINK`). The reply is therefore present in the mic feed at full level — the worst case for echo/VAD questions, the best case for repeatability. Conclusions about VAD/AEC transfer to a real room qualitatively (a room adds delay spread and lower echo level), not numerically.
- **The speaker is a null path.** Playback renders through Web Audio into the loopback; there is no DAC, amplifier or air. "Audible" means *the page's output graph carried the samples*; Firefox reported `outputLatency` 19.5–26.4 ms on this rig. A handset's hardware buffer and speaker path remain unmeasured.
- **Firefox is not a phone browser.** Mobile Safari/Chrome `getUserMedia` and AudioContext behaviour (sample rates, EC implementations, autoplay rules) differ and are unmeasured.
- **The phone itself is still unreachable.** The page ran on the Orin's localhost by the sanctioned workaround; a phone on the LAN cannot open this page with mic rights over plain HTTP. That gap is the owner's, was not relitigated, and is now the *only* unmeasured leg (§8).
- **The brain is shared.** :8310 also serves the agent league's governor traffic. First-token latency shows it: p50 134 ms, p95 1,508 ms across the reported set. The tail in §4 is contention, labelled where it lands.
- **ASR is tiny.en.** Word errors are frequent on Piper-synthesised questions (dock→"dark" in 3 of 12, embeds→"in beds" in 3 of 12, one garbled beyond recognition). Latency numbers are unaffected; transcript quality is reported qualitatively, not as WER.

## 3. What was built

- **`harness/b1_server.py`** (Thor): the B0 harness cascade as a WebSocket server — v3 `ledger_digest()` (real digest: dock-cam, phone-cam, porch-cam), brain streaming against :8310 with abort-by-close, `claims.check_claims` → `grounding_check` → SAFE_REPLY per sentence, spike-owned Piper worker (own socket, as B0). Validated before any browser involvement by `harness/smoke_client.py` (utterance turn + bench interrupt turn; SMOKE PASS, server post-signal sends 0).
- **`spike/b1.html`** (Orin): the trial page — capture with EC on/off, integer-ratio downsample 48→16 kHz, energy VAD with per-run calibration, preroll ring, Web Audio player (per-turn gain, generation counter so post-signal chunks are dropped unscheduled), analyser output monitor, self-driving trial engine, rows beamed to both the Thor server (`harness/b1-results*.jsonl`) and the Orin host log.
- **`spike/b1_host.py`** (Orin): serves the page on 127.0.0.1:18711, collects rows, feeds clips into `b1feed` on the page's request.
- **Trial sets.** Reported first-audio set (run 3): 12 utterances EC-on + 4 EC-off, rotating B0's seven fixture questions, synthesised by the same Piper voice. Interrupt set (run 1): 12 bench-story turns, interrupt fired through the real button handler at a uniform-random 823–2,458 ms after first audio. Barge-in set (run 1): 4 bench turns, a "Stop! Stop talking now." clip fed into the mic mix 900 ms after first audio, VAD as the trigger. Runs 1–2's first-audio sets are **invalid and preserved** (§6); the interrupt and barge-in sets are unaffected by those faults (button/VAD-trigger paths, argued in §6) and are reported from run 1.

## 4. Measurements

### First-audio — run 3, EC-on n=12, EC-off n=4, no errors
*Path label: real browser path. Clocks: all page-side figures are the Orin page's `performance.now()`; server figures are the Thor server's clock and are used only for stage deltas measured wholly on the server.*

| Metric (EC-on) | Value | Bar | Verdict |
|---|---|---|---|
| end-of-speech → first-audio p50 / p95 | **2,533.5 / 3,859.7 ms** | — (new leg) | reported |
| VAD end-of-utterance → first-audio p50 | **1,808.5 ms** | — | reported |
| transcript-ready → first-audio p50 / p95 | **945.0 / 2,303.4 ms** | ≤ 900 / ≤ 1,800 | **marginal miss / miss** |
| server transcript → first chunk sent p50 / p95 | 834.5 / 2,174.5 ms | — | stage |
| browser chunk-receipt → audible p50 / p95 | **86.0 / 95.2 ms** | — | stage |
| ASR (server, per utterance) p50 / p95 | 597.9 / 1,387.4 ms | — | stage |
| brain first-token p50 / p95 | 133.8 / 1,508.2 ms | — | stage |

The decomposition is the finding: **the browser path's own addition over B0's loopback is ~86 ms at the median** (chunk receipt → scheduled → rendered → analyser-confirmed, including the page's 10 ms schedule offset and this rig's ~26 ms reported output latency), and the LAN WebSocket RTT median was 14–22 ms. The bars are missed in the *server* stage, on the shared production brain: when the brain answers promptly (its first-token p50 is 134 ms), the same path's transcript→audio runs land at 621–960 ms — B0's dedicated-brain loopback measured 485.5/696.3 — and the EC-off mini-set, run minutes later, saw no tail at all (first-token p95 147.7 ms; transcript→audio p50 973 ms). The p95 miss is episodic contention with league traffic on :8310, not a property of the transport. End-of-speech → first-audio (the figure a person at the table would feel, ASR and VAD hangover included) is **2.53 s at the median**; B0 could not measure this leg at all.

EC-off (n=4): end-of-speech → first-audio p50 2,337.5 ms; transcript→audio p50 973.0 ms. No underruns in any of the 16 trials; 1–3 sentence chunks per reply.

### Interrupt — run 1, n=12, PASS
*Path label: real browser path; signal = the page's interrupt handler (button, clicked programmatically at the randomised offset — the genuine handler); silence measured on the page's output analyser.*

| Metric | Value | Bar | Verdict |
|---|---|---|---|
| audible audio after signal (analyser) p50 / p95 / max | **35.5 / 43.5 / 44 ms** | ≤ 300 (p95) | **PASS, ~7× margin** |
| trials with any post-signal audio *played* | **0 / 12** beyond the ≤44 ms already-rendering tail | 0 | PASS |
| chunks *sent* by server after the signal | **0 / 12 trials** | 0 | PASS |
| in-flight chunks arriving at the page after the signal | 2 trials × 1 chunk (~224k samples ≈ 10 s of speech each) | — | both dropped unscheduled, never played |
| server sentences discarded after signal | 0–4 per trial (of 512-token bench stories) | — | the abort really was mid-generation |
| strict confirmed-silence (60 ms quiet window + no live sources) p50 / p95 / max | 102 / 786 / 1,389 ms | ≤ 300 (p95) | over — see note |

Note on the last row: the strict figure is definitional, not acoustic — it includes a built-in 60 ms confirmation window and is inflated in the tail by Firefox's `onended` bookkeeping for sources that were scheduled seconds ahead and then stopped (inference from the pattern: trials with a future-scheduled second sentence are the slow ones; the analyser itself shows output ending ≤44 ms in every trial). The quantity the budget exists for — sound the user hears after deciding to interrupt — is the first row.

### Barge-in (voice-stop) — run 1, n=4, exploratory
The pipeline supports voice-stop through the client VAD, as the design required (U1 made VAD the client's job). **Detection in 4/4 trials, no fallbacks.** Feed-start → interrupt: **402/404 ms with EC on; 161/163 ms with EC off.** Post-stop behaviour matches the button set (played-after-signal 36–39 ms; zero post-signal chunks played). Before the stop clip, the reply's presence in the mic feed measured: EC-on 0 and 6 above-threshold VAD frames (max RMS 0 / 0.206); EC-off 19 and 30 frames (max RMS ~0.3). Across the first-audio set, the reply occupies **25–40% of playback frames above the VAD threshold in the mic feed with EC either on or off** (max RMS 0.29–0.44) — an energy VAD left open during playback on this path would false-fire constantly, and echo cancellation does not rescue it; it also appears to *slow* genuine stop-word detection ~2.5×, consistent with the canceller initially treating the stop clip as more of the echo it is suppressing (labelled inference). Endpointing on this transport must be playback-aware: the client knows its own play schedule and must gate or reference-subtract it — the half-duplex discipline the radio-room line already uses, now with a measured reason.

A related artefact, measured in run 3's transcripts: when a trial's listen window opened while the previous reply's tail was still in the loopback mix, the segment started on the tail and whisper transcribed lead-in fragments ("by phone what changed at the dark camera?", "come stop, how long are…"). Timings are unaffected (speech-end still lands on the question), but a production client must mute its endpointing against its own playback timeline for transcript purity as well.

## 5. Walls hit

None new. The B0 walls stand exactly as recorded: `/v1/realtime` refuses the text brain, `/tts` 501s on text-only models, no audio-capable model on the box (LFM3-Audio download remains an owner decision), no server VAD. B1 was built entirely on the transport B0 measured PASS, so none of them were re-struck. B0 wall 4 (the missing faster-whisper cache) was closed by the owner's cache restore on 2026-11-06 and is verified closed here: the ASR leg ran in-path for every reported trial (warm-up transcription at server start: 777 ms including model load).

## 6. Process notes (deficits kept, per doctrine)

- **Run 1's first-audio set is invalid and is preserved as such** (`harness/b1-results-run1.jsonl`, Orin `page-log-run1.jsonl`). The client VAD segmented the system's own reply echo — with EC either way, the reply is a full-level signal in this mic feed — corrupting every trial boundary after the first: first-audio deltas came out negative (audio "before" speech-end), one utterance reached the server as 0.00 s of audio and all four EC-off utterances as silence (the VAD's state machine, left mid-segment by the previous reply, never opened a segment on the re-acquired stream). The interrupt and barge-in sets ran in the same run and are **not** invalidated: the interrupt path does not use VAD segmentation at all (button → flush → analyser), and the barge-in set's use of the echo-saturated feed was its subject, not its flaw.
- **Run 2's first-audio set is also invalid, differently** (`harness/b1-results-run2.jsonl`, Orin `page-log-run2.jsonl`). Two measurement faults: (a) the output monitor stamped "first audio" ~3 ms after the feed call in 9 of 12 trials — the analyser's 2048-sample tail of the *previous* reply, still playing when the turn reset, satisfied the detector before this turn's first chunk existed; (b) the Orin's Minecraft client stream had followed the system default sink into the spike feed (WirePlumber moved it when the defaults were swung), adding game audio to the "mic". Fixes for run 3: first-audio requires this turn's first chunk *and* an observed below-threshold poll after reset; mic/sink routing is per-process (`deviceId` selection in the page; `PULSE_SINK` for Firefox) with system defaults left alone. Run 3's set is the reported one. (One run-2 launch also sat idle for a minute on a URL/regex mismatch in the page's autorun gate — `?autorun=fa` vs `/autorun=1/` — an operator error, fixed in the page.)
- **Two operator errors with the process table**: a `pkill -f` whose pattern matched the operator's own shell command line killed the shell (and, in the first instance, left state ambiguous) — the B0-era lesson about naming one's own processes applies to killing them. No spike or production process was harmed in either instance; state was re-verified from the boxes each time.
- The spike brain question did not arise: B1 deliberately used the production brain through its API, so no thor-admit lease was needed (the spike's own compute is CPU: whisper tiny, Piper, two small Python servers, one headless browser).

## 7. Teardown — boxes left as found

Thor: spike tmux session killed → :8411 free; spike Piper worker verified gone (no leak of the kind B0 hit), stale spike socket removed. Production verified after teardown: presence :8330 HTTP 200 (PID 141299, untouched), brain :8310 `{"status":"ok"}`, production Piper (PID 3768238) alive. Orin: Firefox and the page host stopped (18711 free); `pw-loopback` killed and the temporary null sink destroyed — `wpctl status` shows no spike nodes; system defaults restored (sink = HDMI/DP out, source = built-in stereo) and the Minecraft client's audio stream verified back on its original target. Spike artefacts remain filed: Thor `presence-v4/harness/{b1_server.py, smoke_client.py, gen_clips.py, b1-results*.jsonl, page-log-run*.jsonl, b1-clips/}`, Thor `presence-v4/spike/{b1.html, b1_host.py, probe.html}`, Orin `~/b1-spike/` (page, host, clips, run logs, Firefox profile). No GitHub pushes were made.

## 8. Verdict and named next step

**B1: PASS on the interrupt shape through a real browser path; first-audio marginally over the design bars under shared-brain load, with the overage isolated to the server stage.** Interrupt: audible escape after the signal p95 43.5 ms against a 300 ms bar, zero post-signal audio played in 12/12 trials, zero post-signal sends by the server in 12/12 — B0's loopback result (12.6 ms p95, 0/24) survives contact with a real browser, a real capture/playback graph, and a Wi-Fi LAN hop. First-audio: the browser path adds ~86 ms at the median over loopback; the transcript→audio p50 of 945 ms sits just over the 900 ms bar and the p95 of 2,303 ms over the 1,800 ms bar, on a brain whose first-token p95 (1,508 ms) is set by league contention — a scheduling property, not a transport property. Voice-stop works (4/4), and the run's sharpest design finding is about endpointing: on an open speaker/mic path the system's own voice is a first-class signal in the mic feed (25–40% of playback frames over threshold, EC notwithstanding), so the client VAD must be playback-aware — gated or reference-subtracted — or it will segment, and eventually interrupt on, the system's own speech.

**Named next steps (B2, in order):**
1. **The phone leg.** Everything between the page's APIs and the cascade is now measured; the unmeasured surface is a handset — which first requires the owner's standing decision on LAN HTTPS (or a native shell) before a phone can hold mic rights on this page at all. One sentence version: the remaining gap is a phone browser on this LAN, in a real room, against this page — transport, acoustics and handset audio policy together.
2. **Playback-aware endpointing**, built as measured: VAD gated by the client's own play schedule (and un-gated for a stop-word band), re-running the barge-in set to show the false-fire rate during playback falling to zero while stop detection stays in the 160–400 ms band.
3. **A presence lane on the brain** (or a spike-brain repeat of the first-audio set) to separate the contention tail from the path's own numbers before the p50/p95 bars are judged finally.
4. The B0 owner decisions stand unchanged and still gate the remaining protocol legs: LFM3-Audio (closes U5/U6 and the `/v1/realtime` re-test).
