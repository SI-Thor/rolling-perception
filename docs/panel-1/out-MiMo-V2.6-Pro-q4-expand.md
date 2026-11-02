## Three expansions the substrate can carry

**1. Retrieval — "find the thing I half‑remember."**
- **Failure mode in month 2:** the change feed is a *temporal* index. By week 6 the household asks "the clip where the delivery guy came Tuesday" and the only door out is a deep link to a commercial service's search — i.e. the platform becomes a shelf in front of someone else's cloud. The ledger is structured text and the overnight pass already produces speech/meaning text; it is already 90% of a retrieval index.
- **Fit + fix:** a `retrieval` lane family over ledger text (BM25 + text embeds). Text embeds are ~1–5 ms on Thor vs 173 ms/tile image embeds, so a 100k‑entry ledger at 768‑dim fp16 ≈ 150 MB — a rounding error in 122 GB. Budget it as its own metered lane ("sips"), and put it **above** library backfill on the yield ladder: a search typed by a person is owner's own work, which the ladder's "owner wins" rule already promises but the ladder's four steps don't currently express.

**2. Per‑person attention (who cares, quiet hours, per‑person demotion).**
- **Failure mode in month 2:** one shared feed means the nursery camera pushes to everyone at 02:00. Worse, the trust spec's 0.9 precision floor is measured *per stream* — a stream can sit at 0.95 overall and 0.60 for one person's cares. That is the same ranker‑not‑separator problem you already measured (skipped tiles drift 0.20 vs 0.48), now with a human attached.
- **Fit + fix:** per‑person ledger views + per‑person precision counters (4 people × 30 streams = 120 counters, trivial). Quiet hours are not a new mechanism — they are a **phase mask** in the LensFile, whose period/jitter/phase is already learned. Per‑person budget knobs inherit the plain‑language compiler unchanged.

**3. Coverage proof — "is the box actually watching?"**
- **Failure mode in month 2:** a silent feed is ambiguous: nothing happened, the box was shedding (your own yield ladder kills decision before the owner notices), or a stream died. You have no failover in v1 and unmeasured sustained camera rates, so this ambiguity is guaranteed, not hypothetical. A household that can't distinguish silence from blindness uninstalls.
- **Fit + fix:** per‑stream heartbeat in the ledger (last embed, last reflex tick, % of scheduled ticks served this hour) plus a shelf badge. It is one more ledger field and one more staggered lane, and it makes your TO‑MEASURE list falsifiable in the field instead of at review time.

## One to refuse

**On‑
