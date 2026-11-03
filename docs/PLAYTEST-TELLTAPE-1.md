# Cold playtest — telltape (github.com/SuperInstance/telltape, v0.2.0 @ 647542d)

**Playtester posture:** first contact. Nothing read outside a fresh
clone of the public repo. The job I brought: *I have security-camera
footage; tell me what changed, where in the frame, and when — and how
I jump to that moment in my footage.*
**Machine:** Linux VM, Rust 1.99.1, Python 3.12.3, ffmpeg present.
**Total session:** ~35 minutes of work inside ~5 minutes of tool time;
every command below was run as written.

---

## Step-by-step

### 1. Clone and build — no friction (≈45 s total)

```
git clone https://github.com/SuperInstance/telltape.git   # 9 s
cargo build --release                                     # 12 s, clean
python3 -m venv .venv && .venv/bin/pip install -r crates/telltape/requirements.txt
                                                          # 20 s (numpy, Pillow, requests)
```

The README quickstart is copy-paste accurate, including the PEP 668
warning. This is the smoothest part of the product.

### 2. The staged acceptance — works exactly as promised (≈3 s)

Ran the README's `acceptance.conf` verbatim with the venv active.
Output matched the documented expectation to the digit: 18 frames,
**2 events, 34 embeds**, frame 4 = all 16 tiles, frame 7 = exactly
{5, 6}, drift silent. `health.txt` reads sensibly. Full marks — with
one seed planted here that sprouts in §5: the ledger this tutorial
just created is stamped `embedder_identity = unknown`, even though
everyone involved knows the embedder was the test double.

### 3. Indexing "my footage", attempt 1 — my footage was the problem (5.5 s)

I built a 12 s mp4 from the bundled wave-3 photos (six A photos, then
six B photos) and indexed it with the README's `index.conf` verbatim.
Result: 24 frames (the sampler took 2 fps; my stills each lasted
1 s), **11 events**, every one a full 16-tile verdict, embeds 192,
spend ratio 50%.

First reaction: "the tool cries wolf." Second, honest reaction: my
footage was six *different photographs* in a row — of course every
tile changed. The tool was right about my input. But a real first
user will have this exact experience with real footage and the test
double, and nothing in the README's index recipe warns them that the
double's distances saturate — any visible difference reads as maximal
change. (The BYO-embedder doc *does* say this, plainly. The README
path that leads a stranger to `index` never points at that sentence.)

Also in this run's summary JSON: `verdict_latency_p50_ms: 16649.953`.
Nothing in the output tells a stranger that for indexed footage this
number is *processing lag behind the footage timeline*, not "the tool
took 16 seconds to notice." See friction F4.

### 4. Indexing, attempt 2 — a fair camera scene, and the tool shines (≈4 s)

Built a proper test: a static 512×512 yard scene, 10 s at 2 fps, with
the bundled `patch.png` object pasted at the fixture rig's own
rectangle from t = 6 s on. Indexed it the same way.

Result: **20 frames, exactly 1 event — frame 12, tiles [5, 6]** —
precisely where and when I put the object. 18 embeds total (16
baseline + 2), spend 0.141 s against a 2.506 s embed-everything
estimate (5.6%). Frame 12 ÷ 2 fps = 6.0 s into the file: the seek
story works, and the answer to my job's question is *in* the ledger.

Two shadows on this otherwise clean run:

- During the run, stderr printed `[telltape] source frozen: repeated
  frames, silence no longer meaningful` three times, and the finished
  ledger's `health.txt` ends `freshness = frozen`,
  `silence_meaningful = false` — because the last stretch of a
  *static scene in a file* is pixel-identical frames. For a live
  camera that alarm is the product's best idea. For recorded footage
  it is a category error: the file cannot "die," the tool *did* watch
  every frame, and the health file of a successful index run now
  reads like a failure. See F3.
- The same run's summary: `verdict_latency_p50_ms: 28994.084` for a
  20-frame file processed in ~3.6 s of wall time. See F4.

### 5. The identity trap — the tutorial's own ledger refuses its own embedder

Curious about the `unknown` identity from step 2, I did what
docs/LEDGER-FORMAT.md teaches: declared the embedder properly
(`embedder_name = double`, `embedder_version = 1`) and re-ran the
acceptance against the existing ledger. Result, exit 1:

```
telltape: embedder identity mismatch: this ledger was written by embedder
'unknown' but the configured embedder is 'double@1'. … Refusing to
continue; to accept the swap and recalibrate, set recalibrate = true …
```

The error message itself is excellent — it names both identities and
the remedy. The trap is upstream: the README's quickstart config
never declares the identity, so the first ledger every new user
creates is `unknown`, and the first time they follow the format doc's
guidance they are refused by their own tutorial ledger. Meanwhile
`index` stamps `double@1` automatically (both my index ledgers show
it), so the two verbs teach opposite habits. See F2.

### 6. Query — the best surface in the tool (0.02 s)

