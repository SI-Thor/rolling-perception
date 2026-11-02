#!/usr/bin/env python3
"""Split a fragmented MP4 stream (ftyp moov [moof mdat]...) into an HLS-fMP4
init segment + media segments, emit a VOD playlist, and report per-fragment
structure facts (mfhd sequence, tfdt, tfhd flags, sample counts, first-sample
sync) as JSON. Stdlib only.

Usage: fmp4_split.py input.fmp4 outdir
Writes: outdir/init.mp4, outdir/seg_001.m4s..., outdir/playlist.m3u8,
        outdir/fragments.json
"""
import json
import struct
import sys
import os


def read_boxes(buf, start=0, end=None):
    end = len(buf) if end is None else end
    pos = start
    while pos + 8 <= end:
        size, typ = struct.unpack_from(">I4s", buf, pos)
        typ = typ.decode("latin1")
        hdr = 8
        if size == 1:
            size = struct.unpack_from(">Q", buf, pos + 8)[0]
            hdr = 16
        elif size == 0:
            size = end - pos
        yield pos, size, hdr, typ
        pos += size


def find_child(buf, start, size, wanted):
    for pos, sz, hdr, typ in read_boxes(buf, start, start + size):
        if typ == wanted:
            return pos, sz, hdr
    return None


def parse_moov(buf, pos, size):
    mv = find_child(buf, pos + 8, size - 8, "mvhd")
    timescale = None
    if mv:
        p, _, h = mv
        ver = buf[p + h]
        if ver == 1:
            timescale = struct.unpack_from(">I", buf, p + h + 20)[0]
        else:
            timescale = struct.unpack_from(">I", buf, p + h + 12)[0]
    # track timescale (mdhd inside trak/mdia)
    track_ts = None
    trak = find_child(buf, pos + 8, size - 8, "trak")
    if trak:
        mdia = find_child(buf, trak[0] + 8, trak[1] - 8, "mdia")
        if mdia:
            mdhd = find_child(buf, mdia[0] + 8, mdia[1] - 8, "mdhd")
            if mdhd:
                p, _, h = mdhd
                ver = buf[p + h]
                if ver == 1:
                    track_ts = struct.unpack_from(">I", buf, p + h + 20)[0]
                else:
                    track_ts = struct.unpack_from(">I", buf, p + h + 12)[0]
    entry = None
    for tag in (b"hvc1", b"hev1", b"avc1"):
        if tag in buf[pos:pos + size]:
            entry = tag.decode()
            break
    return {"movie_timescale": timescale, "track_timescale": track_ts,
            "sample_entry": entry, "has_mvex": b"mvex" in buf[pos:pos + size],
            "has_hvcC": b"hvcC" in buf[pos:pos + size]}


