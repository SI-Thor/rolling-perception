**The lie in “embed-seconds” is that it treats perception as a homogeneous, linear, user-meaningful currency. It is none of those things.**

## 1. Where the model lies to the user

### A. “Embed-seconds” hides the actual cost stack
An “embed-second” is only the decision-model image-embedding time. It excludes:

- Reflex CPU tile-diff/hash cost, which can dominate on high-resolution or high-FPS camera lanes.
- Decode/transcode cost, which is unmeasured on Thor and is likely the real bottleneck for multiple 1080p/4K IP cameras.
- Reflective judge calls at 0.47s each, which are not embed-seconds but still consume wall-clock and budget.
- Model load/unload, VRAM pressure in 122GB unified memory, PCIe/NVENC contention, and thermal/SM clock throttling on 20 SMs.
- Storage and ledger write cost.

If the UI says “front door: 300 embed-seconds/hour,” the user has no idea whether that means:

- 1,732 tile embeds/hour at 173ms median, or
- far fewer actual embeds because tail latency, batching, or contention inflates effective time, or
- that decode already ate 80% of the GPU and embedding is stalled behind it.

**Fix:** meter the full metered resource: GPU SM-seconds, NVENC/NVDEC sessions, CPU reflex seconds, judge calls, and wall-clock latency per lane. Show a stacked “cost per stream-hour” breakdown, not just embed-seconds.

### B. It implies spending more embed-seconds means better awareness
It does not. The cheap diff gate is a **ranker, not a separator**. Skipped tiles drift 0.20 in embedding space; embedded tiles drift 0.48. That means the gate is selecting tiles that are already more unusual, not cleanly separating “changed” from “unchanged.” So:

- Raising the embed budget may embed more tiles, but not necessarily the *right* tiles.
- Lowering the budget may skip subtle but meaningful changes that the gate ranks low.
- The 54% overall embed reduction and 88% reduction on gradual scenes are efficiency numbers, not accuracy guarantees. The controlled 0.60 → 1.00 precision gain from Laplacian smoothing was on controlled ground truth, not uncontrolled household reality.

**Fix:** show budget knobs alongside expected precision/recall bands, not just spend. If precision is unmeasured in uncontrolled settings, the knob must say “unvalidated,” not “sip” or “spend freely.”

### C. “Spend freely / sip” is false granularity
Plain language is fine; the lie is that it compiles to a single number. “Spend freely on the front door” could mean:

- 10 embeds/minute at 1080p,
- 2 embeds/minute at 4K tiles,
- 0 reflective calls,
- or unlimited embeds
