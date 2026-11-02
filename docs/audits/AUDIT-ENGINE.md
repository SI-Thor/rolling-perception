# AUDIT-ENGINE — deep polish audit of the engine crates (2026-11-02)

Scope: `crates/` (rolling-perception, rolling-substrate-core,
rolling-pipeline, rolling-adaptive, cuda-thor, harbor-watch) plus
`slice1/core` (confluence-watch) where it consumes the engine.
**Audit only — no code was changed.** Every item carries severity,
effort, and evidence (file:line or the command that produced it).
Method: `cargo clippy --workspace --all-targets`, per-package
`cargo fmt -- --check`, grep sweeps, a scripted pub-item/doc scan,
and hand sample-verification of every dead-code claim before it
was written down.

## Verified clean (checked, not assumed)

- **rolling-substrate-core + cuda-thor hardening holds**:
  `cargo clippy -p rolling-substrate-core -p cuda-thor
  --all-targets -- -D warnings` finishes clean; both carry
  `#![warn(missing_docs)]` (substrate lib.rs:20, cuda-thor
  lib.rs:29) with zero missing-doc warnings; both are fmt-clean.
- **Zero TODO debt**: `grep -rnE "todo!|unimplemented!|TODO|FIXME|XXX|HACK"`
  over all engine + slice1 Rust sources returns **nothing**.
- **Library unwrap surface is near zero**: substrate-core and
  rolling-perception have 0 `unwrap`/`expect` in non-test library
  code (scripted scan classifying `#[cfg(test)]` modules).

## Major

1. **MAJOR / M — The GPU executor's refusal rationale is factually
   stale.** `crates/rolling-pipeline/src/executor.rs:173` —
   `API_GAP` still asserts cuda-thor's public API "cannot express
   the sheaf stencil" for five reasons (private `nvrtc_compile`,
   hardcoded kernel name/signature, f32-only upload, one stream).
   **All five were closed** by the cuda-thor generic-API round and
   a sheaf stencil was Thor-proven through the new API
   (`crates/cuda-thor/tests/sheaf_stencil.rs`: bit-exact Laplacian
   via `compile`/`load_named`/`launch_args`/`new_stream`).
   `GpuShadowExecutor` still refuses every tick with `GpuApiGap`
   citing the dead list, and the claim is repeated in
   `crates/rolling-pipeline/Cargo.toml` (gpu-shadow feature
   comment) and `crates/rolling-pipeline/README.md:171`. Either
   fill the executor or rewrite the rationale to the true reason
   it stays unfilled (the crossover bound) — the current text
   misinforms any reader of the seam.
2. **MAJOR / S — fmt drift in 4 of 7 packages, 48 diff hunks.**
   `cargo fmt -p <pkg> -- --check`: rolling-perception 10,
   rolling-adaptive 9, harbor-watch 14, confluence-watch 15
   (e.g. `slice1/core/src/ledger.rs:190`, `harbor-watch/src/pipeline.rs:129`,
   `rolling-adaptive/src/lib.rs:149`). substrate-core,
   rolling-pipeline and cuda-thor are clean. The known
   rolling-adaptive dirtiness is confirmed and is not the worst
   offender — the production slice1/core is.
3. **MAJOR / M — Whole modules with no unit tests.**
   harbor-watch: **zero** `#[test]` in every src module
   (ablation.rs 193 ln, fixture.rs, pipeline.rs 360 ln, record.rs,
   rng.rs) — all coverage is 8 integration tests in
   `tests/harbor.rs`, so a module-level regression localises
   poorly. slice1/core: config.rs (139 ln), ledger.rs (353 ln —
   the lens/state/health text formats are the product's ledger
   contract), service.rs (274 ln) have no unit tests; only
   `tests/live.rs` (3 tests) covers the crate. cuda-thor's
   gpu.rs (1,298 ln of FFI) has no inline tests — mitigated by
   lib.rs unit tests (7), tests/properties.rs (5) and the
   Thor-gated spikes, recorded here as partial cover, not none.
