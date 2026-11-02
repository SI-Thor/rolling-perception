# AUDIT-DOCS — numbers, links, and spec-debt (2026-11-02)

Audit only: nothing in the tree was changed by this pass. Method:
`docs/RESULTS.md` re-verified line by line against its cited sources
plus a fresh `cargo test --workspace`; every backticked path in every
doc checked for existence; every relative Markdown link resolved;
`docs/SPEC-STREAM-PLATFORM.md` + Amendments 1–2 read in full and
diffed against what the code actually does. Severity = damage if a
reader (stranger, technician, Casey) trusts the item as-is. Effort =
cost to close. History sections are allowed to be historical; only
wrong *current-state* claims are flagged.

Fresh ground truth for this audit: **workspace 107 passed / 0
failed** — rolling-perception 6, rolling-substrate-core 55,
rolling-pipeline 17, rolling-adaptive 6, cuda-thor 12,
harbor-watch 8, confluence-watch 3.

---

## Pass 1 — NUMBERS

### Flagged

| # | Item | Severity | Effort | Evidence |
|---|---|---|---|---|
| N1 | Root README's cold-run line says `cargo test` "runs all **95 tests**" — actual is 107, and the same README says 107 twice elsewhere (quickstart arithmetic + scope note). The front door contradicts itself. | HIGH | trivial | `README.md:37` vs `README.md:72,89`; fresh run = 107 |
| N2 | Reading guide stop 1 repeats "(95 tests; …)" while its own crates table says 107 workspace tests. | HIGH | trivial | `docs/READING-GUIDE.md:19` vs `:73` |
| N3 | RESULTS' serve row still says the H.265 path is unusable and "the player ships H.264 **until an fMP4 path exists**" — the fMP4 path exists and is wired as a player mode (0 encode-fps, 41-check validation passed). A current-state product claim that is now false. | HIGH | small | `docs/RESULTS.md` Slice-2 table vs `slice2/player/RESULTS.md` + `slice2/player/fmp4-spike/RESULTS.md` |
| N4 | RESULTS' soak row quotes a "+50 min" snapshot (5,431 frames, 0 events, spend ratio 0.0002) that appears **nowhere in its cited source**. The cited doc records different numbers (calibration: 1,200 frames, ratio 0.0008; the hour-1.3 snapshot: 48 verdicts) — and "0 events" was superseded inside the same soak by the arrival episode the source doc itself records. | MEDIUM | small | `docs/RESULTS.md` Slice-1 table vs `slice1/PROART-CAMERA.md:63-94` (grep: no "5,431", no "0.0002") |
| N5 | RESULTS' deficits still speak of panel round 3 in the future tense ("round 3 must ask ≥2 questions per model"). Round 3 ran; its synthesis is in the tree. | MEDIUM | trivial | `docs/RESULTS.md` deficits vs `docs/SPEC-PANEL-3.md` |
| N6 | RESULTS' TTFO row (243.5 µs vs 2,528.6 µs, 10.39×) cites `crates/rolling-perception` + PLAN/DESIGN — none of those carry the absolute figures (the crate README gives only a "3x–16x" ratio range). The numbers exist in exactly one place: the CHANGELOG's wave-1 bench entry. Right numbers, wrong citation. | MEDIUM | trivial | grep for `2528`/`243.5` across tree: only `CHANGELOG.md:276-277`, `docs/RESULTS.md:11`, `docs/READING-GUIDE.md:78` |
| N7 | RESULTS' cascade row (gating 71.9%, energy 132.75→95.97) cites `crates/rolling-pipeline` — its README does not contain the figures. They live in the root README's results table and the CHANGELOG. | LOW | trivial | `README.md:126`, `CHANGELOG.md:252`; absent from `crates/rolling-pipeline/README.md` |
| N8 | ARCHITECTURE's printed tally ("34 claims — 10 proven, 13 partial, 10 unproven, 1 refuted") and its "single worst divergence is D1" prose no longer match the book's own tables after the amendments + proof sweep moved D1 (resolved), D9, D10, P5, P13 (proven) and D4, D12 (partial). A recount of the status cells gives ≈8 proven-family / 14 partial / 8 unproven + 1 resolved + 1 refuted. | MEDIUM | small | `docs/ARCHITECTURE.md:151` vs its own rows at `:109-150` |
| N9 | Substrate-core README's test line says "32 tests, this crate only" — the crate now runs 55. | MEDIUM | trivial | `crates/rolling-substrate-core/README.md:19`; fresh `cargo test -p rolling-substrate-core` = 55 |
| N10 | RESULTS' deficits state Casey's :8295/:8296 servers "are down" as a standing fact. It was true when measured (2026-11-01); nothing in the tree can re-verify it, and the sentence has no date fence in place. | LOW | trivial | `docs/RESULTS.md` deficits (last bullet) |

