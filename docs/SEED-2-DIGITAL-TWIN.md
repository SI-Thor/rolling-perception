# SEED 2 — "Re: digital twin": preservation, verification, and fit

Lane SEED-2, 2026-11-02. Study only: nothing was downloaded (no
model weights), nothing was installed, no box was touched.

**Source:** Casey's seed email *"Re: digital twin"* (2 Nov 2026,
15:41 AKST; Gmail id `1a19eda9fc1b35a1`), self-sent, carrying a
37 KB attachment `try1.md`. Like seed 1, it is a multi-generation
LLM-chain artefact: the email body is a refined four-step pipeline
with an "unrefined:" original (citation links intact), and the
attachment is a longer chain that re-answers the same questions
several times, each time with more architecture and more invented
specifics than the last.

**Archive:** the raw email snapshot and the attachment are kept
verbatim alongside this doc, following the seed-1 precedent
(mail-archive copy + a grading document that cites it):

- `docs/seed-2/email.md` — the Gmail snapshot (body, refined +
  unrefined, attachment inventory).
- `docs/seed-2/try1.md` — the attachment, byte-identical to the
  Gmail download (37,381 bytes, md5 `a7c83bc51bc680ae953ae284a`).

**Rule applied, same as seed 1:** every load-bearing claim in the
chain is unverified until checked against a primary source. This
doc grades the claims; it does not port the email.

---

## Deficits first — what does not survive checking

The seed's spine is real (see §2). What does not survive is
almost everything the attachment adds on top of the spine, plus
the one thing that matters most for us: **the hardware story is
backwards.** The chain puts the heavy generative work on the
Jetson Thor. EdenLive's own verified environment is **Linux
x86-64 with an 80 GB NVIDIA GPU**, its default 5B profile needs
**SM90** kernels (flash-attn-4), and its real-time numbers come
from an **H100** and an **RTX 5090**. The Thor is aarch64,
**sm_110**, with ~273 GB/s of LPDDR5X bandwidth against a 5090's
~1,792 GB/s. There is no port, no Jetson recipe, and no aarch64
path in the repo. On our hardware EdenLive does not run slowly;
it does not run.

Itemised, worst first:

1. **"Run EdenLive on the Thor" — FABRICATED as stated.**
   Repo-verified environment: `Linux x86-64, NVIDIA GPUs with
   80 GB (CUDA 13 driver)`; default 5B bidirectional profile
   "requires SM90, BF16, `flash-attn-4`". The Reactor integration
   "runs on one B200". The 24 FPS real-time figure is LightX2V on
   a **single RTX 5090** (≈24.7 FPS at 1280×704) and VAST's own
   table is an **H100** (5B: 73.5 FPS @ 832×480, 29.8 @
   1280×704). Nothing in the repo, the model card, or the
   project page mentions Jetson, aarch64, or sm_110.
2. **The attachment's Thor "production architecture" is
   invented.** "EdenGolem + Live" as a rendering layer fed by
   NVIDIA Isaac (simulation) and NVIDIA Cosmos (world model)
   exists in no source. EdenGolem is real (see §2) but it is an
   *agent skill that writes graybox games*, not a game-state
   interceptor in a Thor pipeline. The Cosmos layer as drawn — a
   frame-by-frame temporal "sanity check" passing "tokenized
   scene physics states" into the renderer — is not a thing
   Cosmos does in any pipeline anyone publishes.