4. **MAJOR / M — Error-type inconsistency: cuda-thor's whole
   public API is `Result<_, String>`.** ~25 public functions in
   `crates/cuda-thor/src/gpu.rs` (Gpu::new:188, compile:716,
   Module::load_named:804, DevBuf::upload:335, …) return string
   errors, while the rest of the workspace uses typed errors with
   `Display` + `std::error::Error` (SheafError sheaf.rs:108/122/138,
   ExecutorError executor.rs:94/112/128, ParseError record.rs:32,
   ConfigError config.rs:55). rolling-pipeline's `parse_trace`/
   `load_trace` (lib.rs:908) and confluence `service::run`
   (service.rs:87) also return `Result<_, String>`. Callers that
   need error *kinds* (the executor wrapping cuda-thor failures)
   are reduced to string matching.

## Minor

5. **MINOR / S — Clippy: 4 unique warnings in the default
   workspace run.** rolling-perception `needless_range_loop` ×2
   (lib.rs:130, lib.rs:175 — the known pair, still present);
   harbor-watch bin `manual_pattern_char_comparison`
   (main.rs:77); confluence-watch test `manual_flatten`
   (slice1/core/tests/live.rs:127). Duplicates across lib/bin/test
   targets inflate the raw count; 4 is the deduplicated truth.
6. **MINOR / S — User-input panics in the harbor-watch CLI.**
   `crates/harbor-watch/src/main.rs:89,92,98,99` — `--threshold`,
   `--alpha`, `--dim`, `--seed` are parsed with `.expect(...)`;
   a typo'd flag crashes with a panic instead of a usage error.
   Same file's file writes expect at :106,119,174. Bin-only, but
   it is the crate's front door.
7. **MINOR / S — `expect` on an empty-records edge in library
   code.** `crates/harbor-watch/src/pipeline.rs:358` —
   `run_records` expects at least one record; an empty input set
   from a caller panics rather than returning an empty output or
   a typed error.
8. **MINOR / S — `partial_cmp().unwrap()` in adaptive stats.**
   `crates/rolling-adaptive/src/lib.rs:311` (sort) and :402 —
   a NaN in the error samples panics inside `stats`/
   `percentile`. Sits oddly next to the D9 doctrine the sheaf
   step now enforces (refuse non-finite, don't propagate or
   crash); at minimum the precondition wants documenting.
9. **MINOR / S — rolling-pipeline's `rolling-perception`
   dependency is used by exactly one demo bin.**
   `crates/rolling-pipeline/Cargo.toml` declares it; the only
   reference in the package is
   `src/bin/pipeline-demo.rs:80` (`rolling_perception::percentile`).
   The library itself never uses it. Harmless, but the dep graph
   a stranger reads (docs/ARCHITECTURE.md) overstates the coupling.
10. **MINOR / M — Duplicated logic across crates.**
    SplitMix64 implemented twice (rolling-adaptive lib.rs:47–67;
    harbor-watch rng.rs:1–18, the latter adding Box–Muller);
    the workspace LCG re-implemented per test file
    (substrate tests/properties.rs:27, tests/spsc_properties.rs:30,
    cuda-thor tests/properties.rs:14, cuda-thor lib.rs:117)
    with comments admitting they copy each other; percentile
    implemented three times (rolling-perception lib.rs:270 over
    `Duration`, rolling-adaptive lib.rs:301 over `f64`,
    slice1/core ledger.rs:34); the hand-rolled "find a number in
    JSON-ish text" scrape implemented twice (harbor-watch
    main.rs:75–78; slice1/core service.rs:47–52).
11. **MINOR / S — Dead public API (verified: zero callers
    anywhere in the workspace).** `DevBuf::byte_len`
    (cuda-thor gpu.rs:363) and `PinnedBuf::byte_len`
    (gpu.rs:536) — definitions only, no reference in src, tests,
    examples, or the Thor stencil test.