### Verified clean (spot-checked against sources, no discrepancy)

- Workspace arithmetic 107 = 6+55+17+6+12+8+3: README quickstart,
  ARCHITECTURE head, READING-GUIDE crates table, fresh run — agree.
- Wave-3 rows: embed p50 173 / p95 200 ms, 312 vs 576 embeds
  (−54%), refine precision 0.60→1.00, Jev P=0.750 / tie-breaker
  harm — all present in `docs/WAVE3.md` /
  `experiments/wave3/driver/RESULTS.md` / `experiments/wave3/jev/`.
- Slice-1 staged rows: 3,347.6 ms / 392.8 ms / ratio 0.118 —
  present verbatim in `slice1/README.md` + `slice1/core/README.md`.
- NVENC rows: aggregate ≈580–640 fps, holds at N=16 (38.4 fps),
  breaks at N=24 (24.1), V4L2 H.265 530–740 fps, embed p99
  170→251 ms — all in `slice2/NVENC-BENCH.md`.
- Player rows: remux 141 frames, transcode 1800/1800 at 138.1 fps
  draw, 429-at-cap — in `slice2/player/RESULTS.md`.
- Presence rows: TTS 1,974→287 ms, loop 2,891→1,284 ms, 23/23,
  8/8 — in `slice2/presence/README.md`. Brain 65 tok/s —
  `slice2/BRAIN-BENCH.md`.
- Backfill rows: 234 items (232 images + 2 videos), 65.9 s of
  video — in `slice3/BACKFILL-PASS1.md`.
- Synth rows: sampler/engine means (0.935/0.087, 4.347/0.236,
  33.083/4.065 → 11×/18×/8×), reversal peak 60×, snap v2
  6.00 s → 2.00 s — in `slice3/synth/README.md`.
- Checksum 345101.1999, error 209, 1,000/1,000 swaps, persistent
  9–27× — in crate READMEs / `results/thor/` receipts.