3. **The resource matrix is numerology.** try1's totals
   (~400 GB cinematic / ~101 GB peak; "~75 GB / ~24 GB
   streamlined") do not match the real artefacts. The real
   full HF tree is ≈225 GB of files (the repo itself says
   "about 210 GB in total") — but that buys *both* DiT sizes in
   *both* modes plus the FLUX workbench. A single DiT is
   20.05 GB (5B) / 65.66 GB (14B) per variant. try1's "Wan2.2 5B
   weights ~24 GB", "Cosmos Reason2 8B NIM ~32 GB static FP8 KV
   cache", "Isaac ~60 GB / ~16 GB" have no source. Its
   streamlined profile also silently deletes the UMT5 text
   encoder (11.36 GB), the 5B VAE (2.82 GB) and the proxy-DINO
   vision encoder (~2.4 GB) that a real 5B run needs.
4. **Commands that do not exist.** `python inference.py
   --model_profile 5B_distilled --width 848 --height 480
   --steps 5 --precision fp8` (both variants in try1) is not an
   EdenLive interface; the real entry points are
   `python -m edenlive.scripts.infer --config <yaml>` and the
   `realtime/` scripts. `docker run … ghcr.io/nvidia-ai-iot/
   vllm:latest-jetson-thor --model cosmos-3-edge`, the
   SculptForge command lines (`sculptforge-cli -c 'open
   path=…; splat_to_mesh resolution=512 …'`,
   `quad_remesh target_count=…`, `export_lods …`) are likewise
   NOT FOUND — plausible-shaped strings, not documented syntax.
5. **60+ FPS on the Thor — FABRICATED.** No source gives any
   Thor FPS for anything in this stack. The honest vendor
   numbers are §2's H100/5090 figures; the streamlined profile's
   "60+ FPS (ultra-low latency line-rate)" is the chain
   extrapolating its own inventions. (Cosmos 3 Edge's real Thor
   numbers make the point by contrast: NVIDIA's card reports
   ~137 s for a 189-frame image-to-video workload on a Thor
   T5000 — seconds-per-clip territory, not a real-time layer.)
6. **Isaac Lab as the Thor's room-physics server — NOT FOUND.**
   Isaac Sim's documented requirements are an RTX GPU with RT
   cores (16 GB+ VRAM) on x86-class workstations; Jetson is the
   *deployment* target for trained policies (Isaac ROS / GR00T
   inference), not the Sim host. No source runs Isaac Sim/Lab as
   a LAN multiplayer physics server on a Jetson. The whole
   Thor-backend diagram rests on this.
7. **ScanForge is mis-scoped in the email.** It is real, but it
   is a **paid (USD 24.99), GPL-3.0 Blender add-on for
   phone-scanned *objects***, not a companion room tool: floor
   find/cut, floaters, hole closing, triangle budget with
   measured shape error, two LODs, GLB/FBX out. Its delighting
   is real and *measured* — and its own seller states the limit
   the email omits: median colour error 4.89 → 3.11 ΔE2000
   through the full pipeline, worse in 3 of 16 cases, "sharp
   contact shadows are reduced, not removed". "Mathematically
   strip out ambient lighting and contact shadows" overstates a
   partial, honestly-documented correction. It is also not
   SculptForge's companion anything — the email's pairing is a
   name-collision (two unrelated "Forge" products), and its
   licence is GPL-3.0, i.e. **not** admissible inside our
   permissive-licensed tooling (seed-1 programme ruling 3:
   never be limited by another's licence — the seam pattern
   applies, not incorporation).
8. **"Open-source weights" needs its asterisk.** EdenLive code
   is Apache-2.0 and the DiT/VAE/UMT5 weights are Apache-2.0,
   but the HF repo's licence is `other` ("edenlive-mixed") for a
   reason: the vision encoder is under the **DINOv3 licence**,
   and the workbench's first-frame renderer is **FLUX.2
   [klein] 9B under the FLUX Non-Commercial License** —
   non-commercial, non-production, with a content-filtering
   requirement. Playing games via `start.sh` does not load
   FLUX; the prompt-to-game workbench does. Any future use must
   route around the FLUX component or accept NC terms.
9. **Multi-viewpoint collaboration is an extrapolation.** The
   released realtime service is one upstream program → one
   rendered stream over WebRTC (plus a workbench). "The Thor
   computes separate model passes for different camera angles
   for each collaborator simultaneously" appears in no source,
   and at 5090-class cost per stream it is the most expensive
   sentence in the attachment.
10. **Small wrong numbers.** Thor unified memory is **122 GiB**
    on our box (the dev-kit headline 128 GB is the marketing
    figure try1 repeats). The streamlined storage total
    (~75 GB) would fit our Thor's *disk* (~89 GB free at last
    measure) but the full weight tree (~210–225 GB) would not —
    moot, since none of it runs there (item 1).

---

## 1. The seed, preserved in substance

### 1.1 The email's pipeline (refined body)

A fully local digital-twin workflow in four steps:

1. **Scan.** Capture a room's gray-box geometry with a LiDAR
   phone app, a 360 camera, or the Room Scan Exporter on Meta
   Quest 3; export a coarse OBJ/FBX mesh; transfer it to the
   Jetson Thor as the LAN hub / structural reference.
