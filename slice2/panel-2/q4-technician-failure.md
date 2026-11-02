# CONFLUENCE — FULL DESIGN SPECIFICATION (shared review context)

===== DOCUMENT 1: docs/SPEC-STREAM-PLATFORM.md =====

# SPEC — Confluence: a Thor-native platform for all your streams

*Status: design, 2026-11-01. Working title "Confluence" — Casey's to
rename. This spec is the plan; nothing here is built yet except the
substrate it stands on (waves 1–3 of this repo, measured). Numbers
quoted are measured where a source is given; everything else is
marked TO-MEASURE and is a debt the build order pays explicitly.*

## The product in one paragraph

StreamVibe (a no-license portfolio project — **inspiration and
demand evidence only; this design is clean-room**) shows a competent
Netflix-shaped app for one kind of stream. Confluence is the general
form, designed for a Jetson AGX Thor from the ground up: **one box
under your roof ingests every stream you have — your library, live
sources, cameras, radio, audio, feeds — perceives all of them
rolling, keeps every stream's state as structured text, and serves
it all back as one living thing: one shelf, one player, and one
change feed that says what changed, across everything, and is
otherwise silent.** Watch this for me, tell me what changed — and
play it back to me — are two faces of one substrate.

## Principles (binding on the build)

1. **Inventory before building.** The fleet's existing services are
   called, not rebuilt (§A1). The substrate is this repo.
2. **The world is text.** All platform state is structured text in
   per-stream ledgers; every UI is a replaceable projection.
3. **Perception is budgeted.** Expensive models run only where a
   cheap reflex nominated change, in rank order, against a visible
   budget the user sets in plain language.
4. **The Thor is Casey's bench first.** The platform is a tenant:
   it yields in labelled steps and never makes his box feel taken.
5. **Silence by default.** The attention plane speaks only on
   published verdicts, and any source whose measured precision
   decays is demoted automatically.
6. **No cloud, no account, no DRM.** Commercial services are
   findable (metadata + deep links), never perceivable.

The three parts below were drafted as separate lanes and are
assembled with their section marks (§A/§B/§C) intact:
**A** architecture + ingest, **B** the perception plane,
**C** serve + attention planes and the build order.

---

## §A — Architecture and ingest

Working title: **Confluence**. The application layer on top of
SI-Thor/rolling-perception: every stream in the house, ingested by one
Thor-native platform, perceived rolling, served back as one living
thing. Reference point: StreamVibe (github.com/amirrezaRst/StreamVibe),
a no-license Netflix-style MERN platform — **inspiration only,
clean-room**. Nothing of its code, structure, or text is used. Its
feature categories are cited below solely as prior-art evidence that
demand for a catalogue, a player, subscriptions/entitlements, and an
admin surface exists.

House rule for this document, inherited from the substrate repo: no
claim without a number. Anything not yet measured is marked
**TO-MEASURE** and is a bench task, not an assumption.

---

## 1. Inventory before building

Casey's standing doctrine: never greenfield a layer that already has
prior art. Confluence is an application layer; almost everything under
it already exists on the fleet and is *called*, not rebuilt.

### 1.1 Already on the Thor (build on these)

| Asset | Where | What Confluence takes from it |
|---|---|---|
| rolling-perception substrate | SI-Thor/rolling-perception, 6 crates, 52/52 tests native on the Thor (2026-11-01) | The engine: lock-free rings, rolling cascade (perceive→decide→direct→refine→publish), LensFile adaptive stagger, cuda-thor GPU executor (NVRTC-from-Rust, launch-boundary swap), harbor-watch as the reference workload. Confluence adds no second scheduler. |
| JEV rack | Thor :8077, FastAPI, systemd (`jev-rack`), lazy model load; state as of 2026-11-01: service **inactive** at wave-3 start, started for the run, stopped after, verified inactive | The perception model shelf: I-JEPA (1280-dim image embeds, **p50 173 ms per tile crop** measured in wave 3), V-JEPA 2 (1024-dim video embeds), jev-semantic judge (measured 137–223 ms per call, 2026-10-23). The rack's own pattern — lazy load, a `/cards` registry with measured cost per tool — is the pattern every Confluence perception stage follows. Rack start/stop is an operator action until the platform owns it; Confluence must health-check and report, never assume. |
| llama-server | Thor :8001 (live 2026-11-01) | The language brain: summarisation, the reflective tier's local option, natural-language queries over the ledger ("what changed while I was out" is a ledger query with an LLM face). Local models are *gauges consulted when useful*, per fleet doctrine — decision dice are local and recorded; big minds author, they don't sit in the hot loop. |
| Image studio | ComfyUI :8188 + portal :8190 (FastAPI, single page, sqlite gallery, queue view; phone-verified 2026-10-23) | Proof that a Thor service with a one-page face is the right product shape for this house; also a generation lane — produced media enters Confluence as library items through the same ingest as any file (see §3.1), not through a special door. |
| Foundry portal | Thor :8200 (FastAPI, builder chat + workbench + registry board) | The console precedent: conversation on the left, the machine's work visible in a glass box, a registry/lifecycle board. Confluence's console (§2.6) is a projection in this style, not a new UI paradigm. Foundry's brain chain (Worker → Thor :8001 → fallback parser) is also the degradation precedent: every smart feature names its dumber fallback. |
| Radio Room | ProArt front-end + Thor brain service :8079 (TTS), faster-whisper STT on the ProArt (0.13 s warm for 5 s speech), per-stage receipts in JSONL | The audio lane's proven shape: capture where the human is, perceive where the GPU is, receipts per stage. Confluence audio ingest (§3.5) reuses the pipeline pattern and the receipt discipline; the VHF dressing itself is Radio Room's, not Confluence's. |
| LAN mesh + gpu-queue | Thor = hub, <thor-lan-ip> (DHCP; `thor.local` is the durable name); gpu-queue service owns Thor GPU dispatch with the successor rule | Placement facts and the GPU contention rule: Confluence perception jobs enter the same queue discipline as everything else on the box. No Confluence lane runs a private downloader or a private GPU free-for-all. |

Hardware facts the design leans on (measured, docs/FEASIBILITY.md in
the substrate repo): AGX Thor, sm_110, 20 SMs, 122 GiB unified
LPDDR5X, driver 595.78, CUDA 13.2. Control/flag slots belong in
host-pinned mapped memory; bulk tensors in managed memory
(`directManagedMemAccessFromHost=0` on this part). These constrain
§2.5; they are not re-derived here.

### 1.2 External incumbents (what each proves, what each teaches)

- **Jellyfin** — proves a self-hosted media server with library,
  transcode, and multi-client playback is a solved *serving* problem,
  and that a large public wants to own it. Teaches: don't rebuild the
  serving plane as a science project; Confluence's serve plane (§2.4)
  is deliberately boring. Also teaches the gap: Jellyfin perceives
  nothing. Its library is filenames and scraped metadata.
- **Plex** — proves the commercial version: polish, remote access,
  and account-mediated convenience sell. Teaches the anti-pattern for
  this house: the account *is* the product's centre of gravity, and
  the user's library phones home. Confluence's posture (§2.7) is the
  negation: no account, no phone-home, the box works with the WAN
  cable pulled.
- **Frigate** — proves local-first camera perception on edge hardware
  is a real, wanted category, and that event-not-stream is the right
  unit for cameras. Teaches: its perception is detector-shaped
  (objects in frames, batched per frame). Confluence's difference is
  the substrate: change-first gating and rolling verdicts (harbor-
  watch measured the saving: 312 embeds vs 576 for the same scenes,
  −54% rack time), and cameras are one ingest class among many, not
  the platform's centre.
- **StreamVibe** (inspiration only) — proves the *demand shape* of the
  consumer surface: people expect a catalogue with rails and search, a
  player that resumes where they left off, plan/entitlement concepts,
  and an admin console behind it. Confluence takes the demand as
  evidence and designs its own surface from the ledger (§2.4); the
  subscription concept maps to *local household profiles and
  entitlements on the box*, never to a billing relationship with us.

### 1.3 What is deliberately NOT built

- No new scheduler, ring, or GPU executor (substrate exists).
- No new model serving stack (JEV rack + llama-server exist).
- No new portal framework (two FastAPI single-page portals exist and
  are the house style).
- No media *player* engineering beyond what serving requires until a
  client gap is measured (TO-MEASURE: client matrix, §2.4).

---

## 2. Architecture

### 2.0 The one-paragraph shape

A stream is anything that arrives over time. Confluence gives every
stream a **lane family** in the rolling pipeline, a **LensFile** that
learns its rhythm, and a **ledger record** that is its complete,
current, structured-text state. Perception runs rolling — each item
perceived as it lands, verdicts emitted per stage completion, never
per clock tick. Everything a human sees is a projection of the
ledger. Nothing else is state.

### 2.1 The five planes

| Plane | Job | Lives where |
|---|---|---|
| **Ingest** | Accept every stream class in §3, normalise to items, stamp arrival, enforce backpressure per class. Owns no opinions about content. | Thor (capture adapters for ProArt/Orin sources run at the edge, ship items over the LAN) |
| **Perception** | The rolling cascade per lane family: perceive → decide → direct → refine → publish. Spends model calls only where change or novelty justifies them (the gate decides what is *launched* — wave-2/3 finding, not a slogan). | Thor GPU, via gpu-queue discipline; JEV rack + llama-server as the model shelf |
| **Ledger** | The single source of truth: per-stream structured-text state, event log, lineage. Every other plane reads/writes here; nothing keeps private state that matters. | Thor disk, plain files under version control discipline (§2.3) |
| **Serve** | Projections out: catalogue, player streams, search, household profiles/entitlements, admin. Boring on purpose (§1.2, Jellyfin). | Thor serves; clients are browsers and light apps |
| **Attention** | The change feed across *all* streams: what departed from normal, ranked, with receipts. Also the actuation edge for cross-stream rules (§2.6). | A projection of the ledger, plus a rules runner on the Thor |

Planes communicate through the ledger and the rings, never through
ad-hoc side channels. If a fact isn't in the ledger, it didn't
happen; if a job isn't in the queue, it isn't running.

### 2.2 The substrate mapping

- **One stream = one lane family.** Each family is the proven
  five-stage cascade (perceive, decision, attention-director,
  refine/step, publish — the harbor-watch shape) instantiated with
  that stream class's item type and models. Families are independent:
  separate rings, separate LensFiles, separate failure domains (§2.8).