`telltape query ledger-yard`, `--tile 5`, and `--summary` are fast,
legible, and honest (the header declares which clock each row type
uses; filters behave; malformed-row accounting exists; read-only).
This is how the ledger becomes an answer to "what changed, where,
when": one tell, human time, frame 12, tiles [5, 6] (r1c1, r1c2).

Notes: with `TZ` unset on this machine, times rendered in UTC — my
tell displayed as **2026-11-03** 01:15 UTC, a day ahead of the local
calendar date (US/Alaska) a user would expect; the docs' examples
show local time and the quickstart never mentions TZ. And
`--summary`'s frozen-stretch pairing is wall-clock based, so on fast
index runs it prints stretches of **(0s)** — noise that makes a
careful feature look sloppy. See F3/F7.

### 7. The real-embedder journey — where the docs stop, and what I found there

docs/BRING-YOUR-OWN-EMBEDDER.md gives the HTTP contract (multipart
PNG in, JSON vector out, width checked at startup probe) and a
stdlib server sketch. I ran the sketch **verbatim** — its `embed()`
returns `[0.0] * 1280` — and pointed the staged acceptance at it via
`--embedder http --embed-url http://127.0.0.1:9000/embed`.

Result: **18 frames, 2 events, 34 embeds, frame 4 = 16/16,
frame 7 = {5, 6}.** The canonical acceptance, reproduced perfectly
by an "embedder" that returns a zero vector for every tile — the
least informative embedding mathematically possible.

The mechanism is in the repo's own code
(crates/harbor-watch/src/rng.rs): `cosine_distance` returns **1.0 —
maximal distance — whenever either vector has zero norm**. So every
nominated tile scores a maximal "changed," the verdict layer
rubber-stamps whatever the pixel-diff gate nominated, and the gate's
nominations on the staged material happen to be exactly the ground
truth — so the run *looks* perfect. The startup probe checks width
only (the doc says so); nothing anywhere checks that embeddings are
non-degenerate, and `health.txt` for this run reports
`embedder = up` like any other.

A stranger's real embedder failing this way is not exotic: a model
that failed to load, an endpoint returning placeholder zeros, would
produce a confident, plausible ledger of "changes" that are really
just pixel-diff nominations wearing maximal scores (raw = 1.0 in the
rows I inspected). The tool's whole promise is "a watch that doesn't
guess"; here it guesses silently. See F1 — the finding of this
playtest.

