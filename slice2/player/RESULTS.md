# Player spike — acceptance results (Thor, 2026-11-01 ~18:53–19:06 AKST)

Ran `acceptance.sh` against the deployed copy in
`~/confluence-play/slice2/player/` while the Slice-1 soak was
running on the same box (untouched throughout; verified alive
after: confluence-watch PID 1049389, rack active, encoder back to
0%, port 8340 free, no player/gst processes left).

**Final verdict: ALL PASS** (run 4, exit 0; full log on the Thor at
`~/confluence-play/slice2/player/acceptance-run4.log`).

## (a) Full HLS chain, transcode — PASS

- Item `ball-1080-h265` (real bench media: HEVC 1920×1080, 60 s,
  1800 frames) → session ready; `GET /play/ball-1080-h265` → **200**
  playlist (21 segments, EXT-X-ENDLIST).
- First 3 segments fetched → **200/200/200**; ffprobe on segment 0:
  `codec_name=h264, width=1920, height=1080` — the V4L2 transcode
  output, as decided.
- Remux chain (a2): real library item `hero` (H.264 1366×768) →
  playlist **200**, segment probes `h264 1366×768`, 141 frames =
  exactly 5.875 s × 24 fps.

## (b) Registry — PASS

Stop row for the transcode session (final code, focused re-test):

```json
{"event": "stop", "session": "2dfebd33", "item": "ball-1080-h265",
 "mode": "transcode", "units": 1, "frames": 1800,
 "fps_draw": 138.1, "throughput_fps": 138.1, "reason": null}
```

Frames counted exactly (1800/1800). fps_draw 138.1 with the soak
concurrent on the GPU — the bench's solo V4L2 H.264 full-pipeline
rate was 176–240 fps and its measured contention delta under
perception load was −36%, so 138 under a live soak is in family,
not a surprise. Remux rows log `fps_draw: 0.0` by design (no encode
spent) with `throughput_fps` carrying the copy rate (65.8).

## (c) Budget refusal — PASS

Server restarted with `PLAYER_PHANTOM_UNITS=8` (test hook):

- Transcode request → **429** `{"state": "busy", "message": "The
  house is busy — the Thor is at its encode budget right now.
  Direct-play items still work.", "units_used": 8,
  "units_budget": 8}`; registry gained a `refused` row
  (`"reason": "budget: 8+1 > 8 units"`).
- Remux request under the same cap → session **ready**, playlist
  **200**. Direct play is never refused.

## (d) Watchdog — PASS

Item `stall` (a fifo that never delivers a byte; worker process
alive, zero frames): session flipped to
`{"status": "failed", "reason": "watchdog_stall"}` inside the
5 s stall window plus poll granularity; registry `failed` row
written; `pgrep` confirmed no stall worker remained.

## Defects found and fixed on the way (the runs earn their keep)

1. **Run 1**: acceptance harness never started its server for
   tests (a)–(d) (missing `start_server 0`) — every request 000.
   Section (c), the one place a server *was* started, passed —
   which is what proved it was the harness, not the player.
2. **Run 2**: registry logged `frames: 0` — ffprobe count output
   for these TS segments is `"120\n\n120\n"` (stream listed
   twice) and `int()` on it threw. Parser now takes the first
   all-digit token.
3. **Run 2**: `POST /api/play` 500'd for any session started
   while another existed — `active_units()` subscripted Session
   objects as dicts (`TypeError`). Fixed to attribute access;
   also explained run 2's empty `/api/sessions` (same crash).
4. **Run 3 → 4**: decoded-frame counting (`-count_frames`)
   undercounted (1080/1800) — this ffprobe decodes via h264_cuvid
   and returned `nb_read_frames=N/A` on segments with PPS
   complaints. Switched to packet counting: exactly 1800/1800.
5. **Run 4 follow-up**: `fps_draw` billed the watchdog's own
   ~15 s final recount (70.7 fps). Worker-exit is now stamped
   before recounting; the meter no longer bills its own reading
   (138.1 fps on the same workload).

Also measured en route: this ffmpeg build has **no HLS muxer**
(`hls_time` unrecognized) — both modes run on GStreamer; and the
box has **no fMP4/CMAF HLS sink**, which is the load-bearing fact
behind the H.264-out codec decision in README.md.
