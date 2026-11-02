# fMP4 spike — can this Thor produce spec-valid HLS with H.265 today?

Ran on the Thor 2026-11-01 ~23:26–23:40 AKST, in a scratch dir
(removed after), while the Slice-1 soak was running (confluence-watch
PID 1049389, verified alive before and after; no spike process left
running). Test item: the player lane's `ball-1080-h265.mp4` — HEVC
1920×1080, 30 fps, 1800 frames, 60.0 s, IDR every 256 frames.

**Verdict: YES — by remux, with two small post-processing steps, and
no new software.** A GStreamer fragmented-MP4 remux of the existing
HEVC encode splits cleanly into an init segment + GOP-aligned media
segments that pass every structural check we can run without an
Apple client (box structure, per-segment independent decode,
strict playlist parse). This is **"spec-conformant by checklist +
probe"** — it is not a claim that any particular iPhone plays it;
no Apple client was available to this lane. The player's H.264-out
decision can be revisited on this evidence; nothing here integrates
into the player (spike only).

## 1. Inventory (what the box has)

| tool | version | relevant surface |
|---|---|---|
| GStreamer | 1.24.2 (Ubuntu) | `mp4mux`/`qtmux` PRESENT with `fragment-duration`, `fragment-mode` (dash-or-mss), `streamable`; `h265parse` PRESENT; `hlssink`/`hlssink2` PRESENT (TS only) |
| — | — | `cmafmux` **absent**, `hlscmafsink` **absent**, `hlssink3` **absent** (these live in gst-plugins-rs; `apt-cache search` finds no rs-plugins package in Ubuntu 24.04's gstreamer1.0 set). `libgstisomp4.so` on disk is plugins-good's qtmux/mp4mux plugin, not the rs one |
| ffmpeg | n8.0.1-17 (Ubuntu) | 26 muxers total; **no** `hls`, no `dash`, no `segment`/`stream_segment` (confirms the player lane). The `mp4`/`mov` muxer *does* carry `-movflags cmaf` ("Write CMAF compatible fragmented MP4"), `empty_moov`, `-frag_duration`, `-fragment_index` |

## 2. The two candidate paths, measured

### Path A — GStreamer mp4mux (the one that works)

```
filesrc ! qtdemux ! h265parse ! mp4mux fragment-duration=3000 streamable=true ! filesink
```
Output structure: `ftyp, moov` (903 B; sample entry **hvc1** + hvcC,
mvex/trex present), one XMP `uuid` box, then 22 `moof`/`mdat`
fragment pairs covering exactly 1800 samples. Fragment durations
tile the GOP grid — 90/90/76 samples repeating (3.0/3.0/2.53 s):
mp4mux cuts at the duration target *or* at a keyframe, whichever
comes first, so every 3rd fragment starts exactly on an IDR.

Two defects, both repairable in post (see §3):
- `tfhd` flags = 0: **no `default-base-is-moof`** (a CMAF shall).
- Fragment starts are not all sync samples — true of any
  duration-cut grid; the fix is grouping, not re-cutting.

### Path B — ffmpeg mov muxer, `-movflags cmaf+empty_moov -frag_duration 3000000`

Structurally the most "correct" header on the box: ftyp major brand
`iso6`, compatible `iso6 cmfc mp41`; tfhd flags `0x2003A` include
`default-base-is-moof` on all 20 fragments. **But its fragment grid
is pure duration** — 20 × exactly 90 samples, boundaries never
coinciding with an IDR after the first (fragments 3, 6, 9, …
provably start on non-sync samples, `depends_on=1`). Unlike Path A,
the fragments cannot be regrouped onto the GOP grid, and ffmpeg has
no segment muxer to cut per-GOP files itself. Rejected for remux;
it would only work on an encode whose GOP already equals the
segment length.

## 3. The build (spike scripts in this dir)

`fmp4_split.py` — box/fragment parser used for all evidence below.
`build_hls.py` — produces the deliverable set from Path A's stream:

1. **Init segment** = `ftyp` + `moov` as written (the XMP `uuid` box
   is dropped — metadata, not structure).
2. **Grouping**: a new media segment starts at every fragment whose
   own trun flags mark its first sample sync; other fragments join
   the open segment (multiple moof/mdat pairs per media segment is
   valid CMAF). Result: **8 segments** — 7 × 256 samples
   (8.533 s) + a tail of 8 samples (0.267 s), 1800 total.
3. **tfhd patch**: set the `default-base-is-moof` bit in place
   (byte `p+h+1 |= 0x02` inside each moof's tfhd). With no
   base-data-offset field present, ISO 14496-12's implicit default
   already anchors sample data at the enclosing moof, so the patch
   changes no offsets, sizes, or semantics — it makes the existing
   anchoring explicit, as CMAF requires. 22/22 moofs patched;
   re-parse confirms `tfhd_flags = 0x20000`.

   *Process note:* the first build patched the wrong flag byte
   (0x000002, "sample-description-index present") and produced
   segments ffprobe decoded as 0 frames. The probe method was
   calibrated against the source file (1800 frames) before the
   artifacts were distrusted, the byte was fixed, and the whole
   validation below was re-run on the rebuilt set.

## 4. Validation evidence

- **ffprobe, init segment**: `codec_name=hevc`,
  `codec_tag_string=hvc1`, 1920×1080. hvcC fields: profile_idc 1
  (Main), tier 0, level_idc 120 → a master playlist would carry
  `CODECS="hvc1.1.6.L120.9"` (constructed per RFC 6381 from hvcC;
  this spike validates a media playlist, no master was served).
- **Per-segment independent decode** (init + segment concatenated,
  ffprobe full frame decode): seg_001 = 256 frames, first frame
  key; seg_002 = 256, first key; seg_008 = 8, first key. Full set
  concatenated decodes **1800/1800 frames, no errors** (this ffmpeg
  build has no `wrapped_avframe` encoder, so the decode check is
  ffprobe frame extraction, not `-f null`).
- **Strict playlist parse** (python `m3u8`, installed into the
  scratch dir for the spike): media playlist, version 7, VOD,
  8 segments, **EXTINF sum = 60.000 s**, `EXT-X-MAP` → `init.mp4`
  shared by all segments, max EXTINF ≤ TARGETDURATION (9).
- **HLS/CMAF checklist** (RFC 8216 + ISO 23000-19 + Apple's
  HEVC-in-fMP4 authoring requirements):
  - init segment with ftyp+moov, empty sample tables, mvex/trex ✔
  - sample entry `hvc1` (not `hev1`), hvcC present ✔
  - media segments are moof+mdat sequences, tfdt continuous from 0,
    mfhd sequence continuous ✔
  - every media segment starts with a sync sample (IDR) and is
    independently decodable — probed, not assumed ✔
  - tfhd `default-base-is-moof` set (after patch) ✔
  - `EXT-X-MAP`, `EXT-X-VERSION` ≥ 6 (7 used),
    `EXT-X-INDEPENDENT-SEGMENTS` — claim backed by the decode
    probes above ✔
  - deviations, recorded not hidden: **no `styp` box** at segment
    starts (CMAF-recommended, not required by RFC 8216/Apple);
    **ftyp brands** are `mp42 / mp42 mp41 isom iso2` — no
    `iso6`/`cmfc` brand (Path B's header shows what ideal looks
    like; players key off the `hvc1` sample entry, but a strict
    CMAF-brand checker would flag this); segment lengths follow
    the source GOP (8.53 s, plus a 0.27 s tail) — future encodes
    for HLS should use a ~3 s GOP so segments land near target.

## 5. Cost

Remux + packaging only — **no encode is performed on this path**;
the H.265 encode cost was already paid when the item was made (by
whatever produced it — for a live transcode pipeline, the V4L2
H.265 numbers from the NVENC bench, 530–740 fps, are the encode
side of the ledger).

| step | wall (median of 3) | for the 60 s item |
|---|---|---|
| gst remux to fragmented MP4 | 0.05 s | ≈36,000 fps equivalent |
| ffmpeg `-movflags cmaf` remux (Path B, for scale) | 0.27 s | ≈6,700 fps |
| `build_hls.py` (split + patch + playlist) | 0.04 s | — |

Reference encode costs on this box: player H.264 transcode
138 fps under soak (solo V4L2 H.264 ~176–240 fps); V4L2 H.265
transcode 530–740 fps. Packaging an existing HEVC encode into
HLS-fMP4 is therefore ~50–250× cheaper than the cheapest encode
path — for library/serve purposes it is effectively free, and the
serve plane's encode-fps budget should charge it ~0, like the
player already charges TS remux.

Caveat on the gst figure: the item is 5.7 MB and page-cached; the
honest claim is "IO-bound and negligible at library scale", not
the headline fps.

## 6. If a native sink is ever wanted (gap, for the record)

Not needed for the verdict above. A zero-post-processing pipeline
would want `cmafmux` or `hlscmafsink` from **gst-plugins-rs**,
which Ubuntu 24.04 does not package for gstreamer1.0 (checked
`apt-cache`); closing that gap means building gst-plugins-rs from
source (cargo-c) against the system 1.24.2, or moving to a distro
GStreamer that ships it. Neither is justified while the
remux+group+patch path above validates.
