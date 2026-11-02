# QUICKSTART-TEST — literal follow-through, on the Thor

> **Update note (2026-11-01, doc sweep; corrected in the
> rehearsal pass the same night):** dated pass record. The
> "29 tests" figures below describe the workspace as it stood
> during this pass; it has since grown to **95 tests** across
> seven members, and slices 1–3 have landed. This document
> remains the record of the wave-2 engine quickstart only —
> the current front door is the README's Quickstart, re-verified
> cold on a fresh clone in `slice1/install/REHEARSAL-LOG.md`.

Method: the repo (staging tree = commit `d528ba5` content) was copied
to the Thor at `~/rolling-perception-play/quickstart-test/` and a
stranger pass followed **only** what the docs in that tree actually
say, in a fresh non-login SSH shell (the way fleet access works).
Every failure was logged, the docs were fixed in
`wave2/polish/edited-docs/`, and a second pass
(`quickstart-test2/`, edited docs applied) followed the new
Quickstart literally, start to finish.

## Pass 1 — failures found (9)

| # | Failure | Evidence |
|---|---|---|
| F1 | **Top-level README has no Quickstart at all** — claims table + layout, but no prerequisites, build, test, or run commands. A stranger has no door in. *(Worst.)* | Reading the README end-to-end; nothing to execute |
| F2 | **`cargo` is not on the Thor's non-login SSH PATH** — the docs' first command fails immediately, and no doc at any entry point says so. Only clue: a table cell buried in `docs/FEASIBILITY.md` line 17. | `which cargo` → exit 1; `cargo test` → `command not found`, exit 127 |
| F3 | **`nvcc` also off-PATH**, same failure shape for the CUDA side. | `which nvcc` → exit 1 |
| F4 | **Command scope is ambiguous.** `cargo test` = 29 tests at the root, 6 inside `crates/rolling-perception/`, 23 inside `crates/rolling-substrate-core/`; the crate READMEs never state a working directory, and `docs/THOR-VERIFICATION.md`'s "29/29" is unreachable from a crate folder with no explanation. `cargo run` at the root is never mentioned (it does pick the only binary — a stranger can't know that). | Pass-1 transcript P1-6…P1-9 |
| F5 | **Cargo warning + stale doc note.** Root runs emit `profiles for the non root package will be ignored`, from `[profile.release]` in `crates/rolling-perception/Cargo.toml` (opt-level 3 / debug=false — both defaults, so the section does nothing but warn). `THOR-VERIFICATION.md` says the warning came from substrate-core and was removed — it wasn't, fully. | P1-7; `grep profile` on both crate manifests |
| F6 | **No expected output anywhere.** Neither README shows a sample bench result or the invariant checksum (`345101.1999`, delta `0.000000`), so a stranger cannot tell a correct run from a broken one. | Reading both READMEs |
| F7 | **Experiments have no build commands at all.** No `nvcc` line, no `-arch=sm_110` requirement, in the top README or PLAYLOG. (A guessed no-arch build happened to work via PTX JIT — luck, not documentation.) | P1-10 |
| F8 | **exp2's link flags are undocumented**: `-lnvrtc -lcuda` appears nowhere as an instruction (only inside a FEASIBILITY sentence about a different probe). `exp1b` / `exp4b` variant files are explained in no index — a stranger can't tell `exp4b` is the headline 192× version without reading source comments. | `grep -rn lnvrtc` across docs; P1-11 |
| F9 | **No safety/expectation note for exp3**: a persistent kernel that spins by design, with no statement that it serves 300 requests and stops itself, nor a `timeout` guard suggestion. Also no prerequisites section anywhere (Rust edition/stable? CUDA 13.2 + sm_110 for experiments only?). | P1-12; reading PLAYLOG |

## Fixes (in `edited-docs/`)

- **`edited-docs/README.md`** — added Prerequisites (Rust stable/2021,
  std-only; CUDA 13.2 + sm_110 for experiments only) and a tested
  Quickstart: the Thor PATH export first, root commands with expected
  results (29 tests; checksum `345101.1999`; delta `0.000000`; TTFO
  ratio given as a range, since it is machine/load-dependent), the
  scope table (root vs crate folders, `-p` flag), and a per-experiment
  build table with exact `nvcc` lines — including exp2's `-lnvrtc
  -lcuda`, exp1b/exp4b explained, and exp3's self-termination +
  `timeout 60` guard.
- **`edited-docs/crates/rolling-perception/README.md`** — "Run it" now
  states its directory (or `-p` from root), the PATH note, test scope
  (6 here / 29 at root), and an expected-output block with the
  invariants a correct run must show.
- **`edited-docs/crates/rolling-substrate-core/README.md`** — same
  treatment: directory, PATH note, 23-here/29-at-root scope, and a
  note that it is a library whose tests are the demonstration.
- **`edited-docs/crates/rolling-perception/Cargo.toml.fixed`** — the
  ignored `[profile.release]` removed with an explanatory comment
  (F5); profiles belong in the workspace-root manifest.

Self-caught during Pass 2 staging: the first edited Quickstart draft
put exp3's *run* command before its *build* command (build was a
trailing comment) — a literal reader would have hit "no such file".
Fixed to a single build-then-run line before Pass 2 ran.

## Pass 2 — literal follow-through of the fixed docs: PASS

Fresh copy + edited docs, fresh SSH shell, Quickstart followed in
order, nothing improvised:

- `cargo test --release` at root: **29/29 pass, and the profile
  warning is gone**.
- Bench: TTFO ratio **6.33×** this run, outputs 5.0×, checksum
  `345101.1999`, delta `0.000000` — invariants exactly as documented
  (ratio varies with box load, as the fixed docs now say).
- All six CUDA experiments built and ran from the documented lines:
  exp1 staircase (first output 5.42 ms, 3.8×), exp1b (3.9×), exp2 swap
  MATCH (out 12.0), exp3 300 requests served, buffer 1659.0 MATCH,
  clean stop (mean ack 8.4 µs this run vs 4.8 µs in PLAYLOG — the box
  was loaded; PLAYLOG number stands as the quiet-box record), exp4
  CLEAN (1.8× this run), exp4b CLEAN (78× this run vs 192× quiet —
  again load variance, direction and cleanliness invariant).
- Afterwards: GPU utilisation back to **0%** — nothing left resident,
  per the FEASIBILITY rule (explicitly started/stopped, small footprint).

Copies on the Thor: `quickstart-test/` (original docs, Pass 1) and
`quickstart-test2/` (fixed docs, Pass 2), both under
`~/rolling-perception-play/`. Nothing was pushed to GitHub; the repo
remains private and untouched by this lane.