- **Per-stream LensFile.** The adaptive-stagger self-model (period
  EMA, jitter EMA-variance, signed phase error) already exists as
  text (`key = value`, roundtrip-tested). In Confluence it also
  carries the stream's *normal*: expected rate, expected drift band,
  quiet hours. This is what "learned normal" means concretely — a
  file a human can read, diff, and correct. Measured basis: under
  jitter+drift, adaptive prediction p95 was 1,669 µs vs fixed
  stagger's 854,285 µs; at zero jitter the two tie exactly, so the
  lens costs nothing when there's nothing to learn.
- **Stagger is the scheduling doctrine.** Stages and streams are
  offset by their measured periods, not aligned to a global frame
  clock. Basis: on identical work, rolling TTFO beat batched 10.4×
  (CPU, 400 µs stagger) and first GPU output came 3.7× earlier
  (21.41 ms batched vs 5.74 ms rolling), with total completion
  unchanged — continuity, honestly, not throughput.
- **The gate decides what is launched.** Expensive perception
  (embeds at ~173 ms, judge calls at 137–223 ms, LLM calls slower)
  is launched only for items the cheap stages nominate. Wave 3's
  counted figure: gating removed 54% of embeds on real scenes and
  88% on a gradual scene, with frame verdicts agreeing 1.0000 with
  the ungated run on the cuts sequence. The gate is a *ranker with a
  budget knob*, not a separator — the wave-3 audit (skipped tiles'
  drift 0.20 vs embedded band's 0.48) is quoted wherever this is
  claimed, and per-stream budgets live in the LensFile.

### 2.3 The ledger (the world is text)

All canonical state is structured text on the Thor:

```
ledger/
  streams/<stream-id>/lens.txt        # the LensFile: rhythm + normal
  streams/<stream-id>/state.txt       # current state, key = value
  streams/<stream-id>/events.jsonl    # append-only event log, per stage receipts
  items/<item-id>.txt                 # one item's record: provenance, embeddings ref, verdicts
  household/profiles.txt              # who exists, what each profile may see/do
  attention/feed.jsonl                # the cross-stream change feed (a projection, rebuildable)
```

Rules:
- **Text is canonical; every render is a replaceable projection.**
  The catalogue page, the change feed, the console — all are
  regenerated from the ledger and can be thrown away and rebuilt.
  Binary payloads (media, embeddings) live outside the text files,
  referenced by id + hash; the text says what they *mean*.
- **Lineage is recorded, not reconstructed.** Every event carries
  the substrate's lineage (visited-bitmask + saturating counts —
  the fix that replaced the seed's lossy prime-product scheme):
  which stages touched this item, how many times, in what order.
  Verdicts without lineage are not published.
- **Receipts per stage**, the Radio Room discipline: each stage
  appends what it did, what it cost (ms), and what it decided.
  The attention plane ranks from receipts, not from vibes.
- Embedding vectors are stored as data (1280-dim I-JEPA, 1024-dim
  V-JEPA 2), referenced from item records; similarity search over
  them is a serve-plane projection. Index technology: TO-MEASURE
  (household scale may make brute force honest; decide by count,
  not by fashion).

### 2.4 Serve plane (deliberately boring)

- Catalogue, search, and playback of owned media over the LAN,
  HTTP(S) with range requests; transcode via the Thor's hardware
  encoders. Codec/ABR matrix: TO-MEASURE against the actual client
  set in the house (browsers first; native TV/phone apps only if a
  measured gap appears — §1.3).
- Resume points, watch state, and per-profile entitlements are
  ledger records, so "continue watching" is a projection, not a
  database product.
- Commercial services appear **only** as catalogue entries with
  metadata and deep links (§3.8). The serve plane never proxies,
  re-streams, or caches their content.
- Household profiles and entitlements are local configuration
  (who may watch what, whose change feed includes which streams) —
  the honest local form of the subscription concept StreamVibe
  demonstrates demand for. There is no billing. There is no account
  to create.

### 2.5 GPU and memory placement (wave-2 findings, applied)

- **Two-stream shadow is the default executor arrangement** for
  perception work: identical launch pickup to per-slice launches,
  better wall time (big slices 3.6→3.0 ms, small 4.2→2.7 ms,
  measured). The persistent-kernel arrangement is reserved for its
  proven niche — the tiny-buffer ack path (request→ack mean 4.8 µs,
  p95 5.5 µs in the tight loop) — and is *not* used for slice work,
  where it measured 9–27× slower (resident-grid starvation).
- **Stream priorities are not a mechanism.** Measured: no effect on
  this part (per-lane medians identical to 0.01 ms). Fairness
  between lane families is achieved by stagger + budgets (§2.2),
  never by priority flags.
- **Unified memory discipline:** control/flag slots in host-pinned
  mapped memory; bulk tensors in managed memory; kernel variants
  swapped at launch boundaries only, with epoch retirement
  (1,000/1,000 swaps verified in wave 2). No design element anywhere
  in Confluence depends on mid-kernel splicing — it does not exist.
- **Contention is a governed resource.** All perception jobs enter
  through the gpu-queue successor discipline (§1.1). A finite job
  names its successor or the standing feeder; idle-GPU intervals
  are logged and are a reportable deficit. When Casey is working
  the Thor directly, Confluence yields — his bench outranks the
  platform (2026-10-28 placement ruling).
- Host CPU cost of spin-sync executors measured ≈100% of wall in
  wave 2's arrangements; a blocking-sync variant is an open
  substrate follow-up. Confluence budgets CPU accordingly:
  TO-MEASURE per lane family at platform scale.

### 2.6 Attention plane and cross-stream rules

- The **change feed** is the primary human surface: one ranked
  stream of departures-from-normal across every ingested stream,
  each entry carrying its receipts and a link to the item/projection
  that shows it. Ranking inputs: embedding drift vs the stream's
  LensFile normal, sheaf-refined coherence (the wave-3 ablation:
  one Laplacian step over the tile grid took fixture precision
  0.60 → 1.00 at recall 1.00 — local agreement is a stronger signal
  than any single judge), profile interests, and recency. The
  reflective judge (TypeSafe Jev, or local equivalents) sits in
  this plane as a **recorded advisor**: its probability rides in
  the verdict, surfaced, not thresholded — the seat it earned in
  wave 3 (as tie-breaker it *lowered* a perfect score; as gate it
  changed nothing; it never doubted a true change, p 0.88–0.92).
- **Cross-stream rules** are small, ledger-stored, human-readable
  statements evaluated by the attention plane ("door camera flags a
  person after dark → pause the cinema room's playback and put the
  camera's current frame on the console"). Rules are data, not
  code paths; every firing is an event with lineage. Rule language
  expressiveness: TO-MEASURE against the first ten rules Casey
  actually writes; start with trigger→action pairs, grow only on
  evidence.
- **The console** (ProArt, the chair) is one master projection:
  every stream's current state, the change feed, and the rules —
  the bridge-console pattern from the rooms doctrine. Residents
  (agents, the platform itself) get full-density text; the human
  gets the chart-like face.

### 2.7 Security and ownership posture

- **Local-first, account-free.** No cloud account, no sign-in, no
  telemetry, no phone-home. The platform runs whole with the WAN
  disconnected; anything that breaks when the cable is pulled is a
  defect, reported as one.
- **The house's data stays in the house.** Media, embeddings,
  ledger, and verdicts live on the Thor. Embeddings and text
  verdicts are the *only* things that ever need to move between
  boxes; raw camera frames and audio do not leave the LAN unless a
  rule Casey wrote says so.
- **Access is the LAN + household profiles.** Per-profile
  entitlements (§2.4) gate streams and items (a guest profile need
  not see the camera change feed). Anything beyond the LAN —
  remote viewing — is out of scope until Casey asks; if it ever
  lands, it rides the fleet's existing tunnel discipline, not a
  new cloud relay.
- **Outbound calls are named and few.** Metadata lookups (§3.8)
  and the optional hosted judge are the only egress, each logged
  in the ledger as an event with the payload class recorded.
  Secrets (any service keys) live in the fleet's credential
  store, never in the ledger, never in this repo.
- **Clean-room discipline.** Confluence is designed from this
  document and the substrate repo. StreamVibe and the incumbents
  are demand evidence and cautionary tales, never sources.

### 2.8 Failure modes (the stagger doctrine, applied to death)

The rolling architecture's core failure property: **lanes are
independent, so death is local.**

| Failure | Behaviour | Basis |
|---|---|---|
| A stream source dies (camera unplugged, feed 404s, tuner loses lock) | Its lane family marks the stream *stale* in the ledger (last-seen + LensFile expectation breached), the attention plane posts one "stream down" entry, all other families continue untouched. Restart resumes from the ledger state; missed interval is recorded as a gap, never backfilled with invention. | Per-family rings and LensFiles are separate by construction (§2.2); harbor-watch's publish rule — a verdict is a claim about *this* frame — generalises: stale items publish as stale, labelled. |
| A perception model is down (JEV rack inactive — the actual state at wave-3 start) | Health check fails loudly in the console; affected stages degrade to their named fallback (cheap-diff verdicts continue; embedding verdicts pause and the gap is receipts-logged). The platform never silently reports embedding-grade confidence from diff-grade evidence. | Foundry brain-chain precedent (smart → dumber fallback, labelled); wave-3 rack lifecycle (started for the run, stopped after, verified). |
| GPU saturation / foreign tenant load | gpu-queue discipline sheds by budget: attention-nominated items first, background indexing last; shed items are logged, not dropped silently. | Wave-2 soak was *disturbed by* a foreign all-core burn and said so in its record; the platform attributes contention the same way. |
| Ledger write failure / disk pressure | Ingest backpressures (§3) rather than losing events; media storage and ledger storage are separate volumes of concern — a full media disk must not eat the text record. Retention policy: TO-MEASURE (household media growth rate unknown). | — |
| One lane family wedges (bad kernel variant, pathological input) | Launch-boundary swap + epoch retirement rolls the family back to its last verified variant; other families unaffected. A family that fails twice halts and reports, per gpu-queue's two-failure rule. | Wave-2 swap machinery (1,000/1,000, unload only after event sync). |
| Clock/arrival pathology (bursts, duplicates, out-of-order items) | Arrival stamps are ingest's, not the source's; duplicates detected by content hash at the item record; out-of-order items enter with their true arrival order and the ledger says so. | Substrate sequence protocol (monotonic publication check — the v0.1 bug fix) is the model. |

What is *not* claimed: no high-availability story (one Thor is one
Thor), no multi-house sync, no guarantee language anywhere. The
platform's promise is narrower and kept: **one box, honestly
reporting what it perceived, degrading in labelled steps.**

### 2.9 Placement summary

- **Thor thinks and perceives**: ingest, perception, ledger, serve,
  attention all live here. It is the back-room engine and Casey's
  own bench — Confluence is a tenant with budgets, not the owner.
- **Orin-class boxes are light clients**: the front room — display,
  console projection, capture edge (a camera or mic attached there
  ships items to the Thor). The full platform never needs to fit in
  an Orin's RAM; a client needs a browser and the ledger's text.
- **ProArt is the chair**: the master console (§2.6), the place
  rules are written and the feed is read. Its GPU seats (Radio
  Room STT today) are edge perception, shipping items like any
  other source.

---

## 3. Ingest taxonomy

Every class below names: protocol reality, arrival pattern, what
"an item" is (the unit that enters a ring and gets a ledger record),
and backpressure behaviour. The shared contract first.

**Shared ingest contract.** An adapter per class produces items:
`{stream_id, arrival_stamp, content_ref (hash-addressed), class
payload}`. Ingest stamps arrival itself (source clocks are
advisory). Adapters are dumb: decode and hand over; all judgement
is downstream. If perception falls behind, ingest sheds by class
policy below — and every shed is an events.jsonl entry. Silence
about loss is the one unforgivable behaviour in this plane.

### 3.1 Local files — the library

- **Reality:** files on Thor storage (owned rips/downloads,
  fleet-generated media from the image studio and Foundry, recorded
  items from other classes). Filesystem watch + explicit rescan;
  hash-gated on entry (the fleet's download doctrine: a file whose
  hash doesn't verify doesn't enter the tree — quarantine, report).
- **Arrival:** bulk and bursty — a rescan can present thousands of
  items at once; thereafter near-zero. Effectively infinite rate
  at scan time, which is precisely why it is throttled hardest.
- **Item:** one media file (film, episode, song, image), with
  sidecar text (existing metadata files) absorbed into its record.
- **Backpressure:** the scan is a background job under gpu-queue
  discipline with the lowest budget; indexing a new library must
  never delay a live stream's perception. Partial progress is the
  normal state and is shown as such.

### 3.2 RTSP / IP cameras

- **Reality:** RTSP (usually H.264/H.265 over TCP or UDP), ONVIF
  for discovery/PTZ where the camera offers it; vendor quirks are
  per-camera facts recorded in that stream's LensFile notes, not
  platform folklore. Reconnect with backoff is the adapter's job;
  RTSP sources drop, that is their nature.
- **Arrival:** continuous video, 5–30 fps nominal — but the
  *perception* item rate is set by the gate, not the frame rate.
  Measured shape (wave 3): cheap per-tile diff at frame rate
  (µs-class, numpy), embeds only for nominated tiles at ~173 ms
  each. Sustained item rate per camera is a LensFile budget
  (TO-MEASURE per camera position: a dock at night and a doorway
  at school-run time are different streams that happen to share a
  protocol).
- **Item:** a *tile-verdict unit* — one frame's nominated tiles
  with their diffs and (when launched) embeddings; plus periodic
  full-frame reference items so "normal" itself is refreshed, at
  a LensFile interval.
- **Backpressure:** frames are worthless old. When behind, drop
  frames, never queue them — the adapter always works on the
  newest frame and the drop count is receipted. This is the class
  where "a verdict is a claim about *this* frame" bites hardest.

### 3.3 HLS / live streams

- **Reality:** HLS (segmented .m3u8, typically 2–10 s segments) or
  direct live URLs the household is entitled to watch (public
  streams, harbour/weather cams, event streams). Latency is
  inherent (segments), so this class is *near*-live by design and
  the ledger says so per stream.
- **Arrival:** segment-paced — one segment every few seconds,
  steady, with playlist stalls as the failure signature.
- **Item:** one segment (audio+video), from which the perception
  lane samples frames/audio at its budget; the serve plane passes
  the stream through to players with the ledger state riding
  alongside (what's happening in it, per perception).
- **Backpressure:** segments age out like camera frames — keep
  the live edge, drop the stale middle, receipt the drop. A
  *watched* live stream (someone is playing it) outranks an
  unwatched one for perception budget; viewing state is a ledger
  fact the director can read.

### 3.4 OTA tuners

- **Reality:** ATSC via USB/network tuner (HDHomeRun-class) where
  reception exists; output is MPEG-TS, guide data from the
  broadcaster's PSIP and/or a schedules source. In Sitka,
  reception itself is a per-channel empirical fact: TO-MEASURE
  (which channels lock, at what margin) before any design weight
  rests on this class.
- **Arrival:** broadcast-scheduled — the most predictable class
  in the taxonomy; programmes start and end on a published grid.
- **Item:** one programme (recorded or live-passed-through), or
  one guide block for the ledger's schedule projection.
- **Backpressure:** tuners are the scarce resource (N tuners,
  M simultaneous demands). Contention resolves by household
  priority in the ledger (a recording Casey scheduled beats a
  speculative one); every loss is an explicit event naming the
  winner. Never silent, never first-come-served by accident.

### 3.5 Audio — radio, podcasts, streams

- **Reality:** three sub-shapes: internet radio / live audio
  (Icecast/HLS-audio, continuous), podcasts (RSS enclosures —
  files that arrive episodically, ingested like §3.1 with feed
  metadata), and local radio via SDR where fitted (the Radio
  Room precedent makes VHF a fleet-native source; broadcast FM
  via the same SDR pattern is a TO-MEASURE adapter, not a claim).
- **Arrival:** continuous for live; episodic-bursty for podcasts
  (a feed drop is a small library scan).
- **Item:** a *window* for live (fixed-length PCM window, the
  substrate's audio lane shape — rolling-perception's cascade
  already carries an interleaved-PCM lane with real demux), an
  *episode* for podcasts. Perception per window: transcription
  (faster-whisper class; 0.13 s warm for 5 s on the ProArt's
  4050 — Thor-side figure TO-MEASURE), audio embeddings where a
  model earns its place, loudness/event marks in the ledger.
- **Backpressure:** live audio windows drop like frames (newest
  wins, drops receipted); podcast *files* never drop — they
  queue as library work at the lowest budget (§3.1).

### 3.6 Screen / game capture

- **Reality:** capture of a desktop or game feed from a fleet box
  (the Orin front room, the ProArt) via the LAN — screen content
  over the mesh (measured Thor↔Orin ~71 Mb/s Wi-Fi, two hops;
  wired figures TO-MEASURE). This is the class that makes "the
  game in the other room" a stream the house can perceive:
  spectating, coaching surfaces, and the change feed for a
  session ("your build finished rendering", "the race ended").
- **Arrival:** high-rate (30–60 fps at source) but perception
  samples it; bursty in content (menus are static, play is not)
  — the gate earns its keep here exactly as with cameras.
- **Item:** a nominated frame or frame-region, same tile-verdict
  unit as §3.2; the *served* spectate stream is a serve-plane
  passthrough, separate from perception sampling.
- **Backpressure:** perception drops frames freely (receipted);
  the passthrough, if a human is watching it, is a serve-plane
  problem with its own jitter budget — the two never share a
  queue, so perception can never stutter someone's spectating.

### 3.7 Sensor / text feeds — scores, weather, RSS, household state

- **Reality:** HTTP polling or push of small structured payloads:
  sports scores, weather observations/forecasts, RSS/Atom items,
  and the fleet's own text state (other services' published
  status, the gpu-queue's idle log, tells-class sensor neurons
  if/when they report). Cheapest class in the taxonomy by three
  orders of magnitude — and the one that makes the change feed
  feel alive between media events.
- **Arrival:** poll-paced (minutes) or event-paced (irregular,
  sometimes bursty — a feed catching up after an outage delivers
  a batch; the batch is ingested as individual items with true
  arrival stamps and source timestamps both recorded).
- **Item:** one observation / one article / one score update —
  already text or trivially text. Perception here is the direct
  stage: dedupe, diff against the stream's previous state
  (a score change *is* the change event), summarise only when a
  profile's interests nominate it.
- **Backpressure:** effectively none needed at household scale;
  poll intervals adapt per LensFile (a feed in its off-season
  polls rarely). A misbehaving feed (firehose) is capped by
  items/minute in its LensFile, excess receipted.

### 3.8 Commercial services — the boundary, stated precisely

- **What never happens:** no ingestion, proxying, re-streaming,
  caching, decrypting, or embedding-extraction of DRM'd or
  account-gated commercial content (Netflix, Disney+, Spotify
  streams, and their kin). Not "for now" — the class is defined
  by this exclusion. No adapter for a commercial service will be
  written.
- **What does happen:** catalogue-level unification. A title the
  household watches on a service may exist in the ledger as a
  *reference item*: title, poster/metadata from public metadata
  sources, the service it lives on, and a **deep link** that
  opens that service's own app/page at that title. Watch state
  for reference items is manual or profile-entered (we do not
  scrape accounts); if a household member marks it watched, the
  ledger learns the taste fact, never the stream.
- **Arrival / item / backpressure:** reference items arrive when
  a human or a metadata lookup adds them; an item is one title
  reference; there is no stream to backpressure. Metadata
  freshness is a §3.7-class poll at most.
- **Why the boundary is here and not further out:** it is the
  line between *a platform that perceives what is yours* and a
  redistribution machine. The first is the product; the second
  is a lawsuit with a UI. The demand StreamVibe demonstrates —
  one place where everything lives — is met honestly: everything
  *perceivable* is perceived; everything else is, at least,
  *findable* from the same catalogue.

### 3.9 Taxonomy summary

| Class | Item | Arrival | Shed policy when behind |
|---|---|---|---|
| Local files | one media file | bulk bursts, then ~zero | never shed; throttle the scan |
| RTSP cameras | tile-verdict unit per frame | continuous, gate-paced | drop frames, newest wins |
| HLS / live | one segment | segment-paced, steady | keep live edge, drop stale |
| OTA tuner | one programme | broadcast schedule | tuner contention by ledger priority |
| Audio live | PCM window | continuous | drop windows, newest wins |
| Podcasts | one episode | episodic bursts | never shed; lowest budget queue |
| Screen / game | tile-verdict unit | high-rate, content-bursty | drop frames (perception only) |
| Sensor / text | one observation | poll/event, small | cap by LensFile rate |
| Commercial | title reference (metadata + deep link) | human/lookup-paced | n/a — no stream exists |

---

## Open measurements this lane owes (TO-MEASURE index)

1. Client matrix for the serve plane (which real devices, which
   codecs direct-play vs transcode).
2. Per-camera sustained perception item rates by scene type.
3. Embedding index technology vs item count at household scale.
4. Thor-side whisper throughput for the audio lane.
5. OTA channel lock survey (Sitka) before the class carries weight.
6. SDR broadcast-FM adapter viability.
7. Host-CPU cost per lane family with spin-sync executors at
   platform scale (blocking-sync variant is the substrate fix).
8. Ledger/media retention growth rates.
9. Wired vs Wi-Fi LAN throughput for screen capture.
10. Rule-language expressiveness vs the first ten real rules.

*End of lane A. Lane B (perception + serve product detail) and
lane C (build order + acceptance gates) build on this document;
where they disagree with it, the disagreement is recorded in the
open, per house doctrine.*


---

## §B — The perception plane

Status: design, 2026-11-01. Application layer over
SI-Thor/rolling-perception waves 1–3. Every number below is either
measured in that repo (cited) or marked **TO-MEASURE**. Derived
arithmetic from measured unit costs is labelled *derived*.

The perception plane answers one question for every stream, all the
time: **what is this stream showing/hearing/saying right now, and did
it change?** It publishes text state to the stream's ledger entry —
never raw media. Raw media stays in the serve plane; perception
writes only embeddings, transcripts, verdicts and summaries, each
with a timestamp and a lineage mask (which stages touched it — the
substrate's bitmask+counts lineage carries over unchanged).

## 0. The three-speed stack (tiers every lane is built from)

| Tier | What runs there | Cost class | Measured anchors |
|---|---|---|---|
| **Reflex** | Frame/tile diffs, audio energy/onset, hash & metadata change, deadband checks. CPU, no model. | µs | Tile mean-abs diff in numpy: µs/tile (wave 3). Persistent-kernel ack path: 4.8 µs mean request→ack (exp3) |
| **Decision** | Embedding models: I-JEPA (1280-dim, image/tile), V-JEPA 2 (video), speech embed/STT, text embed. GPU, gated by reflex. | 10² ms class | I-JEPA tile embed **p50 173 ms, p95 200 ms** (n=887, Thor, wave 3). Cold model load 11.9 s once |
| **Reflective** | Typed judge (TypeSafe Jev) and local LLM (Thor :8001 class). Sees *text state only*, never pixels. | 0.5 s–seconds | Jev p50 **0.47 s**/call. LLM latency TO-MEASURE per model |

Rules inherited from measurement, not preference:

- **The gate decides what is launched, not what returns early**
  (exp4b: launch-shaped ROI grid = 192×, early-exit blocks = 1.3×).
  Reflex output selects decision-tier work items; it never starts
  work and aborts it.
- **The judge is an advisor, never a gate.** Measured (wave 3,
  n=15 curated-hard): Jev alone P=0.750/R=1.000; as tie-breaker it
  *lowered* a perfect pipeline to 0.750; as hard gate it changed
  nothing. Its probability is recorded in the ledger entry and
  surfaced in the UI. It can raise a flag's *display rank*; it
  cannot suppress or create a published verdict.
- **A verdict is a claim about this tick.** Stale scores never
  re-fire (the wave-3 stale-score bug, fixed by rule in
  harbor-watch's publish stage). Every ledger write carries its
  source tick; consumers ignore anything older than the tick they
  asked about.
- **Rolling, not batched.** Stages publish as they land: TTFO
  measured 10.4× earlier than batched on CPU at 400 µs stagger,
  3.7× on GPU, identical total work and identical checksums. The
  change feed is therefore a stream of small verdicts, not a
  periodic digest, unless the user asks for a digest.

## 1. Per-stream-type perception lanes

Common shape per lane: reflex runs always (it is nearly free);
decision runs only on reflex nomination, subject to budget (§2);
reflective runs on a sampled or user-pinned subset of decision
output, subject to budget. Each lane writes a fixed ledger schema.

### 1.1 Library video (files: film, TV, home video)

| Stage | Perceives | Model / tier | Cost |
|---|---|---|---|
| Reflex | Scene-cut candidates (histogram diff), black/silence spans, loudness | CPU diff | µs/frame sampled at 2 fps |
| Decision | One 1280-dim embedding per confirmed scene (representative frame); per-scene tile grid only if scene is "busy" (high intra-scene drift) | I-JEPA, decision | 173 ms/scene-frame. *Derived:* a 2 h film at ~400 scenes ≈ 70 s of embed time |
| Decision | Full transcript with word timestamps | Whisper-class STT, decision | TO-MEASURE on Thor (RTF); gates chaptering and search |
| Reflective | Chapter boundaries + titles, highlight candidates (drift peaks + transcript salience), one-paragraph synopsis per title | Local LLM over transcript + scene list | TO-MEASURE; backfill-only (§4), never on the playback path |

**Ledger entry (per title):** scene list `[{t0, t1, embedding_ref,
drift_in, drift_out}]`; transcript ref + language; entities
(people/places/objects — from transcript NER + user-confirmed tags
only; **no face recognition**, embedding clusters stay anonymous
"person-cluster-3" until the user names them); chapters
`[{t0, title, source: llm}]`; highlights `[{t0, t1, score}]`;
perception completeness % (a title mid-backfill says so).

### 1.2 Live video (HLS/IPTV/OTA/web streams)

| Stage | Perceives | Tier | Cost |
|---|---|---|---|
| Reflex | Scene cuts, freeze/black detection (stream health), loudness | CPU | µs |
| Decision | Embedding per scene while live; rolling drift vs the stream's lens (§3) | I-JEPA | 173 ms/scene, budget-gated harder than library (live is perishable — a skipped embed is gone, so live gets priority tokens, §2) |
| Decision | Live transcript (rolling window) | STT streaming | TO-MEASURE |
| Reflective | "What is this, actually" — programme identification from transcript+embeddings matched against the library index and the stream's own history | LLM/Jev over text state | sampled, ≤1/min/stream |

**Ledger entry (per stream):** now-playing semantics
`{kind: sport|news|film|talk|unknown, title_guess, confidence,
entities[], topic_line}`; scene drift series; health verdicts
(frozen/black/off-air are change-feed events); a rolling
last-15-min summary line, rewritten only when reflective runs.

### 1.3 Camera (RTSP/ONVIF/USB — the harbor-watch lane, already built)

This lane exists and is measured; the spec adopts harbor-watch
as-is.

| Stage | Perceives | Tier | Measured |
|---|---|---|---|
| Reflex | Per-tile mean-abs diff, 4×4 grid (finer grids TO-MEASURE per camera class) | CPU | µs |
| Decision | I-JEPA embed of nominated tiles only; cosine vs tile's last published embedding; one Laplacian (sheaf) step over the tile grid before publish | GPU | Diff-gating spent **312 vs 576 embeds (−54%)**; on gradual material **23/192 (−88%)** |
| Reflective | Jev probability recorded on published changes in the borderline band [0.15, 0.60] only | Jev | p50 0.47 s, advisor-only per §0 |

**Ledger entry (per camera):** per-tile last embedding ref + drift;
published change verdicts `{tick, tiles[], score, sheaf_energy,
jev_p?}`; current frame-level state line ("dock: quiet", "door:
person-scale change, NE tiles"). Wave-3 truth on this lane: cuts
flagged **16/16 tiles on the landing frame**; gradual rotation
2/192 tiles flagged; frame verdict agreement gated-vs-ungated
**1.0000** on the cuts sequence.

### 1.4 Audio (radio, podcasts, mic, music streams)

| Stage | Perceives | Tier | Cost |
|---|---|---|---|
| Reflex | Energy/onset, silence spans, speaker-change candidates (energy+ spectral flux) | CPU | µs–ms |
| Decision | Transcript (spoken content), sound-event tags on nominated spans (glass, alarm, engine, voice) | STT + audio embed, decision | TO-MEASURE on Thor |
| Reflective | Conversation/topic segmentation, "who is being talked about", summaries for spoken-word content | LLM over transcript | backfill + sampled-live |

**Ledger entry (per stream):** transcript (rolling for live,
complete for files); sound-event verdicts `{tick, kind, score}`;
for radio specifically: station semantics `{format, current
segment: music|talk|ads|news, track_guess?}` — track ID only from
transcript/metadata, TO-MEASURE accuracy, never claimed until
measured. The seed's Skald/PIR audio lineage stays dropped (PLAN
autopsy); lineage is the substrate bitmask, as everywhere.

### 1.5 Text / feed (RSS, APIs, scores, prices, folder & page watchers)

| Stage | Perceives | Tier | Cost |
|---|---|---|---|
| Reflex | Content hash / structural diff — *what fields moved* | CPU | µs |
| Decision | Semantic embedding of the changed fragment; drift vs the feed's lens (§3) — distinguishes "the number ticked" from "the story changed" | text embed, decision | ms–10s of ms, TO-MEASURE |
| Reflective | Importance call on borderline drift: is this worth the human's feed slot? Jev probability recorded; LLM writes the one-line "what changed" | Jev / LLM | 0.47 s class |

**Ledger entry (per feed):** current canonical text state (the
world-is-text rule: the feed's state IS its ledger text); change
verdicts `{tick, fragment, drift, line: "what changed in one
sentence"}`; deadband config (a stock ticking 0.1% is weather; 5%
is climate — per-feed, learned + user-overridable).

## 2. The budget system

Perception is metered in **embed-seconds** (one I-JEPA embed ≈
0.173 s; STT/LLM work converts at measured rates once TO-MEASURE
lands; until then each model class has its own sub-budget). The
budget is the product's central knob because the measured gate is
a **ranker, not a separator** (§3): there is no threshold that
cleanly splits change from noise, so the honest control is *how
much perception to buy*, spent in rank order.

### 2.1 The gate cascade (fixed order, every lane)

1. **Reflex diff** ranks candidate work items by expected drift
   (wave-3 audit: reflex rank correlates with true embedding drift
   0.484 embedded-band vs 0.202 skipped-band, ~2.4× separation).
2. **Budget check** (§2.2): the scheduler admits items in rank
   order until the stream's current window budget is spent.
3. **Decision embed** runs; the sheaf refine (spatial lanes) or
   deadband (scalar lanes) shapes the verdict.
4. **Reflective sampling**: fixed small fraction of published
   verdicts + all verdicts in the borderline band get a Jev
   probability attached, budget permitting. Never blocking publish.

Scheduling substrate: two-stream shadow arrangement is the default
executor (wave-2 Spike 2: same pickup, better wall than
single-stream; stream priorities measured *no effect* — priority
is enforced by our scheduler's admission order, not CUDA streams).

### 2.2 Budgets: per-stream, global, and plain language

- **Per-stream budget**: embed-seconds per rolling hour, plus a
  burst allowance (a scene cut may borrow against the next hour —
  real events are bursty; a flat cap would go blind exactly when
  it matters). Unspent budget does not accumulate beyond the burst
  allowance: perception is perishable.
- **Global budget**: a ceiling across all streams that maps to a
  target GPU duty cycle for perception (default 60% of one GPU —
  the Thor has one GPU and other tenants, §2.3). The scheduler is
  work-conserving below the ceiling: if the global budget is
  unspent and backfill (§4) has work, backfill eats the slack.
- **Plain-language knobs** compile to numbers, and the compiled
  numbers are shown next to the words (no hidden mappings):
  - *"spend freely"* → per-stream cap = 10× the stream's measured
    trailing baseline, burst 60 s
  - *"normal"* → cap = 2× baseline, burst 20 s
  - *"sip"* → cap = 0.25× baseline, reflex + decision on
    top-decile ranks only, burst 5 s
  - *"reflex only"* → decision budget 0; the stream still reports
    diff-level change ("something moved, NE tiles, unperceived")
  Worked example: front door = freely, nursery = sip, driveway =
  normal, garden = reflex only. Baseline = the stream's own
  trailing 7-day embed spend at "normal"; a new stream starts at a
  class default (camera 300 embed-s/h ≈ 14% duty at 173 ms —
  *derived*) until its baseline exists. TO-MEASURE: baseline
  stability across a week of real scenes.

### 2.3 Tenancy: the Thor is Casey's bench first (2026-10-28 ruling)

Two doctrines collide here and the resolution is explicit:

- *Fleet doctrine:* a powered-on idle GPU is a failure; the
  gpu-queue always carries a successor.
- *Placement ruling:* the Thor is Casey's primary system, worked
  by him directly; Muse's/platform's lanes do not colonise it.

Resolution — **the platform is a tenant with a yield contract:**

1. **Foreign-work detection**: the perception scheduler samples
   GPU utilisation and non-platform GPU processes every 2 s.
   Sustained non-platform GPU load (>20% for >5 s) or any
   interactive session activity signal ⇒ the platform is no
   longer the primary tenant.
2. **Yield ladder** (each step within one scheduler tick of the
   trigger; in-flight embeds finish, nothing new launches):
   - L1: backfill (§4) pauses. (Backfill is always first to die —
     it is defined as slack-eating.)
   - L2: reflective sampling off; live/library decision budgets
     halved.
   - L3: decision tier off entirely; **reflex-only mode** — diffs,
     hashes and verdicts still publish ("unperceived change"
     events), lenses keep updating their cheap statistics. The
     change feed degrades in *resolution*, never in *liveness*.
   - L4: if the box is under memory pressure, decision models
     unload (reload cost is measured: 11.9 s cold — acceptable,
     and it is paid on recovery, not by the user's work).
3. **Recovery** is hysteretic: 60 s of clear headroom before
   stepping back up, one ladder step per 60 s, so a bursty user
   workload doesn't make perception flap.
4. **The user's own platform use outranks background perception**:
   a stream the user is actively watching gets its decision budget
   from a reserved pool (10% of global) that background streams
   cannot touch. Watching is a tenancy signal, not a budget line.
5. When the box is genuinely idle, the gpu-queue doctrine applies
   in full: backfill keeps the GPU warm (a successor queue is
   named at all times — §4.3), and idle intervals are logged with
   the same honesty as the gpu-queue's idle.jsonl.

**TO-MEASURE:** yield latency end-to-end (foreign load start →
last platform kernel), and false-yield rate (platform stepping
down for a 3 s transcode spike it could have ridden out).

## 3. Learned normal: the lens

Adaptive staggering (wave 2) proved the pattern: a per-lane
LensFile — period/jitter/phase as plain text, self-calibrating —
cut prediction p95 from 854,285 µs (fixed) to 1,669 µs under drift,
and tied exactly when there was nothing to learn. Confluence
generalises the lens from *timing* to *appearance*: each stream
carries a text LensFile describing what normal looks like and how
it moves.

### 3.1 LensFile contents (per stream, plain text, user-readable)

- `baseline_embeddings`: per-tile (camera) or per-context (feed)
  reference embedding refs + their spread (mean pairwise drift of
  confirmed-normal samples).
- `drift_model`: the stream's normal rate of change — EMA of
  per-tick drift (α=0.10, the wave-2 value), plus a diurnal profile
  for cameras (24 hourly drift quantiles: dawn light ramps are
  normal at 07:00 and alarming at 03:00).
- `ranker_calibration`: the reflex→drift mapping *for this
  stream* — the pooled-median threshold of wave 3 was a global
  stopgap; per-stream, the scheduler records (reflex score, true
  drift) pairs from audit samples and refits the admission rank
  weekly.
- `known_rhythms`: periodic non-events (sprinklers at 06:00, the
  mail truck, a feed's hourly wire update) — learned from
  recurrence, proposed to the user, active only once confirmed or
  after 5 unflagged recurrences (*derived rule*, TO-MEASURE).
- `exceptions`: user rulings ("the flag moving is not an event")
  — stored as embedding-space exemplars with negative weight.
- `timing`: the wave-2 fields unchanged (period EMA, jitter
  EMA-variance, signed phase error) for staggered lanes.

### 3.2 Learning, aging, and the drift/change distinction

- **Learning is conservative**: a sample enters the baseline only
  if it was perceived, published as *no-change* (or user-ruled
  normal), and is at least one deadband away from any live alert.
  Contaminated baselines are the classic failure (the intruder who
  stands still becomes furniture) — so baseline admission also
  requires the sample to differ from the *previous* baseline by
  less than the current change threshold. Anything bigger is
  treated as a change and held out, pending either recurrence
  (it becomes the new normal by repetition, not by stealth) or a
  user ruling.
- **Aging**: baseline samples decay with a 14-day half-life
  (EMA-weighted, not a cliff); diurnal profiles re-fit weekly;
  a stream whose lens is younger than 48 h is labelled
  `lens: warming` in its ledger and its change feed carries a
  lower trust badge (§3.3). Seasonal change is handled by the
  diurnal+decay pair, not by special cases. TO-MEASURE: half-life
  sensitivity on a month of real camera data.
- **Drift vs change**, defined operationally: *drift* is movement
  whose per-tick size stays within the lens's normal drift
  quantiles — it updates the baseline and never publishes.
  *Change* is a tick (or short run of ticks) whose drift exceeds
  the lens's 99th percentile *and* survives the sheaf refine.
  The twilight zone between them accumulates in a per-stream
  **pending-drift accumulator**: slow-but-relentless movement
  (a creeping shadow line, a boat settling, a story developing
  across a feed's day) publishes once when the accumulated
  displacement crosses the change threshold, with the verdict
  honestly labelled `slow-change` and its time-span attached.
  This is the mechanism wave 3 lacked: its A_burst sequence
  (genuine per-frame drift ≈0.48 vs a 0.25 threshold) shows what
  happens without it — everything fires, all the time.

### 3.3 False-alarm economics (the trust budget)

The change feed is a promise: *silence means nothing happened.*
That promise is kept or broken on precision, and wave 3 sets the
honest starting point: **the reflex gate is a ranker, not a
separator** (audit drift 0.202 skipped vs 0.484 embedded — real
signal, no clean cut). Fixture precision (curated, sheaf-refined)
was 1.000; uncontrolled-material precision is **TO-MEASURE** and
must not be quoted from the fixture.

Design targets the feed must hold, stated as engineering
requirements to be verified on real streams:

- **≤1 false change event per stream per day** at default budget.
  Above ~1/day/stream, users mute the stream (the Ring failure
  mode); a muted stream is worse than no stream. This, not raw
  precision, is the operative metric, and it is why the budget
  (§2) and the lens (this section) are one system: precision is
  *bought* with embeds and *earned* by calibration.
- Every published event carries its evidence (tiles/fragments,
  drift, Jev probability if sampled) so a false alarm is
  *correctable in one tap* — the correction writes an exception
  exemplar into the lens (§3.1). Cost of being wrong must be one
  tap, or users stop correcting and the lens rots.
- Recall is deliberately traded: at "sip" budget the system
  *states* its expected miss mode in the ledger ("this stream is
  sipping: sub-threshold change may pass unperceived") rather than
  pretending completeness. A watch that admits its blind spots
  keeps trust; one caught pretending loses it permanently.
- Trust accounting is published per stream in its ledger: events
  fired, user-confirmed, user-dismissed, trailing 7-day precision
  estimate. The platform reports its own precision the way the
  repo reports bench numbers — measured, or marked unmeasured.

## 4. Library perception (backfill + index)

Library video is the one stream class with no live clock, which
makes it the natural slack-eater and the natural first tenant of
the idle GPU.

### 4.1 Ingest-time backfill: the overnight staging ladder

Per the staging ladder doctrine, overnight is a legitimate render
time; a library is perceived in passes, each pass complete and
useful on its own — never a half-perceived title presented as
perceived (completeness % is in the ledger, §1.1):

1. **Pass 0 — inventory** (minutes): probe, hashes, technical
   metadata, poster frames. Reflex only. The title is browsable
   immediately.
2. **Pass 1 — structure** (same night): scene cuts (reflex),
   per-scene embeddings (decision). *Derived throughput:* at
   173 ms/scene-frame and ~400 scenes/2 h title, ≈70 s of embeds
   per title plus decode/diff time — a 500-title library is a
   few GPU-nights, not a month. TO-MEASURE at scale (decode may
   dominate; measure before promising).
3. **Pass 2 — speech** (following nights): STT transcripts.
   Throughput TO-MEASURE (Whisper RTF on Thor unknown).
4. **Pass 3 — meaning** (background, reflective): chapters,
   highlights, synopsis, entity extraction — from transcript +
   scene structure, text-only. LLM cost per title TO-MEASURE.
5. **Pass 4 — deepening** (opportunistic, lowest priority):
   busy-scene tile grids, per-scene audio events, re-embedding
   with better models as the rack's shelf improves. The index is
   versioned by model; re-embedding never blocks the earlier
   passes' usefulness.

Queue order inside backfill: newest additions first (the user
just acquired them), then most-watched unpinned titles, then the
long tail by size ascending (smallest finishes first — the
download-governor's smallest-to-largest lesson applied to jobs).
Backfill is L1 on the yield ladder (§2.3): it exists to be
pre-empted.

### 4.2 The index: searchable by content

- **Scene embeddings**: 1280-dim I-JEPA vectors in a flat
  vector store (at library scale — 10⁵–10⁶ scenes — brute-force
  cosine on GPU is subsecond; a dedicated ANN index is
  TO-MEASURE/only when profiling demands it. Do not build the
  index infrastructure before the measurement).
- **Transcripts**: full-text index over word-timestamped STT —
  every spoken line is findable and seekable ("jump to where
  they say *harbour*").
- **The join is the product**: scene embeddings × transcript ×
  chapters in one query surface. A query resolves to *moments*
  (title, t0, t1), not titles.
- Embeddings stored as refs in the ledger; vectors in the store.
  Ledger stays text and diff-able; vectors stay binary and
  rebuildable (doctrine: geometry is a cache, the seed+params —
  here, the media + model version — are the asset).

### 4.3 Day-one queries (acceptance list)

The index is done when these answer correctly against a test
library with known content (ground truth by construction, the
wave-3 method):

1. "Every scene with a boat / a dog / snow / a kitchen at night"
   — visual content search over scene embeddings.
2. "Where does anyone say *…*" — transcript search with seek.
3. "The scene where the harbour burns" — combined: transcript
   fragment × visual drift peak within the same scene window.
4. "More moments like this one" — embedding nearest neighbours
   from a user-picked moment.
5. "What are this title's highlights" — chapter/highlight list
   from Pass 3, each with its evidence (drift peak, transcript
   salience) attached.
6. "Show me everything that changed in the library this week" —
   the library is also a feed: new arrivals arrive *perceived to
   Pass 1 minimum* before they are announced.

Queries 1–4 depend only on Passes 1–2; 5 on Pass 3; the spec's
claim is that 1–4 work on day one for new arrivals and night one
for the back catalogue. All six are TO-MEASURE for precision —
the acceptance test reports the numbers, favourable or not.

---

*End of Spec B. Companion specs: A (substrate/serve), C (client/
ledger UI), D (tenancy/runtime ops) — cross-references by section
number.*


---

## §C — Serve plane, attention plane, build order

Working title "Confluence": the application layer over
SI-Thor/rolling-perception. One Thor-native platform for all of the
household's own streams — media library, live sources, cameras,
audio — local-first on a Jetson AGX Thor, with rolling perception
underneath (what that layer has already proved is in
`docs/WAVE3.md`; this spec cites those numbers, it does not
re-derive them).

Scope of this document: the serve plane (catalogue, player,
clients, profiles), the attention plane (the cross-stream change
feed and cross-stream actions — the differentiator), the build
order, and risks. Ingest and the perception pipeline itself are
other lanes' specs; this one consumes their outputs: per-stream
text state, per-item embeddings/transcripts, and published change
verdicts.

Design rule inherited from the whole project: **no claim without a
measurement**. Anything below that is not yet measured on the Thor
is marked TO-MEASURE or ESTIMATE, never stated as a capability.

---

## 1. Serve plane

### 1.1 Catalogue — one shelf across stream types

One library, one shelf, every stream type on it. An item is an
item whether it is a film, a recorded camera event, a live channel,
a radio stream, or a podcast episode. Concretely:

- **Unified item model.** Every item carries the same spine:
  id, type (film / series-episode / live / camera-event /
  audio / recording), title, source, duration or live-ness,
  thumbnail, perception state (unperceived / perceiving /
  perceived), and pointers to its artefacts (embedding set,
  transcript, verdict history). Type-specific fields hang off the
  spine, never fork the model.
- **Rails, not folders.** The home screen is generated rails over
  the unified model: Continue Watching, New Since You Last Looked
  (fed by the attention plane, §2), Live Now, Recently Perceived,
  per-source shelves (Library / Cameras / Radio). A camera event
  and a new episode sit in the same rail grammar.
- **Search is perception-backed, not filename-backed.** Text search
  over titles, transcripts, and perceived descriptions ("harbour
  at night", "the scene where the boat leaves"). The transcript
  and embedding index comes from the perception plane; the serve
  plane only queries it. Search quality is bounded by perception
  coverage — an unperceived item is searchable by metadata only,
  and the UI says so on the item (perception state is visible, not
  hidden).
- **Admin is a shelf too.** Ingest sources, perception queue and
  budget, storage, and profile management live in the same UI as
  an admin section — not a separate console product. (The
  Netflix-clone pattern of a full admin CMS is explicitly out of
  scope; see §1.6.)

### 1.2 Player

- **One player for every type.** The same player chrome plays a
  film, a camera recording, a live stream, or audio (audio gets
  the transcript view as its "picture"). Live items get a
  live-edge indicator and a "jump to the flagged moment" list —
  the verdicts from the perception plane rendered as chapter
  marks on the scrub bar. For a camera recording, those marks are
  the change events; for a film, perceived scene boundaries.
- **Resume across devices is server state, not client state.**
  Position, per profile, per item, stored on the Thor; any client
  picks up where any other left off. Resume granularity: the
  player heartbeats position every 10 s and on pause/close
  (ESTIMATE: worst-case resume error ~10 s; tighten to ~2 s if the
  heartbeat cost proves trivial — it is a local write, so it
  likely will).
- **Quality / transcode strategy.** Source files are served
  direct-play when the client can handle the codec; otherwise the
  Thor transcodes. Ladder: original → 1080p → 720p → 480p,
  client picks by measured throughput, can be pinned per profile
  (the kid profile can be pinned to a ceiling, §1.4).
  **Transcode throughput on this Thor is TO-MEASURE** — number of
  simultaneous 1080p transcodes, and whether the hardware encoder
  path is usable from our stack, are unknown until benched. The
  build order (§3, Slice 2) carries the bench as an acceptance
  item. Until that number exists, the design assumes the worst
  case that still works: **one** live transcode at a time, queue
  beyond that, prefer pre-transcoded derivatives for the library's
  hot items (computed in idle time — the perception budget
  machinery already knows how to spend idle cycles).
- **Subtitles and transcripts are perception output.** Where a
  source has embedded subtitles, use them. Where it does not, the
  perception plane's transcript (speech-to-text on the audio lane)
  is the subtitle track — same file, two uses: it renders as
  captions in the player and it is the search index in §1.1.
  Consequence stated plainly: caption availability follows
  perception coverage and speech-to-text accuracy, both measured
  elsewhere; the player must handle "transcript pending" and
  "no transcript" as normal states, not errors.

### 1.3 Clients

- **Browser first.** The reference client is a web app served by
  the Thor itself. Every feature lands there first; other clients
  are projections of it. No app store, no install, works on
  anything in the house with a browser.
- **TV = browser on a light client.** The big-screen client is the
  same web app in a TV-browser / kiosk mode driven by an
  Orin-class light client (or the TV's own browser where it is
  adequate): 10-foot layout, remote-first navigation, no
  independent feature set. If the TV browser proves too weak in
  practice, the fallback is the same web app in a native shell —
  decided by use, not in advance.
- **Phone.** The web app, responsive; the phone is primarily the
  attention surface (§2) — the change feed and alert follow-ups —
  and a remote-resume client second. Playback on the phone works
  but is not the design centre.

### 1.4 Profiles

- **Household profiles, minimal model.** A profile is: a name, an
  avatar, a set of shelves it sees, its own Continue Watching and
  resume state, and its own attention-feed preferences (§2.4).
  Profiles are a viewing/attention boundary inside one house,
  **not** a security boundary — no passwords between household
  profiles by default (a PIN on the adult/admin profile is
  offered, off by default, decided by the household).
- **Kid profile (Casey's son).** A profile with: a curated shelf
  (items explicitly shared to it, not a filter over the whole
  catalogue — allowlist, not blocklist), a quality ceiling if set,
  no admin section, no attention-feed alerts except ones a parent
  profile routes to it (default: none). The allowlist is a parent
  action in the admin shelf, one tap per item or per collection.
  Scope discipline: the kid profile is a shelf + a ceiling, not a
  parental-control product — no time limits, no usage reports, no
  content-rating engine in this spec (see risks, §4).
- **Guests** are not a profile type; a guest uses the household's
  living-room profile on the TV. Multi-household support is out
  of scope entirely.

### 1.5 Offline / download posture

- The house is the primary venue and the Thor is on the LAN, so
  **offline is a cache, not a sync system**. A client (phone,
  laptop leaving the house) can pin items; the Thor serves a
  derivative at the profile's quality ceiling into the client's
  local storage; the pin expires when removed, no background sync,
  no conflict resolution (there is nothing to conflict — the Thor
  copy is the only canonical one).
- Resume state still lives on the Thor; an offline play updates
  its local position and reports it back on reconnect, last-write
  wins. That is the entire offline consistency model, stated so
  nobody builds more.

### 1.6 Deliberately NOT built

- **No payments, no subscriptions, no plans, no trials.** It is
  the household's own media on the household's own box. The
  Netflix-clone feature list (Stripe checkout, tiers, entitlement
  gating) exists to monetise strangers; there are no strangers.
- **No DRM, and no DRM'd-source ingest.** Commercial services are
  unified only at the honest layer — catalogue entries with
  deep links into their own apps (other lanes' spec covers the
  directory mechanics). Confluence never decrypts, re-hosts, or
  re-serves a DRM'd stream.
- **No recommendation engine.** Rails are chronological,
  continuations, and perception-derived (new, changed, similar-
  by-embedding where the perception plane offers it). No
  engagement optimisation, no per-user behavioural model.
- **No social features.** No reviews, ratings, comments, sharing
  outside the house.
- **No cinema-booking anything.** That was StreamVibe surface
  area for a business this is not.

---

## 2. Attention plane

The serve plane is table stakes — every media platform has a
shelf and a player. The attention plane is why this exists:
**the box perceives all of its streams continuously, and the
household's scarcest resource — attention — is spent only where
reality changed.** Design anchor: "Watch this for me. Tell me
what changed. Otherwise, silence."

### 2.1 The cross-stream change feed

- **One feed, all sources.** "What changed while I was out" is a
  single chronological feed whose entries come from every stream
  the perception plane watches: a camera flagged a change (with
  the changed tiles / region shown, as wave 3's report already
  renders), a library item finished perceiving, a new item
  arrived, a download completed, a live stream produced a flagged
  moment, a score or state the household tracks moved. Entry
  grammar is uniform: *source, what changed, when, evidence
  attached* (thumbnail, tile overlay, transcript excerpt,
  before/after values).
- **Entries are verdicts, not raw events.** The feed consumes the
  perception plane's published verdicts — the same publish rule
  wave 3 established: a verdict is a claim about *this* moment;
  stale scores do not re-fire. A feed entry that turns out wrong
  stays in the feed, marked corrected — the feed is a record, not
  a notification tray that quietly deletes its mistakes.
- **The feed is the home screen's second rail** (§1.1) and a
  full page of its own; the phone client (§1.3) leads with it.

### 2.2 Alert policy — silence by default

The feed is pull; alerts are push, and push is rationed.

- **Default: nothing pushes.** Every change lands in the feed;
  an alert (phone push / spoken / TV interruption) fires only
  when a rule the household wrote says it should (§2.3), or when
  a source the household explicitly promoted to "tell me now"
  crosses its threshold.
- **The precision bar is inherited from wave 3, numerically.**
  Wave 3's measured results set the expectation: the sheaf-refined
  cascade reached precision 1.000 / recall 1.000 on the controlled
  fixture; the diff gate alone is a ranker, not a separator
  (skipped-tile drift 0.20 vs embedded 0.48). Policy consequence:
  **no alert may be wired to the cheap gate alone.** Anything
  that pushes must pass the refined verdict path, and any source
  whose measured precision on the household's own ground truth
  (the first weeks of feed corrections are exactly that ground
  truth) drops below 0.9 gets demoted to feed-only automatically,
  with a feed entry saying so. False alarms are the product
  failure; a missed minor change in the feed is a shrug.
- **The reflective judge's seat is already decided** by wave 3's
  measurement: Jev-class judgement rides *in* the verdict as a
  recorded probability (advisor seat), it does not gate alerts.
  Alert logic thresholds the refined verdict and the advisor
  probability together only where a household rule says so.
- **Quiet hours and per-profile routing** are part of the policy,
  not preferences garnish: alerts route per profile, and the
  default household quiet window suppresses all but rules marked
  "wake me" (default: none are).

### 2.3 Cross-stream rules and actions

Rules connect a verdict on one stream to an action on another.
Kept deliberately small and mechanical — rules are code-held
values, models advise (the fleet's standing doctrine), and every
rule is visible and editable in plain language (§2.4).

Initial rule set (v1 — each ships only when its slice lands):

1. **Door camera → player.** A person-verdict at the door camera
   (refined path, precision bar per §2.2) pauses playback on the
   living-room client and shows the camera's live view as an
   overlay card; dismissing resumes. If nothing is playing, it is
   a feed entry plus an alert per policy — no overlay.
2. **Harbour camera → live view raise.** A flagged harbour change
   (boat moved, person on the dock) raises the harbour live view
   on the bridge console (§2.4) and pins the event clip at the
   top of the feed; it pushes only if the household promoted
   harbour events to "tell me now".
3. **Playback → perception budget.** While any client is playing,
   background perception drops to its low-power budget (the gate
   spends less; the playing stream's own live perception is
   unaffected). Playback smoothness outranks background indexing
   — this rule exists because the transcode/perception contention
   numbers are TO-MEASURE (§1.2), and the safe default is to
   protect the thing a human is watching.
4. **New item → shelf.** A library item that finishes perceiving
   enters the New rail and the feed once — not at ingest, at
   *perceived*, because perceived is when it becomes searchable
   and describable (§1.1).

Rules are data (a small table: trigger verdict, condition,
action, profile scope, on/off), edited in the UI; adding a *kind*
of rule is a code change, adding an *instance* is not. No
free-form automation builder in v1 — that is a scope cliff
(see §4).

### 2.4 The bridge console

One projection of all streams' state — Casey's standing bridge-
console doctrine applied to the house's streams.

- **A single live page**: every stream as a tile — live sources
  show their current frame/state and their last verdict; library
  and ingest show queue and perception progress; players show
  who is watching what, where paused. Change-only updates with a
  deadband heartbeat (rooms-perceive doctrine): the console does
  not re-render the world on a timer, it renders *deltas*, with a
  slow heartbeat so "quiet" is visibly different from "dead".
- **The console is a projection of text state**, per the world-
  is-text doctrine: each stream's canonical state is its text
  record in the ledger; the console, the feed, and the shelf are
  three renderings of the same records. If the console and the
  feed ever disagree, the ledger is right and the rendering has a
  bug — that ordering is a design commitment, not a hope.
- **Density is per audience.** The console defaults to the
  human face (chart-like, glanceable, on the TV when idle as the
  house's ambient screen — ESTIMATE: this becomes the most-seen
  screen in the house, which is why it is in Slice 4 and not
  later). The full-density per-stream text readouts sit one tap
  behind each tile.

### 2.5 User controls, in plain language

Every control is stated the way a household member would say it;
the UI uses these words, not the spec's:

- "Tell me now / Feed only / Never show me" — per source, three
  positions, no finer grain in v1.
- "What changed while I was out?" — one button; the feed filtered
  to since-last-looked, per profile.
- "That's not a change" / "That mattered" — one-tap corrections
  on a feed entry; these are the ground-truth labels §2.2's
  demotion rule consumes, and they retrain nothing automatically
  in v1 (they are recorded, reviewed, and used to adjust
  thresholds deliberately — no silent self-modification).
- "Watch this for me" — promote any source (a camera, a folder, a
  live stream) into the perceived set; "Stop watching this"
  removes it. The perception budget display sits next to these
  controls in plain units ("watching costs ≈ X embed-minutes a
  day at current settings" — the unit is an ESTIMATE until the
  live budget bench lands).
- "Pause everything" — one control that stops all alerting and
  background perception; playback and the catalogue keep working.

---

## 3. Build order

Five slices. Each is independently useful in the hand the day it
lands — the standing standard: progress is a result usable in
his hands, not infrastructure awaiting a reveal. Each slice has a
pre-committed acceptance test with at least one measured number;
if a slice misses its test, the miss is the result and is written
into the record before the next slice starts.

### Slice 1 — The change feed over one camera + the library shelf

**What:** The smallest thing that makes a person say "I need
that": the Thor watches **one** real camera (the harbour or door
camera) through the wave-3 cascade, and the household opens one
page that shows (a) the unified shelf of the existing library
(metadata search only) and (b) the change feed for that camera —
"What changed" entries with the changed-region evidence image,
in the wave-3 report format, live.

**Acceptance test (pre-committed):**
- Over a continuous 48 h run on the real camera: feed precision
  ≥ 0.9 against hand-labelled ground truth for that window
  (labels from the one-tap corrections), and **zero** missed
  staged events (a person walks the scene at three announced
  times — recall on staged events = 3/3).
- Feed page renders the 48 h window (ESTIMATE ≤ 200 entries)
  in ≤ 2 s on the Thor over LAN.
- Perception spend for the window is reported in embed count and
  rack seconds, next to the ALL-strategy counterfactual (the
  wave-3 method), and the gated spend is ≤ 60% of ALL.

**Dependencies:** wave-3 harbor-watch crate + driver (exist),
JEV rack residency decision (the rack was inactive at wave-3's
end — Slice 1 requires it running as a service during the window;
that is an operational decision for Casey, flagged here, not
assumed). **Deferred:** alerts/push (feed is pull-only), other
cameras, content search, profiles, playback.

### Slice 2 — The player: library playback with resume + the transcode bench

**What:** Browser playback of library items with server-side
resume across two devices, direct-play first, transcode ladder
behind it; the transcript/subtitle track rendered where a
transcript exists.

**Acceptance test (pre-committed):**
- Resume: start on the TV client, continue on a phone browser —
  position error ≤ 10 s (the §1.2 heartbeat), measured over
  10 hand-offs, 10/10 within tolerance.
- **The transcode bench (the number §1.2 is waiting for):**
  measured simultaneous 1080p transcodes sustained 10 min
  without dropping below real-time, and GPU/CPU headroom during
  one transcode + one playback + background perception at low
  budget. The result is written into §1.2 either way — if the
  number is 1, the queue design stands and the spec says 1.
- Cold start: pressing play on a direct-play item reaches first
  frame in ≤ 3 s over LAN (median of 10).

**Dependencies:** Slice 1's shelf (items and item model).
**Deferred:** offline pins, quality pinning per profile, live
playback, chapter marks.

### Slice 3 — Profiles + kid profile + perception-backed search

**What:** Household profiles with separate shelves/resume/feed
preferences; the kid profile as allowlist shelf + ceiling;
search over transcripts and perceived descriptions for all
perceived items.

**Acceptance test (pre-committed):**
- Search: on a fixed 20-query set over the perceived library
  (queries written before the index is built), ≥ 15 return the
  intended item in the top 3 (measured, queries and results
  recorded verbatim).
- Kid profile: an audit pass over every surface reachable from
  the kid profile finds 0 items not on the allowlist (checklist
  audit, recorded).
- Profile switch ≤ 2 taps from any screen; resume state provably
  separate (same item, two profiles, two positions, both
  restored correctly in a scripted pass).

**Dependencies:** Slices 1–2; a perceived corpus large enough
for the query set to mean something (ESTIMATE: ≥ 50 perceived
items — if the library's perceived count is lower, the query set
shrinks to fit and the shortfall is recorded).
**Deferred:** PIN enforcement, per-profile alert routing beyond
feed preferences (lands with Slice 4 alerts), guest mode.

### Slice 4 — Alerts, cross-stream rules, bridge console

**What:** The attention plane goes live: push alerts under the
§2.2 policy, rules 1–4 of §2.3, and the bridge console page.

**Acceptance test (pre-committed):**
- Alert precision over a 14-day live window: ≥ 0.9 against the
  household's one-tap corrections, with total push count for the
  window reported alongside (precision at a volume of 2 is not
  the same achievement as at 200 — both numbers ship).
- Rule 1 (door → pause + overlay): end-to-end latency from
  staged door event to paused player ≤ 5 s, 5/5 staged trials.
- Console: all connected streams' tiles reflect a staged change
  within ≤ 5 s of its verdict; the console page itself adds
  ≤ 5% CPU on the Thor at idle (measured over 1 h).

**Dependencies:** Slice 1 (feed + verdicts), Slice 2 (a player
to pause), Slice 3 (profiles to route to). The 14-day window is
calendar time, not effort — this slice's acceptance is the
slowest by design, because alert trust is earned in weeks.
**Deferred:** rules beyond the initial four, any rule *builder*
UI, spoken alerts, wake-me rules.

### Slice 5 — All streams: live sources, audio, offline pins

**What:** Live streams and audio join the same shelf/feed/player
(audio with transcript view; live with flagged-moment marks);
offline pins per §1.5; the commercial-service directory entries
(deep links only, §1.6) appear on the shelf, badged as external.

**Acceptance test (pre-committed):**
- One live source runs perceived for 24 h: flagged-moment marks
  land within ≤ 60 s of the moment (median over the window's
  flags, hand-checked on a 10-flag sample), and live playback
  through the house player holds a ≤ 10 s glass-to-glass latency
  budget (ESTIMATE to be replaced by the measured number from
  the first live bench).
- Offline pin: a pinned item plays fully offline on the phone
  (airplane-mode pass), and its position reconciles on reconnect
  per §1.5's last-write rule in a scripted check.
- Shelf audit: every item on the shelf renders its type,
  source, and perception state correctly in a full-catalogue
  pass (0 mislabelled in the audit sample of 50).

**Dependencies:** Slices 1–4. **Deferred:** second camera
onboarding is *not* deferred — it is expected to happen
opportunistically from Slice 1 onward as data; what Slice 5
defers is multi-*household* anything, native apps, and any
public release packaging.

---

## 4. Risks / open questions (top 5, honestly stated)

1. **Transcode capacity is unknown and could be the binding
   constraint.** Everything in the serve plane that involves
   more than one simultaneous viewer, or viewing + perceiving at
   once, leans on a number nobody has measured on this box
   (§1.2, Slice 2's bench). If the Thor sustains only one
   transcode, multi-room playback of non-direct-play material
   queues — survivable, but it demotes "the house's media box"
   to "one screen at a time for some files", and the pre-transcode
   derivative strategy moves from optimisation to load-bearing.
   Mitigation is designed in (direct-play first, idle-time
   derivatives, Rule 3 protecting playback) but the risk is real
   until benched.
2. **Library backfill time.** Perceiving an existing library at
   wave-3 rates (embed p50 173 ms per tile crop, transcripts at
   speech-to-text speed) means a large library takes days-to-
   weeks of background budget to become searchable-by-content
   (total hours = a function of library size nobody has counted
   yet — TO-MEASURE at Slice 3 planning). Until backfill lands,
   the flagship search demo works on the perceived subset only,
   and the UI must not oversell coverage (§1.1's visible
   perception state exists precisely for this).
3. **Feed-source fragility.** The attention plane is only as good
   as its least reliable source: cameras drop off networks, live
   stream URLs rot, download sources change shape. A source that
   silently dies produces the worst failure mode this product
   can have — *confident silence* (the household believes "no
   change" because the watcher is dead). The heartbeat/deadband
   design (§2.4) detects a dead console projection; source-level
   liveness ("camera X has produced no frame in N minutes" is
   itself a feed entry) must be built with Slice 1, and even so,
   source churn is a permanent maintenance tail, not a one-time
   cost.
4. **Household-profile scope creep.** Profiles look small and
   grow teeth: the kid profile invites time limits, content
   ratings, per-item disputes between household members about
   shelves and alert routing, and "just add accounts for the
   neighbours". Each addition is reasonable in isolation and
   collectively they turn a household shelf into a consumer
   product's worth of policy machinery. The spec's defence is
   the allowlist-only kid model and the explicit non-goals
   (§1.6), but the pressure will come from real household life,
   not from engineering — it is flagged here so the decision to
   grow is made deliberately, on the record, or not at all.
5. **Single-box failure.** Confluence concentrates the house's
   media, perception, feed history, and alerting on one Thor.
   Its failure is total: no shelf, no feed, no alerts, and —
   worse — no *record* that anything was missed. Mitigations are
   partial and known: the ledger is text and cheap to mirror to
   a second box (the Orin is the natural mirror target), media
   files themselves live on storage that outlives the service,
   and the cameras keep their own local recording where they
   have it. But v1 has no failover, and the honest statement is
   that the household trades the cloud's redundancy for the
   box's locality and privacy, knowingly. Whether that trade
   needs a hot spare is an open question for Casey, not a
   decision this spec makes.

---

*End of Spec C. Companions: ingest/perception specs (other
lanes). All ESTIMATE and TO-MEASURE markers are debts this
document owes the record; each names the slice whose acceptance
test pays it.*

===== DOCUMENT 2: docs/SPEC-AMENDMENT-1.md (product: Thor back-end, thin devices, technician install/service) =====

# Spec Amendment 1 — the product shape: engine room + thin devices

*2026-11-01, Casey's framing, recorded the day Slice 1 started.*

The spec describes a platform. Casey named the **product**:

> A Thor is the back-end superpower for any thin device — a phone
> becomes the IO, cameras included. And "product" means a thing
> his technicians can install and service. All open source, easy
> to use.

Consequences, binding on the build order:

1. **Thin devices are first-class citizens, not demo props.** The
   phone-as-camera is the reference IO node: zero-install on the
   device beyond a commodity streaming app, discovered on the LAN
   by the platform, perceived by the Thor. Tablets, old phones,
   Orin-class boxes and browsers are the same citizen at different
   sizes. The platform's API surface is designed for devices that
   bring a sensor and a screen and nothing else.
2. **Installability is a feature with an acceptance test.** Slice 1
   ships with a technician's install guide and a dry-run-first
   installer (`slice1/install/` in the working tree). A build that
   only Muse can install is not the product. Serviceability means
   plain-language health, named faults with symptom → check → fix,
   and a service card a technician can work from without the repo.
3. **Open source is the distribution.** The repo's graduation
   (private → public, Casey's call) is the product launch channel:
   technicians install from the public repo, and the docs a
   stranger reads are the docs the technician uses. The
   stranger-test standard from wave 2 applies to every slice.
4. **The customer is a household; the channel is a technician.**
   Design reviews must pass both readers: the person who lives
   with the feed, and the person who gets called when it breaks.
5. **One wiring model for the technician (Casey, same day).** The
   uniformity is not an aesthetic — it is the service model. If
   everything is a cell with power and IO attached, the technician
   learns ONE way to wire anything together: a camera, a voice, a
   model, a stream. No per-device folklore, no special cases to
   memorise. The complexity lives inside the cells.
6. **Agents are the optimisers in the background.** What lives
   inside a cell — the actual logic of the application — is
   optimised continuously by coding agents, and the scoreboard for
   that optimisation is the human experience of the system: the
   feed's trustworthiness, the presence at the table, the
   technician's ten-minute install. Humans wire cells and judge
   experience; agents grind the internals. A technician never
   needs to know which model or scheduler a cell runs this month.
7. **Converters are the platform's problem (Casey, same day).** The
   technician thinks like the person who wires a building: what
   connects where, and which protocol the connection speaks. Where
   two things don't natively speak — a camera's stream into the
   ledger's text, a model's dialect into a verdict — the back end
   provides the converter, maintained by the agents. The
   technician's craft is wiring, endpoints and protocols; what a
   converter does inside is one more cell interior he never opens.
   A connection that needs a human to translate is a missing
   converter, and a missing converter is a platform bug, not a
   service call.
   Corollary (Casey): this is why coding agents are the most
   powerful thing to come out of AI — they make a *translation*
   become a *conversion*. A translation is an event: a human
   understands how two things map, and the understanding evaporates
   when they leave the room. A conversion is an asset: the mapping
   exists as working machinery, forever, for everyone. Agents
   collapse the cost between the two, so comprehension compiles
   into infrastructure — every explanation only has to happen once.

===== DOCUMENT 3: docs/SPEC-AMENDMENT-2.md (presence: any device is a terminal) =====

# Spec Amendment 2 — presence: any device is a terminal, the system sits at the table

*2026-11-01, Casey's framing, recorded while Slice 1 was building.*

Amendment 1 made thin devices first-class IO. Casey extends it:

> The system should be device agnostic. You should be able to pull
> up a browser on the ProArt laptop and use the speaker and
> microphone connected directly on the network to the Thor — and
> the system can be present with you, like it's there at the table.

## What this means in the architecture

1. **A terminal lends senses, not just a screen.** Any browser on
   the LAN can offer the platform its camera, microphone, speaker
   and display as a bundle. The Thor remains the only mind:
   perception, memory and voice are computed there; the device is
   IO. Joining is opening a page — no install, no app, no pairing
   ritual beyond being on the house network.
2. **Presence is a session, not a sensor.** A presence session is
   something a person deliberately opens (like joining a call) and
   can see is live. Voice is conversational: the system listens,
   answers through the same device's speaker, and its attention is
   the rolling perception already in the substrate — the room's
   streams, the change feed, the ledger — so "what did I miss?"
   and "what's happening at the dock?" are questions it can answer
   from its own records.
3. **Prior art is inventoried, not rebuilt.** The fleet already
   proved this loop on this hardware: Radio Room (ProArt + Thor,
   2026-10-23) — hold-to-talk capture, faster-whisper STT on the
   Thor side, a persona brain, Piper TTS dressed as radio audio,
   per-stage receipts. Confluence generalises that point solution
   into a platform capability any terminal can join, and inherits
   its lessons (subprocess audio IO, not PortAudio; placement is a
   wash, contention decides).

## The boundary that does NOT move

Panel 1's refusal stands: **no always-on ambient microphone
perception.** Presence audio exists only inside a session a person
opened, with a live indicator, and ends when the session ends.
The distinction is consent and visibility: a voice at the table
you invited, versus a microphone that never sleeps. Camera change
perception (Slice 1) is a separate, declared watch; presence does
not silently widen it.

## Sequencing

Slice 1 (live change feed + shelf + install pack) is unchanged and
already building. Presence becomes the headline of the next slice
after Slice 1's acceptance, reusing the Radio Room pipeline as its
starting point and the ledger/health surfaces from Slice 1 as its
face. Its acceptance will include a from-the-chair test: a
conversation held through a laptop browser, at the table, with the
system answering from the live ledger.

## Lineage (one paragraph, deliberately no more)

Confluence is the quilt paradigm wearing product clothes: anything
is a cell in a graph — a stream, a terminal, a model, a camera, a
voice — and the connections between cells are second-class citizens
next to the function each cell achieves with whatever power and IO
is attached to it. The substrate's rings are one rendering of
cell-to-cell flow; the ledger is the graph written as text. The
build stays on Confluence; the paradigm is the inheritance, not a
second project.

===== END OF SPECIFICATION =====

You are an adversarial design reviewer for the system specified above. Panel output is testimony, not measurement: be concrete, name mechanisms and numbers where you can, do not flatter, do not restate the spec back. Answer ONLY the question below, in structured form (numbered points), in at most ~900 words.

QUESTION 4 — TECHNICIAN FAILURE. The product model (Amendment 1 §§5–7) promises a field technician ONE wiring model for everything: every thing is a cell with power and IO; converters are the platform's problem; the technician thinks in wiring, endpoints and protocols, never in cell internals. ATTACK this promise. Name THREE concrete field situations — real houses, real networks, real devices — where the one-model promise breaks and the technician is stranded on site with a dead install. For each: what exactly breaks the model (not the device — the MODEL), what the technician experiences, and what specific platform feature would un-strand them (a tool, a ledger surface, a fallback mode, a converter class). No generic "better docs" answers; each fix must be a buildable feature.
