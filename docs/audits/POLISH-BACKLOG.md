# The polish backlog — master list, 2026-11-02

Four deep audits, one merged queue. Detail lives in the audit
files; this page is the order of battle. Counts: ENGINE 18 items
(0 blocker / 4 major / 10 minor / 4 nit) · PRODUCT 33 (2 / 12 / 14
/ 5) · DOCS 48 (10 numbers + 3 links + 35 spec-debt) · OPS ~20
(1 blocker + majors) — **≈119 items**, every one carrying severity,
effort, and file:line evidence in its audit file.

- `AUDIT-ENGINE.md` — crates, clippy/fmt, APIs, tests, dead code.
- `AUDIT-PRODUCT.md` — console, install, presence, player, slices.
- `AUDIT-DOCS.md` — numbers re-verified, links, the spec-debt menu.
- `AUDIT-OPS.md` — secrets (none live), hygiene, Thor state.

## Blockers (fix before anything calls itself finished)

1. **The install pack cannot work as shipped** (PRODUCT): install.sh
   looks for a `confluence` binary the build never produces (it is
   `confluence-watch`), and its systemd unit starts
   `confluence serve --config …` — a CLI that never existed. The
   technician guide also documents surfaces no program implements
   (LAN-sweep discovery, `attention/feed.jsonl`, retention knob,
   `library.txt`/`streams.txt` readers) and points at a console
   health page (:8210/health) the console does not have (it serves
   :8320, no /health route).
2. **No licence files** (OPS): all 7 crates declare
   "MIT OR Apache-2.0", no LICENSE file exists; GitHub reports
   `license: null`. A public repo cannot ship like this. Effort S.
3. **Player readiness has no frame floor** (PRODUCT, verified in
   code): exit-0 + any segment = ready, so a 0-frame session is
   served as ready; the stall watchdog is transcode-only, so a hung
   remux/fMP4 session zombies an item forever via the reuse rule.
   — **CLOSED 2026-11-03**: player.py frame floor — ready requires
   ≥1 counted frame (exit-0 with a playlist but zero frames →
   `failed/no_frames`); a live worker with zero frames past
   FIRST_FRAME_S (default 10 s, env PLAYER_FIRST_FRAME_S) is killed
   as `failed/no_first_frame` in all modes; /play waiters are
   released with the failure. Both defects were reproduced against
   the pre-fix code first (empty-EOS → ready/0 frames; hung remux
   still `running` after a simulated hour, reuse returning the same
   session). Tests: slice2/player/test_frame_floor.py, 7 passing;
   workspace cargo suite still 107/0. Staging tree only — not
   deployed to the Thor. (The separate fMP4 verify-not-integrated
   MAJOR in AUDIT-PRODUCT remains open.)

## Majors, ranked

4. **The GPU executor's refusal cites a dead rationale** (ENGINE):
   `executor.rs` still lists the five cuda-thor blockers that the
   generic-API round closed and Thor-proved. The refusal itself is
   a choice (crossover); its stated reason is now false — repeated
   in the crate's Cargo.toml and README.
5. **Tracked bytecode in git history** (OPS): ≥10 `__pycache__/*.pyc`
   blobs are committed; .gitignore lacks the patterns; the tar-push
   route re-adds them. Stopping is S; purging history before the
   public flip is M and must be scheduled with the flip.
6. **Home LAN addressing in shipped docs** (OPS): the Thor's
   192.168.0.78 across six duplicated spec copies, the phone's IP in
   INSTALL.md, the owner's username in absolute paths in 2 files.
