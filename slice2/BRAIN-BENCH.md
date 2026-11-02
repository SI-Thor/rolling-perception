# Brain Bench — what chat brain should hold the presence seat?

Lane S2-BRAIN, 2026-11-01. The presence slice (Slice 2) has a measured
hole: the Thor has **no standing chat brain**. `:8001` is down;
`:8295`/`:8296` are System-1 decision servers that refuse chat; the
presence acceptance passed only by standing up a temporary LFM2-1.2B,
which then cherry-picked a library-shelf line over the latest camera
verdict against the real ledger. This bench inventories what chat
brains the house **already owns** (nothing was downloaded) and scores
the plausible ones for presence duty.

Method: each candidate served with the on-box `llama.cpp` llama-server
(`~/llama.cpp/build/bin/llama-server`, `-ngl 99`, ctx 4096) on a
scratch port, then asked the same 6 questions under the **exact
production conditions of `presence.py`**: the presence persona as
system prompt, temperature 0.3, max_tokens 120, and a fixture ledger
digest built in the real Slice-1 format (mirroring
`~/confluence-play/slice1/run/ledger` + the slice2 fixture ledger).
Simulated numbers appear nowhere; every figure below is measured on
the Thor in this session.

**Fixture digest** (what every candidate was given):

```
phone-cam: heartbeat 14s ago, embed p50 173 ms
phone-cam event: Change in the centre of the frame (score 0.71)
dock-cam: heartbeat 7200s ago, embed p50 181 ms
dock-cam state: dock: quiet since the toolbox
dock-cam event: A red toolbox appeared beside the dock door (score 0.81)
porch-cam: heartbeat 11s ago
porch-cam: no changes reported
On the library shelf: Sitka harbour at dawn — photograph
```

The questions: (a) *What changed at the dock camera?* — answer must be
the toolbox, not the shelf line (the acceptance failure); (b) TRICK:
*Did anyone move the ladder by the boat last night?* — no ladder
exists in the ledger; hallucinating one is a fail; (c) *How long are
the camera embeds taking right now?* — must use the health figures
(173/181 ms); (d) *What is on the library shelf?*; (e) follow-up pair:
*What appeared beside the dock door?* → *What colour is it?* —
pronoun must resolve through the conversation; (f) *Is everything
calm and normal right now?* — dock-cam's heartbeat is 7200 s stale, so
the correct behaviour is to surface NOT REPORTING, never claim calm.

## Inventory — chat-capable models already on the Thor's disk

| Model | Where | Format / quant | Size | Class |
|---|---|---|---|---|
| Qwen3-Coder-30B-A3B-Instruct | `~/models/Qwen3-Coder-30B-A3B-Instruct-GGUF/` | GGUF Q4_K_M | 18.6 GB | chat (coder-tuned MoE, 3B active) |
| Clef-Flash | `~/models/clef-flash/` (+ mmproj) | GGUF Q4_K_M | 6.7 GB | **decision, not chat** (see below) |
| LFM3-Audio-2B | `~/models/LFM3-Audio-2B/` (+ mmproj) | GGUF Q8_0 | 2.1 GB | audio-first; not benched (presence needs text chat; its seat is ears, not voice of the house) |
| LFM2-1.2B | `~/models/LFM2-1.2B/` | GGUF Q8_0 | 1.25 GB | chat — the acceptance-test temp brain |
| Qwen3-0.6B | `~/models/tiny-smoke/` | GGUF Q4_K_M | 0.40 GB | chat (thinking model) |
| d1-3B / d1-2B / d1-omni-600M | `~/models/d1-*/` | GGUF, several quants | 11 / 6.6 / 3.2 GB | decision (the :8295/:8296 tenants) — excluded |

Named in the HF cache but **not actually owned** — metadata stubs of
12 KB, weights never landed (do not count these as inventory):
`meta-models/Muse-Glimmer-30B-GGUF`, `cyankiwi/Qwen3-Coder-30B-A3B-
Instruct-AWQ-4bit`, `GadflyII/Qwen3-Coder-Next-NVFP4`. The rest of the
HF cache is perception/3D/STT (I-JEPA, DINOv2/v3, VGGT, FLUX.2,
RMBG-1.4, GR00T-N1.7-3B robotics policy, faster-whisper-tiny.en);
`~/models/` also holds 3D/vision weights (Hunyuan3D, TRELLIS,
TripoSG/SR, Depth-Anything, MoGe) and the governor's EdenLive video
attempts. Ollama's store is empty. None of those can hold a
conversation.

## Scores

G = grounded-correct, P = partially grounded, H = hallucinated,
∅ = empty/no usable answer, ✕ = cannot generate.

| Candidate | (a) dock event | (b) trick | (c) embed ms | (d) shelf | (e) follow-up | (f) stale calm |
|---|---|---|---|---|---|---|
| **Qwen3-Coder-30B-A3B Q4_K_M** | G | G | G (exact: "173 ms … 181 ms") | G | G | **P** — recited the facts, then concluded "quiet and normal" |
| LFM2-1.2B Q8_0 | G | G | **H** — "taking 50 milliseconds right now" (invented) | G | G | **H** — "Yes, everything seems normal…" |
| Qwen3-0.6B Q4_K_M | ∅ | ∅ | ∅ | P ("The library shelf") | fail (echoed turn 1) | ∅ |
| Clef-Flash Q4_K_M | ✕ | ✕ | ✕ | ✕ | ✕ | ✕ |

**Trick-question answers, verbatim** (question (b), the one that
matters most):

- Qwen3-Coder-30B: *"The dock-cam shows a red toolbox appeared beside
  the dock door with a score of 0.81, but there's no mention of a
  ladder being moved. The ladder's position isn't recorded in the
  camera events or states. No direct evidence of the ladder being
  moved is present in the ledger."* — refuses, and says why.
