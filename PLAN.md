# Rolling Perception — The Real Plan

**Status:** Private planning document for a future private repo in the GitHub org
`SI-Thor`. Not public. No repo is created by this document.
**Source:** Casey's seed email *"Rolling perception [muse]"* (1 Nov 2026, 10:48 AKST;
5,318 lines / 233 KB in Gmail; saved copy in the fleet mail archive).
**Companion:** `DESIGN.md` in this same directory — module layout, data structures,
invariants, failure modes.
**Rule for the whole project, stated once and binding everywhere:**
*No claim without a test or a bench number attached to it.* Anything we have not
measured is labelled **hypothesis**, anything we simulated is labelled **simulated**,
and simulated numbers never appear in the same table as measured ones.

---

## 0. How this plan was made (process, in the body)

Casey's doctrine is *document well as you go — the process means more than the
product.* So the process is recorded here, not in an appendix:

1. **Read the whole seed, then mapped its repetition.** The 5,318 lines are not
   5,318 lines of distinct content. They are a multi-generation LLM chain circling
   the same architecture: the four pillars are specified at least four times, the
   Rust "complete implementation" appears at least three times with drifting field
   names (`execution_latency` → `actual_latency` → `reported_latency`), and the
   mathematical "proofs" appear twice. Distinct ideas occupy maybe 15% of the file.
   First planning decision, therefore: **do not port the email. Extract its ideas,
   grade each one, and rebuild only what survives.**
2. **Checked the code against its own claims.** Every Rust listing was read as
   code, not as prose. That check — not an opinion about the writing — is what
   produced the keep / fix / drop table in §3. The load-bearing findings:
   NVRTC/CUPTI/`cuLaunchKernel` calls are commented out or absent; "GPU latency"
   is `std::thread::sleep(...)`; "compiled binaries" are literal mock byte vectors
   (`vec![0x90, 0xBF, 0x10]`); "optimisation" is a hard-coded `baseline * 0.75` /
   `* 0.85`; the sheaf pass is a magnitude clamp; the hot-swap frees the old module
   (`Box::from_raw(old_ptr)`) while other threads may still be executing through it.
3. **Checked the hardware target against the fleet's own records.** The email
   targets `sm_100` / `sm_101` throughout. The actual Jetson AGX Thor in the fleet
   reports compute capability **11.0 → `sm_110`**. Every CUDA statement in the seed
   is therefore aimed at the wrong architecture string, and v0.2 (§6) treats the
   correct NVRTC target as an *empirical question to verify on the box*, not a
   constant copied from the email.
4. **Tried and rejected three plan shapes before settling (dead ends, kept on
   purpose):**
   - *Dead end A — "Faithful implementation":* implement all four pillars as
     specified, in order. Rejected: it would spend the entire budget re-building
     the simulated parts (PIR, DMA audio, autonomous JIT mutation) whose
     correctness fails on paper, before ever testing the one idea that might be
     true (rolling vs. batched).
   - *Dead end B — "CUDA first, because Thor":* start on the GPU so the result is
     "real". Rejected: CUDA conflates four separate questions (is staggering
     better? is gating cheaper? does the sheaf step converge? is lineage exact?)
     with driver, stream, and occupancy noise, and none of the four questions
     needs a GPU to be answered falsifiably. CUDA also breaks our own rule: on
     day one we would have no CPU reference to check GPU output against.
   - *Dead end C — "Benchmark a simulation":* keep `sleep()` as the compute proxy
     and just measure the scheduler around it. Rejected as the core method:
     sleeping threads measure the OS timer, not work; a scheduler that wins
     around sleeps may lose around real arithmetic (cache effects, no wake-up
     granularity cost for real work). Sleep is allowed in exactly one place —
     modelling *sensor inter-arrival time*, where a wait really is a wait — and
     must be labelled as such wherever used.
5. **Settled shape (this plan):** a small pure-Rust CPU crate that proves or
   refutes the scheduling / gating / consistency / lineage claims with real
   arithmetic and real measurements (v0.1), *then* a gated CUDA experiment on
   the Thor that re-asks the same questions against the CPU reference (v0.2),
   *then* sensors and models (v0.3+). If v0.1 refutes the core claim, v0.2 does
   not happen and we publish the negative result privately to ourselves and stop —
   that is a successful outcome of the plan, not a failure of it.

---

## 1. The first-principles problem

### 1.1 The asymmetry that actually exists

A sensor and a small compute kernel live on different clocks:

| Quantity | Order of magnitude | Source of the number |
|---|---|---|
| 240 Hz camera frame interval | 4,166 µs | 1 / 240 s, arithmetic |
| 60 Hz sensor frame interval | 16,667 µs | 1 / 60 s, arithmetic |
| Audio block, 128 samples @ 48 kHz | 2,667 µs | 128 / 48,000 s, arithmetic |
| Small spatial kernel (filter / small matvec over a slice) | ~1–50 µs | **Hypothesis on Thor/CPU — v0.1/v0.2 must measure our own kernels; the email's "~10 µs" is asserted, never measured** |

If a pipeline waits until *all* lanes have a fresh frame, processes them
together, and only then emits anything, the consumer sees updates at the
**slowest lane's rate**, and each update's data is on average half a frame old
when processing starts. The compute device, meanwhile, is idle for most of the
frame interval and saturated for a burst. That is the real problem. It is a
problem about **latency distribution and data staleness**, not about total
throughput — total work is identical either way.

### 1.2 The four metrics that define "better"

Any version of this project is judged on these, measured the same way for
batched and rolling execution of *the same work*:

1. **Time to first update (TTFU)** — from a lane's data becoming available to
   the first downstream output that depends on it.
2. **Inter-update interval** — p50 / p95 / p99 gap between successive outputs
   to the consumer. Rolling wins, if it wins, here: many small, frequent
   updates instead of few large, bursty ones.
