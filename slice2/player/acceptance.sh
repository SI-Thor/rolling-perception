#!/usr/bin/env bash
# Confluence Slice 2 player — acceptance, run ON the Thor.
# Starts its own server instances (phantom 0, then phantom 8) on
# :8340, runs tests (a)-(d) from the spike brief, prints evidence,
# and leaves nothing running. Tee stdout to RESULTS.md's evidence.
set -u
PLAY="${PLAYER_HOME:-$HOME/confluence-play/slice2/player}"
PY="$HOME/ml/.venv/bin/python"
BASE="http://127.0.0.1:8340"
SRV_PID=""

say() { echo; echo "=== $* ==="; }
fail() { echo "FAIL: $*"; FAILED=1; }
pass() { echo "PASS: $*"; }
FAILED=0

start_server() {  # $1 = phantom units
  # Pin media/work/ledger to $PLAY itself: player.py's env defaults
  # are home-based (~/confluence-play/slice2/player/...), so a
  # scratch copy run without these would silently serve and write
  # the deployed copy's dirs (observed 2026-11-02, fMP4 run 1).
  (cd "$PLAY" && exec env PLAYER_PHANTOM_UNITS="$1" PLAYER_PORT=8340 \
     PLAYER_MEDIA_DIR="$PLAY/media" PLAYER_WORK_DIR="$PLAY/work" \
     PLAYER_LEDGER_DIR="$PLAY/ledger" \
     "$PY" player.py > "server-phantom$1.log" 2>&1) &
  SRV_PID=$!
  for i in $(seq 1 30); do
    curl -s -o /dev/null "$BASE/api/library" && return 0
    sleep 0.5
  done
  echo "server did not come up"; cat "$PLAY/server-phantom$1.log"; exit 1
}
stop_server() {
  [ -n "$SRV_PID" ] && kill "$SRV_PID" 2>/dev/null
  for i in $(seq 1 20); do curl -s -o /dev/null --max-time 1 "$BASE/api/library" || break; sleep 0.5; done
  SRV_PID=""
}
wait_ready() {  # $1 = session id -> echoes final status
  for i in $(seq 1 120); do
    st=$(curl -s "$BASE/api/session/$1" | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('status',''))" 2>/dev/null)
    case "$st" in ready|failed) echo "$st"; return 0;; esac
    sleep 0.5
  done
  echo "timeout"
}
post_play() { curl -s -w "\n%{http_code}" -X POST "$BASE/api/play" -H 'Content-Type: application/json' -d "{\"id\":\"$1\"}"; }

say "preflight: media in $PLAY/media"
if [ ! -f "$PLAY/media/test-vp9.webm" ]; then
  echo "generating test-vp9.webm (3 s VP9 720p — the transcode-chain item;"
  echo "ball-1080-h265 now takes the fMP4 path, section (e))"
  gst-launch-1.0 -q videotestsrc num-buffers=90 pattern=ball ! \
    video/x-raw,width=1280,height=720,framerate=30/1 ! vp9enc deadline=1 ! \
    matroskamux ! filesink location="$PLAY/media/test-vp9.webm" \
    || echo "WARN: vp9 generation failed; section (a)/(c) transcode checks will fail"
fi
ls -la "$PLAY/media"
start_server 0

say "(a) transcode chain: V4L2 stack regression + in-player admission"
echo "Why not an in-player transcode completion: HEVC (run 4's proven"
echo "transcode input) now routes to FMP4, and every other codec the"
echo "parse map names is rejected by this box's V4L2 decoder — VP9"
echo "silent EOS, AV1 error 801 'Feature not supported on this GPU',"
echo "MJPEG 'no supported format' (measured 2026-11-02, RESULTS.md)."
echo "So: the player's exact transcode pipeline (build_cmd's elements"
echo "and parameters) is re-run at gst level on the HEVC item, and the"
echo "player itself is checked for transcode ADMISSION + mode only."
rm -rf /tmp/transcode-regression && mkdir -p /tmp/transcode-regression
# timeout -k: a V4L2 preroll wedge ignores plain TERM (observed
# 2026-11-02, run 3 — the decoder sat in an uninterruptible ioctl
# after repeated killed decoder sessions; the suite must not hang
# on the box's state).
timeout -k 10 240 gst-launch-1.0 -e filesrc location="$PLAY/media/ball-1080-h265.mp4" ! \
  qtdemux name=d d.video_0 ! queue ! h265parse ! nvv4l2decoder ! nvvidconv ! \
  "video/x-raw(memory:NVMM),width=1920,height=1080,format=NV12" ! \
  nvv4l2h264enc bitrate=6000000 iframeinterval=120 control-rate=1 ! h264parse ! \
  hlssink2 playlist-location=/tmp/transcode-regression/playlist.m3u8 \
  location=/tmp/transcode-regression/seg%05d.ts target-duration=4 \
  playlist-length=0 max-files=0 > /tmp/transcode-regression.log 2>&1
