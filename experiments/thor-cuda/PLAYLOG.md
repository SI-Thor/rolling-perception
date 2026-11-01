# Thor play log — rolling perception, first hands-on session

Date: 2026-11-01 (AKST) · Box: AGX Thor, sm_110, CUDA 13.2, driver 595.78 ·
Location on Thor: `~/rolling-perception-play/` · All experiments are
single-shot, explicitly started and stopped; nothing is left resident.
GPU before starting: 0% util, 37 °C.

## exp1 — Rolling vs batched (GPU streams)

Same 4 lanes, same work, same 5 ms modelled sensor stagger. Batched waits
for all arrivals, then runs all lanes and emits one output. Rolling launches
each lane on its own stream the moment it arrives.

| Config | Batched first (=only) output | Rolling outputs | First-output gain |
|---|---|---|---|
| Big lanes (1M elems × 60 reps) | 21.41 ms | **5.74, 11.04, 16.32, 21.28 ms** | 3.7× |
| Small lanes (64K elems) | 20.46 ms | **5.27, 10.21, 15.41, 20.48 ms** | 3.9× |

Rolling output spacing ≈ max(stagger, per-lane kernel time): compute-bound
in the big config (~5.3 ms spacing), arrival-bound in the small config
(~5.1 ms spacing). Total completion is the same (~21 ms) — rolling does not
make the whole batch faster, it makes perception *arrive continuously*.
That is the email's core claim, and on this hardware it is true.

**Process note (a rig that lied, and how it was caught):** the first two runs
showed all rolling outputs bunched at ~20.3 ms and a ~1.0× "gain". The
outputs looked wrong (identical for two very different work sizes), so the
bench was re-read: it timestamped outputs with the host clock *after* a
synchronisation loop that itself only started after the last launch — it
measured when the host observed completion, never when completion happened.
Fixed by reading the CUDA events' own GPU timestamps
(`cudaEventElapsedTime` from a start event). The bunched numbers were the
bench, not the hardware. (A second build failure in between — a stale
binary silently re-ran after a macro name collision broke compilation —
is why every run here is from a freshly verified build.)

## exp2 — NVRTC hot-swap (CascadeJIT, honest version)

- v1 (`out = in*2`) compiled by NVRTC for `compute_110` + loaded via driver
  API: **54.4 ms**, PTX 909 B; ran in 49 µs, out[0]=6.0 ✓
- v2 (`out = in² + in`) compiled at runtime: **29.6 ms**, PTX 917 B; host
  swapped the `CUfunction` it launches — between launches — ran in 44 µs,
  out[0]=12.0 ✓

Swap is real at launch granularity. Compile (~30–55 ms) happens off the run
path. There is no mid-kernel splicing; that part of the email stays dropped.

## exp3 — Persistent kernel + mapped-memory control (CudaClaw, honest version)

One launch (2 blocks, 18 of 20 SMs left free) stayed resident and served
**300 work requests** through a control struct in host-pinned *mapped*
memory (per the feasibility finding: control slots belong there, not in
managed memory, because `directManagedMemAccessFromHost=0`).

- Request→ack latency: **mean 4.8 µs, p50 4.6 µs, p95 5.5 µs, max 12.1 µs**
- Behaviour swap mid-run: `scale` changed 1.0 → 10.0 at request 150, no
  relaunch; final buffer 1659.0 = expected 1659.0 ✓
- Clean stop via flag; device synchronised. Total wall 1.6 ms for the
  request loop (the kernel's spin is the waiting, not the work).

The email claimed "<100 ns warp catch" — the honest measured number for a
full host→GPU→host round trip through mapped memory is ~5 µs. Still fast
enough to be the rolling tick substrate; just not the fantasy number.

## exp4 — Viewport gating (FluidAttn, two versions — the lesson is the difference)

Field 4096×4096 (16.8M elems), ROI 512×512 = 1.56% of the field. Both
versions verified clean: inside-ROI output identical to full-frame, and a
sentinel check proved **zero** outside-ROI elements were touched.

| Version | Time/frame | Speedup |
|---|---|---|
| Full frame | 0.90–1.08 ms | — |
| Gated, same grid, blocks early-exit outside ROI | 0.68 ms | 1.3× |
| Gated, **grid launched only over ROI tiles** | **0.006 ms** | **192×** |

Early-exit gating barely helps: you still pay to launch and schedule
65,536 blocks. Gating has to shrink the launch itself. Any v0.2 design
carries this as a rule: *the gate decides what is launched, not what
returns early.*

## What this session established

1. The rolling claim survives contact with the hardware (exp1) — as a
   latency-to-first / continuity win, not a throughput win.
2. Runtime compilation + swap works today on sm_110 (exp2), at launch
   granularity, ~30–55 ms compile off-path.
3. A persistent kernel with mapped-memory control is a ~5 µs round-trip
   substrate and stops cleanly (exp3) — soak/thermals still untested, per
   FEASIBILITY.md; it was run for milliseconds here, not hours.
4. Gating is a launch-shape decision, not a branch (exp4).
