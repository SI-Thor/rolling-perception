## 1. Auto-demotion: the measured quantity

The control is **not raw event count** — 393 published verdicts may be honest. It is the **interruptive false-alarm rate**, tracked per stream (and per tile region if a region is independently promoted).

Ledger counters, appended per event:
- `published`, `alerts_pushed`, `user_confirmed`, `user_dismissed`, `unjudged`.
- `precision_est = confirmed / (confirmed + dismissed)` over the **trailing judged window**: the last **30 judged events** or **7 days**, whichever is reached first — *30 is a guess to be measured; the 7-day half is the spec’s §B 3.3 trust window*.
- `false_per_day = (1 − precision_est) × alerts_pushed_per_day` — *derivation from the ≤1 false event/stream/day target (§B 3.3)*.

**Demote to “logged quietly” (feed-only, no push/overlay) when either:**
1. **Precision trigger:** `precision_est < 0.90` over the judged window. *0.90 is inherited from §C 2.2, not a new guess.*
2. **Rate trigger:** `alerts_pushed > 2 in the trailing 1 hour` **and** `precision_est` is unmeasured or `< 0.99`. *2/hour is a guess to be measured; it is a livability cap — 2/h ≈ 48/day, which at the 0.90 floor gives ≤4.8 false/day, so the precision trigger usually binds first. The rate trigger catches the 98/h evening blow-up regardless of labels.*
3. **Projected-budget trigger:** `false_per_day > 1.0` over the trailing 24 h. *Derivation from the trust target.*

Demotion is **visible and reversible**: it writes a feed entry + ledger line `alerting: feed-only (auto)`, naming the trigger, the numbers, and the timestamp. It is *not* silence: events still publish to the feed, and the console shows a “demoted (auto)” badge. A stream cannot stay demoted invisibly — the weekly trust digest reports “feed-only for N days; 0 of M recent events confirmed”.

**Promotion back:** automatic only after a **24 h probation** in which `alerts_pushed ≤ 2/h` **and** `precision_est ≥ 0.95` over ≥10 judged events (*0.95 and 10 are guesses to be measured*), or immediately on the homeowner’s explicit “Tell me now” (§C 2.5). No silent self-modification: promotion is recorded as an event.

## 2. Recalibration cadence

Recalibrate on **trigger + schedule**, never continuously:

- **Scheduled:** the lens refits `drift_model` EMA (α=0.10) and the 24-hour diurnal profile **weekly** (§B 3.1); baseline embeddings decay with a **14-day half-life** (§B 3.2, *derived from the aging rule, sensitivity TO-MEASURE*).
- **Triggered:** a recalibration audit runs when the rate trigger fires, or when `unjudged` exceeds **200 events** (*guess to be measured*), or when the homeowner issues ≥3 corrections in an hour. The audit re-fits `ranker_calibration` from recorded `(reflex score, true drift)` pairs (§B 3.1).

**Avoiding “a person in the room” becoming invisible:** baseline admission is conservative (§B 3.2). A sample enters the baseline only if it was published as *no-change* **and** differs from the previous baseline by **less than the current change threshold**. A person-sized, person-shaped change is held out, not absorbed. It becomes normal only by **confirmed recurrence** — the lens proposes `known_rhythms` after **5 unflagged recurrences** (*derived rule, TO-MEASURE*) or explicit user confirmation — never by stealth. Crucially, the **sheaf refine** and the **pending-drift accumulator** keep a *second* person visible: a second person is a new spatial pattern, not just more drift, so it breaks the tile-grid consensus / exceeds the 99th-percentile drift band and publishes as `change`, labelled `slow-change` if it accumulated. The lens learns *rhythm and light*, not “occupancy = normal”: occupancy is a `known_rhythm` only if the homeowner confirms it, and even then the change threshold is not lowered, only the expected-recurrence annotation.

## 3. Homeowner surface

**Digest shape:** during the evening the homeowner sees **one feed**, not 393 alerts. The 393 are grouped into a **“since you last looked” digest** (§C 2.5): a single card — *“Main room: 393 changes, 4 h. 1 confirmed arrival (18:42), 12 flagged as person-scale, 380 low-drift / light-shift.”* The top **2 ranked alerts/hour** (by drift × sheaf energy × Jev probability) may push; the rest are feed entries with tile overlays. The console tile shows a **sparkline of drift**, not a list.

**Budget knob (plain language):** next to the source, *“Tell me now / Feed only / Never show me”* (§C 2.5), plus the spend line: *“Watching costs ≈ X embed-minutes a day at current settings”* (§B 2.2; unit is an ESTIMATE until the live budget bench lands). The evening blow-up auto-suggests **“Feed only”** with the reason.

**A correction buys:** “That wasn’t a change” / “That mattered” (§C 2.5) are the ground-truth labels. Mechanically, a dismissal writes a **negative-weight exception exemplar** into the stream’s LensFile (§B 3.1), increments `user_dismissed`, and lowers `precision_est`; a confirmation increments `user_confirmed` and, if it is a person-scale event, seeds a `known_rhythm` candidate. Corrections are **reviewed, not auto-applied as threshold changes in v1** — they adjust the ranker at the next weekly/triggered refit, so the lens cannot silently rot or silently learn the wrong normal.
