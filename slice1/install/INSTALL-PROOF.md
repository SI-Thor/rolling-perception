# Install proof — the pack, run end to end (2026-11-02)

Lane INSTALL-FIX. The original pack shipped without ever being
run: its installer looked for a binary the build never produces
(`confluence`, for `confluence-watch`) and its service unit
started a CLI that never existed (`confluence serve --config
<dir>`). This file records the rewritten pack being run, in
full, in a scratch prefix — the step the original skipped.

## Environment, stated plainly

- Machine: the dev VM (x86_64, no GPU, no jev-rack service) —
  **not** a Thor. The Thor-only machine checks were bypassed
  with the installer's documented rehearsal flag
  (`CONFLUENCE_ALLOW_UNTESTED_MACHINE=1`), which downgrades
  them to loud warnings. Everything else about the run is the
  real flow: real build, real binary, real units, real config,
  real ingest, real ledger.
- Scratch root: `/tmp/confluence-install-proof/root`, passed as
  `CONFLUENCE_HOME`; units additionally redirected with
  `CONFLUENCE_UNIT_DIR=<root>/.config/systemd/user`, so nothing
  on the machine was enabled or touched outside the scratch
  tree. (`/tmp` here is a 512 MB tmpfs — the installer's disk
  warning below is that fact, correctly reported.)
- The soak and the Thor deployment were not touched.

## Step 1 — dry run (default): plan prints, nothing changes

```
$ CONFLUENCE_HOME=$S bash install.sh
Confluence installer — DRY RUN. Nothing will be changed.
Install root: /tmp/confluence-install-proof/root
Source: ~/workspace/rolling-perception-work/repo-staging (checkout)

Checking prerequisites...
  WARN: Jetson AGX Thor (aarch64); this machine reports x86_64 — check failed.
        (dry run: the plan below still prints; --apply would stop here)
  WARN: GPU answers (nvidia-smi) — nvidia-smi not on PATH — check failed.
  WARN: CUDA compiler (nvcc) — check failed.
  ok: Rust toolchain (cargo)       (cargo 1.99.1)
  ok: git
  ok: python3 (the ingest is a Python program)
  ok: python3 can import numpy, Pillow and requests (ingest dependencies)
  WARN: image-understanding rack (jev-rack service) is installed — check failed.
  WARN: only 0 GB free under /tmp/confluence-install-proof (minimum 50 GB).
  WARN: no interpreter found that imports fastapi + uvicorn.
        The console unit will be written for python3 and will NOT
        start until its dependencies are installed, e.g.:
          python3 -m pip install fastapi uvicorn

Actions:
  WOULD: create folder …/app/bin        (and 11 more folders)
  ok: building from the checkout at …/repo-staging (no clone needed)
  WOULD: build the watcher (cargo build --release -p confluence-watch; …)
  WOULD: install program confluence-watch into …/app/bin
  WOULD: install the ingest (ingest.py) into …/app/core/ingest
  WOULD: install the bundled fixtures into …/app/core/fixtures
  WOULD: install the console (app.py + index.html) into …/app/console
  WOULD: write …/config/watch.conf (13 lines)
  WOULD: write …/confluence-watch.service (13 lines)
  WOULD: write …/confluence-console.service (16 lines)
  WOULD: refresh the user service manager
  WOULD: enable and start confluence-watch + confluence-console (skipped: …)
Dry run complete — nothing was changed.
exit=0
$ ls /tmp/confluence-install-proof/root
ls: cannot access …: No such file or directory     ← nothing was created
```

(The old pack's dry run could not even be rehearsed off a
provisioned Thor: its prerequisite checks `die`d before the
plan printed. Now a failed check in dry-run is a warning and
the plan always prints; `--apply` keeps them fatal.)

## Step 2 — enabling without applying is refused

```
$ CONFLUENCE_HOME=$S bash install.sh --enable-service
STOP: --enable-service needs --apply in the same run: enabling is a deliberate step taken on a completed install.
exit=1
```

## Step 3 — apply into the scratch prefix

