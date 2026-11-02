#!/usr/bin/env python3
"""Build HLS-fMP4 (init + grouped media segments + VOD playlist) from a
fragmented MP4 whose fragments may be finer than the GOP grid.

Grouping rule (data-driven, from each fragment's own trun first-sample
flags): a new media segment starts at every fragment whose first sample
is a sync sample; other fragments join the open segment. A CMAF media
segment may contain several moof/mdat pairs.

Post-patch: GStreamer mp4mux leaves tfhd flags = 0. CMAF requires the
default-base-is-moof flag (0x020000). With no base-data-offset field
present, ISO 14496-12's implicit default already anchors data at the
enclosing moof, so setting the bit in place changes no offsets or
sizes; it makes the existing semantics explicit. Every moof's tfhd is
patched and the patch is reported.

Usage: build_hls.py input.fmp4 outdir
Writes: init.mp4, seg_001.m4s..., playlist.m3u8, segments.json
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fmp4_split import read_boxes, find_child, parse_moov, parse_moof


def patch_tfhd(buf, moof_pos, moof_size):
    traf = find_child(buf, moof_pos + 8, moof_size - 8, "traf")
    if not traf:
        return False
    tfhd = find_child(buf, traf[0] + 8, traf[1] - 8, "tfhd")
    if not tfhd:
        return False
    p, _, h = tfhd
    # version(1 byte) then flags(3 bytes, big-endian): the 0x020000 bit is
    # the 0x02 bit of the FIRST flags byte, at p+h+1.
    flag_byte = p + h + 1
    before = buf[flag_byte]
    buf[flag_byte] = before | 0x02
    return buf[flag_byte] != before


def main():
    src, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    buf = bytearray(open(src, "rb").read())
    top = list(read_boxes(bytes(buf)))
    moov_info, init_end, frag_pos = None, None, []
    pending = None
    for pos, size, hdr, typ in top:
        if typ == "moov":
            moov_info = parse_moov(bytes(buf), pos, size)
            init_end = pos + size
        elif typ == "moof":
            pending = (pos, size)
        elif typ == "mdat" and pending:
            frag_pos.append((pending[0], pos + size - pending[0]))
            pending = None
    init = b""
    for pos, size, hdr, typ in top:
        if pos >= init_end:
            break
        if typ in ("ftyp", "moov"):
            init += bytes(buf[pos:pos + size])
    open(os.path.join(outdir, "init.mp4"), "wb").write(init)
    ts = moov_info["track_timescale"] or moov_info["movie_timescale"]
    infos = []
    for pos, size in frag_pos:
        info = parse_moof(bytes(buf), pos, size)
        info["_pos"], info["_size"] = pos, size
        infos.append(info)
    for i, info in enumerate(infos):
        if info.get("duration_units"):
            info["duration_s"] = info["duration_units"] / ts
        elif i + 1 < len(infos):
            info["duration_s"] = (infos[i + 1]["tfdt"] - info["tfdt"]) / ts
        elif info.get("default_sample_duration"):
            info["duration_s"] = info["default_sample_duration"] * info["samples"] / ts
    # group: new segment at each sync-start fragment
    groups, cur = [], []
    for info in infos:
        if cur and not info.get("first_sample_non_sync", True):
            groups.append(cur)
            cur = []
        cur.append(info)
    if cur:
        groups.append(cur)
    patched = 0
    seg_infos = []
    for gi, group in enumerate(groups):
        name = f"seg_{gi+1:03d}.m4s"
        with open(os.path.join(outdir, name), "wb") as f:
            for info in group:
                chunk = bytearray(buf[info["_pos"]:info["_pos"] + info["_size"]])
                # patch tfhd inside this moof chunk (chunk starts at moof)
                moof_size = struct.unpack_from(">I", chunk, 0)[0]
                if patch_tfhd(chunk, 0, moof_size):
                    patched += 1
                f.write(bytes(chunk))
        seg_infos.append({
            "file": name,
            "fragments": [g["seq"] for g in group],
            "samples": sum(g["samples"] for g in group),
            "duration_s": round(sum(g["duration_s"] for g in group), 6),
            "starts_sync": not group[0].get("first_sample_non_sync", True),
        })
    target = max(-(-int(s["duration_s"]) // 1) for s in seg_infos)
    target = max(int(s["duration_s"] + 0.999999) for s in seg_infos)
    lines = ["#EXTM3U", "#EXT-X-VERSION:7", "#EXT-X-PLAYLIST-TYPE:VOD",
             f"#EXT-X-TARGETDURATION:{target}", "#EXT-X-MEDIA-SEQUENCE:0",
             "#EXT-X-INDEPENDENT-SEGMENTS", '#EXT-X-MAP:URI="init.mp4"']
    for s in seg_infos:
        lines.append(f"#EXTINF:{s['duration_s']:.6f},")
        lines.append(s["file"])
    lines.append("#EXT-X-ENDLIST")
    open(os.path.join(outdir, "playlist.m3u8"), "w").write("\n".join(lines) + "\n")
    json.dump({"moov": moov_info, "tfhd_patched": patched,
               "fragments_total": len(infos), "segments": seg_infos},
              open(os.path.join(outdir, "segments.json"), "w"), indent=1)
    print(f"segments={len(seg_infos)} samples={sum(s['samples'] for s in seg_infos)} "
          f"patched_tfhd={patched} all_sync={all(s['starts_sync'] for s in seg_infos)}")


if __name__ == "__main__":
    main()
