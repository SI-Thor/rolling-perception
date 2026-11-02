# NVENC Bench — Jetson AGX Thor (Confluence Slice 2 debt payment)

**Date:** 2026-11-01, ~17:35–18:00 AKST · **Box:** `thor` (NVIDIA Thor, driver 595.78, CUDA 13.2)
**Question (Panel 1, top amendment):** do NVENC sessions break before compute does?
**Short answer:** No — not on this box. Session *count* is effectively free (≥64 concurrent
opens, zero failures). What breaks is aggregate encode *throughput*: the engine saturates at
≈600 fps of 1080p H.264, and per-session fps degrades from there. **The metered resource for
the spec is encode-fps, not sessions.**

All numbers below were measured live on the Thor during this bench. Nothing here is simulated.
Baseline tenancy during every measurement (the box as Casey actually runs it, left untouched):
2× `llama-server` + a trellis Python process holding ~16 GB GPU memory with the GPU busy.
These numbers are therefore conservative — they are what the platform gets on a lived-in box,
not on a sterilised one.

---

## 0. Stack reality (read this before trusting any transcode plan)

Two distinct hardware-encode stacks exist on this box, and they perform *differently*:

| Stack | Path | Used for |
|---|---|---|
| CUDA-NVENC | ffmpeg `h264_nvenc` / `hevc_nvenc` / `av1_nvenc` (ffnvcodec) | ffmpeg pipelines |
| V4L2-NVENC | GStreamer `nvv4l2h264enc` / `nvv4l2h265enc`, `nvv4l2decoder`, `nvvidconv` (VIC scaling) | Jetson-native pipelines |

The installed ffmpeg (n8.0.1, Ubuntu Jetson build) is a **device-resident-only** build:

- Encoders present: `h264_nvenc`, `hevc_nvenc`, `av1_nvenc`, `nvjpegenc`; decoders `*_cuvid`, `*_nvv4l2dec`.
- **Absent:** `testsrc`/lavfi input, `scale_cuda`, CPU `scale` (swscale disabled), software H.264/HEVC decoders.
  Test sources were therefore generated with GStreamer `videotestsrc` (pattern=ball; pattern=snow for the stress case).
- Scaling on the ffmpeg path = cuvid's `-resize` option (scales inside NVDEC, frames never leave the device).
- **The host round-trip path does not exist in this build** (measured, §3): `hwdownload` fails with
  `Error reinitializing filters!` and `hwupload_cuda` → nvenc fails with
  `Could not open encoder before EOF … Invalid argument`. Any design that assumes
  decode→CPU→encode on ffmpeg/Thor is dead on arrival; frames stay on-device or the pipeline moves to GStreamer.
- NVML does not see encoder sessions on this platform: `nvidia-smi --query-gpu=encoder.stats.sessionCount`
  returns `0` even with 24 sessions running. Utilisation *is* visible via
  `nvidia-smi -q -d UTILIZATION` → `Encoder : NN %`. Do not build session accounting on NVML counters.

---

## 1. Session cap — opens

**Method.** Sessions launched one at a time (3 s apart), each verified alive after launch.
Feed: raw 1080p YUV420 file, paced realtime (`-re`, 30 fps, looped), so every session is a
genuine sustained 1080p30 encode, preset `p4`, 6 Mb/s:

```
ffmpeg -stream_loop -1 -re -f rawvideo -pix_fmt yuv420p -s 1920x1080 -framerate 30 \
  -i raw1080.yuv -c:v h264_nvenc -preset p4 -b:v 6M -f null -
```

| Test | Result |
|---|---|
| H.264 sessions, incremental | **64 / 64 opened, zero failures** — search stopped at 64, not at a failure |
| H.265 sessions, incremental | **20 / 20 opened, zero failures** — search stopped at 20 |
| Mixed pool | 20× H.265 already open + 8× H.264 added → **28 / 28 fine** (one shared pool) |
| Failure error text | **None exists to quote — no session open ever failed.** |

There is no consumer-style session wall (3/5/8) on this silicon/driver. But note what the
utilisation counter said while those sessions were "open": **Encoder: 98%** already at 24
realtime sessions. Sessions beyond the engine's throughput don't get refused — they get
*slow*. That is a worse failure mode for a product than a clean error, and it is why §2 is
the operative cap.

## 2. Sustained aggregate throughput — the operative cap

**Method.** N sessions start simultaneously; each encodes 1,200 frames of raw 1080p
full-speed (no pacing); wall time until *all* finish; encoder utilisation sampled throughout.

