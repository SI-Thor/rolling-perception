## QUESTION 2 — SESSION BUDGETING (NVENC)

**0. The cap, defended.** Jetson-class NVENC exposes a fixed session count independent of GPU compute — panel round 1's finding that "sessions break before compute" is exactly the Orin/Thor part family. Design assumption: **8 concurrent 1080p30 H.265 encode sessions** on the Thor's hardware encoder (TO-MEASURE at Slice 2's transcode bench, which already owes this number per §1.2). I design to 8, not 10 or 12, because: (i) the bench hasn't run, (ii) mixed-resolution sessions (1080p + 720p thumbnails) fragment the budget unpredictably, and (iii) the tenancy ruling (2026-10-28) requires headroom for Casey's own work. **Platform ceiling: 6 of 8.** The 2 held back are the yield contract's session face — Casey's direct use outranks the platform, same as the GPU ladder.

**1. (a) Allocation policy — reservations and priority.**

| Tier | Consumer | Reserved sessions | Notes |
|---|---|---|---|
| **P0** | Camera ingest (perception input) | **2** | Inviolable. See §2 — the reservation is a *worst-case floor*, not steady-state demand. |
| **P1** | Live human viewing (transcode) | **2** | The "house is watching" pool. Direct-play consumes **0** sessions and is the primary lever — the spec's direct-play-first rule (§1.2) is a *session* rule, not a bandwidth rule. |
| **P2** | Thumbnails, ingest-time derivatives | **0** (1 burst slot) | Best-effort, batched during scans, throttled to 1 session, always deferrable. |
| **P3** | Library backfill pre-transcode | **0** | Slack-eater. Eats whatever P0–P2 leave. First to die. |

Within P1, the 2 sessions resolve contention by ledger priority (the §3.4 tuner rule generalised): a profile actively watching beats a background pin; ties by most-recent-start. A third transcode request queues, not steals. **A queued transcode is a visible state** ("waiting for an encode slot — try direct play") — never a silent stall.

**2. (b) Degradation order — perception is never starved.**

The critical mechanism: **camera ingest should consume zero sessions in steady state.** Cameras deliver H.264/H.265 natively; the adapter *remuxes*, it does not re-encode. Re-encode happens only where a converter is genuinely required (Amendment 1's converter doctrine: a missing converter is a platform bug). So P0's 2 reserved sessions are the floor for the *converter case* — a camera whose transport/codec forces transcode, or a re-mux into the ledger's canonical container. The change-detection path (reflex diffs, µs-class CPU) needs no session at all; only its input frames do.

When the pool exhausts, shed in this strict order:

1. **P3 backfill pauses** (the yield ladder's L1, unchanged). Logged, resumes from ledger state.
2. **P2 thumbnails throttle to 0** — scans show "thumbnail pending", never block.
3. **P1 second viewer degrades to a lower rung** (1080p→720p) rather than losing the session — a degraded picture beats a dead one. If the client can't accept the rung, the stream queues.
4. **P1 first viewer is the last human to lose a session.** Never shed below one live viewing session while a human is watching — that is the product.
5. **P0 is never shed.** If P0's reservation is somehow breached (a converter bug, a pathological camera), ingest sheds *frames* per §3.2 (newest wins, drops receipted) — it never sheds the session. Perception degrades in resolution, never in liveness — the §2.3 L3 rule, applied to sessions.

Foreign/interactive load triggers the tenancy ladder: platform drops to its 6-session ceiling immediately, and if Casey's own work claims sessions, P3→P2→P1-second-viewer shed within one scheduler tick, P0 held to the last.

**3. (c) Plain-language expression.**

The spec's budget knobs compile to invertible terms. Sessions are shown as **"screens"**
