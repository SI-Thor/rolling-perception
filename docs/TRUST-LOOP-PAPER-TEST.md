# TRUST-LOOP-PAPER-TEST — does certification arithmetic produce our demotion rule?

The study of NVIDIA's auto-ontology (`docs/STUDY-AUTO-ONTOLOGY.md`
§3.5/§6.1) queued one deciding test: take the certification
arithmetic as their code computes it, lay our corrections file
against it, and check whether spec §2.2's demotion figure falls out
without new machinery. This note is that test, on paper. Nothing was
built; nothing was run against a live stream.

Truth rules for this note: every figure about the soak is **measured**
and cited to `slice1/PROART-CAMERA.md` (SOAK-VERDICT, collected
2026-11-03); every figure in the worked example is **SYNTHETIC** —
invented inputs exercising the arithmetic, labelled as such in-line
and never mixed with measured numbers. The reality that shapes the
whole exercise: **the soak's corrections file does not exist.** 1,675
events published, corrections for the stream: none — "there is no
`ledger/attention/corrections.jsonl` under `run-proart/` at all"
(SOAK-VERDICT deficit 2), and the ledger itself agrees:
`precision_self_report = placeholder (labels pending)`. The
human-judgement half of precision is UNJUDGED. This paper test
therefore runs against the mechanism's *shape* with zero real
corrections, and designs for the first non-empty file.

## 1. The two mechanisms, stated exactly

### (a) Our §2.2 demotion rule, as the spec words it

The spec states the rule twice, at two altitudes. Founding principle
5 (`docs/SPEC-STREAM-PLATFORM.md`):

> "Silence by default. The attention plane speaks only on published
> verdicts, and any source whose measured precision decays is
> demoted automatically."

The operative sentence (§2.2, Alert policy):

> "any source whose measured precision on the household's own ground
> truth (the first weeks of feed corrections are exactly that ground
> truth) drops below 0.9 gets demoted to feed-only automatically,
> with a feed entry saying so."

Two more passages complete the design's intent. §3.3 (trust
accounting):

> "Trust accounting is published per stream in its ledger: events
> fired, user-confirmed, user-dismissed, trailing 7-day precision
> estimate. The platform reports its own precision the way the repo
> reports bench numbers — measured, or marked unmeasured."

And the console's corrections controls:

> "'That's not a change' / 'That mattered' — one-tap corrections on a
> feed entry; these are the ground-truth labels §2.2's demotion rule
> consumes, and they retrain nothing automatically in v1 (they are
> recorded, reviewed, and used to adjust thresholds deliberately — no
> silent self-modification)."

What exists in code today: `slice1/console/app.py`'s `/api/correct`
validates the `event_id` against the stream's events and appends one
JSON line to `ledger/attention/corrections.jsonl`:

```json
{"ts": <epoch>, "stream": "...", "event_id": "<stream>:<frame>",
 "correction": "not-a-change", "frame": ..., "tiles": ...}
```

The audit row that names the debt (AUDIT-DOCS.md D-A3): "unbuilt —
corrections are recorded, nothing consumes them … A periodic pass
over corrections.jsonl computing per-stream precision + a demotion
ledger note."

**The rule as worded is not implementable.** Precisely what is
missing:

1. **The window.** "Measured precision" over what? §3.3's "trailing
   7-day precision estimate" is a hint, not a binding definition, and
   nothing says demotion evaluates on the same window.
2. **The denominator.** Judged events only, or all published? On the
   soak's numbers (measured: 1,675 events, 0 corrections) the two
   readings cannot even be distinguished — but with 3 taps they give
   3/3 = 1.000 versus 3/1675 = 0.002, demotion versus not.
3. **Minimum evidence.** One dismissal in an otherwise unjudged week
   is 0/1 < 0.9 — a single tap would demote a stream.
