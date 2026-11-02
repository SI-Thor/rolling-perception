#!/bin/bash
# Confluence Slice 1 (core lane) acceptance, run ON THE THOR from
# ~/confluence-play/slice1/core. Three parts:
#   1. cargo test (parity / ledger / service-interface)
#   2. staged-events run through the real rack: cut + object must
#      publish, drift must not; rack started by the service and
#      stopped by it again (state restored as found)
#   3. wave-3 sequence C (a real cut at every boundary) through the
#      replay source: a verdict on every cut frame
#   4. phone-interface run: staged frames served over localhost HTTP
#      (shot.jpg) and ingested via the shot source — the exact code
#      path the phone will use
# Exits non-zero on the first failed check; prints numbers as it goes.
set -u
export PATH=$HOME/.cargo/bin:$PATH
cd "$(dirname "$0")"
BIN=./target/release/confluence-watch
PY="python3 ingest/ingest.py"
FAIL=0
check() { # name, ok(0/1)
  if [ "$2" = "0" ]; then echo "PASS: $1"; else echo "FAIL: $1"; FAIL=1; fi
}

echo "=== 1. cargo test ==="
cargo test --release 2>&1 | grep -E "test result" || { echo "FAIL: cargo test"; exit 1; }
cargo build --release 2>&1 | tail -1

rack_state() { systemctl is-active jev-rack 2>/dev/null || true; }
echo "rack before: $(rack_state)"

echo "=== 2. staged events (real rack) ==="
rm -rf run-staged
cat > staged.conf <<EOF
stream_id = staged
ledger_dir = run-staged/ledger
ingest_cmd = $PY --source staged --gate 3.0 --cadence-ms 50 --truth-out run-staged/truth.json
rack_autostart = true
stop_rack_on_exit = true
max_frames = 18
EOF
mkdir -p run-staged
$BIN --config staged.conf > run-staged/summary.json 2> run-staged/service.log
echo "summary: $(cat run-staged/summary.json)"
python3 - <<'PYEOF'
import json, sys
ev = [json.loads(l) for l in open("run-staged/ledger/events.jsonl")]
verd = {e["frame"]: e for e in ev if e.get("kind") == "verdict"}
truth = json.load(open("run-staged/truth.json"))
ok = True
def chk(name, cond):
    global ok
    print(("PASS: " if cond else "FAIL: ") + name)
    ok = ok and cond
cut = truth["cut_frame"]; obj = truth["object_frame"]
chk(f"cut frame {cut} published", cut in verd)
chk(f"cut frame flags most tiles ({len(verd.get(cut, {}).get('changed_tiles', []))}/16)",
    len(verd.get(cut, {}).get("changed_tiles", [])) >= 12)
chk(f"object frame {obj} published", obj in verd)
chk(f"object tiles {truth['object_tiles']} flagged",
    set(truth["object_tiles"]) <= set(verd.get(obj, {}).get("changed_tiles", [])))
drift_hits = [f for f in truth["drift_frames"] if f in verd]
chk(f"drift frames {truth['drift_frames']} publish nothing (hits: {drift_hits})",
    not drift_hits)
for f, e in sorted(verd.items()):
    print(f"  frame {f}: changed={e['changed_tiles']} latency_ms={e['verdict_latency_ms']:.1f} "
          f"embeds={e['embeds_this_frame']} lineage={e['lineage_mask']}")
state = open("run-staged/ledger/state.txt").read()
print("state:", " | ".join(l.strip() for l in state.splitlines()
      if any(k in l for k in ("embeds_spent_s", "estimate", "spend_ratio", "coverage"))))
sys.exit(0 if ok else 1)
PYEOF
check "staged events 3/3 (cut, object, drift-silent)" $?

echo "rack after staged: $(rack_state) (service started it; service must have stopped it)"
[ "$(rack_state)" = "inactive" ]; check "rack restored to inactive" $?

echo "=== 3. wave-3 sequence C (real frames, cut every boundary) ==="
rm -rf run-wave3
cat > wave3.conf <<EOF
stream_id = wave3-c
ledger_dir = run-wave3/ledger
ingest_cmd = $PY --source wave3 --seq C --gate 3.0 --cadence-ms 10
rack_autostart = true
stop_rack_on_exit = true
max_frames = 12
EOF
mkdir -p run-wave3
$BIN --config wave3.conf > run-wave3/summary.json 2> run-wave3/service.log
echo "summary: $(cat run-wave3/summary.json)"
python3 - <<'PYEOF'
import json, sys
ev = [json.loads(l) for l in open("run-wave3/ledger/events.jsonl")]
verd = {e["frame"]: e for e in ev if e.get("kind") == "verdict"}
ok = True
missing = [f for f in range(1, 12) if f not in verd]
print(("PASS: " if not missing else "FAIL: ") +
      f"verdict on every cut frame 1..11 (missing: {missing})")
ok = not missing
full = [f for f in range(1, 12) if len(verd.get(f, {}).get("changed_tiles", [])) == 16]
print(f"  frames flagging all 16 tiles: {len(full)}/11")
sys.exit(0 if ok else 1)
PYEOF
check "wave3 C cuts 11/11" $?
echo "rack after wave3: $(rack_state)"
[ "$(rack_state)" = "inactive" ]; check "rack restored to inactive (2)" $?

echo "=== 4. phone interface (shot.jpg over HTTP, localhost stand-in) ==="
rm -rf run-shot
python3 test-server.py --port 8901 &
SRV=$!
sleep 1
cat > shot.conf <<EOF
stream_id = phone-standin
ledger_dir = run-shot/ledger
ingest_cmd = $PY --source shot --url http://127.0.0.1:8901/shot.jpg --gate 3.0 --cadence-ms 50 --max-frames 18
rack_autostart = true
stop_rack_on_exit = true
max_frames = 18
EOF
mkdir -p run-shot
$BIN --config shot.conf > run-shot/summary.json 2> run-shot/service.log
kill $SRV 2>/dev/null
echo "summary: $(cat run-shot/summary.json)"
python3 - <<'PYEOF'
import json, sys
ev = [json.loads(l) for l in open("run-shot/ledger/events.jsonl")]
verd = {e["frame"]: e for e in ev if e.get("kind") == "verdict"}
ok = 4 in verd and 7 in verd and not any(f in verd for f in range(10, 18))
print(("PASS: " if ok else "FAIL: ") +
      f"shot.jpg path: cut+object published, drift silent (verdict frames: {sorted(verd)})")
sys.exit(0 if ok else 1)
PYEOF
check "shot interface staged events" $?
echo "rack after shot: $(rack_state)"
[ "$(rack_state)" = "inactive" ]; check "rack restored to inactive (3)" $?

echo "=== leftover processes ==="
pgrep -af "confluence-watch|ingest.py|test-server" || echo "none"
[ $FAIL = 0 ] && echo "ACCEPTANCE: ALL PASS" || echo "ACCEPTANCE: FAILURES ABOVE"
exit $FAIL
