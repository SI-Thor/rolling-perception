# rolling-perception — phase-interleaved vs. batched, measured

A standalone, dependency-free (std-only) Rust experiment distilled from the
"Rolling perception [muse]" email (2026-11-01), specifically its
*Sequential Phase-Interleaved Rolling Pipeline* and *Cascading Cognitive
Substrate* sections.

The email's code simulated everything (`sleep` stood in for GPU latency,
NVRTC/CUPTI calls were commented out, cubins were mock bytes). This crate
keeps only the claim that can be tested honestly on a CPU today, and tests
exactly that claim.

## The claim

> On a single sequential execution resource, if stages become ready at
> staggered times and each stage's result is useful on its own, then
> emitting an output **per stage completion** (rolling) gives a smaller
> time-to-first-output and a denser output stream than waiting for all
> stages and emitting **one** output per frame (batched) — for
> *identical* work.

That is the whole claim. This crate makes **no** claim about GPUs,
persistent warps, CUDA, NVRTC hot-swapping, sheaf Laplacians, or
sub-microsecond anything. Those parts of the email are not implemented
here (sibling experiments may address the substrate pieces separately).

## Design

**Lanes** (`default_lanes()`, in cascade order, as named in the email):

| lane | work |
|---|---|
| `perception` | matvec kernel, dim 96, 28 repeats |
| `decision` | matvec kernel, dim 96, 12 repeats |
| `attention-director` | matvec kernel, dim 96, 18 repeats; **writes `Manifold::focus`** from its result (the Nemotron-Mini "director" role) |
| `diffusion-step` | matvec kernel, dim 96, 36 repeats (one step, not a full generation) |
| `audio-skald` | demuxes 1024×2 interleaved f32 PCM into per-channel buffers, per-channel energy, small matvec over channel features — the honest CPU version of SkaldAudio (no DMA claim) |

- Work is **real**: a matrix–vector kernel over owned, deterministic
  (LCG-filled) data, with the output fed back (`tanh` chain) so repeats
  cannot be hoisted away, and checksums accumulated through
  `std::hint::black_box`.
- Both schedulers execute the lanes **in the same order, with the same
  manifold updates**, so the total checksum must match between them
  (a test asserts this). Scheduling/emission is the only variable.
- Perception and diffusion read `Manifold::focus` (set by the director)
  as their starting row — the cascade coupling from the email, in
  miniature and in the open.

**Schedulers**

- `BatchedScheduler` (`run_batched`): per cycle, wait for the last
  lane's sensor, run all lanes, emit **1 output**.
- `RollingScheduler` (`run_rolling`): per cycle, lane *i* starts when
  its own sensor is ready, run it, **emit immediately** — `lanes`
  outputs per cycle.

**Sensor timing — the one modelled part.** Sensors becoming ready is
modelled with `sleep` until `cycle_start + i * sensor_stagger` (default
stagger 400 µs in the bench, 300 µs in the tests), and is labelled
`MODELLED SENSOR PERIOD` at every call site in `src/lib.rs`. Sleep is
never used as compute. If a lane's real work already takes longer than
its offset, the rolling scheduler waits not at all — which is precisely
the regime the email argues for (compute ≪ sensor period).

**Metrics** (bench, `src/main.rs`): time-to-first-output,
outputs/sec, and mean / p95 inter-output interval, all from
`std::time::Instant`. The bench runs each scheduler twice and prints
both passes.

## Run it

Run these **from this crate's directory** (`crates/rolling-perception/`),
or prefix with `-p rolling-perception` from the repository root.
On the Thor over SSH, first:
`export PATH=$HOME/.cargo/bin:/usr/local/cuda/bin:$PATH`
(cargo is not on the default PATH there).

```sh
cargo test                                              # 6 tests, this crate only
                                                        # (from the repo root, cargo test runs all 75)
cargo run --release                                     # 120 cycles, 400 µs stagger
cargo run --release -- --cycles 50 --stagger-us 0       # no sensor stagger
cargo run --release -- --cycles 50 --stagger-us 2000    # sensor-dominated regime
```

Expected output shape (numbers vary by machine; the invariants don't):

```
batched  ttfo=... us  total=... ms  outputs=120  ...  checksum=345101.1999
rolling  ttfo=... us  total=... ms  outputs=600  ...  checksum=345101.1999
---
ttfo ratio (batched / rolling): <about 3x-16x>
outputs ratio (rolling / batched): 5.0x
checksum delta |batched - rolling|: 0.000000
```

If the checksum is not `345101.1999`, or the delta is not exactly
`0.000000`, something is wrong — the two schedulers must do identical
work (that identity is also asserted by a test).

## What would falsify the claim

1. **TTFO test fails.** If, under the stated parameters, rolling
   time-to-first-output is not clearly below batched (the test demands
   `< batched / 2`), the structural argument is wrong for this
   workload shape — e.g. if the first lane's work dominates the whole
   cycle, batching costs almost nothing in TTFO.
2. **Zero-stagger collapse.** With `--stagger-us 0` *and* a hypothetical
   scheduler that could run all lanes truly in parallel (this crate is
   deliberately single-threaded/sequential), batched TTFO could match
   rolling. That would show the advantage is a property of a
   *sequential* resource + staggered readiness, not of "rolling" in
   the abstract. The crate's claim is explicitly scoped that way.
3. **Intermediate outputs are useless.** The bench counts emissions,
   not usefulness. If a real consumer (a controller, a renderer)
   cannot act on a perception-only or decision-only output — if it
   needs the full cascade every time — then rolling emits more
   *often* but delivers nothing sooner. That is an application-level
   falsifier this crate cannot rule out; it must be tested downstream
   with a real consumer.
4. **Checksum divergence.** If the two schedulers' checksums diverged,
   the comparison would be invalid (different work), and the
   same-work test would catch it.

## Known limitations

- Single-threaded CPU model of a claim the email makes about a GPU.
  It validates the *scheduling arithmetic*, not Thor performance.
- Sensor readiness is modelled, not measured from real devices.
- Work per lane is synthetic matvec/PCM, not real models; lane costs
  are configurable (`repeats`, `dim`, PCM size) so the experiment can
  be re-run in regimes where the claim should weaken (e.g. make
  `perception` 10× the other lanes combined and watch the TTFO
  margin shrink toward the falsifier in §1).
