# ProArt-cam soak — early results (in progress)

**Status: RUNNING.** Started 2026-11-01 18:18 AKST. Verdict check
2026-11-03 18:30 AKST. This note was filed at hour ~1.3 of 48, from
live inspection of the running system, at the owner's request. It
will be superseded by the verdict note; nothing here is a conclusion.

## What is being tested

Slice 1's promise, on a real household feed instead of staged
footage: *watch this room; tell me what changed; otherwise,
silence.* The soak is the trust measurement behind that promise —
a false-alarm rate needs a per-day denominator, a gate calibrated
at night has to survive dawn and dusk, and unattended plumbing has
to prove it cannot fail silently (frame counter + heartbeats are
part of the record; a stall reads as a stall, not as calm).

## The feed

- ProArt PX13 webcam, stills at a 500 ms cadence, pushed outbound
  from the laptop (`proart-push.py`) to a receiver on the Thor —
  outbound because the Windows firewall blocks inbound.
- `confluence-watch` (config `proart.conf`, gate 3.0) splits each
  frame into 16 tiles, diffs them against the settled scene, and
  embeds only nominated tiles via the JEV rack. A frame that
  changes nothing writes nothing.
- **Nothing photographic is retained.** Frames exist only in
  flight and in memory for comparison. The ledger holds verdicts:
  timestamps, tile indices, change energies. Verified by search:
  no camera images exist anywhere in the run tree. Total run
  footprint at snapshot time: **116 KB**.

## Measured so far (snapshot 2026-11-01 19:35 AKST)

- Frames processed: ~7,980 in 77 minutes.
- Verdicts written: **48** — i.e. the system has spoken on 0.6% of
  frames and been silent on the rest.
- Cost on the Thor: watcher RSS 2.9 MB, receiver RSS 17.8 MB,
  CPU ~0.0–0.1% each; embedding happens in bursts of under a
  second (7–12 embeds) only on nominated frames; verdict latency
  750–870 ms end to end.
- Raw receipt: the ledger snapshot filed beside this note
  (`soak-proart-cam-ledger-snapshot-2026-11-01T1935.jsonl`).

## One unplanned recall probe

At ~19:24 the owner — who had been away from the house — sat down
at the desk in view of the camera, not as a test. The ledger shows
the episode with no human annotation: frames 7767–7788 flag tiles
9, 13, 14; frame 7807 fires a wide seven-tile event (a person
crossing the frame and settling); frames 7982–7983 flag a single
tile (small movement); then silence resumes while he works at the
desk. Event count went 43 → 48, all five his. The gate absorbed
him into the scene within about ninety seconds and stopped
reporting — which is the behaviour the whole design exists to
produce, observed live rather than staged.

## What remains open until the verdict

- Two dawn/dusk light transitions still to survive.
- The false-event count across the full 48 h (the budget number).
- Recall across ordinary household life in the window.
- Whether the spend rate (embeds per frame processed) holds its
  staged-test figure (~12%) on a live feed.