(The docs' journey also ends here by design: no model is bundled,
for stated licence reasons. The contract and sketch are genuinely
clear; a stranger with a model to wrap is carried. A stranger
without one gets pipeline proof only — acceptable, and honestly
labelled in the README's layer-honesty section.)

### 8. The proof battery — passes, with one dangling pointer

```
cargo test --workspace     # 116 passed, 0 failed (≈20 s)
python3 crates/telltape/prove_fixtures.py   # ALL PASS (≈2 s)
```

But prove_fixtures' own closing note says verdict-layer acceptance
"runs through the built-in test double (**acceptance.sh**)" — and
fixtures/README.md likewise cites `../acceptance.sh`. **There is no
acceptance.sh anywhere in the repo** (`find` = 0). The README's
inline config is the real path; the script is a ghost. See F5.

### 9. Error-path probes

- `telltape query ledger-nope` → `telltape query: no such ledger
  directory: ledger-nope`, exit 1. Clean.
- `telltape --help` / `telltape query --help` → real usage text,
  including the time grammar. Good.
- Bare `telltape` → `config: cannot read config telltape.conf: No
  such file or directory`, exit 2. No usage shown.
- `telltape bogusverb` → *not* refused as an unknown verb; it falls
  through to the same missing-default-config error. The failure
  points at the wrong problem. See F6.

---

## Friction list, ranked

### Blocker

**F1 — A degenerate embedder silently produces a perfect-looking,
wrong ledger.** Zero-norm embeddings score maximal distance (1.0)
by construction; the startup probe checks width only; health
reports the embedder "up." Reproduced end-to-end with the BYO doc's
own verbatim sketch server. Any real-world embedder failure that
returns zeros/constant vectors turns the tool into a pixel-diff
echo with maximal confidence scores, and neither the run output nor
the ledger warns. This is the one place the tool's output would
actively mislead a user who trusted it.

### Stumbles

**F2 — The quickstart sets an identity trap.** README acceptance
config declares no embedder identity → ledger stamped `unknown` →
declaring the true identity later (as the format doc teaches) is
refused against the tutorial's own ledger until `--recalibrate`.
`index` auto-stamps `double@1`; `watch` doesn't. One line in the
README's config (or watch behaving like index) closes it.

**F3 — "Source frozen" semantics leak into recorded footage.** A
static-scene file finishes with `freshness = frozen`,
`silence_meaningful = false`, stderr alarms during the run, and
0-second "frozen stretches" in `query --summary`. The live-feed
alarm is a genuinely good idea; applied unchanged to files, it
teaches users to distrust the health file — the one file whose
whole job is to be trusted.

**F4 — `verdict_latency_ms` in index summaries reads as detection
latency.** 16.6 s and 29.0 s "p50" figures on files processed in
seconds. It's processing lag behind the footage timeline; nothing
in the summary a stranger sees first says so.

**F8 — For indexed footage, "when" is anchored to the file's mtime,
not the recording's clock.** The ingest derives frame 0's epoch as
*mtime minus duration* (documented only in `ingest.py --help` and a
LEDGER-FORMAT pointer to "the ingest header"). For an NVR export —
the README's headline use case — mtime is export/copy time, so
every tell's wall-clock time is silently wrong by the age of the
copy. The frame-number seek key stays true; the timestamp seek key
doesn't, and nothing in the ledger says which anchor was used.

### Warts

**F5 — `acceptance.sh` is referenced by fixtures/README.md and by
prove_fixtures.py's output, and does not exist in the repo.**

**F6 — Unknown verbs are not refused.** `telltape bogusverb` falls
through to watch-with-default-config and reports a missing config
file. (Bare `telltape` similarly shows no usage, though `--help`
exists and is good.)

**F7 — Query's clock depends on an unmentioned TZ.** With TZ unset,
tells render in UTC and can show a different calendar date than the
user's local day; the docs' examples silently assume a set TZ.

**F9 — The README's index recipe defaults to the test double with
no saturation warning at the point of use.** The BYO doc is honest
("its distances saturate"); the recipe a stranger actually follows
never says that varied real footage through the double yields
maximal-change verdicts for any visible difference (my step-3 run:
11 full-frame events). One sentence in the recipe would set the
expectation.

---

## Would I adopt it?

Yes — for the pipeline and the ledger, with a real embedder behind
the seam, and my step-4 run is why: a static scene and one object
produced exactly one tell, at the right frame, on the right tiles,
for 5.6% of the naive embedding budget, in a text file I can grep,
diff, and keep forever; and `query` turns that file back into an
answer in 20 milliseconds. The seek-index idea is real and it
works. But I would not yet trust it *unattended*, because of the
first thing I'd change: **the embedder seam needs a degeneracy
guard** — the startup probe should verify the probe embedding is
non-zero and finite (and periodically re-verify), zero-norm or
constant embeddings should stop the run or be receipted as a loud
service event, and a maximal distance should never be the silent
answer to a broken vector. Until that exists, the tool's most
confident output is also its least checked — and a change-witness
is only worth keeping forever if it can't lie to you politely.

---

## Appendix — verbatim outputs

**A. Identity refusal (step 5):**
```
telltape: embedder identity mismatch: this ledger was written by embedder 'unknown' but the configured embedder is 'double@1'. A swap is a lens change — the old baselines and gate calibration do not transfer. Refusing to continue; to accept the swap and recalibrate, set recalibrate = true in the config (or pass --recalibrate)
```

**B. Zero-vector embedder run summary (step 7)** — indistinguishable
from a healthy acceptance:
```json
{"frames":18,"events":2,"embeds":34,"embeds_spent_s":0.083,"embed_everything_estimate_s":0.703,"verdict_latency_p50_ms":25.423,"verdict_latency_max_ms":256.359,"embedder_started_by_me":false,"embedder_stopped_by_me":false}
```
with verdict rows carrying `"raw":1.0,"smoothed":1.0` on nominated
tiles.

**C. Frozen-source stderr during the yard index (step 4):**
```
[telltape] source frozen: repeated frames, silence no longer meaningful
[telltape] source live again: novel frames arriving
[telltape] source frozen: repeated frames, silence no longer meaningful
[telltape] source live again: novel frames arriving
[telltape] source frozen: repeated frames, silence no longer meaningful
```
and the finished ledger's health: `freshness = frozen`,
`frames_repeated = 13`, `silence_meaningful = false`.

**D. Query --summary frozen stretches on the same ledger:**
```
frozen stretches (source_frozen -> source_recovered)
  2026-11-03 01:16:18 UTC -> 2026-11-03 01:16:18 UTC  (0s)
  2026-11-03 01:16:18 UTC -> 2026-11-03 01:16:18 UTC  (0s)
```

**E. Index summary, attempt 1 (step 3):**
```json
{"frames":24,"events":11,"embeds":192,"embeds_spent_s":1.322,"embed_everything_estimate_s":2.644,"verdict_latency_p50_ms":16649.953,"verdict_latency_max_ms":20727.987,…}
```

**F. Bare / unknown verb (step 9):**
```
$ telltape bogusverb
config: cannot read config telltape.conf: No such file or directory (os error 2)
```

**Artefacts kept alongside this report** (under
`~/workspace/cold-playtest/`): the clone (`telltape/`, including
`ledger-acceptance/`, `ledger-front-door/`, `ledger-yard/`,
`ledger-http/` and the conf files used), `footage/front-door.mp4`,
`footage2/yard.mp4` + its frames, and `byo/embed_server_verbatim.py`
— the doc's sketch exactly as printed, which produced Appendix B.