def parse_moof(buf, pos, size):
    out = {}
    mfhd = find_child(buf, pos + 8, size - 8, "mfhd")
    if mfhd:
        p, _, h = mfhd
        out["seq"] = struct.unpack_from(">I", buf, p + h + 4)[0]
    traf = find_child(buf, pos + 8, size - 8, "traf")
    if traf:
        tp, tsz, _ = traf
        tfhd = find_child(buf, tp + 8, tsz - 8, "tfhd")
        if tfhd:
            p, _, h = tfhd
            flags = struct.unpack_from(">I", buf, p + h)[0] & 0xFFFFFF
            out["tfhd_flags"] = flags
            out["default_base_is_moof"] = bool(flags & 0x020000)
            out["base_data_offset_present"] = bool(flags & 0x000001)
            q = p + h + 4  # track id
            if flags & 0x000001: q += 8
            if flags & 0x000002: q += 4
            if flags & 0x000008: q += 4
            out["default_sample_duration"] = None
            if flags & 0x000010:
                out["default_sample_duration"] = struct.unpack_from(">I", buf, q)[0]
        tfdt = find_child(buf, tp + 8, tsz - 8, "tfdt")
        if tfdt:
            p, _, h = tfdt
            ver = buf[p + h]
            if ver == 1:
                out["tfdt"] = struct.unpack_from(">Q", buf, p + h + 4)[0]
            else:
                out["tfdt"] = struct.unpack_from(">I", buf, p + h + 4)[0]
        trun = find_child(buf, tp + 8, tsz - 8, "trun")
        if trun:
            p, _, h = trun
            flags = struct.unpack_from(">I", buf, p + h)[0] & 0xFFFFFF
            count = struct.unpack_from(">I", buf, p + h + 4)[0]
            out["samples"] = count
            q = p + h + 8
            if flags & 0x000001: q += 4
            first_flags = None
            if flags & 0x000004:
                first_flags = struct.unpack_from(">I", buf, q)[0]
                q += 4
            dur_sum, recs = 0, []
            for i in range(count):
                dur = size_ = sflags = None
                if flags & 0x000100:
                    dur = struct.unpack_from(">I", buf, q)[0]; q += 4
                if flags & 0x000200:
                    size_ = struct.unpack_from(">I", buf, q)[0]; q += 4
                if flags & 0x000400:
                    sflags = struct.unpack_from(">I", buf, q)[0]; q += 4
                if flags & 0x000800: q += 4
                if dur: dur_sum += dur
                if i == 0: recs.append(sflags)
            out["duration_units"] = dur_sum or None
            sf = first_flags if first_flags is not None else (recs[0] if recs else None)
            if sf is not None:
                out["first_sample_non_sync"] = bool(sf & 0x00010000)
                out["first_sample_depends_on"] = (sf >> 24) & 0x3
    return out


def main():
    src, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    buf = open(src, "rb").read()
    top = list(read_boxes(buf))
    moov_info, init_end, frags = None, None, []
    pending = None
    for pos, size, hdr, typ in top:
        if typ == "moov":
            moov_info = parse_moov(buf, pos, size)
            init_end = pos + size
        elif typ == "moof":
            pending = (pos, size)
        elif typ == "mdat" and pending:
            frags.append((pending[0], pos + size - pending[0]))
            pending = None
    # init = ftyp + moov only (drop any metadata boxes in between, e.g. XMP uuid)
    init = b""
    for pos, size, hdr, typ in top:
        if pos >= init_end: break
        if typ in ("ftyp", "moov"):
            init += buf[pos:pos + size]
    open(os.path.join(outdir, "init.mp4"), "wb").write(init)
    ts = moov_info["track_timescale"] or moov_info["movie_timescale"]
    infos = []
    for i, (pos, size) in enumerate(frags):
        name = f"seg_{i+1:03d}.m4s"
        open(os.path.join(outdir, name), "wb").write(buf[pos:pos + size])
        info = parse_moof(buf, pos, size)
        info["file"] = name
        infos.append(info)
    for i, info in enumerate(infos):
        if info.get("duration_units"):
            info["duration_s"] = info["duration_units"] / ts
        elif i + 1 < len(infos) and "tfdt" in info and "tfdt" in infos[i + 1]:
            info["duration_s"] = (infos[i + 1]["tfdt"] - info["tfdt"]) / ts
        elif info.get("default_sample_duration"):
            info["duration_s"] = info["default_sample_duration"] * info["samples"] / ts
    target = max(round(i["duration_s"]) for i in infos if "duration_s" in i)
    lines = ["#EXTM3U", "#EXT-X-VERSION:7", "#EXT-X-PLAYLIST-TYPE:VOD",
             f"#EXT-X-TARGETDURATION:{target}", "#EXT-X-MEDIA-SEQUENCE:0",
             '#EXT-X-MAP:URI="init.mp4"']
    for info in infos:
        lines.append(f"#EXTINF:{info['duration_s']:.6f},")
        lines.append(info["file"])
    lines.append("#EXT-X-ENDLIST")
    open(os.path.join(outdir, "playlist.m3u8"), "w").write("\n".join(lines) + "\n")
    json.dump({"moov": moov_info, "fragments": infos}, open(os.path.join(outdir, "fragments.json"), "w"), indent=1)
    print(f"init={len(init)}B fragments={len(infos)} timescale={ts} entry={moov_info['sample_entry']}")


if __name__ == "__main__":
    main()
