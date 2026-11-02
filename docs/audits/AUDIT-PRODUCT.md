# Audit — product surfaces (console, install, presence, player, slice 3)

Lane AUDIT-PRODUCT, 2026-11-02. Audit only; no code changed.
Method: every slice README's claims spot-checked against the code
in the same tree; the player wart from RESULTS.md re-verified in
source. Format per item: SEVERITY · EFFORT · EVIDENCE · one line.

## slice1/console

- MAJOR · S · slice1/console/app.py:291 vs slice1/install/SERVICE-CARD.md:12,24 — console defaults to port 8320 and has no `/health` route (routes are `/`, `/api/state`, `/api/correct`, `/files`), while the install pack sends the technician to `thor.local:8210/health`, a page that does not exist on any port.
- MAJOR · S · slice1/console/app.py:260-275 — `/api/correct` records any `stream`/`event_id` strings without checking the event exists, and a malformed JSON body raises out of `await req.json()` as a bare 500; the trust-metrics feedstock is pollutable by any LAN client (the POST is also unauthenticated).
- MAJOR · S · slice1/console/README.md:22 — claims "Porch-cam behaviour in the fixture test proves the no-heartbeat case also goes amber", but slice1/console contains no test at all (only app.py, index.html, make_fixtures.py); the claimed proof is not in the repo.
- MINOR · S · slice1/console/app.py:283-289 — `/files` traversal guard is a string-prefix `startswith(root)` check, the sibling-prefix pattern (`ledger-evil` passes a `ledger` prefix); the regex-free join should be a path-component check.
- MINOR · M · slice1/console/app.py:62-78,232-249 + index.html:139 — every 5 s poll re-reads each stream's whole events.jsonl (file read fully, then sliced to the last 2000 lines) and re-globs the entire media tree; cost grows with exactly the long soaks this console exists to display.
- MINOR · S · slice1/console/index.html:100-105 — the correction button handles an HTTP error but not a network throw: a failed `fetch` leaves the button unchanged with no feedback, indistinguishable from "recorded".
- NIT · S · slice1/console/README.md:29 vs app.py:19 — the corrections feedstock is cited as SPEC §C2.2/2.5 in the README and §C2.5 in the code docstring; one of the citations is wrong.

## slice1/install

