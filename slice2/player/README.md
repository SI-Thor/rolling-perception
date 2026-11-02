# Confluence Slice 2 — player spike (serve plane, first cut)

The serve plane's first working spike: one FastAPI backend + one
static page that turn a library item into an HLS stream, deciding
per request between **remux** and **transcode**, under the NVENC
bench's budget, with the bench's zombie lesson implemented as a
frame-counter watchdog.

Files: `player.py` (backend), `index.html` (page), `acceptance.sh`
(the acceptance, run on the Thor), `RESULTS.md` (evidence from the
2026-11-01 runs), `fmp4_pipeline.py` + `build_hls.py` +
`fmp4_split.py` (the HEVC→fMP4 production path, copied from the
spike in `fmp4-spike/`), `verify_fmp4.py` (the spike's validation
checklist as code).

## Run it (on the Thor)

```sh
cd ~/confluence-play/slice2/player        # deployed copy
~/ml/.venv/bin/python player.py           # :8340, env-configured
# page: http://thor.local:8340/
```

Media lives in `media/` beside it (env `PLAYER_MEDIA_DIR`);
sessions write HLS to `work/<sid>/`, the registry appends to
`ledger/sessions.jsonl`. Test content used: `hero.mp4` (a real
library item, copied from `~/cartography-verify/jev-quilt/assets/`),
`ball-1080-h265.mp4` (the bench's 60 s HEVC 1080p source), and
`stall.fifo` (watchdog test source).

## The mode decision (per request, from ffprobe)

- **h264 source → REMUX.** GStreamer parse-only pipeline
  (`qtdemux → h264parse → hlssink2`) into TS HLS. Encode draw
  **0 fps**; a 5.9 s clip remuxes in ~50 ms. Always served.
- **hevc source → FMP4.** `fmp4_pipeline.py`: GStreamer `mp4mux`
  remux to a fragmented MP4, split into an init segment +
  GOP-aligned media segments (tfhd `default-base-is-moof` patched
  in place), served as HLS-fMP4 (`EXT-X-MAP`, `seg_*.m4s`). Encode
  draw **0 fps** — a remux, charged exactly like REMUX, never
  refused. Wired 2026-11-02 from the spike in `fmp4-spike/`,
  whose verdict stands: spec-conformant by checklist + probe
  (`verify_fmp4.py` is that checklist as code); no Apple-client
  playback is claimed.
- **anything else → TRANSCODE.** GStreamer V4L2 stack end to end
  (`nvv4l2decoder → nvvidconv → nvv4l2h264enc`, 6 Mb/s, GOP = one
  segment) into TS HLS.

Why GStreamer for both: this box's ffmpeg build has **no HLS muxer
at all** (measured during the spike: `Unrecognized option
'hls_time'`; its muxer list has mp4/mpegts only). One stack, the
bench's stack.

### Codec decision: H.264 out, not H.265 — from evidence

The bench prefers V4L2 H.265 (2.5–3.5× cheaper). The spike still
transcodes to **H.264**, because of what the box can produce and
what the page's client (a plain `<video>` element, the console
pattern — no hls.js) can be promised to play:

- HEVC-in-HLS was generated and inspected: segments are MPEG-TS
  (EXT-X-VERSION:3, no EXT-X-MAP, no hvc1 sample entry). It decodes
  fine in GStreamer — the stream is well-formed.
- But the box has **no fMP4/CMAF HLS sink** (`hlscmafsink` absent;
  only `hlssink`/`hlssink2`, both TS-only), and Apple's HLS spec
  requires HEVC in fMP4 — HEVC-in-TS is outside the spec for the
  one browser family with native HLS. Chrome has no native HLS.
- Verdict (as written 2026-11-01): spend the more expensive H.264
  encode today; H.265 becomes the follow-up the day an fMP4 HLS
  path is verified against a real client. The decision is recorded
  here so it is re-opened by evidence, not by habit.
- **Update (2026-11-02):** the fMP4 path now exists and is wired
  (FMP4 mode above; `fmp4-spike/RESULTS.md` for the evidence) —
  for items whose HEVC encode already exists, no transcode is
  spent at all. The H.264 verdict above still governs the live
  TRANSCODE output, which is produced as TS by the V4L2 stack;
  the original reasoning is kept verbatim because it still
  describes that half correctly.

## Budget (NVENC-BENCH.md §6, Panel-2 Q2 shed order)

The metered resource is encode work. Sessions are admitted in
**1080p-equivalent units**: PROMISE = **8 units** (the bench's
promise-8), a >1080p source counts 2 (the bench's 4K rule). A new
transcode that would exceed the budget is **refused** — HTTP 429
with a plain "house is busy" state the page renders as a banner —
and the refusal is written to the registry. **Remux is never
refused** (0 units): direct play is the shed order's last rung,
below even the last viewer. A second viewer of an item already
transcoding/ready reuses its session and spends nothing.
Every session's **measured** encode-fps draw (frames out ÷ worker
wall time) is logged in the registry regardless of the unit model.

Registry: `ledger/sessions.jsonl`, append-only rows
`{ts, event: start|stop|failed|refused, session, item, mode,
units, frames, fps_draw, reason}` — plain text, ledger style.

## Supervision: frames, not processes

A watchdog thread counts frames in each transcode's segment files.
If the count does not increase for **> 5 s** while the worker is
alive, it kills the worker's process group and marks the session
`failed(reason=watchdog_stall)`. (The bench's ffmpeg `-stream_loop`
zombie — process alive, zero frames — is the failure this exists
for.) Frames are counted as **video packets** (`ffprobe
-count_packets`), never decoded frames: this box's ffprobe decodes
via h264_cuvid, which returned `nb_read_frames=N/A` on some
segments and silently undercounted; packet counting summed to
exactly 1800/1800 on the test item. Known spike cost: each probe
is ~0.5–1 s of CPU, so supervision is not free — a production
version should take counts from the pipeline itself.

## API

| Route | What |
|---|---|
| `GET /` | the player page |
| `GET /api/library` | items with probe + predicted mode |
| `POST /api/play {id}` | start/reuse a session (429 busy when refused) |
| `GET /api/session/<sid>` | live session state incl. fps draw |
| `GET /api/sessions` | folded state + registry tail + units used |
| `GET /play/<id>` | start/reuse and return the playlist itself |
| `GET /hls/<sid>/<file>` | playlist/segments, traversal-guarded |

Test hook: `PLAYER_PHANTOM_UNITS=N` pretends N budget units are
already in use (acceptance test (c) uses 8). Off (0) in any real
deployment; it is labelled in `/api/sessions` output when set.

## Not in the spike

Live/realtime-paced sessions (this is VOD-style full-speed HLS
generation), 720p step-down rungs, backfill/thumbnail consumers of
the same budget, audio handling (test sources are video-only;
pipelines wire the video pad only), and multi-item concurrency
beyond the admission gate. All are named in the spec's shed order
and land behind this same registry.
