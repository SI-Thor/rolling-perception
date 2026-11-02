# Slice 1 — live change feed + library shelf + install pack

Built and acceptance-tested on the Thor 2026-11-01
(`~/confluence-play/slice1/` is the play-area deployment; nothing is
installed resident yet).

- `core/` — `confluence-watch` (Rust): live ingest (IP Webcam
  /shot.jpg polling, MJPEG drop-to-newest, staged + wave-3 replay
  sources behind one interface) → tile + diff-gate → JEV-rack embeds
  → the harbor-watch cascade running incrementally (parity-tested
  verdict-identical to the batch pipeline) → text ledger
  (lens/state/events/health, incl. embed-second meter, coverage,
  and the Panel-1 health heartbeat: `silence_meaningful`).
  Acceptance on the Thor: staged cut 16/16 tiles (3,347.6 ms, 16
  embeds), staged object exactly tiles {5,6} (392.8 ms, 2 embeds),
  drift silent; spend ratio 0.118 vs embed-everything; wave-3
  sequence C live-mode: 11/11 cut frames, latency p50 3.00 s.
  Rig lesson kept: synthetic flat-gradient scenes embed nearly
  identically in I-JEPA — the staged rig is built from real-photo
  composites (probe distances in core/README.md).
- `console/` — the one page (FastAPI, Thor's ml venv): change feed
  with tile overlays + working corrections button (appends to
  corrections.jsonl), library shelf, health that goes AMBER
  "NOT REPORTING" when the heartbeat is stale. Tested on the Thor
  against fixtures built from real wave-3 verdicts (200s, traversal
  refused, correction POST verified in the ledger).
- `install/` — the technician's pack: INSTALL.md, SERVICE-CARD.md,
  and install.sh (dry-run first; `--apply` never enables the
  service without `--enable-service`). Dry-run verified on the
  Thor; nothing was applied.

Remaining for Slice 1 acceptance: the real phone stream (config
points at its /shot.jpg or /video), per-scene gate calibration
(gate 3.0 nominates nearly everything on busy real photos — the
wave-3 lesson, again), and the 48 h soak for the precision number.