4. **Both label kinds.** Precision needs confirmed *and* dismissed.
   The shipped console has only the "That wasn't a change" button;
   every correction value is `"not-a-change"` (the writer's default).
   The "That mattered" tap is designed in the spec and not built.
5. **The restore rule.** Demote at < 0.9 — un-demote at? Nothing.
6. **Cadence, computation, receipt.** Who evaluates, how often, and
   where the "feed entry saying so" and the ledger note land.
7. **Fault attribution.** The feed froze for 21.64 h of the soak
   (measured). A correction born of a feed fault is about the feed,
   not the gate; the rule does not say how such taps are treated.
8. **Instrument era.** Corrections convict the threshold/embedder
   that produced the verdict. Across a recalibration they are
   evidence about a departed instrument; the rule is silent.

### (b) auto-ontology's certification roll-up, as the code computes it

Read in code (clone at HEAD `caced11e`; the certification machinery
is unchanged since the study's HEAD `6c4fb71e` — no commits touch
`dal/terms.py` or `dal/schema.py` between them).

**The flags.** `auto_ontology/dal/schema.py:121` defines the column
helper — every flag is `Boolean, NOT NULL, DEFAULT false`, "because
every read of these absent means false, and making that the column's
job removes the coalesce from each caller." A glossary **Term**
carries two own-flags, `name_certified` and `description_certified`
(schema.py:464–465); each linked `column_attribute` and
`sql_attribute` carries one `certified` flag of its own (schema.py:502,
607).

**The roll-up.** `auto_ontology/dal/terms.py:156–234`, `_certification`
— one SQL expression, the docstring of which states the discipline:

> "The single definition of the rollup — the list cards, the detail
> page and the certification writes all project this, so the three
> cannot disagree."

and the construction that matters most to us:

> "Because the Term's two are always present the set is never empty,
> and a Term with no attributes is decided by them alone."

The arithmetic, exactly:

```
total     = 2 (own flags, always present) + column_total + sql_total
certified = own_certified (0..2) + column_certified + sql_certified

status = "certified" if certified == total
       = "pending"   if certified == 0
       = "partial"   otherwise
```

That is the whole rule: a **fraction** `certified/total` over per-field
booleans, bucketed at its two ends. **A human action** (the write path
`update_term`, terms.py:328+, or an attribute certification write)
flips exactly one boolean; the projected status re-derives through the
same single expression.

**Properties that matter for the mapping:** it is stateless (no time,
no window, no decay — the status is a function of the flags as they
stand); it is thresholdless (only the ends 0 and all are
distinguished; there is no 0.9 anywhere); it cannot be empty (the
always-present own flags make an untouched Term read `pending` — both
flags false, `certified == 0` — **never** `certified`); and their own
shipped management skill warns what this is not
(`skills/nvidia-ontology-management/references/publication.md:98`):
"Current Auto Ontology certification fields are not an atomic
review/promotion system… do not claim atomic certification, promotion,
supersession, or rollback."

## 2. The mapping

Corrections rows → certification inputs. What auto-ontology calls a
*field*, we call a **judged event**: one `event_id` in the trailing
window that has received at least one tap. The tap is the flag —
`mattered` = certified-true, `not-a-change` = certified-false. The one
deliberate deviation from their shape: **their flag set is complete by
construction (every field exists, defaulted false); ours cannot be.**
An unjudged event is not a false flag — absence of judgement is not
negative judgement — so unjudged events are *absent from the set*, and
our set **can** be empty. Their never-empty trick then reaches us from
the other side: the empty set reads *unjudged* (their `pending`), never
*certified*.

| auto-ontology (code) | Confluence trust loop (this design) |
|---|---|
| Term | the stream (per stream being judged), within one instrument era |
| field: `name_certified`, `description_certified`, per-attribute `certified` | one judged event in the trailing window |
| flag true / false (one column flip) | tap `mattered` / `not-a-change`; one row per tap, deduped by `event_id`, last tap wins |
| the flag set (never empty; own two flags always present) | the window's judged set (may be empty → status **unjudged**, never certified) |
| `total`, `certified` counts | `n = mattered + dismissed`, `m = mattered` over the window |
| fraction `certified/total` (implicit) | `φ = m / n` — per-stream trailing precision |
| status certified / partial / pending | healthy (`φ ≥ 0.9`) / decayed (`φ < 0.9`) / unjudged (`n = 0`) — plus **insufficient** (`0 < n < N_MIN`), which they do not need and we do |
| a human flips one flag | a household tap appends one corrections.jsonl row |
| no window | trailing `W = 7` days (spec §3.3's own figure) |
| no threshold | the 0.9 bar (spec §2.2) |
| no hysteresis | demote on 2, restore on 7 consecutive daily evaluations |
| — (no notion of fault) | taps on events inside a receipted frozen span are **feed fault**, excluded from `φ`, counted separately |
| — (one instrument, timeless) | **era fence**: only events published in the current instrument era count (cf. telltape's embedder-identity rule) |

**The arithmetic in closed form.** Evaluated once per day at time
`t`, per stream:

```
W(t)   = correction rows with tap time in (t − 7 d, t],
         deduped by event_id (last tap wins)
E(t)   = era fence: keep rows whose event publish time ≥
         the latest era marker ≤ t        (era markers: stream start,
         recalibration / embedder-swap receipts, once stamped)
F(t)   = rows in E(t) whose event publish time falls inside a
         receipted frozen span → excluded, counted as feed_fault
G(t)   = the remainder (gate-judged):  m = #mattered, d = #dismissed,
         n = m + d
φ(t)   = m / n        (undefined when n = 0)

status(t) = unjudged     if n = 0
          = insufficient if 0 < n < N_MIN          (N_MIN = 10)
          = healthy     if φ ≥ 0.9
          = decayed     otherwise

decision:  demote  (full → feed-only)  when status = decayed on
           SUSTAIN_DEMOTE = 2 consecutive evaluations
           restore (feed-only → full)  when status = healthy on
           SUSTAIN_RESTORE = 7 consecutive evaluations
           every transition appends a trust_status receipt and the
           spec's feed entry
```

The numbers the spec fixes: 0.9 (§2.2), and 7 days if §3.3's phrase is
taken as the window. The numbers this design chooses and exposes as
config, because the spec does not fix them: `N_MIN`, both sustains,
and daily evaluation cadence — the same posture the tenancy build
took with `mem_pressure_pct` (the spec named the trigger, the build
chose the number and documented it).

## 3. The verdict on the question

**YES with named adaptations.** The demotion *figure* — per-stream
trailing precision — falls out of their arithmetic as-is: `φ` **is**
their `certified/total`, restricted to the judged set, and the
counting core (per-field booleans rolling up to one fraction) carries
over verbatim. The demotion *decision* does not fall out, because
their mechanism stops exactly where ours begins: a stateless roll-up
over current flags, bucketed at 0 and 1, cannot demote at 0.9 over a
trailing week. The adaptations, named:

1. **Threshold comparison on top of the fraction** (0.9, from our
   spec; they have no middle threshold by design).
2. **A time window** (trailing 7 d; their flags are timeless).
3. **A minimum-evidence guard** (`N_MIN`); their never-empty
   construction inverts into our unjudged-by-construction — the same
   property read from the other side.
4. **Hysteresis** (2-eval demote sustain, 7-eval restore sustain);
   they have no notion of oscillation because nothing in their system
   acts on the status.
5. **Two-sided taps** (`mattered` must exist; their certify flag is
   one-directional and our shipped console is one-sided).
6. **Dedup by event_id, last tap wins** (their flags are idempotent
   single writes; our file is append-only taps).
7. **Feed-fault routing** and **era fencing** — both absent from
   their shape because their artefact has neither a feed that can
   freeze nor an instrument that can be swapped out from under the
   flags.

Why this is adaptation and not structural mismatch: the two things
their code is *for* — keeping one bad field from tainting a whole
record's status, and keeping every projection of the status derived
from one definition — are exactly the two things the demotion pass
needs (one bad event taps one flag, not the stream's reputation; one
roll-up function feeds the console badge, the ledger's trust line,
and the demotion decision, "so the three cannot disagree"). What
their system deliberately is *not* — automatic, timely, action-taking
("human-paced curation with software bookkeeping," as the study put
it) — is the half we must add, and the spec already ruled v1's
 posture: corrections "retrain nothing automatically," the pass only
demotes and restores with receipts.

## 4. A worked example — SYNTHETIC

**Everything in this section is SYNTHETIC.** The inputs are invented
(110 correction rows in total: scenario S1+S2 lays down 36 judged
events across the two decay weeks and 42 across the recovery
fortnight; scenario S3 adds 26 gate taps and 6 feed-fault taps); no
real corrections file exists for any stream in the soak. The script
is `~/lane-trust-loop/trust_paper_test.py` (outside this repo, under
the job's workdir); its full output is quoted below so the arithmetic
is checkable line by line.

**Scenario S1+S2 — decay, demotion, recovery.** Week 1 healthy (18
mattered / 1 dismissed across 19 judged events), week 2 decaying
(5/12 across 17), then two healthy weeks (3 mattered/day):

```
--- S1+S2: two-week decay -> demotion -> recovery (28 days; 36 judged events in the two decay weeks, 42 in recovery)  [SYNTHETIC INPUTS]
day  1  mattered= 3 dismissed= 0 n= 3  precision=1.000  status=insufficient mode=full     feed_fault_excl=0
day  2  mattered= 5 dismissed= 0 n= 5  precision=1.000  status=insufficient mode=full     feed_fault_excl=0
day  3  mattered= 8 dismissed= 0 n= 8  precision=1.000  status=insufficient mode=full     feed_fault_excl=0
day  4  mattered=10 dismissed= 1 n=11  precision=0.909  status=healthy     mode=full     feed_fault_excl=0
day  5  mattered=13 dismissed= 1 n=14  precision=0.929  status=healthy     mode=full     feed_fault_excl=0
day  6  mattered=15 dismissed= 1 n=16  precision=0.938  status=healthy     mode=full     feed_fault_excl=0
day  7  mattered=18 dismissed= 1 n=19  precision=0.947  status=healthy     mode=full     feed_fault_excl=0
day  8  mattered=16 dismissed= 2 n=18  precision=0.889  status=decayed     mode=full     feed_fault_excl=0
day  9  mattered=15 dismissed= 4 n=19  precision=0.789  status=decayed     mode=feed-only feed_fault_excl=0
         RECEIPT trust_status demote: demoted to feed-only: precision 0.789 < 0.9 over 19 judged events (window 7d), sustained 2 evaluations
day 10  mattered=12 dismissed= 6 n=18  precision=0.667  status=decayed     mode=feed-only feed_fault_excl=0
day 11  mattered=11 dismissed= 7 n=18  precision=0.611  status=decayed     mode=feed-only feed_fault_excl=0
day 12  mattered= 9 dismissed= 8 n=17  precision=0.529  status=decayed     mode=feed-only feed_fault_excl=0
day 13  mattered= 7 dismissed=10 n=17  precision=0.412  status=decayed     mode=feed-only feed_fault_excl=0
day 14  mattered= 5 dismissed=12 n=17  precision=0.294  status=decayed     mode=feed-only feed_fault_excl=0
day 15  mattered= 7 dismissed=11 n=18  precision=0.389  status=decayed     mode=feed-only feed_fault_excl=0
day 16  mattered= 9 dismissed= 9 n=18  precision=0.500  status=decayed     mode=feed-only feed_fault_excl=0
day 17  mattered=12 dismissed= 7 n=19  precision=0.632  status=decayed     mode=feed-only feed_fault_excl=0
day 18  mattered=14 dismissed= 5 n=19  precision=0.737  status=decayed     mode=feed-only feed_fault_excl=0
day 19  mattered=16 dismissed= 4 n=20  precision=0.800  status=decayed     mode=feed-only feed_fault_excl=0
day 20  mattered=19 dismissed= 2 n=21  precision=0.905  status=healthy     mode=feed-only feed_fault_excl=0
day 21  mattered=21 dismissed= 0 n=21  precision=1.000  status=healthy     mode=feed-only feed_fault_excl=0
day 22  mattered=21 dismissed= 0 n=21  precision=1.000  status=healthy     mode=feed-only feed_fault_excl=0
day 23  mattered=21 dismissed= 0 n=21  precision=1.000  status=healthy     mode=feed-only feed_fault_excl=0
day 24  mattered=21 dismissed= 0 n=21  precision=1.000  status=healthy     mode=feed-only feed_fault_excl=0
day 25  mattered=21 dismissed= 0 n=21  precision=1.000  status=healthy     mode=feed-only feed_fault_excl=0
day 26  mattered=21 dismissed= 0 n=21  precision=1.000  status=healthy     mode=full     feed_fault_excl=0
         RECEIPT trust_status restore: restored to full: precision 1.000 >= 0.9 sustained 7 evaluations
day 27  mattered=21 dismissed= 0 n=21  precision=1.000  status=healthy     mode=full     feed_fault_excl=0
day 28  mattered=21 dismissed= 0 n=21  precision=1.000  status=healthy     mode=full     feed_fault_excl=0
```

Read off the designed behaviours: days 1–3 are **insufficient**
(evidence exists, `n < 10`, no decision possible — a single tap
cannot demote); the healthy week holds 0.909–0.947; day 8 is the
first below-bar evaluation (0.889, no action — one bad day is not a
trend); day 9's second consecutive below-bar evaluation **demotes**
with the receipt the spec's "feed entry saying so" asks for; the
trough (0.294 at day 14) and the climb back are held at feed-only —
restoration is not bribed by one good day; day 20 is the first
healthy evaluation (0.905) and the seventh consecutive one lands on
day 26, which **restores**. Demotion took 2 days; restoration took a
full window's worth of good behaviour — the asymmetry is the
anti-flap property, the same shape as the tenancy ladder's.

**Scenario S3 — a frozen-stretch burst and a recalibration.** Six
`not-a-change` taps on events published inside a receipted frozen
span (feed fault), and a threshold recalibration at day 10 (era
marker):

```
--- S3: frozen-span burst (6 feed-fault taps) + recalibration era fence at day 10  [SYNTHETIC INPUTS]
day  1  mattered= 2 dismissed= 0 n= 2  precision=1.000  status=insufficient mode=full     feed_fault_excl=0
day  2  mattered= 4 dismissed= 0 n= 4  precision=1.000  status=insufficient mode=full     feed_fault_excl=0
day  3  mattered= 6 dismissed= 0 n= 6  precision=1.000  status=insufficient mode=full     feed_fault_excl=0
day  4  mattered= 8 dismissed= 0 n= 8  precision=1.000  status=insufficient mode=full     feed_fault_excl=0
day  5  mattered= 8 dismissed= 0 n= 8  precision=1.000  status=insufficient mode=full     feed_fault_excl=0
day  6  mattered=10 dismissed= 0 n=10  precision=1.000  status=healthy     mode=full     feed_fault_excl=6
day  7  mattered=12 dismissed= 0 n=12  precision=1.000  status=healthy     mode=full     feed_fault_excl=6
day  8  mattered=11 dismissed= 2 n=13  precision=0.846  status=decayed     mode=full     feed_fault_excl=6
day  9  mattered=10 dismissed= 4 n=14  precision=0.714  status=decayed     mode=feed-only feed_fault_excl=6
         RECEIPT trust_status demote: demoted to feed-only: precision 0.714 < 0.9 over 14 judged events (window 7d), sustained 2 evaluations
day 10  mattered= 0 dismissed= 0 n= 0  precision=    -  status=unjudged    mode=feed-only feed_fault_excl=0
         RECEIPT trust_status era_reset: instrument era change (recalibration: threshold 0.25 -> 0.18); window re-derived from day 10; pre-era corrections no longer convict
day 11  mattered= 1 dismissed= 1 n= 2  precision=0.500  status=insufficient mode=feed-only feed_fault_excl=0
day 12  mattered= 2 dismissed= 2 n= 4  precision=0.500  status=insufficient mode=feed-only feed_fault_excl=0
day 13  mattered= 3 dismissed= 3 n= 6  precision=0.500  status=insufficient mode=feed-only feed_fault_excl=0
day 14  mattered= 4 dismissed= 4 n= 8  precision=0.500  status=insufficient mode=feed-only feed_fault_excl=0

config: window=7d bar=0.90 n_min=10 sustain_demote=2 sustain_restore=7
ALL FIGURES ABOVE ARE SYNTHETIC — no real corrections file exists for the soak.
```

Two behaviours to read. First, the frozen burst: the six feed-fault
taps appear as `feed_fault_excl=6` and never enter `φ` — on day 6 the
gate-judged precision is 1.000 at `n = 10` where counting the burst
would give 10/16 = 0.625 and a bogus demotion run. A feed freeze is
the feed's crime; the gate is not convicted for it. (In the soak's
build no events publish inside a frozen stretch — the last verdict
precedes each gap — so this routing is defensive, but slice 1's own
defect 3 shows builds exist where frozen polls look like frames.)
Second, the era fence: the day-10 recalibration re-derives the
window from the new instrument's events only. `n` drops to 0
(**unjudged** — not certified, not demoted), the demotion stands (a
reset is not an acquittal), and days 11–14 accumulate evidence at
0.500 but **insufficient** — no new demotion can fire and no
restoration until the new era earns its own seven good days. The old
instrument's 18 pre-era judgements no longer convict its successor.

## 5. Failure modes of the mechanism itself

- **Judgement sparsity — the social form of "silence = meaningful."**
  A stream nobody corrects must not read as certified. The design
  answers structurally, the same way their code does: the flag set is
  *judged events only*, so zero corrections means `n = 0` means
  **unjudged** — their never-empty construction guarantees an
  untouched Term reads `pending`, never `certified`, and our empty
  set inherits exactly that property. The console badge and the
  ledger trust line carry the four states (`unjudged` /
  `insufficient` / `healthy` / `decayed`), so the soak, run through
  this pass today, would publish **UNJUDGED** — measured-honesty
  ("measured, or marked unmeasured", §3.3) in social form.
- **Correction gaming and laziness.** Laziness (nobody taps) is
  unjudged-forever — honest, and the badge says so rather than
  rotting silently. One-sided pressure: dismissal is one tap and
  confirmation does not ship yet, so `φ` computed from today's file
  shape is biased downward — which is why the `mattered` tap is part
  of the build, not an enhancement, and why `N_MIN` gates any
  demotion. Blanket dismissal (a household that taps everything
  "not-a-change") drives `φ` to 0 and demotes — which is the correct
  response to a household telling you everything is noise: feed-only,
  receipted, reversible. What the mechanism must never do is *act on
  corrections that were never filed*; the denominator is judged
  events, never all events, so silence cannot be forged into either
  a 1.000 or a 0.000.
- **Demotion oscillation.** Two guards, both visible in the worked
  example: the asymmetric sustains (demote after 2 below-bar
  evaluations, restore after 7 at-bar), and the fact that demotion
  does not choke off its own evidence — feed-only stops *alerts*,
  not the feed (spec §2.2: "demoted to feed-only"), so events and
  corrections keep flowing and the window can recover on real
  evidence rather than on the absence of it.
- **Corrections arriving after a recalibration — the instrument-era
  problem.** A correction convicts the instrument that published the
  verdict; applied across a swap it convicts the wrong one. telltape
  already fences this at the ledger level (embedder identity, the
  swap refusal, `embedder_swap` receipts); the pass reuses the same
  rule at the trust level — the window is re-derived at each era
  marker and pre-era corrections stop counting, with an `era_reset`
  receipt so the discontinuity is in the record, not smoothed over.
  Slice 1's ledger has no identity/recalibration stamps today; the
  pass's v0 era marker is the stream's `start` row, and the missing
  stamp is named in the build list below.

## 6. Build / no-build recommendation

**Build** — this is D-A3's pass, now with the arithmetic specified.
The smallest mechanism that closes spec-debt #1:

1. **One roll-up function** (their "single definition" discipline):
   `rollup(corrections, events, frozen_spans, era_markers) ->
   {m, d, n, precision, status, action}` — pure, deterministic,
   ~100 lines with the dedup/window/fence/exclusion logic above,
   plus fixtures lifted from the SYNTHETIC script. It lives beside
   the console (`slice1/console/trust.py`) or as a standalone pass;
   the console badge, the ledger trust line, and the demotion
   decision all project it — never three copies of the rule.
2. **A daily evaluation** (systemd timer or the console's read path
   with a cached daily state file) that appends, on every
   transition, a `trust_status` service row to the stream's
   `events.jsonl` and writes `ledger/attention/trust-state.json`
   (per-stream `n`, `precision`, `status`, `mode`, `feed_fault`
   count) — the demotion ledger note D-A3 names, plus the feed entry
   the spec requires.
3. **The missing inputs, in dependency order:** the **"That mattered"
   tap** (one button + one correction value — without it the file can
   only ever hold one side of the labels and `φ` is a downward-biased
   artefact); **frozen-span receipts** on the slice-1 watcher
   (telltape's `source_frozen`/`source_recovered` rows are the
   pattern — slice 1's pre-G1 build has none, so v0 ships the
   feed-fault routing ready and inactive); **era markers** (a
   `recalibrate` receipt when thresholds change — v0 uses the start
   row).

Sizing, honestly: items 1–2 are **an afternoon** — the arithmetic is
specified above to the last fraction, the input format exists
(`corrections.jsonl`'s shipped shape), and the script in §4 is the
test rig. The `mattered` tap and the console badge are another small
chunk; with the watcher-side frozen receipts, the whole of items 1–3
is **a short slice**, not an afternoon — because two of the three
inputs the arithmetic needs do not exist yet. What explicitly stays
out: any automatic threshold adjustment (the spec's v1 ruling:
"retrain nothing automatically"), and lens-exemplar writing from
corrections (spec §3.1/§3.3's exception-exemplar design — the
CustomAnalysis lesson says the exemplar is the right *unit* for that
future mechanism, but the demotion pass only reads; writing exemplars
is separate work with its own acceptance).

If it were no-build instead, the only honest alternative would be a
console badge rendering "UNJUDGED — n corrections filed" per stream
from the file as it stands — which stops the file lying by omission
but leaves the ≤0.9 rule dead letters and spec-debt #1 open. The
arithmetic falling out as cleanly as §3 says it does is precisely the
evidence that the build is small.
