# Slice 1 core — confluence-watch (the live harbor-watch)

The LIVE version of wave 3's harbor-watch: a service on the Thor
that ingests a phone camera stream (or a file replay through the
identical interface), runs the harbor-watch cascade incrementally
as frames arrive, and publishes change verdicts to a per-stream
text ledger.

## Shape

```
[ingest.py] --records + frame_end (JSONL)--> [confluence-watch] --> ledger/
  phone /shot.jpg, /video (MJPEG),            perceive -> decide ->   lens.txt
  replay: staged events, wave-3 frames        direct -> refine ->    state.txt
  tiles 4x4, diff gate, rack embeds           publish (substrate      events.jsonl
                                                rings, batch-parity)   health.txt
```

- **ingest/ingest.py** owns acquisition, decode, tiling, the µs
  diff gate, and I-JEPA embeds of nominated tiles via the JEV rack
  (`POST /embed/image`). Sources: `staged`, `wave3`, `shot`,
  `mjpeg` — the service cannot tell them apart.
- **src/live.rs** is the batch cascade refactored frame-at-a-time;
  `tests/live.rs` proves verdict-identical output vs
  `harbor_watch::pipeline` on the fixture (including the stale
  publish rule and lineage masks).
- **src/service.rs** spawns the ingest, assembles frames, manages
  the rack lifecycle: if the rack is down it starts it, logs that
  in events.jsonl, and on exit stops it **iff it started it** —
  the box is left as found.
- **src/ledger.rs** writes the ledger: `lens.txt` (rhythm EMA +
  per-tile score EMA + gate/threshold), `state.txt` (counters,
  embed-second meter, coverage = embedded/nominated,
  embed-everything estimate, spend ratio; soak self-report
  placeholders in soak mode), `events.jsonl` (service receipts +
  one verdict event per changed frame, with changed tiles, focus,
  per-stage ms receipts, substrate lineage mask, verdict latency),
  `health.txt` (embed p50/p99, max frame backlog, last-frame age,
  `silence_meaningful` — Panel-1: silence is only "normal" when
  health says so).

Config is a `key = value` text file (see acceptance.sh for working
examples): stream_id, ledger_dir, ingest_cmd, rack_url,
rack_autostart, stop_rack_on_exit, threshold, alpha, focus_k,
soak, max_frames, stop_file.

Verdict latency is end-to-end: frame capture stamp (ingest) to
ledger write, so it includes that frame's own embed time.

## Acceptance (acceptance.sh, on the Thor — ALL PASS 2026-11-01)

1. `cargo test` — 3/3 (parity, ledger, service-via-ingest-interface).
2. **Staged events** (real rack, real-photo composite scenes):
   cut at frame 4 → published, 16/16 tiles, latency 3,347.6 ms
   (16 embeds); object at frame 7 → published, tiles {5,6} exactly,
   latency 392.8 ms (2 embeds); drift frames 10–17 → nothing.
   34 embeds total; spend 13.4 s vs 113.2 s embed-everything
   estimate (ratio 0.118). Lineage mask 31 (all five stages).
3. **Wave-3 sequence C** (real frames, cut every boundary):
   verdicts on 11/11 cut frames, 16/16 tiles each; latency p50
   3.00 s (13–16 embeds per frame at gate 3.0 — on real photos this
   gate nominates nearly everything; per-stream gate calibration
   is a lens-tuning task, recorded not hidden).
4. **Phone interface**: staged frames served as /shot.jpg over
   localhost HTTP and ingested via the `shot` source — cut and
   object published, drift silent. The real phone uses this path.
5. **Soak smoke** (separate run): soak=true + stop file → clean
   unattended shutdown, placeholders in state.txt, rack stopped.
   After every run: rack verified `inactive` (as found), no
   leftover processes (pgrep).

## Rig lesson (kept, per doctrine)

The first staged rig used synthetic flat-gradient scenes and the
cut published *nothing*: I-JEPA embeds two flat colour fields
nearly identically, so the "different" scenes scored under
threshold. The rig was rebuilt compositing real photos (wave-3
burst/turntable frames + a real-photo patch as the object); probe
distances: cut min 0.299 / mean 0.491, object tiles 0.588/0.651,
non-object max 0.027. A staged scene the perception model cannot
tell apart tests nothing.

## What the phone hookup still needs

- The phone on the LAN running an IP Webcam-style app; point the
  config's ingest_cmd at it:
  `ingest.py --source shot --url http://<phone-ip>:8080/shot.jpg`
  or `--source mjpeg --url http://<phone-ip>:8080/video`.
  Both paths are implemented; the shot path is acceptance-tested
  against a localhost stand-in.
- Per-stream gate calibration against the phone's real scene
  (gate 3.0 is busy-material-tolerant, quiet-scene-rough; the lens
  carries it as a per-stream value).
- The 48 h soak for the Slice-1 precision acceptance: **update
  2026-11-01** — the soak is running (started 2026-11-01 18:18 AKST)
  on the ProArt webcam stand-in via outbound push, because the phone
  was off the LAN when Casey stepped away; see
  `../PROART-CAMERA.md`. The phone remains the reference node and
  this hookup is still the path it will use.
