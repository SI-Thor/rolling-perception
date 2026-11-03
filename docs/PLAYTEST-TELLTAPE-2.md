# Cold playtest 2 — telltape v0.3.1

**Playtester:** a fresh agent, first contact with the project.
**Source:** public GitHub only — `git clone --branch v0.3.1
https://github.com/SuperInstance/telltape`. Nothing outside the
clone was read. No fixes made; friction recorded verbatim.
**Job I brought:** I run a small workshop with a camera over the
bench and want a daily answer to *"what moved in the shop while
I was out, and when?"* — in a form I can hand to someone else.
**Artefacts:** all under `~/workspace/cold-playtest-2/` —
`shop-seq/` (fabricated footage), `embed_server.py` (my BYO
server), `run-mode.sh` + `out-*.txt` (failure battery),
`ledger-*` (every ledger produced), `daily-answer.txt` /
`daily-answer.csv` (the hand-off artefact).

---

## Step-by-step

### 1. Clone and build (~20 s total, zero friction)

Clone 7.9 s. `cargo build --release` finished in 10.3 s;
`python3 -m venv .venv && pip install -r
crates/telltape/requirements.txt` (numpy, requests, Pillow)
clean. One environment note, not a repo defect: this machine
keeps cargo in `~/.cargo/bin`, off the default PATH — a
bare-shell stranger on a machine like this one gets
`cargo: command not found` from the quickstart's first line.

### 2. Staged acceptance — exact (~5 s)

Ran the README's acceptance verbatim. Output:
`{"frames":18,"events":2,"embeds":34,...}` and the ledger
shows frame 4 = all 16 tiles, frame 7 = exactly {5, 6},
`freshness = live`, `silence_meaningful = true`,
`embedder_identity = double@1` stamped in the lens. The
packaged `crates/telltape/acceptance.sh` the README mentions
exists. This is the tool showing its best self, and it earns it.

### 3. My own footage, test double — exact (~1 s)

Fabricated a 10-frame still sequence from the bundled photos
(512×512): frames 0–4 scene A (empty bench), 5–7 scene A with
the bundled `patch.png` pasted at rows 128–256 / cols 128–384
(an object on the bench), 8–9 scene B (different photo
entirely). `telltape index shop-seq --config shop.conf --fps 2`:

- frame 5 → verdict, tiles **[5, 6]** — the object, right tiles.
- frame 8 → verdict, **all 16 tiles** — the scene change.
- `freshness = footage`, `silence_meaningful = true`, lens
  records `time_anchor = file_mtime` — the recorded-footage
  semantics are correct and self-describing.

`query` on it is fast (instant), legible, gives local times
with epoch alongside, and annotates tiles with row/col.
The seek story works: frame 5 at 2 fps = 2.5 s into the footage.

### 4. `query --summary` on that ledger — one phantom (see S3)

The summary is good (by-hour, by-tile, spend) except its
"service-stopped stretches" section reports
`2026-11-03 07:15:39 AKST -> still open at the last row in the
filter` plus *"1 closing row(s) with no opening row in view"*
— for a run that completed normally. Details in S3 below.

### 5. Bring-your-own embedder — the long way round (~25 min)

I wrote a minimal server from the BYO doc's contract: stdlib
Python, POST multipart field `file` → `{"embedding": [...]}`,
feature = tile downscaled to greyscale, L2-normalised,
`--embed-dim 256`.

**Detour 1 — the undocumented health gate.** First run refused
instantly:

```
telltape: embedder not healthy at http://127.0.0.1:9000/health (embedder_autostart=false, start_cmd unset)
```

The BYO contract doc never mentions a health endpoint; the
doc's own server sketch has no GET handler at all, so anyone
following the sketch literally hits this. I found the rule only
by grepping the clone's *source* (`config.rs`: the service
derives `{embed_url origin}/health`, any HTTP 200 counts;
`embed_health_url` overrides). The only doc mention is one line
in BUILD-LOG.md. The error message itself is loud and precise —
the *requirement* is what's undiscoverable. (S1)

**Detour 2 — my black tile is a zero vector.** With `/health`
served, the probe refused:

```
ingest: embedder probe failed: embedder http: probe embedding is degenerate (zero norm) — a vector with no information cannot be scored; refusing to start
```

My luminance features map a genuinely black tile to all-zeros.
The refusal is correct behaviour and a superb message; I fixed
my server the way practitioners do (constant bias component).
The doc never warns that "black tile → zero vector" is a shape
an honest embedder can produce. (W4)

**Then it ran** — and with the default threshold it was
nearly deaf: frame 5 (object) **missed entirely**; frame 8
(full scene change) flagged only tiles {9, 10, 13, 14}. The
ledger's frame-8 row shows why: raw scores 0.02–0.16 for 12 of
16 tiles against threshold 0.25 — my geometry compresses
distances, and 0.25 was calibrated on I-JEPA.