| Encoder / content | N=1 | N=4 | N=8 | N=12 | N=16 | N=24 |
|---|---|---|---|---|---|---|
| H.264 aggregate fps | 351.6 | 522.7 | 598.4 | 640.6 | 614.7 | 578.7 |
| H.264 per-session fps | 351.6 | 130.6 | 74.8 | 53.3 | **38.4** | **24.1** |
| H.264 snow (max-entropy) aggregate | 338.9 | — | 638.8 | — | — | — |
| H.265 aggregate fps | 344.0 | — | 522.8 | — | — | — |
| Encoder utilisation | 48% | 98% | 98% | 98% | 98% | 98% |

Readings:

- **Aggregate H.264 1080p ceiling ≈ 580–640 fps ≈ 19–21 realtime 1080p30 streams.**
  Content barely matters (snow ≈ ball): the engine is clock-bound, not entropy-bound, at p4/6 Mb/s.
- **A single session cannot fill the engine** (351 fps at 48% util). Concurrency is required
  to reach the ceiling — good news: one greedy backfill job cannot monopolise NVENC by accident;
  it takes ~4+ sessions to saturate.
- **Realtime (≥30 fps/session) holds through N=16** (38.4 fps each) and **breaks at N=24**
  (24.1 fps each). The realtime crossover is ≈19–20 concurrent 1080p transcodes.
- H.265 (ffmpeg path) aggregate at N=8 is 522.8 fps ≈ 87% of H.264 — but see §3: the V4L2
  stack tells a completely different H.265 story.

## 3. Throughput matrix — single-session transcode

Sources: 60 s files (1,800 frames), `videotestsrc pattern=ball`, generated via the V4L2 encoder.
ffmpeg fps = encoder-reported steady rate; GStreamer fps = 1,800 / wall (frame-count-verified
with `ffprobe -count_frames` on re-runs to real files: exactly 1,800 frames out, every case).

### A. ffmpeg, device-resident (cuvid decode → `-resize` in NVDEC → nvenc) — "scaling on the GPU path"

| Case | fps | ×realtime |
|---|---|---|
| 4K H.264 → 1080p H.264 | 267 | 8.9× |
| 1080p H.264 → 720p H.264 | 293 | 9.8× |
| 1080p H.264 → 1080p H.265 | 209 | 7.0× |
| 1080p H.264 → 1080p H.264 (no scale) | 208 | 6.9× |

Full-pipeline transcode runs well below raw-encode speed (208–293 vs 351 fps encode-only):
decode + frame movement costs ~40%. In the pipeline, H.264→H.265 ≈ H.264→H.264 — the
encoder difference is hidden behind decode cost on the ffmpeg path.

### B. ffmpeg, host round-trip ("without scaling on the GPU path") — DOES NOT EXIST

| Variant | Result |
|---|---|
| cuvid → `hwdownload,format=nv12,hwupload_cuda` → nvenc | 0 frames — `Could not open encoder before EOF`, `Invalid argument` |
| cuvid → `hwdownload,format=nv12` → nvenc (system-memory frames) | 0 frames — `Error reinitializing filters!`, `Invalid argument` |

There is no CPU-touch transcode path in this ffmpeg build. The honest comparison the spec
asked for is therefore A (device-resident ffmpeg) vs G (GStreamer/VIC) below.

### G. GStreamer, Jetson-native (nvv4l2decoder → nvvidconv/VIC scale → nvv4l2 encoder)

| Case | fps | ×realtime | Note |
|---|---|---|---|
| 4K H.264 → 1080p H.264 | 239.5 | 8.0× | comparable to ffmpeg A (267) |
| 1080p H.264 → 720p H.264 | 176.3 | 5.9× | anomaly: *slower* than the 4K case; reproduced on re-run, frame-count verified — nvvidconv 720p path is oddly expensive |
| 1080p H.264 → 1080p H.265 | **530–740** | **17.7–24.7×** | 3 runs, 2.44–3.39 s per 1,800 frames, **1,800/1,800 frames verified** — the V4L2 H.265 path is 2.5–3.5× faster than ffmpeg's `hevc_nvenc` pipeline |

