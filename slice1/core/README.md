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
soak, max_frames, stop_file, budget_embed_s_per_hour, tenancy,
tenancy_sample_ms, tenancy_sustain_s, tenancy_recovery_s,
mem_pressure_pct, tenancy_platform_units.

## Tenancy: the yield ladder (SPEC §2.3, built 2026-11-03)

The watcher is a tenant on a shared box. `src/tenancy.rs` samples
the host every 2 s — foreign GPU load **attributed per process**
(nvidia-smi compute-apps minus the platform's own pids: the
service's tree plus the MainPIDs of `tenancy_platform_units`;
aggregate counters are never trusted, or the platform would yield
to its own embeds), interactive sessions via loginctl's idle
hint, memory via /proc/meminfo — and steps a ladder:

- **L1** backfill stops being permitted (flag in state/control;
  the §4 backfill process is the consumer).
- **L2** the stream's embed budget halves; reflective sampling
  flag off (published for consumers; slice 1's cascade has no
  reflective stage yet).
- **L3** reflex-only: the ingest embeds nothing and reports each
  changed frame at the reflex tier; the ledger publishes those as
  *unperceived-change* verdicts and health.txt carries
  `yield_rung`, `yield_reason`, `decision_tier`, `silence_basis` —
  a yielded stream's silence never claims decision-tier meaning.
- **L4** (needs memory pressure too: MemAvailable <
  `mem_pressure_pct` of RAM) decision models unload — the rack is
  stopped **only if this service started it**; a foreign-owned
  rack is receipted as not ours and left running. On recovery the
  rack is restarted if we unloaded it.

Entry: foreign GPU > 20% sustained > 5 s, an active interactive
session, or memory pressure. Recovery is hysteretic: 60 s of
clear headroom, one rung back per 60 s, so a stream hovering at
the threshold cannot flap the box. Every transition is receipted
in `events.jsonl` (`yield_rung` events with the sample figures),
and the ladder's orders reach the ingest through `control.json`
in the ledger dir (path in `$CONFLUENCE_CONTROL_FILE`): budget
admission in diff-rank order over a rolling hour
(`budget_embed_s_per_hour`, default 300 — the §2.2 camera class),
sheds counted as `tiles_shed`. Tests: `cargo test` (tenancy unit
+ integration suites, scripted probe) and
`python3 tests/test_ingest_control.py` (the ingest's control
effects against a stub rack).

Verdict latency is end-to-end: frame capture stamp (ingest) to
ledger write, so it includes that frame's own embed time.

## Fixtures (bundled 2026-11-02 — the rehearsal S2 blocker, cleared)

The staged and wave-3 sources run from **fixtures bundled in
this repo** (`fixtures/`: six wave-3 burst photos, six turntable
frames, and the object patch — 3.35 MB, the project's own wave-3
material, provenance in `fixtures/README.md`). Path resolution:
`--fixtures-dir` → `$CONFLUENCE_FIXTURES_DIR` → the bundled set;
a full local library is reachable only via the explicit
`CONFLUENCE_WAVE3_*_GLOB` / `CONFLUENCE_WAVE3_B_FILE` overrides.
No home-directory path is a default anymore (the ingest used to
read `~/image-studio/outputs/…` and `~/sitka-distill/…` directly,
which made this acceptance unreproducible from a clone).

What reproduces **cold, anywhere**: `python3 prove_fixtures.py`
runs the real ingest over the bundled fixtures with no rack and
proves the gate/diff layer — baseline 16 tiles, cut frame 16/16
nominated, object frame exactly {5,6}, drift frames silent,
every wave-3 C landing 16/16 (verified 2026-11-02 from a copied
tree under an empty `$HOME`). What still needs the Thor: the
**verdict layer** — embedding distances and the cascade need a
live JEV rack, so the numbered acceptance below remains a
Thor run, now against these same fixtures by default.

## Acceptance (acceptance.sh, on the Thor — ALL PASS 2026-11-01)

> Disclosure (per the graduation rehearsal): steps 2–4 run the
> staged/wave-3 sources against the bundled fixtures (above) and
> need the live JEV rack for embeds; the repo-only cold equivalent
> of their gate layer is `prove_fixtures.py`, and the
> fixture-driven Rust suite (`cargo test`) covers the cascade.

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