**Calibration is where the docs strand you.** The BYO doc
says: *"index a known stretch, read the raw scores in the
ledger's per-tile rows, and set the threshold from what your
scenes actually score."* But a frame that doesn't publish
leaves **no row anywhere** — the missed frame-5 scores exist
nowhere in the ledger, so the most important calibration data
(the near-miss) is unobservable. And the `threshold` config key
itself appears in **no user-facing doc** — I found it in
`crates/telltape/src/config.rs`. There is no config reference
in `docs/` at all. (S2)

Source-diving anyway, I set `threshold = 0.05` and re-ran:
frame 5 → **[5, 6] exactly**; frame 8 → 13 of 16 tiles (the 3
missed tiles are low-luminance-contrast regions — a fair limit
of my toy embedder, not the tool). The tool *can* answer my
question with my embedder; reaching that state required
reading source code twice.

### 6. The failure battery — what a failing embedder does

Same footage, my server in sabotage modes (full outputs in
`out-*.txt`):

| Mode | Result | Grade |
|---|---|---|
| all zeros | Probe refusal, exact message, exit 1 | ✅ loud |
| all NaN | Probe refusal ("non-finite component"), exit 1 | ✅ loud |
| wrong width (128 vs 256) | Probe refusal naming both numbers, exit 1 | ✅ loud |
| dies mid-run → zeros at call 21 | Run stops at frame 8 tile 1; typed error; ledger carries a `degenerate_embedder` service event: *"degenerate embedding refused at frame 8 tile 1 (zero norm); run stopped — a broken embedder must not produce a confident ledger"* | ✅ exemplary |
| dies mid-run → HTTP 500 | Run stops, exit 1 — but the user sees a raw Python traceback, and the ledger gets **no closing receipt at all** (only `start`), while `health.txt` still claims `embedder = up`, `silence_meaningful = true` | ⚠️ S4 |
| **constant vector** (same valid vector for every tile) | **Run completes: 0 events, exit 0, `silence_meaningful = true`** — over footage containing an appearing object *and* a full scene change | ❌ **B1** |
| random vectors (valid, unit-norm, different every call) | 1 event: frame 8, 9 tiles — a plausible-looking partial answer to a question the embedder knew nothing about | ⚠️ noted |

The **constant** case is the one that matters. Every check in
v0.3.1 passes it: right width, finite, non-zero norm, different
from nothing — it just never *varies*. The tool then certifies
the one thing my job cannot tolerate: authoritative, meaningful
silence over a shop where things demonstrably moved. Query's
daily answer for that ledger is a clean "(no verdicts)" with
start/stop rows — indistinguishable from a genuinely quiet
night. Nothing in health, state, or query reports embedding
variance, distinct-vector counts, or anything else that would
let blindness be seen. The degeneracy net catches a *dead*
embedder; a *collapsed* one sails through and the silence keeps
its "meaningful" stamp.

The random case is lesser but real: garbage that varies
produces verdict-shaped output (the pixel gate paces it — only
nominated tiles get embedded, so the chaos is bounded — but
the frame-8 verdict looks like knowledge).

### 7. Live watch against a frozen feed — correct (~2 s)

Served one still PNG over HTTP and ran `watch` with the
`shot` source, 6 frames: `freshness = frozen`,
`frames_novel = 1`, `frames_repeated = 5`,
`silence_meaningful = false`, a `source_frozen` receipt in the
ledger, and a console warning
`[telltape] source frozen: repeated frames, silence no longer
meaningful`. The dead-camera case — my 3 a.m. scenario on the
*live* side — is told truthfully and in detail.

### 8. The daily answer, handed over

From the calibrated run (`ledger-shop-http3`): `query
--summary` → `daily-answer.txt`; `export --format csv --out
daily-answer.csv` → clean CSV (the `--out` confirmation goes
to stderr, stdout stays pure — a thoughtful touch). JSON
export is full-fidelity and handles even the partial
degenerate-stopped ledger without complaint. Two blemishes in
the hand-off artefacts: the phantom open "service-stopped
stretch" (S3) is in the summary, and the CSV's
`verdict_latency_ms` column shows **147566.792** for a
two-second indexing job over stills — the number is processing
lag behind an mtime-derived timeline, but the basis label that
exists in the run-summary JSON does not travel into exports
(S5), so a spreadsheet reader meets a 2.5-minute "latency"
with no explanation.

---

## Friction list, ranked

### Blocker