pkts=0
for f in /tmp/transcode-regression/seg*.ts; do
  n=$(ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of csv=p=0 "$f" 2>/dev/null | grep -o '^[0-9]*' | head -1)
  pkts=$((pkts + ${n:-0}))
done
echo "transcode regression: $pkts video packets across $(ls /tmp/transcode-regression/seg*.ts 2>/dev/null | wc -l) segments (expect 1800)"
[ "$pkts" = "1800" ] && pass "V4L2 transcode stack: 1800/1800 frames (run-4 configuration)" \
  || fail "transcode regression counted $pkts packets"
out=$(post_play test-vp9); echo "$out"
echo "$out" | head -1 | "$PY" -c "import sys,json;d=json.load(sys.stdin);assert d.get('mode')=='transcode' and d.get('units')==1" 2>/dev/null \
  && pass "player admits the vp9 item as a transcode session (mode=transcode, units=1)" \
  || fail "player did not admit vp9 as transcode: $out"
echo "note: that session cannot complete on this box (VP9 rejected by the"
echo "V4L2 decoder, silent EOS) — completion is asserted at gst level above"
echo "for the codec the stack can actually decode, not in-player for VP9."

say "(a2) remux chain: h264 library item (hero) -> HLS"
out=$(post_play hero); echo "$out"
sid2=$(echo "$out" | head -1 | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('session',''))" 2>/dev/null)
st=$(wait_ready "$sid2"); echo "session $sid2 status: $st"
rcode=$(curl -s -o /tmp/pl2.m3u8 -w "%{http_code}" "$BASE/play/hero")
echo "GET /play/hero -> $rcode"; cat /tmp/pl2.m3u8
[ "$rcode" = "200" ] && pass "remux playlist 200" || fail "remux playlist $rcode"
seg2=$(grep -o '/hls/[^ ]*\.ts' /tmp/pl2.m3u8 | head -1)
curl -s -o /tmp/seg2.ts "$BASE$seg2"
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height -of default=noprint_wrappers=1 /tmp/seg2.ts

say "(e) fMP4 chain: hevc item -> HLS-fMP4 (remux, 0 encode-fps)"
out=$(post_play ball-1080-h265); echo "$out"
echo "$out" | head -1 | "$PY" -c "import sys,json;d=json.load(sys.stdin);assert d.get('mode')=='fmp4' and d.get('units')==0" 2>/dev/null \
  && pass "hevc item assigned mode=fmp4, units=0" \
  || fail "hevc item not in fmp4 mode / units not 0: $out"
sid5=$(echo "$out" | head -1 | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('session',''))" 2>/dev/null)
st=$(wait_ready "$sid5"); echo "session $sid5 status: $st"
[ "$st" = "ready" ] && pass "fmp4 session ready" || fail "fmp4 session status $st"
fcode=$(curl -s -o /tmp/pl5.m3u8 -w "%{http_code}" "$BASE/play/ball-1080-h265")
echo "GET /play/ball-1080-h265 -> $fcode"; cat /tmp/pl5.m3u8
[ "$fcode" = "200" ] && pass "fmp4 playlist 200" || fail "fmp4 playlist $fcode"
grep -q "EXT-X-MAP" /tmp/pl5.m3u8 && pass "served playlist carries EXT-X-MAP" || fail "no EXT-X-MAP in served playlist"
initurl=$(grep -o '/hls/[^"]*init\.mp4' /tmp/pl5.m3u8 | head -1)
segurl=$(grep -o '/hls/[^ ]*\.m4s' /tmp/pl5.m3u8 | head -1)
icode=$(curl -s -o /tmp/init.mp4 -w "%{http_code}" "$BASE$initurl")
scode=$(curl -s -o /tmp/seg.m4s -w "%{http_code}" "$BASE$segurl")
echo "init $initurl -> $icode ; segment $segurl -> $scode"
[ "$icode" = "200" ] && [ "$scode" = "200" ] && pass "init + media segment served 200" \
  || fail "init/segment codes $icode/$scode"
