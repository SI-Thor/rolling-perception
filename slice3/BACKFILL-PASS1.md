# Slice 3 — Backfill Pass 1 (inventory) + Pass 2 (posters/thumbnails)

Run on the Thor 2026-11-01. Script: `slice3/backfill_pass1.py`.
Play area: `~/confluence-play/slice3/library/` (ledger, media index,
hardlink shelf, posters, thumbs). Nothing left resident; the running
Slice-1 soak was excluded from the walk and verified untouched after.

**Numbering map (honesty first):** the spec (§4.1) calls inventory +
poster frames *Pass 0* and reserves Pass 1 for structure (scene cuts +
per-scene embeds), Pass 2 for speech. This lane executed the brief's
numbering — inventory + thumbnails/posters — which is spec Pass 0.
The remaining debt below uses spec numbering.

## What the house actually holds

Found (media extensions the console can shelve, stat-level, excluding
this pass's own output dir): **13,466 files, 739.5 MB** — 13,464
images + **2 videos**, spanning 2026-10-23 → 2026-11-01.

| Tree | Files | Size | Notes |
|---|---|---|---|
| ~/image-studio/outputs | 127 | 145.6 MB | all images (115 png, 12 webp) — the real generated art |
| ~/foundry | 13,309 | 577.5 MB | images only; see junk note |
| ~/confluence-play | 30 | 16.4 MB | incl. the only 2 videos + 28 soak files (excluded, untouched) |
| ~/Videos, ~/Pictures | 0 | — | empty |
| ~/Downloads | 0 shelf media | (898 MB) | .riva TTS model files, not media |

Excluded from the shelf: **12,580 files** in `~/foundry/portal/cache/`
(generated fishing-boat preview/turntable frames — a render cache,
93% of all "media" found), 28 live-soak files, venv/site-packages
internals (incl. sklearn's sample images inside `foundry/cad-venv`).

**Shelf-eligible: 858 files (856 images + 2 videos, 634.9 MB).**

## The capped run

Cap 300, taken as 150 most-recent + 150 largest (dedup → **234
selected**; both videos force-included): foundry non-cache 166,
image-studio outputs 66, confluence-play 2. All 234 ffprobe-probed
with **0 errors**; facts (codec, dimensions, duration, size, mtime)
written to `ledger/items/<id>.txt` in the slice-1 format plus
`media-index.jsonl`; originals referenced by path (symlink shelf),
never copied.

- **Thumbnails: 232/232 images OK** (≤480 px JPEG, each verified
  decodable by ffprobe — count what decodes, not what ffmpeg claims).
- **Posters: 2/2 videos OK** (mid-duration frame, ≤640 px, verified).
- **NVENC budget drawn: zero.** Single frames are CPU decode + PIL;
  nothing touched the encode-fps budget or the JEV rack.

## Two rig findings (this ffmpeg build is crippled)

The Thor's ffmpeg 8.0.1 has **no `scale` filter** and **cannot convert
pixel formats at all** — the auto-conversion inserts the missing
scale filter, so even a plain frame→JPEG extraction fails
(`'scale' filter not present, cannot convert formats`). Workarounds
that work, now in the script: thumbnails are pure PIL; posters are
decoded to **raw NV12** (the decoder's native format — no conversion),
converted NV12→RGB in numpy (BT.601), saved via PIL. Any future
ffmpeg-based pass (scene-cut detection, transcoding) must route
around this build — GStreamer/nvvidconv or PIL — or use a different
ffmpeg. (First poster attempt also died on my own UV-plane slice bug;
the error was in my arithmetic, not the rig, and is fixed in the
script.)

## Verified through the actual surface

Slice-1 console served against this ledger + shelf (port 8321,
stopped after): page **200**; `/api/state` returned **234 shelf
items — exactly the inventory selection count** — 232 image / 2
video, perception strings populated ("inventoried; poster ready" /
"inventoried; thumbnail ready").

The byte path failed first, and the failure is the finding: with the
shelf built as **symlinks**, `/files/` returned **404 for every
item** — the console's traversal guard `resolve()`s the request
path, a symlink resolves to its target *outside* the media root, and
the guard refuses it. The API looked perfect while nothing could
actually be served. Fix: shelf entries are **hardlinks** (same
inode — referenced, not copied; they resolve inside the root).
Re-verified after the fix: `/files/` image **200 (611,798 B)**,
video **206** on a 64 KB range request. Server killed, port
verified free, soak processes verified still running. (The script
now creates hardlinks, so a re-run reproduces the working shelf.)

One console quirk recorded, not hidden: posters live in
`library/posters/` (path recorded in each item record), **not** as
siblings in the media dir — the console enumerates *any* `.jpg` in
the media tree as a shelf item, so sibling posters would double-count
and break the shelf's count integrity. That's a console fix (exclude
`*.poster.jpg` in `shelf_items`), owed by whoever touches the console
next. Item stems were pre-made unique (`s3-NNNN--<stem>`) because the
console keys metadata by stem and the trees are full of collisions.

## What the later passes owe (with the arithmetic)

The entire eligible video holding is **0.0183 h (65.9 s)**: a 60.0 s
HEVC 1920×1080 test clip and a 5.9 s H.264 1366×768 clip — **both are
the S2 player lane's own test files. The house has zero real video
titles today**, so the spec's 500-title GPU-nights math is moot
until real video lands.

- **Structure (spec Pass 1)** — at the spec's derived rate (~400
  scenes / 2 h title = 200 scenes/h) × 0.173 s per tile-embed:
  34.6 embed-seconds per video-hour → **≈0.63 embed-seconds total**
  for everything the house owns. Paranoid bound (1 scene/second):
  65.9 × 0.173 ≈ 11.4 embed-seconds.
- **Deepening (spec Pass 4)** — 16 tiles/scene: ×16 → **≈10.1
  embed-seconds total**.
- **Speech (spec Pass 2)** — 65.9 s of audio; Whisper RTF on the Thor
  is still TO-MEASURE, but at any plausible RTF this is seconds.
- **Images, if a future pass embeds them 1:1**: 856 eligible ×
  0.173 s ≈ **148 embed-seconds** — the largest single future bill,
  and it belongs to images, not video.
- **Meaning (spec Pass 3)** — text-only over transcripts that don't
  exist yet; cost lands after Pass 2 and is bounded by 66 s of
  speech. Effectively zero today.

## Junk & surprises

- 93% of the house's "media" by count is one render cache of boat
  previews. The real library is 127 studio images + ~730 foundry
  asset renders.
- Downloads is a model shelf wearing a media folder's name
  (four ~225 MB .riva files).
- The only videos on the box are two test clips the platform itself
  made yesterday. Slice 3's real work is images until Casey points
  the library at actual video.