2. **Clean.** SculptForge (presented as an open-source ZBrush
   alternative) for retopology and mesh cleanup; the ScanForge
   Blender add-on for floor-finding, levelling, and delighting
   (stripping baked-in real-world lighting/shadows). Export a
   low-overhead proxy mesh or camera path as the reference
   layer.
3. **Render generatively.** EdenLive (VAST-AI) takes three
   inputs — a reference video/stream (gray-box or depth
   sequence), a styled target first frame, and a text prompt —
   and paints photorealistic video in real time at 24+ FPS via
   its `realtime/` streaming service. Weights (5B or 14B) come
   from Hugging Face; environment is Python 3.10 + PyTorch +
   CUDA 13.
4. **Collaborate locally.** coturn (TURN/STUN) on the LAN,
   `TURN_HOST`/`TURN_SECRET` in `realtime/deploy.conf`,
   `bash start.sh 5b`; collaborators join from headset, desktop
   or tablet browsers; an upstream program owns the world state
   and EdenLive re-renders on every state change.

The email closes by asking three tailoring questions (scan
device, GPU configuration, photoreal vs stylised).

### 1.2 The attachment's elaborations (try1.md)

The attachment re-answers follow-ups the body never asked, in
escalating layers — this is where most fabrications live:

- A "production architecture": Thor as headless backend running
  **NVIDIA Isaac** (simulation) → **NVIDIA Cosmos** (world
  model / temporal stabiliser) → **EdenGolem + EdenLive**
  (renderer, NVENC → WebRTC/RTMP); the ProArt as a thin-client
  "director's monitor" running a three.js workspace.
- A storage/memory matrix (~400 GB / ~101 GB peak, itemised by
  layer) and instructions to bind services to the LAN IP, put
  coturn on the Thor, and open ufw ports 3000/3478/5349.
- Thin-client stories for the HP laptop and iPad (browser-only,
  "<15% utilisation", touchscreen camera control).
- A "streamlined" performance profile: 5B only, 848×480, 4–8
  distilled steps, Cosmos disabled → claims ~24 GB footprint,
  ~75 GB storage, **60+ FPS**; with invented CLI flags.
- Multiplayer world-building: one authoritative Isaac scene,
  per-device roles (cameraman / level designer / director),
  WebSocket + WebRTC bridge, multiple simultaneous viewpoints.
- A room-twin walkthrough: iPad Gaussian-splat scan (Polycam /
  Scaniverse) → SculptForge headless MCP daemon on the Thor
  (`sculptforge-cli --mcp`, splat→mesh→retopo→LOD command
  lines) → Isaac Lab colliders → Cosmos 3 Edge container →
  EdenLive at 60+ FPS to all clients.

The attachment's * instincts* — split state from appearance,
keep clients thin, prefer the small model, cut resolution and
steps before cutting interactivity — are sound. Its specifics
are not.

---

## 2. Verification, claim by claim

Primary sources checked 2026-11-02/03: the EdenLive GitHub repo
(README + tree, HEAD pushed 2026-10-21), the HF model repo
`VAST-AI/EdenLive` (API metadata + file sizes; not gated), the
VAST project page (tripo3d.ai/research/edenlive), sculptforge
.app (incl. its CLI/MCP section), the ScanForge Superhive
listing, the Room Scan Exporter itch.io page, Jetson AI Lab /
NVIDIA Cosmos pages, and fleet records (TOOLS.md, staging
docs) for our hardware.

### 2.1 EdenLive — the spine is real

