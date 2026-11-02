## What kills trust in week 2 / month 2

### 1. “1 false event per stream per day” is not a household budget
If “stream” includes each media-library file, IP camera, live channel, podcast, and text feed, then a 40-source house is 40 false events/day at the target. A 3,000-title library is 3,000/day if files are lanes. Day-1 precision on controlled ground truth will not catch this because day-1 metrics are usually per-decision or per-controlled-clip, not annualized across the real lane population.

**Fix:** Replace the spec with:
- **Household false-event budget:** e.g. ≤1 push-worthy false event/day across all alerting streams, and ≤0.1 false events/active stream-day for feed-only streams.
- **Per-stream rate, not absolute count:** false events per active stream-hour, with separate budgets for cameras/live vs library backfill vs text.
- **Lane-count-aware knob:** “spend freely on front door” should show expected false events/day, not just embed-seconds.

### 2. Auto-demotion below 0.9 precision is a lagging, low-power, easy-to-game metric
Precision from one-tap corrections is sparse. If a camera produces 200 candidate changes/day and the user taps “not meaningful” on 3, measured precision is 197/200 = 0.985; the system stays in push mode while still emitting 3 bad alerts/day. Worse, if the system emits fewer alerts to conserve budget, precision can stay high while recall collapses. The user experiences silence, then a missed event, then loss of trust — not a precision number below 0.9.

**Failure mode:** precision stays ≥0.9 while the system is useless or dangerous because it is under-alerting.

**Fix:** Demote on a **precision/recall/false-rate triad**, not precision alone:
- Precision ≥0.9 over trailing 7 days, **and**
- Recall ≥ floor for the stream class (e.g. front-door camera: ≥0.95 on known event types), **and**
- False events/day ≤ stream budget, **and**
- Correction sample size ≥ N (e.g. 20 taps) before demotion is allowed to fire.

### 3. Day-1 precision is measured on controlled ground truth; month-2 is distribution shift
The Laplacian result — precision 0.60 → 1.00 on controlled ground truth — is exactly the kind of number that dies outside the lab. Real month-2 shifts:
- seasonal lighting / IR cutover / shadows / rain / snow / insects / headlights;
- camera auto-exposure, WB, noise, bitrate collapse, firmware update;
- new furniture, new car, new pet, construction, holiday decorations;
- library items with grain, interlacing, bad OCR, foreign-language subs;
- podcast/radio ad insertion, rebroadcasts, clock drift;
- HLS ad breaks, stream restarts,
