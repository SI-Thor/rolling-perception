# AUDIT-OPS — graduation readiness & operations (2026-11-02)

Lane AUDIT-OPS. Audit only — nothing was modified to produce this
list (this file is the deliverable). Scope: the whole repo tree
(as it will stand at the public flip), GitHub-side state, the Thor
deployment, and the local working trees. Every item carries
SEVERITY (blocker / major / minor / nit), EFFORT (S/M/L), and the
EVIDENCE it rests on.

**Headline: no live secrets exist anywhere in the tree.** The
graduation risks are a missing licence, binary junk already
committed to history, home-network details in the docs, and
operational leftovers on the Thor.

---

## 1. Secrets & privacy scan

Greps actually run over the full tree (excluding `target/`):
`sk-…`, `api[_-]?key`, `bearer`, `BEGIN .*PRIVATE`, `token`,
`secret`, `password`, `Authorization`, `.env`, credential-file
names, long base64 runs, `192.168.`, personal-mail domains,
`/home/` paths.

### OPS-S1 — No live secrets found — CLEAN (evidence, no action)
- Zero hits for key-shaped strings (`sk-`, `api_key`, bearer
  tokens, private-key blocks); no `.env` files anywhere; no
  credential files tracked.
- All `token|secret|password` hits are benign identifiers or
  prose: `BRAIN_MAX_TOKENS` (an env-tunable generation limit,
  `slice2/presence/presence.py`), a uniqueness "token" in a
  substrate doc comment, `_CAM_TOKEN` (a regex in
  `slice2/presence/claims.py`), panel/spec discussion of judge
  probabilities.
- `experiments/wave3/jev/RESULTS.md` *discusses* a rejected
  TypeSafe credential at length (routes, HTTP 401s, the remedy) —
  the credential's value never appears. Fine as-is; it is a good
  record of a blocked route.
- The Oracle's public IP (<oracle-public-ip>) appears nowhere.
- Commit identity is the agent address
  (superinstance-agent@example.com) — fine by design.

