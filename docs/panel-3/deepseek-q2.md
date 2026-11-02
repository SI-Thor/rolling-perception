# Trust economics for the chatty gate

**The core reframe first.** 393 events in 4 hours is not 393 *decisions the homeowner must make* — it is 393 *verdicts the ledger recorded*. The trust system's job is to keep those two numbers from ever being forced equal. The design below separates **what is recorded** (always, cheap, complete) from **what interrupts** (rationed, ranked, budgeted) from **what is learned** (only from confirmed samples, never from the stream's own output).

---

## 1. Auto-demotion and promotion

**The measured quantity is trailing precision, not event count.** Count is the wrong signal — a genuinely busy evening (a party) is 393 honest events and demoting it would be a bug. Precision is the signal, and it is *already* the house's operative metric (Spec C §2.2: "any source whose measured precision … drops below 0.9 gets demoted"). The 393 evening is exactly the case that metric was written for; the spec just never said what window or what the demotion *does*.

**The window: a 24-hour trailing window, minimum 20 scored events.** Below 20 scored events the estimate is too noisy to act on (derivation: binomial CI at n=20, p=0.9 is ±0.13 — wide but bounded; at n=10 it is ±0.19 and demotion would fire on noise). Scored = the homeowner tapped "that mattered" or "that wasn't a change"; **unscored events do not enter the denominator** — silence is not a vote.

**Demotion is per-stream *and* per-tile-region.** The 393 evening is almost certainly not uniform: the door region is honest, the window-blind region is light. So the demotion unit is a tile region (the 4×4 grid's cells, clustered by adjacency into regions the user can see on the evidence image). A region whose trailing precision < **0.70 (guess — the spec's 0.9 is the *alert* bar; feed-only demotion should be looser, and 0.70 is a starting point to be measured against the first month of corrections)** drops from "interrupt" to "logged quietly": still in the feed, still in the ledger, no push, no overlay, no pause.

**Promotion back is automatic and visible, on a schedule, not on silence.** A demoted region re-enters a **7-day probation** at the next recalibration (below), during which its events are feed-only but *scored against the same corrections ledger*. If probation precision ≥ 0.90 over ≥ 20 scored events, it promotes. If not, it stays demoted and the probation resets. **The system cannot demote itself into permanent silence invisibly** because: (a) every demotion writes a feed entry naming the region and the precision that caused it; (b) every probation writes a feed entry when it starts and when it resolves; (c) a demoted region still *records* — the ledger shows its events, badged "quiet", so the homeowner can see what the system is suppressing and override with one tap. The failure mode "the watcher went quiet and nobody noticed" is caught by the same liveness heartbeat the spec already requires (Spec C §4.3): a region that produces *zero* verdicts for 24 h is itself a feed entry ("region X has been silent — is the camera seeing it?").

---

## 2. Recalibration cadence

**Three triggers, one schedule, and a hard rule about what may enter the baseline.**

- **Scheduled:** the lens re-fits weekly (Spec B §3.2 already says diurnal profiles re-fit weekly; the drift model and ranker calibration join that cadence).
- **Triggered by drift:** the pending-drift accumulator (Spec B §3.2) publishing a `slow-change` verdict is a recalibration trigger — the world moved, the lens should follow.
- **Triggered by correction:** every "that wasn't a change" writes an exception exemplar and *also* schedules a ranker refit for that stream within 24 h (batched, not per-tap — one tap should not thrash the model).

**The anti-contamination rule is the load-bearing one, and it is already in Spec B §3.2 — the design just needs to say it louder for the lived-in-room case.** A sample enters the baseline only if it was published as *no-change* (or user-ruled normal) **and** differs from the previous baseline by less than the current change threshold. "A person in the room" is, by construction, a *change* — it exceeds the threshold, so it is held out of the baseline and accumulates as pending-drift, not as normal. The failure the question worries about (learning the person as furniture so a second person is invisible) is exactly the failure the held-out rule prevents: the first person never becomes baseline, so the second person is measured against the *empty-room* baseline, not against "one person present."

**The residual risk is the person who sits still for hours.** That is a genuine slow-change, and the honest answer is that the lens *will* eventually absorb it — but only through the pending-drift accumulator, which publishes a labelled `slow-change` verdict *when it does*, so the homeowner sees "the room's baseline shifted at 19:40" rather than a silent absorption. The baseline shift is a feed entry. That is the visibility the question demands.

---

## 3. The homeowner's surface

**The digest shape: one card per hour, not one per event.** During a busy evening the feed *page* shows all 393 (it is a record); the *push surface* shows a single hourly digest card: "Main room: 47 changes this hour — [3 thumbnails of the highest-ranked], 44 more in the feed." The digest is ranked by the same drift × sheaf × recency score the feed uses (Spec C §2.1), so the three thumbnails are the three most likely to matter. The homeowner's choice is never "judge 393 events"; it is "glance at 3, tap the feed if curious."

**The budget knob in plain language** (Spec C §2.5's vocabulary, extended): the existing three positions ("Tell me now / Feed only / Never show me") gain a fourth, **"Busy tonight"** — a one-tap temporary demotion of the whole stream to feed-only until morning, auto-expiring, logged as a feed entry. This is the pressure valve for exactly the 393-evening: the homeowner who comes home to a chatty room taps once and gets silence until morning, without permanently demoting a stream that was honest.

**What a correction buys, mechanically:** "that wasn't a change" does four things, all recorded: (1) writes an exception exemplar into the lens (negative weight in embedding space, Spec B §3.1); (2) counts toward the trailing-precision denominator for that region (§1 above); (3) schedules the batched ranker refit; (4) **does not** silently retrain anything — Spec C §2.5 is explicit that corrections are "recorded, reviewed, and used to adjust thresholds deliberately — no silent self-modification." The homeowner's tap is a *label*, and the system's response to labels is a scheduled, visible refit, not an immediate behavior change. That is the discipline that keeps the lens from chasing its own tail.

**The one number to measure first:** the 393-evening's per-region precision against the corrections ledger. Until that exists, every threshold above is a guess, and the spec's own rule applies — the guess is labelled, and the first month of real corrections is what pays it.
