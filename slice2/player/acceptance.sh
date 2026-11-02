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
  (cd "$PLAY" && exec env PLAYER_PHANTOM_UNITS="$1" PLAYER_PORT=8340 \
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
ls -la "$PLAY/media"
start_server 0

say "(a) transcode chain: hevc item -> HLS"
out=$(post_play ball-1080-h265); echo "$out"
sid=$(echo "$out" | head -1 | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('session',''))" 2>/dev/null)
st=$(wait_ready "$sid"); echo "session $sid status: $st"
[ "$st" = "ready" ] && pass "transcode session ready" || fail "transcode session status $st"
pl_code=$(curl -s -o /tmp/pl.m3u8 -w "%{http_code}" "$BASE/play/ball-1080-h265")
echo "GET /play/ball-1080-h265 -> $pl_code"; cat /tmp/pl.m3u8
[ "$pl_code" = "200" ] && pass "playlist 200" || fail "playlist $pl_code"
nseg=0
for segurl in $(grep -o '/hls/[^ ]*\.ts' /tmp/pl.m3u8 | head -3); do
  code=$(curl -s -o /tmp/seg.ts -w "%{http_code}" "$BASE$segurl")
  echo "segment $segurl -> $code"
  [ "$code" = "200" ] && nseg=$((nseg+1))
done
[ "$nseg" -ge 3 ] && pass ">=3 segments served 200" || fail "only $nseg segments 200"
firstseg=$(grep -o '/hls/[^ ]*\.ts' /tmp/pl.m3u8 | head -1)
curl -s -o /tmp/seg0.ts "$BASE$firstseg"
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height -of default=noprint_wrappers=1 /tmp/seg0.ts

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
out=$(post_play ball-1080-h265); echo "$out"
echo "$out" | tail -1 | grep -q "429" && echo "$out" | grep -qi "busy" \
  && pass "transcode refused 429 'house is busy' at budget cap" || fail "transcode not refused at cap"
out=$(post_play hero); echo "$out"
sid4=$(echo "$out" | head -1 | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('session',''))" 2>/dev/null)
st=$(wait_ready "$sid4"); echo "remux-under-cap session status: $st"
rcode=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/play/hero")
echo "GET /play/hero under cap -> $rcode"
[ "$st" = "ready" ] && [ "$rcode" = "200" ] && pass "remux still serves under transcode cap" \
  || fail "remux blocked under cap (status $st, playlist $rcode)"
grep '"event": "refused"' "$PLAY/ledger/sessions.jsonl" | tail -1
stop_server

say "verdict"
[ "$FAILED" = "0" ] && echo "ACCEPTANCE: ALL PASS" || echo "ACCEPTANCE: FAILURES PRESENT"
exit $FAILED
