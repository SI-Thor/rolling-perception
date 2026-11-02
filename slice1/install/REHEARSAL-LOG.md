# REHEARSAL LOG — the stranger's pass, 2026-11-01 (night)

Method: a **fresh clone of the repo as it stands on GitHub**
(main@1fa1d8b) — not the staging tree — walked on a plain dev VM
(x86_64, no GPU, no Thor, no rack) following **only** the front
door: README → `docs/READING-GUIDE.md` → the Quickstart, every
command run as written, in order. A *stumble* is anywhere the doc
and the territory disagree, however small. Fixes were applied to
the staging tree's front-door docs (README, READING-GUIDE,
QUICKSTART-TEST) and each corrected instruction re-run; code was
**not** touched — code-level stumbles are logged with reproductions
for the owning lane.

## What the stranger ran, and what happened

| Step (as written) | Result |
|---|---|
| `export PATH=$HOME/.cargo/bin:/usr/local/cuda/bin:$PATH` | Harmless on a desktop; framed as a Thor-SSH fix (see S7) |
| `cargo test --release` at the clone root | **95 passed, 0 failed** — the headline number and its per-crate arithmetic (6+47+13+6+12+8+3) are exact; zero cargo warnings on a cold build |
| `cargo run --release -p rolling-perception -- --cycles 120 --stagger-us 400` | Checksum **345101.1999** both schedulers, delta **0.000000**, ratio 9.91× — inside the documented 3–16× range (wording stumble S4) |
| CUDA experiments block | Correctly scoped Thor-only in the README; all six `.cu` filenames match the commands verbatim. Not run here (no nvcc on this VM) |
| Every path the README + guide point at (25 checked) | All exist in the clone |

## Stumbles

| # | Stumble | Severity | Disposition |
|---|---|---|---|
| S1 | **The cold path is invisible.** The one run-anywhere demonstration of the whole perception cascade — `harbor_watch::fixture` (generated embedding records) driving the harbor-watch tests and the `confluence-watch` live-service tests — is named **nowhere** at the front door. A stranger who wants to *see it work* without a Thor finds only pointers to Thor-and-rack material. | Worst | **Fixed** (docs): README status section + guide stop 1 now surface the cold run |
| S2 | **Slice-1 acceptance is not reproducible from the repo.** `slice1/core/ingest/ingest.py`'s `wave3` source (and therefore `staged`, which composites wave-3 frames) reads hardcoded paths in the original author's home directory: `~/image-studio/outputs/burst_1792818193_b512cd_f*.png` and `~/sitka-distill/showcase/dock-turntable.webp`. The repo contains **zero** image files, and `slice1/core/README.md`'s Acceptance section never discloses that its steps 2–4 need Thor-local frames plus the live rack. Reproduction: fresh clone → `grep -rn "image-studio" slice1/core/ingest/ingest.py`; `find . -name "*.png" -o -name "*.jpg"` → empty. | Worst | **Logged, not fixed** (code is outside this lane). Suggested one-line disclosure for the core README's Acceptance header: *"Steps 2–4 run on the Thor against frame files that live outside this repo (see ingest.py's wave3 source); the repo-only cold equivalent is the fixture-driven test suite (`cargo test`)."* |
| S3 | **QUICKSTART-TEST misleads the current stranger.** The README sends readers to "QUICKSTART-TEST notes" with no path; the document is a wave-2 pass record over a 29-test tree (commit d528ba5), and its update note claims the workspace "has since grown to **55 tests**" — wrong by 40 (it is 95), and silent about slices 1–3, which postdate it entirely. | Worst | **Fixed** (docs): note corrected to 95 + scope stated; README now gives the path and the dated-record caveat |
| S4 | README bench expectation says "two lines (batched, rolling)"; the program prints **two passes** (measured + reported), two lines each, then three summary lines. Every invariant is exact — only the shape description is off. | Small | **Fixed** (docs) |
| S5 | The README's first screen ("Where this stands") contains no hands-on pointer at all; the Quickstart sits below two sections of prose. This is panel round 3 Q4's exact complaint, still true after the round-2/3 pushes. | Medium | **Fixed** (docs): "Run it cold" block added to the status section |
| S6 | The Reading Guide is a map of things to *read*; no stop tells a newcomer what to *run*. Stop 4 also omits panel round 3 entirely, though its raws and synthesis are in the repo. | Medium | **Fixed** (docs): stop 1 gains the run-alongside lines; stop 4 gains round 3 |
| S7 | The Quickstart's PATH-export framing ("On the Thor over SSH…") undersells that the whole Rust half is machine-agnostic — the Prerequisites say it, the door doesn't. A desktop stranger can hesitate over whether the section applies to them. It does: this entire pass ran on a desktop-class VM. | Small | **Fixed** (docs): Quickstart header now says so and points here |

