# TELLTAPE P4 — staged acceptance against a REAL embedder, generic HTTP adapter

**Status: CLOSED, all canonical numbers reproduced, no deviations.**
Run 2026-11-02 on the Thor by the TELLTAPE-P4 lane. This was the
extracted repo's last unverified battery item (plan §5, P4): inside
telltape itself, the staged acceptance had only ever run through the
hash test-double. The real-embedder record existed for the parent
project (confluence-watch, Slice 1); it now exists for telltape.

## Setup

- Source: the extracted repo (`~/workspace/rolling-perception-work/
  extracted/`, v0.1.1) copied to `~/confluence-play/telltape-p4/` on
  the Thor (target/ and .git excluded), built there with the Thor's
  cargo 1.99.1: `cargo build --release -p telltape` (clean, 1.35 s).
- Embedder: the live JEV rack on `http://127.0.0.1:8077` (I-JEPA
  ViT-H, 1280-dim; `/health` reported `{"ok":true, "loaded":
  {"ijepa":true, …}}` before the run), reached **through the generic
  HTTP adapter — not the `jev` adapter**: `--embedder http
  --embed-url http://127.0.0.1:8077/embed/image` with the documented
  defaults (multipart field `file`, response key `embedding`,
  `--embed-dim 1280`). That is the stranger's path: the same wire
  contract `docs/BRING-YOUR-OWN-EMBEDDER.md` specifies for any
  operator's own service. The adapter's startup probe passed against
  the real rack (`embedder http ok (dim 1280)`).
- Run: `telltape watch --config p4.conf`, config carrying
  `ingest_cmd = python3 …/ingest/ingest.py --source staged
  --embedder http --embed-url http://127.0.0.1:8077/embed/image
  --gate 3.0 --cadence-ms 50`, `max_frames = 18`, system python3.
  Threshold/α/focus at the tool defaults (0.25 / 0.1 / 4) — the
  values calibrated on I-JEPA in the origin record.
- The 48 h soak was running throughout (confluence-watch PID
  1049389, rack owned by it). This lane made 35 read-only embed
  calls (34 run + 1 probe) against the rack — about a minute of
  soak-class traffic — and started/stopped nothing:
  `embedder_started_by_me = false`, `embedder_stopped_by_me =
  false`. `~/confluence-play/slice1` was not touched. Post-run:
  soak process alive, rack still `active`.

## Numbers, as measured

| Check | Expected | Measured |
|---|---|---|
| Frames | 18 | **18** |
| Events published | 2 (frames 4, 7) | **2 (frames 4, 7 only)** |
| Embeds total | 34 (16+16+2+0) | **34** (frame 4 row: 16; frame 7 row: 2; the remaining 16 are frame 0's baseline, the only other nominating frame per the gate-layer proof) |
| Frame 4 (cut) verdict | 16/16 tiles | **16/16** — changed_tiles [0…15], lineage 31, smoothed scores 0.350–0.639, all above the 0.25 threshold |
| Frame 7 (object) verdict | exactly {5,6} | **exactly [5, 6]** — smoothed 0.542 / 0.611 |
| Drift frames 10–17 | silent | **silent** — no verdicts |
| Spend ratio | 0.118 (canonical) | **0.1181** (4.138 embed-s spent vs 35.053 s embed-everything estimate) |

Embed latency against the real rack, under concurrent soak load:
`embed_ms` p50 **91.4 ms**, p99 **339.7 ms**, n = 34 (ledger
health.txt). Verdict latency p50 212.8 ms; max 2,119 ms on the
16-embed cut frame (embeds are sequential in the ingest). These are
operating numbers, not acceptance criteria; they are recorded
because they are what a stranger on this class of box, sharing the
embedder with another tenant, would see.

## v0.1.1 identity check (D1)

The config declared the identity the way `index` derives it for
this adapter: `embedder_name = http`,
`embedder_version = http://127.0.0.1:8077/embed/image`. After the
run, all three ledger files carry it verbatim:

- `lens.txt`: `embedder_identity = http@http://127.0.0.1:8077/embed/image`
- `state.txt`: same line, plus `embedder = up`
- `health.txt`: same line

So a later run pointing this ledger at a different endpoint — or
the same endpoint re-declared under a bumped version — refuses as
a swap unless recalibrated, exactly as D1 specifies. (The refusal
path itself was already exercised in the v0.1.1 test suite; this
run verifies the positive half end-to-end against a real embedder:
the identity is written, by the generic-HTTP path, on a real run.)

## Deviations

None in the acceptance numbers. Every canonical figure from the
test-double battery (18 / 2 / 34, 16/16, {5,6}, drift silent,
spend 0.118) reproduced exactly through a real perception model
over the generic adapter — which is also the cross-check the seam
was designed for: the pipeline cannot tell the double from I-JEPA,
and now the verdict layer is proven on both.

## Cleanup

`target/` (2.5 MB) removed from the Thor scratch dir; the scratch
keeps the source tree, `p4.conf`, the `run-p4/` ledger + logs +
checker script, and a one-page `P4-RESULTS.md`. Thor disk posture
unchanged (92% used, ~80 GB free, as found). No pushes; no changes
to the extracted repo's code — the only new file is this record.
