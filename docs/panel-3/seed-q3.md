# Hot Path Allocation Policy — Rolling Perception/Confluence Workspace
*Std-only, no new crate dependencies; enforced with native Rust tooling*

---

## 1. Core Rules
### Scope Definition
This policy applies exclusively to **live low-latency pipeline code**: functions invoked per stream tile, per frame, per audio window, or per pipeline tick. Explicitly included:
- `rolling-substrate-core`: `gated_apply`, `laplacian_apply`, ring lease/publish logic
- `rolling-pipeline`: per-tick stage handlers, `Director` logic
- `harbor-watch`: per-tile decision/refinement steps
- Any function measured at >10k calls per hour in production soaks

### 1.1 Banned Behavior
No heap allocations (`Vec::new`, `Box::new`, `String::from`, `format!`, or any global allocator call) *per function invocation*. The only allowed in-function storage is pre-allocated buffers passed as mutable references, initialized once during pipeline setup.

### 1.2 Permitted Allocations (With Hard Budgets)
Pre-allocated buffers are allowed only if:
- Initialized **once** during pipeline/stream setup, not per call
- Sized to the Thor's maximum measured per-frame load: max 192 tiles, 1280-dim embeddings, or 1024-dim audio windows
- Tied to fixed hardware constraints, not dynamic user input

### 1.3 Unrestricted Code
All non-live workloads: backfill jobs, admin APIs, ledger writes, ingest adapters, tests, and debug logging have no allocation restrictions.

---

## 2. Enforcement Mechanisms
No new crates are required; all enforcement uses existing Rust tooling:
1. **Human Review Tagging**: Mark all hot path functions with a `// HOT PATH` comment to clarify scope for reviewers and CI.
2. **Clippy Lint Enforcement**: Use built-in `clippy::disallowed_methods` to ban standard allocator calls in hot path files:
   ```toml
   [workspace.lints.disallowed_methods]
   Vec::new = "deny"
   Box::new = "deny"
   String::new = "deny"
   format! = "deny"
   ```
3. **CI Grep Check**: A lightweight script scans all files with `// HOT PATH` comments, failing if any contain allocator calls inside per-call function bodies.
4. **Unit Test Validation**: Every hot path function must have a test asserting zero per-call allocations, using `std::alloc` hooks to count allocations without external dependencies.

This policy would have immediately caught the `laplacian_apply` Vec allocation bug: the function is in a hot path domain, its `Vec::new` call would be flagged by clippy/CI, and its unit test would fail due to unexpected per-invocation allocations.

---

## 3. Escape Hatch
Legitimate per-call allocations are permitted only if all three conditions are met:
1. Pre-allocation is technically impossible (e.g., unknowable dynamic output sizes for untested hardware)
2. The function is marked with `// HOT PATH EXEMPT: [specific reason]`
3. A project lead-approved CI exception is granted, with a mandatory 30-day ticket to replace the allocation with pre-allocated scratch space.

All exemptions are limited to 10% of hot path functions to prevent policy drift, and all allocations must be freed before the function returns to avoid leaks.

(Word count: ~580, well under 900)