```
$ CONFLUENCE_HOME=$S CONFLUENCE_UNIT_DIR=$S/.config/systemd/user \
  CONFLUENCE_ALLOW_UNTESTED_MACHINE=1 bash install.sh --apply
  … (machine-check WARNs as step 1, marked "rehearsal bypass")
  DO: create folder … (×12)
  ok: building from the checkout at …/repo-staging (no clone needed)
  DO: build the watcher (cargo build --release -p confluence-watch; …)
     Compiling rolling-substrate-core / harbor-watch / confluence-watch
      Finished `release` profile [optimized] target(s) in 6.33s
  DO: install program confluence-watch into …/app/bin
  DO: install the ingest (ingest.py) into …/app/core/ingest
  DO: install the bundled fixtures into …/app/core/fixtures
  DO: install the console (app.py + index.html) into …/app/console
  DO: write …/config/watch.conf
  DO: write …/confluence-watch.service
  DO: write …/confluence-console.service
  SKIP: systemctl --user daemon-reload (units were written to a
        non-default CONFLUENCE_UNIT_DIR — rehearsal layout; …)
  WOULD: enable and start … (skipped: pass --enable-service with --apply when ready)
Apply pass complete.
exit=0
```

Wart found by this run and fixed in the same pass: the first
apply copied the checkout's `__pycache__/` (bytecode from
another machine) into `app/core/ingest/`. The installer now
removes any `__pycache__` it copied; a second `--apply` (also
the idempotence check: exit 0, `KEEP: …/config/watch.conf
already exists, not overwriting`) verified the fix.

Installed layout, as written (`find` on the scratch root):
`app/bin/confluence-watch` (ELF, 753,328 bytes, executable),
`app/core/ingest/ingest.py`, `app/core/fixtures/` (README +
`patch.png` + `wave3/A-00..05.png`, `B-00..05.png`),
`app/console/{app.py,index.html}`, `config/watch.conf`,
`.config/systemd/user/{confluence-watch,confluence-console}.service`,
`ledger/{streams,items,household,attention}/`, `media/`.

