#!/usr/bin/env python3
"""Confluence Slice 2 — serve-plane spike: the player backend.

One FastAPI app (the fleet portal pattern, Thor ml venv). Turns a
library item into an HLS stream, deciding per request:

  REMUX     source codec is already browser-playable (probe says
            h264) -> GStreamer parse-only pipeline into TS HLS.
            Encode draw: 0 fps. Always served, never refused.
  FMP4      source codec is hevc -> fmp4_pipeline.py: GStreamer
            mp4mux remux to a fragmented MP4, split into init +
            GOP-aligned media segments (tfhd default-base-is-moof
            patched in place), HLS-fMP4 with EXT-X-MAP. Encode
            draw: 0 fps (a remux, charged like REMUX). Always
            served, never refused. Evidence: fmp4-spike/RESULTS.md
            — spec-conformant by checklist + probe; the automated
            form of that checklist is verify_fmp4.py.
  TRANSCODE anything else -> GStreamer V4L2 stack end to end
            (nvv4l2decoder -> nvvidconv -> nvv4l2h264enc) into
            TS HLS. Target stays H.264: the transcode output is
            produced live by the V4L2 stack as TS; HEVC-in-TS is
            outside Apple's HLS spec, and no live fMP4 sink is
            wired for the encode path (the FMP4 mode above covers
            items whose HEVC encode already exists).

Why GStreamer for both modes: this box's ffmpeg build has NO HLS
muxer at all (measured: 'Unrecognized option hls_time'; muxers
list has mp4/mpegts only). The bench's stack lesson applied.

Budget (NVENC-BENCH.md §6): the metered resource is encode work.
Sessions are budgeted in 1080p-equivalent transcode units —
PROMISE_UNITS = 8 (the bench's promise), a >1080p source counts
2 (4K rule). A new transcode that would exceed the budget is
REFUSED with a plain "house is busy" state; remux always serves.
Every session's MEASURED encode-fps draw (frames out / wall time,
from counting frames in finished segments) is logged to the
registry whether or not the budget model used it.

Supervision (the bench's zombie lesson, implemented): a watchdog
counts FRAMES in segment files, never process existence. If a
transcode's frame count does not increase for > STALL_S seconds
while its worker is alive, the worker's process group is killed
and the session is marked failed(reason=watchdog_stall) in the
registry.

Registry: LEDGER/sessions.jsonl, append-only, one JSON object per
row: {ts, event: start|stop|failed|refused, session, item, mode,
units, pid?, fps_draw?, frames?, reason?}. Plain text, foldable by
any tool — the ledger style, same as slices 1's streams.

Config (env):
  PLAYER_MEDIA_DIR    library root       (default ~/confluence-play/slice2/player/media)
  PLAYER_WORK_DIR     session HLS output (default <media>/../work)
  PLAYER_LEDGER_DIR   registry dir       (default <media>/../ledger)
  PLAYER_PORT         default 8340
  PLAYER_PHANTOM_UNITS  TEST HOOK: pretend N budget units are
                      already used (acceptance test c). Default 0.
"""
import json, math, os, re, signal, subprocess, sys, threading, time, uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, PlainTextResponse

HOME = Path.home()
MEDIA = Path(os.environ.get("PLAYER_MEDIA_DIR", str(HOME / "confluence-play/slice2/player/media")))
WORK = Path(os.environ.get("PLAYER_WORK_DIR", str(MEDIA.parent / "work")))
LEDGER = Path(os.environ.get("PLAYER_LEDGER_DIR", str(MEDIA.parent / "ledger")))
PHANTOM_UNITS = int(os.environ.get("PLAYER_PHANTOM_UNITS", "0"))
HERE = Path(__file__).resolve().parent

PROMISE_UNITS = 8          # NVENC-BENCH §6: promise 8 live transcodes
SEG_DUR = 4                # HLS segment target seconds
STALL_S = 5.0              # watchdog: no new frames for this long = zombie
BITRATE = 6000000          # bench used 6 Mb/s

