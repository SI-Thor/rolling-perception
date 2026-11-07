# Presence v4 — B0 Spike Result

**Date:** 2026-11-06 (America/Anchorage) · **Box:** Thor (Jetson AGX, sm_110) · **Spike dir:** `~/confluence-play/presence-v4/`
**Production presence was not modified or restarted.** All spike processes ran on spike ports under thor-admit leases and have been torn down (see §7).

## 1. The design under test (restated)

V4-DESIGN.md's Shape B keeps the v3 presence cascade unchanged — ledger digest → brain (Qwen3-Coder-30B) → per-sentence claims gate (`claims.py` + `grounding_check`, SAFE_REPLY on violation) → Piper TTS — but streams it: brain tokens are segmented into sentences as they arrive, each sentence is gated and synthesised in turn, and an interrupt signal aborts the brain stream, clears the TTS queue and flushes the player so speech stops near-instantly. B0 is the protocol/latency spike that proves or kills this shape against two acceptance budgets — **interrupt signal→silence p95 ≤ 300 ms** and **end-of-speech→first-audio p50 ≤ 900 ms** (design §1.3 fuller table: interrupt p50 ≤ 150 ms; first-audio p95 ≤ 1,800 ms) — and resolves the open protocol questions U1–U6 against llama.cpp's `/v1/realtime` + `/tts` surface. Per the tasking, loopback/simulated audio paths are acceptable if labelled; every measurement below carries its path label.

## 2. What was built

- **Spike brain:** a second, spike-owned `llama-server` from the upstream build that contains the realtime code (`~/llama.cpp-upstream/build-up`, 0.8.0-dev; the production build is 0.7.0-dev and has no realtime strings), serving the same Qwen3-Coder-30B-A3B Q4_K_M model on **127.0.0.1:8410**, alias `spike-brain`, under thor-admit lease **#125** (`run --tier live --peak 23G`; see §6 for why 23G). Production's brain on :8310 was never touched.
- **Protocol probe** (`spike/rt_probe.py`, `spike/probe2.py`): HTTP `/v1/models` + `POST /tts` captures and WebSocket session attempts (conversation and `?intent=transcription`) against :8410, all frames timestamped to `spike/captures/rt-capture.jsonl` / `rt-capture2.jsonl`.
- **Harness** (`harness/v4_harness.py`): the v3 cascade streamed. Live `ledger_digest()` from the unmodified v3 code; brain over streaming `/v1/chat/completions` (abort = close the HTTP connection); sentence segmentation on the token stream; every sentence passed through v3's `claims.check_claims` → `grounding_check` → SAFE_REPLY replacement before synthesis; a spike-owned Piper worker (own unix socket, v3's `piper_worker.py`, en_US-lessac-medium); a simulated real-time **Player** (in-process jitter buffer, ≤120 ms release discipline, 5 ms consumer quanta; flush discards queued samples and silence is consumer-confirmed). Interrupt trials used the design B1 bench shape (storyteller prompt, max_tokens 512, reply-length cap lifted for the bench only), interrupt fired at a uniform-random 300–2500 ms after first audio.

## 3. Protocol probe — U1–U6 verdicts

The realtime endpoint **exists** in the 0.8.0-dev build (route registered in `tools/server/server.cpp`; `server-realtime.cpp`, 1,169 lines; strings live in `libllama-server-impl.so`). It is, however, **gated on audio-encoder models**, and that gate decides most of U1–U5 for this box:

