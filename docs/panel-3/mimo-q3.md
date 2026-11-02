# Hot-path allocation policy — rolling-perception / Confluence

**Scope.** All seven workspace crates. Std-only: no allocation-tracking crate, no lint crate, no new dependency of any kind for enforcement. The policy's unit of account is the **call** (allocations per invocation) and the **tick** (bytes per tick), because those are the units the pipeline's contracts already speak in.

## 1. Tiers, budgets, and the boundary rule

**What is hot?** A function is hot iff it lives in a file listed in the manifest `docs/HOTPATH.md`, and the manifest is closed: a function in a manifest file may only call (a) another manifest function, (b) a function whose file carries an `// ALLOC-FREE` marker with a passing zero-alloc test, or (c) std primitives on the caller's own stack/scratch. The manifest names files, not functions, because file membership is checkable by grep and function membership is not.

**Reviewer's boundary rule (no judgement calls):** *does this line execute once per item, frame, tile, window, or sample?* If yes → tier H0/H1. If it executes once per tick, job, request, or user action → tier H1/H2. When the call site is ambiguous, the manifest decides; if the file isn't in the manifest, the rules don't apply and the change is free.

**The syntactic allocation list** (std Rust makes allocation a lexical property — this is the no-judgement-call list a reviewer applies to a diff):
`vec!`, `Vec::new/with_capacity`, `String::new`, `format!`, `to_vec`, `to_owned`, `to_string`, `.collect()`, `Box::new`, `HashMap/BTreeMap/HashSet/BTreeSet::new` (and any insert), `Rc/Arc::clone` into a new owner, `read_to_string/read_to_end`, `str::split` collect, `println!/eprintln!/write!` to a `String`, `sort` on an owned collection, `?` on any IO. Anything matching is an allocation. Anything else is not.

**Tier H0 — banned outright in hot paths.** Any of the above. Also banned: file IO, syscalls, locking a mutex, and `unsafe` allocation bypassing the global allocator. Hot functions take **caller-provided scratch** (`&mut [f64]`) and return nothing owned. This is a signature convention the compiler cannot enforce but review can: a hot function returning `Vec<T>` is a policy violation before it compiles.

**Tier H1 — allowed against explicit budget.** Per-*tick* (not per-item) work: one scratch buffer per stage per tick, a bounded log line, a single ledger write. Budget unit: **≤ 1 allocation and ≤ 4 KiB per call, declared per function in the manifest** (`allocs=1 bytes=4096`). A budget > 0 is an exception, not a default (see §3).

**Tier H2 — unrestricted.** Cold paths: ingest startup, config parse, ledger/service lifecycle, backfill job setup, console rendering, anything outside the per-item loop. The manifest marks these files `cold`.

## 2. Enforcement at commit time — exact mechanisms, and honesty

**a. Counting allocator (std-only, the load-bearing gate).** A `#[cfg(test)]` wrapper implementing `std::alloc::GlobalAlloc` around `System`, with atomic counters for allocation count and bytes. Pure std, no dependency. A test per hot function: `let a = allocs(); f(&mut scratch); assert_eq!(allocs(), a);` — or `assert!(allocs() - a <= budget)`. **This catches THIS bug deterministically on the introducing commit**, because `laplacian_apply`'s `vec![…]` goes through the global allocator and the counter moves. The gate only works if the test exists and CI runs it, so the policy's closure rule (§4) makes the test mandatory in the same commit as the function.

*Caveats, stated:* the counter is process-global, so alloc tests live in a dedicated test binary run with `--test-threads=1`; it counts allocations routed through `System` (all of std's), not stack growth or a pre-reserved `Vec` reused across calls (which is the fix, not the bug); it cannot see an allocation inside a library the workspace doesn't own — irrelevant here, all deps are path deps.

**b. CI grep gate.** A step in the existing `.github/workflows/ci.yml` (the audit, P14, records that this gate was *missing*): `grep -nE 'vec!|Vec::|String::|format!|to_vec|to_owned|\.collect\(|Box::new|println!|eprintln!'` over every file in the manifest, failing on any hit not preceded by an `// ALLOC-OK <budget>` waiver comment. **This catches THIS bug** (the literal `vec!`/`Vec::new` in `sheaf.rs`) — but only the literal form. An allocation behind a helper call, inside `std` internals, or spelled `self.buf.resize(…)` escapes grep entirely. Grep is a coarse gate: it catches the common case, not the general one. It cannot tell hot from cold, which is why it runs only on manifest files.

**c. Debug-build assertion.** `debug_assert_eq!(ALLOC.load(Ordering::Relaxed), snapshot)` inside the hot function under `cfg(debug_assertions)`. Deterministic in debug/test runs; catches transitive allocations grep misses (a `format!` in a callee) because the counter is global. Nothing in release builds.

**d. Compiler.** Contributes **nothing**. Std Rust permits allocation anywhere; `no_std` would forbid it but the workspace is std by policy and the substrate's payloads are `Box<[f32]>`. Do not pretend otherwise.

**e. Clippy (`-D warnings`, already in CI).** No allocation lint exists. It may incidentally flag `slow_vector_initialization`; relied on for nothing.

**f. Out-of-band backstop.** `valgrind --tool=massif` / `heaptrack` over the wave-3 fixture (external tools, not crate deps) monthly, reported in the results ledger. Catches late/transitive introductions the commit-time gates miss. Not commit-time.

**Summary of what catches the bug:** the counting-allocator test (deterministic, if written), the grep gate (this literal, probabilistic in general), the debug assertion (deterministic in debug). Compiler and clippy: never.

## 3. The escape hatch

A legitimate allocation in a hot path is admitted only by: (a) a manifest entry `ALLOC-OK <fn> allocs=N bytes=M reason=… owner=…`, (b) the zero-alloc test replaced by a budget test `assert!(delta <= N && bytes <= M)`, (c) a named owner and a one-line record of the alternative considered (hoist to scratch, reuse a buffer, reserve capacity) and why it was rejected — size depends on runtime input, etc. The entry expires at the next wave boundary and is reported as a debt in `docs/RESULTS.md` until renewed or removed. No waiver comments in code outside the manifest; the manifest is the single place, and CI cross-checks that every manifest function has either a zero-alloc test or a budgeted test. If neither exists, CI fails.

**Closure rule:** every file in the manifest has a test asserting its allocation budget (default zero); every allocation in a manifest file is either absent, tested to zero, or manifested with a budget and an owner. Nothing is untested and nothing is undocumented.

*Word count: ~860.*