| # | Claim (seed) | Verdict | Evidence |
|---|---|---|---|
| E1 | VAST-AI's EdenLive exists, open source | **CONFIRMED** | GitHub `VAST-AI-Research/EdenLive`, created 2026-10-12, Apache-2.0, 408★; "Real-time generative rendering for interactive worlds, from any visual reference." |
| E2 | Inputs = reference video + target first frame + text prompt | **CONFIRMED** | Repo README + project page, verbatim: reference decides layout/camera/dynamics; first frame + prompt decide appearance. Event descriptions (e.g. "a hit") can also arrive mid-stream. |
| E3 | 5B and 14B weights on Hugging Face | **CONFIRMED, corrected on licence** | `VAST-AI/EdenLive`, public, **not gated**; DiTs for both sizes in bidirectional and few-step (chunk-AR) variants, plus split Diffusers repos. Licence is mixed, not plain open — see Deficit 8. |
| E4 | Real-time generative painting at 24+ FPS | **CONFIRMED as vendor claim, on vendor hardware** | Project page: "5B … 24 FPS or higher at 720p on a single GPU" + "*5B supports real-time rendering on a single NVIDIA RTX 5090*". H100 table: 73.52 FPS @ 832×480, 29.80 @ 1280×704 (model-side throughput, reference encoding included). LightX2V on one RTX 5090: ≈24.7 FPS @ 1280×704. No third-party reproduction found. |
| E5 | `realtime/` streaming service exists | **CONFIRMED** | `realtime/` in repo: service topology, WebRTC streaming, TAEHV (LightTAE) decoder, builds on NVIDIA FlashDreams. |
| E6 | `realtime/deploy.conf` with `TURN_HOST` / `TURN_SECRET` | **CONFIRMED, one addition** | README names `TURN_HOST`, **`TURN_IFACE`**, `TURN_SECRET` in `realtime/deploy.conf`; `MODEL_ROOT` also lives there. |
| E7 | coturn for local WebRTC | **CONFIRMED** | README: `apt-get install coturn`, `bash turn_server.sh` before the model service. |
| E8 | `bash start.sh 5b` starts the backend | **CONFIRMED** | README: `bash start.sh 14b  # or use 5b`; workbench needs three more scripts (`workbench_bridge.sh`, `workbench_flux.sh`, `launch.sh`) and opens on port 8089. |
| E9 | Python 3.10 + PyTorch + CUDA 13 | **CONFIRMED, sharpened** | Verified stack: Python 3.10, PyTorch cu130 (2.13 pinned for realtime), diffusers 0.39 — and **Linux x86-64, 80 GB GPU, CUDA 13 driver**. CUDA 13.2 on our Thor satisfies the *driver* line and nothing else (see §3). |
| E10 | EdenLive "decouples world simulation from rendering" | **CONFIRMED — it is the project's own thesis** | Project Eden: "State First, Rendering Follows." Upstream program/engine owns structured state; EdenLive implements the state-to-visual interface + renderer only. |
| E11 | EdenGolem | **CONFIRMED, corrected on role** | EdenGolem v0.1 is a *skill for coding agents* that turns a text prompt into a coarse playable graybox game in four checked stages (`realtime/skills/edengolem/`). It authors the upstream; it is not a runtime game-state layer, and it is not Thor software. |
| E12 | Models are Wan-based | **CONFIRMED (attachment only, by luck)** | Initialised from Wan2.2-TI2V-5B and Wan2.1-I2V-14B; visual encoder fine-tuned from DINOv3. try1's "Wan2.2 5B / Wan2.1 14B" naming is the one attachment detail that matches the sources. |
| E13 | Offline + realtime modes; minute-scale generation | **CONFIRMED** | Bidirectional (offline, joint denoise) and chunk-AR few-step (4 steps/chunk, streaming); project page claims minute-scale continuous generation. |

### 2.2 Scanning and mesh tools

