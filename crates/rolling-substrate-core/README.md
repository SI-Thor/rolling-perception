# rolling-substrate-core

Honest, dependency-free (std-only) Rust for the salvageable parts of the
"Rolling perception" email: `substrate` (Disruptor-style 64-byte-aligned
ring), `lineage` (bitmask + counts replacing PIR prime-product, with the
PIR failure demonstrated in a test), `sheaf` (real graph-Laplacian
smoothing: energy `sᵀLs`, gradient step, energy strictly decreases),
`gating` (ROI/FluidAttn with exact skip counts).

Not implemented, deliberately: CascadeJIT/CudaClaw/NVRTC/CUPTI and
SkaldAudio DMA — those need a CUDA/Thor lane and the email's versions
were mocks. See `src/lib.rs` for the claim-by-claim table.

## Run it

From **this crate's directory** (`crates/rolling-substrate-core/`):

```sh
cargo test   # 32 tests, this crate only (27 unit + 5 randomised property
             # tests in tests/properties.rs)
             # (from the repository root, cargo test runs the whole
             # workspace suite — 75 tests at the time of the 2026-11-01
             # hardening pass; see HARDENING.md)
```

On the Thor over SSH, first:
`export PATH=$HOME/.cargo/bin:/usr/local/cuda/bin:$PATH`
(cargo is not on the default PATH there).

There is no binary in this crate — it is a library. The tests are the
demonstration: ring claim/publish across laps, multi-producer claim
uniqueness, Laplacian energy strictly decreasing on inconsistent
input, the PIR wrap false-positive shown as a counterexample, and
gating skip counts checked exactly.