VID_EXT = {".mp4", ".mkv", ".mov", ".m4v", ".webm"}
DEMUX = {".mp4": "qtdemux", ".m4v": "qtdemux", ".mov": "qtdemux",
         ".mkv": "matroskademux", ".webm": "matroskademux"}
DECODE_PARSE = {"hevc": "h265parse", "h264": "h264parse", "av1": "av1parse",
                "vp9": "vp9parse", "mpeg4": "mpeg4videoparse"}

app = FastAPI(title="Confluence Slice 2 player (spike)")

REG_LOCK = threading.Lock()
SES_LOCK = threading.Lock()
SESSIONS = {}              # sid -> Session dict (live truth; registry is the log)


# ---------------------------------------------------------------- library

def probe(path):
    """ffprobe -> {codec,width,height,fps,duration} or None. Timeout-guarded;
    never called on non-regular files (a fifo probe would block forever)."""
    if not path.is_file():
        return None
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name,width,height,r_frame_rate",
             "-show_entries", "format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=8)
        d = json.loads(out.stdout or "{}")
        st = (d.get("streams") or [{}])[0]
        if not st.get("codec_name"):
            return None
        fps = 0.0
        num, _, den = str(st.get("r_frame_rate", "0/1")).partition("/")
        try:
            fps = float(num) / float(den or 1)
        except (ValueError, ZeroDivisionError):
            fps = 0.0
        return {"codec": st["codec_name"], "width": st.get("width"),
                "height": st.get("height"), "fps": fps,
                "duration": float((d.get("format") or {}).get("duration", 0) or 0)}
    except Exception:
        return None


def library():
    items = []
    if MEDIA.is_dir():
        for p in sorted(MEDIA.iterdir()):
            if p.name == "stall.fifo":
                items.append({"id": p.stem, "title": "Stall test (fifo, never delivers)",
                              "src": p.name, "probe": None, "mode": "transcode",
                              "test_only": True})
                continue
            if not p.is_file() or p.suffix.lower() not in VID_EXT:
                continue
            pr = probe(p)
            codec = (pr or {}).get("codec")
            mode = ("remux" if codec == "h264" else
                    "fmp4" if codec == "hevc" else "transcode")
            items.append({"id": p.stem,
                          "title": p.stem.replace("-", " ").replace("_", " "),
                          "src": p.name, "probe": pr, "mode": mode,
                          "poster": (p.stem + ".jpg") if (p.with_suffix(".jpg")).exists() else None})
    return items


def find_item(item_id):
    for it in library():
        if it["id"] == item_id:
            return it
    return None


def units_for(item):
    h = (item.get("probe") or {}).get("height") or 1080
    return 1 if h <= 1080 else 2     # bench: 4K counts as 2 units


# ---------------------------------------------------------------- registry

def reg(row):
    LEDGER.mkdir(parents=True, exist_ok=True)
    row = {"ts": time.time(), **row}
    with REG_LOCK:
        with open(LEDGER / "sessions.jsonl", "a") as f:
            f.write(json.dumps(row) + "\n")


def read_registry(limit=500):
    rows = []
    try:
        lines = (LEDGER / "sessions.jsonl").read_text(errors="replace").splitlines()
    except OSError:
        return rows
    for line in lines[-limit:]:
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def active_units():
    with SES_LOCK:
        live = sum(s.units for s in SESSIONS.values()
                   if s.mode == "transcode" and s.status in ("starting", "running"))
    return live + PHANTOM_UNITS


# ---------------------------------------------------------------- workers