| # | Claim (seed) | Verdict | Evidence |
|---|---|---|---|
| S1 | Room Scan Exporter for Meta Quest 3 exists; exports room meshes | **CONFIRMED, and better than claimed** | itch.io (zoynctech), free, fully offline, Quest 3/3S: textured mesh refined on-headset or on a Windows PC Companion, exports **OBJ+MTL+PNG or FBX+PNG**, plus PC-trained Gaussian splats viewable life-size in-headset. v0.3 current. |
| S2 | Scan via LiDAR app / 360 camera | **CONFIRMED as generic practice** | Polycam/Scaniverse-class phone scanning is exactly ScanForge's stated input class (20 real scans from six apps tested by its seller). A 360 camera alone yields imagery, not geometry — the chain elides the photogrammetry step. |
| S3 | SculptForge is an open-source ZBrush alternative on Linux | **CONFIRMED, licence corrected** | sculptforge.app: free, open source, Linux/macOS/Windows, **GPL-3.0** (not permissive); Quad Remesh, voxel remesh, map baking, OpenUSD/glTF/FBX, phone-capture → Gaussian splat training (0.9), one-click splat→watertight quad mesh. |
| S4 | SculptForge does automatic retopology / cleanup | **CONFIRMED in substance** | Quad Remesh 2 is its headline feature; "Make sculptable" turns scans into watertight quad meshes. The email's "mesh-cleaning brushes seal holes" is artist-tool language for a mostly manual sculpting app, not a batch room-cleaner — usable, but it is a sculptor's desk, not a pipeline stage. |
| S5 | SculptForge has `sculptforge-cli` + a built-in MCP server | **CONFIRMED (site), syntax NOT FOUND** | sculptforge.app: "`sculptforge-cli` runs any operation headless for build farms. Its built-in MCP server lets Claude Code, Claude Desktop or any MCP client sculpt, convert and export." The attachment's specific command grammars (`splat_to_mesh resolution=512`, `quad_remesh target_count=50000`, `export_lods …`) appear in **no** source. |
| S6 | SculptForge has built-in Hunyuan3D 2.1 / stable-fast-3d engines | **NOT FOUND as named** | The site advertises built-in AI (Brush Lab; sketch/sentence → model) without naming those engines in the checked pages. The capability class is real; the named engines are the chain's decoration. |
| S7 | ScanForge finds floor plane, levels, delights | **CONFIRMED with the seller's own limits** | Superhive listing: floor found/cut (44/44 synthetic scans, tilt within 0.02°), delighting measured at median ΔE2000 4.89 → 3.11, improved 13/16, sharp contact shadows "reduced, not removed". See Deficit 7 for scope/licence. |
| S8 | ScanForge is SculptForge's "companion" add-on | **FABRICATED (name collision)** | Unrelated products, unrelated vendors; one is a sculpting application (GPL), the other a paid Blender add-on (GPL-3.0, USD 24.99). Nothing links them. |

### 2.3 The attachment's added stack (Isaac / Cosmos / Thor)

