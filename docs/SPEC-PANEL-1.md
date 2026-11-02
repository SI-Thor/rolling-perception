# Panel 1 — outside critique of the Confluence spec (refereed)

*2026-11-01. Four hosted models on DeepInfra (DeepSeek-V4.1-Flash,
Hy4-preview, MiMo-V2.6-Pro, Seed-2.0-mini) were given one identical
design brief and four adversarial questions. 16/16 answers, total
cost $0.034. Raw answers: `docs/panel-1/`. Panel output is testimony,
not measurement — this file is the referee's record of what
survives, what is amended, and what is rejected, with reasons.*

## Cache economics, honestly

The brief was a condensed ~700-token prefix. Cached-token hits:
DeepSeek 640 on calls 2–4, Hy 512, MiMo 688 on calls 3–4, **Seed 0
on every call** (its cache never engaged). At this prefix size the
saving is pennies; the mechanism pays at full-spec scale (~25k
tokens), which is how round 2 should run. Seed also invented
hardware facts (it repeatedly gave the Thor "2 SMs"; the brief and
the box say 20) and fabricated statistics (false-positive rates to
one decimal from no data). Its answers are used only where another
model independently converged on the same point.

## Accepted — amendments to the spec

1. **NVENC sessions break first, not compute** (DeepSeek, Hy, MiMo,
   convergent). The platform itself consumes sessions (ingest
   re-mux, thumbnails, DVR writes), so "one live transcode" is
   really 3–5. *Amendment: the Slice-2 bench order is reversed —
   empirical session-cap test (open sessions to failure, record N
   and the error) runs before any player work, and sessions join
   the budget as a metered resource.*
2. **Starvation must not look like calm** (DeepSeek). Under
   contention, embed latency spikes and the change feed goes quiet
   because the decision plane is starving — a correctness failure
   wearing the product's core promise. *Amendment: every lane
   publishes a health heartbeat (embed p50/p99, queue depth) into
   its ledger; silence is only presented as "all normal" when the
   lane reports healthy. This extends §C's "confident silence is
   the worst failure" from ingest to perception.*
3. **The budget meters cost, not coverage** (all four, convergent).
   A stream can be 100% within budget and 30% covered; low budgets
   bias attention toward high-contrast motion, so a plain-language
   knob silently buys a *biased* watcher. *Amendment: beside
   embed-seconds spent, every stream shows estimated coverage
   (nominated tiles embedded / nominated), and each knob's compiled
   form must be invertible into detection terms a user can reason
   about — refresh period and the smallest reliably detected event
   class (MiMo's formulation). The full cost stack (SM-seconds,
   NVENC sessions, reflex CPU, judge calls) is metered, with
   embed-seconds remaining the headline unit (Hy).*
4. **Trust needs three numbers, not one** (DeepSeek, Hy, MiMo,
   convergent). (a) Precision alone hides the trust-killer: the
   *missed* event. The spec had no recall term. *Amendment: recall
   probes — known synthetic events injected through ingest at a
   low rate, detection measured, recall@probe reported per stream.*
   (b) At household label rates the 0.9 gate is statistically
   underpowered (n=4 flips it). *Amendment: precision is reported
   with its n and interval; unknown precision defaults to
   feed-only.* (c) 1 false event/stream/day × N streams is N/day
   of household noise. *Amendment: a household-level budget
   (≤1 push-worthy false event/day across all alerting streams)
   sits above the per-stream target, and precision is stratified
   by hour/regime where labels allow.*

## Accepted into the roadmap (not v1)

- **"Why did you alert me?" evidence replay** (DeepSeek, Hy): a
  per-event evidence pointer and a short scrub of gated tiles +
  scores. Cheap — replays stored artifacts — and it makes the
  correction loop auditable instead of blind taps.
- **Retrieval over the ledger** ("find the thing I half-remember")
  (MiMo, Hy, Seed): the change feed is a temporal index; month 2
  asks historical questions. Text-side, cheap, fits the ledger.
- **Budget profiles** (away / night / guest) with hysteresis
  (DeepSeek): named profiles as ledger records; minimum dwell to
  prevent thrash; backfill only under away/night.

## Refused, with the panel's help

- **Always-on ambient microphone perception as a first-class
  stream** (Hy's nomination for refusal; the referee agrees):
  consent and privacy posture break the local-first promise. Audio
  lanes stay limited to streams the household explicitly points at
  the box (radio, podcasts, a camera's own audio), never ambient
  listening.

## Noted, not adopted

- MiMo's "the yield ladder is a kill, not a yield" — partially
  fair (model unload does impose a reload tax on resume). Recorded
  as a Slice-3 measurement (resume latency after a full yield)
  rather than a redesign: the ladder's job is that the owner's work
  never waits, and a ramp that delays him is worse than a cliff
  that delays the platform.