def build_cmd(item, sdir):
    """The GStreamer pipeline for this session (list form, no shell)."""
    src = MEDIA / item["src"]
    hls = ["hlssink2", f"playlist-location={sdir}/playlist.m3u8",
           f"location={sdir}/seg%05d.ts", f"target-duration={SEG_DUR}",
           "playlist-length=0", "max-files=0"]
    demux = DEMUX.get(Path(item["src"]).suffix.lower(), "qtdemux")
    if item["mode"] == "fmp4":
        return [sys.executable, str(HERE / "fmp4_pipeline.py"),
                str(src), str(sdir), demux]
    if item["mode"] == "remux":
        return (["gst-launch-1.0", "-e", "filesrc", f"location={src}", "!",
                 demux, "name=d", "d.video_0", "!", "queue", "!",
                 "h264parse", "!"] + hls)
    pr = item.get("probe") or {}
    parse = DECODE_PARSE.get(pr.get("codec", ""), "h265parse")
    w = pr.get("width") or 1920
    h = pr.get("height") or 1080
    fps = pr.get("fps") or 30.0
    gop = max(int(round(fps)) * SEG_DUR, 30)
    return (["gst-launch-1.0", "-e", "filesrc", f"location={src}", "!",
             demux, "name=d", "d.video_0", "!", "queue", "!",
             parse, "!", "nvv4l2decoder", "!", "nvvidconv", "!",
             f"video/x-raw(memory:NVMM),width={w},height={h},format=NV12", "!",
             "nvv4l2h264enc", f"bitrate={BITRATE}", f"iframeinterval={gop}",
             "control-rate=1", "!", "h264parse", "!"] + hls)


