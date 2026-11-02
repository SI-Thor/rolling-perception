# Confluence Slice 1 console

FastAPI + one static page (fleet portal pattern). Run with the
Thor's ml venv: `~/ml/.venv/bin/python app.py` (uvicorn, :8320).

Env: `CONSOLE_LEDGER_DIR` (default `~/confluence/ledger`),
`CONSOLE_MEDIA_DIR` (default `~/confluence/media`),
`CONSOLE_PORT` (8320), `CONSOLE_STALE_S` (90).

Reads, tolerantly (missing/malformed = "no data yet", never a
crash), per SPEC §A2.3: `ledger/streams/<id>/{lens.txt, state.txt,
events.jsonl, health.txt}`, `ledger/items/<id>.txt`, and the media
dir for the shelf. `events.jsonl` accepts the watcher's own
verdict rows (`{kind: "verdict", frame, changed_tiles[],
wall_us, t_capture_us}`), spec frame verdicts
(`{tick, tiles[], score, jev_p?, line?, image?}`) and wave-3
per-tile rows (`{frame, tile, changed, smoothed_score}`), grouped
per frame; frame images resolve from the event or
`streams/<id>/frames/<frame>.png|jpg`.

Health: heartbeat from `health.txt` (`heartbeat_ts`), falling back
to `state.txt`, then file mtimes. Age > `CONSOLE_STALE_S` (or no
heartbeat ever) renders AMBER "NOT REPORTING" — never silently
green. Porch-cam behaviour in the fixture test proves the
no-heartbeat case also goes amber.

Corrections: the "That wasn't a change" button POSTs to
`/api/correct`, which appends one JSON line to
`ledger/attention/corrections.jsonl` — the trust-metrics
feedstock (SPEC §C2.2/2.5). Verified live on the Thor: POST
returned ok and the line landed in the file.

Files: `app.py` (backend + /api/state + /api/correct +
traversal-guarded /files), `index.html` (feed / shelf / health),
`make_fixtures.py` (builds the Thor test fixture from wave-3
verdicts + real frames), `test_console.py` (regression tests —
see the defect-fix section below).

## 2026-11-02 — defect fix: the feed dropped the watcher's verdicts

**Symptom** (found by the INSTALL-FIX proof, INSTALL-PROOF.md
step 6): against a ledger written by the installed
`confluence-watch`, `/api/state` reported `"events": 0` and an
empty feed although `events.jsonl` held two verdict rows.
Health, shelf and corrections were unaffected; the ledger itself
was complete and correct.

**Cause**: the watcher writes verdict rows as
`{kind: "verdict", frame, wall_us, t_capture_us, changed_tiles[],
tiles: [per-tile objects], …}` (`slice1/core/src/ledger.rs`).
`stream_events` recognised only `tiles` (as int indices), `line`/
`summary`/`text`, or wave-3 per-tile rows — never
`changed_tiles` — and the row's `tiles` field is a list of
objects, which the int filter emptied; with no tiles and no line,
the event was silently dropped. The deployed console had only
ever been exercised against wave-3-shaped rows. The row's only
timestamps are also microsecond epochs, which the parser never
read.

**Fix** (`app.py`, `stream_events`): prefer `changed_tiles` for
the changed set, fall back to int `tiles`; derive `ts` from
`t_capture_us`/`wall_us` (µs → s) when no `ts`/`timestamp` is
present. Both older shapes remain accepted unchanged. Same pass,
per AUDIT-PRODUCT: `/api/correct` now validates `event_id`
against the stream's known events (400 for unknown id or stream)
and returns 400 — not 500 — for a malformed or non-object JSON
body.

**Proof**: `test_console.py` builds a ledger with the real
verdict shape (a service row, a 16-tile cut verdict at frame 4,
an object verdict `{5,6}` at frame 7), wave-3 per-tile rows, and
a spec frame verdict, and asserts over HTTP: both verdicts
surface with correct tiles, synthesised lines, and capture
timestamps; the wave-3 and spec rows still surface; service rows
do not; corrections validate (unknown → 400, malformed → 400,
known → 200 + appended). Run 2026-11-02 (dev VM, venv with
fastapi + httpx):

```
PASS GET /api/state 200 · cam1 reports 4 events
PASS cut verdict surfaces · tiles = all 16 · line "Whole scene changed"
PASS cut ts from t_capture_us · kind = verdict
PASS object verdict surfaces {5,6} · line names the centre
PASS wave-3 rows still group per frame · spec verdict still surfaces
PASS service rows do not surface
PASS unknown event_id -> 400 · unknown stream -> 400
PASS malformed JSON -> 400 (not 500) · known -> 200 · correction appended
ALL PASS  (17 checks)
```

Not deployed: the Thor's running console is untouched; shipping
this fix is a post-soak-verdict decision.