- **B1 — A collapsed embedder produces authoritative false
  silence.** A server returning the same finite, unit-norm
  vector for every tile passes the probe and every per-call
  check; telltape completes the run with 0 events and
  `silence_meaningful = true` over footage containing an
  object appearing and a wholesale scene change. Query then
  presents an empty, well-formatted "nothing moved" answer.
  v0.3.1's degeneracy rule (zero / non-finite / width) cannot
  see variance collapse, and no surface (health, state, query,
  export) reports embedding variance or distinctness. For
  unattended use this is worse than the round-1 zero-vector
  bug: that failure is now loud; this one is silent *and*
  stamped meaningful.

### Stumbles

- **S1 — The `/health` requirement is undocumented in the
  contract.** Setting `embed_url` makes the service poll
  `{origin}/health` and refuse to start without a 200. The BYO
  doc's contract section and its server sketch (no GET
  handler) omit it entirely; the only mention is BUILD-LOG.md
  line 52. Every first-time BYO user following the docs hits
  the refusal. (The refusal message itself is clear — the
  requirement is what can't be discovered.)
- **S2 — Calibration is advised but unreachable.** (a) The
  default threshold 0.25 is deaf for non-I-JEPA geometries:
  with an honest luminance embedder, a full scene change
  scored 0.02–0.16 on 12 of 16 tiles. (b) The doc's calibration
  method — read raw scores from the ledger's per-tile rows —
  fails exactly where needed: unpublished frames leave no
  rows, so a near-miss's scores are unobservable. (c) The
  `threshold` config key appears in no user doc; there is no
  config reference in `docs/`. I reached a correct calibration
  only by reading `config.rs`.
- **S3 — `query --summary` invents an open "service-stopped
  stretch" for every completed run.** It pairs stop→start, so
  a finished index/watch run's terminal `stop` renders as
  `… -> still open at the last row in the filter` with a note
  about "closing row(s) with no opening row in view". In the
  artefact meant for handing to someone else, this reads as
  "the service is down / a stop is unexplained".
- **S4 — Transport failures leave an unclosed, over-claiming
  ledger.** On HTTP 500 mid-run: no stop/abort/ failure receipt
  in `events.jsonl` (contrast the degenerate path's exemplary
  receipt), a raw Python traceback as the user-facing error,
  and `health.txt` still asserting `embedder = up` and
  `silence_meaningful = true`. A health-only reader is told
  the opposite of what happened.
- **S5 — `verdict_latency_ms` travels into exports without its
  basis.** The run summary labels it
  (`processing_lag_behind_footage_timeline`); export JSON/CSV
  carry the bare number (147,566 ms for a 10-frame still
  sequence), inviting a confident misreading.

### Warts

- **W1 — Intermittent Python `BrokenPipeError` traceback on
  ingest shutdown.** Seen after the mid-run degeneracy refusal
  and on one of two identical frozen-watch runs (the other was
  clean). Noise splashed across the exact runs a user inspects
  most closely.
- **W2 — The doc's server sketch doesn't parse multipart.** It
  passes the whole multipart envelope to `embed()` and punted
  parsing to a comment. Writing a correct stdlib parser is
  doable but is real work the sketch pretends away.
- **W3 — `health.txt` says `embedder = up` in refused
  ledgers.** In the zeros/NaN/width ledgers the health file
  claims the embedder is up (the /health endpoint did answer)
  in the same ledger where the probe refused it. Narrowly true,
  broadly misleading.
- **W4 — "Black tile → zero vector" is a real embedder shape
  the doc never mentions.** Sparse/luminance-style features
  legitimately produce exact zeros on black tiles; the probe
  refuses them with no hint in the docs that this is a known
  shape with a known remedy (bias component / offset features).
- **W5 — Absent surfaces a stranger looks for:** a config
  reference (keys, defaults); any way to inspect scores for
  frames that didn't publish; an explanation anywhere in
  `docs/` of the `focus` field that verdict rows and CSV
  exports carry.

### What was genuinely good (a cold reader's praise is earned)

- Error messages on the checked paths are the best I've met in
  a tool this size: they name the defect, the numbers, and the
  fix ("probe returned dim 128, expected 256 — fix
  --embed-dim or the service").
- The mid-run degeneracy refusal — typed error + a receipt in
  the ledger explaining *why the run stopped* — is the
  standard other tools should be held to.
- Frozen-feed accounting (novel vs repeated frames,
  `silence_meaningful = false`, receipted) is exactly right.
- Identity, freshness, and time-anchor are stamped in the
  ledger where a later reader can't miss them; exports are
  full-fidelity; query is instant and legible; `--out` keeps
  stdout pure.

---

## Adoption verdict

Would I run this unattended over my workshop? **Not yet with
an embedder I brought myself — yes with the shipped double or
a known, calibrated model, and even then I'd read the first
week's ledgers by eye.** The pipeline, the gate economics, the
frozen-feed honesty, and the refusal discipline on every
*failure the authors imagined* are genuinely strong; the tool
found my object at the right tiles and the right second, spent
a fifth of the naive embed budget doing it, and every loud
failure was loud in the right words. But unattended use lives
or dies on the failures that don't announce themselves, and
this build still certifies meaningful silence from an embedder
that has collapsed to answering one vector forever — I proved
that with ten lines of sabotage and an empty ledger over a
shop where everything moved. **The first thing I'd change:**
give the seam a variance watch — count distinct embeddings,
track the score distribution's spread, and let `health.txt`
say "embedder answering but its answers never vary" with the
same receipted bluntness the degenerate path already has.
Until then, the silence stamp is only as trustworthy as the
embedder, and the tool can't tell me how trustworthy that is.

---

## Appendix — verbatim outputs

**A. Health refusal (S1), first BYO attempt:**
```
telltape: embedder not healthy at http://127.0.0.1:9000/health (embedder_autostart=false, start_cmd unset)
```

**B. Probe refusals (zeros / NaN / width):**
```
ingest: embedder probe failed: embedder http: probe embedding is degenerate (zero norm) — a vector with no information cannot be scored; refusing to start
telltape: ingest: ingest command exited with exit status: 2 after 0 frames
```
```
ingest: embedder probe failed: embedder http: probe embedding is degenerate (non-finite component) — a vector with no information cannot be scored; refusing to start
```
```
ingest: embedder probe failed: embedder http: probe returned dim 128, expected 256 — fix --embed-dim or the service
```

**C. Mid-run degeneracy (flaky mode) — terminal error and ledger receipt:**
```
telltape: pipeline: record seq 0 has a degenerate embedding (zero norm) at frame 8 tile 1: the vector carries no information and must not be scored
{"kind":"service","event":"degenerate_embedder","msg":"degenerate embedding refused at frame 8 tile 1 (zero norm); run stopped — a broken embedder must not produce a confident ledger","wall_us":1793722749158789}
```
followed in the console by (W1):
```
BrokenPipeError: [Errno 32] Broken pipe
Exception ignored in: <_io.TextIOWrapper name='<stdout>' mode='w' encoding='utf-8'>
```

**D. HTTP 500 mid-run (boom mode) — the whole user-facing error:**
```
requests.exceptions.HTTPError: 500 Server Error: Internal Server Error for url: http://127.0.0.1:9000/embed
telltape: ingest: ingest command exited with exit status: 1 after 8 frames
```
Ledger state afterwards: one `start` service row, no closing
row; `health.txt`: `embedder = up`, `silence_meaningful = true`.

**E. Constant embedder — the complete run summary over footage
with an appearing object and a full scene change (B1):**
```
ingest: embedder http ok (dim 256)
{"frames":10,"events":0,"embeds":34,"embeds_spent_s":0.136,"embed_everything_estimate_s":0.638,"verdict_latency_p50_ms":0.000,"verdict_latency_max_ms":0.000,"verdict_latency_basis":"processing_lag_behind_footage_timeline","embedder_started_by_me":false,"embedder_stopped_by_me":false}
```
and `health.txt`: `embedder = up` / `silence_meaningful = true`;
`query`: `TELLS (no verdicts under these filters)`.

**F. Random embedder verdict (garbage in, verdict-shaped out):**
```
verdict frame 8 [1, 2, 5, 6, 10, 11, 13, 14, 15]
```

**G. Default-threshold deafness — frame-8 raw scores under a
luminance embedder at a full scene change (threshold 0.25):**
tiles 0–15 raw: 0.0728, 0.0385, 0.0789, 0.0215, 0.0419,
0.0567, 0.0583, 0.0426, 0.1273, **0.3051**, **0.3063**, 0.0909,
0.1578, **0.3169**, **0.4529**, 0.1355 (bold = published as
changed). Frame 5 (the object) published nothing and left no
row in any ledger file.

**H. Phantom stopped stretch in `query --summary` of a
normally completed run (S3):**
```
service-stopped stretches (stop -> start)
  2026-11-03 07:15:39 AKST -> still open at the last row in the filter
  note: 1 closing row(s) with no opening row in view (the opening row is outside the filter, or predates this ledger)
```

**I. Frozen live feed — console + health (the good kind of loud):**
```
[telltape] source frozen: repeated frames, silence no longer meaningful
freshness = frozen
frames_novel = 1
frames_repeated = 5
silence_meaningful = false
```

**J. Timings (this machine):** clone 7.9 s · release build
10.3 s · staged acceptance 4.9 s · index of 10 frames 0.9–2.0 s
· query/export effectively instant · BYO server, first working
version: ~25 min including both detours.