def count_frames(segfile):
    """Frames in a finished TS segment, counted as video PACKETS
    (-count_packets), not decoded frames. Two measured reasons
    (acceptance run 3): (1) this box's ffprobe decodes via
    h264_cuvid, which returned nb_read_frames=N/A on some segments
    ("non-existing PPS") and silently undercounted the session
    (1080 of 1800); packet counting needs no decode and summed to
    exactly 1800/1800. (2) hlssink2/mpegtsmux TS exposes the video
    stream twice, so the csv is "120\n\n120\n" — take the first
    all-digit token, never int() the whole output."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
             "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(segfile)],
            capture_output=True, text=True, timeout=10)
        for tok in (out.stdout or "").split():
            if tok.isdigit():
                return int(tok)
        return None
    except Exception:
        return None


class Session:
    def __init__(self, item):
        self.id = uuid.uuid4().hex[:8]
        self.item = item
        self.mode = item["mode"]
        self.units = units_for(item) if self.mode == "transcode" else 0
        self.dir = WORK / self.id
        self.status = "starting"        # starting|running|ready|failed|busy
        self.proc = None
        self.started = time.time()
        self.frames = 0
        self.fps_draw = 0.0
        self.reason = None
        self.ended = None               # worker-exit timestamp (pre-recount)
        self._counted = {}              # segfile -> frames (stable files)
        self._last_frames = 0
        self._last_increase = time.time()

    def playlist_ready(self):
        if self.mode == "fmp4":
            return ((self.dir / "playlist.m3u8").exists()
                    and (self.dir / "init.mp4").exists()
                    and any(self.dir.glob("seg_*.m4s")))
        return (self.dir / "playlist.m3u8").exists() and any(self.dir.glob("seg*.ts"))


def start_session(item):
    """Budget gate lives here: transcode over budget -> refused row + busy."""
    with SES_LOCK:
        for s in SESSIONS.values():
            if s.item["id"] == item["id"] and s.status in ("starting", "running", "ready"):
                return s, False                      # second viewer rides free
    if item["mode"] == "transcode":
        used = active_units()
        if used + units_for(item) > PROMISE_UNITS:
            reg({"event": "refused", "session": None, "item": item["id"],
                 "mode": "transcode", "units": units_for(item),
                 "reason": f"budget: {used}+{units_for(item)} > {PROMISE_UNITS} units"})
            busy = Session(item)
            busy.status = "busy"
            return busy, False
    s = Session(item)
    s.dir.mkdir(parents=True, exist_ok=True)
    with SES_LOCK:
        SESSIONS[s.id] = s
    log = open(s.dir / "worker.log", "wb")
    s.proc = subprocess.Popen(build_cmd(item, s.dir), stdout=log, stderr=subprocess.STDOUT,
                              start_new_session=True)
    s.status = "running"
    reg({"event": "start", "session": s.id, "item": item["id"], "mode": s.mode,
         "units": s.units, "pid": s.proc.pid})
    return s, True


def finish(s, status, reason=None):
    s.status = status
    s.reason = reason
    # Wall ends when the WORKER ended (stamped by supervise before
    # its recount), not when bookkeeping finished — acceptance run 4
    # showed the 21-segment recount adding ~15 s of phantom "draw
    # time" to fps_draw. The meter must not bill its own reading.
    wall = max((s.ended or time.time()) - s.started, 0.001)
    s.fps_draw = round(s.frames / wall, 1) if s.mode == "transcode" else 0.0
    reg({"event": "stop" if status == "ready" else "failed",
         "session": s.id, "item": s.item["id"], "mode": s.mode, "units": s.units,
         "frames": s.frames, "fps_draw": s.fps_draw,
         "throughput_fps": round(s.frames / wall, 1),
         "reason": reason})


def supervise():
    """The watchdog loop: frames, not processes (bench zombie lesson)."""
    while True:
        time.sleep(0.5)
        with SES_LOCK:
            live = [s for s in SESSIONS.values() if s.status in ("starting", "running")]
        for s in live:
            if s.mode == "fmp4":
                # frames = samples recorded by build_hls.py; the
                # pipeline is a ~0.1 s remux, so this is bookkeeping,
                # not supervision (the stall watchdog is transcode-only).
                sj = s.dir / "segments.json"
                if sj.exists():
                    try:
                        s.frames = sum(g.get("samples", 0) for g in
                                       json.loads(sj.read_text()).get("segments", []))
                    except Exception:
                        pass
                if s.proc and s.proc.poll() is not None:
                    if s.ended is None:
                        s.ended = time.time()
                    if s.proc.returncode == 0 and s.playlist_ready():
                        finish(s, "ready")
                    else:
                        finish(s, "failed", reason=f"worker_exit_{s.proc.returncode}")
                continue
            # count frames: stable segments once; newest segment repeatedly
            segs = sorted(s.dir.glob("seg*.ts"))
            total = sum(s._counted.values())
            for seg in segs:
                if seg.name in s._counted:
                    continue
                newest = seg == segs[-1] and s.proc and s.proc.poll() is None
                if not newest:
                    n = count_frames(seg)
                    if n is not None:
                        s._counted[seg.name] = n
                        total += n
            if segs:
                n = count_frames(segs[-1])
                if n is not None:
                    total = sum(s._counted.values()) + (0 if segs[-1].name in s._counted else n)
            s.frames = total
            if total > s._last_frames:
                s._last_frames = total
                s._last_increase = time.time()
            wall = max(time.time() - s.started, 0.001)
            if s.mode == "transcode":
                s.fps_draw = round(total / wall, 1)
            # stall?
            if (s.mode == "transcode" and s.proc and s.proc.poll() is None
                    and time.time() - s._last_increase > STALL_S):
                try:
                    os.killpg(s.proc.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                finish(s, "failed", reason="watchdog_stall")
                continue
            # exited?
            if s.proc and s.proc.poll() is not None:
                if s.ended is None:
                    s.ended = time.time()
                # final full count
                s.frames = sum(c for c in (count_frames(g) for g in sorted(s.dir.glob("seg*.ts"))) if c)
                if s.proc.returncode == 0 and s.playlist_ready():
                    finish(s, "ready")
                else:
                    finish(s, "failed", reason=f"worker_exit_{s.proc.returncode}")


threading.Thread(target=supervise, daemon=True).start()


def session_view(s):
    return {"session": s.id, "item": s.item["id"], "mode": s.mode,
            "status": s.status, "units": s.units, "frames": s.frames,
            "fps_draw": s.fps_draw, "reason": s.reason,
            "playlist": f"/hls/{s.id}/playlist.m3u8" if s.playlist_ready() else None}


# ---------------------------------------------------------------- http

@app.get("/", response_class=HTMLResponse)
def index():
    try:
        return (HERE / "index.html").read_text()
    except OSError:
        return PlainTextResponse("index.html missing beside player.py", status_code=500)


@app.get("/api/library")
def api_library():
    return JSONResponse({"items": library(), "media": str(MEDIA)})


@app.get("/api/sessions")
def api_sessions():
    rows = read_registry()
    with SES_LOCK:
        live = [session_view(s) for s in SESSIONS.values()]
    return JSONResponse({"sessions": live, "registry_tail": rows[-20:],
                         "units_used": active_units(), "units_budget": PROMISE_UNITS,
                         "phantom_units": PHANTOM_UNITS})


@app.post("/api/play")
async def api_play(req: Request):
    body = await req.json()
    item = find_item(str(body.get("id", "")))
    if not item:
        return JSONResponse({"ok": False, "error": "unknown item"}, status_code=404)
    s, _ = start_session(item)
    if s.status == "busy":
        return JSONResponse({"ok": False, "state": "busy",
                             "message": "The house is busy — the Thor is at its encode "
                                        "budget right now. Direct-play items still work.",
                             "units_used": active_units(), "units_budget": PROMISE_UNITS},
                            status_code=429)
    return JSONResponse({"ok": True, **session_view(s)})


@app.get("/api/session/{sid}")
def api_session(sid: str):
    with SES_LOCK:
        s = SESSIONS.get(sid)
    if not s:
        return JSONResponse({"ok": False, "error": "unknown session"}, status_code=404)
    return JSONResponse({"ok": True, **session_view(s)})


@app.get("/play/{item_id}")
def play(item_id: str):
    """Start (or reuse) a session and return the HLS playlist itself,
    segment URLs rewritten to this server's /hls/<sid>/ paths."""
    item = find_item(item_id)
    if not item:
        return PlainTextResponse("unknown item", status_code=404)
    s, _ = start_session(item)
    if s.status == "busy":
        return JSONResponse({"state": "busy",
                             "message": "The house is busy — the Thor is at its encode budget.",
                             "units_used": active_units(), "units_budget": PROMISE_UNITS},
                            status_code=429)
    deadline = time.time() + 90
    while time.time() < deadline:
        if s.status == "failed":
            return JSONResponse({"state": "failed", "reason": s.reason}, status_code=502)
        if s.playlist_ready() and s.status == "ready":
            break
        if s.playlist_ready() and s.mode in ("remux", "fmp4"):
            break
        time.sleep(0.4)
    pl = s.dir / "playlist.m3u8"
    if not pl.exists():
        return JSONResponse({"state": s.status, "error": "playlist not ready"}, status_code=503)
    text = pl.read_text(errors="replace")
    out_lines = []
    for ln in text.splitlines():
        st = ln.strip()
        if st.startswith("#EXT-X-MAP:") and 'URI="' in st:
            ln = ln.replace('URI="', f'URI="/hls/{s.id}/', 1)
        elif st.endswith(".ts") or st.endswith(".m4s"):
            ln = f"/hls/{s.id}/{st}"
        out_lines.append(ln)
    return PlainTextResponse("\n".join(out_lines) + "\n",
                             media_type="application/x-mpegURL")


@app.get("/hls/{sid}/{name}")
def hls(sid: str, name: str):
    if not re.fullmatch(r"[0-9a-f]{8}", sid) or not re.fullmatch(
            r"(playlist\.m3u8|seg\d+\.ts|init\.mp4|seg_\d+\.m4s)", name):
        return PlainTextResponse("not found", status_code=404)
    cand = (WORK / sid / name).resolve()
    if not str(cand).startswith(str(WORK.resolve())) or not cand.is_file():
        return PlainTextResponse("not found", status_code=404)
    mt = ("application/x-mpegURL" if name.endswith(".m3u8") else
          "video/MP2T" if name.endswith(".ts") else
          "video/mp4" if name == "init.mp4" else "video/iso.segment")
    return FileResponse(cand, media_type=mt)


@app.on_event("shutdown")
def _shutdown():
    with SES_LOCK:
        for s in SESSIONS.values():
            if s.proc and s.proc.poll() is None:
                try:
                    os.killpg(s.proc.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PLAYER_PORT", "8340")))
