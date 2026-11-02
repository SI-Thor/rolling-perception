#!/bin/sh
# fMP4 spike pipeline — HEVC item -> HLS-fMP4 (init + grouped segments + playlist)
# Ran on the Thor 2026-11-01 (see RESULTS.md). Remux only: no re-encode.
# Usage: ./pipeline.sh <hevc-source.mp4> <outdir>
set -e
SRC="$1"
OUT="$2"
DIR="$(dirname "$0")"

# 1. Remux to a fragmented MP4 stream (ftyp moov [moof mdat]...).
#    mp4mux cuts fragments at the fragment-duration target OR at the next
#    keyframe, whichever comes first — fragment boundaries therefore tile
#    the source GOP grid, which build_hls.py relies on when grouping.
gst-launch-1.0 -q filesrc location="$SRC" ! qtdemux ! h265parse ! \
  mp4mux fragment-duration=3000 streamable=true ! \
  filesink location="$OUT.stream.mp4"

# 2. Split into init segment + GOP-aligned media segments (several
#    fragments per segment is valid CMAF), patch tfhd
#    default-base-is-moof (see build_hls.py header), write playlist.
python3 "$DIR/build_hls.py" "$OUT.stream.mp4" "$OUT"
rm -f "$OUT.stream.mp4"