Counts: **7 stumbles found, 6 fixed in docs, 1 logged with reproduction**
(S2, code-owned). Verified-good, for the record: the 95-test
arithmetic, the bench invariants, the absence of build warnings,
all 25 front-door path references, all six CUDA filenames.

## Appendix — the clean-machine checklist (the real rehearsal)

The exact sequence a technician would run on a **fresh Thor-class
box**. Status: **awaiting an actual clean box** — the Orin is the
candidate machine and using it is Casey's call. Nothing in this
appendix was executed on the Orin or the Thor by this lane; steps
1–4's repo half is pre-verified by the dev-VM pass above, the rest
is assembled from `slice1/install/INSTALL.md` §§1–3, the
SERVICE-CARD, and this repo's measured records.

1. **Machine checks** (INSTALL.md §2): `uname -m` → `aarch64`;
   `nvidia-smi` names the NVIDIA Thor GPU; ≥ 50 GB free disk;
   box on the home LAN with a login (+ sudo for rack control).
2. **Toolchain**: Rust stable via rustup; CUDA 13.2 present
   (JetPack); then the PATH export from the README Quickstart —
   on a fresh box over SSH, `cargo`/`nvcc` are not on PATH until
   this line runs.
3. **Get the code**: clone the repo (public URL after graduation;
   until then, an authenticated `gh repo clone SI-Thor/rolling-perception`).
4. **Cold verification** (must pass before anything is installed):
   `cargo test --release` → **95 passed, 0 failed**;
   `cargo run --release -p rolling-perception -- --cycles 120 --stagger-us 400`
   → checksum `345101.1999`, delta `0.000000`.
5. **Embedding rack**: confirm the JEV rack is installed and note
   its state (`systemctl is-active jev-rack`). Slice 1's live
   path needs it for embeds; the installer never starts it —
   service control is per the SERVICE-CARD.
6. **Install, dry-run first**: `slice1/install/install.sh` with no
   flags prints the plan and changes nothing. Only then
   `--apply`; enabling the service additionally requires
   `--apply --enable-service` together (the script refuses
   anything less, by design).
7. **First stream**: a phone (IP Webcam-style app) `shot` source,
   or an outbound-push camera of the ProArt kind. Then calibrate
   the gate on a still window: the live bar from the first hookup
   is **zero steady-state nominations** on an empty scene.
8. **Household surface**: open the console (port 8210, marked
   [interface] in the install docs) and check `health.txt` in the
   stream's ledger — `silence_meaningful` must read true before
   silence is allowed to mean "all is well".
9. **Known gaps a clean box will hit today** (honest list, from
   this log + the benches): the slice-1 staged/wave3 acceptance
   needs frame files that are not in the repo (S2 above);
   presence needs a local chat model on disk — a clean box has
   none until one is fetched (the BRAIN-BENCH winner is the
   default); the historical `:8001` brain endpoint is not part of
   a fresh install and nothing should expect it.