12. **MINOR / S — Test-only public API.** `roi_coords`
    (substrate gating.rs:147) is called only by gating's own
    tests (:249, :257); `gated_apply` does not use it.
    `LensFile::from_text` (rolling-adaptive lib.rs:178) is called
    only by its own round-trip test (:559) — the parse half of
    the lens persistence pair has no production caller yet.
    Both may be deliberate surface for the next consumer; neither
    is marked as such.
13. **MINOR / S — Version and metadata drift.** cuda-thor is
    `0.2.0-spike` (a pre-release suffix) while every other
    package is `0.1.0`; no `rust-version`/MSRV is declared in any
    Cargo.toml; harbor-watch's Cargo.toml still carries a stale
    comment describing a "wave3 workdir layout" that no longer
    exists (its own dependency block).
14. **MINOR / M — Missing doc comments outside the hardened
    crates.** No `#![warn(missing_docs)]` anywhere except
    substrate-core/cuda-thor. Scripted scan (pub item not preceded
    by `///`, `pub mod` lines excluded): ~5 undocumented pub items
    in rolling-perception (lib.rs:94,102,254,257,264), ~6 in
    rolling-adaptive (lib.rs:52,55,101,121,301,309), ~12 in
    rolling-pipeline (stage consts lib.rs:60–68, :93,154,157,245,
    259,379,908), ~30 across harbor-watch (fixture consts,
    pipeline consts, record::parse_record:59 among them), ~23 in
    slice1/core (ledger.rs alone: 12, incl. `Ledger` itself :94).

## Nit

15. **NIT / S — Demo bins panic on bad invocation.**
    rolling-pipeline `src/bin/pipeline-demo.rs:24,25` and
    `src/bin/trace-gen.rs:17` use `expect` for CLI args and file
    IO. Acceptable for demos; inconsistent with the library's
    typed-error posture and worth one shared pattern.
16. **NIT / S — slice1/core service.rs:140** `stdout.take().expect("piped stdout")`
    in production code — structurally safe (the child is spawned
    piped three lines earlier) but the invariant is not written
    at the site, unlike the hardened crates' discipline.
17. **NIT / S — `pub mod` declarations carry no module docs** in
    harbor-watch (lib.rs:31–35) and slice1/core (lib.rs:22–25);
    the module-level `//!` docs inside the files themselves are
    good, so this is purely the index page a doc reader lands on.
18. **NIT / M — No workspace-level lint policy.** The root
    Cargo.toml has no `[workspace.lints]`; each crate's hygiene
    (clippy clean, missing_docs) is convention, not enforcement —
    which is how items 2, 5 and 14 accumulated.

## Counts

- Blocker: **0**
- Major: **4** (items 1–4)
- Minor: **10** (items 5–14)
- Nit: **4** (items 15–18)
- Total list items: **18**

## Fix first (top 5)

1. **Item 1 — the stale API_GAP.** The repo's core rule is that
   its documents don't claim what measurement refuted; right now
   *code* does. Cheapest truth-fix in the audit and the one a
   stranger building on the executor seam will hit first.
2. **Item 2 — one `cargo fmt --all` commit.** 48 hunks is pure
   noise in every future diff until it's done; S effort, and it
   makes item 18's enforcement possible.
3. **Item 4 — a typed `GpuError` for cuda-thor.** Every other
   crate already paid this cost; cuda-thor is now a dependency
   of the pipeline, so its string errors leak into everyone
   else's error design.
4. **Item 3 — unit tests for harbor-watch's modules and
   slice1/core's ledger.** The ledger text formats are the
   product's contract with its own future readers; today nothing
   pins them below the integration level.
5. **Item 5 — the 4 clippy warnings.** Ten minutes of work that
   takes the default `cargo clippy --workspace --all-targets`
   output to zero and keeps "warning-free" a checkable claim
   instead of an aspiration.