| # | Claim (try1) | Verdict | Evidence |
|---|---|---|---|
| A1 | Isaac Lab runs on the Thor as the simulation layer | **NOT FOUND / implausible** | Deficit 6. Isaac Sim wants an RTX/RT-core workstation GPU; Jetson is the policy-deployment target. |
| A2 | Cosmos 3 Edge exists and runs on Thor via vLLM | **CONFIRMED as a product, CORRECTED as a component** | Cosmos3-Edge is real: 4B omnimodal (2.4B reasoner + diffusion tower), released 2026-07-20, Jetson AI Lab documents vLLM / vLLM-Omni serving on Thor. It is a reasoner/generator/policy model — not a temporal stabiliser stage, not 8B, not a "NIM microservice" in the documented Thor recipe, and its Thor latencies (seconds per clip) disqualify it from any per-frame role. |
| A3 | "Cosmos Reason2 8B NIM", "~32 GB static FP8 KV cache" | **FABRICATED-looking** | No such SKU/recipe found. Cosmos-Reason2 exists as a GR00T VLM backbone (2B, per NVIDIA's GR00T N1.7 notes) — a different artefact from a different stack, conflated by the chain. |
| A4 | EdenLive uses flash-attn-4 + "Blackwell tensor layouts" on Thor | **CORRECTED** | flash-attn-4 is real — as the **SM90** requirement of the default 5B bidirectional profile (Hopper). It is evidence *against* the Thor story, not for it: sm_110 is not SM90, and the kernels are x86-64 builds. |
| E4b | Thor NVENC encodes the WebRTC stream | **UNVERIFIED in the EdenLive sources** | The repo's realtime stack streams WebRTC from the GPU host; no checked source attributes the encode to a Jetson NVENC block, because no checked source runs it on a Jetson. |
| A5 | HP laptop at "<15% utilisation" as thin client; iPad touchscreen camera control | **PLAUSIBLE, UNMEASURED** | Browser WebRTC decode is genuinely cheap and the frontend is a browser app; the specific utilisation figure and the iPad role assignments are the chain's staging, not measurements. |
| A6 | Storage/memory matrices (400 GB / 101 GB; 75 GB / 24 GB) | **FABRICATED** | Deficit 3. Real file sizes are in §3.2. |
| A7 | Multi-device roles on one authoritative scene, separate viewpoints per client | **NOT FOUND** | Deficit 9. EdenGolem games are single-world; the released frontend is one stream. |

### 2.4 Score line

Of the email body's load-bearing claims: the pipeline's four
tools all exist, the EdenLive interface (E2/E5–E8) is described
accurately enough to follow, and the FPS claim is a real vendor
claim — attached to hardware the email then mis-assigns. Of the
attachment's additions: the MCP/CLI claim (S5) and the Wan
lineage (E12) check out; the Thor architecture, both resource
matrices, both command sets, the Cosmos role, and the 60+ FPS
profile do not. **The chain got the catalogue right and the
physics wrong** — the same failure shape as seed 1 (right
ingredients, invented numbers), one level up.

---

## 3. Hardware verdicts (paper only — no downloads, no installs)

Fleet facts (TOOLS.md / THOR-VERIFICATION.md): **Thor** =
Jetson AGX Thor, Blackwell iGPU **sm_110**, 14-core Neoverse
V3AE, **122 GiB unified LPDDR5X** (~273 GB/s), CUDA 13.2,
driver 595.78, NVMe 936 GB with ~89 GB free at last measure.
**ProArt** = ASUS laptop, RTX 4050 Laptop GPU (Ada, sm_89,
6 GB GDDR6 catalogue spec), already the fleet's interactive
desk (its 4050 runs the radio-room STT today).

### 3.1 EdenLive's own stated requirements

- OS/arch: **Linux x86-64**. GPU: **80 GB class** (verified
  environment line). Default 5B bidirectional profile:
  **SM90 + flash-attn-4 + CUTLASS-DSL**. 14B offline examples
  use 2 GPUs with sequence parallelism. Reactor demo: **one
  B200**. Real-time 24 FPS: **RTX 5090** (LightX2V) or H100
  numbers. Node 22 only fetches three.js.

### 3.2 Real sizes (HF API, 2026-11-02)

| Component | Size |
|---|---|
| dit-5b (few-step) | 20.05 GB |
| dit-5b-bidir | 20.05 GB |
| dit-14b (few-step) | 65.66 GB |
| dit-14b-bidir | 65.66 GB |
| umt5 text encoder | 11.36 GB |
| vae-5b / vae-14b | 2.82 / 0.51 GB |
| vision-encoder (DINOv3 proxy) | ≈2.43 GB |
| clip image encoder (14B only) | 1.26 GB |
| flux-c2f tree (workbench only) | ≈35 GB |
| **Full tree** | **≈225 GB** (repo: "about 210 GB") |
| Minimal realtime-5B subset (one DiT + umt5 + vae-5b + vision-encoder + LightTAE decoder) | ≈37 GB |

### 3.3 Thor — verdict: NO (not a performance question)

Three independent hard blockers, any one sufficient:

1. **Architecture.** The verified stack is x86-64; the Thor is
   aarch64. PyTorch cu130 wheels, flashdreams, and the FA4 /
   CUTLASS kernels have no aarch64 builds in the repo. This is
   a porting project, not a configuration.
2. **Kernel generation.** The default profile requires SM90
   kernels. Thor is sm_110 (Blackwell, but the Jetson variant);
   even the B200 Reactor path is a datacenter part with ~8×
   the memory bandwidth.
3. **Bandwidth arithmetic.** Generative video at 24 FPS is a
   memory-bandwidth workload. The 5090 that *just* makes
   24.7 FPS has ~1,792 GB/s; the Thor has ~273 GB/s — a
   ~6.5× deficit before compute is even discussed, on a model
   whose 5B DiT alone streams 20 GB of weights per pass.
   A heroic port would land in single-digit FPS at 480p, i.e.
   it would fail the seed's own purpose (real-time painting).

Memory capacity is the *only* line that passes: a minimal 5B
subset (~37 GB) fits the 122 GiB pool, and even the 14B DiT
(65.66 GB) fits on paper. Disk does not pass for the full tree
(~89 GB free < ~210 GB). **What the Thor *can* be in this
design is what it already is in ours: the hub** — state,
ledger, ingest, serving files and streams to the GPU host —
which is also the role EdenLive's own architecture assigns to
everything that is not the GPU (its bridge host is a separate
machine by design).

### 3.4 ProArt RTX 4050 — verdict: NO as the renderer, YES as the client

- VRAM: 6 GB against a 20.05 GB DiT (5B) — fails by >3× before
  the text encoder (11.36 GB) is even loaded. Quantised
  LightX2V-style conversions shrink DiTs, but no published
  EdenLive profile targets sub-24 GB cards, and the 4050 is
  sm_89 (Ada): no FA4/SM90 path either.
- As the seed's *client*, though, the ProArt is correctly cast:
  browser WebRTC decode + a three.js graybox view is light
  work, and it is already the fleet's camera/desk box. In the
  strongest version of this design (§5) the ProArt is the
  control surface and viewport — exactly the role try1 gives
  it, minus the fiction that the Thor does the rendering
  behind it.

### 3.5 The missing machine

Every working version of this pipeline needs **one x86-64
NVIDIA GPU host in the 5090/H100/B200 class (≥32 GB, ideally
80 GB)** on the LAN. The fleet does not own one. That absence —
not any software gap — is the seed's real distance from us.

---

## 4. The fit, honestly, for THIS programme

This lane is Confluence / rolling-perception / telltape: live
streams, change ledgers, presence. A room-twin world-builder is
not its centre of gravity, and most of this seed belongs
elsewhere. What follows is deliberately tight.

### 4.1 Genuinely ours (small, real)

- **State first, rendering follows — we already hold this.**
  Project Eden's split (structured state owned by a program;
  appearance generated downstream) is the same doctrine as our
  Foundry line ("seed+params ARE the asset; geometry is a
  cache") and telltape's ("the ledger is the record; footage is
  the user's"). EdenLive is external evidence that the split
  scales to photoreal video — a citation for the doctrine, not
  a component for the stack.
- **A twin is state; our ledger is change-against-state.** The
  one idea in this seed that is native to *this* programme: if
  a scanned room mesh is the baseline state, then a telltape-
  style ledger over re-scans (or over the live camera watching
  the room) is a **change record for a physical place** —
  "what moved, where in the room, when, how strongly", with
  the mesh as the seek index instead of a video timeline. The
  slice-1 soak already produces the 2D version of exactly this
  against a desk scene. A 3D variant needs no EdenLive, no
  Isaac, no Cosmos: scan (S1 is real and free) + our existing
  diff/gate machinery lifted from tiles to mesh regions. That
  is a telltape-shaped tool, and it is the only build this
  seed suggests to this lane.
- **The proxy-premise rhyme, with our measurement attached.**
  EdenLive's bet — a cheap proxy stream plus synthesis beats
  rendering/sampling the real thing — is Slice 3's thesis, and
  Slice 3 *measured* its version: the synthesiser beat the
  sampler at every lag (11× at lag 0, 8× at 10 s) on synthetic
  ground truth, with the honest costs priced (reversal recovery
  ~2 s after a state flip; everything past ~1 s labelled
  `stale`, and the label governing how a consumer may act).
  EdenLive's own report concedes the twin failure modes
  (reappearing objects lose detail; adherence is fixed, not
  user-controlled). The lesson transfers in both directions:
  their existence proof is at video scale; our contribution
  is the discipline they lack — every synthesised serve in
  our stack carries `basis` and `extrapolation_age`, i.e. a
  generated frame should say whether it is corrected,
  extrapolated, or stale. A generative room renderer without
  that labelling is a presence-grade fluency risk: it will
  paint a plausible room that is not the room, confidently,
  at 24 FPS. (Our standing rule from the judge studies:
  synthesis may advise the eye; it never sits alone on a
  consequential gate. A twin used for *viewing* is fine; a
  twin used as *evidence* about the physical room is not,
  unless its tells come from the measured ledger, not the
  painted frames.)

### 4.2 Belongs to neighbouring programmes (routing, not colonising)

- **Otherhere / the holodeck-quilt line** owns explorable
  shared places: the scan → clean → walkable-room pipeline,
  the multi-device LAN presence, the thin-client viewport
  story. Seed 2's centre of gravity is there. If Casey wants
  the twin built, it should be chartered there, with this doc
  as its verification input (and §3.5's missing GPU host as
  its first procurement question).
- **The Foundry** already owns mesh cleanup/retopology in our
  house (Blender on the Thor, mint/registry, seed+params
  doctrine). SculptForge/ScanForge are candidate *tools for
  that bench* (GPL caveats noted), not new pipeline stages
  for this lane.
- **Presence (slice 2)** owns "talk to the room about what
  changed". A room twin would be a *display surface* for its
  digest, downstream of the ledger — not a replacement for
  verdict-only grounding.

### 4.3 Fantasy at our scale

- EdenLive running on the Thor (any FPS), the Isaac→Cosmos→
  EdenLive Thor pipeline, 60+ FPS anything, multi-viewpoint
  simultaneous neural rendering, and both resource matrices.
- "Scan a room in the morning, walk its photoreal twin with
  collaborators by lunch" — every individual tool in that
  sentence exists except the renderer-on-our-hardware; the
  sentence is a procurement (a 5090-class host) plus an
  integration project, not a configuration.

---

## 5. What would have to be true (strongest honest version)

For the seed's best self — *a local, private, explorable twin
of a real room, kept current, viewable from every device in
the house* — all of the following, in dependency order:

1. **A GPU host exists.** One x86-64 Linux box with an
   RTX 5090-class card (32 GB) minimum for the 5B realtime
   profile at 720p/24 FPS per the vendor's own figures; 80 GB
   class to stop negotiating. Until this is true, every
   rendering claim in the seed is about someone else's
   machine.
2. **The renderer is used as a renderer.** EdenLive paints
   appearance over a reference owned by an upstream program.
   The twin's *truth* (geometry, object state, change
   history) must live in inspectable state — a mesh plus a
   ledger — never in generated frames. First frame + prompt
   are styling inputs, and the FLUX workbench path stays out
   (non-commercial licence) or is replaced.
