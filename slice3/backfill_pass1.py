#!/usr/bin/env python3
"""Confluence Slice 3 — backfill Pass 1 (inventory) + Pass 2 (posters/thumbs).

Runs ON the Thor. Inventories user media in the obvious trees (stat-level
for everything found), deep-probes a capped selection with ffprobe,
generates a poster frame per video and a small thumb per image, and
writes the slice-1 ledger item format + a shelf media dir of symlinks
(originals are referenced by path, never copied).

Outputs under ~/confluence-play/slice3/library/:
  inventory-all.jsonl   every media-ext file found (stat facts + flags)
  media-index.jsonl     the capped selection, fully probed
  summary.json          totals
  ledger/items/*.txt    slice-1 console item records
  media/                symlinks to originals (console MEDIA dir)
  posters/  thumbs/     generated images (verified decodable)
"""
import hashlib, json, os, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HOME = Path.home()
ROOTS = [HOME/"image-studio/outputs", HOME/"foundry", HOME/"confluence-play",
         HOME/"Videos", HOME/"Pictures", HOME/"Downloads"]
OUT = HOME/"confluence-play/slice3/library"
IMG = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
VID = {".mp4", ".webm", ".mkv", ".mov", ".m4v"}
EXC_DIRS = {".git", ".cache", "__pycache__", "node_modules", ".mypy_cache",
            ".pytest_cache", "site-packages"}
SOAK = str(HOME/"confluence-play/slice1")
SELF = str(OUT)
CAP = 300

def excluded(p: Path):
    """Return a reason string if this file is out of shelf scope, else None."""
    s = str(p)
    if s.startswith(SOAK):
        return "live-soak-tree (not touched)"
    if s.startswith(SELF):
        return "self (slice3 library output)"
    parts = set(p.parts)
    if parts & EXC_DIRS or any(part.endswith("venv") or part == ".venv" for part in parts):
        return "venv/cache internals"
    if "portal/cache" in s:
        return "foundry portal render cache (generated preview frames)"
    if p.suffix.lower() in (IMG | VID) and p.stat().st_size == 0:
        return "zero-byte"
    if p.stat().st_size > 16 * (1 << 30):
        return "suspicious size >16GiB (model-weight sanity)"
    return None

def scan():
    rows = []
    for root in ROOTS:
        if not root.exists():
            continue
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in EXC_DIRS and not d.endswith("venv")]
            for f in fns:
                p = Path(dp) / f
                if p.suffix.lower() not in (IMG | VID):
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                rows.append({
                    "path": str(p), "tree": str(root),
                    "rel": str(p.relative_to(root)),
                    "ext": p.suffix.lower(),
                    "kind": "video" if p.suffix.lower() in VID else "image",
                    "bytes": st.st_size, "mtime": st.st_mtime,
                    "excluded": excluded(p),
                })
    return rows

def probe(path):
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type,codec_name,width,height,avg_frame_rate,duration",
             "-show_entries", "format=duration,format_name",
             "-show_entries", "format_tags=creation_time",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=20)
        d = json.loads(r.stdout or "{}")
    except Exception as e:
        return {"probe_error": str(e)}
    streams = d.get("streams", [])
    vs = next((s for s in streams if s.get("codec_type") == "video"), streams[0] if streams else {})
    fmt = d.get("format", {})
    dur = fmt.get("duration") or vs.get("duration")
    return {
        "codec": vs.get("codec_name"), "width": vs.get("width"),
        "height": vs.get("height"),
        "duration_s": round(float(dur), 3) if dur else None,
        "format": fmt.get("format_name"),
        "creation_time": (fmt.get("tags") or {}).get("creation_time"),
    }