- **U1 (server VAD / `speech_started` / auto-cancel): NO.** No VAD exists anywhere in the server source (no `speech_started`/`speech_stopped`/`server_vad`; `server-realtime.cpp` hard-codes `"turn_detection", nullptr` in the session object). Any VAD in a v4 built on this endpoint must be client-side.
- **U2 (realtime `response.cancel` promptness / post-cancel emission): UNMEASURABLE on this box.** No realtime session of either type can be created with the production brain model — both attempts were refused at session creation (verbatim in §5), so there is no response to cancel. The interrupt property itself was measured on the HTTP-streaming path instead (§4) and passes there by a wide margin.
- **U3 (wire format / rates): PARTIALLY ANSWERED.** Confirmed: WebSocket JSON events; session types `realtime` and `transcription` (`?intent=transcription`); OpenAI-shaped error events; `/v1/models` advertises only `"capabilities":["completion"]` for this model. Audio sample-rate questions cannot be reached without an audio-capable model.
- **U4 (do transcript deltas lead audio deltas): UNANSWERABLE here.** Requires a model with audio output; none exists on the box.
- **U5 (LFM3 split modes — transcription-only, `/tts`, verbatim-speak): BLOCKED.** `~/models/LFM3-Audio-2B/` is an **empty directory** (dated Nov 5 00:27, the cleanup window), and a whole-disk GGUF inventory finds no audio-capable model at all (only Qwen3-Coder-30B and Dory 4B). Separately, the `/tts` route itself exists but refuses a text-only model with 501 (verbatim in §5).
- **U6 (LFM3 quality/latency on sm_110): BLOCKED**, same cause as U5. Downloading LFM3-Audio is an owner decision under the standing model-download rule; it was not worked around.

**Design consequence:** Shape B *as literally transported* — the text brain streamed over `/v1/realtime` + `/tts` — cannot run in this build: the realtime endpoint serves streaming-audio-encoder models (mtmd class: Voxtral Realtime, LFM3-Audio), not the Qwen3-Coder brain. The cascade shape itself, transported over streaming chat completions + connection abort, meets both budgets (§4). The transport named in the design is the wall; the shape is not.

## 4. Measurements

### First-audio — n=24, PASS
*Path label: loopback, transcript-ready → first audio. ASR leg excluded (see §5, wall 4): the fixture questions' known text was fed as the transcript; digest, brain, claims gate, Piper and Player are the real components on the real box.*

| Metric | Value | Bar | Verdict |
|---|---|---|---|
| first-audio p50 | **485.5 ms** | ≤ 900 ms | PASS |
| first-audio p95 | **696.3 ms** | ≤ 1,800 ms | PASS |
| first-audio min / max | 307.5 / 742.1 ms | — | 0 errors in 24 trials |

Supporting stages: brain first-token p50 95.3 ms (max 471.3 ms); claims-gate p95 ≤ 0.81 ms in every trial (the gate is not a latency factor); replies 2–3 sentences, all gated. Raw rows: `harness/results-firstrun.json`.