**Stack-choice finding:** for H.265 renditions the serve plane should use the V4L2/GStreamer
path (or ffmpeg's nvv4l2 interop), not `hevc_nvenc`. ffmpeg-nvenc numbers remain the
conservative floor for planning; V4L2 H.265 is the cheapest engine time per stream on this box.

*Gap, stated plainly:* encode-only 4K raw throughput was not measured (no 4K raw source was
generated); 4K figures above are decode-inclusive transcodes. The 4K per-stream engine cost
in a mixed aggregate is an open measurement, not a number in this report.

## 4. Contention — perception vs transcode (the panel's real question)

JEV rack started for this test (I-JEPA lazy-loaded in 6.8 s; weights present), stopped after,
verified `inactive`. Embed = `POST /embed/image`, real 1.5 MB PNG, 40 sequential calls per phase.

| Metric | Idle (no transcode) | Under 1× 1080p→720p transcode | Delta |
|---|---|---|---|
| Embed p50 | 139 ms | 237 ms | **+70%** |
| Embed p99 | 170 ms | 251 ms | **+48%** |
| Transcode fps (same window method) | 232 fps solo | 149 fps under embed loop | **−36%** |

NVENC is a separate engine, but the two workloads share the GPU's memory bandwidth, the
decoder, and the power envelope — contention is real, and it is *mutual and graceful*:
embeds stay sub-300 ms, the transcode stays at ~5× realtime. Neither side collapses.
Budget perception latency assuming transcode load: **embed p99 ≈ 250 ms under load** is the
planning number, not the idle 170 ms.

**Rig failure worth keeping (serve-plane finding):** ffmpeg `-stream_loop` + cuvid dies at
the loop seam — first pass completes, then `cuvid decode callback error / Decoding error:
Invalid argument` repeats forever while the process stays alive and its fps counter decays.
An in-process-looped transcode on this stack silently becomes a zombie. The serve plane must
loop at the supervisor level (restart per pass) or use long/concatenated inputs — never trust
a transcode process that merely *exists*; watch its frame counter. (First contention run was
invalidated by exactly this and re-run against a 7,200-frame single-pass source; only the
re-run is reported above.)

## 5. Who else consumes the encoder?

Nobody, at rest. Inventory taken during the bench:

- `pgrep ffmpeg / gst-launch`: none outside this bench's own processes.
- `/dev/nvidia0` holders: Xorg + gnome-shell (display only), 2× llama-server, 1× trellis
  Python — all **compute** tenants; none opens NVENC sessions.
- No `/dev/video*` nodes exist on this box (the V4L2 encoder does not surface as a
  userspace video node), so encoder tenancy can't be audited via device files — audit by
  process list instead.
- Consequence: **every encode-fps the engine spends will be spent by the platform itself.**
  The budget below is entirely self-inflicted or self-denied; there is no noisy neighbour.

## 6. Verdict — what the serve plane can honestly promise

**Promise: 8 simultaneous live player transcodes at 1080p with deep headroom; 12 as the
engineered cap; 16 is the measured realtime edge; ~19–20 is where physics says no.**
A household will not hit this. What it *can* hit is one backfill job eating the engine at
full speed — so the budget is enforced on fps, not on session count.

Key reframing from the data: a *live* player transcode paced at realtime only consumes
30 fps of engine. The 600 fps ceiling is only threatened by **full-speed work** (backfill,
catch-up, thumbnail bursts). The degradation ladder therefore sheds full-speed work first
and touches live players last:

1. **Backfill/library transcodes: 1 session, fps-capped** (e.g. ≤150 fps) whenever any live
   player or perception load is active; first thing paused at pressure. Alone at night it
   may use the whole engine.
2. **Thumbnail/poster generation: batch, ≤1 session-equivalent**, single-frame encodes
   (nvjpegenc stills don't even touch NVENC video sessions); shed with backfill.
3. **New live sessions beyond 8 concurrent:** start at a 720p rendition (cheaper pipeline,
   measured 293 fps class) and step up if the fps budget allows.
4. **Prefer H.265 renditions via the V4L2 path** for clients that accept them — measured
   2.5–3.5× cheaper per stream than the ffmpeg HEVC path.
5. **Hard cap 16 live transcode sessions** (mixed-resolution, counted in 1080p-H.264-equivalent
   fps units; a 4K-sourced player counts double until the 4K aggregate cost is measured).
   Beyond the cap: queue the request, never let fps rot silently — §1 showed the failure
   mode is degradation, not refusal, if you don't enforce this yourself.

### Session budget line for the spec

> **NVENC on the Thor is metered in encode-fps, not sessions** (≥64 sessions open without
> error; the engine saturates at ≈600 fps of 1080p H.264 ≈ 19–20 realtime streams).
> Platform's own consumers: ingest remux = 0 (stream copy; 1 realtime-paced session only on
> codec-mismatch re-encode), thumbnails = ≤1 batch session-equivalent, library backfill =
> 1 fps-capped session, first to shed. Player sessions: engineered budget **12 concurrent**
> (hard cap 16), 4K sources count as 2 units. Perception (I-JEPA) does not use NVENC but
> shares the GPU: reserve headroom by capping total full-speed transcode at ≤450 fps
> whenever the perception plane is active, and plan embed latency at p99 ≈ 250 ms under
> transcode load (vs 170 ms idle).

## Cleanup verification

All bench ffmpeg/GStreamer processes killed (final `pgrep`: none), encoder/decoder
utilisation 0%, JEV rack stopped and verified `inactive` with its port closed, the two
933 MB raw sources deleted from `/tmp/nvb` (scripts, logs and MP4 sources remain there for
re-runs). Casey's own GPU tenants (llama-server ×2, trellis) were never touched and are
still running as found.
