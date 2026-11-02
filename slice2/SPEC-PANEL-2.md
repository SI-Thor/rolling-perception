# Panel 2 — outside critique of the Confluence spec (refereed)

*2026-11-01 (AKST). Four hosted models on DeepInfra, ONE question
each, with the FULL spec as the shared prefix — SPEC-STREAM-PLATFORM
+ Amendment 1 + Amendment 2, 92,681 bytes ≈ 23.1k tokens, byte-
identical across calls, question appended last. Raw answers:
`slice2/panel-2/`. Panel output is testimony, not measurement —
this file is the referee's record.*

## Cache economics — the round's own negative result

Round 2 was designed on the assumption that "the first call pays
the prefix, the rest ride the cache." **Measured: cached_tokens = 0
on all four calls.** The flaw in the design: prompt caching is
per-model, and round 2 gave each model exactly one call, so no
model ever made a second call that could ride its own cache.
Round 1's hits (DeepSeek 640, Hy 512, MiMo 688) came from its
4-questions-per-model shape. The miss cost almost nothing here —
full-price total for the round was **$0.0537** — but round 3's
design must either return to ≥2 questions per model or price each
model's prefix at full rate and stop calling it a cache game.

| Call | Model | Question | Prompt tok | Cached | Completion tok | Cost |
|---|---|---|---|---|---|---|
| 1 | DeepSeek-V4.1-Flash-1017 | Q1 presence brain | 23,127 | 0 | 1,353 | $0.0027 |
| 2 | MiMo-V2.6-Pro | Q2 session budget | 23,252 | 0 | 2,500 (cap) | $0.0110 |
| 3 | Hy4-preview | Q3 synthesiser risk | 23,087 | 0 | 6,853 (4,800 reasoning) | $0.0364 |
| 4 | Seed-2.0-mini | Q4 technician failure | 24,098 | 0 | 3,212 (2,507 reasoning) | $0.0037 |

Referee flags carried from round 1: Seed's vendor-specific claims
are used only where the general shape survives without them. New
flag: MiMo's Q2 answer was **truncated mid-sentence** — it spent
1,500 of its 2,500 completion tokens reasoning and hit the cap in
its §3; its plain-language section is refereed as partial, not
complete.

## Q1 — Presence brain (DeepSeek)

