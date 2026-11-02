#!/usr/bin/env python3
"""FMP4 session worker for player.py — one HEVC item -> HLS-fMP4.

The production form of fmp4-spike/pipeline.sh (spike RESULTS.md:
spec-conformant by checklist + probe, ~0.09 s per 60 s item, zero
encode). Two steps, both idempotent — re-running overwrites the
same init/segments/playlist and removes the intermediate:

  1. GStreamer remux (parse-only, no decode/encode):
     filesrc ! <demux> ! h265parse ! mp4mux fragment-duration=3000
     streamable=true ! filesink .stream.mp4
     mp4mux cuts at the duration target OR the next keyframe, so
     fragment boundaries tile the source GOP grid.
  2. build_hls.py (beside this file, copied from the spike): split
     into init.mp4 + GOP-aligned seg_*.m4s (grouping at sync-start
     fragments), patch every moof's tfhd default-base-is-moof bit
     in place, write playlist.m3u8 + segments.json.

Usage: fmp4_pipeline.py <source> <outdir> [demux-element]
Exit code is the failing step's, or build_hls.py's on success path.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    src, outdir = Path(sys.argv[1]), Path(sys.argv[2])
    demux = sys.argv[3] if len(sys.argv) > 3 else "qtdemux"
    outdir.mkdir(parents=True, exist_ok=True)
    stream = outdir / ".stream.mp4"
    gst = ["gst-launch-1.0", "-q", "filesrc", f"location={src}", "!",
           demux, "name=d", "d.video_0", "!", "queue", "!",
           "h265parse", "!", "mp4mux", "fragment-duration=3000",
           "streamable=true", "!", "filesink", f"location={stream}"]
    r = subprocess.run(gst)
    if r.returncode != 0:
        stream.unlink(missing_ok=True)
        return r.returncode or 1
    r = subprocess.run([sys.executable, str(HERE / "build_hls.py"),
                        str(stream), str(outdir)])
    stream.unlink(missing_ok=True)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
