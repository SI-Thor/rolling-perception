# Slice 1 live camera — the ProArt route (lane S1-PROCAM, 2026-11-01)

Casey's phone is off the LAN (he's away); he directed: use the
ProArt's camera as the live source. Result: a real webcam on the
ProArt is feeding confluence-watch on the Thor, gate-calibrated on
the real scene, and the 48 h soak is RUNNING (started 2026-11-01
18:18 AKST, completes 2026-11-03 18:18 AKST; control sheet in
`~/confluence-play/slice1/SOAK.md` on the Thor).

## Route taken — and the two that failed, with evidence

1. **WSL v4l2 — dead end.** `/dev/video*` does not exist in the
   ProArt's WSL. Nothing to capture from.
2. **usbipd — blocked by elevation, as briefed.** usbipd-win is
   installed; `usbipd list` shows the camera (BUSID 4-1,
   3277:0059, "ASUS FHD webcam, ASUS IR camera") in state
   **Not shared**. Sharing (bind) requires an admin prompt; the
   user is absent, so this route was skipped by design.
3. **Windows-side capture — WON, in two attempts.**
   - *VLC attempt (failed):* no ffmpeg.exe exists anywhere on the
     Windows side (PATH, winget, scoop, Program Files, bounded
     find all empty), but VLC is installed. VLC's dshow → HTTP
     MJPEG never produced a listener: startup stalls on a stale
     plugin-cache rebuild, iterations left zombie processes, and
     no frame ever crossed. Abandoned on evidence.
   - *Python + OpenCV (works):* Windows Python 3.12 had no cv2;
     `pip install --user opencv-python-headless` (user scope, no
     admin) added cv2 5.0.0. A small server captured the camera
     (DirectShow idx 0, 1280×720) immediately — but served only to
     Windows-localhost: **the Windows Firewall drops unsolicited
     inbound on the Wi-Fi interface** for processes with no rule,
     from both the LAN (Thor: connect timeout) and WSL (gateway
     IP). A firewall rule needs admin.
   - *Direction flip (the fix):* the camera side dials OUT.
     `C:\Users\casey\proart-push.py` (Windows python.exe PID 42356)
     captures the ASUS FHD webcam and POSTs a JPEG ~2×/s to a
     40-line stdlib receiver on the Thor
     (`~/confluence-play/slice1/push-receiver.py`, PID 651692,
     port 8091), which re-serves `/shot.jpg` and `/stream` on the
     Thor's loopback/LAN. confluence-watch's `shot` ingest polls
     `http://127.0.0.1:8091/shot.jpg` — the exact interface the
     phone will use later; only the transport behind it differs.
     Stream URL shape (no credentials anywhere):
     pusher → `http://<thor-lan-ip>:8091/push` (POST),
     service → `http://127.0.0.1:8091/shot.jpg` (GET).

## Proof the frames are the real room

A frame pulled through the full chain (camera → pusher → Thor
receiver → /shot.jpg) was viewed by the agent: a wood-panelled
room shot from laptop-lid angle — exposed ceiling beams with
translucent panels under warm light, an acoustic guitar hanging
on the panelled wall, a framed picture beside it, a bright
daylight doorway at the back, shelving and a fridge with papers
at the right edge. Capture stats agree: 1280×720, mean brightness
≈63 (a dim, warm, lit interior; the second DirectShow device —
the IR camera — read mean 0.0 and was not selected). Frame copies
were not kept outside the Thor play area; the verification copy
was deleted after viewing.

## Gate calibration on the real scene (Thor, live feed)

Sweep, 180 frames per gate against the still night room:

| gate | frames | tiles nominated | events | notes |
|------|--------|-----------------|--------|-------|
| 3.0  | 180 | 16 | 0 | all 16 nominations are frame 1 (cold-start baseline) |
| 4.5  | 180 | 16 | 0 | identical |
| 6.0  | 180 | 16 | 0 | identical |
| 8.0  | 180 | 16 | 0 | identical |

The diffs this scene produces sit below even the most sensitive
gate after the baseline frame — the gate is not the binding
parameter at night; sensitivity is free, so the soak runs the
**lowest gate tested, 3.0**. Final still window at gate 3.0:
**1200 frames, 16 nominations total (frame 1 only), 0 events,
embed spend ratio 0.0008** — steady-state nomination rate 0 in
1199 consecutive still frames.

Sensitivity at the same gate, validated by replaying the staged
event rig through gate 3.0: scene cut → verdict, 16/16 tiles;
object appearing → verdict, exactly tiles {5,6}; gradual drift →
silent. Quiet when still, exact when it matters.

Honest caveat: calibration is a night measurement. Daylight will
raise scene dynamics; the lens carries the gate per-stream
(state.txt / lens.txt in the soak ledger will show it if the
daytime nomination rate climbs).

## Soak status

RUNNING. confluence-watch PID 1049389 (Thor), soak mode, config
`~/confluence-play/slice1/core/proart.conf`, ledger
`run-proart/ledger/`. Verified at start: frames_seen advancing
(98 → 137 in 20 s), rack up (started and owned by the service),
`silence_meaningful = true`, receiver age 0.08 s. Stop procedure
and all PIDs: `~/confluence-play/slice1/SOAK.md` on the Thor —
stop is `touch run-proart/STOP` (the service then stops the rack
it started), plus killing the receiver and the Windows pusher.

Rig lessons banked: (1) interop Windows .exe processes swallow
the remainder of a `bash -s` script's stdin — drive them from
script files with stdin redirected; (2) WSL `timeout` does not
kill Windows children — taskkill by name/PID; (3) a second VLC
instance defers to the first, so crashed tests leave camera-hog
ghosts — enumerate processes before relaunching.
