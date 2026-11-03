#!/usr/bin/env python3
"""Tenancy-control proof for the real ingest (SPEC §2.2/§2.3).

Runs slice1/core's ingest.py (staged source) against a stub JEV
rack that counts its POSTs and answers with a constant 1280-dim
vector after a deliberate 200 ms — so embed_ms is ~200 and the
budget arithmetic is deterministic:

  PROVED HERE : the control file's three effects on the real
                ingest code path —
                (a) budget admission in rank order: with a 0.5
                    embed-s/h budget, frame 0 admits exactly 2
                    tiles and sheds 14 (frame_end says so), and
                    the cut frame sheds all 16 and reports itself
                    at the reflex tier instead of going silent;
                (b) decision_enabled=false: zero rack calls,
                    reflex lines naming the nominated tiles on
                    the baseline and cut frames, shed stays 0
                    (yielding is not shedding);
                (c) no control file at all: the pre-ladder
                    behaviour, byte for byte in counts — frame 0
                    and the cut embed all 16 tiles each.
  NOT PROVED  : verdicts (the stub's embeddings are constant —
                same caveat as prove_fixtures.py), and the ladder
                itself, which is Rust-side and covered by
                tests/tenancy.rs.

Exit 0 iff every assertion holds.
"""
import json, os, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.dirname(HERE)
INGEST = os.path.join(CORE, "ingest", "ingest.py")

posts = {"n": 0}
lock = threading.Lock()


class StubRack(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(n)
        time.sleep(0.2)
        with lock:
            posts["n"] += 1
        body = json.dumps({"embedding": [0.001] * 1280}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def run_ingest(control):
    """Run the staged ingest for 6 frames; return (posts, lines)."""
    with lock:
        posts["n"] = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubRack)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = {k: v for k, v in os.environ.items()
           if k != "CONFLUENCE_CONTROL_FILE"}
    cmd = [sys.executable, INGEST, "--source", "staged", "--gate", "3.0",
           "--cadence-ms", "1", "--rack", f"http://127.0.0.1:{port}",
           "--max-frames", "6"]
    ctl_path = ""
    if control is not None:
        ctl_path = os.path.join(HERE, "control-test.json")
        with open(ctl_path, "w") as fh:
            json.dump(control, fh)
        cmd += ["--control", ctl_path]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=120, env=env, cwd=CORE)
    finally:
        server.shutdown()
        if ctl_path:
            os.unlink(ctl_path)
    assert out.returncode == 0, f"ingest failed: {out.stderr[-2000:]}"
    lines = [json.loads(l) for l in out.stdout.splitlines() if l.strip()]
    return posts["n"], lines


def frame_ends(lines):
    return {l["frame"]: l for l in lines if l.get("control") == "frame_end"}


def reflexes(lines):
    return {l["frame"]: l for l in lines if l.get("control") == "reflex"}


def main():
    # (a) Budget: 0.5 embed-s per rolling hour, ~0.2 s per embed.
    n, lines = run_ingest({"decision_enabled": True,
                           "budget_embed_s_per_hour": 0.5})
    fe, rf = frame_ends(lines), reflexes(lines)
    assert n == 2, f"budget run: expected 2 rack posts, got {n}"
    assert fe[0]["shed"] == 14, f"frame 0 must shed 14: {fe[0]}"
    assert fe[0]["nominated"] == 16
    assert fe[4]["shed"] == 16, f"cut frame must shed all 16: {fe[4]}"
    assert 4 in rf and len(rf[4]["nominated_tiles"]) == 16, \
        f"cut frame must report at the reflex tier: {rf}"
    assert rf[4]["decision_enabled"] is True
    print("PASS: budget admission (2 embedded, 14 shed, cut reflex-reported)")

    # (b) Decision yielded off: no rack calls at all.
    n, lines = run_ingest({"decision_enabled": False,
                           "budget_embed_s_per_hour": 150.0})
    fe, rf = frame_ends(lines), reflexes(lines)
    assert n == 0, f"yielded run: expected 0 rack posts, got {n}"
    assert set(rf) == {0, 4}, f"reflex frames must be baseline+cut: {set(rf)}"
    assert len(rf[0]["nominated_tiles"]) == 16
    assert rf[0]["decision_enabled"] is False
    assert all(l["shed"] == 0 for l in fe.values()), \
        "yielding is not shedding — shed must stay 0"
    print("PASS: decision off (0 posts, reflex verdicts on frames 0 and 4)")

    # (c) No control: pre-ladder behaviour (baseline + cut, 16 each).
    n, lines = run_ingest(None)
    fe, rf = frame_ends(lines), reflexes(lines)
    assert n == 32, f"uncontrolled run: expected 32 rack posts, got {n}"
    assert all(l["shed"] == 0 for l in fe.values())
    assert not rf, f"no reflex lines without control pressure: {rf}"
    print("PASS: no control file (32 posts, unchanged behaviour)")

    print("INGEST TENANCY-CONTROL PROOF: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
