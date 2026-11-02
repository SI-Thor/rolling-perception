# Hardening record — cuda-thor (CPU side)

Audit → fix → prove pass, 2026-11-01. Scope: the CPU-side code of
this crate — `src/lib.rs` in full and the non-spike half of
`src/gpu.rs`, plus the unsafe surface of the spikes. The GPU spike
tests stay feature-gated and `#[ignore]`d exactly as before; nothing
here changes what runs on the Thor. Pre-fix references are
file:line in the pre-hardening tree where a tool reported them,
otherwise file + function + the pre-fix snippet.

End state: 8 CPU tests (3 unit + 5 property in
`tests/properties.rs`), `cargo clippy --all-targets -- -D warnings`
clean **in both feature configurations** (it was not before — see
item 9), `cargo fmt` applied, `#![warn(missing_docs)]` on with zero
warnings in both configurations (52 warnings cleared by documenting
the public API, including the feature-gated GPU surface and both
report structs field by field).

## Fixed

1. **Out-of-bounds host read behind a safe signature — the worst
   bug of the pass.** `src/gpu.rs`, `DevBuf::upload`. Pre-fix, the
   length check was `debug_assert_eq!(data.len(), self.n)` only.
   In a *release* build a short slice passed silently and
   `cuMemcpyHtoD` copied the buffer's full byte count out of a
   smaller host allocation. Fixed: a hard checked comparison
   (`checked_mul` on the element size) returning `Err` on mismatch.
   All in-repo callers pass exact-length slices by construction, so
   nothing that ran on the Thor was affected — but the function was
   one future caller away from it.
2. **Unvalidated kernel extent** — `src/gpu.rs`, `Module::launch`.
   Pre-fix, any `n` was accepted: a negative `n` wrapped through the
   `as u32` grid math, and an oversized `n` would have the kernel
   write past the output allocation on-device. Fixed with runtime
   validation before launch: `n > 0` and `4n` bytes must fit *both*
   buffers, else `Err`. (The kernel's own `i >= n` guard does not
   save the launch configuration.)
3. **Safe functions dereferencing raw handles** — `Event::record`
   (pre-fix gpu.rs:259) and `Module::launch` (pre-fix gpu.rs:429)
   were `pub` safe functions whose bodies dereference a
   caller-supplied `CUstream`. Clippy's `not_unsafe_ptr_arg_deref`
   is deny-by-default for a reason: the validity of the stream (and,
   for `launch`, that the module outlives the launched work) is a
   caller obligation, not something the callee can check. Both are
   now `pub unsafe fn` with `# Safety` contracts; every in-crate
   call site is wrapped with a `// SAFETY:` comment stating why it
   holds. No downstream crate calls either function.
4. **Leaked context retain on an error path** — `Gpu::new`. If
   `cuCtxSetCurrent` failed after `cuDevicePrimaryCtxRetain`
   succeeded, the retain was never released (the stream-create path
   below it already released correctly — this branch was simply
   missed). Fixed: the retain is released before returning the
   error. Process-lifetime leak, but a wrong one.
5. **Panics on string construction in library code** — four
   `CString::new(…).unwrap()` sites (pre-fix gpu.rs:285–287 in
   `nvrtc_compile`, gpu.rs:381 in `Module::load`) now go through a
   private `cstring()` helper that returns `Err`. The inputs were
   crate literals (provably NUL-free), so these could not fire as
   written — but a library returns errors; it does not keep panic
   paths warm for the next editor.
6. **Silent unwraps in spike 3's retirement path** — pre-fix
   gpu.rs:667 and 676, `epoch.module.unwrap()`. The invariant is
   structural (an epoch's module is `Some` from push until the
   retirement that consumes it), and it is now stated in
   `expect("epoch holds its module from push to retirement")`
   instead of being left implicit.
7. **A doc that described behaviour the code doesn't have** —
   `src/lib.rs`, `max_abs_err`. The old doc claimed the function
   returns +∞ for unequal lengths ("0 if lengths differ but the
   shared prefix agrees…"). It does neither: it `zip`s, comparing
   only the common prefix. The doc now says exactly that, and a
   `debug_assert_eq!` on the lengths pins the equal-length contract
   in debug builds (every real caller passes equal lengths by
   construction). CPU-side only; spike numbers unaffected.
8. **Unguarded unsafe blocks** — roughly thirty `unsafe` blocks in
   `gpu.rs` carried no `// SAFETY:` comment; the module doc even
   described a `Swapper`/`retire_oldest` structure that does not
   exist in the code. Every block now carries a SAFETY comment
   stating the invariant it relies on (live handles, sizes taken
   from driver-reported lengths, out-params at live locals,
   exactly-once destroy/unload on each path), and the module doc
   describes the code as it is.

## Fenced (kept, contract written)

9. **The crate did not pass its own hygiene gate.** Before this
   pass, `cargo clippy --features cuda-thor --all-targets --
   -D warnings` failed on pre-existing lints: `manual_div_ceil`
   (gpu.rs:421) and the two deny-level items in (3). All fixed in
   the code (the grid computation is now `(n as u32).div_ceil(256)`),
   none by blanket allows.
10. **`PinnedBuf::as_f32_slice`** — a safe function over
    `from_raw_parts`. Its soundness rests on three facts, now
    written as a SAFETY comment at the site and an aliasing caveat
    on the method doc: the allocation is live for `&self`'s
    lifetime, host-pinned allocations are aligned for fundamental
    types, and the length is the allocation's byte size floored to
    whole `f32`s.
11. **`Module` deliberately has no `Drop`** — unload is an explicit,
    error-returning act because spike 3's retirement rule needs to
    know when it happened. A forgotten unload leaks device memory
    until context teardown; that trade is now documented on the
    struct, and spike 3's `cuMemGetInfo` accounting is the tripwire.
12. **`spike3`'s `free_after as i64 - free_before as i64`** — casts
    classified provably safe in situ (device memory sizes are far
    below `i64::MAX`); left unchanged.
13. **`test_input`'s wrapping LCG** — intentional and already
    documented; the property tests pin its determinism, prefix
    property, and `[-1, 1)` range so the fixture the GPU verdicts
    rest on cannot drift silently.

## Property tests added (`tests/properties.rs`)

Std-only, seeded LCG from the crate's own constants; seeds in every
assertion message.

- `reference_a`/`reference_b` vs naive f64 stencils written directly
  from the kernel text (sizes 0, 1, 2, 3, 17, 256, and random ≤ 4000).
- `reference()` dispatch agrees exactly with the direct functions.
- The two variants stay measurably different on random inputs —
  spike 3's stale-module detection rests on this.
- `max_abs_err`: zero on identical inputs, symmetric, constant-offset
  exact, triangle bound.