### OPS-S2 — Home-network addressing in shipped docs — MAJOR, MUST-FIX before public, effort S
- `<thor-lan-ip>` (the Thor's LAN address) in
  `docs/SPEC-STREAM-PLATFORM.md`, `slice1/install/INSTALL.md`,
  `slice1/PROART-CAMERA.md`, and the panel-2 prefix copies
  (`slice2/panel-2/_prefix.md` + all four `q*.md` — the spec text
  is duplicated six times, so one fact has six homes).
- `<lan-ip>` — a personal phone's LAN address — in
  `slice1/install/INSTALL.md` (the IP Webcam example).
- RFC1918 addresses are not routable, so the exposure is
  topology/fingerprinting, not reachability; but this is the
  owner's home network and a personal device. Replace with
  `thor.local` / placeholders before the flip.

### OPS-S3 — Personal username in absolute home paths — MINOR, MUST-FIX before public, effort S
- 4 lines, 2 files: `experiments/wave3/driver/driver.log`
  (`~/image-studio/outputs/…`, three lines of
  run log) and `docs/FEASIBILITY.md`. The username is the owner's
  real name in machine form. Redact to `~/…` in the log excerpt or
  drop the log file (its numbers are quoted in the wave-3 docs).
- Related, fine-as-is: `~/…` paths in
  `experiments/wave3/jev/*.py` are this VM's agent home, not the
  owner's; first-name "Casey" mentions throughout are the public
  persona the repo is published under.

---

## 2. Repo hygiene

### OPS-H1 — No licence files — BLOCKER for public, effort S
- Every crate declares `license = "MIT OR Apache-2.0"` (all 7
  `Cargo.toml`s), but there is **no LICENSE file anywhere** and
  GitHub reports `license: null`. The intent is recorded; the
  legal artefact a public repo needs is missing. Add
  LICENSE-MIT + LICENSE-APACHE (or a combined LICENSE) at root.

### OPS-H2 — Compiled Python bytecode is TRACKED in git — MAJOR, effort S to stop, M to purge
- `git ls-tree origin/main` shows ≥10 `__pycache__/*.pyc` blobs
  committed: `slice1/core/__pycache__/prove_fixtures…pyc`,
  `slice1/core/ingest/__pycache__/ingest…pyc`, eight under
  `slice2/presence/__pycache__/` (acceptance scripts, claims,
  piper_worker, presence, tts_bench…).
- `.gitignore` covers `/target`, `**/target`, `*.o` and the
  thor-cuda experiment binaries — but **not** `__pycache__/`,
  `*.pyc`, or `.env`. The tar-extract push route sweeps whatever
  is in the staging tree, so local bytecode rode along silently.
- Bytecode also embeds the build machine's absolute source paths
  — a small privacy echo of OPS-S3 inside binary blobs.
- Fix in two parts: add the gitignore lines + `git rm --cached`
  (S), and scrub history before the flip (M) — removing them from
  HEAD alone leaves them in the public history forever.

### OPS-H3 — Large tracked data files — MINOR, effort S–M, mostly justified
Tracked content totals ~19 MB across 247 files (GitHub repo size
7.9 MB compressed — small). Everything >1 MB:
- `experiments/wave3/driver/embeddings_ALL.jsonl` 7.7 MB +
  `embeddings_CHANGED.jsonl` 4.2 MB + `embeddings_AUDIT.jsonl`
  0.8 MB — the wave-3 evidence base. Justified as the measured
  record (RESULTS quotes them), but they are derivable artefacts;
  a stranger clones them forever. Keep-or-compress is a judgement
  call for the flip, not a defect.
- `experiments/wave3/report/report-C-real.html` 4.5 MB — carries
  the base64 frames the cold fixtures were recovered from;
  justified provenance, heavy for an HTML report.
- **Duplicate blob**: `experiments/wave3/jev/fixture.jsonl` and
  `crates/harbor-watch/fixtures/harbor-fixture-1280.jsonl` are
  the *same blob* (identical hash) tracked twice at 2.35 MB.
  One should reference the other. MINOR, effort S.
- `slice1/core/fixtures/wave3/*.png` (~370–425 KB × 12) — the
  bundled cold fixtures; justified by the reproducibility fix
  they exist for.

### OPS-H4 — GitHub-side state — MINOR/NIT, effort S
- `private: true` ✓, default branch `main` ✓, 0 open issues,
  0 open PRs ✓. CI exists (`.github/workflows/ci.yml`) ✓.
- Branch protection: the API returns 403 — the plan tier does
  not offer protection on private repos, so none exists and none
  can until the flip (or a plan change). NIT — revisit at flip.
- No `CONTRIBUTING.md`, no `SECURITY.md`, no code of conduct.
  For a technician-facing public repo, SECURITY.md (how to
  report) is the one worth having on day one. MINOR, effort S.
- The root `Cargo.lock` is 718 bytes (near-empty workspace of
  path-only crates) — correct, not a gap; noted so nobody
  "fixes" it.

### OPS-H5 — Local staging tree is not itself a git repo — MINOR, effort S
- `repo-staging/` has no `.git`; the only clone lives on the
  Oracle (`/tmp/rp-push3`, an ephemeral `/tmp`). The staging tree
  is the de-facto source of truth between pushes and exists in
  exactly one place. A named local clone (or a documented
  statement that staging is scratch and GitHub is truth) would
  remove the ambiguity. (See also OPS-L1.)

---

## 3. Thor deployment state (read-only inspection)

Project footprint: `~/confluence-play` = **308 MB** of the Thor's
936 GB disk (91% used, 82 GB free — the pressure is the box's,
not this project's: 0.04%).

### Running, intended
- `confluence-watch` PID 1049389 — the soak (see SOAK.md) ✓.
- `jev-rack.service` active — started/owned by the soak ✓.
- Push receiver PID 651692 (:8091) — soak plumbing ✓.
- No presence backend, no brain-server, no player running;
  `thor-admit status` shows **no leases held** by any project
  process (Casey's :8295/:8296 remain down, as recorded).

### OPS-T1 — Wedged transcode process + parked acceptance shell — MAJOR (ops), effort S
- PID 3465567: `gst-launch-1.0` in **D state (uninterruptible
  sleep)** since 08:34 today — the FMP4-wiring lane's run-3
  transcode regression (V4L2 decoder wedge, recorded in the
  player RESULTS). It holds a decoder session and will not die
  on SIGTERM; only a reboot or driver recovery clears D-state.
- PID 3457723: its parent `bash acceptance.sh` (player-fmp4-
  accept) still parked in Ss, waiting on the wedged child.
- Neither belongs to the soak; both are lane leftovers that the
  lane's own cleanup could not reap. Kill the parent shell; note
  the gst-launch in the verdict report as a known D-state
  resident until the next reboot — and check it isn't holding
  the encoder the serve plane promises.

### OPS-T2 — Scratch deployments left in confluence-play — MINOR, effort S
- `slice2/player-fmp4-accept/` (8.3 MB) — a full second copy of
  the player deployed for acceptance runs; superseded by the
  wired player in the repo.
- `slice1/console-test/` (3.9 MB), `slice2/app/`, `app-v2/`,
  `app-v3/` (presence test builds), `slice2/fixture-ledger*/`
  ×3, `slice2/q2/`, `q3/` (panel-era scratch), `question.wav`.
- `repo-staging/` on the Thor (2.5 MB, crates only) — Thor-build
  scratch from the GPU lanes; the lanes recorded cleaning their
  scratch, this one survived.
- `apriel/` (40 KB: download.sh + log) — the cancelled model's
  residue, deliberately kept as the lane record; fine, labelled.
- `slice3/library/` (265 MB) is **not** scratch — it is the
  backfill library itself (the product's shelf). Largest single
  project item on the box; legitimate, but worth knowing it is
  86% of the project's disk.

### OPS-T3 — SOAK.md end-state documentation — FINE, one nit
- `~/confluence-play/slice1/SOAK.md` documents the full stop
  procedure in order (STOP file → watch stops its rack; kill the
  push receiver by pid file; stop the Windows pusher), the
  health checks, and the completion time (2026-11-03 18:18
  AKST). The verdict cron exists (Tue 18:30 AKST) and reads it.
- NIT: Thor-side PIDs are stated bare (the Windows PID is
  explicitly caveated as run-scoped; the Thor ones are not) —
  after the verdict, SOAK.md should be annotated "completed"
  so a future reader doesn't treat it as a live control sheet.

---

## 4. Local working trees (this VM)

### OPS-L1 — A crowd of stale lane trees beside the staging tree — MINOR, effort S
`~/workspace/rolling-perception-work/` (~950 MB total):
- `repo-staging/` 812 MB — of which **786 MB is `target/`**
  (gitignored build output; the tree itself is 27 MB). Fine,
  but it makes every size report lie until excluded.
- Pre-staging lane work dirs whose contents were long since
  folded into the repo: `slice1/` 73 MB, `wave3/` 41 MB,
  `core/` 24 MB, `rolling/` 2.4 MB, `slice2/` 848 KB,
  `wave2/`, `slice3/`, `stream-spec/`, `plan/`, `thor-play/`,
  `thor-feasibility/` (~145 MB across eleven directories).
  Nothing marks them archival; the next builder (human or agent)
  can pick the wrong tree. Archive or delete in one pass, with a
  one-line README in the folder saying repo-staging + GitHub are
  the truth.
- `/tmp/rp-*.tgz` — one push tarball per round accumulates;
  harmless, self-cleaning on reboot. NIT.

---

## Top 5 (in the order to fix them)

1. **OPS-H1 — No licence files** (BLOCKER, S): crates declare
   MIT OR Apache-2.0; no LICENSE exists; GitHub shows
   `license: null`. A public repo without one is all-rights-
   reserved by default — the opposite of the project's intent.
2. **OPS-H2 — Tracked `.pyc` + gitignore gap** (MAJOR, S/M):
   ≥10 bytecode blobs already in history, embedding build paths;
   the push route will keep sweeping them in until `.gitignore`
   learns `__pycache__/`/`*.pyc`/`.env`, and history needs a
   scrub before the flip, not after.
3. **OPS-S2 — Home LAN addressing in docs** (MAJOR, S): the
   Thor's <thor-lan-ip> in six duplicated spec copies and the
   phone's <lan-ip> in INSTALL.md — replace with names/
   placeholders before public.
4. **OPS-T1 — Wedged gst-launch (D-state) + parked parent on
   the Thor** (MAJOR, S): a dead V4L2 session from today's
   acceptance run is still resident; clear the parent, record
   the D-state process for the next reboot, verify the encoder
   budget is unaffected.
5. **OPS-L1 / OPS-T2 — Stale trees & scratch** (MINOR, S): eleven
   superseded local lane dirs (~145 MB) and ~15 MB of Thor
   test deployments invite the next builder to work in the
   wrong place; one archive pass each side ends the ambiguity.

## Counts

- Secrets: **0 live secrets**; 0 `.env`; 0 private keys.
- Privacy MUST-FIX hits: 2 classes (LAN addresses ×8 files,
  username paths ×2 files).
- Hygiene: 1 blocker (licence), 1 major (tracked bytecode),
  3 minor (large files/duplicate blob, GitHub docs gaps,
  staging-not-a-repo).
- Thor: 3 intended processes + rack service; 2 leftover
  processes (1 unkillable); ~15 MB scratch deployments;
  project disk 308 MB.
- Local: 1 live tree (staging) + 11 stale lane dirs.

## Addendum (2026-11-02, POLISH-FIX lane)

- The `.gitignore` half of the tracked-bytecode item is fixed
  (`__pycache__/`, `*.pyc`, `.env` added). **Reminder for flip
  time: the ≥10 `__pycache__/*.pyc` blobs already in git history
  still need a history scrub before the public flip** — removing
  them at HEAD is not enough; schedule the rewrite with the flip,
  not before (the repo is private and the blobs carry only
  build-machine paths). Not attempted by the polish lane.
- The licence blocker is closed: `LICENSE`, `LICENSE-MIT`, and
  `LICENSE-APACHE` (canonical text, verified against apache.org)
  now sit at the repo root; all seven crates' `license` fields
  already read `"MIT OR Apache-2.0"` and match.