- Adaptive row: RESULTS' "1.7 ms vs 854 ms" is the rounded form of
  the source's 1,669 µs vs 854,285 µs (`crates/rolling-adaptive/
  README.md:37`) — consistent.

---

## Pass 2 — LINKS & REFS

Every relative Markdown link in the tree resolves (**0 dead**).
Glob references (`crates/*/HARDENING.md`,
`experiments/thor-cuda/exp1–exp4*`) resolve to real files. The dead
references are path-style citations:

| # | Item | Severity | Effort | Evidence |
|---|---|---|---|---|
| L1 | CHANGELOG cites `docs/FINDINGS-CFC-JEPA-V2.md` — **absent from this staging tree** (it exists on origin, commit eba962f; the staging tree and origin have skewed). In-tree, the reference is dead and the note's three findings have no local home. | MEDIUM | trivial (sync) | `CHANGELOG.md:30`; `ls docs/` — no FINDINGS file |
| L2 | `docs/HOTPATH.md` is cited as the adopted hot-path allocation policy — the file was never created. The policy exists only as panel raw text. | MEDIUM | small | `docs/SPEC-PANEL-3.md:188`, `docs/panel-3/mimo-q3.md:7`; no `docs/HOTPATH.md` |
| L3 | The technician docs tell the reader to `tail ~/confluence/ledger/attention/feed.jsonl` — **no code writes that file**, and the live ledger does not live at that path (it lives in the watch run directory). A service instruction pointing at a file that will never exist. | MEDIUM | small | `slice1/install/INSTALL.md:236`, `slice1/install/SERVICE-CARD.md:32`; grep: no writer of `feed.jsonl` anywhere in `slice1/` code |

---

## Pass 3 — SPEC-DEBT (the next-phase menu)

Every promised behaviour in `docs/SPEC-STREAM-PLATFORM.md` (§ refs
to the spec) + Amendments 1–2 that is not built. Status: **unbuilt**
/ **partial** / **built-elsewhere** (exists outside Confluence's
code). "Close" is one line each — the cheapest honest way to make
the promise true or amend it away.

### Slices 2–5 (the build order, §C.3)

| # | Promise (spec §) | Status | Severity | Effort | Close |
|---|---|---|---|---|---|
| D-S2 | Slice 2: server-side **resume across devices** (10 s heartbeat, per profile), 10-hand-off acceptance (§C.1.2, §C.3 Slice 2) | unbuilt — the player keeps no position state at all | HIGH | medium | Add a position ledger file + heartbeat POST to the player; run the hand-off acceptance |
| D-S3 | Slice 3 entire: household **profiles**, kid allowlist profile, per-profile shelves/resume/feed prefs (§C.1.4, §C.3 Slice 3) | unbuilt | HIGH | large | Build the profile model on the ledger (`household/profiles.txt`, see D-L2) + console switching |
| D-S3b | Slice 3: **perception-backed search** + the 20-query acceptance (§C.1.1, §B.4.2) | unbuilt — no index, no query surface | HIGH | large | Needs D-B4 (index) first; then a query endpoint + the pre-written query set |
| D-S4 | Slice 4 entire: **push alerts**, cross-stream **rules engine**, **bridge console** page, 14-day alert-precision acceptance (§C.2, §C.3 Slice 4) | unbuilt | HIGH | large | The attention plane (D-A1) is the prerequisite for all three |
| D-S5 | Slice 5 entire: live sources, audio lane, offline pins, commercial directory on the shelf (§C.3 Slice 5) | unbuilt | MEDIUM | large | One ingest class at a time (D-I3/D-I5/D-I7), each behind the existing source interface |

### Attention plane (§C.2, §A.2.6)

| # | Promise | Status | Severity | Effort | Close |
|---|---|---|---|---|---|
| D-A1 | **Cross-stream change feed** as one ranked projection across all streams (§C.2.1) | partial — the console shows one camera's feed; no cross-stream projection exists | HIGH | medium | Write the `attention/feed.jsonl` projector over per-stream ledgers (also closes L3) |
| D-A2 | **Alert policy**: silence-by-default push, quiet hours, per-profile routing, "wake me" marks (§C.2.2) | unbuilt | MEDIUM | medium | A policy file + evaluator over the feed projection; no push channel exists yet either |
| D-A3 | **Auto-demotion** of any source whose measured precision drops below 0.9 (§C.2.2; panel-3 Q2 design) | unbuilt — corrections are recorded, nothing consumes them | HIGH | small | A periodic pass over corrections.jsonl computing per-stream precision + a demotion ledger note |
| D-A4 | **Rules 1–4** (door→pause+overlay, harbour→console raise, playback→budget drop, perceived→New rail) (§C.2.3) | unbuilt — no rule table, no evaluator | MEDIUM | medium | Rule table as ledger data + evaluator in the attention plane; rule 3 also needs D-Y3's budget hooks |
| D-A5 | **Bridge console**: one live page, every stream a tile, delta-rendered with deadband heartbeat (§C.2.4) | unbuilt — the Slice-1 console is feed+shelf for one stream | MEDIUM | medium | Extend the console into tiles over the feed projection (D-A1) |
| D-A6 | Plain-language controls: "Tell me now / Feed only / Never", "Pause everything", since-last-looked button (§C.2.5) | unbuilt (only "That wasn't a change" exists) | LOW | small | Console controls writing per-source policy + correction records |

### Budgets & tenancy (§B.2.2–2.3)

| # | Promise | Status | Severity | Effort | Close |
|---|---|---|---|---|---|
| D-B1 | **Per-stream budgets**: embed-seconds/hour + burst allowance, global ceiling, work-conserving scheduler (§B.2.2) | partial — the ledger *meters* spend and reports a ratio; nothing enforces a budget or borrows burst | HIGH | medium | A budget block in the lens/state + admission check in the cascade |
| D-B2 | **Plain-language knobs** ("spend freely / normal / sip / reflex only") compiled to shown numbers (§B.2.2) | unbuilt | MEDIUM | small | Knob→numbers table in config, rendered next to the word in the console |
| D-B3 | **Yield ladder**: foreign-work detection (2 s sampling), L1 backfill pause → L2 halve → L3 reflex-only → L4 model unload, 60 s hysteresis recovery, reserved watching pool (§B.2.3) | unbuilt — no rung is implemented in Confluence code; thor-admit (built-elsewhere, fleet tooling) only reaps unleased loads | HIGH | large | A tenancy module in the watch service: GPU/proc sampler + ladder state machine; L1/L3 are the cheap rungs |
| D-B4 | Class defaults + 7-day trailing baseline per stream (§B.2.2) | unbuilt | LOW | small | Baseline field in the lens, updated from the spend meter |

### The lens (§B.3)

| # | Promise | Status | Severity | Effort | Close |
|---|---|---|---|---|---|
| D-LN1 | LensFile full contents: **diurnal profile** (24 hourly drift quantiles), **ranker_calibration** weekly refit, **known_rhythms** propose/confirm, **exceptions** as negative exemplars (§B.3.1) | partial — the shipped lens carries rhythm + appearance baseline only | MEDIUM | medium | Extend `lens.txt` sections one at a time; exceptions first (corrections already exist to feed it) |
| D-LN2 | **Baseline admission + aging**: conservative admission rule, 14-day half-life decay, `lens: warming` label under 48 h, trust badge (§B.3.2, §B.3.3) | partial — baselines update in the soak build; no decay, no warming label, no admission deadband vs alerts | MEDIUM | medium | Admission/decay rules in the lens update path + a warming flag in state.txt |
| D-LN3 | **Pending-drift accumulator** → `slow-change` verdicts for slow-but-relentless movement (§B.3.2) | unbuilt | MEDIUM | small | An accumulator field per tile in state.txt, publishing once at threshold with the slow-change label |
| D-LN4 | **Trust accounting published per stream**: events fired / confirmed / dismissed, trailing 7-day precision estimate in the ledger (§B.3.3) | partial — state.txt carries "precision self-report placeholders" (the code's own words); no real accounting | HIGH | small | Compute from events + corrections in the ledger writer (shares machinery with D-A3) |
| D-LN5 | Feed trust target **≤1 false event/stream/day** verified on real streams (§B.3.3) | unbuilt as a measurement — the soak verdict (2026-11-03) is the first data | MEDIUM | small | Verdict analysis; then a standing per-stream false-rate line via D-LN4 |

### Library perception & index (§B.4)

| # | Promise | Status | Severity | Effort | Close |
|---|---|---|---|---|---|
| D-BK1 | Backfill **Pass 2 (STT transcripts)**, **Pass 3 (chapters/highlights/synopsis)**, **Pass 4 (deepening/re-embed)** (§B.4.1) | unbuilt — Pass 0+1 exist for images only; video got posters, not scene structure | MEDIUM | large | Pass 2 first (whisper already on the box from presence); each pass is its own lane |
| D-BK2 | **The index**: scene-embedding store, transcript full-text, moment-level join; day-one queries 1–6 as acceptance (§B.4.2–4.3) | unbuilt | HIGH | large | Brute-force cosine over stored embeddings (spec-sanctioned at household scale) + a query CLI before any UI |
| D-BK3 | Backfill queue order (newest → most-watched → smallest) + completeness % per title in the ledger (§B.4.1, §B.1.1) | partial — pass 1 used recency+size heuristics once; no standing queue, no completeness field | LOW | small | A queue file + completeness line in `items/<id>.txt` |

### Ledger (§A.2.3)

| # | Promise | Status | Severity | Effort | Close |
|---|---|---|---|---|---|
| D-L1 | `attention/feed.jsonl` — the cross-stream feed as a rebuildable projection file | unbuilt (see L3, D-A1) | MEDIUM | small | The projector in D-A1 writes it |
| D-L2 | `household/profiles.txt` | unbuilt — no profiles exist anywhere | MEDIUM | small | Created by D-S3; a stub with the household's real profiles is a one-file start |
| D-L3 | Events carry **per-stage receipts** (what each stage did, cost ms, decided) ranked by the attention plane (§A.2.3, §A.2.6) | partial — events.jsonl carries verdicts + service receipts; the attention plane that ranks from receipts doesn't exist | LOW | medium | Lands with D-A1's ranking inputs (drift, coherence, profile interest, recency) |

### Ingest classes (§A.3) & per-stream lanes (§B.1)

| # | Promise | Status | Severity | Effort | Close |
|---|---|---|---|---|---|
| D-I1 | **RTSP/ONVIF camera ingest** (§A.3.2) | unbuilt — sources are `shot` polling, `mjpeg`, `staged`, `wave3` replay; the one live camera is a custom outbound pusher, not RTSP | MEDIUM | medium | An RTSP source behind the existing source interface (GStreamer is on the box) |
| D-I2 | **LAN discovery** of thin devices (Amendment 1 §1; INSTALL's sweep) | unbuilt — honestly marked `[interface]` in the install docs; the ProArt pusher is hand-started | MEDIUM | medium | A sweep (ARP/mDNS/port probe) that writes discovered sources to config — the spec's own fallback is manual-IP entry |
| D-I3 | **HLS/live-stream ingest + live lane** with flagged moments (§A.3.3, §B.1.2) | unbuilt | MEDIUM | large | Segment-polling source + the camera lane reused at segment pace |
| D-I4 | **OTA tuner ingest** (§A.3.4) | unbuilt — no tuner hardware in evidence either | LOW | large | Hardware first (Casey's call); spec item can also be amended away |
| D-I5 | **Audio lane**: radio/podcast ingest, windowed perception (§A.3.5, §B.1.4) | unbuilt — STT exists only inside presence sessions | MEDIUM | medium | A podcast-file lane reusing presence's whisper path is the cheap first shape |
| D-I6 | **Screen/game capture lane** (§A.3.6) | unbuilt | LOW | medium | A frame-pusher source like the ProArt camera's, pointed at a desktop |
| D-I7 | **Sensor/text feeds** (scores, weather, RSS, household state) (§A.3.7, §B.1.5) | unbuilt | LOW | small | A polling text source emitting ledger observations — cheapest lane in the taxonomy |
| D-I8 | **Commercial-service directory entries** (metadata + deep links on the shelf) (§A.3.8, §C.1.6) | unbuilt | LOW | small | Item records with `external` type on the shelf; no ingest by design |

### Serve plane (§C.1)

| # | Promise | Status | Severity | Effort | Close |
|---|---|---|---|---|---|
| D-V1 | **Unified item model + rails** (Continue Watching, New Since You Last Looked, Live Now, per-source shelves) (§C.1.1) | partial — the console shelf lists media-dir items; no unified spine, no rails | MEDIUM | medium | Item spine over `items/*.txt` + rail rendering in the console |
| D-V2 | **Transcode ladder** original→1080p→720p→480p, client-chosen, per-profile quality pinning (§C.1.2) | partial — the player serves one rung (remux or single transcode); no ladder, no pinning | LOW | medium | Rung parameter on the existing transcode path |
| D-V3 | **Subtitle/transcript track in the player** ("transcript pending" as a normal state) (§C.1.2) | unbuilt | LOW | small | Serve the item's transcript file as a track once D-BK1 Pass 2 exists; the pending state is free today |
| D-V4 | **TV/kiosk client + phone-first attention client** (§C.1.3) | unbuilt — one responsive page serves all | LOW | medium | A kiosk layout mode on the same page; decided-by-use per spec |
| D-V5 | **Offline pins** with last-write-wins resume reconcile (§C.1.5) | unbuilt | LOW | medium | Client-side pin store + the resume state from D-S2 |

### Amendments & failure modes

| # | Promise | Status | Severity | Effort | Close |
|---|---|---|---|---|---|
| D-P1 | Presence session lends **camera + screen**, not just mic/speaker (Amendment 2 §1) | partial — mic/speaker/display-chat built; the terminal's camera is not a presence sense (the ProArt camera is a separate declared watch) | LOW | medium | A getUserMedia video track feeding a session-scoped stream |
| D-P2 | **From-the-chair presence acceptance** (Amendment 2, sequencing) | unbuilt as a test — never performed by a human (also in RESULTS' deficits, honestly) | HIGH | small (needs Casey) | One real conversation through the browser page, recorded as the acceptance |
| D-F1 | Failure modes: stream-down posts **one attention entry** + gap recorded, never backfilled (§A.2.8) | partial — the console health goes AMBER "NOT REPORTING"; no feed entry, no gap record | LOW | small | Emit the entry from the health transition (lands with D-A1) |
| D-F2 | Lane-family **two-failure halt-and-report** rule (§A.2.8) | unbuilt | LOW | small | A failure counter in the lane supervisor |
| D-F3 | Duplicate detection by **content hash at ingest** (§A.2.8) | unbuilt (backfill deduped by path/recency heuristics) | LOW | small | Hash at item creation, checked against `items/` |
| D-T1 | The spec's **TO-MEASURE index** (§A, after §3.9) still-open items: baseline stability over a week, yield latency + false-yield rate, lens half-life sensitivity, Whisper RTF, LLM cost/title, ABR matrix vs real clients | partial — several closed by the benches (transcode, NVENC); the six named remain open | LOW | medium | One measurement lane per item, or amend the index to drop what the build no longer needs |

---

## Counts

- **Numbers**: 10 flagged (3 HIGH, 5 MEDIUM, 2 LOW); 10 figure-groups
  verified clean against sources.
- **Links & refs**: 3 flagged (all MEDIUM); 0 dead Markdown links.
- **Spec-debt**: 35 items — 8 HIGH, 13 MEDIUM, 14 LOW. By status:
  22 unbuilt, 11 partial, 0 fully built-elsewhere (thor-admit is the
  nearest, and it covers none of the ladder's rungs by itself).

## Top 5 (fix these first)

1. **N3 — RESULTS claims the player can't ship H.265.** It can, by
   fMP4 remux, today. The ledger of record is wrong about the
   product's current capability. (HIGH, small)
2. **N1+N2 — the front door says 95 tests, twice, on the two pages
   a stranger reads first**, while the real count is 107 and the
   same files say so elsewhere. (HIGH, trivial)
3. **D-B3 — the yield ladder is entirely unbuilt.** The tenancy
   contract ("Casey's bench first; the platform yields") is the
   safety story for running this on his primary box, and right now
   it is doctrine, not code. (HIGH, large)
4. **D-A3 + D-LN4 — corrections are written and never read.** No
   auto-demotion, no published trust accounting: the feed's trust
   loop is open at exactly the point the spec (and panel round 3)
   says it must close. (HIGH, small)
5. **D-S2 — no resume anywhere.** Slice 2's headline promise and
   its pre-committed acceptance are unmet, and D-V5/D-S3 both
   depend on the same position-state machinery. (HIGH, medium)
