#!/usr/bin/env python3
"""Confluence Slice 1 ingest: frames -> tiles -> diff gate -> I-JEPA embeds.

Owns everything the Rust service should not: frame acquisition, image
decode, tiling, the cheap frame-diff gate, and the JEV rack embed
calls. Emits, on stdout, the wave-3 record schema (one JSON object
per embedded tile) plus a frame_end control line per frame:

  {"seq":0,"frame":F,"tile":T,"t_arrival_us":<capture epoch us>,
   "diff_score":D,"embed_ms":M,"embedding":[1280 floats]}
  {"control":"frame_end","frame":F,"t_capture_us":<capture epoch us>,
   "nominated":K,"gate_diff":G}

Sources (identical interface — the service cannot tell them apart):
  staged   synthetic staged-events sequence (cut / object / drift),
           ground truth written to --truth-out. The acceptance rig.
  wave3    the real wave-3 frame sequences from the Thor's own files
           (A burst, B turntable, C interleaved cuts).
  shot     IP Webcam style: poll GET <url> for one JPEG per frame.
  mjpeg    IP Webcam style: MJPEG stream at <url> (/video), frames
           taken at the lens cadence, drop-to-newest.

Gate: frame 0 embeds every tile (baseline). Later frames embed a
tile iff its mean-abs diff vs the previous frame exceeds --gate.
This is the wave-3 CHANGED strategy, live.
"""
import argparse, io, json, sys, time
import numpy as np
import requests
from PIL import Image, ImageDraw

TILES = 16


def now_us():
    return int(time.time() * 1_000_000)


def tiles_of(frame):
    h, w = frame.shape[:2]
    th, tw = h // 4, w // 4
    return [frame[r * th:(r + 1) * th, c * tw:(c + 1) * tw]
            for r in range(4) for c in range(4)]


class Emitter:
    def __init__(self, rack_url, gate):
        self.rack = rack_url.rstrip("/") + "/embed/image"
        self.gate = gate
        self.session = requests.Session()
        self.prev_tiles = None

    def embed(self, tile_img):
        buf = io.BytesIO()
        Image.fromarray(tile_img.astype(np.uint8)).save(buf, format="PNG")
        data = buf.getvalue()
        t0 = time.perf_counter()
        r = self.session.post(self.rack, files={"file": ("tile.png", data, "image/png")},
                              timeout=600)
        dt = (time.perf_counter() - t0) * 1000.0
        r.raise_for_status()
        emb = r.json()["embedding"]
        assert len(emb) == 1280, f"embedding dim {len(emb)}"
        return emb, dt

    def frame(self, img, frame_idx):
        """Tile, gate, embed nominated tiles, emit records + frame_end."""
        t_capture = now_us()
        tls = tiles_of(img)
        nominated = []
        diffs = []
        for ti, t in enumerate(tls):
            if self.prev_tiles is None:
                d = 255.0
            else:
                d = float(np.mean(np.abs(t - self.prev_tiles[ti])))
            diffs.append(d)
            if self.prev_tiles is None or d > self.gate:
                nominated.append(ti)
        for ti in nominated:
            emb, ms = self.embed(tls[ti])
            rec = {"seq": 0, "frame": frame_idx, "tile": ti,
                   "t_arrival_us": t_capture,
                   "diff_score": round(diffs[ti], 4),
                   "embed_ms": round(ms, 2),
                   "embedding": [round(float(x), 6) for x in emb]}
            print(json.dumps(rec), flush=True)
        print(json.dumps({"control": "frame_end", "frame": frame_idx,
                          "t_capture_us": t_capture,
                          "nominated": len(nominated),
                          "gate_diff": self.gate}), flush=True)
        self.prev_tiles = tls
        return len(nominated)


# ---------------- staged synthetic sequence ----------------

def scene1(rng):
    img = np.zeros((512, 512, 3), dtype=np.float32)
    for y in range(512):
        img[y, :, 0] = 30 + 60 * y / 512      # red gradient
        img[y, :, 1] = 40 + 30 * y / 512
        img[y, :, 2] = 90
    pil = Image.fromarray(img.astype(np.uint8))
    d = ImageDraw.Draw(pil)
    d.rectangle([40, 300, 220, 470], fill=(25, 35, 70))       # dark block
    d.ellipse([320, 60, 470, 210], fill=(120, 120, 110))      # grey disc
    return np.asarray(pil, dtype=np.float32)


def scene2(rng):
    img = np.zeros((512, 512, 3), dtype=np.float32)
    for x in range(512):
        img[:, x, 0] = 150
        img[:, x, 1] = 120 + 80 * x / 512     # green gradient
        img[:, x, 2] = 40 + 40 * x / 512
    pil = Image.fromarray(img.astype(np.uint8))
    d = ImageDraw.Draw(pil)
    for i in range(4):
        d.rectangle([30 + i * 120, 330, 110 + i * 120, 440], fill=(200, 140, 40))
    d.ellipse([60, 40, 190, 170], fill=(60, 60, 160))         # blue disc
    return np.asarray(pil, dtype=np.float32)