The watch unit, verbatim — the real deployment's shape
(binary + `--config <file>`, working directory at the core so
the ingest's relative fixture resolution behaves as deployed):

```
[Service]
WorkingDirectory=<root>/app/core
ExecStart=<root>/app/bin/confluence-watch --config <root>/config/watch.conf
```

The console unit sets `CONSOLE_LEDGER_DIR=<root>/ledger`,
`CONSOLE_MEDIA_DIR=<root>/media`, `CONSOLE_PORT=8320` and runs
`app.py` with the detected interpreter (`python3` here, with
the step-1 warning standing: on this VM no interpreter had
fastapi+uvicorn — see step 6 for how the console was exercised
anyway).

The starter `watch.conf` is the config the binary's own parser
(`slice1/core/src/config.rs`) defines — `stream_id`,
`ledger_dir = <root>/ledger/streams/cam1`, `ingest_cmd` (shot
source; the URL is the documented site edit), `rack_url`,
`rack_autostart`, `stop_rack_on_exit`, `threshold`, `alpha`,
`focus_k`, `soak`.

## Step 4 — a rack stand-in, fenced as one

`confluence-watch` refuses to start without a healthy rack at
`rack_url` (checked, then started by the service if configured
to). There is no rack on this VM, so the run used a **test
double** (kept with this proof's scratch, not shipped): a
~60-line HTTP server answering `GET /health` 200 and
`POST /embed/image` with a 1280-dim vector that is a
deterministic function of the tile's bytes (sha256-seeded) —
identical tiles embed identically, different tiles differently.
**It is not I-JEPA.** It exercises tiling, the diff gate, the
record stream, the cascade plumbing and the ledger. It cannot
say whether a real scene change crosses the perception
threshold; that remains proven only by `slice1/core/
acceptance.sh` against the real rack on a Thor.

## Step 5 — the installed binary, run against the bundled fixtures

Config: the installed starter `watch.conf` with three edits —
`ingest_cmd` → the installed ingest, `--source staged
--truth-out <root>/run-proof/truth.json`; `rack_autostart =
false` (the double was already running); `max_frames = 18`
added. Run from `<root>/app/core`, exactly as the unit runs it:

```
$ <root>/app/bin/confluence-watch --config <root>/config/proof.conf
{"frames":18,"events":2,"embeds":34,"embeds_spent_s":0.151,
 "embed_everything_estimate_s":1.281,"verdict_latency_p50_ms":28.626,
 "verdict_latency_max_ms":374.217,"rack_started_by_me":false,
 "rack_stopped_by_me":false}
exit=0
```

The gate layer, exactly as the fixture rig's ground truth
predicts (and as `prove_fixtures.py` proves rack-free):
**18 frames in; 34 tiles nominated and embedded** = 16
(baseline) + 16 (cut) + 2 (object) + 0 (drift). The ledger the
installed service wrote (`ledger/streams/cam1/`:
`lens.txt`, `state.txt`, `events.jsonl`, `health.txt`) agrees:
`frames_seen = 18`, `tiles_nominated = 34`,
`tiles_embedded = 34`, `events_published = 2`,
`spend_ratio = 0.1181`.

The two verdicts the cascade published, against the rig's
truth (`{"cut_frame": 4, "object_frame": 7, "object_tiles":
[5, 6], "drift_frames": [10..17]}`): **frame 4, all 16 tiles;
frame 7, exactly tiles {5, 6}; nothing on any drift frame.**
That is the acceptance pattern — recorded here as a
*structural* result against test-double embeddings, not as a
perception result (see step 4's fence).

## Step 6 — the installed console, serving the installed ledger

Deps installed into a scratch venv
(`pip install fastapi uvicorn`), the installed `app.py` run
with the unit's own environment (`CONSOLE_LEDGER_DIR`,
`CONSOLE_MEDIA_DIR`, `CONSOLE_PORT=8320`):

```
GET  /            -> 200 (the household page)
GET  /api/state   -> 200: stream "cam1" present, has_data true,
                     heartbeat_age_s live (48.5 at check time),
                     stale false, coverage "1.0000"
GET  /health      -> 404 — the URL the OLD guide promised does
                     not exist; there is no health route. Health
                     is the per-stream heartbeat on the page /
                     in /api/state. Guide and card now say so.
POST /api/correct -> 200 {"ok":true,…}; the tap was appended to
                     ledger/attention/corrections.jsonl — the
                     real corrections file (the old guide pointed
                     technicians at a feed.jsonl nothing writes).
```

**Defect found by this run (not in the install pack; not fixed
here — console/ledger territory):** `/api/state` reported
`"events": 0` and an empty feed for cam1 although its
`events.jsonl` holds two verdict rows. Cause, verified in code:
the watcher writes verdict rows with a `changed_tiles` field
(`slice1/core/src/ledger.rs`); the console's feed reader
(`slice1/console/app.py`, `stream_events`) recognises `tiles`,
`line`/`summary`/`text`, or per-tile `{tile, changed}` rows —
never `changed_tiles` — so the watcher's own verdicts are
dropped from the feed. The Thor deployment's console was
exercised against wave-3-shaped rows, which is how this
slipped through. The ledger is complete and correct; health,
shelf and corrections are unaffected. INSTALL.md §7 and the
SERVICE-CARD now carry this as a known defect until the
mismatch is fixed.

## Step 7 — workspace tests

```
$ cargo test --workspace     (staging tree, after all edits)
TOTAL: 107 passed, 0 failed
```

## What this proof does not claim

- Nothing here ran on a Thor, against the real rack, or
  against a real camera. Thor + rack + camera acceptance is
  `slice1/core/acceptance.sh`'s job, on the Thor.
- The systemd enable path (`--apply --enable-service` against
  the real `~/.config/systemd/user`) was deliberately not
  exercised on this VM; the refusal without `--apply` was
  (step 2), and the unit *contents* were verified verbatim
  (step 3).
