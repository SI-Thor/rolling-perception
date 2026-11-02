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

*[Correction, 2026-11-02: the sentence above is the 2026-11-01
record and is kept verbatim as history. It is no longer the
operative fact: the fMP4 spike (fmp4-spike/RESULTS.md) proved a
sink is not needed — GStreamer `mp4mux` remux + split + a tfhd
patch produces spec-conformant HLS-fMP4 — and that path is now
wired into the player as the FMP4 mode. See the next section.]*

---

# FMP4 wired — acceptance results (Thor, 2026-11-02)

The spike's remux path is a production mode of player.py:
probe says `hevc` → **fmp4** (was: transcode). `fmp4_pipeline.py`
(the spike's pipeline.sh as a worker: gst mp4mux remux →
`build_hls.py` split/group/tfhd-patch, both copied beside the
player) writes init.mp4 + seg_*.m4s + playlist into the session
dir; the /play route rewrites EXT-X-MAP and segment URLs like it
does TS; the /hls route serves init.mp4 (`video/mp4`) and .m4s
(`video/iso.segment`). Budget: fmp4 sessions carry **units 0** and
log **fps_draw 0.0** — a remux, charged exactly like REMUX, never
refused. `verify_fmp4.py` is the spike's §4 checklist as code
(playlist/EXT-X-MAP/EXTINF-sum, init probes hevc/hvc1 + mvex/hvcC,
per-segment moof presence, tfhd default-base-is-moof on every
moof, first-sample sync, init+segment packet count == recorded
samples). Claim discipline unchanged: **spec-conformant by
checklist + probe**; no Apple-client playback is claimed.

## What passed (acceptance run 2, scratch deployment, soak live)

- **(e) fMP4 end-to-end**: POST ball-1080-h265 → mode=fmp4,
  units=0 → session ready → GET /play → **200**, playlist v7 with
  EXT-X-MAP and 8 GOP-aligned segments (7×8.533 s + 0.267 s) →
  init **200**, segment **200** → **verify_fmp4 ALL PASS** (41
  checks, incl. EXTINF sum 60.000 s and packet counts
  256×7 + 8 = 1800/1800). Registry stop row: `"mode": "fmp4",
  "units": 0, "frames": 1800, "fps_draw": 0.0,
  "throughput_fps": 8417.2` — the remux's copy rate, billed as
  zero encode.
- **(a2) H.264 remux**: hero → ready, playlist 200, segment probes
  h264 1366×768 (unchanged behaviour).
- **(b) registry**, **(d) watchdog** (stall fifo →
  watchdog_stall, no worker left): PASS, as in run 4.
- **(c) budget at phantom cap 8**: transcode (vp9 item) refused
  **429 "house is busy"** + refused row; hero remux serves 200;
  **ball fMP4 serves 200 under the same cap** — the refusal holds
  for transcodes while fMP4 items serve.

## Transcode completion — the honest state

Section (a) could not be repeated in its run-4 form, for reasons
that are themselves findings:

1. Run 4's transcode input was HEVC; HEVC now routes to FMP4 —
   the improvement working as intended.
2. Every other codec the parse map names was tried as a
   replacement test item and is **rejected by this box's V4L2
   decoder**, each in its own dialect: VP9 (gst- and
   ffmpeg-muxed) prerolls then EOSes with zero frames; AV1 (both
   containers) fails preroll with `nvv4l2decoder` error **801
   "Feature not supported on this GPU"**; MJPEG fails with
   "Device '/dev/nvidia0' has no supported format". No local
   encoder exists for MPEG-2/VC-1. So the DECODE_PARSE map
   advertises inputs the hardware cannot decode; on this box the
   transcode stack's decodable inputs are H.264/HEVC in practice.
3. The transcode branch itself is unchanged by this lane and
   **did complete in-player today** under the current code:
   run 1 (below) session `2c978b8a`, ball-1080-h265 as transcode,
   stop row `frames: 1800, fps_draw: 131.3` in the deployed
   ledger — in family with run 4's 138.1.
4. Run 3's attempt to re-prove the stack at gst level wedged in
   V4L2 **preroll** (decoder in an uninterruptible ioctl after
   this lane's many killed decoder probes; `timeout`'s TERM was
   ignored, hence `timeout -k` in acceptance.sh now). The suite
   was stopped there rather than left hanging; sections
   (a2)–(e) evidence stands from run 2.

## Defects found on the way (this lane's runs earn their keep too)

1. **Run 1 served the wrong library**: player.py's env defaults
   are home-based, so the scratch deployment silently used the
   *deployed* copy's media/work/ledger (and its probes, timing
   out under load at server start, flipped items to transcode).
   acceptance.sh now pins PLAYER_MEDIA_DIR/WORK/LEDGER to its own
   directory in start_server. Run 1's rows remain in the deployed
   ledger (append-only is append-only); its work dirs were
   removed.
2. **Run 2 (a) harness**: the first VP9 test file was generated
   with `vp9enc deadline=1`, which dropped every frame — the
   transcode "failure" was the fixture's, caught by packet
   counting the source (0 real frames vs ffprobe's stream
   header). Superseded by finding 2 above. Run 2's (e) also
   recorded one harness FAIL that was not one: the mode check
   grepped for `"mode": "fmp4"` (with space) against FastAPI's
   compact JSON (`"mode":"fmp4"`); the check now parses the JSON.
   Run 3 carried both harness fixes but was stopped in (a)
   (finding 4) before re-exercising them.
3. **Observed wart, not fixed (out of this lane's scope)**: a
   transcode source that EOSes instantly with an empty segment
   (the VP9 case) is marked `ready` with 0 frames —
   playlist_ready() accepts any seg*.ts. Worth a frame-count
   floor in finish(); recorded here for the serve plane's next
   pass.

Box state after: no player/gst processes left by this lane
(one gst-launch from the wedged run-3 regression remained in
uninterruptible sleep, not consuming CPU; it does not hold the
port), port 8340 free, and the Slice-1 soak verified alive
(confluence-watch PID 1049389) before and after every run.