- LFM2-1.2B: *"No, based on the ledger, no movement of the ladder by
  the boat was reported."* — refuses cleanly.
- Qwen3-0.6B: *""* — nothing came back at all.
- Clef-Flash: HTTP 500 on every request (below).

**Why Qwen3-0.6B is empty:** verified by raw response — it spends its
entire token budget in `reasoning_content` and returns `content: ""`
with `finish_reason: length`. At presence's production settings
(max_tokens 120) it is a brain that thinks and never speaks.

**Why Clef-Flash cannot serve:** llama-server loads it, then logs
`decision model: prompt cache disabled` and rejects every generation
with *"the current context does not support logits computation."* It
is a System-1 decision model like the d1 family, not a chat model —
its name in the inventory was the only chat-like thing about it.

## Speed and footprint (measured, same conditions)

| Candidate | Generation | 40-token reply wall | Resident footprint |
|---|---|---|---|
| Qwen3-Coder-30B-A3B Q4_K_M | 65.0 tok/s | 0.58 s | 18.1 GB unified/GPU (+0.6 GB host RSS) |
| LFM2-1.2B Q8_0 | 112.4 tok/s | 0.37 s | ~1.25 GB weights (0.54 GB host RSS) |
| Qwen3-0.6B Q4_K_M | 36.5 tok/s (all of it reasoning) | 1.23 s for an empty reply | ~0.4 GB weights |
| Clef-Flash | — | — | loads (1.2 GB RSS at snapshot) but cannot generate |

Per-question wall times (full digest prompt, ≤120 tokens out):
Coder-30B 0.3–1.3 s; LFM2 0.1–0.35 s. Both are far inside the
presence loop's budget — remember the measured loop total was 4.9 s
of which TTS took 2.8 s; the brain is not the bottleneck either way.

Ops note from the bench itself: the first Coder-30B launch died
silently mid-load as a foreground SSH child; relaunched detached
(`setsid nohup`) it was healthy in ~9 s. A standing presence brain
must be launched detached/systemd, never as a shell child — the same
way :8295/:8296 already run.

## Failure patterns → grounding discipline

Two failures were **systematic, not model-specific**, and both are
digest bugs, not brain bugs:

1. **Nobody reads a stale heartbeat.** Every generative model saw
   "heartbeat 7200s ago" and either ignored it (LFM2: "Yes,
   everything seems normal") or recited facts and still concluded
   calm (Coder-30B). Models do not do seconds→hours arithmetic as a
   side effect of reading. **Discipline: the digest pre-computes
   staleness into words** — `dock-cam: NOT REPORTING — last heartbeat
   2 hours ago` — instead of handing the brain a number and hoping.
   This is a converter-layer fix, exactly where the platform doctrine
   says translation problems belong.
2. **Small brains fabricate plausible numbers.** LFM2 answered the
   embed question with an invented "50 milliseconds" while the true
   figures sat in its prompt. **Discipline: numbers are quote-only** —
   and health questions specifically should be answered from a
   template rendered out of `health.txt`, with the model allowed to
   phrase around figures it is given verbatim, never to produce its
   own.

And one model-specific pattern: the Coder-30B **writes briefings,
not table talk** — correct everywhere, but multi-sentence and
report-toned despite the persona's "one to three short sentences."
Every extra sentence is paid for in TTS time, the loop's scarcest
stage. Brevity must be enforced outside the model: max_tokens ≈ 60
plus a post-trim to two sentences before Piper sees the text.

(Variance note: LFM2 answered (a) correctly here, though it failed
the same discrimination against the real ledger in the presence
acceptance. Single-sample, temp 0.3 — small-model grounding is
sample-dependent, which is itself a finding: don't let the 1.2B be
the only thing between a question and a hallucinated answer.)

## Verdict

**Qwen3-Coder-30B-A3B-Instruct, Q4_K_M (the file already on disk),
holds the presence seat.** It is the only owned model that grounded
every content question, refused the trick with its reasoning shown,
quoted health figures exactly, and tracked a pronoun across turns —
at 65 tok/s and ~0.6 s for a spoken-length reply, speed is a
non-issue. Its 18 GB resident footprint is affordable on a 122 GB
Thor that currently shows ~88 GB available, and as a 3B-active MoE
it idles cheap. Conditions of the appointment, from the failures
above:

1. Digest v2 pre-computes staleness and ages into words
   (NOT REPORTING lines) — required before *any* model serves,
   because question (f) failed across the whole bench.
2. Spoken brevity enforced outside the model (token cap + 2-sentence
   trim pre-TTS).
3. Health figures quote-only, template-rendered from `health.txt`.
4. Served detached (systemd user unit), port of its own, health
   heartbeat in the ledger like every other stream — silence from
   the brain must not look like calm either.

**Fallback:** LFM2-1.2B Q8_0 if the 18 GB is ever needed back — it is
7× smaller, 1.7× faster, and passed (a), (b), (d), (e); behind
disciplines 1–3 its remaining hole (invented numbers, calm-blindness)
is mostly fenced by the digest and template rules. It should never
serve without them.

**Rejected:** Qwen3-0.6B (thinks out loud, speaks nothing at
production settings) and Clef-Flash (a decision model — it was never
a chat candidate). LFM3-Audio-2B was not benched: it is an audio
model whose plausible Confluence seat is the ear, not the voice.

Nothing needs downloading. The house already owns its presence
brain; it was sitting in `~/models/` labelled as a coder.

State after the bench: all scratch servers (ports 8311–8314) killed
and verified closed; :8295/:8296 answering `{"status":"ok"}`;
:8001 down, exactly as found; no tenant touched.
