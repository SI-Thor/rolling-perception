#!/usr/bin/env python3
"""Confluence Slice 1 console — the human face.

FastAPI + one static page (the fleet portal pattern). Reads the
slice-1 ledger (SPEC §A2.3: ledger/streams/<id>/{lens,state}.txt,
events.jsonl, health.txt) and a media directory for the shelf.
Every read is tolerant: missing or malformed data renders as
"no data yet", never a crash — the console is a projection of the
ledger, and a broken projection must not pretend the world is fine
or dead; it says what it could not read.

Config (env):
  CONSOLE_LEDGER_DIR   default ~/confluence/ledger
  CONSOLE_MEDIA_DIR    default ~/confluence/media
  CONSOLE_PORT         default 8320
  CONSOLE_STALE_S      heartbeat age (s) past which a stream shows
                       AMBER "not reporting" (default 90)

Corrections (the trust-metrics feedstock, SPEC §C2.5) append to
ledger/attention/corrections.jsonl — real writes, one JSON line per
tap, never a silent no-op.
"""
import json, os, time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, PlainTextResponse

LEDGER = Path(os.environ.get("CONSOLE_LEDGER_DIR", str(Path.home() / "confluence" / "ledger")))
MEDIA = Path(os.environ.get("CONSOLE_MEDIA_DIR", str(Path.home() / "confluence" / "media")))
STALE_S = float(os.environ.get("CONSOLE_STALE_S", "90"))
HERE = Path(__file__).resolve().parent

app = FastAPI(title="Confluence Slice 1 console")

IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
VID_EXT = {".mp4", ".webm", ".mkv", ".mov", ".m4v"}


def read_kv(path):
    """key = value text file -> dict. Missing/bad file -> {}."""
    out = {}
    try:
        for line in path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    except OSError:
        pass
    return out


