# W3-JEV — Jev (TypeSafe hosted) as the reflective judge over harbor-watch candidates

**Status: EVALUATION BLOCKED on a rejected credential — routes proven, candidates
built, runner ready. No Jev numbers are claimed anywhere in this file, because
no Jev call has yet succeeded in this lane.** (Repo rule: no claim without a
measurement; a blocked measurement is reported as blocked, not simulated.)

Naming, kept distinct throughout: (1) **TypeSafe hosted Jev** (`jev-latest`,
typed `noul`/`choice` over text states) — the subject of this lane;
(2) **jev-semantic** — the local ONNX student in the Thor rack, a
wording-sensitive fluency prior, not evaluated here; (3) the **JEV rack** —
Thor :8077 I-JEPA/V-JEPA embeddings + that local student. This lane is
about (1) only, in the fleet's established split: *Syzygy/harbor-watch
measures, Jev judges.*

## Route investigation (both routes tried, evidence recorded)

### Route A — through the pi agent on the Oracle: FAILS CLEANLY (not configured)
- pi is installed and drives headlessly (`~/.local/bin/pi`, v1.4.0 harness).
  Its spool bridge from the three-speed lane still exists
  (`~/pi-three-speed/spool/{req,ans}`, client `omods/reflex.py`): Oracle-side
  code drops `{text}` request files; a bridge process on the agent VM answers
  them by calling Jev here — i.e. the spool is a *transport*, and its Jev
  calls land on the same credential as route B.
- Decisive check, run 2026-11-01: `pi --list-models` shows only providers
  **kimi-coding** and **minimax**; `pi auth check --provider typesafe --json`
  returns `{"status":"not_ready","provider":"typesafe","reason":"credentials_not_configured"}`.
  Provider *data* for TypeSafe exists on disk (Casey's recollection is right
  about the install), but no TypeSafe credential is configured in pi today,
  so Jev cannot be reached through pi. (auth.json was never read.)

### Route B — TypeSafe connector tooling directly: BLOCKED (credential rejected)
- Tooling: `~/workspace/skills/typesafe/bin/jev.py` (the
  custom-connectors copy has a stale `sys.path` and dies on import; the
  skills copy imports the documented helper correctly).
- Verified the request *carries* the credential: the entry for
  `custom.typesafe` resolves and `add_surrogate_to_request` attaches an
  `Authorization` header. Per the connector doc, a bare request and a
  rejected credential look identical — this one is the second kind.
- With the credential attached, both `GET /v1/models` and
  `POST /v1/systemone` return **HTTP 401** from api.typesafe.ai
  (2026-11-01, both helper copies tried).
- The doc's remedy at this exact point is `credentials.request_api_access`
  (reconnect) for `custom.typesafe`. That tool is not available to this
  subagent lane. **Parent action that unblocks everything below: reconnect
  the TypeSafe credential, then run `run_jev.py` (≈1–2 min at the direct
  route's historical ~0.5 s/call).**
- Historical calibration (three-speed, 2026-10-27, for when it runs):
  direct Jev ≈ 0.52 s/call; via the pi spool bridge ≈ 4–5 s/call uncached.
  This lane's runner uses the direct route, so its latencies will be
  direct-route numbers.

## Candidates (built and ready)

From the harbor-watch fixture (`--make-fixture`, 12 frames × 16 tiles,
ground truth in `fixture.jsonl.truth.jsonl`): the pipeline flags 5 tiles
raw (3 true scene-change tiles at frame 4, cosine ≈ 1.0; 2 false positives,
frames 6–7 tile 9, cosine ≈ 0.35 with near-zero pixel diff — embedding moved,
pixels didn't). Candidate set (`candidates.jsonl`, 15 states, built by
`make_candidates.py`): every tile with raw score ≥ 0.02 (the 5 flagged, plus
4 persistent low drift tiles at ≈ 0.03) + 6 background negatives (≈ 0.006).
Each candidate is a compact text state in the Syzygy digest style — tile id,
frame, pixel_diff_score, embedding_change_score, neighbours flagged,
sheaf-smoothed score, system flag — numbers only, recomputable from the
verdicts. No pixels cross to Jev.

**Question (one `noul` per candidate):** "Is this a real scene change in
this tile, rather than noise, a lighting shift, or sensor jitter?" —
true: large embedding change *corroborated* (substantial pixel diff or
neighbours changing together); false: embedding moved while pixels barely
changed, or small/isolated/uncorroborated.

**Borderline band (defined from the measured score distribution):**
raw score ∈ [0.15, 0.60] — the region where the 0.25 threshold decision is
contestable. It contains exactly the 2 false positives (the sheaf-refined
verdict already rejects both; Jev would be a second, independent opinion).

**Scoring plan (computed by comparing `jev_verdicts.jsonl` to truth):**
agreement of Jev with raw and with refined verdicts; latency p50/p95;
precision/recall delta under (i) Jev as tie-breaker inside the borderline
band only, (ii) Jev as a gate on all system-flagged candidates. Design
rule held throughout: Jev is an evaluated layer, never the sole decider —
the deltas decide whether it earns the reflective seat.

## Driver-lane real data
`wave3/driver/` currently holds only the schema/ground-truth/driver script
(no real JSONLs yet — that lane is still running). When its
`embeddings_ALL.jsonl` lands, the same runner takes the real candidate set
with no code change beyond candidate extraction.
