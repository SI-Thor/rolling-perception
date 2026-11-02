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

## The generic kernel surface (2026-11-01, night)

Beyond the spikes, the GPU module now carries the five additions
rolling-pipeline's executor seam specified (its README's
Composition section; ARCHITECTURE claim D13): public
`gpu::compile` over the NVRTC path, `Module::load_named` for
arbitrary kernel names, `Module::launch_args` taking typed
`KernelArg` descriptors (encoding + launch-shape validation live
in the lib, outside the feature gate, and are unit-tested
anywhere), byte-level `DevBuf::upload_bytes` + async downloads,
and `Gpu::new_stream` — an RAII second stream for the two-stream
shadow. `tests/sheaf_stencil.rs` proves the surface end to end on
the Thor: an f64 sheaf stencil (Laplacian apply + smooth step)
compiled, loaded by name, launched on the second stream and
compared against the CPU rule — Laplacian bit-exact, smooth step
max err 1.388e-17 against a stated 1e-9 tolerance. Safety
discipline and the full record: HARDENING.md, final section.

## Run it (on the Thor)

```sh
export PATH=$HOME/.cargo/bin:/usr/local/cuda/bin:$PATH
cargo test  # CPU parts, anywhere: 12 tests (7 unit + 5 randomised
            # property tests in tests/properties.rs); see HARDENING.md
cargo test --release --features cuda-thor -- --ignored --nocapture  # GPU spikes + stencil proof
cargo run  --release --features cuda-thor --bin spikes              # the spikes, as a report
```

Measured results: see `results/thor/2026-11-01-spike1-3.txt` at the
repository root (captured on the Thor, 2026-11-01).