3. **The scan chain is the verified one.** Room Scan Exporter
   (free, offline, OBJ/FBX out) or a phone photogrammetry app
   → cleanup in tools whose licences fit (Blender/Foundry in
   our house; SculptForge/ScanForge only as external,
   GPL-respecting steps) → a proxy the renderer can follow.
   Delighting expectations set by ScanForge's own numbers
   (partial correction), not the email's.
4. **Change is measured, not painted.** The twin stays a twin
   — rather than a diorama — only if something re-observes
   the physical room and writes the differences down: our
   ledger pattern (§4.1), with silence carrying its basis.
   Without that loop the artefact is a *model of the room as
   scanned*, ageing from the moment of capture.
5. **Collaboration starts single-stream.** One rendered
   viewpoint, many viewers (WebRTC + coturn, both real),
   roles expressed as *who controls the camera/state*, not
   as parallel neural renders. Multi-viewpoint is a later,
   separately-costed claim.
6. **The Thor plays its real role.** Hub: ingest, state,
   ledger, file/stream serving, presence — the back-room
   engine room it already is — with the GPU host as a new
   appliance beside it, not a personality transplant for it.

If items 1–3 were handed to the Otherhere lane tomorrow, the
first demonstrable artefact would be: one scanned room,
rendered photoreal at 24 FPS on the GPU host from a graybox
fly-through, viewable on the ProArt/iPad/HP browsers — the
seed's steps 1, 3 and 4 with step 2 done in Blender. That is
a real thing. It is just not this lane's thing, and it starts
with buying a graphics card, not with configuring the Thor.