**Points raised.** An 8-mode failure taxonomy for small-brain
presence: wrong-line selection (the observed failure), stale-line
selection, confident paraphrase drift, silence-as-answer (retrieved
nothing → says "nothing," when the honest answer is "not watching
closely"), lineage erasure (evidence class dropped in speech),
cross-stream conflation, fabricated specificity, refusal collapse.
Fixes ranked by cost-to-trust: (1) **verdict-only grounding** — the
brain never sees the ledger, only pre-selected published verdict
records whose fields are the sentence's slots; (2) a **deterministic
selector** owns ledger access for open questions and hands the brain
a closed context with citation ids the renderer resolves; (3)
**escalation** to a bigger brain on named triggers (failed
self-check — a cited id not in context, a number in no record —
low selector confidence, an explicit "why"), every escalation
logged; (4) confidence-gated speech carrying the verdict's evidence
class; (5) corrections-fed selector tuning, later.

**Accepted.**
- **Verdict-only grounding is the presence architecture.** It
  correctly reframes the acceptance-test failure: the 1.2B model
  didn't fail at language, it was handed a retrieval job. The brain
  is a *verbaliser* of records the perception plane already
  published; selection is not its job. This kills taxonomy modes
  1, 2, 5, 6, 7 by construction, and it matches the platform's own
  doctrine — the ledger is the system's text, a small model free-
  reading it is an unconverted seam (Amendment 1 §7 corollary:
  retrieval discipline is a converter, built once).
- **The deterministic selector + citation-by-id for open
  questions**, with "I can't answer that from what I watch" as a
  first-class reply. Its coverage is the honest limit of presence's
  knowledge, stated rather than papered over.
- **Escalation triggers and the cheap self-check** (cited id ∉
  context, spoken number ∉ any record → don't speak, escalate or
  abstain). The self-check is string matching, not a judge — it
  obeys the fleet rule that judges never sit alone on a gate.
- **Silence-as-answer joins Panel 1's starvation amendment**: a
  presence answer of "nothing changed" must be backed by the lane's
  health (heartbeat fresh, coverage known), or the answer is the
  coverage statement instead. Cross-round convergence with Q3's
  shed-blindness (below) — three independent arrivals at "quiet
  must carry its basis."

**Refused.** Nothing in DeepSeek's answer is refused. Its Rank 5
(learn-from-corrections tuning loop) is deferred, not refused —
Slice 1's corrections file exists; the tuning loop is a later
investment, as DeepSeek itself ranks it.

## Q2 — Session budgeting (MiMo)

**Points raised.** Design to a conservative cap (it proposes 8
sessions, platform ceiling 6, 2 held back as the yield contract's
session face); tiered allocation — P0 ingest reserved, P1 live
viewing, P2 thumbnails burst-only, P3 backfill slack-only; the
load-bearing mechanism: **ingest should consume zero sessions in
steady state** (cameras deliver H.264/H.265 natively; the adapter
remuxes, re-encode only where a converter is genuinely required),
so P0's reservation is a floor for the converter case, not a
standing draw. Direct-play-first reframed as a *session* rule, not
a bandwidth rule. Degradation order: backfill pauses → thumbnails
to zero → second viewer drops a rung (720p beats dead) → first
viewer last; ingest under breach sheds *frames* (receipted), never
the session — perception degrades in resolution, never in liveness.
A queued transcode is a visible household state, never a silent
stall. Plain-language form (§3, truncated): sessions shown as
"screens."

**Accepted.**
- **Remux-not-re-encode as the steady state.** This dissolves most
  of the session problem rather than rationing it, and it is the
  converter doctrine applied to the serve plane: a session spent
  re-encoding a native stream is a missing-converter bug with a
  meter running.
- **Direct-play-first is a session rule** — accepted as a wording
  amendment to §1.2's rule, because sessions are the scarcer
  resource.
- **Degradation order and the platform ceiling.** Shed order
  (backfill → thumbnails → second viewer's rung → never ingest,
  never the last viewer) extends the existing yield ladder to the
  session resource without new machinery, and holding sessions back
  for the owner's own use is the tenancy ruling applied to a new
  meter — consistent, not novel.
- **Queued-is-visible.** A waiting state the household can read,
  never a stall — the same honesty rule as Panel 1's heartbeat
  amendment, now on the serve plane.

**Refused / held.**
- **The number 8 is refused as a design constant.** It is an
  assumption about Jetson-family session behaviour; this platform's
  own NVENC bench (running as this panel sat) owns the measured cap
  and its error text. The policy is written cap-relative (platform
  ceiling = cap − 2, tiers as above) and the bench's number drops
  in when it lands. Panel testimony does not set hardware facts —
  the same rule that disqualifies Seed's inventions.
- **§(c) is refereed as incomplete** (truncated, see header). The
  "screens" unit is directionally right — sessions are countable in
  household objects — but the compiled knob forms must be re-derived
  when the bench number exists, not adopted from half a section.

## Q3 — Synthesiser risk (Hy4)

**Points raised.** Top three production failures of the
extrapolated-world layer, each with mechanism, household
manifestation, and the ledger evidence that catches it:
1. **Consistency lie** — the state is served as "now" while its last
   correction is old or its tolerance narrower than truth; worst
   variant is *shed-blindness* (ingest shed everything in a
   saturation window, the error model never saw a correction, the
   band never widened, the feed stayed silent). Evidence: state.txt
   must carry `last_correction_stamp`, `extrapolation_age_ms`,
   `staleness_class` (fresh|extrapolating|stale|dead), trailing
   `shed_fraction`; feed entries carry `basis:
   corrected|extrapolated|stale` + `tolerance`; age > lens period +
   3σ jitter forces `stale`, never "now"; shed_fraction > 0 labels
   the state degraded and suspends its precision accounting.
2. **Tolerance mislearning** — the error model is fit on a biased
   regime (the quiet week, the sleeping baby) and meets the real
   world with a band too tight (misses) or too wide (absorbs).
   Evidence: lens.txt exposes `regime_tag`, `sample_count`,
   refit/audit counts, hourly drift quantiles; a
   `tolerance_exceedance_rate` counter (fraction of trailing 100
   corrections whose residual exceeds the band) > 5% across two
   refits forces recalibration and a 2× widening rather than
   trusting the learned value; a lens younger than its warm-up is
   labelled `warming` and its learned band is not served as truth.
3. **State poisoning** — a frozen, looping, or spoofed source
   "corrects" the state to a confident falsehood. Evidence: per-item
   content hash + source device id; a `duplicate_content_hash_run`
   counter raising `frozen_source` when the hash repeats while the
   lens predicts change; a per-class `max_physical_delta` in the
   lens (temperature cannot jump 40° in one poll) — violations are
   *rejected and logged* as `poisoned_correction_rejected` with the
   sample retained; new thin devices start `provisional`, their
   corrections quarantined at widened tolerance until corroborated;
   cross-stream actuation requires corroboration ≥ 2 or an advisor-
   band judge probability, with a `single_witness` flag otherwise.
   Swap note (Hy's, accepted as roadmap): actions taken on
   extrapolated state later contradicted need a `rule_compensation`
   event and a `false_action_count` counter — a consequence of 1+3,
   caught by the same basis fields.

**Accepted.**
- **The whole evidence kit.** Every named field is cheap text in
  files the platform already keeps, and each cross-check is
  arithmetic, not a model. In particular: `basis` on every served
  state (the reader can always tell a corrected fact from an
  extrapolation), the forced-`stale` rule (age vs the stream's own
  measured rhythm — the lens judging its own freshness), and
  exceedance-rate as the tolerance model's self-test.
- **Shed-blindness is Panel 1's starvation amendment arriving
  again from a different door** — saturation produces silence in
  both. Independent convergence across rounds and models is the
  strongest signal a panel can give; the synthesiser inherits the
  heartbeat/coverage requirements by construction, not as a patch.
- **Poisoning defences match the substrate's existing posture**:
  provisional trust for new devices generalises Slice 1's staged
  trust in fixtures, retained rejected samples match the
  quarantine-never-delete rule from the download governor, and
  `max_physical_delta` is Casey's pressure-rating doctrine in
  ledger form — equality/plausibility as an agreed tolerance, per
  stream class, stated in the lens where a technician can read it.
- **`rule_compensation` + `false_action_count`** — accepted into
  the roadmap: a system that acts on extrapolated state owes a
  visible undo when the world contradicts it, and the count is how
  the household learns whether to let it act at all.

**Refused.** Nothing refused. One referee correction of emphasis:
Hy writes as if the synthesiser exists; it is a designed layer, not
a built one. Every accepted item above is a *requirement on its
ledger surface before it may serve state*, not a description of
current behaviour — the fields are cheap precisely because they
must exist from its first commit.

## Q4 — Technician failure (Seed)

**Points raised.** Three field situations: (1) a proprietary camera
whose auth dialect the generic RTSP converter rejects, with the
wizard returning an undifferentiated "connection failed" the
technician cannot act on without SSH and raw logs; (2) a
VLAN-segmented house where broadcast discovery listens on the wrong
interface and finds nothing — fix: interface selection in the
add-source flow plus manual IP entry that skips discovery entirely;
(3) an MQTT audio device publishing on a house-specific topic the
generic converter doesn't map, silently producing no events — fix:
a binding editor with a live subscribe test showing real messages
while the technician adjusts it.

**Accepted.**
- **Case 2 (VLAN) in full.** Discovery that assumes one flat LAN is
  the one-model promise meeting a real house; both fixes are cheap
  and buildable, and manual-address entry is the universal fallback
  that must exist for every discovery-based flow (this fleet's own
  LAN history — .local asymmetries,
...[truncated 1649 chars]