3. **Staleness at query time** — when a consumer reads the shared state at an
   arbitrary instant, how old is the newest contribution from each lane?
   (Directly Casey's *active log* idea: dated readings, age is part of the data.)
4. **Total completion time / total work** — the honesty metric. Rolling may be
   *worse* here (per-slice overhead, poorer cache locality, more scheduler
   wake-ups). We report it alongside 1–3, never instead of them. A design that
   buys freshness at a stated throughput cost can be the right trade; a design
   that hides the cost is not.

### 1.3 What rolling can and cannot do (correcting the seed)

- Rolling **can** pipeline: lane B's slice is processed while lane C is still
  exposing / in flight, and model stage 2 works on stage 1's *latest partial
  output* instead of waiting for a full barrier. This reduces TTFU and
  inter-update interval when per-slice compute ≪ frame interval.
- Rolling **cannot** "bypass Nyquist–Shannon", despite the email's claim.
  Staggering does not create information between a sensor's samples. What it
  produces between samples is *prediction / extrapolation from prior samples*,
  which is sometimes useful and always has error that grows with horizon.
  v0.1 therefore treats any between-samples output as a prediction carrying an
  age and a horizon, never as a measurement.
- Rolling **does not** help when per-slice compute ≈ frame interval, when the
  consumer needs a globally consistent snapshot (it then waits for the slowest
  contributor anyway), or when slices share so much state that serialising them
  costs more than batching. The benchmarks must include a regime where batched
  is expected to win, and we must publish that crossover if we find it.

### 1.4 The problem statement, in one sentence

> Given several slow, periodic producers and several fast compute stages that
> share state, can a phase-staggered ("rolling") schedule deliver measurably
> fresher, more frequent updates than a barrier ("batched") schedule for the
> same total work — and can the shared state be kept provably consistent and
> its provenance exactly recorded, cheaply enough that the overhead does not
> erase the gain?

Everything in v0.1 exists to answer that sentence. Everything else in the email
is downstream of it.

---

## 2. Honest architecture (the shape we are actually building)

```
 producers (v0.1: synthetic, real arithmetic)     ┌────────────────────────────┐
 ┌─────────┐  ┌─────────┐  ┌─────────┐            │        shared state         │
 │ lane A  │  │ lane B  │  │ lane C  │            │  sections per lane/stage,   │
 │ sensor  │  │ sensor  │  │ audio   │            │  each with: values,         │
 └────┬────┘  └────┬────┘  └────┬────┘            │  sequence no., timestamp,   │
      │ phase φA   │ φB         │ φC               │  lineage (exact counts)     │
      ▼            ▼            ▼                  └──────────────▲─────────────┘
 ┌──────────────────────────────────────┐                       │ read latest /
 │  bounded SPSC ring per lane           │                       │ write own section
 │  (sequence-numbered slots, §DESIGN)   │                       │
 └──────────────────┬───────────────────┘                       │
                    ▼                                            │
 ┌─────────────────────────────────────────────────────────────┴──┐
 │  SCHEDULER — one of two, same node code, same total work:      │
 │   • BatchedScheduler   : barrier — wait all lanes, run stages  │
 │   • RollingScheduler   : phase-staggered — run a stage on the  │
 │                          newest available slice, publish       │
 │                          immediately, advance one phase        │
 │  Stages (nodes): perceive → decide → direct (sets gate) →      │
 │                  refine (one iterative step, e.g. one sheaf /  │
 │                  diffusion-style relaxation step) → publish    │
 └──────────────────┬─────────────────────────────────────────────┘
                    ▼
        consumer: dated snapshot { value, per-lane age,
        lineage, gate used }  +  metrics log (for benches/replay)
```

Design commitments that make this honest rather than theatrical:

- **One node codebase, two schedulers.** Batched vs. rolling is a scheduling
  policy over identical stages and identical arithmetic. If the two paths had
  different math, the comparison would prove nothing.
- **Real arithmetic everywhere.** A "perception" node in v0.1 does an actual
  small computation over its slice (e.g. a separable filter / edge response /
  small matvec) whose cost scales with input size and gate area, and whose
  output is checked against a naive reference. No `sleep` as compute, no
  hard-coded speed-up factors, no mock byte buffers standing in for binaries.
- **The director is a policy, not an LLM, in v0.1.** The email has a
  Nemotron-Mini LLM setting attention masks every 10 µs. No LLM runs in 10 µs;
  LLM inference is milliseconds — three orders of magnitude off the claimed
  cadence, and at that cadence it would *become* the slowest lane. v0.1's
  director is a cheap deterministic policy (e.g. track the highest-response
  tile, with hysteresis / deadband — Casey's band + yaw-time) that runs at
  slice rate. A learned / model director is a v0.3 question, running at its
  own honest, slower cadence and updating the gate *asynchronously*.
- **Consistency is a measured relaxation, not a clamp.** The sheaf idea
  survives only as a real graph-Laplacian diffusion step over overlapping
  sections with a computable energy that tests can watch decrease (§3 row 5,
  §5.3). If it does not decrease, the code is wrong and the test must fail.
- **Provenance is exact, or it is not claimed.** Prime-product lineage is
  replaced by counted lineage (§3 row 6). Presence-in-history is a bitset;
  how-many-times is a counter array; overflow saturates and sets a flag
  instead of silently wrapping into a wrong answer.
- **No component claims to be "lock-free", "zero-copy", or "sub-microsecond"
  in prose unless a test or bench in the repo substantiates the specific
  meaning used.** v0.1's ring is SPSC per lane (see `DESIGN.md` for why the
  email's MPMC protocol is unsound and why we narrowed it).

---

## 3. Keep / Fix / Drop — grading every idea in the seed

| # | Idea in the email | Verdict | Why (checked, not vibes) | What we do instead |
|---|---|---|---|---|
| 1 | **Sequential phase-interleaved rolling pipeline** — stagger lanes/stages at µs offsets, emit continuously | **KEEP — this is the project** | Follows directly from the sensor/compute asymmetry (§1.1); makes falsifiable predictions about TTFU, inter-update interval, staleness | The v0.1 scheduler pair and bench suite are built around testing exactly this (§5) |
| 2 | **Shared ring buffer in unified memory** as the only producer→compute channel | **KEEP, narrowed** | Sound shape (bounded ring, sequence numbers, no per-message allocation). But the email's protocol is unsound: `finalize_write` stores a sequence derived from the *current global cursor*, not the lease's cursor, so two leases can publish the same/wrong sequence; `lease_slot` spins on a sequence that its own protocol may never produce; it is presented as multi-producer while the cursor logic races | SPSC ring per lane, per-slot sequence protocol specified and invariant-tested in `DESIGN.md`; multi-producer deferred until loom-tested (v0.3+) |
| 3 | **Viewport / attention gating** — skip work outside a region of interest | **KEEP, with counting** | Real and elementary: work skipped is work saved, proportional to skipped fraction, *minus* gating overhead. The email asserts sub-µs results and "100% of power focused" without counting a single skipped operation | Gate at tile granularity; instrument an **operation counter** so savings are counted operations first and wall-time second; correctness contract: output inside the gate is bit-identical to ungated, outside is explicitly *stale/skipped*, never silently wrong (§5.2) |
| 4 | **Attention director** — a cognitive node sets the next gate | **KEEP the seam, FIX the actor** | The feedback loop (director → gate → cheaper next pass → director) is the interesting system dynamics. An LLM in the µs loop is physically implausible (ms inference) and would dominate latency | v0.1: deterministic policy with deadband/hysteresis. v0.3: optional slow model director updating gates asynchronously; its cadence is measured and reported, not hidden |
| 5 | **Sheaf Laplacian consistency** — $\Delta_\mathcal{F}=D D^{T}$, project back to the global section | **FIX — keep the math, replace the implementation and fix the statement** | The email's code is `if \|v\|>10 { v *= 0.333 }` — a clamp; it computes no $D$, no Laplacian, no projection, and would pass its own "test" on any input. Its formula also flips between $D D^{T}$ and $D^{T} D$ across generations; for an incidence/coboundary $D$, the graph Laplacian on 0-sections is $L = D^{T}D$, and the energy is $E(s)=s^{T}Ls=\|Ds\|^{2}$. The one-page "proof" in the email is that definition restated | Implement a real sparse incidence for a stated overlap graph, $L=D^{T}D$, energy $E(s)$, and an explicit relaxation step $s \leftarrow s - \alpha L s$ with $\alpha$ bounded by the Laplacian's spectral radius estimate. Tests assert $E$ is non-increasing per step and converges toward consensus on a connected graph (§5.3) |
| 6 | **Prime Integer Relations (PIR) lineage** — $S \leftarrow S \times p_{node}$; check $S \bmod p = 0$ | **DROP as a correctness mechanism; KEEP as a documented counterexample** | Fails three ways, all demonstrable in a unit test: (a) *counts are lost* — $3^1$ and "3 then 3 again divided out once" are indistinguishable in kind; history $\{3,5\}$ and $\{3,5,5,5\}$ both just pass the mod-5 check; (b) *u64 wraps* — $3^{40} > 2^{64}$, so a busy slot overflows quickly and `wrapping_mul` then yields residues unrelated to history, i.e. false positives/negatives; (c) modulo is not "single-cycle bitwise" — integer division is among the slowest scalar ops. The email's "proof" invokes unique factorisation of an integer the machine no longer holds once it has wrapped | **Counted lineage:** per-slot `present: bitset` + `counts: [u16; N_NODES]` (saturating, with overflow flag) + monotonic sequence. Property test: random node sequences vs. a reference `Vec<NodeId>` log must match exactly. A `pir.rs` experiment file may remain, with tests that *demonstrate* its failure modes, so the dead end is on record |
| 7 | **Persistent warps (CudaClaw)** resident on SMs, polling flags, "<100 ns pickup" | **DEFER to v0.2 experiment; DROP the numbers** | Persistent kernels are a real technique, but the pickup latency, occupancy cost, preemption/watchdog behaviour, and power cost on *this* Thor are all unmeasured; "<100 ns" is asserted in every generation and measured in none | v0.2 spike (§6) measures launch-latency-bound vs. persistent-kernel pickup on the actual box, including its costs, and keeps whichever wins. No latency number enters the docs before that bench exists |
| 8 | **CascadeJIT / NVRTC hot-swap** — compile a mutated kernel on a shadow stream, atomic pointer swap, zero downtime | **DEFER, heavily fenced (v0.2)** | The mechanism (NVRTC → cubin → load → swap handle *between launches*) is real. Three parts are not: (a) target `sm_100/sm_101` is wrong for Thor (`sm_110` — §0.3); (b) the email's swap dereferences and frees the old module while sibling threads hold the raw pointer — a textbook use-after-free; a safe swap needs epoch/refcount reclamation and "swap takes effect at a launch boundary"; (c) mock cubin bytes prove nothing | v0.2: host-side handle swap at launch boundaries only, old modules retired after an epoch drains, NVRTC target verified empirically, correctness of the swapped kernel checked against the CPU reference before it may serve traffic (§6) |
| 9 | **RLEF critique loop / LLM rewrites kernels autonomously** from CUPTI stalls | **DROP for v0.1–v0.2; reconsider as an offline advisor in v0.3+** | Nothing in the chain exists yet to critique: there is no real kernel, no CUPTI plumbing, no evaluation gate — and an autonomous code-mutation loop without a correctness+bench gate is how a system gets faster and wronger. The email's loop "verifies" by sleeping for the new latency it invented | Offline only, later: a tool may *propose* a kernel variant; a human-reviewed PR + the full correctness suite + benches decide. Never self-deploying |
| 10 | **NVFP4 + micro-scaling as a core premise; "2,070 TFLOPS"** | **DROP as a premise; MAYBE as a v0.2 kernel variant** | Peak FP4 TFLOPS is a dense-large-GEMM number. Our kernels are small, likely memory/latency-bound; quoting 2,070 TFLOPS for them is marketing arithmetic. NVFP4 also imposes block-scaling accuracy costs the email asserts away ("99.6%") without a single comparison | If a v0.2 kernel uses a low-precision path, it ships with an accuracy comparison vs. the FP32/FP16 CPU reference on the same inputs, and the bench reports bytes moved as well as time |
| 11 | **SkaldAudio — direct DMA intercept of mic arrays**, bypassing the OS audio stack | **DROP the DMA intercept; KEEP audio as a lane** | No evidence in the seed (or on our box) that bypassing PipeWire/ALSA is needed, safe, or even accessible from userspace on the Thor; it is the highest-risk, least-verified claim in the file. Audio as a *staggered periodic producer* is, however, a perfect rolling-pipeline lane (2,667 µs block cadence, §1.1) | v0.1: audio-shaped synthetic lane (real PCM-like arithmetic: demux + filter). v0.3: real audio via the normal OS stack (ALSA/PipeWire), measured jitter and all |
| 12 | **Cold-boot bootstrap kernel** (immutable C++/asm layer that brings the system up) | **DROP** | Solves a problem we do not have: the Thor boots Linux fine. It exists in the email to make the architecture feel self-contained | The process starts as a normal user-space process under systemd like every other fleet service, when and if it ever runs on the box |
| 13 | **"Zero human engineering overhead" / "zero-maintenance intelligent grid" / "continuous consciousness"** | **DROP — language rule** | Unfalsifiable. Every such phrase in our docs is a debt someone will believe | Banned-phrases list in §8; docs use the four metrics of §1.2 or say "unknown" |
| 14 | **Optical-flow "infinite frame synthesis" / rolling raster display warp** | **DROP from this repo** | A different project (display pipeline) bolted onto this one; depends on hardware paths we have not probed | Out of scope (§7 non-goals). If it is ever pursued, it is its own repo with its own reference checks |
| 15 | **One diffusion step per rolling tick** as a pipeline stage | **KEEP as a stage *shape*, not as a diffusion model** | "One iterative-refinement step per tick, publishing the partially refined state" is exactly the rolling pattern applied to iterative algorithms, and it generalises beyond diffusion (relaxation, tracking, solvers) | v0.1's `refine` stage is one step of an iterative relaxation (the sheaf step doubles as this). A real diffusion model as a stage is a v0.3 integration question |

---

## 4. Repo shape (when the parent lane creates it)

- **Name (proposal, parent lane / Casey to confirm):** `SI-Thor/rolling-perception`.
- **Visibility:** private until §9's public gate is met. Being born private is a
  deliberate reversal of the house "public by default" habit, at Casey's explicit
  direction for this repo: *working and useful on our Thor first, documentation
  improved second, public third.* The reversal and its reason go in the repo's
  first commit message and in the README's status line, so nobody later reads
  the private phase as secrecy-by-drift.
- **Licence:** undecided until the public gate; add no licence file while private
  beyond a `NOTICE: private, all rights reserved, licence TBD before publication`
  line. (Choosing MIT/Apache-2.0 is a public-gate decision, not a v0.1 blocker.)
- **Language/tooling:** Rust, stable toolchain, `cargo test`, `cargo bench`
  (Criterion), `cargo clippy -- -D warnings`, `rustfmt`. No CUDA, no FFI, no
  network dependencies in v0.1. Dev-dependencies for property tests (`proptest`)
  and concurrency-model tests (`loom`, behind a cfg flag) are allowed.
- **Layout:** single crate first (lib + examples + benches), modules per
  `DESIGN.md`. Splitting into a workspace is earned only when a second consumer
  exists — Casey's monorepo-first rule: one body, one clock, one test suite;
  extraction too early freezes guesses as seams.

```
rolling-perception/
  Cargo.toml
  README.md            # status: PRIVATE / EXPERIMENTAL, what is measured vs not
  PLAN.md  DESIGN.md   # these documents, copied in as the founding record
  src/
    lib.rs
    slot.rs      ring.rs       # §DESIGN 2–3
    lineage.rs                 # counted lineage (+ pir.rs experiment, clearly fenced)
    sheaf.rs                   # incidence, Laplacian, energy, relaxation step
    gate.rs                    # tile gate + operation counting
    node.rs      workloads.rs  # stage trait + real-arithmetic workloads
    scheduler.rs               # BatchedScheduler, RollingScheduler
    metrics.rs   replay.rs     # histograms, dated snapshots, deterministic replay log
    clock.rs                   # logical clock (tests) + monotonic clock (benches)
  examples/
    rolling_demo.rs            # prints the four metrics for both schedulers
  benches/
    rolling_vs_batched.rs  gating.rs  sheaf.rs  ring.rs
  tests/
    ring_protocol.rs  lineage_property.rs  sheaf_energy.rs
    gate_correctness.rs  scheduler_fairness.rs
  results/                     # committed bench outputs (CSV/JSON) + machine description
```

Process note — *why a `results/` directory in git:* a bench that lives only in
CI logs or a chat message is a claim, not a record. Every number quoted in the
README must point at a committed result file that names the machine, the
toolchain (`rustc --version`), the workload parameters, and the date.

---

## 5. v0.1 scope — CPU-provable, pure Rust, no CUDA dependency

**Goal of v0.1:** answer §1.4 for synthetic-but-real workloads, with numbers we
would be willing to show a sceptic. v0.1 is *not* a Thor product; it must build
and pass on any ordinary Linux x86_64/aarch64 dev machine, including the fleet's
non-Thor boxes, so that "it only works on the magic box" can never be an excuse.

### 5.0 In scope (the whole of v0.1 — anything not listed is out)

1. Bounded SPSC ring per lane with the sequence protocol, invariants, and
   backpressure policy (block / drop-oldest-with-counter / drop-newest-with-counter,
   chosen per lane, never silent) specified in `DESIGN.md`.
2. The stage pipeline `perceive → decide → direct → refine → publish` as a
   `Node` trait, with at least these workload implementations, all doing real,
   input-dependent arithmetic with a naive reference implementation for
   correctness checks:
   - *perceive:* separable filter / gradient response over a 2-D slice;
   - *decide:* per-tile response reduction + threshold/hysteresis state;
   - *direct:* gate policy (largest-response tile cluster, deadband on movement);
   - *refine:* one sheaf relaxation step over the shared sections (§5.3);
   - *publish:* dated snapshot assembly (values + per-lane ages + lineage + gate).
3. `BatchedScheduler` and `RollingScheduler` over the *same* nodes, rings, and
   workloads, with matched total work enforced by an operation counter (a bench
   in which the two schedulers perform different amounts of arithmetic is
   invalid and the harness must detect and reject it).
4. Tile gating with operation counting (§5.2).
5. Sheaf consistency module (§5.3).
6. Counted lineage, plus the fenced PIR counterexample (§5.4).
7. Metrics: TTFU, inter-update interval, staleness-at-query, total completion —
   collected by both schedulers in the same format, exportable as CSV/JSON.
8. Deterministic replay: with the logical clock and a recorded input trace, a
   run replays bit-identically (same outputs, same lineage, same gate sequence);
   wall-clock mode is for benches only and is labelled non-deterministic.
9. `rolling_demo` example + committed `results/` from at least one named machine.

**Explicitly not in v0.1:** CUDA, threads-per-SM anything, real sensors, real
audio devices, any LLM, any network I/O, any daemon/service mode, NVFP4,
optical flow, a display path, autonomous code generation, multi-producer rings.

### 5.1 The headline experiment: rolling vs. batched

- **Scenarios (all four mandatory; a suite that only shows rolling winning is
  presumed rigged until proven otherwise):**
  - **S1 — staggered-friendly:** 3 lanes, different periods (e.g. 60 Hz /
  120 Hz / 240 Hz equivalents, scaled to logical ticks), per-slice compute
  ≪ shortest period. *Expectation (hypothesis):* rolling improves TTFU, p95
  inter-update interval, and mean staleness vs. batched.
  - **S2 — heavy slices:** per-slice compute ≈ shortest period. *Expectation:*
  rolling's advantage shrinks or vanishes; total completion may favour batched.
  - **S3 — global-consumer:** consumer periodically requires a consistent
  all-lanes snapshot. *Expectation:* batched is competitive or better; rolling
  must wait or publish a knowingly partial snapshot (flagged partial, with ages).
  - **S4 — single lane:** degenerate case; both schedulers must behave
  identically within noise. (Guards against "rolling wins" being an artefact of
  the harness treating the two paths differently.)
- **Fairness rules (enforced by the harness, not by honour):** identical input
  traces for both schedulers; identical node instances reset to identical state;
  identical total operation counts (±0 counted ops — the counters must match
  exactly for ungated runs); same thread count (v0.1 default: producers on
  their own threads, scheduler single-threaded, identical for both policies);
  interleaved bench ordering (A/B/A/B) to cancel thermal/ordering drift.
- **Reporting:** for each scenario × metric: median and p95 with the sample
  count, machine, and parameters, committed under `results/`. **No pre-committed
  speed-up target.** The acceptance criterion is that the numbers exist, are
  reproducible (§8), and the README states them *including where rolling loses*.

### 5.2 Gating: savings must be counted, not implied

- Work is divided into fixed tiles (default 32×32, configurable). The gate is a
  set of tiles. A gated node counts every scalar operation it performs in an
  `OpCounter`; ungated count is measured by running the same node ungated on
  the same input, not computed from geometry alone.
- **Claims allowed, in this order of strength:** (1) counted ops saved =
  ungated ops − gated ops on identical inputs (exact, primary); (2) wall-time
  saved on the bench machine (secondary, noisy, reported with spread).
  Geometry (`gate area / total area`) may be shown as context but is *not* a
  savings claim — tile granularity and border effects make it an overestimate.
- **Correctness contract (tested):** for any input and gate, outputs for tiles
  inside the gate are identical to the ungated run; tiles outside the gate are
  left at their previous values and the snapshot marks them stale-by-gate with
  the tick at which they were last computed. A test that finds an inside-gate
  mismatch, or an outside-gate tile silently updated, fails the build.
- Edge cases under test: empty gate (zero work, snapshot all-stale, no panic),
  full gate (must equal ungated exactly, overhead reported), gate moving every
  tick (policy thrash — deadband must bound gate churn; churn is a metric).

### 5.3 Sheaf consistency: a real Laplacian, a watched energy

- **Definitions (fixed here to end the seed's $DD^{T}$/$D^{T}D$ drift):** the
  overlap graph has one vertex per section (lane/stage output block) and one
  edge per stated overlap/consistency relation. $D$ is the (signed, weighted)
  incidence matrix of that graph acting on section-value differences in the
  simplified scalar-per-coordinate setting of v0.1: each edge contributes a row
  comparing the overlapping coordinates of its two sections. $L = D^{T}D$.
  Energy $E(s) = s^{T} L s = \lVert D s \rVert^{2} \ge 0$, with $E(s)=0$ iff
  all compared overlaps agree (consensus on each connected component).
  v0.1 is explicit that this is the *graph-consensus special case* of a cellular
  sheaf (all restriction maps = identity on overlaps) — honest mathematics for
  the case we implement, not the general sheaf machinery the email gestures at.
  Non-identity restriction maps are a v0.3+ research item, if ever.
- **Step:** $s \leftarrow s - \alpha L s$, with $\alpha \in (0, 2/\lambda_{\max}]$
  estimated by power iteration at setup and asserted in tests; or equivalently
  a neighbour-averaging (Jacobi diffusion) step whose equivalence for the
  test graphs is shown in a test, not asserted in prose.
- **Tests (all mandatory):**
  - $E(s) \ge 0$ for random $s$ (property test);
  - $E$ is **non-increasing** after each step (within a stated floating-point
    tolerance, e.g. `E_next ≤ E_prev * (1 + 1e-6) + 1e-12`) for random initial
    $s$ on random connected graphs — this is the test the email's clamp would
    also need to face, and a clamp does *not* pass it in general, which is the
    point of having it;
  - on a connected graph, repeated steps drive $E \to$ below a stated epsilon
    and sections toward per-component consensus (mean-preserved for the
    averaging form — assert the invariant the chosen form actually has);
  - on a disconnected graph, consensus is reached per component and *not*
    across components (guards against a "global average" cheat);
  - disagreement injection: corrupt one section by a known delta; energy rises
    by a computable amount and the step reduces it — the "drift correction"
    story, made measurable.
- **Bench:** cost of one step vs. section size / edge count; energy-vs-steps
  curve committed as data. If a step costs more than re-running the producer
  would, the docs must say so.

### 5.4 Lineage: exact counts, and the PIR autopsy

- **Data (per slot, per `DESIGN.md`):** `present: u64` bitset over node IDs
  (≤64 registered nodes in v0.1), `counts: [u16; 64]` saturating counters, and
  the slot's sequence number. Node IDs are assigned by a registry at pipeline
  construction — never by primes, never by hand-duplicated constants.
- **Property test (the core of this module):** generate random sequences of
  node executions (including repeats, long runs past 255 and past 65,535 for a
  single node); after each prefix, `present`/`counts` must exactly match a
  reference computed from a plain `Vec<NodeId>` log — with the single stated
  exception that counts at saturation report `u16::MAX` *and* the slot's
  `lineage_overflowed` flag is set. Silent wrong answers are the failure mode;
  flagged saturation is specified behaviour.
- **PIR autopsy (`src/pir.rs`, fenced with a module doc that says EXPERIMENT /
  NOT USED FOR CORRECTNESS):** re-implement the email's u64 prime-product
  scheme and include tests that *demonstrate*: (a) two different histories with
  the same mod-check answers; (b) a history long enough to wrap u64 and produce
  a false negative for a node that demonstrably ran; (c) count blindness
  (1 visit vs. 5 visits indistinguishable). These tests pass by showing the
  scheme failing — the dead end, preserved as evidence per the documentation
  doctrine, so a future reader never has to re-litigate it.

### 5.5 Ring and scheduler correctness tests

- Sequence protocol: no slot is read before it is `Ready`, no slot is
  overwritten while `Ready`/`Reading` under the block policy, sequence numbers
  are strictly increasing per lane, and a wrapped ring (capacity ≪ message
  count, e.g. 8 slots / 100,000 messages) delivers every message exactly once
  in order under SPSC. Model-checked with `loom` for the concurrent interleavings
  and stress-tested with real threads.
- Drop policies: under drop-oldest / drop-newest, the drop counter equals the
  number of messages the consumer can prove it missed from sequence gaps —
  *accounted loss, never silent loss.*
- Scheduler determinism: same logical-clock trace in → identical snapshot
  sequence out, for both schedulers (bit-identical outputs; timings excluded).

### 5.6 v0.1 acceptance gate (all must hold to call v0.1 done)

1. `cargo test` green, including property and loom suites; `clippy` clean.
2. All four §5.1 scenarios benched, results committed, README updated with the
   numbers *as found* — including any scenario where batched wins.
3. Gating counted-ops savings and inside-gate correctness demonstrated (§5.2).
4. Sheaf energy tests of §5.3 pass; energy curve committed.
5. Lineage property test passes; PIR autopsy tests pass (by failing PIR).
6. No banned pattern present in the codebase (§8 list is grep-enforced in CI:
   no `thread::sleep` outside the sensor-arrival model and bench harness, no
   hard-coded latency/speed-up multipliers, no byte vector named as a compiled
   binary).
7. A sceptic path exists: from a clean clone, `cargo run --example rolling_demo`
   reproduces the headline comparison on the reader's own machine in under a
   few minutes.

**If rolling loses on the metrics that matter in S1** (its home scenario), v0.1
still "passes" as an experiment — and the plan stops, the result is written up,
and v0.2 is cancelled. Pre-committing to that now is what makes the positive
result, if we get one, worth believing later.

---

## 6. v0.2 scope — Thor CUDA, as an experiment behind a feature flag

**Preconditions (all of them):** v0.1 acceptance gate met *and* rolling showed
a real advantage somewhere worth chasing *and* the separate Thor-feasibility
lane has verified on the actual box: CUDA toolkit version, NVRTC availability,
the correct architecture string for capability 11.0, and a working
compile→load→launch path from Rust. v0.2 does no work on the Thor except
through the parent lane's booking/coordination for that box (Casey works the
Thor directly; this project does not colonise it).

**Shape:** a `cuda-thor` cargo feature, off by default. The CPU crate remains
the reference implementation and the source of truth; the feature adds an
alternative `Executor` for *one* workload kernel first (the perceive filter),
nothing else. Everything below is an experiment protocol, not a promise:

- **Spike 1 — NVRTC correctness, target verified empirically.** Compile the
  kernel source at runtime via NVRTC, trying the architecture flags the
  installed toolkit documents for capability 11.0 (`compute_110` / `sm_110`
  family) and *recording which flag the box actually accepts* — the email's
  `sm_100` string is treated as a known-wrong control. Load via the driver API,
  launch on known inputs, compare against the CPU reference bit-for-bit or
  within a stated FP tolerance. *Kill criterion:* if NVRTC/driver plumbing from
  Rust cannot be made to work cleanly, v0.2 stops here and the finding is filed.
- **Spike 2 — launch-bound vs. persistent.** Measure, on the Thor, for the same
  kernel and slice sizes as v0.1: (a) ordinary per-slice launch on a stream;
  (b) two-stream shadow arrangement (compute on A while B is staged);
  (c) a persistent kernel polling a flag in device-visible memory. Report
  pickup latency distributions, occupancy, CPU cost of the polling host/device
  sides, and power/thermal behaviour over a sustained run — persistent kernels
  that spin are not free, and on a shared box they are a neighbour problem.
  Keep whichever arrangement the numbers favour, including arrangement (a).
- **Spike 3 — host-side swap at launch boundaries.** Swap the loaded module
  handle *between* launches (never a raw function pointer inside a running
  persistent kernel in v0.2). Retired modules are freed only after all launches
  submitted against them have completed (stream/event-tracked epoch). Test:
  swap mid-stream 1,000 times under load; outputs remain reference-correct on
  every slice; no use-after-free, no leaked modules (driver memory accounting
  before/after).
- **Explicitly not in v0.2:** CUPTI-driven anything, LLM/RLEF kernel mutation,
  NVFP4 unless a spike-1 kernel variant isolates its accuracy cost, persistent
  kernels in any always-on service, any claim about the other three pillars on
  GPU. CUPTI telemetry, *if* ever added, is v0.3 observability work — reading
  counters, not feeding an autonomous rewriter.
- **v0.2 acceptance gate:** the feature builds only on the Thor (or a documented
  `sm_110` environment), its kernel matches the CPU reference under the full
  v0.1 correctness suite run against the GPU executor, spike results are
  committed under `results/thor/`, and the README's Thor section states measured
  numbers or states that the spike was killed and why.

---

## 7. v0.3+ roadmap and non-goals

### Roadmap (each item is a separate decision, not a commitment)

- **v0.3 — real producers, boring plumbing:** file-replay producer (recorded
  traces as lanes — replay first, live sensors second), then one live lane via
  the OS's normal stack (V4L2 camera *or* ALSA/PipeWire audio), with measured
  arrival jitter published next to the synthetic-lane results so the gap
  between model and reality is on paper.
- **v0.3 — slow director:** a small model (or the fleet's JEV-style scorer)
  updating the gate at its natural cadence (10s–100s of ms), asynchronously,
  with its staleness treated exactly like a slow sensor's. Question to answer:
  does a smarter gate beat the deterministic policy's counted-ops savings per
  unit of director cost?
- **v0.3 — offline kernel-variant advisor:** tooling that *proposes* kernel
  variants (human- or model-authored) into a PR, gated by the full correctness
  suite + benches. This is the honest descendant of the email's RLEF loop:
  the loop exists, but a human and a test suite are inside it.
- **v0.4 — multi-producer ring**, only if a real consumer needs it, and only
  with a loom-verified protocol (Vyukov-style bounded MPMC or per-producer
  rings with a merge step — the merge-step design is the current favourite
  precisely because v0.1's SPSC proof stays intact inside it).
- **v0.4 — general sheaf restriction maps** (non-identity), only if a concrete
  multi-model consistency problem appears that the consensus special case
  demonstrably cannot express, and with the energy theory re-derived for that
  case before code.
- **Public gate (§9)** whenever the Thor work is genuinely useful.

### Non-goals (for the life of this repo, unless Casey re-opens them)

- A general-purpose "operating system for the Thor", a runtime that hosts
  arbitrary models, or a PyTorch/TensorRT competitor.
- Autonomous self-modifying production code (no RLEF self-deployment, ever).
- Bypassing OS device stacks (no DMA intercepts, no kernel modules).
- Display / optical-flow / frame-generation work.
- Chasing peak-TFLOPS figures or benchmarking against large-GEMM workloads.
- Multi-machine / distributed rolling perception (single-box shared memory is
  the premise; distribution is a different problem with a different plan).
- Becoming a dependency of any life-critical or navigation-critical path
  without a separate safety case. This is an experimental substrate.

---

## 8. Verification standards

These bind every version, every author (human, Muse, or fleet seat) and every
document in the repo:

1. **Claim labelling.** Every performance or correctness statement in README /
   docs carries one of: **[measured]** (link to committed result + test),
   **[derived]** (arithmetic from stated inputs, shown), **[hypothesis]**
   (untested), **[simulated]** (modelled, with the model named). Unlabelled
   superlatives ("sub-microsecond", "zero overhead", "100 ns pickup") are
   review-blocking defects.
2. **Banned implementation patterns** (grep-enforced in CI, §5.6.6):
   `sleep` as a compute proxy; hard-coded speed-up/latency fudge factors;
   mock byte arrays presented as compiled binaries; commented-out FFI presented
   in docs as working FFI; a "verification" script whose assertions cannot fail
   (e.g. the email's Python rig, which computes values and prints
   `VERIFICATION_SUCCESS = True` unconditionally — our tests must be capable
   of going red, and reviewers must be able to say how).
3. **Reference-first.** Every optimised or accelerated path ships with a naive
   reference implementation and a test that compares them on adversarial as
   well as random inputs (empty, single-element, all-equal, NaN-containing
   where floats are involved, gate empty/full).
4. **Bench hygiene.** Release profile; warm-up; interleaved A/B; sample counts
   and spread reported (median + p95 minimum); machine, OS, toolchain, and
   workload parameters committed with the results; a bench whose harness
   cannot prove both sides did the same counted work is invalid (§5.1).
5. **Concurrency hygiene.** The ring's protocol is stated as invariants in
   `DESIGN.md`; `loom` models run in CI; any change to an `Ordering` is a
   review flag requiring a sentence of justification in the PR.
6. **Negative results are results.** A bench that refutes the project's own
   hypothesis is committed with the same care as a confirming one, and the
   README is updated to match. Deleting or quietly re-runing-away a negative
   result is the one unforgivable sin in this repo.
7. **Process in the body.** Each version's work updates a `## Process log`
   section in its PR description *and* a running `NOTES.md`: decisions and
   their reasons, dead ends with the evidence that killed them, deviations
   from this plan with the reason for deviating. A result without its process
   is a claim, not a record.

---

## 9. Risks

| Risk | L×I | Mitigation / kill criterion |
|---|---|---|
| Rolling simply doesn't beat batched on real arithmetic (scheduler overhead, cache effects) | Med × High (it is the thesis) | §5.1 includes rolling-hostile scenarios; negative result = stop after v0.1 write-up. Pre-committed in §5.6 |
| Synthetic workloads don't predict sensor/model behaviour | High × Med | Keep workloads parameterised by slice size/period so the crossover regime is mapped, not a point estimate; v0.3 replay of recorded traces before any live-sensor conclusion |
| Sheaf-as-consensus is too weak to matter for real multi-model state | Med × Med | It is scoped as the consensus special case (§5.3); if no consumer needs even that, the module stays a small, tested library piece and is not grown speculatively |
| Persistent-kernel spike harms the shared Thor (thermals, watchdog, starving Casey's own work) | Low × High | v0.2 runs only in parent-lane-booked windows on the box, sustained-run thermal/power reporting is part of spike 2, kill on any watchdog/preemption weirdness |
| NVRTC-from-Rust plumbing eats the whole v0.2 budget | Med × Med | Spike 1 is time-boxed by the parent lane; kill criterion stated in §6; CPU crate remains a complete, publishable result without it |
| Scope creep back toward the email's full cathedral (JIT mutation, DMA, display) | High × Med | §7 non-goals are explicit; any addition requires amending this plan in a reviewed PR with its own falsifiable §5-style test design first |
| Private-repo drift: "temporary" private becomes permanent and the work is lost to the public shelf SI-Thor was created for | Med × Med | §10's public gate has objective criteria; the parent lane reviews them at each version tag |
| Licence/IP ambiguity from building on an LLM-chain seed | Low × Low | The seed is Casey's own emailed notes; the repo implements graded *ideas* with original code and cites the seed as provenance in the founding commit. No code is copied from the email (there is no working code in it to copy) |

---

## 10. Going public — the gate (Casey's stated endgame)

Private → public when **all** hold, reviewed by Casey:

1. v0.1 gate (§5.6) met, and v0.2 either met its gate or was formally killed
   with its findings written up — i.e. the repo is *working and useful on our
   Thor*, or honestly documents why the Thor part is not.
2. Documentation pass: README leads with what it is, the four metrics, and the
   measured results (including losses); `PLAN.md`/`DESIGN.md` updated to match
   what was actually built, with deviations recorded, not airbrushed; banned
   phrases (§8.1) swept.
3. `results/` complete enough that a stranger can reproduce the headline
   numbers from a clean clone.
4. Licence chosen by Casey and added; provenance note (seed email, date)
   included.
5. Visibility flipped by Casey or at his explicit instruction — never as a
   side effect of another task.

---

## 11. Open questions (for Casey / the parent lane, not blockers for v0.1)

1. Repo name: `rolling-perception` as proposed in §4?
2. Which real workload should v0.3's first live lane be — camera or audio?
   (Determines which recorded-trace format v0.1's replay seam should favour;
   v0.1 itself is unaffected.)
3. Is there an existing fleet trace (Radio Room audio, a JEV stream, a Foundry
   render loop) whose recorded data would make the most honest v0.3 replay?
4. Licence preference for the public gate — MIT, Apache-2.0, or dual?

---

## 12. Process log (this plan)

- **2026-11-01 — Lane PLAN created.** Read the full seed email and the parent
  lane's verified critique; independently re-checked the four load-bearing
  code findings (sleep-as-latency, mock cubins, clamp-as-sheaf, PIR wrap) in
  the saved mail copy before relying on them. Drafted this plan + `DESIGN.md`.
  No repo created, nothing pushed, Thor untouched — per lane instructions.
- **Decision:** CPU-first sequencing (§0 dead end B). **Reason:** falsifiability
  and a reference implementation; CUDA noise would otherwise be indistinguishable
  from scheduler signal.
- **Decision:** counted lineage replaces PIR, PIR kept as an autopsy (§5.4).
  **Reason:** three independent failure modes, each unit-testable; an exact
  scheme costs ~130 bytes/slot, which the benches must — and can — price.
- **Decision:** sheaf scoped to graph consensus (§5.3). **Reason:** it is the
  only special case whose energy and convergence we can state, test, and
  bench today; general restriction maps without a concrete consumer would be
  the email's gesture repeated in our own handwriting.
- **Dead end preserved:** the email's MPMC ring protocol (§3 row 2) — analysed,
  found unsound, narrowed to SPSC; the analysis is in `DESIGN.md` §3.3 so the
  next reader inherits the reasoning, not just the conclusion.