---

## Sources (primary, checked 2026-11-02/03)

- Email + attachment: `docs/seed-2/email.md`,
  `docs/seed-2/try1.md` (Gmail id `1a19eda9fc1b35a1`).
- EdenLive code: github.com/VAST-AI-Research/EdenLive
  (README, `realtime/` tree, `realtime/deploy.conf`).
- EdenLive weights: huggingface.co/VAST-AI/EdenLive (API
  metadata + blob sizes; licence `other` / edenlive-mixed).
- Project page: tripo3d.ai/research/edenlive (FPS table,
  Project Eden state/rendering split, known limitations).
- SculptForge: sculptforge.app (features, CLI/MCP section,
  GPL-3.0 via its GitHub).
- ScanForge: superhivemarket.com/products/scanforge
  (USD 24.99, GPL-3.0, measured floor/delight numbers).
- Room Scan Exporter: zoynctech.itch.io/
  room-scan-exporter-for-meta-quest-3 (v0.3, OBJ/FBX, free).
- Cosmos 3 Edge: jetson-ai-lab.com/models/cosmos3-edge +
  NVIDIA/cosmos repo (4B, Thor vLLM serving, card latencies).
- Isaac requirements: NVIDIA Isaac Sim/Lab documentation and
  hardware guides as surfaced 2026-11-03 (RTX/RT-core
  workstation requirement).
- Fleet hardware: TOOLS.md (Thor door + full stack),
  docs/THOR-VERIFICATION.md, docs/RESULTS.md (Slice 3).