def read_jsonl(path, limit=2000):
    rows = []
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return rows
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def parse_ts(v):
    """Epoch float/int, digit string, or ISO text -> epoch float|None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    try:
        return float(s)
    except ValueError:
        pass
    try:
        from datetime import datetime
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


REGIONS = [(0, "top-left"), (1, "top"), (2, "top"), (3, "top-right"),
           (4, "left"), (5, "centre"), (6, "centre"), (7, "right"),
           (8, "left"), (9, "centre"), (10, "centre"), (11, "right"),
           (12, "bottom-left"), (13, "bottom"), (14, "bottom"), (15, "bottom-right")]


def describe_tiles(tiles, grid=4):
    if not tiles:
        return "Change detected"
    if len(tiles) >= (grid * grid) * 3 // 4:
        return "Whole scene changed"
    words = []
    for t in tiles:
        w = REGIONS[t][1] if isinstance(t, int) and 0 <= t < 16 else None
        if w and w not in words:
            words.append(w)
    if not words:
        return "Change detected"
    return "Change in the " + ", ".join(words[:3]) + " of the frame"


def stream_events(sdir, sid):
    """Normalise events.jsonl rows into feed events.

    Accepts (a) frame verdicts {tick|frame, tiles[], score, line?,
    image?}, (b) wave-3 per-tile verdict rows {frame, tile, changed}
    which are grouped per frame, (c) generic {ts, line|summary}.
    """
    rows = read_jsonl(sdir / "events.jsonl")
    events, tile_groups = [], {}
    for i, r in enumerate(rows):
        if "tile" in r and ("changed" in r or "changed_raw" in r):
            tile_groups.setdefault(r.get("frame", r.get("tick", 0)), []).append(r)
            continue
        tiles = r.get("tiles") or []
        ev = {
            "id": f"{sid}:{r.get('tick', r.get('frame', i))}",
            "stream": sid,
            "ts": parse_ts(r.get("ts", r.get("timestamp"))),
            "frame": r.get("frame", r.get("tick")),
            "tiles": [t for t in tiles if isinstance(t, int)],
            "score": r.get("score", r.get("smoothed_score")),
            "jev_p": r.get("jev_p"),
            "line": r.get("line") or r.get("summary") or r.get("text"),
            "image": r.get("image") or r.get("frame_image"),
            "kind": r.get("kind") or r.get("type") or "change",
        }
        if ev["tiles"] or ev["line"]:
            events.append(ev)
    for frame, trows in tile_groups.items():
        changed = [t["tile"] for t in trows if t.get("changed")]
        if not changed:
            continue
        scores = [t.get("smoothed_score") for t in trows if t.get("smoothed_score") is not None]
        events.append({
            "id": f"{sid}:{frame}", "stream": sid, "ts": None, "frame": frame,
            "tiles": changed, "score": max(scores) if scores else None,
            "jev_p": None, "line": None, "image": None, "kind": "change",
        })
    for ev in events:
        if not ev["line"]:
            ev["line"] = describe_tiles(ev["tiles"])
        if not ev["image"]:
            for cand in (sdir / "frames" / f"{ev['frame']}.png",
                         sdir / "frames" / f"frame-{ev['frame']}.png",
                         sdir / "frames" / f"{ev['frame']}.jpg"):
                if cand.exists():
                    ev["image"] = str(cand.relative_to(LEDGER)) if str(cand).startswith(str(LEDGER)) else None
                    break
    events.sort(key=lambda e: (e["ts"] or 0, e["frame"] if isinstance(e["frame"], (int, float)) else 0), reverse=True)
    return events


def stream_health(sdir, sid, lens, state):
    h = read_kv(sdir / "health.txt")
    hb = parse_ts(h.get("heartbeat_ts") or h.get("ts") or h.get("last_beat")
                  or state.get("heartbeat_ts") or state.get("last_heartbeat"))
    if hb is None:
        try:
            hb = max((sdir / f).stat().st_mtime for f in ("state.txt", "events.jsonl") if (sdir / f).exists())
        except ValueError:
            hb = None
    age = (time.time() - hb) if hb else None
    stale = (age is None) or (age > STALE_S)
    def num(*sources):
        for src, key in sources:
            v = src.get(key)
            if v not in (None, ""):
                return v
        return None
    return {
        "stream": sid,
        "state_line": state.get("state") or state.get("line") or h.get("state") or "no state reported",
        "heartbeat_age_s": round(age, 1) if age is not None else None,
        "stale": stale,
        "embed_spent": num((state, "embeds_spent"), (state, "embed_seconds_spent"), (h, "embeds_spent")),
        "budget": num((lens, "budget_embed_seconds"), (lens, "budget"), (h, "budget_embed_seconds")),
        "coverage": num((state, "coverage"), (h, "coverage")),
        "embed_p50_ms": num((h, "embed_p50_ms"), (state, "embed_p50_ms")),
        "embed_p99_ms": num((h, "embed_p99_ms"), (state, "embed_p99_ms")),
        "queue_depth": num((h, "queue_depth"), (state, "queue_depth")),
    }


def shelf_items():
    items_meta = {}
    idir = LEDGER / "items"
    if idir.is_dir():
        for f in idir.glob("*.txt"):
            items_meta[f.stem] = read_kv(f)
    items = []
    if MEDIA.is_dir():
        for p in sorted(MEDIA.rglob("*")):
            if not p.is_file():
                continue
            ext = p.suffix.lower()
            if ext not in IMG_EXT | VID_EXT:
                continue
            rel = str(p.relative_to(MEDIA))
            meta = items_meta.get(p.stem, {})
            poster = None
            if ext in VID_EXT:
                for cand in (p.with_suffix(".poster.jpg"), p.with_name(p.stem + ".jpg"),
                             p.with_name(p.stem + ".png")):
                    if cand.exists():
                        poster = str(cand.relative_to(MEDIA))
                        break
            items.append({
                "id": p.stem, "title": meta.get("title") or p.stem.replace("-", " ").replace("_", " "),
                "type": meta.get("type") or ("video" if ext in VID_EXT else "image"),
                "perception": meta.get("perception") or meta.get("perception_state") or "unperceived",
                "src": rel, "poster": poster,
            })
    return items


def full_state():
    streams_dir = LEDGER / "streams"
    streams, feed = [], []
    if streams_dir.is_dir():
        for sdir in sorted(streams_dir.iterdir()):
            if not sdir.is_dir():
                continue
            sid = sdir.name
            lens, state = read_kv(sdir / "lens.txt"), read_kv(sdir / "state.txt")
            evs = stream_events(sdir, sid)
            feed.extend(evs)
            streams.append({
                "id": sid,
                "has_data": bool(lens or state or evs),
                "health": stream_health(sdir, sid, lens, state),
                "events": len(evs),
            })
    feed.sort(key=lambda e: (e["ts"] or 0, e["frame"] if isinstance(e["frame"], (int, float)) else 0), reverse=True)
    return {"streams": streams, "feed": feed[:200], "shelf": shelf_items(),
            "ledger": str(LEDGER), "generated": time.time()}


@app.get("/", response_class=HTMLResponse)
def index():
    try:
        return (HERE / "index.html").read_text()
    except OSError:
        return PlainTextResponse("index.html missing beside app.py", status_code=500)


@app.get("/api/state")
def api_state():
    return JSONResponse(full_state())


@app.post("/api/correct")
async def api_correct(req: Request):
    body = await req.json()
    sid, eid = str(body.get("stream", "")), str(body.get("event_id", ""))
    if not sid or not eid:
        return JSONResponse({"ok": False, "error": "stream and event_id required"}, status_code=400)
    adir = LEDGER / "attention"
    adir.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.time(), "stream": sid, "event_id": eid,
           "correction": body.get("correction") or "not-a-change",
           "frame": body.get("frame"), "tiles": body.get("tiles")}
    with open(adir / "corrections.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    return JSONResponse({"ok": True, "recorded": rec})


@app.get("/files/{path:path}")
def files(path: str):
    """Serve ledger frame images and shelf media, traversal-guarded."""
    for root in (LEDGER, MEDIA):
        cand = (root / path).resolve()
        if str(cand).startswith(str(root.resolve())) and cand.is_file():
            return FileResponse(cand)
    return PlainTextResponse("not found", status_code=404)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("CONSOLE_PORT", "8320")))
