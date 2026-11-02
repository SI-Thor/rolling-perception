# Attacking the transcode plan

## What breaks first

**NVENC session count, not compute.** Thor's NVENC is a fixed-function block with a hard session cap (historically 2–8 concurrent encode sessions on Jetson parts, and the cap is per-process/context in some driver versions). The moment the player does "one live transcode" *plus* the ingest pipeline's own encode path (camera re-mux, HLS segment packaging, thumbnail/sprite generation for the shelf, DVR ring writes), you are not at 1 session — you are at 3–5. The failure is not slow frames; it is `NV_ENC_ERR_INVALID_DEVICE` / session-open failure, which surfaces as a player that opens a black tile while the log says the GPU is 40% idle. That is the first thing to break, and it breaks *before* any bandwidth or SM contention.

**Second: the unified-memory allocator under encode + perception.** NVENC needs pinned host-visible buffers; I-JEPA embed calls need large weight + activation allocations. On a 122 GB unified pool the *capacity* is fine but the *fragmentation and pinning* is not: a long-lived encode ring (say 8 s × 4K × 4:2:0 ≈ 500 MB pinned) plus a 173 ms embed burst that allocates several GB transiently will start failing `cudaMalloc` at ~90% pool occupancy even though `nvidia-smi` shows free memory. This shows up as perception latency spikes (embed median 173 ms → p99 seconds) exactly when someone starts a transcode — i.e., the "silent unless meaningful" feed goes quiet because the decision plane is starving, not because nothing changed. That is the worst failure mode: **a correctness bug that looks like calm.**

**Third: SM contention is real but late.** 20 SMs shared between NVENC's feed (NVENC does not use SMs, but the *pre/post* — color convert, scaling, mux — does) and I-JEPA's conv/attention. Expect the 173 ms embed to degrade ~1.5–2× under a 4K transcode with scaling. This is the *last* thing to break and the easiest to bound.

## What to benchmark before writing a line of player code

1. **Session cap, empirically, per driver version.** Open N concurrent `nvenc` sessions of 1080p30 H.264 until failure. Report the exact N and the error code. Do this with the perception pipeline *running* and *idle* — the cap may differ if the driver shares a context.
2. **Transcode throughput vs. ladder, measured, not spec'd.** For each of {1080p→720p, 1080p→480p, 4K→1080p}: fps sustained, GPU util, NVENC util, and *embed latency delta* on a concurrent I-JEPA call. The spec's "NVENC sessions vs bitrate ladders unmeasured" is the single biggest hole; fill it with a 2×2 (resolution × concurrent perception on/off).
3. **Pinned-memory headroom.** Run the encode ring at max DVR depth + a worst-case embed burst; record the `cudaMalloc` failure threshold as a % of pool. This sets the yield-ladder trigger.
4. **Per-camera sustained rate** (also TO-MEASURE) — because if 8 cameras each push 4 Mbps and the player wants one 4K transcode, the *ingest* encode path is already eating sessions before the player asks.
5. **Cold-start latency** of a transcode session (session open + first keyframe) — this determines whether "open player" can be synchronous or must show a poster.

## Sane degradation ladder (ordered, with triggers)

The 4-step yield ladder is for *the owner's work*; transcode needs its own, and it must be **demand-ordered, not FIFO**, because a live player is latency-critical and backfill is not.

1. **Drop to direct-play / remux.** If the client can decode the source codec, never transcode — remux only (no NVENC session). Trigger: codec/container mismatch only. This should be the default path, not the fallback.
2. **Downscale the ladder, not the session count.** 4K→1080p becomes 1080p→720p. One session, lower pixel rate, frees SM headroom for perception. Trigger: NVENC util > 80% or embed p99 > 2× median.
3. **Shed perception on non-priority lanes.** The "sip on the nursery" knob already compiles to numbers — reuse it: when transcode demand spikes, decision-plane budget for low-priority streams drops to zero (reflex-only, feed-only). This protects the trust spec's "≤1 false event/stream/day" because reflex-only never pushes alerts anyway.
4. **Refuse new transcodes, queue with a visible poster + ETA.** Never silently fail to a black tile. The shelf shows "transcoding, ~Ns" derived from measured cold-start. This is the honest degradation.
5. **Kill backfill first** (already in the 4-step ladder) — but note backfill is *overnight*, so it should rarely collide; if it does, it dies before any of the above.
6. **Last resort: unload the embedding model** (already step 4 of the yield ladder) — but this must be *after* refusing new transcodes, because unloading the model makes the "what changed" feed blind, which is the product's whole point. Reorder the existing ladder: transcode refusal should sit *above* model unload.

**The adversarial fix the spec is missing:** the trust spec says "alerts may never fire off the cheap diff gate alone" — good. But the transcode plan has no equivalent invariant. Add one: **a transcode session may never be opened if it would push embed p99 past the point where the decision plane misses its per-stream period.** Measure that threshold (item 2 above), compile it to a number, and make the player respect it. Otherwise the failure is invisible: the feed goes quiet, the user trusts the silence, and the silence is a lie.
