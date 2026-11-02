# Results ledger — every headline number, with its source

Measured on the house Thor (AGX Thor, sm_110, driver 595.78) unless
noted. Each row names the document that carries the method and the
receipts. Simulated numbers never appear here.

## The engine (waves 1–2)

| result | value | source |
|---|---|---|
| First output, rolling vs batched (identical work, 400 µs stagger) | **243.5 µs vs 2,528.6 µs (10.39×)**, checksum Δ = 0 | `crates/rolling-perception`, PLAN/DESIGN |
| Checksum identical across x86_64 and aarch64 | 345101.1999 on both | `README.md` quickstart |
| NVRTC hot-swap at launch boundary | **1,000/1,000 swaps**, bit-exact; sm_100 CUBIN fails (error 209), sm_100 PTX runs | `crates/cuda-thor` |
| Persistent kernel for slice work | loses (9–27× slower) — two-stream shadow is the default | `crates/cuda-thor` |
| Adaptive vs fixed stagger under drift | prediction p95 **1.7 ms vs 854 ms**; exact tie at zero jitter | `crates/rolling-adaptive` |
| Cascade gating saving | 71.9% of perceive ops skipped; sheaf energy 132.75 → 95.97 | `crates/rolling-pipeline` |

## Harbor-watch — the first real workload (wave 3)

| result | value | source |
|---|---|---|
| I-JEPA embed latency via the Thor's JEV rack | p50 173 ms / p95 200 ms | `docs/WAVE3.md` |
| Diff-gating vs embed-everything | 312 vs 576 embeds (**−54%**) | `experiments/wave3/` |
| Scene cuts (sequence C) | **16/16 tiles flagged on every landing frame**; precision/recall 1.000/1.000 | `experiments/wave3/report/` |
| Sheaf refine ablation | precision 0.60 → 1.00 at recall 1.00 | `crates/harbor-watch` |
| Reflective Jev (TypeSafe), 15 ground-truth cases | alone P=0.750; as tie-breaker it *lowered* the refined pipeline 1.000 → 0.750; as gate, no change → **advisor seat, never the gate** | `experiments/wave3/jev/` |

## Slice 1 — live (2026-11-01)

| result | value | source |
|---|---|---|
| Staged cut through the live service | 16/16 tiles, 3,347.6 ms, 16 embeds | `slice1/README.md` |
| Staged object appearing | exactly tiles {5,6}, 392.8 ms, 2 embeds | `slice1/README.md` |
| Gradual drift | silent (correct) | `slice1/README.md` |
| Spend vs embed-everything (staged) | ratio **0.118** | `slice1/README.md` |
| Live camera (ProArt, outbound push) | gate 3.0; 1,200 still frames → **0 steady-state nominations**, 0 events; sensitivity replay still exact | `slice1/PROART-CAMERA.md` |
| 48 h soak | **running** 2026-11-01 18:18 → 2026-11-03 18:18 AKST; at +50 min: 5,431 frames, 0 events, spend ratio 0.0002, `silence_meaningful = true` | `slice1/PROART-CAMERA.md` |

## Slice 2 — serve + presence

| result | value | source |
|---|---|---|
| NVENC sessions | 64/64 H.264 opened, **no cap found**; the cap is aggregate **~580–640 fps** of 1080p | `slice2/NVENC-BENCH.md` |
| Realtime transcodes | hold through 16, break at 24 → promise 8, engineer 12, hard cap 16 | `slice2/NVENC-BENCH.md` |
| GStreamer V4L2 H.265 vs ffmpeg nvenc | **530–740 fps vs ~209 (2.5–3.5× cheaper)** — but H.265-in-TS is outside Apple's HLS spec; the player ships H.264 until an fMP4 path exists | `slice2/NVENC-BENCH.md`, `slice2/player/README.md` |
| Contention (transcode × embeds) | embed p99 170 → 251 ms; transcode −36%; graceful both ways | `slice2/NVENC-BENCH.md` |
| Player | remux 141/141 frames at 0 fps draw; transcode 1800/1800 at 138 fps draw; budget refusal 429 at cap while remux still serves; watchdog kills a stalled source and marks it failed | `slice2/player/RESULTS.md` |
| Presence brain (already on disk) | Qwen3-Coder-30B-A3B: grounded all content questions, refused the trick with reasoning; 65 tok/s | `slice2/BRAIN-BENCH.md` |
| Piper TTS, resident worker vs spawn | **1,974 → 287 ms**; full voice loop 2,891 → 1,284 ms | `slice2/presence/README.md` |
| Presence v2 battery (voice loop) | **7/7**, zero invented numbers, stale heartbeat answered correctly | `slice2/presence/README.md` |
| Presence v3 claim checker | 23/23 unit traps; 8/8 stub-fed traps replaced before TTS; battery 6/7 twice (failures upstream: STT garbling) — no third run taken to fish for 7/7 | `slice2/presence/README.md` |

## Slice 3 — library + synthesiser

| result | value | source |
|---|---|---|
| Backfill pass 1+2 | 234 real items shelved (232 images, 2 videos), thumbs 232/232, posters 2/2, zero NVENC draw | `slice3/BACKFILL-PASS1.md` |
| The house's video holding | **65.9 seconds total** | `slice3/BACKFILL-PASS1.md` |
| Engine vs sampler, late readers | mean error better at every lag: **11× at lag 0, 18× at 1 s, 8× at 10 s** | `slice3/synth/README.md` |
| Wave-3 echo (scene-label at a lag) | sampler error oscillates 1.000/0.000 by frame parity; rhythm-learning engine **0.000 at all lags** | `slice3/synth/README.md` |
| Reversal cost | engine worse than sampler for ~2 s post-flip (peak 60× baseline) | `slice3/synth/README.md` |
| Snap rule v2 (3× + decontaminated band) | reversal recovery **6.0 s → 2.0 s**, 2 corrections, **zero false snaps**, controls/speeder bit-identical | `slice3/synth/README.md` |

## Deficits and open debts (kept at the same prominence)

- **The diff gate is a ranker, not a separator** (wave 3): skipped-tile
  drift 0.20 vs embedded 0.48 — per-scene lens calibration is real,
  recurring work, not a solved problem.
- **Every brain tested was blind to a stale heartbeat** presented as
  raw data; the fix lives in the digest (staleness pre-computed into
  words), not in model choice. Prose staleness claims needed a second
  fence (v3's claim checker); STT garbling remains an unfenced
  upstream failure.
- **Panel round 2's cache design failed** (per-model caching, one
  question per model): round 3 must ask ≥2 questions per model or
  price the prefix at full rate.
- **The Thor's ffmpeg 8.0.1 has no scale filter and cannot convert
  pixel formats** — media work routes around it (PIL/NV12) until it
  is replaced.
- **Slice 1's precision number does not exist yet**: the soak's
  silence is machine-verifiable, but precision needs a human to judge
  events against the corrections ledger. The soak verdict lands
  2026-11-03.
- **Presence has never been used by a human.** All voice acceptance
  is synthesised-speech fixtures; the from-the-chair test (a real
  conversation through a browser) remains the headline acceptance
  of Amendment 2.
- **Casey's decision-model servers (:8295/:8296) are down** — the
  Thor's thor-admit guard reaps unleased multi-GB loads; their
  leases were absent. Not restarted by the fleet: the launch
  recipe is the owner's.
