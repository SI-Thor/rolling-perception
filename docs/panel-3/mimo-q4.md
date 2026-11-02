# The graduation bar

## Part 1 — My demands, ordered by fatality

**1. A stranger can build it and run its tests in under an hour.** Clone, build, `cargo test` green, on documented hardware. GPU-only tests may be `#[ignore]`d but must say so. Without this, nothing else matters.

**2. Every headline number is verifiable from committed artifacts.** RESULTS.md cites a source file per row; that file exists in the repo and contains the method, not just the number. A stranger can pick 3 rows and confirm them.

**3. The documentation describes the code, or explicitly records where it doesn't.** If DESIGN.md says SPSC and the code is Disruptor, the audit says so and points to the real spec. Silence about divergence is fatal; recorded divergence is a feature.

**4. Tests pass and CI enforces them — a gate that isn't on isn't a gate.** `cargo test --workspace` green. CI runs fmt, clippy, tests on push. No "prepared but Casey enables it."

**5. A stranger can trigger a demo that produces visible output without the owner's house.** A bundled fixture, a synthetic stream, a sample library — something that works cold on a fresh clone. The owner's harbour camera is not a demo.

**6. The project's scope is honest about who it's for.** If it's a personal home platform, say so prominently. A stranger should know in 2 minutes whether this is for them.

**7. Limitations and unproven claims are as findable as the wins.** A deficits section at the same prominence as results. TO-MEASURE markers everywhere a number is missing.

**8. A developer can find the entry points in 10 minutes.** Where's main? What calls what? What's the API surface?

---

## Part 2 — Grading this project

**1. Buildable in under an hour: PARTIAL.** ARCHITECTURE.md claims `cargo test --workspace` = 75 passed on the dev VM (2026-11-01). Hardware is documented (AGX Thor, sm_110, driver 595.78). But the prefix contains **no build instructions** — no "clone, install X, run Y." GPU tests are `#[ignore]`d and feature-gated, Thor-only (P15/P17). A stranger on x86_64 can run CPU tests but the prefix doesn't tell them how. The test-count discrepancy (SPEC §A: "52/52 native on the Thor" vs ARCHITECTURE: "75 passed") is reconciled in ARCHITECTURE's preamble but a cold reader hits the discrepancy first.

**2. Verifiable receipts: PARTIAL.** RESULTS.md is exemplary in structure — every row names a source document. But the prefix is spec + audit + ledger; the cited source files (`slice1/README.md`, `experiments/wave3/report/`, `results/thor/2026-11-01-spike2.md`) are **not in the prefix**. I cannot verify a single number from what I was given. Internal consistency is strong (173 ms, 54% gating, and the Jev advisor finding appear identically in all three documents). Load-bearing numbers still TO-MEASURE: Thor-side whisper RTF, library backfill time, per-camera rates, rule-language expressiveness.

**3. Code-doc consistency: PROVEN.** ARCHITECTURE.md §2–§3 is exactly this demand, executed well. 34 claims traced: 10 proven, 13 partial, 10 unproven, 1 refuted. D1 (SPSC designed, Disruptor built) is called out as "the single worst divergence" with a pointer to the real spec in `substrate.rs`. §5 lists four places where DESIGN.md no longer describes the code. This is the strongest document in the prefix.

**4. Tests + CI enforced: PARTIAL.** 75 tests pass (claimed). CI config exists (fmt + clippy `-D warnings` + tests on x86_64/aarch64). But the clippy leg's "enablement is Casey's" — a workflow prepared, not confirmed on. No grep gate for banned patterns (P14: "no grep gate… no loom job exist in CI"). No loom model for the ring (P11/D1: "the happens-before argument exists only as comments"). GPU tests never execute in CI by design. The invariant ledger (§4) has explicit GAPs: no lineage saturation test, no adversarial causality test, no random-graph sheaf property test.

**5. Cold demo: MISSING.** Every measured result runs on the owner's hardware with the owner's sources: the ProArt camera, the harbour, "Casey's son's" kid profile. The harbor-watch fixture exists and is referenced, but the prefix contains no evidence a stranger can clone and see output. Slice 1's acceptance test requires "the real camera" — no synthetic fallback is described. The 48h soak is running on a real camera in a real house.

**6. Honest scope: PROVEN as honesty, MISSING as generality.** The spec is unambiguous: "Casey's bench," "Sitka," "the household," "Casey's son." §A's title says "all *your* streams." This is a personal platform and says so. But the bar asks "useful to a stranger" — and the documents don't claim that. A stranger reading this knows immediately it's not for them to install; it's for them to learn from. That honesty is a point in the project's favour and a disqualifier for the "useful tool" reading of the bar.

**7. Limitations prominent: PROVEN.** RESULTS.md's "Deficits and open debts" sits at the same prominence as the wins, listing 7 named deficits including "Presence has never been used by a human" and "Slice 1's precision number does not exist yet." ARCHITECTURE.md's tally (10 unproven) is not buried. SPEC §A's TO-MEASURE index names 10 open measurements. This demand is met strongly.

**8. Entry points: PARTIAL.** ARCHITECTURE.md §1's mermaid graph + component table is the map. But there's no "start here": the workspace has 7 Rust crates, a Python ingest process, and two external services (JEV rack, llama-server). A developer must read §1 carefully to find that `confluence-watch` is the integration point and `ingest.py` is the data entry. SPEC §A §2.1's five planes are a conceptual map, not a code map.

---

**Where documents disagree:**
- **Test count:** SPEC §A "52/52" vs ARCHITECTURE "75" — reconciled in ARCHITECTURE's preamble (connect+harden added 20) but a cold reader hits it first.
- **DESIGN.md vs code:** D1 is the headline disagreement (SPSC vs Disruptor). ARCHITECTURE handles it; SPEC doesn't mention it.
- **Derived vs measured weight:** SPEC §B §2.2's "camera 300 embed-s/h ≈ 14% duty (*derived*)" sits visually equal to measured numbers. Labelling is honest; visual weight isn't.

**Bottom line:** The audit discipline (demand 3) and limitation honesty (demand 7) are exemplary — better than most public repos. The project fails the cold-start bar (demands 1, 5) and the stranger-utility bar (demand 6) because it is, by design and by admission, a personal platform on personal hardware. It graduates as a **reference implementation and design record**; it does not yet graduate as a **tool a stranger picks up**.