### Interrupt — n=24, PASS
*Path label: loopback simulated player (no physical audio device in the loop; a hardware output buffer's drain time is NOT measured). Signal = abort decision in the harness; silence = player consumer confirming a post-flush tick with nothing emitted.*

| Metric | Value | Bar | Verdict |
|---|---|---|---|
| signal→silence p50 | **6.5 ms** | ≤ 150 ms | PASS |
| signal→silence p95 | **12.6 ms** | ≤ 300 ms | PASS |
| signal→silence min / max | 2.1 / 12.8 ms | — | 0 errors in 24 trials |

Abort integrity: **0 of 24 trials enqueued a TTS chunk after the interrupt signal**; 2,949,525 queued samples were discarded across trials (queued speech is thrown away, not played out). Raw rows: `harness/results.json`.

## 5. Walls hit (verbatim)

1. Realtime session refusal, both session types, with the production brain model:
   `{"type": "invalid_request_error", "code": null, "message": "The current model does not support realtime transcription."}` — followed by WebSocket close code 1000 within ~1 ms.
2. `POST /tts` with a text-only model: HTTP 501 — `{"error":{"code":501,"message":"this server does not support audio generation","type":"not_supported_error"}}`
3. No audio-capable model on the box: `~/models/LFM3-Audio-2B/` is empty; whole-disk GGUF inventory = Qwen3-Coder-30B Q4_K_M + Dory 4B Q5_K_M + vocab-test files only. (U4/U5/U6 blocked; download is owner-gated.)
4. ASR cache gone: v3's `transcribe()` raises `huggingface_hub.errors.LocalEntryNotFoundError: Cannot find an appropriate cached snapshot folder for the specified revision on the local disk and outgoing traffic has been disabled.` A box-wide find locates no `models--*faster-whisper*` directory and `~/.cache/huggingface` does not exist — the tiny.en cache the v3 code points at was removed (consistent with the 2026-11-05 cleanup). The harness therefore bypassed ASR with known fixture text and labelled the first-audio path accordingly.
   **Side-finding (inference, not probed):** production presence (:8330) loads Whisper lazily through this same code path and cache, so its voice path would hit the same wall on its next transcription request. Production was not probed or touched; restoring the cache is an owner decision (it is a model download).

## 6. Process notes (deficits kept, per doctrine)

- **First interrupt run was invalid and is preserved as such.** All 24 trials errored with `AttributeError: 'NoneType' object has no attribute 'read1'` — closing the HTTP connection from the interrupt thread detached the response's `fp` mid-`read1`, and `run_turn` returned before the interrupt thread had written its measurement (a race). The run's rows are preserved in `harness/results-firstrun.json`. Harness fixes: abort-close is now a clean stream end in the generator, an abort is not recorded as an error, and `run_turn` waits for the interrupt record before returning. The second run (reported in §4) was clean: 24/24, 0 errors.
- **Piper stale-socket race:** the first interrupt re-run died at startup with `ConnectionRefusedError` — a leaked spike Piper worker plus a socket-file-exists readiness check. Fixed: unlink stale socket before start; readiness now proven by an actual synthesis ("Ready check."). Leaked spike workers were killed by PID.
- **thor-admit sizing:** a `--peak 24G` request queued indefinitely alongside the residents (the summed reservations reach a cap at 24+8+24+8); `--peak 23G` admitted instantly as lease #125. The size is honest, not gamed: the identical production server's lease (#100) records `peak_gpu_bytes` ≈ 19.1G.
- Servers launched from a bare SSH exec die with that exec; the spike brain therefore ran under tmux (`v4spike`), which persists independently — and its lease, not the exec, was the lifetime that mattered.

## 7. Teardown — box left as found

Spike brain tmux session killed → lease #125 released (thor-admit status: 3 resident leases, queue 0). Spike Piper worker killed; :8410 free. Production verified answering after teardown: presence backend :8330 HTTP 200 (PID 141299, untouched), brain :8310 `{"status":"ok"}` (PID 3763797, untouched), production Piper (PID 3768238) alive. No GitHub pushes were made.

## 8. Verdict and named next step

**B0: PASS on the shape, WALL on the named transport.** The streamed v3 cascade meets both acceptance budgets on the labelled loopback paths (first-audio p50 485.5 ms vs 900; interrupt p95 12.6 ms vs 300, with zero post-signal audio enqueued). The `/v1/realtime` + `/tts` transport named in the design cannot carry the text brain in the 0.8.0-dev build — it is gated to audio-encoder models — so U2/U4 remain open by construction, and U5/U6 remain open for want of the LFM3-Audio weights.

**Named next step (B1, in order):**
1. Build B1 on the transport that measured PASS — streaming chat completions + connection abort — through a real browser/audio-device path, adding the two things B0's loopback could not measure: hardware buffer drain after flush, and the false-interrupt rate with AEC on/off (design §4 B1), with client-side VAD (U1's answer makes VAD the client's job on any current transport).
2. Two owner decisions gate the remaining legs, neither taken here: (a) restore the faster-whisper tiny.en cache (a download; also repairs production presence's voice path per §5.4), and (b) whether to download LFM3-Audio-2B to close U5/U6 and re-test the `/v1/realtime` transport with a model it will accept.
