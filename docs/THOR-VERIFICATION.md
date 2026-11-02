# Thor verification — 2026-11-01

> **Update note (2026-11-01, doc sweep):** this is the dated record of
> the wave-1 verification run, when the workspace had two crates and
> 29 tests. The workspace has since grown to seven members and
> **55 tests** (verified by a fresh `cargo test --workspace` run the
> same day; the Thor-native rerun of the full suite is owed — see
> `docs/ARCHITECTURE.md`). The numbers below are the run's own record
> and are left as measured.

The full Rust workspace was copied to the AGX Thor
(`~/rolling-perception-play/rust/`, a play directory, nothing installed or
left running) and tested natively on the box:

- **Toolchain:** cargo/rustc 1.99.1, aarch64-unknown-linux-gnu (Thor's own).
- **`cargo test --release`: 29/29 pass** (6 rolling-scheduler + 23 substrate-core).
- **CPU bench on the Thor's Neoverse V3AE cores** (120 cycles, 400 µs stagger):
  rolling TTFO **176.5 µs**, batched/rolling TTFO ratio **15.78×**,
  outputs ratio 5.0×, total rolling time 219.6 ms.
- **Cross-architecture determinism:** the bench checksum on Thor/aarch64 is
  `345101.1999` — bit-identical to the x86_64 development VM's checksum, and
  the batched-vs-rolling checksum delta is `0.000000` on both machines.

GPU-side results (rolling streams, NVRTC swap, persistent kernel, gating)
are in `experiments/thor-cuda/PLAYLOG.md`; platform capability probing is
in `docs/FEASIBILITY.md`.

Known cosmetic issue at this commit: cargo warns that `[profile.release]`
in the substrate-core crate is ignored under the workspace root. Harmless;
the section is removed in this repo copy.