"$PY" "$PLAY/verify_fmp4.py" "$PLAY/work/$sid5" --duration 60
[ "$?" = "0" ] && pass "verify_fmp4 validators green on the served session" \
  || fail "verify_fmp4 reported failures on the served session"
grep "\"session\": \"$sid5\"" "$PLAY/ledger/sessions.jsonl" | grep '"event": "stop"' | tail -1
grep "\"session\": \"$sid5\"" "$PLAY/ledger/sessions.jsonl" | grep '"event": "stop"' | grep -q '"mode": "fmp4"' \
  && grep "\"session\": \"$sid5\"" "$PLAY/ledger/sessions.jsonl" | grep '"event": "stop"' | grep -q '"fps_draw": 0.0' \
  && pass "registry: fmp4 stop row carries fps_draw 0.0 (remux charged 0 encode-fps)" \
  || fail "registry fmp4 stop row missing or fps_draw not 0.0"

say "(b) registry: sessions with mode + measured fps draw"
curl -s "$BASE/api/sessions" | "$PY" -m json.tool | head -40
echo "--- sessions.jsonl (stop/failed rows) ---"
grep -E '"event": "(stop|failed)"' "$PLAY/ledger/sessions.jsonl" | tail -4
grep -q '"mode": "transcode"' "$PLAY/ledger/sessions.jsonl" && grep -q '"fps_draw"' "$PLAY/ledger/sessions.jsonl" \
  && pass "registry carries transcode session with fps_draw" || fail "registry missing mode/fps_draw"

say "(d) watchdog: stall source (fifo, process alive, zero frames)"
out=$(post_play stall); echo "$out"
sid3=$(echo "$out" | head -1 | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('session',''))" 2>/dev/null)
final=""
for i in $(seq 1 50); do
  row=$(curl -s "$BASE/api/session/$sid3")
  st=$(echo "$row" | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('status',''))" 2>/dev/null)
  if [ "$st" = "failed" ]; then final="$row"; break; fi
  sleep 0.5
done
echo "stall session final: $final"
echo "$final" | grep -q "watchdog_stall" && pass "watchdog killed stalled worker, marked watchdog_stall" \
  || fail "stall session did not fail via watchdog: $final"
grep '"event": "failed"' "$PLAY/ledger/sessions.jsonl" | tail -2
pgrep -af "stall.fifo" && fail "stall worker still alive" || echo "no stall worker process remains"

stop_server

say "(c) budget refusal at phantom cap (PLAYER_PHANTOM_UNITS=8)"
start_server 8
out=$(post_play test-vp9); echo "$out"
echo "$out" | tail -1 | grep -q "429" && echo "$out" | grep -qi "busy" \
  && pass "transcode refused 429 'house is busy' at budget cap" || fail "transcode not refused at cap"
out=$(post_play hero); echo "$out"
sid4=$(echo "$out" | head -1 | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('session',''))" 2>/dev/null)
st=$(wait_ready "$sid4"); echo "remux-under-cap session status: $st"
rcode=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/play/hero")
echo "GET /play/hero under cap -> $rcode"
[ "$st" = "ready" ] && [ "$rcode" = "200" ] && pass "remux still serves under transcode cap" \
  || fail "remux blocked under cap (status $st, playlist $rcode)"
out=$(post_play ball-1080-h265); echo "$out"
sid6=$(echo "$out" | head -1 | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('session',''))" 2>/dev/null)
st=$(wait_ready "$sid6"); echo "fmp4-under-cap session status: $st"
fcode=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/play/ball-1080-h265")
echo "GET /play/ball-1080-h265 under cap -> $fcode"
[ "$st" = "ready" ] && [ "$fcode" = "200" ] && pass "fmp4 still serves under transcode cap" \
  || fail "fmp4 blocked under cap (status $st, playlist $fcode)"
grep '"event": "refused"' "$PLAY/ledger/sessions.jsonl" | tail -1
stop_server

say "verdict"
[ "$FAILED" = "0" ] && echo "ACCEPTANCE: ALL PASS" || echo "ACCEPTANCE: FAILURES PRESENT"
exit $FAILED
