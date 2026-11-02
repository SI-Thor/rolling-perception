#!/usr/bin/env python3
"""Resident Piper synthesis worker for Confluence presence.

Spawn-per-call Piper cost ~2 s per reply on the Thor (process start +
ONNX model load, every time). This worker loads the voice ONCE and
serves text -> WAV over a unix socket:

    request : one line of UTF-8 text
    reply   : "OK <nbytes>\\n" followed by n bytes of WAV
              or "ERR <message>\\n"

Run it with the radio-room venv python (that's where piper lives):

    ~/radio-room-thor/.venv/bin/python piper_worker.py \
        --sock ~/confluence-play/slice2/piper.sock \
        --model ~/radio-room-thor/voices/en_US-lessac-medium.onnx

Discipline (Slice-1 style): started on demand — presence.py starts
it lazily on the first /hear that needs it and stops it on backend
shutdown when the backend owns it — or started explicitly with the
command above. Never a systemd resident. Stop: SIGTERM/SIGINT, or
kill the PID printed in the log; the socket file is removed by the
next start.
"""
import argparse
import io
import socket
import sys
import wave
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sock", required=True, help="unix socket path")
    ap.add_argument("--model", required=True, help="Piper .onnx voice")
    args = ap.parse_args()

    from piper.voice import PiperVoice
    voice = PiperVoice.load(args.model)

    sock_path = Path(args.sock)
    sock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        sock_path.unlink()
    except FileNotFoundError:
        pass
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(sock_path))
    srv.listen(8)
    print(f"PIPER_WORKER_READY sock={sock_path} model={args.model}",
          flush=True)

    while True:
        conn, _ = srv.accept()
        with conn:
            try:
                buf = b""
                while b"\n" not in buf:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
                text = buf.split(b"\n", 1)[0].decode(
                    "utf-8", "replace").strip()
                if not text:
                    continue  # bare connect = health ping; just close
                out = io.BytesIO()
                with wave.open(out, "wb") as wf:
                    voice.synthesize_wav(text, wf)
                data = out.getvalue()
                conn.sendall(f"OK {len(data)}\n".encode() + data)
            except Exception as e:  # one bad request must not kill us
                try:
                    conn.sendall(f"ERR {e}\n".encode()[:200])
                except Exception:
                    pass


if __name__ == "__main__":
    sys.exit(main())
