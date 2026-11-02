#!/usr/bin/env python3
"""Validate an HLS-fMP4 session directory — the fMP4 spike's
checklist (fmp4-spike/RESULTS.md §4) as code. Stdlib + ffprobe only.

Checks:
  1. playlist.m3u8 parses as text: #EXT-X-MAP present and pointing
     at an existing init segment; every listed media segment
     exists; EXTINF durations sum to the expected duration
     (--duration, tolerance --tol) when one is given.
  2. The init segment probes (ffprobe) as codec hevc with
     codec_tag_string hvc1, and its moov carries mvex + hvcC.
  3. Every media segment: contains at least one moof; every moof's
     tfhd has default-base-is-moof set (the production patch);
     the first moof's first sample is a sync sample; and init +
     segment, packet-counted with ffprobe, yields exactly the
     sample count segments.json records for that segment.

Claim discipline: green here means "spec-conformant by checklist +
probe" — no Apple-client playback is claimed or implied.

Usage: verify_fmp4.py <session-dir> [--duration SECONDS] [--tol S]
Prints one PASS/FAIL line per check; exit 1 if anything failed.
"""
import argparse
import json
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fmp4_split import read_boxes, parse_moov, parse_moof

FAILED = 0


def check(ok, label, detail=""):
    global FAILED
    print(("PASS " if ok else "FAIL ") + label + (f" — {detail}" if detail else ""))
    if not ok:
        FAILED = 1


def packet_count(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
         "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, timeout=30)
    for tok in (out.stdout or "").split():
        if tok.isdigit():
            return int(tok)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--duration", type=float, default=None)
    ap.add_argument("--tol", type=float, default=0.75)
    a = ap.parse_args()
    d = Path(a.dir)

    pl = d / "playlist.m3u8"
    check(pl.is_file(), "playlist exists", str(pl))
    if not pl.is_file():
        return 1
    lines = [ln.strip() for ln in pl.read_text(errors="replace").splitlines() if ln.strip()]
    map_lines = [ln for ln in lines if ln.startswith("#EXT-X-MAP:")]
    check(len(map_lines) == 1, "playlist carries exactly one EXT-X-MAP",
          map_lines[0] if map_lines else "none")
    init_name = None
    if map_lines and 'URI="' in map_lines[0]:
        init_name = map_lines[0].split('URI="', 1)[1].split('"', 1)[0].split("/")[-1]
    init = d / (init_name or "init.mp4")
    check(init.is_file(), "init segment exists", init.name)
    extinf = [float(ln.split(":", 1)[1].rstrip(",")) for ln in lines
              if ln.startswith("#EXTINF:")]
    segs = [ln.split("/")[-1] for ln in lines
            if not ln.startswith("#") and ln.endswith(".m4s")]
    check(len(segs) == len(extinf) and len(segs) > 0,
          "one EXTINF per media segment", f"{len(segs)} segments")
    total = sum(extinf)
    if a.duration is not None:
        check(abs(total - a.duration) <= a.tol,
              "EXTINF sum matches expected duration",
              f"sum={total:.3f}s expected={a.duration:.3f}s tol={a.tol}s")
    else:
        check(total > 0, "EXTINF sum positive", f"sum={total:.3f}s")
    check(all((d / s).is_file() for s in segs), "every listed segment exists on disk")

    sj = d / "segments.json"
    recorded = {}
    if sj.is_file():
        try:
            recorded = {s["file"]: s for s in json.loads(sj.read_text()).get("segments", [])}
        except Exception:
            recorded = {}

    if init.is_file():
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name,codec_tag_string", "-of", "json", str(init)],
            capture_output=True, text=True, timeout=15)
        try:
            st = (json.loads(out.stdout or "{}").get("streams") or [{}])[0]
        except ValueError:
            st = {}
        check(st.get("codec_name") == "hevc" and st.get("codec_tag_string") == "hvc1",
              "init probes hevc/hvc1", f"{st.get('codec_name')}/{st.get('codec_tag_string')}")
        ibuf = init.read_bytes()
        top = list(read_boxes(ibuf))
        moov = next(((p, s) for p, s, h, t in top if t == "moov"), None)
        info = parse_moov(ibuf, moov[0], moov[1]) if moov else {}
        check(bool(info.get("has_mvex")) and bool(info.get("has_hvcC"))
              and info.get("sample_entry") == "hvc1",
              "init moov carries mvex + hvcC, sample entry hvc1", str(info))

    init_bytes = init.read_bytes() if init.is_file() else b""
    for name in segs:
        f = d / name
        if not f.is_file():
            check(False, f"{name}: present for structural checks")
            continue
        buf = f.read_bytes()
        moofs = [(p, s) for p, s, h, t in read_boxes(buf) if t == "moof"]
        check(len(moofs) >= 1 and b"mdat" in buf, f"{name}: moof+mdat present",
              f"{len(moofs)} moof(s)")
        infos = [parse_moof(buf, p, s) for p, s in moofs]
        check(all(i.get("default_base_is_moof") for i in infos),
              f"{name}: tfhd default-base-is-moof set on every moof")
        check(infos and not infos[0].get("first_sample_non_sync", True),
              f"{name}: first sample is a sync sample (keyframe)")
        want = (recorded.get(name) or {}).get("samples")
        if want is not None:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
                tf.write(init_bytes + buf)
                tmp = tf.name
            try:
                got = packet_count(tmp)
            finally:
                Path(tmp).unlink(missing_ok=True)
            check(got == want, f"{name}: init+segment packet count == recorded samples",
                  f"got={got} want={want}")
    print("VERIFY-FMP4: " + ("ALL PASS" if not FAILED else "FAILURES PRESENT"))
    return FAILED


if __name__ == "__main__":
    sys.exit(main())