def staged_frames():
    """(frames, truth). 18 frames: 0-3 scene A, 4 CUT to scene B,
    7 object added (a real-photo patch over tiles 5,6), 10-17 gradual
    drift (slow brightening: per-frame diff must stay under the gate).

    The scenes are composited from REAL photos (the wave-3 burst and
    turntable frames), not synthetic colour fields: the first version
    of this rig used flat gradient scenes and I-JEPA embedded the two
    "different" scenes nearly identically (both are flat fields with
    simple shapes to a model trained on natural images) — the cut
    scored under threshold and published nothing. A rig whose scenes
    the perception model cannot tell apart tests nothing. Falls back
    to the synthetic scenes if the photo files are absent."""
    rng = np.random.default_rng(7)
    try:
        A = wave3_frames("A")
        B = wave3_frames("B")
        s1, s2 = A[0], B[0]
        patch = A[3][128:256, 128:384].copy()  # real photo content
    except Exception:
        s1, s2 = scene1(rng), scene2(rng)
        patch = np.zeros((128, 256, 3), dtype=np.float32)
        patch[:] = (232.0, 42.0, 30.0)

    def noisy(base):
        return np.clip(base + rng.normal(0, 1.0, base.shape), 0, 255)

    def with_object(base):
        out = base.copy()
        out[128:256, 128:384] = patch                          # tiles 5,6
        return out

    frames = []
    for _ in range(4):
        frames.append(noisy(s1))
    for _ in range(3):
        frames.append(noisy(s2))
    for _ in range(3):
        frames.append(noisy(with_object(s2)))
    for k in range(8):  # drift: +1.2 brightness/frame
        frames.append(noisy(with_object(s2) + 1.2 * (k + 1)))
    truth = {"cut_frame": 4, "object_frame": 7, "object_tiles": [5, 6],
             "drift_frames": list(range(10, 18)), "frames": len(frames)}
    return frames, truth


# ---------------- wave-3 real sequences ----------------

def wave3_frames(seq):
    import glob, os
    a_paths = sorted(glob.glob(os.path.expanduser(
        "~/image-studio/outputs/burst_1792818193_b512cd_f*.png")))
    A = [np.asarray(Image.open(p).convert("RGB"), dtype=np.float32) for p in a_paths]
    webp = Image.open(os.path.expanduser("~/sitka-distill/showcase/dock-turntable.webp"))
    B = []
    for i in range(12):
        webp.seek(i)
        fr = webp.convert("RGB")
        w, h = fr.size
        fr = fr.crop((0, (h - w) // 2, w, (h - w) // 2 + w)).resize((512, 512))
        B.append(np.asarray(fr, dtype=np.float32))
    if seq == "A":
        return A
    if seq == "B":
        return B
    C = []
    for i in range(6):
        C.append(A[i]); C.append(B[i])
    return C


# ---------------- live HTTP sources ----------------

def shot_frames(url):
    s = requests.Session()
    while True:
        r = s.get(url, timeout=30)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        yield np.asarray(img, dtype=np.float32)


def mjpeg_frames(url, cadence_ms):
    s = requests.Session()
    resp = s.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    buf = bytearray()
    last = 0.0
    for chunk in resp.iter_content(chunk_size=65536):
        buf.extend(chunk)
        while True:
            soi = buf.find(b"\xff\xd8")
            if soi < 0:
                break
            eoi = buf.find(b"\xff\xd9", soi + 2)
            if eoi < 0:
                break
            jpg = bytes(buf[soi:eoi + 2])
            del buf[:eoi + 2]
            now = time.time()
            if (now - last) * 1000.0 >= cadence_ms:
                last = now
                try:
                    img = Image.open(io.BytesIO(jpg)).convert("RGB")
                except Exception:
                    continue
                yield np.asarray(img, dtype=np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True,
                    choices=["staged", "wave3", "shot", "mjpeg"])
    ap.add_argument("--url", default="")
    ap.add_argument("--seq", default="C", choices=["A", "B", "C"])
    ap.add_argument("--gate", type=float, default=3.0)
    ap.add_argument("--cadence-ms", type=float, default=100.0)
    ap.add_argument("--rack", default="http://127.0.0.1:8077")
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--truth-out", default="")
    args = ap.parse_args()

    em = Emitter(args.rack, args.gate)
    if args.source == "staged":
        frames, truth = staged_frames()
        if args.truth_out:
            with open(args.truth_out, "w") as fh:
                json.dump(truth, fh)
        gen = iter(frames)
    elif args.source == "wave3":
        gen = iter(wave3_frames(args.seq))
    elif args.source == "shot":
        gen = shot_frames(args.url)
    else:
        gen = mjpeg_frames(args.url, args.cadence_ms)

    idx = 0
    for img in gen:
        t0 = time.time()
        if img.shape[0] != 512 or img.shape[1] != 512:
            img = np.asarray(Image.fromarray(img.astype(np.uint8)).resize((512, 512)),
                             dtype=np.float32)
        em.frame(img, idx)
        idx += 1
        if args.max_frames and idx >= args.max_frames:
            break
        wait = args.cadence_ms / 1000.0 - (time.time() - t0)
        if wait > 0:
            time.sleep(wait)
    return 0


if __name__ == "__main__":
    sys.exit(main())
