# Confluence Slice 1 console

FastAPI + one static page (fleet portal pattern). Run with the
Thor's ml venv: `~/ml/.venv/bin/python app.py` (uvicorn, :8320).

Env: `CONSOLE_LEDGER_DIR` (default `~/confluence/ledger`),
`CONSOLE_MEDIA_DIR` (default `~/confluence/media`),
`CONSOLE_PORT` (8320), `CONSOLE_STALE_S` (90).

Reads, tolerantly (missing/malformed = "no data yet", never a
crash), per SPEC §A2.3: `ledger/streams/<id>/{lens.txt, state.txt,
events.jsonl, health.txt}`, `ledger/items/<id>.txt`, and the media
dir for the shelf. `events.jsonl` accepts spec frame verdicts
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
verdicts + real frames).
