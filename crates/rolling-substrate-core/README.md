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

Run: `cargo test`
