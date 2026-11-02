# cuda-thor — v0.2 Spikes 1 + 3 (Thor-only)

Part of [SI-Thor/rolling-perception](https://github.com/SI-Thor/rolling-perception)
(private). Implements PLAN §6 spikes 1 and 3 for the AGX Thor.

**Thor-only, feature-gated.** The `cuda-thor` cargo feature is **off by
default**: without it the crate is pure CPU reference code (the
perceive-filter and its CPU implementation) and builds/tests on any
machine. With it, `build.rs` links `libcuda` + `libnvrtc` from the CUDA
13.2 / JetPack layout and the GPU code compiles. There is no cudarc —
thin direct FFI only (FEASIBILITY §6: raw FFI is the lower-risk route on
CUDA 13.2 / sm_110).

## Spike 1 — NVRTC correctness

Compiles the perceive filter (3-tap, variant A) at runtime via NVRTC with
`-arch=compute_110`, loads the PTX through the driver API, launches it,
and compares against the CPU reference in the same crate (stated
tolerance: max abs err ≤ 1e-5; the observed error is reported).
Known-wrong controls, run and recorded, not assumed:

- PTX compiled for `compute_100` (the seed email's sm_100 family, virtual
  arch) — load + run outcome recorded.
- Native CUBIN compiled for `sm_100` — load outcome recorded.

## Spike 3 — module swap with epoch retirement

1,000 host-side module swaps at launch boundaries, alternating variants
A/B (outputs differ materially, so a stale module is caught, not
tolerated). Modules are pre-compiled once as native `sm_110` CUBINs —
spike 3 tests the swap machinery, not the compiler, and a PTX load would
re-JIT on every swap and swamp the measurement. Each epoch: load module →
4 launches on one stream → record event → async copy-back → verify
against the CPU reference for that variant. A retired module is unloaded
**only after** its epoch event has synchronised; the data structure makes
the reverse order unrepresentable. `cuMemGetInfo` is sampled before and
after (all modules unloaded): the structural gate is loads == unloads
== 1000; the test additionally asserts the free-memory delta stays
above −384 MiB — a wide backstop, because cuMemGetInfo pool noise on
the shared Thor swings ~±150 MB (see the comment in
`tests/spikes.rs`).

## Run it (on the Thor)

```sh
export PATH=$HOME/.cargo/bin:/usr/local/cuda/bin:$PATH
cargo test  # CPU parts, anywhere: 8 tests (3 unit + 5 randomised
            # property tests in tests/properties.rs); see HARDENING.md
cargo test --release --features cuda-thor -- --ignored --nocapture  # GPU spikes
cargo run  --release --features cuda-thor --bin spikes              # same, as a report
```

Measured results: see `results/thor/2026-11-01-spike1-3.txt` at the
repository root (captured on the Thor, 2026-11-01).