def verify_image(path):
    """A generated file counts only if it decodes as a real image."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height,codec_name",
                            "-of", "json", str(path)],
                           capture_output=True, text=True, timeout=10)
        s = json.loads(r.stdout or "{}").get("streams", [])
        return bool(s and s[0].get("width") and path.stat().st_size > 512)
    except Exception:
        return False

def pil_shrink(path, max_dim):
    """Downscale a JPEG in place with PIL. The Thor's ffmpeg 8.0.1 build
    has NO scale filter (measured: `ffmpeg -filters` shows fps only) —
    all resizing in this pass is PIL work."""
    from PIL import Image
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((max_dim, max_dim))
        im.save(path, "JPEG", quality=82)
    return verify_image(path)

def make_poster(src, dur, dest, width, height):
    # This ffmpeg build cannot convert pixel formats at all (the auto
    # conversion inserts the missing scale filter), so: decode one
    # frame to RAW nv12 (the decoder's native format, no conversion),
    # convert NV12->RGB in numpy (BT.601), save + shrink via PIL.
    if not width or not height:
        return False
    import numpy as np
    from PIL import Image
    raw = dest.with_suffix(".nv12")
    seek = (dur / 2.0) if dur else 0.5
    for ss in (seek, 0.5, 0.0):
        subprocess.run(["ffmpeg", "-v", "error", "-ss", str(ss), "-i", str(src),
                        "-frames:v", "1", "-pix_fmt", "nv12",
                        "-f", "rawvideo", "-y", str(raw)],
                       capture_output=True, timeout=60)
        try:
            if not raw.exists() or raw.stat().st_size < width * height * 3 // 2:
                continue
            buf = np.fromfile(raw, dtype=np.uint8)
            y = buf[:width * height].reshape(height, width).astype(np.float32)
            uv = buf[width * height:width * height * 5 // 4].reshape(height // 2, width)
            u = uv[:, 0::2].repeat(2, axis=0).repeat(2, axis=1).astype(np.float32) - 128
            v = uv[:, 1::2].repeat(2, axis=0).repeat(2, axis=1).astype(np.float32) - 128
            yy = (y - 16) * 1.164
            rgb = np.stack([yy + 1.596 * v, yy - 0.813 * v - 0.391 * u,
                            yy + 2.018 * u], axis=-1)
            Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).save(
                dest, "JPEG", quality=85)
            return pil_shrink(dest, 640)
        except Exception:
            continue
        finally:
            raw.unlink(missing_ok=True)
    return False

def make_thumb(src, dest):
    try:
        from PIL import Image
        with Image.open(src) as im:
            im.seek(0)
            im = im.convert("RGB")
            im.thumbnail((480, 480))
            im.save(dest, "JPEG", quality=80)
        return verify_image(dest)
    except Exception:
        return False

def human(stem):
    s = re.sub(r"[_\-]+", " ", stem).strip()
    return s[:120] if s else stem

def main():
    for d in (OUT/"ledger/items", OUT/"media", OUT/"posters", OUT/"thumbs"):
        d.mkdir(parents=True, exist_ok=True)
    rows = scan()
    with open(OUT/"inventory-all.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    eligible = [r for r in rows if not r["excluded"]]
    recent = sorted(eligible, key=lambda r: (-r["mtime"], -r["bytes"]))[:CAP // 2]
    largest = sorted(eligible, key=lambda r: (-r["bytes"], -r["mtime"]))[:CAP // 2]
    sel, seen = [], set()
    for r in recent + largest + [r for r in eligible if r["kind"] == "video"]:
        if r["path"] not in seen:
            seen.add(r["path"]); sel.append(r)
    sel = sel[:CAP]
    sel.sort(key=lambda r: -r["mtime"])

    with ThreadPoolExecutor(max_workers=8) as ex:
        facts = list(ex.map(lambda r: probe(r["path"]), sel))

    index, posters_ok, posters_fail, thumbs_ok, thumbs_fail = [], 0, 0, 0, 0
    for i, (r, fact) in enumerate(zip(sel, facts), 1):
        iid = f"s3-{i:04d}"
        src = Path(r["path"])
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", src.stem)[:60]
        shelf_name = f"{iid}--{stem}{src.suffix.lower()}"
        link = OUT/"media"/shelf_name
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(src)
        poster_rel = thumb_rel = None
        if r["kind"] == "video":
            dest = OUT/"posters"/f"{iid}.jpg"
            if make_poster(src, fact.get("duration_s"), dest,
                           fact.get("width"), fact.get("height")):
                posters_ok += 1; poster_rel = f"posters/{iid}.jpg"
            else:
                posters_fail += 1
            state = "inventoried; poster ready" if poster_rel else "inventoried; poster FAILED"
        else:
            dest = OUT/"thumbs"/f"{iid}.jpg"
            if make_thumb(src, dest):
                thumbs_ok += 1; thumb_rel = f"thumbs/{iid}.jpg"
            else:
                thumbs_fail += 1
            state = "inventoried; thumbnail ready" if thumb_rel else "inventoried; thumbnail FAILED"
        rec = {**r, **fact, "id": iid, "shelf_file": shelf_name,
               "poster": poster_rel, "thumb": thumb_rel, "perception": state}
        index.append(rec)
        kv = {
            "title": human(src.stem), "type": r["kind"], "perception": state,
            "source_path": str(src), "source_tree": r["tree"], "rel": r["rel"],
            "bytes": r["bytes"],
            "mtime_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(r["mtime"])),
            "codec": fact.get("codec") or "", "width": fact.get("width") or "",
            "height": fact.get("height") or "",
            "duration_s": fact.get("duration_s") or "",
            "poster": poster_rel or "", "thumb": thumb_rel or "",
        }
        (OUT/"ledger/items"/f"{Path(shelf_name).stem}.txt").write_text(
            "".join(f"{k} = {v}\n" for k, v in kv.items()))
    with open(OUT/"media-index.jsonl", "w") as f:
        for rec in index:
            f.write(json.dumps(rec) + "\n")

    def agg(rs):
        return {"count": len(rs), "bytes": sum(r["bytes"] for r in rs),
                "videos": sum(1 for r in rs if r["kind"] == "video"),
                "images": sum(1 for r in rs if r["kind"] == "image"),
                "oldest": min((r["mtime"] for r in rs), default=None),
                "newest": max((r["mtime"] for r in rs), default=None)}
    summary = {
        "found_total": agg(rows), "eligible": agg(eligible),
        "excluded_count": len(rows) - len(eligible),
        "by_tree": {t: agg([r for r in rows if r["tree"] == t]) for t in
                    sorted({r["tree"] for r in rows})},
        "selected": len(index),
        "selected_video_hours": round(sum(
            (rec.get("duration_s") or 0) for rec in index
            if rec["kind"] == "video") / 3600, 6),
        "all_eligible_video_hours": None,  # filled by caller if probed
        "posters_ok": posters_ok, "posters_fail": posters_fail,
        "thumbs_ok": thumbs_ok, "thumbs_fail": thumbs_fail,
    }
    (OUT/"summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))

if __name__ == "__main__":
    main()