7. **The trust loop is open** (DOCS spec-debt #1): corrections are
   written and never read — no auto-demotion, no trust accounting.
   Panel 2/3 designed this; nothing implements it.
8. **The yield ladder is doctrine, not code** (DOCS): 0 of 4 rungs
   implemented; budgets meter but never enforce. Spec-debt 35
   items total (8 HIGH) are the next-phase menu.
9. **fmt drift** (ENGINE): 48 hunks across 4 of 7 packages, worst
   in production slice1/core (15); one fmt commit closes it, and
   nothing currently stops it returning (no CI in the repo).
10. **Test deserts** (ENGINE): harbor-watch has zero unit tests in
    all six src modules; slice1's ledger/config/service have none.
11. **cuda-thor errors are strings** (ENGINE): ~25 public fns return
    `Result<_, String>` against typed errors everywhere else.
12. **Presence runbook rot** (PRODUCT): README still exports the
    dead BRAIN_URL :8001; brain-server.sh's default model path
    disagrees with its own acceptance scripts; /hear writes no
    receipt on failure; default LEDGER_DIR is a lane scratch path.
13. **Stale headline numbers** (DOCS): RESULTS says "the player
    ships H.264 until an fMP4 path exists" (it exists, wired);
    README + READING-GUIDE say 95 tests where the same files' own
    arithmetic says 107; RESULTS' soak row quotes a snapshot that
    appears nowhere in its cited source.

## Notes for whoever works this list

- The audits verified as much clean as dirty: zero live secrets;
  substrate-core + cuda-thor still clippy/docs clean; zero
  TODO/FIXME anywhere; RESULTS' link graph has 0 dead links.
- Thor leftovers (OPS #4): a D-state gst-launch from the FMP4 runs
  holds a V4L2 session and cannot be killed from userspace; its
  parent shell is parked. Soak unaffected; noted for the next
  reboot window, not a fire.
- Staging-tree skew found by AUDIT-DOCS (CHANGELOG cites the
  findings note, absent from staging): resolved at this assembly —
  `docs/FINDINGS-CFC-JEPA-V2.md` is now in both trees.
- Nothing on this list changes the soak, which is mid-flight until
  2026-11-03 18:18 AKST. Items touching the running deployment
  wait for the verdict.

## Worked — 2026-11-02 (POLISH-FIX lane)

Cheap blockers and majors, worked the same day the backlog was
written. Verified at the end: **107 passed / 0 failed**,
`cargo clippy --workspace --all-targets` zero warnings,
`cargo fmt --all -- --check` clean.

- **Blocker 2 (licence) — FIXED.** `LICENSE` + `LICENSE-MIT` +
  `LICENSE-APACHE` at the root (Apache text verified section by
  section against apache.org's canonical copy); all 7 crates'
  `license = "MIT OR Apache-2.0"` fields checked, matching.
- **Major 5 (.gitignore half) — FIXED.** `__pycache__/`, `*.pyc`,
  `.env` added. The history scrub of the already-tracked blobs is
  **deferred to flip time by design** — reminder recorded in
  AUDIT-OPS.md's addendum.
- **Major 4 (executor rationale) — FIXED.** `GpuApiGap`/`API_GAP`
  are gone: the error is now `ExecutorError::GpuNotBuilt` carrying
  `NOT_BUILT` — the measured crossover bound (no win below ~4,096
  nodes), with the closed gaps recorded as closed. Same correction
  in executor.rs docs, the gpu-shadow tests, rolling-pipeline's
  Cargo.toml feature comment, and the README Composition section
  (the five-absences list kept, fenced as history). Feature-on
  type-check passes; the behavioural refusal is unchanged.
- **Major 9 (fmt drift) — FIXED.** `cargo fmt --all` applied
  workspace-wide; the full suite stayed green (107) afterwards,
  so no file needed backing out. The "nothing stops it returning"
  half (no CI) remains open — it is a repo-settings item, not a
  formatting one.
- **Major 13 (stale numbers) — FIXED for the cited lines.**
  README + READING-GUIDE cold-run lines: 95 → 107 tests. RESULTS:
  the fMP4 row now records the wired reality with the original
  wording kept as a dated correction; the soak row's +50 min
  snapshot is fenced as a point-in-time live-ledger read
  (2026-11-01 ≈19:08 AKST) with its real source named and the
  "0 events" supersession noted. (AUDIT-DOCS items N5–N10 were
  outside this lane's brief and remain as listed.)
- **Clippy warnings (AUDIT-ENGINE item 5) — FIXED.** All four:
  `needless_range_loop` ×2 in rolling-perception (iterator forms,
  same order/counts — checksum suite green), harbor-watch's
  `manual_pattern_char_comparison`, confluence-watch's
  `manual_flatten`. Workspace clippy is at zero; substrate-core
  and cuda-thor re-verified clean under `-D warnings`.

Not touched by this lane (still open, as listed above): blocker 1
(install pack), blocker 3 (player frame floor), majors 6–8 and
10–12, and the whole spec-debt menu.
