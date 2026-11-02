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
   <thor-lan-ip> across six duplicated spec copies, the phone's IP in
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