- BLOCKER · S · slice1/install/install.sh:35 — `PROGRAMS="confluence harbor-watch"`, but the core's binary is `confluence-watch` (slice1/core/Cargo.toml:13); `--apply` warns "expected build product … not found" and installs nothing for the core.
- BLOCKER · S · slice1/install/install.sh:232 — the unit runs `ExecStart=$BIN_DIR/confluence serve --config $ROOT/config`: no such binary, no `serve` subcommand, and the real CLI takes `--config <file>` (slice1/core/src/main.rs:7-13); the service as installed cannot start.
- MAJOR · M · slice1/install/INSTALL.md:166,191,219,287 + SERVICE-CARD.md:32 — [interface]-marked surfaces that still do not exist: LAN-sweep camera discovery, the console camera list + in-console camera naming, `ledger/attention/feed.jsonl` (the core writes only per-stream events.jsonl), a retention setting under `~/confluence/config/`, and `library.txt`/`streams.txt` — no program in slice1/ or slice2/ reads those two files at all (grep-verified).
- MINOR · S · slice1/install/SERVICE-CARD.md:31-33 + INSTALL.md:235 — the card points at `~/confluence/logs/` "stage receipts"; the installer creates the directory but nothing writes there (the core's receipts live in the ledger), so a technician following the card finds an empty room.
- MINOR · S · slice1/install/install.sh:172-176 — the disk-space prerequisite measures the filesystem under `$HOME`, not under `$CONFLUENCE_HOME` when the install root is overridden to another mount.
- MINOR · S · slice1/install/install.sh:132-170 — prerequisite checks `die` before the plan prints, so the advertised dry-run cannot be rehearsed anywhere except a fully-provisioned aarch64 Thor with the rack installed.
- NIT · S · slice1/install/INSTALL.md:201 — "new files … are picked up on the next scan" describes a library scan that does not exist; the console in fact re-reads the media dir on every request (harmless, but the guide's model of the system is wrong).

## slice2/presence

- MAJOR · S · slice2/presence/README.md:62 vs presence.py:86 — the README's own "Run it" block still exports `BRAIN_URL=http://127.0.0.1:8001`, the dead port v2 replaced; following the runbook overrides the code's correct 8310 default and yields a brainless presence.
- MAJOR · S · slice2/presence/brain-server.sh:29 vs acceptance_v2.py:51 — brain-server.sh defaults llama-server to `$HOME/llama.cpp/build/bin/` while the lane's own acceptance scripts use `$HOME/llama.cpp-upstream/build-up/bin/`; one of them points at nothing, the script checks neither path's existence, and it prints "starting…" even if `systemd-run` failed (no `set -e`).
- MAJOR · M · slice2/presence/presence.py:597-676 — `/hear` has no error handling: a decode, whisper-load, brain (urlopen, presence.py:404) or Piper failure propagates as a bare 500 and writes NO receipt, so the "receipts per stage" discipline breaks on exactly the calls that failed.
- MAJOR · S · slice2/presence/presence.py:84-85 — the default `LEDGER_DIR` is a lane scratch path (`~/confluence-play/slice1/run/ledger`), not the installed ledger (`~/confluence/ledger`) nor the soak's (`run-proart/ledger`); run as shipped, presence silently answers from a fixture-era directory.
- MINOR · M · slice2/presence/ (whole dir) — the shipped version is identifiable only from receipt fields (`digest: v2`, `claim_checker: v3`, presence.py:577-579); `presence.py` carries v1+v2+v3 unnamed, and `acceptance.py` vs `acceptance_v1_rerun.py` are two near-identical 177-line scripts with no marker of which is canonical (the v1 original deploys to `app/`, the rerun to `app-v2/`).
- MINOR · S · slice2/presence/presence.py:143-152 — `get_brain_model()` caches the fallback id `"default"` forever if the brain was unreachable at the first call; a transient outage at startup mislabels the brain for the process's whole life.
- NIT · S · slice2/presence/presence.py:377 — the adversarial brain-stub test hook (`PRESENCE_BRAIN_STUB_FILE`, re-read per call) ships in the production request path; documented in the header, but a set env var silently replaces the brain.

## slice2/player

- MAJOR · S · slice2/player/player.py:374 (and :331) + :258-262 — THE RECORDED WART, VERIFIED: on worker exit 0, `finish(s, "ready")` requires only `playlist_ready()` (a playlist + any `seg*.ts`); there is no frame floor, so an instantly-EOSing source with an empty segment is marked ready with 0 frames, exactly as slice2/player/RESULTS.md:186-189 records.
- MAJOR · M · slice2/player/player.py:358-366,270-271 — the stall watchdog fires only for `mode == "transcode"`; a hung remux or fMP4 worker (alive, no output) is never killed, its session stays `running` forever, and `start_session`'s reuse rule returns that zombie for every later request for the item.
- MAJOR · M · slice2/player/player.py:17 + slice2/player/acceptance.sh:127 — `verify_fmp4.py`'s 41-check validation is NOT integrated into the player: it is referenced only in player.py's docstring and run only by acceptance.sh; at runtime an fMP4 session is marked ready on exit code + playlist presence alone.
- MINOR · M · slice2/player/player.py:87,497-505 — sessions in the in-memory SESSIONS dict and their `work/<sid>/` segment dirs are never evicted, and `_shutdown` kills workers without writing registry closure rows; both grow/stale silently across a service lifetime.
- MINOR · S · slice2/player/player.py:453-465 — `GET /play/<id>` for a transcode waits for status `ready` (worker exit) before serving, up to 90 s, then 503s even though segments exist; the page works around it via /api/play, but direct playlist consumers cannot watch a long item while it generates.
- MINOR · S · slice2/player/player.py:204-208 — an unprobeable or unknown-codec item silently defaults to `h265parse` and invented 1920×1080 geometry, guaranteeing a confusing worker failure instead of a clean refusal at admission.
- NIT · S · slice2/player/fmp4_split.py + build_hls.py vs slice2/player/fmp4-spike/ (same names) — the production helpers are verbatim copies of the spike's (diff-verified identical today): two copies of the tfhd-patch logic to drift apart.

## slice3

- MAJOR · M · slice3/backfill_pass1.py:213-256 — a rerun is not clean: item ids `s3-####` are reassigned by mtime order each run and previous runs' `ledger/items/*.txt` + media hardlinks are never pruned (only same-name files are overwritten), so a second run leaves orphan shelf items the console still lists.
- MINOR · S · slice3/backfill_pass1.py:7 + slice3/BACKFILL-PASS1.md:42 — both documents still say the shelf is symlinks ("shelf media dir of symlinks", "(symlink shelf)"); the code hardlinks (os.link) precisely because symlinks failed the console's guard — the docs describe the abandoned mechanism.
- MINOR · S · slice3/backfill_pass1.py:32-40 — ROOTS, OUT and CAP are hardcoded to one Thor's `$HOME` layout with no CLI/env override; rerunnable only on that box, by that user (the docstring's "Runs ON the Thor" discloses the box, not the rigidity).
- MINOR · S · slice3/backfill_pass1.py:147-152 — poster extraction assumes even-dimension NV12 (`width*height*3//2` size gate + reshape); an odd-dimension video silently lands in posters_fail with no reason recorded in its item file.
- NIT · S · slice3/synth/run_experiment.py (766 lines) — one script holds three experiments and overwrites results.json, snap_results.json and snap2_results.json in place; it is seeded and rerunnable (verified), but re-checking one number rewrites all three artifacts with no way to run a single part.

## Claims I could NOT verify from the repo

- slice2/presence/README.md — v2's "7/7 PASS" battery and v3's "8/8 traps caught": the README says measured numbers live in the run output, but no receipts or run-output files exist in slice2/presence/. (The one checkable number, test_claims.py's 23/23, was re-run in this audit and passes; synth's "17/17" in slice3/synth/README.md:14 likewise re-verified — 17 test methods, unittest OK.)
- slice3/BACKFILL-PASS1.md — the headline numbers (13,466 files found, 234 selected, thumbnails 232/232, posters 2/2, 0 probe errors) rest on Thor-side outputs (media-index.jsonl, summary.json) that are not committed anywhere in the repo.
- slice1/install/SERVICE-CARD.md — "first picture after a rack start takes ~12 s": plausible against the rack's record, not measured by anything in this tree.
- slice1/core/README.md's numbered acceptance (staged events, soak-mode shutdown) — requires a live JEV rack; not re-verifiable from the repo alone in this audit.
- slice2/player/RESULTS.md acceptance runs — internally consistent with the code as audited, but not re-run here (Thor-side); the one claim that IS code-checkable, the 0-frame wart, checked out as written.

## Counts

- BLOCKER: 2 · MAJOR: 12 · MINOR: 14 · NIT: 5 · Total: 33

## Top 5

1. install.sh:232 — the installed systemd unit's ExecStart names a binary and CLI that never existed; the service cannot start (BLOCKER).
2. install.sh:35 — the installer looks for a `confluence` binary the build never produces, so even the copy step installs nothing for the core (BLOCKER).
3. player.py:374 — ready-with-0-frames: the serve plane can report success for an item that delivered nothing (MAJOR, wart verified in code).
4. INSTALL.md/SERVICE-CARD.md [interface] surfaces — the technician's guide describes discovery, a camera list, a feed file and a retention knob that no program implements; the guide, not the code, is what a technician will believe (MAJOR).
5. presence/README.md:62 — the presence runbook's own command line points the brain at the dead :8001, silently disabling the feature the page exists for (MAJOR).
